# Masha Module

- Runtime runner: `runtime/bot/masha.py`
- Hub service: `runtime/api/masha_service.py`
- API surface: `/api/v1/masha/bots/*`
- UI hub: `desktop_shell/lib/main.dart` (`Masha2.0 Hub`)
- SQLite stores:
  - `runtime/data/masha_hub.sqlite`
  - tables: `masha_instances`, `masha_logs`, `masha_runtime_state`, `masha_equity_snapshots`, `masha_metrics_log`
- Paper trade log: `runtime/data/paper_trades.sqlite` (shared, filtered by bot_type="masha")
