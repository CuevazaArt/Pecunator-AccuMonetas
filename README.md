# PecunatorCore

Pecunator Core is a modular, high-integrity engine for real-time trading systems: Python **engine** (`runtime/`) plus a **Flutter desktop** shell (generated under `desktop_shell/`). There is **no web dashboard** in this repo.

## Directiva de trabajo

| Ámbito | Idioma |
|--------|--------|
| Este IDE, conversación y coordinación entre nosotros | **Español latino**, por defecto |
| Código fuente, nombres de símbolos, comentarios en código, mensajes de commit orientados al repositorio, y demás artefactos de implementación | **Inglés** |

## Flutter desktop (UI)

1. Instalar [Flutter SDK (Windows)](https://docs.flutter.dev/get-started/install/windows).
2. En la raíz del repo: `powershell -ExecutionPolicy Bypass -File scripts/init_flutter_desktop.ps1`
3. Abrir `desktop_shell/` en el IDE Flutter y ejecutar (p. ej. `flutter run -d windows`).

Más detalle: [`docs/architecture-next.md`](docs/architecture-next.md).

## Motor Python (HTTP API)

Por defecto **`python main.py`** levanta la API en **http://127.0.0.1:8765** (ajusta con `PECUNATOR_API_HOST` / `PECUNATOR_API_PORT`).

- OpenAPI: http://127.0.0.1:8765/docs  
- Solo stub de log (sin servidor): `PECUNATOR_ENGINE_STUB=1 python main.py`

Conectores Binance, cofre y estado: `runtime/` (ver `runtime/api/`).

### Bot preset B (exampleJV -> API for Flutter)

- Preset path: `GET /api/v1/bot/presets` (includes preset `B` with `XRPUSDT`, `450s`, `quote 8`, `profit 0.05`, `drop 0.004`).
- Current config: `GET /api/v1/bot/config` and update via `PUT /api/v1/bot/config`.
- Run loop: `POST /api/v1/bot/start`, `POST /api/v1/bot/stop`, one shot `POST /api/v1/bot/run_once`.
- Safety model: `simulated=true` by default. Live mode requires explicit switches: `simulated=false` and `trading_enabled=true`.

## Git

[`docs/git-cursor-github.md`](docs/git-cursor-github.md)
