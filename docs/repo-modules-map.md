# Repo Modules Map

Updated: 2026-05-06 (v0.3.0-infra)

## Root module layout

- `bots/`
  - `dorothy/`
  - `masha/`
  - `thusnelda/`
- `tools/`
  - `ops-protocols/`
  - `sandbox-rest/`
  - `rest-weight-monitor/`
- `examples/`
  - `dorothy7.0-reference/`
  - `enhanced/`

## Runtime domain layout

- `runtime/main.py` – engine entrypoint (used by root `main.py`)
- `runtime/modules/bots/` – bot strategy modules
- `runtime/modules/tools/` – operational tool modules
- `runtime/modules/vision/` – VMO (Visual Market Observer)
  - `observer.py` – capture-analyze-store lifecycle
  - `chart_capture.py` – Chart-Img API / Playwright capture
  - `chart_analyzer.py` – Gemini/OpenAI vision classification
  - `regime_cache.py` – SQLite regime snapshot storage
  - `config.py` – VMO configuration (symbols, intervals, indicators)
- `runtime/api/` – API façade and service orchestration
- `runtime/core/` – shared primitives/state/settings/storage
  - `api_governor.py` – **unified multi-service rate limiter** (Binance/ChartImg/Gemini/OpenAI)
  - `api_fuse.py` – thermal circuit breaker for Binance REST
  - `weight_governor.py` – API weight budget per bot
  - `exception_zoo.py` – **forensic exception registry** (dedup, hit counting)
  - `telemetry_vault.py` – **unified data store** (klines, captures, bot decisions)
  - `account_monitor.py` – **periodic balance snapshots, rebalance signals**
  - `bot_coordinator.py` – phase-shifted bot launch and execution
  - `regime_detector.py` – multi-timeframe consensus
  - `market_cache.py` – in-memory shared data cache (single-flight)
  - `rest_usage_log.py` – REST weight samples log
  - `binance_api_log.py` – forensic log of ALL Binance interactions
  - `config_manager.py` – encrypted credential vault (Fernet)
  - `equity.py` – spot equity calculator with rolling window
  - `state_store.py` / `state_wal.py` – bot state persistence (WAL)
  - `db_util.py` – centralized SQLite helper (WAL, busy_timeout)
- `runtime/connectors/` – Binance and market connectors

## Script layout

- `scripts/ui/` – Flutter run/build helpers, launcher, desktop shortcut setup
- `scripts/engine/` – engine start/stop/watchdog and startup-autostart helper
- `scripts/data/` – data snapshots and offline collectors

## Compatibility note

- `runtime/bot/*` remains available as a compatibility bridge while imports migrate to `runtime/modules/bots/*`.
- New code should import bot runners/configs from `runtime.modules.bots`.

