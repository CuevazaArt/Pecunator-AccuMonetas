import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../services/telemetry_hub.dart';
import 'chart_primitives.dart';

/// Compact rolling order-rate chart — shows orders/10s over time.
/// Receives live data via WebSocket push from TelemetryHub.
class MiniOrderRateChart extends StatefulWidget {
  final EngineApi api;
  final Duration syncInterval;
  final Duration timeWindow;
  final double height;

  const MiniOrderRateChart({
    super.key,
    required this.api,
    this.syncInterval = const Duration(seconds: 2),
    this.timeWindow = const Duration(minutes: 10),
    this.height = 54,
  });

  @override
  State<MiniOrderRateChart> createState() => _MiniOrderRateChartState();
}

class _MiniOrderRateChartState extends State<MiniOrderRateChart> {
  StreamSubscription<TelemetrySnapshot>? _hubSub;
  final List<ChartSample> _data = [];
  int _orderLimit = 100;
  bool _danger = false;
  bool _historyLoaded = false;

  @override
  void initState() {
    super.initState();
    _loadHistory();
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
    final cutoff = now.subtract(widget.timeWindow);
    setState(() {
      _data.add(ChartSample(now, snap.orderCount10s.toDouble()));
      _data.removeWhere((s) => s.time.isBefore(cutoff));
      _orderLimit = snap.orderLimit10s > 0 ? snap.orderLimit10s : 100;
      _danger = !snap.orderFuseOk || snap.orderRatePct >= 0.80;
    });
  }

  Future<void> _loadHistory() async {
    if (_historyLoaded) return;
    try {
      final resp = await widget.api.telemetryHistory(
        minutes: widget.timeWindow.inMinutes,
        limit: 500,
      );
      final pts = resp['points'];
      if (pts is List && pts.isNotEmpty) {
        final now = DateTime.now();
        final cutoff = now.subtract(widget.timeWindow);
        final samples = <ChartSample>[];
        for (final p in pts) {
          final ts = DateTime.tryParse('${p['ts_utc']}');
          final c = double.tryParse('${p['order_count_10s']}') ?? -1;
          if (ts != null && c >= 0 && ts.isAfter(cutoff)) {
            samples.add(ChartSample(ts, c));
          }
        }
        if (samples.isNotEmpty && mounted) {
          setState(() => _data.insertAll(0, samples));
        }
      }
    } catch (_) {}
    _historyLoaded = true;
  }

  Color _colorForPct(double pct) {
    if (pct >= 0.80) return const Color(0xFFFF1744);
    if (pct >= 0.60) return const Color(0xFFFF9100);
    if (pct >= 0.30) return const Color(0xFFFFEA00);
    return const Color(0xFF7C4DFF);
  }

  @override
  Widget build(BuildContext context) {
    final pct = _data.isEmpty
        ? 0.0
        : (_data.last.value / _orderLimit).clamp(0.0, 1.0);
    final color = _colorForPct(pct);
    final pctStr = (pct * 100).toStringAsFixed(1);
    final lastVal = _data.isEmpty ? '--' : _data.last.value.toInt().toString();

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
            padding: const EdgeInsets.symmetric(horizontal: 6),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'ORDERS',
                  style: TextStyle(
                    fontSize: 9,
                    color: color,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                Text(
                  '$pctStr%',
                  style: TextStyle(
                    fontSize: 10,
                    color: color,
                    fontFamily: 'monospace',
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  '$lastVal/$_orderLimit',
                  style: const TextStyle(
                    fontSize: 7,
                    color: Colors.white38,
                    fontFamily: 'monospace',
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: CustomPaint(
              painter: SparklinePainter(
                data: _data,
                maxY: _orderLimit.toDouble(),
                color: color,
                fuseTripped: _danger,
              ),
              size: Size.infinite,
            ),
          ),
          if (_danger)
            Container(
              margin: const EdgeInsets.only(right: 4),
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
              decoration: BoxDecoration(
                color: const Color(0x44FF1744),
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Text('⚠', style: TextStyle(fontSize: 10)),
            ),
        ],
      ),
    );
  }
}
