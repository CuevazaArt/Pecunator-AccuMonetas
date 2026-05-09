import 'dart:developer' as dev;

/// Lightweight debug logger for the Pecunator desktop shell.
///
/// In debug mode, logs errors to the console via dart:developer.
/// In release mode, all calls are no-ops (tree-shaken away).
///
/// Usage:
///   import '../utils/plog.dart';
///   } catch (e) { PLog.warn('MiniWeightChart', 'refresh failed', e); }
abstract final class PLog {
  /// Log an informational message.
  static void info(String source, String message) {
    assert(() {
      dev.log('[$source] $message', level: 800);
      return true;
    }());
  }

  /// Log a warning (non-fatal error, swallowed exception).
  static void warn(String source, String message, [Object? error]) {
    assert(() {
      dev.log('[$source] ⚠ $message${error != null ? ': $error' : ''}', level: 900);
      return true;
    }());
  }

  /// Log an error (should be investigated).
  static void error(String source, String message, Object error) {
    assert(() {
      dev.log('[$source] ✖ $message: $error', level: 1000);
      return true;
    }());
  }
}
