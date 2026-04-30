# Dorothy Module

- Runtime runner: `runtime/modules/bots/dorothy.py`
- Hub service: `runtime/api/bot_service.py`
- API surface: `/api/v1/hub/bots/*`
- UI hub: `desktop_shell/lib/main.dart` (`Dorothy Hub`)
- SQLite stores:
  - `runtime/data/dorothy_hub.sqlite`
  - tables: `dorothy_instances`, `dorothy_logs`, `dorothy_runtime_state`, `dorothy_equity_snapshots`, `dorothy_metrics_log`

