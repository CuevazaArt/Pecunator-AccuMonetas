# Louise Bot: Long-Term Asset Accumulation + Earn Flexible

**Updated Model:** Acumulación cíclica + Earn flexible paralelo  
**Status:** Revised specification (2026-05-11)  
**Original Goal:** Acumular activos progresivamente  
**New Goal:** Acumular → Earn → Reiniciar (ciclo repetible)

---

## 🎯 Core Strategy (Revised)

Louise ahora opera en **ciclos de acumulación**, no en "épocas de compra-venta":

```
CICLO 1:
├─ Acumulación: Louise compra sistemáticamente
│  └─ Cada 300+ segundos: verifica precio
│  └─ Si precio < last_buy → compra su volumen
│  └─ Continúa hasta alcanzar monto_trigger (ej: 0.5 BTC)
│
├─ Transferencia a Earn Flexible:
│  └─ Cuando acumulado >= monto_trigger
│  └─ Envía TODO el acumulado a Binance Earn Flexible
│  └─ Comienza a ganar rendimiento (APY variable)
│
└─ Reinicio:
   └─ Louise automáticamente reinicia acumulación desde cero
   └─ Fondos libres disponibles se usan para nuevas compras
   └─ Mientras tanto, lo anterior gana interés en earn

CICLO 2:
├─ Acumulación (paralela): Louise acumula de nuevo
├─ Transferencia: Cuando alcanza trigger, envía a earn
└─ Reinicio: Continúa ciclo

⋮ Ciclos repetidos indefinidamente
```

---

## 📊 Operación Paralela

### Estado de Capital

```
Total Bluechip Capital = Fondos en Operación + Fondos en Earn

Ejemplo:
├─ Total: $5,000
├─ En Operación (Louise acumulando): $2,000
│  └─ Libre (para compras): $1,900
│  └─ Locked (en órdenes): $100
│
└─ En Earn Flexible: $3,000
   └─ Ganando APY (variable, típico 3-20%)
```

### Flujo Simultáneo

```
Tiempo T:
├─ Louise Ciclo 1: Acumuló 0.5 BTC
│  └─ Acciona transferencia a earn
│  └─ Status: "Transfiriendo a earn"
│
├─ Earn: 0.3 BTC anterior genera interés
│  └─ APY: 8% anual
│  └─ Interés acumulado: 0.001234 BTC (ej)
│
└─ Louise Ciclo 2: Inicia nueva acumulación
   └─ Status: "Acumulando"
   └─ Fondos libres: disponibles para comprar
```

**Visualización:** Dos operaciones independientes corriendo simultáneamente.

---

## 💰 Modelo de Ciclos (No Épocas)

### Ciclo = Período de Acumulación

```
CICLO ANTERIOR:
├─ Duración: 2 semanas
├─ Compras ejecutadas: 20 (1 cada 16-17 horas aprox)
├─ BTC acumulado: 0.5
├─ Costo promedio: $39,850/BTC
├─ Total invertido: $19,925
├─ Enviado a Earn: 0.5 BTC
├─ Interés ganado (14 días): 0.001234 BTC
└─ Status: COMPLETADO

CICLO ACTUAL:
├─ Inicio: Hoy (2026-05-11 15:30 UTC)
├─ Acumulado hasta ahora: 0.12 BTC (5 compras)
├─ Meta: 0.5 BTC (nuevo trigger)
├─ Fondos restantes: $2,400
├─ Tiempo estimado: 10 días más aprox
└─ Status: EN PROGRESO
```

**NO hay "exit a ganancia %PNL"** — Louise continúa comprando independientemente del precio actual.

---

## 📈 %PNL: Información, No Control

%PNL sigue siendo **visible y útil para monitoreo**, pero NO determina exit:

```
Ciclo Actual:
├─ Acumulado: 0.12 BTC
├─ Costo promedio: $39,900
├─ Current Value (0.12 × $42,500): $5,100
├─ Cost Basis: $4,788
├─ Unrealized P&L: +$312
├─ %PNL: +6.51% 🟢
│
└─ Decisión: SIGUE COMPRANDO
   (No es "exit trigger", es información)
```

**Operador ve:** "Este ciclo va bien (+6.51%), pero Louise sigue comprando normalmente hasta 0.5 BTC."

