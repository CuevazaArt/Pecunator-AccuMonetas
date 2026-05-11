# Task: Emergency Protocol — Defensive Mode

## ⛔ ABSOLUTE RULE
This task NEVER executes trading operations, withdrawals, or transfers
on its own. It only diagnoses, analyzes, and presents options to the operator.
Any action involving funds requires explicit user confirmation.

## Trigger — When to Execute
- Market crash > 15% in less than 24h
- Bot reporting critical errors or anomalous behavior
- Loan health factor approaching liquidation zone
- Prolonged connectivity loss with Binance API
- Suspected security compromise of API keys

## Project Context
- **Existing ops protocols:**
  - `/api/v1/ops/red_button` — Botón rojo de emergencia (detiene bots)
  - `/api/v1/ops/protocol/close` — Protocolo de cierre ordenado
  - `/api/v1/ops/orders/cleanup/all` — Limpieza de órdenes abiertas
- **Quick reports:** `portfolio_table.py`, `loans_report.py`, `audit_full.py`
- **Infrastructure:** `BotCoordinator`, `WeightGovernor`, `ApiFuse`

## Execution Steps (in strict order)

### Step 1 — 🛑 FREEZE: Bot Status
Verify BotCoordinator status:
- Are there active bots executing trades?
- Are there open pending orders?
- Circuit breaker status (ApiFuse)

**IF there are active bots with trades in progress:**
→ Report immediately to the user before continuing
→ Present option to activate red_button

### Step 2 — 📊 ASSESS: Current Exposure
```bash
python portfolio_table.py
```
Extract and report:
- Total portfolio value
- Top 5 positions by weight
- Percentage change vs last audit (if available)
- Total exposure in leveraged positions

### Step 3 — 💰 ASSESS: Loan Status
```bash
python loans_report.py
```
For each active loan, report:
| Loan | Collateral | Health Factor | Liq. Price | Distance % |
|----------|-----------|---------------|-------------|-------------|
| ...      | ...       | ...           | ...         | ...         |

Classify:
- 🔴 **DANGER**: HF < 1.3 — imminent liquidation
- ⚠️ **ALERT**: HF 1.3-1.5 — requires active monitoring
- ✅ **SAFE**: HF > 1.5 — no immediate risk

### Step 4 — 🔍 DIAGNOSIS: Root Cause
Depending on the trigger:

**If market crash:**
- Which tokens fell the most?
- Do we have direct exposure to those tokens?
- Is our collateral at risk?

**If bot error:**
- Review recent logs of the affected bot
- Is it a connectivity, logic, or rate limit error?
- Does it affect other bots?

**If security suspicion:**
- ⛔ DO NOT make requests to the Binance API
- Report to the user so they can revoke keys manually from the web

### Step 5 — 📋 OPTIONS: Present to Operator

Generate a menu of possible actions, without executing any:

```
## 🚨 Emergency Report — [DATE/TIME]

### Situation
[2-3 line summary of current status]

### Immediate Risk
[Level: CRITICAL / HIGH / MEDIUM / LOW]
[Justification]

### Action Options

#### Option A — Defensive Mode (Conservative)
- Activate red_button → Stop all bots
- Cancel all open orders
- Do not touch loans (maintain position)
- Risk: If the market keeps falling, collateral may not be sufficient

#### Option B — Exposure Reduction (Moderate)
- Activate red_button → Stop all bots
- Cancelar órdenes abiertas
- Add collateral to loans in ⚠️ zone
- Risk: Free capital is used to reinforce positions

#### Option C — Orderly Liquidation (Aggressive)
- Activate red_button → Stop all bots
- Cancelar órdenes abiertas
- Close loans starting from lowest HF
- Redeem earn positions to cover
- Risk: Losses are crystallized but liquidation risk is eliminated

#### Option D — Hold and Monitor
- Do nothing
- Monitor HF every 15 minutes
- Risk: If the market worsens, the action window is lost

### ⏰ Estimated Time Window
[How much time before the situation escalates to the next level]
```

### Step 6 — ⏳ WAIT: Operator Decision
Present the options and WAIT for explicit instruction.
Do not execute any action involving funds without confirmation.

## Post-Emergency
Once the situation is resolved:
1. Document what happened, what was done, and the result
2. Run `@task portfolio_audit` to verify final status
3. Evaluate whether the bots' risk parameters need adjustment

## Success Criteria
- [ ] Bot status verified in < 1 minute
- [ ] Current exposure documented with concrete figures
- [ ] Health factors of all loans calculated
- [ ] Root cause identified or hypothesis formulated
- [ ] Options presented to user WITHOUT executing any
- [ ] Total diagnosis time < 5 minutes
