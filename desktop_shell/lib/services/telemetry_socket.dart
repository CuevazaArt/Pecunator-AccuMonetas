import 'dart:async';
import 'dart:convert';
import 'dart:developer' as dev;

import 'package:web_socket_channel/web_socket_channel.dart';

import '../config/app_config.dart';

/// Central WebSocket service for receiving push telemetry.
///
/// Replaces the previous polling architecture (Timer.periodic → REST GET)
/// with a single persistent WebSocket connection that receives all telemetry,
/// fuse events, and alerts in real-time from the Python backend.
///
/// Usage:
/// ```dart
/// final service = TelemetrySocketService();
/// service.stream.listen((event) {
///   // event is a decoded Map with type, ts_utc, seq, payload
///   if (event['type'] == 'TELEMETRY_TICK') { ... }
/// });
/// service.connect();
/// ```
class TelemetrySocketService {
  final String wsUrl;
  final Duration reconnectDelay;
  final int maxReconnectAttempts;

  WebSocketChannel? _channel;
  StreamSubscription? _subscription;
  Timer? _reconnectTimer;
  int _reconnectCount = 0;
  bool _disposed = false;
  bool _connected = false;

  // Stream controller for broadcasting events to all listeners
  final _controller = StreamController<Map<String, dynamic>>.broadcast();

  // Connection state stream
  final _connectionController = StreamController<bool>.broadcast();

  TelemetrySocketService({
    String? wsUrl,
    Duration? reconnectDelay,
    int? maxReconnectAttempts,
  })  : wsUrl = wsUrl ?? AppConfig.buildWsUrl(),
        reconnectDelay = reconnectDelay ?? AppConfig.wsReconnectDelay,
        maxReconnectAttempts =
            maxReconnectAttempts ?? AppConfig.wsMaxReconnectAttempts;

  /// Stream of decoded telemetry events.
  Stream<Map<String, dynamic>> get stream => _controller.stream;

  /// Stream of connection state changes.
  Stream<bool> get connectionStream => _connectionController.stream;

  /// Whether the WebSocket is currently connected.
  bool get isConnected => _connected;

  /// Connect to the WebSocket endpoint.
  void connect() {
    if (_disposed) return;
    _doConnect();
  }

  void _doConnect() {
    if (_disposed) return;

    try {
      final uri = Uri.parse(wsUrl);
      _channel = WebSocketChannel.connect(uri);

      _subscription = _channel!.stream.listen(
        _onMessage,
        onError: _onError,
        onDone: _onDone,
        cancelOnError: false,
      );

      _connected = true;
      _reconnectCount = 0;
      _connectionController.add(true);

      assert(() {
        dev.log('TelemetrySocket: connected to $wsUrl',
            name: 'pecunator.ws');
        return true;
      }());
    } catch (e) {
      assert(() {
        dev.log('TelemetrySocket: connect failed: $e',
            name: 'pecunator.ws');
        return true;
      }());
      _scheduleReconnect();
    }
  }

  void _onMessage(dynamic raw) {
    if (_disposed) return;
    try {
      final decoded = jsonDecode(raw as String) as Map<String, dynamic>;
      _controller.add(decoded);
    } catch (e) {
      assert(() {
        dev.log('TelemetrySocket: decode error: $e',
            name: 'pecunator.ws');
        return true;
      }());
    }
  }

  void _onError(Object error) {
    assert(() {
      dev.log('TelemetrySocket: error: $error', name: 'pecunator.ws');
      return true;
    }());
    _setDisconnected();
    _scheduleReconnect();
  }

  void _onDone() {
    assert(() {
      dev.log('TelemetrySocket: connection closed', name: 'pecunator.ws');
      return true;
    }());
    _setDisconnected();
    _scheduleReconnect();
  }

  void _setDisconnected() {
    if (_connected) {
      _connected = false;
      _connectionController.add(false);
    }
  }

  void _scheduleReconnect() {
    if (_disposed) return;
    if (_reconnectCount >= maxReconnectAttempts) {
      // Reset counter and try with a longer delay
      _reconnectCount = 0;
      assert(() {
        dev.log(
            'TelemetrySocket: max reconnect attempts reached, resetting...',
            name: 'pecunator.ws');
        return true;
      }());
    }

    _reconnectCount++;
    // Exponential backoff: 3s, 6s, 12s, capped at 30s
    final delay = Duration(
      milliseconds: (reconnectDelay.inMilliseconds *
              (1 << (_reconnectCount - 1).clamp(0, 3)))
          .clamp(0, 30000),
    );

    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, () {
      _cleanup();
      _doConnect();
    });
  }

  void _cleanup() {
    _subscription?.cancel();
    _subscription = null;
    try {
      _channel?.sink.close();
    } catch (_) {}
    _channel = null;
  }

  /// Disconnect and release all resources.
  void dispose() {
    _disposed = true;
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _cleanup();
    _setDisconnected();
    _controller.close();
    _connectionController.close();
  }
}
