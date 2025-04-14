"""Token refresher for Whoop API OAuth tokens."""

import os
import logging
import asyncio
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

import httpx

from whoopsync.data.auth_manager import AuthManager, OAuthToken

logger = logging.getLogger(__name__)


class TokenRefresher:
    """Service to refresh OAuth tokens before they expire."""

    def __init__(self, 
                 auth_manager: AuthManager,
                 client_id: str,
                 client_secret: str,
                 refresh_buffer_hours: int = 24):
        """Initialize the token refresher.

        Args:
            auth_manager: Auth manager instance
            client_id: OAuth client ID
            client_secret: OAuth client secret
            refresh_buffer_hours: How many hours before expiration to refresh tokens
        """
        self.auth_manager = auth_manager
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_buffer_hours = refresh_buffer_hours
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
        
    async def refresh_token(self, token: OAuthToken) -> bool:
        """Refresh a single OAuth token.
        
        Args:
            token: Token to refresh
            
        Returns:
            True if refresh was successful, False otherwise
        """
        token_url = "https://api.prod.whoop.com/oauth/oauth2/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": token.refresh_token,
            "grant_type": "refresh_token"
        }
        
        try:
            response = await self.client.post(token_url, data=payload)
            response.raise_for_status()
            token_data = response.json()
            
            # Store the new token in the database
            with self.auth_manager.get_session() as session:
                self.auth_manager.store_token(
                    session=session,
                    user_id=token.user_id,
                    access_token=token_data["access_token"],
                    refresh_token=token_data["refresh_token"],
                    expires_in=token_data["expires_in"],
                    token_type=token_data["token_type"],
                    scopes=token_data.get("scope", token.scopes)  # Use existing scopes if not in response
                )
                
            logger.info(f"Successfully refreshed token for user {token.user_id}")
            return True
            
        except httpx.HTTPError as e:
            logger.error(f"Error refreshing token for user {token.user_id}: {e}")
            # If refresh failed and token is already expired, deactivate it
            if datetime.utcnow() > token.expires_at:
                with self.auth_manager.get_session() as session:
                    self.auth_manager.deactivate_token(session, token.user_id)
                logger.warning(f"Deactivated expired token for user {token.user_id}")
            return False
            
    async def refresh_all_tokens(self) -> Dict[str, int]:
        """Refresh all tokens that will expire soon.
        
        Returns:
            Dictionary with counts of successful and failed refreshes
        """
        results = {"success": 0, "failed": 0}
        
        # Get tokens that need to be refreshed
        with self.auth_manager.get_session() as session:
            tokens = self.auth_manager.get_tokens_to_refresh(session, self.refresh_buffer_hours)
            
        if not tokens:
            logger.info("No tokens need to be refreshed")
            return results
            
        logger.info(f"Found {len(tokens)} tokens to refresh")
        
        # Process each token
        for token in tokens:
            success = await self.refresh_token(token)
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1
                
        return results
        
    async def run_periodic_refresh(self, interval_hours: int = 6):
        """Run token refresh periodically.
        
        Args:
            interval_hours: How often to check for tokens to refresh
        """
        logger.info(f"Starting periodic token refresh every {interval_hours} hours")
        
        while True:
            try:
                results = await self.refresh_all_tokens()
                logger.info(f"Token refresh completed: {results}")
            except Exception as e:
                logger.error(f"Error in periodic token refresh: {e}")
                
            # Wait for the next refresh cycle
            await asyncio.sleep(interval_hours * 3600)


async def run_token_refresher():
    """Run the token refresher as a standalone script."""
    # Load environment variables
    client_id = os.getenv("WHOOP_CLIENT_ID")
    client_secret = os.getenv("WHOOP_CLIENT_SECRET")
    auth_database_url = os.getenv("AUTH_DATABASE_URL", "sqlite:///auth.db")
    
    if not client_id or not client_secret:
        logger.error("Missing required environment variables")
        raise ValueError("WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET must be set")
        
    # Setup auth manager
    auth_manager = AuthManager(auth_database_url)
    
    # Create and run token refresher
    refresher = TokenRefresher(
        auth_manager=auth_manager,
        client_id=client_id,
        client_secret=client_secret
    )
    
    try:
        await refresher.run_periodic_refresh()
    finally:
        await refresher.close()
        

def main():
    """Entry point for the token refresher script."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_token_refresher())
    
    
if __name__ == "__main__":
    main()