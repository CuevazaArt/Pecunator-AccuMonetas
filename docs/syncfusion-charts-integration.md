# Syncfusion Charts Integration Plan (Desktop UI)

This document describes how to adopt `syncfusion_flutter_charts` in `desktop_shell` without breaking current operational flows.

## Goal

Render real-time operational charts for:

- Spot account equity (`current`, `avg`, `high_avg`)
- REST weight usage (`X-MBX-USED-WEIGHT-1M`)
- Optional per-bot lifecycle/health telemetry

## Current data sources (already available)

- `GET /api/v1/gateway/snapshot`
  - `account_equity`: rolling equity in base asset (from runtime gateway)
  - `used_weight_1m`, `weight_limit_1m`, gateway/hub context
- `GET /api/v1/account/wallets?base_asset=USDT`
  - `equity`: on-demand conversion summary for Spot details
- `GET /api/v1/usage/rest-weight/samples?limit=...`
  - historical sampled REST weight timeline

## Proposed package

Add in `desktop_shell/pubspec.yaml`:

```yaml
dependencies:
  syncfusion_flutter_charts: ^29.2.11
```

Then run:

```powershell
cd desktop_shell
flutter pub get
```

## UI integration plan (incremental)

1) Spot details: Equity trend card
- Build a lightweight model:
  - `ts` (`DateTime`)
  - `equityCurrent` (`double`)
  - `equityAvg` (`double`)
  - `equityHighAvg` (`double`)
- Feed from periodic `gatewaySnapshot()` polling already used by Spot page.
- Render `SfCartesianChart` with:
  - line series for current
  - line series for rolling avg
  - optional dashed line for historical avg high

2) REST monitor dialog: weight timeline
- Reuse `/usage/rest-weight/samples`.
- Plot `used_weight_1m` over `ts_utc`.
- Add horizontal threshold line from `weight_limit_1m`.

3) Optional Dorothy panel chart
- If per-bot series is later exposed, use area/line chart for:
  - runner heartbeat
  - error streaks
  - decision cadence

## Recommended charting conventions

- Keep max points in memory (e.g., 120-300) to avoid UI jank.
- Prefer numeric parsing with safe fallback (`double.tryParse`).
- Use local time formatting for axis labels.
- Avoid repaint storms: update chart at fixed cadence (e.g., every 2-3s).
- Preserve non-chart fallback widgets for environments where chart rendering is disabled.

## Data contract notes

- `account_equity.current|avg|high_avg` arrive as decimal strings; convert carefully.
- `missing_assets_count` indicates partial conversion quality (no price path found).
- REST samples are throttled/heartbeat-based, so sparse points are expected by design.

## Why this approach

- No new backend endpoints are required for initial chart rollout.
- Existing runtime modules already separate concerns:
  - equity computation/rolling stats
  - REST usage sampling/history
- This enables chart adoption as a UI-only enhancement first, with low operational risk.
