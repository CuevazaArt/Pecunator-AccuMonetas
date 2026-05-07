import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';

/// Market Intelligence page — 24h activity heatmap, macro calendar,
/// geopolitical risk factors, and Fear & Greed index.
///
/// ⚠️ DISCLAIMER: This page provides CONTEXTUAL information only.
/// It is NOT wired to bot execution decisions. Data is curated/static
/// and should be used as a human decision-aid, not as operative signals.
class MarketEventsPage extends StatefulWidget {
  final EngineApi api;
  const MarketEventsPage({super.key, required this.api});

  @override
  State<MarketEventsPage> createState() => _MarketEventsPageState();
}

class _MarketEventsPageState extends State<MarketEventsPage> {
  Timer? _timer;
  bool _loading = false;
  String _error = '';

  // Data
  Map<String, dynamic> _summary = {};
  List<dynamic> _calendar = [];
  List<dynamic> _heatmap = [];
  List<dynamic> _geoFactors = [];
  List<dynamic> _fearGreed = [];
  int _currentHourUtc = 0;
  String _currentSession = '';
  double _currentActivityScore = 0;
  String _activityRec = '';

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_loading) return;
    setState(() { _loading = true; _error = ''; });
    try {
      final results = await Future.wait([
        widget.api.eventsSummary(),
        widget.api.eventsCalendar(),
        widget.api.eventsHeatmap(),
        widget.api.eventsGeopolitical(),
        widget.api.eventsFearGreed(),
      ]);
      if (!mounted) return;
      setState(() {
        _summary = results[0];
        _calendar = (results[1]['events'] as List?) ?? [];
        _heatmap = (results[2]['hours'] as List?) ?? [];
        _currentHourUtc = (results[2]['current_hour_utc'] as int?) ?? 0;
        _currentSession = (results[2]['current_session'] ?? '').toString();
        _currentActivityScore = (results[2]['current_activity_score'] is num)
            ? (results[2]['current_activity_score'] as num).toDouble() : 0;
        _activityRec = (results[2]['recommendation'] ?? '').toString();
        _geoFactors = (results[3]['factors'] as List?) ?? [];
        _fearGreed = (results[4]['entries'] as List?) ?? [];
      });
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Color _activityColor(double score) {
    if (score >= 0.85) return const Color(0xFFFF1744);
    if (score >= 0.65) return const Color(0xFFFF9100);
    if (score >= 0.45) return const Color(0xFFFFEA00);
    return const Color(0xFF00E5FF);
  }

  Color _impactColor(String impact) {
    switch (impact) {
      case 'critical': return Colors.redAccent;
      case 'high': return Colors.orangeAccent;
      case 'medium': return Colors.amberAccent;
      default: return Colors.grey;
    }
  }

  Color _fgColor(int value) {
    if (value >= 75) return Colors.greenAccent;
    if (value >= 55) return const Color(0xFF00E676);
    if (value >= 45) return Colors.amberAccent;
    if (value >= 25) return Colors.orangeAccent;
    return Colors.redAccent;
  }

  @override
  Widget build(BuildContext context) {
    final fgValue = _summary['fear_greed_value'] as int?;
    final fgLabel = (_summary['fear_greed_label'] ?? '—').toString();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Market Intelligence'),
        automaticallyImplyLeading: false,
        actions: [
          IconButton(
            onPressed: _loading ? null : _refresh,
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
            if (_loading) const LinearProgressIndicator(),
            if (_error.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(_error, style: const TextStyle(color: Colors.redAccent, fontSize: 12)),
              ),

            // ── Contextual disclaimer ──
            Card(
              color: Colors.amber.withValues(alpha: 0.08),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                child: Row(
                  children: [
                    Icon(Icons.info_outline, size: 14, color: Colors.amber.shade300),
                    const SizedBox(width: 6),
                    Expanded(child: Text(
                      'Info contextual — no conectada a decisiones de ejecución de bots. Datos curados y estadísticos.',
                      style: TextStyle(fontSize: 10, color: Colors.amber.shade300),
                    )),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 4),

            // ── Top KPI Row ──
            Row(
              children: [
                _kpiCard('Sesión', _currentSession, _activityColor(_currentActivityScore)),
                _kpiCard('Actividad', '${(_currentActivityScore * 100).toStringAsFixed(0)}%',
                    _activityColor(_currentActivityScore)),
                _kpiCard('Hora UTC', '$_currentHourUtc:00', Colors.cyanAccent),
                _kpiCard('Fear & Greed',
                    fgValue != null ? '$fgValue ($fgLabel)' : '—',
                    fgValue != null ? _fgColor(fgValue) : Colors.grey),
              ],
            ),
            const SizedBox(height: 4),
            // Activity recommendation
            if (_activityRec.isNotEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(10),
                  child: Row(
                    children: [
                      Icon(Icons.lightbulb, size: 16, color: _activityColor(_currentActivityScore)),
                      const SizedBox(width: 8),
                      Expanded(child: Text(_activityRec, style: const TextStyle(fontSize: 12))),
                    ],
                  ),
                ),
              ),
            const SizedBox(height: 8),

            // ── 24h Activity Heatmap ──
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Mapa de calor 24h — Actividad estadística por hora',
                        style: TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    SizedBox(
                      height: 120,
                      child: _heatmap.isEmpty
                          ? const Center(child: Text('Cargando...'))
                          : CustomPaint(
                              size: const Size(double.infinity, 120),
                              painter: _HeatmapPainter(
                                hours: _heatmap,
                                currentHour: _currentHourUtc,
                              ),
                            ),
                    ),
                    const SizedBox(height: 4),
                    // Legend
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        _legendDot('Baja (<45%)', const Color(0xFF00E5FF)),
                        _legendDot('Moderada (45-65%)', const Color(0xFFFFEA00)),
                        _legendDot('Alta (65-85%)', const Color(0xFFFF9100)),
                        _legendDot('Pico (85%+)', const Color(0xFFFF1744)),
                        _legendDot('Ahora', Colors.white),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),

            // ── Two columns: Calendar + Fear & Greed ──
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Economic Calendar
                Expanded(
                  flex: 3,
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Calendario económico macro',
                              style: TextStyle(fontWeight: FontWeight.w600)),
                          const SizedBox(height: 8),
                          ..._calendar.map((e) {
                            final event = Map<String, dynamic>.from(e as Map);
                            final impact = (event['impact'] ?? 'medium').toString();
                            final hours = (event['typical_hours_utc'] as List?)
                                ?.map((h) => '${h}h UTC').join('-') ?? '';
                            return Padding(
                              padding: const EdgeInsets.symmetric(vertical: 3),
                              child: Row(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Container(
                                    width: 8, height: 8,
                                    margin: const EdgeInsets.only(top: 4, right: 6),
                                    decoration: BoxDecoration(
                                      shape: BoxShape.circle,
                                      color: _impactColor(impact),
                                    ),
                                  ),
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Text(
                                          '${event['event']} · ${event['frequency']}',
                                          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                                        ),
                                        Text(
                                          '${event['description']} · $hours',
                                          style: TextStyle(fontSize: 10,
                                              color: Theme.of(context).colorScheme.onSurfaceVariant),
                                        ),
                                      ],
                                    ),
                                  ),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(
                                      color: _impactColor(impact).withValues(alpha: 0.2),
                                      borderRadius: BorderRadius.circular(4),
                                    ),
                                    child: Text(impact.toUpperCase(),
                                        style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800,
                                            color: _impactColor(impact))),
                                  ),
                                ],
                              ),
                            );
                          }),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                // Fear & Greed history
                Expanded(
                  flex: 1,
                  child: Card(
                    child: Padding(
                      padding: const EdgeInsets.all(12),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Fear & Greed (7d)',
                              style: TextStyle(fontWeight: FontWeight.w600)),
                          const SizedBox(height: 8),
                          if (_fearGreed.isEmpty)
                            const Text('Sin datos', style: TextStyle(fontSize: 12))
                          else
                            ..._fearGreed.take(7).map((e) {
                              final entry = Map<String, dynamic>.from(e as Map);
                              final val = int.tryParse(entry['value']?.toString() ?? '') ?? 0;
                              final label = (entry['value_classification'] ?? '').toString();
                              final ts = entry['timestamp']?.toString() ?? '';
                              final date = ts.isNotEmpty
                                  ? DateTime.fromMillisecondsSinceEpoch(
                                      int.tryParse(ts) != null ? int.parse(ts) * 1000 : 0)
                                      .toString().substring(0, 10)
                                  : '';
                              return Padding(
                                padding: const EdgeInsets.symmetric(vertical: 2),
                                child: Row(
                                  children: [
                                    SizedBox(
                                      width: 30,
                                      child: Text('$val',
                                          style: TextStyle(
                                              fontFamily: 'monospace',
                                              fontWeight: FontWeight.w800,
                                              color: _fgColor(val))),
                                    ),
                                    Expanded(
                                      child: ClipRRect(
                                        borderRadius: BorderRadius.circular(2),
                                        child: LinearProgressIndicator(
                                          minHeight: 8,
                                          value: val / 100,
                                          valueColor: AlwaysStoppedAnimation(_fgColor(val)),
                                          backgroundColor: Colors.white10,
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 4),
                                    Text(date, style: const TextStyle(fontSize: 9, fontFamily: 'monospace')),
                                  ],
                                ),
                              );
                            }),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // ── Geopolitical Risk Factors ──
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Factores geopolíticos activos',
                        style: TextStyle(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    ..._geoFactors.map((e) {
                      final f = Map<String, dynamic>.from(e as Map);
                      final impact = (f['impact'] ?? 'medium').toString();
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 3),
                        child: Row(
                          children: [
                            Icon(Icons.public, size: 14, color: _impactColor(impact)),
                            const SizedBox(width: 6),
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text('${f['factor']}',
                                      style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
                                  Text(
                                    '${f['direction']} · Activos: ${(f['assets_affected'] as List?)?.join(', ') ?? '?'} · Monitor: ${f['monitor']}',
                                    style: TextStyle(fontSize: 10,
                                        color: Theme.of(context).colorScheme.onSurfaceVariant),
                                  ),
                                ],
                              ),
                            ),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                              decoration: BoxDecoration(
                                color: _impactColor(impact).withValues(alpha: 0.2),
                                borderRadius: BorderRadius.circular(4),
                              ),
                              child: Text(impact.toUpperCase(),
                                  style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800,
                                      color: _impactColor(impact))),
                            ),
                          ],
                        ),
                      );
                    }),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _kpiCard(String label, String value, Color valueColor) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Column(
            children: [
              Text(label, style: const TextStyle(fontSize: 10)),
              const SizedBox(height: 2),
              Text(value,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontFamily: 'monospace',
                    fontWeight: FontWeight.w800,
                    fontSize: 13,
                    color: valueColor,
                  )),
            ],
          ),
        ),
      ),
    );
  }

  Widget _legendDot(String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 6, height: 6, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 3),
        Text(label, style: TextStyle(fontSize: 8, color: color)),
      ],
    );
  }
}

