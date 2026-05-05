# Mapa de Módulos — Pecunator

> Referencia de la estructura de carpetas, ownership y entrypoints de cada módulo.  
> Última actualización: 2026-04-29

---

## Estructura raíz del repositorio

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

## Módulos del motor Python (`runtime/`)

### `runtime/api/`

API façade y orquestación de servicios por dominio.

| Archivo | Responsabilidad |
|---------|----------------|
| `app.py` | Composición de rutas FastAPI, middleware |
| `bot_service.py` | Servicio del hub multi-instancia de bots |
| `thusnelda_service.py` | Hub service para Thusnelda |
| Rutas de vault, gateway, ops, sandbox, usage | Façades por dominio |

### `runtime/connectors/`

| Archivo | Responsabilidad |
|---------|----------------|
| `binance_gateway.py` | Polling de cuenta, market streams, REST weight tracking, equity refresh |

### `runtime/core/`

Primitivas compartidas sin dependencia de capas superiores.

| Módulo | Responsabilidad |
|--------|----------------|
| `settings.py` | Variables de entorno y configuración |
| `vault.py` | Cifrado/descifrado de credenciales Fernet |
| `state_store.py` | Estado en memoria del gateway |
| `ops_audit_log.py` | Auditoría de protocolos operativos (SQLite) |
| `config_manager.py` | Configuración persistente de bots |
| `security_util.py` | Sanitización de logs |

### `runtime/modules/bots/`

Módulos de estrategia de bots (imports canónicos desde esta ruta).

| Módulo | Bot | Descripción |
|--------|-----|-------------|
| `dorothy.py` | Dorothy | Escalera spot — SELL LIMIT + compra en caída |
| `masha.py` | Masha | DCA multi-timeframe con señal técnica (`1w`+`1h`) |
| `thusnelda.py` | Thusnelda | Cesta de símbolos con meta de equity global |

### `runtime/modules/tools/`

| Módulo | Herramienta | Descripción |
|--------|-------------|-------------|
| `ops/` | Ops Protocols | Implementación de close protocol y red button |

---

## Módulos de bots en raíz (`bots/`)

Índices documentales con entrypoints, superficie API y stores SQLite.

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

## Módulos de herramientas en raíz (`tools/`)

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

Queries guiadas a Binance REST desde la UI.

- **API:** `/api/v1/sandbox/rest/catalog`, `/api/v1/sandbox/rest/query`
- Soporta: `get_exchange_info`, `get_account`, `get_open_orders`, `get_my_trades`

### `tools/rest-weight-monitor/`

Monitor de peso REST con historial y auditoría por endpoint.

- **API:** `/api/v1/usage/rest-weight/events`, `/api/v1/usage/rest-weight/report`
- Fuente: header Binance `X-MBX-USED-WEIGHT-1M`

---

## Scripts (`scripts/`)

| Carpeta | Scripts clave |
|---------|--------------|
| `scripts/ui/` | `init_flutter_desktop.ps1`, `run_dashboard.ps1`, `run_dashboard.cmd`, `PecunatorDesktopLauncher.ps1`, `InstallDesktopShortcut.ps1` |
| `scripts/engine/` | `run_engine.ps1`, `run_engine_immortal.ps1`, `stop_engine_port.ps1`, `InstallImmortalStartup.ps1` |
| `scripts/data/` | `fetch_binance_exchange_info_limits.py` |

---

## Nota de compatibilidad

- `runtime/bot/*` permanece disponible como puente de compatibilidad mientras los imports migran a `runtime/modules/bots/*`
- El código nuevo debe importar runners/configs desde `runtime.modules.bots`
