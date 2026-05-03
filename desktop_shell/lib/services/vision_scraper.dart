import 'dart:isolate';
import 'package:archive/archive.dart';
import 'package:http/http.dart' as http;
import 'package:candlesticks/candlesticks.dart';
import 'package:flutter/foundation.dart';
import '../utils/histogram_storage.dart';

// ============================================================================
// VisionScraper — Background data ingestion via Binance Vision ZIPs
//
// DESIGN PRINCIPLES:
// 1. ALL heavy work (HTTP, ZIP, CSV) runs in a BACKGROUND Isolate.
// 2. Only the SQLite INSERT runs on the main isolate (FFI limitation).
// 3. Pacing: 1 download per hour during normal operation.
//    The historical data doesn't change — there is no rush.
// 4. Only activated manually from the Library page.
// ============================================================================

/// Message types sent from background isolate → main isolate.
class _ScrapeResult {
  final String type; // 'status', 'log', 'insert', 'done', 'error', 'wait'
  final String text;
  final String? symbol;
  final String? interval;
  final List<Map<String, dynamic>>? candleData;

  _ScrapeResult(this.type, this.text,
      {this.symbol, this.interval, this.candleData});
}

/// Parameters sent to the background isolate.
class _ScrapeParams {
  final SendPort sendPort;
  final List<String> symbols;
  final List<String> intervals;
  final int delayBetweenDownloadsMs;

  _ScrapeParams(this.sendPort, this.symbols, this.intervals,
      this.delayBetweenDownloadsMs);
}

class VisionScraperService {
  static final VisionScraperService instance =
      VisionScraperService._internal();

  VisionScraperService._internal();

  final ValueNotifier<bool> isRunningNotifier = ValueNotifier<bool>(false);
  final ValueNotifier<String> statusNotifier =
      ValueNotifier<String>('Inactivo');

  Isolate? _isolate;
  ReceivePort? _receivePort;

  /// Default: 1 hour between downloads. Calm, patient, no rush.
  static const int defaultDelayMs = 3600000; // 1 hour

  /// Quick mode for first-time setup: 10s between downloads.
  static const int quickDelayMs = 10000; // 10 seconds

  void startColdSync(List<String> symbols, List<String> intervals,
      {bool quickMode = false}) async {
    if (isRunningNotifier.value) return;

    isRunningNotifier.value = true;
    final delayMs = quickMode ? quickDelayMs : defaultDelayMs;
    final modeLabel = quickMode ? 'Rápido (10s)' : 'Paciente (1/hora)';
    statusNotifier.value = 'Iniciando en modo $modeLabel...';

    _receivePort = ReceivePort();
    final params =
        _ScrapeParams(_receivePort!.sendPort, symbols, intervals, delayMs);

    try {
      _isolate = await Isolate.spawn(_isolateWorker, params);
    } catch (e) {
      statusNotifier.value = 'Error al crear isolate: $e';
      isRunningNotifier.value = false;
      return;
    }

    _receivePort!.listen((dynamic rawMsg) async {
      if (rawMsg is _ScrapeResult) {
        switch (rawMsg.type) {
          case 'status':
            statusNotifier.value = rawMsg.text;
            break;
          case 'log':
            debugPrint('[VisionScraper] ${rawMsg.text}');
            break;
          case 'insert':
            if (rawMsg.symbol != null &&
                rawMsg.interval != null &&
                rawMsg.candleData != null) {
              final candles = rawMsg.candleData!
                  .map((m) => Candle(
                        date: DateTime.fromMillisecondsSinceEpoch(
                            m['ts'] as int,
                            isUtc: true),
                        open: m['o'] as double,
                        high: m['h'] as double,
                        low: m['l'] as double,
                        close: m['c'] as double,
                        volume: m['v'] as double,
                      ))
                  .toList();
              try {
                await HistogramStorage.instance
                    .insertCandles(rawMsg.symbol!, rawMsg.interval!, candles);
                debugPrint(
                    '[VisionScraper] INSERT OK: ${candles.length} velas → '
                    '${rawMsg.symbol} ${rawMsg.interval}');
              } catch (e) {
                debugPrint('[VisionScraper] INSERT ERROR: $e');
              }
              // Micro-yield after DB write so the UI thread can paint
              await Future.delayed(const Duration(milliseconds: 20));
            }
            break;
          case 'done':
            statusNotifier.value = rawMsg.text;
            _cleanup();
            break;
          case 'error':
            statusNotifier.value = rawMsg.text;
            debugPrint('[VisionScraper] ERROR: ${rawMsg.text}');
            break;
        }
      }
    });
  }