---

## 🎯 Parámetros Clave por Louise

### Nuevo Parámetro: Monto Trigger

```yaml
louise_btc_001:
  symbol: BTCUSDT
  buy_volume: $100 per cycle
  poll_interval: 300+ seconds (5 min o más)
  cycle_accumulation_target: 0.5 BTC  ← NEW!
  daily_budget: $1,000
  
louise_eth_001:
  symbol: ETHUSDT
  buy_volume: $80 per cycle
  poll_interval: 300+ seconds
  cycle_accumulation_target: 5.0 ETH  ← NEW!
  daily_budget: $800
  
louise_sol_001:
  symbol: SOLUSDT
  buy_volume: $50 per cycle
  poll_interval: 300+ seconds
  cycle_accumulation_target: 100 SOL  ← NEW!
  daily_budget: $500
```

**Lógica:** Cuando `current_accumulated >= cycle_accumulation_target` → Transferir a Earn Flexible automáticamente.

---

## 🔄 Flujo: Acumular → Earn → Reiniciar

### Paso 1: Acumulación

```python
async def poll_market(self):
    """Main loop: accumulate until trigger"""
    
    balance = await balance_checker.check_and_refresh(symbol)
    
    if balance.free_balance < $8:
        await self._pause("Low balance")
        return
    
    current_price = await gateway.get_symbol_price_async(symbol)
    last_buy_price = self._get_last_buy_price()
    
    if current_price < last_buy_price:
        await self._execute_buy(current_price)
        
        # Update accumulated amount
        total_accumulated = await self._get_cycle_accumulated(bot_id)
        
        if total_accumulated >= self.config.cycle_accumulation_target:
            # NEXT: Transferir a earn
            await self._trigger_earn_transfer(total_accumulated)
```

### Paso 2: Transferencia a Earn

```python
async def _trigger_earn_transfer(self, accumulated_amount: float):
    """Send accumulated amount to Binance Earn Flexible"""
    
    logger.info(f"Ciclo completado. Transfiriendo {accumulated_amount} a Earn...")
    
    # 1. Initiate transfer to Binance Earn Flexible
    transfer = await binance_earn_gateway.subscribe_flexible_product(
        asset=self.config.symbol.replace("USDT", ""),
        amount=accumulated_amount,
        product_id="BNB3L"  # Example: Binance Earn Flexible product
    )
    
    # 2. Record in database
    await db.create_earn_transfer(
        bot_id=self.config.bot_id,
        cycle_id=self.current_cycle_id,
        asset=self.config.symbol.replace("USDT", ""),
        amount=accumulated_amount,
        earning_product_id=transfer.product_id,
        apy=transfer.apy,
        transfer_timestamp=datetime.utcnow()
    )
    
    # 3. Update cycle status
    await db.update_cycle_status(self.current_cycle_id, "TRANSFERRED_TO_EARN")
    
    # 4. Log and alert
    await self._send_alert(
        f"✅ Ciclo {self.current_cycle_id} completado: "
        f"{accumulated_amount} {self.config.symbol.replace('USDT','')} → Earn Flexible"
    )
```

### Paso 3: Reinicio de Acumulación

```python
async def _reinitiate_cycle(self):
    """Start new accumulation cycle"""
    
    logger.info(f"Iniciando nuevo ciclo...")
    
    # 1. Create new cycle record
    new_cycle = await db.create_new_cycle(
        bot_id=self.config.bot_id,
        started_at=datetime.utcnow(),
        target_accumulation=self.config.cycle_accumulation_target,
        status="ACCUMULATING"
    )
    
    self.current_cycle_id = new_cycle.id
    
    # 2. Louise continues normally
    # Next poll_market() will start buying again
    
    # 3. Dashboard updates
    await self._broadcast_metrics({
        "cycle_id": new_cycle.id,
        "cycle_status": "ACCUMULATING",
        "accumulated": 0,
        "target": self.config.cycle_accumulation_target
    })
```

---

## 📊 Monitoreo: Ciclos vs. Earn

### Dashboard Cycle View (Nuevo)

