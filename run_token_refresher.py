#!/usr/bin/env python3
"""Run the Whoop OAuth token refresher."""

import os
import sys
import logging
import argparse
import pathlib
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Ensure the project root is in the Python path
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    logger.info(f"Adding {project_root} to Python path")
    sys.path.insert(0, project_root)

# Load environment variables from .env file first
env_path = pathlib.Path(__file__).parent / '.env'
logger.info(f"Loading environment variables from: {env_path} (exists: {env_path.exists()})")
if not env_path.exists():
    logger.warning(".env file not found at expected location")
else:
    logger.info("Found .env file, loading variables...")
load_dotenv(dotenv_path=env_path)

# Now import modules that depend on environment variables
try:
    from whoopsync.api.token_refresher import main as run_refresher
    logger.info("Successfully imported whoopsync module")
except ImportError as e:
    logger.error(f"Failed to import whoopsync module: {e}")
    logger.info(f"Current Python path: {sys.path}")
    logger.info("Try installing the package in development mode with: pip install -e .")
    sys.exit(1)


def main():
    """Run the token refresher."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Run the refresher
    run_refresher()


if __name__ == "__main__":
    main()