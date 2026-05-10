"""Pydantic payloads for the engine API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class GatewayStartBody(BaseModel):
    api_key: Optional[str] = Field(default=None, description="Optional one-shot API key")
    api_secret: Optional[str] = Field(default=None, description="Optional one-shot API secret")


class VaultStatusOut(BaseModel):
    vault_file_exists: bool
    credential_rows: int
    active_credential_id: Optional[str]


class ActiveCredentialOut(BaseModel):
    source: str
    public_key_hint: str
    public_key_last4: str
    active_credential_id: Optional[str] = None
    label: Optional[str] = None


class VaultCredentialUpsertBody(BaseModel):
    api_key: str = Field(min_length=8)
    api_secret: str = Field(min_length=8)
    label: Optional[str] = Field(default=None, max_length=80)


class VaultCredentialLabelBody(BaseModel):
    label: str = Field(default="", max_length=80)


class GatewaySnapshotOut(BaseModel):
    gateway_running: bool
    last_error: Optional[str]
    account_summary: dict[str, Any]
    account_equity: dict[str, Any] = Field(
        default_factory=dict,
        description="Rolling spot equity converted to base asset (current/avg/high_avg).",
    )
    balances: list[dict[str, Any]]
    balances_total_assets_in_response: int
    ws_connected: bool
    selected_symbol: str
    used_weight_1m: Optional[int] = Field(
        default=None,
        description="X-MBX-USED-WEIGHT-1M from last REST response (shared per IP)",
    )
    weight_limit_1m: int = Field(
        default=6000,
        description="Display cap; default from PECUNATOR_API_WEIGHT_LIMIT_1M or 6000",
    )
    binance_server_time_ms: Optional[int] = Field(
        default=None,
        description="Last server time obtained from Binance (/api/v3/time)",
    )
    binance_local_time_ms_at_sync: Optional[int] = Field(
        default=None,
        description="Local epoch ms captured when server time was last synced",
    )
    binance_offset_ms: Optional[int] = Field(
        default=None,
        description="server_time_ms - local_time_ms_at_sync",
    )
    binance_time_synced_at_utc: Optional[str] = Field(
        default=None,
        description="UTC timestamp when last Binance clock sync finished",
    )


class BotConfigBody(BaseModel):
    symbol: str = Field(default="XRPUSDT", min_length=5, max_length=32)
    loop_interval_sec: int = Field(default=450, ge=1, le=86400)
    quote_order_qty: str = Field(default="8")
    profit_factor: str = Field(default="0.05")
    margin_drop_factor: str = Field(default="0.004")
    qty_decimals: int = Field(default=8, ge=0, le=18)
    price_decimals: int = Field(default=4, ge=0, le=18)
    note: str = Field(default="", max_length=20)


class BotConfigOut(BaseModel):
    preset_id: str
    symbol: str
    loop_interval_sec: int
    quote_order_qty: str
    profit_factor: str
    margin_drop_factor: str
    qty_decimals: int
    price_decimals: int
    note: str
    mode: str


class BotStatusOut(BaseModel):
    running: bool
    preset_id: str
    symbol: str
    loop_interval_sec: int
    last_cycle_ts: Optional[str]
    last_error: Optional[str]
    last_report: dict[str, Any]


class TerminalExecBody(BaseModel):
    command: str = Field(min_length=1, max_length=512)


class TerminalExecOut(BaseModel):
    ok: bool
    command: str
    output: str


class TimeSyncBody(BaseModel):
    api_key: Optional[str] = Field(default=None, description="Optional one-shot API key")
    api_secret: Optional[str] = Field(default=None, description="Optional one-shot API secret")


class TimeSyncOut(BaseModel):
    ok: bool
    source: str
    local_time_ms: int
    server_time_ms: int
    offset_ms: int


class HubBotCreateBody(BaseModel):
    bot_id: Optional[str] = None
    tag: str = Field(default="Dorothy", min_length=1, max_length=64)
    symbol: str = Field(default="XRPUSDT", min_length=5, max_length=32)
    loop_interval_sec: int = Field(default=450, ge=1, le=86400)
    quote_order_qty: str = Field(default="8")
    profit_factor: str = Field(default="0.05")
    margin_drop_factor: str = Field(default="0.004")
    margin_rise_factor: Optional[str] = Field(default=None)
    qty_decimals: int = Field(default=8, ge=0, le=18)
    price_decimals: int = Field(default=4, ge=0, le=18)
    note: str = Field(default="", max_length=20)
    max_drawdown_pct: str = Field(default="0.20")
    stop_loss_pct: str = Field(default="0.10")
    metrics_interval_cycles: int = Field(default=5, ge=1, le=10000)


class HubBotUpdateBody(BaseModel):
    tag: Optional[str] = Field(default=None, min_length=1, max_length=64)
    symbol: Optional[str] = Field(default=None, min_length=5, max_length=32)
    loop_interval_sec: Optional[int] = Field(default=None, ge=1, le=86400)
    quote_order_qty: Optional[str] = None
    profit_factor: Optional[str] = None
    margin_drop_factor: Optional[str] = None
    margin_rise_factor: Optional[str] = None
    qty_decimals: Optional[int] = Field(default=None, ge=0, le=18)
    price_decimals: Optional[int] = Field(default=None, ge=0, le=18)
    note: Optional[str] = Field(default=None, max_length=20)
    max_drawdown_pct: Optional[str] = None
    stop_loss_pct: Optional[str] = None
    metrics_interval_cycles: Optional[int] = Field(default=None, ge=1, le=10000)


class HubBotOut(BaseModel):
    bot_id: str
    tag: str
    created_at: str
    running: bool
    preset_id: str
    symbol: str
    loop_interval_sec: int
    quote_order_qty: str
    profit_factor: str
    margin_drop_factor: str
    margin_rise_factor: Optional[str] = None
    qty_decimals: int
    price_decimals: int
    note: str
    max_drawdown_pct: str
    stop_loss_pct: str = "0"
    metrics_interval_cycles: int
    last_cycle_ts: Optional[str]
    last_error: Optional[str]
    last_report: dict[str, Any]


class HubBotsOut(BaseModel):
    bots: list[HubBotOut]


class HubBotLogsOut(BaseModel):
    logs: list[dict[str, Any]]


