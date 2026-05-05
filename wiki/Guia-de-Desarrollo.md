# Development Guide — Pecunator

> Workflow, conventions, tests and CI/CD to contribute to the project.  
> Default branch: `main`.

---

## Quick Start (5 minutes)

```bash
#1. Clone
git clone https://github.com/CuevazaArt/Pecunator.git
cd pecunator

#2. Install Python dependencies
pip install -r requirements-dev.txt

#3. Install Flutter dependencies
cd desktop_shell && flutter pub get && cd ..

# 4. Verify tests
pytest runtime/tests/ -v
cd desktop_shell && flutter test test/ -v
```

---

## Branch Structure

| Branch | Purpose |
|--------|-----------|
| `main` | Stable/default branch and release baseline |
| `refactor/stable-ui-and-tests` | Long-lived integration branch for refactor streams |
| `feature/*` | Feature branches derived from `main` or refactor branch |

### Rules

**✅ DO:**
- Develop in feature branches and open PRs with explicit base branch
- Use `main` for regular PRs unless refactor stream is required
- Run tests locally before pushing
- Document changes in `docs/CHANGELOG.md`

**❌ DON'T:**
- Merge large refactor streams to `main` without review and CI green
- Merge code without tests
- Ignore GitHub Actions crashes

---

## Workflow

### 1. Create feature branch

```bash
git checkout main
git pull
git checkout -b feature/nombre-de-la-feature
```

### 2. Develop and test

```bash
# Make changes...

# Python tests
pytest runtime/tests/ -v

# Flutter tests
cd desktop_shell
flutter test test/ -v
flutter analyze lib/

# Commit with conventional format
git add .
git commit -m "feat(scope): change description"
```

**Commit format:**

| Prefix | When to use |
|---------|-------------|
| `feat(scope):` | New features |
| `fix(scope):` | Bugfix |
| `docs:` | Documentation only |
| `refactor(scope):` | Refactoring without functional change |
| `test:` | Tests |
| `chore:` | Maintenance tasks |

### 3. Push and PR

```bash
git push -u origin feature/feature-name

# Create PR towards main (or another agreed base branch)
gh pr create --base main \
             --head feature/feature-name \
             --title "feat: description" \
             --body "Description of changes"
```

### 4. Wait for GitHub Actions

GitHub Actions automatically run:
- ✅ Python tests (pytest in Python 3.11 and 3.12)
- ✅ Flutter tests (flutter test)
- ✅ Code analysis (ruff, mypy, dart analyzer)
- ✅ Changelog discipline check for PRs to `main`/`develop`
- ✅ Secret scanning for pushes and PRs to main branches

### 5. Merge a refactor branch

Once the tests are passed and there is a review:

```bash
gh pr merge <PR_NUMBER> --merge
```

---

## Tests

### Python

```bash
# All tests
pytest runtime/tests/ -v

# Specific test
pytest runtime/tests/test_dorothy.py -v

# Specific test by name
pytest runtime/tests/test_dorothy.py::test_defaults -v

# With duration report
pytest runtime/tests/ -v --durations=10

# Coverage
pytest runtime/tests/ --cov=runtime --cov-report=term-missing
```

**Test structure:**

```
runtime/
└── tests/
    ├── __init__.py
  └── test_dorothy.py    # sample test suite file
```

###Flutter

```bash
cd desktop_shell

# All tests
flutter test test/ -v

# Static analysis
flutter analyze lib/

# Code format
dart format lib/
```

---

## Code Organization

### Python (Backend)

```
runtime/
├── tests/              # Suite de tests
├── api/                # FastAPI endpoints
├── bot/                # Compatibilidad legacy (deprecado)
├── connectors/         # Clientes API
├── core/               # Config, seguridad, state
└── modules/
    ├── bots/           # Lógica de bots (imports canónicos aquí)
    └── tools/          # Herramientas operativas
```

**Python Conventions:**
- Type hints in public functions
- Docstrings in classes
- Anti-NaN guards on `Decimal` operations
- `sanitize_log_message()` on all log output
- No bare `except:` — always specify type
- Imports: stdlib → third party → local

###Flutter (Frontend)

```
desktop_shell/lib/
├── config/app_config.dart      # centralized config
├── providers/app_providers.dart # state with Riverpod
├── services/
│   ├── http_client.dart
│   ├── exceptions.dart
│   └── preferences.dart
├── screens/                    # full pages
│   ├── home_screen.dart
│   ├── bots_screen.dart
│   └── spot_account_screen.dart
├── widgets/                    # reusable widgets
│   ├── error_display.dart
│   ├── logs_viewer.dart
│   └── gateway_status.dart
├── utils/number_formatter.dart # helpers
├── api_client.dart             # engine HTTP client
└── main.dart                   # entrypoint
```

---

## Examples of Common Tasks

### Add a Python test

```python
# runtime/tests/test_dorothy.py

def test_new_feature():
    """Test of the new feature."""
    #Arrange
    config = DorothyConfig(symbol="BTCUSDT")
    
    #Act
    config.normalize()
    
    # Assert
    assert config.symbol == "BTCUSDT"
```

### Add a Flutter widget

```dart
// desktop_shell/lib/widgets/new_widget.dart

import 'package:flutter/material.dart';

class NewWidget extends StatelessWidget {
  const NewWidget({super.key});

@override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Text('New Widget'),
      ),
    );
  }
}
```

### Add a Riverpod provider

```dart
// desktop_shell/lib/providers/app_providers.dart

final myDataProvider = FutureProvider<MyData>((ref) async {
  final api = ref.watch(engineApiProvider);
  return api.fetchMyData();
});
```

---

## GitHub Actions

### Available workflows

| Workflow | Trigger | What it runs |
|----------|---------|-------------|
| `test-python.yml` | Push to `refactor/**`, `main`, `develop`; PR to `main` | ruff + mypy + pytest (Python 3.11, 3.12) |
| `test-flutter.yml` | Push to `refactor/**`, `main`, `develop`; PR to `main` | flutter analyze + format check + flutter test |
| `protect-main.yml` | PR to `main` | Restricts direct refactor-to-main merges |
| `sync-main.yml` | Push to `main` when docs change | Sync docs/README from `main` into refactor branch |
| `secret-scan.yml` | Push and PR to main branches | Gitleaks secret detection |
| `changelog-discipline.yml` | PR to `main` or `develop` | Enforces updates to `docs/CHANGELOG.md` when code changes |

### View CI logs

```bash
# List latest runs
gh run list --branch main -L 10

# View logs of an execution
gh run view <RUN_ID> --log
```

---

## Synchronization with Main

```bash
# Get latest docs from main
git fetch origin
git merge origin/main -- docs/
git push origin feature/your-branch

# Get code improvements from main
git fetch origin
git merge origin/main -- runtime/core/
git push origin feature/your-branch

# Keep feature branch updated
git fetch origin
git rebase origin/main
git push --force-with-lease origin feature/your-branch
```

---

## Checklist before creating a PR

- [ ] The code runs locally without errors
- [ ] Python tests pass: `pytest runtime/tests/ -v`
- [ ] Flutter tests pass: `flutter test test/ -v`
- [ ] Formatted code: `dart format lib/`
- [ ] No lint warnings: `flutter analyze lib/`
- [ ] Descriptive commits with conventional format
- [ ] PR description explains the changes

---

## Process to Merge to Main

1. Obtain **explicit authorization**: "merge to main approved"
2. Create formal PR: `gh pr create --base main --head refactor/stable-ui-and-tests`
3. Wait for GitHub Actions to pass + owner approval
4. Merge when all checks are green