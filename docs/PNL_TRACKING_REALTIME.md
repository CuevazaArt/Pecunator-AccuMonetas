# Real-time PNL Tracking for Louise Bot Hub

**Feature:** Live profit/loss percentage display on every bot instance  
**Purpose:** Enable operator to monitor position health at a glance  
**Update Frequency:** Every 5 seconds (WebSocket broadcast)  
**Status:** UI/Metrics enhancement for Phase 1

---

## 🎯 Concept

Every Louise bot instance displays **live %PNL** that updates in real-time:

```
louise_btc_001
BTC/USDT
Status: ✅ RUNNING
Price: $42,500
%PNL: +2.81% 📈
Position: 0.05 BTC
Cost: $1,200
```

The **%PNL** shows unrealized profit/loss compared to **cost basis** (VWAP of all purchases).

---

## 📐 PNL Calculation Formula

### Unrealized PNL %

```
unrealized_pct = ((current_position_value - total_cost) / total_cost) * 100

Where:
├─ current_position_value = position_size * current_price
├─ position_size = sum of all tokens bought
├─ current_price = live market price right now
├─ total_cost = sum of all USDT spent on purchases
└─ Result: % gain/loss from cost basis
```

### Example Walkthrough

```
Epoch: louise_btc_001

Purchase 1: Buy 0.0025 BTC @ $40,000
├─ Cost: $100
├─ Position: 0.0025 BTC

Purchase 2: Buy 0.00253 BTC @ $39,500 (price dropped)
├─ Cost: $100
├─ Position: 0.00503 BTC
├─ Total Cost: $200
├─ Avg Price (VWAP): $200 / 0.00503 = $39,761

Purchase 3: Buy 0.00249 BTC @ $40,100 (price rose)
├─ Cost: $100
├─ Position: 0.00752 BTC
├─ Total Cost: $300
├─ Avg Price (VWAP): $300 / 0.00752 = $39,894

Current Market Price: $42,500

Calculation:
├─ Current Value: 0.00752 BTC × $42,500 = $319.70
├─ Total Cost: $300
├─ Unrealized P&L: $319.70 - $300 = $19.70
├─ %PNL: ($19.70 / $300) × 100 = +6.57% 🟢
└─ Status: Above target (5%), bot will auto-sell next cycle
```

---

## 🔄 Real-time Update Flow

```
Every poll cycle (every N seconds):

[1] Fetch market data
    └─ current_price = await gateway.get_price(symbol)

[2] Fetch position from DB
    ├─ position_size = sum(all purchases this epoch)
    ├─ total_cost = sum(all purchase costs)
    └─ avg_price = total_cost / position_size

[3] Calculate PNL
    ├─ current_value = position_size * current_price
    ├─ unrealized_pnl_usdt = current_value - total_cost
    └─ unrealized_pnl_pct = (unrealized_pnl_usdt / total_cost) * 100

[4] Broadcast via WebSocket
    └─ Send: {unrealized_pnl_pct, current_price, status}

[5] UI updates in real-time
    ├─ Bot card shows: %PNL with color coding
    ├─ Chart updates: plot new data point
    └─ Status: Check if >= target_profit_pct
```

---

## 🎨 Color Coding for %PNL

```
%PNL Range        | Color    | Icon  | Meaning
────────────────────────────────────────────
< -5%             | 🔴 Red   | ⬇️  | Major loss (rare, DCA downside only)
-5% to -1%        | 🔴 Red   | ⬇️  | Drawdown
-1% to 0%         | 🟡 Yellow| →   | Flat
0% to 2%          | ⚪ Gray  | →   | Accumulating, small profit
2% to 5%          | 🟡 Yellow| ↗️  | Approaching target
>= target (5%)    | 🟢 Green | ⬆️  | TARGET REACHED!
```

### Visual Examples

```
louise_btc_001                louise_eth_001               louise_sol_001
BTC/USDT                      ETH/USDT                     SOL/USDT

%PNL: -0.50% 🔴              %PNL: +1.20% ⚪              %PNL: +5.50% 🟢
(Below cost, still buying)    (Small profit, accumulating)  (TARGET! Auto-exit)
```

---

## 📊 Widget Updates for Dashboard

