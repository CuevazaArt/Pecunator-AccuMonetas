# Balance Verification Feature for Louise Bot

**Feature Request:** From production feedback (previous bot)  
**Problem:** Unnecessary API calls when minimum funds not available  
**Solution:** Proactive balance check + live equity metrics refresh  
**Status:** Ready for implementation in Phase 1

---

## 🎯 Problem Statement

### Current Inefficiency

Without pre-execution balance verification:

```
Louise Poll Cycle (every 5 min):
1. Fetch market price (1 API weight)
2. Calculate if buy condition met
3. IF buy → Place market order (24 API weight)
4. IF order fails (insufficient balance) → Error + Alert
5. Retry next cycle (wasted API weight)

Scenario: Account has $5 available, buy_volume = $100
├─ Every 5 min → price check (1 weight)
├─ Failed buy attempts (24 weight wasted)
├─ Accumulated waste → 288 failed checks = 6,912 wasted weight/day
└─ Result: High API weight consumption, low trading productivity
```

### Business Impact

- **Wasted API Weight:** Each failed buy = 24 weight units
- **Delayed Feedback:** Operator doesn't know immediately funds are low
- **Poor UX:** Bot appears "stuck" when just out of money
- **No Equity Insights:** UI metrics stale, doesn't refresh account health

---

## ✅ Solution: Proactive Balance Verification

### Core Concept

**Before each buy attempt, verify:**
1. ✅ Account has minimum $8 USDT available (free balance)
2. ✅ If insufficient → Pause bot, don't waste API weight
3. ✅ **Opportunistic refresh:** Use balance check to fetch fresh account metrics
   - Equity (total portfolio value)
   - Free balance (available to trade)
   - Locked balance (in orders)
   - Margin level (if margin enabled)

### API Efficiency Gain

```
New Flow with Balance Verification:
1. [Every poll] Check balance (1 call to Account endpoint)
2. IF free_balance < $8 → Pause bot, return (no order attempt)
3. IF free_balance >= $8 → Proceed to price check + buy

Result:
├─ Only 1 API call per cycle (balance check = lightweight)
├─ NO wasted 24-weight buy attempts when funds low
├─ Fresh account data available for UI metrics
└─ Savings: ~6,912 weight/day when account < $8
```

---

## 🏗️ Implementation Architecture

### 1. Balance Checker Module

**File:** `runtime/core/balance_checker.py`

