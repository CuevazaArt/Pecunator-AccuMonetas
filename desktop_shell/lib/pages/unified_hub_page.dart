import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../services/preferences.dart';
import '../widgets/mini_charts.dart';
import '../widgets/bot_hub_template.dart';

import '../widgets/emergency_ops_drawer.dart';
import '../widgets/staged_symbol_panel.dart';
import '../widgets/order_ledger_panel.dart';

/// Unified hub page — single view for the entire Pecunator operating console.
///
/// Layout (top → bottom):
///   1. Telemetry bar (weight + equity + spot balances + status lights)
///   2. Emergency Ops (collapsible, collapsed by default)
///   4. Dorothy ↔ Elphaba side-by-side hubs
///   5. Order Ledger (expandable details)
class UnifiedHubPage extends StatefulWidget {
  final String engineBase;

  const UnifiedHubPage({super.key, required this.engineBase});

  @override
  State<UnifiedHubPage> createState() => UnifiedHubPageState();
}

class UnifiedHubPageState extends State<UnifiedHubPage> {
  late final EngineApi _api;
  Timer? _timer;

  bool _fuseTripped = false;
  bool _gatewayRunning = false;

  // Bot lists
  List<Map<String, dynamic>> _dorothyBots = [];
  List<Map<String, dynamic>> _elphabaBots = [];

  String? _stagedSymbol;
  Map<String, Map<String, dynamic>> _savedPresets = {};

