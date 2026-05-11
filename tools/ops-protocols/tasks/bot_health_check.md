# Task: Bot Infrastructure Health Check

## Objective
Verify the structural and functional integrity of the Pecunator runtime,
including the 3 bots (Dorothy, Masha, Thusnelda), the coordination systems
(BotCoordinator, WeightGovernor), and the API layer.

## Project Context
```
runtime/
├── core/
│   ├── bot_coordinator.py    # Central bot orchestrator
│   ├── weight_governor.py    # API request weight control
│   ├── api_fuse.py           # Circuit breaker for API calls
│   ├── market_cache.py       # Market data cache
│   ├── rest_usage_log.py     # REST API usage logging
│   ├── config_manager.py     # Configuration management
│   ├── settings.py           # Central settings
│   ├── event_bus.py          # Inter-module event bus
│   └── state_store.py        # State persistence
├── api/
│   ├── app.py                # Main FastAPI app (~100KB, monolith)
│   ├── routers/              # Decoupled routers
│   │   ├── system.py
│   │   ├── masha.py
│   │   └── thusnelda.py
│   ├── schemas.py            # Pydantic schemas
│   └── deps.py               # Dependency injection
├── connectors/
│   └── binance_gateway.py    # Binance API gateway
├── modules/
│   ├── bots/                 # Per-bot logic
│   │   ├── dorothy.py
│   │   ├── masha.py
│   │   └── thusnelda.py
│   └── tools/                # Auxiliary tools
│       ├── ops/
│       ├── rest_weight/
│       └── sandbox/
└── tests/                    # Test suite
```

## Execution Steps

### Step 1 — Syntax Validation
Verify that all Python files in the runtime parse without errors:
```bash
python -m py_compile runtime/core/bot_coordinator.py
python -m py_compile runtime/core/weight_governor.py
python -m py_compile runtime/core/api_fuse.py
python -m py_compile runtime/connectors/binance_gateway.py
python -m py_compile runtime/api/app.py
```
Report any SyntaxError immediately.

### Step 2 — Import Validation
Verify that cross-module imports resolve correctly:
```bash
python -c "from runtime.core.bot_coordinator import BotCoordinator"
python -c "from runtime.core.weight_governor import WeightGovernor"
python -c "from runtime.connectors.binance_gateway import BinanceGateway"
```

### Step 3 — Test Suite
Run the existing tests:
```bash
python -m pytest runtime/tests/ -v --tb=short
```
Capture: total tests, passed, failed, errors, warnings.

### Step 4 — Circuit Breaker Inspection
Review `runtime/core/api_fuse.py`:
- Are there circuit breakers in OPEN state (triggered by failure)?
- How many consecutive failures are recorded?
- When was the last reset?

### Step 5 — Rate Limit Inspection
Review `runtime/core/rest_usage_log.py` and `weight_governor.py`:
- Current accumulated weight vs allowed limit?
- Rate limit usage percentage?
- Any time window close to the limit?

### Step 6 — Router Integrity
Verify that FastAPI routers are correctly registered:
- `routers/system.py` → system routes
- `routers/masha.py` → Masha bot routes
- `routers/thusnelda.py` → Thusnelda bot routes

### Step 7 — Generate Status Table

```
| Componente            | Estado | Detalle                        |
|-----------------------|--------|--------------------------------|
| bot_coordinator.py    | ✅/⚠️/🔴 | [description]               |
| weight_governor.py    | ✅/⚠️/🔴 | [description]               |
| api_fuse.py           | ✅/⚠️/🔴 | [circuit breaker status]    |
| binance_gateway.py    | ✅/⚠️/🔴 | [description]               |
| FastAPI app + routers | ✅/⚠️/🔴 | [routes loaded]             |
| Test suite            | ✅/⚠️/🔴 | [X/Y passed]                |
| Rate limits           | ✅/⚠️/🔴 | [X% used]                   |
```

## Status Criteria
- ✅ **OK**: Component functional, no warnings
- ⚠️ **WARN**: Functional but with warnings or detected degradation
- 🔴 **FAIL**: Compilation error, failed test, or open circuit breaker

## Success Criteria
- [ ] All core files compile without SyntaxError
- [ ] Cross-module imports resolve correctly
- [ ] Test suite executed (report pass rate)
- [ ] Circuit breaker status documented
- [ ] Complete status table generated
