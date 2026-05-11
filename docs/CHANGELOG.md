# Documentation Changelog

This changelog is the disciplined, operator-facing history for architecture, UI behavior, API surface, and operational safety rules.

## Rules

- Every change that touches `runtime/`, `desktop_shell/`, or `.github/workflows/` must add one entry here.
- Entries are append-only and ordered newest first.
- Keep each entry short and operational: what changed, why it matters, and migration notes if needed.
- Do not log secrets, credentials, or local machine paths.

## Entry template

```md
## YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Operational impact
- ...
```

## 2026-05-09 (v3.1.1)

### Added
- **M2: Atomic Symmetric Deploy**: Endpoint `/api/v1/hub/deploy-symmetric` for simultaneous creation/start of Dorothy+Elphaba pairs with automatic rollback on partial failure.
- **M3: Alert Dispatcher**: Centralized alerting system in `runtime/core/alert_dispatcher.py`, writing to `alerts.log`.
- **M4: Process Watchdog**: External `watchdog.py` monitor for auto-restart on engine crashes.
- **M1.1: Log Rotation & Silence**: `RotatingFileHandler` (15MB cap) + suppression of `uvicorn.access` logs to reduce polling noise.

### Changed
- **M5: Legacy Test Quarantine**: `tests/legacy/` now uses `collect_ignore_glob` to skip broken imports without polluting the suite.
- **Prospector Visibility**: Added batch progress and auto-staging decision logging at `INFO` level.

### Fixed
- **HubBotOut Validation**: Fixed `stop_loss_pct` validation error for Elphaba bots (made optional).
- **Silent Guard Failures**: Replaced silent `except: pass` in `_base_runner.py` with explicit logging.

### Operational impact
- Reduced risk of asymmetric bot operation (one side live, one dead).
- Guaranteed disk safety via log rotation.
- Improved reliability via external watchdog.
- Cleaner logs for real-time monitoring.

## 2026-04-29

### Added
- `examples/` folder as the single entry point for non-functional historical references (merging the purpose of `exampleJV` + `exampleJV_enhanced`).
- Architecture document `docs/main-runtime-boundary.md` with explicit responsibilities of `main` and `runtime` for scaling.

### Changed
- Scripts reorganized by domain:
  - `scripts/ui/` (dashboard, launcher, desktop shortcuts)
  - `scripts/engine/` (engine start/stop/supervisor)
  - `scripts/data/` (operational snapshots such as `exchangeInfo`)
- Documentation updated to new script paths and to the use of `examples/`.

### Operational impact
- Less friction for maintenance by separating operational responsibilities per folder.
- Lower risk of mixing production code with reference examples.

## 2026-04-29

### Added
- New security workflow `.github/workflows/secret-scan.yml` (Gitleaks) to detect secrets in pushes/PRs to main branches.

### Changed
- Startup scripts `scripts/engine/run_engine.ps1` and `scripts/engine/run_engine_immortal.ps1` hardened with fallback to system `python` when `.venv` does not exist.

### Operational impact
- Lower risk of credential leaks in the repository.
- Less operational fragility when starting the engine on machines without an active virtual environment.

## 2026-04-29

### Added
- Explicit modular structure by domain:
  - `runtime/modules/bots/`
  - `runtime/modules/tools/`
- Modular indexes in root for expansion and readability:
  - `bots/` (Dorothy, Masha, Thusnelda)
  - `tools/` (ops protocols, sandbox rest, rest-weight monitor)
- `MODULE.md` files per bot/tool with entrypoints, API surface, and associated SQLite.

### Changed
- Bot API services and main tests migrated to `runtime.modules.bots.*` imports.
- Python workflow (`mypy`) updated to validate the bot modular path.
- Architecture documentation (`README.md`, `docs/architecture-next.md`) aligned to the new modular schema.

### Fixed
- Removed legacy refactor documentation that no longer represents the current state (`REFACTOR_*`).

### Operational impact
- Clearer navigation for adding new bots/tools without mixing layers.
- Less friction for onboarding and runtime maintenance in the medium term.

## 2026-04-29

### Added
- Detailed REST weight audit per action/source with new endpoints:
  - `GET /api/v1/usage/rest-weight/events`
  - `GET /api/v1/usage/rest-weight/report`
- Operational document `docs/rest-weight-audit.md` with quantization model and list of consumption sources.
- REST weight UI monitor enriched with summary tabs, audited events, and historical samples.

### Changed
- Removed redundant `ping` calls in the gateway polling loop to reduce unnecessary weight consumption.
- Added extended tooltips on individual Masha and Thusnelda setup (create + edit per instance).
- Expanded the in-app manual per bot (`BotGuidePage`) with parameter guide and troubleshooting.
- Operational tools module (close/red/cleanups) reorganized into a compact list on a single card.

### Operational impact
- More traceability to identify which endpoint/action raises weight per minute.
- Less baseline consumption noise in the monitor by avoiding redundant periodic pings.
- Less operational ambiguity when adjusting parameters per bot and instrument.

