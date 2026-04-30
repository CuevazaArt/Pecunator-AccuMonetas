# GitHub Workflow: Parallel Development & Safeguards

## Overview

PecunatorCore uses a **protected main branch** with parallel development on `refactor/stable-ui-and-tests`. This enables:

- ✅ Multiple offices working in parallel
- ✅ Continuous testing via GitHub Actions
- ✅ Safe synchronization from main (docs, improvements)
- ✅ Zero accidental merges to production

---

## Branch Policy

### Protected Main (`main`)

```
✅ ALLOWED:
  - Pull requests from any non-refactor/* branch
  - Documentation updates
  - Critical hotfixes

❌ BLOCKED:
  - Direct push (protected)
  - Merges from refactor/* branches without explicit authorization
  - Unreviewed PRs (require approval)
```

### Refactor Branch (`refactor/stable-ui-and-tests`)

```
✅ ALLOWED:
  - All development work
  - Feature additions
  - Testing improvements
  - Documentation

❌ BLOCKED:
  - Nothing! Full autonomy within this branch
  - Can merge pull requests from derived branches
```

---

## Workflow: Collaborative Development

### Scenario 1: Work on Refactor Branch (Default)

```bash
# Office 1
git fetch origin
git checkout refactor/stable-ui-and-tests
git pull

# Make changes
git add .
git commit -m "feat(ui): add bot config history"
git push origin refactor/stable-ui-and-tests

# Office 2 (same time)
git fetch origin
git checkout refactor/stable-ui-and-tests
git pull

# See office 1's changes
git log --oneline -5
# ✅ Both working in sync!
```

### Scenario 2: Sync Documentation from Main

GitHub Actions automatically syncs docs from `main`:

```bash
# Someone updates docs on main
# Example: docs/API.md gets updated

# Automatic:
# ✅ GitHub Actions runs on main push
# ✅ Pulls docs changes to refactor/stable-ui-and-tests
# ✅ You see updated docs locally after `git pull`

# Manual sync (if needed):
git fetch origin
git merge origin/main -- docs/ README.md
git push origin refactor/stable-ui-and-tests
```

### Scenario 3: Get Code Improvements from Main

```bash
# Someone fixes a critical bug on main
# Example: runtime/core/security_util.py improved

# Pull the improvement:
git fetch origin
git merge origin/main -- runtime/core/security_util.py
git push origin refactor/stable-ui-and-tests

# Or use merge strategy to resolve:
git merge origin/main -X theirs
git push origin refactor/stable-ui-and-tests
```

### Scenario 4: Authorization to Merge to Main

When refactoring is approved:

```bash
# Step 1: Get explicit authorization
# You: "Ready to merge refactor/stable-ui-and-tests to main"
# Owner: "merge to main approved"

# Step 2: Create a formal PR (not direct merge)
gh pr create --base main --head refactor/stable-ui-and-tests \
  --title "Merge refactoring: stable UI and tests" \
  --body "This PR merges the complete refactoring..."

# Step 3: Owner reviews and approves

# Step 4: Merge (this time allowed)
gh pr merge --merge
```

---

## GitHub Actions Automation

### 1. **Python Tests** (`test-python.yml`)

Runs automatically on:
- Push to `refactor/**`, `main`, `develop`
- Pull request to `main`
- Changes to `runtime/`

```
✅ Runs on: Python 3.11, 3.12
✅ Tests: pytest (25+ tests for Dorothy)
✅ Reports: Coverage to Codecov
✅ Artifact: Failed tests block merge (if PR to main)
```

### 2. **Flutter Tests** (`test-flutter.yml`)

Runs automatically on:
- Push to `refactor/**`, `main`, `develop`
- Pull request to `main`
- Changes to `desktop_shell/`

```
✅ Runs on: Flutter latest stable
✅ Tests: Flutter test suite (18+ UI tests)
✅ Analysis: Dart analyzer
✅ Reports: Coverage to Codecov
✅ Artifact: Failed tests block merge (if PR to main)
```

### 3. **Protect Main** (`protect-main.yml`)

Prevents accidental merges:

```
✅ Blocks: refactor/* → main (without authorization)
✅ Allows: docs-only changes, hotfixes
✅ Requires: Approvals on all PRs to main
```

### 4. **Sync Docs** (`sync-main.yml`)

Keeps documentation up-to-date:

```
✅ Triggers: On push to main (docs changes)
✅ Action: Merges docs to refactor/stable-ui-and-tests
✅ Strategy: Accept main's docs (no conflicts)
```

---

## Status Badges

Add to README.md to show CI status:

```markdown
![Python Tests](https://github.com/Cuevaza/PecunatorCore/workflows/Python%20Tests/badge.svg?branch=refactor/stable-ui-and-tests)
![Flutter Tests](https://github.com/Cuevaza/PecunatorCore/workflows/Flutter%20Tests/badge.svg?branch=refactor/stable-ui-and-tests)
![Main Branch Protection](https://github.com/Cuevaza/PecunatorCore/workflows/Protect%20Main/badge.svg?branch=main)
```

---

## Multi-Office Workflow Example

### Setup (Each Office)

