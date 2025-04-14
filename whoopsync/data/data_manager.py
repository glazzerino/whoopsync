"""Data manager for the Whoop data."""

import json
import logging
from typing import Dict, List, Optional, Any, Union, Tuple
from datetime import datetime, timedelta

import sqlalchemy
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session

from whoopsync.data.models import Base, User, Cycle, Sleep, Workout, Recovery, UserToken

logger = logging.getLogger(__name__)


class DataManager:
    """Interface for data storage and retrieval."""

    def __init__(self, database_url: str):
        """Initialize the data manager.

        Args:
            database_url: Database connection URL
        """
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        
    def initialize_database(self) -> None:
        """Create database tables if they don't exist."""
        Base.metadata.create_all(self.engine)
        
    def get_session(self) -> Session:
        """Get a new database session.
        
        Returns:
            A new SQLAlchemy session
        """
        return self.Session()
        
    def get_user(self, session: Session, user_id: str) -> Optional[User]:
        """Get a user by ID.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            User object if found, None otherwise
        """
        return session.query(User).filter(User.user_id == user_id).first()
        
    def create_or_update_user(
        self, session: Session, user_id: str, user_data: Dict[str, Any]
    ) -> User:
        """Create or update a user.
        
        Args:
            session: Database session
            user_id: User ID
            user_data: User data from the API
            
        Returns:
            The created or updated user
        """
        user = self.get_user(session, user_id)
        
        if user is None:
            # Create new user
            user = User(
                user_id=user_id,
                email=user_data.get("email"),
                first_name=user_data.get("first_name"),
                last_name=user_data.get("last_name"),
            )
            session.add(user)
        else:
            # Update existing user
            user.email = user_data.get("email", user.email)
            user.first_name = user_data.get("first_name", user.first_name)
            user.last_name = user_data.get("last_name", user.last_name)
            user.updated_at = datetime.utcnow()
            
        session.commit()
        return user
        
    def get_last_data_timestamp(
        self, session: Session, user_id: str, data_type: str
    ) -> Optional[datetime]:
        """Get the timestamp of the latest data for a user.
        
        Args:
            session: Database session
            user_id: User ID
            data_type: Type of data (cycle, sleep, workout, recovery)
            
        Returns:
            Timestamp of the latest data or None if no data exists
        """
        if data_type == "cycle":
            result = session.query(func.max(Cycle.updated_at)).filter(
                Cycle.user_id == user_id
            ).first()
        elif data_type == "sleep":
            result = session.query(func.max(Sleep.updated_at)).filter(
                Sleep.user_id == user_id
            ).first()
        elif data_type == "workout":
            result = session.query(func.max(Workout.updated_at)).filter(
                Workout.user_id == user_id
            ).first()
        elif data_type == "recovery":
            result = session.query(func.max(Recovery.updated_at)).filter(
                Recovery.user_id == user_id
            ).first()
        else:
            raise ValueError(f"Invalid data type: {data_type}")
            
        return result[0] if result and result[0] else None
        
    def store_cycles(
        self, session: Session, user_id: str, cycles_data: List[Dict[str, Any]]
    ) -> int:
        """Store cycle data for a user.
        
        Args:
            session: Database session
            user_id: User ID
            cycles_data: List of cycle data from the API
            
        Returns:
            Number of cycles stored
        """
        stored_count = 0
        
        for cycle_data in cycles_data:
            cycle_id = cycle_data.get("id")
            
            # Check if the cycle already exists
            existing_cycle = session.query(Cycle).filter(
                Cycle.cycle_id == cycle_id
            ).first()
            
            if existing_cycle:
                # Update if the API data is newer
                api_updated_at = datetime.fromisoformat(cycle_data.get("updated_at").replace("Z", "+00:00"))
                # Convert existing_cycle.updated_at to aware datetime if it's naive
                existing_updated_at = existing_cycle.updated_at
                if existing_updated_at.tzinfo is None:
                    # Add UTC timezone if it's naive
                    from datetime import timezone
                    existing_updated_at = existing_updated_at.replace(tzinfo=timezone.utc)
                if api_updated_at > existing_updated_at:
                    self._update_cycle(existing_cycle, cycle_data)
                    stored_count += 1
            else:
                # Create new cycle
                new_cycle = self._create_cycle(user_id, cycle_data)
                session.add(new_cycle)
                stored_count += 1
                
        session.commit()
        return stored_count
        
    def _create_cycle(self, user_id: str, cycle_data: Dict[str, Any]) -> Cycle:
        """Create a new cycle object from API data.
        
        Args:
            user_id: User ID
            cycle_data: Cycle data from the API
            
        Returns:
            New Cycle object
        """
        # Extract score data if available
        score_data = cycle_data.get("score", {})
        
        return Cycle(
            cycle_id=cycle_data.get("id"),
            user_id=user_id,
            created_at=datetime.fromisoformat(cycle_data.get("created_at").replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(cycle_data.get("updated_at").replace("Z", "+00:00")),
            start=datetime.fromisoformat(cycle_data.get("start").replace("Z", "+00:00")),
            end=datetime.fromisoformat(cycle_data.get("end").replace("Z", "+00:00")) if cycle_data.get("end") else None,
            timezone_offset=cycle_data.get("timezone_offset"),
            score_state=cycle_data.get("score_state"),
            
            # Score fields
            strain=score_data.get("strain"),
            kilojoule=score_data.get("kilojoule"),
            average_heart_rate=score_data.get("average_heart_rate"),
            max_heart_rate=score_data.get("max_heart_rate"),
            
            # Store raw data
            raw_data=json.dumps(cycle_data)
        )
        
    def _update_cycle(self, cycle: Cycle, cycle_data: Dict[str, Any]) -> None:
        """Update an existing cycle with new API data.
        
        Args:
            cycle: Existing Cycle object
            cycle_data: New cycle data from the API
        """
        # Extract score data if available
        score_data = cycle_data.get("score", {})
        
        cycle.updated_at = datetime.fromisoformat(cycle_data.get("updated_at").replace("Z", "+00:00"))
        cycle.end = datetime.fromisoformat(cycle_data.get("end").replace("Z", "+00:00")) if cycle_data.get("end") else None
        cycle.score_state = cycle_data.get("score_state")
        
        # Update score fields
        cycle.strain = score_data.get("strain")
        cycle.kilojoule = score_data.get("kilojoule")
        cycle.average_heart_rate = score_data.get("average_heart_rate")
        cycle.max_heart_rate = score_data.get("max_heart_rate")
        
        # Update raw data
        cycle.raw_data = json.dumps(cycle_data)
        
    def store_sleeps(
        self, session: Session, user_id: str, sleeps_data: List[Dict[str, Any]]
    ) -> int:
        """Store sleep data for a user.
        
        Args:
            session: Database session
            user_id: User ID
            sleeps_data: List of sleep data from the API
            
        Returns:
            Number of sleeps stored
        """
        stored_count = 0
        
        for sleep_data in sleeps_data:
            sleep_id = sleep_data.get("id")
            
            # Check if the sleep already exists
            existing_sleep = session.query(Sleep).filter(
                Sleep.sleep_id == sleep_id
            ).first()
            
            if existing_sleep:
                # Update if the API data is newer
                api_updated_at = datetime.fromisoformat(sleep_data.get("updated_at").replace("Z", "+00:00"))
                # Convert existing_sleep.updated_at to aware datetime if it's naive
                existing_updated_at = existing_sleep.updated_at
                if existing_updated_at.tzinfo is None:
                    # Add UTC timezone if it's naive
                    from datetime import timezone
                    existing_updated_at = existing_updated_at.replace(tzinfo=timezone.utc)
                if api_updated_at > existing_updated_at:
                    self._update_sleep(existing_sleep, sleep_data)
                    stored_count += 1
            else:
                # Create new sleep
                new_sleep = self._create_sleep(user_id, sleep_data)
                session.add(new_sleep)
                stored_count += 1
                
        session.commit()
        return stored_count
        
    def _create_sleep(self, user_id: str, sleep_data: Dict[str, Any]) -> Sleep:
        """Create a new sleep object from API data.
        
        Args:
            user_id: User ID
            sleep_data: Sleep data from the API
            
        Returns:
            New Sleep object
        """
        # Extract score data if available
        score_data = sleep_data.get("score", {})
        stage_summary = score_data.get("stage_summary", {})
        
        return Sleep(
            sleep_id=sleep_data.get("id"),
            user_id=user_id,
            created_at=datetime.fromisoformat(sleep_data.get("created_at").replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(sleep_data.get("updated_at").replace("Z", "+00:00")),
            start=datetime.fromisoformat(sleep_data.get("start").replace("Z", "+00:00")),
            end=datetime.fromisoformat(sleep_data.get("end").replace("Z", "+00:00")),
            timezone_offset=sleep_data.get("timezone_offset"),
            nap=sleep_data.get("nap"),
            score_state=sleep_data.get("score_state"),
            
            # Score fields
            respiratory_rate=score_data.get("respiratory_rate"),
            sleep_performance_percentage=score_data.get("sleep_performance_percentage"),
            sleep_consistency_percentage=score_data.get("sleep_consistency_percentage"),
            sleep_efficiency_percentage=score_data.get("sleep_efficiency_percentage"),
            
            # Sleep stages
            total_in_bed_time_milli=stage_summary.get("total_in_bed_time_milli"),
            total_awake_time_milli=stage_summary.get("total_awake_time_milli"),
            total_no_data_time_milli=stage_summary.get("total_no_data_time_milli"),
            total_light_sleep_time_milli=stage_summary.get("total_light_sleep_time_milli"),
            total_slow_wave_sleep_time_milli=stage_summary.get("total_slow_wave_sleep_time_milli"),
            total_rem_sleep_time_milli=stage_summary.get("total_rem_sleep_time_milli"),
            sleep_cycle_count=stage_summary.get("sleep_cycle_count"),
            disturbance_count=stage_summary.get("disturbance_count"),
            
            # Store raw data
            raw_data=json.dumps(sleep_data)
        )
        
    def _update_sleep(self, sleep: Sleep, sleep_data: Dict[str, Any]) -> None:
        """Update an existing sleep with new API data.
        
        Args:
            sleep: Existing Sleep object
            sleep_data: New sleep data from the API
        """
        # Extract score data if available
        score_data = sleep_data.get("score", {})
        stage_summary = score_data.get("stage_summary", {})
        
        sleep.updated_at = datetime.fromisoformat(sleep_data.get("updated_at").replace("Z", "+00:00"))
        sleep.score_state = sleep_data.get("score_state")
        
        # Update score fields
        sleep.respiratory_rate = score_data.get("respiratory_rate")
        sleep.sleep_performance_percentage = score_data.get("sleep_performance_percentage")
        sleep.sleep_consistency_percentage = score_data.get("sleep_consistency_percentage")
        sleep.sleep_efficiency_percentage = score_data.get("sleep_efficiency_percentage")
        
        # Update sleep stages
        sleep.total_in_bed_time_milli = stage_summary.get("total_in_bed_time_milli")
        sleep.total_awake_time_milli = stage_summary.get("total_awake_time_milli")
        sleep.total_no_data_time_milli = stage_summary.get("total_no_data_time_milli")
        sleep.total_light_sleep_time_milli = stage_summary.get("total_light_sleep_time_milli")
        sleep.total_slow_wave_sleep_time_milli = stage_summary.get("total_slow_wave_sleep_time_milli")
        sleep.total_rem_sleep_time_milli = stage_summary.get("total_rem_sleep_time_milli")
        sleep.sleep_cycle_count = stage_summary.get("sleep_cycle_count")
        sleep.disturbance_count = stage_summary.get("disturbance_count")
        
        # Update raw data
        sleep.raw_data = json.dumps(sleep_data)
        
    def store_workouts(
        self, session: Session, user_id: str, workouts_data: List[Dict[str, Any]]
    ) -> int:
        """Store workout data for a user.
        
        Args:
            session: Database session
            user_id: User ID
            workouts_data: List of workout data from the API
            
        Returns:
            Number of workouts stored
        """
        stored_count = 0
        
        for workout_data in workouts_data:
            workout_id = workout_data.get("id")
            
            # Check if the workout already exists
            existing_workout = session.query(Workout).filter(
                Workout.workout_id == workout_id
            ).first()
            
            if existing_workout:
                # Update if the API data is newer
                api_updated_at = datetime.fromisoformat(workout_data.get("updated_at").replace("Z", "+00:00"))
                # Convert existing_workout.updated_at to aware datetime if it's naive
                existing_updated_at = existing_workout.updated_at
                if existing_updated_at.tzinfo is None:
                    # Add UTC timezone if it's naive
                    from datetime import timezone
                    existing_updated_at = existing_updated_at.replace(tzinfo=timezone.utc)
                if api_updated_at > existing_updated_at:
                    self._update_workout(existing_workout, workout_data)
                    stored_count += 1
            else:
                # Create new workout
                new_workout = self._create_workout(user_id, workout_data)
                session.add(new_workout)
                stored_count += 1
                
        session.commit()
        return stored_count
        
    def _create_workout(self, user_id: str, workout_data: Dict[str, Any]) -> Workout:
        """Create a new workout object from API data.
        
        Args:
            user_id: User ID
            workout_data: Workout data from the API
            
        Returns:
            New Workout object
        """
        # Extract score data if available
        score_data = workout_data.get("score", {})
        zone_duration = score_data.get("zone_duration", {})
        
        return Workout(
            workout_id=workout_data.get("id"),
            user_id=user_id,
            created_at=datetime.fromisoformat(workout_data.get("created_at").replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(workout_data.get("updated_at").replace("Z", "+00:00")),
            start=datetime.fromisoformat(workout_data.get("start").replace("Z", "+00:00")),
            end=datetime.fromisoformat(workout_data.get("end").replace("Z", "+00:00")),
            timezone_offset=workout_data.get("timezone_offset"),
            sport_id=workout_data.get("sport_id"),
            score_state=workout_data.get("score_state"),
            
            # Score fields
            strain=score_data.get("strain"),
            average_heart_rate=score_data.get("average_heart_rate"),
            max_heart_rate=score_data.get("max_heart_rate"),
            kilojoule=score_data.get("kilojoule"),
            percent_recorded=score_data.get("percent_recorded"),
            distance_meter=score_data.get("distance_meter"),
            altitude_gain_meter=score_data.get("altitude_gain_meter"),
            altitude_change_meter=score_data.get("altitude_change_meter"),
            
            # Zone durations
            zone_zero_milli=zone_duration.get("zone_zero_milli"),
            zone_one_milli=zone_duration.get("zone_one_milli"),
            zone_two_milli=zone_duration.get("zone_two_milli"),
            zone_three_milli=zone_duration.get("zone_three_milli"),
            zone_four_milli=zone_duration.get("zone_four_milli"),
            zone_five_milli=zone_duration.get("zone_five_milli"),
            
            # Store raw data
            raw_data=json.dumps(workout_data)
        )
        
    def _update_workout(self, workout: Workout, workout_data: Dict[str, Any]) -> None:
        """Update an existing workout with new API data.
        
        Args:
            workout: Existing Workout object
            workout_data: New workout data from the API
        """
        # Extract score data if available
        score_data = workout_data.get("score", {})
        zone_duration = score_data.get("zone_duration", {})
        
        workout.updated_at = datetime.fromisoformat(workout_data.get("updated_at").replace("Z", "+00:00"))
        workout.score_state = workout_data.get("score_state")
        
        # Update score fields
        workout.strain = score_data.get("strain")
        workout.average_heart_rate = score_data.get("average_heart_rate")
        workout.max_heart_rate = score_data.get("max_heart_rate")
        workout.kilojoule = score_data.get("kilojoule")
        workout.percent_recorded = score_data.get("percent_recorded")
        workout.distance_meter = score_data.get("distance_meter")
        workout.altitude_gain_meter = score_data.get("altitude_gain_meter")
        workout.altitude_change_meter = score_data.get("altitude_change_meter")
        
        # Update zone durations
        workout.zone_zero_milli = zone_duration.get("zone_zero_milli")
        workout.zone_one_milli = zone_duration.get("zone_one_milli")
        workout.zone_two_milli = zone_duration.get("zone_two_milli")
        workout.zone_three_milli = zone_duration.get("zone_three_milli")
        workout.zone_four_milli = zone_duration.get("zone_four_milli")
        workout.zone_five_milli = zone_duration.get("zone_five_milli")
        
        # Update raw data
        workout.raw_data = json.dumps(workout_data)
        
    def store_recoveries(
        self, session: Session, user_id: str, recoveries_data: List[Dict[str, Any]]
    ) -> int:
        """Store recovery data for a user.
        
        Args:
            session: Database session
            user_id: User ID
            recoveries_data: List of recovery data from the API
            
        Returns:
            Number of recoveries stored
        """
        stored_count = 0
        
        for recovery_data in recoveries_data:
            cycle_id = recovery_data.get("cycle_id")
            sleep_id = recovery_data.get("sleep_id")
            
            # Check if the recovery already exists
            existing_recovery = session.query(Recovery).filter(
                Recovery.cycle_id == cycle_id,
                Recovery.sleep_id == sleep_id
            ).first()
            
            if existing_recovery:
                # Update if the API data is newer
                api_updated_at = datetime.fromisoformat(recovery_data.get("updated_at").replace("Z", "+00:00"))
                # Convert existing_recovery.updated_at to aware datetime if it's naive
                existing_updated_at = existing_recovery.updated_at
                if existing_updated_at.tzinfo is None:
                    # Add UTC timezone if it's naive
                    from datetime import timezone
                    existing_updated_at = existing_updated_at.replace(tzinfo=timezone.utc)
                if api_updated_at > existing_updated_at:
                    self._update_recovery(existing_recovery, recovery_data)
                    stored_count += 1
            else:
                # Create new recovery
                new_recovery = self._create_recovery(user_id, recovery_data)
                session.add(new_recovery)
                stored_count += 1
                
        session.commit()
        return stored_count
        
    def _create_recovery(self, user_id: str, recovery_data: Dict[str, Any]) -> Recovery:
        """Create a new recovery object from API data.
        
        Args:
            user_id: User ID
            recovery_data: Recovery data from the API
            
        Returns:
            New Recovery object
        """
        # Extract score data if available
        score_data = recovery_data.get("score", {})
        
        return Recovery(
            cycle_id=recovery_data.get("cycle_id"),
            sleep_id=recovery_data.get("sleep_id"),
            user_id=user_id,
            created_at=datetime.fromisoformat(recovery_data.get("created_at").replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(recovery_data.get("updated_at").replace("Z", "+00:00")),
            score_state=recovery_data.get("score_state"),
            
            # Score fields
            user_calibrating=score_data.get("user_calibrating"),
            recovery_score=score_data.get("recovery_score"),
            resting_heart_rate=score_data.get("resting_heart_rate"),
            hrv_rmssd_milli=score_data.get("hrv_rmssd_milli"),
            spo2_percentage=score_data.get("spo2_percentage"),
            skin_temp_celsius=score_data.get("skin_temp_celsius"),
            
            # Store raw data
            raw_data=json.dumps(recovery_data)
        )
        
    def _update_recovery(self, recovery: Recovery, recovery_data: Dict[str, Any]) -> None:
        """Update an existing recovery with new API data.
        
        Args:
            recovery: Existing Recovery object
            recovery_data: New recovery data from the API
        """
        # Extract score data if available
        score_data = recovery_data.get("score", {})
        
        recovery.updated_at = datetime.fromisoformat(recovery_data.get("updated_at").replace("Z", "+00:00"))
        recovery.score_state = recovery_data.get("score_state")
        
        # Update score fields
        recovery.user_calibrating = score_data.get("user_calibrating")
        recovery.recovery_score = score_data.get("recovery_score")
        recovery.resting_heart_rate = score_data.get("resting_heart_rate")
        recovery.hrv_rmssd_milli = score_data.get("hrv_rmssd_milli")
        recovery.spo2_percentage = score_data.get("spo2_percentage")
        recovery.skin_temp_celsius = score_data.get("skin_temp_celsius")
        
        # Update raw data
        recovery.raw_data = json.dumps(recovery_data)
        
    # OAuth Token Management
    
    def save_oauth_token(
        self, 
        session: Session, 
        user_id: str, 
        access_token: str, 
        refresh_token: str, 
        expires_in: int, 
        scope: str,
        token_type: str = "Bearer"
    ) -> UserToken:
        """Save OAuth token for a user.

        Args:
            session: Database session
            user_id: User ID
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_in: Token expiration time in seconds
            scope: Token scope
            token_type: Token type (default: Bearer)

        Returns:
            UserToken object
        """
        # Calculate expiration time
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

        # Try to get existing token
        token = session.query(UserToken).filter(UserToken.user_id == user_id).first()
        if token:
            # Update existing token
            token.access_token = access_token
            token.refresh_token = refresh_token
            token.expires_at = expires_at
            token.scope = scope
            token.token_type = token_type
            token.updated_at = datetime.utcnow()
        else:
            # Get or create user
            user = self.get_user(session, user_id)
            if not user:
                user = User(user_id=user_id)
                session.add(user)
                session.flush()
                
            # Create new token
            token = UserToken(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                expires_at=expires_at,
                scope=scope,
                token_type=token_type
            )
            session.add(token)

        session.commit()
        return token

    def get_user_token(self, session: Session, user_id: str) -> Optional[UserToken]:
        """Get OAuth token for a user.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            UserToken object if found, None otherwise
        """
        return session.query(UserToken).filter(UserToken.user_id == user_id).first()

    def is_token_valid(self, session: Session, user_id: str) -> Tuple[bool, Optional[UserToken]]:
        """Check if a user's OAuth token is valid.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            Tuple of (is_valid, token). If token does not exist, returns (False, None).
            If token exists but is expired, returns (False, token).
            If token exists and is valid, returns (True, token).
        """
        token = session.query(UserToken).filter(UserToken.user_id == user_id).first()
        if not token:
            return False, None
        
        # Check if token is expired (with 5 minute buffer to be safe)
        buffer_time = datetime.utcnow() + timedelta(minutes=5)
        if token.expires_at < buffer_time:
            return False, token
            
        return True, token

    def get_all_valid_tokens(self, session: Session) -> List[UserToken]:
        """Get all valid OAuth tokens.

        Args:
            session: Database session

        Returns:
            List of valid UserToken objects
        """
        # Get tokens that have not expired (with 5 minute buffer)
        buffer_time = datetime.utcnow() + timedelta(minutes=5)
        return session.query(UserToken).filter(UserToken.expires_at > buffer_time).all()

    def delete_user_token(self, session: Session, user_id: str) -> bool:
        """Delete OAuth token for a user.

        Args:
            session: Database session
            user_id: User ID

        Returns:
            True if token was deleted, False if token was not found
        """
        token = session.query(UserToken).filter(UserToken.user_id == user_id).first()
        if not token:
            return False
            
        session.delete(token)
        session.commit()
        return True