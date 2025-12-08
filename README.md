# ISIR Watcher
A Python utility to monitor and track changes on the Czech Insolvency Registry (ISIR) website. Automatically scrapes entity documents, detects changes, downloads PDFs, and generates HTML reports.


## DISCLAIMER: I'm not wasting my time on people that owe me money, so this was vibecoded on one winter evening with Cursor

## I did not even bother to read most of the code, let alone check it, so this is provided as-is, without any warranty. Use at your own risk.

## Cursor generated detailed readme below, but TL;DR:

Put it on a server and have crontab (or ideally systemd timer) run it periodically. It will log changes and
basically create a mirror in the output directory (useful in case some documents get deleted from ISIR).
The output directory is meant to be served by a web server. There's an env file to put the domain there. 
If you are already using something like urlwatch, point it at the changelog to get notifications.

(fun fact: I was using urlwatch to track ISIR, but for stupid reasons, ISIR sometimes renders the page with
wrong dates for some documents, triggering false change alerts. Government software quality right there.)



## Features

- 🔍 **Automated Scraping** - Monitors ISIR entity pages for document updates
- 📊 **Database Tracking** - SQLite database with SQLAlchemy ORM for data persistence
- 📁 **Document Downloads** - Automatically downloads PDFs from ISIR
- 📝 **HTML Reports** - Generates beautiful, responsive HTML reports for each entity
- 📋 **Change Logs** - Condensed changelog for easy notification integration
- 🔄 **Smart Retries** - Automatically retries failed downloads
- 🗃️ **Document History** - Tracks document lifecycle (published, updated, deleted)
- ⚙️ **Configuration** - Environment-based configuration with `.env` support
- 🚀 **Production Ready** - Designed for cron/systemd timer automation

## Quick Start

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd isir-watcher
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Initialize database**
```bash
alembic upgrade head
```

### Configuration (Optional)

Copy the example configuration:
```bash
cp .env.example .env
```

Edit `.env` to set your configuration:
```bash
# Base URL where output directory is publicly accessible
BASE_URL=https://example.com/isir-reports
```

### Add Entities to Watch

```bash
# Add an entity (name and ISIR ID)
python -m src.manage add "John Doe" "E035915C75D6FEF5E05333F21FAC5E51"

# List all watched entities
python -m src.manage list

# Show entity details
python -m src.manage show "E035915C75D6FEF5E05333F21FAC5E51"

# Remove an entity
python -m src.manage remove "E035915C75D6FEF5E05333F21FAC5E51"
```

### Run the Watcher

```bash
python -m src.main
```

This will:
1. Check all watched entities for document changes
2. Update the database with new/modified/deleted documents
3. Generate HTML reports in `output/` for each entity
4. Generate an index page (`output/index.html`) with entity overview
5. Create `changelog.txt` if changes were detected
6. Download all pending PDF documents to `output/documents/`

## Automation

### Using Cron

```bash
# Edit crontab
crontab -e

# Run every hour
0 * * * * cd /path/to/isir-watcher && /path/to/venv/bin/python -m src.main >> /var/log/isir-watcher.log 2>&1

# Run every 15 minutes
*/15 * * * * cd /path/to/isir-watcher && /path/to/venv/bin/python -m src.main >> /var/log/isir-watcher.log 2>&1
```

### Using Systemd Timer

Create `/etc/systemd/system/isir-watcher.service`:
```ini
[Unit]
Description=ISIR Watcher
After=network.target

[Service]
Type=oneshot
User=your-user
WorkingDirectory=/path/to/isir-watcher
ExecStart=/path/to/venv/bin/python -m src.main
StandardOutput=journal
StandardError=journal
```

