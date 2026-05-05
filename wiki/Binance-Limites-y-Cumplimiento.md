#Binance—Limits and Compliance

> Operational reference for PecunatorCore on Binance REST and WebSocket rate limits.  
> The limits **change**; Binance is the source of truth.  
> Last revision: 2026-04-29

---

##OfficialSources

| Theme | URL |
|------|-----|
| REST Limits (Spot) | https://developers.binance.com/docs/binance-spot-api-docs/rest-api/limits |
| WebSocket API Limits | https://developers.binance.com/docs/binance-spot-api-docs/websocket-api/rate-limits |
| Streams WebSocket (Spot) | https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md |
| FAQ API (hard limits, WAF, bans) | https://www.binance.com/en/support/faq/detail/360004492232 |
| Changelog API | https://developers.binance.com/docs/binance-spot-api-docs |

> Regional note: if you use another domain (e.g. `.info`), verify that the policy matches your jurisdiction and product.

---

## Key Concepts

### Request weight (`REQUEST_WEIGHT`)

Each REST endpoint has a **different weight** — it's not "one request = one unit".

- Consumption is accumulated **per IP** in typical REST Spot
- Responses include `X-MBX-USED-WEIGHT-*` headers
- **HTTP 429** = limit exceeded
- **HTTP 418** = IP ban for insisting without backoff (scalable duration)

> ⚠️ Don't set limits as constants in code — the exact values ​​​​change.

### Orders (`ORDERS`)

- Limits **per account** for order creation (per time windows)
- Rejected orders may not increment certain counters (see current documentation)

### Web Application Firewall (WAF)

- Suspicious traffic patterns produces **403** with typical block duration of minutes (mild abuse)
- **Don't** try to evade limits — reduce frequency and use streams

### WebSocket—Market Streams

| Parameters | Typical value (check current doc) |
|-----------|------------------------|
| Maximum connection duration | ~24 hours (expect reconnection) |
| Control messages (subscribe/unsubscribe) | ~5 per second per connection |
| Streams per connection | Up to 1024 |
| New connection attempts | ~300 for 5 minutes per IP |

The server sends periodic **ping**; the client must respond **pong** or the connection drops.

### WebSocket API (API over WS)

- Weight limits and connections documented separately from REST
- A new connection can have weight cost > 0

---

## How it is related to PecunatorCore

| Area | Recommended behavior |
|------|--------------------------|
| **REST Polling** | Adjust `PECUNATOR_ACCOUNT_POLL_SEC` in `runtime/core/settings.py` if 429 or excessive latency appears |
| **Credentials** | Use the encrypted vault (`runtime/data/`) or environment variables; do not embed keys in Flutter or repos |
| **Engine start** | Run `scripts/engine/run_engine.ps1` or `python main.py`; credentials are resolved by environment or chest |
| **Orders / bots** | Respect symbol filters (`PRICE_FILTER`, `LOT_SIZE`, minimum notional); precision errors are the responsibility of the strategy |

---

## REST Weight Monitor in UI

The engine exposes the current REST weight:

- **In `GET /api/v1/gateway/snapshot`:** field `used_weight_1m` and `weight_limit_1m`
- **In Flutter UI:** REST weight bar with colors: green/orange/red
- **Detailed audit:** `GET /api/v1/usage/rest-weight/events` and `/report`

**Environment variable to adjust reference limit:**
```
PECUNATOR_API_WEIGHT_LIMIT_1M=6000 # default
```

### Main sources of weight consumption

| Source | Frequency |
|--------|-----------|
| `fetch_account:get_account` | Each polling cycle |
| `fetch_open_orders:get_open_orders` | Each polling cycle |
| `fetch_my_trades:get_my_trades` | Every `PECUNATOR_MY_TRADES_POLL_STRIDE` cycles |
| `refresh_equity:get_all_tickers` | Every `PECUNATOR_EQUITY_POLL_STRIDE` cycles |
| `sync_time:get_server_time` | Startup / manual / retry |
| Sandbox queries | At the operator's request |

---

## Incident Checklist

| Code | Action |
|--------|--------|
| **HTTP 429** | Reduce frequency, wait for `Retry-After` if it is in header, check accumulated weight |
| **HTTP 418** | Do not retry in loop; wait the indicated time and correct polling strategy |
| **HTTP 403 WAF** | Review volume and patterns; wait lock window |
| **WS offline** | Implement exponential backoff and reconnection; answer ping/pong correctly |

---

## Historical Snapshots of Rate Limits

Dated snapshots of the `exchangeInfo.rateLimits` endpoint for historical analysis:

- **Folder:** `docs/binance-limits-snapshots/`
- **Script to update:** `scripts/data/fetch_binance_exchange_info_limits.py`

---

## Compliance and Terms of Use

- The [Binance Terms of Use](https://www.binance.com/en/terms) and policies applicable to API use take precedence over any local automation
- Pecunator is **local automation** software; the operator is responsible for regulatory compliance (KYC, jurisdictions, permitted products)