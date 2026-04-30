"""Allow `python -m runtime` (same engine entrypoint as root `main.py`)."""

from __future__ import annotations

from runtime.main import main

if __name__ == "__main__":
    main()
