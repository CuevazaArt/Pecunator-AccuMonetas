# Louise Bot Specification

**Bot Name:** Louise  
**Strategy Type:** DCA (Dollar Cost Averaging) — Downside-Only Averaging  
**Version:** 1.0.0  
**Status:** In Development

---

## 📌 Overview

Louise is a progressive accumulation bot designed to build positions in selected assets by averaging down on dips. It operates autonomously with minimal complexity:

- ✅ **No stop-loss** — by design, only averages down
- ✅ **No technical indicators** — pure price-based logic
- ✅ **Time-driven execution** — polls market at fixed intervals
- ✅ **Profitable exit** — closes position when target profit % is reached
- ✅ **Multi-instance hub** — many Louise bots run simultaneously on different symbols

---

## 🎯 Core Logic

### Initialization (First Execution)

When Louise starts for the first time on a symbol with no prior purchase history:

```
Event: FIRST_BUY
├─ Timestamp: T0
├─ Action: Market buy at current price (P0)
├─ Volume: buy_volume (configured parameter)
├─ Cost Basis: P0
├─ Average Price: P0
└─ Position Status: ACCUMULATING
```

**Reference Price Set:** `last_buy_price = P0`

---

### Main Loop (Every N Seconds)

**Polling Cycle:**

```python
Every poll_interval_seconds:
    current_price = fetch_market_price(symbol)
    last_buy_price = read_from_db()
    
    if current_price < last_buy_price:
        # Condition met: price dropped below last purchase
        
        if has_budget_remaining():
            market_buy(volume=buy_volume)
            
            # Update statistics
            average_price = recalculate_vwap()
            total_cost = sum_all_purchases()
            current_value = current_price * position_size
            current_profit_pct = ((current_value - total_cost) / total_cost) * 100
            
            # Check exit condition
            if current_profit_pct >= target_profit_pct:
                market_sell_all()
                close_epoch()  # Mark as successful execution
                bot_shutdown()
        else:
            log(WARN, "Budget exhausted, waiting for next cycle")
    else:
        log(INFO, f"Holding: current={current_price}, last_buy={last_buy_price}")
```

---

## 🔄 Execution States

### State Machine

```
IDLE
  ↓
FIRST_BUY (triggered on bot start)
  ↓
ACCUMULATING (loop while price stays above/below reference)
  ├─ BUYING (when condition met)
  │  └─ back to ACCUMULATING
  └─ WAITING (when no condition met)
  ↓
PROFIT_TARGET_REACHED (when profit % threshold hit)
  ├─ SELLING (market sell all)
  ├─ EPOCH_CLOSED (log successful execution)
  └─ SHUTDOWN

ERROR_STATES:
├─ INSUFFICIENT_BALANCE
├─ EXCHANGE_ERROR
├─ NETWORK_ERROR
└─ AUTH_ERROR
```

---

## 📊 Key Parameters

Each Louise instance requires configuration:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `symbol` | str | — | Trading pair (e.g., "BTCUSDT", "ETHUSDT") |
| `buy_volume` | float | — | Amount to buy per cycle (USDT) |
| `poll_interval_seconds` | int | 300 | Check market every N seconds (5 min default) |
| `target_profit_pct` | float | 5.0 | Exit when profit reaches X% |
| `daily_budget_usdt` | float | — | Max spend per calendar day (optional hard cap) |
| `subaccount` | str | — | Binance subaccount ID for credentials |
| `enabled` | bool | true | Start bot immediately or wait for operator? |

### Example Configuration

```json
{
  "bot_id": "louise_btc_001",
  "symbol": "BTCUSDT",
  "buy_volume": 100.0,
  "poll_interval_seconds": 300,
  "target_profit_pct": 5.0,
  "daily_budget_usdt": 1000.0,
  "subaccount": "trading-bot-prod",
  "enabled": true
}
```

---

## 💾 Data Model

### Bot Instance (SQLite Table: `louise_bots`)

```sql
CREATE TABLE louise_bots (
    bot_id TEXT PRIMARY KEY,
    symbol TEXT NOT NULL,
    buy_volume REAL NOT NULL,
    poll_interval_seconds INTEGER DEFAULT 300,
    target_profit_pct REAL DEFAULT 5.0,
    daily_budget_usdt REAL,
    subaccount TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_poll_at TIMESTAMP,
    last_buy_at TIMESTAMP,
    status TEXT DEFAULT 'IDLE',  -- IDLE, ACCUMULATING, PAUSED, ERROR, SHUTDOWN
    error_message TEXT,
    epoch_id TEXT
);
```

### Purchase History (SQLite Table: `louise_purchases`)

