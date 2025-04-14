"""OAuth2 server for Whoop authentication."""

import os
import json
import logging
import secrets
import urllib.parse
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta

import httpx
from fastapi import FastAPI, Request, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from whoopsync.data.data_manager import DataManager
from whoopsync.data.models import UserToken

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
WHOOP_AUTH_URL = "https://api.prod.whoop.com/oauth/oauth2/auth"
WHOOP_TOKEN_URL = "https://api.prod.whoop.com/oauth/oauth2/token"
WHOOP_REVOKE_URL = "https://api.prod.whoop.com/oauth/oauth2/revoke"

# Environment variables should be set for these values in production
CLIENT_ID = os.environ.get("WHOOP_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("WHOOP_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("WHOOP_REDIRECT_URI", "http://localhost:8000/auth/callback")
DB_PATH = os.environ.get("DB_PATH", "whoop.db")

# Scopes required for the application
REQUIRED_SCOPES = [
    "read:cycles",
    "read:recovery",
    "read:sleep",
    "read:workout",
    "read:profile",
    "read:body_measurement"
]

# State management
state_store: Dict[str, Dict[str, Any]] = {}

# Models
class TokenRequest(BaseModel):
    """OAuth2 token request."""
    
    grant_type: str = Field(..., description="OAuth2 grant type")
    code: Optional[str] = Field(None, description="Authorization code for authorization_code grant")
    refresh_token: Optional[str] = Field(None, description="Refresh token for refresh_token grant")
    redirect_uri: Optional[str] = Field(None, description="Redirect URI for authorization_code grant")
    client_id: str = Field(..., description="Client ID")
    client_secret: str = Field(..., description="Client secret")

class TokenResponse(BaseModel):
    """OAuth2 token response."""
    
    access_token: str = Field(..., description="Access token")
    token_type: str = Field(..., description="Token type")
    expires_in: int = Field(..., description="Token expiration time in seconds")
    refresh_token: str = Field(..., description="Refresh token")
    scope: str = Field(..., description="Granted scopes")

class ErrorResponse(BaseModel):
    """Error response."""
    
    error: str = Field(..., description="Error code")
    error_description: Optional[str] = Field(None, description="Error description")

# Initialize FastAPI app
app = FastAPI(title="Whoop OAuth2 Server")

# Initialize data manager
data_manager = DataManager(f"sqlite:///{DB_PATH}")

# Initialize templates
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Dependency to get database session
def get_db():
    """Get database session."""
    with data_manager.get_session() as session:
        yield session


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    data_manager.initialize_database()


@app.get("/auth/login")
async def login(request: Request):
    """Initiate OAuth2 authorization code flow."""
    
    # Validate client configuration
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        logger.error("Missing OAuth2 configuration")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "server_error", "error_description": "Missing OAuth2 configuration"}
        )
    
    # Generate state parameter to prevent CSRF
    state = secrets.token_urlsafe(32)
    
    # Store state with timestamp to expire old states
    state_store[state] = {
        "created_at": datetime.utcnow(),
    }
    
    # Build authorization URL
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(REQUIRED_SCOPES),
        "state": state
    }
    auth_url = f"{WHOOP_AUTH_URL}?{urllib.parse.urlencode(params)}"
    
    # Redirect to authorization URL
    return RedirectResponse(url=auth_url)


