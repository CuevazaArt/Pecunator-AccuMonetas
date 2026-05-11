import 'dart:async';
import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../api_client.dart';
import '../models/louise_models.dart';

class LouiseHubPage extends StatefulWidget {
  final String engineBase;

  const LouiseHubPage({super.key, required this.engineBase});

  @override
  State<LouiseHubPage> createState() => _LouiseHubPageState();
}

class _LouiseHubPageState extends State<LouiseHubPage> {
  late final EngineApi _api;
  Timer? _refreshTimer;

  List<BotMetrics> _bots = [];
  HubMetrics? _hubMetrics;
  WeightStatus? _weightStatus;
  RequestsStats? _requestsStats;
  List<WeightHistory> _weightHistory = [];

  bool _loading = false;
  String? _error;
  final List<double> _pnlHistory = [];

  @override
  void initState() {
    super.initState();
    _api = EngineApi(widget.engineBase);
    _loadData();
    _refreshTimer = Timer.periodic(const Duration(seconds: 5), (_) => _loadData());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _loadData() async {
    if (!mounted) return;
    try {
      setState(() => _error = null);

      final results = await Future.wait([
        _api.louiseBots().catchError((_) => <Map<String, dynamic>>[]),
        _api.louiseMetrics().catchError((_) => <String, dynamic>{}),
        _api.louiseWeightStatus().catchError((_) => <String, dynamic>{}),
        _api.louiseRequestsStats().catchError((_) => <String, dynamic>{}),
        _api.louiseWeightHistory().catchError((_) => <Map<String, dynamic>>[]),
      ]);

      if (!mounted) return;

      setState(() {
        _bots = (results[0] as List).map((b) => BotMetrics.fromJson(b as Map<String, dynamic>)).toList();
        _hubMetrics = (results[1] as Map<String, dynamic>).isNotEmpty ? HubMetrics.fromJson(results[1] as Map<String, dynamic>) : null;
        _weightStatus = (results[2] as Map<String, dynamic>).isNotEmpty ? WeightStatus.fromJson(results[2] as Map<String, dynamic>) : null;
        _requestsStats = (results[3] as Map<String, dynamic>).isNotEmpty ? RequestsStats.fromJson(results[3] as Map<String, dynamic>) : null;

        final histList = (results[4] as List).map((h) => WeightHistory.fromJson(h as Map<String, dynamic>)).toList();
        _weightHistory = histList;

        if (_hubMetrics != null && _pnlHistory.length < 100) {
          _pnlHistory.add(_hubMetrics!.hubPnlPercent);
        } else if (_pnlHistory.isNotEmpty) {
          _pnlHistory.removeAt(0);
          _pnlHistory.add(_hubMetrics!.hubPnlPercent);
        }
      });
    } catch (e) {
      if (mounted) setState(() => _error = 'Error: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return CustomScrollView(
      slivers: [
        // ── Hub Summary ────────────────────────────────────
        if (_hubMetrics != null)
          SliverToBoxAdapter(
            child: _buildHubSummary(),
          ),

        const SliverToBoxAdapter(child: SizedBox(height: 4)),

        // ── Charts Row (Weight + PNL History) ──────────────
        SliverToBoxAdapter(
          child: _buildChartsRow(),
        ),

        const SliverToBoxAdapter(child: SizedBox(height: 8)),

        // ── Telemetry Row (Weight Gauge + Requests) ───────
        SliverToBoxAdapter(
          child: _buildTelemetryRow(),
        ),

        const SliverToBoxAdapter(child: SizedBox(height: 8)),

        // ── Bot Details Grid ───────────────────────────────
        SliverToBoxAdapter(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Louise Bots (${_bots.length})',
                  style: Theme.of(context).textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
                ),
                ElevatedButton.icon(
                  onPressed: () => _showCreateBotDialog(),
                  icon: const Icon(Icons.add, size: 16),
                  label: const Text('Crear', style: TextStyle(fontSize: 12)),
                ),
              ],
            ),
          ),
        ),

        // ── Bot list ───────────────────────────────────────
        SliverList(
          delegate: SliverChildBuilderDelegate(
            (ctx, i) {
              if (i >= _bots.length) return null;
              return _buildBotCard(_bots[i]);
            },
            childCount: _bots.length,
          ),
        ),

        // ── Error message ──────────────────────────────────
        if (_error != null)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.red.withAlpha(25),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.redAccent.withAlpha(100)),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.warning_amber_rounded, color: Colors.redAccent, size: 20),
                    const SizedBox(width: 8),
                    Expanded(child: Text(_error!, style: const TextStyle(color: Colors.redAccent, fontSize: 12))),
                  ],
                ),
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildHubSummary() {
    final m = _hubMetrics!;
    final pnlColor = m.hubPnlPercent >= 0 ? Colors.greenAccent : Colors.redAccent;

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [Colors.blue.withAlpha(20), Colors.cyan.withAlpha(10)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.blue.withAlpha(100)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('📊 Hub Summary', style: Theme.of(context).textTheme.labelLarge?.copyWith(fontWeight: FontWeight.bold)),
              Chip(
                label: Text(
                  '${m.hubPnlPercent > 0 ? "🟢" : "🔴"} ${m.hubPnlPercent.toStringAsFixed(2)}%',
                  style: TextStyle(color: pnlColor, fontWeight: FontWeight.bold),
                ),
                backgroundColor: pnlColor.withAlpha(30),
              ),
            ],
          ),
          const SizedBox(height: 10),
          GridView.count(
            crossAxisCount: 4,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 1.2,
            children: [
              _summaryCard('Bots Activos', '${m.activeBots}', Colors.blueAccent),
              _summaryCard('Portfolio', '\$${m.totalPortfolio.toStringAsFixed(0)}', Colors.greenAccent),
              _summaryCard('Libre', '\$${m.totalFreeBalance.toStringAsFixed(0)}', Colors.orangeAccent),
              _summaryCard('PNL \$', '\$${m.totalUnrealizedPnl.toStringAsFixed(2)}', pnlColor),
            ],
          ),
        ],
      ),
    );
  }

  Widget _summaryCard(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: color.withAlpha(15),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: color.withAlpha(80)),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(label, style: const TextStyle(fontSize: 9, color: Colors.white70)),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: color)),
        ],
      ),
    );
  }

  Widget _buildChartsRow() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          Expanded(
            flex: 2,
            child: _buildWeightHistoryChart(),
          ),
          const SizedBox(width: 8),
          Expanded(
            flex: 2,
            child: _buildPnlHistoryChart(),
          ),
        ],
      ),
    );
  }

  Widget _buildWeightHistoryChart() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('⚡ API Weight (24h)', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          SizedBox(
            height: 140,
            child: _weightHistory.isEmpty
                ? const Center(child: CircularProgressIndicator(strokeWidth: 2))
                : LineChart(
                    LineChartData(
                      lineTouchData: LineTouchData(enabled: false),
                      gridData: const FlGridData(show: false),
                      titlesData: const FlTitlesData(show: false),
                      borderData: FlBorderData(show: false),
                      lineBarsData: [
                        LineChartBarData(
                          spots: _weightHistory.asMap().entries.map((e) => FlSpot(e.key.toDouble(), e.value.total.toDouble())).toList(),
                          isCurved: true,
                          gradient: const LinearGradient(colors: [Colors.blueAccent, Colors.cyanAccent]),
                          barWidth: 2,
                          isStrokeCapRound: true,
                          dotData: const FlDotData(show: false),
                          belowBarData: BarAreaData(
                            show: true,
                            gradient: LinearGradient(
                              colors: [Colors.blueAccent.withAlpha(50), Colors.blueAccent.withAlpha(5)],
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildPnlHistoryChart() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('📈 Hub PNL% History', style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          SizedBox(
            height: 140,
            child: _pnlHistory.length < 2
                ? const Center(child: Text('Acumulando datos...', style: TextStyle(fontSize: 11, color: Colors.white54)))
                : LineChart(
                    LineChartData(
                      lineTouchData: LineTouchData(enabled: false),
                      gridData: const FlGridData(show: false),
                      titlesData: const FlTitlesData(show: false),
                      borderData: FlBorderData(show: false),
                      lineBarsData: [
                        LineChartBarData(
                          spots: _pnlHistory.asMap().entries.map((e) => FlSpot(e.key.toDouble(), e.value)).toList(),
                          isCurved: true,
                          gradient: LinearGradient(
                            colors: _pnlHistory.last >= 0 ? [Colors.greenAccent, Colors.green] : [Colors.redAccent, Colors.red],
                          ),
                          barWidth: 2,
                          isStrokeCapRound: true,
                          dotData: const FlDotData(show: false),
                          belowBarData: BarAreaData(
                            show: true,
                            gradient: LinearGradient(
                              colors: _pnlHistory.last >= 0
                                  ? [Colors.greenAccent.withAlpha(50), Colors.greenAccent.withAlpha(5)]
                                  : [Colors.redAccent.withAlpha(50), Colors.redAccent.withAlpha(5)],
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildTelemetryRow() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          if (_weightStatus != null)
            Expanded(
              child: _buildWeightCard(),
            ),
          const SizedBox(width: 8),
          if (_requestsStats != null)
            Expanded(
              child: _buildRequestsCard(),
            ),
        ],
      ),
    );
  }

  Widget _buildWeightCard() {
    final w = _weightStatus!;
    final percentage = w.weightPercentage;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.speed, size: 14, color: Colors.white70),
              const SizedBox(width: 4),
              Text('API Weight', style: Theme.of(context).textTheme.labelSmall),
              const SizedBox(width: 4),
              Text(w.zoneEmoji, style: const TextStyle(fontSize: 12)),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            '${w.currentWeight}/${w.weightLimit}',
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, fontFamily: 'monospace'),
          ),
          const SizedBox(height: 4),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: percentage / 100,
              minHeight: 6,
              backgroundColor: Colors.white10,
              valueColor: AlwaysStoppedAnimation<Color>(
                percentage < 70 ? Colors.greenAccent : percentage < 90 ? Colors.orangeAccent : Colors.redAccent,
              ),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            '${percentage.toStringAsFixed(1)}%',
            style: const TextStyle(fontSize: 10, color: Colors.white70),
          ),
        ],
      ),
    );
  }

  Widget _buildRequestsCard() {
    final r = _requestsStats!;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.http, size: 14, color: Colors.white70),
              const SizedBox(width: 4),
              Text('HTTP Requests', style: Theme.of(context).textTheme.labelSmall),
            ],
          ),
          const SizedBox(height: 6),
          Text(
            '${r.total}',
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, fontFamily: 'monospace'),
          ),
          const SizedBox(height: 6),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _requestBotStat('BTC', r.louiseBtc001),
              _requestBotStat('ETH', r.louiseEth001),
              _requestBotStat('SOL', r.louiseSol001),
            ],
          ),
        ],
      ),
    );
  }

  Widget _requestBotStat(String symbol, int count) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        Text(symbol, style: const TextStyle(fontSize: 9, color: Colors.white70)),
        Text('$count', style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
      ],
    );
  }

  Widget _buildBotCard(BotMetrics bot) {
    final pnlColor = bot.unrealizedPct >= 0 ? Colors.greenAccent : Colors.redAccent;

    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Text(bot.statusEmoji, style: const TextStyle(fontSize: 14)),
                  const SizedBox(width: 6),
                  Text(
                    bot.symbol,
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, fontFamily: 'monospace'),
                  ),
                  const SizedBox(width: 8),
                  Chip(
                    label: Text(
                      '${bot.unrealizedPct.toStringAsFixed(2)}%',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: pnlColor),
                    ),
                    backgroundColor: pnlColor.withAlpha(30),
                  ),
                ],
              ),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _actionButton(Icons.pause_circle_outline, 'Pausar', () => _pauseBot(bot.id), size: 16),
                  const SizedBox(width: 4),
                  _actionButton(Icons.edit_outlined, 'Editar', () => _editBot(bot.id), size: 16),
                  const SizedBox(width: 4),
                  _actionButton(Icons.delete_outline, 'Eliminar', () => _deleteBot(bot.id), size: 16, color: Colors.redAccent),
                ],
              ),
            ],
          ),
          const SizedBox(height: 10),
          GridView.count(
            crossAxisCount: 4,
            crossAxisSpacing: 8,
            mainAxisSpacing: 8,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 1.6,
            children: [
              _botDetailCard('Precio', '\$${bot.currentPrice.toStringAsFixed(2)}'),
              _botDetailCard('Posición', '${bot.positionSize.toStringAsFixed(4)} ${bot.symbol.split("/")[0]}'),
              _botDetailCard('Libre', '\$${bot.freeBalance.toStringAsFixed(2)}'),
              _botDetailCard('Trades', '${bot.tradesToday}'),
            ],
          ),
          const SizedBox(height: 8),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Progreso: ${bot.progressPercent.toStringAsFixed(1)}%',
                    style: const TextStyle(fontSize: 10, color: Colors.white70),
                  ),
                  Text(
                    'Target: ${bot.targetProfitPct.toStringAsFixed(1)}%',
                    style: const TextStyle(fontSize: 10, color: Colors.white70),
                  ),
                ],
              ),
              const SizedBox(height: 4),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: (bot.progressPercent / 100).clamp(0, 1),
                  minHeight: 6,
                  backgroundColor: Colors.white10,
                  valueColor: const AlwaysStoppedAnimation<Color>(Colors.blueAccent),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _botDetailCard(String label, String value) {
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: Colors.white.withAlpha(8),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: const TextStyle(fontSize: 8, color: Colors.white70)),
          Text(value, style: const TextStyle(fontSize: 10, fontWeight: FontWeight.bold, fontFamily: 'monospace')),
        ],
      ),
    );
  }

  Widget _actionButton(
    IconData icon,
    String tooltip,
    VoidCallback onPressed, {
    double size = 16,
    Color color = Colors.white70,
  }) {
    return Tooltip(
      message: tooltip,
      child: GestureDetector(
        onTap: onPressed,
        child: Icon(icon, size: size, color: color),
      ),
    );
  }

  void _pauseBot(String botId) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Pausar $botId'), duration: const Duration(seconds: 1)),
    );
  }

  void _editBot(String botId) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Editar $botId'), duration: const Duration(seconds: 1)),
    );
  }

  void _deleteBot(String botId) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Eliminar Bot'),
        content: Text('¿Estás seguro de que deseas eliminar $botId?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancelar')),
          TextButton(
            onPressed: () {
              Navigator.pop(ctx);
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(content: Text('Eliminar $botId'), duration: const Duration(seconds: 1)),
              );
            },
            child: const Text('Eliminar', style: TextStyle(color: Colors.redAccent)),
          ),
        ],
      ),
    );
  }

  void _showCreateBotDialog() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Crear bot'), duration: Duration(seconds: 1)),
    );
  }
}
