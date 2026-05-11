# Task: Subaccount Operations

## Objective
Programmatically manage Binance subaccounts from the Master account,
including creation, permission configuration, fund transfers,
and consolidated reports.

## ⛔ Caution
All operations involving fund movement or account creation
require explicit user confirmation before executing.

## Context
- **Gateway:** `runtime/connectors/binance_gateway.py`
- **Base URL:** `https://api.binance.com`
- **Authentication:** HMAC SHA256 signing (implemented in gateway)

## Variant A — Create New Subaccount for Bot

### Steps
1. Call `POST /sapi/v1/sub-account/virtualSubAccount`
   - Automatically generates a virtual email
   - Requires "Enable Spot & Margin Trading" permission on Master API key

2. Enable capabilities per bot:
   - Dorothy (Spot): Spot only enabled by default
   - Masha (Futures): `POST /sapi/v1/sub-account/futures/enable`
   - Thusnelda (Mixed): Futures + Margin enable

3. Create API Key for the subaccount:
   - Minimum required permissions (principle of least privilege)
   - **NEVER** enable withdraw on a bot subaccount

4. Apply IP restriction:
   - `POST /sapi/v1/sub-account/subAccountApi/ipRestriction`
   - Whitelist only the server IP where the bot runs

5. Register credentials in `runtime/core/config_manager.py`:
   - Save subaccount email
   - Save API key (encrypted)
   - Associate with the corresponding bot

6. Verify connectivity:
   - `GET /sapi/v1/sub-account/list` → confirm subaccount exists
   - Balance query → confirm API key works

### Output
- Created subaccount email
- Generated API key (show only last 4 chars)
- Permissions configured
- IP restriction applied
- Connectivity test: ✅/🔴

---

## Variant B — Capital Redistribution

### Steps
1. Query balance of all subaccounts:
   - `GET /sapi/v1/sub-account/spot/summary` → Spot totals
   - For each subaccount: `GET /sapi/v1/sub-account/assets` (V4)

2. Query recent performance of each bot:
   - PnL last 24h / 7d if available
   - Capital utilization ratio (how much of the assigned balance is used)

3. Calculate optimal distribution:
   ```
   Para cada bot:
     score = (PnL_7d / capital_asignado) * utilizacion
     capital_nuevo = total_disponible * (score / sum_scores)
   ```
   Con floor mínimo por bot y cap máximo de concentración.

4. Generate transfer plan:
   | Desde | Hacia | Monto | Token | Motivo |
   |-------|-------|-------|-------|--------|
   | Master | Sub-Masha | 500 USDT | USDT | Rendimiento alto |
   | Sub-Dorothy | Master | 200 USDT | USDT | Rendimiento bajo |

5. **WAIT for user confirmation**

6. Execute Universal Transfers:
   - `POST /sapi/v1/sub-account/universalTransfer`
   - Type: `MAIN_TO_SUB` / `SUB_TO_MAIN` / `SUB_TO_SUB`

7. Verify post-transfer balances

### Output
- Pre/post transfer balance table
- Transfers executed with txnIds
- Balance verification correct

---

## Variant C — Consolidated Report

### Steps
1. List all subaccounts:
   - `GET /sapi/v1/sub-account/list`

2. For each subaccount, aggregate:
   - Total balance in USD equivalent
   - PnL (if historical data exists)
   - Open positions (Futures)
   - Active loans (Margin)

3. Calculate consolidated metrics:
   | Métrica | Valor |
   |---------|-------|
   | AUM Total (Master + Subs) | $XXX |
   | Mejor bot (7d) | [nombre] +X% |
   | Peor bot (7d) | [nombre] -X% |
   | Capital idle total | $XXX (X%) |
   | Exposición apalancada total | $XXX |

4. Generate comparative report across bots

### Output
Artifact `subaccount_report_YYYY-MM-DD.md` with consolidated tables

## Success Criteria
- [ ] Operation completed without API errors
- [ ] User confirmation obtained before moving funds
- [ ] Balances verified post-operation
- [ ] Entry recorded in audit log
