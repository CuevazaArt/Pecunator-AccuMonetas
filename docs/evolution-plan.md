# Evolutionary Architectural Plan — Pecunator

> Phased roadmap with clear prerequisites, measurable deliverables,
> and promotion criteria between phases.
> Date: 2026-05-05

---

## Phase Vision

```
Fase 0 ─── Fase 1 ─── Fase 2 ─── Fase 3 ─── Fase 4 ─── Fase 5
Hardening   Bots       Subaccounts  Sensors    Multi-CEX   Web3
(doctrine)  (prod)     (isolation) (VMO+rot)  (ccxt)      (on-chain)
    ▲           ▲           ▲          ▲          ▲           ▲
  NOW       PRE-PROD    WITH P&L   WITH DATA   STABLE     MATURE
```

---

## Phase 0 — Doctrinal Hardening (CURRENT)

> **Status:** In progress.
> **Prerequisite:** None.

### Deliverables

- [x] Manifesto updated with hardening resolutions
- [x] Pillar III redefined: Flutter as pure View, DB in Python
- [x] Section 4.2 expanded: LLM Proposal-Execution Principle
- [x] Section 5.1 updated: Persisted StateStore (WAL)
- [x] Section 6.2 expanded: OOB Kill Switch (PANIC.lock)
- [x] Section 6.3 expanded: Fair/unfair loss framework
- [x] New section 6.4: Bot promotion pipeline
- [x] VMO registered in roadmap as reserved phase
- [x] Web3 registered in roadmap as future phase
- [x] Reference documents created:
  - `docs/hardening-critique.md`
  - `docs/subcuentas-architecture.md`
  - `docs/loss-framework.md`
  - `docs/evolution-plan.md` (este documento)

### Completion Criterion

Manifesto reflects all accepted doctrine. Reference documents
cover all discussed dimensions.

---

## Phase 1 — Bots in Production

> **Status:** Pending.
> **Prerequisite:** Phase 0 complete.

### Phase 1a — Resilience Infrastructure

- [ ] WAL State Hydration in `runtime/core/state_store.py`
- [ ] PANIC.lock watchdog implemented
- [ ] Drawdown guard per bot active and tested

**Criterion:** All 3 resilience mechanisms (WAL, PANIC.lock, drawdown
guard) working and tested. No bot is yet operating with capital.

### Phase 1b — First Bot Operational

- [ ] Executable strategy logic for 1 bot (e.g. Dorothy)
- [ ] Promotion pipeline executed for that bot:
  - Backtest ≥6 months → Paper trading ≥2 weeks → Minimum capital
- [ ] First month of operation with recorded P&L

**Criterion:** 1 bot operating with real capital ≥1 month, without unfair losses.

### Phase 1c — Bot Expansion

- [ ] Strategy logic for Masha and Thusnelda
- [ ] Promotion pipeline executed for each
- [ ] ≥2 bots operating simultaneously with recorded P&L

### Promotion Criterion to Phase 2

At least 2 bots operating with real capital for ≥1 month with measurable P&L
and without unfair losses.

---

## Phase 2 — Subaccounts and Isolation

> **Status:** Pending.
> **Prerequisite:** Phase 1 complete + measurable P&L from at least 1 bot.

### Deliverables

- [ ] Subaccounts created in Binance (SUB-01 to SUB-05)
- [ ] Independent API keys per subaccount (withdraw: OFF)
- [ ] Bots migrated to their assigned subaccounts
- [ ] Per-subaccount metrics active (`{sub_id}_metrics.sqlite`)
- [ ] First monthly capital rotation executed and recorded
- [ ] `capital_rotation_log.csv` with at least 1 entry

### Promotion Criterion to Phase 3

≥3 months of operation with subaccounts. Clear per-subaccount metrics.
At least 1 capital rotation executed based on real data.

---

## Phase 3 — Sensors and Heuristics (VMO + Sector Rotation)

> **Status:** Reserved.
> **Prerequisite:** Phase 2 complete + validated hypothesis of which
> market regime favors each bot (based on Phase 1-2 data).

### Deliverables

- [ ] `runtime/modules/vision/` implemented (chart_capture, analyzer, cache)
- [ ] VMO integrated with BotCoordinator for activation/deactivation
- [ ] Sector Strength Scanner operational
- [ ] Automated sector rotation (monthly)
- [ ] Dynamic parameter adjustment by regime
- [ ] Validation: Does VMO improve P&L vs fixed parameters?

### Promotion Criterion to Phase 4

VMO demonstrates measurable P&L improvement or drawdown reduction vs baseline
for ≥3 months. If not → deactivate VMO, maintain fixed parameters.

---

## Phase 4 — Multi-CEX (Diversification)

> **Status:** Roadmap.
> **Prerequisite:** Phase 2 stable + Gateway abstraction justified.

### Deliverables

- [ ] `IExchange` interface extracted from the current `BinanceGateway`
- [ ] Second exchange integrated via `ccxt` (Bybit or OKX)
- [ ] Injectable MockExchange for backtesting
- [ ] Cross-exchange rate comparator
- [ ] Bots operating on ≥2 exchanges with separate metrics

### Promotion Criterion to Phase 5

Stable operation on ≥2 exchanges for ≥3 months.

---

## Phase 5 — Web3 Multichain (Reserved)

> **Status:** Reserved — its own dimension.
> **Prerequisite:** Phase 4 stable + capital and stability justify it.

### Deliverables (conceptuales)

- [ ] Wallet Engine (web3.py, eth_account)
- [ ] DEX Execution (Uniswap, PancakeSwap, Curve)
- [ ] On-chain Metrics (TVL, flows, whales)
- [ ] Multichain Router (ETH, BNB, Arbitrum, Base)
- [ ] DeFi Strategies (LP, yield farming, liquid staking)
- [ ] Extreme security: private keys, cold/hot wallets

### Activation Criterion

CEX system hardened. Bots stable. Clear metrics. Sufficient capital
to justify DeFi diversification. Security protocols for
private keys designed and audited.

---

## Reference Document Map

| Document | Conceptual group | Phases |
|-----------|-----------------|-------|
| [MANIFESTO.md](MANIFESTO.md) | Core doctrine | All |
| [architecture-next.md](architecture-next.md) | Technical status | 0-1 |
| [hardening-critique.md](hardening-critique.md) | Resilience and security | 0-1 |
| [subcuentas-architecture.md](subcuentas-architecture.md) | Isolation and rotation | 2-3 |
| [loss-framework.md](loss-framework.md) | Risk and promotion | 1-2 |
| [evolution-plan.md](evolution-plan.md) | Evolutionary roadmap (this doc) | All |
| [bots/*.md](bots/) | Per-bot documentation | 1+ |

---

## Evolutionary Principle

> Each phase builds on the previous one. None are skipped.
> A phase is not activated until the previous one has measurable data.
> Doctrine is updated with each phase transition.