### Bot Card (Dashboard Grid)

```
BEFORE:
┌────────────────────┐
│ louise_btc_001     │
│ BTC/USDT           │
│ Status: ✅ RUNNING │
│ Price: $42,500     │
│ Position: 0.05 BTC │
│ Cost: $1,200       │
│ [Enable/Disable]   │
└────────────────────┘

AFTER:
┌────────────────────────┐
│ louise_btc_001         │
│ BTC/USDT               │
│ Status: ✅ RUNNING     │
│ Price: $42,500 🔄     │ (updates live)
│ %PNL: +2.81% 🟡       │ (COLOR-CODED, LARGE FONT)
│ Position: 0.05 BTC    │
│ Cost: $1,200          │
│ [Enable/Disable]      │
└────────────────────────┘
```

**%PNL Styling:**
- Large font (18-24pt, prominent)
- Color-coded background or text
- Icon indicator (📈🔴🟢)
- Updates every 5 seconds via WebSocket

### Mini PNL Indicator (Compact View)

```
louise_btc_001   Status: RUNNING   Price: $42,500   %PNL: +2.81% 🟡   [Details]
louise_eth_001   Status: PAUSED    ...              %PNL: -0.50% 🔴   [Details]
louise_sol_001   Status: SHUTDOWN  ...              %PNL: +6.20% 🟢   [Details]
```

---

## 📈 Detailed View: PNL Section

### Bot Details Page

```
╔════════════════════════════════════════════════════════════════╗
║  louise_btc_001 (BTC/USDT)                                     ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  MARKET & POSITION                                             ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Current Price (Live): $42,500 ↑                          │ ║
║  │ Last Buy Price:       $41,200                            │ ║
║  │ Avg Buy Price (VWAP): $40,850                            │ ║
║  │ Price Change (4h):    +$800 (+1.92%)                    │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  POSITION & PROFITABILITY                                      ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Position Size:    0.0512 BTC                             │ ║
║  │ Total Cost:       $2,093.12                              │ ║
║  │ Current Value:    $2,152.00                              │ ║
║  │                                                          │ ║
║  │ Unrealized P&L:   +$58.88                                │ ║
║  │ Unrealized P&L %: +2.81% 🟡                              │ ║
║  │                   ╔════════════════════════╗             │ ║
║  │                   ║ Target: 5.00% (████░░░)║             │ ║
║  │                   ║ Need: +$46.65 more     ║             │ ║
║  │                   ╚════════════════════════╝             │ ║
║  │                                                          │ ║
║  │ Status: ACCUMULATING (need +2.19% to exit)              │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  PNL TREND (Last 24h)                                           ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │    %PNL                                                  │ ║
║  │   +10%│                                                  │ ║
║  │       │                                  ╱═════          │ ║
║  │    +5%│                            ╱════╱               │ ║
║  │       │                       ╱═══╱                     │ ║
║  │     0%│══════════════════════╱                           │ ║
║  │       │                                                  │ ║
║  │    -5%│                                                  │ ║
║  │       └──────────────────────────────────────            │ ║
║  │       0h         6h        12h       18h      24h        │ ║
║  │                                                          │ ║
║  │  Min: -0.50%  Avg: +1.20%  Max: +3.50%                  │ ║
║  │  Current (now): +2.81%                                  │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

---

## 🌐 WebSocket Payload Update

### Current Structure

```json
{
  "bot_id": "louise_btc_001",
  "timestamp": "2026-05-11T14:35:00Z",
  "current_price": 42500.50,
  "last_buy_price": 41200.00,
  "avg_buy_price": 40850.00,
  "position_size": 0.0512,
  "total_cost": 2093.12,
  "current_value": 2152.00,
  "free_balance": 450.00,
  "locked_balance": 100.00,
  "equity": 15850.00,
  "status": "ACCUMULATING",
  "next_poll_in_seconds": 272
}
```

### UPDATED with PNL

```json
{
  "bot_id": "louise_btc_001",
  "timestamp": "2026-05-11T14:35:00Z",
  
  "current_price": 42500.50,
  "last_buy_price": 41200.00,
  "avg_buy_price": 40850.00,
  
  "position_size": 0.0512,
  "total_cost": 2093.12,
  "current_value": 2152.00,
  
  "unrealized_pnl_usdt": 58.88,           ← NEW
  "unrealized_pnl_pct": 2.81,             ← NEW (CRITICAL)
  "target_profit_pct": 5.0,               ← NEW (for progress bar)
  "progress_to_target": 56.2,             ← NEW (2.81/5.0 * 100)
  
  "free_balance": 450.00,
  "locked_balance": 100.00,
  "equity": 15850.00,
  
  "status": "ACCUMULATING",
  "num_purchases": 8,
  "epoch_duration_minutes": 127,
  
  "next_poll_in_seconds": 272,
  "last_buy_at": "2026-05-11T14:32:45Z"
}
```

**Key additions:**
- `unrealized_pnl_pct` — **The main metric operator watches**
- `unrealized_pnl_usdt` — Dollar amount
- `target_profit_pct` — For progress visualization
- `progress_to_target` — Percentage toward exit

---

## 📋 PNL Calculation in Louise Bot

### Method 1: Simple (Per Cycle)

**File:** `runtime/bot/louise.py`

```python
async def _calculate_unrealized_pnl(self) -> tuple[float, float]:
    """
    Calculate unrealized P&L in USDT and %.
    
    Returns:
        (pnl_usdt, pnl_pct)
    """
    # Fetch current position from DB
    position = await self.db.get_current_position(
        self.config.bot_id, 
        self.current_epoch_id
    )
    
    if not position or position.position_size == 0:
        return (0.0, 0.0)
    
    # Get current market price
    current_price = await self.gateway.get_symbol_price_async(
        self.config.symbol
    )
    
    # Calculate
    current_value = position.position_size * current_price
    pnl_usdt = current_value - position.total_cost
    pnl_pct = (pnl_usdt / position.total_cost) * 100 if position.total_cost > 0 else 0.0
    
    return (pnl_usdt, pnl_pct)
