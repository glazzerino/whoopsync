"""Whoop API interface."""

import time
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

import httpx
from pydantic import BaseModel
from sqlalchemy.orm import Session

from whoopsync.auth.token_manager import TokenManager
from whoopsync.data.models import UserToken

logger = logging.getLogger(__name__)


class WhoopAPIError(Exception):
    """Exception raised for Whoop API errors."""

    pass


class WhoopAPI:
    """Interface for the Whoop API."""

    BASE_URL = "https://api.prod.whoop.com/developer"
    TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        token_manager: Optional[TokenManager] = None,
        user_tokens: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
        retry_delay: int = 2,
    ):
        """Initialize the Whoop API interface.

        Args:
            client_id: Whoop API client ID
            client_secret: Whoop API client secret
            token_manager: TokenManager instance for token management
            user_tokens: Dict of user IDs to their OAuth tokens (legacy mode)
            max_retries: Maximum number of retries on failure
            retry_delay: Delay between retries in seconds
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_manager = token_manager
        self.user_tokens = user_tokens or {}
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def _make_request(
        self, method: str, path: str, user_id: str, params: Optional[Dict[str, Any]] = None,
        db_session: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Make a request to the Whoop API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            user_id: User ID for authentication
            params: Query parameters
            db_session: Database session for token management

        Returns:
            Response JSON

        Raises:
            WhoopAPIError: If the request fails after retries
        """
        # Get access token
        access_token = None
        
        # First try token manager if available
        if self.token_manager and db_session:
            access_token = await self.token_manager.get_valid_token(db_session, user_id)
        # Fall back to legacy token dictionary
        elif user_id in self.user_tokens:
            access_token = self.user_tokens[user_id]
            
        if not access_token:
            raise WhoopAPIError(f"No valid token found for user {user_id}")

        url = f"{self.BASE_URL}{path}"
        headers = {"Authorization": f"Bearer {access_token}"}

        for attempt in range(self.max_retries):
            try:
                response = await self.client.request(
                    method=method, url=url, headers=headers, params=params
                )
                
                if response.status_code == 429:
                    # Rate limited, wait and retry
                    retry_after = int(response.headers.get("Retry-After", self.retry_delay))
                    logger.warning(f"Rate limited, retrying after {retry_after}s")
                    time.sleep(retry_after)
                    continue
                    
                if response.status_code == 401:
                    # Token might be expired, try to refresh
                    logger.warning(f"Authentication error for user {user_id}, token might be expired")
                    
                    if self.token_manager and db_session:
                        try:
                            # Get token again 
                            token = db_session.query(UserToken).filter_by(user_id=user_id).first()
                            if not token:
                                raise WhoopAPIError(f"No token found for user {user_id}")
                                
                            # Refresh token
                            refreshed_token = await self.token_manager.refresh_token(
                                db_session, user_id, token.refresh_token
                            )
                            
                            if not refreshed_token:
                                raise WhoopAPIError(f"Failed to refresh token for user {user_id}")
                                
                            # Try request again with new token
                            headers = {"Authorization": f"Bearer {refreshed_token.access_token}"}
                            response = await self.client.request(
                                method=method, url=url, headers=headers, params=params
                            )
                            
                            if response.status_code == 200:
                                return response.json()
                        except Exception as e:
                            logger.error(f"Error refreshing token: {e}")
                            raise WhoopAPIError(f"Authentication failed for user {user_id}") from e
                    else:
                        # No token manager or DB session available
                        raise WhoopAPIError(f"Authentication failed for user {user_id}")
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPError as e:
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.warning(f"Request failed: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Request failed after {self.max_retries} attempts: {e}")
                    raise WhoopAPIError(f"Failed to make request: {e}") from e

        # This should never be reached due to the raised exception above
        raise WhoopAPIError("Maximum retries exceeded")

    async def get_cycles(
        self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None,
        db_session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get cycles for a user.

        Args:
            user_id: User ID
            start_time: Start time to fetch data from
            end_time: End time to fetch data to
            db_session: Database session for token management

        Returns:
            List of cycles data
        """
        params = {}
        if start_time:
            params["start"] = start_time.isoformat()
        if end_time:
            params["end"] = end_time.isoformat()

        all_records = []
        next_token = None

        while True:
            if next_token:
                params["nextToken"] = next_token

            response = await self._make_request("GET", "/v1/cycle", user_id, params, db_session)
            
            # Add records to our collection
            all_records.extend(response.get("records", []))
            
            # Check if there are more pages
            next_token = response.get("next_token")
            if not next_token:
                break

        return all_records

    async def get_sleep(
        self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None,
        db_session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get sleep data for a user.

        Args:
            user_id: User ID
            start_time: Start time to fetch data from
            end_time: End time to fetch data to
            db_session: Database session for token management

        Returns:
            List of sleep data
        """
        params = {}
        if start_time:
            params["start"] = start_time.isoformat()
        if end_time:
            params["end"] = end_time.isoformat()

        all_records = []
        next_token = None

        while True:
            if next_token:
                params["nextToken"] = next_token

            response = await self._make_request("GET", "/v1/activity/sleep", user_id, params, db_session)
            
            # Add records to our collection
            all_records.extend(response.get("records", []))
            
            # Check if there are more pages
            next_token = response.get("next_token")
            if not next_token:
                break

        return all_records

    async def get_workouts(
        self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None,
        db_session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get workout data for a user.

        Args:
            user_id: User ID
            start_time: Start time to fetch data from
            end_time: End time to fetch data to

        Returns:
            List of workout data
        """
        params = {}
        if start_time:
            params["start"] = start_time.isoformat()
        if end_time:
            params["end"] = end_time.isoformat()

        all_records = []
        next_token = None

        while True:
            if next_token:
                params["nextToken"] = next_token

            response = await self._make_request("GET", "/v1/activity/workout", user_id, params, db_session)
            
            # Add records to our collection
            all_records.extend(response.get("records", []))
            
            # Check if there are more pages
            next_token = response.get("next_token")
            if not next_token:
                break

        return all_records

    async def get_recoveries(
        self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None,
        db_session: Optional[Session] = None
    ) -> List[Dict[str, Any]]:
        """Get recovery data for a user.

        Args:
            user_id: User ID
            start_time: Start time to fetch data from
            end_time: End time to fetch data to

        Returns:
            List of recovery data
        """
        params = {}
        if start_time:
            params["start"] = start_time.isoformat()
        if end_time:
            params["end"] = end_time.isoformat()

        all_records = []
        next_token = None

        while True:
            if next_token:
                params["nextToken"] = next_token

            response = await self._make_request("GET", "/v1/recovery", user_id, params, db_session)
            
            # Add records to our collection
            all_records.extend(response.get("records", []))
            
            # Check if there are more pages
            next_token = response.get("next_token")
            if not next_token:
                break

        return all_records

    async def get_user_profile(self, user_id: str, db_session: Optional[Session] = None) -> Dict[str, Any]:
        """Get user profile data.

        Args:
            user_id: User ID

        Returns:
            User profile data
        """
        return await self._make_request("GET", "/v1/user/profile/basic", user_id, db_session=db_session)