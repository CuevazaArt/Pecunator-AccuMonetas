/// Centralized application configuration.
library;

class AppConfig {
  // Engine API
  static const String engineDefaultHost = '127.0.0.1';
  static const int engineDefaultPort = 8000;

  // Network
  static const Duration networkTimeout = Duration(seconds: 10);
  static const int maxNetworkRetries = 3;
  static const Duration retryDelay = Duration(milliseconds: 500);

  // UI Refresh
  static const Duration backgroundRefreshInterval = Duration(seconds: 4);
  static const Duration clockUpdateInterval = Duration(seconds: 1);

  // Logging
  static const int maxLogLines = 120;
  static const int maxStoredLogs = 1000;

  // Bot defaults
  static const String defaultBotTag = 'Dorothy';
  static const String defaultSymbol = 'XRPUSDT';
  static const int defaultLoopInterval = 75;

  // WebSocket
  static const Duration wsReconnectDelay = Duration(seconds: 3);
  static const int wsMaxReconnectAttempts = 50;  // ~2.5 min then reset
  static const String defaultQuoteQty = '8';
  static const String defaultProfit = '0.05';
  static const String defaultDrop = '0.004';
  static const int defaultQtyDecimals = 8;
  static const int defaultPriceDecimals = 4;

  // UI
  static const int minDialogWidth = 520;
  static const int maxDialogWidth = 860;
  static const int configHistoryMaxItems = 50;
  static const int decimalDisplayPlaces = 12;

  /// Build engine URL from host and port.
  static String buildEngineUrl({
    String host = engineDefaultHost,
    int port = engineDefaultPort,
  }) {
    return 'http://$host:$port';
  }

  /// Build WebSocket URL from host and port.
  static String buildWsUrl({
    String host = engineDefaultHost,
    int port = engineDefaultPort,
  }) {
    return 'ws://$host:$port/ws/telemetry';
  }
}
