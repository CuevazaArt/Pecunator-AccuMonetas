# Manual de Usuario — Masha (Hub)

## Qué hace

`Masha` usa señal técnica multi-timeframe (`1w` + `1h`) para comprar en zonas de debilidad y recalcular DCA con una salida `SELL LIMIT` consolidada.

## Variables clave (nuevas y existentes)

- `symbol`, `base_asset`, `quote_asset`
- `loop_interval_sec`
- `quote_min_free_to_operate`
- `buy_qty_base`
- `profit_factor`
- `timeframe_w`, `periods_w`, `mm_periods_w`, `margin_low_w`
- `timeframe_h`, `periods_h`, `mm_periods_h`, `margin_low_h`
- `max_drawdown_pct`: **[MEJORA]** frena nuevas compras si drawdown excede el umbral
- `stop_loss_pct`: **[MEJORA]** protege el DCA si el precio rompe el límite inferior
- `metrics_interval_cycles`: **[MEJORA]** periodicidad de métricas

## Mejoras integradas (reemplazo incremental desde `exampleJV_enhanced`)

- **Guardia de drawdown global** por instancia.
- **Stop-loss DCA:** cancela `SELL LIMIT` activa y permite liquidación de defensa.
- **Persistencia robusta en SQLite:**
  - `masha_runtime_state`
  - `masha_equity_snapshots`
  - `masha_metrics_log`
- **Métricas periódicas:** Sharpe, win rate y max drawdown.

## Dónde consultar datos en SQLite

Base: `runtime/data/masha_hub.sqlite`

Consultas útiles:

```sql
SELECT * FROM masha_metrics_log ORDER BY id DESC LIMIT 20;
SELECT * FROM masha_equity_snapshots ORDER BY id DESC LIMIT 50;
SELECT * FROM masha_runtime_state;
```

## Recomendación operativa

Usar períodos y márgenes conservadores al inicio, y validar en simulación varias sesiones antes de habilitar ejecución real.
