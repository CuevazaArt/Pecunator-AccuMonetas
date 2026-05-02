import 'dart:io';
import 'package:candlesticks/candlesticks.dart';
import 'package:path/path.dart' as p;
import 'package:sqlite3/sqlite3.dart';
import 'package:path_provider/path_provider.dart';

/// Singleton that manages the `histogram_candles` SQLite table.
class HistogramStorage {
  HistogramStorage._internal();

  static final HistogramStorage instance = HistogramStorage._internal();

  // Path to the SQLite file.
  String? _dbPath;

  Future<void> _init() async {
    if (_dbPath != null) return;
    final dir = await getApplicationSupportDirectory();
    final dataDir = p.join(dir.path, 'runtime', 'data');
    await Directory(dataDir).create(recursive: true);
    final path = p.join(dataDir, 'histogram_candles.sqlite');
    _dbPath = path;

    final db = sqlite3.open(_dbPath!);
    db.execute('''
      CREATE TABLE IF NOT EXISTS histogram_candles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol TEXT NOT NULL,
        interval TEXT NOT NULL,
        ts_utc TEXT NOT NULL,
        open REAL NOT NULL,
        high REAL NOT NULL,
        low REAL NOT NULL,
        close REAL NOT NULL,
        volume REAL NOT NULL,
        UNIQUE(symbol, interval, ts_utc)
      );
    ''');
    db.dispose();
  }

  /// Insert a candle for the given symbol/interval.
  Future<void> insertCandle(String symbol, String interval, Candle candle) async {
    await insertCandles(symbol, interval, [candle]);
  }

  /// Insert multiple candles in a batch.
  Future<void> insertCandles(String symbol, String interval, List<Candle> candles) async {
    if (candles.isEmpty) return;
    await _init();
    final db = sqlite3.open(_dbPath!);
    final stmt = db.prepare('''
      INSERT OR REPLACE INTO histogram_candles
        (symbol, interval, ts_utc, open, high, low, close, volume)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''');
    
    db.execute('BEGIN TRANSACTION');
    try {
      for (final candle in candles) {
        stmt.execute([
          symbol,
          interval,
          candle.date.toUtc().toIso8601String(),
          candle.open,
          candle.high,
          candle.low,
          candle.close,
          candle.volume,
        ]);
      }
      db.execute('COMMIT');
    } catch (e) {
      db.execute('ROLLBACK');
      rethrow;
    } finally {
      stmt.dispose();
      db.dispose();
    }
  }

  /// Retrieve all candles for a symbol/interval ordered by timestamp.
  Future<List<Candle>> getCandles(String symbol, String interval) async {
    await _init();
    final db = sqlite3.open(_dbPath!);
    final result = db.select('''
      SELECT ts_utc, open, high, low, close, volume
      FROM histogram_candles
      WHERE symbol = ? AND interval = ?
      ORDER BY ts_utc ASC
    ''', [symbol, interval]);

    final candles = result.map((row) => Candle(
          date: DateTime.parse(row['ts_utc'] as String).toUtc(),
          open: (row['open'] as num).toDouble(),
          high: (row['high'] as num).toDouble(),
          low: (row['low'] as num).toDouble(),
          close: (row['close'] as num).toDouble(),
          volume: (row['volume'] as num).toDouble(),
        )).toList();
    db.dispose();
    return candles;
  }

  /// Retrieve summary statistics for all symbols and intervals
  Future<List<Map<String, dynamic>>> getLibraryStats() async {
    await _init();
    final db = sqlite3.open(_dbPath!);
    try {
      final result = db.select('''
        SELECT symbol, interval, COUNT(*) as count, MIN(ts_utc) as min_ts, MAX(ts_utc) as max_ts
        FROM histogram_candles
        GROUP BY symbol, interval
        ORDER BY symbol ASC, interval ASC
      ''');
      return result.map((r) => Map<String, dynamic>.from(r)).toList();
    } finally {
      db.dispose();
    }
  }
}
