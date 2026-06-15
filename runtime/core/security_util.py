"""Local hardening helpers (log redaction, filesystem permissions, vault key derivation)."""

from __future__ import annotations

import os
import re
import secrets
import hashlib
import logging
from pathlib import Path
from cryptography.fernet import Fernet

_LOG = logging.getLogger("pecunator.security")

_SIGNATURE_RE = re.compile(r"signature=[a-f0-9]{20,}", re.IGNORECASE)
_KEY_TAIL_RE = re.compile(r"(api[_-]?key|secret)(=|\":\s*|\':\s*)([^\s&\"']+)", re.IGNORECASE)

# Key derivation constants
_PBKDF2_ITERATIONS = 100000
_PBKDF2_HASH_NAME = "sha256"
_SALT_LENGTH = 32  # 256 bits


def restrict_secret_file(path: Path) -> None:
    """Best-effort owner-only read/write permissions.

    On POSIX: chmod 600.
    On Windows: uses icacls to remove inherited permissions and grant
    full control only to the current user.
    """
    if os.name == "posix":
        try:
            path.chmod(0o600)
        except OSError:
            pass
    elif os.name == "nt":
        import subprocess
        try:
            p = str(path)
            # Remove inherited permissions, grant only current user
            subprocess.run(
                ["icacls", p, "/inheritance:r", "/grant:r",
                 f"{os.environ.get('USERNAME', 'CURRENT_USER')}:(R,W)"],
                capture_output=True, timeout=10,
            )
        except Exception:
            _LOG.debug("Could not restrict permissions on %s (Windows)", path)


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


def derive_key_from_passphrase(passphrase: str, salt: bytes | None = None) -> tuple[str, str]:
    """
    Derive a 32-byte key from a passphrase using PBKDF2.
    Returns (base64_key, base64_salt) for storage.
    If salt is None, generates new random salt.
    """
    if salt is None:
        salt = secrets.token_bytes(_SALT_LENGTH)
    else:
        if isinstance(salt, str):
            import base64
            salt = base64.b64decode(salt)

    # PBKDF2-SHA256: derive 32 bytes for Fernet key
    derived = hashlib.pbkdf2_hmac(
        _PBKDF2_HASH_NAME,
        passphrase.encode("utf-8"),
        salt,
        _PBKDF2_ITERATIONS,
    )

    import base64
    key_b64 = base64.b64encode(derived).decode("ascii")
    salt_b64 = base64.b64encode(salt).decode("ascii")

    return key_b64, salt_b64


def get_fernet_key_from_passphrase(passphrase: str, salt: str) -> str:
    """
    Convert a passphrase + salt to a Fernet-compatible key.
    Salt should be base64-encoded from storage.
    Returns base64-encoded Fernet key.
    """
    key_b64, _ = derive_key_from_passphrase(passphrase, salt)

    # Fernet requires URL-safe base64, but PBKDF2 output is already bytes
    # We need to pad the derived key to 32 bytes for Fernet
    import base64
    derived_bytes = base64.b64decode(key_b64)
    if len(derived_bytes) != 32:
        raise ValueError(f"Derived key size {len(derived_bytes)} != 32")

    # Fernet key = base64(derived_key)
    fernet_key = base64.urlsafe_b64encode(derived_bytes)
    return fernet_key.decode("ascii")


def encrypt_data(data: str, fernet_key: str) -> str:
    """
    Encrypt a string using Fernet (AES-128-CBC) with the provided key.
    Key should be base64-encoded from get_fernet_key_from_passphrase().
    Returns base64-encoded ciphertext.
    """
    cipher = Fernet(fernet_key.encode("utf-8"))
    ciphertext = cipher.encrypt(data.encode("utf-8"))
    return ciphertext.decode("ascii")


def decrypt_data(ciphertext: str, fernet_key: str) -> str:
    """
    Decrypt a string using Fernet.
    Returns plaintext string.
    """
    cipher = Fernet(fernet_key.encode("utf-8"))
    try:
        plaintext = cipher.decrypt(ciphertext.encode("utf-8"))
        return plaintext.decode("utf-8")
    except Exception as e:
        raise ValueError(f"Decryption failed (wrong passphrase?): {e}")


def audit_log_vault_event(event: str, details: str = "") -> None:
    """
    Log vault operations to audit trail for compliance.
    Events: unlock, lock, rotate_key, derive_key, encrypt, decrypt.
    Audit log location: runtime/data/vault_audit.log
    """
    from runtime.core.settings import data_dir
    audit_path = Path(data_dir()) / "vault_audit.log"

    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat()
    audit_entry = f"[{timestamp}] {event}"
    if details:
        audit_entry += f" - {sanitize_log_message(details)}"

    try:
        with open(audit_path, "a") as f:
            f.write(audit_entry + "\n")
    except Exception as e:
        _LOG.warning("Failed to write vault audit log: %s", e)
