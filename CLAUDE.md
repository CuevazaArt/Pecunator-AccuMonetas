# Pecunator-AccuMonetas: New Trading Bot Hub

**Repo:** https://github.com/CuevazaArt/Pecunator-AccuMonetas.git  
**Base Template:** PecunatorCore (v3.7.5 stable)  
**Status:** 🟠 Staging Phase — Paper Trading Active, Production Validation Pending  
**Blockers:** UI testing (5h), Ops docs (3h), Tech debt cleanup (3h) — see ESTADO_REAL.md

---

## 🎯 Project Overview

**Pecunator-AccuMonetas** es un nuevo hub de bots de trading autónomo, basado en la arquitectura probada de PecunatorCore. Reutiliza toda la infraestructura de producción (API, WebSocket, telemetría, DB, rate-limiting, error handling) pero implementa:

- ✅ **Nuevo bot de trading** (estrategia específica — *TBD*)
- ✅ **UI Flutter customizada** para las necesidades de ese bot
- ✅ **Subacuenta de Binance dedicada** (a especificar)

### Directiva de Trabajo

- **Coordinación, decisiones, feedback:** Español latino
- **Código fuente, commits, documentación técnica:** Inglés

---

## 🏗️ Technology Stack (Inherited from PecunatorCore)

### Backend
- **Framework:** FastAPI + Uvicorn
- **Async Runtime:** Python 3.11+ con `asyncio` nativo
- **Exchange Connector:** python-binance (AsyncClient)
- **Database:** SQLite (bot state + audit trail)
- **Real-time:** WebSocket (metrics, price feeds, alerts)
- **Credentials:** Fernet-encrypted vault (`runtime/data/credentials.enc`)

### Frontend
- **Desktop UI:** Flutter (Windows native)
- **State:** Provider / BLoC pattern
- **Charts:** Syncfusion (candlestick, metrics)
- **Auth:** Bearer token from `runtime/data/api.token`

### Risk & Control Modules
- **WeightGovernor** — API rate-limit zones (GREEN/YELLOW/RED)
- **ApiFuse** — Circuit breaker with exponential backoff
- **BotCoordinator** — Load distribution across bot instances
- **BudgetGuard** — Daily USDT spend ceiling
- **OrderLedger** — Forensic audit trail
- **SymmetryGuard** — Multi-bot watchdog + auto-recovery
- **StateWAL** — Crash-safe state persistence (WAL-backed)

---

## 📋 Development Workflow

### Phase 1: Structure & Setup (Current)
- [ ] Define new trading bot strategy + name
- [ ] Map UI screens required for bot
- [ ] Identify Binance subaccount (API keys, daily limit)
- [ ] Create feature branches from `main`
- [ ] Adapt `runtime/bot/` with new bot implementation

### Phase 2: Backend Implementation
- [ ] Implement bot runner (`runtime/bot/`)
- [ ] Connect to BinanceGateway
- [ ] Integrate control modules (WeightGovernor, BudgetGuard, etc.)
- [ ] Create API endpoints in `runtime/api/routers/`
- [ ] Write tests in `runtime/tests/`

### Phase 3: Frontend Implementation
- [ ] Adapt `desktop_shell/` UI screens
- [ ] Implement WebSocket listeners
- [ ] Add real-time metrics/charts
- [ ] Test Flutter app against local engine

### Phase 4: Testing & Hardening
- [ ] Run full test suite: `pytest runtime/tests/ -x`
- [ ] Flutter test: `flutter test test/ -v`
- [ ] Integration testing (UI ↔ API)
- [ ] Load testing (API weight limits)

### Phase 5: Deployment
- [ ] Create release branch
- [ ] Tag version (semantic versioning)
- [ ] Deploy to production with explicit operator approval

---

## 📂 Repository Structure

```
Pecunator-AccuMonetas/
├── runtime/
│   ├── bot/                 ← NEW BOT IMPLEMENTATION HERE
│   ├── core/                ← Reuse: WeightGovernor, ApiFuse, etc.
│   ├── api/                 ← Reuse: FastAPI routers + expand
│   ├── connectors/          ← Reuse: BinanceGateway (async)
│   ├── modules/             ← Reuse: TrendSignal, EVI, extend as needed
│   ├── tests/               ← Expand with new bot tests
│   └── data/                ← SQLite, vault, API token
├── desktop_shell/           ← ADAPT: Flutter UI for new bot
├── scripts/                 ← Reuse: engine startup, Flutter launcher
├── docs/                    ← Document architecture for new bot
├── wiki/                    ← Operational guides (Spanish)
└── main.py                  ← Entry point (no changes needed)
```

