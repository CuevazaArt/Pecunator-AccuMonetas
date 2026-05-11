# Task: Earn/Loans Yield Optimization

## Objective
Analyze yield rates (earn) vs debt costs (loans) in real time,
detect carry trade opportunities, identify idle capital, and propose
moves to maximize the portfolio's net yield.

## Project Context
- **Earn rates log:** `earn_rates_log.csv` — historical earn rates
- **Earn rates latest:** `earn_rates_last.txt` — most recent snapshot
- **Loan rates log:** `loan_rates_log.csv` — historical loan rates
- **Loan rates latest:** `loan_rates_last.txt` — most recent snapshot
- **Subscribe to earn:** `subscribe_to_earn.py` — tool to deposit into earn
- **Redeem from earn:** `redeem_to_spot.py` — tool to move from earn to spot
- **Portfolio:** `portfolio_table.py` → `portfolio_report.txt`

## Execution Steps

### Step 1 — Capture Current State
Parse `earn_rates_last.txt` and `loan_rates_last.txt`:
- Extract: product, token, current rate (APY/APR), type (flexible/locked)

### Step 2 — Trend Analysis
Parse `earn_rates_log.csv` (at least last 7 days):
- Calculate 7d average rate per product
- Calculate trend: ↑ rising / → stable / ↓ falling
- Detect drops > 30% vs the previous week

Parse `loan_rates_log.csv` (at least last 7 days):
- Calculate 7d average cost per borrowed token
- Detect sustained increases in debt cost

### Step 3 — Opportunity Detection

#### A) Positive Carry Trade
Look for tokens where:
```
earn_rate[token] > loan_rate[token]
```
This means you can borrow a token and simultaneously
put it in earn, earning the differential (positive spread).

#### B) Earn with Declining Rate
Tokens currently in earn whose rate has fallen > 30% in 7 days.
→ Candidates for `redeem_to_spot.py` and rotation to a better product.

#### C) Idle Capital
Tokens in spot wallet that are NOT in earn or active positions.
→ Candidates for `subscribe_to_earn.py` if the rate justifies it.

#### D) Expensive Debt
Loans whose cost has risen > 20% in 7 days without the corresponding
earn rising proportionally.
→ Evaluate partial loan closure.

### Step 4 — Impact Calculation
For each detected opportunity, calculate:
- **Estimated impact** — USD/day or USD/month of additional yield
- **Risk** — Token volatility, liquidation risk
- **Effort** — Does it require multiple transactions? Is there a lock period?

### Step 5 — Generate Action Table

```
## 💰 Optimization Opportunities — [DATE]

### Current Yields
| Token | Earn Rate | 7d Trend | In Portfolio | Status |
|-------|-----------|----------|-------------|--------|
| ...   | X.XX%     | ↑/→/↓    | Yes/No      | Earn/Spot/Loan |

### Debt Costs
| Token | Loan Rate | 7d Trend | Amount | Health Factor |
|-------|-----------|----------|--------|---------------|
| ...   | X.XX%     | ↑/→/↓   | $XXX   | X.XX          |

### Recommended Actions (by impact)
| # | Action | Token | Est. Impact | Risk | Tool |
|---|--------|-------|-------------|------|------|
| 1 | Subscribe to earn | XXX | +$X/day | Low  | subscribe_to_earn.py |
| 2 | Redeem and rotate  | YYY | +$X/day | Low  | redeem_to_spot.py |
| 3 | Carry trade        | ZZZ | +$X/day | Med  | Manual |
| 4 | Close loan         | AAA | -$X/day savings | Low | Manual |
```

## Success Criteria
- [ ] Earn and loan rates parsed correctly
- [ ] 7-day trends calculated
- [ ] At least 1 opportunity identified (or confirmation there are none)
- [ ] Estimated USD impact for each opportunity
- [ ] Action table generated and prioritized
