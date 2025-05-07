#!/usr/bin/env python3
"""Simple script to run the Whoopsync daemon."""

import os
import sys
import logging
import pathlib
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file first
env_path = pathlib.Path(__file__).parent / '.env'
logger.info(f"Loading environment variables from: {env_path} (exists: {env_path.exists()})")
if not env_path.exists():
    logger.warning(".env file not found at expected location")
else:
    logger.info("Found .env file, loading variables...")
load_dotenv(dotenv_path=env_path)

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    logger.info(f"Adding {project_root} to Python path")
    sys.path.insert(0, project_root)

try:
    from whoopsync.sync_daemon import main
    logger.info("Successfully imported whoopsync module")
except ImportError as e:
    logger.error(f"Failed to import whoopsync module: {e}")
    logger.info(f"Current Python path: {sys.path}")
    logger.info("Try installing the package in development mode with: pip install -e .")
    sys.exit(1)

def run_daemon():
    """Run the daemon with configuration from environment variables."""
    try:
        main()
    except Exception as e:
        logger.error(f"Error running daemon: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_daemon()