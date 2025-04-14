#!/usr/bin/env python3
"""Run the Whoop OAuth token refresher."""

import os
import logging
import argparse
import pathlib
from dotenv import load_dotenv

# Load environment variables from .env file first
env_path = pathlib.Path(__file__).parent / '.env'
print(f"Loading environment variables from: {env_path} (exists: {env_path.exists()})")
if not env_path.exists():
    print("WARNING: .env file not found at expected location")
else:
    print("Found .env file, loading variables...")
load_dotenv(dotenv_path=env_path)

# Now import modules that depend on environment variables
from whoopsync.api.token_refresher import main as run_refresher


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