# Binance — Límites y Cumplimiento

> Referencia operativa para PecunatorCore sobre rate limits de Binance REST y WebSocket.  
> Los límites **cambian**; Binance es la fuente de verdad.  
> Última revisión: 2026-04-29

---

## Fuentes Oficiales

| Tema | URL |
|------|-----|
| Límites REST (Spot) | https://developers.binance.com/docs/binance-spot-api-docs/rest-api/limits |
| Límites WebSocket API | https://developers.binance.com/docs/binance-spot-api-docs/websocket-api/rate-limits |
| Streams WebSocket (Spot) | https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md |
| FAQ API (límites duros, WAF, bans) | https://www.binance.com/en/support/faq/detail/360004492232 |
| Changelog API | https://developers.binance.com/docs/binance-spot-api-docs |

> Nota regional: si usas otro dominio (ej. `.info`), verificar que la política coincida con tu jurisdicción y producto.

---

## Conceptos Clave

### Peso de peticiones (`REQUEST_WEIGHT`)

Cada endpoint REST tiene un **peso distinto** — no es "un request = una unidad".

- El consumo se acumula **por IP** en Spot REST típico
- Las respuestas incluyen cabeceras `X-MBX-USED-WEIGHT-*`
- **HTTP 429** = límite superado
- **HTTP 418** = ban por IP por insistir sin backoff (duración escalable)

> ⚠️ No fijes límites como constantes en código — los valores exactos cambian.

### Órdenes (`ORDERS`)

- Límites **por cuenta** para creación de órdenes (por ventanas de tiempo)
- Órdenes rechazadas pueden no incrementar ciertos contadores (ver documentación vigente)

### Web Application Firewall (WAF)

- Patrones de tráfico sospechosos producen **403** con duración de bloqueo típica de minutos (abuso leve)
- **No** intentes evadir límites — reduce frecuencia y usa streams

### WebSocket — Streams de Mercado

| Parámetro | Valor típico (verificar doc actual) |
|-----------|--------------------------------------|
| Duración máxima de conexión | ~24 horas (prever reconexión) |
| Mensajes de control (subscribe/unsubscribe) | ~5 por segundo por conexión |
| Streams por conexión | Hasta 1024 |
| Intentos de nueva conexión | ~300 por 5 minutos por IP |

El servidor envía **ping** periódico; el cliente debe responder **pong** o la conexión cae.

### WebSocket API (API sobre WS)

- Límites de peso y conexiones documentados separadamente del REST
- Una conexión nueva puede tener coste de peso > 0

---

## Cómo se Relaciona con PecunatorCore

| Área | Comportamiento recomendado |
|------|----------------------------|
| **Polling REST** | Ajustar `PECUNATOR_ACCOUNT_POLL_SEC` en `runtime/core/settings.py` si aparecen 429 o latencia excesiva |
| **Credenciales** | Usar el vault cifrado (`runtime/data/`) o variables de entorno; no incrustar claves en Flutter ni repos |
| **Arranque motor** | Ejecutar `scripts/engine/run_engine.ps1` o `python main.py`; credenciales se resuelven por entorno o cofre |
| **Órdenes / bots** | Respetar filtros de símbolo (`PRICE_FILTER`, `LOT_SIZE`, notional mínimo); errores de precisión son responsabilidad de la estrategia |

---

## Monitor de Peso REST en la UI

El motor expone el peso REST actual:

- **En `GET /api/v1/gateway/snapshot`:** campo `used_weight_1m` y `weight_limit_1m`
- **En la UI Flutter:** barra de peso REST con colores: verde / naranja / rojo
- **Auditoría detallada:** `GET /api/v1/usage/rest-weight/events` y `/report`

**Variable de entorno para ajustar límite de referencia:**
```
PECUNATOR_API_WEIGHT_LIMIT_1M=6000  # default
```

### Fuentes principales de consumo de peso

| Fuente | Frecuencia |
|--------|-----------|
| `fetch_account:get_account` | Cada ciclo de polling |
| `fetch_open_orders:get_open_orders` | Cada ciclo de polling |
| `fetch_my_trades:get_my_trades` | Cada `PECUNATOR_MY_TRADES_POLL_STRIDE` ciclos |
| `refresh_equity:get_all_tickers` | Cada `PECUNATOR_EQUITY_POLL_STRIDE` ciclos |
| `sync_time:get_server_time` | Startup / manual / retry |
| Sandbox queries | A demanda del operador |

---

## Lista de Verificación ante Incidentes

| Código | Acción |
|--------|--------|
| **HTTP 429** | Reducir frecuencia, esperar `Retry-After` si está en cabecera, revisar peso acumulado |
| **HTTP 418** | No reintentar en bucle; esperar el tiempo indicado y corregir estrategia de polling |
| **HTTP 403 WAF** | Revisar volumen y patrones; esperar ventana de bloqueo |
| **WS desconectado** | Implementar backoff exponencial y reconexión; responder ping/pong correctamente |

---

## Snapshots Históricos de Rate Limits

Capturas fechadas del endpoint `exchangeInfo.rateLimits` para análisis histórico:

- **Carpeta:** `docs/binance-limits-snapshots/`
- **Script para actualizar:** `scripts/data/fetch_binance_exchange_info_limits.py`

---

## Cumplimiento y Términos de Uso

- Las [Condiciones de uso de Binance](https://www.binance.com/en/terms) y políticas aplicables al uso de API prevalecen sobre cualquier automatización local
- Pecunator es software de **automatización local**; el operador es responsable del cumplimiento normativo (KYC, jurisdicciones, productos permitidos)
