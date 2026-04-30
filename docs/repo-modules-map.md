# Repo Modules Map

Updated: 2026-04-29

## Root module layout

- `bots/`
  - `dorothy/`
  - `masha/`
  - `thusnelda/`
- `tools/`
  - `ops-protocols/`
  - `sandbox-rest/`
  - `rest-weight-monitor/`

## Runtime domain layout

- `runtime/main.py` – engine entrypoint (used by root `main.py`)
- `runtime/modules/bots/` – bot strategy modules
- `runtime/modules/tools/` – operational tool modules
- `runtime/api/` – API façade and service orchestration
- `runtime/core/` – shared primitives/state/settings/storage
- `runtime/connectors/` – Binance and market connectors

## Compatibility note

- `runtime/bot/*` remains available as a compatibility bridge while imports migrate to `runtime/modules/bots/*`.
- New code should import bot runners/configs from `runtime.modules.bots`.