```python
from dataclasses import dataclass
from datetime import datetime
from binance.exceptions import BinanceAPIException

@dataclass
class AccountBalance:
    """Fresh account metrics snapshot"""
    free_balance: float         # Available to trade (USDT)
    locked_balance: float       # In open orders (USDT)
    total_balance: float        # Free + locked
    equity_usdt: float          # Total account value
    margin_level: float         # If margin enabled (e.g., 500%)
    timestamp: datetime
    

class BalanceChecker:
    """Lightweight balance verification + metrics refresh"""
    
    def __init__(self, binance_gateway):
        self.gateway = binance_gateway
        self.min_free_balance = 8.0  # Minimum USDT to trade
        
    async def check_and_refresh(self, symbol: str) -> AccountBalance:
        """
        Check if account has minimum balance + refresh equity metrics
        
        Returns:
            AccountBalance: Current account state
            
        Raises:
            BinanceAPIException: If account endpoint fails
        """
        try:
            # Single API call: Account endpoint
            account = await self.gateway.get_account_async()
            
            # Parse USDT balance
            usdt_asset = next(
                (a for a in account['balances'] if a['asset'] == 'USDT'),
                None
            )
            
            free_balance = float(usdt_asset['free']) if usdt_asset else 0.0
            locked_balance = float(usdt_asset['locked']) if usdt_asset else 0.0
            total_balance = free_balance + locked_balance
            
            # Calculate equity (simplified: cash + position values)
            # For multi-asset accounts, sum all assets converted to USDT
            equity = await self._calculate_equity(account, symbol)
            
            # Margin level (if applicable)
            margin_level = account.get('totalUserAsset', {}).get('totalAssetOfBtc')
            
            balance_snapshot = AccountBalance(
                free_balance=free_balance,
                locked_balance=locked_balance,
                total_balance=total_balance,
                equity_usdt=equity,
                margin_level=margin_level or 0.0,
                timestamp=datetime.utcnow()
            )
            
            return balance_snapshot
            
        except BinanceAPIException as e:
            logger.error(f"Balance check failed: {e}")
            raise
    
    async def has_minimum_balance(self, symbol: str) -> bool:
        """
        Quick check: does account have >= $8 free?
        
        Returns:
            bool: True if free_balance >= min_free_balance
        """
        balance = await self.check_and_refresh(symbol)
        return balance.free_balance >= self.min_free_balance
    
    async def _calculate_equity(self, account: dict, symbol: str) -> float:
        """
        Calculate total account equity in USDT
        
        Includes:
        - Cash (USDT balance)
        - Position values (BTC, ETH, etc. * current price)
        - Open order values
        """
        usdt_balance = next(
            (float(a['free']) + float(a['locked']) 
             for a in account['balances'] if a['asset'] == 'USDT'),
            0.0
        )
        
        # For Louise bot tracking specific symbol
        # Get position in that asset
        asset = symbol.replace('/USDT', '').replace('USDT', '')
        asset_balance = next(
            (float(a['free']) + float(a['locked'])
             for a in account['balances'] if a['asset'] == asset),
            0.0
        )
        
        if asset_balance > 0:
            # Fetch current price
            current_price = await self.gateway.get_symbol_price_async(symbol)
            position_value = asset_balance * current_price
            return usdt_balance + position_value
        
        return usdt_balance
```

### 2. Integration with Louise Bot

**File:** `runtime/bot/louise.py`

```python
class LouiseBot:
    def __init__(self, config, binance_gateway, db_session):
        self.config = config
        self.gateway = binance_gateway
        self.db = db_session
        self.balance_checker = BalanceChecker(binance_gateway)
        self.last_balance_refresh = None
        
    async def poll_market(self):
        """Main polling loop (runs every poll_interval_seconds)"""
        try:
            # STEP 1: Check minimum balance (1 API call, no weight waste)
            balance = await self.balance_checker.check_and_refresh(self.config.symbol)
            
            # Store balance snapshot for UI metrics
            self._cache_balance_metrics(balance)
            
            # STEP 2: If insufficient funds, pause and alert
            if balance.free_balance < self.balance_checker.min_free_balance:
                await self._handle_insufficient_balance(balance)
                return
            
            # STEP 3: Proceed with normal flow
            current_price = await self.gateway.get_symbol_price_async(
                self.config.symbol
            )
            
            # Check buy condition
            last_buy_price = self._get_last_buy_price()
            
            if current_price < last_buy_price:
                # Execute buy (we know balance is sufficient)
                await self._execute_buy(current_price)
            
            # Broadcast updated metrics to UI
            await self._broadcast_metrics(balance, current_price)
            
        except Exception as e:
            logger.error(f"Poll failed: {e}")
            await self._handle_error(e)
    
    async def _handle_insufficient_balance(self, balance: AccountBalance):
        """Graceful handling when funds < $8"""
        status = "PAUSED_LOW_BALANCE"
        
        # Update bot status in DB
        await self.db.update_bot_status(
            self.config.bot_id,
            status,
            f"Insufficient balance. Free: ${balance.free_balance:.2f}"
        )
        
        # Alert operator
        alert_msg = {
            "bot_id": self.config.bot_id,
            "symbol": self.config.symbol,
            "event": "INSUFFICIENT_BALANCE",
            "free_balance": balance.free_balance,
            "required": self.balance_checker.min_free_balance,
            "action": "Deposit funds to resume",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self._send_alert(alert_msg)
        
        # Still broadcast the balance metrics for UI visibility
        await self._broadcast_metrics(balance, None)
    
    def _cache_balance_metrics(self, balance: AccountBalance):
        """Store balance data for quick UI access"""
        self.last_balance_refresh = {
            "timestamp": balance.timestamp,
            "free_balance": balance.free_balance,
            "locked_balance": balance.locked_balance,
            "total_balance": balance.total_balance,
            "equity": balance.equity_usdt
        }
    
    async def _broadcast_metrics(self, balance: AccountBalance, current_price: float = None):
        """Send fresh metrics to WebSocket subscribers"""
        metrics = {
            "bot_id": self.config.bot_id,
            "symbol": self.config.symbol,
            "current_price": current_price,
            "free_balance": balance.free_balance,
            "locked_balance": balance.locked_balance,
            "equity": balance.equity_usdt,
            "margin_level": balance.margin_level,
            "position_size": await self._get_position_size(),
            "total_cost": await self._get_total_cost(),
            "unrealized_pct": await self._calculate_unrealized_pct(),
            "status": self.config.current_status,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        await self.gateway.broadcast_websocket(
            f"/ws/louise/metrics/{self.config.bot_id}",
            metrics
        )
```

