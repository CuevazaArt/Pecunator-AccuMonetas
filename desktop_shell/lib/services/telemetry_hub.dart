import 'dart:async';
import 'dart:developer' as dev;

import 'package:flutter/widgets.dart';

import 'telemetry_socket.dart';
import '../api_client.dart';

/// Central telemetry hub — single source of truth for all UI telemetry data.
///
/// Architecture:
///   - Connects to ws://localhost:8000/ws/telemetry
///   - Receives TELEMETRY_TICK events every 10s from TelemetryCollector
///   - Exposes a [stream] that all widgets can listen to
///   - Automatically falls back to REST polling if WebSocket is unavailable
///
/// This replaces the previous pattern where every widget had its own
/// Timer.periodic → REST GET loop (causing 6+ req/s overhead).
///
/// Usage in widgets:
/// ```dart
/// // In initState:
/// _sub = TelemetryHub.instance.stream.listen(_onTick);
///
/// // In the listener:
/// void _onTick(TelemetrySnapshot snap) {
///   setState(() {
///     _weight = snap.usedWeight;
///     _equity = snap.equity;
///   });
/// }
/// ```
class TelemetrySnapshot {
  final DateTime timestamp;

  // Account
  final double equity;
  final double freeUsdt;
  final double lockedUsdt;
  final double marginUsdt;

  // Weight
  final int usedWeight;
  final int weightLimit;

  // Order rate
  final int orderCount10s;
  final int orderLimit10s;

  // Fleet
  final int botsRunning;
  final int botsTotal;
  final int dorothyRunning;
  final int dorothyTotal;
  final int elphabaRunning;
  final int elphabaTotal;

  // Fuses
  final bool apiFuseOk;
  final bool orderFuseOk;

  // Gateway
  final bool gatewayRunning;
  final Map<String, dynamic>? gatewaySnapshot;

  // Bot detail lists (pushed via WS — eliminates REST polling)
  final List<Map<String, dynamic>> dorothyBots;
  final List<Map<String, dynamic>> elphabaBots;

  // Order ledger (pushed via WS — eliminates REST polling)
  final Map<String, dynamic>? orderLedgerStats;
  final List<Map<String, dynamic>> orderLedgerRecent;

  const TelemetrySnapshot({
    required this.timestamp,
    this.equity = 0,
    this.freeUsdt = 0,
    this.lockedUsdt = 0,
    this.marginUsdt = 0,
    this.usedWeight = 0,
    this.weightLimit = 6000,
    this.orderCount10s = 0,
    this.orderLimit10s = 100,
    this.botsRunning = 0,
    this.botsTotal = 0,
    this.dorothyRunning = 0,
    this.dorothyTotal = 0,
    this.elphabaRunning = 0,
    this.elphabaTotal = 0,
    this.apiFuseOk = true,
    this.orderFuseOk = true,
    this.gatewayRunning = false,
    this.gatewaySnapshot,
    this.dorothyBots = const [],
    this.elphabaBots = const [],
    this.orderLedgerStats,
    this.orderLedgerRecent = const [],
  });

  factory TelemetrySnapshot.fromPayload(Map<String, dynamic> payload) {
    return TelemetrySnapshot(
      timestamp: DateTime.tryParse('${payload['ts_utc']}') ?? DateTime.now(),
      equity: _toDouble(payload['equity_usdt']),
      freeUsdt: _toDouble(payload['free_usdt']),
      lockedUsdt: _toDouble(payload['locked_usdt']),
      marginUsdt: _toDouble(payload['margin_usdt']),
      usedWeight: _toInt(payload['used_weight_1m']),
      weightLimit: _toInt(payload['weight_limit_1m'], fallback: 6000),
      orderCount10s: _toInt(payload['order_count_10s']),
      orderLimit10s: _toInt(payload['order_limit_10s'], fallback: 100),
      botsRunning: _toInt(payload['bots_running']),
      botsTotal: _toInt(payload['bots_total']),
      dorothyRunning: _toInt(payload['dorothy_running']),
      dorothyTotal: _toInt(payload['dorothy_total']),
      elphabaRunning: _toInt(payload['elphaba_running']),
      elphabaTotal: _toInt(payload['elphaba_total']),
      apiFuseOk: (payload['api_fuse_ok'] ?? 1) == 1,
      orderFuseOk: (payload['order_fuse_ok'] ?? 1) == 1,
      gatewayRunning: (payload['gateway_running'] ?? 0) == 1,
      gatewaySnapshot: payload['gateway_snapshot'] as Map<String, dynamic>?,
      dorothyBots: _toBotList(payload['dorothy_bots']),
      elphabaBots: _toBotList(payload['elphaba_bots']),
      orderLedgerStats: payload['order_ledger_stats'] as Map<String, dynamic>?,
      orderLedgerRecent: _toBotList(payload['order_ledger_recent']),
    );
  }

  double get weightPct =>
      weightLimit > 0 ? (usedWeight / weightLimit).clamp(0.0, 1.0) : 0.0;

  double get orderRatePct =>
      orderLimit10s > 0
          ? (orderCount10s / orderLimit10s).clamp(0.0, 1.0)
          : 0.0;

