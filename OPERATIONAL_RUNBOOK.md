# Operational Runbook: Louise Bot Hub 24/7 Operations

## Quick Reference: Emergency Procedures

| Situation | Action | Time |
|-----------|--------|------|
| Bot stuck (not polling) | Check weight governor, gateway status | 5 min |
| Order execution fails | Verify balance, Binance status | 5 min |
| WebSocket disconnected | Restart service, check firewall | 10 min |
| API token compromised | Rotate token, restart with new token | 15 min |
| Budget exhausted | Check BudgetGuard config, may need restart | 5 min |
| Orphan orders detected | Use `/api/louise/orphans/scan` endpoint | 10 min |

---

## Daily Monitoring (Start of Business)

### 1. Health Check (5 min)

```bash
# SSH into production server
ssh trading@louise-prod

# Check service status
systemctl status louise
# Expected: active (running)

# Check API responds
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/health

# Expected response:
{
  "status": "healthy",
  "uptime_seconds": 86400,  # ~1 day if running fine
  "active_bots": 5,
  "weight_zone": "GREEN"
}

# If status != "healthy" → consult troubleshooting below
```

### 2. Check Recent Logs (10 min)

```bash
# View last 100 lines of logs
tail -n 100 logs/louise.log

# Look for patterns:
grep "ERROR\|CRITICAL" logs/louise.log | tail -20

# Expected: No CRITICAL, minimal ERRORs (retry scenarios are normal)
```

### 3. Verify Database Integrity (5 min)

```bash
# Check SQLite integrity
sqlite3 runtime/data/louise_hub.sqlite "PRAGMA integrity_check;"

# Expected output: "ok"

# Check bot counts
sqlite3 runtime/data/louise_hub.sqlite "SELECT COUNT(*) FROM louise_bots;"
sqlite3 runtime/data/louise_hub.sqlite "SELECT COUNT(*) FROM louise_epochs WHERE status='RUNNING';"
```

### 4. Check Binance Connectivity (5 min)

```bash
# From Python REPL
python
>>> from runtime.connectors.binance_gateway import BinanceGateway
>>> import asyncio
>>> async def test():
...     gw = BinanceGateway()
...     await gw.start()
...     price = await gw.get_ticker_price('BTCUSDT')
...     print(f"BTC/USDT: {price}")
...     await gw.stop()
>>> asyncio.run(test())

# Expected: Current price, e.g., "BTC/USDT: 45321.50"
# If fails: Check Binance API status, API keys, network
```

---

## Continuous Monitoring (Every 4 Hours)

### Metrics to Check

```bash
# 1. Active Bots Count
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/bots | jq 'length'

# 2. Weight Governor Status (GREEN = OK, YELLOW = caution, RED = pause)
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/weight-governor/status | jq '.zone'

# 3. Budget Guard Status
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/telemetry/budget-guard

# 4. Recent Alerts
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/alerts?limit=20

# 5. Processing time (should be <100ms)
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/metrics | jq '.http_request_duration_seconds'
```

### Alert Thresholds

**GREEN (OK):**
- Weight zone: GREEN
- Budget remaining: >10%
- Active bots: All RUNNING or PAUSED (no ERROR)
- Logs: No CRITICAL messages in last hour

