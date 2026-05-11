# Louise Bot Integration Flow: Balance Verification + Equity Metrics

**Document:** Technical flow showing how BalanceChecker integrates with Louise bot and UI  
**Status:** Implementation guide for Phase 1-3

---

## 🔄 Complete Execution Flow

### Timeline: Louise Bot Poll Cycle (Every N Seconds)

```
T=0: Poll Interval Triggers
│
├─ [1] BALANCE CHECK
│  │
│  ├─ Louise.poll_market() called
│  ├─ await balance_checker.check_and_refresh(symbol)
│  │  │
│  │  ├─ Check cache: is data < 5 seconds old?
│  │  │  ├─ YES → return cached AccountBalance (no API call)
│  │  │  └─ NO → continue to API call
│  │  │
│  │  └─ API Call: gateway.get_account_async()
│  │     ├─ Extract: USDT free, locked
│  │     ├─ Extract: Position in symbol asset
│  │     ├─ Fetch: Current price
│  │     ├─ Calculate: Equity = cash + (position * price)
│  │     └─ Return: AccountBalance snapshot
│  │
│  └─ Cache result for next 5 seconds
│
├─ [2] BALANCE VALIDATION
│  │
│  ├─ Check: free_balance >= $8 USDT?
│  │
│  ├─ IF NO (insufficient balance):
│  │  │
│  │  ├─ db.update_bot_status(bot_id, "PAUSED_LOW_BALANCE")
│  │  ├─ send_alert("Insufficient balance, deposit funds")
│  │  ├─ broadcast_metrics(balance, None) → WebSocket
│  │  └─ RETURN (skip price check, no wasted API)
│  │
│  └─ IF YES (sufficient balance):
│     └─ continue to next step
│
├─ [3] MARKET PRICE CHECK
│  │
│  ├─ Fetch: current_price = gateway.get_symbol_price()
│  ├─ Get: last_buy_price from database
│  │
│  └─ Compare: current_price < last_buy_price?
│
├─ [4] BUY CONDITION EVALUATION
│  │
│  ├─ IF NO (price above or equal last buy):
│  │  │
│  │  ├─ db.update_poll_timestamp(bot_id)
│  │  ├─ broadcast_metrics(balance, current_price)
│  │  └─ Log: "Holding, price above last_buy"
│  │
│  └─ IF YES (price below last buy):
│     └─ continue to execution
│
├─ [5] EXECUTE BUY
│  │
│  ├─ Place market order: buy_volume at current price
│  ├─ Get order_id from response
│  ├─ Wait for fill confirmation
│  │
│  └─ IF order filled:
│     │
│     ├─ db.record_purchase(
│     │    bot_id, epoch_id, price, volume, cost, order_id
│     │  )
│     │
│     ├─ Recalculate metrics:
│     │  ├─ position_size += volume
│     │  ├─ total_cost += cost
│     │  ├─ avg_buy_price = total_cost / position_size
│     │
│     ├─ Check profit target:
│     │  ├─ current_value = position_size * current_price
│     │  ├─ unrealized_pct = (current_value - total_cost) / total_cost * 100
│     │  │
│     │  └─ IF unrealized_pct >= target_profit:
│     │     │
│     │     ├─ Execute market SELL all
│     │     ├─ Record sale in ledger
│     │     ├─ db.close_epoch(epoch_id, profit_pct, duration)
│     │     ├─ db.update_bot_status(bot_id, "SHUTDOWN")
│     │     └─ Send success alert
│     │
│     └─ broadcast_metrics(balance, current_price)
│
└─ [6] BROADCAST METRICS TO UI
   │
   ├─ Gather all metrics:
   │  ├─ current_price (from step 3)
   │  ├─ last_buy_price (from DB)
   │  ├─ avg_buy_price (calculated)
   │  ├─ position_size (from DB)
   │  ├─ total_cost (from DB)
   │  ├─ free_balance (from step 1)
   │  ├─ locked_balance (from step 1)
   │  ├─ equity_usdt (from step 1)
   │  ├─ unrealized_pct (calculated)
   │  ├─ bot_status (from DB)
   │  └─ next_poll_countdown
   │
   ├─ Send via WebSocket:
   │  └─ /ws/louise/metrics/{bot_id}
   │
   └─ UI receives and updates in real-time
      └─ BotCard metrics update
      └─ Dashboard equity chart updates
      └─ BalanceCard shows latest free/locked/equity

T=N+poll_interval: Repeat
```