## 2026-04-29

### Added
- Dedicated guide pages per bot in the Flutter UI (`Dorothy`, `Masha`, `Thusnelda`) to simplify operational onboarding and avoid lengthy instructions in modals.

### Changed
- Guide buttons in each Hub now open a full screen with: what the bot does, base operation, risks, and quick-start flow.
- Engine startup scripts (`run_engine.ps1`, `run_engine_immortal.ps1`) simplified to direct launch of `main.py` without dependency on external examples.
- Documentation (`README.md`, `docs/architecture-next.md`, `docs/binance-api-and-compliance.md`) updated to reflect credential flow via vault/environment.

### Fixed
- Cleaned up old operational references to `exampleJV` in runtime/UI to avoid maintenance confusion.

### Operational impact
- Faster onboarding to operate each bot from its Hub.
- Less coupling between production runtime and example folders.

## 2026-04-29

### Added
- Imported `exampleJV_enhanced/` from the collaboration branch to preserve traceability of improved examples (`Dorothy7.1`, `Masha2.1`, `Thusnelda1.1`) alongside `exampleJV/`.
- Per-bot user manuals in `docs/bots/` (one each for Dorothy, Masha, and Thusnelda) with operational variables and SQLite queries.
- New SQLite tables per hub for operational persistence:
  - `*_runtime_state`
  - `*_equity_snapshots`
  - `*_metrics_log`

### Changed
- Incremental integration of `exampleJV_enhanced` improvements into the runtime runners:
  - `runtime/bot/dorothy.py`
  - `runtime/bot/masha.py`
  - `runtime/bot/thusnelda.py`
- Added configurable risk/metrics parameters per bot:
  - `max_drawdown_pct`
  - `stop_loss_pct`
  - `metrics_interval_cycles`
- Updated the API schema/surface to accept those parameters in create/update for all 3 hubs.
- Flutter UI updated to expose those parameters in Dorothy/Masha/Thusnelda and apply changes via `Save and apply`.
- Added in-interface guides for Masha and Thusnelda (Dorothy already existing) to improve usage consistency.

### Fixed
- Hubs now restore persisted risk state on restart (peak equity / max drawdown / cycle counter), avoiding "blind" restart of protection.

### Operational impact
- Greater protection against bear markets (drawdown guard + stop-loss) without breaking the original architecture of each bot.
- Performance metrics and equity snapshots are persisted in SQLite per instance for auditing and tuning.

## 2026-04-29

### Added
- New `Thusnelda1.0` bot integration with dedicated runtime runner (`runtime/bot/thusnelda.py`) implementing multi-symbol average-buy trigger, equity target tracking, and optional liquidation-to-USDT behavior.
- New multi-instance hub service for Thusnelda (`runtime/api/thusnelda_service.py`) with SQLite persistence/logging and immortality recovery flow, equivalent to Dorothy/Masha management style.
- New API surface for Thusnelda hub lifecycle and logs (`/api/v1/thusnelda/bots`, `/start`, `/stop`, `/run_once`, `/logs`) plus Flutter client methods and a dedicated `Thusnelda1.0 Hub` page.

### Changed
- REST weight monitor bars now use color thresholds (green/orange/red) in dashboard and monitor dialog to quickly identify load risk against Binance 1m weight limits.
- Ops status payload now includes `thusnelda_hub_stats` for centralized hub visibility.

### Fixed
- Verified current engine/UI terminal logs for active processes: no new `Traceback`, `500`, `404`, or Binance API errors detected during this update window.

### Operational impact
- Operators can compare and run three bots (Dorothy, Masha, Thusnelda) from the same control surface with consistent controls.
- Weight saturation risk is easier to detect at a glance due to explicit color coding in monitor bars.

## 2026-04-29

### Added
- Sandbox REST query API (`/api/v1/sandbox/rest/catalog`, `/api/v1/sandbox/rest/query`) for guided Binance calls such as `get_exchange_info`, `get_account`, `get_open_orders`, `get_my_trades`.
- Backend timestamp auto-sync + retry for signed sandbox and wallet calls to mitigate Binance `-1021` drift errors.
- Architecture doctrine section documenting profit-first objective with controlled-loss handling.

### Changed
- Sandbox UI simplified to a guided REST-query model instead of free-form method/body editing.
- Credential manager UX simplified around add/delete with auto-activation flow.
- CI expectation clarified: checks/tests are enforced in GitHub Actions.

### Fixed
- `/api/v1/account/wallets` intermittent failures caused by timestamp ahead-of-server.
- Sandbox attempts to call raw Binance paths directly from Flutter (`/api/v3/exchangeInfo`), now routed through engine API.

### Operational impact
- Operators can validate Binance structures faster with fewer UI steps.
- Less manual recovery from timestamp drift during account/sandbox calls.
- Changelog discipline is now explicit for future maintenance.
