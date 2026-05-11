# Loss and Bot Promotion Framework

> Operational philosophy: when a loss is fair, when it is unfair,
> and how a bot moves from idea to production with real capital.
> Date: 2026-05-05

---

## 1. Definition of a Fair Loss

> A loss is **fair** when it is the result of following a system
> with positive mathematical expectation, within defined parameters,
> in an environment compatible with the strategy.
>
> Everything else is noise, error, or poor architecture.

### FAIR Losses (acceptable)

- Within the bot's maximum allowed drawdown.
- Stop-loss executed correctly.
- Occurs in an environment where the strategy statistically loses
  (Dorothy in a strong trend, Masha in sideways).
- Does not break the mathematical expectation of the system.
- It is the cost of participating in an uncertain system.

### UNFAIR Losses (system errors)

- No stop-loss defined.
- Bot operating outside its ideal environment.
- Insufficient capital for the strategy.
- Incorrect or unvalidated parameters.
- Operating with unauthorized loans or leverage.
- Operating in a dead sector with no macro signals.
- Operating without sub-account segmentation.
- Code or configuration error.

### Operational principle

**The goal is not to avoid losses. It is to avoid unfair losses.**

---

## 2. Limits per Sub-account

| Sub-account | Max Drawdown | Stop Loss per Trade | Maximum Capital |
|-------------|-------------|---------------------|-----------------|
| SUB-01 (CORE_L1_DCA) | 15% | N/A (DCA, does not apply) | 40% of total |
| SUB-02 (SCALP_RANGE) | 20% | Defined by Dorothy | 25% of total |
| SUB-03 (MULTI_ASSET) | 20% | Per individual asset | 25% of total |
| SUB-04 (SECTOR_BETA) | 25% | Per sector | 15% of total |
| SUB-05 (SANDBOX) | 50% (accepted) | Free | 5% of total |

> **Note:** These are **maximum caps**, not fixed allocations. The sum
> intentionally exceeds 100% because MASTER acts as a floating reserve
> that absorbs the difference. At any time:
> `subaccount_capital + MASTER_capital = 100%`.

---

## 3. Bot Promotion Pipeline

No bot touches real capital without passing through all three stages:

### Stage A — Historical Backtest

| Requirement | Minimum criterion |
|-------------|-------------------|
| Period | >= 6 months of data |
| Trades | >= 100 simulated trades |
| Win rate | > 40% |
| Sharpe | > 0.5 |
| Max drawdown | < sub-account threshold |
| Result | Documented in `docs/bots/{bot}/backtest_report.md` |

### Stage B — Live Paper Trading

| Requirement | Minimum criterion |
|-------------|-------------------|
| Period | >= 2 weeks |
| Execution | Real bot against real data, no capital |
| Validation | Compare paper results vs backtest |
| Acceptable deviation | <= 20% discrepancy |
| Result | Log in `runtime/data/{bot}_paper_log.sqlite` |

### Stage C — Production with Real Capital

| Requirement | Minimum criterion |
|-------------|-------------------|
| Initial capital | Minimum viable (e.g. $50-100 USDT) |
| Sub-account | Assigned and isolated |
| Drawdown guard | Configured and active |
| Monitoring | First month with weekly review |
| Scaling | Only after 1 month with positive PnL |

### Visual flow

```
IDEA -> Backtest (>=6 months) -> Paper Trading (>=2 weeks) -> Production (minimum capital)
                                                                    |
                                                           1 month PnL+ -> Scale capital
                                                           3 months PnL- -> Review/Shutdown
```

---

## 4. Shutdown Protocol for Unfair Losses

If an unfair loss is detected:

1. **Stop** the bot immediately (via BotCoordinator or PANIC.lock).
2. **Record** the event in `runtime/data/incident_log.csv`.
3. **Diagnose** the root cause.
4. **Fix** the parameter, code, or configuration.
5. **Return** the bot to Stage B (paper trading) before reactivating.

Never reactivate a bot after an unfair loss without a fix.
