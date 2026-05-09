import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';

/// Collapsible system drawer — shows balances, budget guard, order ledger,
/// guard chain, signals, and emergency ops in a compact expandable section.
///
/// Extracted from spot_account_page.dart so the unified hub page stays thin.
class AccountSystemDrawer extends StatefulWidget {
  final EngineApi api;

  const AccountSystemDrawer({super.key, required this.api});

  @override
  State<AccountSystemDrawer> createState() => _AccountSystemDrawerState();
}

class _AccountSystemDrawerState extends State<AccountSystemDrawer> {
  Timer? _timer;
  bool _expanded = false;
  bool _opsExpanded = false;
  bool _operating = false;
  String? _opResult;

  Map<String, dynamic> _wallets = {};
  Map<String, dynamic> _budgetStatus = {};
  Map<String, dynamic> _ledgerStats = {};
  List<dynamic> _ledgerRecent = [];
  List<Map<String, dynamic>> _activeSignals = [];

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
      final results = await Future.wait([
        widget.api.budgetGuardStatus().catchError((_) => <String, dynamic>{}),
        widget.api.orderLedgerStats().catchError((_) => <String, dynamic>{}),
        widget.api.orderLedgerRecent(limit: 10).catchError((_) => <String, dynamic>{}),
        widget.api.accountWallets().catchError((_) => <String, dynamic>{}),
      ]);

      // Fetch active signals
      List<Map<String, dynamic>> signals = [];
      try {
        final dorothy = await widget.api.hubBots();
        final elphaba = await widget.api.elphabaBots();
        for (final list in [(dorothy['items'] as List?) ?? [], (elphaba['items'] as List?) ?? []]) {
          for (final bot in list) {
            if (bot is Map && bot['running'] == true && bot['last_report'] is Map) {
              final r = bot['last_report'] as Map;
              signals.add({
                'bot': bot['tag'] ?? bot['bot_id'] ?? '?',
                'symbol': r['symbol'] ?? bot['symbol'] ?? '?',
                'decision': r['decision'] ?? '—',
                'market_price': r['market_price'] ?? '—',
                'active_rungs': r['active_rungs'],
                'max_rungs': r['max_rungs'],
              });
            }
          }
        }
      } catch (_) {}