---

## 📊 Data Flow Diagram

```
LOUISE BOT                 BINANCE GATEWAY          DATABASE          WEBSOCKET/UI
    │                           │                       │                   │
    ├─ poll_market()            │                       │                   │
    │  │                        │                       │                   │
    │  └─ check_and_refresh()   │                       │                   │
    │      │                    │                       │                   │
    │      ├─ [cache valid?]────────────────────────────┤                   │
    │      │                    │                       │                   │
    │      └─ get_account()     │                       │                   │
    │         └────────────────→│                       │                   │
    │                           │                       │                   │
    │      ←───────── AccountBalance ─────────┘         │                   │
    │                           │                       │                   │
    ├─ free_balance >= $8?      │                       │                   │
    │                           │                       │                   │
    ├─ IF NO → pause            │                       │                   │
    │  └────────────────────────────────────→ update status               │
    │                           │               │                           │
    │  └────────────────────────────────────────────────→ send ALERT ──────→│
    │                           │               │                           │
    │  └────────────────────────────────────────────────→ broadcast metrics ┤
    │                           │               │              │            │
    ├─ IF YES → continue        │               │              │            │
    │                           │               │              │            │
    ├─ get_symbol_price()       │               │              │            │
    │  └────────────────────────→│               │              │            │
    │         ←──── current_price ──────────────┘              │            │
    │                           │               │              │            │
    ├─ current_price < last_buy_price?                        │            │
    │                           │               │              │            │
    ├─ IF YES → execute_buy()    │               │              │            │
    │  │                        │               │              │            │
    │  ├─ place_market_order()  │               │              │            │
    │  │  └────────────────────→│               │              │            │
    │  │         ←────── order_id ─────────────┘              │            │
    │  │                        │               │              │            │
    │  ├─ record_purchase()     │               │              │            │
    │  │  └────────────────────────────────────→ INSERT purchase           │
    │  │                        │               │              │            │
    │  ├─ check_profit_target() │               │              │            │
    │  │                        │               │              │            │
    │  └─ IF target_reached:    │               │              │            │
    │     ├─ market_sell_all()  │               │              │            │
    │     │  └────────────────→│               │              │            │
    │     └─ close_epoch()      │               │              │            │
    │        └────────────────────────────────→ UPDATE epoch to CLOSED   │
    │                           │               │              │            │
    ├─ broadcast_metrics()      │               │              │            │
    │  ├─ gather metrics        │               │              │            │
    │  └────────────────────────────────────────────────────────────────→│
    │                           │               │              │         UI │
    │                           │               │              │      Updates│
```

---

## 🎯 Key Integration Points

### 1. Louise Bot Runner ↔ BalanceChecker

**File:** `runtime/bot/louise.py`

```python
class LouiseBot:
    def __init__(self, config, binance_gateway, db_session):
        # ... other init ...
        self.balance_checker = BalanceChecker(binance_gateway)
        self.metrics_cache = {}
    
    async def poll_market(self):
        """Main execution loop"""
        try:
            # [1] Balance verification
            balance = await self.balance_checker.check_and_refresh(
                self.config.symbol
            )
            
            # [2] Check if sufficient funds
            if not balance.can_trade:
                await self._handle_low_balance(balance)
                return
            
            # [3-5] Price check → Buy execution
            # ... existing logic ...
            
            # [6] Broadcast metrics with fresh balance data
            await self._broadcast_metrics(balance, current_price)
            
        except Exception as e:
            logger.error(f"Poll failed: {e}")
            await self._handle_error(e)
```