```sql
CREATE TABLE louise_purchases (
    purchase_id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    epoch_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    price_at_buy REAL NOT NULL,
    volume REAL NOT NULL,
    cost_usdt REAL NOT NULL,  -- price * volume
    order_id TEXT UNIQUE NOT NULL,  -- Binance order ID
    status TEXT DEFAULT 'FILLED',  -- PENDING, FILLED, FAILED, CANCELLED
    FOREIGN KEY(bot_id) REFERENCES louise_bots(bot_id),
    FOREIGN KEY(epoch_id) REFERENCES louise_epochs(epoch_id)
);
```

### Epochs (Successful Executions) (SQLite Table: `louise_epochs`)

```sql
CREATE TABLE louise_epochs (
    epoch_id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    
    -- Accumulation phase
    num_purchases INTEGER,
    total_cost_usdt REAL,
    avg_buy_price REAL,
    
    -- Exit phase
    final_price REAL,
    final_position_size REAL,
    final_value_usdt REAL,
    profit_usdt REAL,
    profit_pct REAL,
    
    status TEXT DEFAULT 'RUNNING',  -- RUNNING, CLOSED_SUCCESSFUL, CLOSED_MANUAL, CLOSED_ERROR
    notes TEXT,
    
    FOREIGN KEY(bot_id) REFERENCES louise_bots(bot_id)
);
```

---

## 📈 Metrics Tracked

For each Louise instance, track:

### Real-time Metrics
- **Current Price** — Live market price of symbol
- **Last Buy Price** — Reference price for next cycle
- **Position Size** — Total tokens accumulated so far
- **Total Cost** — Sum of all purchase costs (USDT)
- **Average Buy Price** — VWAP of all purchases
- **Current Value** — `position_size * current_price`
- **Unrealized P&L** — `current_value - total_cost`
- **Unrealized P&L %** — `(current_value - total_cost) / total_cost * 100`
- **Budget Used Today** — USDT spent in current calendar day
- **Budget Remaining** — Daily limit - used

### Historical Metrics
- **Total Epochs Completed** — Number of successful execution cycles
- **Total Profit (All Epochs)** — Sum of `profit_usdt` across closed epochs
- **Win Rate** — 100% (by design, always closes at profit)
- **Avg Epoch Duration** — Average days to reach target profit
- **Max Accumulated Before Exit** — Max number of purchases in single epoch

---

## 🛡️ Risk Controls

### Budget Management
- **Daily Spend Cap:** Configurable per bot
- **Hard Minimum:** Bot stops buying if budget depleted for the day
- **Rollover:** Budget resets at midnight UTC

### Position Limits (Optional)
- **Max Position Size:** Optional ceiling on accumulated tokens
- **Max Purchase Count:** Optional limit on number of buys per epoch

### Error Handling
- **Exchange Error** → Pause bot, log error, alert operator
- **Insufficient Balance** → Pause bot, log balance check
- **Network Timeout** → Retry with backoff (3 retries, exponential 2x)
- **Invalid Credentials** → Critical alert, require operator action

---

## 🔌 API Endpoints

Louise hub exposes REST API for UI and external integration:

### Bot Management
- `GET /api/v1/louise/bots` — List all Louise instances
- `GET /api/v1/louise/bots/{bot_id}` — Get bot details
- `POST /api/v1/louise/bots` — Create new Louise instance
- `PATCH /api/v1/louise/bots/{bot_id}` — Update bot config (target profit, interval, etc.)
- `POST /api/v1/louise/bots/{bot_id}/enable` — Start bot
- `POST /api/v1/louise/bots/{bot_id}/disable` — Pause bot
- `POST /api/v1/louise/bots/{bot_id}/shutdown` — Force shutdown (sell all, close epoch)
- `DELETE /api/v1/louise/bots/{bot_id}` — Remove bot instance

### Metrics & History
- `GET /api/v1/louise/bots/{bot_id}/metrics` — Current metrics (price, P&L, budget)
- `GET /api/v1/louise/bots/{bot_id}/epoch/current` — Active epoch details
- `GET /api/v1/louise/bots/{bot_id}/epochs` — Historical epochs (paginated)
- `GET /api/v1/louise/bots/{bot_id}/purchases` — Purchase history (paginated)
- `GET /api/v1/louise/stats` — Hub-wide statistics (total profit, active bots, etc.)

### WebSocket Streams
- `/ws/louise/metrics/{bot_id}` — Real-time metrics updates
  - Emits every N seconds (configurable, default 5s)
  - Payload: `{current_price, avg_price, position_size, unrealized_pct, budget_remaining}`

---

## 🧪 Testing Strategy