@app.get("/auth/callback")
async def callback(
    request: Request,
    background_tasks: BackgroundTasks,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Handle OAuth2 callback."""
    
    # Check for errors from the authorization server
    if error:
        logger.error(f"Authorization error: {error} - {error_description}")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": error,
                "error_description": error_description or "Authorization failed"
            }
        )
    
    # Validate state parameter to prevent CSRF
    if not state or state not in state_store:
        logger.error("Invalid state parameter")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "invalid_request", "error_description": "Invalid state parameter"}
        )
    
    # Remove state from store
    state_data = state_store.pop(state)
    
    # Check state expiration (30 minutes)
    state_age = datetime.utcnow() - state_data["created_at"]
    if state_age > timedelta(minutes=30):
        logger.error("State parameter expired")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "invalid_request", "error_description": "State parameter expired"}
        )
    
    # Validate authorization code
    if not code:
        logger.error("Missing authorization code")
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "invalid_request", "error_description": "Missing authorization code"}
        )
    
    # Exchange authorization code for tokens
    token_request = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(WHOOP_TOKEN_URL, data=token_request)
            
            if response.status_code != 200:
                # Try to parse error response
                error_data = response.json()
                logger.error(f"Token exchange failed: {error_data}")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error": error_data.get("error", "server_error"),
                        "error_description": error_data.get("error_description", "Token exchange failed")
                    }
                )
            
            # Parse token response
            token_data = response.json()
            
            # Validate token response
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")
            token_type = token_data.get("token_type")
            scope = token_data.get("scope")
            
            if not all([access_token, refresh_token, expires_in, token_type, scope]):
                logger.error("Invalid token response")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error": "server_error",
                        "error_description": "Invalid token response"
                    }
                )
            
            # Get user profile to determine user ID
            profile_response = await client.get(
                "https://api.prod.whoop.com/developer/v1/user/profile/basic",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if profile_response.status_code != 200:
                logger.error(f"Failed to get user profile: {profile_response.text}")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "error": "server_error",
                        "error_description": "Failed to get user profile"
                    }
                )
            
            profile_data = profile_response.json()
            user_id = str(profile_data.get("user_id"))
            
            if not user_id:
                logger.error("Missing user ID in profile data")
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content={
                        "error": "server_error",
                        "error_description": "Missing user ID in profile data"
                    }
                )
            
            # Create or update user
            data_manager.create_or_update_user(db, user_id, profile_data)
            
            # Store tokens
            data_manager.save_oauth_token(
                db,
                user_id,
                access_token,
                refresh_token,
                expires_in,
                scope,
                token_type
            )
            
            logger.info(f"Successfully authenticated user {user_id}")
            
            # Return success page
            html_content = f"""
            <!DOCTYPE html>
            <html>
                <head>
                    <title>Authentication Successful</title>
                    <style>
                        body {{
                            font-family: Arial, sans-serif;
                            line-height: 1.6;
                            max-width: 600px;
                            margin: 0 auto;
                            padding: 20px;
                            text-align: center;
                        }}
                        .success {{
                            color: #4CAF50;
                            font-size: 24px;
                            margin-bottom: 20px;
                        }}
                        .info {{
                            background-color: #f8f9fa;
                            border-radius: 5px;
                            padding: 20px;
                            margin-top: 20px;
                        }}
                    </style>
                </head>
                <body>
                    <h1>Authentication Successful</h1>
                    <div class="success">✓ Your Whoop account has been connected successfully!</div>
                    <p>You can now close this window and return to the application.</p>
                    <div class="info">
                        <p>User ID: {user_id}</p>
                        <p>Name: {profile_data.get('first_name', '')} {profile_data.get('last_name', '')}</p>
                        <p>Scopes: {scope}</p>
                    </div>
                </body>
            </html>
            """
            return HTMLResponse(content=html_content)
    
    except Exception as e:
        logger.exception("Error during token exchange")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "server_error",
                "error_description": f"Error during token exchange: {str(e)}"
            }
        )


@app.post("/auth/refresh")
async def refresh_token(
    token_request: TokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh an access token."""
    
    # Validate request
    if token_request.grant_type != "refresh_token":
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "invalid_request",
                "error_description": "Grant type must be refresh_token"
            }
        )
    
    if not token_request.refresh_token:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "invalid_request",
                "error_description": "Refresh token is required"
            }
        )
    
    # Check client credentials
    if token_request.client_id != CLIENT_ID or token_request.client_secret != CLIENT_SECRET:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "invalid_client",
                "error_description": "Invalid client credentials"
            }
        )
    
    # Find user with this refresh token
    user_tokens = db.query(UserToken).filter(UserToken.refresh_token == token_request.refresh_token).all()
    
    if not user_tokens:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "error": "invalid_grant",
                "error_description": "Invalid refresh token"
            }
        )
    
    if len(user_tokens) > 1:
        logger.warning(f"Multiple users found with the same refresh token: {[t.user_id for t in user_tokens]}")
    
    user_token = user_tokens[0]
    user_id = user_token.user_id
    
    # Exchange refresh token for a new access token
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(WHOOP_TOKEN_URL, data={
                "grant_type": "refresh_token",
                "refresh_token": token_request.refresh_token,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET
            })
            
            if response.status_code != 200:
                # Try to parse error response
                error_data = response.json()
                logger.error(f"Token refresh failed: {error_data}")
                
                # If the refresh token is invalid, delete it
                if error_data.get("error") == "invalid_grant":
                    data_manager.delete_user_token(db, user_id)
                
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error": error_data.get("error", "server_error"),
                        "error_description": error_data.get("error_description", "Token refresh failed")
                    }
                )
            
            # Parse token response
            token_data = response.json()
            
            # Validate token response
            access_token = token_data.get("access_token")
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")
            token_type = token_data.get("token_type")
            scope = token_data.get("scope")
            
            if not all([access_token, refresh_token, expires_in, token_type, scope]):
                logger.error("Invalid token response")
                return JSONResponse(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    content={
                        "error": "server_error",
                        "error_description": "Invalid token response"
                    }
                )
            
            # Store new tokens
            data_manager.save_oauth_token(
                db,
                user_id,
                access_token,
                refresh_token,
                expires_in,
                scope,
                token_type
            )
            
            logger.info(f"Successfully refreshed token for user {user_id}")
            
            # Return token response
            return {
                "access_token": access_token,
                "token_type": token_type,
                "expires_in": expires_in,
                "refresh_token": refresh_token,
                "scope": scope,
                "user_id": user_id
            }
    
    except Exception as e:
        logger.exception("Error during token refresh")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "server_error",
                "error_description": f"Error during token refresh: {str(e)}"
            }
        )


