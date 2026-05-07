import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import '../api_client.dart';
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

