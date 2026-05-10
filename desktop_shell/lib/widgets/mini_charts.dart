import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../api_client.dart';

/// Compact rolling weight chart — shows API weight over a configurable time window.
/// Zero API weight cost: reads from local gateway snapshot only.
class MiniWeightChart extends StatefulWidget {
  final EngineApi api;
  final Duration syncInterval;
  final Duration timeWindow;
  final double height;

  const MiniWeightChart({
    super.key,
    required this.api,
    this.syncInterval = const Duration(seconds: 2),
    this.timeWindow = const Duration(minutes: 10),
    this.height = 48,
  });

  @override
  State<MiniWeightChart> createState() => _MiniWeightChartState();
}

class _MiniWeightChartState extends State<MiniWeightChart> {
  Timer? _timer;
  final List<_Sample> _data = [];
  int _weightLimit = 6000;
  bool _fuseTripped = false;

  @override
  void initState() {
    super.initState();
    _tick();
    _timer = Timer.periodic(widget.syncInterval, (_) => _tick());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _tick() async {
    try {
      final snap = await widget.api.gatewaySnapshot();
      final usedRaw = snap['used_weight_1m'];
      int? used;
      if (usedRaw is int) {
        used = usedRaw;
      } else if (usedRaw is num) {
        used = usedRaw.toInt();
      } else {
        used = int.tryParse('$usedRaw');
      }

      final limitRaw = snap['weight_limit_1m'];
      int limit = 6000;
      if (limitRaw is int) {
        limit = limitRaw;
      } else if (limitRaw is num) {
        limit = limitRaw.toInt();
      } else {
        limit = int.tryParse('$limitRaw') ?? 6000;
      }

      if (!mounted) return;
      final now = DateTime.now();
      final cutoff = now.subtract(widget.timeWindow);
      setState(() {
        if (used != null) _data.add(_Sample(now, used));
        _data.removeWhere((s) => s.time.isBefore(cutoff));
        _weightLimit = limit > 0 ? limit : 6000;
        // Derive fuse-like state from weight percentage (>90% = danger)
        _fuseTripped = used != null && limit > 0 && (used / limit) >= 0.90;
      });
    } catch (_) {}
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
    final lastVal = _data.isEmpty ? '--' : _data.last.value.toString();

    return Container(
      height: widget.height,
      decoration: BoxDecoration(
        color: const Color(0xFF1A1A2E),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          // Label
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 6),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'W',
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
                  '$lastVal/$_weightLimit',
                  style: const TextStyle(
                    fontSize: 7,
                    color: Colors.white38,
                    fontFamily: 'monospace',
                  ),
                ),
              ],
            ),
          ),
          // Chart
          Expanded(
            child: CustomPaint(
              painter: _SparklinePainter(
                data: _data,
                maxY: _weightLimit.toDouble(),
                color: color,
                fuseTripped: _fuseTripped,
              ),
              size: Size.infinite,
            ),
          ),
          // Fuse indicator
          if (_fuseTripped)
            Container(
              margin: const EdgeInsets.only(right: 4),
              padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
              decoration: BoxDecoration(
                color: const Color(0x44FF1744),
                borderRadius: BorderRadius.circular(4),
              ),
              child: const Text('⚡', style: TextStyle(fontSize: 10)),
            ),
        ],
      ),
    );
  }
}

/// Compact rolling equity chart — shows equity USDT over time.
class MiniEquityChart extends StatefulWidget {
  final EngineApi api;
  final String label;
  final Color color;
  final Duration syncInterval;
  final Duration timeWindow;
  final double height;

  /// If provided, fetches specific subaccount equity endpoint.
  /// null = global equity from gateway snapshot.
  final String? subaccountId;

  const MiniEquityChart({
    super.key,
    required this.api,
    this.label = 'Equity',
    this.color = const Color(0xFF00E676),
    this.syncInterval = const Duration(seconds: 5),
    this.timeWindow = const Duration(minutes: 30),
    this.height = 48,
    this.subaccountId,
  });

  @override
  State<MiniEquityChart> createState() => _MiniEquityChartState();
}

