# Pecunator-AccuMonetas: Executive Summary

**Project:** Louise Bot Hub (DCA Downside-Only)  
**Status:** 🟢 Ready to start development  
**Date:** 2026-05-11

---

## 🎯 What is Louise?

**Louise** is an autonomous trading bot that progressively accumulates an asset through downside-only DCA averaging:

```
Simple Logic:
1. Every N seconds it checks the symbol's price
2. If current price < last buy price → buys its configured volume
3. If there are no previous buys → executes the first buy (base reference)
4. No stop-loss (by design, only averages down)
5. When profit reaches X% → sells EVERYTHING at market, closes epoch (successful)
6. Ready for a new epoch
```

**Multi-Louise Hub:** Hundreds of Louise bots running simultaneously on different symbols/assets, each with its own parameters.

---

## 📦 What is Completed?

### ✅ Base Documentation

| Document | Purpose | Status |
|-----------|----------|--------|
| **CLAUDE.md** | Workflow, phases, technical stack | ✅ Ready |
| **BOT_SPECIFICATION.md** | Detailed logic, parameters, API | ✅ Ready |
| **UI_WIREFRAMES.md** | 6 screens, flows, components | ✅ Ready |
| **IMPLEMENTATION_ROADMAP.md** | 9-week plan, phases, milestones | ✅ Ready |
| **ONBOARDING.md** | Pre-development checklist | ✅ Ready |

### ✅ Inherited Infrastructure (PecunatorCore v3.7.5)

```
Backend (Python FastAPI)
├─ HTTP API on port 8000
├─ WebSocket for real-time telemetry
├─ AsyncClient (python-binance) 100% native
├─ SQLite for state persistence
└─ 195+ tests (complete suite)

Frontend (Flutter Desktop)
├─ Native Windows UI
├─ State management (Provider)
├─ Syncfusion charts
└─ WebSocket listeners

Control Modules
├─ WeightGovernor (API rate limiting)
├─ ApiFuse (circuit breaker)
├─ BudgetGuard (spend caps)
├─ OrderLedger (audit trail)
└─ StateWAL (crash recovery)
```

---

## 📋 Implementation Plan (9 Weeks)

### Phase 1: Foundation (Weeks 1-2)
- [ ] Create bot runner module: `runtime/bot/louise.py`
- [ ] Create API routers: `runtime/api/routers/louise.py`
- [ ] Extend SQLite schema with Louise tables
- [ ] Test suite (unit + integration)
- **Deliverable:** Functional bot runner + ready API

### Phase 2: Full Backend (Weeks 3-4)
- [ ] Implement full Louise logic (polling, buys, close)
- [ ] Integrate with control modules (BudgetGuard, WeightGovernor, etc.)
- [ ] Implement all REST endpoints
- [ ] WebSocket for real-time metrics
- **Deliverable:** Production-ready backend + complete API

### Phase 3: Flutter UI (Weeks 5-6)
- [ ] Dashboard: bot grid with status and P&L
- [ ] Detail: metrics, budget, buy history
- [ ] History: completed epochs, all purchases
- [ ] Settings: bot creation and editing
- [ ] Real-time WebSocket: metrics update every 5 seconds
- **Deliverable:** Complete, intuitive, responsive UI

### Phase 4: E2E Testing (Week 7)
- [ ] End-to-end tests: create bot → enable → monitor → close
- [ ] Load tests: 10 bots simultaneously
- [ ] Error tests: disconnections, budget exhausted, invalid credentials
- [ ] UI polish: responsive, dark mode, accessibility
- **Deliverable:** Zero known bugs, all tests pass

### Phase 5: Hardening & Production (Weeks 8-10)
- [ ] Security: credential validation, input sanitization
- [ ] Performance: query optimization, WebSocket latency
- [ ] Reliability: crash recovery, DB integrity
- [ ] Deployment: checklist, rollback procedure, monitoring
- **Deliverable:** ✅ Production-ready

---

## 🎯 Key Technical Decisions

### Database Schema (SQLite)