  /// The actual work runs entirely in a separate isolate.
  /// Zero impact on Flutter's UI thread.
  static void _isolateWorker(_ScrapeParams params) async {
    final port = params.sendPort;
    final symbols = params.symbols;
    final intervals = params.intervals;
    final delayMs = params.delayBetweenDownloadsMs;
    final now = DateTime.now();
    const startYear = 2017;
    const startMonth = 8; // Binance inception

    int downloaded = 0;
    int skipped = 0;
    int totalSymbols = symbols.length;
    int completedSymbols = 0;

    for (final symbol in symbols) {
      for (final interval in intervals) {
        int consecutive404s = 0;

        for (int y = now.year; y >= startYear; y--) {
          int maxMonth = (y == now.year) ? now.month : 12;
          int minMonth = (y == startYear) ? startMonth : 1;

          for (int m = maxMonth; m >= minMonth; m--) {
            final monthStr = m.toString().padLeft(2, '0');
            final targetMonthStr = '$y-$monthStr';

            port.send(_ScrapeResult('status',
                '[$symbol $interval] $targetMonthStr · ↓$downloaded ⊘$skipped · '
                '${completedSymbols + 1}/$totalSymbols'));

            final url =
                'https://data.binance.vision/data/spot/monthly/klines/'
                '$symbol/$interval/$symbol-$interval-$y-$monthStr.zip';

            try {
              final response = await http.get(Uri.parse(url));

              if (response.statusCode == 200) {
                consecutive404s = 0;
                final archive =
                    ZipDecoder().decodeBytes(response.bodyBytes);

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

                      if (ts != null &&
                          o != null &&
                          h != null &&
                          l != null &&
                          c != null &&
                          v != null) {
                        candleData.add({
                          'ts': ts, 'o': o, 'h': h,
                          'l': l, 'c': c, 'v': v,
                        });
                      }
                    }
                  }
                  if (candleData.isNotEmpty) {
                    port.send(_ScrapeResult(
                      'insert',
                      '${candleData.length} velas',
                      symbol: symbol,
                      interval: interval,
                      candleData: candleData,
                    ));
                    downloaded++;
                    port.send(_ScrapeResult('log',
                        'PARSED: ${candleData.length} velas → '
                        '$symbol $interval ($targetMonthStr)'));
                  }
                }
              } else if (response.statusCode == 404) {
                consecutive404s++;
                skipped++;
                if (consecutive404s > 3) {
                  port.send(_ScrapeResult('log',
                      '404 x$consecutive404s → saltando $symbol $interval'));
                  break;
                }
              } else if (response.statusCode == 429) {
                port.send(_ScrapeResult('error',
                    'FUSIBLE: 429 Rate Limit. Motor detenido.'));
                port.send(_ScrapeResult('done',
                    'Abortado por 429. ↓$downloaded total.'));
                return;
              }
            } catch (e) {
              port.send(
                  _ScrapeResult('log', 'ERROR red $symbol: $e'));
            }

            // ── Patience delay ──
            // 1 hour in normal mode, 10s in quick mode.
            // This isolate sleeps without affecting the UI at all.
            if (delayMs > 1000) {
              // Show countdown for long waits
              final waitMin = delayMs ~/ 60000;
              port.send(_ScrapeResult('status',
                  '💤 Esperando ${waitMin}min antes del siguiente... '
                  '(↓$downloaded ⊘$skipped)'));
            }
            await Future.delayed(Duration(milliseconds: delayMs));
          }
          if (consecutive404s > 3) break;
        }
      }
      completedSymbols++;
    }

    port.send(_ScrapeResult('done',
        '✅ Completado. ↓$downloaded descargas, ⊘$skipped omitidos. '
        'Símbolos: $completedSymbols'));
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
      statusNotifier.value = 'Detenido por el usuario.';
      _cleanup();
    }
  }
}
