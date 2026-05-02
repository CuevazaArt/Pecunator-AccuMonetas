import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:candlesticks/candlesticks.dart';
import '../api_client.dart';
import '../utils/histogram_storage.dart';

import 'package:flutter/foundation.dart';

class HistoryScraperService {
  static final HistoryScraperService instance = HistoryScraperService._internal();

  HistoryScraperService._internal();

  EngineApi? api;
  bool _isRunningLoop = false;
  bool _isRunningTick = false;

  final ValueNotifier<String> currentJobNotifier = ValueNotifier<String>('Inactivo');

  final ValueNotifier<int> concurrencyNotifier = ValueNotifier<int>(1);
  final ValueNotifier<int> delayMsNotifier = ValueNotifier<int>(1000);

  // Prioritized symbols by market dominance (top 50)
  final List<String> symbols = [
    'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
    'DOGEUSDT', 'ADAUSDT', 'TRXUSDT', 'AVAXUSDT', 'DOTUSDT',
    'LINKUSDT', 'TONUSDT', 'SHIBUSDT', 'LTCUSDT', 'BCHUSDT',
    'NEARUSDT', 'APTUSDT', 'ICPUSDT', 'UNIUSDT', 'XLMUSDT',
    'INJUSDT', 'ARBUSDT', 'OPUSDT', 'RENDERUSDT', 'FILUSDT',
    'MNTUSDT', 'ETCUSDT', 'HBARUSDT', 'VETUSDT', 'PEPEUSDT',
    // Next 20 symbols for intensive testing
    'STXUSDT', 'TAOUSDT', 'FETUSDT', 'IMXUSDT', 'SUIUSDT',
    'GRTUSDT', 'RNDRUSDT', 'WIFUSDT', 'THETAUSDT', 'SEIUSDT',
    'AAVEUSDT', 'EGLDUSDT', 'QNTUSDT', 'MKRUSDT', 'FLOKIUSDT',
    'TIAUSDT', 'FTMUSDT', 'SANDUSDT', 'GALAUSDT', 'CHZUSDT'
  ];

  // Prioritized intervals (standard highest to 1m)
  final List<String> intervals = ['1M', '1w', '1d', '4h', '1h', '30m', '1m'];

  bool isEnabled = false;

  void start() {
    if (_isRunningLoop) return;
    _isRunningLoop = true;
    _runLoop();
  }

  void stop() {
    _isRunningLoop = false;
  }

  void _panicShutdown(String reason) {
    print('EMERGENCIA SCRAPER: $reason');
    isEnabled = false;
    concurrencyNotifier.value = 0;
    currentJobNotifier.value = '⚠️ BLOQUEO: Limite API / Ban';
    _isRunningLoop = false;
  }

  Future<void> _runLoop() async {
    while (_isRunningLoop) {
      if (!isEnabled) {
        if (!currentJobNotifier.value.contains('Pausing')) {
          currentJobNotifier.value = 'Inactivo';
        }
        await Future.delayed(const Duration(seconds: 2));
        continue;
      }
      
      final didWork = await _tickOnce();
      
      if (didWork) {
        // Sleep a tiny bit to avoid locking
        await Future.delayed(const Duration(milliseconds: 200));
      } else {
        // No work found or weight limit hit
        currentJobNotifier.value = 'Inactivo';
        await Future.delayed(const Duration(seconds: 10));
      }
    }
  }

  Future<bool> _tickOnce() async {
    if (_isRunningTick) return false;
    _isRunningTick = true;
    bool didAnyWork = false;

    try {
      if (api == null) return false;
      // 1. Check API weight
      final snapshot = await api!.gatewaySnapshot();
      final usedStr = snapshot['used_weight_1m']?.toString();
      final limitStr = snapshot['weight_limit_1m']?.toString();

      if (usedStr != null && limitStr != null) {
        final used = double.tryParse(usedStr) ?? 0;
        final limitTxt = limitStr.split(' ').first; // "6000 (per minute)" -> "6000"
        final limit = double.tryParse(limitTxt) ?? 6000;

        if (limit > 0 && (used / limit) >= 0.8) {
          // Weight too high, skip this tick
          currentJobNotifier.value = 'Esperando peso API...';
          return false;
        }
      }

      // 2. Find the next jobs up to concurrency limit
      if (concurrencyNotifier.value <= 0) return false;
      
      final int maxThreads = concurrencyNotifier.value;
      List<Future<void>> workers = [];
      List<String> activeJobs = [];

      for (final symbol in symbols) {
        for (final interval in intervals) {
          if (workers.length >= maxThreads) {
            // Wait for all workers in this batch
            currentJobNotifier.value = activeJobs.join(' | ');
            await Future.wait(workers);
            didAnyWork = true;
            return didAnyWork;
          }
          
          // We don't want to run the same logic if we don't know if it needs download without awaiting,
          // but _processSymbolInterval returns a Future<bool>. We'll collect the futures.
          // Since we need to know if it actually did work to count towards the thread limit,
          // we should just dispatch N symbols to check concurrently.
          // To simplify, we will just spawn _processSymbolInterval and add to workers.
          workers.add(() async {
            final didWork = await _processSymbolInterval(symbol, interval);
            if (didWork) activeJobs.add('$symbol $interval');
          }());
        }
      }
      
      if (workers.isNotEmpty) {
        await Future.wait(workers);
        if (activeJobs.isNotEmpty) {
           currentJobNotifier.value = activeJobs.join(' | ');
           didAnyWork = true;
        }
      }
    } catch (e) {
      print('HistoryScraper error: $e');
    } finally {
      _isRunningTick = false;
    }
    return didAnyWork;
  }

