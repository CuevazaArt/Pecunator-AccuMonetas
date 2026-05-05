# Thusnelda Bot — Operating Manual

> Strategy: **basket of symbols** — buy by historical average of purchases in multiple pairs and evaluate global equity target for comprehensive exit.

---

## What Thusnelda does

`Thusnelda` operates on a **list of Spot symbols** (`symbols_csv`) on a rotating basis:

1. For each symbol in the basket, evaluate whether the current price is **below the historical buying average** adjusted by `factor_multiplication`
2. If the price is favorable, **purchase** according to `quote_order_qty_modulo`
3. Periodically evaluate if the **total equity of the basket** exceeds `meta_equity_usdt`
4. If the goal is reached, you can liquidate basket positions towards USDT
5. Repeat with `between_symbol_sec` to wait between symbols

---

## Module and entrypoints

| Concept | Route |
|----------|------|
| Runner | `runtime/modules/bots/thusnelda.py` |
| Hub service | `runtime/api/thusnelda_service.py` |
| Surface API | `/api/v1/thusnelda/bots/*` |
| UI | Thusnelda Hub in `desktop_shell/lib/main.dart` |
| SQLite | `runtime/data/thusnelda_hub.sqlite` |

---

## Configuration parameters

### Base parameters

| Parameter | Description |
|-----------|-------------|
| `symbols_csv` | CSV list of Spot symbols to trade (e.g. `XRPUSDT,ADAUSDT,DOTUSDT`) |
| `loop_interval_sec` | Interval between complete cycles of the basket |
| `between_symbol_sec` | Pause between processing each basket symbol |
| `quote_order_qty_modulo` | Base purchase size in quote (can be modulated by symbol) |
| `factor_multiplication` | Multiplier factor on the historical average to activate purchase |
| `meta_equity_usdt` | Total basket equity goal in USDT to evaluate exit |
| `reference_ts_iso` | Reference ISO timestamp for historical average calculation |

### Risk parameters and metrics

| Parameter | Description |
|-----------|-------------|
| `max_drawdown_pct` | **Drawdown guard:** Blocks new purchases if the added drawdown exceeds this threshold |
| `stop_loss_pct` | **Stop-loss per symbol:** protection against average purchases per symbol |
| `metrics_interval_cycles` | Metric calculation frequency (Sharpe / win rate / max drawdown) |

---

## Integrated improvements

| Improve | Behavior |
|--------|---------------|
| **Drawdown guard added** | Avoid overaccumulation in adverse markets: block purchases if portfolio drawdown exceeds `max_drawdown_pct` |
| **Stop-loss per symbol** | Additional protection: if the price of a symbol falls below `stop_loss_pct` with respect to the buying average, activate defense |
| **Robust persistence** | State, equity snapshots and metrics in SQLite per instance |
| **Periodic metrics** | Sharpe ratio, win rate and max drawdown of the portfolio |

---

## SQLite tables

**Database:** `runtime/data/thusnelda_hub.sqlite`

| Table | Content |
|-------|-----------|
| `thusnelda_runtime_state` | Persistent runtime state per instance (peak equity, cycles, etc.) |
| `thusnelda_equity_snapshots` | Periodic Snapshots of Total Basket Equity |
| `thusnelda_metrics_log` | Calculated metrics (Sharpe, win rate, max drawdown) |

### Useful queries

```sql
-- Latest metrics
SELECT * FROM thusnelda_metrics_log ORDER BY id DESC LIMIT 20;

-- Equity history
SELECT * FROM thusnelda_equity_snapshots ORDER BY id DESC LIMIT 50;

-- Current status
SELECT * FROM thusnelda_runtime_state;
```

---

## Buy logic by symbol

```
Para cada símbolo en symbols_csv:
  promedio_compras = promedio_ponderado_histórico_compras(símbolo, desde reference_ts_iso)
  umbral_compra = promedio_compras * factor_multiplication
  
  Si precio_actual < umbral_compra
    Y drawdown_total < max_drawdown_pct
    Y equity_total < meta_equity_usdt:
      → Comprar quote_order_qty_modulo en quote
  
  Esperar between_symbol_sec antes del siguiente símbolo
```

---

## Key Differences vs Dorothy/Masha

| Appearance | Dorothy | Masha | Thusnelda |
|---------|---------|-------|-----------|
| Symbols | 1 | 1 | Multiple (basket) |
| Entrance sign | Fall vs anchor SELL LIMIT | Multi-timeframe technical signal | Price vs own historical average |
| Output | SELL LIMIT per step | SELL LIMIT consolidated DCA | Basket Global Equity Target |
| Risk scope | By position | By DCA position | By symbol + basket addition |

---

## Operational recommendation

> **Adjust `symbols_csv` towards liquid assets** and monitor aggregate portfolio drawdown to avoid excessive exposure.

- Start with 3-5 highly liquid symbols (BTC, ETH, XRP pairs with USDT)
- Validate that `meta_equity_usdt` is reachable but not too aggressive
- `factor_multiplication` < 1 means buy when the price falls relative to the average
- Monitor `thusnelda_equity_snapshots` for total basket value
- Check `thusnelda_metrics_log` for problematic symbols within the basket
- In sustained bear markets, consider reducing basket size or increasing `max_drawdown_pct` conservatively