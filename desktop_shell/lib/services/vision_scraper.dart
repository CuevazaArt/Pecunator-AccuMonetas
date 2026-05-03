import 'dart:isolate';
import 'dart:collection';
import 'package:archive/archive.dart';
import 'package:http/http.dart' as http;
import 'package:candlesticks/candlesticks.dart';
import 'package:flutter/foundation.dart';
import '../utils/histogram_storage.dart';

/// Message types sent from the background isolate to the main isolate.
class _IsolateMsg {
  final String type; // 'status', 'log', 'insert', 'done', 'error'
  final String text;
  final String? symbol;
  final String? interval;
  final List<Map<String, dynamic>>? candleData;

  _IsolateMsg(this.type, this.text, {this.symbol, this.interval, this.candleData});
}

/// Parameters sent to the background isolate.
class _IsolateParams {
  final SendPort sendPort;
  final List<String> symbols;
  final List<String> intervals;

  _IsolateParams(this.sendPort, this.symbols, this.intervals);
}

class VisionScraperService {
  static final VisionScraperService instance = VisionScraperService._internal();

  VisionScraperService._internal();

  final ValueNotifier<bool> isRunningNotifier = ValueNotifier<bool>(false);
  final ValueNotifier<String> statusNotifier = ValueNotifier<String>('Inactivo');

  Isolate? _isolate;
  ReceivePort? _receivePort;

  void startColdSync(List<String> symbols, List<String> intervals) async {
    if (isRunningNotifier.value) return;

    isRunningNotifier.value = true;
    statusNotifier.value = 'Iniciando Colección en hilo separado...';

    _receivePort = ReceivePort();
    final params = _IsolateParams(_receivePort!.sendPort, symbols, intervals);

    try {
      _isolate = await Isolate.spawn(_isolateWorker, params);
    } catch (e) {
      statusNotifier.value = 'Error al crear isolate: $e';
      isRunningNotifier.value = false;
      return;
    }

    _receivePort!.listen((dynamic rawMsg) async {
      if (rawMsg is _IsolateMsg) {
        switch (rawMsg.type) {
          case 'status':
            statusNotifier.value = rawMsg.text;
            break;
          case 'log':
            print('[VisionScraper] ${rawMsg.text}');
            break;
          case 'insert':
            // The insert still has to run on the main isolate because
            // sqlite3 FFI handles aren't transferable. But the heavy
            // ZIP+CSV parsing was already done in the background.
            if (rawMsg.symbol != null && rawMsg.interval != null && rawMsg.candleData != null) {
              final candles = rawMsg.candleData!.map((m) => Candle(
                date: DateTime.fromMillisecondsSinceEpoch(m['ts'] as int, isUtc: true),
                open: m['o'] as double,
                high: m['h'] as double,
                low: m['l'] as double,
                close: m['c'] as double,
                volume: m['v'] as double,
              )).toList();
              try {
                await HistogramStorage.instance.insertCandles(rawMsg.symbol!, rawMsg.interval!, candles);
                print('[VisionScraper] INSERCIÓN OK: ${candles.length} velas para ${rawMsg.symbol} ${rawMsg.interval}');
              } catch (e) {
                print('[VisionScraper] INSERT ERROR: $e');
              }
              // Yield to UI thread after DB write
              await Future.delayed(const Duration(milliseconds: 50));
            }
            break;
          case 'done':
            statusNotifier.value = rawMsg.text;
            _cleanup();
            break;
          case 'error':
            statusNotifier.value = rawMsg.text;
            print('[VisionScraper] ERROR: ${rawMsg.text}');
            break;
        }
      }
    });
  }