class _MiniEquityChartState extends State<MiniEquityChart> {
  Timer? _timer;
  final List<_Sample> _data = [];
  double _startEquity = 0;

  @override
  void initState() {
    super.initState();
    _tick();
    _timer = Timer.periodic(widget.syncInterval, (_) => _tick());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _tick() async {
    try {
      final snap = await widget.api.gatewaySnapshot();
      final eqMap = snap['account_equity'];
      double equity = 0;
      if (eqMap is Map) {
        final raw = eqMap['current'] ?? eqMap['total_usdt'] ?? '0';
        equity = double.tryParse('$raw') ?? 0;
      }
      if (equity <= 0) return;

      if (!mounted) return;
      final now = DateTime.now();
      final cutoff = now.subtract(widget.timeWindow);
      setState(() {
        _data.add(_Sample(now, equity.round()));
        _data.removeWhere((s) => s.time.isBefore(cutoff));
        if (_startEquity == 0 && _data.isNotEmpty) {
          _startEquity = _data.first.value.toDouble();
        }
      });
    } catch (_) {}
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
            padding: const EdgeInsets.symmetric(horizontal: 6),
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
              painter: _SparklinePainter(
                data: _data,
                maxY: null,
                color: widget.color,
                fuseTripped: false,
              ),
              size: Size.infinite,
            ),
          ),
        ],
      ),
    );
  }
}

/// System status indicator lights
class StatusLights extends StatelessWidget {
  final bool gatewayRunning;
  final bool fuseTripped;
  final int botsRunning;
  final int botsTotal;
  final String? hubName;

