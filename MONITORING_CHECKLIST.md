# Monitoring Checklist: Louise Bot Hub Metrics & Alerts

## Quick Health Status Dashboard

**Run this every 2 hours:**

```bash
#!/bin/bash
# health-check.sh

TOKEN=$1  # Pass via: ./health-check.sh $TOKEN

echo "=== LOUISE BOT HUB HEALTH REPORT ==="
echo "Timestamp: $(date -u)"
echo ""

# 1. Service Status
echo "📊 SERVICE STATUS:"
systemctl status louise | grep -E "Active|running"

# 2. API Health
echo ""
echo "🏥 API HEALTH:"
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/health | jq '.'

# 3. Bot Status Summary
echo ""
echo "🤖 BOT SUMMARY:"
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/bots | jq '[
    group_by(.status) | 
    map({status: .[0].status, count: length}) |
    .[]
  ]'

# 4. Weight Governor
echo ""
echo "⚖️ WEIGHT GOVERNOR:"
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/weight-governor/status | jq '{
    zone: .zone,
    usage_percent: .usage_percent
  }'

# 5. Budget Guard
echo ""
echo "💰 BUDGET GUARD:"
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/telemetry/budget-guard | jq '.'

# 6. Recent Alerts
echo ""
echo "🚨 RECENT ALERTS (last 5):"
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/alerts?limit=5 | jq '.[].message'

# 7. Recommendations
echo ""
echo "✅ RECOMMENDATIONS:"
if [ $(systemctl status louise | grep -c "active (running)") -eq 0 ]; then
  echo "⚠️  Service not running!"
fi
```

---

## Metrics to Monitor

### System Metrics

| Metric | Good | Warning | Critical | Action |
|--------|------|---------|----------|--------|
| **Uptime** | >99% | <99% | <95% | Investigate crashes |
| **CPU usage** | <30% | 30-70% | >70% | Check for runaway processes |
| **Memory usage** | <200MB | 200-500MB | >500MB | Increase RAM or identify leak |
| **Disk free** | >1GB | 500MB-1GB | <500MB | Archive logs, expand disk |
| **API latency p95** | <50ms | 50-100ms | >100ms | Profile code, check DB |

### Application Metrics

| Metric | Good | Warning | Critical | Action |
|--------|------|---------|----------|--------|
| **Weight Zone** | GREEN | YELLOW | RED | Pause trading if RED |
| **Active bots** | N/A | Trend matters | See logs | Monitor individually |
| **Budget remaining** | >20% | 10-20% | <10% | Alert ops |
| **Epochs active** | <10 | 10-50 | >50 | Risk of accumulation |
| **Avg fill time** | <2s | 2-5s | >5s | Check Binance latency |
| **WebSocket connected** | YES | Reconnecting | NO | Restart service |
| **Database size** | <100MB | 100-500MB | >500MB | Archive old epochs |

### API Metrics

| Endpoint | Response Time | Status | Alerts |
|----------|---------------|--------|--------|
| `GET /health` | <10ms | 200 OK | Critical if fails |
| `GET /bots` | <50ms | 200 OK | Warn if >100ms |
| `POST /bots` | <500ms | 201 Created | Validate input |
| `PATCH /bots/{id}` | <500ms | 200 OK | Validate before send |
| `GET /weight-governor/status` | <20ms | 200 OK | Zone RED? Pause |
| `WS /ws` | <100ms | 101 Upgrade | Reconnect if drops |

---

## Alert Rules

### Critical Alerts (Page Oncall)

```yaml
- name: service_down
  condition: systemctl status louise != "active (running)"
  action: page_oncall
  message: "Louise service is DOWN"

- name: weight_zone_red
  condition: weight_zone == "RED"
  duration: 5_minutes
  action: page_oncall
  message: "Weight zone RED for 5+ min, trading paused"

- name: database_corruption
  condition: "PRAGMA integrity_check" != "ok"
  action: page_oncall
  message: "Database corruption detected, manual intervention needed"

- name: api_latency_high
  condition: api_p95_latency > 200ms
  duration: 10_minutes
  action: page_oncall
  message: "API latency critically high (p95 > 200ms)"

- name: websocket_down
  condition: websocket_connected == false
  duration: 15_minutes
  action: page_oncall
  message: "WebSocket disconnected for 15+ min"
```

### Warning Alerts (Notify Slack)

```yaml
- name: weight_zone_yellow
  condition: weight_zone == "YELLOW"
  duration: 10_minutes
  action: notify_slack
  message: "⚠️ Weight zone YELLOW, watch carefully"

- name: budget_running_low
  condition: budget_remaining < 10%
  action: notify_slack
  message: "⚠️ Budget < 10% remaining"

- name: api_latency_warning
  condition: api_p95_latency > 100ms
  duration: 5_minutes
  action: notify_slack
  message: "API latency elevated (p95 > 100ms)"

- name: large_drawdown
  condition: any_bot.pnl_pct < -10%
  action: notify_slack
  message: "⚠️ Bot in drawdown > 10%, monitor for stop-loss"

- name: disk_space_low
  condition: disk_free < 1GB
  action: notify_slack
  message: "⚠️ Disk < 1GB, archive logs soon"
```

### Informational Alerts (Log Only)

