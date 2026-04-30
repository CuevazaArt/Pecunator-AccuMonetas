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
  final _maxDdCtrl = TextEditingController(text: '0.20');
  final _stopLossCtrl = TextEditingController(text: '0.10');
  final _metricsEveryCtrl = TextEditingController(text: '5');

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
  Map<String, dynamic>? _closeProtocolState;
  Map<String, dynamic>? _redButtonState;
  Map<String, dynamic>? _cleanupLimitState;
  Map<String, dynamic>? _cleanupStopState;
  Map<String, dynamic>? _cleanupAllState;
  final _credLabelCtrl = TextEditingController();
  final _credKeyCtrl = TextEditingController();
  final _credSecretCtrl = TextEditingController();
  Timer? _refreshTimer;
  Timer? _clockTimer;
  String _clockText = '--:--:--';
  String _opsBaseAsset = 'USDT';

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
    _maxDdCtrl.dispose();
    _stopLossCtrl.dispose();
    _metricsEveryCtrl.dispose();
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
      final elapsed = DateTime.now().toUtc().difference(
        _binanceSrvObservedUtc!,
      );
      return _binanceSrvUtc!.add(elapsed);
    }
    return null;
  }

  void _tickBinanceClock() {
    final t = _displayBinanceUtcNow();
    _clockText = t != null ? _formatClock(t.toLocal()) : '--:--:--';
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

  Color _restWeightColor(int? used, int limit) {
    if (used == null || limit <= 0) return Colors.blueAccent;
    final pct = used / limit;
    if (pct >= 0.9) return Colors.redAccent;
    if (pct >= 0.7) return Colors.orangeAccent;
    return Colors.lightGreenAccent;
  }

  String _settingTooltip(String field) {
    switch (field) {
      case 'tag':
        return 'Nombre local de la instancia Dorothy para diferenciar seteo/mercado.';
      case 'symbol':
        return 'Par spot objetivo (ej. XRPUSDT). Determina el mercado sobre el que Dorothy tomará decisiones.';
      case 'loop':
        return 'Segundos entre iteraciones (tiempoEntreEjecucion). Menor valor = más reactividad y más carga REST.';
      case 'qty':
        return 'Monto de compra en quote (quoteOrderQtyModulo, normalmente USDT). Ajustarlo por volatilidad y tamaño de cuenta.';
      case 'profit':
        return 'Factor de beneficio por ciclo. 0.05 equivale a 5%; más alto exige más recorrido para ejecutar salida.';
      case 'drop':
        return 'Margen extra de caída para habilitar compra. Ayuda a espaciar entradas y evitar sobreoperar en rango estrecho.';
      case 'qDec':
        return 'Decimales de cantidad (LOT_SIZE). Si está mal configurado, Binance rechazará la orden.';
      case 'pDec':
        return 'Decimales del precio LIMIT (PRICE_FILTER). Ajustar según tick size del símbolo.';
      case 'note':
        return 'Nota operativa para identificar objetivo o contexto de esta instancia.';
      case 'maxDd':
        return 'Drawdown máximo tolerado (decimal). Si se excede, Dorothy bloquea nuevas compras para contener riesgo.';
      case 'stopLoss':
        return 'Stop-loss por posición (decimal). Fuerza salida defensiva cuando el precio cae bajo el umbral configurado.';
      case 'metricsEvery':
        return 'Número de ciclos entre cálculos de métricas (Sharpe, win rate, max drawdown) persistidas en SQLite.';
      default:
        return field;
    }
  }

  String _extractQuoteAsset(String symbol) {
    final s = symbol.trim().toUpperCase();
    const knownQuotes = [
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
    for (final q in knownQuotes) {
      if (s.endsWith(q) && s.length > q.length) {
        return q;
      }
    }
    return 'USDT';
  }

  String _deriveOperationalBaseAsset(List<Map<String, dynamic>> bots) {
    final counts = <String, int>{};
    for (final b in bots) {
      final symbol = (b['symbol'] ?? '').toString();
      if (symbol.isEmpty) continue;
      final quote = _extractQuoteAsset(symbol);
      counts[quote] = (counts[quote] ?? 0) + 1;
    }
    if (counts.isEmpty) return 'USDT';
    final sorted = counts.entries.toList()
      ..sort((a, b) => b.value.compareTo(a.value));
    return sorted.first.key;
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
    _opsBaseAsset = _deriveOperationalBaseAsset(_hubBots);
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
      final serverMs = snap['binance_server_time_ms'];
      final localSyncMs = snap['binance_local_time_ms_at_sync'];
      if (serverMs is num && localSyncMs is num) {
        _binanceSrvUtc = DateTime.fromMillisecondsSinceEpoch(
          serverMs.toInt(),
          isUtc: true,
        );
        _binanceSrvObservedUtc = DateTime.fromMillisecondsSinceEpoch(
          localSyncMs.toInt(),
          isUtc: true,
        );
        _tickBinanceClock();
      }
    } catch (_) {
      _gatewayRunning = false;
      _gatewayWsConnected = false;
      _gatewayLastError = null;
      _apiWeightUsed = null;
    }
    try {
      final st = await _api.protocolOpsStatus();
      _closeProtocolState = st['close_protocol'] is Map
          ? Map<String, dynamic>.from(st['close_protocol'] as Map)
          : null;
      _redButtonState = st['red_button'] is Map
          ? Map<String, dynamic>.from(st['red_button'] as Map)
          : null;
      _cleanupLimitState = st['cancel_limit_orders_cleanup'] is Map
          ? Map<String, dynamic>.from(st['cancel_limit_orders_cleanup'] as Map)
          : null;
      _cleanupStopState = st['cancel_stop_orders_cleanup'] is Map
          ? Map<String, dynamic>.from(st['cancel_stop_orders_cleanup'] as Map)
          : null;
      _cleanupAllState = st['cancel_all_orders_cleanup'] is Map
          ? Map<String, dynamic>.from(st['cancel_all_orders_cleanup'] as Map)
          : null;
    } catch (_) {
      // Keep previous operation status if endpoint is unavailable.
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
        'max_drawdown_pct': (draft['maxDd'] ?? '0.20').trim(),
        'stop_loss_pct': (draft['stopLoss'] ?? '0.10').trim(),
        'metrics_interval_cycles':
            int.tryParse((draft['metricsEvery'] ?? '5').trim()) ?? 5,
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
        'max_drawdown_pct': _maxDdCtrl.text.trim(),
        'stop_loss_pct': _stopLossCtrl.text.trim(),
        'metrics_interval_cycles': int.tryParse(_metricsEveryCtrl.text.trim()) ?? 5,
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

  Color _opStatusColor(String status) {
    switch (status.toLowerCase()) {
      case 'ok':
        return Colors.greenAccent;
      case 'partial':
        return Colors.orangeAccent;
      case 'failed':
        return Colors.redAccent;
      default:
        return Colors.grey;
    }
  }

  Future<bool?> _confirmProtocolDialog({
    required String title,
    required String message,
  }) {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(message),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Ejecutar'),
          ),
        ],
      ),
    );
  }

  Future<void> _runCloseProtocol() async {
    final ok = await _confirmProtocolDialog(
      title: 'Ejecutar protocolo de cierre',
      message:
          'Antes de cerrar/cancelar órdenes, se detendrán todas las instancias Dorothy '
          'para evitar ciclos de disposición/convertir activos en paralelo. '
          'Base operativa detectada: $_opsBaseAsset. ¿Continuar?',
    );
    if (ok != true) return;
    await _withBusy(() async {
      final r = await _api.executeCloseProtocol(baseAsset: _opsBaseAsset);
      final rec = r['record'];
      final summary = r['summary'];
      if (rec is Map) {
        _closeProtocolState = Map<String, dynamic>.from(rec);
      } else if (summary is Map) {
        _closeProtocolState = <String, dynamic>{
          'status': summary['status'],
          'summary': summary,
        };
      }
      await _reloadData();
    });
  }

  Future<void> _runRedButton() async {
    final ok = await _confirmProtocolDialog(
      title: 'Ejecutar RED BUTTON',
      message:
          'Esto intentará vender a mercado activos Spot al base asset ($_opsBaseAsset). '
          'Primero detendrá todas las instancias Dorothy para evitar conflictos operativos. '
          'Usar solo en eventos de salida de emergencia. ¿Continuar?',
    );
    if (ok != true) return;
    await _withBusy(() async {
      final r = await _api.executeRedButton(baseAsset: _opsBaseAsset);
      final rec = r['record'];
      final summary = r['summary'];
      if (rec is Map) {
        _redButtonState = Map<String, dynamic>.from(rec);
      } else if (summary is Map) {
        _redButtonState = <String, dynamic>{
          'status': summary['status'],
          'summary': summary,
        };
      }
      await _reloadData();
    });
  }

  Future<void> _runCleanupLimitOrders() async {
    final ok = await _confirmProtocolDialog(
      title: 'Cancelar LIMIT (cleanup)',
      message:
          'Se detendrán primero todas las instancias Dorothy activas. '
          'Luego se cancelarán órdenes LIMIT detectadas en pares Spot del inventario para base $_opsBaseAsset. '
          '¿Continuar?',
    );
    if (ok != true) return;
    await _withBusy(() async {
      final r = await _api.executeOrderCleanupLimit(baseAsset: _opsBaseAsset);
      final rec = r['record'];
      final summary = r['summary'];
      if (rec is Map) {
        _cleanupLimitState = Map<String, dynamic>.from(rec);
      } else if (summary is Map) {
        _cleanupLimitState = <String, dynamic>{
          'status': summary['status'],
          'summary': summary,
        };
      }
      await _reloadData();
    });
  }

  Future<void> _runCleanupStopOrders() async {
    final ok = await _confirmProtocolDialog(
      title: 'Cancelar STOP (cleanup)',
      message:
          'Se detendrán primero todas las instancias Dorothy activas. '
          'Luego se cancelarán órdenes STOP/STOP_LIMIT/TAKE_PROFIT detectadas en pares Spot del inventario para base $_opsBaseAsset. '
          '¿Continuar?',
    );
    if (ok != true) return;
    await _withBusy(() async {
      final r = await _api.executeOrderCleanupStop(baseAsset: _opsBaseAsset);
      final rec = r['record'];
      final summary = r['summary'];
      if (rec is Map) {
        _cleanupStopState = Map<String, dynamic>.from(rec);
      } else if (summary is Map) {
        _cleanupStopState = <String, dynamic>{
          'status': summary['status'],
          'summary': summary,
        };
      }
      await _reloadData();
    });
  }

  Future<void> _runCleanupAllOrders() async {
    final ok = await _confirmProtocolDialog(
      title: 'Cancelar TODAS las órdenes (cleanup total)',
      message:
          'Se detendrán primero todas las instancias Dorothy activas. '
          'Luego se cancelará toda orden abierta encontrada en la cuenta Spot (base $_opsBaseAsset). '
          'Usar solo cuando quieras limpiar completamente el libro de órdenes. ¿Continuar?',
    );
    if (ok != true) return;
    await _withBusy(() async {
      final r = await _api.executeOrderCleanupAll(baseAsset: _opsBaseAsset);
      final rec = r['record'];
      final summary = r['summary'];
      if (rec is Map) {
        _cleanupAllState = Map<String, dynamic>.from(rec);
      } else if (summary is Map) {
        _cleanupAllState = <String, dynamic>{
          'status': summary['status'],
          'summary': summary,
        };
      }
      await _reloadData();
    });
  }

  void _openProtocolSummaryDialog(String title, Map<String, dynamic>? row) {
    if (row == null) return;
    final summary = row['summary'] is Map
        ? Map<String, dynamic>.from(row['summary'] as Map)
        : <String, dynamic>{};
    final rendered = const JsonEncoder.withIndent(
      '  ',
    ).convert(<String, dynamic>{...row, 'summary': summary});
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: SizedBox(
          width: 900,
          child: SingleChildScrollView(
            child: SelectableText(
              rendered,
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
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Credencial eliminada')));
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
      setState(
        () => _lastError = 'API key y secret deben tener al menos 8 caracteres',
      );
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
      final updatedExisting = created['updated_existing'] == true;
      _credKeyCtrl.clear();
      _credSecretCtrl.clear();
      _credLabelCtrl.clear();
      await _reloadData();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              updatedExisting
                  ? 'Credencial existente actualizada y activada'
                  : 'Credencial nueva agregada y activada',
            ),
          ),
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
            style: FilledButton.styleFrom(
              backgroundColor: Colors.redAccent.withValues(alpha: 0.18),
              foregroundColor: Colors.redAccent,
            ),
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
                        'La nueva credencial se activa automáticamente.',
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
                              label: const Text('Agregar nueva'),
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
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const BotGuidePage(botName: 'Dorothy'),
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

  Future<void> _openSandboxPage() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ApiSandboxPage(engineBase: _engineBase),
      ),
    );
  }

  Future<void> _openMashaPage() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => MashaHubPage(engineBase: _engineBase),
      ),
    );
  }

  Future<void> _openThusneldaPage() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => ThusneldaHubPage(engineBase: _engineBase),
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
        'maxDd': (bot['max_drawdown_pct'] ?? '0.20').toString(),
        'stopLoss': (bot['stop_loss_pct'] ?? '0.10').toString(),
        'metricsEvery': (bot['metrics_interval_cycles'] ?? 5).toString(),
        'simulated': 'true',
        'trading_enabled': 'false',
      };
    });
    d['simulated'] = ((bot['simulated'] ?? true) == true).toString();
    d['trading_enabled'] = ((bot['trading_enabled'] ?? false) == true)
        .toString();
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

  Widget _protocolModuleCard({
    required String title,
    required IconData icon,
    required String description,
    required String precautions,
    required Map<String, dynamic>? state,
    required VoidCallback onRun,
    required VoidCallback onViewSummary,
    required Color accent,
  }) {
    final status = (state?['status'] ?? '-').toString();
    final ts = (state?['ts_utc'] ?? '-').toString();
    final summary = state?['summary'] is Map
        ? Map<String, dynamic>.from(state?['summary'] as Map)
        : <String, dynamic>{};
    final stopped = (summary['stopped_dorothy_instances'] ?? '-').toString();
    final elapsed = (summary['elapsed_sec'] ?? '-').toString();
    final errors = [
      ...(summary['stop_errors'] is List
          ? (summary['stop_errors'] as List)
          : const []),
      ...(summary['cancel_errors'] is List
          ? (summary['cancel_errors'] as List)
          : const []),
      ...(summary['sell_errors'] is List
          ? (summary['sell_errors'] as List)
          : const []),
    ].length;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Icon(icon, size: 18, color: accent),
          const SizedBox(width: 8),
          SizedBox(
            width: 130,
            child: Row(
              children: [
                Flexible(
                  child: Text(
                    title,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                ),
                const SizedBox(width: 4),
                Tooltip(
                  message: '$description\n\nPrecauciones:\n$precautions',
                  child: const Icon(Icons.info_outline, size: 14),
                ),
              ],
            ),
          ),
          const SizedBox(width: 8),
          SizedBox(
            width: 84,
            child: Text(
              status,
              style: TextStyle(
                fontSize: 11,
                fontFamily: 'monospace',
                color: _opStatusColor(status),
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'ts $ts · stopped $stopped · err $errors · ${_plainNum(elapsed)}s',
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
            ),
          ),
          const SizedBox(width: 8),
          FilledButton.tonal(
            style: FilledButton.styleFrom(
              backgroundColor: accent.withValues(alpha: 0.18),
              foregroundColor: accent,
            ),
            onPressed: _loading ? null : onRun,
            child: const Text('Ejecutar'),
          ),
          const SizedBox(width: 6),
          OutlinedButton(
            onPressed: state == null ? null : onViewSummary,
            child: const Text('Resumen'),
          ),
        ],
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
            onPressed: _loading ? null : _openMashaPage,
            tooltip: 'Hub de instancias Masha2.0',
            icon: const Icon(Icons.psychology_alt_outlined, size: 18),
          ),
          IconButton(
            onPressed: _loading ? null : _openThusneldaPage,
            tooltip: 'Hub de instancias Thusnelda1.0',
            icon: const Icon(Icons.hub_outlined, size: 18),
          ),
          IconButton(
            onPressed: _loading ? null : _openSandboxPage,
            tooltip: 'Sandbox de endpoints y datos curados',
            icon: const Icon(Icons.science_outlined, size: 18),
          ),
          IconButton(
            onPressed: _loading ? null : _openCredentialManager,
            tooltip: 'Gestionar API keys',
            icon: const Icon(Icons.key, size: 18),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Tooltip(
              message:
                  'Gateway ${_gatewayRunning ? "ON" : "OFF"}'
                  '${_gatewayWsConnected ? " · WS" : ""}',
              child: Icon(
                Icons.circle,
                size: 10,
                color: _gatewayTrafficColor(),
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
                'Hora estimada del servidor Binance mostrada en hora local de este equipo '
                '(GET /api/v3/time a través del motor). Pulsa el icono de reloj para sincronizar.',
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
                      'LOCAL',
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
                      'Misma métrica de cabecera Binance (X-MBX-USED-WEIGHT-1M). '
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
                          value:
                              (_apiWeightUsed!.clamp(0, _apiWeightLimit)) /
                              _apiWeightLimit,
                          valueColor: AlwaysStoppedAnimation<Color>(
                            _restWeightColor(_apiWeightUsed, _apiWeightLimit),
                          ),
                          backgroundColor: Theme.of(context)
                              .colorScheme
                              .surfaceContainerHighest,
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
            Text(
              'Activo base operativo: $_opsBaseAsset',
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
                child: Column(
                  children: [
                    _protocolModuleCard(
                      title: 'Protocolo Cierre',
                      icon: Icons.rule_folder_outlined,
                      accent: Colors.amberAccent,
                      description:
                          'Cancela órdenes LIMIT abiertas y toma snapshot operativo/equity de salida.',
                      precautions:
                          '- Detiene Dorothy antes de ejecutar.\n'
                          '- Úsalo para cierre controlado, no para liquidación total.\n'
                          '- Revisa el resumen para trazabilidad.',
                      state: _closeProtocolState,
                      onRun: _runCloseProtocol,
                      onViewSummary: () => _openProtocolSummaryDialog(
                        'Resumen · Protocolo de Cierre',
                        _closeProtocolState,
                      ),
                    ),
                    const Divider(height: 1),
                    _protocolModuleCard(
                      title: 'RED BUTTON',
                      icon: Icons.warning_amber_rounded,
                      accent: Colors.redAccent,
                      description:
                          'Rutina de salida de emergencia: intenta convertir balances Spot al asset base vía ventas a mercado.',
                      precautions:
                          '- Detiene Dorothy antes de vender.\n'
                          '- Puede fallar en activos sin par directo o por filtros LOT_SIZE.\n'
                          '- Ejecutar solo cuando sea estrictamente necesario.',
                      state: _redButtonState,
                      onRun: _runRedButton,
                      onViewSummary: () => _openProtocolSummaryDialog(
                        'Resumen · RED BUTTON',
                        _redButtonState,
                      ),
                    ),
                    const Divider(height: 1),
                    _protocolModuleCard(
                      title: 'Cleanup LIMIT',
                      icon: Icons.format_list_numbered,
                      accent: Colors.lightBlueAccent,
                      description:
                          'Evalúa pares Spot con balance y cancela órdenes LIMIT abiertas.',
                      precautions:
                          '- Primero detiene instancias Dorothy activas.\n'
                          '- No vende activos, solo limpia órdenes LIMIT.\n'
                          '- Útil antes de relanzar estrategia con libro limpio.',
                      state: _cleanupLimitState,
                      onRun: _runCleanupLimitOrders,
                      onViewSummary: () => _openProtocolSummaryDialog(
                        'Resumen · Cleanup LIMIT',
                        _cleanupLimitState,
                      ),
                    ),
                    const Divider(height: 1),
                    _protocolModuleCard(
                      title: 'Cleanup STOP',
                      icon: Icons.pause_circle_outline,
                      accent: Colors.orangeAccent,
                      description:
                          'Cancela órdenes STOP/STOP_LIMIT/TAKE_PROFIT detectadas en pares Spot del inventario.',
                      precautions:
                          '- Primero detiene instancias Dorothy activas.\n'
                          '- Útil cuando quedan stops huérfanos.\n'
                          '- No toca posiciones, solo órdenes abiertas tipo stop.',
                      state: _cleanupStopState,
                      onRun: _runCleanupStopOrders,
                      onViewSummary: () => _openProtocolSummaryDialog(
                        'Resumen · Cleanup STOP',
                        _cleanupStopState,
                      ),
                    ),
                    const Divider(height: 1),
                    _protocolModuleCard(
                      title: 'Cleanup TOTAL',
                      icon: Icons.cleaning_services_outlined,
                      accent: Colors.purpleAccent,
                      description:
                          'Limpieza total de órdenes: cancela toda orden abierta encontrada en la cuenta.',
                      precautions:
                          '- Primero detiene instancias Dorothy activas.\n'
                          '- Es la versión más agresiva de limpieza.\n'
                          '- Usar cuando quieras dejar libro totalmente vacío.',
                      state: _cleanupAllState,
                      onRun: _runCleanupAllOrders,
                      onViewSummary: () => _openProtocolSummaryDialog(
                        'Resumen · Cleanup TOTAL',
                        _cleanupAllState,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(8),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Text(
                          'Nueva instancia Dorothy',
                          style: TextStyle(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(width: 8),
                        Tooltip(
                          message: 'Crear instancia con este seteo',
                          child: FilledButton.icon(
                            onPressed: _loading ? null : _createBot,
                            icon: const Icon(Icons.add_circle_outline, size: 16),
                            label: const Text('Nueva instancia'),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    SingleChildScrollView(
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
                      const SizedBox(width: 6),
                      _field(
                        _maxDdCtrl,
                        'maxDd',
                        width: 90,
                        tooltip: _settingTooltip('maxDd'),
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _stopLossCtrl,
                        'stopLoss',
                        width: 90,
                        tooltip: _settingTooltip('stopLoss'),
                      ),
                      const SizedBox(width: 6),
                      _field(
                        _metricsEveryCtrl,
                        'metricsEvery',
                        width: 90,
                        tooltip: _settingTooltip('metricsEvery'),
                      ),
                          const SizedBox(width: 10),
                          IconButton(
                            tooltip: 'Seteos usados anteriormente',
                            onPressed: _loading ? null : _openConfigHistoryDialog,
                            icon: const Icon(Icons.history, size: 18),
                          ),
                        ],
                      ),
                    ),
                  ],
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
                        const SizedBox(width: 8),
                        Text(
                          'dd ${_plainNum(b['max_drawdown_pct'])}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'sl ${_plainNum(b['stop_loss_pct'])}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'm${(b['metrics_interval_cycles'] ?? '-')}',
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
                        activeThumbColor: Colors.redAccent,
                        activeTrackColor: Colors.redAccent.withValues(alpha: 0.3),
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
                            const SizedBox(width: 6),
                            _draftField(
                              botId,
                              draft,
                              'maxDd',
                              label: 'maxDd',
                              width: 85,
                              tooltip: _settingTooltip('maxDd'),
                            ),
                            const SizedBox(width: 6),
                            _draftField(
                              botId,
                              draft,
                              'stopLoss',
                              label: 'stopLoss',
                              width: 90,
                              tooltip: _settingTooltip('stopLoss'),
                            ),
                            const SizedBox(width: 6),
                            _draftField(
                              botId,
                              draft,
                              'metricsEvery',
                              label: 'metricsEvery',
                              width: 95,
                              tooltip: _settingTooltip('metricsEvery'),
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
  State<_RestWeightMonitorDialog> createState() =>
      _RestWeightMonitorDialogState();
}

class _RestWeightMonitorDialogState extends State<_RestWeightMonitorDialog> {
  bool _loading = true;
  String _error = '';
  List<Map<String, dynamic>> _rows = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _events = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _topActions = <Map<String, dynamic>>[];
  Map<String, dynamic> _report = <String, dynamic>{};
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

  Color _weightColorFromPct(double pct) {
    if (pct >= 0.9) return Colors.redAccent;
    if (pct >= 0.7) return Colors.orangeAccent;
    return Colors.lightGreenAccent;
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
      final events = await widget.api.restWeightEvents(limit: 300);
      final report = await widget.api.restWeightReport();
      final rowsRaw = (samples['items'] as List?) ?? const [];
      final rows = rowsRaw
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final eventRows = ((events['items'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final topRows = ((report['top_actions'] as List?) ?? const [])
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
        _events = eventRows;
        _report = Map<String, dynamic>.from(report);
        _topActions = topRows;
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
                  valueColor: AlwaysStoppedAnimation<Color>(
                    _weightColorFromPct(v),
                  ),
                  backgroundColor: Theme.of(context)
                      .colorScheme
                      .surfaceContainerHighest,
                ),
              ),
              const SizedBox(height: 6),
              SelectableText(
                _asciiBar(_liveUsed, _liveLimit),
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
              ),
              const SizedBox(height: 10),
              Expanded(
                child: DefaultTabController(
                  length: 3,
                  child: Column(
                    children: [
                      const TabBar(
                        isScrollable: true,
                        tabs: [
                          Tab(text: 'Resumen'),
                          Tab(text: 'Eventos'),
                          Tab(text: 'Muestras'),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Expanded(
                        child: TabBarView(
                          children: [
                            _buildSummaryTab(context),
                            _buildEventsTab(),
                            _buildSamplesTab(),
                          ],
                        ),
                      ),
                    ],
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

  Widget _buildSummaryTab(BuildContext context) {
    final cfg = _report['polling_config'] is Map
        ? Map<String, dynamic>.from(_report['polling_config'] as Map)
        : <String, dynamic>{};
    final est = _report['estimated_calls_per_min'] is Map
        ? Map<String, dynamic>.from(_report['estimated_calls_per_min'] as Map)
        : <String, dynamic>{};
    final notes = ((_report['notes'] as List?) ?? const []).map((e) => '$e').toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SelectableText(
          'Poll s=${cfg['account_poll_sec'] ?? "-"} | myTrades stride=${cfg['my_trades_stride'] ?? "-"} | '
          'equity stride=${cfg['equity_stride'] ?? "-"} | ciclos/min=${est['cycles_per_min'] ?? "-"}',
          style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
        ),
        const SizedBox(height: 6),
        ...notes.take(3).map(
          (n) => Text(
            '- $n',
            style: TextStyle(
              fontSize: 11,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        const Divider(height: 14),
        Text(
          'Top acciones por delta acumulado',
          style: Theme.of(context).textTheme.titleSmall,
        ),
        const SizedBox(height: 6),
        Expanded(
          child: _topActions.isEmpty
              ? const Text('Aún no hay acciones auditadas.')
              : ListView.builder(
                  itemCount: _topActions.length.clamp(0, 25),
                  itemBuilder: (ctx, i) {
                    final r = _topActions[i];
                    final src = (r['source'] ?? '-').toString();
                    final action = (r['action'] ?? '-').toString();
                    final events = (r['events'] ?? '-').toString();
                    final delta = (r['delta_sum'] ?? '-').toString();
                    final avg = _plainNum(r['delta_avg']);
                    return SelectableText(
                      '[$src] $action · events=$events · delta_sum=$delta · delta_avg=$avg',
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 11,
                      ),
                    );
                  },
                ),
        ),
      ],
    );
  }

  Widget _buildEventsTab() {
    if (_events.isEmpty) {
      return const Text('Aún no hay eventos de auditoría de peso.');
    }
    return ListView.separated(
      itemCount: _events.length,
      separatorBuilder: (_, index) => const Divider(height: 1),
      itemBuilder: (ctx, i) {
        final e = _events[i];
        final ts = (e['ts_utc'] ?? '-').toString();
        final src = (e['source'] ?? '-').toString();
        final action = (e['action'] ?? '-').toString();
        final used = (e['used_weight_1m'] ?? '-').toString();
        final delta = (e['delta_weight_1m'] ?? '-').toString();
        final note = (e['note'] ?? '').toString();
        return SelectableText(
          '$ts · [$src] $action · used=$used · delta=$delta${note.isEmpty ? "" : " · $note"}',
          style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
        );
      },
    );
  }

  Widget _buildSamplesTab() {
    if (_rows.isEmpty) {
      return const Text(
        'Aún no hay muestras. Activa el gateway y espera algunos segundos.',
      );
    }
    return ListView.separated(
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
          style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
        );
      },
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

class MashaHubPage extends StatefulWidget {
  const MashaHubPage({super.key, required this.engineBase});

  final String engineBase;

  @override
  State<MashaHubPage> createState() => _MashaHubPageState();
}

class _MashaHubPageState extends State<MashaHubPage> {
  final _tagCtrl = TextEditingController(text: 'Masha');
  final _symbolCtrl = TextEditingController(text: 'BTCUSDT');
  final _baseCtrl = TextEditingController(text: 'BTC');
  final _quoteCtrl = TextEditingController(text: 'USDT');
  final _loopCtrl = TextEditingController(text: '300');
  final _minQuoteCtrl = TextEditingController(text: '6');
  final _buyQtyCtrl = TextEditingController(text: '0.001');
  final _profitCtrl = TextEditingController(text: '0.01');
  final _tfWCtrl = TextEditingController(text: '1w');
  final _periodsWCtrl = TextEditingController(text: '2');
  final _mmWCtrl = TextEditingController(text: '2');
  final _marginWCtrl = TextEditingController(text: '0.03');
  final _tfHCtrl = TextEditingController(text: '1h');
  final _periodsHCtrl = TextEditingController(text: '2');
  final _mmHCtrl = TextEditingController(text: '2');
  final _marginHCtrl = TextEditingController(text: '0.003');
  final _qtyDecCtrl = TextEditingController(text: '8');
  final _priceDecCtrl = TextEditingController(text: '8');
  final _noteCtrl = TextEditingController();
  final _maxDdCtrl = TextEditingController(text: '0.25');
  final _stopLossCtrl = TextEditingController(text: '0.15');
  final _metricsEveryCtrl = TextEditingController(text: '5');

  bool _loading = false;
  String _error = '-';
  List<Map<String, dynamic>> _bots = <Map<String, dynamic>>[];
  final Map<String, Map<String, String>> _draftByBot = <String, Map<String, String>>{};
  final Map<String, String> _logsByBot = <String, String>{};
  final Set<String> _expandedBots = <String>{};
  final Map<String, ScrollController> _logScrollByBot = <String, ScrollController>{};
  Timer? _refreshTimer;

  EngineApi get _api => EngineApi(widget.engineBase);

  @override
  void initState() {
    super.initState();
    _refreshAll();
    _refreshTimer = Timer.periodic(const Duration(seconds: 4), (_) {
      if (mounted && !_loading) {
        _reload();
      }
    });
  }

  @override
  void dispose() {
    _tagCtrl.dispose();
    _symbolCtrl.dispose();
    _baseCtrl.dispose();
    _quoteCtrl.dispose();
    _loopCtrl.dispose();
    _minQuoteCtrl.dispose();
    _buyQtyCtrl.dispose();
    _profitCtrl.dispose();
    _tfWCtrl.dispose();
    _periodsWCtrl.dispose();
    _mmWCtrl.dispose();
    _marginWCtrl.dispose();
    _tfHCtrl.dispose();
    _periodsHCtrl.dispose();
    _mmHCtrl.dispose();
    _marginHCtrl.dispose();
    _qtyDecCtrl.dispose();
    _priceDecCtrl.dispose();
    _noteCtrl.dispose();
    _maxDdCtrl.dispose();
    _stopLossCtrl.dispose();
    _metricsEveryCtrl.dispose();
    for (final c in _logScrollByBot.values) {
      c.dispose();
    }
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _withBusy(Future<void> Function() fn) async {
    if (_loading) return;
    setState(() => _loading = true);
    try {
      await fn();
      _error = '-';
    } catch (e) {
      _error = e.toString();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(_error)),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Map<String, String> _draftFor(Map<String, dynamic> bot) {
    final botId = (bot['bot_id'] ?? '').toString();
    final d = _draftByBot.putIfAbsent(botId, () {
      return <String, String>{
        'tag': (bot['tag'] ?? 'Masha').toString(),
        'symbol': (bot['symbol'] ?? 'BTCUSDT').toString(),
        'base': (bot['base_asset'] ?? 'BTC').toString(),
        'quote': (bot['quote_asset'] ?? 'USDT').toString(),
        'loop': (bot['loop_interval_sec'] ?? 300).toString(),
        'minQuote': (bot['quote_min_free_to_operate'] ?? '6').toString(),
        'buyQty': (bot['buy_qty_base'] ?? '0.001').toString(),
        'profit': (bot['profit_factor'] ?? '0.01').toString(),
        'tfW': (bot['timeframe_w'] ?? '1w').toString(),
        'pW': (bot['periods_w'] ?? 2).toString(),
        'mmW': (bot['mm_periods_w'] ?? 2).toString(),
        'mW': (bot['margin_low_w'] ?? '0.03').toString(),
        'tfH': (bot['timeframe_h'] ?? '1h').toString(),
        'pH': (bot['periods_h'] ?? 2).toString(),
        'mmH': (bot['mm_periods_h'] ?? 2).toString(),
        'mH': (bot['margin_low_h'] ?? '0.003').toString(),
        'qDec': (bot['qty_decimals'] ?? 8).toString(),
        'pDec': (bot['price_decimals'] ?? 8).toString(),
        'note': (bot['note'] ?? '').toString(),
        'maxDd': (bot['max_drawdown_pct'] ?? '0.25').toString(),
        'stopLoss': (bot['stop_loss_pct'] ?? '0.15').toString(),
        'metricsEvery': (bot['metrics_interval_cycles'] ?? 5).toString(),
      };
    });
    return d;
  }

  String _settingTooltip(String key) {
    switch (key) {
      case 'tag':
        return 'Nombre local de la instancia Masha para distinguir mercados o variantes.';
      case 'symbol':
        return 'Par spot principal (ej. BTCUSDT). Debe ser consistente con Base/Quote.';
      case 'base':
        return 'Activo base del par (parte izquierda del símbolo).';
      case 'quote':
        return 'Activo cotizado del par (parte derecha del símbolo, p.ej. USDT).';
      case 'loop':
        return 'Segundos entre ciclos. Más bajo = más reactividad y más consumo REST.';
      case 'minQuote':
        return 'Quote mínima libre para habilitar nuevas compras.';
      case 'buyQty':
        return 'Cantidad de base por compra cuando la señal habilita entrada.';
      case 'profit':
        return 'Objetivo de beneficio para la salida LIMIT consolidada.';
      case 'tfW':
      case 'tfH':
        return 'Timeframe de velas para señal técnica (W y H).';
      case 'pW':
      case 'pH':
        return 'Cantidad de velas para el promedio del timeframe.';
      case 'mmW':
      case 'mmH':
        return 'Suavizado de media móvil para confirmar tendencia.';
      case 'mW':
      case 'mH':
        return 'Margen mínimo para validar entrada respecto a la media.';
      case 'qDec':
        return 'Decimales para cantidad (cumplir LOT_SIZE).';
      case 'pDec':
        return 'Decimales de precio para órdenes LIMIT (cumplir PRICE_FILTER).';
      case 'note':
        return 'Nota operativa corta de la configuración.';
      case 'maxDd':
        return 'Drawdown máximo tolerado. Si se supera, bloquea nuevas compras.';
      case 'stopLoss':
        return 'Stop-loss por posición DCA para cortar pérdidas extremas.';
      case 'metricsEvery':
        return 'Frecuencia de cálculo/persistencia de métricas (ciclos).';
      default:
        return key;
    }
  }

  Widget _newField(
    TextEditingController controller,
    String label,
    double width,
    String key,
  ) {
    return SizedBox(
      width: width,
      child: Tooltip(
        message: _settingTooltip(key),
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

  Widget _f(
    String botId,
    Map<String, String> d,
    String key,
    String label,
    double width,
  ) {
    final value = d[key] ?? '';
    return SizedBox(
      width: width,
      child: Tooltip(
        message: _settingTooltip(key),
        child: TextFormField(
          key: ValueKey('$botId-$key-$value'),
          initialValue: value,
          onChanged: (v) => d[key] = v,
          decoration: InputDecoration(
            labelText: label,
            isDense: true,
            border: const OutlineInputBorder(),
          ),
        ),
      ),
    );
  }

  Future<void> _reload() async {
    final data = await _api.mashaBots();
    final rows = ((data['bots'] as List?) ?? const [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    _bots = rows;
    final ids = _bots.map((b) => (b['bot_id'] ?? '').toString()).toSet();
    _draftByBot.removeWhere((id, _) => !ids.contains(id));
    _expandedBots.removeWhere((id) => !ids.contains(id));
    _logScrollByBot.removeWhere((id, c) {
      if (!ids.contains(id)) {
        c.dispose();
        return true;
      }
      return false;
    });
    for (final id in _expandedBots) {
      await _refreshLogs(id);
    }
    if (mounted) setState(() {});
  }

  Future<void> _refreshAll() async => _withBusy(_reload);

  Future<void> _refreshLogs(String botId) async {
    if (botId.isEmpty) return;
    final logs = await _api.mashaLogs(botId, limit: 120);
    final rows = (logs['logs'] as List?) ?? const [];
    if (rows.isEmpty) {
      _logsByBot[botId] = '(sin logs)';
      return;
    }
    final lines = <String>[];
    for (final r in rows) {
      final m = Map<String, dynamic>.from(r as Map);
      final ts = (m['ts_utc'] ?? '-').toString();
      final level = (m['level'] ?? '-').toString();
      final msg = (m['message'] ?? '').toString();
      final payload = m['payload'];
      final ptxt = payload == null ? '' : jsonEncode(payload);
      lines.add('$ts [$level] $msg${ptxt.isEmpty ? '' : ' | $ptxt'}');
    }
    _logsByBot[botId] = lines.join('\n');
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final c = _logScrollByBot[botId];
      if (c != null && c.hasClients) {
        c.jumpTo(c.position.maxScrollExtent);
      }
    });
  }

  Future<void> _create() async {
    await _withBusy(() async {
      await _api.mashaCreateBot({
        'tag': _tagCtrl.text.trim().isEmpty ? 'Masha' : _tagCtrl.text.trim(),
        'symbol': _symbolCtrl.text.trim().toUpperCase(),
        'base_asset': _baseCtrl.text.trim().toUpperCase(),
        'quote_asset': _quoteCtrl.text.trim().toUpperCase(),
        'loop_interval_sec': int.tryParse(_loopCtrl.text.trim()) ?? 300,
        'quote_min_free_to_operate': _minQuoteCtrl.text.trim(),
        'buy_qty_base': _buyQtyCtrl.text.trim(),
        'profit_factor': _profitCtrl.text.trim(),
        'timeframe_w': _tfWCtrl.text.trim(),
        'periods_w': int.tryParse(_periodsWCtrl.text.trim()) ?? 2,
        'mm_periods_w': int.tryParse(_mmWCtrl.text.trim()) ?? 2,
        'margin_low_w': _marginWCtrl.text.trim(),
        'timeframe_h': _tfHCtrl.text.trim(),
        'periods_h': int.tryParse(_periodsHCtrl.text.trim()) ?? 2,
        'mm_periods_h': int.tryParse(_mmHCtrl.text.trim()) ?? 2,
        'margin_low_h': _marginHCtrl.text.trim(),
        'qty_decimals': int.tryParse(_qtyDecCtrl.text.trim()) ?? 8,
        'price_decimals': int.tryParse(_priceDecCtrl.text.trim()) ?? 8,
        'note': _noteCtrl.text.trim(),
        'max_drawdown_pct': _maxDdCtrl.text.trim(),
        'stop_loss_pct': _stopLossCtrl.text.trim(),
        'metrics_interval_cycles': int.tryParse(_metricsEveryCtrl.text.trim()) ?? 5,
        'simulated': true,
        'trading_enabled': false,
      });
      await _reload();
    });
  }

  Future<void> _save(String botId) async {
    final d = _draftByBot[botId];
    if (d == null) return;
    await _withBusy(() async {
      final wasRunning = _bots.any(
        (b) => (b['bot_id'] ?? '').toString() == botId && b['running'] == true,
      );
      await _api.mashaUpdateBot(botId, {
        'tag': d['tag'],
        'symbol': (d['symbol'] ?? '').toUpperCase(),
        'base_asset': (d['base'] ?? '').toUpperCase(),
        'quote_asset': (d['quote'] ?? '').toUpperCase(),
        'loop_interval_sec': int.tryParse(d['loop'] ?? '300') ?? 300,
        'quote_min_free_to_operate': d['minQuote'] ?? '6',
        'buy_qty_base': d['buyQty'] ?? '0.001',
        'profit_factor': d['profit'] ?? '0.01',
        'timeframe_w': d['tfW'] ?? '1w',
        'periods_w': int.tryParse(d['pW'] ?? '2') ?? 2,
        'mm_periods_w': int.tryParse(d['mmW'] ?? '2') ?? 2,
        'margin_low_w': d['mW'] ?? '0.03',
        'timeframe_h': d['tfH'] ?? '1h',
        'periods_h': int.tryParse(d['pH'] ?? '2') ?? 2,
        'mm_periods_h': int.tryParse(d['mmH'] ?? '2') ?? 2,
        'margin_low_h': d['mH'] ?? '0.003',
        'qty_decimals': int.tryParse(d['qDec'] ?? '8') ?? 8,
        'price_decimals': int.tryParse(d['pDec'] ?? '8') ?? 8,
        'note': d['note'] ?? '',
        'max_drawdown_pct': d['maxDd'] ?? '0.25',
        'stop_loss_pct': d['stopLoss'] ?? '0.15',
        'metrics_interval_cycles': int.tryParse(d['metricsEvery'] ?? '5') ?? 5,
      });
      if (wasRunning) {
        await _api.mashaStopBot(botId);
        await _api.mashaStartBot(botId);
      }
      await _reload();
    });
  }

  Future<void> _toggle(String botId, bool running) async {
    await _withBusy(() async {
      if (running) {
        await _api.mashaStopBot(botId);
      } else {
        await _api.mashaStartBot(botId);
      }
      await _reload();
    });
  }

  Future<void> _runOnce(String botId) async {
    await _withBusy(() async {
      await _api.mashaRunOnce(botId);
      await _refreshLogs(botId);
      await _reload();
    });
  }

  Future<void> _delete(String botId) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirmar eliminación'),
        content: Text('Eliminar instancia Masha $botId.'),
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
    if (ok != true) return;
    await _withBusy(() async {
      await _api.mashaDeleteBot(botId);
      await _reload();
    });
  }

  Future<void> _openGuide() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const BotGuidePage(botName: 'Masha'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Masha2.0 Hub'),
        actions: [
          IconButton(
            onPressed: _loading ? null : _openGuide,
            tooltip: 'Instructivo Masha2.0',
            icon: const Icon(Icons.menu_book_outlined),
          ),
          IconButton(
            onPressed: _loading ? null : _refreshAll,
            tooltip: 'Refrescar instancias Masha',
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
                child: Text(_error, style: const TextStyle(color: Colors.redAccent)),
              ),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Nueva instancia Masha',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        _newField(_tagCtrl, 'Tag', 120, 'tag'),
                        _newField(_symbolCtrl, 'Símbolo', 120, 'symbol'),
                        _newField(_baseCtrl, 'Base', 90, 'base'),
                        _newField(_quoteCtrl, 'Quote', 90, 'quote'),
                        _newField(_loopCtrl, 'Loop s', 90, 'loop'),
                        _newField(_minQuoteCtrl, 'Min quote', 100, 'minQuote'),
                        _newField(_buyQtyCtrl, 'Buy qty', 100, 'buyQty'),
                        _newField(_profitCtrl, 'Profit', 90, 'profit'),
                        _newField(_tfWCtrl, 'TF W', 75, 'tfW'),
                        _newField(_periodsWCtrl, 'P W', 70, 'pW'),
                        _newField(_mmWCtrl, 'MM W', 70, 'mmW'),
                        _newField(_marginWCtrl, 'M W', 90, 'mW'),
                        _newField(_tfHCtrl, 'TF H', 75, 'tfH'),
                        _newField(_periodsHCtrl, 'P H', 70, 'pH'),
                        _newField(_mmHCtrl, 'MM H', 70, 'mmH'),
                        _newField(_marginHCtrl, 'M H', 90, 'mH'),
                        _newField(_qtyDecCtrl, 'QDec', 70, 'qDec'),
                        _newField(_priceDecCtrl, 'PDec', 70, 'pDec'),
                        _newField(_noteCtrl, 'Nota', 140, 'note'),
                        _newField(_maxDdCtrl, 'maxDd', 90, 'maxDd'),
                        _newField(_stopLossCtrl, 'stopLoss', 90, 'stopLoss'),
                        _newField(_metricsEveryCtrl, 'metricsEvery', 95, 'metricsEvery'),
                        FilledButton.icon(
                          onPressed: _loading ? null : _create,
                          icon: const Icon(Icons.add, size: 16),
                          label: const Text('Crear'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            if (_bots.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(12),
                  child: Text(
                    'No hay instancias Masha2.0. Crea la primera.',
                    style: TextStyle(fontSize: 12),
                  ),
                ),
              ),
            ..._bots.map((bot) {
              final botId = (bot['bot_id'] ?? '').toString();
              final running = bot['running'] == true;
              final d = _draftFor(bot);
              final logCtrl = _logScrollByBot.putIfAbsent(botId, ScrollController.new);
              return Card(
                child: ExpansionTile(
                  key: ValueKey('masha-$botId-${running ? "on" : "off"}'),
                  initiallyExpanded: _expandedBots.contains(botId),
                  onExpansionChanged: (v) async {
                    if (v) {
                      _expandedBots.add(botId);
                      await _refreshLogs(botId);
                    } else {
                      _expandedBots.remove(botId);
                    }
                    if (mounted) setState(() {});
                  },
                  title: Text(
                    '${(bot['tag'] ?? 'Masha').toString()} · $botId · ${running ? "ACTIVO" : "INACTIVO"}',
                    style: const TextStyle(fontSize: 13),
                  ),
                  subtitle: Text(
                    '${(bot['symbol'] ?? '-').toString()} | dd ${_plainNum(bot['max_drawdown_pct'])} | sl ${_plainNum(bot['stop_loss_pct'])} | m ${(bot['metrics_interval_cycles'] ?? '-')} | err: ${(bot['last_error'] ?? '-').toString()}',
                    style: const TextStyle(fontSize: 11),
                  ),
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(8),
                      child: Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [
                          _f(botId, d, 'tag', 'Tag', 120),
                          _f(botId, d, 'symbol', 'Símbolo', 120),
                          _f(botId, d, 'base', 'Base', 85),
                          _f(botId, d, 'quote', 'Quote', 85),
                          _f(botId, d, 'loop', 'Loop s', 85),
                          _f(botId, d, 'minQuote', 'Min quote', 95),
                          _f(botId, d, 'buyQty', 'Buy qty', 95),
                          _f(botId, d, 'profit', 'Profit', 85),
                          _f(botId, d, 'tfW', 'TF W', 70),
                          _f(botId, d, 'pW', 'P W', 60),
                          _f(botId, d, 'mmW', 'MM W', 70),
                          _f(botId, d, 'mW', 'M W', 80),
                          _f(botId, d, 'tfH', 'TF H', 70),
                          _f(botId, d, 'pH', 'P H', 60),
                          _f(botId, d, 'mmH', 'MM H', 70),
                          _f(botId, d, 'mH', 'M H', 80),
                          _f(botId, d, 'qDec', 'QDec', 65),
                          _f(botId, d, 'pDec', 'PDec', 65),
                          _f(botId, d, 'note', 'Nota', 130),
                          _f(botId, d, 'maxDd', 'maxDd', 80),
                          _f(botId, d, 'stopLoss', 'stopLoss', 90),
                          _f(botId, d, 'metricsEvery', 'metricsEvery', 95),
                          FilledButton.tonalIcon(
                            onPressed: _loading ? null : () => _toggle(botId, running),
                            icon: Icon(
                              running ? Icons.pause_circle : Icons.play_circle,
                              size: 16,
                            ),
                            label: Text(running ? 'Inactivar' : 'Activar'),
                          ),
                          OutlinedButton.icon(
                            onPressed: _loading ? null : () => _runOnce(botId),
                            icon: const Icon(Icons.play_arrow, size: 16),
                            label: const Text('Run once'),
                          ),
                          OutlinedButton.icon(
                            onPressed: _loading ? null : () => _save(botId),
                            icon: const Icon(Icons.save_outlined, size: 16),
                            label: const Text('Guardar y aplicar'),
                          ),
                          IconButton(
                            onPressed: _loading ? null : () => _delete(botId),
                            tooltip: 'Eliminar',
                            icon: const Icon(Icons.delete_outline),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      height: 230,
                      margin: const EdgeInsets.fromLTRB(10, 0, 10, 10),
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        border: Border.all(
                          color: Theme.of(context).colorScheme.outlineVariant,
                        ),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Scrollbar(
                        controller: logCtrl,
                        thumbVisibility: true,
                        child: SingleChildScrollView(
                          controller: logCtrl,
                          child: SelectableText(
                            _logsByBot[botId] ?? '(sin logs)',
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 11,
                            ),
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

class ThusneldaHubPage extends StatefulWidget {
  const ThusneldaHubPage({super.key, required this.engineBase});

  final String engineBase;

  @override
  State<ThusneldaHubPage> createState() => _ThusneldaHubPageState();
}

class _ThusneldaHubPageState extends State<ThusneldaHubPage> {
  final _tagCtrl = TextEditingController(text: 'Thusnelda');
  final _symbolsCtrl = TextEditingController(text: 'BTCUSDT,ETHUSDT');
  final _loopCtrl = TextEditingController(text: '600');
  final _betweenCtrl = TextEditingController(text: '3');
  final _quoteQtyCtrl = TextEditingController(text: '8');
  final _factorCtrl = TextEditingController(text: '0.99');
  final _metaCtrl = TextEditingController(text: '1000000');
  final _refTsCtrl = TextEditingController();
  final _qtyDecCtrl = TextEditingController(text: '8');
  final _noteCtrl = TextEditingController();
  final _maxDdCtrl = TextEditingController(text: '0.25');
  final _stopLossCtrl = TextEditingController(text: '0.20');
  final _metricsEveryCtrl = TextEditingController(text: '3');

  bool _loading = false;
  String _error = '-';
  List<Map<String, dynamic>> _bots = <Map<String, dynamic>>[];
  final Map<String, Map<String, String>> _draftByBot = <String, Map<String, String>>{};
  final Map<String, String> _logsByBot = <String, String>{};
  final Set<String> _expandedBots = <String>{};
  final Map<String, ScrollController> _logScrollByBot = <String, ScrollController>{};
  Timer? _refreshTimer;

  EngineApi get _api => EngineApi(widget.engineBase);

  @override
  void initState() {
    super.initState();
    _refreshAll();
    _refreshTimer = Timer.periodic(const Duration(seconds: 4), (_) {
      if (mounted && !_loading) {
        _reload();
      }
    });
  }

  @override
  void dispose() {
    _tagCtrl.dispose();
    _symbolsCtrl.dispose();
    _loopCtrl.dispose();
    _betweenCtrl.dispose();
    _quoteQtyCtrl.dispose();
    _factorCtrl.dispose();
    _metaCtrl.dispose();
    _refTsCtrl.dispose();
    _qtyDecCtrl.dispose();
    _noteCtrl.dispose();
    _maxDdCtrl.dispose();
    _stopLossCtrl.dispose();
    _metricsEveryCtrl.dispose();
    for (final c in _logScrollByBot.values) {
      c.dispose();
    }
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _withBusy(Future<void> Function() fn) async {
    if (_loading) return;
    setState(() => _loading = true);
    try {
      await fn();
      _error = '-';
    } catch (e) {
      _error = e.toString();
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(_error)));
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Map<String, String> _draftFor(Map<String, dynamic> bot) {
    final botId = (bot['bot_id'] ?? '').toString();
    final d = _draftByBot.putIfAbsent(botId, () {
      return <String, String>{
        'tag': (bot['tag'] ?? 'Thusnelda').toString(),
        'symbols': (bot['symbols_csv'] ?? 'BTCUSDT,ETHUSDT').toString(),
        'loop': (bot['loop_interval_sec'] ?? 600).toString(),
        'between': (bot['between_symbol_sec'] ?? 3).toString(),
        'quoteQty': (bot['quote_order_qty_modulo'] ?? '8').toString(),
        'factor': (bot['factor_multiplication'] ?? '0.99').toString(),
        'meta': (bot['meta_equity_usdt'] ?? '1000000').toString(),
        'refTs': (bot['reference_ts_iso'] ?? '').toString(),
        'qDec': (bot['qty_decimals'] ?? 8).toString(),
        'note': (bot['note'] ?? '').toString(),
        'maxDd': (bot['max_drawdown_pct'] ?? '0.25').toString(),
        'stopLoss': (bot['stop_loss_pct'] ?? '0.20').toString(),
        'metricsEvery': (bot['metrics_interval_cycles'] ?? 3).toString(),
        'simulated': ((bot['simulated'] ?? true) == true).toString(),
        'trading_enabled': ((bot['trading_enabled'] ?? false) == true).toString(),
      };
    });
    return d;
  }

  String _settingTooltip(String key) {
    switch (key) {
      case 'tag':
        return 'Nombre local de la instancia Thusnelda.';
      case 'symbols':
      case 'symbolsCsv':
        return 'Lista CSV de símbolos spot a recorrer en el ciclo (ej. BTCUSDT,ETHUSDT).';
      case 'loop':
        return 'Segundos entre ciclos completos de la cesta.';
      case 'between':
        return 'Pausa entre símbolos dentro de un mismo ciclo.';
      case 'quoteQty':
        return 'Módulo de quote por compra parcial en cada símbolo.';
      case 'factor':
        return 'Factor multiplicador para ajustar gatillo de entrada por promedio.';
      case 'meta':
        return 'Meta de equity global en base asset para condición de salida estratégica.';
      case 'refTs':
        return 'Timestamp ISO de referencia histórica (opcional).';
      case 'qDec':
        return 'Decimales de cantidad para cumplir filtros de lote.';
      case 'note':
        return 'Nota operativa corta para recordar propósito de la instancia.';
      case 'maxDd':
        return 'Drawdown máximo permitido antes de bloquear nuevas entradas.';
      case 'stopLoss':
        return 'Stop-loss por símbolo para defensa cuando el precio se deteriora.';
      case 'metricsEvery':
        return 'Frecuencia de métricas y snapshots de rendimiento en ciclos.';
      default:
        return key;
    }
  }

  Widget _newField(
    TextEditingController controller,
    String label,
    double width,
    String key,
  ) {
    return SizedBox(
      width: width,
      child: Tooltip(
        message: _settingTooltip(key),
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

  Widget _f(
    String botId,
    Map<String, String> d,
    String key,
    String label,
    double width,
  ) {
    final value = d[key] ?? '';
    return SizedBox(
      width: width,
      child: Tooltip(
        message: _settingTooltip(key),
        child: TextFormField(
          key: ValueKey('$botId-$key-$value'),
          initialValue: value,
          onChanged: (v) => d[key] = v,
          decoration: InputDecoration(
            labelText: label,
            isDense: true,
            border: const OutlineInputBorder(),
          ),
        ),
      ),
    );
  }

  Future<void> _reload() async {
    final data = await _api.thusneldaBots();
    final rows = ((data['bots'] as List?) ?? const [])
        .map((e) => Map<String, dynamic>.from(e as Map))
        .toList();
    _bots = rows;
    final ids = _bots.map((b) => (b['bot_id'] ?? '').toString()).toSet();
    _draftByBot.removeWhere((id, _) => !ids.contains(id));
    _expandedBots.removeWhere((id) => !ids.contains(id));
    _logScrollByBot.removeWhere((id, c) {
      if (!ids.contains(id)) {
        c.dispose();
        return true;
      }
      return false;
    });
    for (final id in _expandedBots) {
      await _refreshLogs(id);
    }
    if (mounted) setState(() {});
  }

  Future<void> _refreshAll() async => _withBusy(_reload);

  Future<void> _refreshLogs(String botId) async {
    if (botId.isEmpty) return;
    final logs = await _api.thusneldaLogs(botId, limit: 120);
    final rows = (logs['logs'] as List?) ?? const [];
    if (rows.isEmpty) {
      _logsByBot[botId] = '(sin logs)';
      return;
    }
    final lines = <String>[];
    for (final r in rows) {
      final m = Map<String, dynamic>.from(r as Map);
      final ts = (m['ts_utc'] ?? '-').toString();
      final level = (m['level'] ?? '-').toString();
      final msg = (m['message'] ?? '').toString();
      final payload = m['payload'];
      final ptxt = payload == null ? '' : jsonEncode(payload);
      lines.add('$ts [$level] $msg${ptxt.isEmpty ? '' : ' | $ptxt'}');
    }
    _logsByBot[botId] = lines.join('\n');
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final c = _logScrollByBot[botId];
      if (c != null && c.hasClients) {
        c.jumpTo(c.position.maxScrollExtent);
      }
    });
  }

  Future<void> _create() async {
    await _withBusy(() async {
      await _api.thusneldaCreateBot({
        'tag': _tagCtrl.text.trim().isEmpty ? 'Thusnelda' : _tagCtrl.text.trim(),
        'symbols_csv': _symbolsCtrl.text.trim().toUpperCase(),
        'loop_interval_sec': int.tryParse(_loopCtrl.text.trim()) ?? 600,
        'between_symbol_sec': int.tryParse(_betweenCtrl.text.trim()) ?? 3,
        'quote_order_qty_modulo': _quoteQtyCtrl.text.trim(),
        'factor_multiplication': _factorCtrl.text.trim(),
        'meta_equity_usdt': _metaCtrl.text.trim(),
        'reference_ts_iso': _refTsCtrl.text.trim(),
        'qty_decimals': int.tryParse(_qtyDecCtrl.text.trim()) ?? 8,
        'note': _noteCtrl.text.trim(),
        'max_drawdown_pct': _maxDdCtrl.text.trim(),
        'stop_loss_pct': _stopLossCtrl.text.trim(),
        'metrics_interval_cycles': int.tryParse(_metricsEveryCtrl.text.trim()) ?? 3,
        'simulated': true,
        'trading_enabled': false,
      });
      await _reload();
    });
  }

  Future<void> _save(String botId) async {
    final d = _draftByBot[botId];
    if (d == null) return;
    await _withBusy(() async {
      final wasRunning = _bots.any(
        (b) => (b['bot_id'] ?? '').toString() == botId && b['running'] == true,
      );
      await _api.thusneldaUpdateBot(botId, {
        'tag': d['tag'],
        'symbols_csv': (d['symbols'] ?? '').toUpperCase(),
        'loop_interval_sec': int.tryParse(d['loop'] ?? '600') ?? 600,
        'between_symbol_sec': int.tryParse(d['between'] ?? '3') ?? 3,
        'quote_order_qty_modulo': d['quoteQty'] ?? '8',
        'factor_multiplication': d['factor'] ?? '0.99',
        'meta_equity_usdt': d['meta'] ?? '1000000',
        'reference_ts_iso': d['refTs'] ?? '',
        'qty_decimals': int.tryParse(d['qDec'] ?? '8') ?? 8,
        'note': d['note'] ?? '',
        'max_drawdown_pct': d['maxDd'] ?? '0.25',
        'stop_loss_pct': d['stopLoss'] ?? '0.20',
        'metrics_interval_cycles': int.tryParse(d['metricsEvery'] ?? '3') ?? 3,
      });
      if (wasRunning) {
        await _api.thusneldaStopBot(botId);
        await _api.thusneldaStartBot(botId);
      }
      await _reload();
    });
  }

  Future<void> _toggle(String botId, bool running) async {
    await _withBusy(() async {
      if (running) {
        await _api.thusneldaStopBot(botId);
      } else {
        await _api.thusneldaStartBot(botId);
      }
      await _reload();
    });
  }

  Future<void> _runOnce(String botId) async {
    await _withBusy(() async {
      await _api.thusneldaRunOnce(botId);
      await _refreshLogs(botId);
      await _reload();
    });
  }

  Future<void> _delete(String botId) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Confirmar eliminación'),
        content: Text('Eliminar instancia Thusnelda $botId.'),
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
    if (ok != true) return;
    await _withBusy(() async {
      await _api.thusneldaDeleteBot(botId);
      await _reload();
    });
  }

  Future<void> _openGuide() async {
    await Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => const BotGuidePage(botName: 'Thusnelda'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Thusnelda1.0 Hub'),
        actions: [
          IconButton(
            onPressed: _loading ? null : _openGuide,
            tooltip: 'Instructivo Thusnelda1.0',
            icon: const Icon(Icons.menu_book_outlined),
          ),
          IconButton(
            onPressed: _loading ? null : _refreshAll,
            tooltip: 'Refrescar instancias Thusnelda',
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
                child: Text(_error, style: const TextStyle(color: Colors.redAccent)),
              ),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Nueva instancia Thusnelda',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 6,
                      children: [
                        _newField(_tagCtrl, 'Tag', 130, 'tag'),
                        _newField(_symbolsCtrl, 'Símbolos CSV', 220, 'symbols'),
                        _newField(_loopCtrl, 'Loop s', 90, 'loop'),
                        _newField(_betweenCtrl, 'Entre sym s', 90, 'between'),
                        _newField(_quoteQtyCtrl, 'Quote qty', 105, 'quoteQty'),
                        _newField(_factorCtrl, 'Factor', 90, 'factor'),
                        _newField(_metaCtrl, 'Meta USDT', 110, 'meta'),
                        _newField(_refTsCtrl, 'Referencia ISO (opc)', 180, 'refTs'),
                        _newField(_qtyDecCtrl, 'QDec', 75, 'qDec'),
                        _newField(_noteCtrl, 'Nota', 150, 'note'),
                        _newField(_maxDdCtrl, 'maxDd', 90, 'maxDd'),
                        _newField(_stopLossCtrl, 'stopLoss', 90, 'stopLoss'),
                        _newField(_metricsEveryCtrl, 'metricsEvery', 95, 'metricsEvery'),
                        FilledButton.icon(
                          onPressed: _loading ? null : _create,
                          icon: const Icon(Icons.add, size: 16),
                          label: const Text('Crear'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 8),
            if (_bots.isEmpty)
              const Card(
                child: Padding(
                  padding: EdgeInsets.all(12),
                  child: Text(
                    'No hay instancias Thusnelda1.0. Crea la primera.',
                    style: TextStyle(fontSize: 12),
                  ),
                ),
              ),
            ..._bots.map((bot) {
              final botId = (bot['bot_id'] ?? '').toString();
              final running = bot['running'] == true;
              final d = _draftFor(bot);
              final logCtrl = _logScrollByBot.putIfAbsent(botId, ScrollController.new);
              return Card(
                child: ExpansionTile(
                  key: ValueKey('thusnelda-$botId-${running ? "on" : "off"}'),
                  initiallyExpanded: _expandedBots.contains(botId),
                  onExpansionChanged: (v) async {
                    if (v) {
                      _expandedBots.add(botId);
                      await _refreshLogs(botId);
                    } else {
                      _expandedBots.remove(botId);
                    }
                    if (mounted) setState(() {});
                  },
                  title: Text(
                    '${(bot['tag'] ?? 'Thusnelda').toString()} · $botId · ${running ? "ACTIVO" : "INACTIVO"}',
                    style: const TextStyle(fontSize: 13),
                  ),
                  subtitle: Text(
                    '${(bot['symbols_csv'] ?? '-').toString()} | dd ${_plainNum(bot['max_drawdown_pct'])} | sl ${_plainNum(bot['stop_loss_pct'])} | m ${(bot['metrics_interval_cycles'] ?? '-')} | err: ${(bot['last_error'] ?? '-').toString()}',
                    style: const TextStyle(fontSize: 11),
                  ),
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(8),
                      child: Wrap(
                        spacing: 6,
                        runSpacing: 6,
                        children: [
                          _f(botId, d, 'tag', 'Tag', 120),
                          _f(botId, d, 'symbols', 'Símbolos CSV', 210),
                          _f(botId, d, 'loop', 'Loop s', 85),
                          _f(botId, d, 'between', 'Entre sym s', 95),
                          _f(botId, d, 'quoteQty', 'Quote qty', 95),
                          _f(botId, d, 'factor', 'Factor', 85),
                          _f(botId, d, 'meta', 'Meta USDT', 110),
                          _f(botId, d, 'refTs', 'Referencia ISO', 180),
                          _f(botId, d, 'qDec', 'QDec', 65),
                          _f(botId, d, 'note', 'Nota', 130),
                          _f(botId, d, 'maxDd', 'maxDd', 80),
                          _f(botId, d, 'stopLoss', 'stopLoss', 90),
                          _f(botId, d, 'metricsEvery', 'metricsEvery', 95),
                          FilledButton.tonalIcon(
                            onPressed: _loading ? null : () => _toggle(botId, running),
                            icon: Icon(
                              running ? Icons.pause_circle : Icons.play_circle,
                              size: 16,
                            ),
                            label: Text(running ? 'Inactivar' : 'Activar'),
                          ),
                          OutlinedButton.icon(
                            onPressed: _loading ? null : () => _runOnce(botId),
                            icon: const Icon(Icons.play_arrow, size: 16),
                            label: const Text('Run once'),
                          ),
                          OutlinedButton.icon(
                            onPressed: _loading ? null : () => _save(botId),
                            icon: const Icon(Icons.save_outlined, size: 16),
                            label: const Text('Guardar y aplicar'),
                          ),
                          IconButton(
                            onPressed: _loading ? null : () => _delete(botId),
                            tooltip: 'Eliminar',
                            icon: const Icon(Icons.delete_outline),
                          ),
                        ],
                      ),
                    ),
                    Container(
                      height: 230,
                      margin: const EdgeInsets.fromLTRB(10, 0, 10, 10),
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        border: Border.all(
                          color: Theme.of(context).colorScheme.outlineVariant,
                        ),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: Scrollbar(
                        controller: logCtrl,
                        thumbVisibility: true,
                        child: SingleChildScrollView(
                          controller: logCtrl,
                          child: SelectableText(
                            _logsByBot[botId] ?? '(sin logs)',
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 11,
                            ),
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

class BotGuidePage extends StatelessWidget {
  const BotGuidePage({super.key, required this.botName});

  final String botName;

  static const Map<String, String> _titles = {
    'Dorothy': 'Manual operativo Dorothy7.0',
    'Masha': 'Manual operativo Masha2.0',
    'Thusnelda': 'Manual operativo Thusnelda1.0',
  };

  static const Map<String, String> _intro = {
    'Dorothy':
        'Bot de ciclo perpetuo para un simbolo. Toma referencia de orden SELL ancla '
            'y compra cuando el mercado cae bajo el umbral configurado.',
    'Masha':
        'Bot DCA multi-timeframe. Evalua señal tecnica para comprar, recalcula precio '
            'promedio y consolida salida con una SELL LIMIT.',
    'Thusnelda':
        'Bot multi-simbolo por cesta. Recorre simbolos, compra por regla de promedio '
            'historico y vigila meta de equity global.',
  };

  static const Map<String, List<String>> _sections = {
    'Dorothy': [
      'Flujo principal: evalúa open orders + ticker y decide compra/espera/gestión de salida.',
      'Activación: botón ACTIVO/INACTIVO gobierna ciclo perpetuo por instancia.',
      'Guardar y aplicar: aplica cambios al instante y reinicia si estaba activo.',
      'Objetivo: recomponer posición y retornar quote/base con beneficio por spread.',
      'Control de riesgo: maxDd bloquea nuevas compras; stopLoss permite salida defensiva.',
      'Observabilidad: usar logs crudos Binance para validar filtros, cantidades y decisiones.',
    ],
    'Masha': [
      'Flujo principal: estrategia DCA con señal técnica multi-timeframe (W + H).',
      'Compra: requiere condiciones de señal y disponibilidad mínima de quote.',
      'Salida: mantiene una SELL LIMIT consolidada recalculada con cada compra.',
      'Riesgo: maxDd limita nuevas entradas; stopLoss corta deterioro extremo.',
      'Métricas: sharpe, win rate y drawdown persistidos cada metricsEvery ciclos.',
      'Observabilidad: comparar señal, precio DCA, orden de salida y logs Binance.',
    ],
    'Thusnelda': [
      'Flujo principal: recorre una cesta de símbolos en cada ciclo.',
      'Compra: compara precio actual con referencia/promedio histórico por símbolo.',
      'Salida: vigila meta de equity global y estado de cada activo de la cesta.',
      'Riesgo: maxDd bloquea entradas adicionales; stopLoss protege símbolo a símbolo.',
      'Operación: ajustar entre_symbol_sec para balancear latencia vs carga REST.',
      'Observabilidad: revisar eventos de equity, decisiones por símbolo y métricas.',
    ],
  };

  static const Map<String, List<String>> _parameterGuide = {
    'Dorothy': [
      'symbol: par spot a operar; debe existir y tener liquidez.',
      'loop sec: define frecuencia de reacción y consumo API.',
      'qty/profit/drop: núcleo de rentabilidad y ritmo de entradas.',
      'qDec/pDec: imprescindibles para cumplir filtros Binance.',
      'maxDd/stopLoss: contención de pérdidas acumuladas y por posición.',
      'metricsEvery: costo/beneficio entre detalle histórico y carga.',
    ],
    'Masha': [
      'base/quote/symbol: coherencia obligatoria para evitar errores de mercado.',
      'min quote + buy qty: controlan cuándo y cuánto compra.',
      'TF/periods/mm/margins: sensibilidad de señal técnica.',
      'profit: objetivo de salida de la orden consolidada.',
      'maxDd/stopLoss: protección macro y micro del ciclo DCA.',
      'qDec/pDec: adaptar al instrumento para evitar rechazos.',
    ],
    'Thusnelda': [
      'symbols CSV: universo de activos a escanear por ciclo.',
      'loop + entre sym: velocidad total de barrido y carga REST.',
      'quote qty + factor: tamaño y agresividad de cada entrada.',
      'meta equity: umbral objetivo de rendimiento agregado.',
      'maxDd/stopLoss: freno global y defensa por símbolo.',
      'refTs/qDec: soporte de referencia histórica y cumplimiento de filtros.',
    ],
  };

  static const Map<String, List<String>> _troubleshooting = {
    'Dorothy': [
      'No compra: validar drop/profit, saldo quote y estado de órdenes ancla.',
      'Errores de filtro: ajustar qDec/pDec al tick size y lot size.',
      'Mucho peso REST: subir loop o revisar monitor de peso por acciones.',
    ],
    'Masha': [
      'No dispara señal: revisar timeframe, periods y márgenes W/H.',
      'No coloca salida: validar pDec/profit y restricciones del símbolo.',
      'DCA agresivo: ajustar buy qty y maxDd para menor exposición.',
    ],
    'Thusnelda': [
      'Cesta lenta: reducir símbolos o aumentar entre_symbol_sec.',
      'Sin entradas: revisar factor, referencia y liquidez real de símbolos.',
      'Riesgo alto: endurecer maxDd/stopLoss y validar meta de equity.',
    ],
  };

  static const List<String> _quickStart = [
    '1) Crear instancia desde su Hub.',
    '2) Confirmar simbolo(s), base asset y quote qty.',
    '3) Presionar Activar para iniciar ciclo perpetuo.',
    '4) Observar logs crudos y ajustes de riesgo.',
    '5) Guardar y aplicar cuando cambies parametros.',
  ];

  @override
  Widget build(BuildContext context) {
    final title = _titles[botName] ?? 'Guia de bot';
    final intro = _intro[botName] ?? '-';
    final bullets = _sections[botName] ?? const <String>[];
    final params = _parameterGuide[botName] ?? const <String>[];
    final troubleshoot = _troubleshooting[botName] ?? const <String>[];
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(intro),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Guía de parámetros',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    ...params.map(
                      (text) => Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text('- $text'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Como operarlo',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    ...bullets.map(
                      (text) => Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text('- $text'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Inicio rapido',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    ..._quickStart.map(
                      (step) => Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text(step),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Troubleshooting rápido',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    ...troubleshoot.map(
                      (text) => Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text('- $text'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class ApiSandboxPage extends StatefulWidget {
  const ApiSandboxPage({super.key, required this.engineBase});

  final String engineBase;

  @override
  State<ApiSandboxPage> createState() => _ApiSandboxPageState();
}

class _ApiSandboxPageState extends State<ApiSandboxPage> {
  final _callCtrl = TextEditingController(text: 'client.get_exchange_info()');
  final _symbolCtrl = TextEditingController(text: 'BTCUSDT');
  final _limitCtrl = TextEditingController(text: '50');
  String _selectedQueryId = 'exchange_info';
  bool _loading = false;
  String _error = '-';
  String _lastExecutedAt = '-';
  List<Map<String, dynamic>> _catalog = <Map<String, dynamic>>[];
  dynamic _response = <String, dynamic>{};
  Map<String, dynamic> _curated = <String, dynamic>{};
  List<Map<String, dynamic>> _savedRows = <Map<String, dynamic>>[];

  EngineApi get _api => EngineApi(widget.engineBase);

  @override
  void initState() {
    super.initState();
    _init();
  }

  @override
  void dispose() {
    _callCtrl.dispose();
    _symbolCtrl.dispose();
    _limitCtrl.dispose();
    super.dispose();
  }

  Future<void> _init() async {
    await _loadCatalog();
    await _execute();
    await _loadSaved();
  }

  Future<void> _loadCatalog() async {
    try {
      final data = await _api.sandboxRestCatalog();
      final list = ((data['items'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      if (!mounted) return;
      setState(() {
        _catalog = list;
        if (_catalog.isNotEmpty &&
            !_catalog.any((r) => (r['query_id'] ?? '') == _selectedQueryId)) {
          _selectedQueryId = (_catalog.first['query_id'] ?? 'exchange_info')
              .toString();
        }
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _error = e.toString());
    }
  }

  String _pretty(dynamic value) {
    try {
      return const JsonEncoder.withIndent('  ').convert(value);
    } catch (_) {
      return value.toString();
    }
  }

  Map<String, dynamic>? _selectedMeta() {
    for (final row in _catalog) {
      if ((row['query_id'] ?? '').toString() == _selectedQueryId) {
        return row;
      }
    }
    return null;
  }

  bool _queryNeedsSymbol() {
    return _selectedQueryId == 'orderbook_ticker' ||
        _selectedQueryId == 'my_trades' ||
        _selectedQueryId == 'exchange_info' ||
        _selectedQueryId == 'open_orders';
  }

  bool _queryNeedsLimit() {
    return _selectedQueryId == 'my_trades';
  }

  Future<void> _execute() async {
    if (_loading) return;
    final callExpr = _callCtrl.text.trim();
    final symbol = _symbolCtrl.text.trim().toUpperCase();
    final limitText = _limitCtrl.text.trim();
    final limit = int.tryParse(limitText);
    if (callExpr.isEmpty &&
        _queryNeedsSymbol() &&
        _selectedQueryId != 'exchange_info' &&
        symbol.isEmpty) {
      setState(() => _error = 'Símbolo requerido para esta consulta.');
      return;
    }
    if (_queryNeedsLimit() && (limit == null || limit <= 0)) {
      setState(() => _error = 'Límite inválido (ej. 50).');
      return;
    }
    setState(() {
      _loading = true;
      _error = '-';
    });
    try {
      final res = await _api.sandboxRestQuery(
        queryId: callExpr.isEmpty ? _selectedQueryId : null,
        callExpression: callExpr.isEmpty ? null : callExpr,
        symbol: symbol,
        limit: limit ?? 50,
      );
      final response = res['response'];
      final curated = Map<String, dynamic>.from(
        (res['curated'] as Map?) ?? const {},
      );
      if (!mounted) return;
      setState(() {
        final qid = (res['query_id'] ?? '').toString();
        if (qid.isNotEmpty) _selectedQueryId = qid;
        _response = response;
        _curated = curated;
        _lastExecutedAt = (res['ts_utc'] ?? DateTime.now().toLocal().toString())
            .toString();
      });
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Future<void> _saveCurated() async {
    final hasResponse = (_response is Map && (_response as Map).isNotEmpty) ||
        (_response is List && (_response as List).isNotEmpty) ||
        (_response != null &&
            _response is! Map &&
            _response is! List &&
            _response.toString().isNotEmpty);
    if (!hasResponse) {
      setState(() => _error = 'No hay respuesta para guardar todavía.');
      return;
    }
    try {
      final symbol = _symbolCtrl.text.trim().toUpperCase();
      final limit = int.tryParse(_limitCtrl.text.trim());
      await _api.saveSandboxCurated(<String, dynamic>{
        'method': 'POST',
        'endpoint': '/api/v1/sandbox/rest/query',
        'request': {
          'query_id': _selectedQueryId,
          if (_callCtrl.text.trim().isNotEmpty) 'call': _callCtrl.text.trim(),
          if (symbol.isNotEmpty) 'symbol': symbol,
          if (limit != null && limit > 0) 'limit': limit,
        },
        'response': _response,
        'curated': _curated,
      });
      await _loadSaved();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Snapshot curado guardado en SQLite.')),
      );
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  Future<void> _loadSaved() async {
    try {
      final rows = await _api.listSandboxCurated(limit: 40);
      final list = ((rows['items'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      if (!mounted) return;
      setState(() {
        _savedRows = list;
      });
    } catch (_) {
      // Keep silent; user can still execute live probes.
    }
  }

  void _openSavedDetail(Map<String, dynamic> row) {
    showDialog<void>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(
          '${row['method'] ?? '-'} ${row['endpoint'] ?? '-'} · #${row['id'] ?? '-'}',
        ),
        content: SizedBox(
          width: 950,
          child: SingleChildScrollView(
            child: SelectableText(
              _pretty(<String, dynamic>{
                'ts_utc': row['ts_utc'],
                'request': row['request'],
                'curated': row['curated'],
                'response': row['response'],
              }),
              style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
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

  List<Map<String, String>> _summaryRows() {
    final out = <Map<String, String>>[];
    String preview(dynamic v) {
      final t = v == null ? 'null' : v.toString();
      return t.length <= 120 ? t : '${t.substring(0, 117)}...';
    }

    if (_response is Map) {
      final m = Map<String, dynamic>.from(_response as Map);
      var i = 0;
      for (final e in m.entries) {
        if (i++ >= 60) break;
        out.add({
          'key': e.key.toString(),
          'type': e.value.runtimeType.toString(),
          'value': preview(e.value),
        });
      }
      return out;
    }
    if (_response is List) {
      final lst = (_response as List);
      out.add({'key': 'list_size', 'type': 'int', 'value': lst.length.toString()});
      if (lst.isNotEmpty && lst.first is Map) {
        final first = Map<String, dynamic>.from(lst.first as Map);
        var i = 0;
        for (final e in first.entries) {
          if (i++ >= 40) break;
          out.add({
            'key': 'item0.${e.key}',
            'type': e.value.runtimeType.toString(),
            'value': preview(e.value),
          });
        }
      } else if (lst.isNotEmpty) {
        out.add({
          'key': 'item0',
          'type': lst.first.runtimeType.toString(),
          'value': preview(lst.first),
        });
      }
      return out;
    }
    out.add({
      'key': 'value',
      'type': _response.runtimeType.toString(),
      'value': preview(_response),
    });
    return out;
  }

  Widget _summaryTableCard() {
    final rows = _summaryRows();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Resumen tabular clave/valor',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            if (rows.isEmpty)
              const Text('(sin datos)', style: TextStyle(fontSize: 12))
            else
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: DataTable(
                  columns: const [
                    DataColumn(label: Text('Clave')),
                    DataColumn(label: Text('Tipo')),
                    DataColumn(label: Text('Valor (preview)')),
                  ],
                  rows: rows
                      .map(
                        (r) => DataRow(
                          cells: [
                            DataCell(
                              SizedBox(
                                width: 220,
                                child: SelectableText(
                                  r['key'] ?? '-',
                                  style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                                ),
                              ),
                            ),
                            DataCell(Text(r['type'] ?? '-')),
                            DataCell(
                              SizedBox(
                                width: 520,
                                child: SelectableText(
                                  r['value'] ?? '-',
                                  style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
                                ),
                              ),
                            ),
                          ],
                        ),
                      )
                      .toList(),
                ),
              ),
          ],
        ),
      ),
    );
  }

  Widget _curatedCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Curado rápido de respuesta',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 8),
            SelectableText(
              _pretty(_curated),
              style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
            ),
          ],
        ),
      ),
    );
  }

  Widget _savedCard() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'SQLite snapshots curados',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            if (_savedRows.isEmpty)
              const Text('(sin registros)', style: TextStyle(fontSize: 12))
            else
              SizedBox(
                height: 240,
                child: ListView.separated(
                  itemCount: _savedRows.length,
                  separatorBuilder: (_, separatorIndex) =>
                      const Divider(height: 8),
                  itemBuilder: (ctx, i) {
                    final row = _savedRows[i];
                    return Row(
                      children: [
                        Expanded(
                          child: SelectableText(
                            '#${row['id']} · ${row['ts_utc']} · ${row['method']} ${row['endpoint']}',
                            style: const TextStyle(
                              fontFamily: 'monospace',
                              fontSize: 11,
                            ),
                          ),
                        ),
                        OutlinedButton(
                          onPressed: () => _openSavedDetail(row),
                          child: const Text('Detalle'),
                        ),
                      ],
                    );
                  },
                ),
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final selectedMeta = _selectedMeta();
    final description = (selectedMeta?['description'] ?? '-').toString();
    final requiresCred = selectedMeta?['requires_credentials'] == true;
    final args = (selectedMeta?['args'] as List?) ?? const [];
    return Scaffold(
      appBar: AppBar(
        title: const Text('Sandbox REST Binance'),
        actions: [
          IconButton(
            onPressed: _loading ? null : _execute,
            tooltip: 'Ejecutar endpoint',
            icon: const Icon(Icons.play_arrow),
          ),
          IconButton(
            onPressed: _loading ? null : _loadSaved,
            tooltip: 'Cargar snapshots guardados',
            icon: const Icon(Icons.history),
          ),
          IconButton(
            onPressed: _loading ? null : _saveCurated,
            tooltip: 'Guardar curado en SQLite',
            icon: const Icon(Icons.save_outlined),
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
            Text(
              'Última ejecución UTC: $_lastExecutedAt',
              style: TextStyle(
                fontSize: 12,
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: DropdownButtonFormField<String>(
                    initialValue: _selectedQueryId,
                    decoration: const InputDecoration(
                      labelText: 'Consulta REST',
                      isDense: true,
                      border: OutlineInputBorder(),
                    ),
                    items: _catalog
                        .map(
                          (m) => DropdownMenuItem<String>(
                            value: (m['query_id'] ?? '').toString(),
                            child: Text(
                              '${m['title'] ?? m['query_id']}',
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                        )
                        .toList(),
                    onChanged: _loading
                        ? null
                        : (v) {
                            if (v == null || v.isEmpty) return;
                            setState(() => _selectedQueryId = v);
                          },
                  ),
                ),
                const SizedBox(width: 8),
                FilledButton.icon(
                  onPressed: _loading ? null : _execute,
                  icon: const Icon(Icons.play_arrow, size: 16),
                  label: const Text('Consultar'),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: _loading ? null : _saveCurated,
                  icon: const Icon(Icons.save_alt_outlined, size: 16),
                  label: const Text('Guardar curado'),
                ),
              ],
            ),
            const SizedBox(height: 8),
            TextField(
              controller: _callCtrl,
              decoration: const InputDecoration(
                labelText: 'Solicitud estilo python-binance',
                hintText: 'client.get_exchange_info() / client.get_my_trades(symbol="BTCUSDT", limit=50)',
                isDense: true,
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 8),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      description,
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 12,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      'Usa credenciales registradas: ${requiresCred ? "sí" : "no"}',
                      style: TextStyle(
                        fontSize: 12,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    if (args.isNotEmpty)
                      Text(
                        'Parámetros: ${args.join(", ")}',
                        style: TextStyle(
                          fontSize: 12,
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                      ),
                    const SizedBox(height: 4),
                    Text(
                      'Tip: puedes usar el catálogo o escribir la llamada tipo python-binance arriba; se ejecuta por backend y devuelve JSON.',
                      style: TextStyle(
                        fontSize: 12,
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        SizedBox(
                          width: 160,
                          child: TextField(
                            controller: _symbolCtrl,
                            textCapitalization: TextCapitalization.characters,
                            decoration: const InputDecoration(
                              labelText: 'Símbolo',
                              hintText: 'BTCUSDT',
                              isDense: true,
                              border: OutlineInputBorder(),
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        SizedBox(
                          width: 120,
                          child: TextField(
                            controller: _limitCtrl,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                              labelText: 'Límite',
                              hintText: '50',
                              isDense: true,
                              border: OutlineInputBorder(),
                            ),
                          ),
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            'Objetivo operativo: maximizar beneficio y reducir pérdida (inevitable en ocasiones) con datos verificables.',
                            style: const TextStyle(fontSize: 12),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            _summaryTableCard(),
            const SizedBox(height: 10),
            _curatedCard(),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Respuesta cruda',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 8),
                    SelectableText(
                      _pretty(_response),
                      style: const TextStyle(
                        fontFamily: 'monospace',
                        fontSize: 11,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            _savedCard(),
          ],
        ),
      ),
    );
  }
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
      if (mounted) setState(() => _error = 'Base asset requerido (ej. USDT)');
      return;
    }
    _baseAssetCtrl.text = base;
    if (mounted) {
      setState(() {
        _loading = true;
        _error = '-';
      });
    }
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
      if (mounted) {
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
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
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
    final base =
        (_equity['base_asset'] ?? _baseAssetCtrl.text.trim().toUpperCase())
            .toString();
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
