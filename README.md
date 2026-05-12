# Pecunator-AccuMonetas

**A specialized autonomous trading bot built on PecunatorCore infrastructure.**

Pecunator-AccuMonetas is a dedicated bot hub featuring a modular Python engine (FastAPI) and customized Flutter desktop UI. This repository is **desktop-first**: the Flutter shell connects to the local engine over HTTP, inheriting the proven architecture from PecunatorCore (v3.7.5 stable).

**Key Features:**
- Specialized trading bot strategy (AccuMonetas — *in development*)
- Full infrastructure: REST API, WebSocket, metrics, telemetry, DB persistence
- Risk control modules: rate-limiting, budget guards, auto-recovery
- Production-hardened: tests, monitoring, explicit deployment policy

## Status: Staging-Ready (Not Production)

**Current readiness:** ✅ Safe for **non-financial testing** (dry-run, paper trading, local development)  
**Production readiness:** ❌ **NOT READY** for operation with real capital or live Binance subaccounts

### Audit Findings & Remediation Status

| Finding | Severity | Status | Details |
|---------|----------|--------|---------|
| API route authentication gaps | CRITICAL | ✅ FIXED | All ops_router and gateway_router endpoints now require token verification |
| Exception handling specificity | HIGH | ✅ FIXED | lifespan.py updated to catch specific exception types for better diagnostics |
| CI gate incomplete coverage | HIGH | ✅ FIXED | test_e2e_pipeline.py now included in required merge checks |
| Graceful shutdown missing | HIGH | ✅ FIXED | Signal handlers (SIGTERM/SIGINT) + 6-step shutdown sequence with pending order cancellation |
| Orphan order recovery unavailable | MEDIUM | ✅ FIXED | Scan/adopt/cancel orphan orders tool implemented with REST endpoints |
| Vault key rotation missing | MEDIUM | ✅ FIXED | PBKDF2+Fernet encryption with passphrase-based key derivation and audit logging |
| Observability gaps | MEDIUM | ✅ FIXED | Prometheus metrics endpoint + JSON structured logging with correlation IDs |
| Integration test coverage | MEDIUM | ✅ FIXED | 12 comprehensive tests covering Louise bot lifecycle, stop-loss, concurrency, recovery |

### Requirements Before Production Deployment

Before operating this system with real capital:

1. ✅ All tests pass: `pytest runtime/tests/ tests/ -v --tb=short`
2. ✅ Authentication verified on all operational endpoints (ops_router, gateway_router)
3. ✅ Graceful shutdown tested: send SIGTERM, verify pending orders cancelled, DB state consistent
4. ✅ Vault security configured: PECUNATOR_VAULT_PASSPHRASE set, vault_audit.log monitored
5. ✅ Monitoring configured: Prometheus scraping `/metrics` endpoint, Grafana dashboard imported
6. ✅ Alerting verified: Telegram token configured, test alert fires successfully
7. ⚠️ Peer security review: another engineer reviews ops_router.py, lifespan.py, security_util.py
8. ⚠️ Load testing passed: p95 API latency < 500ms, peak memory < 200MB under 10 concurrent bots
9. ⚠️ Incident runbook reviewed: operator familiarized with alert meanings and recovery procedures
10. ⚠️ Backup & restore tested: database backup/recovery workflow validated end-to-end

## Directiva de trabajo

- Este IDE, conversación y coordinación entre nosotros: **Español latino**, por defecto.
- Código fuente, nombres de símbolos, comentarios en código, mensajes de commit orientados al repositorio, y demás artefactos de implementación: **Inglés**.

## Flutter desktop (UI)

