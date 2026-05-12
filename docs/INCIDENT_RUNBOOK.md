# Incident Runbook — Pecunator-AccuMonetas Louise Hub

This runbook covers the most likely failure scenarios during live production operation. For each scenario: what it means, how to confirm it, and the exact recovery steps.

**Emergency contact:** If unsure, stop all bots immediately using the Louise Hub UI "Stop All" button.

---

## Table of Contents

1. [ApiFuse Circuit Breaker Tripped](#1-apifuse-circuit-breaker-tripped)
2. [Orphan Orders Detected](#2-orphan-orders-detected)
3. [WebSocket Gateway Disconnected](#3-websocket-gateway-disconnected)
4. [Stop-Loss Triggered](#4-stop-loss-triggered)
5. [Database Corruption or Locked](#5-database-corruption-or-locked)
6. [Daily Budget Exhausted](#6-daily-budget-exhausted)
7. [High API Weight (WeightGovernor RED Zone)](#7-high-api-weight-weightgovernor-red-zone)
8. [Telegram Alert Spam](#8-telegram-alert-spam)
9. [Suspicious Activity (Duplicate/Frozen Orders)](#9-suspicious-activity-duplicatefrozen-orders)
10. [Emergency Shutdown Procedure](#10-emergency-shutdown-procedure)

---

## 1. ApiFuse Circuit Breaker Tripped

**What it means:** The system hit repeated errors calling Binance API (429 rate limit, 5xx server errors, or network timeouts). The fuse tripped to prevent further damage.

**Symptoms:**
- Telegram alert: `FUSE_TRIPPED`
- UI shows "API circuit open" warning
- All bot buy/sell operations are blocked

**Confirm:**
```
GET http://127.0.0.1:8000/api-fuse/status
```
Response: `{"state": "OPEN", "trip_count": N, "reason": "..."}`

**Recovery steps:**
1. Check Binance status at [binance.com/en/support/announcement](https://binance.com/en/support/announcement) — is there a known outage?
2. If Binance is down: wait for recovery, fuse will auto-reset after backoff window
3. If Binance is up: check API key status in Binance account portal (is it restricted?)
4. If key is fine: manually reset the fuse:
   ```
   POST http://127.0.0.1:8000/api-fuse/reset
   Authorization: Bearer <token>
   ```
5. Monitor for 15 minutes — if fuse trips again immediately, escalate to key investigation
6. If recurring: check `backend.log` for the specific error (429 = exceeded weight limit, 403 = key suspended)

**Prevention:** WeightGovernor prevents most rate-limit hits. If recurring, reduce `PECUNATOR_API_WEIGHT_LIMIT_1M` setting.

---

## 2. Orphan Orders Detected

**What it means:** Orders exist on Binance that the engine does not have records of in the database. This can happen after a crash, missed shutdown, or manual orders placed outside the bot.

**Symptoms:**
- Telegram alert: `ORPHAN_DETECTED`
- Account balance shows unexpected locked funds
- `GET /api/louise/orphans/scan?symbol=BTCUSDT` returns non-empty list

**Confirm:**
```
GET http://127.0.0.1:8000/api/louise/orphans/scan?symbol=BTCUSDT
Authorization: Bearer <token>
```

**Recovery options:**

**Option A — Adopt (recommended if order was placed by a known bot):**
```
POST http://127.0.0.1:8000/api/louise/orphans/adopt
Authorization: Bearer <token>
Content-Type: application/json

{"order_id": "<id>", "bot_id": "louise-dca-btc", "epoch_id": "epoch_..."}
```
→ Inserts the order into the DB, recalculates epoch stats.

**Option B — Cancel (if order is open and should not exist):**
```
POST http://127.0.0.1:8000/api/louise/orphans/cancel
Authorization: Bearer <token>
Content-Type: application/json

{"order_id": "<id>", "symbol": "BTCUSDT"}
```
→ Cancels the open order on Binance and marks it ignored.

**Option C — Ignore (if order is filled and you accept the position):**
Manually verify the position in Binance, then adopt with the appropriate bot/epoch.

**After recovery:** Re-scan to confirm no orphans remain. Restart affected bot to recalculate epoch state.

---

## 3. WebSocket Gateway Disconnected

**What it means:** The persistent WebSocket connection to Binance was dropped. The system switches to REST polling automatically, but this is slower and uses more API weight.

**Symptoms:**
- Telegram alert: `GATEWAY_DISCONNECTED`
- UI shows "WS: Disconnected" status indicator
- API weight usage increases (more REST calls to compensate)

**Confirm:**
```
GET http://127.0.0.1:8000/api/v1/gateway/status
Authorization: Bearer <token>
```
Response: `{"connected": false, "last_connected": "..."}`

**Recovery steps:**
1. If disconnected < 5 minutes: auto-recovery is likely in progress. Monitor for reconnection.
2. If disconnected > 5 minutes: trigger manual reconnect from UI "Reconnect Gateway" button
3. If reconnect fails: check network connectivity to Binance WebSocket (`wss://stream.binance.com`)
4. If network fine: restart the engine process (graceful shutdown first — see section 10)
5. After restart: verify gateway reconnects and WS status shows "Connected"

**Impact while disconnected:** Bots continue operating via REST polling. Buy/sell decisions may be delayed by up to 1 poll interval (default: 60 seconds). No capital risk.

---

## 4. Stop-Loss Triggered

**What it means:** A bot's position dropped below the stop-loss threshold. The bot sold the position at a loss to prevent further decline.

**Symptoms:**
- Telegram alert: `STOP_LOSS_TRIGGERED` with bot_id, symbol, loss_usdt
- Bot epoch shows status `CLOSED_STOP_LOSS`
- Account balance reduced by loss amount

**Confirm:**
1. Check epoch in DB: status should be `CLOSED_STOP_LOSS`
2. Verify the sell order filled on Binance in Trade History
3. Check `locked_usdt` — should have been released after sell

**Recovery steps:**
1. Verify the sell order actually filled (not just submitted). Check Binance trade history.
2. If order filled: accept the loss, no action needed. Bot will create a new epoch automatically.
3. If order stuck (status = NEW for > 5 minutes): check if market is operating normally
4. If order rejected: manually sell from Binance UI, then scan for orphans (section 2)
5. Optionally: review the stop-loss threshold in bot config if it triggered prematurely

**Review questions after stop-loss:**
- Was the loss within expected range for the stop-loss percentage configured?
- Is the market in a downtrend that suggests pausing the bot?
- Is the bot's `target_profit_pct` or `buy_volume` appropriate for current volatility?

---

## 5. Database Corruption or Locked

**What it means:** The SQLite database file is corrupt, locked by another process, or inaccessible.

**Symptoms:**
- Engine fails to start with `sqlite3.DatabaseError` or `OperationalError: database is locked`
- `backend.log` shows `database disk image is malformed`
- API returns 500 errors on all Louise endpoints

**Confirm:**
```bash
sqlite3 runtime/data/louise_hub.sqlite "PRAGMA integrity_check;"
```
→ Should return `ok`. Any other output = corruption.

**Recovery steps:**

**Scenario A — Database is locked (not corrupt):**
1. Check for other processes using the file: `lsof runtime/data/louise_hub.sqlite` (Linux) or Task Manager (Windows)
2. If another engine instance is running: stop it first (section 10)
3. If lock persists after engine stop: delete the `-wal` and `-shm` files alongside the `.sqlite` file (these are WAL mode artifacts — safe to delete if engine is stopped)
4. Restart engine

**Scenario B — Database is corrupt:**
1. Stop the engine immediately (section 10)
2. Check if backup exists: `runtime/data/backups/louise_hub_YYYYMMDD.sqlite`
3. Restore from backup:
   ```powershell
   Copy-Item "runtime/data/backups/louise_hub_20260512.sqlite" "runtime/data/louise_hub.sqlite"
   ```
4. Restart engine
5. Scan for orphans immediately after restart (orders placed since backup may be orphaned)

**If no backup exists:**
1. Export whatever data is recoverable: `sqlite3 runtime/data/louise_hub.sqlite ".dump" > recovery.sql`
2. Create fresh DB by deleting the corrupt file and restarting engine
3. Manually reconcile open positions via orphan scanner

**Prevention:** Enable daily automated backups (see `scripts/backup/backup_databases.ps1`).

---

## 6. Daily Budget Exhausted

**What it means:** The BudgetGuard module has blocked further buys because the configured daily USDT spend ceiling has been reached.

**Symptoms:**
- Telegram alert: `BUDGET_EXHAUSTED` or bot logs "BudgetGuard blocked buy"
- Bots continue running but skip all buy decisions
- Sell decisions are NOT affected — bots will still take profits

**Confirm:**
```
GET http://127.0.0.1:8000/api/v1/budget-guard/status
Authorization: Bearer <token>
```
Response: `{"daily_spent": N, "daily_limit": N, "blocked": true}`

**Recovery options:**

**Option A — Wait for reset (recommended):** Budget resets at UTC midnight. Bots auto-resume buys.

**Option B — Increase budget temporarily:**
```
POST http://127.0.0.1:8000/api/v1/budget-guard/update
Authorization: Bearer <token>
Content-Type: application/json

{"daily_budget_usdt": 1500}
```
⚠️ Only do this if you consciously accept higher daily exposure.

**Option C — Pause bots until reset:** Stop all bots from UI, restart after midnight UTC.

---

## 7. High API Weight (WeightGovernor RED Zone)

**What it means:** The engine is close to hitting Binance's 1-minute REST API weight limit (6000 by default). WeightGovernor has throttled non-critical requests.

**Symptoms:**
- Telegram alert: `WEIGHT_ZONE_RED`
- UI shows "Weight: RED" status
- Some bot polls may be deferred/skipped temporarily

**Confirm:**
```
GET http://127.0.0.1:8000/api/v1/governor/status
Authorization: Bearer <token>
```
Response: `{"zone": "RED", "weight_used": N, "weight_limit": 6000, "pct_used": 0.85}`

**Recovery steps:**
1. If zone = YELLOW (warning): no action needed, system self-throttles
2. If zone = RED: the system will pause low-priority polls automatically. Monitor for 2 minutes.
3. If you see 429 errors from Binance: the fuse may trip (section 1)
4. To permanently reduce weight pressure: increase `poll_interval_seconds` per bot (60 → 120)
5. If running many bots: stagger their start times so polls don't cluster at same second

**Understanding weight zones:**
- GREEN (< 40%): normal operation
- YELLOW (40-80%): throttling active, non-critical requests deferred
- RED (> 80%): emergency mode, only critical operations allowed

---

## 8. Telegram Alert Spam

**What it means:** The alert dispatcher is sending repeated notifications for the same condition (e.g., WeightGovernor fluctuating in/out of YELLOW repeatedly).

**Symptoms:** Telegram bot sending > 10 messages in 5 minutes for the same alert type.

**Note:** The deduplication window is 300 seconds — same alert within this window is suppressed. If you're seeing spam, the alert condition is oscillating faster than the window.

**Recovery steps:**
1. Identify the spammy alert type from Telegram message prefix (e.g., `WEIGHT_ZONE_YELLOW`)
2. Check root cause — why is this condition oscillating?
3. For WeightGovernor: increase `poll_interval_seconds` to reduce weight oscillation
4. For gateway disconnects: investigate and fix the network issue causing reconnect cycles
5. If alert is noise: temporarily disable via env var:
   ```bash
   PECUNATOR_ALERT_TELEGRAM_DISABLED=1 python main.py
   ```
   ⚠️ Disabling alerts means you won't receive critical notifications. Use only short-term.

---

## 9. Suspicious Activity (Duplicate/Frozen Orders)

**What it means:** Orders appear duplicated in the DB, a bot appears frozen (no activity for > 30 minutes during market hours), or position values are inconsistent with market price.

**Symptoms:**
- Same order_id appearing multiple times in `louise_purchases`
- Bot epoch hasn't updated in > 30 minutes but market is active
- Account balance doesn't match what the DB shows

**Investigation steps:**
1. Check for duplicate purchases:
   ```bash
   sqlite3 runtime/data/louise_hub.sqlite "SELECT order_id, COUNT(*) FROM louise_purchases GROUP BY order_id HAVING COUNT(*) > 1;"
   ```
2. Check bot status:
   ```
   GET http://127.0.0.1:8000/api/louise/bots/<bot_id>/status
   ```
3. Check for stuck epoch (no purchases for > 30m on a RUNNING epoch):
   ```bash
   sqlite3 runtime/data/louise_hub.sqlite "SELECT epoch_id, bot_id, status, datetime(created_at, 'unixepoch') FROM louise_epochs WHERE status = 'RUNNING';"
   ```

**Recovery for frozen bot:**
1. From UI: stop the bot, wait 10 seconds, restart it
2. If bot won't stop: restart the engine (section 10)
3. After restart: scan for orphans to catch any orders placed by frozen bot

**Recovery for duplicates:**
1. Stop all bots
2. Identify and delete duplicate records (keep the first occurrence by created_at):
   ```bash
   sqlite3 runtime/data/louise_hub.sqlite "DELETE FROM louise_purchases WHERE rowid NOT IN (SELECT MIN(rowid) FROM louise_purchases GROUP BY order_id);"
   ```
3. Recalculate epoch stats for affected epochs
4. Restart bots

---

## 10. Emergency Shutdown Procedure

**Use this when:** Something is wrong and you need to stop everything cleanly NOW.

**Step 1 — Stop all bots from UI**
Open Louise Hub → click "Stop All Bots" → wait for all bot status indicators to show "IDLE"

**Step 2 — Stop new orders (gateway disconnect)**
Open Louise Hub → click "Disconnect Gateway" → confirm disconnection in status bar

**Step 3 — Verify open orders**
On Binance account portal, check Subaccount → Open Orders for any unfilled buy/sell orders.
If any open orders exist that should not: cancel them manually on Binance.

**Step 4 — Graceful engine shutdown**
```powershell
# Stop the engine process (sends SIGTERM → graceful 30s shutdown)
scripts\engine\stop_engine_port.ps1
```
Watch logs for: `Graceful shutdown complete in X.XXs`

**Step 5 — Verify DB integrity**
```bash
sqlite3 runtime/data/louise_hub.sqlite "PRAGMA integrity_check;"
```

**Step 6 — Create emergency backup**
```powershell
scripts\backup\backup_databases.ps1
```

**Step 7 — Investigate root cause before restarting**
Check `backend.log` for the last 100 lines before the issue occurred.

**Restart sequence:**
1. Verify root cause is understood and addressed
2. Start engine: `scripts\engine\run_engine.ps1`
3. Verify gateway connects: UI shows "WS: Connected"
4. Start bots one at a time, monitoring for errors
5. Scan for orphans after first successful restart

---

## Quick Reference — Alert Codes

| Alert Code | Meaning | Section |
|-----------|---------|---------|
| `FUSE_TRIPPED` | API circuit breaker open | §1 |
| `ORPHAN_DETECTED` | Untracked orders on Binance | §2 |
| `GATEWAY_DISCONNECTED` | WebSocket dropped > 5min | §3 |
| `STOP_LOSS_TRIGGERED` | Bot sold at loss | §4 |
| `DATABASE_ERROR` | SQLite error | §5 |
| `BUDGET_EXHAUSTED` | Daily spend limit reached | §6 |
| `WEIGHT_ZONE_RED` | API weight > 80% of limit | §7 |
| `WEIGHT_ZONE_YELLOW` | API weight > 40% of limit | §7 |
| `SHUTDOWN_INITIATED` | Graceful shutdown started | §10 |
| `SHUTDOWN_TIMEOUT_EXCEEDED` | Shutdown took > 30s | §10 |

---

*Last updated: 2026-05-12*
