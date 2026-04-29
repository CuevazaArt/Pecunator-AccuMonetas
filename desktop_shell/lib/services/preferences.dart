/// Application preferences persistence layer using SharedPreferences.

import 'package:shared_preferences/shared_preferences.dart';

class AppPreferences {
  static late final SharedPreferences _prefs;

  static Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
  }

  // Theme
  static bool get darkMode => _prefs.getBool(_Keys.darkMode) ?? true;

  static Future<void> setDarkMode(bool value) =>
      _prefs.setBool(_Keys.darkMode, value);

  // Engine connection
  static String get engineHost =>
      _prefs.getString(_Keys.engineHost) ?? '127.0.0.1';

  static Future<void> setEngineHost(String value) =>
      _prefs.setString(_Keys.engineHost, value);

  static int get enginePort => _prefs.getInt(_Keys.enginePort) ?? 8765;

  static Future<void> setEnginePort(int value) =>
      _prefs.setInt(_Keys.enginePort, value);

  // Bot config defaults
  static String get lastBotTag =>
      _prefs.getString(_Keys.lastBotTag) ?? 'Dorothy';

  static Future<void> setLastBotTag(String value) =>
      _prefs.setString(_Keys.lastBotTag, value);

  static String get lastSymbol =>
      _prefs.getString(_Keys.lastSymbol) ?? 'XRPUSDT';

  static Future<void> setLastSymbol(String value) =>
      _prefs.setString(_Keys.lastSymbol, value);

  static String get lastBaseAsset =>
      _prefs.getString(_Keys.lastBaseAsset) ?? 'USDT';

  static Future<void> setLastBaseAsset(String value) =>
      _prefs.setString(_Keys.lastBaseAsset, value);

  // Config history
  static List<String> get configHistory =>
      _prefs.getStringList(_Keys.configHistory) ?? [];

  static Future<void> addConfigHistory(String config) async {
    final history = configHistory;
    history.insert(0, config);
    // Keep only last 50
    if (history.length > 50) {
      history.removeRange(50, history.length);
    }
    await _prefs.setStringList(_Keys.configHistory, history);
  }

  static Future<void> clearConfigHistory() =>
      _prefs.remove(_Keys.configHistory);

  // Expanded bots (for UI state)
  static Set<String> get expandedBotIds =>
      Set<String>.from(_prefs.getStringList(_Keys.expandedBots) ?? []);

  static Future<void> setExpandedBotIds(Set<String> ids) =>
      _prefs.setStringList(_Keys.expandedBots, ids.toList());

  // Last scroll positions
  static int get lastLogScrollPosition =>
      _prefs.getInt(_Keys.lastScrollPos) ?? 0;

  static Future<void> setLastLogScrollPosition(int position) =>
      _prefs.setInt(_Keys.lastScrollPos, position);

  // Clear all
  static Future<void> clearAll() => _prefs.clear();

  /// Internal key constants to prevent typos.
  class _Keys {
    static const String darkMode = 'app.darkMode';
    static const String engineHost = 'app.engineHost';
    static const String enginePort = 'app.enginePort';
    static const String lastBotTag = 'app.lastBotTag';
    static const String lastSymbol = 'app.lastSymbol';
    static const String lastBaseAsset = 'app.lastBaseAsset';
    static const String configHistory = 'app.configHistory';
    static const String expandedBots = 'app.expandedBots';
    static const String lastScrollPos = 'app.lastScrollPos';
  }
}
