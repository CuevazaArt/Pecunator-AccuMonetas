import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/bot_hub_template.dart';

class ThusneldaHubPage extends StatelessWidget {
  final String engineBase;

  const ThusneldaHubPage({super.key, required this.engineBase});

  EngineApi get _api => EngineApi(engineBase);

  @override
  Widget build(BuildContext context) {
    return BotHubTemplate(
      hubName: 'Thusnelda',
      hubColor: const Color(0xFFFFD600),
      hubIcon: Icons.hub_outlined,
      api: _api,
      engineBase: engineBase,
      fetchBots: () async {
        final resp = await _api.thusneldaBots();
        final items = resp['items'];
        if (items is List) return items.cast<Map<String, dynamic>>();
        return [];
      },
      createBot: (config) async {
        await _api.thusneldaCreateBot(config);
      },
      startBot: (id) async {
        await _api.thusneldaStartBot(id);
      },
      stopBot: (id) async {
        await _api.thusneldaStopBot(id);
      },
      deleteBot: (id) async {
        await _api.thusneldaDeleteBot(id);
      },
      fetchLogs: (id) async {
        try {
          final resp = await _api.thusneldaLogs(id, limit: 50);
          final items = resp['items'];
          if (items is List) return items.map((e) => '$e').toList();
        } catch (_) {}
        return [];
      },
      formFields: const [
        BotFormField(key: 'tag', label: 'Tag', hint: 'thu-volatile', defaultValue: 'thu-basket'),
        BotFormField(key: 'symbols', label: 'Symbols', hint: 'PEPE,SUI,NEAR', defaultValue: 'PEPEUSDT,SUIUSDT,NEARUSDT,INJUSDT,FETUSDT'),
        BotFormField(key: 'interval_sec', label: 'Loop (s)', hint: '60', defaultValue: '60',
            inputType: TextInputType.number),
        BotFormField(key: 'quote_order_qty_modulo', label: 'Qty USDT', hint: '8', defaultValue: '8',
            inputType: TextInputType.number),
        BotFormField(key: 'qty_decimals', label: 'Qty Dec', hint: '0', defaultValue: '0',
            inputType: TextInputType.number),
        BotFormField(key: 'price_decimals', label: 'Price Dec', hint: '8', defaultValue: '8',
            inputType: TextInputType.number),
        BotFormField(key: 'max_drawdown_pct', label: 'Max DD %', hint: '0.20', defaultValue: '0.20',
            inputType: TextInputType.number),
        BotFormField(key: 'note', label: 'Nota', hint: 'descripción'),
      ],
    );
  }
}
