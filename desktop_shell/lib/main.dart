import 'dart:convert';

import 'package:flutter/material.dart';

import 'api_client.dart';

void main() {
  runApp(const PecunatorDesktopApp());
}

class PecunatorDesktopApp extends StatelessWidget {
  const PecunatorDesktopApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Pecunator Desktop',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueGrey),
      ),
      darkTheme: ThemeData.dark(useMaterial3: true),
      themeMode: ThemeMode.dark,
      home: const BotControlPage(),
    );
  }
}

class BotControlPage extends StatefulWidget {
  const BotControlPage({super.key});

  @override
  State<BotControlPage> createState() => _BotControlPageState();
}

class _BotControlPageState extends State<BotControlPage> {
  static const _engineBase = 'http://127.0.0.1:8765';

  final _apiKeyCtrl = TextEditingController();
  final _apiSecretCtrl = TextEditingController();
  final _tagCtrl = TextEditingController(text: 'Dorothy');
  final _symbolCtrl = TextEditingController(text: 'XRPUSDT');
  final _loopCtrl = TextEditingController(text: '450');
  final _quoteCtrl = TextEditingController(text: '8');
  final _profitCtrl = TextEditingController(text: '0.05');
  final _dropCtrl = TextEditingController(text: '0.004');
  final _qtyDecCtrl = TextEditingController(text: '8');
  final _priceDecCtrl = TextEditingController(text: '4');

  bool _loading = false;
  String _lastError = '-';
  String _activeCredential = 'none · -';
  String _selectedBotId = '';
  List<Map<String, dynamic>> _hubBots = <Map<String, dynamic>>[];
  final Map<String, String> _hubLogsByBot = <String, String>{};
  final Set<String> _expandedBots = <String>{};
  bool _keysExpanded = false;

  EngineApi get _api => EngineApi(_engineBase);

  @override
  void initState() {
    super.initState();
    _refreshAll();
  }

  @override
  void dispose() {
    _apiKeyCtrl.dispose();
    _apiSecretCtrl.dispose();
    _tagCtrl.dispose();
    _symbolCtrl.dispose();
    _loopCtrl.dispose();
    _quoteCtrl.dispose();
    _profitCtrl.dispose();
    _dropCtrl.dispose();
    _qtyDecCtrl.dispose();
    _priceDecCtrl.dispose();
    super.dispose();
  }

  Future<void> _withBusy(Future<void> Function() fn) async {
    if (_loading) return;
    setState(() => _loading = true);
    try {
      await fn();
      _lastError = '-';
    } catch (e) {
      _lastError = e.toString();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_lastError)),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  String? get _apiKey => _apiKeyCtrl.text.trim().isEmpty ? null : _apiKeyCtrl.text.trim();
  String? get _apiSecret => _apiSecretCtrl.text.trim().isEmpty ? null : _apiSecretCtrl.text.trim();

  Future<void> _reloadData() async {
    final cred = await _api.activeCredential();
    final source = (cred['source'] ?? 'none').toString();
    final last4 = (cred['public_key_last4'] ?? '-').toString();
    final activeId = (cred['active_credential_id'] ?? '-').toString();
    _activeCredential = '$source · $last4 · id:$activeId';
    final hub = await _api.hubBots();
    final botsRaw = (hub['bots'] as List?) ?? const [];
    _hubBots = botsRaw.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    if (_hubBots.isNotEmpty) {
      final hasSelected = _hubBots.any((b) => (b['bot_id'] ?? '').toString() == _selectedBotId);
      if (!hasSelected) {
        _selectedBotId = (_hubBots.first['bot_id'] ?? '').toString();
      }
    } else {
      _selectedBotId = '';
    }
    final selected = _hubBots.where((b) => (b['bot_id'] ?? '').toString() == _selectedBotId).toList();
    final b = selected.isNotEmpty ? selected.first : <String, dynamic>{};

    if (b.isNotEmpty) {
      _tagCtrl.text = (b['tag'] ?? 'Dorothy').toString();
      _symbolCtrl.text = (b['symbol'] ?? 'XRPUSDT').toString();
      _loopCtrl.text = (b['loop_interval_sec'] ?? 450).toString();
      _quoteCtrl.text = (b['quote_order_qty'] ?? '8').toString();
      _profitCtrl.text = (b['profit_factor'] ?? '0.05').toString();
      _dropCtrl.text = (b['margin_drop_factor'] ?? '0.004').toString();
      _qtyDecCtrl.text = (b['qty_decimals'] ?? 8).toString();
      _priceDecCtrl.text = (b['price_decimals'] ?? 4).toString();
    }
    for (final id in _expandedBots) {
      await _refreshHubLogs(id);
    }
  }

