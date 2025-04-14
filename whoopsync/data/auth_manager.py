"""Authentication data manager for the Whoop API."""

import json
import logging
from typing import Dict, Optional, Any, Tuple, List
from datetime import datetime, timedelta

import sqlalchemy
from sqlalchemy import create_engine, func, Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

# Create a separate base for auth models
AuthBase = declarative_base()


class OAuthToken(AuthBase):
    """OAuth token model."""

    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True)
    user_id = Column(String, unique=True, nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    token_type = Column(String, nullable=False, default="Bearer")
    expires_at = Column(DateTime, nullable=False)  # Absolute time when token expires
    scopes = Column(String, nullable=False)  # Space-separated list of scopes
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)  # Flag to indicate if token is still valid


class AuthManager:
    """Authentication data manager for OAuth tokens."""

    def __init__(self, database_url: str):
        """Initialize the auth manager.

        Args:
            database_url: Database connection URL for the auth database
        """
        self.engine = create_engine(database_url)
        self.Session = sessionmaker(bind=self.engine)
        
    def initialize_database(self) -> None:
        """Create database tables if they don't exist."""
        AuthBase.metadata.create_all(self.engine)
        
    def get_session(self) -> Session:
        """Get a new database session.
        
        Returns:
            A new SQLAlchemy session
        """
        return self.Session()
        
    def store_token(self, 
                    session: Session, 
                    user_id: str, 
                    access_token: str, 
                    refresh_token: str, 
                    expires_in: int, 
                    token_type: str, 
                    scopes: str) -> OAuthToken:
        """Store OAuth token for a user.
        
        Args:
            session: Database session
            user_id: User ID
            access_token: OAuth access token
            refresh_token: OAuth refresh token
            expires_in: Token expiration time in seconds
            token_type: Token type (e.g., "Bearer")
            scopes: Space-separated list of scopes
            
        Returns:
            The created or updated token
        """
        # Calculate absolute expiration time
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Check if a token already exists for this user
        token = session.query(OAuthToken).filter(OAuthToken.user_id == user_id).first()
        
        if token is None:
            # Create new token record
            token = OAuthToken(
                user_id=user_id,
                access_token=access_token,
                refresh_token=refresh_token,
                token_type=token_type,
                expires_at=expires_at,
                scopes=scopes,
                is_active=True
            )
            session.add(token)
        else:
            # Update existing token
            token.access_token = access_token
            token.refresh_token = refresh_token
            token.token_type = token_type
            token.expires_at = expires_at
            token.scopes = scopes
            token.is_active = True
            token.updated_at = datetime.utcnow()
            
        session.commit()
        return token
        
    def get_token(self, session: Session, user_id: str) -> Optional[OAuthToken]:
        """Get OAuth token for a user.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            Token object if found, None otherwise
        """
        return session.query(OAuthToken).filter(
            OAuthToken.user_id == user_id,
            OAuthToken.is_active == True
        ).first()
        
    def get_token_dict(self, session: Session, user_id: str) -> Optional[Dict[str, Any]]:
        """Get token as a dictionary for a user.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            Dictionary with token data if found, None otherwise
        """
        token = self.get_token(session, user_id)
        if token is None:
            return None
            
        return {
            "access_token": token.access_token,
            "refresh_token": token.refresh_token,
            "token_type": token.token_type,
            "expires_at": token.expires_at.isoformat(),
            "scopes": token.scopes,
            "is_active": token.is_active
        }
        
    def get_active_tokens(self, session: Session) -> List[OAuthToken]:
        """Get all active tokens.
        
        Args:
            session: Database session
            
        Returns:
            List of active token objects
        """
        return session.query(OAuthToken).filter(OAuthToken.is_active == True).all()
        
    def deactivate_token(self, session: Session, user_id: str) -> bool:
        """Deactivate token for a user.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            True if token was found and deactivated, False otherwise
        """
        token = session.query(OAuthToken).filter(OAuthToken.user_id == user_id).first()
        if token is None:
            return False
            
        token.is_active = False
        token.updated_at = datetime.utcnow()
        session.commit()
        return True
        
    def is_token_valid(self, session: Session, user_id: str) -> bool:
        """Check if a user's token is valid and not expired.
        
        Args:
            session: Database session
            user_id: User ID
            
        Returns:
            True if token is valid and not expired, False otherwise
        """
        token = self.get_token(session, user_id)
        if token is None:
            return False
            
        # Check if token is expired (with 5 minute buffer to be safe)
        buffer_time = datetime.utcnow() + timedelta(minutes=5)
        if token.expires_at <= buffer_time:
            return False
            
        return True
        
    def get_tokens_to_refresh(self, session: Session, buffer_hours: int = 24) -> List[OAuthToken]:
        """Get tokens that need to be refreshed soon.
        
        Args:
            session: Database session
            buffer_hours: Number of hours before expiration to refresh tokens
            
        Returns:
            List of tokens that need to be refreshed
        """
        refresh_threshold = datetime.utcnow() + timedelta(hours=buffer_hours)
        
        return session.query(OAuthToken).filter(
            OAuthToken.is_active == True,
            OAuthToken.expires_at <= refresh_threshold
        ).all()