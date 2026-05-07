import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';

/// System Dashboard — replaces browser-based backend access.
/// Dense, information-rich view of all v0.11+ risk controls,
/// order ledger, regime filter, budget guard, and system health.
class SystemDashboardPage extends StatefulWidget {
  final EngineApi api;
  const SystemDashboardPage({super.key, required this.api});

  @override
  State<SystemDashboardPage> createState() => _SystemDashboardPageState();
}

class _SystemDashboardPageState extends State<SystemDashboardPage> {
  Timer? _timer;
  Map<String, dynamic> _health = {};
  Map<String, dynamic> _budget = {};
  Map<String, dynamic> _ledgerStats = {};
  List<dynamic> _ledgerRecent = [];
  Map<String, dynamic> _regime = {};
  bool _loading = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 5), (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    if (!mounted) return;
    try {
      final results = await Future.wait([
        widget.api.healthV1(),
        widget.api.budgetGuardStatus(),
        widget.api.orderLedgerStats(),
        widget.api.orderLedgerRecent(limit: 20),
        widget.api.regimeFilterStatus(),
      ]);
      if (!mounted) return;
      setState(() {
        _health = results[0];
        _budget = results[1];
        _ledgerStats = results[2];
        _ledgerRecent = (results[3]['items'] as List?) ?? [];
        _regime = results[4];
        _error = '';
        _loading = false;
      });
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  Color _statusColor(bool ok) => ok ? const Color(0xFF00E676) : const Color(0xFFFF1744);
  Color _zoneColor(String zone) {
    switch (zone.toUpperCase()) {
      case 'GREEN': return const Color(0xFF00E676);
      case 'YELLOW': return const Color(0xFFFFEA00);
      case 'ORANGE': return const Color(0xFFFF9100);
      case 'RED': return const Color(0xFFFF1744);
      default: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    final cs = Theme.of(context).colorScheme;
    final status = _health['status'] ?? 'unknown';
    final fuse = _health['fuse_tripped'] == true;
    final zone = (_health['weight_zone'] ?? 'GREEN').toString();
    final hubs = _health['hubs'] as Map? ?? {};

    return Scaffold(
      appBar: AppBar(
        title: const Text('System Dashboard'),
        automaticallyImplyLeading: false,
        actions: [
          if (_error.isNotEmpty)
            Tooltip(message: _error, child: const Icon(Icons.error_outline, color: Colors.redAccent, size: 16)),
          IconButton(onPressed: _refresh, tooltip: 'Refrescar', icon: const Icon(Icons.refresh, size: 18)),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // ── Row 1: System Status KPIs ──
            _sectionLabel('ESTADO DEL SISTEMA'),
            const SizedBox(height: 4),
            Row(children: [
              _kpiCard('Estado', status.toString().toUpperCase(), _statusColor(status == 'healthy')),
              _kpiCard('API Fuse', fuse ? 'TRIPPED' : 'OK', _statusColor(!fuse)),
              _kpiCard('Weight Zone', zone, _zoneColor(zone)),
              _kpiCard('Uptime', _formatUptime(_health['uptime_sec']), cs.primary),
            ]),
            const SizedBox(height: 6),

            // ── Row 2: Hub Status ──
            _sectionLabel('HUBS DE BOTS'),
            const SizedBox(height: 4),
            Row(children: [
              for (final entry in hubs.entries)
                _hubCard(entry.key, entry.value as Map? ?? {}),
            ]),
            const SizedBox(height: 6),

            // ── Row 3: Risk Controls (2-column) ──
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Budget Guard
                Expanded(child: _buildBudgetGuard()),
                const SizedBox(width: 8),
                // Regime Filter
                Expanded(child: _buildRegimeFilter()),
              ],
            ),
            const SizedBox(height: 6),

            // ── Row 4: Order Ledger ──
            _buildOrderLedger(),
            const SizedBox(height: 6),

            // ── Row 5: Guard Chain ──
            _buildGuardChain(),
          ],
        ),
      ),
    );
  }

  Widget _sectionLabel(String text) {
    return Text(text, style: TextStyle(
      fontSize: 10, fontWeight: FontWeight.w700, letterSpacing: 1.5,
      color: Theme.of(context).colorScheme.primary.withOpacity(0.7),
    ));
  }

  Widget _kpiCard(String label, String value, Color color) {
    return Expanded(
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 3),
        padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 10),
        decoration: BoxDecoration(
          color: color.withOpacity(0.08),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withOpacity(0.25)),
        ),
        child: Column(children: [
          Text(label, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w500)),
          const SizedBox(height: 3),
          Text(value, style: TextStyle(
            fontSize: 13, fontWeight: FontWeight.w800, fontFamily: 'monospace', color: color,
          )),
        ]),
      ),
    );
  }

  Widget _hubCard(String name, Map hub) {
    final total = hub['hub_bots_total'] ?? 0;
    final running = hub['hub_bots_running'] ?? 0;
    final desired = hub['hub_bots_desired_running'] ?? 0;
    final color = running > 0 ? const Color(0xFF00E676) : Colors.grey;
    return Expanded(
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 3),
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: color.withOpacity(0.06),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withOpacity(0.2)),
        ),
        child: Row(children: [
          Icon(Icons.smart_toy_outlined, size: 16, color: color),
          const SizedBox(width: 6),
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name.toUpperCase(), style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: color)),
              Text('$running/$total running · $desired desired',
                style: const TextStyle(fontSize: 9, fontFamily: 'monospace')),
            ],
          )),
        ]),
      ),
    );
  }

  Widget _buildBudgetGuard() {
    final spent = _budget['spent_24h_usdt'] ?? '0';
    final max = _budget['max_daily_usdt'] ?? '100';
    final remaining = _budget['remaining_usdt'] ?? '100';
    final blocked = _budget['blocked'] == true;
    final spentVal = double.tryParse('$spent') ?? 0;
    final maxVal = double.tryParse('$max') ?? 100;
    final pct = maxVal > 0 ? (spentVal / maxVal).clamp(0.0, 1.0) : 0.0;
    final color = blocked ? const Color(0xFFFF1744) : pct > 0.7 ? const Color(0xFFFF9100) : const Color(0xFF00E676);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.shield_outlined, size: 14, color: color),
              const SizedBox(width: 6),
              const Text('BUDGET GUARD (24h)', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, letterSpacing: 1)),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: color.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(blocked ? 'BLOCKED' : 'OK', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: color)),
              ),
            ]),
            const SizedBox(height: 8),
            Row(children: [
              _miniKpi('Gastado', '$spent USDT', color),
              _miniKpi('Máximo', '$max USDT', Colors.grey),
              _miniKpi('Restante', '$remaining USDT', const Color(0xFF00E5FF)),
            ]),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                minHeight: 6, value: pct,
                valueColor: AlwaysStoppedAnimation(color),
                backgroundColor: Colors.white10,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRegimeFilter() {
    final entries = _regime.entries.where((e) => e.key != '_btc_global').toList();
    final btc = _regime['_btc_global'] as Map?;
    final btcOk = btc?['allowed'] == true;
    final btcReason = (btc?['reason'] ?? 'no data').toString();
    final btcColor = btcOk ? const Color(0xFF00E676) : const Color(0xFFFF1744);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(Icons.filter_alt_outlined, size: 14, color: btcColor),
              const SizedBox(width: 6),
              const Text('REGIME FILTER', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, letterSpacing: 1)),
              const Spacer(),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                decoration: BoxDecoration(
                  color: btcColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Text(btcOk ? 'ALLOWING' : 'BLOCKING', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: btcColor)),
              ),
            ]),
            const SizedBox(height: 6),
            // BTC Global
            Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: btcColor.withOpacity(0.05),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Row(children: [
                Text('BTC', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, color: btcColor)),
                const SizedBox(width: 8),
                Expanded(child: Text(btcReason, style: const TextStyle(fontSize: 9, fontFamily: 'monospace'), overflow: TextOverflow.ellipsis)),
              ]),
            ),
            const SizedBox(height: 4),
            // Per-symbol
            for (final e in entries)
              _regimeRow(e.key, e.value as Map? ?? {}),
            if (entries.isEmpty && btc == null)
              const Text('Sin datos de régimen. Ejecuta un bot para activar.', style: TextStyle(fontSize: 10, color: Colors.grey)),
          ],
        ),
      ),
    );
  }

  Widget _regimeRow(String symbol, Map data) {
    final ok = data['allowed'] == true;
    final reason = (data['reason'] ?? '').toString();
    final age = data['age_sec'] ?? 0;
    final color = ok ? const Color(0xFF00E676) : const Color(0xFFFF9100);
    return Padding(
      padding: const EdgeInsets.only(top: 3),
      child: Row(children: [
        Container(width: 6, height: 6, decoration: BoxDecoration(color: color, shape: BoxShape.circle)),
        const SizedBox(width: 6),
        SizedBox(width: 70, child: Text(symbol, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w600, fontFamily: 'monospace'))),
        Expanded(child: Text(reason, style: const TextStyle(fontSize: 8, fontFamily: 'monospace'), overflow: TextOverflow.ellipsis)),
        Text('${age}s ago', style: const TextStyle(fontSize: 8, color: Colors.grey)),
      ]),
    );
  }

  Widget _buildOrderLedger() {
    final total = _ledgerStats['total_orders'] ?? 0;
    final live = _ledgerStats['live_orders'] ?? 0;
    final sim = _ledgerStats['simulated_orders'] ?? 0;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              const Icon(Icons.receipt_long_outlined, size: 14, color: Color(0xFF00E5FF)),
              const SizedBox(width: 6),
              const Text('ORDER LEDGER (FORENSIC)', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, letterSpacing: 1)),
              const Spacer(),
              _miniKpi('Total', '$total', const Color(0xFF00E5FF)),
              _miniKpi('Live', '$live', live > 0 ? const Color(0xFFFF9100) : Colors.grey),
              _miniKpi('Simulated', '$sim', const Color(0xFF00E676)),
            ]),
            const SizedBox(height: 6),
            if (_ledgerRecent.isEmpty)
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.03),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: const Center(child: Text('Sin órdenes registradas — todos los guards están activos.', style: TextStyle(fontSize: 10, color: Colors.grey))),
              )
            else
              Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(6),
                  color: Colors.white.withOpacity(0.03),
                ),
                child: Column(
                  children: [
                    // Header
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.05),
                        borderRadius: const BorderRadius.vertical(top: Radius.circular(6)),
                      ),
                      child: const Row(children: [
                        SizedBox(width: 60, child: Text('Bot', style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700))),
                        SizedBox(width: 80, child: Text('Symbol', style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700))),
                        SizedBox(width: 40, child: Text('Side', style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700))),
                        SizedBox(width: 50, child: Text('Type', style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700))),
                        Expanded(child: Text('Reason', style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700))),
                        SizedBox(width: 50, child: Text('Mode', style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700))),
                      ]),
                    ),
                    // Rows
                    for (final order in _ledgerRecent.take(15))
                      _ledgerRow(order as Map? ?? {}),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _ledgerRow(Map order) {
    final side = (order['side'] ?? '').toString();
    final sideColor = side == 'BUY' ? const Color(0xFF00E676) : const Color(0xFFFF1744);
    final mode = (order['execution_mode'] ?? '').toString();
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: Colors.white.withOpacity(0.04))),
      ),
      child: Row(children: [
        SizedBox(width: 60, child: Text('${order['bot_type']}', style: const TextStyle(fontSize: 8, fontFamily: 'monospace'))),
        SizedBox(width: 80, child: Text('${order['symbol']}', style: const TextStyle(fontSize: 8, fontFamily: 'monospace'))),
        SizedBox(width: 40, child: Text(side, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: sideColor))),
        SizedBox(width: 50, child: Text('${order['order_type']}', style: const TextStyle(fontSize: 8, fontFamily: 'monospace'))),
        Expanded(child: Text('${order['reason']}', style: const TextStyle(fontSize: 8, fontFamily: 'monospace'), overflow: TextOverflow.ellipsis)),
        SizedBox(width: 50, child: Text(mode, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w600, color: mode == 'LIVE' ? const Color(0xFFFF9100) : Colors.grey))),
      ]),
    );
  }

  Widget _buildGuardChain() {
    final guards = [
      ('PanicLock', Icons.lock_outline, 'Bloqueo de emergencia', true, 'CLEAR'),
      ('DrawdownGuard', Icons.trending_down, 'Bloquea en drawdown alto', true, 'ACTIVE'),
      ('MaxRungs', Icons.stacked_line_chart, 'Límite DCA por símbolo (5)', true, 'ENFORCED'),
      ('RegimeFilter', Icons.filter_alt, 'BTC>EMA200 + ADX + Vol', _regime['_btc_global']?['allowed'] != false, _regime.isEmpty ? 'NO DATA' : (_regime['_btc_global']?['allowed'] == true ? 'ALLOWING' : 'BLOCKING')),
      ('BudgetGuard', Icons.shield, 'Techo de gasto 24h', _budget['blocked'] != true, _budget.isEmpty ? 'NO DATA' : (_budget['blocked'] == true ? 'BLOCKED' : 'CLEAR')),
      ('OrderLedger', Icons.receipt_long, 'Auditoría forense', true, 'RECORDING'),
      ('FeeModel', Icons.calculate, 'Fees+slippage 15bps', true, 'ACTIVE'),
    ];

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(children: [
              Icon(Icons.security_outlined, size: 14, color: Color(0xFF00E5FF)),
              SizedBox(width: 6),
              Text('GUARD CHAIN (orden de evaluación)', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700, letterSpacing: 1)),
            ]),
            const SizedBox(height: 6),
            for (int i = 0; i < guards.length; i++)
              _guardRow(i + 1, guards[i]),
          ],
        ),
      ),
    );
  }

  Widget _guardRow(int idx, (String, IconData, String, bool, String) guard) {
    final (name, icon, desc, ok, status) = guard;
    final color = ok ? const Color(0xFF00E676) : const Color(0xFFFF1744);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 2),
      child: Row(children: [
        SizedBox(width: 16, child: Text('$idx', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w600, color: Colors.grey.withOpacity(0.6)))),
        Icon(icon, size: 13, color: color),
        const SizedBox(width: 6),
        SizedBox(width: 100, child: Text(name, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w700, fontFamily: 'monospace'))),
        Expanded(child: Text(desc, style: const TextStyle(fontSize: 9, color: Colors.grey))),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
          decoration: BoxDecoration(
            color: color.withOpacity(0.1),
            borderRadius: BorderRadius.circular(3),
          ),
          child: Text(status, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: color, fontFamily: 'monospace')),
        ),
      ]),
    );
  }

  Widget _miniKpi(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Column(children: [
        Text(value, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, fontFamily: 'monospace', color: color)),
        Text(label, style: const TextStyle(fontSize: 8)),
      ]),
    );
  }

  String _formatUptime(dynamic seconds) {
    if (seconds == null) return '—';
    final sec = (seconds is num) ? seconds.toInt() : int.tryParse('$seconds') ?? 0;
    final d = sec ~/ 86400;
    final h = (sec % 86400) ~/ 3600;
    final m = (sec % 3600) ~/ 60;
    if (d > 0) return '${d}d ${h}h';
    if (h > 0) return '${h}h ${m}m';
    return '${m}m';
  }
}
