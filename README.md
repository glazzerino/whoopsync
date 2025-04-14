# Whoopsync

A daemon service to synchronize Whoop health data for multiple users locally.

## Overview

Whoopsync is a Python-based daemon that periodically fetches data from the Whoop API for multiple users and stores it locally in a SQLite database (default) or any other SQLAlchemy-supported database. This allows you to have a local copy of your Whoop health data for analysis, backup, or integration with other systems.

## Features

- Periodic synchronization with configurable interval
- Support for multiple Whoop users
- Stores data in a local SQLite database (or any other SQLAlchemy-supported database)
- Fetches various types of Whoop data:
  - Cycles
  - Sleep
  - Workouts
  - Recoveries
  - User profile information
- Efficient synchronization by only fetching new or updated data

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/whoopsync.git
   cd whoopsync
   ```

2. Create a virtual environment and install the package:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -e .
   ```

## Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file with your Whoop API credentials and other settings:
   ```
   # Whoop API credentials
   WHOOP_CLIENT_ID=your_client_id
   WHOOP_CLIENT_SECRET=your_client_secret
   
   # Database configuration
   DATABASE_URL=sqlite:///whoopsync.db
   
   # Sync settings
   SYNC_INTERVAL=3600  # Sync interval in seconds (1 hour)
   MAX_DATA_RANGE=604800  # Max data range in seconds (7 days)
   
   # User IDs to sync (comma-separated)
   USER_IDS=user1,user2,user3
   ```

## Usage

Run the daemon:
```bash
python -m whoopsync.cli daemon
```

The daemon will run continuously, synchronizing data for all specified users at the configured interval.

## Authentication

Whoopsync requires OAuth tokens for each user you want to sync data for. The package includes an OAuth2 server to handle the authentication flow:

1. Register an application in the [Whoop Developer Portal](https://developer.whoop.com)
2. Set your client ID and secret in the configuration
3. Run the API server to handle authentication:
   ```bash
   ./run_api_server.py --client-id=your_client_id --client-secret=your_client_secret
   ```
4. Direct users to `http://localhost:8000/api/auth/whoop` to start the OAuth flow
5. After users authorize your app, their tokens will be stored in the database

### Token Management

Whoopsync includes a token refresh system to keep OAuth tokens valid:

1. Run the token refresh script periodically (via cron or similar):
   ```bash
   ./refresh_tokens.py --client-id=your_client_id --client-secret=your_client_secret
   ```
2. This will automatically refresh any tokens that are about to expire

## Development

### Setup Development Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
