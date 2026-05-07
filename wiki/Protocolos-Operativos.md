# Operational Protocols — Pecunator

> Runbooks and operation protocols for the LLM and the operator.  
> Source: `tools/ops-protocols/tasks/`

---

## Emergency Protocols (API)

These endpoints are available in real time from the Flutter UI or via REST API:

### Red Button — `POST /api/v1/ops/red_button`

Stops **all** active bots immediately.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ops/red_button?base_asset=USDT
```

> ⚠️ Dorothy stops **before** the operation to avoid layout loops.

### Close Protocol — `POST /api/v1/ops/protocol/close`

Controlled closure: stops bots + closes positions towards USDT.

```bash
curl -X POST http://127.0.0.1:8000/api/v1/ops/protocol/close?base_asset=USDT
```

### Order Cleaning

```bash
# Cancel open LIMIT orders
curl -X POST http://127.0.0.1:8000/api/v1/ops/orders/cleanup/limit

# Cancel open STOP orders
curl -X POST http://127.0.0.1:8000/api/v1/ops/orders/cleanup/stop

# Cancel ALL open orders
curl -X POST http://127.0.0.1:8000/api/v1/ops/orders/cleanup/all
```

### Protocol Status

```bash
curl http://127.0.0.1:8000/api/v1/ops/protocol/status
```

---

## IDE Runbooks (Tasks)

Tasks executable by the LLM in the IDE. Each Task encodes a reproducible protocol.

| Task | Archive | When to use |
|------|---------|-------------|
| **Market Recon** | `tasks/market_recon.md` | Daily market briefing |
| **Portfolio Audit** | `tasks/portfolio_audit.md` | Deep audit with risk metrics |
| **Bot Health Check** | `tasks/bot_health_check.md` | Runtime integrity check |
| **Code Hardening** | `tasks/code_hardening.md` | Incremental quality pass |
| **Yield Optimizer** | `tasks/yield_optimizer.md` | Earn/loan and carry trade analysis |
| **Shell Build Verify** | `tasks/shell_build_verify.md` | Analysis and build Flutter |
| **Sub-Account Ops** | `tasks/subaccount_ops.md` | Binance Subaccounts |
| **Emergency Protocol** | `tasks/emergency_protocol.md` | Defensive diagnosis in emergencies |

---

## Task: Daily Market Recognition

**Objective:** Complete sweep of the market status and consolidated executive briefing.

### Tools used

| Tool | Output |
|-------------|--------|
| `python portfolio_table.py` | `portfolio_report.txt` — positions, weights, PnL |
| `python token_classifier.py` | `token_classification.txt` — classification by category |
| `python alpha_monitor.py` | Tokens with unusual movements |
| `earn_rates_log.csv` | Earn rate trend (7 days) |
| `loan_rates_log.csv` | Cost of debt and trend |

### Execution steps

1. **Portfolio Snapshot** — Run `python portfolio_table.py`
2. **Token Classification** — Review/update `token_classification.txt`
3. **Alpha Opportunities** — Run `python alpha_monitor.py`
4. **Rate Analysis** — Parse earn and loan logs
5. **Data crossing** — Detect candidates for turnover, idleness, or expensive loans
6. **Generate Briefing** — Artifact `daily_briefing_YYYY-MM-DD.md`

### Briefing format

``markdown
## 📊 Market Briefing — [DATE]

### Portfolio Status
[Summary of main positions and PnL]

### Alpha Signals
[Opportunities detected]

### Earn
[Table of current rates vs trend]

### Debt Costs (Loans)
[Loan status and health factors]

### ⚡ Suggested Actions
1. [Priority action 1]
2. [Priority action 2]

### ⚠️ Alerts
[Conditions requiring immediate attention]
```

---

## Task: Emergency Protocol

> ⛔ **ABSOLUTE RULE:** This task **never** executes operations on its own.  
> Only diagnose, analyze and present options. Any action on funds requires explicit confirmation.

### Triggers

- Market crash > 15% in less than 24 hours
- Bot reporting critical errors or anomalous behavior
- Loan health factor approaching liquidation zone (HF < 1.5)
- Prolonged loss of connectivity with Binance API
- Suspected security compromise in API keys

### Steps (in strict order)

| Step | Action | Notes |
|------|--------|-------|
| 1. Freeze | Check status of active bots and open orders | If there are active bots, report BEFORE continuing |
| 2. Assess Portfolio | `python portfolio_table.py` | Total exposure, top positions, PnL |
| 3. Assess Loans | `python loans_report.py` | Health factors, clearance prices |
| 4. Diagnosis | Identify root cause according to trigger | Do not make requests if there is suspicion of security |
| 5. Options | Present operator WITHOUT execute | See options menu below |
| 6. Wait | Await explicit instruction | DO NOT execute anything without confirmation |

### Health Factor Rating

| Range | Status | Recommended action |
|-------|--------|--------------------|
| HF > 1.5 | ✅ Safe | No immediate risk |
| HF 1.3–1.5 | ⚠️ Alert | Active monitoring |
| HF < 1.3 | 🔴 Danger | Liquidation imminent, action required |

### Operator options menu

| Option | Description | Risk |
|--------|-------------|--------|
| **A — Defensive** | Activate red_button + cancel orders | If the market continues to fall, the collateral may not be enough |
| **B — Reduction** | A + add collateral to loans in ⚠️ | Use free capital |
| **C — Liquidation** | B+ close loans (lowest HF first) | Crystallizes losses, eliminates risk |
| **D — Maintain** | Do nothing, monitor every 15 min | Risk if the market worsens |

---

## Audit and Traceability

- Each protocol execution is in `runtime/data/ops_audit.sqlite`
- Tables include: final status, summary, errors and timestamps
- Check the status in `GET /api/v1/ops/protocol/status`

---

## Diagnostic tools available

| Script | Function |
|--------|---------|
| `python portfolio_table.py` | Portfolio table with weights and PnL |
| `python loans_report.py` | HF loan status and settlement prices |
| `python audit_full.py` | Complete State Audit |
| `python earn_rate_monitor.py` | Current Earn Rates |
| `python loan_rate_monitor.py` | Current Loan Rates |
| `python alpha_monitor.py` | Alpha Signal Monitor |