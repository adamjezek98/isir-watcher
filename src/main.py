"""Main application script for ISIR Watcher."""

import sys
import logging
from datetime import datetime, timezone
from typing import Dict, List
from sqlalchemy.orm import Session
from src.database import SessionLocal, init_db
from src.models import (
    WatchedEntity,
    BeforeBankruptcyDocument,
    AfterBankruptcyDocument,
    OtherDocument,
    ApplicationDocument,
    DisputeDocument
)
from src.scraper import ISIRScraper, NotFoundError
from src.report_generator import ReportGenerator
from src.downloader import DocumentDownloader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('isir_watcher.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Initialize scraper
scraper = ISIRScraper()


def process_documents(
    db: Session,
    entity: WatchedEntity,
    scraped_docs: List[Dict],
    existing_docs: List,
    doc_class
) -> List[Dict]:
    """
    Process documents of a specific type.
    
    Note: ISIR reuses document IDs! When a document is deleted, its ID can be 
    reused for a new document. We match documents by (isir_document_id, document_id)
    pair to avoid duplicates.
    
    Args:
        db: Database session
        entity: WatchedEntity instance
        scraped_docs: List of scraped document dictionaries
        existing_docs: List of existing documents from database
        doc_class: Document model class to use
    
    Returns:
        List of change dictionaries for changelog
    """
    changes = []
    
    # Group existing documents by isir_document_id
    existing_by_isir_id = {}
    for doc in existing_docs:
        if doc.isir_document_id not in existing_by_isir_id:
            existing_by_isir_id[doc.isir_document_id] = []
        existing_by_isir_id[doc.isir_document_id].append(doc)
    
    # Process each scraped document
    for scraped_doc in scraped_docs:
        isir_doc_id = scraped_doc['isir_document_id']
        scraped_pdf_id = scraped_doc.get('document_id')
        is_scraped_deleted = scraped_doc.get('is_deleted', False)
        
        # Get all existing documents with this ISIR ID
        existing_versions = existing_by_isir_id.get(isir_doc_id, [])
        
        # Check if we already have this exact version in the database
        # Match by (isir_document_id, document_id) pair
        found_match = False
        for existing_doc in existing_versions:
            if existing_doc.document_id == scraped_pdf_id:
                # Found matching document
                found_match = True
                
                # Check if it became deleted
                if is_scraped_deleted and not existing_doc.is_deleted:
                    existing_doc.is_deleted = 1
                    logger.info(f"Document marked as deleted: {isir_doc_id} for entity {entity.name}")
                    changes.append({
                        'entity_name': entity.name,
                        'entity_isir_id': entity.isir_id,
                        'change_type': 'deleted',
                        'document_id': isir_doc_id,
                        'document_type': scraped_doc.get('document_type'),
                        'description': scraped_doc.get('description'),
                        'publish_date': scraped_doc.get('publish_date'),
                        'silent': entity.silent,
                    })
                break
        
        if not found_match:
            # This is a new version we haven't seen before
            # But before adding, check if it's a deleted document (no PDF ID)
            if not scraped_pdf_id and is_scraped_deleted:
                # Check if we already have a deleted version with no PDF ID
                has_deleted_no_pdf = any(
                    not doc.document_id and doc.is_deleted 
                    for doc in existing_versions
                )
                if has_deleted_no_pdf:
                    # We already recorded this deleted state, skip it
                    continue
            
            # Add this new version
            new_doc = doc_class(
                watched_entity_id=entity.id,
                isir_document_id=scraped_doc['isir_document_id'],
                document_type=scraped_doc.get('document_type'),
                publish_date=scraped_doc.get('publish_date'),
                description=scraped_doc.get('description'),
                document_id=scraped_doc.get('document_id'),
                side_document_id=scraped_doc.get('side_document_id'),
                legally_binding_date=scraped_doc.get('legally_binding_date'),
                senat_number=scraped_doc.get('senat_number'),
                is_deleted=1 if is_scraped_deleted else 0
            )
            
            # Add type-specific fields
            if doc_class == ApplicationDocument and scraped_doc.get('creditor'):
                new_doc.creditor = scraped_doc['creditor']
            elif doc_class == DisputeDocument and scraped_doc.get('dispute_number'):
                new_doc.dispute_number = scraped_doc['dispute_number']
            
            db.add(new_doc)
            
            if existing_versions:
                # Mark old active versions as deleted if we're adding a new active one
                if not is_scraped_deleted:
                    for old_doc in existing_versions:
                        if not old_doc.is_deleted:
                            old_doc.is_deleted = 1
                            logger.info(f"Document {isir_doc_id} replaced (old version marked deleted) for entity {entity.name}")
                    logger.info(f"New document found (reused ID): {isir_doc_id} for entity {entity.name}")
                    changes.append({
                        'entity_name': entity.name,
                        'entity_isir_id': entity.isir_id,
                        'change_type': 'new',
                        'document_id': isir_doc_id,
                        'document_type': scraped_doc.get('document_type'),
                        'description': scraped_doc.get('description'),
                        'publish_date': scraped_doc.get('publish_date'),
                        'silent': entity.silent,
                    })
                else:
                    logger.info(f"New document found (already deleted): {isir_doc_id} for entity {entity.name}")
                    changes.append({
                        'entity_name': entity.name,
                        'entity_isir_id': entity.isir_id,
                        'change_type': 'new',
                        'document_id': isir_doc_id,
                        'document_type': scraped_doc.get('document_type'),
                        'description': scraped_doc.get('description'),
                        'publish_date': scraped_doc.get('publish_date'),
                        'silent': entity.silent,
                    })
            else:
                if is_scraped_deleted:
                    logger.info(f"New document found (already deleted): {isir_doc_id} for entity {entity.name}")
                else:
                    logger.info(f"New document found: {isir_doc_id} for entity {entity.name}")
                changes.append({
                    'entity_name': entity.name,
                    'entity_isir_id': entity.isir_id,
                    'change_type': 'new',
                    'document_id': isir_doc_id,
                    'document_type': scraped_doc.get('document_type'),
                    'description': scraped_doc.get('description'),
                    'publish_date': scraped_doc.get('publish_date'),
                    'silent': entity.silent,
                })
    
    return changes


def check_entity(db: Session, entity: WatchedEntity) -> List[Dict]:
    """
    Check a single entity for changes.
    
    Returns:
        List of changes detected for this entity
    """
    logger.info(f"Checking entity: {entity.name} (ISIR ID: {entity.isir_id})")
    
    all_changes = []
    
    try:
        # Scrape documents from ISIR website
        try:
            scraped_data = scraper.scrape_entity_documents(entity.isir_id)
        except NotFoundError as e:
            logger.error(f"Error scraping documents for entity {entity.name}: {e}")
            return [{
                'entity_name': entity.name,
                'entity_isir_id': entity.isir_id,
                'change_type': 'INVALID_LINK',
            }]
        
        if not scraped_data:
            logger.warning(f"No data scraped for entity {entity.name}")
            return all_changes
        
        # Process each document type and collect changes
        changes = process_documents(
            db, entity,
            scraped_data.get('before_bankruptcy', []),
            entity.before_bankruptcy_docs,
            BeforeBankruptcyDocument
        )
        all_changes.extend(changes)
        
        changes = process_documents(
            db, entity,
            scraped_data.get('after_bankruptcy', []),
            entity.after_bankruptcy_docs,
            AfterBankruptcyDocument
        )
        all_changes.extend(changes)
        
        changes = process_documents(
            db, entity,
            scraped_data.get('other', []),
            entity.other_docs,
            OtherDocument
        )
        all_changes.extend(changes)
        
        changes = process_documents(
            db, entity,
            scraped_data.get('applications', []),
            entity.application_docs,
            ApplicationDocument
        )
        all_changes.extend(changes)
        
        changes = process_documents(
            db, entity,
            scraped_data.get('disputes', []),
            entity.dispute_docs,
            DisputeDocument
        )
        all_changes.extend(changes)
        
        # Update last_checked timestamp
        entity.last_checked = datetime.now(timezone.utc)
        
        # Update last_modified if there were any changes
        # Use the latest publish_date from changes, fallback to now if not available
        if all_changes:
            # Get all publish dates from changes
            change_dates = [
                change.get('publish_date') 
                for change in all_changes 
                if change.get('publish_date')
            ]
            
            if change_dates:
                # Use the latest document publish date as last_modified
                entity.last_modified = max(change_dates)
            else:
                # Fallback to now if no publish dates available
                entity.last_modified = datetime.now(timezone.utc)
        
        # Commit all changes
        db.commit()
        
        logger.info(f"Completed check for entity: {entity.name} - {len(all_changes)} changes detected")
        
        return all_changes
        
    except Exception as e:
        logger.error(f"Error checking entity {entity.name}: {e}", exc_info=True)
        db.rollback()
        raise


def run_checks():
    """Run checks for all watched entities and generate reports."""
    logger.info("Starting ISIR Watcher checks")
    
    db = SessionLocal()
    report_gen = ReportGenerator()
    downloader = DocumentDownloader()
    all_changes = []
    
    try:
        # Get all watched entities
        entities = db.query(WatchedEntity).all()
        
        if not entities:
            logger.info("No entities to check")
            return
        
        logger.info(f"Found {len(entities)} entities to check")
        
        invalid_link_isir_ids = set()
        
        # Check each entity and collect changes
        for entity in entities:
            try:
                changes = check_entity(db, entity)
                all_changes.extend(changes)
                
                invalid_link = any(
                    c.get('change_type') == 'INVALID_LINK' for c in changes
                )
                if invalid_link:
                    invalid_link_isir_ids.add(entity.isir_id)
                report_gen.generate_entity_report(db, entity, invalid_link=invalid_link)
                
            except Exception as e:
                logger.error(f"Error checking entity {entity.name}: {e}", exc_info=True)
                continue
        
        # Generate index page with all entities
        report_gen.generate_index(db, invalid_link_isir_ids=invalid_link_isir_ids)
        
        # Generate changelog if there were any changes
        if all_changes:
            logger.info(f"Generating changelog with {len(all_changes)} total changes")
            report_gen.generate_changelog(all_changes)
        else:
            logger.info("No changes detected")
        
        logger.info("Completed all checks")
        
        # Download pending documents
        logger.info("Starting document downloads")
        downloaded, failed = downloader.download_pending_documents(db)
        logger.info(f"Document downloads complete: {downloaded} successful, {failed} failed")
        
    except Exception as e:
        logger.error(f"Error during check run: {e}", exc_info=True)
        raise
    finally:
        db.close()


def main():
    """Main entry point."""
    logger.info("Initializing database")
    init_db()
    
    logger.info("Running checks")
    run_checks()
    
    logger.info("Done")


if __name__ == "__main__":
    main()

