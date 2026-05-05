# Changelog — Pecunator

> Historial de cambios arquitectónicos, de API y operativos.  
> Los cambios que tocan `runtime/`, `desktop_shell/`, o `.github/workflows/` deben registrarse aquí.

---

## Reglas de este Changelog

- Cada cambio que toca `runtime/`, `desktop_shell/`, o `.github/workflows/` añade una entrada
- Entradas en orden cronológico inverso (más reciente primero)
- Formato: qué cambió, por qué importa, notas de migración si aplica
- No se registran secrets, credenciales ni rutas de máquinas locales

---

## [Unreleased]

### Inmortalidad del runtime / auto-recovery

- **Adicionado:** Persistencia de estado deseado (`desired_running`) en `runtime/data/dorothy_hub.sqlite`
- **Adicionado:** Supervisor inmortal de instancias: si un bot estaba marcado para correr y se detiene, el servicio reintenta el arranque automáticamente
- **Mejorado:** Resiliencia del loop Dorothy — fallos transitorios activan recreación de cliente + backoff (`bot:retry_in ...`)
- **Scripts nuevos:**
  - `scripts/engine/run_engine_immortal.ps1` (watchdog / auto-restart del motor)
  - `scripts/engine/InstallImmortalStartup.ps1` (shortcut de autoarranque en Windows)

### Monitor de equity de cuenta

- **Adicionado:** Conversión rolling de equity spot al activo base en el estado del gateway (`current`, `avg`, `high_avg`)
- **Variables de entorno nuevas:**
  - `PECUNATOR_EQUITY_BASE_ASSET` (default `USDT`)
  - `PECUNATOR_EQUITY_AVG_WINDOW` (default `6`)
  - `PECUNATOR_EQUITY_POLL_STRIDE` (default `5`)
- **Expuesto** en `GET /api/v1/gateway/snapshot` y en `GET /api/v1/account/wallets`
- **UI:** Tarjeta de equity en vivo en la ventana de detalles de cuenta Spot

### Protocolos operativos: close protocol + botón rojo

- **Adicionado:** Operaciones con detención obligatoria de Dorothy para evitar loops:
  - `POST /api/v1/ops/protocol/close`
  - `POST /api/v1/ops/red_button`
  - `GET /api/v1/ops/protocol/status`
- **Adicionado:** Store de trazabilidad `runtime/core/ops_audit_log.py` (`ops_audit.sqlite`)
- **UI:** Fila de dashboard con tooltips explicativos, botones de operación, valores de monitor y visor de resumen

### Simplificación del vault

- **Almacenamiento:** `credentials.enc` cifrado con Fernet + `vault_local.key`
- **UX/API:** Flujo reducido a add/delete con activación automática de la última key guardada

---

## 2026-04-29

### Documentación y estructura modular de ejemplos

- **Adicionado:** `examples/` como punto único para referencias históricas no funcionales
- **Adicionado:** Documento `docs/main-runtime-boundary.md` con responsabilidades explícitas
- **Cambiado:** Scripts reorganizados por dominio (`scripts/ui/`, `scripts/engine/`, `scripts/data/`)
- **Impacto:** Menor fricción de mantenimiento al separar responsabilidades por carpeta

### Seguridad CI

- **Adicionado:** Workflow `.github/workflows/secret-scan.yml` (Gitleaks) para detectar secretos en pushes/PRs hacia ramas principales
- **Cambiado:** Scripts de arranque endurecidos con fallback a `python` del sistema cuando no existe `.venv`
- **Impacto:** Menor riesgo de fuga de credenciales en el repositorio

### Módulos por dominio

- **Adicionado:** Estructura modular explícita:
  - `runtime/modules/bots/` (Dorothy, Masha, Thusnelda)
  - `runtime/modules/tools/` (ops protocols, sandbox rest, rest-weight monitor)
- **Adicionado:** Índices modulares en raíz (`bots/`, `tools/`) con `MODULE.md` por bot/herramienta
- **Cambiado:** Servicios API de bots y tests migrados a imports `runtime.modules.bots.*`
- **Impacto:** Navegación más clara para añadir nuevos bots/herramientas sin mezclar capas

### Auditoría de peso REST

- **Adicionado:** Auditoría detallada de peso REST por acción/fuente:
  - `GET /api/v1/usage/rest-weight/events`
  - `GET /api/v1/usage/rest-weight/report`
- **Adicionado:** Documento `docs/rest-weight-audit.md`
- **Cambiado:** Eliminadas llamadas redundantes de `ping` en el loop de polling
- **Cambiado:** Tooltips en configuración de Masha y Thusnelda
- **Impacto:** Más trazabilidad para identificar qué endpoint/acción eleva el peso por minuto

### Páginas guía por bot en UI Flutter

- **Adicionado:** Páginas guía dedicadas por bot (`Dorothy`, `Masha`, `Thusnelda`) en la UI
- **Cambiado:** Botones de instructivo abren pantalla completa (qué hace, operación base, riesgos, quick start)
- **Impacto:** Onboarding más rápido para operar cada bot desde su Hub

### Mejoras de riesgo y métricas por bot

- **Adicionado:** `exampleJV_enhanced/` en `examples/` para trazabilidad
- **Adicionado:** Manuales de usuario por bot en `docs/bots/`
- **Adicionado:** Tablas SQLite por hub: `*_runtime_state`, `*_equity_snapshots`, `*_metrics_log`
- **Cambiado:** Parámetros de riesgo/métricas para los 3 bots:
  - `max_drawdown_pct`
  - `stop_loss_pct`
  - `metrics_interval_cycles`
- **Corregido:** Hubs ahora restauran estado de riesgo persistido al reiniciar (peak equity, drawdown, ciclos)
- **Impacto:** Mayor protección ante mercados bajistas sin romper arquitectura original

### Thusnelda 1.0

- **Adicionado:** Bot Thusnelda con runner `runtime/bot/thusnelda.py` (multi-symbol, average-buy, equity target)
- **Adicionado:** Hub service `runtime/api/thusnelda_service.py` con persistencia SQLite
- **Adicionado:** API surface `/api/v1/thusnelda/bots/*` y pantalla Flutter dedicada
- **Cambiado:** Barras de peso REST con colores (verde/naranja/rojo) en dashboard
- **Impacto:** Tres bots (Dorothy, Masha, Thusnelda) operables desde la misma superficie de control

### Sandbox REST

- **Adicionado:** API de Sandbox REST (`/api/v1/sandbox/rest/catalog`, `/api/v1/sandbox/rest/query`)
- **Adicionado:** Sincronización automática de timestamp + retry para llamadas signed
- **Adicionado:** Sección de doctrina arquitectónica sobre objetivo profit-first
- **Cambiado:** UI del Sandbox simplificada a modelo de query guiado
- **Corregido:** Fallos intermitentes de `/api/v1/account/wallets` por timestamp ahead-of-server
- **Corregido:** Sandbox intentaba llamar directamente a paths de Binance desde Flutter; ahora se enruta por engine
- **Impacto:** Operadores pueden validar estructuras Binance más rápido con menos pasos

---

*Para agregar entradas nuevas: seguir el formato y agregar al inicio de la sección `[Unreleased]` o crear nueva sección con fecha.*
