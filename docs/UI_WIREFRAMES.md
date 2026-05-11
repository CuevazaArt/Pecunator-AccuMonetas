# Louise Bot Hub — UI Wireframes

**Target Platform:** Windows Desktop (Flutter)  
**Design Pattern:** Dashboard + Detail Views  
**Status:** Ready for Implementation

---

## 🎨 Design Principles

- **At-a-glance monitoring:** Grid/list view showing all bots + key metrics
- **Minimal clicks:** Essential controls on main screen (enable/disable)
- **Real-time updates:** WebSocket-driven metrics refresh every 5 seconds
- **Progressive detail:** Tap/click for detailed metrics, purchase history, epoch records
- **Clear status indicators:** Color-coded states (RUNNING, IDLE, ERROR, SHUTDOWN)

---

## 📋 Navigation Structure

```
Main App
├─ Bottom Navigation (4 tabs)
│  ├─ Dashboard (Home)
│  ├─ Bot Details (Selected bot)
│  ├─ History (Epochs & purchases)
│  ├─ Settings (Bot config, alerts)
│  └─ User Menu (Logout, preferences)
└─ Modal Dialogs
   ├─ Create New Bot
   ├─ Edit Bot Config
   ├─ Force Shutdown
   └─ Alerts
```

---

## 📱 Screen 1: Dashboard (Main Hub View)

### Layout: Scrollable grid of bot cards

```
╔════════════════════════════════════════════════════════════════╗
║  LOUISE BOT HUB                                  ⚙️  🔔  👤  ║
║────────────────────────────────────────────────────────────────║
║                                                                ║
║  📊 HUB SUMMARY                                                ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Active Bots: 3       │ Completed Epochs: 12              │ ║
║  │ Total Portfolio: $4,850  │ Hub Profit (All-Time): +$2,340 │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  🤖 BOT INSTANCES (Grid View)                                  ║
║  ┌────────────────────┐  ┌────────────────────┐              ║
║  │ louise_btc_001     │  │ louise_eth_001     │              ║
║  │ BTC/USDT           │  │ ETH/USDT           │              ║
║  │                    │  │                    │              ║
║  │ Status: ✅ RUNNING │  │ Status: ⏸️ PAUSED  │              ║
║  │ Price: $42,500     │  │ Price: $2,150      │              ║
║  │ P&L: +2.8%  📈     │  │ P&L: -1.2%  📉     │              ║
║  │ Position: 0.05 BTC │  │ Position: 2.3 ETH  │              ║
║  │ Cost: $1,200       │  │ Cost: $1,850       │              ║
║  │                    │  │                    │              ║
║  │ [Enable/Disable]   │  │ [Enable/Disable]   │              ║
║  │ [Details]          │  │ [Details]          │              ║
║  └────────────────────┘  └────────────────────┘              ║
║                                                                ║
║  ┌────────────────────┐                                       ║
║  │ louise_sol_001     │                                       ║
║  │ SOL/USDT           │                                       ║
║  │                    │                                       ║
║  │ Status: 🔴 SHUTDOWN│                                       ║
║  │ Epoch Closed       │                                       ║
║  │ Profit: +$85.50    │                                       ║
║  │ Duration: 3 days   │                                       ║
║  │                    │                                       ║
║  │ [Details]  [Re-run]│                                       ║
║  └────────────────────┘                                       ║
║                                                                ║
║  [+ CREATE NEW BOT]                                            ║
╚════════════════════════════════════════════════════════════════╝
```

### Card Components
Each bot card displays:
- **Header:** Bot name + symbol + status icon
- **Current Price:** Live market price
- **P&L Indicator:** % change (color: red=-1%, yellow=0-2%, green=2%+)
- **Position:** Size + cost basis
- **Action Buttons:**
  - Enable/Disable toggle (quick control)
  - [Details] → open detailed view
  - (for shutdown bots) [Re-run] → create new epoch

### Hub Summary Section
- Total active bots
- Total completed epochs
- Hub portfolio value (sum of all current positions)
- All-time profit across all closed epochs

---

