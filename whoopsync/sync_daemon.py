"""Daemon for syncing Whoop data."""

import os
import time
import logging
import asyncio
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

from whoopsync.data.auth_manager import AuthManager
from whoopsync.data.data_manager import DataManager
from whoopsync.api.whoop_api_integration import WhoopAPIIntegration

logger = logging.getLogger(__name__)


class SyncDaemon:
    """Daemon for syncing Whoop data."""

    def __init__(self, 
                 auth_manager: AuthManager,
                 data_manager: DataManager,
                 client_id: str,
                 client_secret: str,
                 sync_interval_minutes: int = 60):
        """Initialize the sync daemon.

        Args:
            auth_manager: Auth manager instance
            data_manager: Data manager instance
            client_id: Whoop API client ID
            client_secret: Whoop API client secret
            sync_interval_minutes: How often to sync data in minutes
        """
        self.auth_manager = auth_manager
        self.data_manager = data_manager
        self.client_id = client_id
        self.client_secret = client_secret
        self.sync_interval_minutes = sync_interval_minutes
        self.api = None
        
    async def setup(self):
        """Set up the API client."""
        if self.api is None:
            self.api = WhoopAPIIntegration(
                auth_manager=self.auth_manager,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
        
    async def close(self):
        """Close the API client."""
        if self.api:
            await self.api.close()
            self.api = None
        
    async def sync_user_data(self, user_id: str) -> Dict[str, int]:
        """Sync data for a single user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with counts of synced items by type
        """
        results = {"cycles": 0, "sleep": 0, "workouts": 0, "recoveries": 0}
        
        try:
            # Get the last sync time for each data type
            with self.data_manager.get_session() as session:
                last_cycle_time = self.data_manager.get_last_data_timestamp(session, user_id, "cycle")
                last_sleep_time = self.data_manager.get_last_data_timestamp(session, user_id, "sleep")
                last_workout_time = self.data_manager.get_last_data_timestamp(session, user_id, "workout")
                last_recovery_time = self.data_manager.get_last_data_timestamp(session, user_id, "recovery")
                
            # Use a reasonable default start time if we've never synced before
            default_start = datetime.utcnow() - timedelta(days=30)
            
            # Sync cycles
            cycles = await self.api.get_cycles(
                user_id=user_id,
                start_time=last_cycle_time or default_start
            )
            if cycles:
                with self.data_manager.get_session() as session:
                    results["cycles"] = self.data_manager.store_cycles(session, user_id, cycles)
                    
            # Sync sleep
            sleeps = await self.api.get_sleep(
                user_id=user_id,
                start_time=last_sleep_time or default_start
            )
            if sleeps:
                with self.data_manager.get_session() as session:
                    results["sleep"] = self.data_manager.store_sleeps(session, user_id, sleeps)
                    
            # Sync workouts
            workouts = await self.api.get_workouts(
                user_id=user_id,
                start_time=last_workout_time or default_start
            )
            if workouts:
                with self.data_manager.get_session() as session:
                    results["workouts"] = self.data_manager.store_workouts(session, user_id, workouts)
                    
            # Sync recoveries
            recoveries = await self.api.get_recoveries(
                user_id=user_id,
                start_time=last_recovery_time or default_start
            )
            if recoveries:
                with self.data_manager.get_session() as session:
                    results["recoveries"] = self.data_manager.store_recoveries(session, user_id, recoveries)
                    
            logger.info(f"Synced data for user {user_id}: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Error syncing data for user {user_id}: {e}")
            return results
        
    async def sync_all_users(self) -> Dict[str, Any]:
        """Sync data for all users with valid tokens.
        
        Returns:
            Summary of sync results
        """
        summary = {"total_users": 0, "successful": 0, "failed": 0, "data_synced": {}}
        
        # Get all active tokens
        with self.auth_manager.get_session() as session:
            tokens = self.auth_manager.get_active_tokens(session)
            
        if not tokens:
            logger.info("No active tokens found, nothing to sync")
            return summary
            
        summary["total_users"] = len(tokens)
        total_counts = {"cycles": 0, "sleep": 0, "workouts": 0, "recoveries": 0}
        
        # Sync data for each user
        for token in tokens:
            try:
                results = await self.sync_user_data(token.user_id)
                summary["successful"] += 1
                # Add counts to totals
                for key, count in results.items():
                    total_counts[key] += count
            except Exception as e:
                logger.error(f"Error syncing user {token.user_id}: {e}")
                summary["failed"] += 1
                
        summary["data_synced"] = total_counts
        return summary
        
    async def run(self):
        """Run the sync daemon continuously."""
        logger.info(f"Starting sync daemon with interval of {self.sync_interval_minutes} minutes")
        
        await self.setup()
        
        try:
            while True:
                try:
                    start_time = time.time()
                    logger.info("Starting data sync cycle")
                    
                    summary = await self.sync_all_users()
                    
                    elapsed = time.time() - start_time
                    logger.info(f"Sync completed in {elapsed:.2f}s: {summary}")
                    
                except Exception as e:
                    logger.error(f"Error in sync cycle: {e}")
                    
                # Wait until next sync interval
                await asyncio.sleep(self.sync_interval_minutes * 60)
                
        finally:
            await self.close()


async def run_sync_daemon():
    """Run the sync daemon as a standalone script."""
    # Load environment variables
    client_id = os.getenv("WHOOP_CLIENT_ID")
    client_secret = os.getenv("WHOOP_CLIENT_SECRET")
    auth_database_url = os.getenv("AUTH_DATABASE_URL", "sqlite:///auth.db")
    main_database_url = os.getenv("MAIN_DATABASE_URL", "sqlite:///whoop.db")
    sync_interval = int(os.getenv("SYNC_INTERVAL_MINUTES", "60"))
    
    if not client_id or not client_secret:
        logger.error("Missing required environment variables")
        raise ValueError("WHOOP_CLIENT_ID and WHOOP_CLIENT_SECRET must be set")
        
    # Setup managers
    auth_manager = AuthManager(auth_database_url)
    data_manager = DataManager(main_database_url)
    
    # Create and run daemon
    daemon = SyncDaemon(
        auth_manager=auth_manager,
        data_manager=data_manager,
        client_id=client_id,
        client_secret=client_secret,
        sync_interval_minutes=sync_interval
    )
    
    await daemon.run()
    

def main():
    """Entry point for the sync daemon script."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_sync_daemon())