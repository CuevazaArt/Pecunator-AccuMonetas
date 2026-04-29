/// Application-level state providers using Riverpod.

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../api_client.dart';
import '../config/app_config.dart';
import '../services/exceptions.dart';
import '../services/preferences.dart';

// Theme
final darkModeProvider = StateProvider<bool>((ref) => AppPreferences.darkMode);

// Engine configuration
final engineHostProvider = StateProvider<String>((ref) => AppPreferences.engineHost);
final enginePortProvider = StateProvider<int>((ref) => AppPreferences.enginePort);

final engineBaseUrlProvider = Provider<String>((ref) {
  final host = ref.watch(engineHostProvider);
  final port = ref.watch(enginePortProvider);
  return AppConfig.buildEngineUrl(host: host, port: port);
});

final engineApiProvider = Provider<EngineApi>((ref) {
  final baseUrl = ref.watch(engineBaseUrlProvider);
  return EngineApi(baseUrl);
});

// Hub bots state
final hubBotsProvider = FutureProvider<Map<String, dynamic>>((ref) async {
  final api = ref.watch(engineApiProvider);
  return api.hubBots();
});

// Active credential state
final activeCredentialProvider =
    FutureProvider<Map<String, dynamic>>((ref) async {
  final api = ref.watch(engineApiProvider);
  return api.activeCredential();
});

// Vault credentials state
final vaultCredentialsProvider =
    FutureProvider<Map<String, dynamic>>((ref) async {
  final api = ref.watch(engineApiProvider);
  return api.vaultCredentials();
});

// Gateway snapshot state
final gatewaySnapshotProvider =
    FutureProvider<Map<String, dynamic>>((ref) async {
  final api = ref.watch(engineApiProvider);
  try {
    return await api.gatewaySnapshot();
  } catch (_) {
    // Return default offline state if gateway unavailable
    return {'gateway_running': false, 'ws_connected': false};
  }
});

// Expanded bots (UI state)
final expandedBotsProvider = StateProvider<Set<String>>((ref) {
  return AppPreferences.expandedBotIds;
});

// Bot logs by bot ID
final botLogsProvider =
    FutureProvider.family<Map<String, dynamic>, String>((ref, botId) async {
  final api = ref.watch(engineApiProvider);
  return api.hubLogs(botId, limit: AppConfig.maxLogLines);
});

// Error handling utility
final errorMessageProvider = StateProvider<String?>((ref) => null);

/// Helper to show errors with proper classification
extension ErrorHandling on WidgetRef {
  void handleError(Object error, StackTrace? stack) {
    String message;

    if (error is NetworkException) {
      message = error.message;
    } else if (error is ApiException) {
      message = error.message;
    } else if (error is ValidationException) {
      message = error.message;
    } else if (error is AuthException) {
      message = error.message;
    } else {
      message = 'Error inesperado: ${error.toString()}';
    }

    read(errorMessageProvider.notifier).state = message;
  }

  void clearError() {
    read(errorMessageProvider.notifier).state = null;
  }
}
