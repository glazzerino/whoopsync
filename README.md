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

Whoopsync requires OAuth tokens for each user you want to sync data for. In a production environment, you would need to set up OAuth authentication for each user. For development and testing, you can use:

1. Register an application in the Whoop Developer Portal
2. Follow the OAuth flow to get tokens for each user
3. Store these tokens securely and provide them to Whoopsync

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