### Unit Tests
- Price comparison logic
- VWAP calculation
- Profit % calculation
- Budget tracking
- Epoch state transitions

### Integration Tests
- BinanceGateway integration (testnet)
- SQLite persistence
- WebSocket broadcast
- API endpoint responses

### Simulation Tests
- Market scenarios: downtrend, uptrend, sideways
- Budget exhaustion
- Network failures
- Rapid price swings

---

## 🚀 Deployment & Operations

### Pre-Launch Checklist
- [ ] Credentials vault: API keys loaded securely
- [ ] SQLite database: schema initialized
- [ ] First bot instance: created, ready to enable
- [ ] UI: connected to API, WebSocket stream working
- [ ] Tests: 100% pass rate
- [ ] Rate limiting: WeightGovernor active

### Operational Notes
- Louise instances run independently (no cross-bot state)
- Each bot polls independently; no synchronization needed
- Failed purchases (API error) don't interrupt cycle; retry on next poll
- Epochs are immutable once closed (for audit trail)
- Operator can force-close epoch anytime (manual intervention)

### Monitoring
- Alert if any bot enters ERROR state
- Alert if daily budget exhausted (by bot)
- Alert if target profit reached (epoch closing)
- Periodic health check: bot responsive? DB healthy? Credentials valid?

---

## 📝 Example Walkthrough

**Setup:** Louise configured for BTC, $100 buy every 5 min, 5% profit target, $1000/day budget

```
T0: Bot starts
    └─ FIRST_BUY: Price = $40,000
       ├─ Buy 0.0025 BTC for $100
       ├─ Last Buy Price = $40,000
       └─ Cost Basis = $100

T1 (5 min): Poll market
    Price = $39,500 < $40,000? YES
    └─ Buy 0.002525... BTC for $100
       ├─ Avg Price = ($100*$40k + $100*$39.5k) / $200 = $39,750
       ├─ Position: 0.00505 BTC
       ├─ Cost: $200
       ├─ Current Value: 0.00505 * $39.5k = $199.475k ❌ (typo, should be $199.475)
       └─ P&L %: ($199.475 - $200) / $200 = -0.13% (still negative, holding)

T2 (5 min): Poll market
    Price = $40,500 > $39,750? YES (price up from last buy)
    └─ Hold, price above avg
       ├─ Position: 0.00505 BTC
       ├─ Cost: $200
       ├─ Current Value: 0.00505 * $40.5k = $204.525k ❌
       └─ P&L %: ($204.525 - $200) / $200 = +2.26% (still below 5%)

T3 (5 min): Poll market
    Price = $40,200 < $40,500? YES
    └─ Buy 0.002488... BTC for $100
       ├─ Avg Price = $200 / 0.00505 ≈ $39,603
       ├─ Position: 0.00754 BTC
       ├─ Cost: $300
       ├─ Current Value: 0.00754 * $40.2k = $303.108k ❌
       └─ P&L %: ($303.108 - $300) / $300 = +1.04% (still below 5%)

T4 (5 min): Poll market
    Price = $41,650 > $39,603? YES
    └─ Check profit target: ($41,650 * 0.00754 - $300) / $300 = +5.04% ✅
       ├─ PROFIT TARGET REACHED!
       ├─ Market Sell: 0.00754 BTC at $41,650 = $314.19
       ├─ Profit: $314.19 - $300 = $14.19
       ├─ Close Epoch: SUCCESSFUL
       └─ Bot Status: SHUTDOWN (ready for next epoch if re-enabled)
```

---

## 🔄 Multi-Bot Hub Dynamics

A hub can run many Louise instances:

```
Hub State Snapshot:
├─ louise_btc_001 (BTC/USDT)
│  ├─ Status: ACCUMULATING
│  ├─ Purchases: 8
│  ├─ Cost: $800
│  ├─ P&L: +3.2%
│  └─ Budget Today: $200 remaining
│
├─ louise_eth_001 (ETH/USDT)
│  ├─ Status: ACCUMULATING
│  ├─ Purchases: 15
│  ├─ Cost: $1,500
│  ├─ P&L: -1.5%
│  └─ Budget Today: $0 (exhausted)
│
└─ louise_sol_001 (SOL/USDT)
   ├─ Status: SHUTDOWN (epoch closed)
   ├─ Epoch: louise_sol_001_ep_001
   ├─ Duration: 3 days
   ├─ Profit: $85.50 (6.2%)
   └─ Ready for new epoch
```

Each bot is independent; operator monitors all via unified UI dashboard.

---

**Last Updated:** 2026-05-11  
**Next:** UI Wireframes → Backend Implementation → Testing