  bool get fuseTripped => !apiFuseOk || !orderFuseOk;

  static double _toDouble(dynamic v) {
    if (v == null) return 0;
    if (v is double) return v;
    if (v is int) return v.toDouble();
    return double.tryParse('$v') ?? 0;
  }

  static int _toInt(dynamic v, {int fallback = 0}) {
    if (v == null) return fallback;
    if (v is int) return v;
    if (v is double) return v.toInt();
    return int.tryParse('$v') ?? fallback;
  }

  static List<Map<String, dynamic>> _toBotList(dynamic v) {
    if (v == null) return [];
    if (v is List) {
      return v
          .whereType<Map<String, dynamic>>()
          .toList();
    }
    return [];
  }
}

/// Singleton telemetry hub — manages the WebSocket lifecycle and
/// exposes a broadcast stream of [TelemetrySnapshot] to all widgets.
class TelemetryHub {
  // Singleton
  static TelemetryHub? _instance;
  static TelemetryHub get instance {
    _instance ??= TelemetryHub._();
    return _instance!;
  }

  TelemetrySocketService? _socket;
  StreamSubscription? _socketSub;
  Timer? _fallbackTimer;
  EngineApi? _fallbackApi;

  TelemetrySnapshot? _last;
  bool _wsConnected = false;

  final _controller = StreamController<TelemetrySnapshot>.broadcast();

  TelemetryHub._();

  /// Stream of parsed telemetry snapshots.
  Stream<TelemetrySnapshot> get stream => _controller.stream;

  /// The most recent snapshot (null if none received yet).
  TelemetrySnapshot? get last => _last;

  /// Whether the WebSocket is connected.
  bool get isWsConnected => _wsConnected;

  /// Stream of WebSocket connection state changes.
  Stream<bool>? get connectionStream => _socket?.connectionStream;

  /// Initialize the hub — connects WebSocket and sets up REST fallback.
  void init({required EngineApi api}) {
    if (_socket != null) return; // already initialized

    _fallbackApi = api;

    // Connect WebSocket
    _socket = TelemetrySocketService();
    _socketSub = _socket!.stream.listen(_onWsEvent);
    _socket!.connectionStream.listen((connected) {
      _wsConnected = connected;
      if (connected) {
        // WebSocket connected — disable fallback polling
        _fallbackTimer?.cancel();
        _fallbackTimer = null;
        assert(() {
          dev.log('TelemetryHub: WS connected, fallback polling disabled',
              name: 'pecunator.hub');
          return true;
        }());
      } else {
        // WebSocket lost — enable fallback REST polling
        _startFallbackPolling();
        assert(() {
          dev.log('TelemetryHub: WS lost, fallback polling enabled',
              name: 'pecunator.hub');
          return true;
        }());
      }
    });
    _socket!.connect();

    // Start fallback polling immediately (will be cancelled when WS connects)
    _startFallbackPolling();
  }

  void _onWsEvent(Map<String, dynamic> event) {
    final type = event['type'];
    if (type == 'TELEMETRY_TICK') {
      final payload = event['payload'] as Map<String, dynamic>? ?? {};
      final snap = TelemetrySnapshot.fromPayload(payload);
      _last = snap;
      _controller.add(snap);
    }
    // Future: handle FUSE_TRIPPED, ALERT, etc.
  }

  void _startFallbackPolling() {
    if (_fallbackTimer != null) return;
    _fallbackTimer = Timer.periodic(
      const Duration(seconds: 8),
      (_) => _fallbackPoll(),
    );
  }

  Future<void> _fallbackPoll() async {
    if (_wsConnected || _fallbackApi == null) return;
    try {
      final snap = await _fallbackApi!.gatewaySnapshot();
      final snapshot = TelemetrySnapshot(
        timestamp: DateTime.now(),
        equity: TelemetrySnapshot._toDouble(snap['equity_usdt']),
        freeUsdt: TelemetrySnapshot._toDouble(snap['free_usdt']),
        lockedUsdt: TelemetrySnapshot._toDouble(snap['locked_usdt']),
        usedWeight: TelemetrySnapshot._toInt(snap['used_weight_1m']),
        weightLimit: TelemetrySnapshot._toInt(snap['weight_limit_1m'],
            fallback: 6000),
        gatewayRunning: snap['gateway_running'] == true,
      );
      _last = snapshot;
      _controller.add(snapshot);
    } catch (_) {}
  }

  /// Dispose the hub — call on app shutdown.
  void dispose() {
    _fallbackTimer?.cancel();
    _socketSub?.cancel();
    _socket?.dispose();
    _controller.close();
    _instance = null;
  }
}

/// Inherited widget for providing the TelemetryHub to the widget tree.
class TelemetryHubProvider extends InheritedWidget {
  final TelemetryHub hub;

  const TelemetryHubProvider({
    super.key,
    required this.hub,
    required super.child,
  });

  static TelemetryHub of(BuildContext context) {
    final provider =
        context.dependOnInheritedWidgetOfExactType<TelemetryHubProvider>();
    return provider?.hub ?? TelemetryHub.instance;
  }

  @override
  bool updateShouldNotify(TelemetryHubProvider oldWidget) =>
      hub != oldWidget.hub;
}
