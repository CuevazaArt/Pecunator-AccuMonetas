# L0 Operator Philosophy — Juan's Investment Doctrine

> Personal investment philosophy of the sovereign operator.
> These are preferences and styles, not dogmas or laws.
> Subject to organic evolution through observation and experience.

---

## Core Convictions

### 1. Structural Optimism (Long-Only Bias)

The operator is fundamentally optimistic about the future of digital assets.
This translates to a **long-only operational stance** — the system is designed
to accumulate, hold, and compound, not to short or bet against markets.

### 2. Capital Velocity — Never Idle

Capital must always be working across multiple instruments simultaneously.
Cash sitting idle is considered an opportunity cost. Every unit of capital
should be deployed in one of:
- Active trading positions (bots)
- Earn/staking services (yield)
- Accumulation orders (DCA into conviction assets)

> **Guardrail accepted:** A 10-20% reserve in stablecoins is not "idle" —
> it is *optionality* (dry powder for sudden opportunities or drawdown protection).

### 3. Conviction Holdings (Top-10 + Selected Projects)

The operator maintains a list of **conviction assets** — primarily the top 10
by market capitalization, plus select projects with strong fundamentals.
These assets are:
- Actively accumulated when prices are favorable
- Held through depreciation (floating loss accepted as "impermanent")
- Deployed in Earn services to compound yield in-kind
- Concentrated in a dedicated subcuenta (SUB-HOLD)

> **Guardrail accepted:** If a conviction asset drops >40% from average entry
> over 90 days, a mandatory review is triggered:
> (1) Is the thesis still intact? (2) Has the market cap ranking changed?
> (3) Is Earn yield covering the depreciation rate?
> If 2/3 answers are negative → reduce position by 50% and redeploy.

### 4. Micro-Atomization of Operations

The operator prefers **many small discrete operations** distributed across
the **maximum number of assets**, using the minimum viable order size allowed
by Binance. The rationale:

| Cost | Value Gained |
|------|-------------|
| Higher commission overhead | Massive empirical feedback |
| More complexity to manage | Risk dissolution across positions |
| Lower per-trade profit | Broader market exposure and learning |

> **Guardrail accepted:** Each micro-position must pass a break-even yield test:
> `break_even = (commission × 2 × cycles_per_month) / position_size`
> If expected monthly return < break_even → position is net negative.

### 5. Holistic Experimentation

The operator follows a philosophy of **broad exposure**: try every tool,
technique, idea, method, and practice available. Integrate what has value,
identify what doesn't, deprecate it, and keep the experience.

> **Guardrail accepted (MVE Protocol):** Every experiment gets:
> - Minimum duration: 30 days or 200 cycles
> - Success criteria: Sharpe > 0, win rate > 40%, max drawdown < 20%
> - Decision: KEEP → MODIFY → DEPRECATE
> - Post-mortem logged in `docs/experiments/`

### 6. Segment-Weighted Attention

No prejudice between sectors, but capital and attention are allocated
proportionally to asset quality:

| Tier | Examples | Attention | Stop-Loss |
|------|----------|-----------|-----------|
| **A — Blue Chip** | BTC, ETH, SOL, BNB | Maximum | Wide or none (hold-through) |
| **B — Layer-2 / Emerging** | ARB, OP, MATIC | Moderate | 15-25% |
| **C — Speculative** | Meme coins, micro-caps | Minimal | 5-10% trailing |

### 7. Compound Reinvestment

Profits follow a distribution pipeline:
1. Cover personal expenses first
2. Remainder distributed by allocation policy (TBD):
   - Conviction asset accumulation
   - Bot trading capital
   - Earn/staking deployment
   - Reserve maintenance

The operator believes in the power of compound interest as the primary
wealth-building mechanism over time horizons of years.

### 8. Stop-Loss Evolution

The operator's stance on stop-losses is evolving:
- **Historical position:** Reluctant; prefers to hold through drawdowns
- **Current position:** Increasingly accepting; recognizes that capital
  preservation enables future compounding
- **Implemented rule:** Stop-loss policy is segment-dependent (see Tier table above)
- **Conviction exception:** Tier A assets may be held through drawdowns
  as the long-term thesis overrides short-term price action

### 9. Anti-Dogma Clause

> **All principles above are preferences, not laws.**
> They are subject to organic evolution through observation, experience,
> and market regime changes. The operator reserves the right to modify,
> suspend, or reverse any principle when evidence warrants it.

---

## Architectural Implications

| Philosophy | Pecunator Module | Status |
|------------|-----------------|--------|
| Long-only bias | All bots: BUY + SELL LIMIT only | ✅ Built |
| Capital velocity | Bot rotation + Earn integration | 🟡 Partial |
| Conviction holds | SUB-HOLD subcuenta + Earn service | 🟡 Designed |
| Micro-atomization | `quote_order_qty` at minimum viable | ✅ Configurable |
| Experimentation | MVE protocol + experiment logs | ❌ Not built |
| Segment allocation | Per-instance `stop_loss_pct` | ✅ Built |
| Compound reinvestment | Auto-reinvestment logic | ❌ Not built |
| Regime awareness | VMO (Visual Market Observer) | ❌ Not built |
| Break-even calculator | Commission analysis tool | ❌ Not built |
| Conviction review | Depreciation alert system | ❌ Not built |

---

*Document version: 2026-05-05 · Subject to evolution per the Anti-Dogma Clause.*
