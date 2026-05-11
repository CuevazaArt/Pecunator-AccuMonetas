# Bluechip Subaccount Configuration

**Subaccount Name:** bluechip  
**Purpose:** Louise Bot Hub primary trading account  
**Status:** ✅ Confirmed (2026-05-11)  
**Environment:** Production

---

## 📋 Subaccount Details

### Identification
```
Subaccount UID: bluechip
Description: Louise Bot Hub - Multi-instance DCA trading
Created: [Date]
Status: ACTIVE
```

### API Configuration
```
API Key:    [STORED IN runtime/data/credentials.enc]
API Secret: [STORED IN runtime/data/credentials.enc]
IP Whitelist: 127.0.0.1 (localhost)
                [Add any other whitelisted IPs if needed]
```

### Permissions Required
- [x] Read: Account info, balances, orders, trades
- [x] Write: Place orders, cancel orders
- [ ] Margin trading (if needed)
- [ ] Futures trading (if needed)

### Rate Limits & Quotas
```
REST API Weight Limit: 6000/minute (default Binance)
Active Orders Limit: 200 per symbol
Position Limit: [Confirm with Binance]
```

---

## 💰 Trading Parameters

### Daily Budget (Per Louise Instance)

**Format:** One parameter per bot instance

```
louise_btc_001:       $1,000/day  (BTC accumulation)
louise_eth_001:       $800/day    (ETH accumulation)
louise_sol_001:       $500/day    (SOL accumulation)
louise_ada_001:       $400/day    (ADA accumulation)
louise_bnb_001:       $300/day    (BNB accumulation)

Total Hub Daily Budget: $3,000/day  ← Hard cap across all Louise instances
```

**Reset Schedule:** UTC midnight (00:00 UTC)

### Position Size Limits (Optional)

```
Max per bot instance: [TBD based on bluechip balance]
Max portfolio value: $15,000 USD equivalent
```

---

## 🎯 Louise Instances on Bluechip

### Initial Configuration

```yaml
louise_btc_001:
  symbol: BTCUSDT
  buy_volume: $100 per cycle
  poll_interval: 300 seconds (5 min)
  target_profit: 5.0%
  daily_budget: $1,000
  subaccount: bluechip
  enabled: false  (manual start)
  
louise_eth_001:
  symbol: ETHUSDT
  buy_volume: $80 per cycle
  poll_interval: 300 seconds
  target_profit: 5.0%
  daily_budget: $800
  subaccount: bluechip
  enabled: false
  
louise_sol_001:
  symbol: SOLUSDT
  buy_volume: $50 per cycle
  poll_interval: 300 seconds
  target_profit: 5.0%
  daily_budget: $500
  subaccount: bluechip
  enabled: false
```

### Expansion Plan

```
Phase 1: 3 bots (BTC, ETH, SOL)
Phase 2: +2 bots (ADA, BNB) if running well
Phase 3: +5 bots (other assets) based on performance
```

---

## 🔐 Credential Storage

### Secure Vault Setup

```
File: runtime/data/credentials.enc
Encryption: Fernet (symmetric)
Key: runtime/data/vault_local.key

Structure:
{
  "bluechip": {
    "api_key": "[ENCRYPTED]",
    "api_secret": "[ENCRYPTED]",
    "exchange": "binance",
    "created_at": "2026-05-11T00:00:00Z",
    "last_rotated": "2026-05-11T00:00:00Z"
  }
}
```

### Loading Credentials at Startup

```python
# runtime/core/credential_manager.py

async def load_binance_credentials(subaccount: str = "bluechip"):
    """Load API keys from encrypted vault"""
    vault = CredentialVault("runtime/data/credentials.enc")
    creds = vault.get_credentials(subaccount)
    
    return {
        "api_key": creds["api_key"],
        "api_secret": creds["api_secret"],
        "subaccount_name": subaccount
    }
```

### Security Checklist

- [ ] vault_local.key file is readable only by app user
- [ ] vault_local.key is NOT committed to git (.gitignore)
- [ ] credentials.enc is NOT committed to git (.gitignore)
- [ ] API keys rotated annually
- [ ] Audit log: which account accessed vault when
- [ ] No API keys in logs or error messages
- [ ] Separate keys for testnet vs production

---

## 📊 Monitoring & Alerts

### Real-time Monitoring

```
Dashboard view shows:
├─ Total bluechip balance
├─ Free balance (available for trading)
├─ Locked balance (in open orders)
├─ All Louise instances on bluechip
├─ Combined %PNL across all instances
└─ Daily budget consumption
```

### Critical Alerts

```
Alert Type                  Trigger              Action
────────────────────────────────────────────────────────
Low Account Balance         < $500 free          Operator review
Daily Budget Exhausted       hit limit            Bot pauses (all instances)
API Rate Limit              approaching          WeightGovernor pause
Unusual Activity            [TBD]                Immediate pause + alert
Connection Lost             > 5 min              Auto-retry + alert
Credential Error            auth fails           Critical alert
```

