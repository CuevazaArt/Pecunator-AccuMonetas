# Arquitectura de Subcuentas Binance — Protocolo Operativo

> Segmentación operativa mediante subcuentas, asignación de bots,
> permisos, métricas, y rotación de capital.
> Fecha: 2026-05-05

---

## 1. Mapa de Subcuentas

| ID | Nombre | Rol | Bots | Riesgo |
|----|--------|-----|------|--------|
| MASTER | Bóveda | Router de capital, sin bots | Ninguno | Mínimo |
| SUB-01 | CORE_L1_DCA | Acumulación BTC/ETH largo plazo | Masha | Conservador |
| SUB-02 | SCALP_RANGE | Scalping en rangos líquidos | Dorothy | Moderado |
| SUB-03 | MULTI_ASSET | Rotación multi-símbolo | Thusnelda | Moderado-Alto |
| SUB-04 | SECTOR_BETA | Sectores fuertes (SOL, AI, DeFi) | Bots sectoriales | Alto |
| SUB-05 | SANDBOX | Pruebas, capital mínimo (≤5%) | Versiones beta | Contenido |

**Reglas:** MASTER no opera. Cada subcuenta = 1 API key. Withdraw: OFF siempre.

---

## 2. Permisos API por Subcuenta

| Permiso | MASTER | SUB-01..05 |
|---------|--------|------------|
| Read | ✅ | ✅ |
| Trade (Spot) | ❌ | ✅ |
| Withdraw | ❌ | ❌ |
| Futures/Margin/Loans | ❌ | ❌ (salvo habilitación explícita) |
| IP Whitelisting | ✅ | ✅ cuando posible |

Rotación de claves: cada 6 meses. Revocar ante sospecha antes de diagnosticar.

---

## 3. Métricas por Subcuenta

Almacenadas en `runtime/data/{sub_id}_metrics.sqlite`:

| Categoría | Métricas |
|-----------|----------|
| Equity | equity_usdt diario, capital libre vs invertido |
| Riesgo | max_drawdown_pct, volatilidad equity, días en drawdown |
| Performance | PnL acumulado, PnL mensual, win_rate, sharpe aprox |
| Operativa | trades/día, tamaño medio, comisiones pagadas |

**Alertas:** PnL negativo 3 meses → revisión. Drawdown >25% → congelar entradas.

---

## 4. Rotación de Capital

### Frecuencia
- Rebalanceo ligero: **mensual** (±10-20%).
- Revisión agresiva: **trimestral**.

### Reglas
- PnL >+3% Y drawdown <10% → **+10-20% capital** (premio).
- PnL <0% O drawdown >20% → **-10-30% capital** (castigo).
- Drawdown >25% → **congelar** entradas, solo salidas.

### Flujo mensual
1. Snapshot métricas → 2. Evaluar reglas → 3. Calcular transferencias →
4. Ejecutar (MASTER ↔ SUB) → 5. Loggear en `capital_rotation_log.csv`

---

## 5. Rotación Sectorial

| Sector | Tokens | Subcuenta |
|--------|--------|-----------|
| L1 | BTC, ETH, SOL, BNB | SUB-01, SUB-03 |
| DeFi | UNI, AAVE, MKR | SUB-04 |
| AI | FET, RNDR, AGIX | SUB-04 |
| Gaming | GALA, AXS, IMX | SUB-04 |
| Memecoins | DOGE, SHIB, PEPE | SUB-05 |

**Protocolo mensual:** Rankear sectores por momentum + volumen.
Sector fuerte → +capital + activar bots. Sector débil → -capital.
Sector muerto → mover todo a MASTER. Registrar decisión y motivo.
