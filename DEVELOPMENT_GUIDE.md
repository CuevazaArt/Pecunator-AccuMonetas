# Development Guide — Pecunator-AccuMonetas

**Repo:** https://github.com/CuevazaArt/Pecunator-AccuMonetas  
**Main Branch:** `main`  
**Status:** 🟠 Staging-Ready — Paper Trading Active

---

## Quick Start (5 minutos)

### Clone & Setup

```bash
# Clone
git clone https://github.com/CuevazaArt/Pecunator-AccuMonetas.git
cd Pecunator-AccuMonetas

# Install Python dependencies
python -m venv venv
venv\Scripts\activate
pip install -r requirements-dev.txt

# Install Flutter dependencies
cd desktop_shell && flutter pub get && cd ..
```

### Run Tests Locally

```bash
# Python tests (run from repo root)
pytest runtime/tests/ -v

# E2E pipeline tests
pytest tests/ -v

# Flutter tests
cd desktop_shell
flutter test test/ -v
flutter analyze lib/
```

---

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
# Examples: feature/louise-stop-loss, feature/ui-portfolio-screen
```

### 2. Make Changes & Test

```bash
# Edit code...

# Run tests before committing
pytest runtime/tests/ -x -q

# Check linting
ruff check runtime/

# Flutter checks (if UI changed)
cd desktop_shell && flutter analyze lib/
```

### 3. Commit

```bash
git add <specific-files>
git commit -m "feat(scope): brief description"
# Examples:
# feat(bot): add trailing stop-loss for Louise
# fix(api): handle weight governor zone transition
# test(flutter): add bot creation widget test
```

### 4. Push & Create PR

```bash
git push -u origin feature/your-feature-name

gh pr create --base main \
             --title "feat(scope): describe feature" \
             --body "What changed and why"
```

### 5. Wait for GitHub Actions

GitHub Actions automatically runs on every PR:
- ✅ `pytest runtime/tests/` — Python test suite
- ✅ `pytest tests/` — E2E pipeline tests
- ✅ Ruff linting + type checking
- ✅ Secret scanning (gitleaks)
- ✅ Flutter analyze (if desktop_shell changed)

### 6. Merge Once Green

```bash
gh pr merge <PR_NUMBER> --squash
```

---

## Rules

### ✅ DO:
- Create feature branches FROM `main`
- Create PRs TO `main`
- Run tests locally before pushing
- Commit specific files (not `git add -A` blindly)
- Write descriptive commit messages (feat/fix/refactor/test/docs)

### ❌ DON'T:
- Push directly to `main` (branch protected)
- Skip tests before pushing
- Commit `.env`, `*.token`, `credentials.enc` files
- Use `PECUNATOR_API_AUTH_DISABLED=1` outside local dev
- Bind to `0.0.0.0` on a local dev machine (use `127.0.0.1`)

---

## Repository Structure

```
Pecunator-AccuMonetas/
├── runtime/
│   ├── bot/
│   │   ├── louise.py          # Louise DCA bot runner (main bot)
│   │   ├── _base_runner.py    # Shared runner base
│   │   └── _paper_log.py      # Paper trading log
│   ├── core/                  # WeightGovernor, ApiFuse, BudgetGuard, etc.
│   ├── api/
│   │   ├── app.py             # FastAPI factory + router wiring
│   │   ├── auth.py            # Bearer token auth dependency
│   │   └── routers/
│   │       ├── louise.py      # Louise bot endpoints
│   │       ├── system.py      # Health, weight, fuse
│   │       ├── vault.py       # Credentials vault
│   │       └── ...
│   ├── connectors/            # BinanceGateway (async)
│   ├── modules/               # TrendSignal, VMO
│   └── tests/                 # Python test suite (240+ tests)
├── tests/                     # E2E pipeline tests
├── desktop_shell/             # Flutter Windows UI
│   ├── lib/                   # Dart source
│   └── test/                  # Flutter widget tests
├── scripts/
│   ├── engine/                # run_engine.ps1, run_engine_immortal.ps1
│   └── ui/                    # run_dashboard.ps1
├── docs/                      # Architecture, specs, integration docs
├── wiki/                      # Operational guides (Spanish)
└── main.py                    # Entry point
```

---

## Key Modules

| Module | File | Purpose |
|--------|------|---------|
| **LouiseBotRunner** | `runtime/bot/louise.py` | Main DCA bot — runs trading cycles |
| **WeightGovernor** | `runtime/core/weight_governor.py` | API rate-limit zones (GREEN/YELLOW/RED) |
| **ApiFuse** | `runtime/core/api_fuse.py` | Circuit breaker + exponential backoff |
| **BudgetGuard** | `runtime/core/budget_guard.py` | Daily USDT spend ceiling |
| **LouiseDB** | `runtime/core/louise_db.py` | SQLite persistence for bot state |
| **BinanceGateway** | `runtime/connectors/binance_gateway.py` | Async Binance client |
| **auth.py** | `runtime/api/auth.py` | Bearer token generation + verification |

---

## Common Development Tasks

### Add a Python Test

```python
# runtime/tests/test_your_feature.py

