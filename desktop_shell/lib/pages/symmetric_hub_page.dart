import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/bot_hub_template.dart';
import '../widgets/bot_instances_paired.dart';
import '../widgets/hub_status_explainer.dart';
import '../widgets/mini_charts.dart';
import '../widgets/prospector_panel.dart';

/// Unified Symmetric Hub page — Dorothy + Elphaba side-by-side.
///
/// L0 Doctrine: there is no Dorothy without Elphaba. Both sides must
/// be visible simultaneously so asymmetry is detected immediately.
class SymmetricHubPage extends StatefulWidget {
  final String engineBase;

  const SymmetricHubPage({super.key, required this.engineBase});

  @override
  State<SymmetricHubPage> createState() => _SymmetricHubPageState();
}

class _SymmetricHubPageState extends State<SymmetricHubPage> {
  EngineApi get _api => EngineApi(widget.engineBase);

  String? _injectedSymbol;
  Timer? _statusTimer;
  Map<String, dynamic> _dorothyReport = {};
  Map<String, dynamic> _elphabaReport = {};
  List<Map<String, dynamic>> _dorothyBots = [];
  List<Map<String, dynamic>> _elphabaBots = [];
  bool _fuseTripped = false;
  bool _budgetBlocked = false;

  @override
  void initState() {
    super.initState();
    _refreshStatus();
    _statusTimer = Timer.periodic(const Duration(seconds: 10), (_) => _refreshStatus());
  }

  @override
  void dispose() {
    _statusTimer?.cancel();
    super.dispose();
  }

  Future<void> _refreshStatus() async {
    try {
      final dorothy = await _api.hubBots();
      final elphaba = await _api.elphabaBots();
      final dorBots = (dorothy['bots'] as List?) ?? [];
      final elpBots = (elphaba['bots'] as List?) ?? [];
      // Find running bots' last_report
      Map<String, dynamic> dorReport = {};
      Map<String, dynamic> elpReport = {};
      for (final b in dorBots) {
        if (b is Map && b['running'] == true && (b['last_report'] as Map?)?.isNotEmpty == true) {
          dorReport = Map<String, dynamic>.from(b['last_report'] as Map);
          break;
        }
      }
      for (final b in elpBots) {
        if (b is Map && b['running'] == true && (b['last_report'] as Map?)?.isNotEmpty == true) {
          elpReport = Map<String, dynamic>.from(b['last_report'] as Map);
          break;
        }
      }
      bool fuse = false;
      try { final fs = await _api.apiFuseStatus(); fuse = fs['tripped'] == true; } catch (_) {}
      bool budget = false;
      try { final bs = await _api.budgetGuardStatus(); budget = bs['blocked'] == true; } catch (_) {}
      if (!mounted) return;
      setState(() {
        _dorothyReport = dorReport;
        _elphabaReport = elpReport;
        _dorothyBots = dorBots.whereType<Map<String, dynamic>>().toList();
        _elphabaBots = elpBots.whereType<Map<String, dynamic>>().toList();
        _fuseTripped = fuse;
        _budgetBlocked = budget;
      });
    } catch (_) {}
  }

