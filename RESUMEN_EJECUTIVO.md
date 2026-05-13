# Pecunator-AccuMonetas: Resumen Ejecutivo

**Proyecto:** Hub de Bots Louise (DCA Downside-Only)  
**Estado:** 🟠 Staging-Ready — Paper Trading Active, Production Pending UI+Ops Validation  
**Backend:** 85% (core logic solid, tests comprehensive)  
**UI Testing:** 10% (boilerplate only, needs control/WebSocket coverage)  
**Ops Docs:** 0% (deployment/runbook/rollback missing)  
**Fecha:** 2026-05-13 (Updated after honest assessment)

---

## 🎯 Qué es Louise?

**Louise** es un bot de trading autónomo que acumula progresivamente un activo mediante DCA a la baja (downside-only averaging):

```
Lógica Simple:
1. Cada N segundos revisa el precio del símbolo
2. Si precio actual < último precio de compra → compra su volumen configurado
3. Si no hay compras previas → ejecuta la primera compra (referencia base)
4. Sin stop-loss (por diseño, solo promedia a la baja)
5. Cuando ganancia alcanza X% → vende TODO a mercado, cierra época (exitosa)
6. Listo para nueva época
```

**Hub de múltiples Louise:** Cientos de bots Louise ejecutándose simultáneamente en diferentes símbolos/activos, cada uno con sus propios parámetros.

---

## 📦 Qué está Completado?

### ✅ Documentación Base

| Documento | Propósito | Estado |
|-----------|----------|--------|
| **CLAUDE.md** | Workflow, fases, stack técnico | ✅ Listo |
| **BOT_SPECIFICATION.md** | Lógica detallada, parámetros, API | ✅ Listo |
| **UI_WIREFRAMES.md** | 6 pantallas, flujos, componentes | ✅ Listo |
| **IMPLEMENTATION_ROADMAP.md** | Plan 9 semanas, fases, hitos | ✅ Listo |
| **ONBOARDING.md** | Checklist pre-desarrollo | ✅ Listo |

### ✅ Infraestructura Heredada (PecunatorCore v3.7.5)

```
Backend (Python FastAPI)
├─ API HTTP en puerto 8000
├─ WebSocket para telemetría en tiempo real
├─ AsyncClient (python-binance) 100% nativo
├─ SQLite para persistencia de estado
└─ 195+ tests (suite completa)

Frontend (Flutter Desktop)
├─ UI Windows nativa
├─ State management (Provider)
├─ Syncfusion charts
└─ WebSocket listeners

Control Modules
├─ WeightGovernor (rate limiting API)
├─ ApiFuse (circuit breaker)
├─ BudgetGuard (caps de gasto)
├─ OrderLedger (auditoría)
└─ StateWAL (recuperación ante caídas)
```

---

## 📋 Plan de Implementación (9 Semanas)

### Fase 1: Cimientos (Semanas 1-2)
- [ ] Crear módulo bot runner: `runtime/bot/louise.py`
- [ ] Crear routers API: `runtime/api/routers/louise.py`
- [ ] Extender schema SQLite con tablas Louise
- [ ] Suite de tests (unit + integration)
- **Deliverable:** Bot runner funcional + API lista

### Fase 2: Backend Completo (Semanas 3-4)
- [ ] Implementar lógica completa de Louise (polling, compras, cierre)
- [ ] Integrar con módulos de control (BudgetGuard, WeightGovernor, etc.)
- [ ] Implementar todos los endpoints REST
- [ ] WebSocket para métricas en tiempo real
- **Deliverable:** Backend producción-listo + API completa

### Fase 3: UI Flutter (Semanas 5-6)
- [ ] Dashboard: grid de bots con status y P&L
- [ ] Detalle: métricas, presupuesto, historial de compras
- [ ] Historial: épocas completadas, todas las compras
- [ ] Configuración: creación y edición de bots
- [ ] WebSocket real-time: métricas actualizan cada 5 segundos
- **Deliverable:** UI completa, intuitiva, responsiva

### Fase 4: Testing E2E (Semana 7)
- [ ] Tests end-to-end: crear bot → habilitar → monitorear → cierre
- [ ] Tests de carga: 10 bots simultáneamente
- [ ] Tests de error: desconexiones, presupuesto agotado, credenciales inválidas
- [ ] Polish UI: responsive, dark mode, accesibilidad
- **Deliverable:** Cero bugs conocidos, todas las pruebas pasan

### Fase 5: Hardening & Producción (Semanas 8-10)
- [ ] Security: validación de credenciales, sanitización de inputs
- [ ] Performance: optimización de queries, latencia WebSocket
- [ ] Reliability: recuperación ante caídas, integridad de DB
- [ ] Deployment: checklist, rollback procedure, monitoring
- **Deliverable:** ✅ Listo para producción

---

## 🎯 Decisiones Técnicas Clave

### Database Schema (SQLite)

