import 'dart:async';
import 'package:flutter/material.dart';
import '../utils.dart';
import '../api_client.dart';

class RestWeightMonitorDialog extends StatefulWidget {
  const RestWeightMonitorDialog({
    super.key,
    required this.api,
    this.embedded = false,
  });

  final EngineApi api;
  final bool embedded;

  @override
  State<RestWeightMonitorDialog> createState() =>
      RestWeightMonitorDialogState();
}

class RestWeightMonitorDialogState extends State<RestWeightMonitorDialog> {
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
    final bar = ('â–“' * filled) + ('-' * (barLength - filled));
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
    final body = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'Este monitor muestra el encabezado acumulado de Binance por ventana de 1 minuto '
          'y por IP compartida. No es por bot individual.',
          style: TextStyle(
            fontSize: 12,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 8),
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
              valueColor: AlwaysStoppedAnimation<Color>(_weightColorFromPct(v)),
              backgroundColor: Theme.of(
                context,
              ).colorScheme.surfaceContainerHighest,
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
    );

    if (widget.embedded) {
      return Padding(padding: const EdgeInsets.all(12), child: body);
    }

    return AlertDialog(
      title: const Text('Monitor de peso REST (X-MBX-USED-WEIGHT-1M)'),
      content: SizedBox(width: 860, height: 560, child: body),
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
    final notes = ((_report['notes'] as List?) ?? const [])
        .map((e) => '$e')
        .toList();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SelectableText(
          'Poll s=${cfg['account_poll_sec'] ?? "-"} | myTrades stride=${cfg['my_trades_stride'] ?? "-"} | '
          'equity stride=${cfg['equity_stride'] ?? "-"} | ciclos/min=${est['cycles_per_min'] ?? "-"}',
          style: const TextStyle(fontFamily: 'monospace', fontSize: 11),
        ),
        const SizedBox(height: 6),
        ...notes
            .take(3)
            .map(
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
                    final avg = plainNum(r['delta_avg']);
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
