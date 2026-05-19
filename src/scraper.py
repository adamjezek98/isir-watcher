"""ISIR website scraper for extracting document information."""

import logging
from typing import List, Dict, Optional
from datetime import datetime
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Base URL for ISIR entity details
ISIR_BASE_URL = "https://isir.justice.cz/isir/ueu/evidence_upadcu_detail.do"


class NotFoundError(Exception):
    """Raised when the ISIR entity page does not exist (invalid link)."""


class ISIRScraper:
    """Scraper for extracting document information from ISIR website."""
    
    def __init__(self, timeout: int = 30):
        """
        Initialize the ISIR scraper.
        
        Args:
            timeout: Request timeout in seconds
        """
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
    
    def fetch_entity_page(self, isir_id: str) -> Optional[BeautifulSoup]:
        """
        Fetch the ISIR entity detail page.
        
        Args:
            isir_id: The ISIR entity ID
            
        Returns:
            BeautifulSoup object or None if fetch failed
        """
        url = f"{ISIR_BASE_URL}?id={isir_id}&pageA=all&pageB=all&pageC=all&pageD=all&pageP=all"
        
        try:
            logger.info(f"Fetching ISIR page for entity: {isir_id}")
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            
            # Check if we got valid content
            if not response.text or len(response.text) < 100:
                logger.error(f"Received empty or too short response for entity {isir_id}")
                return None

            if "Zvolili jste neplatný odkaz." in response.text:
                logger.error(f"Invalid link for entity {isir_id}")
                raise NotFoundError(f"Invalid link for entity {isir_id}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            return soup
            
        except requests.RequestException as e:
            logger.error(f"Error fetching ISIR page for entity {isir_id}: {e}")
            return None
    
    def extract_documents_from_table(self, table, doc_type: str = 'generic') -> List[Dict]:
        """
        Extract document information from a table.
        
        Generic documents table structure (Oddíl A, B, D):
        - Column 0: isir_document_id (e.g., "1 -")
        - Column 1: publish_date (date part, e.g., "21.11.2025")
        - Column 2: publish_date (time part, e.g., "06:41")
        - Column 3: description
        - Column 4: document_type (hidden, e.g., "I_63")
        - Column 5: document link (href="/isir/doc/dokument.PDF?id=51254100")
        - Column 6: side_document link (href="/isir/doc/dokument.PDF?id=51254101")
        - Column 7: legally_binding_date
        - Column 8: senat_number
        
        Applications/Disputes table structure (Oddíl P, C):
        - Columns 0-7: same as generic
        - Column 8: creditor (applications) or dispute_number (disputes)
        - Column 9: senat_number
        
        Args:
            table: BeautifulSoup table element
            doc_type: Type of document table ('generic', 'application', or 'dispute')
            
        Returns:
            List of document dictionaries
        """
        documents = []
        
        if not table:
            return documents
        
        # Find all rows in the table body
        rows = table.find_all('tr')
        
        for row in rows:
            try:
                # Extract cells
                cells = row.find_all('td')
                
                if len(cells) < 3:
                    continue
                
                # Column 0: Extract document ID (format like "P1 - 1." or "1 -")
                # Handle newlines and extra whitespace in the cell
                doc_id_cell = cells[0].get_text(separator=' ', strip=True)
                # Collapse multiple spaces into one
                doc_id_cell = ' '.join(doc_id_cell.split())
                
                # Skip if this is a header row or empty
                if not doc_id_cell or doc_id_cell.startswith('Okamžik'):
                    continue
                
                # Keep the full ID (e.g., "P1 - 1." or "1 - 1.")
                isir_doc_id = doc_id_cell
                
                # Columns 1-2: Extract publish date (date in col 1, time in col 2)
                date_text = cells[1].get_text(strip=True) if len(cells) > 1 else None
                time_text = cells[2].get_text(strip=True) if len(cells) > 2 else None
                
                # Combine date and time
                datetime_text = None
                if date_text and time_text:
                    datetime_text = f"{date_text} {time_text}"
                elif date_text:
                    datetime_text = date_text
                
                publish_date = self._parse_date(datetime_text)
                
                # Column 3: Description
                description = cells[3].get_text(strip=True) if len(cells) > 3 else None
                
                # Column 4: Document type (e.g., "I_63")
                document_type = cells[4].get_text(strip=True) if len(cells) > 4 else None
                
                # Column 5: Document link - extract ID from href or detect "není k dispozici"
                document_id = None
                is_document_deleted = False
                if len(cells) > 5:
                    cell_text = cells[5].get_text(strip=True)
                    if 'není k dispozici' in cell_text.lower():
                        is_document_deleted = True
                    else:
                        link = cells[5].find('a', href=True)
                        if link:
                            document_id = self._extract_document_id_from_link(link['href'])
                
                # Column 6: Side document link - extract ID from href or detect "není k dispozici"
                side_document_id = None
                if len(cells) > 6:
                    cell_text = cells[6].get_text(strip=True)
                    if 'není k dispozici' in cell_text.lower():
                        is_document_deleted = True
                    else:
                        link = cells[6].find('a', href=True)
                        if link:
                            side_document_id = self._extract_document_id_from_link(link['href'])
                
                # Column 7: Legally binding date
                legally_binding_date = None
                if len(cells) > 7:
                    date_text = cells[7].get_text(strip=True)
                    # Sometimes dates are duplicated like "25.05.202325.05.2023" or "25.05.2023 25.05.2023"
                    # Just take the first one
                    if date_text:
                        # If there's whitespace, split and take first
                        if ' ' in date_text:
                            date_text = date_text.split()[0]
                        # If it's exactly 20 chars, it's two dates concatenated (DD.MM.YYYY is 10 chars)
                        elif len(date_text) == 20:
                            date_text = date_text[:10]
                    legally_binding_date = self._parse_date(date_text)
                
                # For applications and disputes, there's an extra column before senat_number
                creditor = None
                dispute_number = None
                senat_number = None
                
                if doc_type == 'application':
                    # Column 8: Creditor (for applications)
                    if len(cells) > 8:
                        creditor = cells[8].get_text(strip=True) or None
                    # Column 9: Senat number
                    if len(cells) > 9:
                        senat_number = cells[9].get_text(strip=True) or None
                elif doc_type == 'dispute':
                    # Column 8: Dispute number (for disputes)
                    if len(cells) > 8:
                        dispute_number = cells[8].get_text(strip=True) or None
                    # Column 9: Senat number
                    if len(cells) > 9:
                        senat_number = cells[9].get_text(strip=True) or None
                else:
                    # Generic documents: Column 8 is senat_number
                    if len(cells) > 8:
                        senat_number = cells[8].get_text(strip=True) or None
                
                doc_info = {
                    'isir_document_id': isir_doc_id,
                    'document_type': document_type,
                    'publish_date': publish_date,
                    'description': description,
                    'document_id': document_id,
                    'side_document_id': side_document_id,
                    'legally_binding_date': legally_binding_date,
                    'senat_number': senat_number,
                    'creditor': creditor,
                    'dispute_number': dispute_number,
                    'is_deleted': is_document_deleted,
                }
                
                documents.append(doc_info)
                
            except Exception as e:
                logger.warning(f"Error parsing row: {e}")
                continue
        
        return documents
    
    def _extract_document_id_from_link(self, href: str) -> Optional[str]:
        """
        Extract document ID from ISIR document link.
        
        Args:
            href: Link like "/isir/doc/dokument.PDF?id=51254100"
            
        Returns:
            Document ID (e.g., "51254100") or None
        """
        if not href:
            return None
        
        # Extract id parameter from URL
        if '?id=' in href:
            return href.split('?id=')[1].split('&')[0]
        
        return None
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse Czech date format to datetime.
        
        Args:
            date_str: Date string (e.g., "21.11.2025" or "21.11.2025 06:41")
            
        Returns:
            datetime object or None
        """
        if not date_str:
            return None
        
        # Try different date formats
        formats = [
            '%d.%m.%Y',
            '%d.%m.%Y %H:%M',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def scrape_entity_documents(self, isir_id: str) -> Dict[str, List[Dict]]:
        """
        Scrape all documents for an entity.
        
        Args:
            isir_id: The ISIR entity ID
            
        Returns:
            Dictionary mapping section names to lists of documents
        """
        soup = self.fetch_entity_page(isir_id)
        
        if not soup:
            return {}
        
        result = {
            'before_bankruptcy': [],
            'after_bankruptcy': [],
            'disputes': [],
            'other': [],
            'applications': [],
        }
        
        # Map div IDs to document types and their table type
        section_mapping = {
            'zalozkaA': ('before_bankruptcy', 'generic'),  # Oddíl A - Řízení do úpadku
            'zalozkaB': ('after_bankruptcy', 'generic'),   # Oddíl B - Řízení po úpadku
            'zalozkaC': ('disputes', 'dispute'),           # Oddíl C - Incidenční spory
            'zalozkaD': ('other', 'generic'),              # Oddíl D - Ostatní
            'zalozkaP': ('applications', 'application'),   # Oddíl P - Přihlášky
        }
        
        for div_id, (doc_type, table_type) in section_mapping.items():
            # Find the div with the specified ID
            div = soup.find('div', id=div_id)
            
            if not div:
                logger.debug(f"Section {div_id} not found for entity {isir_id}")
                continue
            
            # Find the table with class evidenceUpadcuDetailTable
            table = div.find('table', class_='evidenceUpadcuDetailTable')
            
            if not table:
                logger.debug(f"Table not found in section {div_id} for entity {isir_id}")
                continue
            
            # Extract documents from the table with the appropriate table type
            documents = self.extract_documents_from_table(table, table_type)
            result[doc_type] = documents
            
            logger.info(f"Found {len(documents)} documents in section {div_id} for entity {isir_id}")
        
        return result

