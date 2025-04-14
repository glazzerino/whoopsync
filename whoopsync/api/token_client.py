"""Token client for accessing Whoop API with automatic token refresh."""

import logging
from typing import Dict, Optional, Any, Tuple
from datetime import datetime

import httpx

from whoopsync.data.auth_manager import AuthManager

logger = logging.getLogger(__name__)


class TokenClient:
    """HTTP client with automatic token refresh for Whoop API."""

    def __init__(self, 
                 auth_manager: AuthManager,
                 client_id: str,
                 client_secret: str,
                 base_url: str = "https://api.prod.whoop.com/developer"):
        """Initialize the token client.

        Args:
            auth_manager: Auth manager instance
            client_id: OAuth client ID
            client_secret: OAuth client secret
            base_url: Base URL for the Whoop API
        """
        self.auth_manager = auth_manager
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()
        
    async def refresh_token(self, user_id: str, refresh_token: str) -> Dict[str, Any]:
        """Refresh an OAuth token.
        
        Args:
            user_id: User ID
            refresh_token: Refresh token
            
        Returns:
            New token data
            
        Raises:
            httpx.HTTPError: If token refresh fails
        """
        token_url = "https://api.prod.whoop.com/oauth/oauth2/token"
        payload = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        }
        
        response = await self.client.post(token_url, data=payload)
        response.raise_for_status()
        token_data = response.json()
        
        # Store the new token in the database
        with self.auth_manager.get_session() as session:
            current_token = self.auth_manager.get_token(session, user_id)
            scopes = current_token.scopes if current_token else ""
            
            self.auth_manager.store_token(
                session=session,
                user_id=user_id,
                access_token=token_data["access_token"],
                refresh_token=token_data["refresh_token"],
                expires_in=token_data["expires_in"],
                token_type=token_data["token_type"],
                scopes=token_data.get("scope", scopes)  # Use existing scopes if not in response
            )
            
        return token_data
        
    async def get_access_token(self, user_id: str) -> Tuple[str, str]:
        """Get a valid access token for a user, refreshing if needed.
        
        Args:
            user_id: User ID
            
        Returns:
            Tuple of (access_token, token_type)
            
        Raises:
            ValueError: If no valid token is found and refresh fails
        """
        with self.auth_manager.get_session() as session:
            # Check if we have a valid token
            token = self.auth_manager.get_token(session, user_id)
            if not token:
                raise ValueError(f"No token found for user {user_id}")
                
            # If token is still valid, return it
            if token.expires_at > datetime.utcnow():
                return token.access_token, token.token_type
                
            # Token is expired, try to refresh it
            try:
                token_data = await self.refresh_token(user_id, token.refresh_token)
                return token_data["access_token"], token_data["token_type"]
            except httpx.HTTPError as e:
                logger.error(f"Failed to refresh token for user {user_id}: {e}")
                # Deactivate the expired token
                self.auth_manager.deactivate_token(session, user_id)
                raise ValueError(f"Failed to refresh token for user {user_id}")
                
    async def request(self, 
                     method: str, 
                     path: str, 
                     user_id: str, 
                     params: Optional[Dict[str, Any]] = None,
                     json_data: Optional[Dict[str, Any]] = None,
                     retry_on_auth_error: bool = True) -> Dict[str, Any]:
        """Make an authenticated request to the Whoop API.
        
        Args:
            method: HTTP method
            path: API path
            user_id: User ID
            params: Query parameters
            json_data: JSON body
            retry_on_auth_error: Whether to retry on authentication errors
            
        Returns:
            Response data
            
        Raises:
            ValueError: If authentication fails
            httpx.HTTPError: If the request fails
        """
        # Get access token
        try:
            access_token, token_type = await self.get_access_token(user_id)
        except ValueError as e:
            logger.error(f"Authentication error: {e}")
            raise
            
        # Make the request
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"{token_type} {access_token}"}
        
        try:
            response = await self.client.request(
                method=method, 
                url=url, 
                headers=headers, 
                params=params,
                json=json_data
            )
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            # If it's an auth error and we should retry, refresh the token and try again
            if e.response.status_code == 401 and retry_on_auth_error:
                logger.warning(f"Authentication failed for user {user_id}, refreshing token")
                try:
                    with self.auth_manager.get_session() as session:
                        token = self.auth_manager.get_token(session, user_id)
                        if not token:
                            raise ValueError(f"No token found for user {user_id}")
                        
                        # Force token refresh
                        token_data = await self.refresh_token(user_id, token.refresh_token)
                        access_token = token_data["access_token"]
                        token_type = token_data["token_type"]
                        
                    # Retry the request with the new token
                    headers = {"Authorization": f"{token_type} {access_token}"}
                    response = await self.client.request(
                        method=method, 
                        url=url, 
                        headers=headers, 
                        params=params,
                        json=json_data
                    )
                    response.raise_for_status()
                    return response.json()
                    
                except (httpx.HTTPError, ValueError) as refresh_error:
                    logger.error(f"Failed to refresh token: {refresh_error}")
                    raise ValueError(f"Authentication failed for user {user_id} and token refresh failed")
            else:
                # Not an auth error or we already retried, just raise it
                raise