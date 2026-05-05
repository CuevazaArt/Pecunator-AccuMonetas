# Bot Dorothy — Operating Manual

> Strategy: **spot ladder** — detect SELL LIMIT anchor + dip buy + new SELL LIMIT with target profit.

---

## What does Dorothy do?

`Dorothy` trades on a **single Spot symbol** with ladder logic:

1. Detects **lowest** active `SELL LIMIT` as anchor
2. Wait for **sufficient drop** with respect to that anchor
3. **Buy from market** when the drop exceeds the threshold
4. Place a new **`SELL LIMIT`** with target profit (`profit_factor`)

The cycle repeats, building a ladder of positions downward with programmed exits upward.

---

## Module and entrypoints

| Concept | Route |
|----------|------|
| Runner | `runtime/modules/bots/dorothy.py` |
| Hub service | `runtime/api/bot_service.py` |
| Surface API | `/api/v1/hub/bots/*` |
| UI | Dorothy Hub in `desktop_shell/lib/main.dart` |
| SQLite | `runtime/data/dorothy_hub.sqlite` |

---

## Configuration parameters

### Base parameters

| Parameter | Description |
|-----------|-------------|
| `symbol` | Spot pair to trade (e.g. `XRPUSDT`) |
| `loop_interval_sec` | Interval between cycles (seconds) |
| `quote_order_qty` | Buy size in quote (USDT) |
| `profit_factor` | Profit target per step (e.g. `1,015` = 1.5%) |
| `margin_drop_factor` | Additional drop margin required for new purchase |

### Risk parameters and metrics (built-in improvements)

| Parameter | Description |
|-----------|-------------|
| `max_drawdown_pct` | **Drawdown guard:** blocks new purchases if the drawdown exceeds this percentage |
| `stop_loss_pct` | **Stop-loss:** position protection exit when the price falls below the limit |
| `metrics_interval_cycles` | How many cycles to calculate metrics (Sharpe / win rate / max drawdown) |

### Operating parameters

| Parameter | Description |
|-----------|-------------|
| `simulated` | If `true`, simulate without executing real commands |
| `trading_enabled` | If `false`, only read status without operating |

---

## Integrated improvements

| Improve | Behavior |
|--------|---------------|
| **Drawdown save** | If the equity falls more than the `max_drawdown_pct` threshold, Dorothy enters the `WAIT_DRAWDOWN_GUARD` state and suspends new purchases |
| **Stop-loss per position** | You can cancel the `SELL LIMIT` anchor and liquidate the market if the price breaks `stop_loss_pct` |
| **Robust persistence** | State, equity snapshots and metrics persist in SQLite per instance |
| **Periodic metrics** | Sharpe ratio, win rate and max drawdown calculated every `metrics_interval_cycles` cycles |
| **Immortality** | If the engine restarts, instances marked `desired_running=true` automatically resume |
| **Retry with backoff** | Transient disconnections trigger client recreation + exponential backoff (`bot:retry_in ...`) |

---

## SQLite tables

**Database:** `runtime/data/dorothy_hub.sqlite`

| Table | Content |
|-------|-----------|
| `dorothy_instances` | Configuration and desired state of each instance |
| `dorothy_logs` | Cycle logs per instance |
| `dorothy_runtime_state` | Persistent runtime state (peak equity, cycles, etc.) |
| `dorothy_equity_snapshots` | Periodic snapshots of equity per instance |
| `dorothy_metrics_log` | Calculated metrics (Sharpe, win rate, max drawdown) |

### Useful queries

```sql
-- Latest metrics
SELECT * FROM dorothy_metrics_log ORDER BY id DESC LIMIT 20;

-- Equity history
SELECT * FROM dorothy_equity_snapshots ORDER BY id DESC LIMIT 50;

-- Current status of instances
SELECT * FROM dorothy_runtime_state;

-- Configured instances
SELECT * FROM dorothy_instances;
```

---

## Life cycle of an instance

```
Crear instancia (POST /api/v1/hub/bots)
       ↓
Configurar parámetros (symbol, qty, profit_factor, riesgo)
       ↓
[Opcional] Arrancar en modo simulated=true para calibrar
       ↓
Validar estabilidad de drawdown y métricas
       ↓
Activar trading_enabled=true + simulated=false
       ↓
Monitor continuo desde Dorothy Hub en la UI
```

---

## Bot States

| Status | Description |
|--------|-------------|
| `IDLE` | No anchor order detected, waiting |
| `WAIT_DROP` | Anchor detected, waiting for enough drop |
| `BUYING` | Executing market purchase |
| `PLACING_SELL` | Placing new SELL LIMIT |
| `WAIT_DRAWDOWN_GUARD` | Drawdown overcome, purchases suspended |

---

## Operational recommendation

> **Keep `simulated=true` when calibrating parameters** and move to `trading_enabled=true` only after validating drawdown stability and metrics across multiple sessions.

- Start with small `quote_order_qty` to check behavior
- Monitor `dorothy_equity_snapshots` for drawdown trend
- Adjust `margin_drop_factor` and `profit_factor` according to volatility of the traded symbol