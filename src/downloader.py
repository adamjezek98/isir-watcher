import os
import logging
import requests
from pathlib import Path
from typing import Optional, Tuple
from sqlalchemy import or_
from sqlalchemy.orm import Session
from src.models import (
    BeforeBankruptcyDocument,
    AfterBankruptcyDocument,
    OtherDocument,
    ApplicationDocument,
    DisputeDocument,
)

logger = logging.getLogger(__name__)


class DocumentDownloader:
    """Downloads PDF documents from ISIR website."""
    
    BASE_URL = "https://isir.justice.cz/isir/doc/dokument.PDF"
    
    def __init__(self, output_dir: str = "output/documents"):
        self.output_dir = Path(output_dir)
        self.ensure_directory()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def ensure_directory(self):
        """Create output directory if it doesn't exist."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Documents directory ensured: {self.output_dir}")
    
    def download_document(self, document_id: str) -> Tuple[Optional[int], Optional[str]]:
        """
        Download a single PDF document from ISIR.
        
        Args:
            document_id: The document ID from ISIR
            
        Returns:
            Tuple of (HTTP status code, file path if successful)
        """
        if not document_id:
            return None, None
        
        url = f"{self.BASE_URL}?id={document_id}"
        file_path = self.output_dir / f"{document_id}.pdf"
        
        # Check if file already exists
        if file_path.exists():
            logger.debug(f"Document {document_id} already exists, skipping download")
            return 200, str(file_path)
        
        try:
            logger.info(f"Downloading document {document_id} from {url}")
            response = self.session.get(url, timeout=30)
            status_code = response.status_code
            
            if status_code == 200:
                # Save the PDF
                file_path.write_bytes(response.content)
                logger.info(f"Successfully downloaded document {document_id} ({len(response.content)} bytes)")
                return status_code, str(file_path)
            else:
                logger.warning(f"Failed to download document {document_id}: HTTP {status_code}")
                return status_code, None
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout downloading document {document_id}")
            return 408, None  # Request Timeout
        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading document {document_id}: {e}")
            return 500, None  # Internal Server Error
        except Exception as e:
            logger.error(f"Unexpected error downloading document {document_id}: {e}", exc_info=True)
            return 500, None
    
    def download_pending_documents(self, db: Session):
        """
        Download all documents that need downloading or retrying.
        This includes documents where download status is NULL or not equal to 200.
        Updates the download status in the database.
        """
        logger.info("Starting download of pending documents")
        
        # Get all document models
        document_models = [
            BeforeBankruptcyDocument,
            AfterBankruptcyDocument,
            OtherDocument,
            ApplicationDocument,
            DisputeDocument,
        ]
        
        total_downloaded = 0
        total_failed = 0
        
        for model in document_models:
            model_name = model.__name__
            logger.info(f"Processing {model_name}...")
            
            # Get documents that need downloading or retrying
            # (download is NULL OR download != 200) AND document_id is not NULL
            pending_main = db.query(model).filter(
                or_(model.download.is_(None), model.download != 200),
                model.document_id.isnot(None)
            ).all()
            
            logger.info(f"Found {len(pending_main)} {model_name} main documents to download")
            
            for doc in pending_main:
                status_code, file_path = self.download_document(doc.document_id)
                doc.download = status_code
                
                if status_code == 200:
                    total_downloaded += 1
                else:
                    total_failed += 1
                
                # Commit after each document to save progress
                db.commit()
            
            # Get side documents that need downloading or retrying
            pending_side = db.query(model).filter(
                or_(model.side_download.is_(None), model.side_download != 200),
                model.side_document_id.isnot(None)
            ).all()
            
            logger.info(f"Found {len(pending_side)} {model_name} side documents to download")
            
            for doc in pending_side:
                status_code, file_path = self.download_document(doc.side_document_id)
                doc.side_download = status_code
                
                if status_code == 200:
                    total_downloaded += 1
                else:
                    total_failed += 1
                
                # Commit after each document to save progress
                db.commit()
        
        logger.info(f"Download complete: {total_downloaded} successful, {total_failed} failed")
        return total_downloaded, total_failed

