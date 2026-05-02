import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:candlesticks/candlesticks.dart';

/// Volume histogram widget based on candle data.
class VolumeHistogram extends StatelessWidget {
  final List<Candle> candles;

  const VolumeHistogram({super.key, required this.candles});

  @override
  Widget build(BuildContext context) {
    if (candles.isEmpty) {
      return const Center(child: Text('Sin datos de volumen'));
    }

    // Normalize volume to 0-1 range
    final maxVol = candles.map((c) => c.volume).reduce((a, b) => a > b ? a : b);
    final barGroups = candles.asMap().entries.map((e) {
      final idx = e.key;
      final vol = e.value.volume / (maxVol == 0 ? 1 : maxVol);
      
      // Basic color logic: green if close > open, red otherwise
      final isUp = e.value.close >= e.value.open;
      final color = isUp ? Colors.green.withOpacity(0.5) : Colors.red.withOpacity(0.5);

      return BarChartGroupData(
        x: idx,
        barRods: [
          BarChartRodData(
            toY: vol,
            color: color,
            width: 4,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(2)),
          ),
        ],
      );
    }).toList();

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
      child: BarChart(
        BarChartData(
          alignment: BarChartAlignment.spaceBetween,
          barTouchData: BarTouchData(enabled: false),
          titlesData: const FlTitlesData(show: false),
          gridData: const FlGridData(show: false),
          borderData: FlBorderData(show: false),
          barGroups: barGroups,
          maxY: 1.1, // Leave a little room at the top
        ),
      ),
    );
  }
}