## 🔍 Screen 2: Bot Details (Expanded View)

### Layout: Scroll-down detail pane

Triggered by: Click [Details] on any bot card

```
╔════════════════════════════════════════════════════════════════╗
║  ← louise_btc_001 (BTC/USDT)         ⚙️ [Edit Config]         ║
║────────────────────────────────────────────────────────────────║
║                                                                ║
║  STATUS                                                        ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Current Status: ✅ ACCUMULATING                          │ ║
║  │ Bot Enabled: [Toggle] ON                                 │ ║
║  │ Epoch ID: louise_btc_001_ep_003                          │ ║
║  │ Epoch Duration: 5 days, 3 hours                          │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  MARKET & POSITION                                             ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Current Price (Live): $42,500                            │ ║
║  │ Last Buy Price:       $41,200                            │ ║
║  │ Avg Buy Price (VWAP): $40,850                            │ ║
║  │ Price Change (4h):    +$800 (+1.92%)                    │ ║
║  │                                                          │ ║
║  │ Position Size: 0.0512 BTC                                │ ║
║  │ Total Cost:   $2,093.12                                  │ ║
║  │ Current Value: $2,152.00                                 │ ║
║  │                                                          │ ║
║  │ Unrealized P&L: +$58.88                                  │ ║
║  │ Unrealized P&L %: +2.81%  📈                             │ ║
║  │ Target Profit: 5.00% → Need +$46.65 more                │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  BUDGET & ACTIVITY                                             ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Daily Budget: $1,000                                     │ ║
║  │ Spent Today:  $400 (Today: 2024-05-11)                   │ ║
║  │ Remaining:    $600                                       │ ║
║  │ Budget Reset: Tomorrow at 00:00 UTC                      │ ║
║  │                                                          │ ║
║  │ Next Poll: 4 min 32 sec                                  │ ║
║  │ Last Poll: 2 min ago                                     │ ║
║  │ Last Buy:  1 hour 23 min ago                             │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  CONFIGURATION                                                 ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Buy Volume (per cycle):  $100                            │ ║
║  │ Poll Interval:           300 seconds (5 min)             │ ║
║  │ Target Profit:           5.0%                            │ ║
║  │ Subaccount:              trading-bot-prod                │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  QUICK ACTIONS                                                 ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ [Enable] [Disable] [Edit Config] [Force Shutdown]        │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  PURCHASES THIS EPOCH                                          ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ #  │ Time          │ Price    │ Volume  │ Cost    │      │ ║
║  ├────┼───────────────┼──────────┼─────────┼─────────┤      │ ║
║  │ 8  │ Today 14:32   │ $41,200  │ 0.0024  │ $98.88  │ ✅   │ ║
║  │ 7  │ Today 11:00   │ $41,500  │ 0.0024  │ $99.60  │ ✅   │ ║
║  │ 6  │ Yest 23:15    │ $40,800  │ 0.0025  │ $102.00 │ ✅   │ ║
║  │ ... (5 more)                                             │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║  [See All Purchases]                                           ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

### Sections

1. **Status** — Current bot state, epoch info, enabled toggle
2. **Market & Position** — Live price, avg price, VWAP, P&L metrics
3. **Budget & Activity** — Daily budget tracking, next poll countdown
4. **Configuration** — Bot parameters (read-only or editable)
5. **Quick Actions** — Enable/Disable/Shutdown buttons
6. **Purchase Table** — Recent buys this epoch (truncated, link to full history)

---

## 📜 Screen 3: History (Epochs & Purchases)

### Layout: Tabbed view

Triggered by: Bottom navigation tab "History"

#### Tab 3a: Epochs (Completed Cycles)

```
╔════════════════════════════════════════════════════════════════╗
║  HISTORY                     [Epochs] [All Purchases] [Logs]  ║
║────────────────────────────────────────────────────────────────║
║                                                                ║
║  FILTER: All Symbols | All Status                             ║
║                                                                ║
║  COMPLETED EPOCHS (12 total)                                   ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Epoch ID            │ Symbol │ Duration │ Profit │ P&L %  │ ║
║  ├─────────────────────┼────────┼──────────┼────────┼────────┤ ║
║  │ louise_btc_001_e003 │ BTC    │ 5d 3h    │ +$58.88│ +2.81% │ ║
║  │ louise_btc_001_e002 │ BTC    │ 3d 14h   │ +$142.50│+6.25% │ ║
║  │ louise_eth_001_e002 │ ETH    │ 8d 2h    │ +$75.00│+5.10% │ ║
║  │ louise_btc_001_e001 │ BTC    │ 2d 21h   │ +$89.50│+5.75% │ ║
║  │ ... (8 more)                                               │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  [Epoch Detail]                                                ║
║                                                                ║
║  SUMMARY STATS                                                 ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Total Epochs: 12                                         │ ║
║  │ Win Rate: 100% (all epochs profitable)                   │ ║
║  │ Total Profit: +$1,245.30                                 │ ║
║  │ Avg Profit: +$103.78 per epoch                           │ ║
║  │ Avg Duration: 4.5 days per epoch                         │ ║
║  │ Longest Epoch: 12 days 5 hours                           │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

