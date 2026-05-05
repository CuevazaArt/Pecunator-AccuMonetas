# Bot Dorothy — Manual Operativo

> Estrategia: **escalera spot** — detecta ancla SELL LIMIT + compra en caída + nueva SELL LIMIT con beneficio objetivo.

---

## Qué hace Dorothy

`Dorothy` opera en un **solo símbolo Spot** con lógica de escalera:

1. Detecta la `SELL LIMIT` activa **más baja** como ancla
2. Espera una **caída suficiente** respecto a ese ancla
3. **Compra a mercado** cuando la caída supera el umbral
4. Coloca una nueva **`SELL LIMIT`** con beneficio objetivo (`profit_factor`)

El ciclo se repite, construyendo una escalera de posiciones hacia abajo con salidas programadas hacia arriba.

---

## Módulo y entrypoints

| Concepto | Ruta |
|----------|------|
| Runner | `runtime/modules/bots/dorothy.py` |
| Hub service | `runtime/api/bot_service.py` |
| API surface | `/api/v1/hub/bots/*` |
| UI | Dorothy Hub en `desktop_shell/lib/main.dart` |
| SQLite | `runtime/data/dorothy_hub.sqlite` |

---

## Parámetros de configuración

### Parámetros base

| Parámetro | Descripción |
|-----------|-------------|
| `symbol` | Par Spot a operar (ej. `XRPUSDT`) |
| `loop_interval_sec` | Intervalo entre ciclos (segundos) |
| `quote_order_qty` | Tamaño de compra en quote (USDT) |
| `profit_factor` | Objetivo de beneficio por escalón (ej. `1.015` = 1.5%) |
| `margin_drop_factor` | Margen adicional de caída requerido para nueva compra |

### Parámetros de riesgo y métricas (mejoras integradas)

| Parámetro | Descripción |
|-----------|-------------|
| `max_drawdown_pct` | **Drawdown guard:** bloquea nuevas compras si el drawdown excede este porcentaje |
| `stop_loss_pct` | **Stop-loss:** salida de protección por posición cuando el precio cae bajo el límite |
| `metrics_interval_cycles` | Cada cuántos ciclos calcular métricas (Sharpe / win rate / max drawdown) |

### Parámetros operativos

| Parámetro | Descripción |
|-----------|-------------|
| `simulated` | Si `true`, simula sin ejecutar órdenes reales |
| `trading_enabled` | Si `false`, solo lee estado sin operar |

---

## Mejoras integradas

| Mejora | Comportamiento |
|--------|---------------|
| **Drawdown guard** | Si el equity cae más del umbral `max_drawdown_pct`, Dorothy entra en estado `WAIT_DRAWDOWN_GUARD` y suspende nuevas compras |
| **Stop-loss por posición** | Puede cancelar la `SELL LIMIT` ancla y liquidar a mercado si el precio rompe `stop_loss_pct` |
| **Persistencia robusta** | Estado, snapshots de equity y métricas persisten en SQLite por instancia |
| **Métricas periódicas** | Sharpe ratio, win rate y max drawdown calculados cada `metrics_interval_cycles` ciclos |
| **Inmortalidad** | Si el motor reinicia, las instancias marcadas como `desired_running=true` se reanudan automáticamente |
| **Retry con backoff** | Desconexiones transitorias activan recreación de cliente + backoff exponencial (`bot:retry_in ...`) |

---

## Tablas SQLite

**Base de datos:** `runtime/data/dorothy_hub.sqlite`

| Tabla | Contenido |
|-------|-----------|
| `dorothy_instances` | Configuración y estado deseado de cada instancia |
| `dorothy_logs` | Logs de ciclo por instancia |
| `dorothy_runtime_state` | Estado de runtime persistido (peak equity, ciclos, etc.) |
| `dorothy_equity_snapshots` | Snapshots periódicos de equity por instancia |
| `dorothy_metrics_log` | Métricas calculadas (Sharpe, win rate, max drawdown) |

### Consultas útiles

```sql
-- Últimas métricas
SELECT * FROM dorothy_metrics_log ORDER BY id DESC LIMIT 20;

-- Historial de equity
SELECT * FROM dorothy_equity_snapshots ORDER BY id DESC LIMIT 50;

-- Estado actual de instancias
SELECT * FROM dorothy_runtime_state;

-- Instancias configuradas
SELECT * FROM dorothy_instances;
```

---

## Ciclo de vida de una instancia

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

## Estados del bot

| Estado | Descripción |
|--------|-------------|
| `IDLE` | Sin orden ancla detectada, esperando |
| `WAIT_DROP` | Ancla detectada, esperando caída suficiente |
| `BUYING` | Ejecutando compra a mercado |
| `PLACING_SELL` | Colocando nueva SELL LIMIT |
| `WAIT_DRAWDOWN_GUARD` | Drawdown superado, compras suspendidas |

---

## Recomendación operativa

> **Mantener `simulated=true` al calibrar parámetros** y mover a `trading_enabled=true` solo después de validar estabilidad de drawdown y métricas en múltiples sesiones.

- Empezar con `quote_order_qty` pequeño para verificar el comportamiento
- Monitorear `dorothy_equity_snapshots` para detectar tendencia de drawdown
- Ajustar `margin_drop_factor` y `profit_factor` según volatilidad del símbolo operado