```

### Method 2: With Caching (Optimized)

```python
class LouiseBot:
    def __init__(self, ...):
        # ... init ...
        self._cached_pnl = {
            "usdt": 0.0,
            "pct": 0.0,
            "timestamp": None,
            "ttl_seconds": 2  # Cache valid for 2 seconds
        }
    
    async def get_unrealized_pnl(self, use_cache=True) -> tuple[float, float]:
        """Get P&L, optionally from cache"""
        
        now = datetime.utcnow()
        
        # Check cache
        if use_cache and self._cached_pnl["timestamp"]:
            age = (now - self._cached_pnl["timestamp"]).total_seconds()
            if age < self._cached_pnl["ttl_seconds"]:
                return (self._cached_pnl["usdt"], self._cached_pnl["pct"])
        
        # Calculate fresh
        pnl_usdt, pnl_pct = await self._calculate_unrealized_pnl()
        
        # Update cache
        self._cached_pnl = {
            "usdt": pnl_usdt,
            "pct": pnl_pct,
            "timestamp": now
        }
        
        return (pnl_usdt, pnl_pct)
```

---

## 📊 Hub Summary: Total PNL

### Dashboard Top Section

```
╔════════════════════════════════════════════════════════════════╗
║  LOUISE BOT HUB SUMMARY                                        ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  Active Bots: 3              Completed Epochs: 12             ║
║  Total Portfolio: $4,850     Hub P&L: +$127.50  (+2.71%) 🟡  ║
║                              ↑↑↑                              ║
║  Hub-wide Unrealized P&L (sum of all active positions)       ║
║                                                                ║
║  Free Balance: $2,450        Locked: $100                     ║
║  Equity: $15,850             Margin: 250%                     ║
║                                                                ║
║  [Equity Chart - Last 24h] ──────────────────────────────     ║
║  $16k │                    ╱╲                                 ║
║  $15k │                   ╱  ╲___                             ║
║  $14k │___╱╲             ╱                                    ║
║       └─────────────────────────────────                      ║
║       0h        6h      12h      18h    24h                   ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

**Hub P&L = Sum of all unrealized PNLs from active bots**

---

## 📱 Mobile/List View Format

### Compact Bot List (Easy Scanning)