  @override
  void initState() {
    super.initState();
    _loadPresets();
    _api = EngineApi(widget.engineBase);
    _poll();
    _timer = Timer.periodic(const Duration(seconds: 8), (_) => _poll());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> forcePoll() async => await _poll();

  Future<void> _poll() async {
    if (!mounted) return;
    try {
      final results = await Future.wait([
        _api.hubBots().catchError((_) => <String, dynamic>{}),
        _api.elphabaBots().catchError((_) => <String, dynamic>{}),
        _api.apiFuseStatus().catchError((_) => <String, dynamic>{}),
        _api.gatewaySnapshot().catchError((_) => <String, dynamic>{}),
      ]);

      final dorBots = ((results[0]['bots'] as List?) ?? []).cast<Map<String, dynamic>>();
      final elpBots = ((results[1]['bots'] as List?) ?? []).cast<Map<String, dynamic>>();

      if (!mounted) return;
      setState(() {
        _dorothyBots = dorBots;
        _elphabaBots = elpBots;
        _fuseTripped = results[2]['tripped'] == true;
        _gatewayRunning = results[3]['gateway_running'] == true;
      });
    } catch (_) {}
  }

  void _loadPresets() {
    try {
      final jsonStr = AppPreferences.savedPresetsJson;
      final decoded = jsonDecode(jsonStr) as Map<String, dynamic>;
      _savedPresets = decoded.map((key, value) => MapEntry(key, Map<String, dynamic>.from(value)));
    } catch (_) {}
  }

  void _handleSymbolSelected(String symbol) {
    setState(() => _stagedSymbol = symbol);
  }

  Future<void> _handleStagedAcceptSymmetric(Map<String, dynamic> dConfig, Map<String, dynamic> eConfig) async {
    try {
      final dorBot = await _api.hubCreateBot(dConfig);
      final elpBot = await _api.elphabaCreateBot(eConfig);

      if (dorBot['bot_id'] != null) {
        _api.hubStartBot(dorBot['bot_id']).catchError((e) { debugPrint('Error auto-starting Dorothy: $e'); return <String, dynamic>{}; });
      }
      if (elpBot['bot_id'] != null) {
        _api.elphabaStartBot(elpBot['bot_id']).catchError((e) { debugPrint('Error auto-starting Elphaba: $e'); return <String, dynamic>{}; });
      }

      setState(() {
        _savedPresets[dConfig['symbol']] = dConfig;
        _savedPresets['${eConfig['symbol']}_elphaba'] = eConfig;
        _stagedSymbol = null;
      });
      AppPreferences.setSavedPresetsJson(jsonEncode(_savedPresets));
      forcePoll();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Símbolo desplegado simétricamente con éxito'), backgroundColor: Colors.green),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.redAccent),
        );
      }
    }
  }

  int get _botsRunning =>
      _dorothyBots.where((b) => b['running'] == true).length +
      _elphabaBots.where((b) => b['running'] == true).length;

  int get _botsTotal => _dorothyBots.length + _elphabaBots.length;

  @override
  Widget build(BuildContext context) {
    const pad = EdgeInsets.symmetric(horizontal: 16);

    return CustomScrollView(
      slivers: [
        // ── 1. Telemetry bar ───────────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 2),
            child: Row(
              children: [
                // Weight chart
                Expanded(
                  flex: 4,
                  child: MiniWeightChart(api: _api, height: 48),
                ),
                const SizedBox(width: 4),
                // Equity chart
                Expanded(
                  flex: 4,
                  child: MiniEquityChart(
                    api: _api,
                    label: 'Equity',
                    color: const Color(0xFF00E676),
                    height: 48,
                    syncInterval: const Duration(seconds: 8),
                  ),
                ),
                const SizedBox(width: 4),
                // Status lights
                StatusLights(
                  gatewayRunning: _gatewayRunning,
                  fuseTripped: _fuseTripped,
                  botsRunning: _botsRunning,
                  botsTotal: _botsTotal,
                ),
              ],
            ),
          ),
        ),



        // ── 2.5 Staged Symbol Panel ────────────────────────────
        if (_stagedSymbol != null)
          SliverToBoxAdapter(
            child: Padding(
              padding: pad,
              child: StagedSymbolPanel(
                symbol: _stagedSymbol!,
                initialPresetDorothy: _savedPresets[_stagedSymbol!],
                initialPresetElphaba: _savedPresets['${_stagedSymbol!}_elphaba'],
                onAcceptSymmetric: _handleStagedAcceptSymmetric,
                onCancel: () => setState(() => _stagedSymbol = null),
              ),
            ),
          ),

        // ── 3. Emergency Ops (collapsed by default) ────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 2),
            child: EmergencyOpsDrawer(api: _api),
          ),
        ),

        // ── 4. Dorothy ↔ Elphaba + Order Ledger ────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 2, 16, 8),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Dorothy (LONG)
                Expanded(
                  flex: 4,
                  child: BotHubTemplate(
                    hubName: 'Dorothy',
                    hubColor: Colors.greenAccent,
                    hubIcon: Icons.trending_up,
                    api: _api,
                    engineBase: widget.engineBase,
                    fetchBots: () async {
                      final resp = await _api.hubBots();
                      final items = resp['bots'];
                      if (items is List) return items.cast<Map<String, dynamic>>();
                      return [];
                    },
                    createBot: (config) async => await _api.hubCreateBot(config),
                    startBot: (id) async => await _api.hubStartBot(id),
                    stopBot: (id) async => await _api.hubStopBot(id),
                    deleteBot: (id) async => await _api.hubDeleteBot(id),
                    fetchLogs: (id) async {
                      try {
                        final resp = await _api.hubLogs(id, limit: 50);
                        final items = resp['logs'];
                        if (items is List) return items.map((e) => '$e').toList();
                      } catch (_) {}
                      return [];
                    },
                  ),
                ),
                Container(
                  width: 1,
                  margin: const EdgeInsets.symmetric(vertical: 8),
                  color: Colors.white.withValues(alpha: 0.06),
                ),
                // Elphaba (SHORT)
                Expanded(
                  flex: 4,
                  child: BotHubTemplate(
                    hubName: 'Elphaba',
                    hubColor: const Color(0xFF00E676),
                    hubIcon: Icons.bolt,
                    api: _api,
                    engineBase: widget.engineBase,
                    fetchBots: () async {
                      final resp = await _api.elphabaBots();
                      final items = resp['bots'];
                      if (items is List) return items.cast<Map<String, dynamic>>();
                      return [];
                    },
                    createBot: (config) async => await _api.elphabaCreateBot(config),
                    startBot: (id) async => await _api.elphabaStartBot(id),
                    stopBot: (id) async => await _api.elphabaStopBot(id),
                    deleteBot: (id) async => await _api.elphabaDeleteBot(id),
                    fetchLogs: (id) async {
                      try {
                        final resp = await _api.elphabaLogs(id, limit: 50);
                        final items = resp['logs'];
                        if (items is List) return items.map((e) => '$e').toList();
                      } catch (_) {}
                      return [];
                    },
                  ),
                ),
                const SizedBox(width: 4),
                // Order Ledger
                Expanded(
                  flex: 3,
                  child: OrderLedgerPanel(api: _api),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
