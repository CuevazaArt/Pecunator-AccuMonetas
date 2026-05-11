# Pecunator-AccuMonetas: Onboarding Checklist

**Project Status:** 🟡 Ready for Definition Phase  
**Repository:** https://github.com/CuevazaArt/Pecunator-AccuMonetas.git  
**Based on:** PecunatorCore v3.7.5 (production-stable)

---

## ✅ Pre-Development Checklist

Before starting Phase 1 (Structure & Setup), define the following:

### 1. Trading Bot Strategy

- [ ] **Bot Name:** What will this bot be called?
- [ ] **Trading Logic:** What is the core strategy? Examples:
  - DCA (Dollar Cost Averaging) — regular buy intervals
  - Grid Trading — automated buy/sell grid on a range
  - Momentum Trading — trend-following with signal gates
  - Yield Optimization — optimal order routing + fee minimization
  - Custom Hybrid — combination of above
- [ ] **Time Horizon:** Scalping (minutes), day trading, swing (days), long-term (weeks+)?
- [ ] **Asset Classes:** Spot only? Margin? Derivatives?
- [ ] **Entry/Exit Signals:**
  - Manual (operator decision) ?
  - Automatic (algorithm triggers)?
  - Hybrid (algorithm suggests, operator approves)?

### 2. Binance Subaccount

- [ ] **Subaccount Name:** Which subaccount will this bot use?
- [ ] **API Keys Created?** (need API Key + Secret)
- [ ] **Daily Spend Limit:** What's the max USDT per day budget?
- [ ] **IP Whitelist:** Is 127.0.0.1 / localhost whitelisted?
- [ ] **Permissions:**
  - [ ] Read: Account, Orders, Trades
  - [ ] Write: Orders, Cancel Orders
  - [ ] Is margin enabled? (if needed)
- [ ] **Sub-account restrictions:** (futures, spot, testnet?)

### 3. UI Requirements

Map out the operator's dashboard. Example screens:

- [ ] **Home/Dashboard**
  - Current balance (USDT)
  - Active positions
  - Daily P&L
  - Bot status (running/paused/error)

- [ ] **Orders**
  - Pending orders
  - Execution history (24h, 7d, all)
  - Order details + average price

- [ ] **Metrics**
  - Buy/sell volume
  - Win rate (if applicable)
  - Daily/weekly profit
  - API weight usage (WeightGovernor status)

- [ ] **Alerts & Logs**
  - Critical events (errors, budget breach, etc.)
  - Recent activity (bot actions)
  - Notification preferences (Telegram? Discord?)

- [ ] **Settings**
  - Bot enable/disable
  - Budget cap adjustment
  - Signal parameters (if customizable)
  - Credentials management

- [ ] **Manual Controls**
  - Force close all positions?
  - Pause bot?
  - Update strategy parameters?

### 4. Risk & Control Parameters

Define what safeguards are essential:

- [ ] **Daily Budget Cap:** (e.g., $500/day max spend)
- [ ] **Position Size Limits:** (e.g., max $100 per trade)
- [ ] **Leverage (if margin):** (e.g., 2x max)
- [ ] **Error Handling:** On exchange error, should bot pause or retry?
- [ ] **Recovery Policy:** If bot crashes, auto-resume or wait for operator?
- [ ] **Rate Limiting:** REST weight limits (default: 6000/min with Binance)

### 5. Monitoring & Alerts

- [ ] **Real-time Metrics:**
  - WebSocket price feeds? (which pairs?)
  - Order execution latency?
  - API weight consumption?

- [ ] **Alerts (Telegram, Discord, email):**
  - [ ] Critical: bot crashed, budget exceeded, auth failed
  - [ ] Warning: low balance, high API weight
  - [ ] Info: daily summary, position closed

- [ ] **Telemetry:**
  - Every trade logged? (default: yes)
  - Audit trail for orders? (default: yes via OrderLedger)
  - Metrics stored in SQLite? (default: yes)

---

## 📋 Definition Phase Outputs

Once you complete the above, create these documents:

### `docs/BOT_SPECIFICATION.md`
Document the bot's logic, triggers, and decision tree:
```markdown
# AccuMonetas Bot Specification

## Strategy
- Name: AccuMonetas DCA
- Logic: Buy every 2 hours at 5% below EMA(200), stop-loss at -3%
- Assets: BTC/USDT, ETH/USDT
- Budget: $100/day

## Entry Rules
1. EMA(200) pointing up (slope > 0)
2. Current price < EMA(200) * 0.95
3. Check budget remaining today
4. If all true → Place limit buy

## Exit Rules
1. If profit > 5% → Sell all
2. If loss > -3% → Cut loss
3. If EMA(200) slope inverts → Sell all

## Risk Controls
- Max position: $500
- Daily budget: $100
- Max leverage: 1.0 (spot only)
```

### `.env.example`
Add bot-specific configuration:
```bash
# AccuMonetas Bot Configuration
ACCU_API_KEY=<your_subaccount_key>
ACCU_API_SECRET=<your_subaccount_secret>
ACCU_DAILY_BUDGET_USDT=100
ACCU_BUY_INTERVAL_MINUTES=120
ACCU_BUY_THRESHOLD_BELOW_EMA=0.05
ACCU_STOP_LOSS_PCT=-0.03
ACCU_TAKE_PROFIT_PCT=0.05
```

### `docs/UI_WIREFRAMES.md`
Simple wireframes of the 5-6 main screens (text-based or Figma link).

### `SUBACCOUNT_SETUP.md`
Record for ops team:
```markdown
# Subaccount Setup Log

**Subaccount Name:** trading-bot-prod  
**API Key:** [masked]  
**Daily Limit:** $500  
**Enabled:** 2026-05-11  
**Operator:** [name]  
**IP Whitelist:** 127.0.0.1, [VPN IP if applicable]  
```

---

## 🚀 Next Steps (Once Checklist Complete)

1. **Create feature branches** for:
   - `feature/bot-backend` — Implement bot runner
   - `feature/ui-dashboard` — Adapt Flutter UI
   - `feature/api-endpoints` — Extend API routers
   - `feature/tests-bot` — Comprehensive test coverage

2. **Implement Phase 1 deliverables:**
   - [ ] Bot spec + naming finalized
   - [ ] Credentials vault setup (subaccount keys)
   - [ ] UI wireframes → Flutter prototypes
   - [ ] API contract (endpoints bot will use)

3. **Setup GitHub:**
   - [ ] Enable branch protection on `main`
   - [ ] Require PR reviews before merge
   - [ ] Setup GitHub Actions for CI/CD
   - [ ] Create issue templates

4. **First local test:**
   - [ ] Start engine: `python main.py`
   - [ ] Check API: `curl -H "Authorization: Bearer $(cat runtime/data/api.token)" http://127.0.0.1:8000/health`
   - [ ] Start Flutter UI
   - [ ] Verify connection (UI shows "API connected")

---

## 📞 Questions?

Refer to:
- **CLAUDE.md** — Development workflow & architecture
- **README.md** — Quick start commands
- **DEVELOPMENT_GUIDE.md** — Step-by-step instructions
- **docs/*** — Detailed architecture & operational docs

---

**Status:** Ready for your input → Fill checklist → Phase 1 begins  
**Estimated time to complete checklist:** 1-2 hours  
**Estimated time to Phase 2 (backend ready):** 1-2 weeks (depends on bot complexity)