  Future<void> _refreshAll() async {
    await _withBusy(_reloadData);
  }

  Future<void> _applySelectedBotConfig() async {
    if (_selectedBotId.isEmpty) return;
    await _withBusy(() async {
      await _api.hubUpdateBot(_selectedBotId, {
        'tag': _tagCtrl.text.trim(),
        'symbol': _symbolCtrl.text.trim(),
        'loop_interval_sec': int.tryParse(_loopCtrl.text.trim()) ?? 450,
        'quote_order_qty': _quoteCtrl.text.trim(),
        'profit_factor': _profitCtrl.text.trim(),
        'margin_drop_factor': _dropCtrl.text.trim(),
        'qty_decimals': int.tryParse(_qtyDecCtrl.text.trim()) ?? 8,
        'price_decimals': int.tryParse(_priceDecCtrl.text.trim()) ?? 4,
      });
      await _reloadData();
    });
  }

  Future<void> _createBot() async {
    await _withBusy(() async {
      final created = await _api.hubCreateBot({
        'tag': _tagCtrl.text.trim().isEmpty ? 'Dorothy' : _tagCtrl.text.trim(),
        'symbol': _symbolCtrl.text.trim(),
        'loop_interval_sec': int.tryParse(_loopCtrl.text.trim()) ?? 450,
        'quote_order_qty': _quoteCtrl.text.trim(),
        'profit_factor': _profitCtrl.text.trim(),
        'margin_drop_factor': _dropCtrl.text.trim(),
        'qty_decimals': int.tryParse(_qtyDecCtrl.text.trim()) ?? 8,
        'price_decimals': int.tryParse(_priceDecCtrl.text.trim()) ?? 4,
      });
      _selectedBotId = (created['bot_id'] ?? '').toString();
      await _reloadData();
    });
  }

  Future<void> _startGateway() async {
    await _withBusy(() async {
      await _api.gatewayStart(apiKey: _apiKey, apiSecret: _apiSecret);
      await _reloadData();
    });
  }

  Future<void> _syncTimestamp() async {
    await _withBusy(() async {
      await _api.syncTimestamp(apiKey: _apiKey, apiSecret: _apiSecret);
      await _reloadData();
    });
  }

  Future<void> _stopGateway() async {
    await _withBusy(() async {
      await _api.gatewayStop();
      await _reloadData();
    });
  }

  Future<void> _startBot() async {
    if (_selectedBotId.isEmpty) return;
    await _withBusy(() async {
      await _api.hubStartBot(
        _selectedBotId,
        apiKey: _apiKey,
        apiSecret: _apiSecret,
      );
      await _reloadData();
    });
  }

  Future<void> _stopBot() async {
    if (_selectedBotId.isEmpty) return;
    await _withBusy(() async {
      await _api.hubStopBot(_selectedBotId);
      await _reloadData();
    });
  }

  Future<void> _runOnce() async {
    if (_selectedBotId.isEmpty) return;
    await _withBusy(() async {
      await _api.hubRunOnce(
        _selectedBotId,
        apiKey: _apiKey,
        apiSecret: _apiSecret,
      );
      await _reloadData();
    });
  }

  Future<void> _deleteBot() async {
    if (_selectedBotId.isEmpty) return;
    await _withBusy(() async {
      await _api.hubDeleteBot(_selectedBotId);
      await _reloadData();
    });
  }

  Future<void> _refreshHubLogs(String botId) async {
    if (botId.isEmpty) {
      return;
    }
    final logs = await _api.hubLogs(botId, limit: 120);
    _hubLogsByBot[botId] = _formatLogs(logs);
  }