```sql
louise_bots:
  - bot_id (PK)
  - symbol (BTC/USDT, ETH/USDT, etc.)
  - buy_volume (cuánto comprar por ciclo)
  - poll_interval_seconds (cada cuánto revisar mercado)
  - target_profit_pct (% ganancia para cerrar)
  - daily_budget_usdt (límite gasto por día)
  - status (IDLE, ACCUMULATING, PAUSED, ERROR, SHUTDOWN)

louise_purchases:
  - purchase_id (PK)
  - bot_id, epoch_id (FK)
  - price_at_buy, volume, cost_usdt
  - order_id (Binance)
  - status (FILLED, FAILED, etc.)

louise_epochs:
  - epoch_id (PK)
  - bot_id (FK)
  - num_purchases, total_cost, avg_buy_price
  - final_price, final_value, profit_usdt, profit_pct
  - status (RUNNING, CLOSED_SUCCESSFUL, CLOSED_MANUAL)
```

### API Endpoints (Total: 14 endpoints)

```
Bot Management:
  POST   /api/v1/louise/bots
  GET    /api/v1/louise/bots
  GET    /api/v1/louise/bots/{bot_id}
  PATCH  /api/v1/louise/bots/{bot_id}
  POST   /api/v1/louise/bots/{bot_id}/enable
  POST   /api/v1/louise/bots/{bot_id}/disable
  POST   /api/v1/louise/bots/{bot_id}/shutdown
  DELETE /api/v1/louise/bots/{bot_id}

Metrics & History:
  GET    /api/v1/louise/bots/{bot_id}/metrics
  GET    /api/v1/louise/bots/{bot_id}/epochs
  GET    /api/v1/louise/bots/{bot_id}/purchases
  GET    /api/v1/louise/stats

WebSocket:
  WS     /ws/louise/metrics/{bot_id} (actualización cada 5 segundos)
```

### UI Screens (6 pantallas principales)

1. **Dashboard** — Grid de bots, status, P&L, botones rápidos
2. **Bot Details** — Métricas completas, presupuesto, tabla de compras
3. **History** — Épocas completadas, todas las compras, filtros
4. **Settings** — Configuración API, alertas, backup
5. **Create/Edit Bot** — Formulario para crear novo bot
6. **Alerts** — Notificaciones de errores, confirmaciones

---

## 💾 Decisiones de Infraestructura

### Credenciales

```bash
# .env para cada subacuenta
BOT_API_KEY=<key_binance>
BOT_API_SECRET=<secret_binance>

# Vault cifrado (Fernet)
runtime/data/credentials.enc
```

### Rate Limiting (Herencia de PecunatorCore)

- **WeightGovernor:** Zonas COLOR (GREEN/YELLOW/RED) basadas en peso REST
- Cada Louise usa su propia asignación de peso
- Si zona vira RED → pausa automática

### Recuperación ante Caídas

- **StateWAL:** Persiste estado después de cada ciclo
- **Auto-resume:** Si bot estaba habilitado, intenta reanudar al reiniciar
- **Retry logic:** Reconexión con backoff exponencial

---

## 🚀 Decisiones de UX/UI

### Diseño Mobile-First (pero Desktop-Optimized)

- **Grid responsive:** Se adapta a 1280x800, 1920x1080, etc.
- **Colores:**
  - ✅ Verde = RUNNING/Ganancia
  - ⏸️ Amarillo = PAUSED/Drawdown
  - 🔴 Rojo = ERROR/Loss
  - 🟡 Gris = SHUTDOWN
  
### Real-time Updates (WebSocket)

- **Frecuencia:** Cada 5 segundos (configurable)
- **Payload:** `{price, avg_price, P&L%, budget_remaining, status}`
- **Auto-refresh:** Sin clicks, usuario ve actualización en vivo

### Flujos de Interacción

```
Create Bot → [Form] → Crear instancia → Bot status: IDLE
            ↓
         [Enable] → Ejecuta primera compra → ACCUMULATING
            ↓
     [Monitorear] → Cada 5s actualiza P&L
            ↓
    P&L >= target_profit% → Auto-vende todo → SHUTDOWN (época exitosa)
```

---

## 📊 Métricas Clave Monitoreadas

### Por Bot

| Métrica | Descripción |
|---------|-------------|
| Current Price | Precio actual del símbolo |
| Last Buy Price | Referencia para siguiente compra |
| Avg Buy Price | VWAP de todas las compras |
| Position Size | Total tokens acumulados |
| Total Cost | USDT gastados en todas compras |
| Current Value | `position_size * current_price` |
| Unrealized P&L | `current_value - total_cost` |
| Unrealized P&L % | `(current_value - total_cost) / total_cost * 100` |
| Budget Used Today | USDT gastados hoy (se reinicia mañana) |
| Budget Remaining | Límite diario - usado |

### Hub-Wide

