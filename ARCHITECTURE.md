# Pecunator-AccuMonetas Architecture

## Overview

Pecunator-AccuMonetas is a **Louise DCA (Dollar-Cost Averaging) bot hub** that reuses PecunatorCore's proven architecture while adding specialized trading logic for autonomous DCA strategies.

**Stack:**
- **Backend:** FastAPI + asyncio (Python 3.11+)
- **Database:** SQLite with WAL for crash-safety
- **UI:** Flutter (Windows native, extensible to Linux/macOS)
- **Real-time:** WebSocket for telemetry push
- **Exchange:** Binance (async python-binance)
- **Credentials:** Fernet-encrypted vault

---

## Core Components

### 1. **Louise Bot Runner** (`runtime/bot/louise.py`)

Main loop that implements DCA logic:

- **Polling Model:** Configurable interval (default 60s)
- **Exit Conditions (checked first):**
  - Take-profit: `current_pnl >= target_profit_pct`
  - Stop-loss: `current_pnl <= max_drawdown_pct` (default -10%)
  - Max purchases: `num_purchases >= max_purchases_per_epoch` (default 20)
- **Buy Gating (after exit checks):**
  - Check API governor (rate-limit zone)
  - Check budget guard (global daily spend)
  - Check local daily budget (per-bot limit)
  - Check position-size limit: `current_exposure >= max_position_size_usdt`
  - Check price staleness (>15s = wait)
  - Check exchange filters (MIN_NOTIONAL)
- **Execution:**
  - BUY: market order, recorded via WebSocket fill event
  - SELL: market order, epoch closed with P&L
- **Resilience:**
  - Cooldown backoff on failures (60s for buy fail, 300s for gateway fail)
  - Logging on every decision (governor block, budget block, etc.)

### 2. **REST API** (`runtime/api/app.py` + routers)

