# Changelog

All notable changes to this project are documented here. Implementation artifacts (source, commits, symbol names) stay **English** per repository convention; this file uses **English** for portability.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Production Hardening Complete - 6 Phases (v3.8.0 RC1)

**Phase 1: Alerting System** — Telegram integration with exponential backoff retry (3 attempts), alert deduplication (300s window), email fallback, and integration to 6 Louise bot critical points.

**Phase 2: Testing** — 12 integration tests covering full Louise DCA lifecycle (buy/sell/epoch completion), 12 load tests validating performance targets (write p95<50ms, read p95<20ms, epoch p95<500ms), 225+ total tests passing.

**Phase 3: Graceful Shutdown & Orphan Recovery**
- Graceful shutdown with SIGTERM/SIGINT handlers (Linux/macOS) and Windows fallback (Ctrl+C)
- 6-step shutdown sequence: stop immortality → cancel pending orders → stop telemetry → stop gateway → stop coordinator → flush DB state
- 30-second timeout enforcement with logging
- Orphan order detection and recovery: scan Binance orders against local DB, adopt with purchase record insertion, cancel open orphans via API

**Phase 4: Vault Security** — PBKDF2-SHA256 key derivation (100,000 iterations) for passphrase-based encryption, Fernet AES-128-CBC for credentials, key rotation endpoint with audit logging to `vault_audit.log`.

**Phase 5: Observability** — Prometheus metrics endpoint exposing 11 metric categories (Louise bots, epochs, orders, API requests, risk controls, gateway, database, alerts), JSON structured logging with correlation ID tracing (optional via `PECUNATOR_LOG_JSON=1`).

**Phase 6: Operations** — Incident Runbook (10 scenarios: fuse, orphans, WS disconnect, stop-loss, DB corruption, budget, weight, alerts, anomalies, emergency shutdown), Operator Manual (daily checklist, environment vars, monitoring, backup/restore, vault security, troubleshooting), Backup Script with SQLite integrity check and 30-day rotation.

**Security Audit Resolution** — All 8 findings resolved: API auth gaps (verify_token on all ops), exception handling specificity (targeted exception types), CI gate coverage (test_e2e_pipeline.py included), graceful shutdown (signal handlers + sequence), orphan recovery (endpoints), vault rotation (PBKDF2+Fernet), monitoring (Prometheus+JSON), integration tests (50+ tests).

### Production Hardening & Security (v3.7.5+)

- **Explicit Deployment:** Removed dangerous auto-update loops (`git pull` at startup) to guarantee predictable and tested deployments.
- **Security Audit:** Added a `CRITICAL` startup log if the engine runs with `PECUNATOR_API_AUTH_DISABLED=1` in production.
- **Environment Schema:** Introduced `.env.example` mapping all environment toggles (`PECUNATOR_LOG_LEVEL`, `PECUNATOR_API_PORT`, `PECUNATOR_ALERT_TELEGRAM_TOKEN`, etc.) for seamless dev-to-prod transition.
- **Alert Dispatcher Integration:** `AlertDispatcher` now pushes events asynchronously via Telegram Webhook (if token and chat ID are configured).
- **UI Architecture Cleanup:** Centralized base engine URLs and app version strings into `app_config.dart`.
- **Bot Orchestration Visibility:** Staged and running instances (Dorothy & Elphaba) are now sorted newest-to-oldest in the Hub UI.
- **State Reliability:** Re-anchored the emergency `PANIC.lock` sentinel to the strictly managed `data_dir` configuration rather than dynamic relative paths.
- **Clean Repository:** Purged all execution-time debris (e.g. `backend.log*`, `scratch/`, `vmo_captures/`, `analyze_out.txt`) from Git tracking. Removed redundant `launch.py` shims.
- **Test Integrity:** Added `autouse` module-reset fixtures in `conftest.py` ensuring pure isolation between tests for Singleton architectures.

### Runtime immortality / auto-recovery

- Added persistent `dorothy_instances` state in `runtime/data/dorothy_hub.sqlite` including `desired_running`.
- Added background immortal supervisor for hub bots: if a bot is marked desired-running and stops (exceptions/disconnects/process restart), the service retries start automatically when credentials/network are available.
- Improved Dorothy loop resilience: transient failures now trigger client re-creation plus retry backoff (`bot:retry_in ...`) instead of waiting a full long cycle.
- Added scripts for operational resilience:
  - `scripts/engine/run_engine_immortal.ps1` (engine watchdog / auto-restart)
  - `scripts/engine/InstallImmortalStartup.ps1` (Windows startup shortcut)

### Account equity monitor

- Integrated rolling spot equity conversion to base asset in runtime gateway state (`current`, `avg`, `high_avg`, missing-price assets).
- Added configurable cadence and parameters:
  - `PECUNATOR_EQUITY_BASE_ASSET` (default `USDT`)
  - `PECUNATOR_EQUITY_AVG_WINDOW` (default `6`)
  - `PECUNATOR_EQUITY_POLL_STRIDE` (default `5`)
- Exposed equity in `GET /api/v1/gateway/snapshot` and included on-demand equity in `GET /api/v1/account/wallets`.
- Updated Spot UI to show a live equity card in the account details window.

### Operational protocols: close protocol + red button

- Added API operations with mandatory Dorothy pre-stop to avoid disposal/conversion loops:
  - `POST /api/v1/ops/protocol/close`
  - `POST /api/v1/ops/red_button`
  - `GET /api/v1/ops/protocol/status`
- Added persistent traceability store `runtime/core/ops_audit_log.py` (`ops_audit.sqlite`) with latest status/summary/error snippets.
- Added dashboard row with explanatory tooltips, precautions, operation buttons, monitor values, and summary viewer for both modules.

### Vault simplification

- **Storage:** `credentials.enc` remains encrypted on disk using **Fernet + `vault_local.key`** (machine-local file under `runtime/data/`).
- **UX/API:** credential flow is reduced to add/delete with automatic activation of the latest saved key.

Earlier repository history was not tracked in this file before this changelog existed.
