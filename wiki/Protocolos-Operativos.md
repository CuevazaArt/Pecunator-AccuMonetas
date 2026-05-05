# Protocolos Operativos — Pecunator

> Runbooks y protocolos de operación para el LLM y el operador.  
> Fuente: `tools/ops-protocols/tasks/`

---

## Protocolos de Emergencia (API)

Estos endpoints están disponibles en tiempo real desde la UI Flutter o vía API REST:

### Botón Rojo — `POST /api/v1/ops/red_button`

Detiene **todos** los bots activos inmediatamente.

```bash
curl -X POST http://127.0.0.1:8765/api/v1/ops/red_button?base_asset=USDT
```

> ⚠️ Dorothy se detiene **antes** de la operación para evitar loops de disposición.

### Protocolo de Cierre — `POST /api/v1/ops/protocol/close`

Cierre controlado: detiene bots + cierra posiciones hacia USDT.

```bash
curl -X POST http://127.0.0.1:8765/api/v1/ops/protocol/close?base_asset=USDT
```

### Limpieza de Órdenes

```bash
# Cancelar órdenes LIMIT abiertas
curl -X POST http://127.0.0.1:8765/api/v1/ops/orders/cleanup/limit

# Cancelar órdenes STOP abiertas
curl -X POST http://127.0.0.1:8765/api/v1/ops/orders/cleanup/stop

# Cancelar TODAS las órdenes abiertas
curl -X POST http://127.0.0.1:8765/api/v1/ops/orders/cleanup/all
```

### Estado del Protocolo

```bash
curl http://127.0.0.1:8765/api/v1/ops/protocol/status
```

---

## Runbooks del IDE (Tasks)

Tasks ejecutables por el LLM en el IDE. Cada Task codifica un protocolo reproducible.

| Task | Archivo | Cuándo usar |
|------|---------|-------------|
| **Market Recon** | `tasks/market_recon.md` | Briefing diario de mercado |
| **Portfolio Audit** | `tasks/portfolio_audit.md` | Auditoría profunda con métricas de riesgo |
| **Bot Health Check** | `tasks/bot_health_check.md` | Verificación de integridad del runtime |
| **Code Hardening** | `tasks/code_hardening.md` | Pasada de calidad incremental |
| **Yield Optimizer** | `tasks/yield_optimizer.md` | Análisis de earn/loan y carry trade |
| **Shell Build Verify** | `tasks/shell_build_verify.md` | Análisis y build Flutter |
| **Sub-Account Ops** | `tasks/subaccount_ops.md` | Subcuentas Binance |
| **Emergency Protocol** | `tasks/emergency_protocol.md` | Diagnóstico defensivo en emergencias |

---

## Task: Reconocimiento de Mercado Diario

**Objetivo:** Barrido completo del estado del mercado y briefing ejecutivo consolidado.

### Herramientas utilizadas

| Herramienta | Salida |
|-------------|--------|
| `python portfolio_table.py` | `portfolio_report.txt` — posiciones, pesos, PnL |
| `python token_classifier.py` | `token_classification.txt` — clasificación por categoría |
| `python alpha_monitor.py` | Tokens con movimientos inusuales |
| `earn_rates_log.csv` | Tendencia de tasas earn (7 días) |
| `loan_rates_log.csv` | Costo de deuda y tendencia |

### Pasos de ejecución

1. **Snapshot de Portfolio** — Ejecutar `python portfolio_table.py`
2. **Clasificación de Tokens** — Revisar/actualizar `token_classification.txt`
3. **Oportunidades Alpha** — Ejecutar `python alpha_monitor.py`
4. **Análisis de Tasas** — Parsear logs de earn y loan
5. **Cruce de datos** — Detectar candidatos a rotar, idle, o préstamos caros
6. **Generar Briefing** — Artefacto `daily_briefing_YYYY-MM-DD.md`

### Formato del briefing

```markdown
## 📊 Briefing de Mercado — [FECHA]

### Estado del Portfolio
[Resumen de posiciones principales y PnL]

### Señales Alpha
[Oportunidades detectadas]

### Rendimientos (Earn)
[Tabla de tasas actuales vs tendencia]

### Costos de Deuda (Loans)
[Estado de préstamos y health factors]

### ⚡ Acciones Sugeridas
1. [Acción prioritaria 1]
2. [Acción prioritaria 2]

### ⚠️ Alertas
[Condiciones que requieren atención inmediata]
```

---

## Task: Protocolo de Emergencia

> ⛔ **REGLA ABSOLUTA:** Este task **nunca** ejecuta operaciones por sí solo.  
> Solo diagnostica, analiza y presenta opciones. Cualquier acción sobre fondos requiere confirmación explícita.

### Triggers

- Crash de mercado > 15% en menos de 24h
- Bot reportando errores críticos o comportamiento anómalo
- Health factor de préstamo acercándose a zona de liquidación (HF < 1.5)
- Pérdida de conectividad prolongada con Binance API
- Sospecha de compromiso de seguridad en API keys

### Pasos (en orden estricto)

| Paso | Acción | Notas |
|------|--------|-------|
| 1. Freeze | Verificar estado de bots activos y órdenes abiertas | Si hay bots activos, reportar ANTES de continuar |
| 2. Assess Portfolio | `python portfolio_table.py` | Exposición total, top posiciones, PnL |
| 3. Assess Préstamos | `python loans_report.py` | Health factors, precios de liquidación |
| 4. Diagnóstico | Identificar causa raíz según trigger | No hacer requests si hay sospecha de seguridad |
| 5. Opciones | Presentar al operador SIN ejecutar | Ver menú de opciones abajo |
| 6. Esperar | Aguardar instrucción explícita | NO ejecutar nada sin confirmación |

### Clasificación de Health Factor

| Rango | Estado | Acción recomendada |
|-------|--------|--------------------|
| HF > 1.5 | ✅ Seguro | Sin riesgo inmediato |
| HF 1.3–1.5 | ⚠️ Alerta | Monitoreo activo |
| HF < 1.3 | 🔴 Peligro | Liquidación inminente, acción requerida |

### Menú de opciones para el operador

| Opción | Descripción | Riesgo |
|--------|-------------|--------|
| **A — Defensivo** | Activar red_button + cancelar órdenes | Si el mercado sigue cayendo, el colateral puede no ser suficiente |
| **B — Reducción** | A + añadir colateral a préstamos en ⚠️ | Usa capital libre |
| **C — Liquidación** | B + cerrar préstamos (HF más bajo primero) | Cristaliza pérdidas, elimina riesgo |
| **D — Mantener** | No hacer nada, monitorear cada 15 min | Riesgo si el mercado empeora |

---

## Auditoría y Trazabilidad

- Cada ejecución de protocolo queda en `runtime/data/ops_audit.sqlite`
- Las tablas incluyen: estado final, resumen, errores y timestamps
- Consultar el estado en `GET /api/v1/ops/protocol/status`

---

## Herramientas de diagnóstico disponibles

| Script | Función |
|--------|---------|
| `python portfolio_table.py` | Tabla de portfolio con pesos y PnL |
| `python loans_report.py` | Estado de préstamos con HF y precios de liquidación |
| `python audit_full.py` | Auditoría completa del estado |
| `python earn_rate_monitor.py` | Tasas actuales de Earn |
| `python loan_rate_monitor.py` | Tasas actuales de préstamos |
| `python alpha_monitor.py` | Monitor de señales alpha |
