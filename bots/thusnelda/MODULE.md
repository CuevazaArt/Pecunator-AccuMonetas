# Thusnelda Module

- Runtime runner: `runtime/bot/thusnelda.py`
- Hub service: `runtime/api/thusnelda_service.py`
- API surface: `/api/v1/thusnelda/bots/*`
- UI hub: `desktop_shell/lib/main.dart` (`Thusnelda1.0 Hub`)
- SQLite stores:
  - `runtime/data/thusnelda_hub.sqlite`
  - tables: `thusnelda_instances`, `thusnelda_logs`, `thusnelda_runtime_state`, `thusnelda_equity_snapshots`, `thusnelda_metrics_log`
- Paper trade log: `runtime/data/paper_trades.sqlite` (shared, filtered by bot_type="thusnelda")
