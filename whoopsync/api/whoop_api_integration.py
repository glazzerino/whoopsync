"""Integration of Whoop API with token management."""

import os
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

import httpx

from whoopsync.data.auth_manager import AuthManager
from whoopsync.api.token_client import TokenClient

logger = logging.getLogger(__name__)


class WhoopAPIIntegration:
    """Integrated Whoop API client with token management."""

    BASE_URL = "https://api.prod.whoop.com/developer"

    def __init__(self, 
                 auth_manager: AuthManager,
                 client_id: str,
                 client_secret: str,
                 max_retries: int = 3,
                 retry_delay: int = 2):
        """Initialize the Whoop API integration.

        Args:
            auth_manager: Auth manager for token storage and retrieval
            client_id: Whoop API client ID
            client_secret: Whoop API client secret
            max_retries: Maximum number of retries on failure
            retry_delay: Delay between retries in seconds
        """
        self.auth_manager = auth_manager
        self.client_id = client_id
        self.client_secret = client_secret
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.token_client = TokenClient(
            auth_manager=auth_manager,
            client_id=client_id,
            client_secret=client_secret,
            base_url=self.BASE_URL
        )
        
    async def close(self) -> None:
        """Close the HTTP client."""
        await self.token_client.close()
        
    async def get_cycles(self, 
                         user_id: str, 
                         start_time: Optional[datetime] = None, 
                         end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
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

            response = await self.token_client.request(
                method="GET", 
                path="/v1/cycle", 
                user_id=user_id, 
                params=params
            )
            
            # Add records to our collection
            all_records.extend(response.get("records", []))
            
            # Check if there are more pages
            next_token = response.get("next_token")
            if not next_token:
                break

        return all_records

    async def get_sleep(self, 
                        user_id: str, 
                        start_time: Optional[datetime] = None, 
                        end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
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

            response = await self.token_client.request(
                method="GET", 
                path="/v1/activity/sleep", 
                user_id=user_id, 
                params=params
            )
            
            # Add records to our collection
            all_records.extend(response.get("records", []))
            
            # Check if there are more pages
            next_token = response.get("next_token")
            if not next_token:
                break

        return all_records

    async def get_workouts(self, 
                           user_id: str, 
                           start_time: Optional[datetime] = None, 
                           end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
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

            response = await self.token_client.request(
                method="GET", 
                path="/v1/activity/workout", 
                user_id=user_id, 
                params=params
            )
            
            # Add records to our collection
            all_records.extend(response.get("records", []))
            
            # Check if there are more pages
            next_token = response.get("next_token")
            if not next_token:
                break

        return all_records

    async def get_recoveries(self, 
                             user_id: str, 
                             start_time: Optional[datetime] = None, 
                             end_time: Optional[datetime] = None) -> List[Dict[str, Any]]:
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

            response = await self.token_client.request(
                method="GET", 
                path="/v1/recovery", 
                user_id=user_id, 
                params=params
            )
            
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
        return await self.token_client.request(
            method="GET", 
            path="/v1/user/profile/basic", 
            user_id=user_id
        )