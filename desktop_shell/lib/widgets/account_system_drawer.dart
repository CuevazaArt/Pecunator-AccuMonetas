import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';

class AccountSystemDrawer extends StatefulWidget {
  final EngineApi api;
  const AccountSystemDrawer({super.key, required this.api});

  @override
  State<AccountSystemDrawer> createState() => _AccountSystemDrawerState();
}

class _AccountSystemDrawerState extends State<AccountSystemDrawer> {
  Timer? _timer;
  bool _expanded = false;
  bool _operating = false;

  Map<String, dynamic> _wallets = {};
  Map<String, dynamic> _budgetStatus = {};
  Map<String, dynamic> _ledgerStats = {};
  List<dynamic> _ledgerRecent = [];

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
        widget.api.orderLedgerRecent(limit: 5).catchError((_) => <String, dynamic>{}),
        widget.api.accountWallets().catchError((_) => <String, dynamic>{}),
      ]);

      if (!mounted) return;
      setState(() {
        _budgetStatus = results[0];
        _ledgerStats = results[1];
        _ledgerRecent = (results[2]['items'] as List?) ?? [];
        _wallets = results[3];
      });
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: const Color(0xFF0D1117).withValues(alpha: 0.6),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: Colors.white.withValues(alpha: 0.08)),
        boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.2), blurRadius: 10, offset: const Offset(0, 4)),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              child: Row(
                children: [
                  Icon(Icons.monitor_heart_outlined, size: 16, color: Colors.cyanAccent.withValues(alpha: _expanded ? 1.0 : 0.5)),
                  const SizedBox(width: 8),
                  Text(
                    'SISTEMA & BALANCES',
                    style: TextStyle(
                      fontSize: 11, fontWeight: FontWeight.w800, letterSpacing: 1.2,
                      color: Colors.cyanAccent.withValues(alpha: _expanded ? 1.0 : 0.5),
                    ),
                  ),
                  const Spacer(),
                  _quickBudgetChip(),
                  const SizedBox(width: 12),
                  Icon(_expanded ? Icons.keyboard_arrow_up : Icons.keyboard_arrow_down,
                      size: 18, color: Colors.white38),
                ],
              ),
            ),
          ),
          if (_expanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // Left Col: Budget + Operations
                  Expanded(
                    flex: 4,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        _buildPremiumCard(
                          title: 'BUDGET GUARD',
                          icon: Icons.shield,
                          iconColor: _budgetStatus['blocked'] == true ? Colors.redAccent : Colors.greenAccent,
                          child: _buildBudgetContent(),
                        ),
                        const SizedBox(height: 8),
                        _buildPremiumCard(
                          title: 'EMERGENCY OPS',
                          icon: Icons.warning_amber_rounded,
                          iconColor: Colors.redAccent,
                          child: _buildOpsContent(),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Middle Col: Balances
                  Expanded(
                    flex: 3,
                    child: _buildPremiumCard(
                      title: 'SPOT BALANCES',
                      icon: Icons.account_balance_wallet,
                      iconColor: Colors.cyanAccent,
                      child: _buildBalancesContent(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  // Right Col: Ledger
                  Expanded(
                    flex: 5,
                    child: _buildPremiumCard(
                      title: 'ORDER LEDGER',
                      icon: Icons.receipt_long,
                      iconColor: Colors.purpleAccent,
                      child: _buildLedgerContent(),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _quickBudgetChip() {
    final blocked = _budgetStatus['blocked'] == true;
    final remainPct = _budgetStatus['remaining_pct'];
    final color = blocked ? Colors.redAccent : (remainPct is num && remainPct < 30) ? Colors.orangeAccent : Colors.greenAccent;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(4),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Text(
        blocked ? 'BUDGET BLOCKED' : 'BUDGET OK',
        style: TextStyle(fontSize: 8, fontWeight: FontWeight.w900, color: color, letterSpacing: 0.5),
      ),
    );
  }

  Widget _buildPremiumCard({required String title, required IconData icon, required Color iconColor, required Widget child}) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.05)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 12, color: iconColor),
              const SizedBox(width: 6),
              Text(title, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: Colors.white54, letterSpacing: 0.5)),
            ],
          ),
          const SizedBox(height: 10),
          child,
        ],
      ),
    );
  }

  Widget _buildBudgetContent() {
    final spent = _budgetStatus['spent_24h_usdt'] ?? '0';
    final max = _budgetStatus['max_daily_usdt'] ?? '100';
    final remaining = _budgetStatus['remaining_usdt'] ?? '100';
    final spentVal = double.tryParse('$spent') ?? 0;
    final maxVal = double.tryParse('$max') ?? 100;
    final pct = maxVal > 0 ? (spentVal / maxVal).clamp(0.0, 1.0) : 0.0;
    final color = pct > 0.9 ? Colors.redAccent : pct > 0.7 ? Colors.orangeAccent : Colors.greenAccent;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            _kpiCol('Gastado', '$spent', color),
            _kpiCol('Libre', '$remaining', Colors.cyanAccent),
            _kpiCol('Max 24h', '$max', Colors.white38),
          ],
        ),
        const SizedBox(height: 10),
        ClipRRect(
          borderRadius: BorderRadius.circular(2),
          child: LinearProgressIndicator(
            minHeight: 4, value: pct,
            valueColor: AlwaysStoppedAnimation(color),
            backgroundColor: Colors.white10,
          ),
        ),
      ],
    );
  }

  Widget _kpiCol(String label, String val, Color color) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 8, color: Colors.white38)),
        const SizedBox(height: 2),
        Text(val, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: color, fontFamily: 'monospace')),
      ],
    );
  }

  Widget _buildBalancesContent() {
    final spotRows = (_wallets['spot'] as List?) ?? [];
    final filtered = spotRows.where((r) {
      if (r is! Map) return false;
      return (double.tryParse('${r['total'] ?? 0}') ?? 0) > 0;
    }).toList();

    if (filtered.isEmpty) return const Text('Sin datos', style: TextStyle(fontSize: 9, color: Colors.white24));

    return Column(
      children: filtered.take(6).map((r) {
        final m = r as Map;
        return Padding(
          padding: const EdgeInsets.only(bottom: 4),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('${m['asset']}', style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, fontFamily: 'monospace', color: Colors.white70)),
              Text('${m['total']}', style: const TextStyle(fontSize: 10, fontFamily: 'monospace', color: Colors.cyanAccent)),
            ],
          ),
        );
      }).toList(),
    );
  }

  Widget _buildLedgerContent() {
    final total = _ledgerStats['total_orders'] ?? 0;
    final live = _ledgerStats['live_orders'] ?? 0;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text('Órdenes Activas: ', style: const TextStyle(fontSize: 9, color: Colors.white54)),
            Text('$live', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: live > 0 ? Colors.orangeAccent : Colors.white38)),
            const Spacer(),
            Text('Histórico: ', style: const TextStyle(fontSize: 9, color: Colors.white54)),
            Text('$total', style: TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: Colors.white70)),
          ],
        ),
        const SizedBox(height: 8),
        if (_ledgerRecent.isEmpty)
          const Text('Sin órdenes recientes', style: TextStyle(fontSize: 9, color: Colors.white24))
        else
          ..._ledgerRecent.take(4).map((o) {
            final order = o as Map? ?? {};
            final side = '${order['side'] ?? ''}';
            final sideColor = side == 'BUY' ? Colors.greenAccent : Colors.redAccent;
            return Container(
              margin: const EdgeInsets.only(bottom: 4),
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.03),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Row(
                children: [
                  SizedBox(width: 45, child: Text('${order['bot_type']}', style: const TextStyle(fontSize: 8, fontFamily: 'monospace', color: Colors.white54))),
                  SizedBox(width: 55, child: Text('${order['symbol']}', style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w800, fontFamily: 'monospace', color: Colors.white))),
                  Container(
                    width: 25,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(color: sideColor.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(2)),
                    child: Text(side, style: TextStyle(fontSize: 7, fontWeight: FontWeight.w900, color: sideColor)),
                  ),
                  const SizedBox(width: 8),
                  Expanded(child: Text('${order['reason']}', style: const TextStyle(fontSize: 8, color: Colors.white38), overflow: TextOverflow.ellipsis)),
                ],
              ),
            );
          }),
      ],
    );
  }

  Widget _buildOpsContent() {
    return Wrap(
      spacing: 6, runSpacing: 6,
      children: [
        _opBtn('Close Protocol', Icons.cancel, Colors.orangeAccent, 'close'),
        _opBtn('Cancel Limits', Icons.remove_circle, Colors.amber, 'cancel_limits'),
        _opBtn('RED BUTTON', Icons.emergency, Colors.redAccent, 'red_button'),
        _opBtn('Reset Fuse', Icons.flash_on, Colors.cyanAccent, 'reset_fuse'),
      ],
    );
  }

  Widget _opBtn(String label, IconData icon, Color color, String action) {
    return SizedBox(
      height: 26,
      child: OutlinedButton.icon(
        onPressed: _operating ? null : () => _confirmOp(label, action),
        icon: Icon(icon, size: 10, color: color),
        label: Text(label, style: TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: color)),
        style: OutlinedButton.styleFrom(
          side: BorderSide(color: color.withValues(alpha: 0.3)),
          padding: const EdgeInsets.symmetric(horizontal: 8),
          backgroundColor: color.withValues(alpha: 0.05),
        ),
      ),
    );
  }

  Future<void> _confirmOp(String label, String action) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1A1A1A),
        title: Text('¿Ejecutar $label?', style: const TextStyle(color: Colors.white)),
        content: const Text('Esta operación es irreversible.', style: TextStyle(color: Colors.white70)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar', style: TextStyle(color: Colors.white54))),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(backgroundColor: Colors.redAccent),
            child: const Text('Ejecutar', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
    if (ok == true && mounted) _executeOp(action);
  }

  Future<void> _executeOp(String op) async {
    setState(() { _operating = true; });
    try {
      if (op == 'close') await widget.api.executeCloseProtocol();
      else if (op == 'cancel_limits') await widget.api.executeOrderCleanupLimit();
      else if (op == 'red_button') await widget.api.executeRedButton();
      else if (op == 'reset_fuse') await widget.api.apiFuseReset();
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Operación $op completada'), backgroundColor: Colors.green));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Error en $op: $e'), backgroundColor: Colors.redAccent));
      }
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