  /// Returns true if an API call was made, false otherwise.
  Future<bool> _processSymbolInterval(String symbol, String interval) async {
    final localCandles = await HistogramStorage.instance.getCandles(symbol, interval);

    if (localCandles.isEmpty) {
      // Fetch initial batch (1000 candles ending at current time)
      currentJobNotifier.value = 'Descargando $symbol $interval';
      await _fetchAndStore(symbol, interval, null, null);
      currentJobNotifier.value = 'Inactivo';
      return true; // We made an API call
    } else {
      // Fetch forwards (catch up to present)
      final lastDate = localCandles.last.date;
      final now = DateTime.now().toUtc();
      
      // Calculate how much time has passed since the last candle
      Duration intervalDuration = const Duration(minutes: 1);
      if (interval == '30m') intervalDuration = const Duration(minutes: 30);
      if (interval == '1h') intervalDuration = const Duration(hours: 1);
      if (interval == '4h') intervalDuration = const Duration(hours: 4);
      if (interval == '1d') intervalDuration = const Duration(days: 1);
      if (interval == '1w') intervalDuration = const Duration(days: 7);
      if (interval == '1M') intervalDuration = const Duration(days: 30);

      if (now.difference(lastDate) > intervalDuration) {
        // We have a gap forward
        currentJobNotifier.value = 'Actualizando $symbol $interval';
        await _fetchAndStore(symbol, interval, lastDate.millisecondsSinceEpoch + 1, null);
        currentJobNotifier.value = 'Inactivo';
        return true;
      }

      // Fetch backwards (historical backfill)
      // We will ask for 1000 candles ending just before our oldest local candle.
      final firstDate = localCandles.first.date;
      final endTs = firstDate.millisecondsSinceEpoch - 1;
      
      // We need to know if we've reached the beginning of Binance history.
      // If the last fetch returned 0 candles backwards, we should mark it as "done".
      // We can check if the first local candle is older than Binance inception (e.g., 2017)
      // For now, if we fetch backwards and get 0 candles, we can just insert a dummy candle 
      // or keep a separate state to remember we reached the start.
      // A simple trick: if we get 0 candles backwards, we won't insert anything, and next tick we might spam.
      // To prevent spam, we can just rely on the fact that if we get 0 candles, we can insert a fake candle at 0 TS,
      // but let's just use SharedPreferences or a simple memory set to track completed backwards syncs.
      if (!_backwardsCompleted.contains('${symbol}_$interval')) {
        currentJobNotifier.value = 'Descargando histórico viejo $symbol $interval';
        final fetchedCount = await _fetchAndStore(symbol, interval, null, endTs);
        currentJobNotifier.value = 'Inactivo';
        if (fetchedCount == 0) {
          _backwardsCompleted.add('${symbol}_$interval');
        }
        return true;
      }
    }
    return false; // No API calls needed for this pair
  }

  final Set<String> _backwardsCompleted = {};

  DateTime _nextAllowedRequestTime = DateTime.now();

  Future<void> _enforceDelay() async {
    if (delayMsNotifier.value <= 0) return;
    
    final delay = Duration(milliseconds: delayMsNotifier.value);
    DateTime waitTarget;
    
    final now = DateTime.now();
    if (_nextAllowedRequestTime.isBefore(now)) {
      _nextAllowedRequestTime = now.add(delay);
      return; // No wait needed
    } else {
      waitTarget = _nextAllowedRequestTime;
      _nextAllowedRequestTime = _nextAllowedRequestTime.add(delay);
    }

    final toWait = waitTarget.difference(DateTime.now());
    if (toWait.isNegative) return;
    await Future.delayed(toWait);
  }

  Future<int> _fetchAndStore(String symbol, String interval, int? startTime, int? endTime) async {
    try {
      await _enforceDelay();

      String callExpr = "get_klines(symbol='$symbol', interval='$interval', limit=1000";
      if (startTime != null) callExpr += ", startTime=$startTime";
      if (endTime != null) callExpr += ", endTime=$endTime";
      callExpr += ")";

      final res = await api!.sandboxRestQuery(
        callExpression: callExpr,
        limit: 1000,
      );

      if (res.containsKey('error')) {
        final errStr = res['error'].toString().toLowerCase();
        print('Scraper API Error: $errStr');
        
        if (errStr.contains('429') || 
            errStr.contains('418') || 
            errStr.contains('limit') || 
            errStr.contains('banned') || 
            errStr.contains('too many requests') || 
            errStr.contains('weight') ||
            errStr.contains('ip')) {
          _panicShutdown(errStr);
        }
        return 0;
      }

      final List data = res['response'] ?? [];
      final List<Candle> parsed = [];
      for (final kline in data) {
        parsed.add(Candle(
          date: DateTime.fromMillisecondsSinceEpoch(kline[0]),
          open: double.parse(kline[1].toString()),
          high: double.parse(kline[2].toString()),
          low: double.parse(kline[3].toString()),
          close: double.parse(kline[4].toString()),
          volume: double.parse(kline[5].toString()),
        ));
      }

      if (parsed.isNotEmpty) {
        await HistogramStorage.instance.insertCandles(symbol, interval, parsed);
        print('Scraper OK: +${parsed.length} velas para $symbol $interval');
        return parsed.length;
      }
      return 0;
    } catch (e) {
      print('Scraper error on $symbol $interval: $e');
      return 0;
    }
  }
}
