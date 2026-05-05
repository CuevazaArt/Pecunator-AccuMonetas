# Changelog—Pecunator

> History of architectural, API and operational changes.  
> Changes that touch `runtime/`, `desktop_shell/`, or `.github/workflows/` should be logged here.

---

## Rules of this Changelog

- Every change that touches `runtime/`, `desktop_shell/`, or `.github/workflows/` adds an entry
- Entries in reverse chronological order (most recent first)
- Format: what changed, why it matters, migration notes if applicable
- No local machine secrets, credentials or routes are recorded

---

## [Unreleased]

### Runtime immortality/auto-recovery

- **Added:** Desired state persistence (`desired_running`) in `runtime/data/dorothy_hub.sqlite`
- **Added:** Immortal Instance Monitor: If a bot was marked to run and stops, the service automatically retries the start
- **Improved:** Dorothy loop resiliency — transient failures trigger client recreation + backoff (`bot:retry_in ...`)
- **New scripts:**
  - `scripts/engine/run_engine_immortal.ps1` (watchdog/engine auto-restart)
  - `scripts/engine/InstallImmortalStartup.ps1` (autostart shortcut on Windows)

### Account equity monitor

- **Added:** Rolling conversion of equity spot to base asset in the gateway state (`current`, `avg`, `high_avg`)
- **New environment variables:**
  - `PECUNATOR_EQUITY_BASE_ASSET` (default `USDT`)
  - `PECUNATOR_EQUITY_AVG_WINDOW` (default `6`)
  - `PECUNATOR_EQUITY_POLL_STRIDE` (default `5`)
- **Exposed** in `GET /api/v1/gateway/snapshot` and in `GET /api/v1/account/wallets`
- **UI:** Live equity card in Spot account details window

### Operational protocols: close protocol + red button

- **Added:** Operations with mandatory stopping of Dorothy to avoid loops:
  - `POST /api/v1/ops/protocol/close`
  - `POST /api/v1/ops/red_button`
  - `GET /api/v1/ops/protocol/status`
- **Added:** Traceability store `runtime/core/ops_audit_log.py` (`ops_audit.sqlite`)
- **UI:** Dashboard row with explanatory tooltips, operation buttons, monitor values and summary viewer

### Vault simplification

- **Storage:** `credentials.enc` encrypted with Fernet + `vault_local.key`
- **UX/API:** Flow reduced to add/delete with automatic activation of the last saved key

---

## 2026-05-05

### Runtime state durability and tools

- **Added:** WAL-backed persistence for runtime state storage
- **Added:** Paper P&L reporting tool for operator analysis
- **Changed:** Router extraction from monolith `runtime/api/app.py` to dedicated modules (including vault and ops)
- **Impact:** Better crash resilience, cleaner API layering, and easier maintenance

### Wiki and documentation operations

- **Added:** New wiki page `L0-Operator-Philosophy.md` with accepted operational guardrails
- **Changed:** Wiki translation process and content moved to full English operational baseline
- **Impact:** Clearer doctrine for operators and more consistent documentation language

---

## 2026-04-29

### Documentation and modular structure of examples

- **Added:** `examples/` as a single point for non-functional history references
- **Added:** Document `docs/main-runtime-boundary.md` with explicit responsibilities
- **Changed:** Scripts reorganized by domain (`scripts/ui/`, `scripts/engine/`, `scripts/data/`)
- **Impact:** Reduced maintenance friction by separating responsibilities by folder

### Security CI

- **Added:** Workflow `.github/workflows/secret-scan.yml` (Gitleaks) to detect secrets in pushes/PRs to main branches
- **Changed:** Hardened boot scripts with fallback to system `python` when `.venv` does not exist
- **Impact:** Reduced risk of credential leaks in the repository

### Modules per domain

- **Added:** Explicit modular structure:
  - `runtime/modules/bots/` (Dorothy, Masha, Thusnelda)
  - `runtime/modules/tools/` (ops protocols, sandbox rest, rest-weight monitor)
- **Added:** Modular indexes in root (`bots/`, `tools/`) with `MODULE.md` per bot/tool
- **Changed:** Bots and tests API services migrated to imports `runtime.modules.bots.*`
- **Impact:** Clearer navigation for adding new bots/tools without mixing layers

### REST weight audit

- **Added:** Detailed REST weight audit per action/source:
  - `GET /api/v1/usage/rest-weight/events`
  - `GET /api/v1/usage/rest-weight/report`
- **Added:** Document `docs/rest-weight-audit.md`
- **Changed:** Removed redundant `ping` calls in the polling loop
- **Changed:** Tooltips in Masha and Thusnelda settings
- **Impact:** More traceability to identify which endpoint/action raises the weight per minute

### Guide pages per bot in UI Flutter

- **Added:** Dedicated guide pages per bot (`Dorothy`, `Masha`, `Thusnelda`) in the UI
- **Changed:** Instruction buttons open full screen (what it does, basic operation, risks, quick start)
- **Impact:** Faster onboarding to operate each bot from your Hub

### Risk and metrics improvements per bot

- **Added:** `exampleJV_enhanced/` in `examples/` for traceability
- **Added:** User manuals per bot in `docs/bots/`
- **Added:** SQLite tables per hub: `*_runtime_state`, `*_equity_snapshots`, `*_metrics_log`
- **Changed:** Risk parameters/metrics for all 3 bots:
  - `max_drawdown_pct`
  - `stop_loss_pct`
  - `metrics_interval_cycles`
- **Fixed:** Hubs now restore persisted risk state on restart (peak equity, drawdown, cycles)
- **Impact:** Greater protection against bearish markets without breaking original architecture

### Thusnelda 1.0

- **Added:** Thusnelda bot with runner `runtime/bot/thusnelda.py` (multi-symbol, average-buy, equity target)
- **Added:** Hub service `runtime/api/thusnelda_service.py` with SQLite persistence
- **Added:** API surface `/api/v1/thusnelda/bots/*` and dedicated Flutter screen
- **Changed:** REST weight bars with colors (green/orange/red) in dashboard
- **Impact:** Three bots (Dorothy, Masha, Thusnelda) operable from the same control surface

### REST sandbox

- **Added:** Sandbox REST API (`/api/v1/sandbox/rest/catalog`, `/api/v1/sandbox/rest/query`)
- **Added:** Automatic timestamp + retry synchronization for signed calls
- **Added:** Architectural doctrine section on profit-first objective
- **Changed:** Sandbox UI simplified to guided query model
- **Fixed:** Intermittent crashes of `/api/v1/account/wallets` by timestamp ahead-of-server
- **Fixed:** Sandbox was trying to call Binance paths directly from Flutter; now it is routed by engine
- **Impact:** Operators can validate Binance structures faster with fewer steps

---

*To add new entries: follow the format and add `[Unreleased]` to the beginning of the section or create a new section with a date.*