import 'package:flutter/material.dart';
import '../api_client.dart';

/// Prospector panel — scans Binance symbols and ranks them by
/// oscillation score for the Dorothy ⇄ Elphaba symmetric hub.
class ProspectorPanel extends StatefulWidget {
  final EngineApi api;
  final Color accentColor;
  /// Called when user taps "Use" on a recommended symbol
  final void Function(String symbol)? onSymbolSelected;

  const ProspectorPanel({
    super.key,
    required this.api,
    this.accentColor = Colors.greenAccent,
    this.onSymbolSelected,
  });

  @override
  State<ProspectorPanel> createState() => _ProspectorPanelState();
}

class _ProspectorPanelState extends State<ProspectorPanel> {
  bool _scanning = false;
  String? _error;
  List<Map<String, dynamic>> _results = [];
  Map<String, dynamic>? _recommendation;

  @override
  void initState() {
    super.initState();
    _loadCached();
  }

  Future<void> _loadCached() async {
    try {
      final resp = await widget.api.prospectorLast();
      if (!mounted) return;
      if (resp['status'] == 'ok') {
        setState(() {
          _results = (resp['results'] as List?)?.cast<Map<String, dynamic>>() ?? [];
          _recommendation = resp['recommendation'] as Map<String, dynamic>?;
        });
      }
    } catch (_) {}
  }

  Future<void> _runScan() async {
    setState(() {
      _scanning = true;
      _error = null;
    });
    try {
      final resp = await widget.api.prospectorScan(topN: 15);
      if (!mounted) return;
      setState(() {
        _results = (resp['results'] as List?)?.cast<Map<String, dynamic>>() ?? [];
        _recommendation = resp['recommendation'] as Map<String, dynamic>?;
        _scanning = false;
      });
    } catch (e) {
      if (!mounted) return;
      final msg = '$e';
      String displayError;
      if (msg.contains('Gateway') || msg.contains('gateway') || msg.contains('400')) {
        displayError = '⚠ Gateway no conectado. Conecta tus credenciales primero.';
      } else if (msg.contains('timeout') || msg.contains('agotada')) {
        displayError = '⚠ Timeout: el scan tardó demasiado. Intenta de nuevo.';
      } else {
        displayError = msg;
      }
      setState(() {
        _scanning = false;
        _error = displayError;
      });
    }
  }