  /// The actual work runs entirely in a separate isolate.
  /// ZIP download, decompression, and CSV parsing happen here — 
  /// zero impact on Flutter's UI thread.
  static void _isolateWorker(_IsolateParams params) async {
    final port = params.sendPort;
    final symbols = params.symbols;
    final intervals = params.intervals;
    final now = DateTime.now();
    const startYear = 2017;
    const startMonth = 8;
    int completedSymbols = 0;

    // We can't access HistogramStorage from here (FFI not transferable),
    // so we'll fetch the existing months via a lightweight HTTP check,
    // or skip the check and let the main isolate handle duplicates via
    // INSERT OR REPLACE. But to avoid unnecessary downloads, we'll
    // query existing months on the main isolate first.
    // 
    // Actually, since we can't easily do that without a back-channel,
    // the simpler approach is: the isolate does HTTP+ZIP+CSV, sends
    // parsed candle data back to the main isolate for DB insert.
    // The main isolate's insertCandles uses INSERT OR REPLACE, so
    // duplicates are safe.

    final queue = Queue<String>.from(symbols);

    while (queue.isNotEmpty) {
      final symbol = queue.removeFirst();

      for (final interval in intervals) {
        int consecutive404s = 0;

        for (int y = now.year; y >= startYear; y--) {
          int maxMonth = (y == now.year) ? now.month : 12;
          int minMonth = (y == startYear) ? startMonth : 1;

          for (int m = maxMonth; m >= minMonth; m--) {
            final monthStr = m.toString().padLeft(2, '0');
            final targetMonthStr = '$y-$monthStr';

            final logMsg = '[W1] Recuperando: $symbol ($interval) $targetMonthStr...';
            port.send(_IsolateMsg('status', logMsg));

            final url = 'https://data.binance.vision/data/spot/monthly/klines/$symbol/$interval/$symbol-$interval-$y-$monthStr.zip';

            try {
              final response = await http.get(Uri.parse(url));
              if (response.statusCode == 200) {
                consecutive404s = 0;
                final archive = ZipDecoder().decodeBytes(response.bodyBytes);

                if (archive.isNotEmpty) {
                  final file = archive.first;
                  final csvString = String.fromCharCodes(file.content);
                  final lines = csvString.split('\n');

                  final candleData = <Map<String, dynamic>>[];
                  for (var line in lines) {
                    if (line.trim().isEmpty) continue;
                    final parts = line.split(',');
                    if (parts.length >= 6) {
                      final ts = int.tryParse(parts[0]);
                      final o = double.tryParse(parts[1]);
                      final h = double.tryParse(parts[2]);
                      final l = double.tryParse(parts[3]);
                      final c = double.tryParse(parts[4]);
                      final v = double.tryParse(parts[5]);

                      if (ts != null && o != null && h != null && l != null && c != null && v != null) {
                        candleData.add({'ts': ts, 'o': o, 'h': h, 'l': l, 'c': c, 'v': v});
                      }
                    }
                  }
                  if (candleData.isNotEmpty) {
                    port.send(_IsolateMsg('insert',
                      'INSERT ${candleData.length} candles $symbol $interval ($targetMonthStr)',
                      symbol: symbol,
                      interval: interval,
                      candleData: candleData,
                    ));
                    port.send(_IsolateMsg('log',
                      'W1 PARSED: ${candleData.length} velas $symbol $interval ($targetMonthStr)'));
                  }
                }
              } else if (response.statusCode == 404) {
                consecutive404s++;
                port.send(_IsolateMsg('log',
                  'W1 404: $symbol $targetMonthStr (Consecutivos: $consecutive404s)'));
                if (consecutive404s > 3) {
                  port.send(_IsolateMsg('log',
                    'W1 Límite 404. Deteniendo $symbol $interval.'));
                  break;
                }
              } else if (response.statusCode == 429) {
                port.send(_IsolateMsg('error',
                  'FUSIBLE ACTIVADO: 429 LIMIT EXCEEDED. Motor detenido.'));
                port.send(_IsolateMsg('done', 'Abortado por 429.'));
                return;
              }
            } catch (e) {
              port.send(_IsolateMsg('log', 'ERROR red $symbol: $e'));
            }

            // Delay between fetches — isolate won't block UI thread
            await Future.delayed(const Duration(milliseconds: 2000));
          }
          if (consecutive404s > 3) break;
        }
      }
      completedSymbols++;
    }

    port.send(_IsolateMsg('done',
      'Auditoría 100% Completada. Símbolos: $completedSymbols'));
  }

  void _cleanup() {
    _isolate?.kill(priority: Isolate.immediate);
    _isolate = null;
    _receivePort?.close();
    _receivePort = null;
    isRunningNotifier.value = false;
  }

  void stop() {
    if (isRunningNotifier.value) {
      statusNotifier.value = 'Abortando hilo...';
      _cleanup();
      statusNotifier.value = 'Abortado por el usuario.';
    }
  }
}
