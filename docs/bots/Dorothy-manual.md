# User Manual — Dorothy (Hub)

## What it does

`Dorothy` operates on a single Spot symbol with ladder logic:

- detects the lowest active `SELL LIMIT`
- waits for a sufficient drop relative to that anchor
- buys at market and places a new `SELL LIMIT` with a target profit

## Key variables (new and existing)

- `symbol`: Spot pair to trade (e.g. `XRPUSDT`)
- `loop_interval_sec`: interval between cycles
- `quote_order_qty`: buy size in quote (USDT)
- `profit_factor`: profit target per step
- `margin_drop_factor`: additional drop margin for a new purchase
- `max_drawdown_pct`: **[IMPROVEMENT]** blocks new purchases if the drawdown exceeds the threshold
- `stop_loss_pct`: **[IMPROVEMENT]** position protection exit when the price falls below the limit
- `metrics_interval_cycles`: **[IMPROVEMENT]** how many cycles to calculate Sharpe/win rate/max drawdown

## Integrated improvements (incremental replacement from `exampleJV_enhanced`)

- **Drawdown protection:** if equity drops more than the threshold, Dorothy enters `WAIT_DRAWDOWN_GUARD`.
- **Stop-loss per position:** can cancel the anchor `SELL LIMIT` and liquidate to market.
- **Robust SQLite persistence:**
  - `dorothy_runtime_state`
  - `dorothy_equity_snapshots`
  - `dorothy_metrics_log`
- **Periodic metrics:** Sharpe, win rate and max drawdown per instance.

## Where to query data in SQLite

Database: `runtime/data/dorothy_hub.sqlite`

Useful queries:

```sql
SELECT * FROM dorothy_metrics_log ORDER BY id DESC LIMIT 20;
SELECT * FROM dorothy_equity_snapshots ORDER BY id DESC LIMIT 50;
SELECT * FROM dorothy_runtime_state;
```

## Operational recommendation

Keep `simulated=true` when calibrating parameters and move to `trading_enabled=true` only after validating drawdown stability and metrics.
