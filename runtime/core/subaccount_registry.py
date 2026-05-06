"""Sub-Account Registry — Maps Pecunator bots to Binance sub-accounts.

Central source of truth for which sub-account belongs to which bot/function.
API keys for sub-accounts are stored separately in the encrypted vault
(config_manager.py) and referenced here by account_id.

SECURITY: This file contains ONLY email identifiers, NEVER API keys.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

_LOG = logging.getLogger("pecunator.core.subaccount_registry")

_REGISTRY_FILE = "subaccount_registry.json"


@dataclass
class SubAccountEntry:
    """A single sub-account registration."""
    account_id: str                    # Internal short ID (e.g. "dorothy")
    email: str                         # Binance sub-account email
    role: str                          # "bot" | "strategy" | "reserve" | "personal"
    bot_type: str = ""                 # "dorothy" | "masha" | "thusnelda" | ""
    description: str = ""              # Human-readable description
    symbols: list[str] = field(default_factory=list)  # Assigned trading pairs
    max_equity_usdt: str = "0"         # Max capital allocation
    enabled: bool = True               # Active or paused
    api_key_label: str = ""            # Label in encrypted vault (NOT the key itself)


# Default registry — the 5 sub-accounts
_DEFAULT_REGISTRY: list[SubAccountEntry] = [
    SubAccountEntry(
        account_id="dorothy",
        email="dorothybot_virtual@j7tmq9bmnoemail.com",
        role="bot",
        bot_type="dorothy",
        description="Trend-following scalper — rides momentum breakouts",
        symbols=["BTCUSDT", "ETHUSDT", "SOLUSDT"],
        max_equity_usdt="500",
        api_key_label="DOROTHY_API",
    ),
    SubAccountEntry(
        account_id="masha",
        email="mashabot_virtual@js13xxewnoemail.com",
        role="bot",
        bot_type="masha",
        description="DCA range bot — accumulates in sideways markets",
        symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        max_equity_usdt="500",
        api_key_label="MASHA_API",
    ),
    SubAccountEntry(
        account_id="thusnelda",
        email="xrpacum_virtual@6nfrqwurnoemail.com",
        role="bot",
        bot_type="thusnelda",
        description="Opportunistic multi-symbol — quick snipes on volatility spikes",
        symbols=["XRPUSDT", "ADAUSDT", "DOGEUSDT", "AVAXUSDT"],
        max_equity_usdt="300",
        api_key_label="THUSNELDA_API",
    ),
    SubAccountEntry(
        account_id="bluechip",
        email="etfbluechipexpert_virtual@vfu3gqt4noemail.com",
        role="strategy",
        bot_type="",
        description="ETF/BlueChip passive strategy — Earn, staking, long-term holds",
        symbols=["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"],
        max_equity_usdt="0",  # No trading limit, managed manually
        api_key_label="BLUECHIP_API",
    ),
    SubAccountEntry(
        account_id="reserve",
        email="arq.valenteochoa@gmail.com",
        role="personal",
        bot_type="",
        description="Personal/Reserve account — emergency capital, manual operations",
        symbols=[],
        max_equity_usdt="0",
        api_key_label="RESERVE_API",
    ),
]


class SubAccountRegistry:
    """Manages the mapping between bots and Binance sub-accounts."""

    def __init__(self, data_dir: Path) -> None:
        self._path = Path(data_dir) / _REGISTRY_FILE
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._accounts: list[SubAccountEntry] = []
        self._load()

    def _load(self) -> None:
        """Load registry from disk, or initialize with defaults."""
        if self._path.is_file():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._accounts = [
                    SubAccountEntry(**entry) for entry in data.get("accounts", [])
                ]
                _LOG.info("Loaded %d sub-accounts from registry", len(self._accounts))
                return
            except Exception as exc:
                _LOG.warning("Failed to load registry, using defaults: %s", exc)

        # Initialize with defaults
        self._accounts = list(_DEFAULT_REGISTRY)
        self._save()
        _LOG.info("Initialized registry with %d default sub-accounts", len(self._accounts))

    def _save(self) -> None:
        """Persist registry to disk."""
        data = {
            "version": 1,
            "accounts": [asdict(a) for a in self._accounts],
        }
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    # ── Queries ─────────────────────────────────────────────────────

    def get(self, account_id: str) -> Optional[SubAccountEntry]:
        """Get a sub-account by internal ID."""
        for a in self._accounts:
            if a.account_id == account_id:
                return a
        return None

    def get_by_email(self, email: str) -> Optional[SubAccountEntry]:
        for a in self._accounts:
            if a.email == email:
                return a
        return None

    def get_bot_account(self, bot_type: str) -> Optional[SubAccountEntry]:
        """Get the sub-account assigned to a specific bot type."""
        for a in self._accounts:
            if a.bot_type == bot_type and a.enabled:
                return a
        return None

    def list_all(self) -> list[SubAccountEntry]:
        return list(self._accounts)

    def list_bots(self) -> list[SubAccountEntry]:
        return [a for a in self._accounts if a.role == "bot" and a.enabled]

    def list_active(self) -> list[SubAccountEntry]:
        return [a for a in self._accounts if a.enabled]

    # ── Mutations ───────────────────────────────────────────────────

    def update_equity_limit(self, account_id: str, max_usdt: str) -> bool:
        """Update the capital allocation limit for a sub-account."""
        acct = self.get(account_id)
        if acct:
            acct.max_equity_usdt = max_usdt
            self._save()
            return True
        return False

    def toggle_enabled(self, account_id: str, enabled: bool) -> bool:
        acct = self.get(account_id)
        if acct:
            acct.enabled = enabled
            self._save()
            return True
        return False

    def assign_symbols(self, account_id: str, symbols: list[str]) -> bool:
        acct = self.get(account_id)
        if acct:
            acct.symbols = symbols
            self._save()
            return True
        return False

    def summary(self) -> dict[str, Any]:
        bots = self.list_bots()
        return {
            "total_accounts": len(self._accounts),
            "active_bots": len(bots),
            "accounts": [
                {
                    "id": a.account_id,
                    "role": a.role,
                    "bot": a.bot_type or "—",
                    "symbols": len(a.symbols),
                    "max_equity": a.max_equity_usdt,
                    "enabled": a.enabled,
                }
                for a in self._accounts
            ],
        }


# ── Singleton ───────────────────────────────────────────────────────

_registry: Optional[SubAccountRegistry] = None


def get_subaccount_registry(data_dir: Optional[Path] = None) -> SubAccountRegistry:
    global _registry
    if _registry is None:
        d = data_dir or Path("runtime/data")
        _registry = SubAccountRegistry(d)
    return _registry