### 3. API Endpoint for Balance Metrics

**File:** `runtime/api/routers/louise.py`

```python
@router.get("/api/v1/louise/bots/{bot_id}/balance")
async def get_bot_balance(bot_id: str, token: str = Depends(verify_token)):
    """
    Get latest account balance metrics for a bot
    
    Returns:
        - free_balance: Available to trade
        - locked_balance: In open orders
        - equity: Total account value
        - margin_level: Leverage level (if applicable)
        - last_refresh: When metrics were last updated
    """
    bot = await db.get_bot(bot_id)
    checker = BalanceChecker(binance_gateway)
    
    balance = await checker.check_and_refresh(bot.symbol)
    
    return {
        "bot_id": bot_id,
        "symbol": bot.symbol,
        "free_balance": balance.free_balance,
        "locked_balance": balance.locked_balance,
        "total_balance": balance.total_balance,
        "equity": balance.equity_usdt,
        "margin_level": balance.margin_level,
        "minimum_required": checker.min_free_balance,
        "can_trade": balance.free_balance >= checker.min_free_balance,
        "last_refresh": balance.timestamp.isoformat(),
        "recommendations": []  # Suggestions if balance low
    }

@router.get("/api/v1/louise/stats/account")
async def get_hub_account_stats(token: str = Depends(verify_token)):
    """
    Hub-wide account metrics (all bots combined)
    
    Returns:
        - Total equity across all positions
        - Free balance available
        - Locked in open orders
        - Margin level (if any bot uses margin)
        - Distribution: how much per bot
    """
    all_bots = await db.get_all_bots()
    checker = BalanceChecker(binance_gateway)
    
    total_equity = 0
    total_free = 0
    total_locked = 0
    distribution = []
    
    for bot in all_bots:
        balance = await checker.check_and_refresh(bot.symbol)
        total_equity += balance.equity_usdt
        total_free += balance.free_balance
        total_locked += balance.locked_balance
        
        distribution.append({
            "bot_id": bot.bot_id,
            "symbol": bot.symbol,
            "equity": balance.equity_usdt,
            "free": balance.free_balance
        })
    
    return {
        "total_equity": total_equity,
        "total_free_balance": total_free,
        "total_locked_balance": total_locked,
        "margin_level": max(b.margin_level for b in all_bots if b.margin_level),
        "num_bots_active": len([b for b in all_bots if b.status == "ACCUMULATING"]),
        "num_bots_paused_low_balance": len([b for b in all_bots if "LOW_BALANCE" in b.status]),
        "distribution": distribution,
        "last_refresh": datetime.utcnow().isoformat()
    }
```

---

## 📊 UI Integration: Updated Equity Charts

### Real-time Equity Dashboard

**Update:** `docs/UI_WIREFRAMES.md` — Add to Dashboard & Details

