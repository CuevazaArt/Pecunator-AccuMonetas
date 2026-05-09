import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/bot_hub_template.dart';

class ElphabaHubPage extends StatelessWidget {
  final String engineBase;

  const ElphabaHubPage({super.key, required this.engineBase});

  EngineApi get _api => EngineApi(engineBase);

  @override
  Widget build(BuildContext context) {
    return BotHubTemplate(
      hubName: 'Elphaba',
      hubColor: const Color(0xFF00E676),
      hubIcon: Icons.bolt,
      api: _api,
      engineBase: engineBase,
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
      formFields: const [
        BotFormField(key: 'tag', label: 'Tag', hint: 'elphaba-ton', defaultValue: 'elphaba',
            tooltip: 'Identificador único de la instancia'),
        BotFormField(key: 'symbol', label: 'Symbol', hint: 'TONUSDT', defaultValue: 'TONUSDT',
            tooltip: 'Par de trading (debe coincidir con Dorothy para simetría)'),
        BotFormField(key: 'loop_interval_sec', label: 'Loop (s)', hint: '60', defaultValue: '60',
            inputType: TextInputType.number, tooltip: 'Intervalo entre ciclos (debe coincidir con Dorothy)'),
        BotFormField(key: 'quote_order_qty', label: 'Qty USDT', hint: '6', defaultValue: '6',
            inputType: TextInputType.number, tooltip: 'USDT por operación short (L0: \$6)'),
        BotFormField(key: 'profit_factor', label: 'Profit %', hint: '0.03', defaultValue: '0.03',
            inputType: TextInputType.number, tooltip: 'Porcentaje de ganancia objetivo por short'),
        BotFormField(key: 'margin_rise_factor', label: 'Rise %', hint: '0.03', defaultValue: '0.03',
            inputType: TextInputType.number, tooltip: 'Subida porcentual para abrir siguiente rung short'),
        BotFormField(key: 'note', label: 'Nota', hint: 'descripción',
            tooltip: 'Nota libre para identificar la instancia'),
      ],
    );
  }
}
