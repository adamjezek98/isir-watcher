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
    </style>
</head>
<body>
    <div class="header">
        <h1>{entity.name}</h1>
        <div class="info">
            <div>ISIR ID: {entity.isir_id}</div>
            <div>Last Checked: {entity.last_checked.strftime('%Y-%m-%d %H:%M:%S') if entity.last_checked else 'Never'}</div>
            <div>Report Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</div>
        </div>
    </div>
    
    <div class="section">
        <h2>Summary</h2>
        <div class="stats">
            <div class="stat-box">
                <div class="number">{len(before_bankruptcy)}</div>
                <div class="label">Before Bankruptcy</div>
            </div>
            <div class="stat-box">
                <div class="number">{len(after_bankruptcy)}</div>
                <div class="label">After Bankruptcy</div>
            </div>
            <div class="stat-box">
                <div class="number">{len(other_docs)}</div>
                <div class="label">Other Documents</div>
            </div>
            <div class="stat-box">
                <div class="number">{len(applications)}</div>
                <div class="label">Applications</div>
            </div>
            <div class="stat-box">
                <div class="number">{len(disputes)}</div>
                <div class="label">Disputes</div>
            </div>
        </div>
    </div>
"""
        
        # Add sections for each document type
        if before_bankruptcy:
            html += self._generate_document_section("Before Bankruptcy Documents", before_bankruptcy)
        
        if after_bankruptcy:
            html += self._generate_document_section("After Bankruptcy Documents", after_bankruptcy)
        
        if other_docs:
            html += self._generate_document_section("Other Documents", other_docs)
        
        if applications:
            html += self._generate_document_section("Application Documents", applications, show_creditor=True)
        
        if disputes:
            html += self._generate_document_section("Dispute Documents", disputes, show_dispute_number=True)
        
        html += """
</body>
</html>
"""
        return html
    
    def _generate_document_section(
        self,
        title: str,
        documents: List,
        show_creditor: bool = False,
        show_dispute_number: bool = False
    ) -> str:
        """Generate HTML for a document section."""
        
        html = f"""
    <div class="section">
        <h2>{title}</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Type</th>
                    <th>Published</th>
                    <th>Description</th>
                    {'<th>Creditor</th>' if show_creditor else ''}
                    {'<th>Dispute #</th>' if show_dispute_number else ''}
                    <th>Documents</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
"""
        
        for doc in documents:
            row_class = "deleted" if doc.is_deleted else ""
            status_badge = "badge-deleted" if doc.is_deleted else "badge-active"
            status_text = "DELETED" if doc.is_deleted else "ACTIVE"
            
            publish_date = doc.publish_date.strftime('%Y-%m-%d %H:%M') if doc.publish_date else 'N/A'
            
            # Generate document links
            doc_links = ""
            if doc.document_id:
                doc_filename = f"{doc.document_id}.pdf"
                doc_links += f'<a href="documents/{doc_filename}" class="document-link">Main PDF</a>'
            else:
                doc_links += '<span class="not-available">No PDF</span>'
            
            if doc.side_document_id:
                side_doc_filename = f"{doc.side_document_id}.pdf"
                doc_links += f' <a href="documents/{side_doc_filename}" class="document-link">Side PDF</a>'
            
            html += f"""
                <tr class="{row_class}">
                    <td>{doc.isir_document_id}</td>
                    <td>{doc.document_type or 'N/A'}</td>
                    <td>{publish_date}</td>
                    <td>{doc.description or ''}</td>
"""
            
            if show_creditor:
                html += f"                    <td>{doc.creditor or 'N/A'}</td>\n"
            
            if show_dispute_number:
                html += f"                    <td>{doc.dispute_number or 'N/A'}</td>\n"
            
            html += f"""
                    <td>{doc_links}</td>
                    <td><span class="badge {status_badge}">{status_text}</span></td>
                </tr>
"""
        
        html += """
            </tbody>
        </table>
    </div>
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

