import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import 'api_client.dart';

String _plainNum(dynamic value, {int maxDecimals = 12}) {
  if (value == null) return '0';
  final raw = value.toString().trim();
  if (raw.isEmpty) return '0';
  final n = num.tryParse(raw);
  if (n == null || n.isNaN || n.isInfinite) return raw;
  if (n == 0) return '0';
  if (n is int) return n.toString();
  var out = n.toStringAsFixed(maxDecimals);
  out = out.replaceFirst(RegExp(r'0+$'), '').replaceFirst(RegExp(r'\.$'), '');
  if (out == '-0') return '0';
  return out;
}

void main() {
  runApp(const PecunatorDesktopApp());
}

class PecunatorDesktopApp extends StatefulWidget {
  const PecunatorDesktopApp({super.key});

  @override
  State<PecunatorDesktopApp> createState() => _PecunatorDesktopAppState();
}

class _PecunatorDesktopAppState extends State<PecunatorDesktopApp> {
  bool _darkMode = true;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Pecunator Desktop',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueGrey),
      ),
      darkTheme: ThemeData.dark(useMaterial3: true),
      themeMode: _darkMode ? ThemeMode.dark : ThemeMode.light,
      home: BotControlPage(
        darkMode: _darkMode,
        onThemeChanged: (v) => setState(() => _darkMode = v),
      ),
    );
  }
}

class BotControlPage extends StatefulWidget {
  const BotControlPage({
    super.key,
    required this.darkMode,
    required this.onThemeChanged,
  });

  final bool darkMode;
  final ValueChanged<bool> onThemeChanged;

  @override
  State<BotControlPage> createState() => _BotControlPageState();
}

class _BotControlPageState extends State<BotControlPage> {
  static const _engineBase = 'http://127.0.0.1:8765';

  final _tagCtrl = TextEditingController(text: 'Dorothy');
  final _symbolCtrl = TextEditingController(text: 'XRPUSDT');
  final _loopCtrl = TextEditingController(text: '450');
  final _quoteCtrl = TextEditingController(text: '8');
  final _profitCtrl = TextEditingController(text: '0.05');
  final _dropCtrl = TextEditingController(text: '0.004');
  final _qtyDecCtrl = TextEditingController(text: '8');
  final _priceDecCtrl = TextEditingController(text: '4');
  final _noteCtrl = TextEditingController();

  bool _loading = false;
  String _lastError = '-';
  bool _gatewayRunning = false;
  bool _gatewayWsConnected = false;
  String? _gatewayLastError;
  int? _apiWeightUsed;
  int _apiWeightLimit = 6000;
  DateTime? _binanceSrvUtc;
  DateTime? _binanceSrvObservedUtc;
  String _activeCredential = 'none · -';
  String _activeCredentialId = '';
  List<Map<String, dynamic>> _hubBots = <Map<String, dynamic>>[];
  List<Map<String, String>> _configHistory = <Map<String, String>>[];
  List<Map<String, dynamic>> _vaultCredentials = <Map<String, dynamic>>[];
  final Map<String, String> _hubLogsByBot = <String, String>{};
  final Map<String, ScrollController> _logScrollByBot =
      <String, ScrollController>{};
  final Set<String> _expandedBots = <String>{};
  final Map<String, Map<String, String>> _draftByBotId =
      <String, Map<String, String>>{};
  final _credLabelCtrl = TextEditingController();
  final _credKeyCtrl = TextEditingController();
  final _credSecretCtrl = TextEditingController();
  Timer? _refreshTimer;
  Timer? _clockTimer;
  String _clockText = '--:--:--';

  EngineApi get _api => EngineApi(_engineBase);

