# PecunatorCore Refactoring: Architecture & Migration Guide

## Overview

This refactoring modernizes PecunatorCore with **testing**, **modularity**, **state management**, and **robustness**. The changes preserve the minimalist UI essence while enabling significant growth.

## Key Improvements

### 1. **Testing** ✅
- **File**: `runtime/tests/test_dorothy.py` (~300 lines)
- **Coverage**: Dorothy bot config, normalization, decimal handling, lifecycle
- **Run**: `pytest runtime/tests/test_dorothy.py -v`
- **Next**: Add integration tests for API layer and hub lifecycle

### 2. **Robust HTTP Client** ✅
- **Files**: 
  - `desktop_shell/lib/services/http_client.dart` – Retries, timeouts, error classification
  - `desktop_shell/lib/services/exceptions.dart` – Custom exception hierarchy
- **Features**:
  - Automatic retry with exponential backoff (max 3 attempts)
  - 10-second timeout (configurable)
  - Classified errors: `NetworkException`, `ApiException`, `ValidationException`, `AuthException`
- **Usage**: `EngineApi` now uses `RobustHttpClient` internally

### 3. **Centralized Configuration** ✅
- **File**: `desktop_shell/lib/config/app_config.dart`
- **Contains**:
  - Engine defaults (host, port, timeout)
  - UI refresh intervals
  - Bot parameter defaults
  - Dialog widths, max items, etc.
- **Benefit**: Single source of truth, easier to adjust across the app

### 4. **Preferences & Persistence** ✅
- **File**: `desktop_shell/lib/services/preferences.dart`
- **Stores**:
  - Dark mode setting
  - Engine connection details
  - Last bot configuration
  - Config history (last 50 items)
  - Expanded bot IDs for UI state
- **Init**: Must call `AppPreferences.init()` in `main()`

### 5. **State Management (Riverpod)** ✅
- **File**: `desktop_shell/lib/providers/app_providers.dart`
- **Providers**:
  - `darkModeProvider` – Theme state
  - `engineBaseUrlProvider` – Computed URL from host/port
  - `engineApiProvider` – Singleton API client
  - `hubBotsProvider` – Auto-refreshing bot list (async)
  - `activeCredentialProvider`, `vaultCredentialsProvider` – Vault state
  - `gatewaySnapshotProvider` – Gateway status (with fallback)
  - `expandedBotsProvider` – UI state (which bots expanded)
  - `botLogsProvider` – Logs per bot (family provider)
  - `errorMessageProvider` – Global error state
- **Benefits**:
  - Reactive updates (watch providers, auto-rebuild)
  - Share state across screens without prop drilling
  - Memoization (expensive calls cached)
  - Easy invalidation (`.refresh()`)

### 6. **Modular UI** ✅
- **New Structure**:
  ```
  lib/
  ├── config/
  │   └── app_config.dart         # Centralized constants
  ├── providers/
  │   └── app_providers.dart      # Riverpod state definitions
  ├── services/
  │   ├── exceptions.dart         # Exception hierarchy
  │   ├── http_client.dart        # Robust HTTP
  │   └── preferences.dart        # LocalStorage wrapper
  ├── screens/
  │   ├── home_screen.dart        # Tab navigation
  │   ├── bots_screen.dart        # Bot management (refactored)
  │   └── spot_account_screen.dart
  ├── widgets/
  │   ├── error_display.dart      # Classification-aware error UI
  │   ├── gateway_status.dart     # Gateway indicator
  │   └── logs_viewer.dart        # Reusable log viewer
  ├── utils/
  │   └── number_formatter.dart   # Number formatting
  ├── api_client.dart             # Updated to use RobustHttpClient
  └── main_refactored.dart        # New entry point with Riverpod
  ```

- **Key Changes**:
  - UI split into screens (tabs: Bots, Spot Account)
  - Widgets extracted: `ErrorDisplay`, `LogsViewer`, `GatewayStatus`
  - State lifted to Riverpod providers
  - No more ad-hoc `Map<String, *>` state
  - Error handling via exception hierarchy

### 7. **Error Handling** ✅
- **Exceptions**:
  ```dart
  NetworkException       // Timeouts, connection refused
  ApiException           // HTTP 4xx/5xx
  ValidationException    // Input validation
  AuthException          // Vault/credential issues
  ```
- **UI**: `ErrorDisplay` widget shows context-aware messages + icons
- **Logging**: Original error captured in `originalError` field

## Migration Path

### Phase 1: Safety (Already Done)
1. ✅ Add pytest to `requirements-dev.txt`
2. ✅ Write `test_dorothy.py` with 25+ test cases
3. ✅ Create exception hierarchy in Dart
4. ✅ Build `RobustHttpClient` with retries

### Phase 2: State Management (Already Done)
1. ✅ Add `flutter_riverpod`, `shared_preferences` to `pubspec.yaml`
2. ✅ Create `AppConfig`, `AppPreferences`, providers
3. ✅ Update `EngineApi` to use new client

