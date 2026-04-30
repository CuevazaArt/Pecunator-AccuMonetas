# REST Weight Audit (Binance)

Updated: 2026-04-29

## What the monitor measures

- Source: Binance response header `X-MBX-USED-WEIGHT-1M`.
- Scope: rolling 1-minute window, **IP-shared** (not per bot).
- Impact: weight can increase from this engine plus any other process using the same outbound IP.

## Quantization model

- Occupancy shown in UI = `used_weight_1m / weight_limit_1m`.
- Default display limit = `PECUNATOR_API_WEIGHT_LIMIT_1M` (default `6000`).
- Gateway cycle frequency = `60 / PECUNATOR_ACCOUNT_POLL_SEC`.

## Main request sources

- Gateway polling:
  - `fetch_account:get_account` (every cycle)
  - `fetch_open_orders:get_open_orders` (every cycle)
  - `fetch_my_trades:get_my_trades:*` (every `PECUNATOR_MY_TRADES_POLL_STRIDE`)
  - `refresh_equity:get_all_tickers` (every `PECUNATOR_EQUITY_POLL_STRIDE`)
  - `sync_time:get_server_time` (startup/manual/retry)
- Operational protocols (`ops`):
  - close protocol, red button, cleanup (open orders, cancels, account snapshots, market sells)
- Wallet/account views (`wallets`):
  - account, funding/futures wallet reads, equity tickers
- Sandbox (`sandbox`):
  - user-triggered `client.get_*` calls

## Current mitigation applied

- Removed redundant periodic `ping` from gateway polling loop to avoid extra weight consumption.
- Added endpoint-level weight event auditing with per-call deltas:
  - `GET /api/v1/usage/rest-weight/events`
  - `GET /api/v1/usage/rest-weight/report`
- Added action summary (`top_actions`) to identify dominant contributors.

## Operator controls

- Increase `PECUNATOR_ACCOUNT_POLL_SEC` to reduce baseline calls/minute.
- Increase `PECUNATOR_MY_TRADES_POLL_STRIDE` and `PECUNATOR_EQUITY_POLL_STRIDE` to lower heavy call frequency.
- Avoid concurrent Sandbox stress queries while bots are active.