  Color _gradeColor(String grade) {
    switch (grade) {
      case 'S':
        return const Color(0xFFFFD700); // Gold
      case 'A':
        return Colors.greenAccent;
      case 'B':
        return Colors.lightGreenAccent;
      case 'C':
        return Colors.amberAccent;
      case 'D':
        return Colors.orangeAccent;
      default:
        return Colors.redAccent;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // ── Header + Scan button ─────────────────────────────────
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                widget.accentColor.withValues(alpha: 0.08),
                Colors.transparent,
              ],
            ),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: widget.accentColor.withValues(alpha: 0.2)),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(Icons.radar, size: 16, color: widget.accentColor),
                  const SizedBox(width: 6),
                  Text(
                    'PROSPECTOR',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w900,
                      color: widget.accentColor,
                      letterSpacing: 1.5,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.06),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text(
                      '~45 weight · ~8s',
                      style: TextStyle(
                        fontSize: 8,
                        color: Colors.white.withValues(alpha: 0.4),
                        fontFamily: 'monospace',
                      ),
                    ),
                  ),
                  const Spacer(),
                  SizedBox(
                    height: 28,
                    child: Tooltip(
                      message: 'Escanear Binance \u2014 Evalúa ~200 pares USDT con SEVI-M\n(~45 API weight, ~8 segundos)',
                      waitDuration: const Duration(milliseconds: 300),
                      textStyle: const TextStyle(fontSize: 11, color: Colors.white),
                      decoration: BoxDecoration(
                        color: const Color(0xEE1A1A2E),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(color: Colors.white24),
                      ),
                      child: FilledButton.icon(
                        onPressed: _scanning ? null : _runScan,
                        icon: _scanning
                            ? SizedBox(
                                width: 12,
                                height: 12,
                                child: CircularProgressIndicator(
                                  strokeWidth: 2,
                                  color: widget.accentColor,
                                ),
                              )
                            : const Icon(Icons.search, size: 14),
                        label: Text(
                          _scanning ? 'Scanning...' : 'Scan',
                          style: const TextStyle(fontSize: 10),
                        ),
                        style: FilledButton.styleFrom(
                          backgroundColor: widget.accentColor,
                          foregroundColor: Colors.black87,
                          padding: const EdgeInsets.symmetric(horizontal: 12),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              Text(
                'SEVI-M = EVI × Safety (Macro × Liquidity). Hard vetos pre-filtran activos letales.',
                style: TextStyle(
                  fontSize: 10,
                  color: Colors.white.withValues(alpha: 0.65),
                ),
              ),
            ],
          ),
        ),

        // ── Recommendation banner ────────────────────────────────
        if (_recommendation != null && !_scanning) ...[
          const SizedBox(height: 6),
          _buildRecommendation(_recommendation!),
        ],

        // ── Error ────────────────────────────────────────────────
        if (_error != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                color: Colors.redAccent.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(6),
                border: Border.all(color: Colors.redAccent.withValues(alpha: 0.3)),
              ),
              child: Text(
                _error!,
                style: const TextStyle(fontSize: 9, color: Colors.redAccent, fontFamily: 'monospace'),
              ),
            ),
          ),

        // ── Scanning indicator ───────────────────────────────────
        if (_scanning)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 12),
            child: Column(
              children: [
                LinearProgressIndicator(
                  minHeight: 2,
                  color: widget.accentColor,
                  backgroundColor: widget.accentColor.withValues(alpha: 0.1),
                ),
                const SizedBox(height: 6),
                Text(
                  'Fetching klines in batches (rate-limited)...',
                  style: TextStyle(
                    fontSize: 9,
                    color: Colors.white.withValues(alpha: 0.4),
                    fontFamily: 'monospace',
                  ),
                ),
              ],
            ),
          ),

        // ── Results table ────────────────────────────────────────
        if (_results.isNotEmpty && !_scanning) ...[
          const SizedBox(height: 6),
          ConstrainedBox(
            constraints: const BoxConstraints(maxHeight: 300),
            child: _buildResultsTable(),
          ),
        ],

        // ── Empty state ──────────────────────────────────────────
        if (_results.isEmpty && !_scanning && _error == null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 20),
            child: Center(
              child: Text(
                'Press Scan to find the best symbol for Dorothy.',
                style: TextStyle(
                  fontSize: 10,
                  color: Colors.white.withValues(alpha: 0.3),
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildRecommendation(Map<String, dynamic> rec) {
    final symbol = rec['symbol'] ?? '';
    final grade = rec['grade'] ?? 'F';
    final sei = (rec['sei_score'] ?? 0).toDouble();
    final safety = (rec['safety_multiplier'] ?? 1).toDouble();
    final evi = (rec['evi_score'] ?? 0).toDouble();
    final atr = (rec['atr_pct'] ?? 0).toDouble();
    final speed = (rec['avg_speed'] ?? 0).toDouble();
    final freq = (rec['freq_extreme'] ?? 0).toDouble();
    final chop = (rec['choppiness'] ?? 0).toDouble();
    final margin = rec['margin_eligible'] == true;
    final vol = ((rec['volume_24h_usdt'] ?? 0).toDouble() / 1e6);

    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            _gradeColor(grade).withValues(alpha: 0.12),
            Colors.transparent,
          ],
        ),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: _gradeColor(grade).withValues(alpha: 0.4)),
      ),
      child: Row(
        children: [
          // Grade badge
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: _gradeColor(grade).withValues(alpha: 0.2),
              border: Border.all(color: _gradeColor(grade), width: 2),
            ),
            child: Center(
              child: Text(
                grade,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w900,
                  color: _gradeColor(grade),
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          // Info
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.recommend, size: 12, color: Colors.amberAccent),
                    const SizedBox(width: 4),
                    Text(
                      'RECOMENDACIÓN: $symbol',
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.w800,
                        color: Colors.white,
                        letterSpacing: 0.5,
                      ),
                    ),
                    const SizedBox(width: 6),
                    if (margin)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                        decoration: BoxDecoration(
                          color: Colors.greenAccent.withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(3),
                        ),
                        child: const Text('MARGIN ✓',
                            style: TextStyle(fontSize: 7, color: Colors.greenAccent, fontWeight: FontWeight.w700)),
                      ),
                  ],
                ),
                const SizedBox(height: 3),
                Text(
                  'SEVI=${sei.toStringAsFixed(3)}  EVI=${evi.toStringAsFixed(3)}  Safety=${safety.toStringAsFixed(2)}  '
                  'ATR%=${atr.toStringAsFixed(2)}  Speed=${speed.toStringAsFixed(3)}  '
                  'Freq=${freq.toStringAsFixed(2)}  CHOP=${chop.toStringAsFixed(1)}  Vol=\$${vol.toStringAsFixed(1)}M',
                  style: TextStyle(
                    fontSize: 9,
                    fontFamily: 'monospace',
                    color: Colors.white.withValues(alpha: 0.5),
                  ),
                ),
              ],
            ),
          ),
          if (widget.onSymbolSelected != null)
            Tooltip(
              message: 'Usar $symbol \u2014 Inyecta este símbolo en Dorothy y Elphaba',
              waitDuration: const Duration(milliseconds: 300),
              child: SizedBox(
                height: 28,
                child: OutlinedButton(
                  onPressed: () => widget.onSymbolSelected!(symbol),
                  style: OutlinedButton.styleFrom(
                    side: BorderSide(color: _gradeColor(grade)),
                    foregroundColor: _gradeColor(grade),
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                  ),
                  child: const Text('Use', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700)),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildResultsTable() {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF0D1B2A),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Table header (fixed)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.03),
              borderRadius: const BorderRadius.vertical(top: Radius.circular(8)),
            ),
            child: Row(
              children: [
                _headerCell('#', 24),
                _headerCell('Symbol', 75),
                _headerCell('', 40),  // Deploy button column
                _headerCell('Grade', 35),
                _headerCell('SEVI', 42),
                _headerCell('Safety', 42),
                _headerCell('EVI', 40),
                _headerCell('ATR%', 38),
                _headerCell('Speed', 40),
                _headerCell('Freq', 35),
                _headerCell('CHOP', 35),
                _headerCell('Vol(M\$)', 45),
                _headerCell('Mgn', 30),
              ],
            ),
          ),
          // Scrollable table body
          Flexible(
            child: ListView.builder(
              shrinkWrap: true,
              padding: EdgeInsets.zero,
              itemCount: _results.length,
              itemExtent: 26,  // fixed row height for performance
              itemBuilder: (context, i) {
                final r = _results[i];
                final grade = r['grade'] ?? 'F';
                final margin = r['margin_eligible'] == true;
                final vol = ((r['volume_24h_usdt'] ?? 0).toDouble() / 1e6);

                return Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: i.isEven ? Colors.transparent : Colors.white.withValues(alpha: 0.015),
                    border: Border(
                      bottom: BorderSide(color: Colors.white.withValues(alpha: 0.03)),
                    ),
                  ),
                  child: Row(
                    children: [
                      _dataCell('${i + 1}', 24, Colors.white30),
                      _dataCell('${r['symbol']}', 75, Colors.white70, bold: true),
                      // Deploy button — inline next to symbol for easy access
                      if (widget.onSymbolSelected != null)
                        Tooltip(
                          message: 'Desplegar ${r['symbol']} en el hub simétrico',
                          waitDuration: const Duration(milliseconds: 200),
                          child: InkWell(
                            onTap: () => widget.onSymbolSelected!('${r['symbol']}'),
                            borderRadius: BorderRadius.circular(4),
                            child: Container(
                              margin: const EdgeInsets.only(right: 6),
                              padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
                              decoration: BoxDecoration(
                                color: widget.accentColor.withValues(alpha: 0.12),
                                borderRadius: BorderRadius.circular(4),
                                border: Border.all(color: widget.accentColor.withValues(alpha: 0.35)),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Icon(Icons.rocket_launch, size: 10, color: widget.accentColor.withValues(alpha: 0.9)),
                                  const SizedBox(width: 2),
                                  Text('GO', style: TextStyle(fontSize: 7, fontWeight: FontWeight.w900, color: widget.accentColor, letterSpacing: 0.5)),
                                ],
                              ),
                            ),
                          ),
                        ),
                      SizedBox(
                        width: 35,
                        child: Center(
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                            decoration: BoxDecoration(
                              color: _gradeColor(grade).withValues(alpha: 0.15),
                              borderRadius: BorderRadius.circular(3),
                              border: Border.all(color: _gradeColor(grade).withValues(alpha: 0.4)),
                            ),
                            child: Text(
                              grade,
                              style: TextStyle(
                                fontSize: 9,
                                fontWeight: FontWeight.w900,
                                color: _gradeColor(grade),
                                fontFamily: 'monospace',
                              ),
                            ),
                          ),
                        ),
                      ),
                      _dataCell((r['sei_score'] ?? 0).toDouble().toStringAsFixed(3), 42, Colors.amberAccent.withValues(alpha: 0.9)),
                      _dataCell((r['safety_multiplier'] ?? 1).toDouble().toStringAsFixed(2), 42, Colors.lightGreenAccent.withValues(alpha: 0.8)),
                      _dataCell((r['evi_score'] ?? 0).toDouble().toStringAsFixed(3), 40, Colors.amberAccent.withValues(alpha: 0.5)),
                      _dataCell((r['atr_pct'] ?? 0).toDouble().toStringAsFixed(2), 38, Colors.cyanAccent.withValues(alpha: 0.7)),
                      _dataCell((r['avg_speed'] ?? 0).toDouble().toStringAsFixed(3), 40, Colors.orangeAccent.withValues(alpha: 0.7)),
                      _dataCell((r['freq_extreme'] ?? 0).toDouble().toStringAsFixed(2), 35, Colors.purpleAccent.withValues(alpha: 0.7)),
                      _dataCell((r['choppiness'] ?? 0).toDouble().toStringAsFixed(1), 35, Colors.white54),
                      _dataCell(vol.toStringAsFixed(1), 45, Colors.white38),
                      SizedBox(
                        width: 30,
                        child: Center(
                          child: Icon(
                            margin ? Icons.check_circle : Icons.cancel,
                            size: 12,
                            color: margin ? Colors.greenAccent : Colors.redAccent.withValues(alpha: 0.4),
                          ),
                        ),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _headerCell(String text, double width) {
    return SizedBox(
      width: width,
      child: Text(
        text,
        style: TextStyle(
          fontSize: 8,
          fontWeight: FontWeight.w700,
          color: Colors.white.withValues(alpha: 0.35),
          fontFamily: 'monospace',
          letterSpacing: 0.3,
        ),
      ),
    );
  }

  Widget _dataCell(String text, double width, Color color, {bool bold = false}) {
    return SizedBox(
      width: width,
      child: Text(
        text,
        style: TextStyle(
          fontSize: 10,
          fontWeight: bold ? FontWeight.w700 : FontWeight.w400,
          color: color,
          fontFamily: 'monospace',
        ),
      ),
    );
  }
}