### Daily Report (Optional)

```
Time: 23:30 UTC (daily)
Report includes:
├─ Total positions (BTC, ETH, SOL, etc.)
├─ Daily profit/loss
├─ Budget usage ($ and %)
├─ Number of purchases executed
├─ Failed orders (if any)
├─ API weight usage
└─ Epochs closed (if any)

Recipient: [Operator email]
Format: Email + Dashboard widget
```

---

## 🔄 Operational Procedures

### Pre-Launch Checklist

- [ ] API keys copied to credentials.enc
- [ ] vault_local.key generated and secured
- [ ] First Louise bot instance created (test mode)
- [ ] Balance verification working (can see balance in dashboard)
- [ ] WebSocket metrics streaming
- [ ] All alerts firing correctly
- [ ] Mock orders tested (if testnet available)
- [ ] Operator trained on dashboard

### Daily Operations

```
Morning (before market open):
├─ Check balance & free margin
├─ Review overnight epochs (if any closed)
├─ Verify all bots status
└─ Confirm daily budget reset

Throughout day:
├─ Monitor %PNL on all instances
├─ Watch for alerts (low balance, errors)
├─ Respond to critical issues
└─ Track number of purchases

Evening (after market close):
├─ Review daily stats
├─ Check if any epochs closed
├─ Plan for next day
└─ Note any issues for team review
```

### Emergency Procedures

#### Scenario: Balance Critically Low (< $100)

```
Immediate:
├─ All Louise bots pause automatically
├─ Operator receives critical alert
├─ No new orders placed

Response:
├─ Deposit funds to bluechip ASAP
├─ OR manually close some positions
├─ OR reduce daily budgets temporarily

Recovery:
├─ When balance recovers, check each bot
├─ Resume bots one by one (avoid surge)
└─ Monitor closely for first 30 min
```

#### Scenario: API Credentials Compromised

```
Immediate:
├─ Rotate API keys on Binance immediately
├─ All Louise bots pause (old keys will fail)
├─ Operator gets alerts
└─ Stop all trading

Recovery:
├─ Generate new API keys on Binance
├─ Update vault with new keys
├─ Restart application
├─ Resume bots carefully
└─ Audit all orders during incident

Audit:
├─ Review order history for unauthorized trades
├─ Check if balance was compromised
├─ Report to compliance/security
└─ Document incident
```

#### Scenario: Binance API Unavailable

```
Monitoring:
├─ BalanceChecker fails → retry with backoff
├─ BinanceGateway detects API timeout
├─ ApiFuse circuit breaker engages

Response:
├─ Louise bots pause (can't fetch price)
├─ Dashboard shows "API DOWN" status
├─ Operator receives alert

Recovery:
├─ Wait for Binance API recovery
├─ Automatic retry (exponential backoff)
├─ Resume bots once connection restored
└─ Verify no missed orders
```

---

## 📈 Expected Performance Metrics

### Monthly Targets (Conservative Estimates)

```
Assumption: 3 active Louise bots, $3,000/day budget

Monthly Budget: $3,000 × 30 = $90,000
Expected Epochs Completed: 30-45 (average 10-15 days each)
Win Rate: 100% (by design, all epochs profitable)

Expected Profit: $3,000 - $5,000/month (3-6%)
API Weight Usage: 500k-1M/month (well under limits)
Success Rate: 99%+ (measured by automated operations)
```

### Monitored KPIs

```
Daily:
├─ Purchases executed
├─ Average buy price
├─ Current portfolio value
├─ Daily budget utilization

Weekly:
├─ Epochs closed
├─ Total profit
├─ Average epoch duration
├─ Failure rate (should be 0)

Monthly:
├─ Portfolio growth
├─ ROI%
├─ API efficiency
└─ Operational incidents (if any)
```

---

## 🔧 Configuration Files

### .env File (Local Development)

```bash
# Bluechip Subaccount Configuration
SUBACCOUNT_NAME=bluechip
SUBACCOUNT_TYPE=spot

# Daily Budget Limits
LOUISE_BTC_DAILY_BUDGET=1000.00
LOUISE_ETH_DAILY_BUDGET=800.00
LOUISE_SOL_DAILY_BUDGET=500.00

# API Configuration
BINANCE_API_TIMEOUT=10  # seconds
BINANCE_API_MAX_RETRIES=3
BINANCE_API_BACKOFF_MULTIPLIER=2

# Louise Bot Defaults
LOUISE_DEFAULT_POLL_INTERVAL=300  # 5 minutes
LOUISE_DEFAULT_TARGET_PROFIT=5.0  # 5%
LOUISE_DEFAULT_MIN_BALANCE=8.0    # $8 USDT

# Monitoring & Alerts
ALERT_LOW_BALANCE_THRESHOLD=500.00
ALERT_BUDGET_EXHAUSTED=true
ALERT_API_ERROR=true
ALERT_CHANNEL=telegram  # or: email, discord

# Logging
LOG_LEVEL=INFO
LOG_FILE=runtime/logs/louise_bluechip.log
LOG_ROTATE_SIZE=50M
LOG_ROTATE_COUNT=5
```