### 2. Database Integration

**Schema Updates:**

```sql
-- Add to louise_bots table:
ALTER TABLE louise_bots ADD COLUMN (
    last_balance_check TIMESTAMP,
    last_free_balance FLOAT,
    last_equity FLOAT,
    balance_check_failures INT DEFAULT 0
);

-- Add metrics tracking table (optional):
CREATE TABLE louise_balance_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    bot_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    free_balance FLOAT,
    locked_balance FLOAT,
    equity FLOAT,
    position_size FLOAT,
    unrealized_pct FLOAT,
    FOREIGN KEY(bot_id) REFERENCES louise_bots(bot_id)
);
```

### 3. WebSocket Broadcasting

**File:** `runtime/api/routers/louise.py`

```python
async def broadcast_metrics(bot_id: str, balance: AccountBalance, metrics: dict):
    """Send fresh metrics to WebSocket subscribers"""
    
    payload = {
        "bot_id": bot_id,
        "timestamp": datetime.utcnow().isoformat(),
        
        # From BalanceChecker
        "free_balance": balance.free_balance,
        "locked_balance": balance.locked_balance,
        "total_balance": balance.total_balance,
        "equity": balance.equity_usdt,
        "margin_level": balance.margin_level,
        "can_trade": balance.can_trade,
        
        # From Louise metrics
        "current_price": metrics.get("current_price"),
        "last_buy_price": metrics.get("last_buy_price"),
        "avg_buy_price": metrics.get("avg_buy_price"),
        "position_size": metrics.get("position_size"),
        "total_cost": metrics.get("total_cost"),
        "unrealized_pnl": metrics.get("unrealized_pnl"),
        "unrealized_pct": metrics.get("unrealized_pct"),
        "status": metrics.get("status"),
        "next_poll_in": metrics.get("next_poll_in"),
    }
    
    # Broadcast to all WebSocket subscribers
    await websocket_manager.broadcast(
        f"/ws/louise/metrics/{bot_id}",
        payload
    )
```

### 4. UI Real-time Updates

**File:** `desktop_shell/lib/providers/louise_metrics_provider.dart`

```dart
class LouiseMetricsProvider with ChangeNotifier {
  StreamSubscription<dynamic>? _websocketSubscription;
  
  void subscribeToMetrics(String botId) {
    _websocketSubscription = websocketService
        .stream("/ws/louise/metrics/$botId")
        .listen((data) {
          // Update metrics in real-time
          _currentMetrics = BotMetrics.fromJson(data);
          
          // Update UI
          notifyListeners();
          
          // Update equity chart
          _equityHistory.add(
            EquityPoint(
              timestamp: DateTime.parse(data['timestamp']),
              equity: data['equity'].toDouble(),
              freeBalance: data['free_balance'].toDouble(),
            ),
          );
          
          // Emit alerts if needed
          if (!data['can_trade']) {
            _alertService.showLowBalanceAlert();
          }
          if (data['unrealized_pct'] >= targetProfit) {
            _alertService.showTargetReachedAlert();
          }
        });
  }
}
```

---

## 📈 UI Components Updated

### 1. Dashboard Hub Summary Card

```
BEFORE:
┌──────────────────────────┐
│ Active Bots: 3           │
│ Completed Epochs: 12     │
│ Total Portfolio: $4,850  │
└──────────────────────────┘

AFTER:
┌──────────────────────────────────────┐
│ Active Bots: 3                       │
│ Completed Epochs: 12                 │
│ Total Portfolio: $4,850              │
│ Free Balance: $2,450 (avail)         │ ← NEW
│ Locked: $100 (in orders)             │ ← NEW
│ Margin Level: 250%                   │ ← NEW
│                                      │
│ [Equity Chart - Last 24h] ──────────→│ ← LIVE UPDATES
└──────────────────────────────────────┘
```

