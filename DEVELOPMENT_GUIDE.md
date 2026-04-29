# Development Guide: refactor/stable-ui-and-tests

**Current Development Branch**: `refactor/stable-ui-and-tests`  
**Status**: 🟢 Active, Testing via GitHub Actions

---

## Quick Start (5 minutes)

### Clone & Setup

```bash
# Clone
git clone https://github.com/Cuevaza/PecunatorCore.git
cd PecunatorCore

# Switch to dev branch
git checkout refactor/stable-ui-and-tests
git pull

# Install dependencies
pip install -r requirements-dev.txt        # Python
cd desktop_shell && flutter pub get        # Dart
```

### Run Tests Locally

```bash
# Python tests
pytest runtime/tests/ -v

# Flutter tests
cd desktop_shell
flutter test test/ -v

# Verify Flutter code
flutter analyze lib/
```

---

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout refactor/stable-ui-and-tests
git pull
git checkout -b feature/your-feature-name

# Work on feature...
```

### 2. Commit & Test

```bash
git add .
git commit -m "feat(scope): description of change"

# Run tests locally BEFORE pushing
pytest runtime/tests/ -v
flutter test test/ -v
```

### 3. Push & Create PR

```bash
git push -u origin feature/your-feature-name

# Create PR to refactor branch (not main!)
gh pr create --base refactor/stable-ui-and-tests \
             --head feature/your-feature-name \
             --title "Feature: your feature" \
             --body "Description of changes"
```

### 4. Wait for GitHub Actions

GitHub Actions automatically runs:
- ✅ Python tests (pytest)
- ✅ Flutter tests (flutter test)
- ✅ Code analysis (ruff, dart analyzer)

You'll see status in PR.

### 5. Merge to Refactor Branch

Once tests pass and reviewed:

```bash
gh pr merge <PR_NUMBER> --merge
```

### 6. Delete Feature Branch (Optional)

```bash
git branch -d feature/your-feature-name
git push origin --delete feature/your-feature-name
```

---

## Important Rules

### ✅ DO:
- Develop on `refactor/stable-ui-and-tests`
- Create feature branches FROM `refactor/stable-ui-and-tests`
- Run tests locally before pushing
- Create PRs to `refactor/stable-ui-and-tests`
- Pull docs from main when available
- Ask for help in discussions

### ❌ DON'T:
- Push directly to `main` (it's protected)
- Create PRs to `main` without authorization
- Merge untested code to `refactor/stable-ui-and-tests`
- Ignore GitHub Actions failures
- Delete `refactor/stable-ui-and-tests` branch

---

## Code Organization

### Python (Backend)

```
runtime/
├── tests/              # ✨ NEW: Test suite
│   ├── test_dorothy.py # 25+ tests
│   └── __init__.py
├── bot/dorothy.py      # Bot logic (tested)
├── connectors/         # API clients
├── core/               # Config, security, state
├── api/                # FastAPI endpoints
└── main.py             # Entry point
```

### Flutter (Frontend)

```
desktop_shell/lib/
├── config/             # ✨ NEW: Centralized config
│   └── app_config.dart
├── providers/          # ✨ NEW: Riverpod state
│   └── app_providers.dart
├── services/           # ✨ NEW: Reusable services
│   ├── http_client.dart
│   ├── exceptions.dart
│   └── preferences.dart
├── screens/            # ✨ NEW: Page components
│   ├── home_screen.dart
│   ├── bots_screen.dart
│   └── spot_account_screen.dart
├── widgets/            # ✨ NEW: Reusable widgets
│   ├── error_display.dart
│   ├── logs_viewer.dart
│   └── gateway_status.dart
├── utils/              # ✨ NEW: Helpers
│   └── number_formatter.dart
├── api_client.dart     # Updated (uses new services)
└── main_refactored.dart # ✨ NEW: Recommended entry
```

---

## Common Development Tasks

### Task: Add a new Python test

```python
# runtime/tests/test_dorothy.py

def test_new_feature():
    """Test your new feature."""
    # Arrange
    config = DorothyConfig(symbol="BTCUSDT")
    
    # Act
    config.normalize()
    
    # Assert
    assert config.symbol == "BTCUSDT"
```

### Task: Add a new Flutter widget

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

// Use in screen:
// body: NewWidget(),
```

### Task: Add a new Riverpod provider