### .env.example (Template)

```bash
# Copy this to .env and fill in your values
SUBACCOUNT_NAME=bluechip
LOUISE_BTC_DAILY_BUDGET=1000.00
LOUISE_ETH_DAILY_BUDGET=800.00
# ... etc
```

### Runtime Config (Loaded at Startup)

```yaml
# runtime/config/louise_bluechip.yaml

subaccount: bluechip
instances:
  - bot_id: louise_btc_001
    symbol: BTCUSDT
    buy_volume: 100.00
    poll_interval_seconds: 300
    target_profit_pct: 5.0
    daily_budget_usdt: 1000.00
    enabled: false
    
  - bot_id: louise_eth_001
    symbol: ETHUSDT
    buy_volume: 80.00
    poll_interval_seconds: 300
    target_profit_pct: 5.0
    daily_budget_usdt: 800.00
    enabled: false
    
  - bot_id: louise_sol_001
    symbol: SOLUSDT
    buy_volume: 50.00
    poll_interval_seconds: 300
    target_profit_pct: 5.0
    daily_budget_usdt: 500.00
    enabled: false

hub_settings:
  total_daily_budget_usdt: 3000.00
  api_weight_limit_per_minute: 6000
  min_free_balance_required: 8.00
  auto_pause_on_low_balance: true
  auto_resume_on_deposit: true
```

---

## 📝 Database: Bluechip Account Tracking

### Account Info Table

```sql
CREATE TABLE bluechip_account_info (
    account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    subaccount_name TEXT UNIQUE NOT NULL,
    exchange TEXT DEFAULT 'binance',
    api_key_hash TEXT NOT NULL,  -- Hash only, not stored plaintext
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_synced TIMESTAMP,
    total_balance_usdt FLOAT,
    free_balance_usdt FLOAT,
    locked_balance_usdt FLOAT,
    equity_usdt FLOAT,
    status TEXT DEFAULT 'ACTIVE'  -- ACTIVE, DISABLED, ERROR
);

INSERT INTO bluechip_account_info 
(subaccount_name, exchange, api_key_hash)
VALUES ('bluechip', 'binance', '[SHA256 HASH]');
```

### Daily Budget Ledger

```sql
CREATE TABLE bluechip_budget_ledger (
    ledger_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    bot_id TEXT NOT NULL,
    daily_budget_usdt FLOAT,
    spent_usdt FLOAT,
    remaining_usdt FLOAT,
    num_purchases INTEGER,
    FOREIGN KEY(bot_id) REFERENCES louise_bots(bot_id)
);
```

---

## ✅ Implementation Checklist

### Phase 0: Configuration (Before Phase 1)

- [ ] Confirm bluechip API keys available
- [ ] Create vault_local.key (secure location)
- [ ] Encrypt credentials → credentials.enc
- [ ] Add to .gitignore (both files)
- [ ] Test credential loading in app startup
- [ ] Create .env.example with bluechip config
- [ ] Document all 5 Louise instances to create

### Phase 1: Integration

- [ ] BalanceChecker loads bluechip credentials
- [ ] BinanceGateway connects to bluechip account
- [ ] First bot instance created (louise_btc_001)
- [ ] Dashboard shows bluechip balance
- [ ] All bots tag as "subaccount: bluechip" in DB

### Phase 2: Monitoring

- [ ] Daily budget tracking per bot
- [ ] Total bluechip budget monitoring
- [ ] Low balance alerts working
- [ ] Budget exhaustion pause logic

### Phase 3: UI

- [ ] Dashboard shows "bluechip account" label
- [ ] All bots tagged with subaccount in UI
- [ ] Bluechip balance visible in top bar
- [ ] Daily budget progress bar (per bot)
- [ ] Hub total budget usage (across all bots)

### Phase 4: Testing

- [ ] Mock trades with bluechip (testnet if available)
- [ ] Budget calculation accuracy
- [ ] Pause/resume logic
- [ ] Credential rotation test
- [ ] Error recovery

### Phase 5: Production

- [ ] Operator trained
- [ ] Runbooks prepared
- [ ] First bot enabled (louise_btc_001)
- [ ] Monitor 24/7 for first week
- [ ] Scale up remaining bots based on performance

---

## 🎯 Next Steps

1. **Immediately:**
   - [ ] Prepare bluechip API keys (generate if needed)
   - [ ] Secure vault_local.key
   - [ ] Update .env with bluechip config

2. **Phase 1 Start:**
   - [ ] Implement credential loading
   - [ ] Connect BinanceGateway to bluechip
   - [ ] First bot instance created

3. **Phase 2:**
   - [ ] Daily budget tracking
   - [ ] Monitoring dashboard

---

**Status:** ✅ Bluechip Subaccount Confirmed  
**Effective Date:** 2026-05-11  
**Last Updated:** 2026-05-11