  @override
  void initState() {
    super.initState();
    _tickBinanceClock();
    _refreshAll();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _syncTimestamp();
    });
    _refreshTimer = Timer.periodic(const Duration(seconds: 4), (_) {
      _backgroundRefresh();
    });
    _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) {
        setState(_tickBinanceClock);
      }
    });
  }

  @override
  void dispose() {
    _tagCtrl.dispose();
    _symbolCtrl.dispose();
    _loopCtrl.dispose();
    _quoteCtrl.dispose();
    _profitCtrl.dispose();
    _dropCtrl.dispose();
    _qtyDecCtrl.dispose();
    _priceDecCtrl.dispose();
    _noteCtrl.dispose();
    _credLabelCtrl.dispose();
    _credKeyCtrl.dispose();
    _credSecretCtrl.dispose();
    for (final c in _logScrollByBot.values) {
      c.dispose();
    }
    _refreshTimer?.cancel();
    _clockTimer?.cancel();
    super.dispose();
  }

  String _formatClock(DateTime now) {
    final hh = now.hour.toString().padLeft(2, '0');
    final mm = now.minute.toString().padLeft(2, '0');
    final ss = now.second.toString().padLeft(2, '0');
    return '$hh:$mm:$ss';
  }

  DateTime? _displayBinanceUtcNow() {
    if (_binanceSrvUtc != null && _binanceSrvObservedUtc != null) {
      final elapsed = DateTime.now().toUtc().difference(_binanceSrvObservedUtc!);
      return _binanceSrvUtc!.add(elapsed);
    }
    return null;
  }

  void _tickBinanceClock() {
    final t = _displayBinanceUtcNow();
    _clockText = t != null ? _formatClock(t) : '--:--:--';
  }

  Color _gatewayTrafficColor() {
    if (!_gatewayRunning) {
      return Colors.grey;
    }
    final err = _gatewayLastError;
    if (err != null && err.isNotEmpty) {
      return Colors.redAccent;
    }
    final u = _apiWeightUsed;
    final lim = _apiWeightLimit;
    if (u != null && lim > 0 && u >= (lim * 0.85).round()) {
      return Colors.redAccent;
    }
    if (!_gatewayWsConnected) {
      return Colors.redAccent;
    }
    return Colors.green;
  }

  String _settingTooltip(String field) {
    switch (field) {
      case 'tag':
        return 'Nombre local de la instancia Dorothy.';
      case 'symbol':
        return 'Activo a operar (ej. XRPUSDT). En Dorothy define el mercado objetivo.';
      case 'loop':
        return 'Segundos entre iteraciones del bot (tiempoEntreEjecucion).';
      case 'qty':
        return 'Monto por compra en moneda quote (quoteOrderQtyModulo, comúnmente USDT).';
      case 'profit':
        return 'Factor de beneficio por ciclo. 0.05 equivale a 5% objetivo de ganancia.';
      case 'drop':
        return 'Margen adicional de caída para habilitar compra, evita compras concentradas.';
      case 'qDec':
        return 'Decimales de cantidad para cumplir filtros de lote de Binance.';
      case 'pDec':
        return 'Decimales de precio SELL LIMIT para cumplir PRICE_FILTER.';
      case 'note':
        return 'Nota breve operativa del seteo (máximo 20 caracteres).';
      default:
        return field;
    }
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
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(_lastError)));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _reloadData() async {
    final cred = await _api.activeCredential();
    final creds = await _api.vaultCredentials();
    final rows = (creds['items'] as List?) ?? const [];
    _vaultCredentials = rows
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    final source = (cred['source'] ?? 'none').toString();
    final last4 = (cred['public_key_last4'] ?? '-').toString();
    _activeCredentialId = (cred['active_credential_id'] ?? '').toString();
    final activeLabel = (cred['label'] ?? '').toString().trim();
    final activeName = activeLabel.isNotEmpty
        ? activeLabel
        : (_activeCredentialId.isEmpty ? '-' : _activeCredentialId);
    _activeCredential = '$activeName · $last4 · $source';
    final hub = await _api.hubBots();
    final botsRaw = (hub['bots'] as List?) ?? const [];
    _hubBots = botsRaw.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    _configHistory = _buildConfigHistory(_hubBots);
    final liveIds = _hubBots.map((b) => (b['bot_id'] ?? '').toString()).toSet();
    _expandedBots.removeWhere((id) => !liveIds.contains(id));
    _draftByBotId.removeWhere((id, _) => !liveIds.contains(id));
    _logScrollByBot.removeWhere((id, ctrl) {
      if (!liveIds.contains(id)) {
        ctrl.dispose();
        return true;
      }
      return false;
    });
    for (final id in _expandedBots) {
      await _refreshHubLogs(id);
    }
    try {
      final snap = await _api.gatewaySnapshot();
      _gatewayRunning = snap['gateway_running'] == true;
      _gatewayWsConnected = snap['ws_connected'] == true;
      final le = snap['last_error'];
      if (le == null || le.toString().trim().isEmpty) {
        _gatewayLastError = null;
      } else {
        _gatewayLastError = le.toString();
      }
      final uw = snap['used_weight_1m'];
      if (uw is int) {
        _apiWeightUsed = uw;
      } else if (uw is num) {
        _apiWeightUsed = uw.toInt();
      } else {
        _apiWeightUsed = int.tryParse('$uw');
      }
      final wl = snap['weight_limit_1m'];
      if (wl is int) {
        _apiWeightLimit = wl;
      } else if (wl is num) {
        _apiWeightLimit = wl.toInt();
      } else {
        _apiWeightLimit = int.tryParse('$wl') ?? 6000;
      }
    } catch (_) {
      _gatewayRunning = false;
      _gatewayWsConnected = false;
      _gatewayLastError = null;
      _apiWeightUsed = null;
    }
  }

  Future<void> _refreshAll() async {
    await _withBusy(_reloadData);
  }

  Future<void> _backgroundRefresh() async {
    if (!mounted || _loading) return;
    try {
      await _reloadData();
      if (mounted) setState(() {});
    } catch (_) {
      // Silent background refresh; explicit actions still surface errors.
    }
  }

  Future<void> _saveBotConfig(String botId) async {
    final draft = _draftByBotId[botId];
    if (draft == null) return;
    final wasRunning = _hubBots.any(
      (b) => (b['bot_id'] ?? '').toString() == botId && b['running'] == true,
    );
    await _withBusy(() async {
      await _api.hubUpdateBot(botId, {
        'tag': (draft['tag'] ?? 'Dorothy').trim(),
        'symbol': (draft['symbol'] ?? 'XRPUSDT').trim(),
        'loop_interval_sec':
            int.tryParse((draft['loop'] ?? '450').trim()) ?? 450,
        'quote_order_qty': (draft['qty'] ?? '8').trim(),
        'profit_factor': (draft['profit'] ?? '0.05').trim(),
        'margin_drop_factor': (draft['drop'] ?? '0.004').trim(),
        'qty_decimals': int.tryParse((draft['qDec'] ?? '8').trim()) ?? 8,
        'price_decimals': int.tryParse((draft['pDec'] ?? '4').trim()) ?? 4,
        'note': (draft['note'] ?? '').trim(),
        'simulated': (draft['simulated'] ?? 'true') == 'true',
        'trading_enabled': (draft['trading_enabled'] ?? 'false') == 'true',
      });
      if (wasRunning) {
        await _api.hubStopBot(botId);
        await _api.hubStartBot(botId);
      }
      await _reloadData();
    });
  }

  Future<void> _createBot() async {
    await _withBusy(() async {
      await _api.hubCreateBot({
        'tag': _tagCtrl.text.trim().isEmpty ? 'Dorothy' : _tagCtrl.text.trim(),
        'symbol': _symbolCtrl.text.trim(),
        'loop_interval_sec': int.tryParse(_loopCtrl.text.trim()) ?? 450,
        'quote_order_qty': _quoteCtrl.text.trim(),
        'profit_factor': _profitCtrl.text.trim(),
        'margin_drop_factor': _dropCtrl.text.trim(),
        'qty_decimals': int.tryParse(_qtyDecCtrl.text.trim()) ?? 8,
        'price_decimals': int.tryParse(_priceDecCtrl.text.trim()) ?? 4,
        'note': _noteCtrl.text.trim(),
        'simulated': true,
        'trading_enabled': false,
      });
      await _reloadData();
    });
  }

  Future<void> _startGateway() async {
    await _withBusy(() async {
      await _api.gatewayStart();
      await _reloadData();
    });
  }

  Future<void> _syncTimestamp() async {
    await _withBusy(() async {
      final r = await _api.syncTimestamp();
      final ms = r['server_time_ms'];
      if (ms is num) {
        _binanceSrvUtc = DateTime.fromMillisecondsSinceEpoch(
          ms.toInt(),
          isUtc: true,
        );
        _binanceSrvObservedUtc = DateTime.now().toUtc();
        _tickBinanceClock();
      }
      await _reloadData();
    });
  }

  Future<void> _stopGateway() async {
    await _withBusy(() async {
      await _api.gatewayStop();
      await _reloadData();
    });
  }

  Future<void> _toggleBotLoop(String botId, bool running) async {
    await _withBusy(() async {
      if (running) {
        await _api.hubStopBot(botId);
      } else {
        await _api.hubStartBot(botId);
      }
      await _reloadData();
    });
  }

  Future<void> _deleteBot(String botId) async {
    await _withBusy(() async {
      await _api.hubDeleteBot(botId);
      await _reloadData();
    });
  }

  Future<void> _deleteCredential(String credentialId) async {
    await _withBusy(() async {
      await _api.deleteVaultCredential(credentialId);
      await _reloadData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Credencial eliminada')),
        );
      }
    });
  }

  Future<void> _confirmDeleteCredential(String credentialId) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirmar eliminación'),
        content: Text('Eliminar credencial $credentialId del vault local.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );
    if (ok == true) {
      await _deleteCredential(credentialId);
    }
  }

  Future<void> _addCredential() async {
    final apiKey = _credKeyCtrl.text.trim();
    final apiSecret = _credSecretCtrl.text.trim();
    final label = _credLabelCtrl.text.trim();
    if (apiKey.isEmpty || apiSecret.isEmpty) {
      setState(() => _lastError = 'API key y secret son requeridos');
      return;
    }
    if (apiKey.length < 8 || apiSecret.length < 8) {
      setState(() => _lastError = 'API key y secret deben tener al menos 8 caracteres');
      return;
    }
    if (label.length > 80) {
      setState(() => _lastError = 'Nombre local máximo 80 caracteres');
      return;
    }
    await _withBusy(() async {
      final created = await _api.addVaultCredential(
        apiKey: apiKey,
        apiSecret: apiSecret,
        label: label,
      );
      final newId = (created['id'] ?? '').toString();
      if (newId.isNotEmpty) {
        await _api.activateVaultCredential(newId);
      }
      _credKeyCtrl.clear();
      _credSecretCtrl.clear();
      _credLabelCtrl.clear();
      await _reloadData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Credencial guardada y activada')),
        );
      }
    });
  }

  Future<void> _refreshHubLogs(String botId) async {
    if (botId.isEmpty) {
      return;
    }
    final logs = await _api.hubLogs(botId, limit: 120);
    _hubLogsByBot[botId] = _formatLogs(logs);
    if (_expandedBots.contains(botId)) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final c = _logScrollByBot[botId];
        if (c != null && c.hasClients) {
          c.jumpTo(c.position.maxScrollExtent);
        }
      });
    }
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
      final payloadText = _formatLogPayload(m['payload']);
      out.add(
        '$ts [$level] $msg${payloadText.isEmpty ? '' : ' | $payloadText'}',
      );
    }
    return out.join('\n');
  }

  String _formatLogPayload(dynamic payload) {
    if (payload == null) return '';
    if (payload is String) return payload;
    if (payload is! Map) return payload.toString();

    final p = Map<String, dynamic>.from(payload);
    final response = p['response'];
    if (response != null) {
      return jsonEncode(response);
    }
    final reportRaw = p['last_report'];
    if (reportRaw is Map) {
      final rep = Map<String, dynamic>.from(reportRaw);
      if (!rep.containsKey('decision')) {
        return '';
      }
      final decision = (rep['decision'] ?? '-').toString();
      final execution = (rep['execution'] ?? '-').toString();
      final symbol = (rep['symbol'] ?? p['symbol'] ?? '-').toString();
      final market = (rep['market_price'] ?? '-').toString();
      final plannedBuy = (rep['planned_buy_price'] ?? '-').toString();
      final plannedSell = (rep['planned_sell_price'] ?? '-').toString();
      return 'decision=$decision execution=$execution symbol=$symbol market=$market buy=$plannedBuy sell=$plannedSell';
    }

    final report = p['report'];
    if (report is Map<String, dynamic>) {
      return jsonEncode(report);
    }

    final decision = p['decision'];
    if (decision != null) {
      return 'decision=${decision.toString()}';
    }
    return jsonEncode(p);
  }

  List<Map<String, String>> _buildConfigHistory(
    List<Map<String, dynamic>> bots,
  ) {
    final seen = <String>{};
    final out = <Map<String, String>>[];
    for (final b in bots) {
      final row = <String, String>{
        'tag': (b['tag'] ?? 'Dorothy').toString(),
        'symbol': (b['symbol'] ?? 'XRPUSDT').toString(),
        'loop': (b['loop_interval_sec'] ?? 450).toString(),
        'qty': (b['quote_order_qty'] ?? '8').toString(),
        'profit': (b['profit_factor'] ?? '0.05').toString(),
        'drop': (b['margin_drop_factor'] ?? '0.004').toString(),
        'qDec': (b['qty_decimals'] ?? 8).toString(),
        'pDec': (b['price_decimals'] ?? 4).toString(),
        'note': (b['note'] ?? '').toString(),
      };
      final key = row.values.join('|');
      if (!seen.contains(key)) {
        seen.add(key);
        out.add(row);
      }
    }
    return out;
  }

  void _applyHistory(Map<String, String> h) {
    _tagCtrl.text = h['tag'] ?? 'Dorothy';
    _symbolCtrl.text = h['symbol'] ?? 'XRPUSDT';
    _loopCtrl.text = h['loop'] ?? '450';
    _quoteCtrl.text = h['qty'] ?? '8';
    _profitCtrl.text = h['profit'] ?? '0.05';
    _dropCtrl.text = h['drop'] ?? '0.004';
    _qtyDecCtrl.text = h['qDec'] ?? '8';
    _priceDecCtrl.text = h['pDec'] ?? '4';
    _noteCtrl.text = h['note'] ?? '';
    setState(() {});
  }

  Future<bool?> _confirmLiveTradingDialog() async {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirmar modo LIVE'),
        content: const Text(
          'Vas a desactivar el modo simulado. Dorothy podrá enviar órdenes '
          'reales a Binance con las API keys activas. Las pérdidas son posibles. '
          '¿Continuar?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Sí, modo LIVE'),
          ),
        ],
      ),
    );
  }

  Future<void> _patchBotLiveSim(
    String botId, {
    required bool simulated,
    required bool tradingEnabled,
  }) async {
    await _withBusy(() async {
      await _api.hubUpdateBot(botId, {
        'simulated': simulated,
        'trading_enabled': tradingEnabled,
      });
      await _reloadData();
    });
  }

  Future<void> _openRestUsageDialog() async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => _RestWeightMonitorDialog(api: _api),
    );
  }

  Future<void> _confirmDeleteBot(String botId) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirmar eliminación'),
        content: Text(
          'Eliminar la instancia $botId y conservar solo su historial SQLite.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );
    if (ok == true) {
      await _deleteBot(botId);
    }
  }

  Future<void> _openCredentialManager() async {
    await _refreshAll();
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setModal) {
            return AlertDialog(
              title: Text('API activa: $_activeCredential'),
              content: SizedBox(
                width: 860,
                child: SingleChildScrollView(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Guarda tus credenciales Binance en el cofre local cifrado. '
                        'No necesitas contraseña maestra; solo API key + API secret.',
                        style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: 10),
                      if (_vaultCredentials.isEmpty)
                        const Padding(
                          padding: EdgeInsets.only(bottom: 8),
                          child: Text(
                            'No hay claves registradas. Agrega una nueva.',
                          ),
                        ),
                      ..._vaultCredentials.map((row) {
                        final id = (row['id'] ?? '').toString();
                        final short = (row['public_key_short'] ?? '-')
                            .toString();
                        final isActive = id == _activeCredentialId;
                        final label = (row['label'] ?? '').toString().trim();
                        final display = label.isNotEmpty ? label : id;
                        return Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: Row(
                              children: [
                                SizedBox(width: 210, child: Text(display)),
                                const SizedBox(width: 6),
                                SizedBox(
                                  width: 230,
                                  child: SelectableText(short),
                                ),
                                const SizedBox(width: 6),
                                Text(
                                  isActive ? 'ACTIVA' : '',
                                  style: TextStyle(
                                    color: isActive
                                        ? Colors.greenAccent
                                        : Theme.of(context).hintColor,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                                const SizedBox(width: 4),
                                if (!isActive)
                                  TextButton(
                                    onPressed: _loading
                                        ? null
                                        : () async {
                                            await _withBusy(() async {
                                              await _api.activateVaultCredential(id);
                                              await _reloadData();
                                            });
                                            if (mounted) {
                                              ScaffoldMessenger.of(context).showSnackBar(
                                                const SnackBar(
                                                  content: Text('Credencial activada'),
                                                ),
                                              );
                                            }
                                            setModal(() {});
                                          },
                                    child: const Text('Activar'),
                                  ),
                                IconButton(
                                  tooltip: 'Borrar',
                                  onPressed: _loading
                                      ? null
                                      : () async {
                                          await _confirmDeleteCredential(id);
                                          setModal(() {});
                                        },
                                  icon: const Icon(
                                    Icons.delete_outline,
                                    size: 18,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        );
                      }),
                      const Divider(height: 16),
                      SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            _field(_credLabelCtrl, 'Nombre local', width: 140),
                            const SizedBox(width: 6),
                            _field(_credKeyCtrl, 'API key', width: 230),
                            const SizedBox(width: 6),
                            SizedBox(
                              width: 230,
                              child: TextField(
                                controller: _credSecretCtrl,
                                obscureText: true,
                                textInputAction: TextInputAction.done,
                                onSubmitted: (_) async {
                                  if (_loading) return;
                                  await _addCredential();
                                  setModal(() {});
                                },
                                decoration: const InputDecoration(
                                  labelText: 'API secret',
                                  isDense: true,
                                  border: OutlineInputBorder(),
                                ),
                              ),
                            ),
                            const SizedBox(width: 6),
                            FilledButton.icon(
                              onPressed: _loading
                                  ? null
                                  : () async {
                                      await _addCredential();
                                      setModal(() {});
                                    },
                              icon: const Icon(Icons.save_outlined, size: 18),
                              label: const Text('Guardar'),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Cerrar'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _openSqliteInfo() async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Registro SQLite'),
        content: SizedBox(
          width: 620,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SelectableText('runtime/data/dorothy_hub.sqlite'),
              const SizedBox(height: 8),
              const Text(
                'Cada instancia se identifica por su bot_id y guarda historial crudo completo.',
              ),
              const SizedBox(height: 10),
              ..._hubBots.map((b) {
                final botId = (b['bot_id'] ?? '').toString();
                return Padding(
                  padding: const EdgeInsets.only(bottom: 6),
                  child: Row(
                    children: [
                      Expanded(child: SelectableText('bot_id=$botId')),
                      TextButton(
                        onPressed: () => _openSqliteRecordsList(botId),
                        child: const Text('Consultar'),
                      ),
                    ],
                  ),
                );
              }),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cerrar'),
          ),
        ],
      ),
    );
  }

  Future<void> _openSqliteRecordsList(String botId) async {
    final rows = await _api.hubLogs(botId, limit: 300);
    final logs = (rows['logs'] as List?) ?? const [];
    if (!mounted) return;
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Registros SQLite · $botId'),
        content: SizedBox(
          width: 760,
          height: 460,
          child: logs.isEmpty
              ? const Text('Sin registros')
              : ListView.separated(
                  itemCount: logs.length,
                  separatorBuilder: (_, separatorIndex) =>
                      const Divider(height: 8),
                  itemBuilder: (ctx, i) {
                    final row = Map<String, dynamic>.from(logs[i] as Map);
                    final ts = (row['ts_utc'] ?? '-').toString();
                    final level = (row['level'] ?? '-').toString();
                    final msg = (row['message'] ?? '').toString();
                    return Row(
                      children: [
                        Expanded(child: Text('$ts [$level] $msg')),
                        TextButton(
                          onPressed: () => _openSqliteRecordDetail(botId, row),
                          child: const Text('Detalle'),
                        ),
                      ],
                    );
                  },
                ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cerrar'),
          ),
        ],
      ),
    );
  }

  Future<void> _openSqliteRecordDetail(
    String botId,
    Map<String, dynamic> row,
  ) async {
    if (!mounted) return;
    final pretty = const JsonEncoder.withIndent('  ').convert(row);
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Detalle registro · $botId'),
        content: SizedBox(
          width: 760,
          height: 520,
          child: SingleChildScrollView(
            child: SelectableText(
              pretty,
              style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cerrar'),
          ),
        ],
      ),
    );
  }

  String _cycleCountdown(Map<String, dynamic> bot) {
    final running = bot['running'] == true;
    if (!running) return 'detenida';
    final loop = int.tryParse((bot['loop_interval_sec'] ?? 0).toString()) ?? 0;
    if (loop <= 0) return '--';
    final rawTs = (bot['last_cycle_ts'] ?? '').toString();
    final last = DateTime.tryParse(rawTs);
    if (last == null) return '${loop}s';
    final now = DateTime.now().toUtc();
    final target = last.add(Duration(seconds: loop));
    final sec = target.difference(now).inSeconds;
    final remain = sec < 0 ? 0 : sec;
    final mm = (remain ~/ 60).toString().padLeft(2, '0');
    final ss = (remain % 60).toString().padLeft(2, '0');
    return '$mm:$ss';
  }

  Future<void> _openConfigHistoryDialog() async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Seteos usados anteriormente'),
        content: SizedBox(
          width: 520,
          child: _configHistory.isEmpty
              ? const Text('Sin historial aún.')
              : ListView.separated(
                  shrinkWrap: true,
                  itemCount: _configHistory.length,
                  separatorBuilder: (_, separatorIndex) =>
                      const Divider(height: 10),
                  itemBuilder: (ctx, i) {
                    final h = _configHistory[i];
                    final note = (h['note'] ?? '').trim();
                    return Row(
                      children: [
                        Expanded(
                          child: Text(
                            '${h['symbol']} · loop ${h['loop']} · qty ${h['qty']}'
                            '${note.isEmpty ? '' : ' · note $note'}',
                          ),
                        ),
                        TextButton(
                          onPressed: () {
                            _applyHistory(h);
                            Navigator.pop(ctx);
                          },
                          child: const Text('Usar'),
                        ),
                      ],
                    );
                  },
                ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cerrar'),
          ),
        ],
      ),
    );
  }

  Future<void> _openDorothyGuide() async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Instructivo Dorothy7.0'),
        content: SizedBox(
          width: 860,
          child: SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: const [
                ExpansionTile(
                  title: Text('1) Lógica base del ciclo'),
                  children: [
                    Padding(
                      padding: EdgeInsets.fromLTRB(12, 0, 12, 10),
                      child: Text(
                        'Cada ciclo consulta open orders y ticker del símbolo. '
                        'Si existe una SELL LIMIT ancla, calcula umbral de entrada: '
                        'anchor * (1 - (profit + drop)). Si no existe ancla, habilita compra.',
                      ),
                    ),
                  ],
                ),
                ExpansionTile(
                  title: Text('2) Seteo clave (preset B)'),
                  children: [
                    Padding(
                      padding: EdgeInsets.fromLTRB(12, 0, 12, 10),
                      child: Text(
                        'Preset por defecto: XRPUSDT, loop 450s, qty 8 quote, profit 0.05, drop 0.004. '
                        'qDec/pDec controlan redondeo para respetar filtros del símbolo.',
                      ),
                    ),
                  ],
                ),
                ExpansionTile(
                  title: Text('3) Operación desde el dashboard'),
                  children: [
                    Padding(
                      padding: EdgeInsets.fromLTRB(12, 0, 12, 10),
                      child: Text(
                        'La instancia corre en ciclo perpetuo con botón ACTIVO/INACTIVO. '
                        'Si editas parámetros usa Guardar seteo para aplicarlos, y si estaba ACTIVO '
                        'se reinicia automáticamente para tomar el nuevo seteo al instante.',
                      ),
                    ),
                  ],
                ),
                ExpansionTile(
                  title: Text('4) Qué mirar en operación'),
                  children: [
                    Padding(
                      padding: EdgeInsets.fromLTRB(12, 0, 12, 10),
                      child: Text(
                        'Revisa: precio de mercado vs umbral, órdenes SELL LIMIT ancla, '
                        'quote disponible para compra, base del símbolo para ventas, '
                        'y errores de filtros (PRICE_FILTER / NOTIONAL).',
                      ),
                    ),
                  ],
                ),
                ExpansionTile(
                  title: Text('5) Riesgos y buenas prácticas'),
                  children: [
                    Padding(
                      padding: EdgeInsets.fromLTRB(12, 0, 12, 10),
                      child: Text(
                        'Validar decimales del símbolo, notional mínimo y saldo suficiente antes de correr. '
                        'Mantener sync de timestamp y monitorear logs crudos de Binance por instancia.',
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cerrar'),
          ),
        ],
      ),
    );
  }

  Future<void> _openSpotAccountPage() async {
    final symbols = _hubBots
        .map((b) => (b['symbol'] ?? '').toString())
        .where((s) => s.isNotEmpty)
        .toList();
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) =>
            SpotAccountPage(engineBase: _engineBase, activeSymbols: symbols),
      ),
    );
  }

  Map<String, String> _draftFor(Map<String, dynamic> bot) {
    final botId = (bot['bot_id'] ?? '').toString();
    final d = _draftByBotId.putIfAbsent(botId, () {
      return <String, String>{
        'tag': (bot['tag'] ?? 'Dorothy').toString(),
        'symbol': (bot['symbol'] ?? 'XRPUSDT').toString(),
        'loop': (bot['loop_interval_sec'] ?? 450).toString(),
        'qty': (bot['quote_order_qty'] ?? '8').toString(),
        'profit': (bot['profit_factor'] ?? '0.05').toString(),
        'drop': (bot['margin_drop_factor'] ?? '0.004').toString(),
        'qDec': (bot['qty_decimals'] ?? 8).toString(),
        'pDec': (bot['price_decimals'] ?? 4).toString(),
        'note': (bot['note'] ?? '').toString(),
        'simulated': 'true',
        'trading_enabled': 'false',
      };
    });
    d['simulated'] = ((bot['simulated'] ?? true) == true).toString();
    d['trading_enabled'] =
        ((bot['trading_enabled'] ?? false) == true).toString();
    return d;
  }

  Widget _draftField(
    String botId,
    Map<String, String> draft,
    String field, {
    required String label,
    required double width,
    String? tooltip,
  }) {
    final value = draft[field] ?? '';
    return SizedBox(
      width: width,
      child: Tooltip(
        message: tooltip ?? label,
        child: TextFormField(
          key: ValueKey('$botId-$field-$value'),
          initialValue: value,
          onChanged: (v) => draft[field] = v,
          decoration: InputDecoration(
            labelText: label,
            isDense: true,
            border: const OutlineInputBorder(),
          ),
        ),
      ),
    );
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
            onPressed: _loading ? null : _openDorothyGuide,
            tooltip: 'Instructivo Dorothy7.0',
            icon: const Icon(Icons.menu_book, size: 18),
          ),
          IconButton(
            onPressed: _loading ? null : _openSpotAccountPage,
            tooltip: 'Resumen cuenta Spot',
            icon: const Icon(Icons.account_balance_wallet_outlined, size: 18),
          ),
          IconButton(
            onPressed: _loading ? null : _openCredentialManager,
            tooltip: 'Gestionar API keys',
            icon: const Icon(Icons.key, size: 18),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Center(
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.cloud, size: 16, color: _gatewayTrafficColor()),
                  const SizedBox(width: 4),
                  Text(
                    'GW ${_gatewayRunning ? "ON" : "OFF"}'
                    '${_gatewayWsConnected ? " · WS" : ""}',
                    style: TextStyle(
                      fontSize: 11,
                      fontFamily: 'monospace',
                      color: _gatewayTrafficColor(),
                    ),
                  ),
                ],
              ),
            ),
          ),
          IconButton(
            onPressed: _loading ? null : _startGateway,
            tooltip: 'Iniciar gateway Binance',
            icon: Icon(
              Icons.cloud_upload_outlined,
              size: 18,
              color: _gatewayRunning ? _gatewayTrafficColor() : Colors.grey,
            ),
          ),
          IconButton(
            onPressed: _loading ? null : _stopGateway,
            tooltip: 'Detener gateway',
            icon: Icon(
              Icons.cloud_off_outlined,
              size: 18,
              color: _gatewayRunning ? _gatewayTrafficColor() : Colors.grey,
            ),
          ),
          IconButton(
            onPressed: _loading ? null : _openRestUsageDialog,
            tooltip:
                'Historial local de peso REST (evitar 429/418). Misma IP para todas las instancias.',
            icon: const Icon(Icons.analytics_outlined, size: 18),
          ),
          IconButton(
            onPressed: _loading ? null : _openSqliteInfo,
            tooltip: 'Acceso a registro SQLite',
            icon: const Icon(Icons.storage, size: 18),
          ),
          IconButton(
            onPressed: () => widget.onThemeChanged(!widget.darkMode),
            tooltip: widget.darkMode ? 'Modo día' : 'Modo noche',
            icon: Icon(
              widget.darkMode ? Icons.light_mode : Icons.dark_mode,
              size: 18,
            ),
          ),
          Tooltip(
            message:
                'Hora del servidor Binance en UTC (GET /api/v3/time a través del motor). '
                'No es la hora de tu PC. Pulsa el icono de reloj para sincronizar de nuevo.',
            child: Padding(
              padding: const EdgeInsets.only(right: 4),
              child: Center(
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.public,
                      size: 15,
                      color: Theme.of(context).colorScheme.primary,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      _clockText,
                      style: const TextStyle(
                        fontSize: 12,
                        fontFamily: 'monospace',
                      ),
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'UTC',
                      style: TextStyle(
                        fontSize: 10,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
          IconButton(
            onPressed: _loading ? null : _syncTimestamp,
            tooltip: 'Sincronizar reloj con servidor Binance',
            icon: const Icon(Icons.schedule, size: 18),
          ),
          IconButton(
            onPressed: _loading ? null : _refreshAll,
            tooltip: 'Refrescar estado, instancias y logs',
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
            if (_gatewayRunning &&
                _apiWeightUsed != null &&
                _apiWeightLimit > 0)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Tooltip(
                  message:
                      'Misma métrica que exampleJV/monitorPesos (X-MBX-USED-WEIGHT-1M). '
                      'Límite de referencia: variable PECUNATOR_API_WEIGHT_LIMIT_1M en el motor.',
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Peso REST (1m): $_apiWeightUsed / $_apiWeightLimit',
                        style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(height: 4),
                      ClipRRect(
                        borderRadius: BorderRadius.circular(4),
                        child: LinearProgressIndicator(
                          minHeight: 6,
                          value: (_apiWeightUsed!.clamp(0, _apiWeightLimit)) /
                              _apiWeightLimit,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            Text(
              'API activa: $_activeCredential',
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            if (_lastError != '-')
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text(
                  _lastError,
                  style: const TextStyle(color: Colors.redAccent, fontSize: 12),
                ),
              ),
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
                        tooltip: _settingTooltip('tag'),
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _symbolCtrl,
                        'symbol',
                        width: 110,
                        tooltip: _settingTooltip('symbol'),
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _loopCtrl,
                        'loop',
                        width: 80,
                        tooltip: _settingTooltip('loop'),
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _quoteCtrl,
                        'qty',
                        width: 80,
                        tooltip: _settingTooltip('qty'),
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _profitCtrl,
                        'profit',
                        width: 90,
                        tooltip: _settingTooltip('profit'),
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _dropCtrl,
                        'drop',
                        width: 90,
                        tooltip: _settingTooltip('drop'),
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _qtyDecCtrl,
                        'qDec',
                        width: 70,
                        tooltip: _settingTooltip('qDec'),
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _priceDecCtrl,
                        'pDec',
                        width: 70,
                        tooltip: _settingTooltip('pDec'),
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _noteCtrl,
                        'note',
                        width: 110,
                        tooltip: _settingTooltip('note'),
                      ),
                      const SizedBox(width: 10),
                      IconButton(
                        tooltip: 'Seteos usados anteriormente',
                        onPressed: _loading ? null : _openConfigHistoryDialog,
                        icon: const Icon(Icons.history, size: 18),
                      ),
                      const SizedBox(width: 6),
                      Tooltip(
                        message: 'Crear instancia con este seteo',
                        child: FilledButton.icon(
                          onPressed: _loading ? null : _createBot,
                          icon: const Icon(Icons.add_circle_outline, size: 16),
                          label: const Text('Create New Instance'),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 6),
            if (_hubBots.isEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(14),
                  child: Text(
                    'Sin instancias Dorothy. Crea la primera instancia en la fila superior.',
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                  ),
                ),
              ),
            ..._hubBots.map((b) {
              final botId = (b['bot_id'] ?? '').toString();
              final running = b['running'] == true;
              final draft = _draftFor(b);
              final logController = _logScrollByBot.putIfAbsent(
                botId,
                () => ScrollController(),
              );
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
                        Icon(
                          Icons.circle,
                          size: 11,
                          color: running
                              ? Colors.greenAccent
                              : Colors.redAccent,
                        ),
                        const SizedBox(width: 6),
                        Text((b['tag'] ?? '-').toString()),
                        const SizedBox(width: 12),
                        Text(
                          (b['symbol'] ?? '-').toString(),
                          style: const TextStyle(fontFamily: 'monospace'),
                        ),
                        const SizedBox(width: 10),
                        Text(
                          'id $botId',
                          style: const TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 11,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Text(
                          'loop ${(b['loop_interval_sec'] ?? '-')}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'qty ${_plainNum(b['quote_order_qty'])}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'p ${_plainNum(b['profit_factor'])}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'd ${_plainNum(b['margin_drop_factor'])}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'qDec ${(b['qty_decimals'] ?? '-')}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'pDec ${(b['price_decimals'] ?? '-')}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'note ${(b['note'] ?? '-')}',
                          style: const TextStyle(fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                  trailing: Wrap(
                    spacing: 0,
                    children: [
                      SizedBox(
                        height: 30,
                        child: Tooltip(
                          message:
                              'Activar o detener ciclo perpetuo de la instancia',
                          child: TextButton(
                            style: TextButton.styleFrom(
                              foregroundColor: running
                                  ? Colors.greenAccent
                                  : Colors.orangeAccent,
                            ),
                            onPressed: _loading
                                ? null
                                : () async {
                                    await _toggleBotLoop(botId, running);
                                  },
                            child: Text(running ? 'ACTIVO' : 'INACTIVO'),
                          ),
                        ),
                      ),
                      IconButton(
                        tooltip: 'Eliminar',
                        onPressed: _loading
                            ? null
                            : () async {
                                await _confirmDeleteBot(botId);
                              },
                        icon: const Icon(Icons.delete_outline, size: 18),
                      ),
                    ],
                  ),
                  children: [
                    Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      child: SwitchListTile(
                        contentPadding: EdgeInsets.zero,
                        title: const Text('Modo simulado'),
                        subtitle: Text(
                          ((b['simulated'] ?? true) == true)
                              ? 'Sin órdenes reales en Binance (recomendado para pruebas).'
                              : (((b['trading_enabled'] ?? false) == true)
                                  ? 'LIVE: Dorothy puede colocar órdenes reales.'
                                  : 'Configuración incompleta: LIVE requiere confirmación.'),
                          style: const TextStyle(fontSize: 12),
                        ),
                        value: (b['simulated'] ?? true) == true,
                        onChanged: _loading
                            ? null
                            : (wantSim) async {
                                if (wantSim) {
                                  await _patchBotLiveSim(
                                    botId,
                                    simulated: true,
                                    tradingEnabled: false,
                                  );
                                } else {
                                  final ok = await _confirmLiveTradingDialog();
                                  if (ok == true && mounted) {
                                    await _patchBotLiveSim(
                                      botId,
                                      simulated: false,
                                      tradingEnabled: true,
                                    );
                                  }
                                }
                              },
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(10, 0, 10, 8),
                      child: SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            _draftField(
                              botId,
                              draft,
                              'tag',
                              label: 'tag',
                              width: 140,
                              tooltip: _settingTooltip('tag'),
                            ),
                            const SizedBox(width: 6),
                            _draftField(
                              botId,
                              draft,
                              'symbol',
                              label: 'symbol',
                              width: 100,
                              tooltip: _settingTooltip('symbol'),
                            ),
                            const SizedBox(width: 6),
                            _draftField(
                              botId,
                              draft,
                              'loop',
                              label: 'loop',
                              width: 75,
                              tooltip: _settingTooltip('loop'),
                            ),
                            const SizedBox(width: 6),
                            _draftField(
                              botId,
                              draft,
                              'qty',
                              label: 'qty',
                              width: 75,
                              tooltip: _settingTooltip('qty'),
                            ),
                            const SizedBox(width: 6),
                            _draftField(
                              botId,
                              draft,
                              'profit',
                              label: 'profit',
                              width: 85,
                              tooltip: _settingTooltip('profit'),
                            ),
                            const SizedBox(width: 6),
                            _draftField(
                              botId,
                              draft,
                              'drop',
                              label: 'drop',
                              width: 85,
                              tooltip: _settingTooltip('drop'),
                            ),
                            const SizedBox(width: 6),
                            _draftField(
                              botId,
                              draft,
                              'qDec',
                              label: 'qDec',
                              width: 70,
                              tooltip: _settingTooltip('qDec'),
                            ),
                            const SizedBox(width: 6),
                            _draftField(
                              botId,
                              draft,
                              'pDec',
                              label: 'pDec',
                              width: 70,
                              tooltip: _settingTooltip('pDec'),
                            ),
                            const SizedBox(width: 6),
                            _draftField(
                              botId,
                              draft,
                              'note',
                              label: 'note',
                              width: 110,
                              tooltip: _settingTooltip('note'),
                            ),
                            const SizedBox(width: 8),
                            Tooltip(
                              message:
                                  'Guardar y aplicar seteo ahora (reinicia si estaba activo)',
                              child: FilledButton.tonalIcon(
                                onPressed: _loading
                                    ? null
                                    : () => _saveBotConfig(botId),
                                icon: const Icon(Icons.save, size: 16),
                                label: const Text('Guardar y aplicar'),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(10, 0, 10, 6),
                      child: Row(
                        children: [
                          Text(
                            'Reinicio ciclo en: ${_cycleCountdown(b)}',
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 12,
                            ),
                          ),
                          const Spacer(),
                          TextButton(
                            onPressed: _loading
                                ? null
                                : () => _openSqliteRecordsList(botId),
                            child: const Text('Ver registros DB'),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      width: double.infinity,
                      constraints: const BoxConstraints(
                        minHeight: 80,
                        maxHeight: 240,
                      ),
                      margin: const EdgeInsets.fromLTRB(10, 0, 10, 10),
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        border: Border.all(
                          color: Theme.of(context).dividerColor,
                        ),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: SingleChildScrollView(
                        controller: logController,
                        child: SelectableText(
                          logs,
                          style: const TextStyle(
                            fontFamily: 'monospace',
                            fontSize: 12,
                          ),
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

class _RestWeightMonitorDialog extends StatefulWidget {
  const _RestWeightMonitorDialog({required this.api});

  final EngineApi api;

  @override
  State<_RestWeightMonitorDialog> createState() => _RestWeightMonitorDialogState();
}

class _RestWeightMonitorDialogState extends State<_RestWeightMonitorDialog> {
  bool _loading = true;
  String _error = '';
  List<Map<String, dynamic>> _rows = <Map<String, dynamic>>[];
  int? _liveUsed;
  int _liveLimit = 6000;
  bool _gatewayRunning = false;
  double _animFrom = 0;
  double _animTo = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 2), (_) {
      _refresh(silent: true);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  double _pct(int? used, int limit) {
    if (used == null || limit <= 0) return 0;
    final raw = used / limit;
    if (raw.isNaN || raw.isInfinite) return 0;
    return raw.clamp(0, 1);
  }

  String _asciiBar(int? used, int limit) {
    final u = (used ?? 0).clamp(0, limit <= 0 ? 1 : limit);
    final total = limit <= 0 ? 1 : limit;
    final percent = (u / total) * 100;
    const barLength = 30;
    final filled = ((barLength * percent) / 100).floor().clamp(0, barLength);
    final bar = ('▓' * filled) + ('-' * (barLength - filled));
    return '[$bar] ${percent.toStringAsFixed(2)}% ($u/$total)';
  }

  Future<void> _refresh({bool silent = false}) async {
    if (!silent) {
      setState(() {
        _loading = true;
        _error = '';
      });
    }
    try {
      final samples = await widget.api.restWeightSamples(limit: 200);
      final snap = await widget.api.gatewaySnapshot();
      final rowsRaw = (samples['items'] as List?) ?? const [];
      final rows = rowsRaw
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final usedRaw = snap['used_weight_1m'];
      final limitRaw = snap['weight_limit_1m'];
      int? used;
      if (usedRaw is int) {
        used = usedRaw;
      } else if (usedRaw is num) {
        used = usedRaw.toInt();
      } else {
        used = int.tryParse('$usedRaw');
      }
      var limit = 6000;
      if (limitRaw is int) {
        limit = limitRaw;
      } else if (limitRaw is num) {
        limit = limitRaw.toInt();
      } else {
        limit = int.tryParse('$limitRaw') ?? 6000;
      }
      final nextPct = _pct(used, limit);
      if (!mounted) return;
      setState(() {
        _rows = rows;
        _gatewayRunning = snap['gateway_running'] == true;
        _liveUsed = used;
        _liveLimit = limit <= 0 ? 6000 : limit;
        _animFrom = _animTo;
        _animTo = nextPct;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.toString();
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Monitor de peso REST (X-MBX-USED-WEIGHT-1M)'),
      content: SizedBox(
        width: 860,
        height: 560,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Este monitor muestra el encabezado acumulado de Binance por ventana de 1 minuto '
              'y por IP compartida. No es por bot individual y puede subir por llamadas de otros '
              'procesos/terminales que usen la misma red.',
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Lógica de cálculo (igual a monitorPesos): ocupación = used_weight_1m / weight_limit_1m.',
              style: const TextStyle(fontSize: 12, fontFamily: 'monospace'),
            ),
            const SizedBox(height: 10),
            if (_loading)
              const LinearProgressIndicator()
            else if (_error.isNotEmpty)
              Text(_error, style: const TextStyle(color: Colors.redAccent))
            else ...[
              Row(
                children: [
                  Text(
                    'Gateway: ${_gatewayRunning ? "ON" : "OFF"}',
                    style: TextStyle(
                      fontWeight: FontWeight.w600,
                      color: _gatewayRunning ? Colors.green : Colors.orange,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Text(
                    'Peso actual: ${_liveUsed ?? "-"} / $_liveLimit',
                    style: const TextStyle(fontFamily: 'monospace'),
                  ),
                ],
              ),
              const SizedBox(height: 8),
              TweenAnimationBuilder<double>(
                tween: Tween<double>(begin: _animFrom, end: _animTo),
                duration: const Duration(milliseconds: 650),
                builder: (context, v, _) => LinearProgressIndicator(
                  minHeight: 10,
                  value: v,
                ),
              ),
              const SizedBox(height: 6),
              SelectableText(
                _asciiBar(_liveUsed, _liveLimit),
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
              ),
              const SizedBox(height: 10),
              Expanded(
                child: _rows.isEmpty
                    ? const Text(
                        'Aún no hay muestras. Activa el gateway y espera algunos segundos.',
                      )
                    : Scrollbar(
                        child: ListView.separated(
                          itemCount: _rows.length,
                          separatorBuilder: (_, index) => const Divider(height: 1),
                          itemBuilder: (ctx, i) {
                            final m = _rows[i];
                            final ts = (m['ts_utc'] ?? '-').toString();
                            final u = m['used_weight_1m'];
                            final lim = m['weight_limit_1m'];
                            final bt = m['hub_bots_total'];
                            final br = m['hub_bots_running'];
                            final poll = m['poll_interval_sec'];
                            final gw = m['gateway_running'];
                            final err = m['last_error_snippet'];
                            return SelectableText(
                              '$ts · peso $u/$lim · bots $br/$bt · poll ${poll}s · '
                              'GW ${gw == true ? "on" : "off"}'
                              '${err != null && err.toString().isNotEmpty ? " · err $err" : ""}',
                              style: const TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 11,
                              ),
                            );
                          },
                        ),
                      ),
              ),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: _loading ? null : () => _refresh(),
          child: const Text('Actualizar'),
        ),
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cerrar'),
        ),
      ],
    );
  }
}

class SpotAccountPage extends StatefulWidget {
  const SpotAccountPage({
    super.key,
    required this.engineBase,
    required this.activeSymbols,
  });

  final String engineBase;
  final List<String> activeSymbols;

  @override
  State<SpotAccountPage> createState() => _SpotAccountPageState();
}

class _SpotAccountPageState extends State<SpotAccountPage> {
  bool _loading = false;
  String _error = '-';
  String _fetchedAt = '-';
  Map<String, dynamic> _summary = <String, dynamic>{};
  Map<String, dynamic> _equity = <String, dynamic>{};
  List<Map<String, dynamic>> _spot = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _futures = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _earn = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _external = <Map<String, dynamic>>[];
  List<String> _warnings = <String>[];
  final _baseAssetCtrl = TextEditingController();
  Timer? _equityTimer;

  EngineApi get _api => EngineApi(widget.engineBase);

  @override
  void initState() {
    super.initState();
    _baseAssetCtrl.text = _inferBaseAsset(widget.activeSymbols);
    _refresh();
    _startEquityTimer();
  }

  @override
  void dispose() {
    _equityTimer?.cancel();
    _baseAssetCtrl.dispose();
    super.dispose();
  }

  void _startEquityTimer() {
    _equityTimer?.cancel();
    _equityTimer = Timer.periodic(
      const Duration(seconds: 3),
      (_) => _refreshLiveEquity(),
    );
  }

  Future<void> _refreshLiveEquity() async {
    if (!mounted) return;
    try {
      final snap = await _api.gatewaySnapshot();
      final equity = Map<String, dynamic>.from(
        (snap['account_equity'] as Map?) ?? const {},
      );
      if (!mounted || equity.isEmpty) return;
      setState(() {
        _equity = equity;
      });
    } catch (_) {
      // Keep last known equity; manual refresh still reports full errors.
    }
  }

  String _inferBaseAsset(List<String> symbols) {
    if (symbols.isEmpty) return 'USDT';
    final s = symbols.first.trim().toUpperCase();
    const quotes = [
      'USDT',
      'FDUSD',
      'USDC',
      'BUSD',
      'BTC',
      'ETH',
      'BNB',
      'TRY',
      'EUR',
    ];
    for (final q in quotes) {
      if (s.endsWith(q) && s.length > q.length) return q;
    }
    return 'USDT';
  }

  Future<void> _refresh({String? forceBaseAsset}) async {
    if (_loading) return;
    final base = (forceBaseAsset ?? _baseAssetCtrl.text).trim().toUpperCase();
    if (base.isEmpty) {
      setState(() => _error = 'Base asset requerido (ej. USDT)');
      return;
    }
    _baseAssetCtrl.text = base;
    setState(() {
      _loading = true;
      _error = '-';
    });
    try {
      await _api.gatewayStart();
      final snapFuture = _api.gatewayFetchAccount();
      final walletsFuture = _api.accountWallets(baseAsset: base);
      final snap = await snapFuture;
      final wallets = await walletsFuture;
      final summary = Map<String, dynamic>.from(
        (snap['account_summary'] as Map?) ?? const {},
      );
      final equity = Map<String, dynamic>.from(
        (snap['account_equity'] as Map?) ?? const {},
      );
      final spot = ((wallets['spot'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final futures = ((wallets['futures'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final earn = ((wallets['stake_earn'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final external = ((wallets['external'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final warnings = ((wallets['warnings'] as List?) ?? const [])
          .map((e) => e.toString())
          .toList();
      final walletEquity = Map<String, dynamic>.from(
        (wallets['equity'] as Map?) ?? const {},
      );
      setState(() {
        _summary = summary;
        _equity = equity.isNotEmpty ? equity : walletEquity;
        _spot = spot;
        _futures = futures;
        _earn = earn;
        _external = external;
        _warnings = warnings;
        _fetchedAt = DateTime.now().toLocal().toString();
      });
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Widget _kpi(String label, String value) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontSize: 12)),
              const SizedBox(height: 4),
              Text(
                value,
                style: const TextStyle(fontFamily: 'monospace', fontSize: 14),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _walletColumn(
    String title,
    List<Map<String, dynamic>> rows, {
    required String primaryKey,
    String? secondaryKey,
  }) {
    final base = _baseAssetCtrl.text.trim().toUpperCase();
    final highlighted = rows.where((r) {
      final asset = (r['asset'] ?? '').toString().toUpperCase();
      return asset == base || asset == 'LD$base';
    }).toList();
    final ordered = [
      ...highlighted,
      ...rows.where((r) => !highlighted.contains(r)),
    ];
    final list = ordered.take(120).toList();
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '$title (${rows.length})',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 6),
              if (list.isEmpty)
                const Text('(vacío)', style: TextStyle(fontSize: 12))
              else
                SizedBox(
                  height: 350,
                  child: ListView.separated(
                    itemCount: list.length,
                    separatorBuilder: (_, separatorIndex) =>
                        const Divider(height: 8),
                    itemBuilder: (ctx, i) {
                      final row = list[i];
                      final asset = (row['asset'] ?? '').toString();
                      final primary = (row[primaryKey] ?? '0').toString();
                      final secondary = secondaryKey == null
                          ? null
                          : (row[secondaryKey] ?? '0').toString();
                      final isBase =
                          asset.toUpperCase() == base ||
                          asset.toUpperCase() == 'LD$base';
                      return Row(
                        children: [
                          SizedBox(
                            width: 88,
                            child: Text(
                              asset,
                              style: TextStyle(
                                fontFamily: 'monospace',
                                color: isBase ? Colors.amberAccent : null,
                                fontWeight: isBase
                                    ? FontWeight.w700
                                    : FontWeight.w400,
                              ),
                            ),
                          ),
                          Expanded(
                            child: Text(
                              secondary == null
                                  ? '$primaryKey ${_plainNum(primary)}'
                                  : '$primaryKey ${_plainNum(primary)} · $secondaryKey ${_plainNum(secondary)}',
                              style: const TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 11,
                              ),
                            ),
                          ),
                        ],
                      );
                    },
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _baseTotalsCard() {
    final base = _baseAssetCtrl.text.trim().toUpperCase();
    String pick(
      List<Map<String, dynamic>> rows,
      String key, {
      bool withLd = false,
    }) {
      final target = withLd ? 'LD$base' : base;
      final row = rows.cast<Map<String, dynamic>?>().firstWhere(
        (r) => (r?['asset'] ?? '').toString().toUpperCase() == target,
        orElse: () => null,
      );
      return (row?[key] ?? '0').toString();
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Row(
          children: [
            _kpi('$base Spot', _plainNum(pick(_spot, 'total'))),
            _kpi('$base Futures', _plainNum(pick(_futures, 'total'))),
            _kpi('LD$base Earn', _plainNum(pick(_earn, 'total', withLd: true))),
            _kpi('$base Ext', _plainNum(pick(_external, 'total'))),
          ],
        ),
      ),
    );
  }

  Widget _equityCard() {
    final base = (_equity['base_asset'] ?? _baseAssetCtrl.text.trim().toUpperCase()).toString();
    final current = _plainNum(_equity['current']);
    final avg = _plainNum(_equity['avg']);
    final highAvg = _plainNum(_equity['high_avg']);
    final missing = (_equity['missing_assets_count'] ?? 0).toString();
    final updatedAt = (_equity['updated_at'] ?? _fetchedAt).toString();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Monitoreo Equity (tiempo real)',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                _kpi('Equity $base', current),
                _kpi('Promedio', avg),
                _kpi('Máx prom', highAvg),
                _kpi('Sin precio', missing),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              'Actualizado: $updatedAt',
              style: const TextStyle(fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  Widget _warningsBlock() {
    if (_warnings.isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Observaciones de lectura',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 4),
            ..._warnings.map(
              (w) => Text('• $w', style: const TextStyle(fontSize: 12)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _baseAssetBar() {
    final symbols = widget.activeSymbols.join(', ');
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Row(
          children: [
            const Text(
              'Activo base Dorothy:',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 110,
              child: TextField(
                controller: _baseAssetCtrl,
                textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(
                  isDense: true,
                  border: OutlineInputBorder(),
                ),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton.tonal(
              onPressed: _loading
                  ? null
                  : () => _refresh(forceBaseAsset: _baseAssetCtrl.text),
              child: const Text('Aplicar'),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'Símbolos activos Dorothy: ${symbols.isEmpty ? '-' : symbols}',
                style: const TextStyle(fontSize: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Cuenta Spot · Binance'),
        actions: [
          IconButton(
            onPressed: _loading
                ? null
                : () => _refresh(forceBaseAsset: _baseAssetCtrl.text),
            tooltip: 'Refrescar resumen Spot',
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
            if (_error != '-')
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  _error,
                  style: const TextStyle(color: Colors.redAccent),
                ),
              ),
            _baseAssetBar(),
            _equityCard(),
            _baseTotalsCard(),
            _warningsBlock(),
            Text(
              'Última lectura: $_fetchedAt',
              style: const TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                _kpi(
                  'Account type',
                  (_summary['accountType'] ?? '-').toString(),
                ),
                _kpi('Can trade', (_summary['canTrade'] ?? '-').toString()),
                _kpi(
                  'Can withdraw',
                  (_summary['canWithdraw'] ?? '-').toString(),
                ),
                _kpi('Can deposit', (_summary['canDeposit'] ?? '-').toString()),
              ],
            ),
            Row(
              children: [
                _kpi(
                  'Maker fee',
                  (_summary['makerCommission'] ?? '-').toString(),
                ),
                _kpi(
                  'Taker fee',
                  (_summary['takerCommission'] ?? '-').toString(),
                ),
                _kpi(
                  'Buyer fee',
                  (_summary['buyerCommission'] ?? '-').toString(),
                ),
                _kpi(
                  'Seller fee',
                  (_summary['sellerCommission'] ?? '-').toString(),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _walletColumn(
                  'Spot',
                  _spot,
                  primaryKey: 'free',
                  secondaryKey: 'locked',
                ),
                _walletColumn(
                  'Futures',
                  _futures,
                  primaryKey: 'wallet_balance',
                  secondaryKey: 'cross_wallet_balance',
                ),
                _walletColumn(
                  'Stake/Earn',
                  _earn,
                  primaryKey: 'free',
                  secondaryKey: 'locked',
                ),
                _walletColumn(
                  'Ext',
                  _external,
                  primaryKey: 'free',
                  secondaryKey: 'locked',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
