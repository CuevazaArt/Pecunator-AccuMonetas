# Pecunator Desktop Shell

Dedicated Flutter desktop UI for `PecunatorCore`.

## Runtime model

- This app talks to the local Python engine over HTTP loopback (`http://127.0.0.1:8765` by default).
- No web UI and no browser dashboard are used.
- API keys are handled by the Python vault layer, not stored in Dart sources.

## Run (Windows)

1. Start engine API from repo root:
   - `python main.py`
2. Start Flutter desktop app:
   - `flutter run -d windows`

## Build (Windows Release)

- `flutter build windows`
- Run binary:
  - `build/windows/x64/runner/Release/pecunator_desktop.exe`

## Current feature focus

- Multi-instance Dorothy hub control
- Active credential visibility and vault management modal
- Per-instance raw Binance logs (SQLite-backed)
- Timestamp sync and runtime status controls
