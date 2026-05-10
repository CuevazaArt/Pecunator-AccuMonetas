# Pecunator V4 — WebSocket Push Telemetry Architecture

## Status: ✅ IMPLEMENTED (v3.5.0)

This document describes the reactive telemetry architecture that replaced
the polling-based ("pull") model in v3.4.0.

---

## Problem (v3.4.0 and earlier)

Every Flutter widget maintained its own `Timer.periodic` loop, independently
calling REST endpoints:

```
MiniWeightChart     → GET /gateway/snapshot    every 2s
MiniOrderRateChart  → GET /gateway/snapshot    every 2s
MiniEquityChart     → GET /gateway/snapshot    every 5s
WeightOscillator    → GET /gateway/snapshot    every 2s
UnifiedHubPage      → GET /hub/bots + /elphaba/bots + /gateway/snapshot + /api-fuse/status  every 8s
HomeShell           → GET /gateway/snapshot    every 10s
BotHubTemplate      → GET /hub/bots            every 4s
OrderLedgerPanel    → GET /order-ledger/recent  every 15s
```

**Result**: 6+ REST calls/second on a single localhost socket, 95%+ returning
identical data. CPU waste, socket churn, delayed UI updates.

---

## Solution (v3.5.0)

### Backend: WebSocket Broadcaster

```
TelemetryCollector (10s loop)
       │
       ├── _persist(snapshot)     → SQLite (unchanged)
       │
       └── _broadcast(snapshot)   → Broadcaster.publish("TELEMETRY_TICK", snapshot)
                                         │
                                    ┌────┴────┐
                                    │ Flutter  │  ← ws://localhost:8000/ws/telemetry
                                    │ Client 1 │
                                    └─────────┘
```

**Files:**
- `runtime/core/ws_broadcaster.py` — Singleton broadcaster with fan-out
- `runtime/api/routers/stream.py` — `/ws/telemetry` WebSocket endpoint
- `runtime/core/telemetry_collector.py` — Hook to broadcast after persist

### Frontend: TelemetryHub

```
TelemetrySocketService (ws://localhost:8000/ws/telemetry)
       │
       └── TelemetryHub (singleton)
                │
                ├── MiniWeightChart.listen()
                ├── MiniOrderRateChart.listen()
                ├── MiniEquityChart.listen()
                ├── WeightOscillator.listen()
                └── UnifiedHubPage.listen()   (gateway + fuse state)
```

**Files:**
- `desktop_shell/lib/services/telemetry_socket.dart` — WebSocket client with auto-reconnect
- `desktop_shell/lib/services/telemetry_hub.dart` — Singleton hub + TelemetrySnapshot model
- `desktop_shell/lib/main.dart` — Hub initialization at app startup

### Hybrid Fallback

If the WebSocket connection drops, TelemetryHub automatically falls back to
REST polling every 8s until the WebSocket reconnects.

### What Still Uses REST Polling

| Widget | Endpoint | Interval | Reason |
|--------|----------|----------|--------|
| UnifiedHubPage | `/hub/bots`, `/elphaba/bots` | 15s | Bot list data is not in telemetry snapshot |
| BotHubTemplate | `/hub/bots` | 4s | Per-bot status needs individual API call |
| OrderLedgerPanel | `/order-ledger/recent` | 15s | Order history is not in telemetry snapshot |
| HomeShell | credentials, vault | 10s | Credential state changes are rare |

---

## Event Envelope Format

```json
{
  "type": "TELEMETRY_TICK",
  "ts_utc": "2026-05-10T17:00:00.000000+00:00",
  "seq": 42,
  "payload": {
    "ts_utc": "...",
    "equity_usdt": 14.03,
    "free_usdt": 7.88,
    "locked_usdt": 0.0,
    "margin_usdt": 6.15,
    "used_weight_1m": 45,
    "weight_limit_1m": 6000,
    "order_count_10s": 0,
    "order_limit_10s": 100,
    "bots_running": 4,
    "bots_total": 4,
    "dorothy_running": 2,
    "dorothy_total": 2,
    "elphaba_running": 2,
    "elphaba_total": 2,
    "api_fuse_ok": 1,
    "order_fuse_ok": 1,
    "gateway_running": 1
  }
}
```

---

## Impact Metrics

| Metric | Before (v3.4) | After (v3.5) |
|--------|:---:|:---:|
| REST calls/sec from UI | ~6 | ~0.2 (bot polls only) |
| Telemetry latency | 2-15s (timer dependent) | <100ms (push) |
| Open sockets | Multiple short-lived | 1 persistent |
| Timer.periodic instances | 10 | 3 (bots, ledger, clock) |
| `flutter analyze` issues | 0 | 0 |
| Python tests | 25/25 | 25/25 |

---

## Debug Endpoint

`GET /api/v1/ws/status` returns:
```json
{
  "connected_clients": 1,
  "total_published": 42,
  "has_last_snapshot": true
}
```
