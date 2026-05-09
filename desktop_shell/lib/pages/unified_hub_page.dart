import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/mini_charts.dart';
import '../widgets/hub_status_explainer.dart';
import '../widgets/bot_instances_paired.dart';
import '../widgets/bot_hub_template.dart';
import '../widgets/prospector_expander.dart';
import '../widgets/account_system_drawer.dart';

/// Unified hub page — single view for the entire Pecunator operating console.
///
/// Layout (top → bottom, minimal scroll):
///   1. Prospector (collapsible)
///   2. Telemetry row (weight chart + oscillator + equity)
///   3. Hub status + paired instances
///   4. Dorothy ↔ Elphaba side-by-side hubs
///   5. System drawer (collapsible: balances, budget, ledger, guards, ops)
class UnifiedHubPage extends StatefulWidget {
  final String engineBase;

  const UnifiedHubPage({super.key, required this.engineBase});

  @override
  State<UnifiedHubPage> createState() => UnifiedHubPageState();
}

class UnifiedHubPageState extends State<UnifiedHubPage> {
  late final EngineApi _api;
  Timer? _timer;
  String? _injectedSymbol;

  // Dorothy + Elphaba reports for HubStatusExplainer
  Map<String, dynamic> _dorothyReport = {};
  Map<String, dynamic> _elphabaReport = {};
  bool _fuseTripped = false;
  bool _budgetBlocked = false;

  // Bot lists for paired instances
  List<Map<String, dynamic>> _dorothyBots = [];
  List<Map<String, dynamic>> _elphabaBots = [];

