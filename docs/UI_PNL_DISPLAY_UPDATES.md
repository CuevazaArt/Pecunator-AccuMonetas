# UI Display Updates: Real-time %PNL on Every Bot

**Companion Document to:** UI_WIREFRAMES.md  
**Purpose:** Show exactly where and how %PNL appears in UI  
**Status:** Implementation guide for Phase 3 (Flutter UI)

---

## 📱 Dashboard Grid: Bot Cards WITH %PNL

### Updated Bot Card Layout

```
BEFORE:                          AFTER (with %PNL):
┌────────────────┐              ┌────────────────────────────┐
│ louise_btc_001 │              │ louise_btc_001             │
│ BTC/USDT       │              │ BTC/USDT                   │
│                │              │                            │
│ Status: RUNNING│              │ Status: ✅ RUNNING         │
│ Price: $42,500 │              │ Price: $42,500 🔄          │
│ P&L: +2.8%     │              │ ┌──────────────────────┐   │
│ Position: 0.05 │              │ │ %PNL: +2.81% 🟡     │   │
│ Cost: $1,200   │              │ │ (LARGE, BOLD, COLOR) │   │
│                │              │ └──────────────────────┘   │
│ [Enable/Disable]              │                            │
│ [Details]      │              │ Position: 0.05 BTC         │
└────────────────┘              │ Cost: $1,200               │
                                │ Free Balance: $450         │
                                │                            │
                                │ [Enable/Disable] [Details] │
                                └────────────────────────────┘
```

