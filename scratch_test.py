import sys
from pydantic import ValidationError
import os
sys.path.append(os.getcwd())
from runtime.api.schemas import HubBotOut
from runtime.api.elphaba_service import ElphabaService

try:
    data = {
        "bot_id": "123",
        "tag": "Elphaba",
        "created_at": "2026-05-09",
        "running": False,
        "preset_id": "E1",
        "symbol": "XRPUSDT",
        "simulated": False,
        "trading_enabled": False,
        "loop_interval_sec": 450,
        "quote_order_qty": "6",
        "profit_factor": "0.05",
        "margin_rise_factor": "0.03",
        "margin_drop_factor": "0",
        "qty_decimals": 8,
        "price_decimals": 4,
        "note": "",
        "max_drawdown_pct": "0.20",
        "stop_loss_pct": "0.0",
        "metrics_interval_cycles": 5,
        "max_rungs_per_symbol": 3,
        "margin_type": "ISOLATED",
        "last_cycle_ts": None,
        "last_error": None,
        "last_report": {},
    }
    HubBotOut(**data)
    print("Success")
except ValidationError as e:
    print(e)
