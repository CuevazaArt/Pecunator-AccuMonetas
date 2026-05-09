import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../api_client.dart';

/// Compact, always-visible API weight monitor widget.
///
/// Designed to sit in the bottom bar or app shell, providing at-a-glance
/// telemetry of Binance REST API weight consumption — without itself
/// consuming any API weight (reads from the local gateway snapshot only).
///
/// Features:
///   - Animated radial gauge with gradient colors
///   - Percentage + absolute weight readout
///   - pts/min estimate from local state
///   - Fuse status indicator (tripped / armed)
///   - Expandable detail drawer on tap
class CompactWeightGauge extends StatefulWidget {
  final EngineApi api;
  final Duration refreshInterval;

  const CompactWeightGauge({
    super.key,
    required this.api,
    this.refreshInterval = const Duration(seconds: 3),
  });

  @override
  State<CompactWeightGauge> createState() => _CompactWeightGaugeState();
}

class _CompactWeightGaugeState extends State<CompactWeightGauge>
    with SingleTickerProviderStateMixin {
  Timer? _timer;
  int? _weightUsed;
  int _weightLimit = 6000;
  bool _gatewayRunning = false;
  bool _fuseTripped = false;
  String _fuseReason = '';
  double _fuseRemainingSec = 0;
  double _animTarget = 0;
  bool _expanded = false;
  int _fuseStreak = 0;
  int _fuseNextCooldown = 300;
  int _fuseCurrentCooldown = 300;
  // For pts/min tracking
  final List<_WeightSample> _samples = [];

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(widget.refreshInterval, (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      // gatewaySnapshot is a local state read — ZERO API weight.
      final snap = await widget.api.gatewaySnapshot();
      final usedRaw = snap['used_weight_1m'];
      final limitRaw = snap['weight_limit_1m'];
      int? used;
      if (usedRaw is int) {
        used = usedRaw;
      } else if (usedRaw is num) {
        used = usedRaw.toInt();
      } else {
        used = int.tryParse('$usedRaw');
      }
      var limit = 6000;
      if (limitRaw is int) {
        limit = limitRaw;
      } else if (limitRaw is num) {
        limit = limitRaw.toInt();
      } else {
        limit = int.tryParse('$limitRaw') ?? 6000;
      }
      final gw = snap['gateway_running'] == true;

      // Track samples for pts/min calculation
      if (used != null) {
        _samples.add(_WeightSample(DateTime.now(), used));
        // Keep last 60 samples (~ 3 min at 3s intervals)
        if (_samples.length > 60) {
          _samples.removeRange(0, _samples.length - 60);
        }
      }

      // Try to get fuse status (also local, no API weight)
      bool fuseTripped = false;
      String fuseReason = '';
      double fuseRemaining = 0;
      try {
        final fuse = await widget.api.apiFuseStatus();
        fuseTripped = fuse['tripped'] == true;
        fuseReason = (fuse['reason'] ?? '').toString();
        fuseRemaining = (fuse['remaining_cooldown_sec'] is num)
            ? (fuse['remaining_cooldown_sec'] as num).toDouble()
            : 0;
        _fuseStreak = (fuse['consecutive_streak'] is num)
            ? (fuse['consecutive_streak'] as num).toInt()
            : 0;
        _fuseNextCooldown = (fuse['next_cooldown_sec'] is num)
            ? (fuse['next_cooldown_sec'] as num).toInt()
            : 300;
        _fuseCurrentCooldown = (fuse['current_cooldown_sec'] is num)
            ? (fuse['current_cooldown_sec'] as num).toInt()
            : 300;
      } catch (_) {}

      if (!mounted) return;
      setState(() {
        _weightUsed = used;
        _weightLimit = limit <= 0 ? 6000 : limit;
        _gatewayRunning = gw;
        _fuseTripped = fuseTripped;
        _fuseReason = fuseReason;
        _fuseRemainingSec = fuseRemaining;
        _animTarget = used != null && limit > 0
            ? (used / limit).clamp(0.0, 1.0)
            : 0.0;
      });
    } catch (_) {}
  }

  double get _ptsPerMin {
    if (_samples.length < 2) return 0;
    final first = _samples.first;
    final last = _samples.last;
    final durationMin = last.time.difference(first.time).inMilliseconds / 60000.0;
    if (durationMin < 0.1) return 0;
    // Weight resets every minute, so we look at the max observed difference
    int maxDelta = 0;
    for (int i = 1; i < _samples.length; i++) {
      final d = _samples[i].weight - _samples[i - 1].weight;
      if (d > 0) maxDelta += d;
    }
    return maxDelta / durationMin;
  }

  Color _gaugeColor(double pct) {
    if (_fuseTripped) return Colors.red;
    if (pct >= 0.80) return const Color(0xFFFF1744);
    if (pct >= 0.60) return const Color(0xFFFF9100);
    if (pct >= 0.40) return const Color(0xFFFFEA00);
    if (pct >= 0.15) return const Color(0xFF00E676);
    return const Color(0xFF00E5FF);
  }

  Color _bgColor(double pct) {
    if (_fuseTripped) return const Color(0x33FF1744);
    if (pct >= 0.80) return const Color(0x22FF1744);
    if (pct >= 0.60) return const Color(0x22FF9100);
    return const Color(0x1500E5FF);
  }

  @override
  Widget build(BuildContext context) {
    final pct = _animTarget;
    final pctStr = (pct * 100).toStringAsFixed(1);
    final usedStr = _weightUsed?.toString() ?? '—';
    final ppm = _ptsPerMin;
    final ppmStr = ppm < 1 ? ppm.toStringAsFixed(2) : ppm.toStringAsFixed(0);
    final color = _gaugeColor(pct);

    return GestureDetector(
      onTap: () => setState(() => _expanded = !_expanded),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: _bgColor(pct),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: color.withValues(alpha: 0.4),
            width: 1,
          ),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // ── Compact bar (always visible) ──────────────
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Animated mini gauge
                SizedBox(
                  width: 28,
                  height: 28,
                  child: TweenAnimationBuilder<double>(
                    tween: Tween(begin: 0, end: pct),
                    duration: const Duration(milliseconds: 800),
                    curve: Curves.easeOutCubic,
                    builder: (ctx, val, _) => CustomPaint(
                      painter: _ArcGaugePainter(
                        value: val,
                        color: _gaugeColor(val),
                        bgColor: Colors.white10,
                      ),
                      child: Center(
                        child: _fuseTripped
                            ? const Icon(Icons.flash_off, size: 12, color: Colors.red)
                            : Icon(
                                _gatewayRunning ? Icons.sensors : Icons.sensors_off,
                                size: 12,
                                color: _gatewayRunning ? color : Colors.grey,
                              ),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                // Percentage
                Text(
                  '$pctStr%',
                  style: TextStyle(
                    color: color,
                    fontWeight: FontWeight.w800,
                    fontSize: 14,
                    fontFamily: 'monospace',
                  ),
                ),
                const SizedBox(width: 6),
                // Weight values
                Text(
                  '$usedStr/$_weightLimit',
                  style: TextStyle(
                    color: Colors.white.withValues(alpha: 0.7),
                    fontSize: 10,
                    fontFamily: 'monospace',
                  ),
                ),
                const SizedBox(width: 8),
                // pts/min chip
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                  decoration: BoxDecoration(
                    color: ppm > 50
                        ? const Color(0x44FF1744)
                        : ppm > 10
                            ? const Color(0x44FF9100)
                            : const Color(0x2200E5FF),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    '${ppmStr}p/m',
                    style: TextStyle(
                      color: ppm > 50
                          ? const Color(0xFFFF1744)
                          : ppm > 10
                              ? const Color(0xFFFF9100)
                              : const Color(0xFF00E5FF),
                      fontSize: 9,
                      fontWeight: FontWeight.w700,
                      fontFamily: 'monospace',
                    ),
                  ),
                ),
                // Fuse indicator
                if (_fuseTripped) ...[
                  const SizedBox(width: 6),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                    decoration: BoxDecoration(
                      color: const Color(0x44FF1744),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(
                      'FUSE ${_fuseRemainingSec.toStringAsFixed(0)}s',
                      style: const TextStyle(
                        color: Color(0xFFFF1744),
                        fontSize: 9,
                        fontWeight: FontWeight.w900,
                        fontFamily: 'monospace',
                      ),
                    ),
                  ),
                ],
                // Expand arrow
                const SizedBox(width: 4),
                Icon(
                  _expanded ? Icons.expand_less : Icons.expand_more,
                  size: 14,
                  color: Colors.white38,
                ),
              ],
            ),
            // ── Expanded detail ──────────────────────────
            if (_expanded) ...[
              const SizedBox(height: 6),
              _buildExpandedDetail(color, pct),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildExpandedDetail(Color color, double pct) {
    final ppm = _ptsPerMin;
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.black26,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Mini progress bar
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: pct),
              duration: const Duration(milliseconds: 600),
              builder: (ctx, v, _) => LinearProgressIndicator(
                minHeight: 6,
                value: v,
                valueColor: AlwaysStoppedAnimation(color),
                backgroundColor: Colors.white10,
              ),
            ),
          ),
          const SizedBox(height: 6),
          // Stats row
          Row(
            children: [
              _statChip('Gateway', _gatewayRunning ? 'ON' : 'OFF',
                  _gatewayRunning ? Colors.greenAccent : Colors.grey),
              const SizedBox(width: 6),
              _statChip('Fusible', _fuseTripped ? 'TRIP' : 'OK',
                  _fuseTripped ? Colors.redAccent : Colors.cyanAccent),
              const SizedBox(width: 6),
              _statChip('pts/min', ppm.toStringAsFixed(1),
                  ppm > 50 ? Colors.redAccent : ppm > 10 ? Colors.orangeAccent : Colors.cyanAccent),
            ],
          ),
          if (_fuseTripped && _fuseReason.isNotEmpty) ...[
            const SizedBox(height: 4),
            Text(
              '⚡ $_fuseReason (${_fuseRemainingSec.toStringAsFixed(0)}s)',
              style: const TextStyle(
                color: Colors.redAccent,
                fontSize: 10,
                fontFamily: 'monospace',
              ),
            ),
          ],
          const SizedBox(height: 4),
          // Safety thresholds
          Row(
            children: [
              _thresholdDot('Safe', const Color(0xFF00E5FF), pct < 0.40),
              const SizedBox(width: 4),
              _thresholdDot('Caution', const Color(0xFFFFEA00), pct >= 0.40 && pct < 0.60),
              const SizedBox(width: 4),
              _thresholdDot('Warning', const Color(0xFFFF9100), pct >= 0.60 && pct < 0.80),
              const SizedBox(width: 4),
              _thresholdDot('Critical', const Color(0xFFFF1744), pct >= 0.80),
            ],
          ),
          // Escalation streak info
          if (_fuseStreak > 0) ...[
            const SizedBox(height: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: _fuseStreak >= 3
                    ? const Color(0x44FF1744)
                    : const Color(0x44FF9100),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.bolt,
                    size: 11,
                    color: _fuseStreak >= 3
                        ? const Color(0xFFFF1744)
                        : const Color(0xFFFF9100),
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'Racha #$_fuseStreak · Cooldown actual: ${_fuseCurrentCooldown}s'
                    ' · Siguiente si re-dispara: ${_fuseNextCooldown}s',
                    style: TextStyle(
                      fontSize: 9,
                      fontFamily: 'monospace',
                      color: _fuseStreak >= 3
                          ? const Color(0xFFFF1744)
                          : const Color(0xFFFF9100),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Widget _statChip(String label, String value, Color valueColor) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
      decoration: BoxDecoration(
        color: valueColor.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: valueColor.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Text(label,
              style: TextStyle(
                  fontSize: 8, color: Colors.white.withValues(alpha: 0.5))),
          Text(value,
              style: TextStyle(
                  fontSize: 11,
                  fontWeight: FontWeight.w800,
                  color: valueColor,
                  fontFamily: 'monospace')),
        ],
      ),
    );
  }

  Widget _thresholdDot(String label, Color color, bool active) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 6,
          height: 6,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: active ? color : color.withValues(alpha: 0.2),
            boxShadow: active
                ? [BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 4)]
                : null,
          ),
        ),
        const SizedBox(width: 2),
        Text(
          label,
          style: TextStyle(
            fontSize: 8,
            color: active ? color : Colors.white24,
            fontWeight: active ? FontWeight.w700 : FontWeight.normal,
          ),
        ),
      ],
    );
  }
}