  const StatusLights({
    super.key,
    required this.gatewayRunning,
    required this.fuseTripped,
    required this.botsRunning,
    required this.botsTotal,
    this.hubName,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
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

// ── Internal classes ──────────────────────────────────────────────────

class _Sample {
  final DateTime time;
  final int value;
  const _Sample(this.time, this.value);
}

class _SparklinePainter extends CustomPainter {
  final List<_Sample> data;
  final double? maxY;
  final Color color;
  final bool fuseTripped;

  _SparklinePainter({
    required this.data,
    this.maxY,
    required this.color,
    required this.fuseTripped,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (data.length < 2) return;

    final effectiveMaxY =
        maxY ?? data.map((d) => d.value).reduce(math.max).toDouble() * 1.1;
    final effectiveMinY = maxY != null
        ? 0.0
        : data.map((d) => d.value).reduce(math.min).toDouble() * 0.95;
    final rangeY = effectiveMaxY - effectiveMinY;
    if (rangeY <= 0) return;

    final firstTime = data.first.time;
    final lastTime = data.last.time;
    final rangeX = lastTime.difference(firstTime).inMilliseconds.toDouble();
    if (rangeX <= 0) return;

    final path = Path();
    final fillPath = Path();

    for (int i = 0; i < data.length; i++) {
      final x =
          (data[i].time.difference(firstTime).inMilliseconds / rangeX) *
          size.width;
      final y =
          size.height -
          ((data[i].value - effectiveMinY) / rangeY) * size.height * 0.85 -
          size.height * 0.05;
      if (i == 0) {
        path.moveTo(x, y);
        fillPath.moveTo(x, size.height);
        fillPath.lineTo(x, y);
      } else {
        path.lineTo(x, y);
        fillPath.lineTo(x, y);
      }
    }

    // Fill gradient
    fillPath.lineTo(size.width, size.height);
    fillPath.close();
    final fillPaint = Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
        colors: [color.withValues(alpha: 0.2), color.withValues(alpha: 0.0)],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    canvas.drawPath(fillPath, fillPaint);

    // Line
    final linePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.5
      ..strokeJoin = StrokeJoin.round;
    canvas.drawPath(path, linePaint);

    // Current value dot
    if (data.isNotEmpty) {
      final last = data.last;
      final lx = size.width;
      final ly =
          size.height -
          ((last.value - effectiveMinY) / rangeY) * size.height * 0.85 -
          size.height * 0.05;
      canvas.drawCircle(Offset(lx, ly), 2.5, Paint()..color = color);
      canvas.drawCircle(
        Offset(lx, ly),
        4,
        Paint()..color = color.withValues(alpha: 0.3),
      );
    }

    // Threshold lines for weight charts (with 100% reference)
    if (maxY != null) {
      // 100% ceiling — the critical reference
      final fullY =
          size.height - (1.0 * size.height * 0.85) - size.height * 0.05;
      final ceilPaint = Paint()
        ..color = const Color(0x66FF1744)
        ..strokeWidth = 1.0;
      canvas.drawLine(Offset(0, fullY), Offset(size.width, fullY), ceilPaint);
      // "100%" label
      final tp100 = TextPainter(
        text: const TextSpan(
          text: '100%',
          style: TextStyle(
            fontSize: 7,
            color: Color(0x88FF1744),
            fontFamily: 'monospace',
          ),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp100.paint(
        canvas,
        Offset(size.width - tp100.width - 1, fullY - tp100.height - 1),
      );

      // Threshold guide lines: 40%, 60%, 80%
      final thresholds = [
        (0.4, '40%', const Color(0x3300E5FF)),
        (0.6, '60%', const Color(0x33FFEA00)),
        (0.8, '80%', const Color(0x33FF9100)),
      ];
      for (final (t, label, tColor) in thresholds) {
        final ty = size.height - (t * size.height * 0.85) - size.height * 0.05;
        final tp = Paint()
          ..color = tColor
          ..strokeWidth = 0.5;
        canvas.drawLine(Offset(0, ty), Offset(size.width, ty), tp);
        // Small label on right edge
        final tpLabel = TextPainter(
          text: TextSpan(
            text: label,
            style: TextStyle(
              fontSize: 6,
              color: tColor.withAlpha(180),
              fontFamily: 'monospace',
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        tpLabel.paint(canvas, Offset(size.width - tpLabel.width - 1, ty + 1));
      }
    }
  }

  @override
  bool shouldRepaint(covariant _SparklinePainter old) =>
      old.data.length != data.length || old.color != color;
}

/// Weight oscillator with adjustable sync interval and time window.
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
  Timer? _timer;
  final List<_Sample> _data = [];
  int _weightLimit = 6000;
  bool _fuseTripped = false;

  // Adjustable controls
  int _syncMs = 2000;
  int _windowMin = 10;
  static const _syncOptions = [1000, 2000, 3000, 5000, 10000];
  static const _windowOptions = [1, 5, 10, 30, 60];

  @override
  void initState() {
    super.initState();
    _tick();
    _startTimer();
  }

  void _startTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(Duration(milliseconds: _syncMs), (_) => _tick());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _tick() async {
    try {
      final snap = await widget.api.gatewaySnapshot();
      final usedRaw = snap['used_weight_1m'];
      int? used;
      if (usedRaw is int) {
        used = usedRaw;
      } else if (usedRaw is num) {
        used = usedRaw.toInt();
      } else {
        used = int.tryParse('$usedRaw');
      }

      final limitRaw = snap['weight_limit_1m'];
      int limit = 6000;
      if (limitRaw is int) {
        limit = limitRaw;
      } else if (limitRaw is num) {
        limit = limitRaw.toInt();
      } else {
        limit = int.tryParse('$limitRaw') ?? 6000;
      }

      if (!mounted) return;
      final now = DateTime.now();
      final cutoff = now.subtract(Duration(minutes: _windowMin));
      setState(() {
        if (used != null) {
          _data.add(_Sample(now, used));
        }
        _data.removeWhere((s) => s.time.isBefore(cutoff));
        _weightLimit = limit > 0 ? limit : 6000;
        _fuseTripped = used != null && limit > 0 && (used / limit) >= 0.90;
      });
    } catch (_) {}
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
          // Label + controls
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
                // Sync selector
                GestureDetector(
                  onTap: () {
                    final idx = _syncOptions.indexOf(_syncMs);
                    setState(() {
                      _syncMs = _syncOptions[(idx + 1) % _syncOptions.length];
                      _startTimer();
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
                // Window selector
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
          // Chart — fixed 0-100% Y axis
          Expanded(
            child: CustomPaint(
              painter: _SparklinePainter(
                data: _data,
                maxY: _weightLimit.toDouble(), // Fixed range
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
