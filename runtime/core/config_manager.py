"""Encrypt and store a single Binance API key pair behind a master password."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from runtime.core.security_util import restrict_secret_file

_DEFAULT_ITERATIONS = 480_000
_MIN_MASTER_PASSWORD_LEN = 12


class ConfigManager:
    """Persist API key + secret in a local file, encrypted with Fernet (AES-128-CBC + HMAC)."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._cred_path = self.data_dir / "credentials.enc"
        self._salt_path = self.data_dir / "salt.bin"

    def exists(self) -> bool:
        return self._cred_path.is_file()

    @staticmethod
    def _derive_key(password: str, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=_DEFAULT_ITERATIONS,
        )
        raw = kdf.derive(password.encode("utf-8"))
        return base64.urlsafe_b64encode(raw)

    def _load_or_create_salt(self) -> bytes:
        if self._salt_path.is_file():
            return self._salt_path.read_bytes()
        salt = os.urandom(16)
        self._salt_path.write_bytes(salt)
        restrict_secret_file(self._salt_path)
        return salt

    @staticmethod
    def validate_master_password_strength(master_password: str) -> None:
        if len(master_password) < _MIN_MASTER_PASSWORD_LEN:
            raise ValueError(
                f"Master password must be at least {_MIN_MASTER_PASSWORD_LEN} characters"
            )

    def save_credentials(self, api_key: str, api_secret: str, master_password: str) -> None:
        self.validate_master_password_strength(master_password)
        salt = self._load_or_create_salt()
        key = self._derive_key(master_password, salt)
        f = Fernet(key)
        blob = json.dumps({"api_key": api_key.strip(), "api_secret": api_secret.strip()})
        token = f.encrypt(blob.encode("utf-8"))
        self._cred_path.write_bytes(token)
        restrict_secret_file(self._cred_path)

    def load_credentials(self, master_password: str) -> Optional[Tuple[str, str]]:
        if not self.exists():
            return None
        if not self._salt_path.is_file():
            return None
        salt = self._salt_path.read_bytes()
        key = self._derive_key(master_password, salt)
        f = Fernet(key)
        try:
            raw = f.decrypt(self._cred_path.read_bytes())
        except InvalidToken:
            return None
        data = json.loads(raw.decode("utf-8"))
        return data["api_key"], data["api_secret"]

    def clear_credentials(self) -> None:
        for p in (self._cred_path, self._salt_path):
            if p.is_file():
                p.unlink()
