"""Quarantine legacy tests — prevent collection entirely.

These tests depend on a `config.py` module from the pre-modular era.
They are preserved for historical reference but excluded from the active suite.
"""

import os

# Tell pytest to ignore all test files in this directory
collect_ignore_glob = ["test_*.py"]