```
louise_btc_001
BTC/USDT

CURRENT CYCLE:
├─ Status: 📈 ACCUMULATING
├─ Duration: 5 days, 3 hours
├─ Accumulated: 0.12 BTC (24% of target)
├─ Purchases: 5
├─ Avg Price: $39,950
├─ Current %PNL: +6.51% 🟡
├─ Target: 0.5 BTC
└─ Est. Completion: 10 days (estimated)

EARNINGS:
├─ In Earn Flexible: 0.5 BTC (previous cycle)
├─ APY: 8.5% (current rate)
├─ Interest Accrued: 0.001234 BTC
├─ Projected: 0.04125 BTC/year
└─ Flexible: Can withdraw anytime

TOTAL HOLDINGS:
├─ Accumulating: 0.12 BTC
├─ Earning: 0.5 BTC
└─ Total: 0.62 BTC (+ interest)
```

### Card Layout (Dashboard Grid)

```
louise_btc_001
BTC/USDT

Cycle: 📈 ACCUMULATING
Acum: 0.12 / 0.5 BTC [████░░░░░░░░░░░░░░]
Price: $42,500
%PNL: +6.51% 🟡

In Earn: 0.5 BTC (APY 8.5%)
Free Balance: $450

[Enable/Disable] [Details]
```

---

## 💾 Database: Ciclos + Earn

### louise_cycles Table (NEW)

```sql
CREATE TABLE louise_cycles (
    cycle_id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    
    target_accumulation FLOAT NOT NULL,
    accumulated_amount FLOAT,
    num_purchases INTEGER,
    avg_buy_price FLOAT,
    total_cost FLOAT,
    
    status TEXT,  -- ACCUMULATING, TRANSFERRED_TO_EARN, COMPLETED
    
    FOREIGN KEY(bot_id) REFERENCES louise_bots(bot_id)
);
```

### louise_earn_transfers Table (NEW)

```sql
CREATE TABLE louise_earn_transfers (
    earn_id TEXT PRIMARY KEY,
    bot_id TEXT NOT NULL,
    cycle_id TEXT NOT NULL,
    
    asset TEXT,  -- BTC, ETH, SOL
    amount FLOAT NOT NULL,
    earning_product_id TEXT,  -- Binance product ID
    apy FLOAT,  -- At time of transfer
    
    transferred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    withdrawn_at TIMESTAMP,  -- If manually withdrawn
    
    interest_accrued FLOAT DEFAULT 0,
    status TEXT,  -- EARNING, WITHDRAWN, COMPLETED
    
    FOREIGN KEY(bot_id) REFERENCES louise_bots(bot_id),
    FOREIGN KEY(cycle_id) REFERENCES louise_cycles(cycle_id)
);
```

### louise_earn_history Table (NEW)

```sql
CREATE TABLE louise_earn_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    earn_id TEXT NOT NULL,
    snapshot_date DATE,
    apy_current FLOAT,
    interest_accrued FLOAT,
    balance_in_earn FLOAT,
    
    FOREIGN KEY(earn_id) REFERENCES louise_earn_transfers(earn_id)
);
```

---

## 🌐 API Endpoints (Updated)

### Ciclos

```
GET    /api/v1/louise/bots/{bot_id}/cycle/current
       → Current accumulation cycle details

GET    /api/v1/louise/bots/{bot_id}/cycles
       → Historical cycles (completed)

POST   /api/v1/louise/bots/{bot_id}/cycle/manual-transfer
       → Manually trigger earn transfer (if accumulated >= target)
```

### Earn Management

```
GET    /api/v1/louise/bots/{bot_id}/earn/active
       → Current holdings in earn flexible

GET    /api/v1/louise/bots/{bot_id}/earn/history
       → Historical earn transfers + interest accrued

GET    /api/v1/louise/bots/{bot_id}/earn/apy
       → Current APY for the earning product

POST   /api/v1/louise/bots/{bot_id}/earn/withdraw
       → Manual withdrawal from earn (operator decision)
```

### Hub Stats

```
GET    /api/v1/louise/stats/accumulation
       ├─ Total accumulated across all bots
       ├─ Total in earn across all bots
       ├─ Average APY
       └─ Projected annual earnings

GET    /api/v1/louise/stats/earn-summary
       └─ Hub-wide earn flexible performance
```

---

## 💡 Beneficios del Modelo Actualizado

