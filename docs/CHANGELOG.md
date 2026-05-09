# Documentation Changelog

This changelog is the disciplined, operator-facing history for architecture, UI behavior, API surface, and operational safety rules.

## Rules

- Every change that touches `runtime/`, `desktop_shell/`, or `.github/workflows/` must add one entry here.
- Entries are append-only and ordered newest first.
- Keep each entry short and operational: what changed, why it matters, and migration notes if needed.
- Do not log secrets, credentials, or local machine paths.

## Entry template

```md
## YYYY-MM-DD

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Operational impact
- ...
```

## 2026-05-09 (v3.1.1)

### Added
- **M2: Atomic Symmetric Deploy**: Endpoint `/api/v1/hub/deploy-symmetric` for simultaneous creation/start of Dorothy+Elphaba pairs with automatic rollback on partial failure.
- **M3: Alert Dispatcher**: Centralized alerting system in `runtime/core/alert_dispatcher.py`, writing to `alerts.log`.
- **M4: Process Watchdog**: External `watchdog.py` monitor for auto-restart on engine crashes.
- **M1.1: Log Rotation & Silence**: `RotatingFileHandler` (15MB cap) + suppression of `uvicorn.access` logs to reduce polling noise.

### Changed
- **M5: Legacy Test Quarantine**: `tests/legacy/` now uses `collect_ignore_glob` to skip broken imports without polluting the suite.
- **Prospector Visibility**: Added batch progress and auto-staging decision logging at `INFO` level.

### Fixed
- **HubBotOut Validation**: Fixed `stop_loss_pct` validation error for Elphaba bots (made optional).
- **Silent Guard Failures**: Replaced silent `except: pass` in `_base_runner.py` with explicit logging.

### Operational impact
- Reduced risk of asymmetric bot operation (one side live, one dead).
- Guaranteed disk safety via log rotation.
- Improved reliability via external watchdog.
- Cleaner logs for real-time monitoring.

## 2026-04-29

### Added
- Carpeta `examples/` como punto único para referencias históricas no funcionales (fusión de propósito de `exampleJV` + `exampleJV_enhanced`).
- Documento arquitectónico `docs/main-runtime-boundary.md` con responsabilidades explícitas de `main` y `runtime` para escalar.

### Changed
- Scripts reorganizados por dominio:
  - `scripts/ui/` (dashboard, launcher, atajos de escritorio)
  - `scripts/engine/` (arranque/parada/supervisor del motor)
  - `scripts/data/` (snapshots operativos como `exchangeInfo`)
- Documentación actualizada a las nuevas rutas de scripts y al uso de `examples/`.

### Operational impact
- Menor fricción para mantenimiento al separar responsabilidades operativas por carpeta.
- Menos riesgo de mezclar código productivo con ejemplos de referencia.

## 2026-04-29

### Added
- Nuevo workflow de seguridad `.github/workflows/secret-scan.yml` (Gitleaks) para detectar secretos en pushes/PR hacia ramas principales.

### Changed
- Scripts de arranque `scripts/engine/run_engine.ps1` y `scripts/engine/run_engine_immortal.ps1` endurecidos con fallback a `python` del sistema cuando no existe `.venv`.

### Operational impact
- Menor riesgo de fuga de credenciales en el repositorio.
- Menor fragilidad operativa al iniciar motor en equipos sin entorno virtual activado.

## 2026-04-29

### Added
- Estructura modular explícita por dominio:
  - `runtime/modules/bots/`
  - `runtime/modules/tools/`
- Índices modulares en raíz para expansión y legibilidad:
  - `bots/` (Dorothy, Masha, Thusnelda)
  - `tools/` (ops protocols, sandbox rest, rest-weight monitor)
- Archivos `MODULE.md` por bot/herramienta con entrypoints, API surface y SQLite asociados.

### Changed
- Servicios API de bots y tests principales migrados a imports `runtime.modules.bots.*`.
- Workflow Python (`mypy`) actualizado para validar el path modular de bots.
- Documentación de arquitectura (`README.md`, `docs/architecture-next.md`) alineada al nuevo esquema modular.

### Fixed
- Eliminada documentación de refactor legacy que ya no representa el estado actual (`REFACTOR_*`).

### Operational impact
- Navegación más clara para añadir nuevos bots/herramientas sin mezclar capas.
- Menor fricción para onboarding y mantenimiento de runtime a mediano plazo.

## 2026-04-29

### Added
- Auditoría detallada de peso REST por acción/fuente con nuevos endpoints:
  - `GET /api/v1/usage/rest-weight/events`
  - `GET /api/v1/usage/rest-weight/report`
- Documento operativo `docs/rest-weight-audit.md` con modelo de cuantización y lista de fuentes de consumo.
- Monitor UI de peso REST enriquecido con pestañas de resumen, eventos auditados y muestras históricas.

### Changed
- Se eliminaron llamadas redundantes de `ping` en el loop de polling del gateway para reducir consumo de peso innecesario.
- Se agregaron tooltips extensos en seteo individual de Masha y Thusnelda (creación + edición por instancia).
- Se amplió el manual in-app por bot (`BotGuidePage`) con guía de parámetros y troubleshooting.
- Módulo de herramientas operativas (close/red/cleanups) reorganizado en lista compacta en una sola tarjeta.