import pytest

class TestYourFeature:
    def test_basic_case(self):
        # Arrange
        ...
        # Act
        ...
        # Assert
        assert result == expected
```

Run it: `pytest runtime/tests/test_your_feature.py -v`

### Add an API Endpoint

```python
# runtime/api/routers/louise.py

@router.get("/bots/{bot_id}/summary")
async def get_bot_summary(bot_id: str, db: LouiseDB = Depends(get_db)):
    bot = db.get_bot(bot_id)
    if not bot:
        raise HTTPException(status_code=404, detail="Bot not found")
    return {"bot_id": bot_id, ...}
```

All endpoints are automatically auth-protected via `Depends(verify_token)` in `app.py`.

### Add a Flutter Widget Test

```dart
// desktop_shell/test/your_feature_test.dart

import 'package:flutter_test/flutter_test.dart';

void main() {
  group('YourFeature', () {
    testWidgets('shows correct initial state', (tester) async {
      await tester.pumpWidget(const YourWidget());
      expect(find.text('Expected text'), findsOneWidget);
    });
  });
}
```

Run it: `cd desktop_shell && flutter test test/your_feature_test.dart -v`

---

## Starting the System Locally

### Option 1: Scripts (recommended)

```powershell
# Terminal 1 — Start engine
powershell -ExecutionPolicy Bypass -File scripts/engine/run_engine.ps1

# Terminal 2 — Start Flutter UI
powershell -ExecutionPolicy Bypass -File scripts/ui/run_dashboard.ps1
```

### Option 2: Manual

```powershell
# Terminal 1 — Engine (binds to localhost only)
python main.py
# API available at: http://127.0.0.1:8000
# OpenAPI docs:     http://127.0.0.1:8000/docs

# Terminal 2 — Flutter
cd desktop_shell
flutter run -d windows
```

### Stub mode (no Binance connection needed)

```powershell
$env:PECUNATOR_ENGINE_STUB=1; python main.py
```

---

## Environment Variables

```bash
# Required for production (via .env or system env)
LOUISE_API_KEY=<binance-subaccount-key>
LOUISE_API_SECRET=<binance-subaccount-secret>

# Optional overrides
PECUNATOR_API_HOST=127.0.0.1      # Never use 0.0.0.0 on local dev
PECUNATOR_API_PORT=8000
PECUNATOR_VAULT_PASSPHRASE=<passphrase>  # Required for vault encryption

# Dev only — disables auth (NEVER in production)
PECUNATOR_API_AUTH_DISABLED=0     # Keep at 0 always
```

---

## GitHub Actions Workflow

### View CI Status

```bash
# List recent runs on main
gh run list --branch main -L 10

# View a specific run
gh run view <RUN_ID> --log

# View PR checks
gh pr checks <PR_NUMBER>
```

### What Triggers CI

- ✅ Push to any `feature/**` branch
- ✅ Pull request to `main`
- ✅ Manual workflow dispatch

### What Blocks Merge

- ❌ Python tests fail (`pytest runtime/tests/`)
- ❌ E2E tests fail (`pytest tests/`)
- ❌ Ruff linting violations
- ❌ Secret scan detects credentials

---

## Testing Checklist (Before PR)

- [ ] All Python tests pass: `pytest runtime/tests/ -x -q`
- [ ] E2E tests pass: `pytest tests/ -q`
- [ ] No linting violations: `ruff check runtime/`
- [ ] No secrets in diff: `git diff --name-only`
- [ ] Flutter tests pass (if UI changed): `flutter test test/ -v`
- [ ] PR description explains what changed and why

---

## Useful Commands

```bash
# See all tests
pytest runtime/tests/ --collect-only -q

# Run only fast tests (skip slow load tests)
pytest runtime/tests/ -x -q -k "not load"

# See test coverage
pytest runtime/tests/ --cov=runtime --cov-report=term-missing

# Lint specific file
ruff check runtime/bot/louise.py

# Check git history
git log --oneline -10

# See what changed vs main
git diff origin/main --stat
```

---

**Questions?** Open a discussion on GitHub or check `wiki/` for operational guides.