#### Tab 3b: All Purchases

```
╔════════════════════════════════════════════════════════════════╗
║  HISTORY                     [Epochs] [All Purchases] [Logs]  ║
║────────────────────────────────────────────────────────────────║
║                                                                ║
║  FILTER: All Symbols | All Status | Last 30 days              ║
║                                                                ║
║  ALL PURCHASES (186 total)                                     ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ ID  │ Bot/Symbol    │ Time           │ Price   │ Cost   │ ║
║  ├─────┼───────────────┼────────────────┼─────────┼────────┤ ║
║  │ 186 │ louise_btc/BTC│ Today 14:32    │ $42,100 │ $100.50│ ║
║  │ 185 │ louise_eth/ETH│ Today 14:00    │ $2,145  │ $100.00│ ║
║  │ 184 │ louise_btc/BTC│ Today 09:00    │ $41,800 │ $99.50 │ ║
║  │ 183 │ louise_sol/SOL│ Yest 23:30     │ $151.20 │ $100.00│ ║
║  │ ... (more)                                                 │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  [Export to CSV]                                               ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

---

## ⚙️ Screen 4: Settings & Configuration

### Layout: Scrollable settings pane

Triggered by: Bottom navigation tab "Settings"

```
╔════════════════════════════════════════════════════════════════╗
║  SETTINGS                                                      ║
║────────────────────────────────────────────────────────────────║
║                                                                ║
║  GENERAL                                                       ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ UI Theme: [Dark Mode] [Light Mode]                       │ ║
║  │ Metrics Refresh Rate: 5 seconds                          │ ║
║  │ Timestamp Timezone: UTC                                  │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  API & CONNECTIVITY                                            ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ API Host: http://127.0.0.1:8000                          │ ║
║  │ API Status: ✅ Connected                                 │ ║
║  │ WebSocket: ✅ Connected                                  │ ║
║  │ Last Sync: 2 seconds ago                                 │ ║
║  │ Auth Token: ****** [Copy] [Regenerate]                   │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  ALERTS & NOTIFICATIONS                                        ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ [ ] Desktop Alerts (OS notifications)                    │ ║
║  │ [ ] Telegram Bot (push alerts)                           │ ║
║  │     Telegram Chat ID: ________________                   │ ║
║  │ [ ] Email Alerts                                         │ ║
║  │     Email: ____________________________                   │ ║
║  │                                                          │ ║
║  │ Alert Types:                                             │ ║
║  │ [X] Epoch completed (profitable exit)                    │ ║
║  │ [X] Bot error (requires attention)                       │ ║
║  │ [X] Budget exhausted                                     │ ║
║  │ [X] Daily summary (5pm UTC)                              │ ║
║  │ [ ] Every purchase (verbose)                             │ ║
║  │ [ ] Price milestones (e.g., new ATH)                     │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  EXPORT & BACKUP                                               ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ [Export All Epochs (CSV)]  [Export All Purchases (CSV)]  │ ║
║  │ [Backup Database] [Restore Backup]                       │ ║
║  │ Last Backup: 2024-05-10 15:30 UTC                        │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  ACCOUNT                                                       ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Logged in as: Cuevaza                                    │ ║
║  │ Subaccount: trading-bot-prod                             │ ║
║  │ [Change Credentials] [Logout]                            │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