### Acumulación Pura
- ✅ No hay urgencia de "cerrar por ganancia"
- ✅ Continúa comprando independientemente de precio
- ✅ Verdadero DCA a largo plazo

### Earn en Paralelo
- ✅ Capital inactivo gana rendimiento
- ✅ Flexible: puede retirarse cuando quiera
- ✅ APY variable pero típicamente 3-20% anual

### Visibilidad
- ✅ %PNL muestra salud del ciclo actual
- ✅ Dashboard separa "acumulando" vs "en earn"
- ✅ Proyecciones de earnings claras

### Escalabilidad
- ✅ Ciclos repetibles indefinidamente
- ✅ Capitalización de interest (earnings ganan más earnings)
- ✅ Multiplicador de riqueza con tiempo

---

## 📋 Monitoreo cada 300+ segundos

### Por qué 300 segundos es suficiente

```
Compra cada ~16-17 horas (ej: $100/compra, $1,600/día, 16 compras/día)

Poll cada 5 min (300s):
├─ Muy frecuente para este ritmo
├─ Detecta inmediatamente si precio < last_buy
├─ Ejecuta compra en < 1 segundo
└─ Actualiza métricas en tiempo real

Poll cada 30 min (1800s):
├─ También suficiente (solo 2 checks entre compras típicas)
├─ Reduce carga de API
├─ Sigue siendo "a largo plazo"
└─ Alternativa si quieres más laxo

Poll cada 1+ hora:
├─ Posible pero menos responsivo
└─ Podría perder oportunidades de compra en picos
```

**Recomendación:** 300 segundos (5 min) es equilibrio perfecto: responsive pero eficiente.

---

## 📈 Ejemplo de Ejecución (12 Meses)

```
CICLO 1 (Weeks 1-2):
├─ Acumula: 0.5 BTC (costo: $19,925)
├─ Envía a Earn: 0.5 BTC @ 8% APY
├─ Status: EARNING

CICLO 2 (Weeks 3-4):
├─ Acumula: 0.5 BTC (costo: $19,800)
├─ Envía a Earn: 0.5 BTC @ 8.5% APY
├─ Total in Earn: 1.0 BTC
├─ Interest accrued Ciclo 1: 0.001234 BTC
└─ Status: EARNING

⋮ (Ciclos 3-26: Repetir acumulación + earn)

FINAL (After 12 months):
├─ Ciclos completados: 26
├─ Total acumulado: 13 BTC
├─ Average cost: ~$39,750/BTC
├─ Total invertido: ~$517,000
├─ All in Earn: 13 BTC @ variable APY
├─ Interest ganado: ~0.8-1.2 BTC (depending on APY)
├─ Total holdings: ~13.8-14.2 BTC
├─ Costo promedio bajado por DCA: ✅
└─ Rendimiento pasivo en earn: ✅
```

**Result:** 13+ BTC acumulado + interés ganado = riqueza building a largo plazo.

---

## 🎯 Cambios a BOT_SPECIFICATION.md

### Qué cambia

```
ANTES (Epoch-based):
├─ Objetivo: Acumula → Si ganancia ≥ 5% → Vende → Cierra época

DESPUÉS (Cycle-based):
├─ Objetivo: Acumula → Si amount ≥ trigger → Envía a Earn → Reinicia ciclo
├─ No hay exit por ganancia
├─ Operación continua indefinida
└─ Earn es multiplicador de riqueza
```

### Qué sigue igual

```
✅ DCA downside-only (continúa comprando si precio < last_buy)
✅ Balance verification ($8 mínimo)
✅ %PNL tracking (información, no control)
✅ Daily budget limits
✅ Multi-instance hub
✅ Bluechip subaccount
```

---

## ✅ Actualización Checklist

- [x] Modelo de ciclos definido
- [x] Earn flexible integrado
- [x] Operación paralela clarificada
- [x] Database schema actualizado
- [x] API endpoints expandidos
- [x] UI mockups actualizados mentalmente
- [ ] BOT_SPECIFICATION.md reescrito (próximo)
- [ ] IMPLEMENTATION_ROADMAP.md ajustado
- [ ] Earn integration code (Phase 1-2)

---

**Status:** Modelo completamente revisado y documentado  
**Next:** Actualizar BOT_SPECIFICATION.md + IMPLEMENTATION_ROADMAP.md + Código
