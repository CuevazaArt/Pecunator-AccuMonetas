import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/bot_hub_template.dart';
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
    return Column(
      children: [
        // ── Prospector panel (shared, top) ─────────────────────
        Padding(
          padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
          child: _ProspectorExpander(
            api: _api,
            onSymbolSelected: _onSymbolSelected,
          ),
        ),
        const SizedBox(height: 4),
        // ── Side-by-side hubs ─────────────────────────────────
        Expanded(
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── Dorothy (LONG) ──────────────────────────────
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
              // ── Divider ──────────────────────────────────────
              Container(
                width: 1,
                margin: const EdgeInsets.symmetric(vertical: 8),
                color: Colors.white.withValues(alpha: 0.08),
              ),
              // ── Elphaba (SHORT) ─────────────────────────────
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
      ],
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
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            borderRadius: BorderRadius.circular(10),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              child: Row(
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
                  const SizedBox(width: 8),
                  Text(
                    'Selecciona símbolo para ambos lados del hub',
                    style: TextStyle(
                      fontSize: 9,
                      color: Colors.white.withValues(alpha: 0.25),
                    ),
                  ),
                  const Spacer(),
                  Icon(
                    _expanded ? Icons.expand_less : Icons.expand_more,
                    size: 16,
                    color: Colors.white30,
                  ),
                ],
              ),
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
