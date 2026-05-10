# Changelog

All notable changes to this project are documented here. Implementation artifacts (source, commits, symbol names) stay **English** per repository convention; this file uses **English** for portability.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

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
