import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../utils.dart';
import '../api_client.dart';
import 'bot_guide_page.dart';
class ThusneldaHubPage extends StatefulWidget {
  const ThusneldaHubPage({super.key, required this.engineBase});

  final String engineBase;

  @override
  State<ThusneldaHubPage> createState() => _ThusneldaHubPageState();
}

class _ThusneldaHubPageState extends State<ThusneldaHubPage> {
  final _tagCtrl = TextEditingController(text: 'Thusnelda L0');
  final _symbolsCtrl = TextEditingController(text: 'PEPEUSDT,SUIUSDT,NEARUSDT,INJUSDT,FETUSDT');
  final _loopCtrl = TextEditingController(text: '300');
  final _betweenCtrl = TextEditingController(text: '3');
  final _quoteQtyCtrl = TextEditingController(text: '6');
  final _factorCtrl = TextEditingController(text: '0.94');
  final _profitTargetCtrl = TextEditingController(text: '0.06');
  final _metaCtrl = TextEditingController(text: '0');
  final _refTsCtrl = TextEditingController();
  final _qtyDecCtrl = TextEditingController(text: '8');
  final _noteCtrl = TextEditingController();
  final _maxDdCtrl = TextEditingController(text: '0.30');
  final _stopLossCtrl = TextEditingController(text: '0.25');
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
    _profitTargetCtrl.dispose();
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
        'tag': (bot['tag'] ?? 'Thusnelda L0').toString(),
        'symbols': (bot['symbols_csv'] ?? 'PEPEUSDT,SUIUSDT,NEARUSDT,INJUSDT,FETUSDT').toString(),
        'loop': (bot['loop_interval_sec'] ?? 300).toString(),
        'between': (bot['between_symbol_sec'] ?? 3).toString(),
        'quoteQty': (bot['quote_order_qty_modulo'] ?? '8').toString(),
        'factor': (bot['factor_multiplication'] ?? '0.94').toString(),
        'profitTarget': (bot['profit_target_pct'] ?? '0.06').toString(),
        'meta': (bot['meta_equity_usdt'] ?? '0').toString(),
        'refTs': (bot['reference_ts_iso'] ?? '').toString(),
        'qDec': (bot['qty_decimals'] ?? 8).toString(),
        'note': (bot['note'] ?? '').toString(),
        'maxDd': (bot['max_drawdown_pct'] ?? '0.30').toString(),
        'stopLoss': (bot['stop_loss_pct'] ?? '0.25').toString(),
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
        return 'Factor multiplicador para ajustar gatillo de entrada (0.94 = compra 6% debajo).';
      case 'profitTarget':
        return 'Objetivo de beneficio por ciclo (0.06 = 6%). Minimo 6% para cesta volatil.';
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
    try {
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
    } catch (e) {
      debugPrint('Thusnelda _reload error: $e');
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
        'profit_target_pct': _profitTargetCtrl.text.trim(),
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
        'loop_interval_sec': int.tryParse(d['loop'] ?? '300') ?? 600,
        'between_symbol_sec': int.tryParse(d['between'] ?? '3') ?? 3,
        'quote_order_qty_modulo': d['quoteQty'] ?? '6',
        'factor_multiplication': d['factor'] ?? '0.94',
        'profit_target_pct': d['profitTarget'] ?? '0.06',
        'meta_equity_usdt': d['meta'] ?? '0',
        'reference_ts_iso': d['refTs'] ?? '',
        'qty_decimals': int.tryParse(d['qDec'] ?? '8') ?? 8,
        'note': d['note'] ?? '',
        'max_drawdown_pct': d['maxDd'] ?? '0.30',
        'stop_loss_pct': d['stopLoss'] ?? '0.25',
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
        title: const Text('Thusnelda L0 · Volatile Basket Hub'),
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
                      'Nueva instancia Thusnelda L0 (Cesta Volatil)',
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
                        _newField(_profitTargetCtrl, 'Profit %', 90, 'profitTarget'),
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
                    'No hay instancias Thusnelda L0. Crea una con la cesta volátil.',
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
                    '${(bot['tag'] ?? 'Thusnelda L0').toString()} · $botId · ${running ? "ACTIVO" : "INACTIVO"}',
                    style: const TextStyle(fontSize: 13),
                  ),
                  subtitle: Text(
                    '${(bot['symbols_csv'] ?? '-').toString()} | dd ${plainNum(bot['max_drawdown_pct'])} | sl ${plainNum(bot['stop_loss_pct'])} | m ${(bot['metrics_interval_cycles'] ?? '-')} | err: ${(bot['last_error'] ?? '-').toString()}',
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
                            _f(botId, d, 'symbols', 'Símbolos CSV', 210), const SizedBox(width: 6),
                            _f(botId, d, 'loop', 'Loop s', 85), const SizedBox(width: 6),
                            _f(botId, d, 'between', 'Entre sym s', 95), const SizedBox(width: 6),
                            _f(botId, d, 'quoteQty', 'Quote qty', 95), const SizedBox(width: 6),
                            _f(botId, d, 'factor', 'Factor', 85), const SizedBox(width: 6),
                            _f(botId, d, 'profitTarget', 'Profit %', 85), const SizedBox(width: 6),
                            _f(botId, d, 'meta', 'Meta USDT', 110), const SizedBox(width: 6),
                            _f(botId, d, 'refTs', 'Referencia ISO', 180), const SizedBox(width: 6),
                            _f(botId, d, 'qDec', 'QDec', 65), const SizedBox(width: 6),
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