### 2. Bot Card Enhanced

```
BEFORE:
┌────────────────────┐
│ louise_btc_001     │
│ BTC/USDT           │
│ Status: ✅ RUNNING │
│ P&L: +2.8%         │
│ Cost: $1,200       │
└────────────────────┘

AFTER:
┌────────────────────┐
│ louise_btc_001     │
│ BTC/USDT           │
│ Status: ✅ RUNNING │
│ P&L: +2.8%         │
│ Cost: $1,200       │
│ Equity: $1,234     │ ← NEW
│ Free: $450 ✅      │ ← NEW
└────────────────────┘
```

### 3. Detail View Equity Section

```
BALANCE & EQUITY
┌─────────────────────────────────────┐
│ Free Balance:    $2,450             │
│ Locked Balance:  $100               │
│ Total Balance:   $2,550             │
│                                     │
│ Equity (Cash+Position): $15,850     │
│ Margin Level: 250% (if applicable)  │
│                                     │
│ [Equity Trend Chart]                │
│ $16k │     ╱─╲                       │
│      │    ╱   ╲                      │
│ $15k │   ╱     ╲___                  │
│      │__╱                            │
│  0h    6h  12h  18h  24h            │
│                                     │
│ Last Update: 2 seconds ago          │
└─────────────────────────────────────┘
```

---

## 🔔 Alert Flow

### Low Balance Alert

```
BalanceChecker detects: free_balance < $8
    ↓
Louise bot pauses: status = "PAUSED_LOW_BALANCE"
    ↓
Alert message:
{
  "bot_id": "louise_btc_001",
  "severity": "WARNING",
  "title": "Insufficient Balance",
  "message": "Free balance $3.50 < required $8.00",
  "recommendation": "Deposit at least $4.50 to resume bot",
  "action_url": "/deposit"
}
    ↓
UI displays alert dialog:
╔─────────────────────────────────────╗
│ ⚠️ louise_btc_001 Low Balance        │
├─────────────────────────────────────┤
│ Free Balance: $3.50                  │
│ Required: $8.00                      │
│ Shortfall: $4.50                     │
│                                     │
│ Bot paused. Deposit funds to resume  │
│ [DISMISS] [DEPOSIT NOW]              │
╚─────────────────────────────────────╝
    ↓
Operator deposits funds
    ↓
Next poll: BalanceChecker detects sufficient balance
    ↓
Louise bot resumes automatically: status = "ACCUMULATING"
    ↓
UI updates, bot continues trading
```

---

## 🚀 Performance Characteristics

### API Call Reduction

**Scenario:** 10 Louise bots, 1 with low balance

```
WITHOUT Balance Verification:
- Each bot: 1 price check + 1 failed buy attempt = 2 API calls
- 10 bots × 2 = 20 API calls per cycle
- 20 calls × 12 cycles/hour = 240 calls/hour
- If 1 bot low balance: 240 calls wasted on failed buys

WITH Balance Verification:
- Each bot: 1 balance check + 1 price check = 2 API calls
- 10 bots × 2 = 20 API calls per cycle
- Low-balance bot: 1 balance check, SKIP price check
- 9 bots × 2 + 1 bot × 1 = 19 API calls per cycle
- Savings: ~5% per cycle, compounding to 30%+ when multiple bots low

Weight Savings:
- 1 failed buy attempt = 24 API weight
- 12 cycles × 24 weight = 288 weight wasted per hour
- Per day: 288 × 24 = 6,912 weight saved per bot that's low
```

### Latency

```
Balance check cycle:
- Cache hit (< 5s old): ~10ms (in-memory)
- Cache miss (API call): ~300-500ms (network)
- Broadcasting metrics: ~50ms (WebSocket)

Total cycle time: 500-600ms (acceptable for 5-minute poll intervals)
```

---

