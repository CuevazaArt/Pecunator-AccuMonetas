import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/bot_hub_template.dart';

class MashaHubPage extends StatelessWidget {
  final String engineBase;

  const MashaHubPage({super.key, required this.engineBase});

  EngineApi get _api => EngineApi(engineBase);

  @override
  Widget build(BuildContext context) {
    return BotHubTemplate(
      hubName: 'Masha',
      hubColor: const Color(0xFF448AFF),
      hubIcon: Icons.psychology_alt_outlined,
      api: _api,
      engineBase: engineBase,
      fetchBots: () async {
        final resp = await _api.mashaBots();
        final items = resp['items'];
        if (items is List) return items.cast<Map<String, dynamic>>();
        return [];
      },
      createBot: (config) async {
        await _api.mashaCreateBot(config);
      },
      startBot: (id) async {
        await _api.mashaStartBot(id);
      },
      stopBot: (id) async {
        await _api.mashaStopBot(id);
      },
      deleteBot: (id) async {
        await _api.mashaDeleteBot(id);
      },
      fetchLogs: (id) async {
        try {
          final resp = await _api.mashaLogs(id, limit: 50);
          final items = resp['items'];
          if (items is List) return items.map((e) => '$e').toList();
        } catch (_) {}
        return [];
      },
      formFields: const [
        BotFormField(key: 'tag', label: 'Tag', hint: 'masha-btc', defaultValue: 'masha-dca'),
        BotFormField(key: 'symbol', label: 'Symbol', hint: 'BTCUSDT', defaultValue: 'BTCUSDT'),
        BotFormField(key: 'base_asset', label: 'Base', hint: 'BTC', defaultValue: 'BTC'),
        BotFormField(key: 'quote_asset', label: 'Quote', hint: 'USDT', defaultValue: 'USDT'),
        BotFormField(key: 'interval_sec', label: 'Loop (s)', hint: '55', defaultValue: '55',
            inputType: TextInputType.number),
        BotFormField(key: 'buy_qty', label: 'Buy Qty', hint: '0.001', defaultValue: '0.001',
            inputType: TextInputType.number),
        BotFormField(key: 'max_drawdown_pct', label: 'Max DD %', hint: '0.20', defaultValue: '0.20',
            inputType: TextInputType.number),
        BotFormField(key: 'note', label: 'Nota', hint: 'descripción'),
      ],
    );
  }
}