```sql
louise_bots:
  - bot_id (PK)
  - symbol (BTC/USDT, ETH/USDT, etc.)
  - buy_volume (how much to buy per cycle)
  - poll_interval_seconds (how often to check the market)
  - target_profit_pct (% profit to close)
  - daily_budget_usdt (daily spend limit)
  - status (IDLE, ACCUMULATING, PAUSED, ERROR, SHUTDOWN)

louise_purchases:
  - purchase_id (PK)
  - bot_id, epoch_id (FK)
  - price_at_buy, volume, cost_usdt
  - order_id (Binance)
  - status (FILLED, FAILED, etc.)

louise_epochs:
  - epoch_id (PK)
  - bot_id (FK)
  - num_purchases, total_cost, avg_buy_price
  - final_price, final_value, profit_usdt, profit_pct
  - status (RUNNING, CLOSED_SUCCESSFUL, CLOSED_MANUAL)
```

### API Endpoints (Total: 14 endpoints)

```
Bot Management:
  POST   /api/v1/louise/bots
  GET    /api/v1/louise/bots
  GET    /api/v1/louise/bots/{bot_id}
  PATCH  /api/v1/louise/bots/{bot_id}
  POST   /api/v1/louise/bots/{bot_id}/enable
  POST   /api/v1/louise/bots/{bot_id}/disable
  POST   /api/v1/louise/bots/{bot_id}/shutdown
  DELETE /api/v1/louise/bots/{bot_id}

Metrics & History:
  GET    /api/v1/louise/bots/{bot_id}/metrics
  GET    /api/v1/louise/bots/{bot_id}/epochs
  GET    /api/v1/louise/bots/{bot_id}/purchases
  GET    /api/v1/louise/stats

WebSocket:
  WS     /ws/louise/metrics/{bot_id} (update every 5 seconds)
```

### UI Screens (6 main screens)

1. **Dashboard** — Bot grid, status, P&L, quick action buttons
2. **Bot Details** — Full metrics, budget, buy table
3. **History** — Completed epochs, all purchases, filters
4. **Settings** — API configuration, alerts, backup
5. **Create/Edit Bot** — Form to create or edit a bot
6. **Alerts** — Error notifications, confirmations

---

## 💾 Infrastructure Decisions

### Credentials

```bash
# .env per subaccount
BOT_API_KEY=<binance_key>
BOT_API_SECRET=<binance_secret>

# Encrypted vault (Fernet)
runtime/data/credentials.enc
```

### Rate Limiting (Inherited from PecunatorCore)

- **WeightGovernor:** COLOR zones (GREEN/YELLOW/RED) based on REST weight
- Each Louise uses its own weight allocation
- If zone turns RED → automatic pause

### Crash Recovery

- **StateWAL:** Persists state after each cycle
- **Auto-resume:** If the bot was enabled, it attempts to resume on restart
- **Retry logic:** Reconnection with exponential backoff

---

## 🚀 UX/UI Decisions

### Mobile-First Design (but Desktop-Optimized)

- **Responsive grid:** Adapts to 1280x800, 1920x1080, etc.
- **Colors:**
  - ✅ Green = RUNNING/Profit
  - ⏸️ Yellow = PAUSED/Drawdown
  - 🔴 Red = ERROR/Loss
  - 🟡 Grey = SHUTDOWN
  
### Real-time Updates (WebSocket)

- **Frequency:** Every 5 seconds (configurable)
- **Payload:** `{price, avg_price, P&L%, budget_remaining, status}`
- **Auto-refresh:** No clicks needed, user sees live updates

### Interaction Flows

```
Create Bot → [Form] → Create instance → Bot status: IDLE
            ↓
         [Enable] → Execute first buy → ACCUMULATING
            ↓
     [Monitor] → Every 5s updates P&L
            ↓
    P&L >= target_profit% → Auto-sell all → SHUTDOWN (successful epoch)
```

---

## 📊 Key Metrics Monitored

### Per Bot

| Metric | Description |
|---------|-------------|
| Current Price | Current symbol price |
| Last Buy Price | Reference for next buy |
| Avg Buy Price | VWAP of all purchases |
| Position Size | Total accumulated tokens |
| Total Cost | USDT spent on all purchases |
| Current Value | `position_size * current_price` |
| Unrealized P&L | `current_value - total_cost` |
| Unrealized P&L % | `(current_value - total_cost) / total_cost * 100` |
| Budget Used Today | USDT spent today (resets tomorrow) |
| Budget Remaining | Daily limit - used |

### Hub-Wide

