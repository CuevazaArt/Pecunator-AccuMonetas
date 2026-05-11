# Task: Daily Market Reconnaissance

## Objective
Execute a complete sweep of the market state using Pecunator's existing
tools and generate a consolidated executive briefing.

## Project Context
- **Token classifier:** `token_classifier.py` → generates `token_classification.txt`
- **Alpha monitor:** `alpha_monitor.py` + `get_alpha_wallet.py`
- **Earn rates:** `earn_rate_monitor.py` → logs in `earn_rates_log.csv` / `earn_rates_last.txt`
- **Loan rates:** `loan_rate_monitor.py` → logs in `loan_rates_log.csv` / `loan_rates_last.txt`
- **Current portfolio:** `portfolio_table.py` → generates `portfolio_report.txt`

## Execution Steps

### Step 1 — Portfolio Snapshot
Run `python portfolio_table.py` from the project root.
Capture the generated report in `portfolio_report.txt`.
Extract: current positions, percentage weights, unrealized PnL.

### Step 2 — Token Classification
Review `token_classification.txt` (latest output of `token_classifier.py`).
If older than 24h, re-run `python token_classifier.py`.
Extract: tokens by category (blue-chip, mid-cap, speculative, stablecoin).

### Step 3 — Alpha Opportunities
Run `python alpha_monitor.py` in query mode.
Identify: tokens with unusual movements, anomalous volume, or technical signals.

### Step 4 — Rate Analysis
Parse `earn_rates_log.csv`:
- Calculate 7-day rate trend per product (rising/falling/stable)
- Identify products with rate > 5% APY that are rising

Parse `loan_rates_log.csv`:
- Calculate average debt cost
- Detect if any loan has a sustained rising rate

### Step 5 — Data Cross-Reference
- Are there portfolio tokens with declining earn rates? → Rotation candidates
- Are there idle spot tokens that could be generating yield?
- Does any loan cost exceed the yield of the corresponding earn?

### Step 6 — Generate Briefing
Create artifact `daily_briefing_YYYY-MM-DD.md` with:

```
## 📊 Market Briefing — [DATE]

### Portfolio Status
[Summary of main positions and PnL]

### Alpha Signals
[Opportunities detected by the monitor]

### Yields (Earn)
[Table of current rates vs trend]

### Debt Costs (Loans)
[Loan status and health factors]

### ⚡ Suggested Actions
1. [Priority action 1]
2. [Priority action 2]
3. [Priority action 3]

### ⚠️ Alerts
[Any condition requiring immediate attention]
```

## Success Criteria
- [ ] Portfolio snapshot generated (< 5 min old)
- [ ] Token classification updated
- [ ] Rate trends calculated with last 7 days data
- [ ] At least 1 concrete action suggested
- [ ] Briefing delivered as artifact in readable format
