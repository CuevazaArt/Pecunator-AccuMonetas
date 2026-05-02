import 'package:flutter/material.dart';
import '../utils/histogram_storage.dart';

class LibraryManagerPage extends StatefulWidget {
  const LibraryManagerPage({super.key});

  @override
  State<LibraryManagerPage> createState() => _LibraryManagerPageState();
}

class _LibraryManagerPageState extends State<LibraryManagerPage> {
  List<Map<String, dynamic>> _stats = [];
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _loadStats();
  }

  Future<void> _loadStats() async {
    setState(() => _loading = true);
    try {
      final stats = await HistogramStorage.instance.getLibraryStats();
      setState(() {
        _stats = stats;
        _loading = false;
      });
    } catch (e) {
      print('Error loading library stats: $e');
      setState(() => _loading = false);
    }
  }

  int _getIntervalMinutes(String interval) {
    if (interval.endsWith('m')) return int.tryParse(interval.replaceAll('m', '')) ?? 1;
    if (interval.endsWith('h')) return (int.tryParse(interval.replaceAll('h', '')) ?? 1) * 60;
    if (interval.endsWith('d')) return (int.tryParse(interval.replaceAll('d', '')) ?? 1) * 1440;
    return 1;
  }

  String _analyzeQuality(Map<String, dynamic> row) {
    final minTs = DateTime.tryParse(row['min_ts'] ?? '');
    final maxTs = DateTime.tryParse(row['max_ts'] ?? '');
    final int count = row['count'] ?? 0;
    final interval = row['interval'] ?? '1m';

    if (minTs == null || maxTs == null) return 'Sin datos';

    final durationMinutes = maxTs.difference(minTs).inMinutes;
    final intervalMinutes = _getIntervalMinutes(interval);

    if (intervalMinutes == 0) return 'Error de formato';

    final expectedBars = (durationMinutes / intervalMinutes).floor() + 1;
    
    if (count < expectedBars) {
      final missing = expectedBars - count;
      return '⚠️ Faltan ~$missing velas (Gaps)';
    } else if (count > expectedBars) {
      return '⚠️ Posibles duplicados/solapamientos';
    }
    return '✅ Íntegro';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Biblioteca Histórica SQLite'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refrescar índice',
            onPressed: _loadStats,
          )
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _stats.isEmpty
              ? const Center(child: Text('La biblioteca SQLite está vacía.', style: TextStyle(color: Colors.grey)))
              : SingleChildScrollView(
                  scrollDirection: Axis.vertical,
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: DataTable(
                      headingRowColor: WidgetStateProperty.all(Colors.black45),
                      columns: const [
                        DataColumn(label: Text('Símbolo')),
                        DataColumn(label: Text('Temporalidad')),
                        DataColumn(label: Text('Registros (Velas)')),
                        DataColumn(label: Text('Desde (Min)')),
                        DataColumn(label: Text('Hasta (Max)')),
                        DataColumn(label: Text('Calidad / Detalles')),
                      ],
                      rows: _stats.map((row) {
                        final quality = _analyzeQuality(row);
                        final isDefective = quality.contains('⚠️');
                        return DataRow(
                          cells: [
                            DataCell(Text(row['symbol'].toString(), style: const TextStyle(fontWeight: FontWeight.bold))),
                            DataCell(Text(row['interval'].toString())),
                            DataCell(Text(row['count'].toString())),
                            DataCell(Text(row['min_ts'].toString().split('.').first)),
                            DataCell(Text(row['max_ts'].toString().split('.').first)),
                            DataCell(
                              Text(
                                quality,
                                style: TextStyle(
                                  color: isDefective ? Colors.orangeAccent : Colors.greenAccent,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                            ),
                          ],
                        );
                      }).toList(),
                    ),
                  ),
                ),
    );
  }
}
