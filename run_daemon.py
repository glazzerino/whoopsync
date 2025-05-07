#!/usr/bin/env python
"""Simple script to run the Whoopsync daemon."""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Error running daemon: {e}", exc_info=True)
        sys.exit(1)