  @override
  void initState() {
    super.initState();
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
        _api.budgetGuardStatus().catchError((_) => <String, dynamic>{}),
      ]);

      final dorBots = ((results[0]['items'] as List?) ?? []).cast<Map<String, dynamic>>();
      final elpBots = ((results[1]['items'] as List?) ?? []).cast<Map<String, dynamic>>();

      // Find a running bot to get the last report
      Map<String, dynamic> dorReport = {};
      Map<String, dynamic> elpReport = {};
      for (final b in dorBots) {
        if (b['running'] == true && b['last_report'] is Map) {
          dorReport = (b['last_report'] as Map).cast<String, dynamic>();
          break;
        }
      }
      for (final b in elpBots) {
        if (b['running'] == true && b['last_report'] is Map) {
          elpReport = (b['last_report'] as Map).cast<String, dynamic>();
          break;
        }
      }

      if (!mounted) return;
      setState(() {
        _dorothyBots = dorBots;
        _elphabaBots = elpBots;
        _dorothyReport = dorReport;
        _elphabaReport = elpReport;
        _fuseTripped = results[2]['tripped'] == true;
        _budgetBlocked = results[3]['blocked'] == true;
      });
    } catch (_) {}
  }

  void _handleSymbolSelected(String symbol) {
    setState(() => _injectedSymbol = symbol);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Símbolo inyectado: $symbol → configurar en los hubs abajo'),
        backgroundColor: Colors.greenAccent.withValues(alpha: 0.8),
        duration: const Duration(seconds: 3),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return CustomScrollView(
      slivers: [
        // ── 1. Prospector (collapsible) ────────────────────────
        SliverToBoxAdapter(
          child: ProspectorExpander(
            api: _api,
            onSymbolSelected: _handleSymbolSelected,
          ),
        ),

        // ── 2. Telemetry row ───────────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            child: Row(
              children: [
                Expanded(
                  flex: 3,
                  child: MiniWeightChart(api: _api, height: 48),
                ),
                const SizedBox(width: 4),
                Expanded(
                  flex: 3,
                  child: WeightOscillator(api: _api, height: 48),
                ),
                const SizedBox(width: 4),
                Expanded(
                  flex: 3,
                  child: MiniEquityChart(
                    api: _api,
                    label: 'Equity',
                    color: const Color(0xFF00E676),
                    height: 48,
                    syncInterval: const Duration(seconds: 8),
                  ),
                ),
                const SizedBox(width: 4),
                Expanded(
                  flex: 2,
                  child: StatusLights(
                    gatewayRunning: _dorothyBots.isNotEmpty || _elphabaBots.isNotEmpty,
                    fuseTripped: _fuseTripped,
                    botsRunning: _dorothyBots.where((b) => b['running'] == true).length +
                        _elphabaBots.where((b) => b['running'] == true).length,
                    botsTotal: _dorothyBots.length + _elphabaBots.length,
                  ),
                ),
              ],
            ),
          ),
        ),

        // ── 3. Hub status + Paired instances ───────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Hub explainer
                Expanded(
                  flex: 4,
                  child: HubStatusExplainer(
                    dorothyReport: _dorothyReport,
                    elphabaReport: _elphabaReport,
                    fuseTripped: _fuseTripped,
                    budgetBlocked: _budgetBlocked,
                  ),
                ),
                const SizedBox(width: 4),
                // Paired instances
                Expanded(
                  flex: 5,
                  child: BotInstancesPairedList(
                    dorothyBots: _dorothyBots,
                    elphabaBots: _elphabaBots,
                  ),
                ),
              ],
            ),
          ),
        ),

        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // ── Dorothy (LONG) ──────────────────────────
                Expanded(
                  child: BotHubTemplate(
                    hubName: 'Dorothy',
                    hubColor: Colors.greenAccent,
                    hubIcon: Icons.trending_up,
                    api: _api,
                    engineBase: widget.engineBase,
                    fetchBots: () async {
                      final resp = await _api.hubBots();
                      final items = resp['items'];
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
                        final items = resp['items'];
                        if (items is List) return items.map((e) => '$e').toList();
                      } catch (_) {}
                      return [];
                    },
                    formFields: [
                      const BotFormField(key: 'tag', label: 'Tag', hint: 'dorothy-ton', defaultValue: 'dorothy',
                          tooltip: 'Identificador único de la instancia'),
                      BotFormField(key: 'symbol', label: 'Symbol', hint: 'TONUSDT', defaultValue: _injectedSymbol ?? 'TONUSDT',
                          tooltip: 'Par de trading (debe tener margen aislado)'),
                      const BotFormField(key: 'loop_interval_sec', label: 'Loop (s)', hint: '60', defaultValue: '60',
                          inputType: TextInputType.number, tooltip: 'Intervalo entre ciclos (L0: 60s)'),
                      const BotFormField(key: 'quote_order_qty', label: 'Qty USDT', hint: '6', defaultValue: '6',
                          inputType: TextInputType.number, tooltip: 'USDT por rung (L0: \$6)'),
                      const BotFormField(key: 'profit_factor', label: 'Profit %', hint: '0.03', defaultValue: '0.03',
                          inputType: TextInputType.number, tooltip: 'Porcentaje de ganancia objetivo'),
                      const BotFormField(key: 'drop_factor', label: 'Drop %', hint: '0.02', defaultValue: '0.02',
                          inputType: TextInputType.number, tooltip: 'Caída para abrir siguiente rung DCA'),
                      const BotFormField(key: 'note', label: 'Nota', hint: 'descripción',
                          tooltip: 'Nota libre para identificar la instancia'),
                    ],
                  ),
                ),
                // ── Divider ─────────────────────────────────
                Container(
                  width: 1,
                  margin: const EdgeInsets.symmetric(vertical: 8),
                  color: Colors.white.withValues(alpha: 0.08),
                ),
                // ── Elphaba (SHORT) ─────────────────────────
                Expanded(
                  child: BotHubTemplate(
                    hubName: 'Elphaba',
                    hubColor: const Color(0xFF00E676),
                    hubIcon: Icons.bolt,
                    api: _api,
                    engineBase: widget.engineBase,
                    fetchBots: () async {
                      final resp = await _api.elphabaBots();
                      final items = resp['items'];
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
                        final items = resp['items'];
                        if (items is List) return items.map((e) => '$e').toList();
                      } catch (_) {}
                      return [];
                    },
                    formFields: [
                      const BotFormField(key: 'tag', label: 'Tag', hint: 'elphaba-ton', defaultValue: 'elphaba',
                          tooltip: 'Identificador único de la instancia'),
                      BotFormField(key: 'symbol', label: 'Symbol', hint: 'TONUSDT', defaultValue: _injectedSymbol ?? 'TONUSDT',
                          tooltip: 'Par de trading (debe coincidir con Dorothy)'),
                      const BotFormField(key: 'loop_interval_sec', label: 'Loop (s)', hint: '60', defaultValue: '60',
                          inputType: TextInputType.number, tooltip: 'Intervalo entre ciclos'),
                      const BotFormField(key: 'quote_order_qty', label: 'Qty USDT', hint: '6', defaultValue: '6',
                          inputType: TextInputType.number, tooltip: 'USDT por operación short'),
                      const BotFormField(key: 'profit_factor', label: 'Profit %', hint: '0.03', defaultValue: '0.03',
                          inputType: TextInputType.number, tooltip: 'Porcentaje de ganancia'),
                      const BotFormField(key: 'margin_rise_factor', label: 'Rise %', hint: '0.03', defaultValue: '0.03',
                          inputType: TextInputType.number, tooltip: 'Subida para abrir siguiente rung short'),
                      const BotFormField(key: 'note', label: 'Nota', hint: 'descripción',
                          tooltip: 'Nota libre para identificar la instancia'),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),

        // ── 5. System drawer (collapsible) ─────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            child: AccountSystemDrawer(api: _api),
          ),
        ),

        // Bottom padding
        const SliverToBoxAdapter(child: SizedBox(height: 8)),
      ],
    );
  }
}
