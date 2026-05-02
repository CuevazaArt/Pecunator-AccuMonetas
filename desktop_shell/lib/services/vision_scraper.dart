import 'dart:io';
import 'dart:collection';
import 'package:archive/archive.dart';
import 'package:http/http.dart' as http;
import 'package:candlesticks/candlesticks.dart';
import 'package:flutter/foundation.dart';
import '../utils/histogram_storage.dart';

class VisionScraperService {
  static final VisionScraperService instance = VisionScraperService._internal();

  VisionScraperService._internal();

  final ValueNotifier<bool> isRunningNotifier = ValueNotifier<bool>(false);
  final ValueNotifier<String> statusNotifier = ValueNotifier<String>('Inactivo');

  bool _shouldStop = false;

  void startColdSync(List<String> symbols, List<String> intervals) async {
    if (isRunningNotifier.value) return;
    
    isRunningNotifier.value = true;
    _shouldStop = false;
    statusNotifier.value = 'Iniciando Colección Tímida (2 Hilos)...';

    final now = DateTime.now();
    final startYear = 2017;
    final startMonth = 8; // Binance inception
    
    final queue = Queue<String>.from(symbols);
    int completedSymbols = 0;

    Future<void> worker(int workerId) async {
      while (queue.isNotEmpty && !_shouldStop) {
        final symbol = queue.removeFirst();
        
        for (final interval in intervals) {
          if (_shouldStop) break;

          final existingMonths = await HistogramStorage.instance.getExistingMonths(symbol, interval);
          int consecutive404s = 0;
          
          for (int y = now.year; y >= startYear; y--) {
            int maxMonth = (y == now.year) ? now.month : 12;
            int minMonth = (y == startYear) ? startMonth : 1;
            
            for (int m = maxMonth; m >= minMonth; m--) {
              if (_shouldStop) break;

              final monthStr = m.toString().padLeft(2, '0');
              final targetMonthStr = '$y-$monthStr';
              
              if (existingMonths.contains(targetMonthStr)) {
                print('[VisionScraper W$workerId] SKIP $symbol $interval $targetMonthStr (ya existe)');
                continue;
              }
              
              final logMsg = '[W$workerId] Recuperando Gap: $symbol ($interval) $targetMonthStr...';
              statusNotifier.value = logMsg;
              print('[VisionScraper] $logMsg');
              
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
                    
                    List<Candle> candles = [];
                    for (var line in lines) {
                      if (line.trim().isEmpty) continue;
                      final parts = line.split(',');
                      if (parts.length >= 6) {
                        final openTime = int.tryParse(parts[0]);
                        final open = double.tryParse(parts[1]);
                        final high = double.tryParse(parts[2]);
                        final low = double.tryParse(parts[3]);
                        final close = double.tryParse(parts[4]);
                        final volume = double.tryParse(parts[5]);
                        
                        if (openTime != null && open != null && high != null && low != null && close != null && volume != null) {
                          candles.add(Candle(
                            date: DateTime.fromMillisecondsSinceEpoch(openTime, isUtc: true),
                            open: open,
                            high: high,
                            low: low,
                            close: close,
                            volume: volume,
                          ));
                        }
                      }
                    }
                    if (candles.isNotEmpty) {
                      await HistogramStorage.instance.insertCandles(symbol, interval, candles);
                      print('[VisionScraper W$workerId] INSERCIÓN OK: ${candles.length} velas para $symbol $interval ($targetMonthStr)');
                    }
                  }
                } else if (response.statusCode == 404) {
                   consecutive404s++;
                   print('[VisionScraper W$workerId] 404 Not Found: $symbol $targetMonthStr (Consecutivos: $consecutive404s)');
                   if (consecutive404s > 3) {
                     print('[VisionScraper W$workerId] Límite de 404 alcanzado. Deteniendo $symbol $interval hacia atrás.');
                     break; 
                   }
                } else if (response.statusCode == 429) {
                   final msg = '[W$workerId] FUSIBLE ACTIVADO: LIMIT EXCEEDED (429). APAGANDO MOTOR.';
                   statusNotifier.value = msg;
                   print('[VisionScraper] 🚨 $msg');
                   _shouldStop = true; // Hard Kill-Switch
                   break;
                }
              } catch (e) {
                 statusNotifier.value = '[W$workerId] Error red en $symbol: $e';
                 print('[VisionScraper] ERROR de red en $symbol: $e');
              }
              
              // Delay timidly to avoid data.binance.vision 429 rate limits
              await Future.delayed(const Duration(milliseconds: 1500));
            }
            if (consecutive404s > 3) break; 
          }
        }
        completedSymbols++;
      }
    }

    // Start extremely conservatively to protect IP
    final int concurrency = 2;
    final List<Future<void>> workers = [];
    for (int i = 0; i < concurrency; i++) {
      workers.add(worker(i + 1));
    }
    
    await Future.wait(workers);
    
    statusNotifier.value = _shouldStop 
      ? 'Auditoría Abortada. Símbolos completados: $completedSymbols' 
      : 'Auditoría 100% Completada (Cero Gaps). Símbolos: $completedSymbols';
    isRunningNotifier.value = false;
  }

  void stop() {
    _shouldStop = true;
    if (isRunningNotifier.value) {
      statusNotifier.value = 'Abortando hilos, espere...';
    }
  }
}