      if (!mounted) return;
      setState(() {
        _budgetStatus = results[0];
        _ledgerStats = results[1];
        _ledgerRecent = (results[2]['items'] as List?) ?? [];
        _wallets = results[3];
        _activeSignals = signals;
      });
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF0A1020),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.04)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // ── Drawer toggle header ────────────────────────────
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
              child: Row(
                children: [
                  Icon(Icons.dashboard_customize, size: 12,
                      color: Colors.cyanAccent.withValues(alpha: _expanded ? 0.7 : 0.3)),
                  const SizedBox(width: 6),
                  Text(
                    'SISTEMA & BALANCES',
                    style: TextStyle(
                      fontSize: 9, fontWeight: FontWeight.w800, letterSpacing: 1,
                      color: Colors.cyanAccent.withValues(alpha: _expanded ? 0.7 : 0.3),
                    ),
                  ),
                  const Spacer(),
                  // Quick budget chip
                  _quickBudgetChip(),
                  const SizedBox(width: 8),
                  Icon(_expanded ? Icons.expand_less : Icons.expand_more,
                      size: 14, color: Colors.white24),
                ],
              ),
            ),
          ),
          // ── Expanded content ────────────────────────────────
          if (_expanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // Row: Budget + Signals
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(child: _buildBudgetGuard()),
                      const SizedBox(width: 6),
                      Expanded(child: _buildBalancesSummary()),
                    ],
                  ),
                  const SizedBox(height: 6),
                  if (_activeSignals.isNotEmpty) ...[
                    _buildSignalStrip(),
                    const SizedBox(height: 6),
                  ],
                  _buildOrderLedger(),
                  const SizedBox(height: 6),
                  _buildGuardChain(),
                  const SizedBox(height: 6),
                  _buildOpsPanel(),
                ],
              ),
            ),
        ],
      ),
    );
  }

  // ── Quick budget chip (always visible in header) ─────────────
  Widget _quickBudgetChip() {
    final blocked = _budgetStatus['blocked'] == true;
    final remainPct = _budgetStatus['remaining_pct'];
    final color = blocked
        ? const Color(0xFFFF1744)
        : (remainPct is num && remainPct < 30)
            ? const Color(0xFFFF9100)
            : Colors.greenAccent;
    final label = blocked ? 'BUDGET BLOCKED' : 'Budget OK';
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(3),
      ),
      child: Text(label, style: TextStyle(fontSize: 7, fontWeight: FontWeight.w700, color: color)),
    );
  }

  // ── Budget Guard ─────────────────────────────────────────────
  Widget _buildBudgetGuard() {
    final spent = _budgetStatus['spent_24h_usdt'] ?? '0';
    final max = _budgetStatus['max_daily_usdt'] ?? '100';
    final remaining = _budgetStatus['remaining_usdt'] ?? '100';
    final blocked = _budgetStatus['blocked'] == true;
    final spentVal = double.tryParse('$spent') ?? 0;
    final maxVal = double.tryParse('$max') ?? 100;
    final pct = maxVal > 0 ? (spentVal / maxVal).clamp(0.0, 1.0) : 0.0;
    final color = blocked ? const Color(0xFFFF1744) : pct > 0.7 ? const Color(0xFFFF9100) : const Color(0xFF00E676);

    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color(0xFF0F3460),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Icon(Icons.shield_outlined, size: 10, color: color),
            const SizedBox(width: 3),
            const Text('BUDGET 24h', style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: Colors.white38)),
            const Spacer(),
            Text(blocked ? 'BLOCKED' : 'OK', style: TextStyle(fontSize: 7, fontWeight: FontWeight.w800, color: color)),
          ]),
          const SizedBox(height: 3),
          Row(children: [
            _kpi('Gastado', '$spent', color),
            _kpi('Máx', '$max', Colors.grey),
            _kpi('Libre', '$remaining', const Color(0xFF00E5FF)),
          ]),
          const SizedBox(height: 3),
          ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: LinearProgressIndicator(
              minHeight: 3, value: pct,
              valueColor: AlwaysStoppedAnimation(color),
              backgroundColor: Colors.white10,
            ),
          ),
        ],
      ),
    );
  }

  // ── Balances Summary ─────────────────────────────────────────
  Widget _buildBalancesSummary() {
    final spotRows = (_wallets['spot'] as List?) ?? [];
    final filtered = spotRows.where((r) {
      if (r is! Map) return false;
      return (double.tryParse('${r['total'] ?? 0}') ?? 0) > 0;
    }).toList();

    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color(0xFF0F3460),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.account_balance_wallet, size: 10, color: Color(0xFF00E676)),
            const SizedBox(width: 3),
            Text('BALANCES (${filtered.length})', style: const TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: Colors.white38)),
          ]),
          const SizedBox(height: 3),
          if (filtered.isEmpty)
            const Text('Sin datos', style: TextStyle(fontSize: 8, color: Colors.white24))
          else
            ...filtered.take(8).map((r) {
              final m = r as Map;
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 1),
                child: Row(children: [
                  SizedBox(width: 40, child: Text('${m['asset']}', style: const TextStyle(fontSize: 8, fontWeight: FontWeight.w700, fontFamily: 'monospace', color: Colors.white70))),
                  Expanded(child: Text('${m['total']}', style: const TextStyle(fontSize: 8, fontFamily: 'monospace', color: Colors.white38), textAlign: TextAlign.right)),
                ]),
              );
            }),
          if (filtered.length > 8)
            Text('+${filtered.length - 8} more', style: const TextStyle(fontSize: 7, color: Colors.white24)),
        ],
      ),
    );
  }

  // ── Signal Strip ─────────────────────────────────────────────
  Widget _buildSignalStrip() {
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color(0xFF0F3460),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: Colors.amber.withValues(alpha: 0.1)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.show_chart, size: 10, color: Colors.amber),
            const SizedBox(width: 3),
            Text('SEÑALES (${_activeSignals.length})', style: const TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: Colors.amber)),
          ]),
          const SizedBox(height: 3),
          for (final s in _activeSignals)
            _signalRow(s),
        ],
      ),
    );
  }

  Widget _signalRow(Map<String, dynamic> s) {
    final decision = '${s['decision'] ?? '—'}';
    final decColor = decision.contains('BUY') ? const Color(0xFF00E676)
        : decision.contains('SELL') ? const Color(0xFFFF1744)
        : decision.contains('WAIT') ? Colors.amber
        : Colors.grey;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(children: [
        SizedBox(width: 50, child: Text('${s['bot']}', style: const TextStyle(fontSize: 8, fontFamily: 'monospace'), overflow: TextOverflow.ellipsis)),
        SizedBox(width: 60, child: Text('${s['symbol']}', style: const TextStyle(fontSize: 8, fontFamily: 'monospace', fontWeight: FontWeight.w600))),
        SizedBox(width: 50, child: Text('${s['market_price']}', style: const TextStyle(fontSize: 8, fontFamily: 'monospace', color: Colors.white54))),
        SizedBox(width: 35, child: Text('${s['active_rungs'] ?? '—'}/${s['max_rungs'] ?? '?'}', style: const TextStyle(fontSize: 8, fontFamily: 'monospace', color: Colors.white30))),
        Expanded(child: Text(decision, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700, fontFamily: 'monospace', color: decColor))),
      ]),
    );
  }

  // ── Order Ledger ─────────────────────────────────────────────
  Widget _buildOrderLedger() {
    final total = _ledgerStats['total_orders'] ?? 0;
    final live = _ledgerStats['live_orders'] ?? 0;
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color(0xFF0F3460),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            const Icon(Icons.receipt_long_outlined, size: 10, color: Color(0xFF00E5FF)),
            const SizedBox(width: 3),
            const Text('LEDGER', style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: Colors.white38)),
            const Spacer(),
            _kpi('Total', '$total', const Color(0xFF00E5FF)),
            _kpi('Live', '$live', live > 0 ? const Color(0xFFFF9100) : Colors.grey),
          ]),
          const SizedBox(height: 3),
          if (_ledgerRecent.isEmpty)
            const Text('Sin órdenes', style: TextStyle(fontSize: 8, color: Colors.white24))
          else
            for (final order in _ledgerRecent.take(5))
              _ledgerRow(order as Map? ?? {}),
        ],
      ),
    );
  }

  Widget _ledgerRow(Map order) {
    final side = '${order['side'] ?? ''}';
    final sideColor = side == 'BUY' ? const Color(0xFF00E676) : const Color(0xFFFF1744);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(children: [
        SizedBox(width: 45, child: Text('${order['bot_type']}', style: const TextStyle(fontSize: 7, fontFamily: 'monospace'))),
        SizedBox(width: 55, child: Text('${order['symbol']}', style: const TextStyle(fontSize: 7, fontFamily: 'monospace'))),
        SizedBox(width: 25, child: Text(side, style: TextStyle(fontSize: 7, fontWeight: FontWeight.w700, color: sideColor))),
        Expanded(child: Text('${order['reason']}', style: const TextStyle(fontSize: 7, fontFamily: 'monospace'), overflow: TextOverflow.ellipsis)),
      ]),
    );
  }

  // ── Guard Chain ──────────────────────────────────────────────
  Widget _buildGuardChain() {
    final guards = [
      ('PanicLock', Icons.lock_outline, true),
      ('MaxRungs', Icons.stacked_line_chart, true),
      ('BudgetGuard', Icons.shield, _budgetStatus['blocked'] != true),
      ('OrderLedger', Icons.receipt_long, true),
      ('FeeModel', Icons.calculate, true),
    ];
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: const Color(0xFF0F3460),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Row(
        children: [
          const Icon(Icons.security_outlined, size: 10, color: Color(0xFF00E5FF)),
          const SizedBox(width: 4),
          const Text('GUARDS', style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: Colors.white38)),
          const SizedBox(width: 8),
          for (final (name, icon, ok) in guards) ...[
            Tooltip(
              message: '$name: ${ok ? "OK" : "BLOCKED"}',
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
                margin: const EdgeInsets.only(right: 4),
                decoration: BoxDecoration(
                  color: (ok ? const Color(0xFF00E676) : const Color(0xFFFF1744)).withValues(alpha: 0.08),
                  borderRadius: BorderRadius.circular(3),
                ),
                child: Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(icon, size: 9, color: ok ? const Color(0xFF00E676) : const Color(0xFFFF1744)),
                  const SizedBox(width: 2),
                  Text(name, style: TextStyle(fontSize: 7, fontWeight: FontWeight.w700, color: ok ? const Color(0xFF00E676) : const Color(0xFFFF1744))),
                ]),
              ),
            ),
          ],
        ],
      ),
    );
  }

  // ── Emergency Ops Panel ──────────────────────────────────────
  Widget _buildOpsPanel() {
    return Container(
      decoration: BoxDecoration(
        color: _opsExpanded ? const Color(0xFF1A0000) : const Color(0xFF0D0D0D),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: Colors.redAccent.withValues(alpha: _opsExpanded ? 0.3 : 0.08)),
      ),
      child: Column(
        children: [
          InkWell(
            onTap: () => setState(() => _opsExpanded = !_opsExpanded),
            borderRadius: BorderRadius.circular(6),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              child: Row(
                children: [
                  Icon(Icons.warning_amber_rounded, size: 10,
                      color: Colors.redAccent.withValues(alpha: _opsExpanded ? 1.0 : 0.3)),
                  const SizedBox(width: 4),
                  Text('Operaciones de emergencia',
                      style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700,
                          color: Colors.redAccent.withValues(alpha: _opsExpanded ? 1.0 : 0.3))),
                  const Spacer(),
                  if (_opResult != null)
                    Flexible(child: Text(_opResult!, style: const TextStyle(fontSize: 7, color: Colors.white38, fontFamily: 'monospace'), overflow: TextOverflow.ellipsis)),
                  Icon(_opsExpanded ? Icons.expand_less : Icons.expand_more, size: 12,
                      color: Colors.redAccent.withValues(alpha: 0.3)),
                ],
              ),
            ),
          ),
          if (_opsExpanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(6, 0, 6, 6),
              child: Wrap(
                spacing: 4, runSpacing: 4,
                children: [
                  _opButton('Close Protocol', Icons.cancel_outlined, Colors.orangeAccent, () => _executeOp('close')),
                  _opButton('Cancel Limits', Icons.remove_circle_outline, Colors.amber, () => _executeOp('cancel_limits')),
                  _opButton('RED BUTTON', Icons.emergency, Colors.red, () => _executeOp('red_button')),
                  _opButton('Reset Fuse', Icons.flash_on, Colors.cyanAccent, () => _executeOp('reset_fuse')),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _opButton(String label, IconData icon, Color color, VoidCallback onTap) {
    return SizedBox(
      height: 24,
      child: OutlinedButton.icon(
        onPressed: _operating ? null : () => _confirmOp(label, onTap),
        icon: Icon(icon, size: 10, color: color),
        label: Text(label, style: TextStyle(fontSize: 8, color: color)),
        style: OutlinedButton.styleFrom(
          side: BorderSide(color: color.withValues(alpha: 0.4)),
          padding: const EdgeInsets.symmetric(horizontal: 6),
        ),
      ),
    );
  }

  Future<void> _confirmOp(String label, VoidCallback action) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('¿Ejecutar $label?'),
        content: const Text('Esta operación es irreversible.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(backgroundColor: Colors.redAccent),
            child: const Text('Ejecutar'),
          ),
        ],
      ),
    );
    if (ok == true) action();
  }

  Future<void> _executeOp(String op) async {
    setState(() { _operating = true; _opResult = 'Ejecutando...'; });
    try {
      Map<String, dynamic> result;
      switch (op) {
        case 'close':   result = await widget.api.executeCloseProtocol(); break;
        case 'cancel_limits': result = await widget.api.executeOrderCleanupLimit(); break;
        case 'red_button': result = await widget.api.executeRedButton(); break;
        case 'reset_fuse': result = await widget.api.apiFuseReset(); break;
        default: result = {'error': 'Unknown op'};
      }
      if (mounted) setState(() => _opResult = '${result['status'] ?? 'ok'}');
    } catch (e) {
      if (mounted) setState(() => _opResult = 'Error: $e');
    } finally {
      if (mounted) setState(() => _operating = false);
    }
  }

  Widget _kpi(String label, String value, Color color) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 3),
      child: Column(children: [
        Text(value, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, fontFamily: 'monospace', color: color)),
        Text(label, style: const TextStyle(fontSize: 6, color: Colors.white38)),
      ]),
    );
  }
}