```dart
// desktop_shell/lib/providers/app_providers.dart

final myDataProvider = FutureProvider<MyData>((ref) async {
  final api = ref.watch(engineApiProvider);
  return api.fetchMyData();
});

// Use in widget:
// final data = ref.watch(myDataProvider);
// data.when(
//   data: (d) => Text(d.toString()),
//   loading: () => CircularProgressIndicator(),
//   error: (e, st) => ErrorDisplay(error: e),
// );
```

### Task: Update dependencies

```bash
# Python
pip install -r requirements-dev.txt

# Flutter
cd desktop_shell
flutter pub get
flutter pub upgrade  # Check for updates
```

---

## Testing Checklist

Before creating a PR:

- [ ] Code runs locally without errors
- [ ] Python tests pass: `pytest runtime/tests/ -v`
- [ ] Flutter tests pass: `flutter test test/ -v`
- [ ] Code formatted: `dart format lib/`
- [ ] No lint warnings: `flutter analyze lib/`
- [ ] Commits are descriptive
- [ ] PR description explains changes

---

## GitHub Actions

### View Test Results

```bash
# List recent runs
gh run list --branch refactor/stable-ui-and-tests -L 10

# View specific run
gh run view <RUN_ID> --log
```

### What Triggers Tests

- ✅ Push to `refactor/**`
- ✅ Push to `develop`
- ✅ Pull request to `main`
- ✅ Manual workflow dispatch

### What Stops Merge

- ❌ Python tests fail
- ❌ Flutter tests fail
- ❌ Code analysis errors (soft, can override)

---

## Sync with Main

### Get latest docs

```bash
git fetch origin
git merge origin/main -- docs/
git push origin refactor/stable-ui-and-tests
```

### Get code improvements

```bash
git fetch origin
git merge origin/main -- runtime/core/
git push origin refactor/stable-ui-and-tests
```

### Keep your feature branch updated

```bash
git fetch origin
git rebase origin/refactor/stable-ui-and-tests
git push --force-with-lease origin feature/your-branch
```

---

## Support

### Having issues?

1. Check GitHub Actions logs: `gh run view <ID> --log`
2. Run tests locally to reproduce
3. Check `docs/GITHUB_WORKFLOW.md` for troubleshooting
4. Open issue or discussion

### Need to merge to main?

1. Get explicit authorization: "merge to main approved"
2. Create formal PR: `gh pr create --base main`
3. Wait for GitHub Actions + owner approval
4. Merge when all checks pass

---

## Key Files to Know

| File | Purpose | Status |
|------|---------|--------|
| `REFACTOR_SUMMARY.md` | Overview of changes | ✅ Read this first |
| `REFACTOR_ARCHITECTURE.md` | Design deep-dive | ✅ Reference |
| `VALIDATION_CHECKLIST.md` | Testing steps | ✅ Follow for QA |
| `docs/GITHUB_WORKFLOW.md` | Collaboration guide | ✅ For multi-office setup |
| `requirements-dev.txt` | Python dependencies | ✅ Keep updated |
| `desktop_shell/pubspec.yaml` | Flutter dependencies | ✅ Keep updated |

---

## Performance Tips

### Speed up Python tests

```bash
# Run specific test file
pytest runtime/tests/test_dorothy.py -v

# Run specific test
pytest runtime/tests/test_dorothy.py::test_defaults -v

# Show slowest tests
pytest runtime/tests/ -v --durations=10
```

### Speed up Flutter builds

```bash
# Use --split-debug-info for faster builds
flutter run --split-debug-info

# Hot reload during development
# Press 'r' in terminal while running
```

---

## Useful Commands

```bash
# See branch status
git status

# See commit history
git log --oneline -10

# See what changed
git diff origin/refactor/stable-ui-and-tests

# Undo local changes
git checkout -- <file>

# Undo last commit (keep changes)
git reset --soft HEAD~1

# See who changed what
git blame <file>
```

---

## Ready to start? 🚀

1. ✅ Clone the repo
2. ✅ Switch to `refactor/stable-ui-and-tests`
3. ✅ Run tests locally
4. ✅ Create a feature branch
5. ✅ Make your changes
6. ✅ Create a PR
7. ✅ Wait for GitHub Actions
8. ✅ Get reviewed & merged

**Questions?** Check `docs/GITHUB_WORKFLOW.md` or open a discussion!