```bash
# Office 1 & 2 (both)
git clone https://github.com/Cuevaza/PecunatorCore.git
cd PecunatorCore

# Switch to refactor branch
git checkout refactor/stable-ui-and-tests
git pull
```

### Daily Workflow

```bash
# Morning: Sync with latest
git fetch origin
git pull origin refactor/stable-ui-and-tests

# Work on feature
git checkout -b feature/webocket-support
# ... make changes ...
git commit -m "feat: add websocket real-time updates"
git push origin feature/websocket-support

# Create PR to refactor branch
gh pr create --base refactor/stable-ui-and-tests \
             --head feature/websocket-support

# Other office approves & merges
gh pr merge --merge

# Back to refactor branch with latest
git checkout refactor/stable-ui-and-tests
git pull
```

---

## Safety Guarantees

### ✅ Main is Always Stable

- ✅ Only code with full approval merges to main
- ✅ All tests pass before merge
- ✅ GitHub Actions enforce quality gates
- ✅ Refactor branch never auto-merges to main

### ✅ Refactor Branch is Always Active

- ✅ Multiple contributors can work simultaneously
- ✅ Automatic testing on every push
- ✅ Docs stay in sync with main
- ✅ Easy to pull improvements from main

### ✅ No Accidental Merges

- ✅ Direct push to main is blocked
- ✅ Pull requests from refactor/* to main are blocked (protected)
- ✅ Manual authorization required
- ✅ Formal PR + approval process

---

## Common Tasks

### Task 1: Create a new feature branch

```bash
git checkout refactor/stable-ui-and-tests
git pull
git checkout -b feature/new-feature-name
# ... work ...
git push -u origin feature/new-feature-name
```

### Task 2: Merge a feature into refactor branch

```bash
# Create PR on GitHub
gh pr create --base refactor/stable-ui-and-tests --head feature/name

# Review & merge
gh pr review <PR_ID>
gh pr merge <PR_ID> --merge
```

### Task 3: Check CI status

```bash
# View workflow runs
gh run list --branch refactor/stable-ui-and-tests -L 10

# View specific workflow
gh run view <RUN_ID> --log
```

### Task 4: Sync docs from main

```bash
git fetch origin
git merge origin/main -- docs/ README.md
git push origin refactor/stable-ui-and-tests
```

### Task 5: Pull improvement from main

```bash
# Fetch main
git fetch origin

# Merge specific file(s)
git checkout --theirs runtime/core/security_util.py
git add runtime/core/security_util.py
git commit -m "chore: pull security improvement from main"
git push origin refactor/stable-ui-and-tests

# Or merge entire folder
git merge origin/main -- runtime/
```

### Task 6: Request merge to main

```bash
# Create formal PR
gh pr create --base main --head refactor/stable-ui-and-tests \
  --title "Merge refactoring: modular UI and tests" \
  --body "Complete refactoring implementation with:
- Comprehensive testing (43 tests)
- Modular architecture (8 modules)
- Riverpod state management
- Error handling & retry logic
- Full documentation

See: https://github.com/Cuevaza/PecunatorCore/blob/main/docs/architecture-next.md
"

# Share PR link with approver
echo "https://github.com/Cuevaza/PecunatorCore/pull/<PR_ID>"
```

---

## Troubleshooting

### Issue: Merge conflict when syncing docs

```bash
# Accept main's docs
git merge origin/main -X theirs -- docs/
git add docs/
git commit -m "chore: sync docs from main"
git push origin refactor/stable-ui-and-tests
```

### Issue: GitHub Actions failing

```bash
# Check logs
gh run list --branch refactor/stable-ui-and-tests
gh run view <RUN_ID> --log

# Fix locally
pytest runtime/tests/ -v  # Python
flutter test test/ -v     # Flutter

# Push fix
git add .
git commit -m "fix: resolve test failures"
git push origin refactor/stable-ui-and-tests
```

### Issue: Can't merge to main

```bash
# Check protection
gh api repos/Cuevaza/PecunatorCore/branches/main --jq '.protection'

# If blocked: Wait for authorization
# Check: Is authorization explicit from owner?

# Approved? Create formal PR instead of force merge
gh pr create --base main --head refactor/stable-ui-and-tests
```

---

## Status Checks

View current branch status:

```bash
# Check latest tests
gh run list --branch refactor/stable-ui-and-tests --limit 5

# Output:
# ID       TITLE                              STATUS
# 12345    Python Tests (Dorothy Bot)         ✅ completed
# 12344    Flutter Tests (Refactored UI)      ✅ completed
# 12343    Protect Main (No Direct Merges)    ✅ completed
```

---

## Summary

| Aspect | Policy |
|--------|--------|
| **Development** | ✅ Full freedom on `refactor/stable-ui-and-tests` |
| **Testing** | ✅ Automatic on every push (Python + Flutter) |
| **Docs** | ✅ Auto-synced from main |
| **Improvements** | ✅ Can pull from main as needed |
| **Merge to main** | ❌ Requires explicit authorization + formal PR |
| **Protection** | ✅ GitHub Actions blocks direct merges |

---

**This setup enables parallel development across offices while maintaining production stability.** 🚀