/// Paints a 24h heatmap bar chart.
class _HeatmapPainter extends CustomPainter {
  final List<dynamic> hours;
  final int currentHour;

  _HeatmapPainter({required this.hours, required this.currentHour});

  @override
  void paint(Canvas canvas, Size size) {
    if (hours.isEmpty) return;
    final barW = size.width / 24;
    final maxH = size.height - 20; // leave room for labels

    for (int i = 0; i < hours.length && i < 24; i++) {
      final h = Map<String, dynamic>.from(hours[i] as Map);
      final score = (h['activity_score'] is num) ? (h['activity_score'] as num).toDouble() : 0.0;
      final barH = maxH * score;
      final x = i * barW;
      final y = maxH - barH;

      Color barColor;
      if (score >= 0.85) {
        barColor = const Color(0xFFFF1744);
      } else if (score >= 0.65) {
        barColor = const Color(0xFFFF9100);
      } else if (score >= 0.45) {
        barColor = const Color(0xFFFFEA00);
      } else {
        barColor = const Color(0xFF00E5FF);
      }

      // Highlight current hour
      if (i == currentHour) {
        canvas.drawRect(
          Rect.fromLTWH(x, 0, barW, maxH),
          Paint()..color = Colors.white.withValues(alpha: 0.08),
        );
      }

      final rrect = RRect.fromRectAndRadius(
        Rect.fromLTWH(x + 1, y, barW - 2, barH),
        const Radius.circular(2),
      );
      canvas.drawRRect(rrect, Paint()..color = barColor.withValues(alpha: 0.7));

      // Current hour marker
      if (i == currentHour) {
        canvas.drawRRect(
          rrect,
          Paint()
            ..color = Colors.white
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.5,
        );
      }

      // Hour label
      if (i % 3 == 0) {
        final tp = TextPainter(
          text: TextSpan(
            text: '${i}h',
            style: TextStyle(
              color: i == currentHour ? Colors.white : Colors.white38,
              fontSize: 8,
              fontWeight: i == currentHour ? FontWeight.bold : FontWeight.normal,
            ),
          ),
          textDirection: TextDirection.ltr,
        )..layout();
        tp.paint(canvas, Offset(x + barW / 2 - tp.width / 2, maxH + 4));
      }
    }
  }

  @override
  bool shouldRepaint(covariant _HeatmapPainter old) => true;
}
