# Module Map — Pecunator

> Reference of the folder structure, ownership and entrypoints of each module.  
> Last update: 2026-04-29

---

## Repository root structure

```
PecunatorCore/
│
├── main.py                    # Bootstrap delgado → runtime/main.py
│
├── runtime/                   # Motor Python (paquete principal)
│   ├── main.py                # Startup del engine y servidor API
│   ├── api/                   # Façade FastAPI + servicios
│   ├── connectors/            # Gateway Binance y conectores de mercado
│   ├── core/                  # Primitivas compartidas
│   ├── modules/               # Módulos de dominio
│   │   ├── bots/              # Estrategias de bots
│   │   └── tools/             # Herramientas operativas
│   ├── bot/                   # Puente de compatibilidad (legacy)
│   └── data/                  # Vault, SQLite y datos de runtime
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
├── scripts/                   # Scripts de operación
│   ├── ui/                    # Arranque/build de Flutter, shortcuts
│   ├── engine/                # Arranque/parada/watchdog del motor
│   └── data/                  # Snapshots y colectores offline
│
├── docs/                      # Documentación técnica
├── examples/                  # Referencias históricas (no funcionales)
└── wiki/                      # Páginas de este wiki
```

---

## Python engine modules (`runtime/`)

### `runtime/api/`

API façade and orchestration of services by domain.

| Archive | Responsibility |
|---------|----------------|
| `app.py` | FastAPI route composition, middleware |
| `bot_service.py` | Multi-instance bot hub service |
| `thusnelda_service.py` | Hub service for Thusnelda |
| Vault routes, gateway, ops, sandbox, usage | Facades by domain |

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
| `state_store.py` | Gateway memory status |
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
- **Hub service:** `runtime/api/bot_service.py`
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
- **API handlers:** `runtime/api/app.py`
  - `POST /api/v1/ops/protocol/close`
  - `POST /api/v1/ops/red_button`
  - `GET /api/v1/ops/protocol/status`
  - `POST /api/v1/ops/orders/cleanup/*`
- **Audit:** `runtime/data/ops_audit.sqlite`
- **Runbooks (Tasks):** `tools/ops-protocols/tasks/`

### `tools/sandbox-rest/`

Queries guided to Binance REST from the UI.

- **API:** `/api/v1/sandbox/rest/catalog`, `/api/v1/sandbox/rest/query`
- Supports: `get_exchange_info`, `get_account`, `get_open_orders`, `get_my_trades`

### `tools/rest-weight-monitor/`

REST weight monitor with history and audit per endpoint.

- **API:** `/api/v1/usage/rest-weight/events`, `/api/v1/usage/rest-weight/report`
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