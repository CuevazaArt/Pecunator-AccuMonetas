"""Sub-Account Transfer Service — Moves funds between master and sub-accounts.

Uses the MASTER account API keys to execute universal transfers.
Sub-accounts CANNOT transfer on their own (by design — security).

All transfers are:
  1. Validated against SubAccountRegistry (target must exist and be enabled)
  2. Governed by ApiGovernor (consumes Binance weight)
  3. Logged in TelemetryVault (bot_decisions) for audit trail
  4. Registered in ExceptionZoo on failure

Binance endpoint: POST /sapi/v1/sub-account/universalTransfer
Weight: 1 per call
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import requests

from runtime.core.api_governor import get_api_governor, P_TRADING
from runtime.core.exception_zoo import get_exception_zoo
from runtime.core.subaccount_registry import get_subaccount_registry
from runtime.core.telemetry_vault import get_telemetry_vault

_LOG = logging.getLogger("pecunator.core.transfer_service")

BASE_URL = "https://api.binance.com"
TRANSFER_WEIGHT = 1  # Binance weight per transfer call


class TransferService:
    """Executes and logs asset transfers between master ↔ sub-accounts."""

    def __init__(self, api_key: str, api_secret: str) -> None:
        self._key = api_key
        self._secret = api_secret
        self._governor = get_api_governor()
        self._registry = get_subaccount_registry()
        self._vault = get_telemetry_vault()
        self._zoo = get_exception_zoo()

    def _signed_request(
        self, method: str, path: str, params: dict[str, Any]
    ) -> requests.Response:
        """Make a signed Binance SAPI request."""
        params["timestamp"] = int(time.time() * 1000)
        query = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = hmac.new(
            self._secret.encode(), query.encode(), hashlib.sha256
        ).hexdigest()
        query += f"&signature={signature}"
        headers = {"X-MBX-APIKEY": self._key}
        url = f"{BASE_URL}{path}?{query}"
        if method == "POST":
            return requests.post(url, headers=headers, timeout=30)
        return requests.get(url, headers=headers, timeout=30)

    def fund_bot(
        self,
        bot_id: str,
        asset: str,
        amount: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Transfer funds from MASTER to a bot's sub-account.

        Args:
            bot_id: Internal bot ID (e.g. "dorothy", "elphaba")
            asset: Asset to transfer (e.g. "USDT", "BNB")
            amount: Amount as string (e.g. "100.50")
            dry_run: If True, validate but don't execute

        Returns:
            {"ok": bool, "txn_id": str, "details": ...}
        """
        # Validate target exists
        acct = self._registry.get(bot_id)
        if acct is None:
            return {"ok": False, "error": f"Unknown bot_id: {bot_id}"}
        if not acct.enabled:
            return {"ok": False, "error": f"Account '{bot_id}' is disabled"}

        # Check equity limit
        try:
            max_eq = float(acct.max_equity_usdt)
            if max_eq > 0 and asset.upper() == "USDT" and float(amount) > max_eq:
                return {
                    "ok": False,
                    "error": f"Amount {amount} exceeds max equity {acct.max_equity_usdt} for {bot_id}",
                }
        except ValueError:
            pass

        # Ask ApiGovernor
        allowed, wait = self._governor.request_token(
            "binance", units=TRANSFER_WEIGHT,
            priority=P_TRADING, caller=f"transfer:fund:{bot_id}",
        )
        if not allowed:
            return {"ok": False, "error": f"API Governor denied (wait={wait:.1f}s)"}

        if dry_run:
            return {
                "ok": True,
                "dry_run": True,
                "target": acct.email,
                "asset": asset.upper(),
                "amount": amount,
            }

        # Execute transfer: SPOT → SUB_SPOT
        t0 = time.monotonic()
        try:
            r = self._signed_request("POST", "/sapi/v1/sub-account/universalTransfer", {
                "fromAccountType": "SPOT",
                "toAccountType": "SPOT",
                "toEmail": acct.email,
                "asset": asset.upper(),
                "amount": amount,
            })
            latency = int((time.monotonic() - t0) * 1000)

            self._governor.record_usage(
                "binance", action=f"transfer:fund:{bot_id}",
                units=TRANSFER_WEIGHT, priority=P_TRADING,
                caller="transfer_service", latency_ms=latency,
                success=r.status_code == 200,
            )

            if r.status_code == 200:
                data = r.json()
                txn_id = str(data.get("tranId", ""))
                _LOG.info(
                    "Transfer OK: %s %s -> %s (txn=%s, %dms)",
                    amount, asset, bot_id, txn_id, latency,
                )
                self._vault.log_decision(
                    bot_id=bot_id, bot_type=acct.bot_type or "transfer",
                    decision="FUND", action_taken=True,
                    symbol=asset.upper(),
                    reason=f"Transfer {amount} {asset} from master to {acct.email}",
                    equity_usdt=amount if asset.upper() == "USDT" else "0",
                    context={"txn_id": txn_id, "target_email": acct.email},
                )
                return {"ok": True, "txn_id": txn_id, "latency_ms": latency}
            else:
                err = r.json() if "json" in r.headers.get("content-type", "") else {}
                error_msg = f"{err.get('code', r.status_code)}: {err.get('msg', r.text[:200])}"
                _LOG.error("Transfer FAILED: %s %s -> %s (%s)", amount, asset, bot_id, error_msg)
                return {"ok": False, "error": error_msg}

        except Exception as exc:
            self._zoo.register(exc, module="transfer_service", context=f"fund:{bot_id}")
            return {"ok": False, "error": str(exc)}

    def withdraw_from_bot(
        self,
        bot_id: str,
        asset: str,
        amount: str,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Transfer funds FROM a bot's sub-account back to MASTER."""
        acct = self._registry.get(bot_id)
        if acct is None:
            return {"ok": False, "error": f"Unknown bot_id: {bot_id}"}

        allowed, wait = self._governor.request_token(
            "binance", units=TRANSFER_WEIGHT,
            priority=P_TRADING, caller=f"transfer:withdraw:{bot_id}",
        )
        if not allowed:
            return {"ok": False, "error": f"API Governor denied (wait={wait:.1f}s)"}

        if dry_run:
            return {
                "ok": True, "dry_run": True,
                "source": acct.email, "asset": asset.upper(), "amount": amount,
            }

        t0 = time.monotonic()
        try:
            r = self._signed_request("POST", "/sapi/v1/sub-account/universalTransfer", {
                "fromAccountType": "SPOT",
                "toAccountType": "SPOT",
                "fromEmail": acct.email,
                "asset": asset.upper(),
                "amount": amount,
            })
            latency = int((time.monotonic() - t0) * 1000)

            self._governor.record_usage(
                "binance", action=f"transfer:withdraw:{bot_id}",
                units=TRANSFER_WEIGHT, priority=P_TRADING,
                caller="transfer_service", latency_ms=latency,
                success=r.status_code == 200,
            )

            if r.status_code == 200:
                txn_id = str(r.json().get("tranId", ""))
                _LOG.info("Withdraw OK: %s %s <- %s (txn=%s)", amount, asset, bot_id, txn_id)
                self._vault.log_decision(
                    bot_id=bot_id, bot_type=acct.bot_type or "transfer",
                    decision="WITHDRAW", action_taken=True,
                    symbol=asset.upper(),
                    reason=f"Withdraw {amount} {asset} from {acct.email} to master",
                    equity_usdt=amount if asset.upper() == "USDT" else "0",
                    context={"txn_id": txn_id, "source_email": acct.email},
                )
                return {"ok": True, "txn_id": txn_id, "latency_ms": latency}
            else:
                err = r.json() if "json" in r.headers.get("content-type", "") else {}
                return {"ok": False, "error": f"{err.get('code')}: {err.get('msg', r.text[:200])}"}

        except Exception as exc:
            self._zoo.register(exc, module="transfer_service", context=f"withdraw:{bot_id}")
            return {"ok": False, "error": str(exc)}

    def get_sub_balances(self, bot_id: str) -> dict[str, Any]:
        """Get balance of a sub-account (uses master API, 1 weight)."""
        acct = self._registry.get(bot_id)
        if acct is None:
            return {"ok": False, "error": f"Unknown bot_id: {bot_id}"}

        allowed, _ = self._governor.request_token(
            "binance", units=1, priority=P_TRADING, caller=f"balance:{bot_id}",
        )
        if not allowed:
            return {"ok": False, "error": "Governor denied"}

        try:
            r = self._signed_request("GET", "/sapi/v1/sub-account/assets", {
                "email": acct.email,
            })
            self._governor.record_usage(
                "binance", action=f"balance:{bot_id}", units=1,
                caller="transfer_service", success=r.status_code == 200,
            )
            if r.status_code == 200:
                data = r.json()
                balances = data.get("balances", [])
                # Filter non-zero
                non_zero = [
                    b for b in balances
                    if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0
                ]
                return {"ok": True, "bot_id": bot_id, "balances": non_zero}
            else:
                return {"ok": False, "error": r.text[:200]}
        except Exception as exc:
            self._zoo.register(exc, module="transfer_service", context=f"balances:{bot_id}")
            return {"ok": False, "error": str(exc)}
