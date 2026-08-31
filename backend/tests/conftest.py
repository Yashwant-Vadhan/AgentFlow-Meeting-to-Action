"""
conftest.py — pytest configuration for the backend test suite.

Adds the backend/ directory to sys.path so `from app.xxx import ...` works
without installing the package.
"""

import sys
import os

# Make sure `backend/` is on the path when pytest runs from the repo root
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
