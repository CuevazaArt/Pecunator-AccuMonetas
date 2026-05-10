# PecunatorCore

PecunatorCore is a modular autonomous trading runtime with a local Python engine (FastAPI) and a dedicated Flutter desktop UI.
This repository is **desktop-first**: the Flutter shell connects to the local engine over HTTP.

**Symmetric Hub Architecture:** Dorothy (bullish DCA spot) + Elphaba (bearish margin short) operate as a paired hedge on the same symbols.

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

## Política de tests

```bash
# Run official test suite (195+ tests, ~1.5 seconds)
python -m pytest runtime/tests/ -x -q --tb=short
```

- **`runtime/tests/`** — official test suite. All tests must pass before merging.
- **`tests/legacy/`** — historical integration tests (reference only, not gated).
- Verificación automatizada en **GitHub Actions** (`.github/workflows/`).
- Escaneo automático de secretos en CI (`secret-scan.yml`).

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
