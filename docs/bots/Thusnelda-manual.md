# Manual de Usuario — Thusnelda (Hub)

## Qué hace

`Thusnelda` trabaja una cesta de símbolos (`symbols_csv`), compra por promedio histórico de compras y evalúa meta de equity global para salida integral.

## Variables clave (nuevas y existentes)

- `symbols_csv`: lista CSV de símbolos Spot
- `loop_interval_sec`, `between_symbol_sec`
- `quote_order_qty_modulo`
- `factor_multiplication`
- `meta_equity_usdt`
- `reference_ts_iso`
- `max_drawdown_pct`: **[MEJORA]** bloquea nuevas compras por riesgo agregado
- `stop_loss_pct`: **[MEJORA]** stop-loss por símbolo contra promedio de compras
- `metrics_interval_cycles`: **[MEJORA]** frecuencia de métricas

## Mejoras integradas (reemplazo incremental desde `exampleJV_enhanced`)

- **Drawdown guard** para evitar sobreacumulación en mercados adversos.
- **Stop-loss por símbolo** como protección adicional.
- **Persistencia robusta en SQLite:**
  - `thusnelda_runtime_state`
  - `thusnelda_equity_snapshots`
  - `thusnelda_metrics_log`
- **Métricas periódicas:** Sharpe, win rate y max drawdown.

## Dónde consultar datos en SQLite

Base: `runtime/data/thusnelda_hub.sqlite`

Consultas útiles:

```sql
SELECT * FROM thusnelda_metrics_log ORDER BY id DESC LIMIT 20;
SELECT * FROM thusnelda_equity_snapshots ORDER BY id DESC LIMIT 50;
SELECT * FROM thusnelda_runtime_state;
```

## Recomendación operativa

Ajustar `symbols_csv` hacia activos líquidos y monitorear drawdown agregado del portafolio para evitar exposición excesiva.
