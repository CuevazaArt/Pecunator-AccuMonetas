# Binance API & WebSocket: Limits and Compliance (Reference)

**Reference** document for PecunatorCore. Limits and policies **change**; Binance is the source of truth.

| Meta | Value |
|------|--------|
| **Last review** | 2026-04-29 |
| **Next suggested review** | After each major engine update or Binance FAQ update |

### Historical snapshots (`exchangeInfo.rateLimits`)

Dated captures of the public Spot endpoint (only `rateLimits` + metadata) for **historical analysis**:

- Folder: [`binance-limits-snapshots/`](binance-limits-snapshots/)
- Script: [`scripts/data/fetch_binance_exchange_info_limits.py`](../scripts/data/fetch_binance_exchange_info_limits.py)

---

## 1. Official sources (keep links updated)

Audit periodically:

| Topic | URL |
|------|-----|
| REST limits (Spot) | https://developers.binance.com/docs/binance-spot-api-docs/rest-api/limits |
| WebSocket API limits | https://developers.binance.com/docs/binance-spot-api-docs/websocket-api/rate-limits |
| WebSocket streams (Spot) | https://github.com/binance/binance-spot-api-docs/blob/master/web-socket-streams.md |
| API FAQ (hard limits, WAF, bans) | https://www.binance.com/en/support/faq/detail/360004492232 |
| API Changelog | https://developers.binance.com/docs/binance-spot-api-docs |

> Regional note: if you use another domain (e.g. `.info`), verify that the policy matches your jurisdiction and product (Spot vs Futures).

---

## 2. Concepts to internalize

### 2.1 Request weight (`REQUEST_WEIGHT`), not "one request = one unit"

- Each REST endpoint has a different **weight**; consumption accumulates per **IP** (typical Spot REST).
- Responses may include headers of the form `X-MBX-USED-WEIGHT-*` and, depending on the endpoint, the body may include `rateLimits` information.
- Exceeding the limit → HTTP **429**. Retrying without backoff can lead to **418** (IP ban with escalating duration).

### 2.2 Orders (`ORDERS`)

- There are **per-account** limits for order creation within time windows (e.g. per 10 seconds and per 24 hours). Exact values appear in documentation and FAQ; **do not hard-code them as eternal constants**.
- Rejected orders may not increment certain counters; consult current documentation.

### 2.3 Web Application Firewall (WAF)

- Suspicious or excessive traffic patterns can produce **403** or other **per-IP** blocks, with typical durations mentioned in FAQ (e.g. on the order of minutes for minor abuse).
- Do not attempt to "evade" limits; reduce frequency and use streams where appropriate.

### 2.4 WebSocket — market streams (Spot)

According to the streams document in the Binance public repository (always check the latest version):

- A single connection is valid for ~**24 h**; plan for reconnection.
- The server sends a periodic **ping**; the client must respond with **pong** correctly or the connection drops.
- Typical limit of incoming control messages (**subscribe/unsubscribe**, ping/pong): on the order of **5 messages per second** per connection; exceeding this may disconnect, and repeating may ban the IP.
- Up to **1024 streams** per connection (per current doc).
- Limit of **new connections per time window per IP** (e.g. **300 attempts / 5 minutes** — see official text).

### 2.5 WebSocket API (API over WS)

- **Weight** and **connection** limits are documented separately from REST; a new connection may have a weight cost > 0 (e.g. historically **2** weight units — see current doc).
- Parameters like `returnRateLimits` affect the size of responses, **not** the fact of being rate-limited.

---

## 3. How this relates to PecunatorCore

| Area | Recommended behavior |
|------|----------------------------|
| **REST polling** | Adjust `PECUNATOR_ACCOUNT_POLL_SEC` in `runtime/core/settings.py` if you see 429 or excessive latency. |
| **Credentials** | Use the encrypted **vault** (`runtime/data/`) or environment variables; do not embed keys in Flutter or in repos. |
| **Engine startup** | Run `scripts/engine/run_engine.ps1` or `python main.py`; credentials are resolved by environment or local encrypted vault. |
| **Orders / bots** | Respect symbol filters (`PRICE_FILTER`, `LOT_SIZE`, minimum notional); precision errors are the strategy's responsibility, not Binance "relaxing" rules. |

---

## 4. Incident checklist

1. HTTP **429**? → Reduce frequency, wait for `Retry-After` if present in header, check accumulated weight.
2. HTTP **418**? → Do not retry in a loop; wait the indicated time and correct the polling strategy.
3. **403** WAF? → Review volume and patterns; wait for the block window.
4. WS disconnected? → Implement exponential backoff and reconnection; correct ping/pong response.

---

## 5. Compliance and terms of use

- The [Terms of Use](https://www.binance.com/en/terms) and policies applicable to **API usage** take precedence over any local automation.
- This project is **local automation** software; the operator is responsible for regulatory compliance (KYC, jurisdictions, permitted products).

---

## 6. Change history for this document

| Date | Change |
|-------|--------|
| 2026-04-29 | Creation: official links, REST/WS/WAF concepts, relation to PecunatorCore. |
| 2026-04-29 | `exchangeInfo.rateLimits` snapshots in `docs/binance-limits-snapshots/`; engine/UI REST weight. |

*To update: edit the §6 table and the "Last review" date above.*