  void _onSymbolSelected(String symbol) {
    setState(() => _injectedSymbol = symbol);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Symbol $symbol loaded into both sides'),
        backgroundColor: Colors.greenAccent.withValues(alpha: 0.8),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        // Reserve space for the side-by-side hubs at the bottom
        // Minimum hub height ensures they remain usable
        const double minHubHeight = 200;
        return Column(
          children: [
            // ── Scrollable top section ─────────────────────────
            Expanded(
              child: CustomScrollView(
                slivers: [
                  // Prospector panel
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
                      child: _ProspectorExpander(
                        api: _api,
                        onSymbolSelected: _onSymbolSelected,
                      ),
                    ),
                  ),
                  const SliverToBoxAdapter(child: SizedBox(height: 4)),
                  // Shared Telemetry
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
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
                          const SizedBox(width: 6),
                          Expanded(
                            flex: 3,
                            child: MiniEquityChart(
                              api: _api,
                              label: 'Dorothy',
                              color: Colors.greenAccent,
                              height: 48,
                            ),
                          ),
                          const SizedBox(width: 4),
                          Expanded(
                            flex: 3,
                            child: MiniEquityChart(
                              api: _api,
                              label: 'Elphaba',
                              color: const Color(0xFF00E676),
                              height: 48,
                            ),
                          ),
                          const SizedBox(width: 4),
                          Expanded(
                            flex: 3,
                            child: MiniEquityChart(
                              api: _api,
                              label: 'Global',
                              color: const Color(0xFF448AFF),
                              height: 48,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SliverToBoxAdapter(child: SizedBox(height: 4)),
                  // Hub Status Explainer
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      child: HubStatusExplainer(
                        dorothyReport: _dorothyReport,
                        elphabaReport: _elphabaReport,
                        fuseTripped: _fuseTripped,
                        budgetBlocked: _budgetBlocked,
                      ),
                    ),
                  ),
                  const SliverToBoxAdapter(child: SizedBox(height: 4)),
                  // Paired Instances List
                  SliverToBoxAdapter(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      child: BotInstancesPairedList(
                        dorothyBots: _dorothyBots,
                        elphabaBots: _elphabaBots,
                      ),
                    ),
                  ),
                  const SliverToBoxAdapter(child: SizedBox(height: 4)),
                  // ── Side-by-side hubs ────────────────────────
                  SliverToBoxAdapter(
                    child: SizedBox(
                      height: (constraints.maxHeight * 0.55).clamp(minHubHeight, 600),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          // ── Dorothy (LONG) ──────────────────
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
                              createBot: (config) async {
                                await _api.hubCreateBot(config);
                              },
                              startBot: (id) async {
                                await _api.hubStartBot(id);
                              },
                              stopBot: (id) async {
                                await _api.hubStopBot(id);
                              },
                              deleteBot: (id) async {
                                await _api.hubDeleteBot(id);
                              },
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
                                BotFormField(
                                  key: 'symbol', label: 'Symbol', hint: 'TONUSDT',
                                  defaultValue: _injectedSymbol ?? 'TONUSDT',
                                  tooltip: 'Par de trading (debe tener margen aislado)',
                                ),
                                const BotFormField(key: 'loop_interval_sec', label: 'Loop (s)', hint: '60', defaultValue: '60',
                                    inputType: TextInputType.number, tooltip: 'Intervalo entre ciclos de análisis (L0: 60s)'),
                                const BotFormField(key: 'quote_order_qty', label: 'Qty USDT', hint: '6', defaultValue: '6',
                                    inputType: TextInputType.number, tooltip: 'USDT por rung/escalón (L0 Doctrine: \$6)'),
                                const BotFormField(key: 'profit_factor', label: 'Profit %', hint: '0.03', defaultValue: '0.03',
                                    inputType: TextInputType.number, tooltip: 'Porcentaje de ganancia objetivo por operación'),
                                const BotFormField(key: 'drop_factor', label: 'Drop %', hint: '0.02', defaultValue: '0.02',
                                    inputType: TextInputType.number, tooltip: 'Caída porcentual para abrir siguiente rung DCA'),
                                const BotFormField(key: 'note', label: 'Nota', hint: 'descripción',
                                    tooltip: 'Nota libre para identificar la instancia'),
                              ],
                            ),
                          ),
                          // ── Divider ──────────────────────────
                          Container(
                            width: 1,
                            margin: const EdgeInsets.symmetric(vertical: 8),
                            color: Colors.white.withValues(alpha: 0.08),
                          ),
                          // ── Elphaba (SHORT) ─────────────────
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
                              createBot: (config) async {
                                await _api.elphabaCreateBot(config);
                              },
                              startBot: (id) async {
                                await _api.elphabaStartBot(id);
                              },
                              stopBot: (id) async {
                                await _api.elphabaStopBot(id);
                              },
                              deleteBot: (id) async {
                                await _api.elphabaDeleteBot(id);
                              },
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
                                BotFormField(
                                  key: 'symbol', label: 'Symbol', hint: 'TONUSDT',
                                  defaultValue: _injectedSymbol ?? 'TONUSDT',
                                  tooltip: 'Par de trading (debe coincidir con Dorothy)',
                                ),
                                const BotFormField(key: 'loop_interval_sec', label: 'Loop (s)', hint: '60', defaultValue: '60',
                                    inputType: TextInputType.number, tooltip: 'Intervalo entre ciclos (debe coincidir con Dorothy)'),
                                const BotFormField(key: 'quote_order_qty', label: 'Qty USDT', hint: '6', defaultValue: '6',
                                    inputType: TextInputType.number, tooltip: 'USDT por operación short (L0: \$6)'),
                                const BotFormField(key: 'profit_factor', label: 'Profit %', hint: '0.03', defaultValue: '0.03',
                                    inputType: TextInputType.number, tooltip: 'Porcentaje de ganancia objetivo por short'),
                                const BotFormField(key: 'margin_rise_factor', label: 'Rise %', hint: '0.03', defaultValue: '0.03',
                                    inputType: TextInputType.number, tooltip: 'Subida porcentual para abrir siguiente rung short'),
                                const BotFormField(key: 'note', label: 'Nota', hint: 'descripción',
                                    tooltip: 'Nota libre para identificar la instancia'),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}

/// Collapsible prospector section with animated expand/collapse.
class _ProspectorExpander extends StatefulWidget {
  final EngineApi api;
  final void Function(String symbol) onSymbolSelected;

  const _ProspectorExpander({
    required this.api,
    required this.onSymbolSelected,
  });

  @override
  State<_ProspectorExpander> createState() => _ProspectorExpanderState();
}

class _ProspectorExpanderState extends State<_ProspectorExpander> {
  bool _expanded = false;
  final _manualCtrl = TextEditingController();

  @override
  void dispose() {
    _manualCtrl.dispose();
    super.dispose();
  }

  void _submitManual() {
    final raw = _manualCtrl.text.trim().toUpperCase();
    if (raw.isEmpty) return;
    // Append USDT if user forgot
    final symbol = raw.endsWith('USDT') ? raw : '${raw}USDT';
    widget.onSymbolSelected(symbol);
    _manualCtrl.clear();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(milliseconds: 250),
      curve: Curves.easeInOut,
      decoration: BoxDecoration(
        color: const Color(0xFF0A1628),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(
          color: _expanded
              ? Colors.greenAccent.withValues(alpha: 0.25)
              : Colors.white.withValues(alpha: 0.05),
        ),
      ),
      child: Column(
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            child: Row(
              children: [
                // ── Prospector toggle ─────────────────────────
                InkWell(
                  onTap: () => setState(() => _expanded = !_expanded),
                  borderRadius: BorderRadius.circular(6),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.radar, size: 14,
                          color: _expanded ? Colors.greenAccent : Colors.white38),
                      const SizedBox(width: 6),
                      Text(
                        'SYMBOL PROSPECTOR',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.w800,
                          letterSpacing: 1.2,
                          color: _expanded ? Colors.greenAccent : Colors.white38,
                        ),
                      ),
                      const SizedBox(width: 4),
                      Icon(
                        _expanded ? Icons.expand_less : Icons.expand_more,
                        size: 16,
                        color: Colors.white30,
                      ),
                    ],
                  ),
                ),
                const Spacer(),
                // ── Manual symbol input ──────────────────────
                SizedBox(
                  width: 130,
                  height: 24,
                  child: TextField(
                    controller: _manualCtrl,
                    style: const TextStyle(
                      fontSize: 10,
                      color: Colors.white,
                      fontFamily: 'monospace',
                    ),
                    textInputAction: TextInputAction.go,
                    onSubmitted: (_) => _submitManual(),
                    decoration: InputDecoration(
                      hintText: 'BTCUSDT',
                      hintStyle: TextStyle(
                        fontSize: 10,
                        color: Colors.white.withValues(alpha: 0.2),
                        fontFamily: 'monospace',
                      ),
                      contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 0),
                      filled: true,
                      fillColor: Colors.white.withValues(alpha: 0.05),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(4),
                        borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.1)),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(4),
                        borderSide: BorderSide(color: Colors.white.withValues(alpha: 0.1)),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(4),
                        borderSide: const BorderSide(color: Colors.amberAccent, width: 1),
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 4),
                SizedBox(
                  height: 24,
                  child: OutlinedButton(
                    onPressed: _submitManual,
                    style: OutlinedButton.styleFrom(
                      side: BorderSide(color: Colors.amberAccent.withValues(alpha: 0.5)),
                      foregroundColor: Colors.amberAccent,
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      minimumSize: Size.zero,
                    ),
                    child: const Text('Go', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700)),
                  ),
                ),
              ],
            ),
          ),
          if (_expanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(8, 0, 8, 8),
              child: ProspectorPanel(
                api: widget.api,
                accentColor: Colors.greenAccent,
                onSymbolSelected: widget.onSymbolSelected,
              ),
            ),
        ],
      ),
    );
  }
}
