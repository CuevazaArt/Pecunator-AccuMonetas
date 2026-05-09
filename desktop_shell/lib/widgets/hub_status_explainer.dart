import 'package:flutter/material.dart';

/// Displays a human-readable explanation of a bot's current decision,
/// including why it is WAITing, what thresholds need to be hit, and
/// the state of open orders.
///
/// This widget helps operators quickly understand _why_ the hub
/// is or isn't placing new orders without reading raw JSON.
class HubStatusExplainer extends StatelessWidget {
  final Map<String, dynamic> dorothyReport;
  final Map<String, dynamic> elphabaReport;
  final bool fuseTripped;
  final bool budgetBlocked;

  const HubStatusExplainer({
    super.key,
    required this.dorothyReport,
    required this.elphabaReport,
    this.fuseTripped = false,
    this.budgetBlocked = false,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: const Color(0xFF0A1628),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header
          Row(
            children: [
              Icon(Icons.info_outline, size: 12, color: Colors.cyanAccent.withValues(alpha: 0.7)),
              const SizedBox(width: 4),
              Text(
                'HUB STATUS',
                style: TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 1.2,
                  color: Colors.cyanAccent.withValues(alpha: 0.7),
                ),
              ),
              const Spacer(),
              _systemChip(fuseTripped, budgetBlocked),
            ],
          ),
          const SizedBox(height: 6),
          // Dorothy + Elphaba explanations side by side
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: _botExplanation(
                  'Dorothy',
                  Colors.greenAccent,
                  Icons.trending_up,
                  dorothyReport,
                  isLong: true,
                ),
              ),
              Container(
                width: 1,
                height: 60,
                margin: const EdgeInsets.symmetric(horizontal: 6),
                color: Colors.white.withValues(alpha: 0.06),
              ),
              Expanded(
                child: _botExplanation(
                  'Elphaba',
                  const Color(0xFF00E676),
                  Icons.bolt,
                  elphabaReport,
                  isLong: false,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _systemChip(bool fuse, bool budget) {
    if (fuse) {
      return _chip('FUSE TRIPPED', const Color(0xFFFF1744));
    }
    if (budget) {
      return _chip('BUDGET BLOCKED', const Color(0xFFFF9100));
    }
    return _chip('SYSTEMS OK', const Color(0xFF00E676));
  }

  Widget _chip(String text, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(3),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 7,
          fontWeight: FontWeight.w800,
          color: color,
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  Widget _botExplanation(
    String name,
    Color color,
    IconData icon,
    Map<String, dynamic> report, {
    required bool isLong,
  }) {
    if (report.isEmpty) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _botHeader(name, color, icon),
          const SizedBox(height: 4),
          Text(
            'Sin datos — bot detenido o sin ciclos',
            style: TextStyle(fontSize: 8, color: Colors.white.withValues(alpha: 0.3), fontStyle: FontStyle.italic),
          ),
        ],
      );
    }

    final decision = '${report['decision'] ?? '—'}';
    final marketPrice = double.tryParse('${report['market_price'] ?? 0}') ?? 0;
    final entryThreshold = double.tryParse('${report['entry_threshold_price'] ?? 0}') ?? 0;
    final activeRungs = report['active_rungs'] ?? 0;
    final maxRungs = report['max_rungs'] ?? 3;
    final hasAnchor = report['has_sell_limit_anchor'] == true || report['has_buy_limit_anchor'] == true;
    final anchorPrice = double.tryParse('${report['sell_anchor_price'] ?? report['buy_anchor_price'] ?? 0}') ?? 0;

    // Calculate distance to next entry
    final distancePct = marketPrice > 0 && entryThreshold > 0
        ? ((marketPrice - entryThreshold) / marketPrice * 100).abs()
        : 0.0;

    // Build explanation
    final explanation = _buildExplanation(
      decision: decision,
      isLong: isLong,
      marketPrice: marketPrice,
      entryThreshold: entryThreshold,
      distancePct: distancePct,
      activeRungs: activeRungs,
      maxRungs: maxRungs,
      hasAnchor: hasAnchor,
      anchorPrice: anchorPrice,
    );

    final decColor = decision == 'WAIT'
        ? Colors.amber
        : decision.contains('BUY')
            ? const Color(0xFF00E676)
            : decision.contains('SELL')
                ? const Color(0xFFFF1744)
                : Colors.white38;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _botHeader(name, color, icon),
        const SizedBox(height: 3),
        // Decision badge
        Row(
          children: [
            _chip(decision, decColor),
            const SizedBox(width: 4),
            Text(
              '$activeRungs/$maxRungs rungs',
              style: const TextStyle(fontSize: 8, fontFamily: 'monospace', color: Colors.white38),
            ),
          ],
        ),
        const SizedBox(height: 3),
        // Price info
        Row(
          children: [
            Text(
              '\$${marketPrice.toStringAsFixed(4)}',
              style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w800, fontFamily: 'monospace', color: Colors.white70),
            ),
            const SizedBox(width: 4),
            if (entryThreshold > 0)
              Text(
                '→ \$${entryThreshold.toStringAsFixed(4)} (${distancePct.toStringAsFixed(1)}%)',
                style: TextStyle(fontSize: 8, fontFamily: 'monospace', color: Colors.white.withValues(alpha: 0.4)),
              ),
          ],
        ),
        const SizedBox(height: 3),
        // Explanation text
        Text(
          explanation,
          style: TextStyle(fontSize: 8, color: Colors.white.withValues(alpha: 0.5), height: 1.3),
        ),
      ],
    );
  }

  Widget _botHeader(String name, Color color, IconData icon) {
    return Row(
      children: [
        Icon(icon, size: 10, color: color),
        const SizedBox(width: 3),
        Text(
          name,
          style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: color),
        ),
      ],
    );
  }

  String _buildExplanation({
    required String decision,
    required bool isLong,
    required double marketPrice,
    required double entryThreshold,
    required double distancePct,
    required int activeRungs,
    required int maxRungs,
    required bool hasAnchor,
    required double anchorPrice,
  }) {
    if (decision == 'WAIT') {
      final parts = <String>[];
      if (hasAnchor) {
        final anchorType = isLong ? 'SELL limit' : 'BUY limit';
        parts.add('Take-profit ($anchorType) en \$${anchorPrice.toStringAsFixed(3)}');
      }
      if (activeRungs >= maxRungs) {
        parts.add('Máximo de rungs alcanzado ($maxRungs/$maxRungs)');
      } else if (entryThreshold > 0) {
        final direction = isLong ? 'baje' : 'suba';
        parts.add('Esperando que $direction a \$${entryThreshold.toStringAsFixed(4)} (-${distancePct.toStringAsFixed(1)}%) para siguiente rung');
      }
      return parts.isEmpty ? 'Esperando condiciones de mercado' : parts.join('\n');
    }
    return 'Ejecutando: $decision';
  }
}
