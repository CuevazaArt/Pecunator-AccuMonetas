import 'dart:async';
import 'package:flutter/material.dart';
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

  bool _loading = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _api = EngineApi(widget.engineBase);
    _loadData();
    // Refresh every 5 seconds as per dashboard spec
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
      ]);

      if (!mounted) return;

      setState(() {
        _bots = (results[0] as List).map((b) => BotMetrics.fromJson(b as Map<String, dynamic>)).toList();
        _hubMetrics = results[1].isNotEmpty ? HubMetrics.fromJson(results[1] as Map<String, dynamic>) : null;
        _weightStatus = results[2].isNotEmpty ? WeightStatus.fromJson(results[2] as Map<String, dynamic>) : null;
        _requestsStats = results[3].isNotEmpty ? RequestsStats.fromJson(results[3] as Map<String, dynamic>) : null;
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

        // ── Telemetry charts (Weight + Requests) ────────────
        SliverToBoxAdapter(
          child: _buildTelemetryRow(),
        ),

        const SliverToBoxAdapter(child: SizedBox(height: 8)),

        // ── Bot list ───────────────────────────────────────
        SliverList(
          delegate: SliverChildBuilderDelegate(
            (ctx, i) {
              if (i == 0) {
                return Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
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
                );
              }
              final botIdx = i - 1;
              if (botIdx >= _bots.length) return null;
              return _buildBotCard(_bots[botIdx]);
            },
            childCount: _bots.length + 1,
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
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Hub Summary', style: Theme.of(context).textTheme.labelMedium?.copyWith(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _summaryItem('Bots Activos', '${m.activeBots}'),
              _summaryItem('Portfolio', '\$${m.totalPortfolio.toStringAsFixed(2)}'),
              _summaryItem('Libre', '\$${m.totalFreeBalance.toStringAsFixed(2)}'),
              _summaryItem(
                'Hub PNL%',
                '${m.hubPnlPercent.toStringAsFixed(2)}%',
                textColor: pnlColor,
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _summaryItem(String label, String value, {Color? textColor}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 10, color: Colors.white70)),
        Text(value, style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold, color: textColor ?? Colors.white)),
      ],
    );
  }

  Widget _buildTelemetryRow() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        children: [
          // Weight Status
          if (_weightStatus != null)
            Expanded(
              child: _buildWeightCard(),
            ),
          const SizedBox(width: 8),
          // Requests Stats
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
    final percentage = (w.currentWeight / w.weightLimit * 100).clamp(0, 100);

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
              minHeight: 4,
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
          const SizedBox(height: 4),
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
          // Header: status + symbol + %PNL
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
                  Text(
                    '${bot.unrealizedPct.toStringAsFixed(2)}%',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold, color: pnlColor),
                  ),
                ],
              ),
              // Action buttons
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _actionButton(
                    Icons.pause_circle_outline,
                    'Pausar',
                    () => _pauseBot(bot.id),
                    size: 16,
                  ),
                  const SizedBox(width: 4),
                  _actionButton(
                    Icons.edit_outlined,
                    'Editar',
                    () => _editBot(bot.id),
                    size: 16,
                  ),
                  const SizedBox(width: 4),
                  _actionButton(
                    Icons.delete_outline,
                    'Eliminar',
                    () => _deleteBot(bot.id),
                    size: 16,
                    color: Colors.redAccent,
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 8),
          // Details row
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _botDetail('Precio', '\$${bot.currentPrice.toStringAsFixed(2)}'),
              _botDetail('Posición', '${bot.positionSize} ${bot.symbol.split("/")[0]}'),
              _botDetail('Libre', '\$${bot.freeBalance.toStringAsFixed(2)}'),
              _botDetail('Trades hoy', '${bot.tradesToday}'),
            ],
          ),
          const SizedBox(height: 8),
          // Progress bar
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

  Widget _botDetail(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 9, color: Colors.white70)),
        Text(value, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold, fontFamily: 'monospace')),
      ],
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
      SnackBar(content: Text('Pausar $botId — En desarrollo')),
    );
  }

  void _editBot(String botId) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Editar $botId — En desarrollo')),
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
                SnackBar(content: Text('Eliminar $botId — En desarrollo')),
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
      const SnackBar(content: Text('Crear bot — En desarrollo')),
    );
  }
}
