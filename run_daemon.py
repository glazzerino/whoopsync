#!/usr/bin/env python
"""Simple script to run the Whoopsync daemon."""

import os
import sys

# Add the project directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from whoopsync.sync_daemon import main

if __name__ == "__main__":
    main()