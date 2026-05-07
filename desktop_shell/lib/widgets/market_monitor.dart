import 'dart:async';
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:candlesticks/candlesticks.dart';
import 'package:web_socket_channel/web_socket_channel.dart';
// import 'package:webview_windows/webview_windows.dart';
import '../api_client.dart'; // EngineApi
import '../utils/histogram_storage.dart';
import '../services/history_scraper.dart';

class MarketMonitorPage extends StatefulWidget {
  final EngineApi api;

  const MarketMonitorPage({super.key, required this.api});

  @override
  State<MarketMonitorPage> createState() => _MarketMonitorPageState();
}

class _MarketMonitorPageState extends State<MarketMonitorPage> {
  final _symbolCtrl = TextEditingController(text: 'BTCUSDT');
  String _currentSymbol = 'BTCUSDT';
  String _currentInterval = '1m';

  List<Candle> _candles = [];
  bool _loading = false;
  final Map<String, List<String>> _libraryData = {};
  bool _dynamicUpdate = true;
  WebSocketChannel? _wsChannel;
  StreamSubscription? _wsSub;

  // Posiciones registradas manualmente
  final List<Map<String, dynamic>> _positions = [];
  final _positionPriceCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadAvailableSymbols();
    _loadData();
  }

  Future<void> _loadAvailableSymbols() async {
    final stats = await HistogramStorage.instance.getLibraryStats();
    if (mounted) {
      setState(() {
        _libraryData.clear();
        for (var stat in stats) {
          final sym = stat['symbol'] as String;
          final interval = stat['interval'] as String;
          if (!_libraryData.containsKey(sym)) {
            _libraryData[sym] = [];
          }
          if (!_libraryData[sym]!.contains(interval)) {
            _libraryData[sym]!.add(interval);
          }
        }
      });
    }
  }

  @override
  void dispose() {
    _symbolCtrl.dispose();
    _wsSub?.cancel();
    _wsChannel?.sink.close();
    _positionPriceCtrl.dispose();
    super.dispose();
  }

  void _addPosition(double price, String side) {
    setState(() {
      _positions.add({'price': price, 'side': side, 'time': DateTime.now()});
    });
  }

  void _removePosition(int index) {
    setState(() {
      _positions.removeAt(index);
    });
  }

  Future<void> _loadData() async {
    if (_loading) return;
    setState(() => _loading = true);

    _wsSub?.cancel();
    _wsChannel?.sink.close();

    final symbol = _currentSymbol.toUpperCase();
    final interval = _currentInterval;

    try {
      // 1. Cargar biblioteca local
      List<Candle> localCandles = await HistogramStorage.instance.getCandles(
        symbol,
        interval,
      );

      String startStr = '';
      if (localCandles.isNotEmpty) {
        // Híbrido: actualizar desde la última vela local
        final lastTs = localCandles.last.date.millisecondsSinceEpoch;
        startStr = '${lastTs + 1}';
      } else {
        // Primera vez: máxima cantidad razonable (ej. 1000 velas)
        if (interval.endsWith('m')) {
          startStr =
              '${int.parse(interval.replaceAll('m', '')) * 1000} minutes ago UTC';
        } else if (interval.endsWith('h')) {
          startStr =
              '${int.parse(interval.replaceAll('h', '')) * 1000} hours ago UTC';
        } else if (interval.endsWith('d')) {
          startStr =
              '${int.parse(interval.replaceAll('d', '')) * 1000} days ago UTC';
        } else {
          startStr = '1000 minutes ago UTC';
        }
      }

      final res = await widget.api.sandboxRestQuery(
        callExpression:
            "get_historical_klines(symbol='$symbol', interval='$interval', start_str='$startStr')",
        limit: 1000,
      );

      if (res.containsKey('error')) {
        throw Exception(res['error']);
      }

      // La respuesta del motor está en 'response', no 'result'
      final List data = res['response'] ?? [];
      final List<Candle> apiCandles = [];
      for (final kline in data) {
        apiCandles.add(
          Candle(
            date: DateTime.fromMillisecondsSinceEpoch(kline[0]),
            open: double.parse(kline[1].toString()),
            high: double.parse(kline[2].toString()),
            low: double.parse(kline[3].toString()),
            close: double.parse(kline[4].toString()),
            volume: double.parse(kline[5].toString()),
          ),
        );
      }

      // Guardar huecos/nuevas velas en SQLite
      if (apiCandles.isNotEmpty) {
        await HistogramStorage.instance.insertCandles(
          symbol,
          interval,
          apiCandles,
        );
        localCandles.addAll(apiCandles);
      }

      // candlesticks package requires the list to be reversed (newest first)
      setState(() {
        _candles = localCandles.reversed.toList();
        _loading = false;
      });

      if (_dynamicUpdate) {
        _connectWs(symbol, interval);
      }
    } catch (e) {
      setState(() {
        _loading = false;
        _candles = [];
      });
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Error: $e')));
      }
    }
  }

  void _connectWs(String symbol, String interval) {
    final wsUrl = Uri.parse(
      'wss://stream.binance.com:9443/ws/${symbol.toLowerCase()}@kline_$interval',
    );
    _wsChannel = WebSocketChannel.connect(wsUrl);
    _wsSub = _wsChannel?.stream.listen(
      (message) {
        final data = jsonDecode(message);
        if (data['e'] == 'kline') {
          final k = data['k'];
          final candle = Candle(
            date: DateTime.fromMillisecondsSinceEpoch(k['t']),
            open: double.parse(k['o']),
            high: double.parse(k['h']),
            low: double.parse(k['l']),
            close: double.parse(k['c']),
            volume: double.parse(k['v']),
          );

          if (!mounted) return;

          setState(() {
            if (_candles.isNotEmpty && _candles.first.date == candle.date) {
              _candles[0] = candle;
            } else {
              _candles.insert(0, candle);
            }
          });
        }
      },
      onError: (e) {
        print('WS Error: $e');
      },
    );
  }

  void _applySymbol() {
    final s = _symbolCtrl.text.trim().toUpperCase();
    if (s.isEmpty) return;
    setState(() {
      _currentSymbol = s;
    });
    _loadData();
  }

  void _changeInterval(String interval) {
    setState(() {
      _currentInterval = interval;
    });
    _loadData();
  }

  void _toggleDynamicUpdate(bool value) {
    setState(() {
      _dynamicUpdate = value;
    });
    if (_dynamicUpdate) {
      _connectWs(_currentSymbol.toUpperCase(), _currentInterval);
    } else {
      _wsSub?.cancel();
      _wsChannel?.sink.close();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Gráficos Nativos'),
        elevation: 0,
        actions: [
          Tooltip(
            message: 'Gráficos Híbridos (Próximamente)',
            child: IconButton(
              icon: const Icon(Icons.auto_graph, color: Colors.greenAccent),
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    content: Text(
                      'Gráficos Híbridos estarán disponibles pronto.',
                    ),
                  ),
                );
              },
            ),
          ),
          Builder(
            builder: (context) => Tooltip(
              message: 'Índice de Biblioteca Local',
              child: IconButton(
                icon: const Icon(
                  Icons.library_books,
                  color: Colors.orangeAccent,
                ),
                onPressed: () {
                  _loadAvailableSymbols(); // Reload before opening
                  Scaffold.of(context).openEndDrawer();
                },
              ),
            ),
          ),
          const SizedBox(width: 16),
        ],
      ),
      endDrawer: Drawer(
        backgroundColor: Colors.grey[900],
        child: Column(
          children: [
            const DrawerHeader(
              decoration: BoxDecoration(color: Colors.black45),
              child: Center(
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(Icons.storage, size: 48, color: Colors.orangeAccent),
                    SizedBox(height: 8),
                    Text(
                      'Índice de Biblioteca',
                      style: TextStyle(
                        color: Colors.orangeAccent,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            Expanded(
              child: ListView(
                children: _libraryData.keys.map((sym) {
                  return ExpansionTile(
                    leading: const Icon(Icons.folder, color: Colors.grey),
                    title: Text(
                      sym,
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                    children: _libraryData[sym]!.map((interval) {
                      return ListTile(
                        leading: const Icon(
                          Icons.show_chart,
                          color: Colors.greenAccent,
                          size: 20,
                        ),
                        title: Text(
                          'Intervalo: $interval',
                          style: const TextStyle(color: Colors.grey),
                        ),
                        onTap: () {
                          Navigator.pop(context); // Close drawer
                          _symbolCtrl.text = sym;
                          _currentInterval = interval;
                          _applySymbol();
                        },
                      );
                    }).toList(),
                  );
                }).toList(),
              ),
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.all(8.0),
            color: Theme.of(context).cardColor,
            child: Row(
              children: [
                SizedBox(
                  width: 150,
                  child: TextField(
                    controller: _symbolCtrl,
                    decoration: InputDecoration(
                      labelText: 'Símbolo (Ej. BTCUSDT)',
                      labelStyle: const TextStyle(color: Colors.orangeAccent),
                      isDense: true,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(
                          color: Colors.orangeAccent,
                        ),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(8),
                        borderSide: const BorderSide(
                          color: Colors.orangeAccent,
                          width: 2,
                        ),
                      ),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 10,
                      ),
                    ),
                    onSubmitted: (_) => _applySymbol(),
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton.icon(
                  onPressed: _loading ? null : _applySymbol,
                  icon: const Icon(Icons.search, size: 16),
                  label: const Text('Cargar'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.orangeAccent,
                    foregroundColor: Colors.black,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(8),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                const Spacer(),
                const Text(
                  'Temporalidad: ',
                  style: TextStyle(
                    color: Colors.grey,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 12),
                  decoration: BoxDecoration(
                    color: Colors.black45,
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: Colors.orangeAccent.withOpacity(0.5),
                    ),
                  ),
                  child: DropdownButtonHideUnderline(
                    child: DropdownButton<String>(
                      value: _currentInterval,
                      dropdownColor: Colors.grey[900],
                      icon: const Icon(
                        Icons.arrow_drop_down,
                        color: Colors.orangeAccent,
                      ),
                      style: const TextStyle(
                        color: Colors.white,
                        fontWeight: FontWeight.bold,
                      ),
                      items: const [
                        DropdownMenuItem(value: '1m', child: Text('1m')),
                        DropdownMenuItem(value: '5m', child: Text('5m')),
                        DropdownMenuItem(value: '15m', child: Text('15m')),
                        DropdownMenuItem(value: '1h', child: Text('1h')),
                        DropdownMenuItem(value: '4h', child: Text('4h')),
                        DropdownMenuItem(value: '1d', child: Text('1d')),
                      ],
                      onChanged: (v) {
                        if (v != null) _changeInterval(v);
                      },
                    ),
                  ),
                ),
                const Spacer(),
                ValueListenableBuilder<String>(
                  valueListenable:
                      HistoryScraperService.instance.currentJobNotifier,
                  builder: (context, currentJob, child) {
                    final bool isIdle = currentJob == 'Inactivo';
                    return Tooltip(
                      message: isIdle ? 'Scraper en reposo' : currentJob,
                      child: Row(
                        children: [
                          Text(
                            'Scraper: ',
                            style: TextStyle(color: Colors.grey),
                          ),
                          Text(
                            isIdle ? 'ON' : 'Procesando...',
                            style: TextStyle(
                              color: isIdle
                                  ? Colors.greenAccent
                                  : Colors.orangeAccent,
                              fontSize: 10,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          if (!isIdle) ...[
                            const SizedBox(width: 4),
                            const SizedBox(
                              width: 10,
                              height: 10,
                              child: CircularProgressIndicator(
                                strokeWidth: 2,
                                color: Colors.orangeAccent,
                              ),
                            ),
                          ],
                        ],
                      ),
                    );
                  },
                ),
                Tooltip(
                  message:
                      'Control manual del servicio de recolección en segundo plano',
                  child: Switch(
                    value: HistoryScraperService.instance.isEnabled,
                    onChanged: (v) => setState(
                      () => HistoryScraperService.instance.isEnabled = v,
                    ),
                    activeThumbColor: Colors.greenAccent,
                  ),
                ),
                const SizedBox(width: 8),
                ValueListenableBuilder<int>(
                  valueListenable:
                      HistoryScraperService.instance.concurrencyNotifier,
                  builder: (context, threads, child) {
                    return Tooltip(
                      message:
                          'Hilos de descarga paralela (0 = Pausado, 1-N = Velocidad)',
                      child: DropdownButton<int>(
                        value: threads,
                        dropdownColor: Colors.grey[900],
                        icon: const Icon(
                          Icons.speed,
                          color: Colors.grey,
                          size: 16,
                        ),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                        ),
                        items: List.generate(
                          7,
                          (index) => DropdownMenuItem(
                            value: index,
                            child: Text('$index Hilos'),
                          ),
                        ),
                        onChanged: (v) {
                          if (v != null)
                            HistoryScraperService
                                    .instance
                                    .concurrencyNotifier
                                    .value =
                                v;
                        },
                      ),
                    );
                  },
                ),
                const SizedBox(width: 8),
                ValueListenableBuilder<int>(
                  valueListenable:
                      HistoryScraperService.instance.delayMsNotifier,
                  builder: (context, delayMs, child) {
                    return Tooltip(
                      message:
                          'Delay entre peticiones individuales (Mitiga límites API)',
                      child: DropdownButton<int>(
                        value: delayMs,
                        dropdownColor: Colors.grey[900],
                        icon: const Icon(
                          Icons.timer_outlined,
                          color: Colors.grey,
                          size: 16,
                        ),
                        style: const TextStyle(
                          color: Colors.white,
                          fontSize: 12,
                        ),
                        items: const [
                          DropdownMenuItem(value: 0, child: Text('0s Delay')),
                          DropdownMenuItem(
                            value: 500,
                            child: Text('0.5s Delay'),
                          ),
                          DropdownMenuItem(
                            value: 1000,
                            child: Text('1s Delay'),
                          ),
                          DropdownMenuItem(
                            value: 2000,
                            child: Text('2s Delay'),
                          ),
                          DropdownMenuItem(
                            value: 5000,
                            child: Text('5s Delay'),
                          ),
                        ],
                        onChanged: (v) {
                          if (v != null)
                            HistoryScraperService
                                    .instance
                                    .delayMsNotifier
                                    .value =
                                v;
                        },
                      ),
                    );
                  },
                ),
                const SizedBox(width: 8),
                Tooltip(
                  message:
                      'Activa o desactiva WebSocket para actualizar el precio en tiempo real',
                  child: const Text(
                    'Dinámica WS:',
                    style: TextStyle(color: Colors.grey),
                  ),
                ),
                Tooltip(
                  message: 'Conectar/Desconectar flujo WebSocket de Binance',
                  child: Switch(
                    value: _dynamicUpdate,
                    onChanged: _toggleDynamicUpdate,
                    activeThumbColor: Colors.greenAccent,
                  ),
                ),
                if (_loading) const CircularProgressIndicator(),
              ],
            ),
          ),
          Expanded(
            child: Container(
              margin: const EdgeInsets.all(8.0),
              decoration: BoxDecoration(
                border: Border.all(color: Colors.grey.withOpacity(0.2)),
                borderRadius: BorderRadius.circular(8),
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(8),
                child: Row(
                  children: [
                    Expanded(
                      child: _candles.length < 20
                          ? Center(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Icon(
                                    Icons.candlestick_chart,
                                    size: 64,
                                    color: Colors.grey.withOpacity(0.3),
                                  ),
                                  const SizedBox(height: 16),
                                  Text(
                                    'Recopilando historial... (${_candles.length}/20 velas)',
                                    style: const TextStyle(color: Colors.grey),
                                  ),
                                ],
                              ),
                            )
                          : Column(
                              children: [
                                Container(
                                  padding: const EdgeInsets.symmetric(
                                    horizontal: 12,
                                    vertical: 4,
                                  ),
                                  color: Colors.black26,
                                  child: Row(
                                    children: [
                                      Text(
                                        '$_currentSymbol · $_currentInterval',
                                        style: const TextStyle(
                                          fontWeight: FontWeight.bold,
                                          color: Colors.orangeAccent,
                                        ),
                                      ),
                                      const Spacer(),
                                      if (_candles.isNotEmpty) ...[
                                        Text(
                                          'O: ${_candles.first.open.toStringAsFixed(2)}  ',
                                          style: const TextStyle(
                                            color: Colors.grey,
                                            fontSize: 12,
                                          ),
                                        ),
                                        Text(
                                          'H: ${_candles.first.high.toStringAsFixed(2)}  ',
                                          style: const TextStyle(
                                            color: Colors.grey,
                                            fontSize: 12,
                                          ),
                                        ),
                                        Text(
                                          'L: ${_candles.first.low.toStringAsFixed(2)}  ',
                                          style: const TextStyle(
                                            color: Colors.grey,
                                            fontSize: 12,
                                          ),
                                        ),
                                        Text(
                                          'C: ${_candles.first.close.toStringAsFixed(2)}  ',
                                          style: const TextStyle(
                                            color: Colors.grey,
                                            fontSize: 12,
                                          ),
                                        ),
                                        Text(
                                          'Vol: ${_candles.first.volume.toStringAsFixed(2)}',
                                          style: const TextStyle(
                                            color: Colors.grey,
                                            fontSize: 12,
                                          ),
                                        ),
                                      ],
                                    ],
                                  ),
                                ),

                                Expanded(
                                  child: TradingViewChartWidget(
                                    symbol: _currentSymbol,
                                    interval: _currentInterval,
                                    candles: _candles,
                                    orderLines: _positions
                                        .map(
                                          (e) => double.parse(
                                            e['price'].toString(),
                                          ),
                                        )
                                        .toList(),
                                    onChangeInterval: _changeInterval,
                                  ),
                                ),
                                Container(
                                  padding: const EdgeInsets.all(4),
                                  alignment: Alignment.center,
                                  child: Row(
                                    mainAxisAlignment: MainAxisAlignment.center,
                                    children: [
                                      const Icon(
                                        Icons.lightbulb_outline,
                                        color: Colors.orangeAccent,
                                        size: 14,
                                      ),
                                      const SizedBox(width: 4),
                                      const Text(
                                        'Mantén presionado para ver los detalles de OHLCV | Gráfico Nativo Acelerado',
                                        style: TextStyle(
                                          color: Colors.grey,
                                          fontSize: 11,
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                              ],
                            ),
                    ),
                    // Panel de Posiciones (Sidebar)
                    Container(
                      width: 250,
                      decoration: BoxDecoration(
                        border: Border(
                          left: BorderSide(color: Colors.grey.withOpacity(0.2)),
                        ),
                        color: Colors.black26,
                      ),
                      child: Column(
                        children: [
                          Container(
                            padding: const EdgeInsets.all(8),
                            color: Colors.black45,
                            width: double.infinity,
                            child: const Text(
                              'Órdenes / Posiciones',
                              style: TextStyle(
                                fontWeight: FontWeight.bold,
                                fontSize: 12,
                              ),
                              textAlign: TextAlign.center,
                            ),
                          ),
                          Padding(
                            padding: const EdgeInsets.all(8.0),
                            child: Row(
                              children: [
                                Expanded(
                                  child: TextField(
                                    controller: _positionPriceCtrl,
                                    decoration: const InputDecoration(
                                      hintText: 'Precio',
                                      isDense: true,
                                      contentPadding: EdgeInsets.symmetric(
                                        horizontal: 8,
                                        vertical: 8,
                                      ),
                                    ),
                                    keyboardType:
                                        const TextInputType.numberWithOptions(
                                          decimal: true,
                                        ),
                                  ),
                                ),
                                IconButton(
                                  icon: const Icon(
                                    Icons.add,
                                    color: Colors.greenAccent,
                                    size: 20,
                                  ),
                                  tooltip: 'Agregar LONG',
                                  onPressed: () {
                                    final val = double.tryParse(
                                      _positionPriceCtrl.text,
                                    );
                                    if (val != null) _addPosition(val, 'LONG');
                                    _positionPriceCtrl.clear();
                                  },
                                ),
                                IconButton(
                                  icon: const Icon(
                                    Icons.add,
                                    color: Colors.redAccent,
                                    size: 20,
                                  ),
                                  tooltip: 'Agregar SHORT',
                                  onPressed: () {
                                    final val = double.tryParse(
                                      _positionPriceCtrl.text,
                                    );
                                    if (val != null) _addPosition(val, 'SHORT');
                                    _positionPriceCtrl.clear();
                                  },
                                ),
                              ],
                            ),
                          ),
                          Expanded(
                            child: ListView.builder(
                              itemCount: _positions.length,
                              itemBuilder: (context, index) {
                                final pos = _positions[index];
                                final isLong = pos['side'] == 'LONG';
                                final double price = pos['price'];

                                // Calcular distancia al precio actual si hay velas
                                String distStr = '';
                                if (_candles.isNotEmpty) {
                                  final current = _candles.first.close;
                                  final pct = ((current - price) / price * 100);
                                  final isProfit = isLong ? pct >= 0 : pct <= 0;
                                  distStr =
                                      '\nDist: ${pct.toStringAsFixed(2)}% ${isProfit ? "🟢" : "🔴"}';
                                }

                                return Card(
                                  color: Colors.black45,
                                  margin: const EdgeInsets.symmetric(
                                    horizontal: 8,
                                    vertical: 4,
                                  ),
                                  child: ListTile(
                                    dense: true,
                                    title: Text(
                                      '${pos['side']} @ ${price.toStringAsFixed(2)}',
                                      style: TextStyle(
                                        color: isLong
                                            ? Colors.greenAccent
                                            : Colors.redAccent,
                                        fontWeight: FontWeight.bold,
                                        fontSize: 12,
                                      ),
                                    ),
                                    subtitle: Text(
                                      '${pos['time'].toString().split('.').first}$distStr',
                                      style: const TextStyle(fontSize: 10),
                                    ),
                                    trailing: IconButton(
                                      icon: const Icon(Icons.delete, size: 16),
                                      onPressed: () => _removePosition(index),
                                    ),
                                  ),
                                );
                              },
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Contenedor preparado arquitectónicamente para integrar TradingView Lightweight Charts (Tier Free).
/// Actualmente hace 'fallback' al paquete de candlesticks existente hasta que se implemente
/// el WebView o el wrapper oficial de JS para Windows.
class TradingViewChartWidget extends StatefulWidget {
  final String symbol;
  final String interval;
  final List<Candle> candles;
  final List<double> orderLines;
  final Function(String) onChangeInterval;

  const TradingViewChartWidget({
    super.key,
    required this.symbol,
    required this.interval,
    required this.candles,
    required this.orderLines,
    required this.onChangeInterval,
  });

  @override
  State<TradingViewChartWidget> createState() => _TradingViewChartWidgetState();
}

class _TradingViewChartWidgetState extends State<TradingViewChartWidget> {
  @override
  Widget build(BuildContext context) {
    if (widget.candles.isEmpty) {
      return const Center(
        child: CircularProgressIndicator(color: Colors.orangeAccent),
      );
    }

    // Convert to Candlesticks package format
    // Candlesticks package expects the most recent candle first (index 0).
    final reversedCandles = widget.candles.toList();

    return Stack(
      children: [
        Candlesticks(candles: reversedCandles, onLoadMoreCandles: () async {}),
        if (widget.orderLines.isNotEmpty)
          Positioned.fill(
            child: IgnorePointer(
              child: CustomPaint(
                painter: _OrderLinesPainter(
                  candles: reversedCandles,
                  orderLines: widget.orderLines,
                ),
              ),
            ),
          ),
        Positioned(top: 0, right: 0, child: _buildIntervalBar()),
      ],
    );
  }

  Widget _buildIntervalBar() {
    return Container(
      color: Colors.black45,
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: [
          _intervalBtn('1m'),
          _intervalBtn('15m'),
          _intervalBtn('1h'),
          _intervalBtn('4h'),
          _intervalBtn('1d'),
          _intervalBtn('1w'),
          _intervalBtn('1M'),
        ],
      ),
    );
  }

  Widget _intervalBtn(String text) {
    final isActive = widget.interval == text;
    return InkWell(
      onTap: () => widget.onChangeInterval(text),
      child: Container(
        margin: const EdgeInsets.only(right: 8),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: isActive
              ? Colors.orangeAccent.withOpacity(0.2)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(4),
        ),
        child: Text(
          text,
          style: TextStyle(color: isActive ? Colors.orangeAccent : Colors.grey),
        ),
      ),
    );
  }
}

class _OrderLinesPainter extends CustomPainter {
  final List<Candle> candles;
  final List<double> orderLines;

  _OrderLinesPainter({required this.candles, required this.orderLines});

  @override
  void paint(Canvas canvas, Size size) {
    if (candles.isEmpty || orderLines.isEmpty) return;

    // Aproximación rápida para encajar las líneas en el viewport visible de Candlesticks.
    // Usamos las últimas 50 velas como referencia heurística de escala visible.
    final visibleCount = candles.length > 50 ? 50 : candles.length;
    final visibleCandles = candles.take(visibleCount).toList();

    double maxVal = visibleCandles
        .map((c) => c.high)
        .reduce((a, b) => a > b ? a : b);
    double minVal = visibleCandles
        .map((c) => c.low)
        .reduce((a, b) => a < b ? a : b);

    if (maxVal == minVal) return;

    // Candlesticks deja un pequeño margen superior e inferior
    final margin = (maxVal - minVal) * 0.1;
    maxVal += margin;
    minVal -= margin;

    final paintLine = Paint()
      ..color = Colors.blueAccent.withOpacity(0.8)
      ..strokeWidth = 1.0
      ..style = PaintingStyle.stroke;

    for (final price in orderLines) {
      if (price < minVal || price > maxVal) continue; // Out of bounds

      final y =
          size.height - ((price - minVal) / (maxVal - minVal)) * size.height;

      _drawDashedLine(canvas, Offset(0, y), Offset(size.width, y), paintLine);

      // Dibujar etiqueta
      final textSpan = TextSpan(
        text: ' ORD ${price.toStringAsFixed(4)}',
        style: const TextStyle(
          color: Colors.blueAccent,
          fontSize: 10,
          fontWeight: FontWeight.bold,
          backgroundColor: Colors.black45,
        ),
      );
      final textPainter = TextPainter(
        text: textSpan,
        textDirection: TextDirection.ltr,
      );
      textPainter.layout();
      textPainter.paint(
        canvas,
        Offset(size.width - textPainter.width - 60, y - 14),
      );
    }
  }

  void _drawDashedLine(Canvas canvas, Offset p1, Offset p2, Paint paint) {
    const int dashWidth = 5;
    const int dashSpace = 5;
    double startX = p1.dx;
    while (startX < p2.dx) {
      canvas.drawLine(
        Offset(startX, p1.dy),
        Offset(startX + dashWidth, p1.dy),
        paint,
      );
      startX += dashWidth + dashSpace;
    }
  }

  @override
  bool shouldRepaint(covariant _OrderLinesPainter oldDelegate) {
    return oldDelegate.orderLines != orderLines ||
        oldDelegate.candles != candles;
  }
}
