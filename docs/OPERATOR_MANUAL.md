# Operator Manual — Pecunator-AccuMonetas Louise Hub

Guía de operación diaria para el operador responsable del hub de bots Louise.

---

## Contenido

1. [Checklist Diario](#1-checklist-diario)
2. [Arranque del Sistema](#2-arranque-del-sistema)
3. [Variables de Entorno](#3-variables-de-entorno)
4. [Configuración de Bots Louise](#4-configuración-de-bots-louise)
5. [Monitoreo](#5-monitoreo)
6. [Alertas Telegram](#6-alertas-telegram)
7. [Backup y Recuperación](#7-backup-y-recuperación)
8. [Seguridad del Vault](#8-seguridad-del-vault)
9. [Troubleshooting Rápido](#9-troubleshooting-rápido)
10. [Objetivos de Performance](#10-objetivos-de-performance)

---

## 1. Checklist Diario

Revisar cada mañana antes de comenzar el día de trading:

### Al iniciar (09:00 UTC)
- [ ] Motor corriendo: `http://127.0.0.1:8000/docs` responde
- [ ] Gateway conectado: UI muestra "WS: Connected"
- [ ] No hay alertas críticas sin resolver en Telegram
- [ ] Revisar balance de subcuenta bluechip en Binance
- [ ] Verificar que no hay órdenes huérfanas: `GET /api/louise/orphans/scan`
- [ ] Estado del presupuesto diario: `GET /api/v1/budget-guard/status`
- [ ] Peso API en zona GREEN: `GET /api/v1/governor/status`

### Al finalizar (antes del cierre de mercado relevante)
- [ ] Revisar PnL del día en la UI (sección Louise Hub)
- [ ] Confirmar epochs activos tienen actividad reciente
- [ ] Ejecutar backup manual: `scripts\backup\backup_databases.ps1`
- [ ] Revisar `backend.log` por errores inesperados

### Antes de un despliegue
- [ ] Backup de bases de datos
- [ ] Verificar que todos los bots están en estado IDLE o PAUSED
- [ ] Desconectar gateway desde la UI
- [ ] Ejecutar graceful shutdown del motor

---

## 2. Arranque del Sistema

### Inicio normal
```powershell
# 1. Motor Python (backend)
powershell -ExecutionPolicy Bypass -File scripts\engine\run_engine.ps1

# 2. UI Flutter (en otra ventana)
cd desktop_shell
flutter run -d windows
```

### Motor con inmortalidad (reinicio automático si cae)
```powershell
powershell -ExecutionPolicy Bypass -File scripts\engine\run_engine_immortal.ps1
```

### Modo stub (solo logging, sin API)
```bash
PECUNATOR_ENGINE_STUB=1 python main.py
```

### Verificar arranque exitoso
```bash
curl http://127.0.0.1:8000/api/v1/governor/status -H "Authorization: Bearer $(cat runtime/data/api.token)"
```
Respuesta esperada: `{"zone": "GREEN", ...}`

---

## 3. Variables de Entorno

### Obligatorias en producción

| Variable | Descripción | Ejemplo |
|----------|-------------|---------|
| `PECUNATOR_VAULT_PASSPHRASE` | Passphrase del vault de credenciales | `mi_passphrase_segura_123!` |
| `PECUNATOR_ALERT_TELEGRAM_TOKEN` | Token del bot de Telegram para alertas | `123456789:ABC...` |
| `PECUNATOR_ALERT_TELEGRAM_CHAT_ID` | Chat ID donde se envían las alertas | `-1001234567890` |

### Opcionales (con valores por defecto)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PECUNATOR_API_HOST` | `127.0.0.1` | IP donde escucha la API |
| `PECUNATOR_API_PORT` | `8000` | Puerto de la API |
| `PECUNATOR_API_WEIGHT_LIMIT_1M` | `6000` | Límite de peso REST por minuto |
| `PECUNATOR_LOG_LEVEL` | `INFO` | Nivel de logging (DEBUG, INFO, WARNING, ERROR) |
| `PECUNATOR_LOG_JSON` | `false` | Activar formato JSON en logs (para ingestión por Grafana/ELK) |
| `PECUNATOR_RELOAD` | `false` | Hot-reload en desarrollo |
| `UVICORN_LOG_LEVEL` | `info` | Log level de uvicorn |
| `PECUNATOR_BACKUP_DIR` | `runtime/data/backups` | Directorio de backups |

### Nunca en producción

| Variable | Riesgo |
|----------|--------|
| `PECUNATOR_API_AUTH_DISABLED=1` | ⚠️ CRÍTICO: expone API sin autenticación |
| `PECUNATOR_ENGINE_STUB=1` | Motor no arranca (modo de prueba) |

### Configurar en PowerShell
```powershell
$env:PECUNATOR_VAULT_PASSPHRASE = "mi_passphrase_segura"
$env:PECUNATOR_ALERT_TELEGRAM_TOKEN = "TOKEN_DE_TELEGRAM"
$env:PECUNATOR_ALERT_TELEGRAM_CHAT_ID = "CHAT_ID"
powershell -ExecutionPolicy Bypass -File scripts\engine\run_engine.ps1
```

---

## 4. Configuración de Bots Louise

### Crear nuevo bot Louise (vía API)
```bash
POST http://127.0.0.1:8000/api/louise/bots
Authorization: Bearer <token>
Content-Type: application/json

{
  "bot_id": "louise-dca-btc",
  "symbol": "BTCUSDT",
  "buy_volume": 50.0,
  "poll_interval_seconds": 60,
  "target_profit_pct": 1.5,
  "daily_budget_usdt": 500.0,
  "subaccount": "bluechip"
}
```

### Parámetros de configuración explicados

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `buy_volume` | USDT | Monto por compra DCA. Recomendado: 25-100 USDT según profundidad del par. |
| `poll_interval_seconds` | segundos | Con qué frecuencia el bot chequea precios. Mínimo recomendado: 30s. Menor = más peso API. |
| `target_profit_pct` | % | Ganancia objetivo para cerrar el epoch. Por defecto 1.5% = vende cuando precio > avg_buy × 1.015. |
| `daily_budget_usdt` | USDT | Límite de gasto diario. El BudgetGuard bloquea compras cuando se supera este límite. |

### Iniciar bot
```bash
POST http://127.0.0.1:8000/api/louise/bots/{bot_id}/start
Authorization: Bearer <token>
```

### Detener bot
```bash
POST http://127.0.0.1:8000/api/louise/bots/{bot_id}/stop
Authorization: Bearer <token>
```

### Ver estado de todos los bots
```bash
GET http://127.0.0.1:8000/api/louise/bots
Authorization: Bearer <token>
```

---

## 5. Monitoreo

### Endpoints de estado clave

| Endpoint | Qué monitorea |
|----------|---------------|
| `GET /api/v1/governor/status` | Peso API (zona GREEN/YELLOW/RED) |
| `GET /api-fuse/status` | Estado del circuit breaker |
| `GET /api/v1/budget-guard/status` | Gasto diario vs límite |
| `GET /api/v1/gateway/status` | Conexión WebSocket a Binance |
| `GET /api/louise/bots` | Estado de todos los bots |
| `GET /api/v1/ws/status` | Clientes WebSocket conectados |
| `GET /metrics` | Métricas Prometheus |

### Prometheus + Grafana (opcional, recomendado en producción)

1. Configurar Prometheus para scrapear `http://127.0.0.1:8000/metrics` cada 15 segundos
2. Importar dashboard: `docs/grafana-louise-dashboard.json`
3. Métricas disponibles:
   - `louise_bots_active` — bots corriendo
   - `louise_epochs_completed_total` — epochs completados (con ganancia)
   - `louise_pnl_total` — PnL acumulado en USDT
   - `api_requests_total` — requests por endpoint y código HTTP
   - `api_fuse_trips_total` — trips del circuit breaker
   - `weight_governor_blocks_total` — requests bloqueados por peso

### Logs en formato JSON (para ingestión por Grafana/ELK)
```bash
PECUNATOR_LOG_JSON=1 python main.py
```

Cada log tendrá la forma:
```json
{
  "timestamp": "2026-05-12T15:30:45Z",
  "level": "INFO",
  "name": "pecunator.api",
  "message": "Bot started",
  "correlation_id": "req-abc123",
  "bot_id": "louise-dca-btc"
}
```

---

## 6. Alertas Telegram

### Configuración inicial
1. Crear bot en Telegram: hablar con `@BotFather`, crear nuevo bot
2. Obtener token del bot
3. Iniciar conversación con el bot o agregar a un grupo
4. Obtener chat_id: `https://api.telegram.org/bot<TOKEN>/getUpdates`

### Verificar alertas funcionando
```bash
curl -X POST http://127.0.0.1:8000/api/v1/alerts/test \
  -H "Authorization: Bearer <token>"
```
→ Debe llegar mensaje de prueba a Telegram en < 10 segundos.

### Ajustar umbral de deduplicación

El sistema suprime alertas repetidas dentro de 300 segundos (5 minutos). Si una condición se recupera y vuelve a activarse dentro de ese período, no enviará una segunda alerta. Esto es por diseño para evitar spam.

### Niveles de alerta

| Nivel | Cuándo | Acción típica |
|-------|--------|---------------|
| CRITICAL | Fuse abierto, stop-loss, shutdown timeout | Intervención inmediata |
| WARNING | Gateway desconectado, zona RED, budget bajo | Revisar en los próximos minutos |
| INFO | Epoch completado, bot iniciado/detenido | Registro informativo |

---

## 7. Backup y Recuperación

### Backup manual
```powershell
powershell -ExecutionPolicy Bypass -File scripts\backup\backup_databases.ps1
```

Crea backup en `runtime/data/backups/<timestamp>/` con todos los SQLite.

### Backup automático (Task Scheduler de Windows)

1. Abrir Task Scheduler
2. Crear tarea básica → "Backup Louise Hub"
3. Trigger: Diario, 03:00 AM
4. Acción: Iniciar programa
   - Programa: `powershell.exe`
   - Argumentos: `-ExecutionPolicy Bypass -File "C:\ruta\al\repo\scripts\backup\backup_databases.ps1"`
5. Verificar que la tarea ejecuta correctamente

### Política de retención

Por defecto: 30 días. Ajustar con `$RetainDays` en el script o:
```powershell
.\scripts\backup\backup_databases.ps1 -RetainDays 60
```

### Restaurar desde backup

```powershell
# 1. Detener motor
scripts\engine\stop_engine_port.ps1

# 2. Restaurar archivo
Copy-Item "runtime\data\backups\20260512_030000\louise_hub.sqlite" `
          "runtime\data\louise_hub.sqlite"

# 3. Verificar integridad
sqlite3 runtime\data\louise_hub.sqlite "PRAGMA integrity_check;"

# 4. Reiniciar motor
powershell -ExecutionPolicy Bypass -File scripts\engine\run_engine.ps1

# 5. Escanear huérfanas (siempre después de restore)
curl -X GET http://127.0.0.1:8000/api/louise/orphans/scan?symbol=BTCUSDT `
  -H "Authorization: Bearer $(cat runtime/data/api.token)"
```

---

## 8. Seguridad del Vault

### Passphrase del vault

El vault de credenciales usa derivación de clave PBKDF2-SHA256 desde la passphrase configurada en `PECUNATOR_VAULT_PASSPHRASE`. La passphrase:

- **Nunca** debe aparecer en el código fuente, logs, o historial de git
- Debe tener al menos 16 caracteres con mayúsculas, números y símbolos
- Debe guardarse en un gestor de contraseñas (Bitwarden, 1Password, etc.)
- Requerida en **cada reinicio** del motor

### Rotación de clave del vault

Para rotar la clave (por ejemplo, después de sospechar compromiso):
```bash
POST http://127.0.0.1:8000/api/vault/rotate-key
Authorization: Bearer <token>
Content-Type: application/json

{
  "old_passphrase": "passphrase_anterior",
  "new_passphrase": "nueva_passphrase_segura_2026!"
}
```

Después de la rotación: actualizar `PECUNATOR_VAULT_PASSPHRASE` en el entorno antes del próximo reinicio.

### Audit log del vault

Todas las operaciones de derivación de clave y desbloqueo quedan registradas en:
```
runtime/data/vault_audit.log
```

Revisar regularmente para detectar accesos inesperados.

### API token

El token de la API se encuentra en `runtime/data/api.token`. Si se sospecha compromiso:
1. Eliminar el archivo: `rm runtime/data/api.token`
2. Reiniciar el motor — se generará un token nuevo automáticamente
3. La UI Flutter leerá el nuevo token en el próximo inicio

---

## 9. Troubleshooting Rápido

| Síntoma | Primer paso | Ver también |
|---------|------------|-------------|
| API no responde | Verificar que el proceso Python está corriendo | Sección 2 |
| UI no conecta al motor | Verificar puerto 8000 libre, token correcto | Sección 2 |
| Bots no compran | Verificar BudgetGuard, WeightGovernor, y ApiFuse | Runbook §1, §6, §7 |
| Balance no coincide | Escanear huérfanas | Runbook §2 |
| WS desconectado | Reconectar desde UI, luego reiniciar si persiste | Runbook §3 |
| Stop-loss inesperado | Verificar orden en Binance, revisar configuración | Runbook §4 |
| Motor no arranca | Verificar passphrase, puerto libre, dependencias | `pip install -r requirements.txt` |
| Tests fallan | Ver output de pytest, revisar dependencias | `pytest runtime/tests/ -v --tb=long` |
| Telegram no envía | Verificar token/chat_id, test con curl directo a API de Telegram | Sección 6 |
| Logs son ilegibles | Activar formato legible: `PECUNATOR_LOG_JSON=0` | Sección 5 |

### Comandos de diagnóstico rápido

```bash
# Estado general del sistema
curl http://127.0.0.1:8000/api/v1/governor/status -H "Authorization: Bearer $(cat runtime/data/api.token)"

# Últimas 50 líneas del log
tail -50 backend.log

# Verificar integridad de la BD
sqlite3 runtime/data/louise_hub.sqlite "PRAGMA integrity_check;"

# Contar epochs activos
sqlite3 runtime/data/louise_hub.sqlite "SELECT COUNT(*) FROM louise_epochs WHERE status = 'RUNNING';"

# Ver bots y su estado
sqlite3 runtime/data/louise_hub.sqlite "SELECT bot_id, status, updated_at FROM louise_bots ORDER BY updated_at DESC;"
```

---

## 10. Objetivos de Performance

Estos son los umbrales de performance validados por los load tests. Si los valores observados los superan consistentemente, investigar antes de continuar operando.

| Operación | Objetivo | Crítico |
|-----------|----------|---------|
| DB write (create bot, add purchase) | p95 < 50ms | > 200ms → revisar disco |
| DB read (get bot, get epochs) | p95 < 20ms | > 100ms → revisar índices |
| Epoch completo (5 compras) | p95 < 500ms | > 2000ms → revisar DB |
| API request (GET endpoints) | p95 < 200ms | > 1000ms → revisar red/carga |
| Graceful shutdown | < 30 segundos | > 30s → SHUTDOWN_TIMEOUT_EXCEEDED |
| Reconexión WS tras caída | < 60 segundos | > 300s → reiniciar motor |

### Cuándo escalar recursos

- CPU > 80% durante > 10 minutos → revisar número de bots y poll intervals
- Memoria > 200MB → revisar fugas en telemetry_collector o log handlers
- Disco con BD > 1GB → activar política de purge de datos históricos viejos

---

*Última actualización: 2026-05-12*  
*Referencia rápida de incidentes: [INCIDENT_RUNBOOK.md](INCIDENT_RUNBOOK.md)*