```
╔════════════════════════════════════════════════════════════════╗
║  HUB SUMMARY                                                   ║
│  ┌──────────────────────────────────────────────────────────┐ │
│  │ Total Equity: $15,850    [Live: 📊 Last 1h]             │ │
│  │ ├─ Free Balance:  $2,450  (Available)                    │ │
│  │ ├─ Locked:        $1,200  (In orders)                    │ │
│  │ └─ Margin Level:  250% (if applicable)                   │ │
│  │                                                          │ │
│  │ [Chart: Equity over time (last 24h)]                    │ │
│  │ ╔════════════════════════════════════════════╗          │ │
│  │ ║  $16k │                    ╱╲              ║          │ │
│  │ ║       │                   ╱  ╲_            ║          │ │
│  │ ║  $15k │                  ╱     ╲___        ║ (refresh │ │
│  │ ║       │ ╱╲              ╱          ╲__     ║  every   │ │
│  │ ║  $14k │╱  ╲____________╱              ╲    ║  5 min)  │ │
│  │ ║       └────────────────────────────────┘   ║          │ │
│  │ ║  0h        6h       12h      18h     24h   ║          │ │
│  │ ╚════════════════════════════════════════════╝          │ │
│  │ Last update: 2 seconds ago                              │ │
│  └──────────────────────────────────────────────────────────┘ │
╚════════════════════════════════════════════════════════════════╝
```

### Per-Bot Balance Card

```
╔────────────────────┐
│ louise_btc_001     │
│ BTC/USDT           │
│                    │
│ Balance Status     │
│ ├─ Free:   $2,450  │
│ ├─ Locked: $100    │
│ └─ Equity: $14,250 │
│                    │
│ Funds Health: ✅   │
│ Status: RUNNING    │
│                    │
│ Next Poll: 3min45s │
└────────────────────┘
```

### Balance Low Alert

```
┌────────────────────────────────────────┐
│ ⚠️ louise_eth_001 — Low Balance Alert   │
├────────────────────────────────────────┤
│ Free Balance: $3.50                     │
│ Required: $8.00                         │
│                                         │
│ Bot Status: PAUSED_LOW_BALANCE          │
│ Reason: Insufficient funds to buy      │
│                                         │
│ Action: Deposit $4.50+ to resume       │
│                                         │
│ [Dismiss] [Deposit Now]                │
└────────────────────────────────────────┘
```

---

## 🔄 Metrics Refresh Frequency

### Before (without balance verification)

```
Dashboard refresh cycle:
- Every 5 seconds: fetch metrics from bot state
- Every 2 minutes: manual full refresh (if user clicks)
- Result: Stale equity data, delayed balance updates
```

### After (with opportunistic refresh)

```
Dashboard refresh cycle:
- Every 5 minutes (bot poll): Fresh balance data broadcasted
- Every buy attempt: Fresh balance check
- On-demand: API endpoint for instant balance
- Fallback: Cache with 2-minute TTL for offline display

Result: Fresh equity metrics guaranteed every 5 min minimum
```

---

## 📈 Example Flow: Pre-Execution Balance Check

### Scenario 1: Sufficient Balance

```
Time: T0
│
├─ Louise bot poll triggered
├─ Call: balance_checker.check_and_refresh()
│  └─ API: Account endpoint (1 call)
│     └─ Response: free=$2,450, locked=$100, equity=$15,850
│
├─ Decision: $2,450 >= $8? YES ✅
│
├─ Proceed to price check
│  └─ Fetch current price
│  └─ Compare with last_buy_price
│
├─ Buy condition met? YES
│  └─ Execute market buy
│
└─ Broadcast metrics to WebSocket
   └─ UI updates: balance=$2,350, equity=$15,750, position+$100
```

### Scenario 2: Insufficient Balance