1. Instalar [Flutter SDK (Windows)](https://docs.flutter.dev/get-started/install/windows).
2. En la raíz del repo: `powershell -ExecutionPolicy Bypass -File scripts/ui/init_flutter_desktop.ps1`
3. Abrir `desktop_shell/` en el IDE Flutter y ejecutar (p. ej. `flutter run -d windows`).
   - Atajo (PATH recargado + `flutter run`): `powershell -ExecutionPolicy Bypass -File scripts/ui/run_dashboard.ps1`, o doble clic en `scripts/ui/run_dashboard.cmd`.
   - Acceso rápido en el escritorio (motor + app): `powershell -ExecutionPolicy Bypass -File scripts/ui/InstallDesktopShortcut.ps1` crea **`PecunatorCore.lnk`**; el lanzador está en `scripts/ui/PecunatorDesktopLauncher.ps1`.
4. Producción Windows: `flutter build windows` y ejecutar `desktop_shell/build/windows/x64/runner/Release/pecunator_desktop.exe`.

**Limpiar caché y recompilar la UI:** cierra la app (`pecunator_desktop.exe`) para liberar DLLs; en `desktop_shell/` ejecuta `flutter clean`, luego `flutter pub get` y `flutter build windows` (o `flutter run -d windows`). Datos del hub en SQLite: `runtime/data/dorothy_hub.sqlite` y `runtime/data/elphaba_hub.sqlite`.

Más detalle: [`docs/architecture-next.md`](docs/architecture-next.md).

## Motor Python (HTTP API)

Por defecto la API se levanta en **[`http://127.0.0.1:8000`](http://127.0.0.1:8000)** (ajusta con `PECUNATOR_API_HOST` / `PECUNATOR_API_PORT`). Opcional: **`PECUNATOR_API_WEIGHT_LIMIT_1M`** (por defecto `6000`) alinea la barra de "peso REST" en la UI con el límite de referencia de `exchangeInfo`.

### API Authentication

The engine auto-generates a bearer token on first boot at `runtime/data/api.token`. The Flutter client reads this file directly from the filesystem. All endpoints require this token via `Authorization: Bearer <token>` header.

- To disable auth for development: `PECUNATOR_API_AUTH_DISABLED=1`
- Token auto-regenerates if the file is deleted.

### Quick Start

- Atajo PowerShell (venv + arranque directo): **`powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine.ps1`**.
- Supervisor inmortal del motor (reinicia si el proceso cae): **`powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine_immortal.ps1`**.
- Si el puerto **8000** queda ocupado por un proceso viejo: **`scripts/engine/stop_engine_port.ps1`** antes de volver a arrancar.
- OpenAPI: [`http://127.0.0.1:8000/docs`](http://127.0.0.1:8000/docs)  
- Solo stub de log (sin servidor): `PECUNATOR_ENGINE_STUB=1 python main.py`

### Política de Despliegue en Producción (Explicit Deployment)

El entorno de producción opera bajo una estricta política de **despliegue explícito**. El motor *no* hace `git pull` de manera automática al arrancar. Esto previene que código no probado (o con conflictos) se introduzca a producción inadvertidamente, lo que es vital al operar capital real.

**Procedimiento de actualización por el operador:**
1. Detener el motor de forma ordenada (apagar Gateway en el UI y detener el proceso Python).
2. Traer los cambios: `git pull origin main` (verificando que la firma del commit es segura).
3. Confirmar que los tests pasan: `pytest runtime/tests/ -x`
4. Reiniciar el motor mediante el script correspondiente.

Conectores Binance (`python-binance`), cofre y estado: `runtime/` (ver `runtime/api/`).

### Estructura modular del repo (raíz)

- `runtime/bot/` — Dorothy (spot DCA) and Elphaba (margin short) runners
- `runtime/core/` — Infrastructure: WeightGovernor, ApiFuse, BotCoordinator, SymmetryGuard, BudgetGuard, OrderLedger, StateWAL
- `runtime/api/` — FastAPI routers and hub services
- `runtime/modules/` — TrendSignal, VMO
- `runtime/connectors/` — BinanceGateway
- `runtime/tests/` — Official test suite
- `desktop_shell/` — Flutter desktop UI

### Credenciales del motor

El motor toma credenciales desde:

1. Variables de entorno por bot: `DOROTHY_API_KEY`/`DOROTHY_API_SECRET` y `ELPHABA_API_KEY`/`ELPHABA_API_SECRET`.
2. Cofre local cifrado (`runtime/data/credentials.enc`) gestionado desde la UI Flutter.

Recomendación operativa: usar una sola fuente activa por sesión para evitar mezclar cuentas sin querer.

### Mecanismo de inmortalidad (hub Dorothy + Elphaba)

- Las instancias del hub se persisten en `runtime/data/dorothy_hub.sqlite` y `runtime/data/elphaba_hub.sqlite` con su **estado deseado** (`desired_running`).
- Si una instancia estaba marcada para correr, el motor intenta **reanudarla automáticamente** al iniciar y también cuando detecta caídas (reintentos periódicos con credenciales disponibles).
- Si hay desconexiones o excepciones transitorias, ambos bots aplican **reintentos con backoff** y recrean cliente para recuperar sesión de red.
- **StateWAL** persiste el estado del gateway después de cada ciclo de polling para crash-safe recovery.

### Cofre (`credentials.enc`)

Las credenciales Binance se guardan en **`runtime/data/credentials.enc`** cifradas con **Fernet** usando la clave **`vault_local.key`** en la misma carpeta.

## Security Considerations

### API Authentication

**All endpoints require authentication** via bearer token (`Authorization: Bearer <token>` header) unless explicitly disabled. This includes:

- REST API endpoints: `/api/v1//*`
- WebSocket: `/ws/telemetry` (token via query param or `X-API-Token` header)
- Operations endpoints: `/api/louise/*`, `/api/orphans/*` (require `verify_token` dependency)
- Metrics endpoint: `/metrics` (public — no auth required for Prometheus scraping)

**Development-only:** Disable auth with `PECUNATOR_API_AUTH_DISABLED=1`. ⚠️ **NEVER** use this in production.

### Vault Passphrase Security

The vault encryption key is derived from **`PECUNATOR_VAULT_PASSPHRASE`** environment variable using PBKDF2-SHA256 (100,000 iterations). This passphrase:

- Must be **strong** (minimum 16 characters, mixed case + numbers + symbols recommended)
- Must **NOT** be committed to source control (store in secure password manager or CI secrets)
- Is **required** on every engine restart (encrypted vault cannot be unlocked without it)
- Can be rotated via `POST /api/vault/rotate-key` endpoint (requires old + new passphrase)

All vault access is logged to **`runtime/data/vault_audit.log`** with timestamps.

### Telegram Alert Credentials

Configure alerts via environment variables:

```bash
PECUNATOR_ALERT_TELEGRAM_TOKEN=<bot-token>
PECUNATOR_ALERT_TELEGRAM_CHAT_ID=<chat-id>
```

Alert deduplication prevents spam: same alert fired multiple times within 300 seconds is muted.

### What NOT to Do

- ❌ Do not enable `PECUNATOR_API_AUTH_DISABLED=1` in production
- ❌ Do not commit passphrases, API keys, or tokens to git (use `.env` files and `.gitignore`)
- ❌ Do not operate with margin trading enabled until after peer security review
- ❌ Do not expose the API port (8000) publicly without proper network segmentation
- ❌ Do not reuse API credentials across multiple engine instances

## Política de tests

```bash
# Run full test suite (50+ tests across runtime/ and tests/)
python -m pytest runtime/tests/ tests/ -v --tb=short

# Or run specific test class/function
python -m pytest runtime/tests/test_louise_integration.py::TestDCALifecycle::test_happy_path -v
```

- **`runtime/tests/`** — official test suite covering core modules, control gates, metrics, security, logging (40+ tests). All tests must pass before merging.
- **`tests/test_e2e_pipeline.py`** — end-to-end integration tests covering Louise bot lifecycle, subaccount registry, decision logging (10+ tests). **Required for merge** (CI gate includes this).
- **`tests/legacy/`** — historical integration tests (reference only, not gated).
- **GitHub Actions** (`.github/workflows/ci-gate.yml`) — automated verification on every PR. Both `runtime/tests/` and `tests/` must pass.
- **Secret scanning** — automatic credential detection in CI (`secret-scan.yml`).

### Risk control modules (v0.11+)

| Module | Purpose | Endpoint |
|---|---|---|
| `weight_governor` | Zone-based API weight throttling (GREEN/YELLOW/RED) | `/api/v1/governor/status` |
| `api_fuse` | Emergency API circuit breaker with escalating backoff | `/api-fuse/status` |
| `bot_coordinator` | Phase-shift bot launches to distribute API load | (internal) |
| `budget_guard` | Hard daily USDT spend ceiling | `/api/v1/budget-guard/status` |
| `order_ledger` | Forensic order audit trail | `/api/v1/order-ledger/recent` |
| `symmetry_guard` | Symmetric hub watchdog with auto-recovery | (internal) |
| `state_wal` | Crash-safe WAL-backed state persistence | (internal) |

### Strategy modules

| Module | Purpose |
|---|---|
| `TrendSignal` | HA MA crossover gate for entry/exit timing |
| `EVI` | Electric Volatility Index gate for dead-market filtering |

## Documentación

- [`CHANGELOG.md`](CHANGELOG.md) — cambios relevantes  
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md) — bitácora disciplinada de arquitectura/UI/API  
- [`docs/architecture-next.md`](docs/architecture-next.md) — arquitectura Flutter + motor  
- [`docs/repo-modules-map.md`](docs/repo-modules-map.md) — mapa modular de carpetas y ownership
- [`docs/main-runtime-boundary.md`](docs/main-runtime-boundary.md) — rol de `main` vs `runtime` y diseño escalable

### Operations (producción)

- [`docs/INCIDENT_RUNBOOK.md`](docs/INCIDENT_RUNBOOK.md) — procedimientos de incidentes: fuse, huérfanas, shutdown, DB corruption
- [`docs/OPERATOR_MANUAL.md`](docs/OPERATOR_MANUAL.md) — checklist diario, variables de entorno, backup, troubleshooting

### Scripts

- [`scripts/backup/backup_databases.ps1`](scripts/backup/backup_databases.ps1) — backup automático de todas las bases SQLite con verificación de integridad y rotación por fecha
