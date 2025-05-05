"""Configuration settings for the application."""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Dune Analytics API Configuration
DUNE_API_KEY = os.getenv("DUNE_API_KEY","123")
BASE_URL = "https://api.dune.com/api/v1"
HEADERS = {"X-Dune-API-Key": DUNE_API_KEY}

# Query Execution Settings
MAX_RETRIES = 30
POLL_INTERVAL = 5  # seconds
MAX_POLL_ATTEMPTS = 60  # 5 minutes maximum wait time
QUERY_TIMEOUT = 300  # seconds
STALE_DATA_THRESHOLD = 8  # hours

# Error Messages
ERROR_MESSAGES = {
    "no_api_key": "DUNE_API_KEY environment variable is not set",
    "execution_failed": "Query execution failed with state: {}",
    "timeout": "Query execution timed out",
    "no_execution_id": "Failed to start query execution",
    "no_data": "Query completed but no data returned",
    "unknown_state": "Unknown query state: {}"
} 