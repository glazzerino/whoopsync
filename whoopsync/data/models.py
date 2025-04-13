"""Database models for the Whoop data."""

from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    cycles = relationship("Cycle", back_populates="user", cascade="all, delete-orphan")
    sleeps = relationship("Sleep", back_populates="user", cascade="all, delete-orphan")
    workouts = relationship("Workout", back_populates="user", cascade="all, delete-orphan")
    recoveries = relationship("Recovery", back_populates="user", cascade="all, delete-orphan")


class Cycle(Base):
    """Cycle model."""

    __tablename__ = "cycles"

    id = Column(Integer, primary_key=True)
    cycle_id = Column(Integer, unique=True, nullable=False)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    start = Column(DateTime, nullable=False)
    end = Column(DateTime, nullable=True)
    timezone_offset = Column(String, nullable=False)
    score_state = Column(String, nullable=False)
    
    # Score fields
    strain = Column(Float, nullable=True)
    kilojoule = Column(Float, nullable=True)
    average_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    
    # Raw data
    raw_data = Column(Text, nullable=False)  # JSON string of the raw API response
    
    # Relationships
    user = relationship("User", back_populates="cycles")
    recovery = relationship("Recovery", back_populates="cycle", uselist=False)


class Sleep(Base):
    """Sleep model."""

    __tablename__ = "sleeps"

    id = Column(Integer, primary_key=True)
    sleep_id = Column(Integer, unique=True, nullable=False)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    start = Column(DateTime, nullable=False)
    end = Column(DateTime, nullable=False)
    timezone_offset = Column(String, nullable=False)
    nap = Column(Boolean, nullable=False)
    score_state = Column(String, nullable=False)
    
    # Score fields
    respiratory_rate = Column(Float, nullable=True)
    sleep_performance_percentage = Column(Float, nullable=True)
    sleep_consistency_percentage = Column(Float, nullable=True)
    sleep_efficiency_percentage = Column(Float, nullable=True)
    
    # Sleep stages
    total_in_bed_time_milli = Column(Integer, nullable=True)
    total_awake_time_milli = Column(Integer, nullable=True)
    total_no_data_time_milli = Column(Integer, nullable=True)
    total_light_sleep_time_milli = Column(Integer, nullable=True)
    total_slow_wave_sleep_time_milli = Column(Integer, nullable=True)
    total_rem_sleep_time_milli = Column(Integer, nullable=True)
    sleep_cycle_count = Column(Integer, nullable=True)
    disturbance_count = Column(Integer, nullable=True)
    
    # Raw data
    raw_data = Column(Text, nullable=False)  # JSON string of the raw API response
    
    # Relationships
    user = relationship("User", back_populates="sleeps")
    recovery = relationship("Recovery", back_populates="sleep", uselist=False)


class Workout(Base):
    """Workout model."""

    __tablename__ = "workouts"

    id = Column(Integer, primary_key=True)
    workout_id = Column(Integer, unique=True, nullable=False)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    start = Column(DateTime, nullable=False)
    end = Column(DateTime, nullable=False)
    timezone_offset = Column(String, nullable=False)
    sport_id = Column(Integer, nullable=False)
    score_state = Column(String, nullable=False)
    
    # Score fields
    strain = Column(Float, nullable=True)
    average_heart_rate = Column(Integer, nullable=True)
    max_heart_rate = Column(Integer, nullable=True)
    kilojoule = Column(Float, nullable=True)
    percent_recorded = Column(Float, nullable=True)
    distance_meter = Column(Float, nullable=True)
    altitude_gain_meter = Column(Float, nullable=True)
    altitude_change_meter = Column(Float, nullable=True)
    
    # Zone durations
    zone_zero_milli = Column(Integer, nullable=True)
    zone_one_milli = Column(Integer, nullable=True)
    zone_two_milli = Column(Integer, nullable=True)
    zone_three_milli = Column(Integer, nullable=True)
    zone_four_milli = Column(Integer, nullable=True)
    zone_five_milli = Column(Integer, nullable=True)
    
    # Raw data
    raw_data = Column(Text, nullable=False)  # JSON string of the raw API response
    
    # Relationships
    user = relationship("User", back_populates="workouts")


class Recovery(Base):
    """Recovery model."""

    __tablename__ = "recoveries"

    id = Column(Integer, primary_key=True)
    cycle_id = Column(Integer, ForeignKey("cycles.cycle_id"), nullable=False)
    sleep_id = Column(Integer, ForeignKey("sleeps.sleep_id"), nullable=False)
    user_id = Column(String, ForeignKey("users.user_id"), nullable=False)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    score_state = Column(String, nullable=False)
    
    # Score fields
    user_calibrating = Column(Boolean, nullable=True)
    recovery_score = Column(Float, nullable=True)
    resting_heart_rate = Column(Float, nullable=True)
    hrv_rmssd_milli = Column(Float, nullable=True)
    spo2_percentage = Column(Float, nullable=True)
    skin_temp_celsius = Column(Float, nullable=True)
    
    # Raw data
    raw_data = Column(Text, nullable=False)  # JSON string of the raw API response
    
    # Relationships
    user = relationship("User", back_populates="recoveries")
    cycle = relationship("Cycle", back_populates="recovery")
    sleep = relationship("Sleep", back_populates="recovery")