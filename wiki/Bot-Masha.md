# Bot Masha — Operating Manual

> Strategy: **multi-timeframe DCA** — technical signal at `1w` + `1h` to buy in areas of weakness and recalculate DCA with consolidated SELL LIMIT.

---

## What does Masha do

`Masha` uses technical signal on **two timeframes** (`1w` + `1h`) to:

1. Identify areas of **technical weakness** (low price compared to the moving average on both timeframes)
2. **Buy base amount** when both signals confirm entry zone
3. **Recalculate the average price** of all purchases (DCA)
4. Place a single consolidated **`SELL LIMIT`** above the average with `profit_factor`
5. Repeat the cycle waiting for new entry zones or the execution of the sale

---

## Module and entrypoints

| Concept | Route |
|----------|------|
| Runner | `runtime/modules/bots/masha.py` |
| Hub service | `runtime/api/bot_service.py` |
| SQLite | `runtime/data/masha_hub.sqlite` |
| UI | Masha Hub in `desktop_shell/lib/main.dart` |

---

## Configuration parameters

### Base parameters

| Parameters | Description |
|-----------|-------------|
| `symbol` | Spot pair to trade |
| `base_asset` | Base asset (e.g. `XRP`) |
| `quote_asset` | Active quote (e.g. `USDT`) |
| `loop_interval_sec` | Interval between cycles |
| `quote_min_free_to_operate` | Minimum quote free to operate (safety threshold) |
| `buy_qty_base` | Base amount per DCA purchase |
| `profit_factor` | Profit target over average DCA |

### Technical parameters — Weekly timeframe (`1w`)

| Parameters | Description |
|-----------|-------------|
| `timeframe_w` | Weekly timeframe (e.g. `1w`) |
| `periods_w` | Periods to analyze in `1w` |
| `mm_periods_w` | Moving average periods in `1w` |
| `margin_low_w` | Lower margin for weakness signal at `1w` |

### Technical parameters — Hourly timeframe (`1h`)

| Parameters | Description |
|-----------|-------------|
| `timeframe_h` | Hourly timeframe (e.g. `1h`) |
| `periods_h` | Periods to analyze in `1h` |
| `mm_periods_h` | Moving average periods in `1h` |
| `margin_low_h` | Lower margin for weakness signal in `1h` |

### Risk parameters and metrics

| Parameters | Description |
|-----------|-------------|
| `max_drawdown_pct` | **Drawdown guard:** stops new purchases if the drawdown exceeds this threshold |
| `stop_loss_pct` | **Stop-loss DCA:** protects the DCA if the price breaks the lower limit |
| `metrics_interval_cycles` | Metric calculation frequency |

---

## Integrated improvements

| Improve | Behavior |
|--------|---------------|
| **Drawdown save global** | If equity falls below the threshold, suspend new DCA purchases per instance |
| **Stop-loss DCA** | Cancels the active `SELL LIMIT` and allows defensive liquidation when the price breaks `stop_loss_pct` from the average |
| **Robust persistence** | State, equity snapshots and metrics in SQLite per instance |
| **Periodic metrics** | Sharpe ratio, win rate and max drawdown calculated periodically |

---

## SQLite tables

**Database:** `runtime/data/masha_hub.sqlite`

| Table | Content |
|-------|-----------|
| `masha_runtime_state` | Persistent runtime state (peak equity, cycles, average DCA) |
| `masha_equity_snapshots` | Periodic equity snapshots |
| `masha_metrics_log` | Calculated metrics (Sharpe, win rate, max drawdown) |

### Useful queries

```sql
-- Latest metrics
SELECT * FROM masha_metrics_log ORDER BY id DESC LIMIT 20;

-- Equity history
SELECT * FROM masha_equity_snapshots ORDER BY id DESC LIMIT 50;

-- Current status
SELECT * FROM masha_runtime_state;
```

---

## Technical signal logic

```
Weekly signal (1w):
  current_price < moving_average(mm_periods_w) * (1 - margin_low_w)
  
Signal time (1h):
  current_price < moving_average(mm_periods_h) * (1 - margin_low_h)

DCA Purchase Condition:
  signal_1w AND signal_1h AND drawdown_within_threshold AND quote_free >= quote_min_free_to_operate

SELL LIMIT Price:
  weighted_average_purchases * profit_factor
```

---

## Operational recommendation

> **Use conservative periods and margins at the beginning**, and validate several sessions in simulation before enabling real execution.

- Start with minimum `buy_qty_base` to measure signal behavior
- Moving average periods must be consistent with the liquidity of the symbol
- Wider `margin_low_w` → fewer signals → more selective (recommended for sideways markets)
- Monitor `masha_equity_snapshots` for excessive accumulation in downtrends
- Review `masha_metrics_log` periodically to adjust parameters according to win rate and Sharpe