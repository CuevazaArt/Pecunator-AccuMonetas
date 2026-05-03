import 'package:flutter/material.dart';
import '../utils/histogram_storage.dart';
import '../services/history_scraper.dart';
import '../services/vision_scraper.dart';

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

  void _onVisionStateChanged() {
    setState(() {});
  }

  @override
  void initState() {
    super.initState();
    VisionScraperService.instance.isRunningNotifier.addListener(_onVisionStateChanged);
    VisionScraperService.instance.statusNotifier.addListener(_onVisionStateChanged);
    _loadStats();
  }

  @override
  void dispose() {
    VisionScraperService.instance.isRunningNotifier.removeListener(_onVisionStateChanged);
    VisionScraperService.instance.statusNotifier.removeListener(_onVisionStateChanged);
    _searchCtrl.dispose();
    super.dispose();
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
            icon: const Icon(Icons.menu_book),
            tooltip: 'Manual de Biblioteca',
            onPressed: () {
              showDialog(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Manual: Biblioteca SQLite', style: TextStyle(color: Colors.greenAccent)),
                  content: const SingleChildScrollView(
                    child: Text(
                      'Objetivo Estratégico:\n'
                      'Mantener un registro local hiper-veloz y gratuito de todo el comportamiento de precios.\n\n'
                      'Tácticas de Recolección:\n'
                      '1. Sincronización en Caliente (REST API): El Scraper de la Barra Superior mantiene vivas las velas actuales (minuto a minuto) utilizando la API regular.\n'
                      '2. Ingesta Masiva (Cold Sync): El botón de "Ingesta Masiva" descarga archivos ZIP públicos de Binance con meses completos de datos históricos. No gasta créditos API.\n\n'
                      'Mantenimiento:\n'
                      'Usa esta biblioteca para evaluar vacíos (Gaps) y presiona el botón Refresh para auditar la integridad de la base de datos.',
                    ),
                  ),
                  actions: [
                    TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Entendido')),
                  ],
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Refrescar índice',
            onPressed: _loadStats,
          )
        ],
      ),
      body: Column(
        children: [
          _buildVisionControlPanel(),
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

  Widget _buildVisionControlPanel() {
    final isRunning = VisionScraperService.instance.isRunningNotifier.value;
    final status = VisionScraperService.instance.statusNotifier.value;
    
    return Card(
      margin: const EdgeInsets.all(12),
      color: Colors.blueGrey.withOpacity(0.2),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              '📦 Ingesta Masiva (data.binance.vision)',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 6),
            const Text(
              'Descarga ZIPs mensuales sin consumir peso API REST.\n'
              '• Paciente: 1 descarga cada hora (recomendado, bajo impacto)\n'
              '• Rápido: 1 cada 10s (solo para setup inicial)',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
            const SizedBox(height: 12),
            if (isRunning) ...[
              Row(
                children: [
                  ElevatedButton.icon(
                    icon: const Icon(Icons.stop, size: 18),
                    label: const Text('Detener'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.red.withOpacity(0.3),
                    ),
                    onPressed: () => VisionScraperService.instance.stop(),
                  ),
                  const SizedBox(width: 12),
                  const SizedBox(
                    width: 16, height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      status,
                      style: const TextStyle(
                          color: Colors.amberAccent, fontSize: 12),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ] else ...[
              Row(
                children: [
                  ElevatedButton.icon(
                    icon: const Icon(Icons.hourglass_bottom, size: 18),
                    label: const Text('Paciente (1/hora)'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.green.withOpacity(0.3),
                    ),
                    onPressed: () {
                      final symbols = HistoryScraperService.instance.symbols;
                      VisionScraperService.instance.startColdSync(
                          symbols, ['1d', '4h', '1h', '1m']);
                    },
                  ),
                  const SizedBox(width: 8),
                  OutlinedButton.icon(
                    icon: const Icon(Icons.bolt, size: 18),
                    label: const Text('Rápido (10s)'),
                    onPressed: () {
                      final symbols = HistoryScraperService.instance.symbols;
                      VisionScraperService.instance.startColdSync(
                          symbols, ['1d', '4h', '1h', '1m'],
                          quickMode: true);
                    },
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      status,
                      style: const TextStyle(color: Colors.grey, fontSize: 12),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}

