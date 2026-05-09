/// Application preferences persistence layer using SharedPreferences.
library;

import 'package:shared_preferences/shared_preferences.dart';

class _PrefsKeys {
  static const String darkMode = 'app.darkMode';
  static const String engineHost = 'app.engineHost';
  static const String enginePort = 'app.enginePort';
  static const String lastBotTag = 'app.lastBotTag';
  static const String lastSymbol = 'app.lastSymbol';
  static const String lastBaseAsset = 'app.lastBaseAsset';
  static const String configHistory = 'app.configHistory';
  static const String expandedBots = 'app.expandedBots';
  static const String lastScrollPos = 'app.lastScrollPos';
  static const String apiKey = 'app.apiKey';
  static const String apiSecret = 'app.apiSecret';
}

class AppPreferences {
  static late final SharedPreferences _prefs;

  static Future<void> init() async {
    _prefs = await SharedPreferences.getInstance();
  }

  // Theme
  static bool get darkMode => _prefs.getBool(_PrefsKeys.darkMode) ?? true;

  static Future<void> setDarkMode(bool value) =>
      _prefs.setBool(_PrefsKeys.darkMode, value);

  // Engine connection
  static String get engineHost =>
      _prefs.getString(_PrefsKeys.engineHost) ?? '127.0.0.1';

  static Future<void> setEngineHost(String value) =>
      _prefs.setString(_PrefsKeys.engineHost, value);

  static int get enginePort => _prefs.getInt(_PrefsKeys.enginePort) ?? 8000;

  static Future<void> setEnginePort(int value) =>
      _prefs.setInt(_PrefsKeys.enginePort, value);

  // Bot config defaults
  static String get lastBotTag =>
      _prefs.getString(_PrefsKeys.lastBotTag) ?? 'Dorothy';

  static Future<void> setLastBotTag(String value) =>
      _prefs.setString(_PrefsKeys.lastBotTag, value);

  static String get lastSymbol =>
      _prefs.getString(_PrefsKeys.lastSymbol) ?? 'XRPUSDT';

  static Future<void> setLastSymbol(String value) =>
      _prefs.setString(_PrefsKeys.lastSymbol, value);

  static String get lastBaseAsset =>
      _prefs.getString(_PrefsKeys.lastBaseAsset) ?? 'USDT';

  static Future<void> setLastBaseAsset(String value) =>
      _prefs.setString(_PrefsKeys.lastBaseAsset, value);

  // Config history
  static List<String> get configHistory =>
      _prefs.getStringList(_PrefsKeys.configHistory) ?? [];

  static Future<void> addConfigHistory(String config) async {
    final history = configHistory;
    history.insert(0, config);
    // Keep only last 50
    if (history.length > 50) {
      history.removeRange(50, history.length);
    }
    await _prefs.setStringList(_PrefsKeys.configHistory, history);
  }

  static Future<void> clearConfigHistory() =>
      _prefs.remove(_PrefsKeys.configHistory);

  // Expanded bots (for UI state)
  static Set<String> get expandedBotIds =>
      Set<String>.from(_prefs.getStringList(_PrefsKeys.expandedBots) ?? []);

  static Future<void> setExpandedBotIds(Set<String> ids) =>
      _prefs.setStringList(_PrefsKeys.expandedBots, ids.toList());

  // Last scroll positions
  static int get lastLogScrollPosition =>
      _prefs.getInt(_PrefsKeys.lastScrollPos) ?? 0;

  static Future<void> setLastLogScrollPosition(int position) =>
      _prefs.setInt(_PrefsKeys.lastScrollPos, position);

  // Credentials Persistence
  static String get apiKey => _prefs.getString(_PrefsKeys.apiKey) ?? '';
  static Future<void> setApiKey(String value) =>
      _prefs.setString(_PrefsKeys.apiKey, value);

  static String get apiSecret => _prefs.getString(_PrefsKeys.apiSecret) ?? '';
  static Future<void> setApiSecret(String value) =>
      _prefs.setString(_PrefsKeys.apiSecret, value);

  // Staged Symbol Presets Persistence
  static String get savedPresetsJson => _prefs.getString('app.savedPresets') ?? '{}';
  static Future<void> setSavedPresetsJson(String json) =>
      _prefs.setString('app.savedPresets', json);

  // Clear all
  static Future<void> clearAll() => _prefs.clear();
}
