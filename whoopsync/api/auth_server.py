"""OAuth server for Whoop API integration."""

import os
import json
import logging
import pathlib
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlencode
from dotenv import load_dotenv

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import httpx

from whoopsync.data.auth_manager import AuthManager
from whoopsync.data.data_manager import DataManager

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
env_path = pathlib.Path(__file__).parents[2] / '.env'  # Go up 2 levels from auth_server.py to reach project root
logger.info(f"Loading environment variables from: {env_path} (exists: {env_path.exists()})")
load_dotenv(dotenv_path=env_path)

app = FastAPI(title="Whoop OAuth Server")

# Load environment variables directly from .env via dotenv
# This ensures we're reading from the .env file and not system environment
from dotenv import dotenv_values
env_values = dotenv_values(env_path)

CLIENT_ID = env_values.get("WHOOP_CLIENT_ID")
CLIENT_SECRET = env_values.get("WHOOP_CLIENT_SECRET") 
REDIRECT_URI = env_values.get("WHOOP_REDIRECT_URI")
AUTH_DATABASE_URL = env_values.get("AUTH_DATABASE_URL", "sqlite:///auth.db")
MAIN_DATABASE_URL = env_values.get("MAIN_DATABASE_URL", "sqlite:///whoop.db")

# Log the values we found in .env
logger.info(f"Values from .env file: WHOOP_CLIENT_ID present: {CLIENT_ID is not None}, " +
            f"WHOOP_CLIENT_SECRET present: {CLIENT_SECRET is not None}, " +
            f"WHOOP_REDIRECT_URI present: {REDIRECT_URI is not None}")

# Setup database managers
auth_manager = AuthManager(AUTH_DATABASE_URL)
data_manager = DataManager(MAIN_DATABASE_URL)

# Initialize databases
auth_manager.initialize_database()
data_manager.initialize_database()

# Templates directory for serving the HTML
templates = Jinja2Templates(directory="whoopsync/frontend")

# Mount static files
app.mount("/static", StaticFiles(directory="whoopsync/frontend/static"), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup."""
    global CLIENT_ID, CLIENT_SECRET, REDIRECT_URI
    
    logger.info("Starting Whoop OAuth server")
    logger.info(f"Environment variables: CLIENT_ID={CLIENT_ID}, CLIENT_SECRET={'*****' if CLIENT_SECRET else 'None'}, REDIRECT_URI={REDIRECT_URI}")
    
    if not CLIENT_ID or not CLIENT_SECRET or not REDIRECT_URI:
        logger.error("Missing required environment variables")
        # For development purposes, use dummy values
        logger.warning("Using dummy values for development")
        CLIENT_ID = "test_client_id" if not CLIENT_ID else CLIENT_ID
        CLIENT_SECRET = "test_client_secret" if not CLIENT_SECRET else CLIENT_SECRET
        REDIRECT_URI = "http://localhost:8000/api/auth/callback" if not REDIRECT_URI else REDIRECT_URI
        logger.info(f"Updated environment variables: CLIENT_ID={CLIENT_ID}, CLIENT_SECRET={'*****' if CLIENT_SECRET else 'None'}, REDIRECT_URI={REDIRECT_URI}")


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the home page."""
    return templates.TemplateResponse("authorize/auhtorize.html", {"request": request})


@app.get("/api/auth/whoop")
async def auth_whoop():
    """Redirect to Whoop OAuth authorization page."""
    # Define the required scopes
    scopes = [
        "read:recovery", 
        "read:cycles", 
        "read:workout", 
        "read:sleep", 
        "read:profile", 
        "read:body_measurement"
    ]
    
    # Prepare the authorization URL
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(scopes)
    }
    
    auth_url = f"https://api.prod.whoop.com/oauth/oauth2/auth?{urlencode(params)}"
    return RedirectResponse(auth_url)


@app.get("/api/auth/callback")
async def auth_callback(code: str, state: Optional[str] = None):
    """Handle the OAuth callback from Whoop."""
    # Exchange the authorization code for an access token
    token_url = "https://api.prod.whoop.com/oauth/oauth2/token"
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(token_url, data=payload)
            response.raise_for_status()
            token_data = response.json()
            
            # Get user profile to extract user ID
            headers = {"Authorization": f"Bearer {token_data['access_token']}"}
            profile_response = await client.get(
                "https://api.prod.whoop.com/developer/v1/user/profile/basic", 
                headers=headers
            )
            profile_response.raise_for_status()
            profile_data = profile_response.json()
            
            user_id = str(profile_data.get("user_id"))
            if not user_id:
                raise HTTPException(status_code=400, detail="Failed to retrieve user ID")
                
            # Store token in the database
            with auth_manager.get_session() as session:
                auth_manager.store_token(
                    session=session,
                    user_id=user_id,
                    access_token=token_data["access_token"],
                    refresh_token=token_data["refresh_token"],
                    expires_in=token_data["expires_in"],
                    token_type=token_data["token_type"],
                    scopes=token_data.get("scope", "")
                )
                
            # Store user profile in the main database
            with data_manager.get_session() as session:
                data_manager.create_or_update_user(
                    session=session,
                    user_id=user_id,
                    user_data=profile_data
                )
                
            # Redirect to success page
            return RedirectResponse("/api/auth/success")
            
        except httpx.HTTPError as e:
            logger.error(f"Error exchanging authorization code: {e}")
            raise HTTPException(status_code=500, detail="Failed to exchange authorization code")


@app.get("/api/auth/success", response_class=HTMLResponse)
async def auth_success(request: Request):
    """Serve the success page after successful authorization."""
    return templates.TemplateResponse("authorize/success.html", {"request": request})


@app.get("/api/auth/revoke/{user_id}")
async def revoke_token(user_id: str):
    """Revoke a user's token."""
    with auth_manager.get_session() as session:
        token = auth_manager.get_token(session, user_id)
        if not token:
            raise HTTPException(status_code=404, detail="Token not found")
            
        # Call Whoop API to revoke the token
        async with httpx.AsyncClient() as client:
            try:
                headers = {"Authorization": f"Bearer {token.access_token}"}
                response = await client.delete(
                    "https://api.prod.whoop.com/developer/v1/user/access", 
                    headers=headers
                )
                response.raise_for_status()
                
                # Deactivate token in the database
                auth_manager.deactivate_token(session, user_id)
                return {"status": "success", "message": "Token revoked successfully"}
                
            except httpx.HTTPError as e:
                logger.error(f"Error revoking token: {e}")
                # Even if the API call fails, deactivate the token locally
                auth_manager.deactivate_token(session, user_id)
                return {"status": "partial", "message": "Token deactivated locally but Whoop API call failed"}


@app.get("/api/auth/status/{user_id}")
async def token_status(user_id: str):
    """Check if a user's token is valid."""
    with auth_manager.get_session() as session:
        is_valid = auth_manager.is_token_valid(session, user_id)
        return {"status": "valid" if is_valid else "invalid"}


# Run the server
def run_server(host: str = "0.0.0.0", port: int = 8000):
    """Run the FastAPI server."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)