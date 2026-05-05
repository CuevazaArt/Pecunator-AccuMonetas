# Installation and Startup — Pecunator

> Complete guide to install, configure and start Python engine and Flutter Desktop UI.

---

## Requirements

| Component | Minimum version |
|------------|---------------|
| Python | 3.11+ |
| Flutter SDK | Latest stable |
| Windows | For desktop production |
| Git | Any recent version |

---

## 1. Clone the Repository

```bash
git clone https://github.com/CuevazaArt/Pecunator.git
cd Pecunator
```

---

## 2. Python Engine

### 2.1 Install dependencies

```bash
# Production dependencies
pip install -r requirements.txt

# Development dependencies (tests, linters)
pip install -r requirements-dev.txt
```

### 2.2 Configure credentials

**Option A — Environment variables (fast boot):**

```bash
# Windows PowerShell
$env:PECUNATOR_BINANCE_API_KEY = "tu_api_key"
$env:PECUNATOR_BINANCE_API_SECRET = "tu_api_secret"
```

**Option B — Encrypted Vault (recommended for production):**  
Manage from the Flutter UI (see Vault section in the UI).

> ⚠️ Use **a single active source** per session to avoid mixing accounts.

### 2.3 Start the engine

```bash
# Direct boot
python main.py

# With PowerShell (venv + boot)
powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine.ps1

# Immortal engine (supervisor that restarts if the process crashes)
powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine_immortal.ps1
```

**Engine available at:** `http://127.0.0.1:8765`  
**Interactive OpenAPI:** `http://127.0.0.1:8765/docs`

### 2.4 Optional environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PECUNATOR_API_HOST` | `127.0.0.1` | API Host |
| `PECUNATOR_API_PORT` | `8765` | API Port |
| `PECUNATOR_API_WEIGHT_LIMIT_1M` | `6000` | REST weight reference limit for UI bar |
| `PECUNATOR_EQUITY_BASE_ASSET` | `USDT` | Base asset for equity metrics |
| `PECUNATOR_EQUITY_AVG_WINDOW` | `6` | Equity rolling average window |
| `PECUNATOR_EQUITY_POLL_STRIDE` | `5` | How many cycles to refresh equity |
| `PECUNATOR_ENGINE_STUB` | — | If `=1`, serverless stub mode (log only) |

### 2.5 Engine Troubleshooting

**Port 8765 occupied by previous process:**
``powershell
powershell -ExecutionPolicy Bypass -File scripts/engine/stop_engine_port.ps1
```

**Autostart after Windows restart:**
``powershell
powershell -ExecutionPolicy Bypass -File scripts/engine/InstallImmortalStartup.ps1
```

---

## 3. Flutter Desktop UI

### 3.1 Install Flutter SDK

Install [Flutter SDK for Windows](https://docs.flutter.dev/get-started/install/windows).

### 3.2 Initialize Flutter Desktop

```powershell
# Desde la raíz del repo
powershell -ExecutionPolicy Bypass -File scripts/ui/init_flutter_desktop.ps1
```

This installs dependencies and configures `desktop_shell/`.

### 3.3 Run the UI

```bash
#Option 1: Direct Flutter
cd desktop_shell
flutter run -d windows

# Option 2: PowerShell Script (PATH reloaded + flutter run)
powershell -ExecutionPolicy Bypass -File scripts/ui/run_dashboard.ps1

# Option 3: Double click
scripts/ui/run_dashboard.cmd
```

### 3.4 Create desktop shortcut

```powershell
# Crea PecunatorCore.lnk en el escritorio (motor + app)
powershell -ExecutionPolicy Bypass -File scripts/ui/InstallDesktopShortcut.ps1
```

The launcher is located in `scripts/ui/PecunatorDesktopLauncher.ps1`.

### 3.5 Build for production

```bash
cd desktop_shell
flutter build windows
# Ejecutable: desktop_shell/build/windows/x64/runner/Release/pecunator_desktop.exe
```

### 3.6 Clear cache and recompile

> ⚠️ Close `pecunator_desktop.exe` first to free DLLs.

```bash
cd desktop_shell
flutter clean
flutter pub get
flutter build windows     # o flutter run -d windows
```

**Hub data in SQLite:** `runtime/data/dorothy_hub.sqlite`  
Delete this file only if you want to reset the hub's logs/config (make a copy first).

---

## 4. Recommended Startup Flow

```
1. Start Python engine:
   powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine.ps1

2. Verify that the API responds:
   curl http://127.0.0.1:8765/api/v1/vault/status

3. Start UI Flutter:
   scripts/ui/run_dashboard.cmd

4. Configure credentials from the UI (Vault tab)

5. Start bot instances from Hubs
```

---

## 5. Quick Check

```bash
# Engine running?
curl http://127.0.0.1:8765/api/v1/vault/status

# Active credentials?
curl http://127.0.0.1:8765/api/v1/credentials/active

# Gateway connected?
curl http://127.0.0.1:8765/api/v1/gateway/snapshot
```

---

## 6. Tests

```bash
#Python
pytest runtime/tests/ -v

# Python (specific test)
pytest runtime/tests/test_dorothy.py -v

#Flutter
cd desktop_shell
flutter test test/ -v

# Flutter Analysis
flutter analyze lib/
```