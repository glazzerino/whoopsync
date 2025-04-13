"""Main daemon module for syncing Whoop data."""

import asyncio
import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set

import dotenv
from pydantic import BaseModel

from whoopsync.api.whoop_api import WhoopAPI
from whoopsync.data.data_manager import DataManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class SyncDaemon:
    """Daemon for syncing Whoop data."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        database_url: str,
        user_ids: List[str],
        user_tokens: Dict[str, str],
        sync_interval: int = 3600,
        max_data_range: int = 604800,
    ):
        """Initialize the sync daemon.

        Args:
            client_id: Whoop API client ID
            client_secret: Whoop API client secret
            database_url: Database connection URL
            user_ids: List of user IDs to sync
            user_tokens: Dict of user IDs to their OAuth tokens
            sync_interval: Interval between syncs in seconds
            max_data_range: Maximum data range to sync in seconds
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.database_url = database_url
        self.user_ids = user_ids
        self.user_tokens = user_tokens
        self.sync_interval = sync_interval
        self.max_data_range = max_data_range
        
        self.api = None
        self.data_manager = None
        self.running = False
        self.loop = None
        
    async def initialize(self) -> None:
        """Initialize the daemon."""
        # Initialize API client
        self.api = WhoopAPI(
            client_id=self.client_id,
            client_secret=self.client_secret,
            user_tokens=self.user_tokens,
        )
        
        # Initialize data manager
        self.data_manager = DataManager(database_url=self.database_url)
        self.data_manager.initialize_database()
        
    async def shutdown(self) -> None:
        """Shutdown the daemon."""
        logger.info("Shutting down sync daemon")
        self.running = False
        
        if self.api:
            await self.api.close()
            
    async def sync_user_data(self, user_id: str) -> None:
        """Sync data for a user.

        Args:
            user_id: User ID to sync
        """
        logger.info(f"Syncing data for user {user_id}")
        
        try:
            session = self.data_manager.get_session()
            
            # Get user profile and create/update user
            user_profile = await self.api.get_user_profile(user_id)
            self.data_manager.create_or_update_user(session, user_id, user_profile)
            
            # Get the last update times for each data type
            last_cycle_time = self.data_manager.get_last_data_timestamp(session, user_id, "cycle")
            last_sleep_time = self.data_manager.get_last_data_timestamp(session, user_id, "sleep")
            last_workout_time = self.data_manager.get_last_data_timestamp(session, user_id, "workout")
            last_recovery_time = self.data_manager.get_last_data_timestamp(session, user_id, "recovery")
            
            # Calculate start and end times for the data range
            end_time = datetime.utcnow()
            
            # Sync cycles
            cycle_start_time = last_cycle_time or (end_time - timedelta(seconds=self.max_data_range))
            cycles = await self.api.get_cycles(user_id, cycle_start_time, end_time)
            stored_cycles = self.data_manager.store_cycles(session, user_id, cycles)
            logger.info(f"Stored {stored_cycles} cycles for user {user_id}")
            
            # Sync sleeps
            sleep_start_time = last_sleep_time or (end_time - timedelta(seconds=self.max_data_range))
            sleeps = await self.api.get_sleep(user_id, sleep_start_time, end_time)
            stored_sleeps = self.data_manager.store_sleeps(session, user_id, sleeps)
            logger.info(f"Stored {stored_sleeps} sleeps for user {user_id}")
            
            # Sync workouts
            workout_start_time = last_workout_time or (end_time - timedelta(seconds=self.max_data_range))
            workouts = await self.api.get_workouts(user_id, workout_start_time, end_time)
            stored_workouts = self.data_manager.store_workouts(session, user_id, workouts)
            logger.info(f"Stored {stored_workouts} workouts for user {user_id}")
            
            # Sync recoveries
            recovery_start_time = last_recovery_time or (end_time - timedelta(seconds=self.max_data_range))
            recoveries = await self.api.get_recoveries(user_id, recovery_start_time, end_time)
            stored_recoveries = self.data_manager.store_recoveries(session, user_id, recoveries)
            logger.info(f"Stored {stored_recoveries} recoveries for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error syncing data for user {user_id}: {e}")
        finally:
            session.close()
            
    async def run(self) -> None:
        """Run the daemon."""
        logger.info("Starting sync daemon")
        self.running = True
        
        # Set up signal handlers for graceful shutdown
        for sig in (signal.SIGINT, signal.SIGTERM):
            self.loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
        
        try:
            while self.running:
                logger.info(f"Starting sync for {len(self.user_ids)} users")
                
                # Create tasks for each user
                tasks = [self.sync_user_data(user_id) for user_id in self.user_ids]
                
                # Run tasks concurrently
                await asyncio.gather(*tasks)
                
                logger.info(f"Sync complete, sleeping for {self.sync_interval} seconds")
                
                # Sleep until next sync
                for _ in range(self.sync_interval):
                    if not self.running:
                        break
                    await asyncio.sleep(1)
                    
        except Exception as e:
            logger.error(f"Error in daemon: {e}")
            await self.shutdown()
            
    def start(self) -> None:
        """Start the daemon."""
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(self.initialize())
        self.loop.run_until_complete(self.run())
        self.loop.close()


def main() -> None:
    """Run the main daemon."""
    # Load environment variables
    dotenv.load_dotenv()
    
    # Get configuration from environment
    client_id = os.getenv("WHOOP_CLIENT_ID")
    client_secret = os.getenv("WHOOP_CLIENT_SECRET")
    database_url = os.getenv("DATABASE_URL", "sqlite:///whoop_data.db")
    sync_interval = int(os.getenv("SYNC_INTERVAL", "3600"))
    max_data_range = int(os.getenv("MAX_DATA_RANGE", "604800"))
    user_ids_str = os.getenv("USER_IDS", "")
    
    # Parse user IDs
    user_ids = [user_id.strip() for user_id in user_ids_str.split(",") if user_id.strip()]
    
    if not client_id or not client_secret:
        logger.error("Missing Whoop API credentials")
        sys.exit(1)
        
    if not user_ids:
        logger.error("No user IDs specified")
        sys.exit(1)
        
    # In a real application, you would load tokens from a secure store
    # Here we're just using a dummy placeholder
    user_tokens = {user_id: "dummy_token" for user_id in user_ids}
    
    # Create and start the daemon
    daemon = SyncDaemon(
        client_id=client_id,
        client_secret=client_secret,
        database_url=database_url,
        user_ids=user_ids,
        user_tokens=user_tokens,
        sync_interval=sync_interval,
        max_data_range=max_data_range,
    )
    
    daemon.start()


if __name__ == "__main__":
    main()