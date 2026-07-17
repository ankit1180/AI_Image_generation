"""Application package."""

import sys
from pathlib import Path

# Add project root directory to sys.path to allow importing from scraper folder
root_dir = Path(__file__).resolve().parents[2]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
