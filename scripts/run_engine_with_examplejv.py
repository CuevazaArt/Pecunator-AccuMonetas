"""Start the Pecunator engine after loading optional credentials from exampleJV/config.py.

If `exampleJV/config.py` exists and defines `api_key` / `api_secret`, they are applied to
`PECUNATOR_BINANCE_API_KEY` / `PECUNATOR_BINANCE_API_SECRET` when those env vars are unset,
so the HTTP API can resolve Binance keys the same way as manual env export.

Does not print secrets. Never commit config.py.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    cfg = root / "exampleJV" / "config.py"
    if cfg.is_file():
        import runpy

        data = runpy.run_path(str(cfg))
        ak = str(data.get("api_key", "") or "").strip()
        sec = str(data.get("api_secret", "") or "").strip()
        if ak and sec:
            os.environ.setdefault("PECUNATOR_BINANCE_API_KEY", ak)
            os.environ.setdefault("PECUNATOR_BINANCE_API_SECRET", sec)

    sys.path.insert(0, str(root))
    os.chdir(root)
    from runtime.main import main as engine_main

    engine_main()


if __name__ == "__main__":
    main()
