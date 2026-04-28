"""Local hardening helpers (log redaction, filesystem permissions)."""

from __future__ import annotations

import os
import re
from pathlib import Path

_SIGNATURE_RE = re.compile(r"signature=[a-f0-9]{20,}", re.IGNORECASE)
_KEY_TAIL_RE = re.compile(r"(api[_-]?key|secret)(=|\":\s*|\':\s*)([^\s&\"']+)", re.IGNORECASE)


def restrict_secret_file(path: Path) -> None:
    """Best-effort owner-only read/write on Unix (no-op on typical Windows)."""
    if os.name != "posix":
        return
    try:
        path.chmod(0o600)
    except OSError:
        pass


def sanitize_log_message(text: str, max_len: int = 240) -> str:
    """Strip patterns that often appear in httpx/Binance errors (query signatures, keys)."""
    if not text:
        return ""
    t = text.strip().replace("\n", " ")
    if len(t) > max_len:
        t = t[: max_len - 3] + "..."
    t = _SIGNATURE_RE.sub("signature=<redacted>", t)
    t = _KEY_TAIL_RE.sub(r"\1\2<redacted>", t)
    return t