---

## 🔐 Credentials & Configuration

### Environment Variables
```bash
# New bot API keys (Binance subaccount)
BOT_NAME_API_KEY=<key>
BOT_NAME_API_SECRET=<secret>

# Optional overrides
PECUNATOR_API_HOST=127.0.0.1
PECUNATOR_API_PORT=8000
PECUNATOR_API_WEIGHT_LIMIT_1M=6000  # REST weight ceiling
PECUNATOR_API_AUTH_DISABLED=0       # Keep enabled in production
```

### Vault Management
- Credentials stored encrypted: `runtime/data/credentials.enc`
- Managed from Flutter UI (secure input dialogs)
- Single source per session (avoid account mixing)

**Subaccount to use:** *TBD — specify which Binance subaccount*

---

## 🧪 Testing Policy

**Before every merge, tests must pass:**

```bash
# Python tests
pytest runtime/tests/ -x -q --tb=short

# Flutter tests (if UI changed)
cd desktop_shell
flutter test test/ -v
flutter analyze lib/

# Quick local run (optional)
PECUNATOR_ENGINE_STUB=1 python main.py
```

---

## 📝 Git Workflow

### Create Feature Branch
```bash
git checkout main
git pull origin main
git checkout -b feature/bot-name-implement
# or: feature/ui-screens, feature/api-endpoints, etc.
```

### Commit Convention
```
feat(scope): brief description
fix(scope): bug fix description
refactor(scope): structural changes
test(scope): test additions

Example:
feat(bot): implement AccuMonetas trend detection logic
fix(api): handle edge case in weight governor zone transition
```

### Submit PR
```bash
git push -u origin feature/bot-name-implement

gh pr create --base main \
             --title "feat(bot): describe feature" \
             --body "Detailed description of changes"
```

### CI/CD
GitHub Actions will run:
- ✅ `pytest runtime/tests/`
- ✅ Ruff linting + type checking
- ✅ Secret scanning
- ✅ Flutter analyze (if applicable)

---

## 🚀 Quick Start (Development)

```bash
# 1. Setup environment
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt

# 2. Start engine
powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine.ps1

# 3. Start Flutter UI (in another terminal)
cd desktop_shell
flutter pub get
flutter run -d windows

# 4. Run tests
pytest runtime/tests/ -x
```

---

## 📚 Key Documentation

| Document | Purpose |
|----------|---------|
| `README.md` | Project overview, quick start |
| `DEVELOPMENT_GUIDE.md` | Step-by-step dev workflow |
| `docs/architecture-next.md` | Flutter + engine architecture |
| `docs/repo-modules-map.md` | Module ownership & responsibilities |
| `wiki/` | Operational guides (Spanish) |
| `.env.example` | Configuration template |

---

## ❓ Questions Before Starting

**Define these before Phase 1 ends:**

1. **Bot Name & Strategy:** What is the trading logic? (e.g., "AccuMonetas DCA", "Grid Trading", etc.)
2. **Binance Subaccount:** Which subaccount's credentials will be used? Daily spend limit?
3. **Key UI Screens:** What does the operator see/control? (Dashboard, Orders, Alerts, Risk Controls?)
4. **Entry/Exit Signals:** Manual, automatic, or hybrid?
5. **Hedge Strategy:** Does it operate alongside Dorothy/Elphaba, or independently?

---

## 🔗 References

- **PecunatorCore (base):** https://github.com/Cuevaza/PecunatorCore
- **This repo:** https://github.com/CuevazaArt/Pecunator-AccuMonetas.git
- **Binance API Docs:** https://binance-docs.github.io/apidocs/
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Flutter Docs:** https://docs.flutter.dev/

---

**Last Updated:** 2026-05-11  
**Next Steps:** Define bot strategy + subaccount → Create feature branches → Implement backend → Adapt UI
