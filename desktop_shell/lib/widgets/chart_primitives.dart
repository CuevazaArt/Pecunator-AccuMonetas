import 'dart:math' as math;
import 'package:flutter/material.dart';

/// Single time-series data point used by all sparkline charts.
class ChartSample {
  final DateTime time;
  final double value;
  const ChartSample(this.time, this.value);
}

/// Reusable sparkline painter for all mini charts.
///
/// Renders a gradient-filled sparkline with optional threshold lines
/// (for weight/order rate percentage reference).
class SparklinePainter extends CustomPainter {
  final List<ChartSample> data;
  final double? maxY;
  final Color color;
  final bool fuseTripped;

  SparklinePainter({
    required this.data,
    this.maxY,
    required this.color,
    required this.fuseTripped,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (data.length < 2) return;

    final effectiveMaxY =
        maxY ?? data.map((d) => d.value).reduce(math.max) * 1.1;
    final effectiveMinY = maxY != null
        ? 0.0
        : data.map((d) => d.value).reduce(math.min) * 0.95;
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
  bool shouldRepaint(covariant SparklinePainter old) =>
      old.data.length != data.length || old.color != color ||
      (data.isNotEmpty && old.data.isNotEmpty && old.data.last.value != data.last.value);
}