**Endpoints (all require Bearer token auth):**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/louise/bots` | GET | List all bots with state |
| `/api/louise/bots` | POST | Create bot (validates symbol, config, initializes) |
| `/api/louise/bots/{id}` | PATCH | Update daily_budget, target_profit (validates) |
| `/api/louise/bots/{id}/pause` | POST | Pause trading (status → PAUSED) |
| `/api/louise/bots/{id}/resume` | POST | Resume trading (status → RUNNING) |
| `/api/louise/bots/{id}` | DELETE | Mark as SHUTDOWN |
| `/api/louise/health` | GET | Real health: active bots, weight zone (not hardcoded) |
| `/api/louise/metrics` | GET | Aggregated: portfolio value, PnL, active bots |
| `/api/louise/weight-governor/status` | GET | Real API weight or explicit error (no fake data) |
| `/api/louise/weight-governor/history` | GET | Weight snapshots (if available) |

**Key Improvements (P0 fixes):**
- `create_bot`: validates config, calls `LouiseBotRunner.initialize()` before RUNNING
- `update_bot`: validates new params before DB write
- `/health`: returns real state (active bots, paused count, weight zone)
- `/weight-governor/*`: returns actual values or explicit error, never "1050" fallback

### 3. **Database** (`runtime/core/louise_db.py`)

**Tables:**
- `louise_bots`: bot config (symbol, budget, target_profit, poll_interval, **max_position_size_usdt**, **max_purchases_per_epoch**)
- `louise_epochs`: DCA cycles (num_purchases, total_cost, avg_buy_price, final_price, profit_pct, status)
- `louise_purchases`: fills (bot_id, epoch_id, price_at_buy, volume, cost_usdt, order_id, status)

**Migrations:** ALTER TABLE with try-except for safe backfill of `max_position_size_usdt`, `max_purchases_per_epoch` columns

### 4. **WebSocket Streaming** (`runtime/api/routers/stream.py`)

- Endpoint: `/ws/telemetry` (auth via token query param or x-api-token header)
- Pushes: telemetry ticks, fuse trips, critical alerts
- Flutter client subscribes for real-time bot state

### 5. **Risk Control Modules** (inherited from PecunatorCore)

| Module | Purpose | Action |
|--------|---------|--------|
| **WeightGovernor** | API weight-limit zones (GREEN/YELLOW/RED) | Blocks bot if RED or weight > limit |
| **ApiFuse** | Circuit breaker (trip on sustained high weight/errors) | Blocks all orders, requires manual reset |
| **BudgetGuard** | Global daily USDT spend ceiling | Blocks bot buy if budget exhausted for day |
| **OrderLedger** | Forensic audit trail (every order) | Logged, queryable for reconciliation |
| **ExchangeFilters** | Binance LOT_SIZE, MIN_NOTIONAL, PRICE_FILTER | Validates quantities before placing orders |
| **AlertDispatcher** | Telegram/email alerts | BUY_FAILED, STOP_LOSS, FUSE_TRIPPED, etc. |

---

## Deployment Workflow

### Local Development

```bash
# 1. Setup
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt

# 2. Engine
powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine.ps1
# Runs on http://localhost:8000

# 3. Flutter UI (new terminal)
cd desktop_shell
flutter pub get
flutter run -d windows

# 4. Tests
pytest runtime/tests/ -x -q
```

### CI/CD Gates (GitHub Actions)

**Required for merge to main:**
1. ✅ `pytest runtime/tests/ -x` (Python tests)
2. ✅ `ruff check` (linting)
3. ✅ `flutter analyze` (Flutter analysis)
4. ⚠️ `flutter test` (Flutter tests — P1.6 to enforce)

### Pre-Production Checklist

- [ ] All tests pass (Python + Flutter)
- [ ] `GET /health` returns real state (not hardcoded)
- [ ] `GET /weight-governor/status` returns real weight or explicit error
- [ ] Bot creation validates config and initializes successfully
- [ ] Endpoints reject invalid budgets/targets with 400 errors
- [ ] Budget guard blocks second bot if daily budget exhausted
- [ ] Bot stops buying at `max_position_size_usdt` limit
- [ ] Bot force-sells at `max_purchases_per_epoch` limit
- [ ] Stop-loss triggers at `max_drawdown_pct` threshold
- [ ] WebSocket fills update epoch stats correctly
- [ ] Shutdown signal (SIGTERM) pauses bot gracefully
- [ ] Peer security review passed (auth, telemetry, budget logic)

---

## File Structure

```
Pecunator-AccuMonetas/
├── runtime/
│   ├── bot/
│   │   └── louise.py              ← Main DCA bot runner
│   ├── api/
│   │   ├── app.py                 ← FastAPI creation + router registration
│   │   ├── auth.py                ← Bearer token verification
│   │   └── routers/
│   │       ├── louise.py           ← Louise endpoints (bots, metrics, health)
│   │       ├── stream.py           ← WebSocket telemetry
│   │       └── [others]            ← Gateway, vault, ops, etc.
│   ├── core/
│   │   ├── louise_db.py           ← DB schema + CRUD
│   │   ├── api_governor.py        ← Weight-limit zones
│   │   ├── budget_guard.py        ← Daily spend limit
│   │   ├── exchange_filters.py    ← Binance LOT_SIZE, MIN_NOTIONAL
│   │   └── [others]               ← Event bus, fuse, alerts, etc.
│   └── tests/
│       ├── test_louise_runner_loop.py    ← P1.1: Main loop execution
│       ├── test_louise_endpoints.py      ← P1.2: API endpoints
│       ├── test_louise_recovery.py       ← P1.3: Failure recovery
│       ├── test_louise_fill_handling.py  ← P1.4: WebSocket fills
│       └── [others]                      ← DB, governor, etc.
├── desktop_shell/
│   ├── lib/
│   │   ├── screens/louise_*       ← Louise dashboard, orders, alerts
│   │   ├── models/louise_model.dart ← Louise state model
│   │   └── main.dart              ← App entry
│   └── test/
│       └── [tests]                ← Flutter tests
├── docs/
│   ├── ARCHITECTURE.md            ← This file
│   └── [other guides]
├── .github/workflows/
│   ├── ci-gate.yml                ← Required: pytest, flutter analyze, flutter test
│   └── [other workflows]
├── main.py                        ← FastAPI app startup
└── README.md                       ← Overview + deployment checklist
```

---

## Key Design Decisions

### 1. **Budget Guard is Source of Truth**
Bot checks `BudgetGuard.can_spend()` BEFORE local daily budget. Prevents race conditions if two bots poll simultaneously.

### 2. **No Fake Telemetry**
- `/health` returns real state or "unknown" (not hardcoded "healthy")
- `/weight-governor/status` returns real weight or explicit "unavailable" error
- No fallback values (e.g., `weight = 1050`) that hide truth

### 3. **Preventive Position Controls**
- `max_position_size_usdt`: Hard limit on exposure per epoch (no unbounded accumulation)
- `max_purchases_per_epoch`: Force-sell after N buys (escape explosive drawdown scenarios)
- Both configurable per bot, with sensible defaults (5000 USDT, 20 buys)

### 4. **Endpoint Validation**
- `create_bot` validates config BEFORE DB write + initializes runner to catch config errors early
- `update_bot` validates new values before update
- Returns 400 Bad Request with clear error message, not 500

### 5. **Test Coverage**
- **P1.1:** Runner loop resilience (cycling, shutdown, errors)
- **P1.2:** Endpoint semantics (validation, state transitions)
- **P1.3:** Failure recovery (API limits, budget, gateway, staleness)
- **P1.4:** Fill handling (BUY, SELL, partial, slippage)

---

## Next Steps (P2: Nice-to-Haves)

- [ ] Move hardcoded thresholds to settings (price staleness, cooldown durations)
- [ ] Flutter integration contract tests (API ↔ UI)
- [ ] Remove secret-scan ignores for `runtime/data/`
- [ ] Prometheus metrics for bot-specific telemetry (buy count, fill latency, etc.)
- [ ] Dashboard charts for weight history, P&L over time

---

**Last Updated:** 2026-05-12  
**Status:** P0 fixes + P1 tests complete; hardening in progress
