import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict
from sqlalchemy.orm import Session
from src.models import (
    WatchedEntity,
    BeforeBankruptcyDocument,
    AfterBankruptcyDocument,
    OtherDocument,
    ApplicationDocument,
    DisputeDocument,
)
from src.config import get_report_url

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates HTML reports and changelog for watched entities."""
    
    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.documents_dir = self.output_dir / "documents"
        self.ensure_directories()
    
    def ensure_directories(self):
        """Create output directories if they don't exist."""
        self.output_dir.mkdir(exist_ok=True)
        self.documents_dir.mkdir(exist_ok=True)
        logger.info(f"Output directories ensured: {self.output_dir}")
    
    def generate_index(self, db: Session):
        """Generate index page with overview of all watched entities."""
        logger.info("Generating index page")
        
        # Get all watched entities sorted by last_modified
        entities = db.query(WatchedEntity).order_by(
            WatchedEntity.last_modified.desc()
        ).all()
        
        if not entities:
            logger.info("No entities to include in index")
            return
        
        # Collect entity data
        entity_data = []
        for entity in entities:
            # Count documents
            doc_count = (
                db.query(BeforeBankruptcyDocument).filter_by(watched_entity_id=entity.id).count() +
                db.query(AfterBankruptcyDocument).filter_by(watched_entity_id=entity.id).count() +
                db.query(OtherDocument).filter_by(watched_entity_id=entity.id).count() +
                db.query(ApplicationDocument).filter_by(watched_entity_id=entity.id).count() +
                db.query(DisputeDocument).filter_by(watched_entity_id=entity.id).count()
            )
            
            # Get latest 3 documents across all types with section info
            all_docs_with_section = []
            
            # Get documents from each type and tag with section letter
            for doc in db.query(BeforeBankruptcyDocument).filter_by(
                watched_entity_id=entity.id
            ).order_by(BeforeBankruptcyDocument.publish_date.desc()).limit(3).all():
                all_docs_with_section.append(('A', doc))
            
            for doc in db.query(AfterBankruptcyDocument).filter_by(
                watched_entity_id=entity.id
            ).order_by(AfterBankruptcyDocument.publish_date.desc()).limit(3).all():
                all_docs_with_section.append(('B', doc))
            
            for doc in db.query(OtherDocument).filter_by(
                watched_entity_id=entity.id
            ).order_by(OtherDocument.publish_date.desc()).limit(3).all():
                all_docs_with_section.append(('C', doc))
            
            for doc in db.query(ApplicationDocument).filter_by(
                watched_entity_id=entity.id
            ).order_by(ApplicationDocument.publish_date.desc()).limit(3).all():
                all_docs_with_section.append(('D', doc))
            
            for doc in db.query(DisputeDocument).filter_by(
                watched_entity_id=entity.id
            ).order_by(DisputeDocument.publish_date.desc()).limit(3).all():
                all_docs_with_section.append(('P', doc))
            
            # Sort all documents by publish date and take top 3
            all_docs_with_section.sort(key=lambda x: x[1].publish_date, reverse=True)
            latest_docs = all_docs_with_section[:3]
            
            entity_data.append({
                'entity': entity,
                'doc_count': doc_count,
                'latest_docs': latest_docs
            })
        
        # Generate HTML
        html = self._generate_index_html(entity_data)
        
        # Write to file
        index_path = self.output_dir / "index.html"
        index_path.write_text(html, encoding='utf-8')
        logger.info(f"Index page generated: {index_path}")
    
    def generate_entity_report(self, db: Session, entity: WatchedEntity):
        """Generate HTML report for a single entity."""
        logger.info(f"Generating report for entity: {entity.name}")
        
        # Fetch all documents for this entity
        before_bankruptcy = db.query(BeforeBankruptcyDocument).filter_by(
            watched_entity_id=entity.id
        ).order_by(BeforeBankruptcyDocument.publish_date.desc()).all()
        
        after_bankruptcy = db.query(AfterBankruptcyDocument).filter_by(
            watched_entity_id=entity.id
        ).order_by(AfterBankruptcyDocument.publish_date.desc()).all()
        
        other_docs = db.query(OtherDocument).filter_by(
            watched_entity_id=entity.id
        ).order_by(OtherDocument.publish_date.desc()).all()
        
        applications = db.query(ApplicationDocument).filter_by(
            watched_entity_id=entity.id
        ).order_by(ApplicationDocument.publish_date.desc()).all()
        
        disputes = db.query(DisputeDocument).filter_by(
            watched_entity_id=entity.id
        ).order_by(DisputeDocument.publish_date.desc()).all()
        
        # Generate HTML
        html = self._generate_html(
            entity,
            before_bankruptcy,
            after_bankruptcy,
            other_docs,
            applications,
            disputes
        )
        
        # Write to file
        report_path = self.output_dir / f"{entity.isir_id}.html"
        report_path.write_text(html, encoding='utf-8')
        logger.info(f"Report generated: {report_path}")
    
    def _generate_html(
        self,
        entity: WatchedEntity,
        before_bankruptcy: List,
        after_bankruptcy: List,
        other_docs: List,
        applications: List,
        disputes: List
    ) -> str:
        """Generate HTML content for entity report."""
        
        # Generate ISIR URL for this entity
        isir_url = f"https://isir.justice.cz/isir/ueu/evidence_upadcu_detail.do?id={entity.isir_id}"
        
        html = f"""<!DOCTYPE html>
<html lang="cs">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{entity.name} - ISIR Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background-color: #2c3e50;
            color: white;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0 0 10px 0;
        }}
        .header .info {{
            font-size: 14px;
            opacity: 0.9;
        }}
        .header a {{
            color: #3498db;
            text-decoration: none;
            background-color: rgba(52, 152, 219, 0.2);
            padding: 5px 10px;
            border-radius: 3px;
            display: inline-block;
            margin-top: 5px;
        }}
        .header a:hover {{
            background-color: rgba(52, 152, 219, 0.3);
        }}
        .section {{
            background-color: white;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 5px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            margin-top: 0;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: bold;
            color: #2c3e50;
        }}
        tr:hover {{
            background-color: #f8f9fa;
        }}
        .deleted {{
            background-color: #ffe6e6;
            text-decoration: line-through;
            opacity: 0.7;
        }}
        .document-link {{
            color: #3498db;
            text-decoration: none;
            padding: 3px 8px;
            background-color: #e3f2fd;
            border-radius: 3px;
            font-size: 12px;
            display: inline-block;
            margin: 2px;
        }}
        .document-link:hover {{
            background-color: #bbdefb;
        }}
        .isir-link {{
            color: #9c27b0;
            text-decoration: none;
            padding: 3px 8px;
            background-color: #f3e5f5;
            border-radius: 3px;
            font-size: 12px;
            display: inline-block;
            margin: 2px;
        }}
        .isir-link:hover {{
            background-color: #e1bee7;
        }}
        .not-available {{
            color: #999;
            font-style: italic;
            font-size: 12px;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 11px;
            font-weight: bold;
        }}
        .badge-deleted {{
            background-color: #f44336;
            color: white;
        }}
        .badge-active {{
            background-color: #4caf50;
            color: white;
        }}
        .stats {{
            display: flex;
            gap: 20px;
            margin-top: 10px;
        }}
        .stat-box {{
            background-color: #e3f2fd;
            padding: 10px 15px;
            border-radius: 5px;
            text-decoration: none;
            display: block;
            transition: all 0.2s ease;
            cursor: pointer;
        }}
        .stat-box:hover {{
            background-color: #bbdefb;
            transform: translateY(-2px);
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }}
        .stat-box .number {{
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
        }}
        .stat-box .label {{
            font-size: 12px;
            color: #666;
        }}
        html {{
            scroll-behavior: smooth;
        }}
        .latest-highlight {{
            background-color: #fff9c4;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{entity.name}</h1>
        <div class="info">
            <div>ISIR ID: {entity.isir_id}</div>
            <div><a href="{isir_url}" target="_blank">View on ISIR →</a></div>
            <div>Last Checked: {entity.last_checked.strftime('%Y-%m-%d %H:%M:%S') if entity.last_checked else 'Never'}</div>
            <div>Report Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</div>
        </div>
    </div>
    
    <div class="section">
        <h2>Summary</h2>
        <div class="stats">
            <a href="#section-a" class="stat-box">
                <div class="number">{len(before_bankruptcy)}</div>
                <div class="label">Before Bankruptcy (A)</div>
            </a>
            <a href="#section-b" class="stat-box">
                <div class="number">{len(after_bankruptcy)}</div>
                <div class="label">After Bankruptcy (B)</div>
            </a>
             <a href="#section-c" class="stat-box">
                <div class="number">{len(disputes)}</div>
                <div class="label">Disputes (C)</div>
            </a>
           <a href="#section-d" class="stat-box">
                <div class="number">{len(other_docs)}</div>
                <div class="label">Other Documents (D)</div>
            </a>
            <a href="#section-p" class="stat-box">
                <div class="number">{len(applications)}</div>
                <div class="label">Applications (P)</div>
            </a>
        </div>
    </div>
"""
        
        # Add latest documents section (top 10 by publish date)
        all_docs_with_section = []
        for doc in before_bankruptcy:
            all_docs_with_section.append(('A', doc, False, False))
        for doc in after_bankruptcy:
            all_docs_with_section.append(('B', doc, False, False))
        for doc in disputes:
            all_docs_with_section.append(('C', doc, False, True))
        for doc in other_docs:
            all_docs_with_section.append(('D', doc, False, False))
        for doc in applications:
            all_docs_with_section.append(('P', doc, True, False))

        
        # Sort by publish date and take top 10
        all_docs_with_section.sort(key=lambda x: x[1].publish_date if x[1].publish_date else datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        latest_docs = all_docs_with_section[:10]
        
        if latest_docs:
            html += self._generate_latest_documents_section(latest_docs)
        
        # Add sections for each document type
        if before_bankruptcy:
            html += self._generate_document_section("Section A - Before Bankruptcy Documents", 
            before_bankruptcy, section_letter='A', section_id='section-a')
        
        if after_bankruptcy:
            html += self._generate_document_section("Section B - After Bankruptcy Documents",
             after_bankruptcy, section_letter='B', section_id='section-b')
        
        if disputes:
            html += self._generate_document_section("Section C - Dispute Documents",
             disputes, section_letter='C', section_id='section-c', show_dispute_number=True)

        if other_docs:
            html += self._generate_document_section("Section D - Other Documents",
             other_docs, section_letter='D', section_id='section-d')
        
        if applications:
            html += self._generate_document_section("Section P - Application Documents",
             applications, section_letter='P', section_id='section-p', show_creditor=True)
        
        
        html += """
</body>
</html>
"""
        return html
    
    def _generate_latest_documents_section(self, latest_docs: List) -> str:
        """Generate HTML for latest documents section."""
        
        html = """
    <div class="section">
        <h2>Latest Documents (Top 10)</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Published</th>
                    <th>Description</th>
                    <th>Documents</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for section_letter, doc, show_creditor, show_dispute_number in latest_docs:
            row_class = "deleted latest-highlight" if doc.is_deleted else "latest-highlight"
            
            publish_date = doc.publish_date.strftime('%Y-%m-%d %H:%M') if doc.publish_date else 'N/A'
            
            # Get HTML-formatted document ID
            display_id = doc.get_html_document_id()
            
            # Generate document links (both local and ISIR)
            doc_links = self._generate_document_links(doc)
            
            # Add creditor or dispute number to description if applicable
            description = doc.description or ''
            if show_creditor and doc.creditor:
                description += f" [Creditor: {doc.creditor}]"
            if show_dispute_number and doc.dispute_number:
                description += f" [Dispute #: {doc.dispute_number}]"
            
            html += f"""
                <tr class="{row_class}">
                    <td>{display_id}</td>
                    <td>{publish_date}</td>
                    <td>{description}</td>
                    <td>{doc_links}</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
    </div>
"""
        return html
    
    def _generate_document_links(self, doc) -> str:
        """Generate HTML for document download links (both local and ISIR)."""
        doc_links = ""
        
        # Local main PDF link
        if doc.document_id:
            doc_filename = f"{doc.document_id}.pdf"
            doc_links += f'<a href="documents/{doc_filename}" class="document-link">📥 Main</a>'
            # ISIR main PDF link
            isir_main_url = f"https://isir.justice.cz/isir/doc/dokument.PDF?id={doc.document_id}"
            doc_links += f' <a href="{isir_main_url}" target="_blank" class="isir-link">🔗 Main (ISIR)</a>'
        else:
            doc_links += '<span class="not-available">No PDF</span>'
        
        # Local side PDF link
        if doc.side_document_id:
            side_doc_filename = f"{doc.side_document_id}.pdf"
            doc_links += f' <a href="documents/{side_doc_filename}" class="document-link">📥 Side</a>'
            # ISIR side PDF link
            isir_side_url = f"https://isir.justice.cz/isir/doc/dokument.PDF?id={doc.side_document_id}"
            doc_links += f' <a href="{isir_side_url}" target="_blank" class="isir-link">🔗 Side (ISIR)</a>'
        
        return doc_links
    
    def _generate_document_section(
        self,
        title: str,
        documents: List,
        section_letter: str = '',
        section_id: str = '',
        show_creditor: bool = False,
        show_dispute_number: bool = False
    ) -> str:
        """Generate HTML for a document section."""
        
        section_id_attr = f' id="{section_id}"' if section_id else ''
        
        html = f"""
    <div class="section"{section_id_attr}>
        <h2>{title}</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Published</th>
                    <th>Description</th>
                    {'<th>Creditor</th>' if show_creditor else ''}
                    {'<th>Dispute #</th>' if show_dispute_number else ''}
                    <th>Documents</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for doc in documents:
            row_class = "deleted" if doc.is_deleted else ""
            
            publish_date = doc.publish_date.strftime('%Y-%m-%d %H:%M') if doc.publish_date else 'N/A'
            
            # Get HTML-formatted document ID
            display_id = doc.get_html_document_id()
            
            # Generate document links (both local and ISIR)
            doc_links = self._generate_document_links(doc)
            
            html += f"""
                <tr class="{row_class}">
                    <td>{display_id}</td>
                    <td>{publish_date}</td>
                    <td>{doc.description or ''}</td>
"""
            
            if show_creditor:
                html += f"                    <td>{doc.creditor or 'N/A'}</td>\n"
            
            if show_dispute_number:
                html += f"                    <td>{doc.dispute_number or 'N/A'}</td>\n"
            
            html += f"""
                    <td>{doc_links}</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
    </div>
"""
        return html
    
    def _generate_index_html(self, entity_data: List[Dict]) -> str:
        """Generate HTML for the index page."""
        
        total_entities = len(entity_data)
        total_documents = sum(e['doc_count'] for e in entity_data)
        timestamp = datetime.now(timezone.utc).strftime('%d.%m.%Y %H:%M:%S UTC')
        
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ISIR Watcher - Entity Overview</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background-color: #f5f5f5;
            padding: 20px;
            line-height: 1.6;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 {
            color: #2c3e50;
            margin-bottom: 10px;
            font-size: 32px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        .stats-summary {
            display: flex;
            gap: 15px;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            justify-content: center;
            flex-wrap: wrap;
        }
        .summary-box {
            background-color: #f8f9fa;
            color: #666;
            padding: 10px 20px;
            border-radius: 5px;
            text-align: center;
        }
        .summary-box .number {
            font-size: 20px;
            font-weight: 600;
            color: #2c3e50;
            margin-right: 5px;
        }
        .summary-box .label {
            font-size: 13px;
            color: #7f8c8d;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th {
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid #e0e0e0;
            vertical-align: top;
        }
        tr:hover {
            background-color: #f8f9fa;
        }
        .entity-name {
            font-weight: 600;
            color: #2c3e50;
        }
        .entity-link {
            color: #3498db;
            text-decoration: none;
            font-weight: 600;
            transition: color 0.2s;
        }
        .entity-link:hover {
            color: #2980b9;
            text-decoration: underline;
        }
        .entity-name-cell {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .isir-badge {
            color: #9c27b0;
            text-decoration: none;
            padding: 3px 8px;
            background-color: #f3e5f5;
            border-radius: 3px;
            font-size: 11px;
            display: inline-block;
            font-weight: 600;
            transition: background-color 0.2s;
        }
        .isir-badge:hover {
            background-color: #e1bee7;
        }
        .doc-count {
            text-align: center;
            font-weight: 600;
            color: #27ae60;
        }
        .latest-doc {
            color: #666;
            font-size: 14px;
        }
        .latest-date {
            color: #7f8c8d;
            font-size: 13px;
            white-space: nowrap;
        }
        .doc-list {
            list-style: none;
            margin: 0;
            padding: 0;
        }
        .doc-list li {
            padding: 4px 0;
            border-bottom: 1px solid #f0f0f0;
        }
        .doc-list li:last-child {
            border-bottom: none;
        }
        .doc-date-inline {
            font-size: 12px;
            margin-right: 8px;
        }
        .doc-list li strong {
            color: #2c3e50;
            margin-right: 6px;
        }
        .no-docs {
            color: #95a5a6;
            font-style: italic;
        }
        .last-modified {
            font-size: 13px;
            white-space: nowrap;
        }
        .footer {
            margin-top: 20px;
            padding-top: 15px;
            border-top: 1px solid #e0e0e0;
            color: #7f8c8d;
            font-size: 12px;
            text-align: center;
        }
        .footer a {
            color: #3498db;
            text-decoration: none;
        }
        .footer a:hover {
            text-decoration: underline;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 ISIR Watcher - Entity Overview</h1>
        <div class="subtitle">Monitoring insolvency proceedings in the Czech Republic with changes notifications</div>
        
        <table>
            <thead>
                <tr>
                    <th>Entity Name</th>
                    <th>Documents</th>
                    <th>Latest Documents (3)</th>
                    <th>Last Modified</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for data in entity_data:
            entity = data['entity']
            doc_count = data['doc_count']
            latest_docs = data['latest_docs']
            
            # Format latest documents
            if latest_docs:
                docs_html = '<ul class="doc-list">'
                for section_letter, doc in latest_docs:
                    # Get HTML-formatted document ID
                    display_id = doc.get_html_document_id()
                    
                    date_str = doc.publish_date.strftime('%d.%m.%Y %H:%M')
                    desc = doc.description[:45] + "..." if len(doc.description) > 45 else doc.description
                    docs_html += f'<li><span class="doc-date-inline">{date_str}</span><strong>{display_id}</strong> {desc}</li>'
                docs_html += '</ul>'
            else:
                docs_html = '<span class="no-docs">No documents</span>'
            
            # Format last modified
            last_modified_str = entity.last_modified.strftime('%d.%m.%Y %H:%M') if entity.last_modified else 'Never'
            
            # ISIR link
            isir_url = f"https://isir.justice.cz/isir/ueu/evidence_upadcu_detail.do?id={entity.isir_id}"
            
            html += f"""
                <tr>
                    <td>
                        <div class="entity-name-cell">
                            <a href="{entity.isir_id}.html" class="entity-link">{entity.name}</a>
                            <a href="{isir_url}" target="_blank" class="isir-badge" title="View on ISIR">ISIR</a>
                        </div>
                    </td>
                    <td class="doc-count">{doc_count}</td>
                    <td class="latest-doc">{docs_html}</td>
                    <td class="last-modified">{last_modified_str}</td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
        
        <div class="stats-summary">
            <div class="summary-box">
                <span class="number">""" + str(total_entities) + """</span>
                <span class="label">Watched Entities</span>
            </div>
            <div class="summary-box">
                <span class="number">""" + str(total_documents) + """</span>
                <span class="label">Total Documents</span>
            </div>
        </div>
        
        <div class="footer">
            Generated on """ + timestamp + """ by <a href="https://github.com/adamjezek98/isir-watcher" target="_blank">ISIR Watcher</a>
        </div>
    </div>
</body>
</html>
"""
        
        return html
    
    def generate_changelog(self, changes: List[Dict]):
        """
        Generate a condensed changelog for subscribers.
        
        Args:
            changes: List of change dictionaries with keys:
                - entity_name: Name of the watched entity
                - entity_isir_id: ISIR ID of the entity
                - change_type: 'new', 'updated', 'deleted'
                - document_id: ISIR document ID
                - document_type: Type of document
                - description: Document description
        """
        if not changes:
            logger.info("No changes to report")
            return
        
        changelog_path = self.output_dir / "changelog.txt"
        
        # Group changes by entity
        changes_by_entity = {}
        for change in changes:
            entity_name = change['entity_name']
            if entity_name not in changes_by_entity:
                changes_by_entity[entity_name] = {
                    'isir_id': change.get('entity_isir_id'),
                    'changes': []
                }
            changes_by_entity[entity_name]['changes'].append(change)
        
        # Generate condensed changelog
        changelog = ""
        
        for entity_name, entity_data in changes_by_entity.items():
            entity_changes = entity_data['changes']
            entity_isir_id = entity_data['isir_id']
            
            changelog += f"Entity: {entity_name}\n"
            
            # Add report URL if BASE_URL is configured
            if entity_isir_id:
                report_url = get_report_url(entity_isir_id)
                if report_url:
                    changelog += f"Report: {report_url}\n"
            
            changelog += "\n"
            
            # Count changes by type
            new_docs = [c for c in entity_changes if c['change_type'] == 'new']
            updated_docs = [c for c in entity_changes if c['change_type'] == 'updated']
            deleted_docs = [c for c in entity_changes if c['change_type'] == 'deleted']
            
            if new_docs:
                changelog += f"NEW DOCUMENTS ({len(new_docs)}):\n"
                for change in new_docs:
                    changelog += f"  • {change['document_id']} - {change.get('document_type', 'N/A')}"
                    if change.get('description'):
                        changelog += f": {change['description'][:100]}"
                    changelog += "\n"
                changelog += "\n"
            
            if deleted_docs:
                changelog += f"DELETED DOCUMENTS ({len(deleted_docs)}):\n"
                for change in deleted_docs:
                    changelog += f"  • {change['document_id']} - {change.get('document_type', 'N/A')}\n"
                changelog += "\n"
            
            if updated_docs:
                changelog += f"UPDATED DOCUMENTS ({len(updated_docs)}):\n"
                for change in updated_docs:
                    changelog += f"  • {change['document_id']} - {change.get('document_type', 'N/A')}\n"
                changelog += "\n"
            
            changelog += f"{'='*60}\n"

        # Add summary info at the end
        changelog += "ISIR Watcher - Change Log\n"
        changelog += f"Total Changes: {len(changes)}\n"
        changelog += f"Entities Affected: {len(changes_by_entity)}\n"
        changelog += f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
        
        # Write changelog
        changelog_path.write_text(changelog, encoding='utf-8')
        logger.info(f"Changelog generated: {changelog_path}")
        logger.info(f"Total changes: {len(changes)}")

