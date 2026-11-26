"""Configuration management for ISIR Watcher."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Base URL where the output directory is publicly accessible
# Example: https://example.com/isir-reports
BASE_URL = os.getenv('BASE_URL', '').rstrip('/')

# Database configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./isir_watcher.db')

# Output directory
OUTPUT_DIR = os.getenv('OUTPUT_DIR', 'output')

# Download configuration
MAX_DOWNLOAD_RETRIES = int(os.getenv('MAX_DOWNLOAD_RETRIES', '3'))
DOWNLOAD_TIMEOUT = int(os.getenv('DOWNLOAD_TIMEOUT', '30'))

# Number of consecutive failed checks (invalid ISIR link) before the error
# is reported in the changelog. Transient failures below this are suppressed.
INVALID_LINK_THRESHOLD = int(os.getenv('INVALID_LINK_THRESHOLD', '10'))


def get_report_url(entity_isir_id: str) -> str:
    """
    Get the full URL to an entity's HTML report.
    
    Args:
        entity_isir_id: The ISIR ID of the entity
        
    Returns:
        Full URL to the report, or empty string if BASE_URL is not configured
    """
    if not BASE_URL:
        return ''
    return f"{BASE_URL}/{entity_isir_id}.html"

