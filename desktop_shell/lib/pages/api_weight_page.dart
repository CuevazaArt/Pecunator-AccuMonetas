import 'dart:async';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../api_client.dart';

/// Dedicated API Weight Monitor page with oscillator chart, crest detection,
/// and utilization window analysis.
class ApiWeightMonitorPage extends StatefulWidget {
  final EngineApi api;
  const ApiWeightMonitorPage({super.key, required this.api});

  @override
  State<ApiWeightMonitorPage> createState() => _ApiWeightMonitorPageState();
}

class _ApiWeightMonitorPageState extends State<ApiWeightMonitorPage> {
  Timer? _timer;
  int? _weightUsed;
  int _weightLimit = 6000;
  bool _gatewayRunning = false;
  bool _fuseTripped = false;
  String _fuseReason = '';
  double _fuseRemainingSec = 0;
  int _fuseStreak = 0;
  int _fuseNextCooldown = 300;
  int _fuseCurrentCooldown = 300;

  // Oscillator history
  final List<_Sample> _history = [];
  // Crest tracking
  int _crestCount = 0;
  double _peakWeight = 0;
  double _avgWeight = 0;
  double _minWeight = double.infinity;

  // ── Configurable refresh options ──
  // Polling intervals in milliseconds
  static const Map<String, int> _pollOptions = {
    '200ms': 200,
    '300ms': 300,
    '500ms': 500,
    '1s': 1000,
    '2s': 2000,
    '5s': 5000,
    '10s': 10000,
  };
  // Time window options in seconds
  static const Map<String, int> _windowOptions = {
    '30s': 30,
    '1 min': 60,
    '2 min': 120,
    '5 min': 300,
    '10 min': 600,
    '15 min': 900,
  };
  String _selectedPoll = '500ms';
  String _selectedWindow = '1 min';

  int get _pollMs => _pollOptions[_selectedPoll] ?? 2000;
  int get _windowSec => _windowOptions[_selectedWindow] ?? 60;
  int get _maxSamples => (_windowSec * 1000 / _pollMs).ceil();

  @override
  void initState() {
    super.initState();
    _refresh();
    _startTimer();
  }

  void _startTimer() {
    _timer?.cancel();
    _timer = Timer.periodic(Duration(milliseconds: _pollMs), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
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

      // Fuse status
      bool fuseTripped = false;
      String fuseReason = '';
      double fuseRemaining = 0;
      int streak = 0;
      int nextCd = 300;
      int currentCd = 300;
      try {
        final fuse = await widget.api.apiFuseStatus();
        fuseTripped = fuse['tripped'] == true;
        fuseReason = (fuse['reason'] ?? '').toString();
        fuseRemaining = (fuse['remaining_cooldown_sec'] is num)
            ? (fuse['remaining_cooldown_sec'] as num).toDouble()
            : 0;
        streak = (fuse['consecutive_streak'] is num)
            ? (fuse['consecutive_streak'] as num).toInt()
            : 0;
        nextCd = (fuse['next_cooldown_sec'] is num)
            ? (fuse['next_cooldown_sec'] as num).toInt()
            : 300;
        currentCd = (fuse['current_cooldown_sec'] is num)
            ? (fuse['current_cooldown_sec'] as num).toInt()
            : 300;
      } catch (_) {}

      // Update history
      if (used != null) {
        _history.add(_Sample(DateTime.now(), used, limit));
        if (_history.length > _maxSamples) {
          _history.removeRange(0, _history.length - _maxSamples);
        }
        // Crest detection: count peaks above 60% in last window
        _crestCount = 0;
        _peakWeight = 0;
        double sum = 0;
        _minWeight = double.infinity;
        for (int i = 1; i < _history.length - 1; i++) {
          final prev = _history[i - 1].weight;
          final cur = _history[i].weight;
          final next = _history[i + 1].weight;
          final pct = cur / (_history[i].limit > 0 ? _history[i].limit : 6000);
          if (cur > prev && cur > next && pct > 0.60) {
            _crestCount++;
          }
          if (cur > _peakWeight) _peakWeight = cur.toDouble();
          if (cur < _minWeight) _minWeight = cur.toDouble();
          sum += cur;
        }
        if (_history.isNotEmpty) {
          final last = _history.last;
          if (last.weight > _peakWeight) _peakWeight = last.weight.toDouble();
          if (last.weight < _minWeight) _minWeight = last.weight.toDouble();
          sum += last.weight;
        }
        _avgWeight = _history.isEmpty ? 0 : sum / _history.length;
      }

      if (!mounted) return;
      setState(() {
        _weightUsed = used;
        _weightLimit = limit <= 0 ? 6000 : limit;
        _gatewayRunning = gw;
        _fuseTripped = fuseTripped;
        _fuseReason = fuseReason;
        _fuseRemainingSec = fuseRemaining;
        _fuseStreak = streak;
        _fuseNextCooldown = nextCd;
        _fuseCurrentCooldown = currentCd;
      });
    } catch (_) {}
  }

