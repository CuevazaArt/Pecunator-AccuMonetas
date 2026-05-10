import 'package:flutter/material.dart';

/// Ultra-compact paired bot instances list — designed to scale to
/// hundreds of rows. Shows Dorothy↔Elphaba pairs matched by symbol
/// in a dense, scrollable table format.
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
        // Only overwrite if current is not running or new is running
        if (dorBySymbol[sym]?['running'] != true) {
          dorBySymbol[sym] = b;
        }
      }
    }
    for (final b in elphabaBots) {
      final sym = '${b['symbol'] ?? ''}';
      if (sym.isNotEmpty) {
        allSymbols.add(sym);
        // Only overwrite if current is not running or new is running
        if (elpBySymbol[sym]?['running'] != true) {
          elpBySymbol[sym] = b;
        }
      }
    }

    // Sort: running pairs first, then by symbol
    final sorted = allSymbols.toList()
      ..sort((a, b) {
        final aRun = (dorBySymbol[a]?['running'] == true || elpBySymbol[a]?['running'] == true) ? 0 : 1;
        final bRun = (dorBySymbol[b]?['running'] == true || elpBySymbol[b]?['running'] == true) ? 0 : 1;
        if (aRun != bRun) return aRun.compareTo(bRun);
        return a.compareTo(b);
      });

    final runningCount = sorted.where((s) =>
        dorBySymbol[s]?['running'] == true || elpBySymbol[s]?['running'] == true).length;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFF0A1628),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: Colors.white.withValues(alpha: 0.04)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header bar
          Row(
            children: [
              Icon(Icons.compare_arrows, size: 10, color: Colors.cyanAccent.withValues(alpha: 0.5)),
              const SizedBox(width: 3),
              Text('INSTANCIAS', style: TextStyle(fontSize: 7, fontWeight: FontWeight.w800, letterSpacing: 1, color: Colors.cyanAccent.withValues(alpha: 0.5))),
              const SizedBox(width: 6),
              Text('$runningCount/${sorted.length} activas', style: TextStyle(fontSize: 7, color: Colors.white.withValues(alpha: 0.2))),
              const Spacer(),
              // Column legend
              _legend('D', Colors.greenAccent),
              const SizedBox(width: 6),
              _legend('E', const Color(0xFF00E676)),
            ],
          ),
          const SizedBox(height: 2),
          // Table header
          _headerRow(),
          // Rows
          if (sorted.isEmpty)
            Padding(
              padding: const EdgeInsets.all(6),
              child: Center(child: Text('Sin instancias', style: TextStyle(fontSize: 8, color: Colors.white.withValues(alpha: 0.2)))),
            )
          else
            ...sorted.map((sym) => _pairRow(sym, dorBySymbol[sym], elpBySymbol[sym])),
        ],
      ),
    );
  }

  Widget _legend(String label, Color color) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(width: 4, height: 4, decoration: BoxDecoration(shape: BoxShape.circle, color: color.withValues(alpha: 0.6))),
        const SizedBox(width: 2),
        Text(label, style: TextStyle(fontSize: 6, fontWeight: FontWeight.w700, color: color.withValues(alpha: 0.5))),
      ],
    );
  }

  Widget _headerRow() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 1),
      decoration: BoxDecoration(color: Colors.white.withValues(alpha: 0.02)),
      child: Row(
        children: [
          SizedBox(width: 44, child: Text('SYM', style: _hStyle())),
          SizedBox(width: 10, child: Text('D', style: _hStyle())),
          SizedBox(width: 10, child: Text('E', style: _hStyle())),
          SizedBox(width: 32, child: Text('DEC', style: _hStyle())),
          SizedBox(width: 28, child: Text('RNG', style: _hStyle())),
          Expanded(child: Text('PRECIO', style: _hStyle(), textAlign: TextAlign.right)),
          const SizedBox(width: 4),
          SizedBox(width: 52, child: Text('THRESH', style: _hStyle(), textAlign: TextAlign.right)),
        ],
      ),
    );
  }

  Widget _pairRow(String symbol, Map<String, dynamic>? dor, Map<String, dynamic>? elp) {
    final dorRun = dor?['running'] == true;
    final elpRun = elp?['running'] == true;
    final anyRun = dorRun || elpRun;
    final orphan = dor == null || elp == null;

    // Pick report from whichever is running (prefer dorothy)
    final report = (dor?['last_report'] as Map?)?.cast<String, dynamic>() ??
        (elp?['last_report'] as Map?)?.cast<String, dynamic>() ??
        <String, dynamic>{};

    final decision = '${report['decision'] ?? (anyRun ? '...' : '')}';
    final rungs = report['active_rungs'];
    final maxRungs = report['max_rungs'];
    final price = report['market_price'] ?? '';
    final thresh = report['entry_threshold_price'] ?? '';

    final decColor = decision == 'WAIT'
        ? Colors.amber
        : decision.contains('BUY')
            ? const Color(0xFF00E676)
            : decision.contains('SELL')
                ? const Color(0xFFFF1744)
                : Colors.white24;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 1),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: Colors.white.withValues(alpha: 0.03))),
        color: orphan ? Colors.amber.withValues(alpha: 0.02) : null,
      ),
      child: Row(
        children: [
          // Symbol (compact)
          SizedBox(
            width: 44,
            child: Text(
              symbol.replaceAll('USDT', ''),
              style: TextStyle(
                fontSize: 9,
                fontWeight: FontWeight.w700,
                fontFamily: 'monospace',
                color: anyRun ? Colors.white70 : Colors.white24,
              ),
            ),
          ),
          // Dorothy dot
          SizedBox(width: 10, child: _dot(dorRun, dor != null)),
          // Elphaba dot
          SizedBox(width: 10, child: _dot(elpRun, elp != null)),
          // Decision
          SizedBox(
            width: 32,
            child: anyRun
                ? Text(decision, style: TextStyle(fontSize: 7, fontWeight: FontWeight.w700, fontFamily: 'monospace', color: decColor))
                : const Text('—', style: TextStyle(fontSize: 7, color: Colors.white12)),
          ),
          // Rungs
          SizedBox(
            width: 28,
            child: rungs != null
                ? Text('$rungs/${maxRungs ?? '?'}', style: const TextStyle(fontSize: 7, fontFamily: 'monospace', color: Colors.white30))
                : const SizedBox.shrink(),
          ),
          // Price
          Expanded(
            child: Text(
              '$price',
              style: TextStyle(fontSize: 8, fontFamily: 'monospace', color: anyRun ? Colors.white38 : Colors.white12),
              textAlign: TextAlign.right,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          const SizedBox(width: 4),
          // Threshold
          SizedBox(
            width: 52,
            child: Text(
              '$thresh',
              style: TextStyle(fontSize: 8, fontFamily: 'monospace', color: anyRun ? Colors.white24 : Colors.white10),
              textAlign: TextAlign.right,
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Widget _dot(bool running, bool exists) {
    if (!exists) {
      return Icon(Icons.remove, size: 6, color: Colors.white.withValues(alpha: 0.1));
    }
    return Container(
      width: 5, height: 5,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: running ? const Color(0xFF00E676) : Colors.grey.withValues(alpha: 0.25),
        boxShadow: running ? [BoxShadow(color: const Color(0xFF00E676).withValues(alpha: 0.3), blurRadius: 2)] : null,
      ),
    );
  }

  TextStyle _hStyle() => TextStyle(fontSize: 6, fontWeight: FontWeight.w700, color: Colors.white.withValues(alpha: 0.2), letterSpacing: 0.5);
}
