# Ops Protocols Tool Module

- Runtime tool package: `runtime/modules/tools/ops/`
- API handlers: `runtime/api/app.py`
  - `/api/v1/ops/protocol/close`
  - `/api/v1/ops/red_button`
  - `/api/v1/ops/orders/cleanup/limit`
  - `/api/v1/ops/orders/cleanup/stop`
  - `/api/v1/ops/orders/cleanup/all`
- Audit storage: `runtime/data/ops_audit.sqlite`
- UI controls: `desktop_shell/lib/main.dart`

## Operational Tasks (`tasks/`)

IDE-executable runbooks for recurring operational workflows:

| Task | File | Purpose |
|------|------|---------|
| Market Recon | `tasks/market_recon.md` | Daily market briefing (classifier + alpha + rates) |
| Portfolio Audit | `tasks/portfolio_audit.md` | Deep audit with risk metrics and rebalancing recs |
| Bot Health Check | `tasks/bot_health_check.md` | Runtime integrity verification (coordinator, governor, fuse) |
| Code Hardening | `tasks/code_hardening.md` | Incremental quality pass (type hints, error handling, docs) |
| Yield Optimizer | `tasks/yield_optimizer.md` | Earn/loan rate analysis and carry trade detection |
| Shell Build Verify | `tasks/shell_build_verify.md` | Flutter analysis, build, and schema sync check |
| Sub-Account Ops | `tasks/subaccount_ops.md` | Binance sub-account creation, transfers, and reporting |
| Emergency Protocol | `tasks/emergency_protocol.md` | Defensive diagnostic (NO auto-trading, options only) |