**YELLOW (Caution):**
- Weight zone: YELLOW (slow down, don't panic)
- Budget remaining: 5-10%
- Latency: 50-100ms
- Action: Monitor, don't escalate yet

**RED (Escalate):**
- Weight zone: RED (pause bot trading immediately)
- Budget exhausted (0% remaining)
- Latency: >100ms consistently
- CRITICAL errors in logs
- WebSocket disconnected >5 min
- Action: Execute troubleshooting below

---

## Troubleshooting Guide

### Issue: Bot Not Polling (Stuck)

**Symptoms:**
- Bot status = RUNNING but no new epochs created
- No "poll_market" entries in logs for >10 min

**Steps:**
1. Check weight governor:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/louise/weight-governor/status
   
   # If zone == "RED": WeightGovernor is blocking (wait for cooldown)
   ```

2. Check API Fuse:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/louise/api-fuse/status
   
   # If tripped: Fuse will auto-reset in a few minutes
   ```

3. Check Binance gateway:
   ```bash
   # Restart service (see below)
   ```

4. If still stuck: See ROLLBACK_PLAN.md → "Service Restart"

---

### Issue: Order Execution Fails

**Symptoms:**
- Bot creates epoch but can't execute BUY
- BUY_FAILED alerts in log

**Steps:**
1. Verify balance:
   ```bash
   python -c "
   from runtime.connectors.binance_gateway import BinanceGateway
   import asyncio
   async def test():
       gw = BinanceGateway()
       await gw.start()
       balance = await gw.get_balance_usdt()
       print(f'USDT Balance: {balance}')
       await gw.stop()
   asyncio.run(test())
   "
   ```

2. Check Binance status (https://status.binance.com)

3. If balance is low:
   - Deposit USDT to subaccount
   - Restart service: `systemctl restart louise`

4. If Binance is down:
   - Wait for recovery
   - Service will retry automatically

---

### Issue: WebSocket Disconnected

**Symptoms:**
- No price updates
- WebSocket reconnects repeatedly in logs

**Steps:**
1. Check firewall:
   ```bash
   # Verify port 8000 open (adjust if using proxy)
   netstat -tuln | grep 8000
   ```

2. Check network:
   ```bash
   ping 8.8.8.8  # Internet connectivity
   curl -I https://binance.com  # Binance reachable
   ```

3. Restart WebSocket (without full restart):
   ```bash
   # This auto-happens, but if stuck:
   systemctl restart louise
   ```

---

### Issue: Budget Exhausted (Cannot Trade)

**Symptoms:**
- BudgetGuard blocks all BUY attempts
- Logs: "Global BudgetGuard rejected buy"

**Steps:**
1. Check daily budget:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/louise/telemetry/budget-guard
   ```

2. Options:
   - **Wait for daily reset:** Happens at 00:00 UTC (see PECUNATOR_BUDGET_RESET_HOUR env var)
   - **Increase daily budget:** PATCH bot config → `daily_budget_usdt`
   - **Emergency:** Contact ops, may need manual BudgetGuard reset

---

### Issue: High API Latency (>100ms)

**Symptoms:**
- Slow response times in logs
- Bots slow to execute trades

**Steps:**
1. Check server load:
   ```bash
   top -b -n 1 | head -10
   free -h
   ```

2. Check database:
   ```bash
   sqlite3 runtime/data/louise_hub.sqlite "ANALYZE;"
   ```

3. If high CPU/memory:
   - Kill non-essential processes
   - Consider server upgrade

---

## Emergency Procedures

### Pause All Trading

```bash
# Pause all bots (market temporarily frozen)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/bots/pause-all

# Verify all are PAUSED
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/bots | jq '.[] | .status'
```

### Resume Trading

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/bots/resume-all
```

### Cancel All Pending Orders

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/orders/cancel-all

# Verify via Binance (https://binance.com/trade/BTCUSDT)
```

---

## Shift Change Handoff

**Outgoing Operator:**
1. Run daily checklist above
2. Document any anomalies in `logs/shift-handoff.txt`
3. Share log excerpt with incoming operator
4. Note any pending investigations

**Incoming Operator:**
1. Read shift handoff notes
2. Verify system status with daily checklist
3. If issues present, page oncall engineer

Example handoff log:
```
2026-05-13 16:00 → 2026-05-14 00:00 (outgoing: Alice)
- System nominal, 5 active bots
- One BUY_FAILED retry at 14:32 (Binance spot down briefly)
- Weight zone GREEN, Budget 70% remaining
- No critical issues

Incoming: Bob, please monitor weight governor closely (was YELLOW at 15:00)
```

---

## Escalation Path

1. **5 min:** Check logs, restart WebSocket
2. **15 min:** Call ops engineer (pagerduty)
3. **30 min:** Execute ROLLBACK_PLAN.md if not resolved
4. **1 hour:** Consider switching to paper trading until resolved

---

## Key Log Locations

- **Main logs:** `logs/louise.log`
- **Alert logs:** `runtime/data/alerts.log`
- **Vault audit:** `runtime/data/vault_audit.log`
- **API errors:** `logs/api_errors.log`

---

See: ROLLBACK_PLAN.md for emergency recovery steps.
