import 'package:flutter/material.dart';

/// Displays bot instances in a paired view — each Dorothy instance
/// matched with its Elphaba counterpart (by symbol).
///
/// Shows running/stopped status, last decision, price levels,
/// and highlights orphaned instances (no counterpart).
class BotInstancesPairedList extends StatelessWidget {
  final List<Map<String, dynamic>> dorothyBots;
  final List<Map<String, dynamic>> elphabaBots;

  const BotInstancesPairedList({
    super.key,
    required this.dorothyBots,
    required this.elphabaBots,
  });

  @override
  Widget build(BuildContext context) {
    // Build pairs by symbol
    final allSymbols = <String>{};
    final dorBySymbol = <String, Map<String, dynamic>>{};
    final elpBySymbol = <String, Map<String, dynamic>>{};

    for (final b in dorothyBots) {
      final sym = '${b['symbol'] ?? ''}';
      if (sym.isNotEmpty) {
        allSymbols.add(sym);
        dorBySymbol[sym] = b;
      }
    }
    for (final b in elphabaBots) {
      final sym = '${b['symbol'] ?? ''}';
      if (sym.isNotEmpty) {
        allSymbols.add(sym);
        elpBySymbol[sym] = b;
      }
    }

    if (allSymbols.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: const Color(0xFF0A1628),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.white.withValues(alpha: 0.04)),
        ),
        child: Center(
          child: Text(
            'Sin instancias creadas',
            style: TextStyle(fontSize: 10, color: Colors.white.withValues(alpha: 0.3)),
          ),
        ),
      );
    }

    final sortedSymbols = allSymbols.toList()..sort();

    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color(0xFF0A1628),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.04)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header
          Padding(
            padding: const EdgeInsets.only(bottom: 4, left: 2),
            child: Row(
              children: [
                Icon(Icons.compare_arrows, size: 11, color: Colors.cyanAccent.withValues(alpha: 0.6)),
                const SizedBox(width: 4),
                Text(
                  'INSTANCIAS',
                  style: TextStyle(fontSize: 8, fontWeight: FontWeight.w800, letterSpacing: 1.2, color: Colors.cyanAccent.withValues(alpha: 0.6)),
                ),
                const SizedBox(width: 6),
                Text('${sortedSymbols.length} pares', style: TextStyle(fontSize: 8, color: Colors.white.withValues(alpha: 0.25))),
              ],
            ),
          ),
          // Column headers
          _headerRow(),
          // Paired rows
          for (final sym in sortedSymbols)
            _pairRow(sym, dorBySymbol[sym], elpBySymbol[sym]),
        ],
      ),
    );
  }

  Widget _headerRow() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: const BorderRadius.vertical(top: Radius.circular(4)),
      ),
      child: Row(
        children: [
          SizedBox(width: 70, child: Text('Symbol', style: _headerStyle())),
          Expanded(child: Center(child: Text('Dorothy (LONG)', style: _headerStyle()))),
          Container(width: 1, height: 10, color: Colors.white.withValues(alpha: 0.06)),
          Expanded(child: Center(child: Text('Elphaba (SHORT)', style: _headerStyle()))),
        ],
      ),
    );
  }

  Widget _pairRow(String symbol, Map<String, dynamic>? dorothy, Map<String, dynamic>? elphaba) {
    final hasOrphan = dorothy == null || elphaba == null;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: Colors.white.withValues(alpha: 0.04))),
        color: hasOrphan ? Colors.amber.withValues(alpha: 0.03) : null,
      ),
      child: Row(
        children: [
          // Symbol label
          SizedBox(
            width: 70,
            child: Row(
              children: [
                if (hasOrphan)
                  Tooltip(
                    message: 'Sin par simétrico',
                    child: Icon(Icons.warning_amber, size: 9, color: Colors.amber.withValues(alpha: 0.7)),
                  ),
                if (hasOrphan) const SizedBox(width: 2),
                Flexible(
                  child: Text(
                    symbol.replaceAll('USDT', ''),
                    style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, fontFamily: 'monospace', color: Colors.white70),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ),
          // Dorothy side
          Expanded(child: dorothy != null ? _botCell(dorothy, isLong: true) : _emptyCell()),
          Container(width: 1, height: 22, color: Colors.white.withValues(alpha: 0.06)),
          // Elphaba side
          Expanded(child: elphaba != null ? _botCell(elphaba, isLong: false) : _emptyCell()),
        ],
      ),
    );
  }

  Widget _botCell(Map<String, dynamic> bot, {required bool isLong}) {
    final running = bot['running'] == true;
    final report = bot['last_report'] as Map? ?? {};
    final decision = '${report['decision'] ?? (running ? '...' : 'IDLE')}';
    final tag = '${bot['tag'] ?? bot['bot_id'] ?? ''}';
    final rungs = report['active_rungs'];
    final maxRungs = report['max_rungs'];

    final statusColor = running
        ? (decision == 'WAIT' ? Colors.amber : decision.contains('BUY') || decision.contains('SELL') ? const Color(0xFF00E676) : Colors.white38)
        : Colors.grey;

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Row(
        children: [
          // Running indicator
          Container(
            width: 5, height: 5,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: running ? const Color(0xFF00E676) : Colors.grey.withValues(alpha: 0.3),
              boxShadow: running ? [BoxShadow(color: const Color(0xFF00E676).withValues(alpha: 0.4), blurRadius: 3)] : null,
            ),
          ),
          const SizedBox(width: 4),
          // Tag
          Expanded(
            child: Text(tag, style: TextStyle(fontSize: 8, fontFamily: 'monospace', color: running ? Colors.white60 : Colors.white24), overflow: TextOverflow.ellipsis),
          ),
          // Decision badge
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 1),
            decoration: BoxDecoration(
              color: statusColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(2),
            ),
            child: Text(decision, style: TextStyle(fontSize: 7, fontWeight: FontWeight.w700, color: statusColor)),
          ),
          // Rungs
          if (rungs != null) ...[
            const SizedBox(width: 3),
            Text('$rungs/${maxRungs ?? '?'}', style: const TextStyle(fontSize: 7, fontFamily: 'monospace', color: Colors.white24)),
          ],
        ],
      ),
    );
  }

  Widget _emptyCell() {
    return Center(
      child: Text('— sin instancia —', style: TextStyle(fontSize: 8, fontStyle: FontStyle.italic, color: Colors.white.withValues(alpha: 0.15))),
    );
  }

  TextStyle _headerStyle() => TextStyle(fontSize: 7, fontWeight: FontWeight.w700, color: Colors.white.withValues(alpha: 0.3));
}
