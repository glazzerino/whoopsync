"""Token management for Whoop OAuth2 authentication."""

import logging
from typing import Dict, Optional, Tuple, Any
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import Session

from whoopsync.data.data_manager import DataManager
from whoopsync.data.models import UserToken

logger = logging.getLogger(__name__)

class TokenManager:
    """Token management for Whoop OAuth2 authentication."""
    
    # Whoop OAuth2 endpoints
    TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
    REVOKE_URL = "https://api.prod.whoop.com/oauth/oauth2/revoke"
    
    def __init__(self, client_id: str, client_secret: str, data_manager: DataManager):
        """Initialize the token manager.
        
        Args:
            client_id: Whoop API client ID
            client_secret: Whoop API client secret
            data_manager: Data manager for storing tokens
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.data_manager = data_manager
        
    async def get_valid_token(self, session: Session, user_id: str) -> Optional[str]:
        """Get a valid access token for a user.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            Valid access token if available, None otherwise
        """
        is_valid, token = self.data_manager.is_token_valid(session, user_id)
        
        if is_valid and token:
            return token.access_token
        
        if token:
            # Token exists but is expired, try to refresh
            try:
                refreshed_token = await self.refresh_token(session, user_id, token.refresh_token)
                if refreshed_token:
                    return refreshed_token.access_token
            except Exception as e:
                logger.error(f"Failed to refresh token for user {user_id}: {e}")
                
        return None
        
    async def refresh_token(
        self, session: Session, user_id: str, refresh_token: str
    ) -> Optional[UserToken]:
        """Refresh an access token.
        
        Args:
            session: Database session
            user_id: User ID
            refresh_token: Refresh token
            
        Returns:
            Updated user token if successful, None otherwise
            
        Raises:
            Exception: If token refresh fails
        """
        logger.info(f"Refreshing token for user {user_id}")
        
        # Prepare refresh token request
        refresh_data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret
        }
        
        async with httpx.AsyncClient() as client:
            # Make request to refresh token
            response = await client.post(self.TOKEN_URL, data=refresh_data)
            response.raise_for_status()
            token_data = response.json()
            
            # Extract new tokens
            new_access_token = token_data.get("access_token")
            new_refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")
            scope = token_data.get("scope")
            token_type = token_data.get("token_type")
            
            if not all([new_access_token, new_refresh_token, expires_in, scope, token_type]):
                logger.error(f"Incomplete token data received: {token_data}")
                return None
            
            # Store new tokens
            updated_token = self.data_manager.save_oauth_token(
                session,
                user_id,
                new_access_token,
                new_refresh_token,
                expires_in,
                scope,
                token_type
            )
            
            logger.info(f"Successfully refreshed token for user {user_id}")
            return updated_token
        
    async def refresh_all_tokens(self, session: Session) -> Dict[str, bool]:
        """Refresh all tokens that will expire soon.
        
        Args:
            session: Database session
            
        Returns:
            Dictionary of user IDs and whether their tokens were refreshed successfully
        """
        logger.info("Refreshing all tokens that will expire soon")
        
        # Get all tokens
        all_tokens = session.query(UserToken).all()
        
        # Filter tokens that will expire soon (within 24 hours)
        expiry_threshold = datetime.utcnow() + timedelta(hours=24)
        expiring_tokens = [token for token in all_tokens if token.expires_at < expiry_threshold]
        
        logger.info(f"Found {len(expiring_tokens)} tokens that need refreshing")
        
        # Refresh each token
        results = {}
        for token in expiring_tokens:
            user_id = token.user_id
            try:
                updated_token = await self.refresh_token(session, user_id, token.refresh_token)
                results[user_id] = updated_token is not None
            except Exception as e:
                logger.error(f"Failed to refresh token for user {user_id}: {e}")
                results[user_id] = False
                
        return results
        
    async def revoke_token(self, session: Session, user_id: str) -> bool:
        """Revoke a user's tokens.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            True if tokens were revoked successfully, False otherwise
        """
        logger.info(f"Revoking tokens for user {user_id}")
        
        # Get user token
        token = self.data_manager.get_user_token(session, user_id)
        
        if not token:
            logger.warning(f"No token found for user {user_id}")
            return False
            
        try:
            async with httpx.AsyncClient() as client:
                # Revoke access token
                access_response = await client.post(self.REVOKE_URL, data={
                    "token": token.access_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                })
                access_response.raise_for_status()
                
                # Revoke refresh token
                refresh_response = await client.post(self.REVOKE_URL, data={
                    "token": token.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                })
                refresh_response.raise_for_status()
                
                # Delete token from database
                self.data_manager.delete_user_token(session, user_id)
                
                logger.info(f"Successfully revoked tokens for user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to revoke tokens for user {user_id}: {e}")
            return False