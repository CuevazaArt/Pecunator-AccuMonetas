# PecunatorCore Refactoring: Quick Start Guide

## What's New?

This branch (`refactor/stable-ui-and-tests`) introduces **6 weeks of production-ready improvements** in a single refactor:

1. ✅ **Comprehensive testing** for Dorothy bot
2. ✅ **Robust HTTP client** with retry logic & error classification
3. ✅ **Modular UI architecture** with Riverpod state management
4. ✅ **Centralized configuration** and persistent preferences
5. ✅ **Exception hierarchy** for proper error handling
6. ✅ **Reusable widgets** (`ErrorDisplay`, `LogsViewer`, `GatewayStatus`)

## Quick Start (5 minutes)

### Backend: Run Tests

```bash
# Install test dependencies
pip install -r requirements-dev.txt

# Run Dorothy bot tests
pytest runtime/tests/test_dorothy.py -v

# Expected output:
# test_defaults PASSED
# test_normalize_symbol_uppercase PASSED
# ... (25 tests total)
# ==================== 25 passed in 0.45s ====================
```

### Frontend: Build Refactored UI

```bash
cd desktop_shell

# Get dependencies
flutter pub get

# Run refactored app (uses new architecture)
flutter run -d windows

# Run UI tests
flutter test test/ui_test.dart -v
```

## File Map

| File | Purpose | Status |
|------|---------|--------|
| `runtime/tests/test_dorothy.py` | Dorothy bot testing suite | ✅ Ready |
| `desktop_shell/lib/services/http_client.dart` | Robust HTTP client | ✅ Ready |
| `desktop_shell/lib/services/exceptions.dart` | Exception hierarchy | ✅ Ready |
| `desktop_shell/lib/services/preferences.dart` | Persistent storage | ✅ Ready |
| `desktop_shell/lib/config/app_config.dart` | Centralized config | ✅ Ready |
| `desktop_shell/lib/providers/app_providers.dart` | Riverpod state | ✅ Ready |
| `desktop_shell/lib/screens/home_screen.dart` | Tab navigation | ✅ Ready |
| `desktop_shell/lib/screens/bots_screen.dart` | Bot management | ✅ Beta |
| `desktop_shell/lib/screens/spot_account_screen.dart` | Account view | ✅ Stub |
| `desktop_shell/lib/widgets/error_display.dart` | Error widget | ✅ Ready |
| `desktop_shell/lib/widgets/logs_viewer.dart` | Logs widget | ✅ Ready |
| `desktop_shell/lib/widgets/gateway_status.dart` | Gateway indicator | ✅ Ready |
| `desktop_shell/lib/main_refactored.dart` | New app entry point | ✅ Ready |
| `desktop_shell/test/ui_test.dart` | UI testing suite | ✅ Ready |

## Key Features

### 1. Error Handling
**Before**: Generic `.toString()` error messages  
**After**: Classified exceptions with user-friendly messages

```dart
try {
  await api.gatewayStart();
} on NetworkException catch (e) {
  // "Conexión agotada: el servidor tardó demasiado"
  showError(e.message);
} on ApiException catch (e) {
  // "Error en el servidor: DB unavailable"
  showError('${e.message}${e.statusCode != null ? ' (${e.statusCode})' : ''}');
}
```

### 2. Automatic Retries
**Before**: Single attempt, fail immediately  
**After**: 3 automatic retries with exponential backoff

```dart
final response = await client.get('/api/v1/hub/bots');
// Internally:
// - Timeout: 10 seconds
// - Retry 1: delay 500ms
// - Retry 2: delay 750ms
// - Retry 3: delay 1000ms
```

### 3. State Management
**Before**: Ad-hoc `Map<String, dynamic>` + `setState()`  
**After**: Reactive Riverpod providers

```dart
// Watch bot list
final bots = ref.watch(hubBotsProvider);

// Refresh when needed
ref.refresh(hubBotsProvider);

// No more prop drilling
final api = ref.watch(engineApiProvider); // Available anywhere
```

