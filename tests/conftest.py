"""Pytest configuration - adds project root to Python path."""
import sys
from pathlib import Path

# Add project root to Python path so 'backend' module can be imported
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