```
Time: T0
│
├─ Louise bot poll triggered
├─ Call: balance_checker.check_and_refresh()
│  └─ API: Account endpoint (1 call)
│     └─ Response: free=$3.50, locked=$0, equity=$8,200
│
├─ Decision: $3.50 >= $8? NO ❌
│
├─ PAUSE bot
│  └─ Update status: PAUSED_LOW_BALANCE
│  └─ Send alert: "Insufficient balance. Deposit funds to resume."
│
├─ Cache balance metrics
│
└─ Broadcast metrics to WebSocket
   └─ UI shows: ⚠️ Low balance, status PAUSED
   └─ No buy attempted, NO wasted API weight
```

---

## 🎯 Benefits Summary

### API Weight Savings

| Scenario | Without Check | With Check | Savings |
|----------|--------------|-----------|---------|
| Account with $3 for 1 day | 1,440 checks + 1,440 failed buys (24 weight each) = 35,424 weight | 1,440 checks (1 weight each) = 1,440 weight | **33,984 weight** ✅ |
| Multi-bot hub, 1 bot low funds | Same per bot × 10 bots | Only that bot paused | **~340,000 weight/day** |

### UX Improvements

- ✅ **Clear status:** Operator sees immediately bot is paused (low balance)
- ✅ **Live equity:** Dashboard shows fresh account metrics every 5 min
- ✅ **Proactive alerts:** Operator doesn't need to check why bot idle
- ✅ **Faster recovery:** As soon as funds deposited, bot resumes automatically

### Operational Efficiency

- ✅ **No silent failures:** Bot doesn't retry failed buys indefinitely
- ✅ **Better visibility:** Equity, free balance, locked balance all tracked
- ✅ **Reduced confusion:** Why is bot paused? Check balance card
- ✅ **Scalability:** More bots, same API weight efficiency

---

## 📝 Implementation Checklist

### Phase 1 Integration

- [ ] Create `runtime/core/balance_checker.py`
  - [ ] `BalanceChecker` class
  - [ ] `check_and_refresh()` method
  - [ ] `has_minimum_balance()` method
  - [ ] `_calculate_equity()` method

- [ ] Update `runtime/bot/louise.py`
  - [ ] Initialize BalanceChecker in `__init__`
  - [ ] Call `check_and_refresh()` at start of `poll_market()`
  - [ ] Add `_handle_insufficient_balance()` method
  - [ ] Add `_cache_balance_metrics()` method
  - [ ] Update `_broadcast_metrics()` to include balance data

- [ ] Update `runtime/api/routers/louise.py`
  - [ ] `GET /api/v1/louise/bots/{bot_id}/balance` endpoint
  - [ ] `GET /api/v1/louise/stats/account` endpoint

- [ ] Update database schema
  - [ ] Add `last_balance_check` timestamp to louise_bots table
  - [ ] Add `last_balance_free`, `last_balance_equity` columns (metrics cache)

- [ ] Update `docs/UI_WIREFRAMES.md`
  - [ ] Add equity chart to dashboard
  - [ ] Add balance card to bot details
  - [ ] Add low balance alert dialog

- [ ] Add tests
  - [ ] Test balance check with sufficient funds
  - [ ] Test balance check with insufficient funds
  - [ ] Test equity calculation
  - [ ] Test pause logic when low balance

---

## 🚀 Production Rollout

### Rollout Strategy

1. **Phase 1.2:** Implement BalanceChecker + integration
2. **Phase 2:** Deploy to testnet, verify with live Binance (testnet API)
3. **Phase 3:** Canary deploy to single bot (testnet subaccount)
4. **Phase 4:** Full rollout to all Louise bots
5. **Monitor:** Track API weight savings, false pause rate, recovery time

### Success Metrics

- **API Weight Savings:** >30% reduction when any bot has <$8
- **Mean Time to Recovery:** <10 seconds from deposit to bot resuming
- **False Pause Rate:** <0.1% (only due to exchange API issues)
- **UI Latency:** Balance refresh <1 second via WebSocket

---

**Status:** Ready for Phase 1 Implementation  
**Estimated Effort:** 1-2 days (small, high-impact feature)  
**Priority:** High (addresses production feedback)  
**ROI:** Very High (saves API weight + improves UX)
