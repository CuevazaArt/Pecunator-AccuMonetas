# PecunatorCore

PecunatorCore is a modular trading runtime with a local Python engine and a dedicated Flutter desktop UI.
This repository is **desktop-first**: there is **no browser dashboard**.

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

**Limpiar caché y recompilar la UI:** cierra la app (`pecunator_desktop.exe`) para liberar DLLs; en `desktop_shell/` ejecuta `flutter clean`, luego `flutter pub get` y `flutter build windows` (o `flutter run -d windows`). Datos del hub en SQLite: `runtime/data/dorothy_hub.sqlite` (elimínalo solo si quieres resetear logs/config del hub; haz copia antes).

Más detalle: [`docs/architecture-next.md`](docs/architecture-next.md).

## Motor Python (HTTP API)

Por defecto **`python main.py`** levanta la API en **[`http://127.0.0.1:8765`](http://127.0.0.1:8765)** (ajusta con `PECUNATOR_API_HOST` / `PECUNATOR_API_PORT`). Opcional: **`PECUNATOR_API_WEIGHT_LIMIT_1M`** (por defecto `6000`) alinea la barra de “peso REST” en la UI con el límite de referencia de `exchangeInfo`.

- Atajo PowerShell (venv + arranque directo): **`powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine.ps1`**.
- Supervisor inmortal del motor (reinicia si el proceso cae): **`powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine_immortal.ps1`**.
- Si el puerto **8765** queda ocupado por un proceso viejo: **`scripts/engine/stop_engine_port.ps1`** antes de volver a arrancar.
- OpenAPI: [`http://127.0.0.1:8765/docs`](http://127.0.0.1:8765/docs)  
- Solo stub de log (sin servidor): `PECUNATOR_ENGINE_STUB=1 python main.py`

Conectores Binance (`python-binance`), cofre y estado: `runtime/` (ver `runtime/api/`).

### Estructura modular del repo (raíz)

- `bots/` contiene un folder dedicado por bot activo:
  - `bots/dorothy/`
  - `bots/masha/`
  - `bots/thusnelda/`
- `tools/` contiene un folder dedicado por herramienta operativa:
  - `tools/ops-protocols/`
  - `tools/sandbox-rest/`
  - `tools/rest-weight-monitor/`
- `runtime/modules/` consolida módulos Python de dominio para bots y herramientas.
- `examples/` consolida referencias históricas/no funcionales (no participa del runtime productivo).

- **Límites de API / WebSocket y cumplimiento (referencia actualizable):** [`docs/binance-api-and-compliance.md`](docs/binance-api-and-compliance.md)

### Credenciales del motor

El motor toma credenciales desde:

1. Variables de entorno `PECUNATOR_BINANCE_API_KEY` / `PECUNATOR_BINANCE_API_SECRET`.
2. Cofre local cifrado (`runtime/data/credentials.enc`) gestionado desde la UI Flutter.

Recomendación operativa: usar una sola fuente activa por sesión para evitar mezclar cuentas sin querer.

### Mecanismo de inmortalidad (hub Dorothy)

- Las instancias del hub se persisten en `runtime/data/dorothy_hub.sqlite` con su **estado deseado** (`desired_running`).
- Si una instancia estaba marcada para correr, el motor intenta **reanudarla automáticamente** al iniciar y también cuando detecta caídas (reintentos periódicos con credenciales disponibles).
- Si hay desconexiones o excepciones transitorias, Dorothy aplica **reintentos con backoff** y recrea cliente para recuperar sesión de red.
- Para retomar trabajo tras reinicio de Windows, instala autoarranque:
  - `powershell -ExecutionPolicy Bypass -File scripts/engine/InstallImmortalStartup.ps1`

### Cofre (`credentials.enc`)

Las credenciales Binance se guardan en **`runtime/data/credentials.enc`** cifradas con **Fernet** usando la clave **`vault_local.key`** en la misma carpeta. Solo hacen falta **API key** y **secret** en la UI o por variables de entorno del motor.

## API surface (current)

- Vault + credenciales:
  - `GET /api/v1/vault/status`
  - `GET /api/v1/vault/credentials`
  - `POST /api/v1/vault/credentials`
  - `PATCH /api/v1/vault/credentials/{credential_id}`
  - `DELETE /api/v1/vault/credentials/{credential_id}`
  - `GET /api/v1/credentials/active`
- Gateway Binance:
  - `POST /api/v1/gateway/start`
  - `POST /api/v1/gateway/stop`
  - `GET /api/v1/gateway/snapshot`
  - `POST /api/v1/gateway/fetch_account`
  - `GET /api/v1/account/wallets?base_asset=USDT`
  - `POST /api/v1/time/sync`
- Protocolos operativos (trazabilidad):
  - `GET /api/v1/ops/protocol/status`
  - `POST /api/v1/ops/protocol/close?base_asset=USDT`
  - `POST /api/v1/ops/red_button?base_asset=USDT`
- Hub Dorothy (multi-instancia):
  - `GET /api/v1/hub/bots`
  - `POST /api/v1/hub/bots`
  - `PATCH /api/v1/hub/bots/{bot_id}`
  - `DELETE /api/v1/hub/bots/{bot_id}`
  - `POST /api/v1/hub/bots/{bot_id}/start`
  - `POST /api/v1/hub/bots/{bot_id}/stop`
  - `POST /api/v1/hub/bots/{bot_id}/run_once`
  - `GET /api/v1/hub/bots/{bot_id}/logs`

Legacy single-bot endpoints remain available under `/api/v1/bot/*` for compatibility.

## Política de tests

- La verificación oficial se ejecuta en **GitHub Actions** (`.github/workflows/`).
- Evitamos depender de test suites locales para validar merges a `main/develop`.
- Cualquier cambio en runtime/UI/workflows debe actualizar `docs/CHANGELOG.md`.
- El repositorio incluye escaneo automático de secretos en CI (`secret-scan.yml`) para prevenir exposición accidental.

## Documentación

- [`CHANGELOG.md`](CHANGELOG.md) — cambios relevantes  
- [`docs/CHANGELOG.md`](docs/CHANGELOG.md) — bitácora disciplinada de arquitectura/UI/API  
- [`docs/architecture-next.md`](docs/architecture-next.md) — arquitectura Flutter + motor  
- [`docs/repo-modules-map.md`](docs/repo-modules-map.md) — mapa modular de carpetas y ownership
- [`docs/main-runtime-boundary.md`](docs/main-runtime-boundary.md) — rol de `main` vs `runtime` y diseño escalable
- [`bots/README.md`](bots/README.md) — índice modular de bots en raíz
- [`tools/README.md`](tools/README.md) — índice modular de herramientas en raíz
- [`docs/bots/Dorothy-manual.md`](docs/bots/Dorothy-manual.md) — guía operativa Dorothy + riesgo + métricas
- [`docs/bots/Masha-manual.md`](docs/bots/Masha-manual.md) — guía operativa Masha + riesgo + métricas
- [`docs/bots/Thusnelda-manual.md`](docs/bots/Thusnelda-manual.md) — guía operativa Thusnelda + riesgo + métricas
- [`docs/syncfusion-charts-integration.md`](docs/syncfusion-charts-integration.md) — plan para integrar `syncfusion_flutter_charts` (equity/REST timeline)  
- [`docs/binance-api-and-compliance.md`](docs/binance-api-and-compliance.md) — límites Binance REST/WebSocket y checklist  
- [`docs/rest-weight-audit.md`](docs/rest-weight-audit.md) — auditoría de consumo REST por fuente/acción  
- [`docs/binance-limits-snapshots/`](docs/binance-limits-snapshots/) — snapshots fechados de `exchangeInfo.rateLimits`  
- [`docs/git-cursor-github.md`](docs/git-cursor-github.md) — Git / Cursor / GitHub  