  Color _zoneColor(double pct) {
    if (pct >= 0.80) return const Color(0xFFFF1744);
    if (pct >= 0.60) return const Color(0xFFFF9100);
    if (pct >= 0.40) return const Color(0xFFFFEA00);
    if (pct >= 0.15) return const Color(0xFF00E676);
    return const Color(0xFF00E5FF);
  }

  double get _ptsPerMin {
    if (_history.length < 2) return 0;
    int totalDelta = 0;
    for (int i = 1; i < _history.length; i++) {
      final d = _history[i].weight - _history[i - 1].weight;
      if (d > 0) totalDelta += d;
    }
    final mins = _history.last.time.difference(_history.first.time).inMilliseconds / 60000.0;
    return mins < 0.1 ? 0 : totalDelta / mins;
  }

  double get _utilizationPct {
    if (_history.isEmpty) return 0;
    // What % of the limit window is being used on average
    return _avgWeight / _weightLimit;
  }

  // Under-utilized windows: periods where weight < 20% for >30s
  int get _underutilizedWindows {
    int count = 0;
    int streak = 0;
    for (final s in _history) {
      final pct = s.weight / (s.limit > 0 ? s.limit : 6000);
      if (pct < 0.20) {
        streak++;
        if (streak >= 15) { // 15 samples × 2s = 30s
          count++;
          streak = 0;
        }
      } else {
        streak = 0;
      }
    }
    return count;
  }

