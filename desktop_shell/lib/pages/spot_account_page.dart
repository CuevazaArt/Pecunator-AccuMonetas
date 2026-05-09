import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/mini_charts.dart';

/// Unified account dashboard — at-a-glance view of all equities,
/// weight monitoring, service lights, operations panel, and balances.
class AccountDashboardPage extends StatefulWidget {
  final String engineBase;
  final List<String> activeSymbols;

  const AccountDashboardPage({
    super.key,
    required this.engineBase,
    this.activeSymbols = const [],
  });

  @override
  State<AccountDashboardPage> createState() => _AccountDashboardPageState();
}

class _AccountDashboardPageState extends State<AccountDashboardPage> {
  late final EngineApi _api;
  Timer? _timer;
  Map<String, dynamic> _wallets = {};
  Map<String, dynamic> _health = {};
  Map<String, dynamic> _budgetStatus = {};
  bool _loading = true;
  bool _operating = false;
  String? _opResult;
  bool _opsExpanded = false; // Collapsed by default — rarely used

  // System state
  bool _gatewayRunning = false;
  bool _fuseTripped = false;
  int _dorothyRunning = 0, _dorothyTotal = 0;
  int _elphabaRunning = 0, _elphabaTotal = 0;

  @override
  void initState() {
    super.initState();
    _api = EngineApi(widget.engineBase);
    _refresh();
    // Refresh every 10s — rational API consumption
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _refreshSilent());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() => _loading = true);
    await _fetchData();
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _refreshSilent() async {
    await _fetchData();
  }

  Future<void> _fetchData() async {
    try {
      final snap = await _api.gatewaySnapshot();
      bool fuse = false;
      try { final fs = await _api.apiFuseStatus(); fuse = fs['tripped'] == true; } catch (_) {}

      Map<String, dynamic> health = {};
      try { health = await _api.healthDeep(); } catch (_) {}

      Map<String, dynamic> budget = {};
      try { budget = await _api.budgetGuardStatus(); } catch (_) {}

      // Parse hub stats
      final hubs = health['hubs'] as Map? ?? {};
      int dr = 0, dt = 0, mr = 0, mt = 0;
      if (hubs['dorothy'] is Map) {
        dr = (hubs['dorothy']['hub_bots_running'] ?? 0) as int;
        dt = (hubs['dorothy']['hub_bots_total'] ?? 0) as int;
      }
      if (hubs['elphaba'] is Map) {
        mr = (hubs['elphaba']['hub_bots_running'] ?? 0) as int;
        mt = (hubs['elphaba']['hub_bots_total'] ?? 0) as int;
      }

      if (!mounted) return;
      setState(() {
        _gatewayRunning = snap['gateway_running'] == true;
        _fuseTripped = fuse;
        _health = health;
        _budgetStatus = budget;
        _dorothyRunning = dr; _dorothyTotal = dt;
        _elphabaRunning = mr; _elphabaTotal = mt;
      });
    } catch (_) {}

    // Fetch wallets (only if gateway is running)
    if (_gatewayRunning) {
      try {
        final w = await _api.accountWallets();
        if (mounted) setState(() => _wallets = w);
      } catch (_) {}
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // ── Row 1: Charts (Weight + Equities) ──────────────────
          Row(
            children: [
              Expanded(
                child: MiniWeightChart(api: _api, height: 56),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: MiniEquityChart(
                  api: _api,
                  label: 'Equity Total',
                  color: const Color(0xFF00E676),
                  height: 56,
                  syncInterval: const Duration(seconds: 8),
                ),
              ),
            ],
          ),
          const SizedBox(height: 6),

          // ── Row 2: Status Lights + Equity Cards ────────────────
          Row(
            children: [
              // Service lights
              _serviceLightsPanel(),
              const SizedBox(width: 6),
              // Equity summary cards
              Expanded(child: _equityCardsRow()),
            ],
          ),
          const SizedBox(height: 6),

          // ── Row 3: Operations Panel (Red Button) ───────────────
          _operationsPanel(),
          const SizedBox(height: 6),

          // ── Row 4: Balance Report ──────────────────────────────
          _balancesTable(),
        ],
      ),
    );
  }

  Widget _serviceLightsPanel() {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: const Color(0xFF0F3460),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('SERVICES', style: TextStyle(fontSize: 8, color: Colors.white38, fontWeight: FontWeight.w800, letterSpacing: 1)),
          const SizedBox(height: 4),
          _svcLight('Gateway', _gatewayRunning),
          _svcLight('API Fuse', !_fuseTripped, tripped: _fuseTripped),
          _svcLight('Dorothy', _dorothyRunning > 0, detail: '$_dorothyRunning/$_dorothyTotal'),
          _svcLight('Elphaba', _elphabaRunning > 0, detail: '$_elphabaRunning/$_elphabaTotal'),
          _svcLight('Budget', (_budgetStatus['remaining_pct'] ?? 100) > 10),
        ],
      ),
    );
  }

  Widget _svcLight(String name, bool on, {String? detail, bool tripped = false}) {
    final color = tripped ? Colors.redAccent : (on ? Colors.greenAccent : Colors.grey);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 6, height: 6,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: on ? color : color.withValues(alpha: 0.3),
              boxShadow: on ? [BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 3)] : null,
            ),
          ),
          const SizedBox(width: 4),
          Text(name, style: TextStyle(fontSize: 9, color: color, fontWeight: FontWeight.w600)),
          if (detail != null) ...[
            const SizedBox(width: 3),
            Text(detail, style: TextStyle(fontSize: 8, color: color.withValues(alpha: 0.7), fontFamily: 'monospace')),
          ],
        ],
      ),
    );
  }

  Widget _equityCardsRow() {
    final equity = _wallets['equity'] as Map? ?? {};
    final totalUsdt = double.tryParse('${equity['current'] ?? 0}') ?? 0;
    final spotSummary = _wallets['summary'] as Map? ?? {};
    final spotAssets = (spotSummary['spot_assets'] ?? 0);

    return Row(
      children: [
        _equityCard('Portfolio', '\$${totalUsdt.toStringAsFixed(2)}', const Color(0xFF00E676), '$spotAssets assets'),
        const SizedBox(width: 4),
        _equityCard('Dorothy', '$_dorothyRunning active', Colors.greenAccent, '$_dorothyTotal total'),
        const SizedBox(width: 4),
        _equityCard('Elphaba', '$_elphabaRunning active', const Color(0xFF00E676), '$_elphabaTotal total'),
      ],
    );
  }

  Widget _equityCard(String label, String value, Color color, String subtitle) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: color.withValues(alpha: 0.2)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label, style: TextStyle(fontSize: 8, color: color, fontWeight: FontWeight.w800)),
            const SizedBox(height: 2),
            Text(value, style: TextStyle(fontSize: 13, color: color, fontWeight: FontWeight.w900, fontFamily: 'monospace')),
            Text(subtitle, style: TextStyle(fontSize: 8, color: color.withValues(alpha: 0.6))),
          ],
        ),
      ),
    );
  }

  Widget _operationsPanel() {
    // Collapsed by default — emergency tools, rarely used
    return Container(
      decoration: BoxDecoration(
        color: _opsExpanded ? const Color(0xFF1A0000) : const Color(0xFF0D0D0D),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.redAccent.withValues(alpha: _opsExpanded ? 0.3 : 0.1)),
      ),
      child: Column(
        children: [
          InkWell(
            onTap: () => setState(() => _opsExpanded = !_opsExpanded),
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
              child: Row(
                children: [
                  Icon(Icons.warning_amber_rounded, size: 12,
                      color: Colors.redAccent.withValues(alpha: _opsExpanded ? 1.0 : 0.4)),
                  const SizedBox(width: 4),
                  Text('Operaciones de emergencia',
                      style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700,
                          color: Colors.redAccent.withValues(alpha: _opsExpanded ? 1.0 : 0.4))),
                  const Spacer(),
                  if (_opResult != null)
                    Flexible(
                      child: Text(_opResult!, style: const TextStyle(fontSize: 8, color: Colors.white38, fontFamily: 'monospace'),
                          overflow: TextOverflow.ellipsis),
                    ),
                  Icon(_opsExpanded ? Icons.expand_less : Icons.expand_more, size: 14,
                      color: Colors.redAccent.withValues(alpha: 0.4)),
                ],
              ),
            ),
          ),
          if (_opsExpanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
              child: Wrap(
                spacing: 6,
                runSpacing: 4,
                children: [
                  _opButton('Close Protocol', Icons.cancel_outlined, Colors.orangeAccent, () => _executeOp('close')),
                  _opButton('Cancel Limits', Icons.remove_circle_outline, Colors.amber, () => _executeOp('cancel_limits')),
                  _opButton('Cancel Stops', Icons.remove_circle, Colors.deepOrange, () => _executeOp('cancel_stops')),
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
      height: 28,
      child: OutlinedButton.icon(
        onPressed: _operating ? null : () => _confirmOp(label, onTap),
        icon: Icon(icon, size: 12, color: color),
        label: Text(label, style: TextStyle(fontSize: 9, color: color)),
        style: OutlinedButton.styleFrom(
          side: BorderSide(color: color.withValues(alpha: 0.4)),
          padding: const EdgeInsets.symmetric(horizontal: 8),
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
        case 'close':
          result = await _api.executeCloseProtocol();
          break;
        case 'cancel_limits':
          result = await _api.executeOrderCleanupLimit();
          break;
        case 'cancel_stops':
          result = await _api.executeOrderCleanupStop();
          break;
        case 'red_button':
          result = await _api.executeRedButton();
          break;
        case 'reset_fuse':
          result = await _api.apiFuseReset();
          break;
        default:
          result = {'error': 'Unknown op'};
      }
      if (mounted) setState(() => _opResult = '${result['status'] ?? 'ok'} — ${result['elapsed_sec'] ?? ''}s');
    } catch (e) {
      if (mounted) setState(() => _opResult = 'Error: $e');
    } finally {
      if (mounted) setState(() => _operating = false);
      _refresh();
    }
  }

  Widget _balancesTable() {
    final spotRows = (_wallets['spot'] as List?) ?? [];
    if (spotRows.isEmpty && !_loading) {
      return Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: const Color(0xFF16213E),
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Center(child: Text('No balance data — start gateway first',
            style: TextStyle(color: Colors.white38, fontSize: 11))),
      );
    }

    // Filter to show only symbols with meaningful balances
    final filtered = spotRows.where((r) {
      if (r is! Map) return false;
      final total = double.tryParse('${r['total'] ?? 0}') ?? 0;
      return total > 0;
    }).toList();

    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: const Color(0xFF16213E),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('CONSOLIDATED BALANCES', style: TextStyle(fontSize: 9, color: Colors.white38, fontWeight: FontWeight.w800, letterSpacing: 1)),
              const Spacer(),
              Text('${filtered.length} assets', style: const TextStyle(fontSize: 9, color: Colors.white24)),
            ],
          ),
          const SizedBox(height: 4),
          // Header
          const Row(
            children: [
              SizedBox(width: 60, child: Text('Asset', style: TextStyle(fontSize: 8, color: Colors.white38, fontWeight: FontWeight.w800))),
              Expanded(child: Text('Free', style: TextStyle(fontSize: 8, color: Colors.white38, fontWeight: FontWeight.w800), textAlign: TextAlign.right)),
              Expanded(child: Text('Locked', style: TextStyle(fontSize: 8, color: Colors.white38, fontWeight: FontWeight.w800), textAlign: TextAlign.right)),
              Expanded(child: Text('Total', style: TextStyle(fontSize: 8, color: Colors.white38, fontWeight: FontWeight.w800), textAlign: TextAlign.right)),
            ],
          ),
          const Divider(height: 4, color: Colors.white10),
          ...filtered.take(50).map((r) {
            final m = r as Map;
            final isActive = widget.activeSymbols.any((s) => s.contains('${m['asset']}'));
            return Padding(
              padding: const EdgeInsets.symmetric(vertical: 1),
              child: Row(
                children: [
                  SizedBox(
                    width: 60,
                    child: Row(
                      children: [
                        if (isActive) Container(
                          width: 4, height: 4, margin: const EdgeInsets.only(right: 3),
                          decoration: const BoxDecoration(shape: BoxShape.circle, color: Colors.greenAccent),
                        ),
                        Text('${m['asset']}',
                            style: TextStyle(fontSize: 10, fontWeight: FontWeight.w700,
                                color: isActive ? Colors.greenAccent : Colors.white70,
                                fontFamily: 'monospace')),
                      ],
                    ),
                  ),
                  Expanded(child: Text('${m['free']}', style: const TextStyle(fontSize: 9, color: Colors.white54, fontFamily: 'monospace'), textAlign: TextAlign.right)),
                  Expanded(child: Text('${m['locked']}', style: TextStyle(fontSize: 9, color: (double.tryParse('${m['locked']}') ?? 0) > 0 ? Colors.orangeAccent : Colors.white24, fontFamily: 'monospace'), textAlign: TextAlign.right)),
                  Expanded(child: Text('${m['total']}', style: const TextStyle(fontSize: 9, color: Colors.white70, fontFamily: 'monospace', fontWeight: FontWeight.w600), textAlign: TextAlign.right)),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }
}