Create `/etc/systemd/system/isir-watcher.timer`:
```ini
[Unit]
Description=Run ISIR Watcher every hour

[Timer]
OnCalendar=hourly
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:
```bash
sudo systemctl enable isir-watcher.timer
sudo systemctl start isir-watcher.timer
sudo systemctl status isir-watcher.timer
```

## Project Structure

```
isir-watcher/
├── src/
│   ├── __init__.py           # Package initialization
│   ├── config.py             # Configuration management
│   ├── database.py           # Database setup and session
│   ├── models.py             # SQLAlchemy models
│   ├── scraper.py            # ISIR website scraper
│   ├── downloader.py         # PDF document downloader
│   ├── report_generator.py   # HTML report and changelog generator
│   ├── manage.py             # CLI for entity management
│   └── main.py               # Main application entry point
├── alembic/                  # Database migrations
├── output/                   # Generated reports and documents (gitignored)
│   ├── documents/            # Downloaded PDF files
│   ├── changelog.txt         # Change log
│   └── *.html                # Entity HTML reports
├── requirements.txt          # Python dependencies
├── .env.example              # Example configuration
├── .gitignore               # Git ignore rules
└── README.md                # This file
```

## How It Works

### Document Types

The watcher monitors 5 types of documents on ISIR:

1. **Before Bankruptcy Documents** (Oddíl A - Řízení do úpadku)
2. **After Bankruptcy Documents** (Oddíl B - Řízení po úpadku)
3. **Other Documents** (Oddíl D - Ostatní)
4. **Application Documents** (Oddíl P - Přihlášky) - includes creditor information
5. **Dispute Documents** (Oddíl C - Incidenční spory) - includes dispute numbers

### Workflow

1. **Scraping Phase**
   - Fetches entity pages from `https://isir.justice.cz/`
   - Extracts document details from HTML tables
   - Parses dates, descriptions, document IDs, etc.
   - Detects deleted documents ("není k dispozici" text)

2. **Database Update**
   - Compares scraped documents with existing database records
   - Detects new documents
   - Marks documents as deleted when no longer available
   - Handles ISIR document ID reuse (same ID can be reused for different documents)

3. **Report Generation**
   - Creates HTML reports for each entity
   - Shows all documents with status (active/deleted)
   - Includes links to downloaded PDFs
   - Responsive design with clean UI

4. **Changelog Creation**
   - Generates condensed text changelog when changes detected
   - Groups changes by entity
   - Includes report URLs (if BASE_URL configured)
   - Perfect for integration with notification tools (email, Slack, etc.)

5. **Document Downloads**
   - Downloads all pending PDF documents
   - Saves to `output/documents/{document_id}.pdf`
   - Updates database with HTTP status codes
   - Automatically retries failed downloads on next run
   - Skips already downloaded files

### Document Metadata

Each document in the database includes:
- `isir_document_id` - ISIR document ID (can be reused)
- `document_type` - Type code (e.g., I_45, I_78)
- `publish_date` - Publication date and time
- `description` - Document description
- `document_id` - Primary PDF document ID
- `side_document_id` - Secondary PDF document ID
- `legally_binding_date` - Legal binding date
- `senat_number` - Senate number
- `is_deleted` - Boolean flag (deleted from ISIR)
- `download` - HTTP status code for main document
- `side_download` - HTTP status code for side document
- `creditor` - Creditor name (application documents only)
- `dispute_number` - Dispute number (dispute documents only)

## Configuration

Configuration is managed via `.env` file (optional):

```bash
# Base URL where output directory is publicly accessible
# Leave empty if not hosting reports online
BASE_URL=https://example.com/isir-reports

# Optional: Output directory (default: output)
OUTPUT_DIR=output

# Optional: Database URL (default: sqlite:///./isir_watcher.db)
DATABASE_URL=sqlite:///./isir_watcher.db

# Optional: Download timeout in seconds (default: 30)
DOWNLOAD_TIMEOUT=30
```

## Output Files

### Index Page

An overview page (`output/index.html`) with:
- List of all watched entities (sorted by last modified)
- Total document counts per entity
- Latest 3 documents per entity with dates and descriptions
- Last modified timestamp (when the entity last had changes)
- Clickable entity names linking to individual reports
- Direct links to ISIR website for each entity (ISIR badge)
- Responsive design for easy navigation