class _WeightSample {
  final DateTime time;
  final int weight;
  const _WeightSample(this.time, this.weight);
}

/// Custom painter for the radial arc gauge.
class _ArcGaugePainter extends CustomPainter {
  final double value; // 0..1
  final Color color;
  final Color bgColor;

  _ArcGaugePainter({
    required this.value,
    required this.color,
    required this.bgColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 2;
    const startAngle = 2.3562; // 135° in radians
    const sweepFull = 4.7124; // 270° arc

    // Background arc
    final bgPaint = Paint()
      ..color = bgColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      sweepFull,
      false,
      bgPaint,
    );

    // Value arc with gradient
    if (value > 0) {
      final valuePaint = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 3
        ..strokeCap = StrokeCap.round;

      // Create gradient shader
      final gradient = SweepGradient(
        startAngle: startAngle,
        endAngle: startAngle + sweepFull * value,
        colors: [
          const Color(0xFF00E5FF),
          color,
        ],
      );
      valuePaint.shader = gradient.createShader(
        Rect.fromCircle(center: center, radius: radius),
      );

      canvas.drawArc(
        Rect.fromCircle(center: center, radius: radius),
        startAngle,
        sweepFull * value,
        false,
        valuePaint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _ArcGaugePainter oldDelegate) =>
      oldDelegate.value != value || oldDelegate.color != color;
}
