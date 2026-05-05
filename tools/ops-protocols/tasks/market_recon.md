# Task: Reconocimiento de Mercado Diario

## Objetivo
Ejecutar un barrido completo del estado del mercado usando las herramientas
existentes de Pecunator y generar un briefing ejecutivo consolidado.

## Contexto del Proyecto
- **Clasificador de tokens:** `token_classifier.py` → genera `token_classification.txt`
- **Monitor alpha:** `alpha_monitor.py` + `get_alpha_wallet.py`
- **Tasas de earn:** `earn_rate_monitor.py` → logs en `earn_rates_log.csv` / `earn_rates_last.txt`
- **Tasas de préstamo:** `loan_rate_monitor.py` → logs en `loan_rates_log.csv` / `loan_rates_last.txt`
- **Portfolio actual:** `portfolio_table.py` → genera `portfolio_report.txt`

## Pasos de Ejecución

### Paso 1 — Snapshot de Portfolio
Ejecutar `python portfolio_table.py` desde la raíz del proyecto.
Capturar el reporte generado en `portfolio_report.txt`.
Extraer: posiciones actuales, pesos porcentuales, PnL no realizado.

### Paso 2 — Clasificación de Tokens
Revisar `token_classification.txt` (último output de `token_classifier.py`).
Si tiene más de 24h de antigüedad, re-ejecutar `python token_classifier.py`.
Extraer: tokens por categoría (blue-chip, mid-cap, speculative, stablecoin).

### Paso 3 — Oportunidades Alpha
Ejecutar `python alpha_monitor.py` en modo consulta.
Identificar: tokens con movimientos inusuales, volumen anómalo, o señales técnicas.

### Paso 4 — Análisis de Tasas
Parsear `earn_rates_log.csv`:
- Calcular tendencia de tasa a 7 días por producto (subiendo/bajando/estable)
- Identificar productos con tasa > 5% APY que estén subiendo

Parsear `loan_rates_log.csv`:
- Calcular costo promedio de deuda
- Detectar si algún préstamo tiene tasa creciente sostenida

### Paso 5 — Cruce de Datos
- ¿Hay tokens en cartera con tasas de earn decrecientes? → Candidatos a rotar
- ¿Hay tokens idle en spot que podrían estar generando yield?
- ¿El costo de algún préstamo supera el rendimiento del earn correspondiente?

### Paso 6 — Generar Briefing
Crear artefacto `daily_briefing_YYYY-MM-DD.md` con:

```
## 📊 Briefing de Mercado — [FECHA]

### Estado del Portfolio
[Resumen de posiciones principales y PnL]

### Señales Alpha
[Oportunidades detectadas por el monitor]

### Rendimientos (Earn)
[Tabla de tasas actuales vs tendencia]

### Costos de Deuda (Loans)
[Estado de préstamos y health factors]

### ⚡ Acciones Sugeridas
1. [Acción prioritaria 1]
2. [Acción prioritaria 2]
3. [Acción prioritaria 3]

### ⚠️ Alertas
[Cualquier condición que requiera atención inmediata]
```

## Criterios de Éxito
- [ ] Portfolio snapshot generado (< 5 min de antigüedad)
- [ ] Clasificación de tokens actualizada
- [ ] Tendencias de tasas calculadas con datos de últimos 7 días
- [ ] Al menos 1 acción concreta sugerida
- [ ] Briefing entregado como artefacto con formato legible
