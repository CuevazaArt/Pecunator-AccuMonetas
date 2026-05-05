# Task: Optimización de Rendimiento Earn/Loans

## Objetivo
Analizar tasas de rendimiento (earn) vs costos de deuda (loans) en tiempo real,
detectar oportunidades de carry trade, identificar capital ocioso, y proponer
movimientos para maximizar el yield neto del portfolio.

## Contexto del Proyecto
- **Earn rates log:** `earn_rates_log.csv` — histórico de tasas de earn
- **Earn rates último:** `earn_rates_last.txt` — snapshot más reciente
- **Loan rates log:** `loan_rates_log.csv` — histórico de tasas de préstamo
- **Loan rates último:** `loan_rates_last.txt` — snapshot más reciente
- **Suscribir a earn:** `subscribe_to_earn.py` — tool para depositar en earn
- **Redimir de earn:** `redeem_to_spot.py` — tool para sacar de earn a spot
- **Portfolio:** `portfolio_table.py` → `portfolio_report.txt`

## Pasos de Ejecución

### Paso 1 — Capturar Estado Actual
Parsear `earn_rates_last.txt` y `loan_rates_last.txt`:
- Extraer: producto, token, tasa actual (APY/APR), tipo (flexible/locked)

### Paso 2 — Análisis de Tendencia
Parsear `earn_rates_log.csv` (últimos 7 días mínimo):
- Calcular tasa promedio 7d por producto
- Calcular tendencia: ↑ subiendo / → estable / ↓ bajando
- Detectar caídas > 30% respecto a la semana anterior

Parsear `loan_rates_log.csv` (últimos 7 días mínimo):
- Calcular costo promedio 7d por token prestado
- Detectar incrementos sostenidos en costo de deuda

### Paso 3 — Detección de Oportunidades

#### A) Carry Trade Positivo
Buscar tokens donde:
```
earn_rate[token] > loan_rate[token]
```
Esto significa que puedes pedir prestado un token y simultáneamente
ponerlo en earn, ganando el diferencial (spread positivo).

#### B) Earn con Tasa Decreciente
Tokens actualmente en earn cuya tasa ha caído > 30% en 7 días.
→ Candidatos a `redeem_to_spot.py` y rotar a mejor producto.

#### C) Capital Ocioso
Tokens en spot wallet que NO están en earn ni en posiciones activas.
→ Candidatos a `subscribe_to_earn.py` si la tasa justifica.

#### D) Deuda Cara
Préstamos cuyo costo ha subido > 20% en 7 días sin que el earn
correspondiente haya subido proporcionalmente.
→ Evaluar cierre parcial del préstamo.

### Paso 4 — Cálculo de Impacto
Para cada oportunidad detectada, calcular:
- **Impacto estimado** — USD/día o USD/mes de rendimiento adicional
- **Riesgo** — Volatilidad del token, riesgo de liquidación
- **Esfuerzo** — ¿Requiere múltiples transacciones? ¿Hay lock period?

### Paso 5 — Generar Tabla de Acciones

```
## 💰 Oportunidades de Optimización — [FECHA]

### Rendimientos Actuales
| Token | Earn Rate | Tendencia 7d | En Portfolio | Estado |
|-------|-----------|-------------|-------------|--------|
| ...   | X.XX%     | ↑/→/↓       | Sí/No       | Earn/Spot/Loan |

### Costos de Deuda
| Token | Loan Rate | Tendencia 7d | Monto | Health Factor |
|-------|-----------|-------------|-------|---------------|
| ...   | X.XX%     | ↑/→/↓       | $XXX  | X.XX          |

### Acciones Recomendadas (por impacto)
| # | Acción | Token | Impacto Est. | Riesgo | Herramienta |
|---|--------|-------|-------------|--------|-------------|
| 1 | Suscribir a earn | XXX | +$X/día | Bajo | subscribe_to_earn.py |
| 2 | Redimir y rotar  | YYY | +$X/día | Bajo | redeem_to_spot.py |
| 3 | Carry trade      | ZZZ | +$X/día | Medio | Manual |
| 4 | Cerrar préstamo  | AAA | -$X/día ahorro | Bajo | Manual |
```

## Criterios de Éxito
- [ ] Tasas de earn y loan parseadas correctamente
- [ ] Tendencias de 7 días calculadas
- [ ] Al menos 1 oportunidad identificada (o confirmación de que no hay)
- [ ] Impacto estimado en USD para cada oportunidad
- [ ] Tabla de acciones generada y priorizada