**Key Differences:**
1. **%PNL in highlighted box** (18-24pt font, bold)
2. **Color-coded background**:
   - 🔴 Red (#FF4444) if %PNL < -1%
   - 🟡 Yellow (#FFAA00) if 0% <= %PNL < 5%
   - 🟢 Green (#44AA44) if %PNL >= 5% (target)
   - ⚪ Gray (#999999) if %PNL between -1% and 0%
3. **Live update** every 5 seconds from WebSocket
4. **Icon indicator** (📈🔴🟢) next to %PNL value

---

## 📊 Dashboard: HUB SUMMARY with Total P&L

### Updated Summary Section

```
BEFORE:
┌──────────────────────────────────────────────────────────┐
│ Active Bots: 3       │ Completed Epochs: 12              │
│ Total Portfolio: $4,850  │ Hub Profit (All-Time): +$2,340 │
└──────────────────────────────────────────────────────────┘

AFTER (with live hub %PNL):
┌──────────────────────────────────────────────────────────┐
│ Active Bots: 3       │ Completed Epochs: 12              │
│ Total Portfolio: $4,850 │ Free Balance: $2,450           │
│                                                          │
│ Hub Unrealized P&L:  +$127.50  (= sum all active bots)  │
│ Hub %PNL: +2.71% 🟡   ← COLOR-CODED, LARGE DISPLAY     │
│                                                          │
│ All-Time Profit (closed epochs): +$2,340                │
└──────────────────────────────────────────────────────────┘
```

---

## 🎯 Bot Detail Page: %PNL Prominence

### BEFORE Detail View

```
╔════════════════════════════════════════════════════════════════╗
║  louise_btc_001 (BTC/USDT)         ⚙️ [Edit Config]         ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  STATUS                                                        ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Current Status: ✅ ACCUMULATING                          │ ║
║  │ Bot Enabled: [Toggle] ON                                 │ ║
║  │ Epoch Duration: 5 days, 3 hours                          │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  MARKET & POSITION                                             ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Current Price (Live): $42,500                            │ ║
║  │ Last Buy Price:       $41,200                            │ ║
║  │ Avg Buy Price (VWAP): $40,850                            │ ║
║  │ Position Size: 0.0512 BTC                                │ ║
║  │ Total Cost:   $2,093.12                                  │ ║
║  │ Current Value: $2,152.00                                 │ ║
║  │ Unrealized P&L: +$58.88                                  │ ║
║  │ Unrealized P&L %: +2.81%                                 │ ║
║  │ Target Profit: 5.00% → Need +$46.65 more                │ ║
║  └──────────────────────────────────────────────────────────┘ ║
```

### AFTER Detail View (with %PNL Emphasis)

```
╔════════════════════════════════════════════════════════════════╗
║  louise_btc_001 (BTC/USDT)         ⚙️ [Edit Config]         ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  STATUS & PROFITABILITY (COMBINED)                             ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Status: ✅ ACCUMULATING                                  │ ║
║  │ Bot Enabled: [Toggle] ON                                 │ ║
║  │ Epoch Duration: 5 days, 3 hours                          │ ║
║  │                                                          │ ║
║  │ ╔════════════════════════════════════════════╗           │ ║
║  │ ║  UNREALIZED P&L: +2.81% 🟡                ║           │ ║
║  │ ║  (Current Position Profit vs. Cost Basis)  ║           │ ║
║  │ ║  $2,152 - $2,093 = +$59                    ║           │ ║
║  │ ║                                            ║           │ ║
║  │ ║  [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░]   ║           │ ║
║  │ ║   0%        Target: 5.00%        100%      ║           │ ║
║  │ ║   2.81% / 5.00% = 56% toward exit          ║           │ ║
║  │ ║                                            ║           ║
║  │ ║  Status: Need +2.19% more to exit          ║           │ ║
║  │ ╚════════════════════════════════════════════╝           │ ║
║  └──────────────────────────────────────────────────────────┘ ║
║                                                                ║
║  MARKET & POSITION DETAILS                                     ║
║  ┌──────────────────────────────────────────────────────────┐ ║
║  │ Current Price (Live): $42,500 ↑                          │ ║
║  │ Last Buy Price:       $41,200                            │ ║
║  │ Avg Buy Price (VWAP): $40,850                            │ ║
║  │                                                          │ ║
║  │ Position Size: 0.0512 BTC                                │ ║
║  │ Total Cost:   $2,093.12                                  │ ║
║  │ Current Value: $2,152.00                                 │ ║
║  └──────────────────────────────────────────────────────────┘ ║
```

---

## 📈 PNL Trend Chart (New Section)

### Added to Detail View

```
╔════════════════════════════════════════════════════════════════╗
║  %PNL TREND (Last 24 Hours)                                   ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  Current: +2.81% 🟡 (updated 3 seconds ago)                   ║
║                                                                ║
║    +10%│                                                       ║
║       │                                                       ║
║   +5%│═══════════════════════════════════════════════════     ║ TARGET LINE
║       │                             ╱═════════                ║
║     0%│═════════════════════════════╱                         ║
║       │     ╱══════════════╲                                  ║
║   -5%│════╱                ╲════════════════════════════       ║
║       │                                                       ║
║  -10%│                                                       ║
║       └───────────────────────────────────────────────       ║
║       0h    4h    8h   12h   16h   20h   24h                 ║
║                                                                ║
║  Statistics:                                                   ║
║  ├─ Minimum: -0.50% (at 6h mark)                             ║
║  ├─ Maximum: +3.50% (at 20h mark)                            ║
║  ├─ Average: +1.20%                                           ║
║  └─ Current: +2.81% (latest)                                 ║
║                                                                ║
║  [Last update: 3 seconds ago] [Refresh Now]                  ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
```

---

## 📋 Bot List View (Compact Monitoring)

### Scannable List with %PNL

```
ACTIVE BOTS

Bot Instance      │ Status  │ Price    │ %PNL       │ Position
──────────────────┼─────────┼──────────┼────────────┼────────────
louise_btc_001    │ ✅ RUN  │ $42,500  │ +2.81% 🟡  │ 0.0512 BTC
louise_eth_001    │ ✅ RUN  │ $2,145   │ -0.50% 🔴  │ 2.3 ETH
louise_sol_001    │ ✅ RUN  │ $151.20  │ +4.99% 🟡  │ 50 SOL
louise_ada_001    │ ⏸️ PAUSE│ $1.05    │ +1.50% ⚪   │ 150 ADA
louise_bnb_001    │ ✅ RUN  │ $2,850   │ +5.00% 🟢  │ 0.1 BNB


CLOSED BOTS

Bot Instance      │ Closed  │ Final %PNL │ Profit
──────────────────┼─────────┼────────────┼─────────
louise_xrp_001    │ 3 days  │ +6.20% 🟢  │ +$85.50
louise_matic_001  │ 5 days  │ +5.10% 🟢  │ +$75.00
louise_link_001   │ 2 days  │ +5.75% 🟢  │ +$89.50
```

**Why this works:**
- Operator can scan all %PNL values instantly
- Identifies which bots are close to exit (4.99%, 5.00%)
- Shows which are underwater (-0.50%)
- Quick overview of portfolio health

---

## 🔔 Alert Dialogs: PNL-Triggered

### Approaching Target Alert

```
╔─────────────────────────────────────────────────┐
│ 🟡 louise_btc_001 Approaching Target            │
├─────────────────────────────────────────────────┤
│                                                 │
│ Current %PNL: +4.95%                            │
│ Target:      +5.00%                             │
│ Remaining:   +0.05%                             │
│                                                 │
│ This bot will exit automatically when profit   │
│ reaches 5.00%. Monitor closely for the exit!   │
│                                                 │
│ [Dismiss] [View Details] [Monitor Live]        │
└─────────────────────────────────────────────────┘
```

### Target Reached Alert (Auto-Exit)

```
╔─────────────────────────────────────────────────┐
│ 🟢 louise_btc_001 TARGET REACHED! ✅             │
├─────────────────────────────────────────────────┤
│                                                 │
│ Epoch Status: CLOSED (SUCCESSFUL)               │
│ Final %PNL: +5.01%                              │
│ Profit: +$105.30                                │
│ Duration: 2 days, 14 hours                      │
│                                                 │
│ Position automatically sold at market price.   │
│ Epoch logged. Ready for new cycle.              │
│                                                 │
│ [Dismiss] [View Epoch Details] [Run Again]     │
└─────────────────────────────────────────────────┘
```

### Significant Drawdown Alert (Optional)

```
╔─────────────────────────────────────────────────┐
│ 🔴 louise_eth_001 Significant Drawdown          │
├─────────────────────────────────────────────────┤
│                                                 │
│ Current %PNL: -5.20%                            │
│ (Market dropped suddenly)                       │
│                                                 │
│ This bot is still buying on the dip per DCA   │
│ strategy. Will recover when market reverses.   │
│                                                 │
│ Actions:                                        │
│ • Keep bot running (normal for DCA)             │
│ • Monitor closely                               │
│ • Deposit more funds if budget exhausted        │
│                                                 │
│ [Dismiss] [View Details] [Pause Bot]           │
└─────────────────────────────────────────────────┘
```

---

## 🎨 Color Scheme Reference

### %PNL Color Mapping

```
HTML Colors for Implementation:

< -5%:        #FF1111 (Bright Red)
-5% to -1%:   #FF4444 (Red)
-1% to 0%:    #FFAA00 (Orange/Yellow)
 0% to 2%:    #999999 (Gray, neutral)
 2% to 5%:    #FFAA00 (Yellow, approaching target)
>= 5%:        #11BB11 (Bright Green, target!)
```

### Text Styling

```
%PNL Display:
- Font: Bold, 20-24pt
- Background: Color-coded (see above)
- Text Color: White (for visibility over colored background)
- Padding: 8px left/right, 4px top/bottom
- Border radius: 4px (slight rounding)
- Icon: Emoji indicator (📈🔴🟡🟢) next to value
```

---

## 📡 WebSocket Updates: %PNL Payload

### Message Broadcast Every 5 Seconds

```json
{
  "event": "metrics_update",
  "bot_id": "louise_btc_001",
  "timestamp": "2026-05-11T14:35:42.500Z",
  
  "price": {
    "current": 42500.50,
    "last_buy": 41200.00,
    "avg_buy": 40850.00
  },
  
  "position": {
    "size": 0.0512,
    "value_usdt": 2152.00,
    "total_cost": 2093.12
  },
  
  "pnl": {
    "unrealized_usdt": 58.88,
    "unrealized_pct": 2.81,         ← CRITICAL for UI
    "target_profit_pct": 5.0,       ← For progress bar
    "progress_percent": 56.2,       ← (2.81/5.0 * 100)
    "color_code": "yellow"          ← Pre-calculated for UI
  },
  
  "status": {
    "bot_status": "ACCUMULATING",
    "can_trade": true,
    "num_purchases": 8,
    "epoch_duration_minutes": 314
  },
  
  "account": {
    "free_balance": 450.00,
    "locked_balance": 100.00,
    "equity": 15850.00
  }
}
```

**UI receives this and immediately updates:**
- Bot card %PNL display (color changes if value changed)
- Detail page metrics (all fields)
- Progress bar (if applicable)
- Trend chart (adds new data point)
- Alerts (if approaching/reaching target)

---

## 🔄 Real-time Update Cycle

```
Bot Poll Every 5 Minutes:
  │
  ├─ [Calculate %PNL]
  │  ├─ current_value = position_size * current_price
  │  ├─ unrealized_pnl = current_value - total_cost
  │  └─ unrealized_pct = (unrealized_pnl / total_cost) * 100
  │
  ├─ [Prepare WebSocket payload]
  │  └─ Include: unrealized_pct, target_profit_pct, color_code
  │
  ├─ [Broadcast via WebSocket]
  │  └─ Send to: /ws/louise/metrics/{bot_id}
  │
  └─ [UI receives and updates]
     ├─ Bot card: %PNL value + color
     ├─ Detail view: all metrics
     ├─ Chart: new data point
     └─ Alerts: check thresholds
        └─ If >= target: show "SOLD" alert
        └─ If >= 4.5%: show "Approaching target" alert
        └─ If <= -5%: show "Drawdown" alert (optional)

Total latency: < 1 second from calculation to UI update
```

---

## 🧪 Testing Checklist

### Unit Tests

- [ ] PNL calculation: basic math
- [ ] Color code selection: %PNL maps to correct color
- [ ] Progress bar: 0-100% based on target
- [ ] Payload generation: all fields present
- [ ] Alert thresholds: correct triggers

### UI Widget Tests

- [ ] Bot card renders %PNL with correct color
- [ ] Detail view shows %PNL prominently
- [ ] Chart plots %PNL over time
- [ ] List view shows %PNL for all bots
- [ ] Colors update when %PNL changes

### Integration Tests

- [ ] WebSocket message updates UI
- [ ] Multiple bots update independently
- [ ] Alerts appear/disappear correctly
- [ ] No lag between calculation and display (< 1 second)
- [ ] Data persists in history

---

## 📋 Implementation Checklist (Phase 3)

### Dashboard Updates

- [ ] Add %PNL box to bot card
  - [ ] Large font (20-24pt)
  - [ ] Color-coded background
  - [ ] Icon indicator
  - [ ] Update every 5 seconds

- [ ] Update Hub Summary
  - [ ] Calculate hub-wide %PNL (sum active bots)
  - [ ] Display prominently
  - [ ] Color-code

### Detail Page Updates

- [ ] Reorganize to put %PNL at top
  - [ ] Add progress bar toward target
  - [ ] Show % progress (e.g., "56% toward exit")

- [ ] Add %PNL Trend Chart
  - [ ] Plot last 24h of %PNL
  - [ ] Show min/max/avg statistics
  - [ ] Mark current value

### List View

- [ ] Add %PNL column to bot list
  - [ ] Scannable format
  - [ ] Color-coded text
  - [ ] Sort by %PNL (optional)

### Alerts

- [ ] Approaching target (>= 4.5%)
- [ ] Target reached (>= 5.0%, auto-sell)
- [ ] Drawdown (optional, <= -5.0%)

### WebSocket Integration

- [ ] Include unrealized_pct in payload
- [ ] Include target_profit_pct for progress
- [ ] Include color_code for easy UI mapping
- [ ] Broadcast every 5 seconds

---

**Status:** Ready for Phase 3 Flutter UI Implementation  
**Effort:** ~8-10 hours (widgets + WebSocket integration + testing)  
**Impact:** CRITICAL (core requirement for real-time monitoring)