| Metric | Description |
|---------|-----------|
| Total Active Bots | Number of Louise bots in ACCUMULATING |
| Completed Epochs | Total historical successful cycles |
| Portfolio Total | Sum of current values of all positions |
| Historical Profit | Sum of profits from all closed epochs |
| Win Rate | 100% (by design, always closes at profit) |
| Average Profit | Average profit per epoch |

---

## 🛡️ Risk Controls

### Budget Guard

```
If daily_budget_usdt = $1,000:
  ├─ Bot can spend maximum $1,000/day
  ├─ If limit reached → pause (no error)
  ├─ Budget resets tomorrow at 00:00 UTC
  └─ Operator sees "Budget exhausted" in UI
```

### Weight Governor

```
If API weight zone → RED (>80% of daily limit):
  ├─ All bots enter automatic pause
  ├─ Wait until weight returns to YELLOW
  ├─ Operator alerted in UI
  └─ Prevents Binance rate-limits
```

### Error Handling

```
Network Error → Retry with exponential backoff (3 attempts)
Exchange Error → Log + Alert + Pause bot (requires manual intervention)
Invalid Credentials → Critical alert + Pause all bots
Insufficient Balance → Pause (no error), waiting for deposit
```

---

## 📈 Example Use Case

**Setup:** Louise on BTC, $100/buy, every 5 min, 5% profit target, $1000/day

```
T0: Bot enabled
    └─ First buy: 0.0025 BTC at $40,000 → cost $100

T5min: Poll market → Price $39,500 < $40,000 ✓
    └─ Second buy: 0.00253 BTC at $39,500 → cost $100
       Pos: 0.00503 BTC, Cost: $200, Avg: $39,750

T10min: Poll market → Price $40,500 > $39,750 ✗
    └─ No buy, just wait

T15min: Poll market → Price $40,100 < $40,500 ✓
    └─ Third buy: 0.00249 BTC at $40,100 → cost $100
       Pos: 0.00752 BTC, Cost: $300, Avg: $39,892

T20min: Poll market → Price $41,900 > $39,892 ✓
    └─ P&L % = (0.00752 * $41,900 - $300) / $300 = +5.16% ✅
    └─ TARGET PROFIT REACHED
    └─ Sell ALL: 0.00752 BTC at $41,900 = $314.87
    └─ Profit: $314.87 - $300 = $14.87
    └─ Epoch CLOSED (successful)
    └─ Bot status: SHUTDOWN
    └─ Epoch recorded in DB (history)
```

---

## 🎯 Checklist Before Starting Phase 1

- [ ] **Binance Subaccount:** Specify which one to use
  - Name: ___________________
  - API Key: ✓ Created
  - Daily limit: $_________/day
  
- [ ] **Initial symbols:** Which ones will Louise monitor first?
  - [ ] BTC/USDT
  - [ ] ETH/USDT
  - [ ] SOL/USDT
  - [ ] Others: __________________

- [ ] **Louise default parameters:**
  - Buy volume: $_________/buy
  - Poll interval: _________seconds
  - Target profit: _________%
  - Daily budget: $_________/day

- [ ] **UI preferences:**
  - [ ] Dark mode by default
  - [ ] Telegram alerts
  - [ ] Email alerts
  - [ ] Session autosave

---

## 🚀 Immediate Next Step

**Commit and push the repository:**

```bash
git status  # Check changes
git log --oneline -5  # View commits
git push origin claude/naughty-shaw-b40d27  # Push to current branch
```

**Then:**
1. Fill in the Binance subaccount checklist
2. Create branch `feature/louise-backend`
3. Start Phase 1 (bot runner module)

---

## 📚 Key Documents for Reference

| Document | When to Read |
|-----------|----------|
| **CLAUDE.md** | Before starting (general workflow) |
| **BOT_SPECIFICATION.md** | To understand Louise logic |
| **UI_WIREFRAMES.md** | To understand UI flows |
| **IMPLEMENTATION_ROADMAP.md** | For detailed schedule |
| **README.md** | Project quick start |

---

## 💬 One-Line Summary

**Louise is a downside-only DCA bot hub that progressively accumulates assets, automatically closes at profit, and the Flutter UI monitors multiple instances in real time — ready to start development in ~9 weeks.**

---

**Status:** ✅ Ready for Phase 1  
**Decision:** Confirm Binance subaccount and start?
