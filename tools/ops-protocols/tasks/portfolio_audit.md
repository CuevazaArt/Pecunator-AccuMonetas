# Task: Auditoría Profunda de Portfolio

## Objetivo
Ejecutar una auditoría completa del portfolio, analizar desviaciones respecto
a la sesión anterior, calcular métricas de riesgo, y proponer acciones
de rebalanceo si corresponde.

## Contexto del Proyecto
- **Auditoría completa:** `audit_full.py` → genera `audit_report.txt`
- **Reporte de préstamos:** `loans_report.py` → genera `loans_report.txt`
- **Tabla de portfolio:** `portfolio_table.py` → genera `portfolio_report.txt`
- **Clasificación:** `token_classification.txt`

## Pasos de Ejecución

### Paso 1 — Generar Reportes Frescos
```bash
python audit_full.py
python loans_report.py
python portfolio_table.py
```
Verificar que los 3 reportes se generaron exitosamente.

### Paso 2 — Análisis de Posiciones
Parsear `audit_report.txt` y `portfolio_report.txt`:
- Listar todas las posiciones con: token, cantidad, valor USD, peso %
- Calcular concentración: ¿Algún token supera el 25% del portfolio?
- Clasificar exposición por sector (usando `token_classification.txt`)

### Paso 3 — Análisis de Deuda
Parsear `loans_report.txt`:
- Extraer préstamos activos: token, monto, tasa, colateral, health factor
- Calcular ratio deuda/equity total
- Identificar préstamos con health factor < 1.5

### Paso 4 — Detección de Drift
Si existe un reporte de auditoría previo (archivo anterior o en historial):
- Comparar pesos actuales vs anteriores
- Detectar posiciones que crecieron/decrecieron > 10%
- Detectar nuevas posiciones o posiciones cerradas

### Paso 5 — Métricas de Riesgo
Calcular y reportar:
| Métrica | Fórmula | Umbral |
|---|---|---|
| Concentración máxima | max(peso_token) | ⚠️ > 25% |
| Ratio deuda/equity | deuda_total / equity_total | ⚠️ > 0.5 |
| Health factor mínimo | min(HF por préstamo) | 🔴 < 1.3, ⚠️ < 1.5 |
| Tokens idle en spot | tokens sin earn ni posición | 💡 oportunidad |
| Earn rate vs loan cost | spread entre rendimiento y costo | 💡 si positivo |

### Paso 6 — Recomendaciones
Generar lista priorizada de acciones:
1. **URGENTE** — Posiciones que requieren acción inmediata (health factor bajo)
2. **OPTIMIZAR** — Rebalanceos para reducir concentración
3. **OPORTUNIDAD** — Tokens idle que podrían generar rendimiento
4. **MONITOREAR** — Posiciones que no requieren acción pero merecen vigilancia

## Criterios de Alerta
- 🔴 **CRITICAL**: Health factor < 1.3 en cualquier préstamo
- ⚠️ **WARNING**: Concentración > 25% en un solo token
- ⚠️ **WARNING**: Ratio deuda/equity > 0.5
- 💡 **INFO**: Capital idle > 5% del portfolio total

## Output Esperado
Artefacto `audit_YYYY-MM-DD.md` con todas las métricas, tablas y recomendaciones.

## Criterios de Éxito
- [ ] Los 3 reportes base generados sin errores
- [ ] Métricas de riesgo calculadas
- [ ] Drift detectado (si hay datos previos disponibles)
- [ ] Al menos 1 recomendación accionable generada
- [ ] Artefacto entregado con formato tabular legible