---

## ➕ Screen 5: Create/Edit Bot (Modal Dialog)

### Triggered by: [+ CREATE NEW BOT] button or [Edit Config] on detail view

```
╔════════════════════════════════════════════════════════════════╗
║  CREATE NEW LOUISE BOT                              [X]        ║
║────────────────────────────────────────────────────────────────║
║                                                                ║
║  BOT NAME & ASSET                                              ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Bot ID (auto): louise_btc_002                            │ ║
║  │ Trading Symbol: [Dropdown: BTC/USDT, ETH/USDT, SOL/USDT] ║
║  │               → BTC/USDT  ✓                              │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  EXECUTION PARAMETERS                                          ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Buy Volume (USDT):                                       │ ║
║  │ [_________100__________]                                 │ ║
║  │ (amount to buy per cycle)                                │ ║
║  │                                                          │ ║
║  │ Poll Interval (seconds):                                 │ ║
║  │ [_________300__________]                                 │ ║
║  │ (check market every N seconds)                           │ ║
║  │                                                          │ ║
║  │ Target Profit (%):                                       │ ║
║  │ [__________5.0_________]                                 │ ║
║  │ (exit when profit reaches X%)                            │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  RISK CONTROLS                                                 ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Daily Budget Cap (USDT):                                 │ ║
║  │ [__________1000________]                                 │ ║
║  │ (max spend per calendar day; 0 = unlimited)              │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  BINANCE SUBACCOUNT                                            ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Subaccount: [Dropdown: trading-bot-prod, ...]            │ ║
║  │           → trading-bot-prod                    ✓        │ ║
║  │ (must have valid API keys stored in vault)               │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  AUTOSTART                                                     ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ [ ] Start bot immediately (unchecked = manual start)     │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ [CANCEL]  [VALIDATE]  [CREATE BOT]                       │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

---

## 🚨 Screen 6: Alert / Error Dialog

### Triggered by: Bot error, budget exhausted, etc.

```
╔════════════════════════════════════════════════════════════════╗
║  ⚠️  ALERT                                          [X]        ║
║────────────────────────────────────────────────────────────────║
║                                                                ║
║  louise_btc_001 — Insufficient Balance                         ║
║                                                                ║
║  Error: Cannot execute buy order. Balance insufficient.        ║
║  Bot Status: PAUSED                                            ║
║  Time: 2024-05-11 14:32:45 UTC                                 ║
║                                                                ║
║  Next Action:                                                  ║
║  • Add funds to subaccount                                     ║
║  • Resume bot manually                                         ║
║                                                                ║
║  [ ] Don't show this alert again for this bot                 ║
║                                                                ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ [OK] [VIEW BOT DETAILS]                                   │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

---

## 🎯 Interaction Flows

### Flow 1: Create & Run New Bot

```
Dashboard
  ↓ [+ CREATE NEW BOT]
Create Dialog
  ↓ Fill params (symbol, buy_volume, etc.)
  ↓ [CREATE BOT]
Bot created (status: IDLE)
  ↓ [Enable] button
  ↓ First buy executed
Bot now: ACCUMULATING
  ↓ WebSocket metrics update every 5s
Dashboard auto-refreshes with new bot card
```

### Flow 2: Monitor Bot Until Target Profit

```
Dashboard (bot card visible)
  ↓ P&L % updates in real-time via WebSocket
  ↓ When P&L % >= target_profit_pct:
    Bot automatically:
      - Market sell all
      - Close epoch (SUCCESSFUL)
      - Status changes to SHUTDOWN
  ↓ User sees card status change to "SHUTDOWN"
  ↓ Epoch profit recorded
  ↓ User can [Re-run] to start new epoch
```

### Flow 3: Manual Intervention

