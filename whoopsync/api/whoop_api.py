"""Whoop API interface."""

import time
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta

import httpx
from pydantic import BaseModel

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
        user_tokens: Dict[str, str],
        max_retries: int = 3,
        retry_delay: int = 2,
    ):
        """Initialize the Whoop API interface.

        Args:
            client_id: Whoop API client ID
            client_secret: Whoop API client secret
            user_tokens: Dict of user IDs to their OAuth tokens
            max_retries: Maximum number of retries on failure
            retry_delay: Delay between retries in seconds
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_tokens = user_tokens
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    async def _make_request(
        self, method: str, path: str, user_id: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Make a request to the Whoop API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path
            user_id: User ID for authentication
            params: Query parameters

        Returns:
            Response JSON

        Raises:
            WhoopAPIError: If the request fails after retries
        """
        if user_id not in self.user_tokens:
            raise WhoopAPIError(f"No token found for user {user_id}")

        url = f"{self.BASE_URL}{path}"
        headers = {"Authorization": f"Bearer {self.user_tokens[user_id]}"}

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
                    # In a real implementation, this would refresh the token
                    # For now, we'll just raise the error
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
        self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get cycles for a user.

        Args:
            user_id: User ID
            start_time: Start time to fetch data from
            end_time: End time to fetch data to

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

            response = await self._make_request("GET", "/v1/cycle", user_id, params)
            
            # Add records to our collection
            all_records.extend(response.get("records", []))
            
            # Check if there are more pages
            next_token = response.get("next_token")
            if not next_token:
                break

        return all_records

    async def get_sleep(
        self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get sleep data for a user.

        Args:
            user_id: User ID
            start_time: Start time to fetch data from
            end_time: End time to fetch data to

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

            response = await self._make_request("GET", "/v1/activity/sleep", user_id, params)
            
            # Add records to our collection
            all_records.extend(response.get("records", []))
            
            # Check if there are more pages
            next_token = response.get("next_token")
            if not next_token:
                break

        return all_records

    async def get_workouts(
        self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
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

            response = await self._make_request("GET", "/v1/activity/workout", user_id, params)
            
            # Add records to our collection
            all_records.extend(response.get("records", []))
            
            # Check if there are more pages
            next_token = response.get("next_token")
            if not next_token:
                break

        return all_records

    async def get_recoveries(
        self, user_id: str, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None
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

            response = await self._make_request("GET", "/v1/recovery", user_id, params)
            
            # Add records to our collection
            all_records.extend(response.get("records", []))
            
            # Check if there are more pages
            next_token = response.get("next_token")
            if not next_token:
                break

        return all_records

    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """Get user profile data.

        Args:
            user_id: User ID

        Returns:
            User profile data
        """
        return await self._make_request("GET", "/v1/user/profile/basic", user_id)