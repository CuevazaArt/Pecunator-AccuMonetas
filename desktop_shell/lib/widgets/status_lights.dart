import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../services/telemetry_hub.dart';
import 'chart_primitives.dart';

/// Status indicator lights — gateway, fuse, bot count.
class StatusLights extends StatelessWidget {
  final bool gatewayRunning;
  final bool fuseTripped;
  final int botsRunning;
  final int botsTotal;
  final String? hubName;
  final bool wsConnected;

  const StatusLights({
    super.key,
    required this.gatewayRunning,
    required this.fuseTripped,
    required this.botsRunning,
    required this.botsTotal,
    this.hubName,
    this.wsConnected = false,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        _light(
          'WS',
          wsConnected,
          wsConnected ? const Color(0xFF00E5FF) : Colors.grey,
        ),
        const SizedBox(width: 4),
        _light(
          'GW',
          gatewayRunning,
          gatewayRunning ? Colors.greenAccent : Colors.grey,
        ),
        const SizedBox(width: 4),
        _light(
          'FUSE',
          !fuseTripped,
          fuseTripped ? Colors.redAccent : Colors.cyanAccent,
        ),
        const SizedBox(width: 4),
        _light(
          hubName ?? 'BOTS',
          botsRunning > 0,
          botsRunning > 0 ? Colors.greenAccent : Colors.orangeAccent,
          detail: '$botsRunning/$botsTotal',
        ),
      ],
    );
  }

  Widget _light(String label, bool on, Color color, {String? detail}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6,
            height: 6,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: on ? color : color.withValues(alpha: 0.3),
              boxShadow: on
                  ? [
                      BoxShadow(
                        color: color.withValues(alpha: 0.5),
                        blurRadius: 4,
                      ),
                    ]
                  : null,
            ),
          ),
          const SizedBox(width: 3),
          Text(
            label,
            style: TextStyle(
              fontSize: 8,
              color: color,
              fontWeight: FontWeight.w800,
            ),
          ),
          if (detail != null) ...[
            const SizedBox(width: 3),
            Text(
              detail,
              style: TextStyle(
                fontSize: 8,
                color: color.withValues(alpha: 0.7),
                fontFamily: 'monospace',
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// Weight oscillator with adjustable time window.
/// Shows the full 0-100% range (fixed Y axis) for reference against
/// the auto-scaled MiniWeightChart.
class WeightOscillator extends StatefulWidget {
  final EngineApi api;
  final double height;

  const WeightOscillator({super.key, required this.api, this.height = 52});

  @override
  State<WeightOscillator> createState() => _WeightOscillatorState();
}

class _WeightOscillatorState extends State<WeightOscillator> {
  StreamSubscription<TelemetrySnapshot>? _hubSub;
  final List<ChartSample> _data = [];
  int _weightLimit = 6000;
  bool _fuseTripped = false;

  int _syncMs = 2000;  // kept for UI label only
  int _windowMin = 10;
  static const _syncOptions = [1000, 2000, 3000, 5000, 10000];
  static const _windowOptions = [1, 5, 10, 30, 60];

  @override
  void initState() {
    super.initState();
    _hubSub = TelemetryHub.instance.stream.listen(_onTelemetryTick);
  }

  @override
  void dispose() {
    _hubSub?.cancel();
    super.dispose();
  }

  void _onTelemetryTick(TelemetrySnapshot snap) {
    if (!mounted) return;
    final now = DateTime.now();
    final cutoff = now.subtract(Duration(minutes: _windowMin));
    setState(() {
      if (snap.usedWeight > 0) {
        _data.add(ChartSample(now, snap.usedWeight.toDouble()));
      }
      _data.removeWhere((s) => s.time.isBefore(cutoff));
      _weightLimit = snap.weightLimit > 0 ? snap.weightLimit : 6000;
      _fuseTripped = !snap.apiFuseOk;
    });
  }

  Color _colorForPct(double pct) {
    if (_fuseTripped) return const Color(0xFFFF1744);
    if (pct >= 0.80) return const Color(0xFFFF1744);
    if (pct >= 0.60) return const Color(0xFFFF9100);
    if (pct >= 0.40) return const Color(0xFFFFEA00);
    return const Color(0xFF00E5FF);
  }

  @override
  Widget build(BuildContext context) {
    final pct = _data.isEmpty
        ? 0.0
        : (_data.last.value / _weightLimit).clamp(0.0, 1.0);
    final color = _colorForPct(pct);
    final pctStr = (pct * 100).toStringAsFixed(1);

    return Container(
      height: widget.height,
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A2E),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 4, right: 2),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '$pctStr%',
                  style: TextStyle(
                    fontSize: 9,
                    color: color,
                    fontFamily: 'monospace',
                    fontWeight: FontWeight.w800,
                  ),
                ),
                GestureDetector(
                  onTap: () {
                    final idx = _syncOptions.indexOf(_syncMs);
                    setState(() {
                      _syncMs = _syncOptions[(idx + 1) % _syncOptions.length];
                    });
                  },
                  child: Text(
                    '${_syncMs}ms',
                    style: const TextStyle(
                      fontSize: 7,
                      color: Colors.white30,
                      fontFamily: 'monospace',
                    ),
                  ),
                ),
                GestureDetector(
                  onTap: () {
                    final idx = _windowOptions.indexOf(_windowMin);
                    setState(() {
                      _windowMin =
                          _windowOptions[(idx + 1) % _windowOptions.length];
                    });
                  },
                  child: Text(
                    '${_windowMin}m',
                    style: const TextStyle(
                      fontSize: 7,
                      color: Colors.white30,
                      fontFamily: 'monospace',
                    ),
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: CustomPaint(
              painter: SparklinePainter(
                data: _data,
                maxY: _weightLimit.toDouble(),
                color: color,
                fuseTripped: _fuseTripped,
              ),
              size: Size.infinite,
            ),
          ),
        ],
      ),
    );
  }
}