@app.delete("/auth/revoke/{user_id}")
async def revoke_token(
    user_id: str,
    db: Session = Depends(get_db)
):
    """Revoke a user's tokens."""
    
    # Get user token
    user_token = data_manager.get_user_token(db, user_id)
    
    if not user_token:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={
                "error": "not_found",
                "error_description": f"No token found for user {user_id}"
            }
        )
    
    # Revoke access token with Whoop
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(WHOOP_REVOKE_URL, data={
                "token": user_token.access_token,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET
            })
            
            # Revoke refresh token with Whoop
            refresh_response = await client.post(WHOOP_REVOKE_URL, data={
                "token": user_token.refresh_token,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET
            })
            
            # Delete token from database
            data_manager.delete_user_token(db, user_id)
            
            logger.info(f"Successfully revoked tokens for user {user_id}")
            
            return {"message": f"Tokens revoked for user {user_id}"}
    
    except Exception as e:
        logger.exception("Error during token revocation")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "server_error",
                "error_description": f"Error during token revocation: {str(e)}"
            }
        )


@app.get("/auth/users")
async def list_users(db: Session = Depends(get_db)):
    """List all users with valid tokens."""
    
    # Get all valid tokens
    valid_tokens = data_manager.get_all_valid_tokens(db)
    
    # Format user data
    users = []
    for token in valid_tokens:
        user = db.query(UserToken).filter(UserToken.user_id == token.user_id).first()
        if user:
            users.append({
                "user_id": token.user_id,
                "email": user.user.email if user.user else None,
                "name": f"{user.user.first_name} {user.user.last_name}" if user.user else None,
                "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                "scopes": token.scope.split() if token.scope else []
            })
    
    return {"users": users}


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Whoop OAuth2 Server"}


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(app, host="0.0.0.0", port=8000)