### Operational impact
- Más trazabilidad para identificar qué endpoint/acción eleva el peso por minuto.
- Menor ruido de consumo base en el monitor al evitar pings periódicos redundantes.
- Menor ambigüedad operativa al ajustar parámetros por bot e instrumento.

## 2026-04-29

### Added
- Páginas guía dedicadas por bot en la UI Flutter (`Dorothy`, `Masha`, `Thusnelda`) para simplificar la introducción operativa y evitar instructivos extensos en modales.

### Changed
- Botones de instructivo en cada Hub ahora abren una pantalla completa con: qué hace el bot, operación base, riesgos y flujo de inicio rápido.
- Scripts de arranque del motor (`run_engine.ps1`, `run_engine_immortal.ps1`) simplificados a arranque directo de `main.py` sin dependencia de ejemplos externos.
- Documentación (`README.md`, `docs/architecture-next.md`, `docs/binance-api-and-compliance.md`) actualizada para reflejar flujo de credenciales por cofre/entorno.

### Fixed
- Limpiadas referencias operativas antiguas a `exampleJV` en runtime/UI para evitar confusión de mantenimiento.

### Operational impact
- Onboarding más rápido para operar cada bot desde su Hub.
- Menor acoplamiento entre runtime productivo y carpetas de ejemplo.

## 2026-04-29

### Added
- Importado `exampleJV_enhanced/` desde la rama de colaboración para dejar trazabilidad de ejemplos mejorados (`Dorothy7.1`, `Masha2.1`, `Thusnelda1.1`) en paralelo a `exampleJV/`.
- Manuales de usuario por bot en `docs/bots/` (uno para Dorothy, Masha y Thusnelda) con variables operativas y consultas SQLite.
- Nuevas tablas SQLite por hub para persistencia operativa:
  - `*_runtime_state`
  - `*_equity_snapshots`
  - `*_metrics_log`

### Changed
- Integración incremental de mejoras de `exampleJV_enhanced` en los runners de runtime:
  - `runtime/bot/dorothy.py`
  - `runtime/bot/masha.py`
  - `runtime/bot/thusnelda.py`
- Se agregaron parámetros configurables de riesgo/métricas por bot:
  - `max_drawdown_pct`
  - `stop_loss_pct`
  - `metrics_interval_cycles`
- Se actualizó el API schema/surface para aceptar esos parámetros en create/update de los 3 hubs.
- UI Flutter actualizada para exponer esos parámetros en Dorothy/Masha/Thusnelda y aplicar cambios vía `Guardar y aplicar`.
- Se agregaron instructivos en interfaz para Masha y Thusnelda (Dorothy ya existente) para mejorar coherencia de uso.

### Fixed
- Los hubs ahora restauran estado de riesgo persistido al reiniciar (peak equity / max drawdown / contador de ciclos), evitando reinicio "ciego" de protección.

### Operational impact
- Mayor protección ante mercados bajistas (drawdown guard + stop-loss) sin romper arquitectura original de cada bot.
- Métricas de performance y snapshots de equity quedan persistidos en SQLite por instancia para auditoría y tuning.

## 2026-04-29

### Added
- New `Thusnelda1.0` bot integration with dedicated runtime runner (`runtime/bot/thusnelda.py`) implementing multi-symbol average-buy trigger, equity target tracking, and optional liquidation-to-USDT behavior.
- New multi-instance hub service for Thusnelda (`runtime/api/thusnelda_service.py`) with SQLite persistence/logging and immortality recovery flow, equivalent to Dorothy/Masha management style.
- New API surface for Thusnelda hub lifecycle and logs (`/api/v1/thusnelda/bots`, `/start`, `/stop`, `/run_once`, `/logs`) plus Flutter client methods and a dedicated `Thusnelda1.0 Hub` page.

### Changed
- REST weight monitor bars now use color thresholds (green/orange/red) in dashboard and monitor dialog to quickly identify load risk against Binance 1m weight limits.
- Ops status payload now includes `thusnelda_hub_stats` for centralized hub visibility.

### Fixed
- Verified current engine/UI terminal logs for active processes: no new `Traceback`, `500`, `404`, or Binance API errors detected during this update window.

### Operational impact
- Operators can compare and run three bots (Dorothy, Masha, Thusnelda) from the same control surface with consistent controls.
- Weight saturation risk is easier to detect at a glance due to explicit color coding in monitor bars.

## 2026-04-29

### Added
- Sandbox REST query API (`/api/v1/sandbox/rest/catalog`, `/api/v1/sandbox/rest/query`) for guided Binance calls such as `get_exchange_info`, `get_account`, `get_open_orders`, `get_my_trades`.
- Backend timestamp auto-sync + retry for signed sandbox and wallet calls to mitigate Binance `-1021` drift errors.
- Architecture doctrine section documenting profit-first objective with controlled-loss handling.

### Changed
- Sandbox UI simplified to a guided REST-query model instead of free-form method/body editing.
- Credential manager UX simplified around add/delete with auto-activation flow.
- CI expectation clarified: checks/tests are enforced in GitHub Actions.

### Fixed
- `/api/v1/account/wallets` intermittent failures caused by timestamp ahead-of-server.
- Sandbox attempts to call raw Binance paths directly from Flutter (`/api/v3/exchangeInfo`), now routed through engine API.

### Operational impact
- Operators can validate Binance structures faster with fewer UI steps.
- Less manual recovery from timestamp drift during account/sandbox calls.
- Changelog discipline is now explicit for future maintenance.
