#!/bin/bash
# Setup script for whoopsync

# Exit on error
set -e

echo "Setting up whoopsync development environment..."

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install package in development mode
echo "Installing package in development mode..."
pip install -e .

echo "Checking installation..."
pip list | grep whoopsync

echo "Setup complete! You can now run the following commands:"
echo "- ./run_auth_server.py to start the auth server"
echo "- ./run_daemon.py to start the sync daemon"
echo "- ./run_token_refresher.py to refresh tokens"
echo ""
echo "Make sure to activate the virtual environment first with:"
echo "source venv/bin/activate"