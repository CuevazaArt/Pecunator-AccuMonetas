import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../utils.dart';
import '../api_client.dart';
import 'bot_guide_page.dart';
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
    try {
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
    } catch (e) {
      debugPrint('Masha _reload error: $e');
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
      final sym = _symbolCtrl.text.trim().toUpperCase();
      // Auto-resolve decimals from Binance exchangeInfo (hardcoded once)
      int qDec = 8;
      int pDec = 8;
      try {
        final prec = await _api.symbolPrecision(sym);
        qDec = (prec['qty_decimals'] as int?) ?? 8;
        pDec = (prec['price_decimals'] as int?) ?? 8;
      } catch (_) { /* gateway offline — use safe defaults */ }
      await _api.mashaCreateBot({
        'tag': _tagCtrl.text.trim().isEmpty ? 'Masha' : _tagCtrl.text.trim(),
        'symbol': sym,
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
        'qty_decimals': qDec,
        'price_decimals': pDec,
        'note': _noteCtrl.text.trim(),
        'max_drawdown_pct': _maxDdCtrl.text.trim(),
        'stop_loss_pct': _stopLossCtrl.text.trim(),
        'metrics_interval_cycles': int.tryParse(_metricsEveryCtrl.text.trim()) ?? 5,
        'simulated': false,
        'trading_enabled': true,
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
      final sym = (d['symbol'] ?? '').toUpperCase();
      // Auto-resolve decimals from Binance exchangeInfo
      int qDec = int.tryParse(d['qDec'] ?? '8') ?? 8;
      int pDec = int.tryParse(d['pDec'] ?? '8') ?? 8;
      try {
        final prec = await _api.symbolPrecision(sym);
        qDec = (prec['qty_decimals'] as int?) ?? qDec;
        pDec = (prec['price_decimals'] as int?) ?? pDec;
      } catch (_) { /* gateway offline — keep current values */ }
      await _api.mashaUpdateBot(botId, {
        'tag': d['tag'],
        'symbol': sym,
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
        'qty_decimals': qDec,
        'price_decimals': pDec,
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
                        // qDec/pDec removed — auto-resolved from Binance exchangeInfo
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
                    '${(bot['symbol'] ?? '-').toString()} | dd ${plainNum(bot['max_drawdown_pct'])} | sl ${plainNum(bot['stop_loss_pct'])} | m ${(bot['metrics_interval_cycles'] ?? '-')} | err: ${(bot['last_error'] ?? '-').toString()}',
                    style: const TextStyle(fontSize: 11),
                  ),
                  children: [
                    Padding(
                      padding: const EdgeInsets.all(8),
                      child: SingleChildScrollView(
                        scrollDirection: Axis.horizontal,
                        child: Row(
                          children: [
                            _f(botId, d, 'tag', 'Tag', 120), const SizedBox(width: 6),
                            _f(botId, d, 'symbol', 'Símbolo', 120), const SizedBox(width: 6),
                            _f(botId, d, 'base', 'Base', 85), const SizedBox(width: 6),
                            _f(botId, d, 'quote', 'Quote', 85), const SizedBox(width: 6),
                            _f(botId, d, 'loop', 'Loop s', 85), const SizedBox(width: 6),
                            _f(botId, d, 'minQuote', 'Min quote', 95), const SizedBox(width: 6),
                            _f(botId, d, 'buyQty', 'Buy qty', 95), const SizedBox(width: 6),
                            _f(botId, d, 'profit', 'Profit', 85), const SizedBox(width: 6),
                            _f(botId, d, 'tfW', 'TF W', 70), const SizedBox(width: 6),
                            _f(botId, d, 'pW', 'P W', 60), const SizedBox(width: 6),
                            _f(botId, d, 'mmW', 'MM W', 70), const SizedBox(width: 6),
                            _f(botId, d, 'mW', 'M W', 80), const SizedBox(width: 6),
                            _f(botId, d, 'tfH', 'TF H', 70), const SizedBox(width: 6),
                            _f(botId, d, 'pH', 'P H', 60), const SizedBox(width: 6),
                            _f(botId, d, 'mmH', 'MM H', 70), const SizedBox(width: 6),
                            _f(botId, d, 'mH', 'M H', 80), const SizedBox(width: 6),
                            // qDec/pDec removed — auto-resolved from Binance exchangeInfo on save
                            _f(botId, d, 'note', 'Nota', 130), const SizedBox(width: 6),
                            _f(botId, d, 'maxDd', 'maxDd', 80), const SizedBox(width: 6),
                            _f(botId, d, 'stopLoss', 'stopLoss', 90), const SizedBox(width: 6),
                            _f(botId, d, 'metricsEvery', 'metricsEvery', 95),
                          ],
                        ),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(left: 8, right: 8, bottom: 8),
                      child: Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        alignment: WrapAlignment.start,
                        children: [
                          FilledButton.tonalIcon(
                            style: FilledButton.styleFrom(
                              backgroundColor: running ? Colors.green.withOpacity(0.2) : Colors.orangeAccent.withOpacity(0.2),
                              foregroundColor: running ? Colors.greenAccent : Colors.orangeAccent,
                            ),
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