  @override
  Widget build(BuildContext context) {
    final pct = _weightUsed != null && _weightLimit > 0
        ? (_weightUsed! / _weightLimit).clamp(0.0, 1.0)
        : 0.0;
    final color = _zoneColor(pct);
    final ppm = _ptsPerMin;

    return Scaffold(
      appBar: AppBar(
        title: const Text('API Weight Monitor'),
        automaticallyImplyLeading: false,
        actions: [
          // Fuse reset
          if (_fuseTripped)
            TextButton.icon(
              onPressed: () async {
                try {
                  await widget.api.apiFuseReset();
                  await _refresh();
                } catch (_) {}
              },
              icon: const Icon(Icons.restart_alt, size: 16, color: Colors.redAccent),
              label: const Text('Reset Fuse', style: TextStyle(color: Colors.redAccent)),
            ),
          // Polling rate selector
          _dropdownChip(
            icon: Icons.speed,
            value: _selectedPoll,
            items: _pollOptions.keys.toList(),
            onChanged: (v) {
              setState(() { _selectedPoll = v; });
              _startTimer();
            },
          ),
          const SizedBox(width: 4),
          // Time window selector
          _dropdownChip(
            icon: Icons.timer,
            value: _selectedWindow,
            items: _windowOptions.keys.toList(),
            onChanged: (v) {
              setState(() {
                _selectedWindow = v;
                _history.clear();
              });
            },
          ),
          const SizedBox(width: 4),
          IconButton(
            onPressed: _refresh,
            tooltip: 'Refrescar',
            icon: const Icon(Icons.refresh, size: 18),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── KPI Row ──
            Row(
              children: [
                _kpi('Peso actual', '${_weightUsed ?? "—"} / $_weightLimit', color),
                _kpi('Uso %', '${(pct * 100).toStringAsFixed(1)}%', color),
                _kpi('pts/min', ppm.toStringAsFixed(1),
                    ppm > 50 ? Colors.redAccent : ppm > 10 ? Colors.orangeAccent : Colors.cyanAccent),
                _kpi('Gateway', _gatewayRunning ? 'ON' : 'OFF',
                    _gatewayRunning ? Colors.greenAccent : Colors.grey),
                _kpi('Fusible', _fuseTripped ? 'TRIP' : 'OK',
                    _fuseTripped ? Colors.redAccent : Colors.cyanAccent),
              ],
            ),
            const SizedBox(height: 8),
            // ── Analysis Row ──
            Row(
              children: [
                _kpi('Pico', _peakWeight.toStringAsFixed(0), Colors.orangeAccent),
                _kpi('Mínimo', _minWeight == double.infinity ? '—' : _minWeight.toStringAsFixed(0), Colors.cyanAccent),
                _kpi('Promedio', _avgWeight.toStringAsFixed(0), Colors.blueAccent),
                _kpi('Crestas >60%', '$_crestCount', _crestCount > 3 ? Colors.redAccent : Colors.greenAccent),
                _kpi('Ventanas <20%', '$_underutilizedWindows',
                    _underutilizedWindows > 0 ? Colors.greenAccent : Colors.grey),
              ],
            ),
            const SizedBox(height: 8),
            // ── Utilization bar ──
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Text('Utilización promedio del window 1m',
                            style: TextStyle(fontWeight: FontWeight.w600)),
                        const Spacer(),
                        Text('${(_utilizationPct * 100).toStringAsFixed(1)}%',
                            style: TextStyle(
                                fontFamily: 'monospace',
                                fontWeight: FontWeight.w800,
                                color: _zoneColor(_utilizationPct))),
                      ],
                    ),
                    const SizedBox(height: 6),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(4),
                      child: LinearProgressIndicator(
                        minHeight: 10,
                        value: _utilizationPct.clamp(0, 1),
                        valueColor: AlwaysStoppedAnimation(_zoneColor(_utilizationPct)),
                        backgroundColor: Colors.white10,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        _thresholdLabel('Safe 0-40%', const Color(0xFF00E5FF)),
                        _thresholdLabel('Caution 40-60%', const Color(0xFFFFEA00)),
                        _thresholdLabel('Warning 60-80%', const Color(0xFFFF9100)),
                        _thresholdLabel('Critical 80%+', const Color(0xFFFF1744)),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            // ── Oscillator Chart ──
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text('Oscilador de peso API (últimos $_selectedWindow)',
                            style: const TextStyle(fontWeight: FontWeight.w600)),
                        const Spacer(),
                        Text('${_history.length}/$_maxSamples @ $_selectedPoll',
                            style: const TextStyle(fontSize: 11, fontFamily: 'monospace')),
                      ],
                    ),
                    const SizedBox(height: 8),
                    SizedBox(
                      height: 200,
                      child: _history.length < 2
                          ? const Center(child: Text('Recopilando datos...', style: TextStyle(color: Colors.grey)))
                          : CustomPaint(
                              size: const Size(double.infinity, 200),
                              painter: _OscillatorPainter(
                                samples: List.unmodifiable(_history),
                                limit: _weightLimit,
                              ),
                            ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            // ── Fixed-scale overview chart (0-6000) ──
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Text('Vista global (0-100% capacidad)',
                            style: TextStyle(fontWeight: FontWeight.w600)),
                        const Spacer(),
                        Text('${_weightUsed ?? 0}/$_weightLimit',
                            style: const TextStyle(fontSize: 11, fontFamily: 'monospace')),
                      ],
                    ),
                    const SizedBox(height: 8),
                    SizedBox(
                      height: 120,
                      child: _history.length < 2
                          ? const Center(child: Text('...', style: TextStyle(color: Colors.grey)))
                          : CustomPaint(
                              size: const Size(double.infinity, 120),
                              painter: _FixedScalePainter(
                                samples: List.unmodifiable(_history),
                                limit: _weightLimit,
                              ),
                            ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            // ── Fuse Detail ──
            if (_fuseTripped || _fuseStreak > 0)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.bolt, size: 18,
                              color: _fuseTripped ? Colors.redAccent : Colors.orangeAccent),
                          const SizedBox(width: 6),
                          Text(
                            _fuseTripped ? 'FUSIBLE ACTIVADO' : 'Historial de fusible',
                            style: TextStyle(
                              fontWeight: FontWeight.w700,
                              color: _fuseTripped ? Colors.redAccent : Colors.orangeAccent,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      if (_fuseTripped && _fuseReason.isNotEmpty)
                        Text('Razón: $_fuseReason',
                            style: const TextStyle(fontSize: 12, fontFamily: 'monospace')),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          _kpi('Racha', '#$_fuseStreak',
                              _fuseStreak >= 3 ? Colors.redAccent : Colors.orangeAccent),
                          _kpi('Cooldown actual', '${_fuseCurrentCooldown}s', Colors.cyanAccent),
                          _kpi('Siguiente cooldown', '${_fuseNextCooldown}s', Colors.amberAccent),
                          if (_fuseTripped)
                            _kpi('Restante', '${_fuseRemainingSec.toStringAsFixed(0)}s', Colors.redAccent),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: 8),
            // ── Recommendations ──
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Recomendaciones', style: TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 6),
                    ..._buildRecommendations(),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  List<Widget> _buildRecommendations() {
    final recs = <Widget>[];
    final pct = _weightUsed != null ? _weightUsed! / _weightLimit : 0.0;

    if (_underutilizedWindows > 2) {
      recs.add(_recItem(Icons.check_circle, Colors.greenAccent,
          'Hay ventanas subutilizadas (<20%) — espacio para más operaciones sin riesgo de fuse.'));
    }
    if (_crestCount > 5) {
      recs.add(_recItem(Icons.warning_amber, Colors.orangeAccent,
          'Muchas crestas >60% detectadas — considerar reducir frecuencia de polling.'));
    }
    if (pct > 0.7) {
      recs.add(_recItem(Icons.dangerous, Colors.redAccent,
          'Uso cercano al límite — reducir loop_interval_sec de los bots activos.'));
    }
    if (_fuseStreak >= 3) {
      recs.add(_recItem(Icons.bolt, Colors.redAccent,
          'Racha de fusible alta (#$_fuseStreak) — revisar configuración de bots.'));
    }
    if (pct < 0.15 && _gatewayRunning) {
      recs.add(_recItem(Icons.lightbulb, Colors.cyanAccent,
          'Uso muy bajo — hay margen amplio para añadir más bots o reducir intervalos.'));
    }
    if (recs.isEmpty) {
      recs.add(_recItem(Icons.thumb_up, Colors.greenAccent,
          'Operación normal. Sin alertas.'));
    }
    return recs;
  }

  Widget _recItem(IconData icon, Color color, String text) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(child: Text(text, style: const TextStyle(fontSize: 12))),
        ],
      ),
    );
  }

