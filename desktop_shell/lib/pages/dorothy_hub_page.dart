import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../api_client.dart';
import '../services/history_scraper.dart';
import '../widgets/market_monitor.dart';
import '../widgets/library_manager.dart';
import '../widgets/earn_manager.dart';
import '../widgets/carry_trade.dart';
import '../widgets/compact_weight_gauge.dart';
import 'masha_hub_page.dart';
import 'thusnelda_hub_page.dart';
import 'bot_guide_page.dart';
import 'spot_account_page.dart';
import '../widgets/weight_monitor_dialog.dart';
import '../widgets/vmo_dashboard.dart';
import '../utils.dart';
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
  static const _engineBase = 'http://127.0.0.1:8000';

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

  bool _loadingHub = false;
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
  int _currentIndex = 0;

  EngineApi get _api => EngineApi(_engineBase);

  @override
  void initState() {
    super.initState();
    _tickBinanceClock();
    _refreshAll();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // NOTE: _syncTimestamp() removed from autostart â€” consumes API weight.
      // User can manually sync via the clock button when needed.
    });
    _refreshTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _backgroundRefresh();
    });
    _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) {
        setState(_tickBinanceClock);
      }
    });
    HistoryScraperService.instance.api = _api;
    // NOTE: HistoryScraperService.start() disabled â€” it uses REST API
    // (banned). Historical data now ingested via VisionScraper (ZIPs).
    // HistoryScraperService.instance.start();
  }

  @override
  void dispose() {
    HistoryScraperService.instance.stop();
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
    if (_loadingHub) return;
    setState(() => _loadingHub = true);
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
      if (mounted) setState(() => _loadingHub = false);
    }
  }

  Future<void> _reloadData() async {
    // â”€â”€ Section 1: Credentials (non-critical) â”€â”€
    try {
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
    } catch (_) {
      // Keep previous credential state
    }

    // â”€â”€ Section 2: Bot list (CRITICAL â€” the stars of the show) â”€â”€
    try {
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
      // Only fetch logs for expanded bots (lazy loading)
      for (final id in _expandedBots) {
        try {
          await _refreshHubLogs(id);
        } catch (_) {
          // Individual bot log failure is non-critical
        }
      }
    } catch (_) {
      // Keep previous bot list â€” never clear running bots on transient error
    }

    // â”€â”€ Section 3: Gateway snapshot (weight monitoring) â”€â”€
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

    // â”€â”€ Section 4: Protocol ops status (non-critical) â”€â”€
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

  bool _bgRefreshInFlight = false;

  Future<void> _backgroundRefresh() async {
    if (!mounted || _loadingHub || _bgRefreshInFlight) return;
    _bgRefreshInFlight = true;
    try {
      await _reloadData();
      if (mounted) setState(() {});
    } catch (_) {
      // Silent background refresh; explicit actions still surface errors.
    } finally {
      _bgRefreshInFlight = false;
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

  Future<void> _openRegistrosPage() async {
    await showDialog<void>(
      context: context,
      builder: (ctx) => Dialog(
        child: SizedBox(
          width: 800,
          height: 600,
          child: DefaultTabController(
            length: 2,
            child: Column(
              children: [
                Container(
                  color: Theme.of(ctx).colorScheme.surfaceContainerHighest,
                  child: TabBar(
                    tabs: const [
                      Tab(icon: Icon(Icons.analytics_outlined), text: 'Monitor de Peso REST'),
                      Tab(icon: Icon(Icons.storage), text: 'Registro SQLite'),
                    ],
                    labelColor: Theme.of(ctx).colorScheme.primary,
                  ),
                ),
                Expanded(
                  child: TabBarView(
                    children: [
                      // Tab 1: REST Weight Monitor
                      RestWeightMonitorDialog(api: _api, embedded: true),
                      // Tab 2: SQLite Registry
                      _buildSqliteTab(ctx),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildSqliteTab(BuildContext ctx) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SelectableText(
            'runtime/data/dorothy_hub.sqlite',
            style: TextStyle(fontFamily: 'monospace', fontSize: 13),
          ),
          const SizedBox(height: 8),
          const Text(
            'Cada instancia se identifica por su bot_id y guarda historial crudo completo.',
          ),
          const SizedBox(height: 12),
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
          if (_hubBots.isEmpty)
            const Text('Sin instancias activas.', style: TextStyle(color: Colors.grey)),
        ],
      ),
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
                                  onPressed: _loadingHub
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
                                  if (_loadingHub) return;
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
                              onPressed: _loadingHub
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

  Future<void> _toggleGateway() async {
    if (_gatewayRunning) {
      await _stopGateway();
    } else {
      await _startGateway();
    }
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
              'ts $ts · stopped $stopped · err $errors · ${plainNum(elapsed)}s',
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
            onPressed: _loadingHub ? null : onRun,
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

  Widget _navBtn(IconData icon, String tooltip, int idx) {
    final active = _currentIndex == idx;
    return IconButton(
      onPressed: () => setState(() => _currentIndex = idx),
      tooltip: tooltip,
      icon: Icon(icon, size: 18,
        color: active
            ? Theme.of(context).colorScheme.primary
            : null),
      style: active
          ? IconButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.primary.withOpacity(0.15),
            )
          : null,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PecunatorCore'),
        automaticallyImplyLeading: false,
        actions: [
          // â”€â”€ Navigation: pages â”€â”€
          _navBtn(Icons.home, 'Dorothy Hub', 0),
          _navBtn(Icons.candlestick_chart, 'Mercado', 1),
          _navBtn(Icons.account_balance_wallet_outlined, 'Cuenta Spot', 2),
          _navBtn(Icons.library_books, 'Biblioteca', 3),
          _navBtn(Icons.psychology_alt_outlined, 'Masha', 4),
          _navBtn(Icons.hub_outlined, 'Thusnelda', 5),
          _navBtn(Icons.savings_outlined, 'Earn', 6),
          _navBtn(Icons.currency_exchange, 'Carry', 7),
          const SizedBox(width: 4),
          Container(width: 1, height: 24, color: Colors.white24),
          const SizedBox(width: 4),
          // â”€â”€ Utilities â”€â”€
          IconButton(
            onPressed: _loadingHub ? null : _openCredentialManager,
            tooltip: 'Gestionar API keys',
            icon: const Icon(Icons.key, size: 18),
          ),
          // â”€â”€ Gateway toggle â”€â”€
          IconButton(
            onPressed: _loadingHub ? null : _toggleGateway,
            tooltip: _gatewayRunning
                ? 'Gateway ON${_gatewayWsConnected ? " · WS" : ""} â€” pulsa para detener'
                : 'Gateway OFF â€” pulsa para iniciar',
            icon: Icon(
              _gatewayRunning ? Icons.cloud_done : Icons.cloud_off_outlined,
              size: 20,
              color: _gatewayRunning ? _gatewayTrafficColor() : Colors.grey,
            ),
          ),
          // â”€â”€ Registros & Monitoreo (combined) â”€â”€
          IconButton(
            onPressed: _loadingHub ? null : _openRegistrosPage,
            tooltip: 'Registros, Monitor de Peso y SQLite',
            icon: const Icon(Icons.assessment_outlined, size: 18),
          ),
          // â”€â”€ Theme toggle â”€â”€
          IconButton(
            onPressed: () => widget.onThemeChanged(!widget.darkMode),
            tooltip: widget.darkMode ? 'Modo día' : 'Modo noche',
            icon: Icon(
              widget.darkMode ? Icons.light_mode : Icons.dark_mode,
              size: 18,
            ),
          ),
          // â”€â”€ Binance Server Clock â”€â”€
          Padding(
            padding: const EdgeInsets.only(right: 2),
            child: GestureDetector(
              onTap: _loadingHub ? null : _syncTimestamp,
              child: Tooltip(
                message: 'Hora del servidor Binance â€” pulsa para sincronizar',
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.public, size: 13,
                      color: Theme.of(context).colorScheme.primary),
                    const SizedBox(width: 3),
                    Text(_clockText,
                      style: const TextStyle(fontSize: 11, fontFamily: 'monospace')),
                    const SizedBox(width: 3),
                    Text('BINANCE',
                      style: TextStyle(fontSize: 8, fontWeight: FontWeight.w600,
                        letterSpacing: 0.5,
                        color: Theme.of(context).colorScheme.primary.withOpacity(0.7))),
                  ],
                ),
              ),
            ),
          ),
          // â”€â”€ Refresh â”€â”€
          IconButton(
            onPressed: _loadingHub ? null : _refreshAll,
            tooltip: 'Refrescar',
            icon: const Icon(Icons.refresh, size: 18),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: [
              _buildDorothyView(),
              MarketMonitorPage(api: _api),
              SpotAccountPage(engineBase: _engineBase, activeSymbols: _hubBots.map((b) => (b['symbol'] ?? '').toString()).where((s) => s.isNotEmpty).toList()),
              const LibraryManagerPage(),
              MashaHubPage(engineBase: _engineBase),
              ThusneldaHubPage(engineBase: _engineBase),
              const EarnManagerPage(),
              const CarryTradePage(),
            ][_currentIndex],
          ),
          // â”€â”€ Persistent compact weight gauge (visible on ALL pages) â”€â”€
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            child: CompactWeightGauge(api: _api),
          ),
        ],
      ),
    );
  }

  Widget _buildDorothyView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_loadingHub) const LinearProgressIndicator(),
          Wrap(
            spacing: 16,
            runSpacing: 16,
            crossAxisAlignment: WrapCrossAlignment.start,
            children: [
              // Left Column: Main Hub Info
              SizedBox(
                width: 400,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
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
            // â”€â”€ Dorothy Guide button â”€â”€
            OutlinedButton.icon(
              onPressed: _openDorothyGuide,
              icon: const Icon(Icons.menu_book, size: 16),
              label: const Text('Instructivo Dorothy 7.0'),
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
                  ],
                ),
              ),
              
              // Right Column: VMO Sensor Dashboard
              SizedBox(
                height: 280, // Constrain height so it doesn't take infinite space
                child: VmoDashboard(api: _api),
              ),
            ],
          ),
          const SizedBox(height: 16),
            Card(
              child: ExpansionTile(
                title: const Text('Herramientas de Protocolo y Cleanup (RED BUTTON)', style: TextStyle(fontWeight: FontWeight.w700, color: Colors.redAccent)),
                leading: const Icon(Icons.warning_amber_rounded, color: Colors.redAccent),
                childrenPadding: const EdgeInsets.all(8),
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
                            onPressed: _loadingHub ? null : _createBot,
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
                            onPressed: _loadingHub ? null : _openConfigHistoryDialog,
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
                          'qty ${plainNum(b['quote_order_qty'])}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'p ${plainNum(b['profit_factor'])}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'd ${plainNum(b['margin_drop_factor'])}',
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
                          'dd ${plainNum(b['max_drawdown_pct'])}',
                          style: const TextStyle(fontSize: 12),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          'sl ${plainNum(b['stop_loss_pct'])}',
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
                            onPressed: _loadingHub
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
                        onPressed: _loadingHub
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
                        onChanged: _loadingHub
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
                                onPressed: _loadingHub
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
                            onPressed: _loadingHub
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
      );
  }
}
