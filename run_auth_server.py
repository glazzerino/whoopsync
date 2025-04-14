#!/usr/bin/env python3
"""Run the Whoop OAuth authentication server."""

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
from whoopsync.api.auth_server import run_server


def main():
    """Run the authentication server."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the Whoop OAuth authentication server")
    parser.add_argument(
        "--host", 
        default=os.getenv("AUTH_SERVER_HOST", "0.0.0.0"),
        help="Host to bind the server to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=int(os.getenv("AUTH_SERVER_PORT", "8000")),
        help="Port to bind the server to (default: 8000)"
    )
    args = parser.parse_args()
    
    # Run the server
    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()