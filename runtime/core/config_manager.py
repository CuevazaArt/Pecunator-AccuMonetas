"""Binance credential store: multiple pairs + manifest. Encrypted at rest with a machine-local key."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, List, Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken

from runtime.core.security_util import restrict_secret_file

_MANIFEST = "credential_public.json"
_ACTIVE = "active_credential_id.txt"
_CRED_FILE = "credentials.enc"
_LOCAL_KEY = "vault_local.key"


class ConfigManager:
    """Persist API keys encrypted with a Fernet key stored alongside data (device-local)."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._cred_path = self.data_dir / _CRED_FILE
        self._manifest_path = self.data_dir / _MANIFEST
        self._active_path = self.data_dir / _ACTIVE
        self._key_path = self.data_dir / _LOCAL_KEY

    def exists(self) -> bool:
        return self._cred_path.is_file()

    def _local_fernet(self) -> Fernet:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self._key_path.is_file():
            self._key_path.write_bytes(Fernet.generate_key())
            restrict_secret_file(self._key_path)
        key = self._key_path.read_bytes()
        return Fernet(key)

    def _load_payload(self) -> Optional[dict[str, Any]]:
        if not self.exists():
            return None
        raw = self._cred_path.read_bytes()
        if not raw:
            return None
        try:
            f = self._local_fernet()
            dec = f.decrypt(raw)
        except InvalidToken as e:
            raise ValueError(
                "Cannot read vault file: unsupported or corrupted vault format. "
                "Back up if needed, then delete runtime/data/credentials.enc and runtime/data/vault_local.key, "
                "restart the engine, and add API keys again.",
            ) from e
        data = json.loads(dec.decode("utf-8"))
        migrated = self._migrate_payload_if_needed(data)
        if migrated != data:
            self._encrypt_and_write(migrated)
        return migrated

    def _migrate_payload_if_needed(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            return {"v": 2, "items": []}
        if data.get("v") == 2 and isinstance(data.get("items"), list):
            return data
        if "api_key" in data and "api_secret" in data:
            cid = str(uuid.uuid4())
            return {
                "v": 2,
                "items": [
                    {
                        "id": cid,
                        "api_key": str(data["api_key"]).strip(),
                        "api_secret": str(data["api_secret"]).strip(),
                    }
                ],
            }
        return {"v": 2, "items": []}

    def _encrypt_and_write(self, payload: dict[str, Any]) -> None:
        f = self._local_fernet()
        blob = json.dumps(payload, separators=(",", ":"), sort_keys=True)
        token = f.encrypt(blob.encode("utf-8"))
        self._cred_path.write_bytes(token)
        restrict_secret_file(self._cred_path)
        self._write_manifest_from_payload(payload)

    def _write_manifest_from_payload(self, payload: dict[str, Any]) -> None:
        items = payload.get("items") if isinstance(payload.get("items"), list) else []
        rows: List[dict[str, str]] = []
        for it in items:
            if not isinstance(it, dict):
                continue
            cid = str(it.get("id", "")).strip()
            ak = str(it.get("api_key", "")).strip()
            label = str(it.get("label", "")).strip()
            if cid and ak:
                rows.append({"id": cid, "public_key": ak, "label": label})
        tmp = self._manifest_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, indent=0), encoding="utf-8")
        tmp.replace(self._manifest_path)
        restrict_secret_file(self._manifest_path)

    def list_public_credentials(self) -> List[dict[str, str]]:
        """Ids and public API keys only (no secrets)."""
        if not self._manifest_path.is_file():
            return []
        try:
            raw = json.loads(self._manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(raw, list):
            return []
        out: List[dict[str, str]] = []
        for row in raw:
            if isinstance(row, dict) and row.get("id") and row.get("public_key"):
                out.append(
                    {
                        "id": str(row["id"]),
                        "public_key": str(row["public_key"]),
                        "label": str(row.get("label", "")),
                    }
                )
        return out

    def get_active_credential_id(self) -> Optional[str]:
        if not self._active_path.is_file():
            return None
        try:
            s = self._active_path.read_text(encoding="utf-8").strip()
            return s or None
        except OSError:
            return None

    def set_active_credential_id(self, credential_id: Optional[str]) -> None:
        if not credential_id:
            if self._active_path.is_file():
                self._active_path.unlink()
            return
        self._active_path.write_text(credential_id.strip(), encoding="utf-8")
        restrict_secret_file(self._active_path)

    def _find_item(
        self, items: List[dict[str, Any]], credential_id: str
    ) -> Optional[dict[str, Any]]:
        for it in items:
            if isinstance(it, dict) and str(it.get("id")) == credential_id:
                return it
        return None

    def _reset_unreadable_vault(self) -> None:
        for p in (self._cred_path, self._manifest_path, self._active_path, self._key_path):
            if p.is_file():
                p.unlink()

    def _known_credential_ids(self) -> List[str]:
        return [str(r.get("id", "")).strip() for r in self.list_public_credentials() if str(r.get("id", "")).strip()]

    def add_credential(
        self,
        api_key: str,
        api_secret: str,
        label: str = "",
    ) -> Tuple[str, bool]:
        """
        Add or update a credential.
        If the same API key (public) already exists, only the secret is updated.
        Returns (credential_id, updated_existing).
        """
        vault_existed = self.exists()
        try:
            payload = self._load_payload()
        except ValueError:
            if vault_existed:
                self._reset_unreadable_vault()
                payload = None
            else:
                raise
        if vault_existed and payload is None:
            payload = {"v": 2, "items": []}
        if payload is None:
            payload = {"v": 2, "items": []}
        items = payload.get("items")
        if not isinstance(items, list):
            items = []

        ak_n = api_key.strip()
        sk_n = api_secret.strip()
        label_n = label.strip()
        for it in items:
            if not isinstance(it, dict):
                continue
            prev = str(it.get("api_key", "")).strip()
            if prev == ak_n:
                it["api_secret"] = sk_n
                if label_n:
                    it["label"] = label_n
                payload["v"] = 2
                payload["items"] = items
                cid = str(it.get("id", "")).strip()
                if cid:
                    self._encrypt_and_write(payload)
                    self.set_active_credential_id(cid)
                    return cid, True
        cid = str(uuid.uuid4())
        items.append({"id": cid, "api_key": ak_n, "api_secret": sk_n, "label": label_n})
        payload["v"] = 2
        payload["items"] = items
        self._encrypt_and_write(payload)
        self.set_active_credential_id(cid)
        return cid, False

    def update_credential_label(self, credential_id: str, label: str) -> bool:
        vault_existed = self.exists()
        try:
            payload = self._load_payload()
        except ValueError:
            if vault_existed:
                self._reset_unreadable_vault()
            return False
        if vault_existed and payload is None:
            raise ValueError("Cannot unlock vault: unreadable credential file.")
        if payload is None:
            return False
        items = payload.get("items")
        if not isinstance(items, list):
            return False
        target = self._find_item(items, credential_id)
        if target is None:
            return False
        target["label"] = (label or "").strip()
        payload["items"] = items
        self._encrypt_and_write(payload)
        return True

    def remove_credential(self, credential_id: str) -> bool:
        vault_existed = self.exists()
        known_ids = self._known_credential_ids()
        try:
            payload = self._load_payload()
        except ValueError:
            if vault_existed:
                # If the encrypted payload is unreadable, the safest repair path is resetting
                # the local vault files. This unblocks the UI instead of leaving it stuck.
                self._reset_unreadable_vault()
                return credential_id in known_ids or bool(known_ids)
            return False
        if vault_existed and payload is None:
            raise ValueError("Cannot unlock vault: unreadable credential file.")
        if payload is None:
            return False
        items = payload.get("items")
        if not isinstance(items, list):
            return False
        new_items = [it for it in items if isinstance(it, dict) and str(it.get("id")) != credential_id]
        if len(new_items) == len(items):
            return False
        payload["items"] = new_items
        self._encrypt_and_write(payload)
        if self.get_active_credential_id() == credential_id:
            self.set_active_credential_id(new_items[0]["id"] if new_items else None)
        return True

    def get_secret_pair(self, credential_id: str) -> Optional[Tuple[str, str]]:
        if not self.exists():
            return None
        payload = self._load_payload()
        if payload is None:
            raise ValueError("Cannot unlock vault: unreadable credential file.")
        items = payload.get("items")
        if not isinstance(items, list):
            return None
        it = self._find_item(items, credential_id)
        if not it:
            return None
        return str(it["api_key"]).strip(), str(it["api_secret"]).strip()

    def get_pair_for_active(self) -> Optional[Tuple[str, str]]:
        """Return key pair for active id, or first item."""
        if not self.exists():
            return None
        payload = self._load_payload()
        if payload is None:
            raise ValueError("Cannot unlock vault: unreadable credential file.")
        items_raw = payload.get("items")
        if not isinstance(items_raw, list):
            return None
        items = [
            it
            for it in items_raw
            if isinstance(it, dict)
            and str(it.get("api_key", "")).strip()
            and str(it.get("api_secret", "")).strip()
        ]
        if not items:
            return None
        aid = self.get_active_credential_id()
        chosen: Optional[dict[str, Any]] = None
        if aid:
            chosen = next((it for it in items if str(it.get("id")) == str(aid)), None)
        if chosen is None:
            chosen = items[0]
            cid = str(chosen.get("id", "")).strip()
            if cid:
                self.set_active_credential_id(cid)
        ak = str(chosen.get("api_key", "")).strip()
        sec = str(chosen.get("api_secret", "")).strip()
        if not ak or not sec:
            return None
        return ak, sec

    def save_credentials(self, api_key: str, api_secret: str) -> None:
        """Backward-compatible: replace vault with a single credential."""
        cid = str(uuid.uuid4())
        payload = {
            "v": 2,
            "items": [
                {
                    "id": cid,
                    "api_key": api_key.strip(),
                    "api_secret": api_secret.strip(),
                }
            ],
        }
        self._encrypt_and_write(payload)
        self.set_active_credential_id(cid)

    def load_credentials(self) -> Optional[Tuple[str, str]]:
        """Return first pair (compat) or active/first resolved pair."""
        return self.get_pair_for_active()

    def clear_credentials(self) -> None:
        for p in (
            self._cred_path,
            self._manifest_path,
            self._active_path,
            self._key_path,
        ):
            if p.is_file():
                p.unlink()