  String _formatLogs(Map<String, dynamic> payload) {
    final rows = (payload['logs'] as List?) ?? const [];
    if (rows.isEmpty) return '(sin logs)';
    final out = <String>[];
    for (final row in rows) {
      final m = Map<String, dynamic>.from(row as Map);
      final ts = (m['ts_utc'] ?? '-').toString();
      final level = (m['level'] ?? '-').toString();
      final msg = (m['message'] ?? '').toString();
      final rawPayload = m['payload_json'];
      var payloadText = '';
      if (rawPayload is String && rawPayload.trim().isNotEmpty) {
        try {
          final obj = jsonDecode(rawPayload);
          payloadText = jsonEncode(obj);
        } catch (_) {
          payloadText = rawPayload;
        }
      }
      out.add('$ts [$level] $msg${payloadText.isEmpty ? '' : ' | $payloadText'}');
    }
    return out.join('\n');
  }

  Widget _field(
    TextEditingController controller,
    String label, {
    double width = 120,
    String? tooltip,
  }) {
    return SizedBox(
      width: width,
      child: Tooltip(
        message: tooltip ?? label,
        child: TextField(
          controller: controller,
          decoration: InputDecoration(
            labelText: label,
            isDense: true,
            border: const OutlineInputBorder(),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PecunatorCore · Dorothy Hub'),
        actions: [
          IconButton(
            onPressed: _loading ? null : _syncTimestamp,
            tooltip: 'Sync timestamp',
            icon: const Icon(Icons.schedule, size: 18),
          ),
          IconButton(
            onPressed: _loading ? null : _refreshAll,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (_loading) const LinearProgressIndicator(),
            ExpansionTile(
              initiallyExpanded: _keysExpanded,
              onExpansionChanged: (v) => setState(() => _keysExpanded = v),
              title: Text('General API Keys · active: $_activeCredential'),
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
                  child: Row(
                    children: [
                      _field(
                        _apiKeyCtrl,
                        'API key',
                        width: 360,
                        tooltip: 'Public key de Binance para autenticar peticiones.',
                      ),
                      const SizedBox(width: 8),
                      SizedBox(
                        width: 420,
                        child: Tooltip(
                          message: 'Secret key privada asociada a la API key.',
                          child: TextField(
                            controller: _apiSecretCtrl,
                            obscureText: true,
                            decoration: const InputDecoration(
                              labelText: 'API secret',
                              isDense: true,
                              border: OutlineInputBorder(),
                            ),
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        tooltip: 'Start gateway',
                        onPressed: _loading ? null : _startGateway,
                        icon: const Icon(Icons.cloud_upload),
                      ),
                      IconButton(
                        tooltip: 'Stop gateway',
                        onPressed: _loading ? null : _stopGateway,
                        icon: const Icon(Icons.cloud_off),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      _field(
                        _tagCtrl,
                        'tag',
                        width: 150,
                        tooltip: 'Etiqueta descriptiva de la instancia Dorothy.',
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _symbolCtrl,
                        'symbol',
                        width: 110,
                        tooltip: 'Par spot (ej. XRPUSDT).',
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _loopCtrl,
                        'loop',
                        width: 80,
                        tooltip: 'Segundos entre iteraciones del ciclo Dorothy.',
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _quoteCtrl,
                        'qty',
                        width: 80,
                        tooltip: 'Monto quote por compra market (quoteOrderQty).',
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _profitCtrl,
                        'profit',
                        width: 90,
                        tooltip: 'Factor de beneficio para calcular el SELL LIMIT.',
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _dropCtrl,
                        'drop',
                        width: 90,
                        tooltip: 'Margen de bajada para gatillar compra respecto al ancla SELL.',
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _qtyDecCtrl,
                        'qDec',
                        width: 70,
                        tooltip: 'Decimales para quantity en órdenes.',
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _priceDecCtrl,
                        'pDec',
                        width: 70,
                        tooltip: 'Decimales para price en órdenes LIMIT.',
                      ),
                      const SizedBox(width: 8),
                      IconButton(
                        tooltip: 'Create instance',
                        onPressed: _loading ? null : _createBot,
                        icon: const Icon(Icons.add_circle_outline),
                      ),
                      IconButton(
                        tooltip: 'Apply selected',
                        onPressed: _loading || _selectedBotId.isEmpty ? null : _applySelectedBotConfig,
                        icon: const Icon(Icons.save_outlined),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 6),
            if (_lastError != '-')
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text(_lastError, style: const TextStyle(color: Colors.redAccent, fontSize: 12)),
              ),
            ..._hubBots.map((b) {
              final botId = (b['bot_id'] ?? '').toString();
              final running = b['running'] == true;
              final selected = botId == _selectedBotId;
              final logs = _hubLogsByBot[botId] ?? '(expande para cargar logs)';
              return Card(
                child: ExpansionTile(
                  onExpansionChanged: (expanded) async {
                    if (expanded) {
                      _expandedBots.add(botId);
                      await _refreshHubLogs(botId);
                      if (mounted) setState(() {});
                    } else {
                      _expandedBots.remove(botId);
                    }
                  },
                  title: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: Row(
                      children: [
                        Icon(Icons.circle, size: 11, color: running ? Colors.greenAccent : Colors.redAccent),
                        const SizedBox(width: 6),
                        Text(selected ? '[*]' : '[ ]', style: const TextStyle(fontFamily: 'monospace')),
                        const SizedBox(width: 8),
                        Text((b['tag'] ?? '-').toString()),
                        const SizedBox(width: 12),
                        Text((b['symbol'] ?? '-').toString(), style: const TextStyle(fontFamily: 'monospace')),
                        const SizedBox(width: 12),
                        Text('loop ${(b['loop_interval_sec'] ?? '-')}', style: const TextStyle(fontSize: 12)),
                        const SizedBox(width: 8),
                        Text('qty ${(b['quote_order_qty'] ?? '-')}', style: const TextStyle(fontSize: 12)),
                        const SizedBox(width: 8),
                        Text('p ${(b['profit_factor'] ?? '-')}', style: const TextStyle(fontSize: 12)),
                        const SizedBox(width: 8),
                        Text('d ${(b['margin_drop_factor'] ?? '-')}', style: const TextStyle(fontSize: 12)),
                        const SizedBox(width: 8),
                        Text('qDec ${(b['qty_decimals'] ?? '-')}', style: const TextStyle(fontSize: 12)),
                        const SizedBox(width: 8),
                        Text('pDec ${(b['price_decimals'] ?? '-')}', style: const TextStyle(fontSize: 12)),
                      ],
                    ),
                  ),
                  trailing: Wrap(
                    spacing: 0,
                    children: [
                      IconButton(
                        tooltip: 'Select',
                        onPressed: _loading
                            ? null
                            : () => setState(() {
                                  _selectedBotId = botId;
                                }),
                        icon: const Icon(Icons.my_location, size: 18),
                      ),
                      SizedBox(
                        height: 28,
                        child: TextButton(
                          onPressed: _loading
                              ? null
                              : () async {
                                    _selectedBotId = botId;
                                    await _runOnce();
                                  },
                          child: const Text('RUN'),
                        ),
                      ),
                      IconButton(
                        tooltip: running ? 'Stop' : 'Start',
                        onPressed: _loading
                            ? null
                            : () async {
                                  _selectedBotId = botId;
                                  if (running) {
                                    await _stopBot();
                                  } else {
                                    await _startBot();
                                  }
                                },
                        icon: Icon(running ? Icons.stop : Icons.power_settings_new, size: 18),
                      ),
                      IconButton(
                        tooltip: 'Delete',
                        onPressed: _loading
                            ? null
                            : () async {
                                  _selectedBotId = botId;
                                  await _deleteBot();
                                },
                        icon: const Icon(Icons.delete_outline, size: 18),
                      ),
                    ],
                  ),
                  children: [
                    Container(
                      width: double.infinity,
                      constraints: const BoxConstraints(minHeight: 80, maxHeight: 240),
                      margin: const EdgeInsets.fromLTRB(10, 0, 10, 10),
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        border: Border.all(color: Colors.white24),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: SingleChildScrollView(
                        child: SelectableText(
                          logs,
                          style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
                        ),
                      ),
                    ),
                  ],
                ),
              );
            }),
          ],
        ),
      ),
    );
  }
}