### HTML Reports

Each entity gets an HTML report (`output/{entity_isir_id}.html`) with:
- Entity name and ISIR ID
- Direct link to ISIR website
- Summary statistics (clickable to jump to sections)
- Latest 10 documents across all sections
- Tabular view of all documents by section (A/B/C/D/P)
- Red highlighting for deleted documents
- Links to downloaded PDFs and original ISIR PDFs
- Responsive design for mobile viewing

### Changelog

When changes are detected, `output/changelog.txt` is created:

```
ISIR Watcher - Change Log

Entity: John Doe
Report: https://example.com/isir-reports/E035915C75D6FEF5E05333F21FAC5E51.html

NEW DOCUMENTS (2):
  • 125. - I_45: Usnesení o zahájení insolvenčního řízení
  • P1 - 20. - I_178: Přihláška pohledávky

DELETED DOCUMENTS (1):
  • 51. - I_52

============================================================
Total Changes: 3
Entities Affected: 1
Generated: 2025-11-23 23:21:54 UTC
```

Perfect for piping to notification services!

## Integration Examples

### Email Notifications

```bash
#!/bin/bash
cd /path/to/isir-watcher
source venv/bin/activate
python -m src.main

if [ -f output/changelog.txt ]; then
    mail -s "ISIR Changes Detected" your@email.com < output/changelog.txt
fi
```

### Webhook Notifications

```python
import requests
from pathlib import Path

changelog_path = Path("output/changelog.txt")
if changelog_path.exists():
    changelog = changelog_path.read_text()
    requests.post(
        "https://hooks.slack.com/services/YOUR/WEBHOOK/URL",
        json={"text": f"```{changelog}```"}
    )
```

## Development

### Database Migrations

After modifying models:
```bash
# Create migration
alembic revision --autogenerate -m "Description of changes"

# Apply migration
alembic upgrade head

# View migration history
alembic history
alembic current
```

### Running Tests

```bash
# TODO: Add tests
python -m pytest
```

## Logging

Logs are written to:
- `isir_watcher.log` - File in project root
- `stdout` - Console output

Log levels:
- `INFO` - Normal operations
- `WARNING` - Potential issues (e.g., failed document downloads)
- `ERROR` - Errors during execution

## Troubleshooting

### Database Issues

If you encounter database errors, you can reset:
```bash
rm isir_watcher.db
alembic upgrade head
```

### Download Failures

Failed downloads (status code != 200) are automatically retried on the next run. Check `download` and `side_download` columns in the database:
```python
from src.database import SessionLocal
from src.models import AfterBankruptcyDocument

db = SessionLocal()
failed = db.query(AfterBankruptcyDocument).filter(
    AfterBankruptcyDocument.download != 200
).all()
for doc in failed:
    print(f"Document {doc.document_id}: status {doc.download}")
```

### Scraper Issues

If ISIR changes their HTML structure, update `src/scraper.py`. The scraper uses BeautifulSoup to parse HTML tables.

## Notes

- **Document ID Reuse**: ISIR reuses document IDs when documents are deleted. The watcher handles this by comparing PDF IDs, not just ISIR document IDs.
- **Deleted Documents**: Once marked as deleted (`is_deleted=1`), documents are never "undeleted" even if they reappear.
- **Performance**: The watcher commits after each document download, so crashes won't lose progress.
- **Rate Limiting**: Be reasonable with cron frequency to avoid overwhelming ISIR servers. Hourly is usually sufficient.

## Credits

Built with Cursor AI assistance. It's a vibe-coded weekend project, so expect some rough edges.

**ISIR Website**: https://isir.justice.cz/

## License

MIT License - See [LICENSE](LICENSE) file for details.

Use it for anything you want, but the author is not liable for what you do with it.
