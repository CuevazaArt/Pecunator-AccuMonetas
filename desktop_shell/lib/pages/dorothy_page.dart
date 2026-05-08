import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/bot_hub_template.dart';
import '../widgets/prospector_panel.dart';

/// Dedicated Dorothy Hub page — uses shared BotHubTemplate + Prospector.
/// Dorothy is a trend-following scalper that buys market + sells limit.
class DorothyPage extends StatefulWidget {
  final String engineBase;

  const DorothyPage({super.key, required this.engineBase});

  @override
  State<DorothyPage> createState() => _DorothyPageState();
}

class _DorothyPageState extends State<DorothyPage> {
  EngineApi get _api => EngineApi(widget.engineBase);

  /// When the user taps "Use" on a prospector result, this propagates
  /// down to the BotHubTemplate's symbol field via a rebuild.
  String? _injectedSymbol;

  void _onSymbolSelected(String symbol) {
    setState(() => _injectedSymbol = symbol);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('Symbol $symbol loaded into form'),
        backgroundColor: Colors.greenAccent.withValues(alpha: 0.8),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        // ── Prospector panel (top, collapsible, fixed height) ─────
        Padding(
          padding: const EdgeInsets.fromLTRB(8, 8, 8, 0),
          child: _ProspectorExpander(
            api: _api,
            onSymbolSelected: _onSymbolSelected,
          ),
        ),
        const SizedBox(height: 4),
        // ── Standard Dorothy Hub (scrollable) ─────────────────────
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
              const BotFormField(key: 'tag', label: 'Tag', hint: 'scalper-btc', defaultValue: 'dorothy'),
              BotFormField(
                key: 'symbol', label: 'Symbol', hint: 'BTCUSDT',
                defaultValue: _injectedSymbol ?? 'XRPUSDT',
              ),
              const BotFormField(key: 'loop_interval_sec', label: 'Loop (s)', hint: '35', defaultValue: '35',
                  inputType: TextInputType.number),
              const BotFormField(key: 'quote_order_qty', label: 'Qty USDT', hint: '8', defaultValue: '8',
                  inputType: TextInputType.number),
              const BotFormField(key: 'profit_factor', label: 'Profit %', hint: '1.05', defaultValue: '1.05',
                  inputType: TextInputType.number),
              const BotFormField(key: 'drop_factor', label: 'Drop %', hint: '0.97', defaultValue: '0.97',
                  inputType: TextInputType.number),
              const BotFormField(key: 'qty_decimals', label: 'Qty Dec', hint: '8', defaultValue: '8',
                  inputType: TextInputType.number),
              const BotFormField(key: 'price_decimals', label: 'Price Dec', hint: '4', defaultValue: '4',
                  inputType: TextInputType.number),
              const BotFormField(key: 'max_drawdown_pct', label: 'Max DD %', hint: '0.20', defaultValue: '0.20',
                  inputType: TextInputType.number),
              const BotFormField(key: 'metrics_every', label: 'Metrics N', hint: '5', defaultValue: '5',
                  inputType: TextInputType.number),
              const BotFormField(key: 'note', label: 'Nota', hint: 'descripción'),
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
                    'Find the best symbol for DCA',
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