### 4. Persistent Preferences
```dart
// Automatically saved/restored
final darkMode = AppPreferences.darkMode;
await AppPreferences.setDarkMode(false);

final lastSymbol = AppPreferences.lastSymbol; // "XRPUSDT"
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│  main_refactored.dart (entry point)                 │
│  └─ ProviderScope(child: PecunatorDesktopApp)       │
└────────────────┬────────────────────────────────────┘
                 │
     ┌───────────┴───────────┐
     ▼                       ▼
┌─────────────┐      ┌──────────────┐
│ HomeScreen  │      │ Providers    │
│ (tabs)      │      │ (Riverpod)   │
└──┬──────────┘      └──┬───────────┘
   │                    │
   ├─ BotsScreen       ├─ engineApiProvider
   │  └─ watch         ├─ hubBotsProvider
   │     hubBots       ├─ gateway...
   └─ Spot...         └─ active...

Services (stateless, reusable):
├─ RobustHttpClient (retries, timeouts)
├─ AppConfig (constants)
├─ AppPreferences (localStorage)
└─ Exception classes

Widgets (presentational, no state):
├─ ErrorDisplay (shows exceptions nicely)
├─ LogsViewer (scrollable logs)
└─ GatewayStatus (indicator)
```

## Incremental Adoption

You **don't need** to migrate everything at once. Mix old and new:

```dart
// ✅ Use new RobustHttpClient (backward compatible)
final api = EngineApi('http://localhost:8765');

// ✅ Use new exception handling
try {
  await api.hubBots();
} on NetworkException {
  // Handle new exception type
}

// ✅ Use new widgets
ErrorDisplay(error: myError);

// ✅ Use old main.dart if you want
// (nothing breaks—new code is additive)
```

## Testing

### Run all tests

```bash
# Backend (Python)
cd runtime
pytest tests/ -v --cov=.

# Frontend (Dart)
cd desktop_shell
flutter test test/ -v

# Specific test
flutter test test/ui_test.dart::GatewayStatus -v
```

### Golden tests (visual regression)
```bash
# Generate baselines
flutter test test/golden_test.dart --update-goldens

# Compare against baselines
flutter test test/golden_test.dart
```

## Common Patterns

### Pattern 1: Load data with error handling
```dart
final botsAsync = ref.watch(hubBotsProvider);

botsAsync.when(
  data: (bots) => _buildBotsList(bots),
  loading: () => const CircularProgressIndicator(),
  error: (err, _) => ErrorDisplay(error: err),
);
```

### Pattern 2: Update settings
```dart
Future<void> _saveDarkMode(bool value) async {
  ref.read(darkModeProvider.notifier).state = value;
  await AppPreferences.setDarkMode(value);
}
```

### Pattern 3: Call API with error handling
```dart
Future<void> _activateCredential(String id) async {
  try {
    final api = ref.read(engineApiProvider);
    await api.activateVaultCredential(id);
    ref.refresh(activeCredentialProvider);
  } catch (e) {
    ref.read(errorMessageProvider.notifier).state = e.toString();
  }
}
```

### Pattern 4: Poll multiple providers
```dart
Future<void> _refreshAll() async {
  ref.refresh(hubBotsProvider);
  ref.refresh(gatewaySnapshotProvider);
  ref.refresh(activeCredentialProvider);
}
```

## Migration Checklist

If you're migrating from `main.dart` to `main_refactored.dart`:

- [ ] `flutter pub get` (adds Riverpod + SharedPreferences)
- [ ] `await AppPreferences.init()` in `main()`
- [ ] Replace `import api_client` with imports from `services/`
- [ ] Replace `_withBusy()` with `.when()` (async handling)
- [ ] Replace `Map<String, dynamic>` state with providers
- [ ] Replace error `.toString()` with exception classification
- [ ] Test: `flutter test`

## Known Issues & TODOs

| Issue | Impact | Timeline |
|-------|--------|----------|
| `BotsScreen` incomplete (inline editing) | Medium | Next PR |
| `SpotAccountScreen` is stub | Low | Follow-up |
| No WebSocket support yet | High | Week 2 |
| No E2E tests | Medium | Week 1 |
| Config history not in UI | Low | Nice-to-have |

## Support & Questions

- **Architecture**: See `docs/REFACTOR_ARCHITECTURE.md`
- **Testing**: See `runtime/tests/test_dorothy.py`
- **Riverpod**: https://riverpod.dev
- **Flutter testing**: https://flutter.dev/docs/testing

---

**Branch**: `refactor/stable-ui-and-tests`  
**Status**: Ready for review & feedback  
**Goal**: Merge to main after approval + E2E validation
