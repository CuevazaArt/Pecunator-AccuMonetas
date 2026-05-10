import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';

/// Compact spot balances strip — shows top non-zero balances inline.
/// Placed next to the equity chart in the telemetry bar.
class SpotBalancesStrip extends StatefulWidget {
  final EngineApi api;
  final double height;
  const SpotBalancesStrip({super.key, required this.api, this.height = 48});

  @override
  State<SpotBalancesStrip> createState() => _SpotBalancesStripState();
}

class _SpotBalancesStripState extends State<SpotBalancesStrip> {
  Timer? _timer;
  List<Map<String, dynamic>> _balances = [];

  @override
  void initState() {
    super.initState();
    _poll();
    _timer = Timer.periodic(const Duration(seconds: 15), (_) => _poll());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _poll() async {
    if (!mounted) return;
    try {
      final resp = await widget.api.accountWallets();
      if (!mounted) return;

      // Backend returns {buckets: [{asset, free}, ...]}
      final raw = (resp['buckets'] as List?) ?? (resp['spot'] as List?) ?? [];
      final filtered = <Map<String, dynamic>>[];
      for (final item in raw) {
        if (item is! Map) continue;
        final free = double.tryParse('${item['free'] ?? item['total'] ?? 0}') ?? 0;
        if (free > 0.001) {
          filtered.add({'asset': '${item['asset']}', 'free': free});
        }
      }
      // Sort by value descending (USDT first typically)
      filtered.sort((a, b) => (b['free'] as double).compareTo(a['free'] as double));

      setState(() => _balances = filtered);
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      height: widget.height,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1117).withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.account_balance_wallet, size: 9,
                  color: Colors.cyanAccent.withValues(alpha: 0.6)),
              const SizedBox(width: 3),
              Text(
                'SPOT',
                style: TextStyle(
                  fontSize: 7,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.8,
                  color: Colors.cyanAccent.withValues(alpha: 0.6),
                ),
              ),
              const Spacer(),
              Text(
                '${_balances.length} assets',
                style: TextStyle(fontSize: 7, color: Colors.white.withValues(alpha: 0.3)),
              ),
            ],
          ),
          const SizedBox(height: 2),
          Expanded(
            child: _balances.isEmpty
                ? Center(
                    child: Text(
                      'Cargando...',
                      style: TextStyle(fontSize: 8, color: Colors.white.withValues(alpha: 0.2)),
                    ),
                  )
                : ListView.builder(
                    padding: EdgeInsets.zero,
                    itemCount: _balances.length.clamp(0, 5),
                    itemBuilder: (_, i) {
                      final b = _balances[i];
                      final asset = b['asset'] as String;
                      final free = b['free'] as double;
                      final isStable = asset == 'USDT' || asset == 'BUSD' || asset == 'USDC';
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 1),
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            Text(
                              asset,
                              style: TextStyle(
                                fontSize: 8,
                                fontWeight: FontWeight.w700,
                                fontFamily: 'monospace',
                                color: isStable ? Colors.cyanAccent : Colors.white60,
                              ),
                            ),
                            Text(
                              free > 1000
                                  ? free.toStringAsFixed(0)
                                  : free > 1
                                      ? free.toStringAsFixed(2)
                                      : free.toStringAsFixed(6),
                              style: TextStyle(
                                fontSize: 8,
                                fontFamily: 'monospace',
                                color: isStable
                                    ? Colors.cyanAccent.withValues(alpha: 0.9)
                                    : Colors.white.withValues(alpha: 0.5),
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
}
