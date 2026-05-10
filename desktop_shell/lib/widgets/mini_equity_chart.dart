import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../services/telemetry_hub.dart';
import 'chart_primitives.dart';

/// Rolling equity sparkline chart with capital breakdown.
/// Receives live data via WebSocket push from TelemetryHub.
class MiniEquityChart extends StatefulWidget {
  final EngineApi api;
  final String label;
  final Color color;
  final Duration timeWindow;
  final double height;
  final String? subaccountId;

  const MiniEquityChart({
    super.key,
    required this.api,
    this.label = 'Equity',
    this.color = const Color(0xFF00E676),
    this.timeWindow = const Duration(minutes: 30),
    this.height = 48,
    this.subaccountId,
  });

  @override
  State<MiniEquityChart> createState() => _MiniEquityChartState();
}

class _MiniEquityChartState extends State<MiniEquityChart> {
  StreamSubscription<TelemetrySnapshot>? _hubSub;
  final List<ChartSample> _data = [];
  double _startEquity = 0;
  bool _historyLoaded = false;

  double _free = 0;
  double _locked = 0;
  double _margin = 0;

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

    // Primary source: equity_usdt from TELEMETRY_TICK
    double equity = snap.equity;

    // Fallback: extract equity from gateway_snapshot if primary is zero
    if (equity <= 0 && snap.gatewaySnapshot != null) {
      final gwEquity = snap.gatewaySnapshot!['account_equity'];
      if (gwEquity is Map) {
        equity = double.tryParse('${gwEquity['current']}') ?? 0;
      }
    }

    if (equity <= 0) return;

    final now = DateTime.now();
    final cutoff = now.subtract(widget.timeWindow);
    setState(() {
      _data.add(ChartSample(now, equity));
      _data.removeWhere((s) => s.time.isBefore(cutoff));
      if (_startEquity == 0 && _data.isNotEmpty) {
        _startEquity = _data.first.value.toDouble();
      }
      _free = snap.freeUsdt;
      _locked = snap.lockedUsdt;
      _margin = snap.marginUsdt;
    });
  }

  Future<void> _loadHistory() async {
    if (_historyLoaded) return;
    try {
      final resp = await widget.api.equityHistory(
        minutes: widget.timeWindow.inMinutes,
        limit: 500,
      );
      final pts = resp['points'];
      if (pts is List && pts.isNotEmpty) {
        final now = DateTime.now();
        final cutoff = now.subtract(widget.timeWindow);
        final samples = <ChartSample>[];
        for (final p in pts) {
          final ts = DateTime.tryParse('${p['ts']}');
          final eq = double.tryParse('${p['equity']}') ?? 0;
          if (ts != null && eq > 0 && ts.isAfter(cutoff)) {
            samples.add(ChartSample(ts, eq));
          }
        }
        if (samples.isNotEmpty && mounted) {
          setState(() {
            _data.insertAll(0, samples);
            _startEquity = _data.first.value.toDouble();
          });
        }
      }
    } catch (_) {}
    _historyLoaded = true;
  }

  @override
  Widget build(BuildContext context) {
    final lastVal = _data.isEmpty ? 0.0 : _data.last.value.toDouble();
    final delta = _startEquity > 0 ? lastVal - _startEquity : 0.0;
    final deltaPct = _startEquity > 0 ? (delta / _startEquity * 100) : 0.0;
    final deltaColor = delta >= 0
        ? const Color(0xFF00E676)
        : const Color(0xFFFF1744);
    final deltaSign = delta >= 0 ? '+' : '';

    return Container(
      height: widget.height,
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A2E),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: widget.color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 6, right: 2),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  widget.label,
                  style: TextStyle(
                    fontSize: 8,
                    color: widget.color,
                    fontWeight: FontWeight.w900,
                  ),
                ),
                Text(
                  '\$${lastVal.toStringAsFixed(2)}',
                  style: TextStyle(
                    fontSize: 10,
                    color: widget.color,
                    fontFamily: 'monospace',
                    fontWeight: FontWeight.w800,
                  ),
                ),
                Text(
                  '$deltaSign${deltaPct.toStringAsFixed(2)}%',
                  style: TextStyle(
                    fontSize: 8,
                    color: deltaColor,
                    fontFamily: 'monospace',
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ],
            ),
          ),
          Expanded(
            child: CustomPaint(
              painter: SparklinePainter(
                data: _data,
                maxY: null,
                color: widget.color,
                fuseTripped: false,
              ),
              size: Size.infinite,
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(left: 4, right: 6),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                _capitalRow('FREE', _free, const Color(0xFF00E676)),
                const SizedBox(height: 2),
                _capitalRow('LOCK', _locked, const Color(0xFFFFEA00)),
                const SizedBox(height: 2),
                _capitalRow('MRGN', _margin, const Color(0xFF00B0FF)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _capitalRow(String label, double value, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 5,
          height: 5,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: color,
            boxShadow: [
              BoxShadow(color: color.withValues(alpha: 0.4), blurRadius: 3),
            ],
          ),
        ),
        const SizedBox(width: 3),
        Text(
          label,
          style: TextStyle(
            fontSize: 8,
            color: color.withValues(alpha: 0.8),
            fontWeight: FontWeight.w700,
          ),
        ),
        const SizedBox(width: 3),
        Text(
          '\$${value.toStringAsFixed(2)}',
          style: TextStyle(
            fontSize: 8,
            color: color,
            fontFamily: 'monospace',
            fontWeight: FontWeight.w700,
          ),
        ),
      ],
    );
  }
}
