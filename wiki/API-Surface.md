# API Surface—Pecunator

> Complete Python Engine REST Endpoints Reference.  
> Base URL: `http://127.0.0.1:8765`  
> Interactive OpenAPI: `http://127.0.0.1:8765/docs`

---

## Vault and Credentials

Binance credentials encrypted vault management.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/vault/status` | Vault status (open/closed, number of credentials) |
| `GET` | `/api/v1/vault/credentials` | List of stored credentials (without exposing secrets) |
| `POST` | `/api/v1/vault/credentials` | Add new credential (API key + secret) |
| `PATCH` | `/api/v1/vault/credentials/{credential_id}` | Update existing credential |
| `DELETE` | `/api/v1/vault/credentials/{credential_id}` | Delete credential |
| `GET` | `/api/v1/credentials/active` | Currently active credential |

---

## Binance Gateway

Control of the connector with Binance and account status.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/gateway/start` | Start the gateway (connect to Binance) |
| `POST` | `/api/v1/gateway/stop` | Stop the gateway |
| `GET` | `/api/v1/gateway/snapshot` | Snapshot of the current state: balances, equity, weight REST |
| `POST` | `/api/v1/gateway/fetch_account` | Force account data update |
| `GET` | `/api/v1/account/wallets` | Account wallets with calculated equity (`?base_asset=USDT`) |
| `POST` | `/api/v1/time/sync` | Synchronize timestamp with Binance server |

### Example response — `GET /api/v1/gateway/snapshot`

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

## Operational Protocols

Security operations and controlled closing of positions.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/ops/protocol/status` | Status of the last executed protocol |
| `POST` | `/api/v1/ops/protocol/close` | Closing Protocol: Stop Bots + Close USDT Positions |
| `POST` | `/api/v1/ops/red_button` | **Red button:** stops **all** bots immediately |
| `POST` | `/api/v1/ops/orders/cleanup/limit` | Cancel all open LIMIT orders |
| `POST` | `/api/v1/ops/orders/cleanup/stop` | Cancel all open STOP orders |
| `POST` | `/api/v1/ops/orders/cleanup/all` | Cancel all open orders |

> ⚠️ The `close` and `red_button` protocols stop Dorothy **before** executing to avoid layout/conversion loops.

**Common parameters:** `?base_asset=USDT`

---

## Dorothy Hub (Multi-instance)

Lifecycle management of Dorothy bot instances.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/hub/bots` | List all bot instances |
| `POST` | `/api/v1/hub/bots` | Create new bot instance |
| `PATCH` | `/api/v1/hub/bots/{bot_id}` | Update configuration of an instance |
| `DELETE` | `/api/v1/hub/bots/{bot_id}` | Delete instance |
| `POST` | `/api/v1/hub/bots/{bot_id}/start` | Start instance |
| `POST` | `/api/v1/hub/bots/{bot_id}/stop` | Stop instance |
| `POST` | `/api/v1/hub/bots/{bot_id}/run_once` | Run a single loop |
| `GET` | `/api/v1/hub/bots/{bot_id}/logs` | Get instance logs |

**Legacy endpoints** (compatibility): `/api/v1/bot/*`

---

## Masha Hub (Multi-instance)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/masha/bots` | List Masha instances |
| `POST` | `/api/v1/masha/bots` | Create Masha instance |
| `PATCH` | `/api/v1/masha/bots/{bot_id}` | Update instance configuration |
| `DELETE` | `/api/v1/masha/bots/{bot_id}` | Delete instance |
| `POST` | `/api/v1/masha/bots/{bot_id}/start` | Start instance |
| `POST` | `/api/v1/masha/bots/{bot_id}/stop` | Stop instance |
| `POST` | `/api/v1/masha/bots/{bot_id}/run_once` | Single cycle |
| `GET` | `/api/v1/masha/bots/{bot_id}/logs` | Instance logs |

---

## Thusnelda Hub (Multi-instance)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/thusnelda/bots` | List Thusnelda instances |
| `POST` | `/api/v1/thusnelda/bots` | Create Thusnelda instance |
| `POST` | `/api/v1/thusnelda/bots/{bot_id}/start` | Start instance |
| `POST` | `/api/v1/thusnelda/bots/{bot_id}/stop` | Stop instance |
| `POST` | `/api/v1/thusnelda/bots/{bot_id}/run_once` | Single cycle |
| `GET` | `/api/v1/thusnelda/bots/{bot_id}/logs` | Instance logs |

---

## REST sandbox

Queries guided to the Binance API for exploration and diagnosis.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/sandbox/rest/catalog` | Catalog of available queries |
| `POST` | `/api/v1/sandbox/rest/query` | Run a guided query |

**Available queries:** `get_exchange_info`, `get_account`, `get_open_orders`, `get_my_trades`

### Curated sandbox records

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/sandbox/curated/save` | Save curated sandbox result |
| `GET` | `/api/v1/sandbox/curated/list` | List curated sandbox records |

---

## Earn monitoring

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/earn/history/{symbol}` | Retrieve persisted Earn rate history by symbol |
| `POST` | `/api/v1/earn/sync` | Force Earn sync from Binance |

---

## System and governance observability

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Lightweight overall health/status |
| `GET` | `/health/deep` | Deep health with gateway/hubs details |
| `GET` | `/api/v1/weight-governor/status` | WeightGovernor status and zone |
| `GET` | `/api/v1/market-cache/status` | Market cache status |
| `GET` | `/api/v1/bot-coordinator/status` | Bot coordinator status |

---

## REST Weight Monitor

REST weight consumption audit per endpoint/action.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/usage/rest-weight/samples` | Historical usage samples |
| `GET` | `/api/v1/usage/rest-weight/events` | Weight events per endpoint |
| `GET` | `/api/v1/usage/rest-weight/report` | Consumption report (`top_actions`, historical) |

---

## Response codes

| Code | Meaning |
|--------|-------------|
| `200` | Success |
| `400` | Invalid parameters |
| `401` | Do not activate credentials |
| `404` | Resource not found |
| `429` | Binance rate limit reached |
| `500` | Internal engine error |

---

## Usage Notes

- All operations require active credentials in the vault
- The timestamp is automatically synchronized at startup; also via `POST /api/v1/time/sync`
- The default `base_asset` field is `USDT` on all endpoints that require it
- REST weight is included in the gateway snapshot for real-time monitoring