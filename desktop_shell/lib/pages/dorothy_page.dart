import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/bot_hub_template.dart';

/// Dedicated Dorothy Hub page — uses shared BotHubTemplate.
/// Dorothy is a trend-following scalper that buys market + sells limit.
class DorothyPage extends StatelessWidget {
  final String engineBase;

  const DorothyPage({super.key, required this.engineBase});

  EngineApi get _api => EngineApi(engineBase);

  @override
  Widget build(BuildContext context) {
    return BotHubTemplate(
      hubName: 'Dorothy',
      hubColor: Colors.greenAccent,
      hubIcon: Icons.trending_up,
      api: _api,
      engineBase: engineBase,
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
      formFields: const [
        BotFormField(key: 'tag', label: 'Tag', hint: 'scalper-btc', defaultValue: 'dorothy'),
        BotFormField(key: 'symbol', label: 'Symbol', hint: 'BTCUSDT', defaultValue: 'XRPUSDT'),
        BotFormField(key: 'loop_interval_sec', label: 'Loop (s)', hint: '35', defaultValue: '35',
            inputType: TextInputType.number),
        BotFormField(key: 'quote_order_qty', label: 'Qty USDT', hint: '8', defaultValue: '8',
            inputType: TextInputType.number),
        BotFormField(key: 'profit_factor', label: 'Profit %', hint: '1.05', defaultValue: '1.05',
            inputType: TextInputType.number),
        BotFormField(key: 'drop_factor', label: 'Drop %', hint: '0.97', defaultValue: '0.97',
            inputType: TextInputType.number),
        BotFormField(key: 'note', label: 'Nota', hint: 'descripción'),
      ],
    );
  }
}
