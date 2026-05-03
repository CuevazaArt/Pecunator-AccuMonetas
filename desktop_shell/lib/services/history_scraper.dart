import 'dart:async';
import 'package:candlesticks/candlesticks.dart';
import '../api_client.dart';
import '../utils/histogram_storage.dart';

import 'package:flutter/foundation.dart';

class HistoryScraperService {
  // ============================================================================
  // ⚠️ PRECAUCIÓN CRÍTICA: INCIDENTE DE BANEO (02/MAYO/2026) ⚠️
  // NUNCA REACTIVAR EL POLLING MASIVO VIA REST API PARA MULTIPLES SIMBOLOS.
  // El intento de descargar 100 símbolos usando peticiones `get_klines` por 
  // REST API consumió el Peso de API (>6000/min) casi instantáneamente, 
  // provocando un BAN DURO de IP (APIError -1003).
  // 
  // DIRECTIVAS FUTURAS:
  // 1. La ingesta masiva histórica DEBE hacerse vía ZIP (VisionScraper).
  // 2. Las actualizaciones en vivo (Masha/Thusnelda) DEBEN usar WebSockets.
  // ============================================================================

  static final HistoryScraperService instance = HistoryScraperService._internal();

  HistoryScraperService._internal();

  EngineApi? api;
  bool _isRunningLoop = false;
  // ignore: unused_field
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
    // 50-100 symbols
    'STXUSDT', 'TAOUSDT', 'FETUSDT', 'IMXUSDT', 'SUIUSDT',
    'GRTUSDT', 'RNDRUSDT', 'WIFUSDT', 'THETAUSDT', 'SEIUSDT',
    'AAVEUSDT', 'EGLDUSDT', 'QNTUSDT', 'MKRUSDT', 'FLOKIUSDT',
    'TIAUSDT', 'FTMUSDT', 'SANDUSDT', 'GALAUSDT', 'CHZUSDT',
    // Next 50 added as requested
    'ATOMUSDT', 'LDOUSDT', 'ARUSDT', 'BOMEUSDT', 'ENJUSDT',
    'BONKUSDT', 'MANAUSDT', 'RUNEUSDT', 'ENAUSDT', 'ONDOUSDT',
    'WLDUSDT', 'JUPUSDT', 'STARKUSDT', 'XTZUSDT', 'KASUSDT',
    'AEROUSDT', 'CRVUSDT', 'DYDXUSDT', 'LUNCUSDT', 'BLURUSDT',
    'MAGICUSDT', 'CFXUSDT', 'ALGOUSDT', 'NEOUSDT', 'IOTAUSDT',
    'KAVAUSDT', 'TWTUSDT', 'CAKEUSDT', 'SNXUSDT', 'GMXUSDT',
    '1INCHUSDT', 'ZILUSDT', 'COMPUSDT', 'YFIUSDT', 'PENDLEUSDT',
    'BTTUSDT', 'GNOUSDT', 'SUSHIUSDT', 'ORDIUSDT', 'JTOUSDT',
    'PYTHUSDT', 'ENSUSDT', 'STRKUSDT', 'BIGTIMEUSDT', 'MEMEUSDT',
    'POLSXUSDT', 'SUPERUSDT', 'NFPUSDT', 'XECUSDT', 'GLMRUSDT'
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
    // ALTO: Shutting down all REST API requests per user request.
    return false;
  }

  /// Returns true if an API call was made, false otherwise.
  // ignore: unused_element
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
    }
    return false; // No API calls needed for this pair
  }

  // ignore: unused_field
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
