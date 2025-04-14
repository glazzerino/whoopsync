"""FastAPI application for Whoop API integration."""

import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from whoopsync.data.data_manager import DataManager
from whoopsync.api.routes import router

# Get environment variables
DB_PATH = os.environ.get("DB_PATH", "whoop.db")

# Create FastAPI app
app = FastAPI(
    title="Whoop Sync API",
    description="API for Whoop integration and data synchronization",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize data manager
data_manager = DataManager(f"sqlite:///{DB_PATH}")

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    data_manager.initialize_database()

# Include API routes
app.include_router(router)

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Whoop Sync API",
        "docs_url": "/docs",
        "auth_url": "/api/auth/whoop"
    }