| Métrica | Descripción |
|---------|-----------|
| Total Bots Activos | Cantidad de Louise en ACCUMULATING |
| Épocas Completadas | Total de ciclos exitosos históricos |
| Portfolio Total | Suma de valores actuales de todas posiciones |
| Ganancia Histórica | Suma de ganancias de todas épocas cerradas |
| Win Rate | 100% (por diseño, siempre cierra a ganancia) |
| Ganancia Promedio | Ganancia promedio por época |

---

## 🛡️ Controles de Riesgo

### Budget Guard

```
Si daily_budget_usdt = $1,000:
  ├─ Bot puede gastar máximo $1,000/día
  ├─ Si alcanza límite → pausa (sin error)
  ├─ Presupuesto se reinicia mañana 00:00 UTC
  └─ Operador ve "Budget exhausted" en UI
```

### Weight Governor

```
Si API weight zone → RED (>80% del límite diario):
  ├─ Todos los bots entran en pausa automática
  ├─ Esperan hasta que peso vuelva a YELLOW
  ├─ Operador alertado en UI
  └─ Previene rate-limits de Binance
```

### Error Handling

```
Network Error → Retry con backoff exponencial (3 intentos)
Exchange Error → Log + Alert + Pausa bot (requiere intervención manual)
Invalid Credentials → Critical alert + Pausa todos los bots
Insufficient Balance → Pausa (sin error), esperando depósito
```

---

## 📈 Caso de Uso Ejemplo

**Setup:** Louise en BTC, $100/compra, cada 5 min, 5% ganancia objetivo, $1000/día

```
T0: Bot habilitado
    └─ Primera compra: 0.0025 BTC a $40,000 → cost $100

T5min: Poll market → Precio $39,500 < $40,000 ✓
    └─ Segunda compra: 0.00253 BTC a $39,500 → cost $100
       Pos: 0.00503 BTC, Cost: $200, Avg: $39,750

T10min: Poll market → Precio $40,500 > $39,750 ✗
    └─ No compra, solo espera

T15min: Poll market → Precio $40,100 < $40,500 ✓
    └─ Tercera compra: 0.00249 BTC a $40,100 → cost $100
       Pos: 0.00752 BTC, Cost: $300, Avg: $39,892

T20min: Poll market → Precio $41,900 > $39,892 ✓
    └─ P&L % = (0.00752 * $41,900 - $300) / $300 = +5.16% ✅
    └─ TARGET PROFIT ALCANZADO
    └─ Vende TODO: 0.00752 BTC a $41,900 = $314.87
    └─ Ganancia: $314.87 - $300 = $14.87
    └─ Época CERRADA (exitosa)
    └─ Bot status: SHUTDOWN
    └─ Época registrada en DB (histórico)
```

---

## 🎯 Checklist Antes de Comenzar Fase 1

- [ ] **Subacuenta Binance:** Especificar cuál usaremos
  - Nombre: ___________________
  - API Key: ✓ Creada
  - Límite diario: $_________/día
  
- [ ] **Símbolos iniciales:** ¿Cuáles Louise monitoreará primero?
  - [ ] BTC/USDT
  - [ ] ETH/USDT
  - [ ] SOL/USDT
  - [ ] Otros: __________________

- [ ] **Parámetros default de Louise:**
  - Buy volume: $_________/compra
  - Poll interval: _________segundos
  - Target profit: _________%
  - Daily budget: $_________/día

- [ ] **Preferencias UI:**
  - [ ] Dark mode por defecto
  - [ ] Alertas Telegram
  - [ ] Alertas email
  - [ ] Autosave de sesión

---

## 🚀 Próximo Paso Inmediato

**Hacer commit y push del repositorio:**

```bash
git status  # Verificar cambios
git log --oneline -5  # Ver commits
git push origin claude/naughty-shaw-b40d27  # Push a rama actual
```

**Luego:**
1. Llenar checklist de subacuenta Binance
2. Crear rama `feature/louise-backend`
3. Comenzar Fase 1 (bot runner module)

---

## 📚 Documentos Clave para Referencia

| Documento | Cuándo Leer |
|-----------|----------|
| **CLAUDE.md** | Antes de empezar (workflow general) |
| **BOT_SPECIFICATION.md** | Para entender lógica de Louise |
| **UI_WIREFRAMES.md** | Para entender flujos de UI |
| **IMPLEMENTATION_ROADMAP.md** | Para cronograma detallado |
| **README.md** | Quick start de proyecto |

---

## 💬 Resumen en Una Frase

**Louise es un hub de bots DCA downside-only que acumula progresivamente activos, cierra automáticamente a ganancia, y la UI Flutter monitorea múltiples instancias en tiempo real — listo para comenzar desarrollo en ~9 semanas.**

---

**Estado:** ✅ Listo para Fase 1  
**Decisión:** ¿Confirmamos subacuenta Binance y comenzamos?
