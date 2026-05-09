import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';

/// Compact system status bar — shows ON/OFF/ERROR for all subsystems.
///
/// Sits in the persistent footer alongside CompactWeightGauge.
/// Polls every 30s.
class SystemStatusBar extends StatefulWidget {
  final EngineApi api;
  const SystemStatusBar({super.key, required this.api});

  @override
  State<SystemStatusBar> createState() => _SystemStatusBarState();
}

class _SystemStatusBarState extends State<SystemStatusBar> {
  Timer? _timer;

  // Gateway
  bool _gwRunning = false;
  bool _gwWs = false;
  String? _gwError;

  // VMO
  bool _vmoEnabled = false;
  bool _vmoRunning = false;
  int _vmoCycles = 0;

  // Fear & Greed
  int? _fgValue;
  String _fgLabel = '—';

  // Bot counts
  int _dorothyRunning = 0;
  int _dorothyTotal = 0;
  int _elphabaRunning = 0;
  int _elphabaTotal = 0;

  // Activity session
  String _session = '—';
  double _activityScore = 0;

  @override
  void initState() {
    super.initState();
    _poll();
    _timer = Timer.periodic(const Duration(seconds: 30), (_) => _poll());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _poll() async {
    if (!mounted) return;
    try {
      // Parallel fetch for speed
      final results = await Future.wait([
        widget.api.gatewaySnapshot().catchError((_) => <String, dynamic>{}),
        widget.api.visionStatus().catchError((_) => <String, dynamic>{}),
        widget.api.eventsSummary().catchError((_) => <String, dynamic>{}),
        widget.api.healthDeep().catchError((_) => <String, dynamic>{}),
      ]);

      final snap = results[0];
      final vmo = results[1];
      final events = results[2];
      final health = results[3];

      if (!mounted) return;
      setState(() {
        // Gateway
        _gwRunning = snap['gateway_running'] == true;
        _gwWs = snap['ws_connected'] == true;
        final le = snap['last_error'];
        _gwError = (le != null && le.toString().trim().isNotEmpty) ? le.toString() : null;

        // VMO
        final vmoConfig = vmo['config'] as Map<String, dynamic>? ?? {};
        _vmoEnabled = vmo['enabled'] == true || vmoConfig['enabled'] == true;
        _vmoRunning = vmo['running'] == true;
        _vmoCycles = (vmo['total_cycles'] as int?) ?? 0;

        // Fear & Greed
        _fgValue = events['fear_greed_value'] as int?;
        _fgLabel = (events['fear_greed_label'] ?? '—').toString();

        // Activity
        _session = (events['session'] ?? '—').toString();
        _activityScore = (events['activity_score'] as num?)?.toDouble() ?? 0;

        // Bot counts from health deep
        final hubs = health['hubs'] as Map<String, dynamic>? ?? {};
        final dHub = hubs['dorothy'] as Map<String, dynamic>? ?? {};
        final mHub = hubs['elphaba'] as Map<String, dynamic>? ?? {};
        _dorothyRunning = (dHub['hub_bots_running'] as int?) ?? 0;
        _dorothyTotal = (dHub['hub_bots_total'] as int?) ?? 0;
        _elphabaRunning = (mHub['hub_bots_running'] as int?) ?? 0;
        _elphabaTotal = (mHub['hub_bots_total'] as int?) ?? 0;
      });
    } catch (_) {}
  }

  Color _gwColor() {
    if (!_gwRunning) return Colors.grey;
    if (_gwError != null) return Colors.redAccent;
    if (!_gwWs) return Colors.orangeAccent;
    return Colors.greenAccent;
  }

  String _gwTooltip() {
    if (!_gwRunning) return 'Gateway: OFF';
    if (_gwError != null) return 'Gateway: ERROR — $_gwError';
    if (!_gwWs) return 'Gateway: ON (WS disconnected)';
    return 'Gateway: ON + WebSocket';
  }

  Color _vmoColor() {
    if (!_vmoEnabled) return Colors.grey;
    if (!_vmoRunning) return Colors.orangeAccent;
    return Colors.greenAccent;
  }

  String _vmoTooltip() {
    if (!_vmoEnabled) return 'VMO: Disabled';
    if (!_vmoRunning) return 'VMO: Enabled (waiting for cycle)';
    return 'VMO: Running ($_vmoCycles cycles)';
  }

  Color _fgColor() {
    if (_fgValue == null) return Colors.grey;
    if (_fgValue! <= 25) return Colors.redAccent; // Extreme Fear
    if (_fgValue! <= 40) return Colors.orangeAccent; // Fear
    if (_fgValue! <= 60) return Colors.blueAccent; // Neutral
    if (_fgValue! <= 75) return Colors.lightGreenAccent; // Greed
    return Colors.greenAccent; // Extreme Greed
  }

  Color _botColor(int running, int total) {
    if (total == 0) return Colors.grey;
    if (running == 0) return Colors.redAccent;
    if (running < total) return Colors.orangeAccent;
    return Colors.greenAccent;
  }

  Color _sessionColor() {
    if (_activityScore >= 0.85) return Colors.greenAccent;
    if (_activityScore >= 0.65) return Colors.blueAccent;
    if (_activityScore >= 0.45) return Colors.orangeAccent;
    return Colors.redAccent;
  }

  Widget _dot(Color color, String label, String tooltip) {
    return Tooltip(
      message: tooltip,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: color.withValues(alpha: 0.4), width: 0.5),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 6, height: 6,
              decoration: BoxDecoration(
                color: color,
                shape: BoxShape.circle,
                boxShadow: [BoxShadow(color: color.withValues(alpha: 0.6), blurRadius: 4)],
              ),
            ),
            const SizedBox(width: 4),
            Text(label, style: TextStyle(
              color: color, fontSize: 10, fontWeight: FontWeight.w600,
              fontFamily: 'monospace',
            )),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _dot(_gwColor(), 'GW', _gwTooltip()),
          const SizedBox(width: 4),
          _dot(_vmoColor(), 'VMO', _vmoTooltip()),
          const SizedBox(width: 4),
          _dot(
            _fgColor(),
            _fgValue != null ? 'F&G:$_fgValue' : 'F&G:—',
            _fgValue != null ? 'Fear & Greed: $_fgValue ($_fgLabel)' : 'Fear & Greed: no data',
          ),
          const SizedBox(width: 4),
          _dot(_sessionColor(), _session, 'Session: $_session (activity: ${(_activityScore * 100).toInt()}%)'),
          const SizedBox(width: 4),
          _dot(_botColor(_dorothyRunning, _dorothyTotal), 'D:$_dorothyRunning/$_dorothyTotal', 'Dorothy: $_dorothyRunning/$_dorothyTotal running'),
          const SizedBox(width: 4),
          _dot(_botColor(_elphabaRunning, _elphabaTotal), 'E:$_elphabaRunning/$_elphabaTotal', 'Elphaba: $_elphabaRunning/$_elphabaTotal running'),
        ],
      ),
    );
  }
}