```
Bot Instance          Status    Price      %PNL      Position
──────────────────────────────────────────────────────────────
louise_btc_001        ✅ RUN    $42.5k    +2.81% 🟡   0.05 BTC
louise_eth_001        ✅ RUN    $2,145    -0.50% 🔴   2.30 ETH
louise_sol_001        🔴 SHUT   $151.20   +6.20% 🟢   [closed]
louise_ada_001        ⏸️ PAUSE  $1.05     +1.50% ⚪   50 ADA
louise_bnb_001        ✅ RUN    $2,850    +4.99% 🟡   0.10 BTC
```

Operator can scan all %PNL values instantly, see which bots are close to exit.

---

## 🔔 Alert Triggers Based on PNL

### Auto-Exit Condition

```python
IF unrealized_pnl_pct >= target_profit_pct:
    # Auto-sell all
    await self._execute_market_sell_all()
    # Close epoch
    await self.db.close_epoch(epoch_id, profit=unrealized_pnl_pct)
    # Broadcast success
    await self._send_alert("Epoch closed successfully: +{unrealized_pnl_pct}%")
```

### Operator Alerts

| Event | Condition | Alert |
|-------|-----------|-------|
| **Approaching Target** | %PNL >= 4.5% | "louise_btc close to exit (+4.5%)" |
| **Target Reached** | %PNL >= 5.0% | "louise_btc SOLD: +5.0% profit! ✅" |
| **Significant Loss** | %PNL <= -5.0% | "louise_eth heavy drawdown: -5.2% ⚠️" |
| **Progress Update** | Every 30 min | "Hub portfolio +1.8%, 3 bots active" |

---

## 🧮 Database Schema: PNL Tracking

### Louise Purchases Table (Add Column)

```sql
ALTER TABLE louise_purchases ADD COLUMN (
    pnl_at_purchase_time FLOAT,  -- %PNL immediately after this buy
    timestamp_last_pnl_update TIMESTAMP
);
```

### Louise Epochs Table (Add Columns)

```sql
ALTER TABLE louise_epochs ADD COLUMN (
    peak_pnl_pct FLOAT,         -- Maximum %PNL during epoch
    peak_pnl_timestamp TIMESTAMP, -- When peak occurred
    pnl_at_close FLOAT,         -- Final %PNL when closed
    pnl_volatility FLOAT        -- Std dev of %PNL (optional)
);
```

### Louise Balance Metrics Table (Log %PNL)

```sql
CREATE TABLE louise_pnl_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id TEXT NOT NULL,
    epoch_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    unrealized_pnl_usdt FLOAT,
    unrealized_pnl_pct FLOAT,
    position_size FLOAT,
    position_value_usdt FLOAT,
    current_price FLOAT,
    FOREIGN KEY(bot_id) REFERENCES louise_bots(bot_id),
    FOREIGN KEY(epoch_id) REFERENCES louise_epochs(epoch_id)
);
```

This table provides historical PNL data for charting and analysis.

---

## 🎯 Implementation Checklist

### Phase 1: Core PNL Calculation

- [ ] Add `_calculate_unrealized_pnl()` method to LouiseBot
  - [ ] Fetch position from DB
  - [ ] Get current market price
  - [ ] Calculate: current_value = position_size * price
  - [ ] Calculate: pnl_usdt = current_value - total_cost
  - [ ] Calculate: pnl_pct = (pnl_usdt / total_cost) * 100

- [ ] Add PNL fields to WebSocket payload
  - [ ] unrealized_pnl_usdt
  - [ ] unrealized_pnl_pct
  - [ ] target_profit_pct
  - [ ] progress_to_target

- [ ] Add check_exit_condition() based on %PNL
  - [ ] IF pnl_pct >= target → market sell all, close epoch

### Phase 3: UI Display

- [ ] Update bot card widget
  - [ ] Display %PNL prominently (large font)
  - [ ] Color-code based on %PNL value
  - [ ] Add icon (📈🔴🟢)
  - [ ] Update every 5 seconds from WebSocket

- [ ] Update details page
  - [ ] Show unrealized_pnl_usdt and _pct
  - [ ] Add progress bar toward target
  - [ ] Add %PNL trend chart (last 24h)

- [ ] Update dashboard summary
  - [ ] Show hub-wide P&L (sum of all active)
  - [ ] Color-code based on hub P&L