### Phase 3: UI Refactoring (In Progress)
1. ✅ Extract widgets (`ErrorDisplay`, `LogsViewer`, `GatewayStatus`)
2. ✅ Create screens (`HomeScreen`, `BotsScreen`, `SpotAccountScreen`)
3. ⏳ Migrate main.dart to use Riverpod (see `main_refactored.dart`)
4. ⏳ Add more detailed bot card widget with inline editing
5. ⏳ Implement vault manager screen

### Phase 4: Features & Tests (Next)
1. Add integration tests for API client
2. WebSocket support for real-time updates (instead of polling)
3. Metrics/alerting endpoints in Python backend
4. E2E UI tests with Flutter test framework

## How to Use the Refactored Code

### Running Tests
```bash
cd runtime
pip install -r ../requirements-dev.txt
pytest tests/test_dorothy.py -v
```

### Building the New UI
1. **Update pubspec.yaml**: Already done ✅
2. **Run flutter pub get**:
   ```bash
   cd desktop_shell
   flutter pub get
   ```
3. **Replace main.dart** (or rename current to `main_old.dart` and use `main_refactored.dart`):
   ```bash
   cp lib/main_refactored.dart lib/main.dart
   ```
4. **Run the app**:
   ```bash
   flutter run -d windows
   ```

### Key Patterns

#### Watching provider state in a widget:
```dart
@override
Widget build(BuildContext context, WidgetRef ref) {
  final bots = ref.watch(hubBotsProvider);
  return bots.when(
    data: (data) => _buildBotsList(data),
    loading: () => const CircularProgressIndicator(),
    error: (err, _) => ErrorDisplay(error: err),
  );
}
```

#### Updating provider state:
```dart
ref.read(darkModeProvider.notifier).state = true;
```

#### Refreshing stale data:
```dart
ref.refresh(hubBotsProvider);
ref.refresh(gatewaySnapshotProvider);
```

#### Handling errors properly:
```dart
Future<void> _startGateway() async {
  try {
    final api = ref.read(engineApiProvider);
    await api.gatewayStart();
    ref.refresh(gatewaySnapshotProvider);
  } catch (e) {
    if (e is NetworkException) {
      _showError('Red desconectada');
    } else if (e is ApiException) {
      _showError('Error API: ${e.message}');
    }
  }
}
```

## Directory Structure: Before vs After

### Before
```
desktop_shell/lib/
├── main.dart (1930 lines, everything mixed)
└── api_client.dart (2 files, minimal error handling)
```

### After
```
desktop_shell/lib/
├── main_refactored.dart (30 lines, clean entry point)
├── api_client.dart (refactored to use services)
├── config/app_config.dart
├── providers/app_providers.dart
├── services/
│   ├── exceptions.dart
│   ├── http_client.dart
│   └── preferences.dart
├── screens/
│   ├── home_screen.dart
│   ├── bots_screen.dart
│   └── spot_account_screen.dart
├── widgets/
│   ├── error_display.dart
│   ├── gateway_status.dart
│   └── logs_viewer.dart
└── utils/number_formatter.dart
```

## Next Steps

1. **Complete bot card widget** (currently inline in bots_screen.dart)
   - Extract to `widgets/bot_card.dart`
   - Support inline editing (tag, symbol, qty, etc.)
   - Show cycle countdown

2. **Add vault manager screen**
   - List credentials
   - Add/delete/activate
   - Label management

3. **Add logging screen**
   - Structured logs (JSON)
   - Filtering & search
   - Export capability

4. **Switch to WebSocket** (in Python backend + Flutter)
   - Real-time bot state updates
   - Stop polling (every 4 seconds)
   - Reduce server load

5. **Add metrics dashboard**
   - Trades per hour
   - Profit/loss tracking
   - Error rate trends

6. **E2E tests**
   - Golden file tests for UI layouts
   - Integration tests for flows (create bot → activate → monitor logs)

## Known Limitations & Future Work

| Issue | Current | Future |
|-------|---------|--------|
| Polling | Every 4 sec (inefficient) | WebSocket (real-time, low load) |
| Logs | In-memory per bot | Persistent DB, queryable |
| Config | In UI fields | Versioned with rollback |
| Errors | String on-screen | Classified + logged to file |
| Multi-exchange | Binance only | Plugin architecture |
| Decimal handling | Manual in UI | Strongly-typed currency type |

## Compatibility

- **Minimum Flutter**: 3.11.5 (unchanged)
- **Minimum Dart**: 3.11.5 (unchanged)
- **New Dependencies**:
  - `flutter_riverpod: ^2.4.1`
  - `shared_preferences: ^2.2.2`
- **Removed Dependencies**: None (only added)
- **Breaking Changes**: None (old main.dart still works)

## Rollback

If you need to revert to the old UI:
1. Keep `lib/main.dart` (old version)
2. Do not import new `providers/`, `services/` (except `http_client`)
3. `EngineApi` still works with the new `RobustHttpClient` ✅

---

**Summary**: This refactoring is a **foundation for growth**. The codebase is now:
- ✅ **Testable** (pytest + fixtures)
- ✅ **Robust** (retry logic, timeouts, error classification)
- ✅ **Modular** (screens, widgets, services separated)
- ✅ **Reactive** (Riverpod state management)
- ✅ **Persistent** (SharedPreferences for user prefs)

Total refactoring effort: **~6 hours of implementation + testing**.