```
Dashboard (bot card visible)
  ↓ User clicks [Details]
Detail View opens
  ↓ User clicks [Force Shutdown]
Confirmation dialog
  ↓ Confirm
Bot action:
  - Market sell all immediately
  - Close epoch (CLOSED_MANUAL)
  - Record profit/loss
  - Status: SHUTDOWN
  ↓ Back to dashboard, card updated
```

---

## 🎨 Color Scheme & Status Indicators

### Status Icons & Colors

| Status | Icon | Color | Meaning |
|--------|------|-------|---------|
| RUNNING | ✅ | Green | Bot active, accumulating |
| PAUSED | ⏸️ | Yellow | Bot paused (manual or error) |
| SHUTDOWN | 🔴 | Gray | Bot inactive, epoch closed |
| ERROR | ❌ | Red | Critical error, requires attention |
| IDLE | ⏳ | Blue | Bot created, not started |

### P&L Color Coding

| P&L % | Color | Indicator |
|-------|-------|-----------|
| < -2% | 🔴 Red | Significant loss (rare) |
| -2% to 0% | 🟡 Yellow | In drawdown |
| 0% to 2% | ⚪ Gray | Flat, accumulating |
| 2% to 5% | 🟢 Light Green | Profitable, approaching target |
| > 5% | 🟢 Bright Green | Target reached (auto-close) |

---

## 📊 Real-time Updates (WebSocket)

All metric cards refresh via WebSocket in real-time:

```
WebSocket URL: ws://127.0.0.1:8000/ws/louise/metrics/{bot_id}

Update Frequency: Every 5 seconds
Payload Example:
{
  "bot_id": "louise_btc_001",
  "current_price": 42500.50,
  "last_buy_price": 41200.00,
  "avg_buy_price": 40850.00,
  "position_size": 0.0512,
  "total_cost": 2093.12,
  "current_value": 2152.00,
  "unrealized_pct": 2.81,
  "budget_remaining": 600.00,
  "status": "ACCUMULATING",
  "next_poll_in_seconds": 272,
  "last_buy_at": "2024-05-11T14:32:45Z"
}
```

Cards update without page reload. User sees live metrics updating in real-time.

---

## 🧪 Testing Scenarios

| Scenario | Expected Behavior |
|----------|-------------------|
| Create bot, enable | First buy executes, status → ACCUMULATING |
| Price drops | Next poll triggers buy (if budget allows) |
| Price stays flat | Bot waits for next poll, shows holding |
| P&L reaches target | Auto-sell, epoch closes, status → SHUTDOWN |
| Budget exhausted | Bot pauses, shows alert |
| Network error | Retry logic, alert if persistent |
| Force shutdown | Manual close, epoch logged as CLOSED_MANUAL |

---

## 📋 Component List (Implementation Checklist)

- [ ] **Widgets:**
  - [ ] BotCard (summary grid item)
  - [ ] BotDetailView (expanded pane)
  - [ ] EpochTable (history list)
  - [ ] PurchaseTable (detailed transactions)
  - [ ] CreateBotDialog (modal form)
  - [ ] AlertDialog (error/confirmation)
  - [ ] StatusIndicator (icon + color)
  - [ ] MetricsRefreshWidget (WebSocket listener)

- [ ] **Pages:**
  - [ ] DashboardPage (main hub view)
  - [ ] DetailPage (bot details)
  - [ ] HistoryPage (epochs & purchases)
  - [ ] SettingsPage (config)

- [ ] **State Management:**
  - [ ] BotProvider (list of bots)
  - [ ] SelectedBotProvider (detail view)
  - [ ] MetricsProvider (WebSocket listener)
  - [ ] AlertsProvider (notifications)

- [ ] **Services:**
  - [ ] LouiseApiService (REST calls)
  - [ ] WebSocketService (real-time metrics)
  - [ ] NotificationService (alerts)
  - [ ] DatabaseService (local cache)

---

**Status:** Ready for Flutter Implementation  
**Next:** Begin `feature/ui-dashboard` branch → Implement components → Connect to API