  Widget _kpi(String label, String value, Color valueColor) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Column(
            children: [
              Text(label, style: const TextStyle(fontSize: 10)),
              const SizedBox(height: 2),
              Text(value,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontWeight: FontWeight.w800,
                    fontSize: 14,
                    color: valueColor,
                  )),
            ],
          ),
        ),
      ),
    );
  }

  Widget _thresholdLabel(String text, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 8, height: 8, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 3),
        Text(text, style: TextStyle(fontSize: 9, color: color)),
      ],
    );
  }

  Widget _dropdownChip({
    required IconData icon,
    required String value,
    required List<String> items,
    required ValueChanged<String> onChanged,
  }) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.white10,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: Colors.cyanAccent),
          const SizedBox(width: 4),
          DropdownButton<String>(
            value: value,
            isDense: true,
            underline: const SizedBox.shrink(),
            dropdownColor: const Color(0xFF1A1A2E),
            style: const TextStyle(fontSize: 11, fontFamily: 'monospace', color: Colors.cyanAccent),
            items: items.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
            onChanged: (v) { if (v != null) onChanged(v); },
          ),
        ],
      ),
    );
  }
}

class _Sample {
  final DateTime time;
  final int weight;
  final int limit;
  const _Sample(this.time, this.weight, this.limit);
}

/// Auto-scaling oscillator painter — zooms to data range for detail.
class _OscillatorPainter extends CustomPainter {
  final List<_Sample> samples;
  final int limit;

  _OscillatorPainter({required this.samples, required this.limit});

