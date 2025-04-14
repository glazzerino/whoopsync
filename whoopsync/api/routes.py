"""API routes for the Whoop Sync service."""

import os
import logging
from urllib.parse import urlencode
from typing import Dict, Optional

from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from whoopsync.data.data_manager import DataManager
from whoopsync.auth.token_manager import TokenManager

# Get environment variables
CLIENT_ID = os.environ.get("WHOOP_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("WHOOP_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("WHOOP_REDIRECT_URI", "http://localhost:8000/api/auth/callback")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api")

# Define scopes
REQUIRED_SCOPES = [
    "read:cycles",
    "read:recovery",
    "read:sleep",
    "read:workout",
    "read:profile",
    "read:body_measurement"
]

# State store for OAuth flow (production would use Redis or similar)
state_store: Dict[str, Dict] = {}

# Dependency for database session
def get_db(data_manager: DataManager = Depends()):
    """Get a database session."""
    with data_manager.get_session() as session:
        yield session

@router.get("/auth/whoop")
async def authorize_whoop(request: Request):
    """Start OAuth flow with Whoop."""
    if not CLIENT_ID or not REDIRECT_URI:
        logger.error("Missing OAuth configuration")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Missing OAuth configuration"
        )
    
    # Generate state for CSRF protection
    import secrets
    state = secrets.token_urlsafe(32)
    
    # Store state (in a real app, would use Redis or similar)
    from datetime import datetime
    state_store[state] = {"created_at": datetime.utcnow()}
    
    # Build authorization URL
    auth_url = "https://api.prod.whoop.com/oauth/oauth2/auth"
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(REQUIRED_SCOPES),
        "state": state
    }
    
    # Redirect to authorization URL
    return RedirectResponse(f"{auth_url}?{urlencode(params)}")


@router.get("/auth/callback")
async def auth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
    data_manager: DataManager = Depends(),
    db: Session = Depends(get_db)
):
    """Handle OAuth callback from Whoop."""
    # Check for errors from the authorization server
    if error:
        logger.error(f"Authorization error: {error} - {error_description}")
        return {
            "success": False,
            "error": error,
            "error_description": error_description or "Authorization failed"
        }
    
    # Validate required parameters
    if not code or not state:
        logger.error("Missing required parameters")
        return {
            "success": False,
            "error": "invalid_request",
            "error_description": "Missing required parameters"
        }
    
    # Validate state to prevent CSRF
    if state not in state_store:
        logger.error("Invalid state parameter")
        return {
            "success": False,
            "error": "invalid_request",
            "error_description": "Invalid state parameter"
        }
    
    # Remove state from store
    state_data = state_store.pop(state)
    
    # Validate state expiration (30 minutes)
    from datetime import datetime, timedelta
    state_age = datetime.utcnow() - state_data["created_at"]
    if state_age > timedelta(minutes=30):
        logger.error("State parameter expired")
        return {
            "success": False,
            "error": "invalid_request",
            "error_description": "State parameter expired"
        }
    
    # Exchange authorization code for tokens
    try:
        import httpx
        
        token_url = "https://api.prod.whoop.com/oauth/oauth2/token"
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=token_data)
            response.raise_for_status()
            
            token_response = response.json()
            
            # Extract token data
            access_token = token_response.get("access_token")
            refresh_token = token_response.get("refresh_token")
            expires_in = token_response.get("expires_in")
            token_type = token_response.get("token_type")
            scope = token_response.get("scope")
            
            if not all([access_token, refresh_token, expires_in, token_type, scope]):
                logger.error("Invalid token response")
                return {
                    "success": False,
                    "error": "server_error",
                    "error_description": "Invalid token response"
                }
            
            # Get user profile to get user ID
            profile_url = "https://api.prod.whoop.com/developer/v1/user/profile/basic"
            profile_response = await client.get(
                profile_url,
                headers={"Authorization": f"Bearer {access_token}"}
            )
            profile_response.raise_for_status()
            
            profile_data = profile_response.json()
            user_id = str(profile_data.get("user_id"))
            
            if not user_id:
                logger.error("User ID not found in profile")
                return {
                    "success": False,
                    "error": "server_error",
                    "error_description": "User ID not found in profile"
                }
            
            # Create or update user
            data_manager.create_or_update_user(db, user_id, profile_data)
            
            # Store token in database
            token_manager = TokenManager(CLIENT_ID, CLIENT_SECRET, data_manager)
            token_obj = await token_manager.refresh_token(db, user_id, refresh_token)
            
            if not token_obj:
                logger.error("Failed to store token")
                return {
                    "success": False,
                    "error": "server_error",
                    "error_description": "Failed to store token"
                }
            
            # Return success response with HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
                <head>
                    <title>Authentication Successful</title>
                    <style>
                        body {{
                            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                            line-height: 1.6;
                            max-width: 600px;
                            margin: 0 auto;
                            padding: 20px;
                            text-align: center;
                            background-color: #f9f9fa;
                            color: #1a1a1a;
                        }}
                        .card {{
                            background-color: white;
                            border-radius: 12px;
                            padding: 32px;
                            box-shadow: 0 4px 24px rgba(0, 0, 0, 0.1);
                            margin-top: 40px;
                        }}
                        .success-icon {{
                            color: #10b981;
                            font-size: 64px;
                            margin-bottom: 20px;
                        }}
                        h1 {{
                            font-size: 24px;
                            margin-bottom: 16px;
                        }}
                        .info {{
                            background-color: #f0f9ff;
                            border-radius: 8px;
                            padding: 16px;
                            margin-top: 24px;
                            text-align: left;
                        }}
                        .info p {{
                            margin: 8px 0;
                        }}
                        .close-button {{
                            background-color: #4f46e5;
                            color: white;
                            border: none;
                            border-radius: 8px;
                            padding: 12px 24px;
                            font-size: 16px;
                            font-weight: 500;
                            margin-top: 24px;
                            cursor: pointer;
                            transition: background-color 0.2s;
                        }}
                        .close-button:hover {{
                            background-color: #4338ca;
                        }}
                    </style>
                </head>
                <body>
                    <div class="card">
                        <div class="success-icon">✓</div>
                        <h1>Authentication Successful</h1>
                        <p>Your Whoop account has been connected successfully!</p>
                        <p>You can now close this window and return to the application.</p>
                        
                        <div class="info">
                            <p><strong>User ID:</strong> {user_id}</p>
                            <p><strong>Name:</strong> {profile_data.get('first_name', '')} {profile_data.get('last_name', '')}</p>
                            <p><strong>Email:</strong> {profile_data.get('email', '')}</p>
                        </div>
                        
                        <button class="close-button" onclick="window.close()">Close Window</button>
                    </div>
                </body>
            </html>
            """
            from fastapi.responses import HTMLResponse
            return HTMLResponse(content=html_content)
            
    except Exception as e:
        logger.exception("Error during token exchange")
        return {
            "success": False,
            "error": "server_error",
            "error_description": f"Error during token exchange: {str(e)}"
        }