## 🧪 Testing Strategy

### Unit Tests

```python
# test_balance_checker.py

async def test_balance_check_sufficient_funds():
    """Verify bot can trade when balance >= $8"""
    checker = BalanceChecker(mock_gateway)
    balance = await checker.check_and_refresh("BTCUSDT")
    assert balance.can_trade == True
    assert balance.free_balance >= 8.0

async def test_balance_check_insufficient_funds():
    """Verify bot pauses when balance < $8"""
    checker = BalanceChecker(mock_gateway_low_balance)
    balance = await checker.check_and_refresh("BTCUSDT")
    assert balance.can_trade == False
    assert balance.free_balance < 8.0

async def test_balance_caching():
    """Verify cache prevents redundant API calls"""
    checker = BalanceChecker(mock_gateway)
    
    # First call: API
    balance1 = await checker.check_and_refresh("BTCUSDT")
    assert mock_gateway.api_call_count == 1
    
    # Second call within 5s: cache hit
    balance2 = await checker.check_and_refresh("BTCUSDT")
    assert mock_gateway.api_call_count == 1  # No additional API call
    
    # Third call after 6s: cache miss
    await asyncio.sleep(6)
    balance3 = await checker.check_and_refresh("BTCUSDT")
    assert mock_gateway.api_call_count == 2

async def test_equity_calculation():
    """Verify equity = cash + position value"""
    checker = BalanceChecker(mock_gateway)
    balance = await checker.check_and_refresh("BTCUSDT")
    
    # Expected: $1000 cash + (0.1 BTC × $40,000) = $5,000
    assert balance.equity_usdt == pytest.approx(5000, rel=0.01)
```

### Integration Tests

```python
# test_louise_balance_integration.py

async def test_louise_pauses_when_low_balance():
    """Verify Louise bot pauses when balance insufficient"""
    bot = LouiseBot(config, mock_gateway_low, db)
    await bot.poll_market()
    
    # Check bot status
    status = await db.get_bot_status(bot.config.bot_id)
    assert status == "PAUSED_LOW_BALANCE"

async def test_louise_resumes_after_deposit():
    """Verify Louise bot resumes when balance restored"""
    bot = LouiseBot(config, mock_gateway_low, db)
    
    # Initial: low balance, bot pauses
    await bot.poll_market()
    assert await db.get_bot_status(bot.config.bot_id) == "PAUSED_LOW_BALANCE"
    
    # Simulate deposit: switch gateway to have more balance
    bot.balance_checker.gateway = mock_gateway_sufficient
    
    # Next poll: bot resumes
    await bot.poll_market()
    assert await db.get_bot_status(bot.config.bot_id) == "ACCUMULATING"
```

---

## 📋 Implementation Checklist

### Phase 1.2: Integration

- [ ] Integrate BalanceChecker into Louise bot runner
  - [ ] Import BalanceChecker in louise.py
  - [ ] Initialize in __init__
  - [ ] Call check_and_refresh() at start of poll_market()
  - [ ] Handle low-balance pause
  
- [ ] Update database schema
  - [ ] Add columns to louise_bots table
  - [ ] Create louise_balance_metrics table (optional)
  
- [ ] Implement WebSocket broadcasting
  - [ ] Gather balance + metrics in one payload
  - [ ] Broadcast to /ws/louise/metrics/{bot_id}

### Phase 2: API Endpoints

- [ ] GET /api/v1/louise/bots/{bot_id}/balance
- [ ] GET /api/v1/louise/stats/account (hub-wide)

### Phase 3: UI Updates

- [ ] Update dashboard hub summary card
- [ ] Add equity chart widget
- [ ] Add balance card to bot details
- [ ] Add low-balance alert dialog
- [ ] Subscribe to WebSocket metrics stream
- [ ] Update real-time on UI

---

**Status:** Ready for Phase 1 implementation  
**Next:** Integrate BalanceChecker into louise.py runner
