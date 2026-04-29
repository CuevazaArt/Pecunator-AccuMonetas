# Changelog

All notable changes to this project are documented here. Implementation artifacts (source, commits, symbol names) stay **English** per repository convention; this file uses **English** for portability.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Runtime immortality / auto-recovery

- Added persistent `dorothy_instances` state in `runtime/data/dorothy_hub.sqlite` including `desired_running`.
- Added background immortal supervisor for hub bots: if a bot is marked desired-running and stops (exceptions/disconnects/process restart), the service retries start automatically when credentials/network are available.
- Improved Dorothy loop resilience: transient failures now trigger client re-creation plus retry backoff (`bot:retry_in ...`) instead of waiting a full long cycle.
- Added scripts for operational resilience:
  - `scripts/run_engine_immortal.ps1` (engine watchdog / auto-restart)
  - `scripts/InstallImmortalStartup.ps1` (Windows startup shortcut)

### Account equity monitor (from `exampleJV/monitoreoEquity` concepts)

- Integrated rolling spot equity conversion to base asset in runtime gateway state (`current`, `avg`, `high_avg`, missing-price assets).
- Added configurable cadence and parameters:
  - `PECUNATOR_EQUITY_BASE_ASSET` (default `USDT`)
  - `PECUNATOR_EQUITY_AVG_WINDOW` (default `6`)
  - `PECUNATOR_EQUITY_POLL_STRIDE` (default `5`)
- Exposed equity in `GET /api/v1/gateway/snapshot` and included on-demand equity in `GET /api/v1/account/wallets`.
- Updated Spot UI to show a live equity card in the account details window.

### Vault — removed user master password

- **Removed:** Any API field or UX flow requiring a **user-supplied master password** (`VaultSessionBody`, `PECUNATOR_VAULT_PASSWORD`, `PECUNATOR_REMEMBER_MASTER`, `runtime/core/master_remember.py`).
- **Storage:** `credentials.enc` is still encrypted on disk using **Fernet + `vault_local.key`** (machine-local file under `runtime/data/`). No passphrase is prompted.
- **Upgrade:** Vault files produced by older builds that used password-derived keys cannot be decrypted automatically. Back up if needed, remove legacy files (`credentials.enc`, `salt.bin`, `master_remember.fenc`, `rem_device.key`), restart the engine, and add API keys again via the UI or env.

Earlier repository history was not tracked in this file before this changelog existed.
