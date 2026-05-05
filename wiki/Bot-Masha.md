# Bot Masha — Manual Operativo

> Estrategia: **DCA multi-timeframe** — señal técnica en `1w` + `1h` para comprar en zonas de debilidad y recalcular DCA con SELL LIMIT consolidada.

---

## Qué hace Masha

`Masha` usa señal técnica en **dos timeframes** (`1w` + `1h`) para:

1. Identificar zonas de **debilidad técnica** (precio bajo respecto a media móvil en ambos timeframes)
2. **Comprar cantidad base** cuando ambas señales confirman zona de entrada
3. **Recalcular el precio promedio** de todas las compras (DCA)
4. Colocar una única **`SELL LIMIT` consolidada** sobre el promedio con `profit_factor`
5. Repetir ciclo esperando nuevas zonas de entrada o la ejecución de la venta

---

## Módulo y entrypoints

| Concepto | Ruta |
|----------|------|
| Runner | `runtime/modules/bots/masha.py` |
| Hub service | `runtime/api/bot_service.py` |
| SQLite | `runtime/data/masha_hub.sqlite` |
| UI | Masha Hub en `desktop_shell/lib/main.dart` |

---

## Parámetros de configuración

### Parámetros base

| Parámetro | Descripción |
|-----------|-------------|
| `symbol` | Par Spot a operar |
| `base_asset` | Activo base (ej. `XRP`) |
| `quote_asset` | Activo quote (ej. `USDT`) |
| `loop_interval_sec` | Intervalo entre ciclos |
| `quote_min_free_to_operate` | Quote mínimo libre para operar (umbral de seguridad) |
| `buy_qty_base` | Cantidad base por compra DCA |
| `profit_factor` | Objetivo de beneficio sobre el promedio DCA |

### Parámetros técnicos — Timeframe semanal (`1w`)

| Parámetro | Descripción |
|-----------|-------------|
| `timeframe_w` | Timeframe semanal (ej. `1w`) |
| `periods_w` | Períodos a analizar en `1w` |
| `mm_periods_w` | Períodos de media móvil en `1w` |
| `margin_low_w` | Margen inferior para señal de debilidad en `1w` |

### Parámetros técnicos — Timeframe horario (`1h`)

| Parámetro | Descripción |
|-----------|-------------|
| `timeframe_h` | Timeframe horario (ej. `1h`) |
| `periods_h` | Períodos a analizar en `1h` |
| `mm_periods_h` | Períodos de media móvil en `1h` |
| `margin_low_h` | Margen inferior para señal de debilidad en `1h` |

### Parámetros de riesgo y métricas

| Parámetro | Descripción |
|-----------|-------------|
| `max_drawdown_pct` | **Drawdown guard:** frena nuevas compras si el drawdown excede este umbral |
| `stop_loss_pct` | **Stop-loss DCA:** protege el DCA si el precio rompe el límite inferior |
| `metrics_interval_cycles` | Periodicidad de cálculo de métricas |

---

## Mejoras integradas

| Mejora | Comportamiento |
|--------|---------------|
| **Drawdown guard global** | Si el equity cae más del umbral, suspende nuevas compras DCA por instancia |
| **Stop-loss DCA** | Cancela la `SELL LIMIT` activa y permite liquidación de defensa cuando el precio rompe `stop_loss_pct` respecto al promedio |
| **Persistencia robusta** | Estado, equity snapshots y métricas en SQLite por instancia |
| **Métricas periódicas** | Sharpe ratio, win rate y max drawdown calculados periódicamente |

---

## Tablas SQLite

**Base de datos:** `runtime/data/masha_hub.sqlite`

| Tabla | Contenido |
|-------|-----------|
| `masha_runtime_state` | Estado de runtime persistido (peak equity, ciclos, promedio DCA) |
| `masha_equity_snapshots` | Snapshots periódicos de equity |
| `masha_metrics_log` | Métricas calculadas (Sharpe, win rate, max drawdown) |

### Consultas útiles

```sql
-- Últimas métricas
SELECT * FROM masha_metrics_log ORDER BY id DESC LIMIT 20;

-- Historial de equity
SELECT * FROM masha_equity_snapshots ORDER BY id DESC LIMIT 50;

-- Estado actual
SELECT * FROM masha_runtime_state;
```

---

## Lógica de señal técnica

```
Señal semanal (1w):
  precio_actual < media_movil(mm_periods_w) * (1 - margin_low_w)
  
Señal horaria (1h):
  precio_actual < media_movil(mm_periods_h) * (1 - margin_low_h)

Condición de compra DCA:
  señal_1w AND señal_1h AND drawdown_dentro_umbral AND quote_libre >= quote_min_free_to_operate

Precio SELL LIMIT:
  promedio_ponderado_compras * profit_factor
```

---

## Recomendación operativa

> **Usar períodos y márgenes conservadores al inicio**, y validar en simulación varias sesiones antes de habilitar ejecución real.

- Comenzar con `buy_qty_base` mínimo para medir el comportamiento de la señal
- Los períodos de media móvil deben ser coherentes con la liquidez del símbolo
- `margin_low_w` más amplio → menos señales → más selectivo (recomendado para mercados laterales)
- Monitorear `masha_equity_snapshots` para detectar acumulación excesiva en tendencias bajistas
- Revisar `masha_metrics_log` periódicamente para ajustar parámetros según win rate y Sharpe
