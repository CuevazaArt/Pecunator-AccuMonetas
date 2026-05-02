import 'package:flutter/material.dart';
import '../utils/histogram_storage.dart';

class LibraryManagerPage extends StatefulWidget {
  const LibraryManagerPage({super.key});

  @override
  State<LibraryManagerPage> createState() => _LibraryManagerPageState();
}

class _LibraryManagerPageState extends State<LibraryManagerPage> {
  List<Map<String, dynamic>> _stats = [];
  Map<String, List<Map<String, dynamic>>> _groupedStats = {};
  String _searchQuery = '';
  final _searchCtrl = TextEditingController();
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
      final grouped = <String, List<Map<String, dynamic>>>{};
      for (var row in stats) {
        grouped.putIfAbsent(row['symbol'].toString(), () => []).add(row);
      }
      setState(() {
        _stats = stats;
        _groupedStats = grouped;
        _loading = false;
      });
    } catch (e) {
      print('Error loading library stats: $e');
      setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _searchCtrl.dispose();
    super.dispose();
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
    // Filter symbols based on search query
    final filteredSymbols = _groupedStats.keys.where((symbol) {
      if (_searchQuery.isEmpty) return true;
      return symbol.toLowerCase().contains(_searchQuery.toLowerCase());
    }).toList();
    
    // Sort symbols alphabetically
    filteredSymbols.sort();

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
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(12.0),
            child: TextField(
              controller: _searchCtrl,
              decoration: InputDecoration(
                labelText: 'Buscar símbolo (Ej. BTCUSDT)',
                prefixIcon: const Icon(Icons.search, color: Colors.orangeAccent),
                suffixIcon: _searchQuery.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: () {
                          _searchCtrl.clear();
                          setState(() => _searchQuery = '');
                        },
                      )
                    : null,
                border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
                isDense: true,
              ),
              onChanged: (val) {
                setState(() => _searchQuery = val);
              },
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _stats.isEmpty
                    ? const Center(child: Text('La biblioteca SQLite está vacía.', style: TextStyle(color: Colors.grey)))
                    : ListView.builder(
                        itemCount: filteredSymbols.length,
                        itemBuilder: (context, index) {
                          final symbol = filteredSymbols[index];
                          final symbolRows = _groupedStats[symbol] ?? [];
                          
                          // Calculate totals for the symbol
                          int totalCandles = 0;
                          for (var row in symbolRows) {
                            totalCandles += (row['count'] as int?) ?? 0;
                          }

                          return Card(
                            margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                            child: ExpansionTile(
                              leading: const Icon(Icons.dataset, color: Colors.blueGrey),
                              title: Text(
                                symbol,
                                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                              ),
                              subtitle: Text(
                                '${symbolRows.length} temporalidades registradas | $totalCandles velas totales',
                                style: const TextStyle(fontSize: 12, color: Colors.grey),
                              ),
                              children: [
                                SingleChildScrollView(
                                  scrollDirection: Axis.horizontal,
                                  child: DataTable(
                                    headingRowColor: WidgetStateProperty.all(Colors.black45),
                                    columns: const [
                                      DataColumn(label: Text('Temporalidad')),
                                      DataColumn(label: Text('Registros (Velas)')),
                                      DataColumn(label: Text('Desde')),
                                      DataColumn(label: Text('Hasta')),
                                      DataColumn(label: Text('Calidad / Detalles')),
                                    ],
                                    rows: symbolRows.map((row) {
                                      final quality = _analyzeQuality(row);
                                      final isDefective = quality.contains('⚠️');
                                      return DataRow(
                                        cells: [
                                          DataCell(Text(row['interval'].toString(), style: const TextStyle(fontWeight: FontWeight.bold))),
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
                              ],
                            ),
                          );
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
