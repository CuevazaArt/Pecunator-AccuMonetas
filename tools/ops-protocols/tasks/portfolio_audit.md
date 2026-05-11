# Task: Deep Portfolio Audit

## Objective
Execute a complete portfolio audit, analyze deviations from the previous session,
calculate risk metrics, and propose rebalancing actions where appropriate.

## Project Context
- **Full audit:** `audit_full.py` → generates `audit_report.txt`
- **Loans report:** `loans_report.py` → generates `loans_report.txt`
- **Portfolio table:** `portfolio_table.py` → generates `portfolio_report.txt`
- **Classification:** `token_classification.txt`

## Execution Steps

### Step 1 — Generate Fresh Reports
```bash
python audit_full.py
python loans_report.py
python portfolio_table.py
```
Verify that all 3 reports were generated successfully.

### Step 2 — Position Analysis
Parse `audit_report.txt` and `portfolio_report.txt`:
- List all positions with: token, quantity, USD value, weight %
- Calculate concentration: Does any token exceed 25% of the portfolio?
- Classify exposure by sector (using `token_classification.txt`)

### Step 3 — Debt Analysis
Parse `loans_report.txt`:
- Extract active loans: token, amount, rate, collateral, health factor
- Calculate total debt/equity ratio
- Identify loans with health factor < 1.5

### Step 4 — Drift Detection
If a previous audit report exists (prior file or in history):
- Compare current weights vs previous
- Detect positions that grew/shrank > 10%
- Detect new positions or closed positions

### Step 5 — Risk Metrics
Calculate and report:
| Métrica | Fórmula | Umbral |
|---|---|---|
| Maximum concentration | max(token_weight) | ⚠️ > 25% |
| Debt/equity ratio | total_debt / total_equity | ⚠️ > 0.5 |
| Minimum health factor | min(HF per loan) | 🔴 < 1.3, ⚠️ < 1.5 |
| Idle tokens in spot | tokens without earn or position | 💡 opportunity |
| Earn rate vs loan cost | spread between yield and cost | 💡 if positive |

### Step 6 — Recommendations
Generate a prioritized list of actions:
1. **URGENT** — Positions requiring immediate action (low health factor)
2. **OPTIMIZE** — Rebalancing to reduce concentration
3. **OPPORTUNITY** — Idle tokens that could generate yield
4. **MONITOR** — Positions requiring no action but warranting watch

## Alert Criteria
- 🔴 **CRITICAL**: Health factor < 1.3 on any loan
- ⚠️ **WARNING**: Concentration > 25% in a single token
- ⚠️ **WARNING**: Debt/equity ratio > 0.5
- 💡 **INFO**: Idle capital > 5% of total portfolio

## Expected Output
Artifact `audit_YYYY-MM-DD.md` with all metrics, tables, and recommendations.

## Success Criteria
- [ ] All 3 base reports generated without errors
- [ ] Risk metrics calculated
- [ ] Drift detected (if prior data available)
- [ ] At least 1 actionable recommendation generated
- [ ] Artifact delivered with readable tabular format
