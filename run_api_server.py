#!/usr/bin/env python3

"""
Run the API server for Whoop OAuth2 integration.
"""

import os
import sys
import argparse
import logging
import uvicorn

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run the Whoop API server")

    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=9090,
        help="Port to bind the server to (default: 9090)"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="whoop.db",
        help="Path to the SQLite database file (default: whoop.db)"
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default=os.environ.get("WHOOP_CLIENT_ID", ""),
        help="Whoop API client ID (default: from WHOOP_CLIENT_ID env var)"
    )
    parser.add_argument(
        "--client-secret",
        type=str,
        default=os.environ.get("WHOOP_CLIENT_SECRET", ""),
        help="Whoop API client secret (default: from WHOOP_CLIENT_SECRET env var)"
    )
    parser.add_argument(
        "--redirect-uri",
        type=str,
        default=os.environ.get("WHOOP_REDIRECT_URI", ""),
        help="OAuth2 redirect URI (default: from WHOOP_REDIRECT_URI env var)"
    )

    return parser.parse_args()

def main():
    """Run the API server."""
    args = parse_args()

    # Set environment variables for the API server
    os.environ["WHOOP_CLIENT_ID"] = args.client_id
    os.environ["WHOOP_CLIENT_SECRET"] = args.client_secret
    os.environ["WHOOP_REDIRECT_URI"] = args.redirect_uri or f"http://{args.host}:{args.port}/api/auth/callback"
    os.environ["DB_PATH"] = args.db_path

    # Check required configuration
    if not args.client_id or not args.client_secret:
        logger.error("Missing required configuration: client_id and client_secret are required")
        logger.error("Set them with --client-id and --client-secret or with environment variables")
        return 1

    # Start the server
    logger.info(f"Starting API server on {args.host}:{args.port}")
    logger.info(f"Using database at {args.db_path}")
    logger.info(f"Redirect URI: {os.environ['WHOOP_REDIRECT_URI']}")

    uvicorn.run(
        "whoopsync.api.app:app",
        host=args.host,
        port=args.port,
        reload=False
    )

    return 0

if __name__ == "__main__":
    sys.exit(main())
