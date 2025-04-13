"""Command line interface for Whoopsync."""

import argparse
import logging
import sys

from whoopsync.sync_daemon import main as run_daemon


def main() -> None:
    """Run the command line interface."""
    parser = argparse.ArgumentParser(description="Whoopsync - Sync Whoop health data locally")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Daemon command
    daemon_parser = subparsers.add_parser("daemon", help="Run the sync daemon")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Handle commands
    if args.command == "daemon":
        run_daemon()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()