  @override
  void paint(Canvas canvas, Size size) {
    if (samples.length < 2) return;
    final effectiveLimit = limit > 0 ? limit : 6000;

    // Auto-scale range
    int dataMin = samples.first.weight;
    int dataMax = samples.first.weight;
    for (final s in samples) {
      if (s.weight < dataMin) dataMin = s.weight;
      if (s.weight > dataMax) dataMax = s.weight;
    }
    final range = (dataMax - dataMin).clamp(1, effectiveLimit);
    final padding = (range * 0.25).ceil().clamp(50, effectiveLimit ~/ 2);
    final viewMin = (dataMin - padding).clamp(0, effectiveLimit);
    final viewMax = (dataMax + padding).clamp(1, effectiveLimit);
    final viewRange = (viewMax - viewMin).clamp(1, effectiveLimit);

    double weightToY(double w) {
      final normalized = ((w - viewMin) / viewRange).clamp(0.0, 1.0);
      return size.height * (1.0 - normalized);
    }

    // Zone backgrounds (mapped to auto-scaled range)
    final zones = [
      (0.0, 0.40, const Color(0x0D00E5FF)),
      (0.40, 0.60, const Color(0x0DFFEA00)),
      (0.60, 0.80, const Color(0x0DFF9100)),
      (0.80, 1.0, const Color(0x18FF1744)),
    ];
    for (final (lo, hi, color) in zones) {
      final zoneBottomW = effectiveLimit * lo;
      final zoneTopW = effectiveLimit * hi;
      if (zoneTopW < viewMin || zoneBottomW > viewMax) continue;
      final top = weightToY(zoneTopW.clamp(viewMin.toDouble(), viewMax.toDouble()));
      final bottom = weightToY(zoneBottomW.clamp(viewMin.toDouble(), viewMax.toDouble()));
      canvas.drawRect(Rect.fromLTRB(0, top, size.width, bottom), Paint()..color = color);
    }

    // Threshold lines
    for (final threshold in [0.40, 0.60, 0.80]) {
      final threshW = effectiveLimit * threshold;
      if (threshW >= viewMin && threshW <= viewMax) {
        final y = weightToY(threshW);
        final isDanger = threshold >= 0.80;
        canvas.drawLine(Offset(0, y), Offset(size.width, y),
          Paint()
            ..color = isDanger ? const Color(0x44FF1744) : Colors.white12
            ..strokeWidth = isDanger ? 1.5 : 0.5);
        if (isDanger) {
          final tp = TextPainter(
            text: TextSpan(text: 'FUSE ${(threshold * 100).toInt()}%',
              style: const TextStyle(color: Color(0x88FF1744), fontSize: 9, fontFamily: 'monospace')),
            textDirection: TextDirection.ltr,
          )..layout();
          tp.paint(canvas, Offset(size.width - tp.width - 4, y - tp.height - 2));
        }
      }
    }

    // Data line
    final path = Path();
    final fillPath = Path();
    for (int i = 0; i < samples.length; i++) {
      final x = (i / (samples.length - 1)) * size.width;
      final y = weightToY(samples[i].weight.toDouble());
      if (i == 0) {
        path.moveTo(x, y);
        fillPath.moveTo(x, size.height);
        fillPath.lineTo(x, y);
      } else {
        path.lineTo(x, y);
        fillPath.lineTo(x, y);
      }
    }
    fillPath.lineTo(size.width, size.height);
    fillPath.close();

    final avgPct = (dataMin + dataMax) / 2 / effectiveLimit;
    final baseColor = _zoneColorStatic(avgPct);
    canvas.drawPath(fillPath, Paint()
      ..shader = LinearGradient(
        begin: Alignment.topCenter, end: Alignment.bottomCenter,
        colors: [baseColor.withValues(alpha: 0.35), baseColor.withValues(alpha: 0.03)],
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height)));
    canvas.drawPath(path, Paint()..color = baseColor..style = PaintingStyle.stroke..strokeWidth = 2..strokeJoin = StrokeJoin.round);

    // Crest markers
    for (int i = 1; i < samples.length - 1; i++) {
      final prev = samples[i - 1].weight, cur = samples[i].weight, next = samples[i + 1].weight;
      if (cur > prev && cur > next && (cur - prev > 20 || cur - next > 20)) {
        final x = (i / (samples.length - 1)) * size.width;
        final y = weightToY(cur.toDouble());
        final pctOfLimit = cur / effectiveLimit;
        final c = pctOfLimit > 0.80 ? const Color(0xFFFF1744) : pctOfLimit > 0.60 ? const Color(0xFFFF9100) : const Color(0xFF00E5FF);
        canvas.drawCircle(Offset(x, y), 3.5, Paint()..color = c);
        canvas.drawCircle(Offset(x, y), 2, Paint()..color = const Color(0xFF1A1A2E));
      }
    }

    // Trough markers
    for (int i = 1; i < samples.length - 1; i++) {
      final prev = samples[i - 1].weight, cur = samples[i].weight, next = samples[i + 1].weight;
      if (cur < prev && cur < next && (prev - cur > 20 || next - cur > 20)) {
        final x = (i / (samples.length - 1)) * size.width;
        canvas.drawCircle(Offset(x, weightToY(cur.toDouble())), 3, Paint()..color = const Color(0xFF00E676));
        canvas.drawCircle(Offset(x, weightToY(cur.toDouble())), 1.5, Paint()..color = const Color(0xFF1A1A2E));
      }
    }

