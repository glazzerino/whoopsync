"""Tests for the data manager module."""

import json
import os
import tempfile
from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from whoopsync.data.data_manager import DataManager
from whoopsync.data.models import Base, User, Cycle


class TestDataManager:
    """Test class for DataManager."""
    
    @pytest.fixture
    def db_file(self):
        """Create a temporary database file."""
        fd, path = tempfile.mkstemp()
        yield path
        os.close(fd)
        os.unlink(path)
        
    @pytest.fixture
    def data_manager(self, db_file):
        """Create a data manager instance."""
        database_url = f"sqlite:///{db_file}"
        dm = DataManager(database_url=database_url)
        dm.initialize_database()
        return dm
        
    def test_create_user(self, data_manager):
        """Test creating a user."""
        session = data_manager.get_session()
        
        # Create a user
        user_data = {
            "user_id": "123",
            "email": "test@example.com",
            "first_name": "Test",
            "last_name": "User"
        }
        
        user = data_manager.create_or_update_user(session, "123", user_data)
        
        # Verify the user was created
        assert user.user_id == "123"
        assert user.email == "test@example.com"
        assert user.first_name == "Test"
        assert user.last_name == "User"
        
        # Verify the user can be retrieved
        retrieved_user = data_manager.get_user(session, "123")
        assert retrieved_user.user_id == "123"
        assert retrieved_user.email == "test@example.com"
        
        session.close()
        
    def test_store_cycles(self, data_manager):
        """Test storing cycle data."""
        session = data_manager.get_session()
        
        # Create a user
        user_data = {"user_id": "123"}
        data_manager.create_or_update_user(session, "123", user_data)
        
        # Create cycle data
        now = datetime.utcnow().isoformat() + "Z"
        cycles_data = [
            {
                "id": 1001,
                "user_id": 123,
                "created_at": now,
                "updated_at": now,
                "start": now,
                "end": now,
                "timezone_offset": "-05:00",
                "score_state": "SCORED",
                "score": {
                    "strain": 10.5,
                    "kilojoule": 1000.5,
                    "average_heart_rate": 65,
                    "max_heart_rate": 120
                }
            }
        ]
        
        # Store the cycles
        stored_count = data_manager.store_cycles(session, "123", cycles_data)
        
        # Verify cycles were stored
        assert stored_count == 1
        
        # Query the cycles
        cycle = session.query(Cycle).filter(Cycle.cycle_id == 1001).first()
        
        # Verify cycle data
        assert cycle.cycle_id == 1001
        assert cycle.user_id == "123"
        assert cycle.score_state == "SCORED"
        assert cycle.strain == 10.5
        assert cycle.kilojoule == 1000.5
        assert cycle.average_heart_rate == 65
        assert cycle.max_heart_rate == 120
        
        # Update cycle data
        updated_now = datetime.utcnow().isoformat() + "Z"
        updated_cycles_data = [
            {
                "id": 1001,
                "user_id": 123,
                "created_at": now,
                "updated_at": updated_now,
                "start": now,
                "end": now,
                "timezone_offset": "-05:00",
                "score_state": "SCORED",
                "score": {
                    "strain": 12.5,
                    "kilojoule": 1200.5,
                    "average_heart_rate": 70,
                    "max_heart_rate": 130
                }
            }
        ]
        
        # Store the updated cycles
        stored_count = data_manager.store_cycles(session, "123", updated_cycles_data)
        
        # Verify cycles were updated
        assert stored_count == 1
        
        # Query the cycles again
        cycle = session.query(Cycle).filter(Cycle.cycle_id == 1001).first()
        
        # Verify updated cycle data
        assert cycle.strain == 12.5
        assert cycle.kilojoule == 1200.5
        assert cycle.average_heart_rate == 70
        assert cycle.max_heart_rate == 130
        
        session.close()