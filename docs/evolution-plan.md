# Plan Arquitectónico Evolutivo — Pecunator

> Hoja de ruta por etapas con prerrequisitos claros, entregables
> medibles, y criterios de promoción entre fases.
> Fecha: 2026-05-05

---

## Visión de Fases

```
Fase 0 ─── Fase 1 ─── Fase 2 ─── Fase 3 ─── Fase 4 ─── Fase 5
Hardening   Bots       Subcuentas  Sensores   Multi-CEX   Web3
(doctrina)  (prod)     (aislam.)   (VMO+rot)  (ccxt)      (on-chain)
    ▲           ▲           ▲          ▲          ▲           ▲
  AHORA     PRE-PROD    CON P&L    CON DATOS   ESTABLE    MADURO
```

---

## Fase 0 — Hardening Doctrinal (ACTUAL)

> **Estado:** En progreso.
> **Prerrequisito:** Ninguno.

### Entregables

- [x] Manifiesto actualizado con resoluciones de hardening
- [x] Pilar III redefinido: Flutter como View pura, DB en Python
- [x] Sección 4.2 expandida: Principio Propuesta-Ejecución del LLM
- [x] Sección 5.1 actualizada: StateStore persistido (WAL)
- [x] Sección 6.2 expandida: Kill Switch OOB (PANIC.lock)
- [x] Sección 6.3 expandida: Marco de pérdidas justas/injustas
- [x] Nueva sección 6.4: Pipeline de promoción de bots
- [x] VMO registrado en roadmap como fase reservada
- [x] Web3 registrado en roadmap como fase futura
- [x] Documentos de consulta creados:
  - `docs/hardening-critique.md`
  - `docs/subcuentas-architecture.md`
  - `docs/loss-framework.md`
  - `docs/evolution-plan.md` (este documento)

### Criterio de completitud

Manifiesto refleja toda la doctrina aceptada. Documentos de consulta
cubren todas las dimensiones discutidas.

---

## Fase 1 — Bots en Producción

> **Estado:** Pendiente.
> **Prerrequisito:** Fase 0 completa.

### Fase 1a — Infraestructura de Resiliencia

- [ ] WAL State Hydration en `runtime/core/state_store.py`
- [ ] PANIC.lock watchdog implementado
- [ ] Drawdown guard por bot activo y testeado

**Criterio:** Los 3 mecanismos de resiliencia (WAL, PANIC.lock, drawdown
guard) funcionando y testeados. Ningún bot opera aún con capital.

### Fase 1b — Primer Bot Operativo

- [ ] Lógica de estrategia ejecutable para 1 bot (ej. Dorothy)
- [ ] Pipeline de promoción ejecutado para ese bot:
  - Backtest ≥6 meses → Paper trading ≥2 semanas → Capital mínimo
- [ ] Primer mes de operación con P&L registrado

**Criterio:** 1 bot operando con capital real ≥1 mes, sin pérdidas injustas.

### Fase 1c — Expansión de Bots

- [ ] Lógica de estrategia para Masha y Thusnelda
- [ ] Pipeline de promoción ejecutado para cada uno
- [ ] ≥2 bots operando simultáneamente con P&L registrado

### Criterio de promoción a Fase 2

Al menos 2 bots operando con capital real durante ≥1 mes con P&L medible
y sin pérdidas injustas.

---

## Fase 2 — Subcuentas y Aislamiento

> **Estado:** Pendiente.
> **Prerrequisito:** Fase 1 completa + P&L medible de al menos 1 bot.

### Entregables

- [ ] Subcuentas creadas en Binance (SUB-01 a SUB-05)
- [ ] API keys independientes por subcuenta (withdraw: OFF)
- [ ] Bots migrados a sus subcuentas asignadas
- [ ] Métricas por subcuenta activas (`{sub_id}_metrics.sqlite`)
- [ ] Primera rotación de capital mensual ejecutada y registrada
- [ ] `capital_rotation_log.csv` con al menos 1 entrada

### Criterio de promoción a Fase 3

≥3 meses de operación con subcuentas. Métricas claras por subcuenta.
Al menos 1 rotación de capital ejecutada basada en datos reales.

---

## Fase 3 — Sensores y Heurísticas (VMO + Rotación Sectorial)

> **Estado:** Reservado.
> **Prerrequisito:** Fase 2 completa + hipótesis validada de qué
> régimen favorece a cada bot (basada en datos de Fase 1-2).

### Entregables

- [ ] `runtime/modules/vision/` implementado (chart_capture, analyzer, cache)
- [ ] VMO integrado con BotCoordinator para activación/desactivación
- [ ] Sector Strength Scanner operativo
- [ ] Rotación sectorial automatizada (mensual)
- [ ] Ajuste dinámico de parámetros por régimen
- [ ] Validación: ¿VMO mejora P&L vs parámetros fijos?

### Criterio de promoción a Fase 4

VMO demuestra mejora medible en P&L o reducción de drawdown vs baseline
durante ≥3 meses. Si no → desactivar VMO, mantener parámetros fijos.

---

## Fase 4 — Multi-CEX (Diversificación)

> **Estado:** Roadmap.
> **Prerrequisito:** Fase 2 estable + Gateway abstraction justificada.

### Entregables

- [ ] Interfaz `IExchange` extraída del `BinanceGateway` actual
- [ ] Segundo exchange integrado vía `ccxt` (Bybit u OKX)
- [ ] MockExchange para backtesting inyectable
- [ ] Comparador de tasas cross-exchange
- [ ] Bots operando en ≥2 exchanges con métricas separadas

### Criterio de promoción a Fase 5

Operación estable en ≥2 exchanges durante ≥3 meses.

---

## Fase 5 — Web3 Multichain (Reservado)

> **Estado:** Reservado — dimensión propia.
> **Prerrequisito:** Fase 4 estable + capital y estabilidad lo justifican.

### Entregables (conceptuales)

- [ ] Wallet Engine (web3.py, eth_account)
- [ ] DEX Execution (Uniswap, PancakeSwap, Curve)
- [ ] On-chain Metrics (TVL, flujos, whales)
- [ ] Multichain Router (ETH, BNB, Arbitrum, Base)
- [ ] DeFi Strategies (LP, yield farming, staking líquido)
- [ ] Seguridad extrema: llaves privadas, wallets frías/calientes

### Criterio de activación

Sistema CEX blindado. Bots estables. Métricas claras. Capital suficiente
para justificar diversificación a DeFi. Protocolos de seguridad para
llaves privadas diseñados y auditados.

---

## Mapa de Documentos de Consulta

| Documento | Grupo conceptual | Fases |
|-----------|-----------------|-------|
| [MANIFESTO.md](MANIFESTO.md) | Doctrina central | Todas |
| [architecture-next.md](architecture-next.md) | Estado técnico | 0-1 |
| [hardening-critique.md](hardening-critique.md) | Resiliencia y seguridad | 0-1 |
| [subcuentas-architecture.md](subcuentas-architecture.md) | Aislamiento y rotación | 2-3 |
| [loss-framework.md](loss-framework.md) | Riesgo y promoción | 1-2 |
| [evolution-plan.md](evolution-plan.md) | Roadmap evolutivo (este doc) | Todas |
| [bots/*.md](bots/) | Documentación por bot | 1+ |

---

## Principio Evolutivo

> Cada fase se construye sobre la anterior. No se salta ninguna.
> No se activa una fase sin que la anterior tenga datos medibles.
> La doctrina se actualiza con cada transición de fase.
