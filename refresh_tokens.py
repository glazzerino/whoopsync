#!/usr/bin/env python3

"""
Token refresh script for Whoop OAuth2 tokens.

This script is intended to be run as a cron job to refresh tokens before they expire.
"""

import os
import sys
import argparse
import logging
import asyncio

from whoopsync.data.data_manager import DataManager
from whoopsync.auth.token_manager import TokenManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Refresh Whoop OAuth2 tokens")
    
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
        "--user-id",
        type=str,
        help="Refresh token for a specific user ID (default: refresh all expiring tokens)"
    )
    
    return parser.parse_args()

async def main():
    """Refresh OAuth2 tokens."""
    args = parse_args()
    
    # Check required configuration
    if not args.client_id or not args.client_secret:
        logger.error("Missing required configuration: client_id and client_secret are required")
        logger.error("Set them with --client-id and --client-secret or with environment variables")
        return 1
    
    # Initialize data manager
    db_url = f"sqlite:///{args.db_path}"
    data_manager = DataManager(db_url)
    data_manager.initialize_database()
    
    # Initialize token manager
    token_manager = TokenManager(args.client_id, args.client_secret, data_manager)
    
    # Get database session
    session = data_manager.get_session()
    
    try:
        if args.user_id:
            # Refresh token for specific user
            logger.info(f"Refreshing token for user {args.user_id}")
            
            # Get user token
            token = data_manager.get_user_token(session, args.user_id)
            
            if not token:
                logger.error(f"No token found for user {args.user_id}")
                return 1
                
            # Refresh token
            try:
                updated_token = await token_manager.refresh_token(session, args.user_id, token.refresh_token)
                
                if updated_token:
                    logger.info(f"Successfully refreshed token for user {args.user_id}")
                    logger.info(f"New token expires at: {updated_token.expires_at}")
                    return 0
                else:
                    logger.error(f"Failed to refresh token for user {args.user_id}")
                    return 1
            except Exception as e:
                logger.error(f"Failed to refresh token for user {args.user_id}: {e}")
                return 1
        else:
            # Refresh all expiring tokens
            results = await token_manager.refresh_all_tokens(session)
            
            # Log results
            success_count = sum(1 for success in results.values() if success)
            total_count = len(results)
            
            logger.info(f"Refreshed {success_count}/{total_count} tokens")
            
            if success_count < total_count:
                # List failed users
                failed_users = [user_id for user_id, success in results.items() if not success]
                logger.warning(f"Failed to refresh tokens for users: {', '.join(failed_users)}")
                return 1
                
            return 0
    finally:
        # Close session
        session.close()

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))