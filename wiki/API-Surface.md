# API Surface — Pecunator

> Referencia completa de endpoints REST del motor Python.  
> Base URL: `http://127.0.0.1:8765`  
> OpenAPI interactivo: `http://127.0.0.1:8765/docs`

---

## Vault y Credenciales

Gestión del vault cifrado de credenciales Binance.

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/v1/vault/status` | Estado del vault (abierto/cerrado, número de credenciales) |
| `GET` | `/api/v1/vault/credentials` | Lista de credenciales almacenadas (sin exponer secrets) |
| `POST` | `/api/v1/vault/credentials` | Añadir nueva credencial (API key + secret) |
| `PATCH` | `/api/v1/vault/credentials/{credential_id}` | Actualizar credencial existente |
| `DELETE` | `/api/v1/vault/credentials/{credential_id}` | Eliminar credencial |
| `GET` | `/api/v1/credentials/active` | Credencial activa actualmente |

---

## Gateway Binance

Control del conector con Binance y estado de cuenta.

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `POST` | `/api/v1/gateway/start` | Iniciar el gateway (conectar con Binance) |
| `POST` | `/api/v1/gateway/stop` | Detener el gateway |
| `GET` | `/api/v1/gateway/snapshot` | Snapshot del estado actual: balances, equity, peso REST |
| `POST` | `/api/v1/gateway/fetch_account` | Forzar actualización de datos de cuenta |
| `GET` | `/api/v1/account/wallets` | Wallets de la cuenta con equity calculado (`?base_asset=USDT`) |
| `POST` | `/api/v1/time/sync` | Sincronizar timestamp con servidor Binance |

### Respuesta ejemplo — `GET /api/v1/gateway/snapshot`

```json
{
  "connected": true,
  "equity": {
    "current": 1234.56,
    "avg": 1230.00,
    "high_avg": 1240.00
  },
  "used_weight_1m": 120,
  "weight_limit_1m": 6000,
  "account": { ... }
}
```

---

## Protocolos Operativos

Operaciones de seguridad y cierre controlado de posiciones.

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/v1/ops/protocol/status` | Estado del último protocolo ejecutado |
| `POST` | `/api/v1/ops/protocol/close` | Protocolo de cierre: detiene bots + cierra posiciones USDT |
| `POST` | `/api/v1/ops/red_button` | **Botón rojo:** detiene **todos** los bots inmediatamente |
| `POST` | `/api/v1/ops/orders/cleanup/limit` | Cancela todas las órdenes LIMIT abiertas |
| `POST` | `/api/v1/ops/orders/cleanup/stop` | Cancela todas las órdenes STOP abiertas |
| `POST` | `/api/v1/ops/orders/cleanup/all` | Cancela todas las órdenes abiertas |

> ⚠️ Los protocolos `close` y `red_button` detienen Dorothy **antes** de ejecutar para evitar loops de disposición/conversión.

**Parámetros comunes:** `?base_asset=USDT`

---

## Hub Dorothy (Multi-instancia)

Gestión del ciclo de vida de instancias del bot Dorothy.

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/v1/hub/bots` | Lista todas las instancias de bots |
| `POST` | `/api/v1/hub/bots` | Crear nueva instancia de bot |
| `PATCH` | `/api/v1/hub/bots/{bot_id}` | Actualizar configuración de una instancia |
| `DELETE` | `/api/v1/hub/bots/{bot_id}` | Eliminar instancia |
| `POST` | `/api/v1/hub/bots/{bot_id}/start` | Arrancar instancia |
| `POST` | `/api/v1/hub/bots/{bot_id}/stop` | Detener instancia |
| `POST` | `/api/v1/hub/bots/{bot_id}/run_once` | Ejecutar un ciclo único |
| `GET` | `/api/v1/hub/bots/{bot_id}/logs` | Obtener logs de la instancia |

**Endpoints legacy** (compatibilidad): `/api/v1/bot/*`

---

## Hub Thusnelda (Multi-instancia)

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/v1/thusnelda/bots` | Lista instancias Thusnelda |
| `POST` | `/api/v1/thusnelda/bots` | Crear instancia Thusnelda |
| `POST` | `/api/v1/thusnelda/bots/{bot_id}/start` | Arrancar instancia |
| `POST` | `/api/v1/thusnelda/bots/{bot_id}/stop` | Detener instancia |
| `POST` | `/api/v1/thusnelda/bots/{bot_id}/run_once` | Ciclo único |
| `GET` | `/api/v1/thusnelda/bots/{bot_id}/logs` | Logs de la instancia |

---

## Sandbox REST

Queries guiadas a la API de Binance para exploración y diagnóstico.

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/v1/sandbox/rest/catalog` | Catálogo de queries disponibles |
| `POST` | `/api/v1/sandbox/rest/query` | Ejecutar una query guiada |

**Queries disponibles:** `get_exchange_info`, `get_account`, `get_open_orders`, `get_my_trades`

---

## Monitor de Peso REST

Auditoría de consumo de peso REST por endpoint/acción.

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| `GET` | `/api/v1/usage/rest-weight/events` | Eventos de peso por endpoint |
| `GET` | `/api/v1/usage/rest-weight/report` | Reporte de consumo (`top_actions`, histórico) |

---

## Códigos de respuesta

| Código | Significado |
|--------|-------------|
| `200` | Éxito |
| `400` | Parámetros inválidos |
| `401` | Sin credenciales activas |
| `404` | Recurso no encontrado |
| `429` | Rate limit de Binance alcanzado |
| `500` | Error interno del motor |

---

## Notas de uso

- Todas las operaciones requieren credenciales activas en el vault
- El timestamp se sincroniza automáticamente en arranque; también vía `POST /api/v1/time/sync`
- El campo `base_asset` por defecto es `USDT` en todos los endpoints que lo requieran
- El peso REST se incluye en el snapshot del gateway para monitoreo en tiempo real