```yaml
- name: bot_paused
  condition: bot.status == "PAUSED"
  action: log
  message: "Bot paused by user or system"

- name: epoch_closed_successful
  condition: epoch.status == "CLOSED_SUCCESSFUL"
  action: log
  message: "Epoch closed with profit"

- name: api_request_count
  condition: api_requests_per_minute
  action: log_metric
  message: "API requests/min for monitoring"
```

---

## Prometheus Metrics (Optional)

If using Prometheus/Grafana for monitoring:

```yaml
# Add to scrape_configs in prometheus.yml
- job_name: 'louise-bot'
  static_configs:
    - targets: ['localhost:8000']
  metrics_path: '/metrics'
  scrape_interval: 15s
```

**Key metrics to graph:**

```
louise_active_bots{status="RUNNING"}        # Number of running bots
louise_weight_zone{zone="GREEN"|"YELLOW"|"RED"}  # Current zone
louise_api_requests_total                   # Total API calls
louise_api_latency_seconds{quantile="0.95"} # P95 latency
louise_websocket_connections                # Active WS connections
louise_database_size_bytes                  # DB file size
louise_epochs_total{status="RUNNING"}       # Active trading cycles
louise_orders_filled_total                  # Cumulative fills
louise_budget_remaining_percent              # Budget usage
```

---

## Dashboard Template

If using Grafana, create a dashboard with:

**Row 1: System Health**
- Service Status (GREEN/RED)
- Uptime (days)
- CPU, Memory, Disk usage
- API latency p95

**Row 2: Trading Status**
- Weight zone (gauge)
- Budget remaining (%)
- Active bots (line chart)
- Epochs active (gauge)

**Row 3: Performance**
- API requests/min
- WebSocket connections
- Database size trend
- Fill time histogram

**Row 4: Alerts**
- Recent critical alerts (table)
- Alert firing status (stat panel)
- Log viewer (Loki)

---

## Log Patterns to Watch

### Normal Operations
```
"[INFO] poll_market: cycle starting"
"[INFO] BUY executed: 0.5 BTC @ 45000"
"[INFO] epoch closed: profit +2.5%"
"[DEBUG] price update: BTCUSDT 45321.50"
```

### Warnings (Monitor but not urgent)
```
"[WARN] API weight at 80% (YELLOW zone)"
"[WARN] Budget 15% remaining"
"[WARN] Price stale (>15s), waiting"
"[WARN] Order rejection: insufficient liquidity"
```

### Errors (Investigate)
```
"[ERROR] BUY execution failed: {reason}"
"[ERROR] Gateway connection lost"
"[ERROR] Database query timed out"
```

### Critical (Page Oncall)
```
"[CRITICAL] Fuse tripped: block all trading"
"[CRITICAL] Database corruption detected"
"[CRITICAL] Service crashed: {backtrace}"
"[CRITICAL] Wallet balance critical: <$10"
```

---

## Shift Checklist (Every 4 Hours)

```bash
# Start of shift
- [ ] Service status: systemctl status louise
- [ ] Health endpoint: curl /health → "healthy"
- [ ] Bot count: curl /bots → expected number
- [ ] Weight zone: GREEN or YELLOW (NOT RED)
- [ ] Budget remaining: >5%
- [ ] Recent errors: grep ERROR logs/louise.log | wc -l < 5?
- [ ] WebSocket: curl /metrics → websocket_connections > 0?
- [ ] Database: sqlite3 louise_hub.sqlite "PRAGMA integrity_check"

# During shift
- [ ] Monitor every 2 hours: run health-check.sh
- [ ] Check alerts every 15 min: grep ALERT logs/louise.log
- [ ] Check Binance status: status.binance.com

# End of shift
- [ ] Summary: Log any issues to shift-handoff.txt
- [ ] Notify next shift of anomalies
- [ ] Verify all bots status before handing off
```

---

## Escalation Contacts

| Issue | Severity | Contact | Response SLA |
|-------|----------|---------|--------------|
| Service down | CRITICAL | Pagerduty → Oncall | 15 min |
| Weight RED >10min | HIGH | Slack ops-channel | 30 min |
| API latency | MEDIUM | Slack #louise-monitoring | 1 hour |
| Budget low | MEDIUM | Email ops team | 2 hours |
| Disk full | MEDIUM | Email infrastructure | 4 hours |

---

## Weekly Review

**Every Monday 9 AM:**

```bash
# Generate weekly report
echo "=== LOUISE BOT HUB - WEEKLY REPORT ==="
echo "Week of $(date -u +%Y-%m-%d)"

echo ""
echo "📈 PERFORMANCE:"
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/metrics | jq '{
    total_epochs: .epochs_total,
    successful_epochs: .epochs_successful,
    failed_epochs: .epochs_failed,
    avg_profit_pct: .avg_profit_pct,
    total_volume_usdt: .total_volume_usdt
  }'

echo ""
echo "⚠️ INCIDENTS:"
grep "CRITICAL\|ERROR" logs/louise.log | wc -l
echo "critical/error events"

echo ""
echo "💰 FINANCIAL:"
curl -s -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/louise/telemetry/revenue | jq '.'

echo ""
echo "✅ RECOMMENDATIONS FOR NEXT WEEK:"
# Manual review based on metrics above
```

---

**See:** OPERATIONAL_RUNBOOK.md for troubleshooting.
**See:** ROLLBACK_PLAN.md for emergency procedures.
