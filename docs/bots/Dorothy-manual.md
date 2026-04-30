# Manual de Usuario — Dorothy (Hub)

## Qué hace

`Dorothy` opera en un solo símbolo Spot con lógica de escalera:

- detecta la `SELL LIMIT` activa más baja
- espera caída suficiente respecto a ese ancla
- compra a mercado y coloca nueva `SELL LIMIT` con beneficio objetivo

## Variables clave (nuevas y existentes)

- `symbol`: par Spot a operar (ej. `XRPUSDT`)
- `loop_interval_sec`: intervalo entre ciclos
- `quote_order_qty`: tamaño de compra en quote (USDT)
- `profit_factor`: objetivo de beneficio por escalón
- `margin_drop_factor`: margen adicional de caída para nueva compra
- `max_drawdown_pct`: **[MEJORA]** bloqueo de nuevas compras si el drawdown excede el umbral
- `stop_loss_pct`: **[MEJORA]** salida de protección por posición cuando el precio cae bajo el límite
- `metrics_interval_cycles`: **[MEJORA]** cada cuántos ciclos calcular Sharpe/win rate/max drawdown

## Mejoras integradas (reemplazo incremental desde `exampleJV_enhanced`)

- **Protección por drawdown:** si el equity cae más del umbral, Dorothy entra en `WAIT_DRAWDOWN_GUARD`.
- **Stop-loss por posición:** puede cancelar la `SELL LIMIT` ancla y liquidar a mercado.
- **Persistencia robusta en SQLite:**
  - `dorothy_runtime_state`
  - `dorothy_equity_snapshots`
  - `dorothy_metrics_log`
- **Métricas periódicas:** Sharpe, win rate y max drawdown por instancia.

## Dónde consultar datos en SQLite

Base: `runtime/data/dorothy_hub.sqlite`

Consultas útiles:

```sql
SELECT * FROM dorothy_metrics_log ORDER BY id DESC LIMIT 20;
SELECT * FROM dorothy_equity_snapshots ORDER BY id DESC LIMIT 50;
SELECT * FROM dorothy_runtime_state;
```

## Recomendación operativa

Mantener `simulated=true` al calibrar parámetros y mover a `trading_enabled=true` solo después de validar estabilidad de drawdown y métricas.
