# Binance Spot API — `rateLimits` snapshots (historical analysis)

Each JSON file is a **point-in-time capture** of the public endpoint:

`GET https://api.binance.com/api/v3/exchangeInfo`

Only fields useful for limits are saved: `serverTime`, `timezone`, `rateLimits`.

## How to generate a new snapshot

From the repo root (with network access):

```powershell
.\.venv\Scripts\python.exe scripts\fetch_binance_exchange_info_limits.py
```

Or manually with `curl`/browser and paste `rateLimits` into a new file named:

`exchangeInfo-rateLimits-YYYY-MM-DD.json`

## Interpretation

- `rateLimits` describes **windows** (`interval`, `intervalNum`) and **types** (`REQUEST_WEIGHT`, `RAW_REQUESTS`, `ORDERS`, etc.) as returned on that date.
- Values **change**; this directory is for **comparing over time**, not as fixed constants in code.