    // Current dot
    if (samples.isNotEmpty) {
      final lastW = samples.last.weight.toDouble();
      final y = weightToY(lastW);
      canvas.drawCircle(Offset(size.width, y), 5, Paint()..color = _zoneColorStatic(lastW / effectiveLimit));
      canvas.drawCircle(Offset(size.width, y), 3, Paint()..color = Colors.white);
    }

    // Y-axis labels
    final textStyle = const TextStyle(color: Colors.white38, fontSize: 9, fontFamily: 'monospace');
    for (int i = 0; i <= 6; i++) {
      final frac = i / 6;
      final val = viewMin + (viewRange * frac);
      final y = size.height * (1 - frac);
      final tp = TextPainter(
        text: TextSpan(text: '${val.toInt()} (${(val / effectiveLimit * 100).toStringAsFixed(0)}%)', style: textStyle),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(canvas, Offset(2, y - tp.height / 2));
    }
  }

  static Color _zoneColorStatic(double pct) {
    if (pct >= 0.80) return const Color(0xFFFF1744);
    if (pct >= 0.60) return const Color(0xFFFF9100);
    if (pct >= 0.40) return const Color(0xFFFFEA00);
    return const Color(0xFF00E5FF);
  }

  @override
  bool shouldRepaint(covariant _OscillatorPainter old) => true;
}

/// Fixed-scale painter: always 0 to limit. Global perspective.
class _FixedScalePainter extends CustomPainter {
  final List<_Sample> samples;
  final int limit;
  _FixedScalePainter({required this.samples, required this.limit});

  @override
  void paint(Canvas canvas, Size size) {
    if (samples.length < 2) return;
    final L = limit > 0 ? limit : 6000;

    // Zone backgrounds
    for (final (lo, hi, color) in [
      (0.0, 0.40, const Color(0x1500E5FF)),
      (0.40, 0.60, const Color(0x15FFEA00)),
      (0.60, 0.80, const Color(0x15FF9100)),
      (0.80, 1.0, const Color(0x22FF1744)),
    ]) {
      canvas.drawRect(
        Rect.fromLTRB(0, size.height * (1 - hi), size.width, size.height * (1 - lo)),
        Paint()..color = color);
    }

    // Threshold lines
    final ls = const TextStyle(color: Colors.white30, fontSize: 8, fontFamily: 'monospace');
    for (final t in [0.20, 0.40, 0.60, 0.80]) {
      final y = size.height * (1 - t);
      canvas.drawLine(Offset(0, y), Offset(size.width, y),
        Paint()
          ..color = t >= 0.80 ? const Color(0x55FF1744) : Colors.white10
          ..strokeWidth = t >= 0.80 ? 1.5 : 0.5);
      final tp = TextPainter(text: TextSpan(text: '${(t * 100).toInt()}% (${(L * t).toInt()})', style: ls), textDirection: TextDirection.ltr)..layout();
      tp.paint(canvas, Offset(2, y - tp.height - 1));
    }

    // Data
    final path = Path();
    final fill = Path();
    for (int i = 0; i < samples.length; i++) {
      final x = (i / (samples.length - 1)) * size.width;
      final pct = (samples[i].weight / L).clamp(0.0, 1.0);
      final y = size.height * (1 - pct);
      if (i == 0) { path.moveTo(x, y); fill.moveTo(x, size.height); fill.lineTo(x, y); }
      else { path.lineTo(x, y); fill.lineTo(x, y); }
    }
    fill.lineTo(size.width, size.height); fill.close();

    canvas.drawPath(fill, Paint()
      ..shader = LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter,
        colors: [const Color(0xFF00E5FF).withValues(alpha: 0.25), const Color(0xFF00E5FF).withValues(alpha: 0.02)])
        .createShader(Rect.fromLTWH(0, 0, size.width, size.height)));
    canvas.drawPath(path, Paint()..color = const Color(0xFF00E5FF)..style = PaintingStyle.stroke..strokeWidth = 1.5..strokeJoin = StrokeJoin.round);

    if (samples.isNotEmpty) {
      final lastPct = (samples.last.weight / L).clamp(0.0, 1.0);
      final y = size.height * (1 - lastPct);
      canvas.drawCircle(Offset(size.width, y), 4, Paint()..color = _OscillatorPainter._zoneColorStatic(lastPct));
      canvas.drawCircle(Offset(size.width, y), 2, Paint()..color = Colors.white);
    }
  }

  @override
  bool shouldRepaint(covariant _FixedScalePainter old) => true;
}
