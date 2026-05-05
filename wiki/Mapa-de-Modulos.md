# Module Map — Pecunator

> Reference of the folder structure, ownership and entrypoints of each module.  
> Last update: 2026-05-05

---

## Repository root structure

```
Pecunator/
│
├── main.py                    # Thin bootstrap → runtime/main.py
│
├── runtime/                   # Python engine package (primary)
│   ├── main.py                # Engine startup and API server lifecycle
│   ├── api/                   # FastAPI façade + services + routers
│   ├── connectors/            # Binance gateway and market connectors
│   ├── core/                  # Shared primitives (state/settings/audit/security)
│   ├── modules/               # Domain modules
│   │   ├── bots/              # Bot strategies
│   │   └── tools/             # Operational tools
│   ├── bot/                   # Compatibility bridge (legacy imports)
│   └── data/                  # Vault, SQLite and runtime stores
│
├── bots/                      # Índice raíz de módulos de bots
│   ├── dorothy/MODULE.md
│   ├── masha/MODULE.md
│   └── thusnelda/MODULE.md
│
├── tools/                     # Índice raíz de herramientas operativas
│   ├── ops-protocols/         # Protocolos y runbooks
│   ├── sandbox-rest/          # Sandbox de queries Binance
│   └── rest-weight-monitor/   # Monitor de peso REST
│
├── desktop_shell/             # UI Flutter Desktop
│   └── lib/
│       ├── main.dart
│       ├── config/
│       ├── providers/
│       ├── services/
│       ├── screens/
│       ├── widgets/
│       └── utils/
│
├── scripts/                   # Operation scripts
│   ├── ui/                    # Flutter run/build and desktop shortcuts
│   ├── engine/                # Engine start/stop/watchdog/autostart
│   └── data/                  # Snapshots and offline collectors
│
├── docs/                      # Technical documentation
├── examples/                  # Historical references (non-runtime)
└── wiki/                      # Wiki pages
```

---

## Python engine modules (`runtime/`)

### `runtime/api/`

API façade and orchestration of services by domain.

| Archive | Responsibility |
|---------|----------------|
| `app.py` | FastAPI app creation + router composition |
| `deps.py` | Shared dependency access to context/services |
| `schemas.py` | Request/response models |
| `bot_service.py` | Dorothy hub service |
| `masha_service.py` | Masha hub service |
| `thusnelda_service.py` | Thusnelda hub service |
| `earn_service.py` | Earn sync/history persistence service |
| `routers/*.py` | Domain routes (`vault`, `ops`, `masha`, `thusnelda`, `system`, `sandbox`, `gateway`, `dorothy`) |

### `runtime/connectors/`

| Archive | Responsibility |
|---------|----------------|
| `binance_gateway.py` | Account polling, market streams, REST weight tracking, equity refresh |

### `runtime/core/`

Shared primitives without dependency on higher layers.

| Module | Responsibility |
|--------|----------------|
| `settings.py` | Environment and configuration variables |
| `vault.py` | Fernet Credential Encryption/Decryption |
| `state_store.py` | Gateway state persistence (WAL mode) |
| `ops_audit_log.py` | Audit of operational protocols (SQLite) |
| `config_manager.py` | Persistent bot configuration |
| `security_util.py` | Log sanitization |

### `runtime/modules/bots/`

Bot strategy modules (canonical imports from this route).

| Module | Bot | Description |
|--------|-----|-------------|
| `dorothy.py` | Dorothy | Spot ladder — SELL LIMIT + dip buy |
| `masha.py` | Masha | Multi-timeframe DCA with technical signal (`1w`+`1h`) |
| `thusnelda.py` | Thusnelda | Symbol basket with global equity goal |

### `runtime/modules/tools/`

| Module | Tool | Description |
|--------|-------------|-------------|
| `ops/` | Ops Protocols | Implementation of close protocol and red button |

---

## Bot modules in root (`bots/`)

Document indexes with entrypoints, API surface and SQLite stores.

### `bots/dorothy/`

- **Runtime runner:** `runtime/modules/bots/dorothy.py`
- **Hub service:** `runtime/api/bot_service.py`
- **API surface:** `/api/v1/hub/bots/*`
- **UI hub:** `desktop_shell/lib/main.dart` (Dorothy Hub)
- **SQLite:** `runtime/data/dorothy_hub.sqlite`
  - `dorothy_instances`, `dorothy_logs`, `dorothy_runtime_state`, `dorothy_equity_snapshots`, `dorothy_metrics_log`

### `bots/masha/`

- **Runtime runner:** `runtime/modules/bots/masha.py`
- **Hub service:** `runtime/api/masha_service.py`
- **API surface:** `/api/v1/masha/bots/*`
- **SQLite:** `runtime/data/masha_hub.sqlite`
  - `masha_runtime_state`, `masha_equity_snapshots`, `masha_metrics_log`

### `bots/thusnelda/`

- **Runtime runner:** `runtime/modules/bots/thusnelda.py`
- **Hub service:** `runtime/api/thusnelda_service.py`
- **API surface:** `/api/v1/thusnelda/bots/*`
- **SQLite:** `runtime/data/thusnelda_hub.sqlite`
  - `thusnelda_runtime_state`, `thusnelda_equity_snapshots`, `thusnelda_metrics_log`

---

## Tool modules in root (`tools/`)

### `tools/ops-protocols/`

- **Runtime:** `runtime/modules/tools/ops/`
- **API handlers:** `runtime/api/routers/ops.py`
  - `POST /api/v1/ops/protocol/close`
  - `POST /api/v1/ops/red_button`
  - `GET /api/v1/ops/protocol/status`
  - `POST /api/v1/ops/orders/cleanup/*`
- **Audit:** `runtime/data/ops_audit.sqlite`
- **Runbooks (Tasks):** `tools/ops-protocols/tasks/`

### `tools/sandbox-rest/`

Queries guided to Binance REST from the UI.

- **API:** `/api/v1/sandbox/rest/catalog`, `/api/v1/sandbox/rest/query`
- **Curated storage API:** `/api/v1/sandbox/curated/save`, `/api/v1/sandbox/curated/list`
- Supports: `get_exchange_info`, `get_account`, `get_open_orders`, `get_my_trades`

### `tools/rest-weight-monitor/`

REST weight monitor with history and audit per endpoint.

- **API:** `/api/v1/usage/rest-weight/samples`, `/api/v1/usage/rest-weight/events`, `/api/v1/usage/rest-weight/report`
- **System status API:** `/api/v1/weight-governor/status`, `/api/v1/market-cache/status`, `/api/v1/bot-coordinator/status`
- Source: Binance header `X-MBX-USED-WEIGHT-1M`

---

## Scripts (`scripts/`)

| Folder | Key scripts |
|---------|--------------|
| `scripts/ui/` | `init_flutter_desktop.ps1`, `run_dashboard.ps1`, `run_dashboard.cmd`, `PecunatorDesktopLauncher.ps1`, `InstallDesktopShortcut.ps1` |
| `scripts/engine/` | `run_engine.ps1`, `run_engine_immortal.ps1`, `stop_engine_port.ps1`, `InstallImmortalStartup.ps1` |
| `scripts/data/` | `fetch_binance_exchange_info_limits.py` |

---

## Compatibility note

- `runtime/bot/*` remains available as a compatibility bridge while imports migrate to `runtime/modules/bots/*`
- New code must import runners/configs from `runtime.modules.bots`