- [ ] Add alerts
  - [ ] Approaching target (>= 4.5%)
  - [ ] Target reached (auto-exit)
  - [ ] Significant drawdown (optional)

### Phase 4: Testing

- [ ] Unit tests
  - [ ] PNL calculation accuracy
  - [ ] Color-coding logic
  - [ ] Target detection

- [ ] Integration tests
  - [ ] WebSocket payload includes PNL
  - [ ] UI updates on PNL change
  - [ ] Auto-exit triggers at target

---

## 📈 Example Scenarios

### Scenario 1: Steady Profit Growth

```
T=0min: Create bot
└─ %PNL = 0% (no purchases yet)

T=5min: First purchase @ $40,000
└─ %PNL = 0% (cost basis set)

T=10min: Price stays $40,000, no new buy
└─ %PNL = 0%

T=15min: Price drops to $39,000, second buy
├─ Total cost: $200
├─ Position: 0.00505 BTC
├─ Current value: 0.00505 × $39,000 = $197
└─ %PNL = ($197 - $200) / $200 = -1.5%

T=20min: Price rises to $42,000
├─ Current value: 0.00505 × $42,000 = $212
├─ %PNL = ($212 - $200) / $200 = +6.0%
└─ Status: TARGET REACHED! Auto-sell triggered ✅
```

**UI Timeline:**
```
T=0: %PNL: 0% (neutral)
T=5: %PNL: 0% (just bought)
T=10: %PNL: 0% (holding)
T=15: %PNL: -1.5% 🔴 (down from cost)
T=20: %PNL: +6.0% 🟢 (TARGET! Selling...)
```

### Scenario 2: Hub Monitoring

```
Dashboard shows 5 active bots:

louise_btc_001: %PNL: +2.81% 🟡 (near target)
louise_eth_001: %PNL: +0.50% ⚪ (accumulating)
louise_sol_001: %PNL: -0.30% 🔴 (still buying dip)
louise_ada_001: %PNL: +4.95% 🟡 (almost target!)
louise_bnb_001: %PNL: +1.20% ⚪ (growing steady)

────────────────────────────────────
Hub Total P&L: +1.83% 🟡

Operator sees: BTC and ADA close to exit, ETH and BNB accumulating,
SOL slightly underwater but holding. Everything on track.
```

---

## 🔍 Real-time Monitoring Workflow

**Operator's View:**

```
1. Open dashboard
   └─ Sees 5 bot cards with %PNL values
      ├─ louise_btc: +2.8% (almost exit)
      ├─ louise_eth: +0.5% (early stage)
      └─ etc.

2. Tap louise_btc card
   └─ Opens detail view
      ├─ Sees %PNL: +2.8%
      ├─ Progress bar: [████░░] toward 5% target
      ├─ %PNL trend chart: shows rise over 2 hours

3. Continues monitoring
   └─ 30 seconds later, WebSocket updates
      ├─ louise_btc: +2.9% (price rose)
      ├─ louise_eth: +0.6% (steady)

4. Alert: louise_btc approaching target
   └─ Notification: "louise_btc at +4.9%, near exit target"

5. Moments later: louise_btc hits target
   └─ Notification: "louise_btc SOLD: +5.0% profit! ✅"
   └─ Bot status changes to SHUTDOWN
   └─ Epoch logged as successful
```

**No confusion, full visibility, automatic exits.**

---

## 💡 Why This Matters

### Transparency
- Operator knows EXACTLY how each bot is performing
- No guessing, no manual calculations
- Live data every 5 seconds

### Quick Decision Making
- Can see which bots are close to exit
- Can see portfolio health at a glance
- Can identify outliers (one bot highly negative)

### Safety
- Automatic exit at target prevents overholding
- If market crashes suddenly, operator sees it immediately (%PNL drops)
- Color-coding makes problems visible instantly

### Psychology
- Seeing green (+5%) feels great when bot exits successfully
- Seeing yellow (accumulating) shows progress
- Seeing red (drawdown) is clear signal to investigate

---

**Status:** Ready for Phase 1 implementation  
**Effort:** ~4-6 hours total (calculation + UI + WebSocket)  
**Impact:** HIGH (critical for real-time monitoring)
