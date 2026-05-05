# Bot Thusnelda — Manual Operativo

> Estrategia: **cesta de símbolos** — compra por promedio histórico de compras en múltiples pares y evalúa meta de equity global para salida integral.

---

## Qué hace Thusnelda

`Thusnelda` opera sobre una **lista de símbolos Spot** (`symbols_csv`) de forma rotativa:

1. Para cada símbolo en la cesta, evalúa si el precio actual está por **debajo del promedio histórico de compras** ajustado por `factor_multiplication`
2. Si el precio es favorable, **compra** según `quote_order_qty_modulo`
3. Evalúa periódicamente si el **equity total de la cesta** supera `meta_equity_usdt`
4. Si se alcanza la meta, puede liquidar posiciones de la cesta hacia USDT
5. Repite con `between_symbol_sec` de espera entre símbolo y símbolo

---

## Módulo y entrypoints

| Concepto | Ruta |
|----------|------|
| Runner | `runtime/modules/bots/thusnelda.py` |
| Hub service | `runtime/api/thusnelda_service.py` |
| API surface | `/api/v1/thusnelda/bots/*` |
| UI | Thusnelda Hub en `desktop_shell/lib/main.dart` |
| SQLite | `runtime/data/thusnelda_hub.sqlite` |

---

## Parámetros de configuración

### Parámetros base

| Parámetro | Descripción |
|-----------|-------------|
| `symbols_csv` | Lista CSV de símbolos Spot a operar (ej. `XRPUSDT,ADAUSDT,DOTUSDT`) |
| `loop_interval_sec` | Intervalo entre ciclos completos de la cesta |
| `between_symbol_sec` | Pausa entre el procesamiento de cada símbolo de la cesta |
| `quote_order_qty_modulo` | Tamaño base de compra en quote (puede modularse por símbolo) |
| `factor_multiplication` | Factor multiplicador sobre el promedio histórico para activar compra |
| `meta_equity_usdt` | Meta de equity total de la cesta en USDT para evaluar salida |
| `reference_ts_iso` | Timestamp ISO de referencia para cálculo de promedio histórico |

### Parámetros de riesgo y métricas

| Parámetro | Descripción |
|-----------|-------------|
| `max_drawdown_pct` | **Drawdown guard:** bloquea nuevas compras si el drawdown agregado excede este umbral |
| `stop_loss_pct` | **Stop-loss por símbolo:** protección contra promedio de compras por símbolo |
| `metrics_interval_cycles` | Frecuencia de cálculo de métricas (Sharpe / win rate / max drawdown) |

---

## Mejoras integradas

| Mejora | Comportamiento |
|--------|---------------|
| **Drawdown guard agregado** | Evita sobreacumulación en mercados adversos: bloquea compras si el drawdown del portfolio supera `max_drawdown_pct` |
| **Stop-loss por símbolo** | Protección adicional: si el precio de un símbolo cae bajo `stop_loss_pct` respecto al promedio de compras, activa defensa |
| **Persistencia robusta** | Estado, equity snapshots y métricas en SQLite por instancia |
| **Métricas periódicas** | Sharpe ratio, win rate y max drawdown del portfolio |

---

## Tablas SQLite

**Base de datos:** `runtime/data/thusnelda_hub.sqlite`

| Tabla | Contenido |
|-------|-----------|
| `thusnelda_runtime_state` | Estado de runtime persistido por instancia (peak equity, ciclos, etc.) |
| `thusnelda_equity_snapshots` | Snapshots periódicos de equity total de la cesta |
| `thusnelda_metrics_log` | Métricas calculadas (Sharpe, win rate, max drawdown) |

### Consultas útiles

```sql
-- Últimas métricas
SELECT * FROM thusnelda_metrics_log ORDER BY id DESC LIMIT 20;

-- Historial de equity
SELECT * FROM thusnelda_equity_snapshots ORDER BY id DESC LIMIT 50;

-- Estado actual
SELECT * FROM thusnelda_runtime_state;
```

---

## Lógica de compra por símbolo

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

## Diferencias clave vs Dorothy/Masha

| Aspecto | Dorothy | Masha | Thusnelda |
|---------|---------|-------|-----------|
| Símbolos | 1 | 1 | Múltiples (cesta) |
| Señal de entrada | Caída vs ancla SELL LIMIT | Señal técnica multi-timeframe | Precio vs promedio histórico propio |
| Salida | SELL LIMIT por escalón | SELL LIMIT DCA consolidada | Meta de equity global de cesta |
| Scope de riesgo | Por posición | Por posición DCA | Por símbolo + agregado de cesta |

---

## Recomendación operativa

> **Ajustar `symbols_csv` hacia activos líquidos** y monitorear el drawdown agregado del portfolio para evitar exposición excesiva.

- Comenzar con 3-5 símbolos de alta liquidez (BTC, ETH, XRP pares con USDT)
- Validar que `meta_equity_usdt` sea alcanzable pero no demasiado agresivo
- `factor_multiplication` < 1 significa comprar cuando el precio baja respecto al promedio
- Monitorear `thusnelda_equity_snapshots` para el valor total de la cesta
- Revisar `thusnelda_metrics_log` para detectar símbolos problemáticos dentro de la cesta
- En mercados bajistas sostenidos, considerar reducir el tamaño de la cesta o aumentar `max_drawdown_pct` conservadoramente
