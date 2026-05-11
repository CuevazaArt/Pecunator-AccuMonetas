import 'dart:async';
import 'package:flutter/material.dart';
import 'package:fl_chart/fl_chart.dart';
import '../api_client.dart';
import '../services/telemetry_hub.dart';
import '../models/louise_models.dart';

/// Louise Hub — main dashboard page.
///
/// Data strategy:
///   PRIMARY  → WebSocket (TelemetryHub) — bots list, metrics, weight
///   FALLBACK → REST polling every 8s when WS is unavailable
///   MUTATION → REST POST/PATCH/DELETE for pause/resume/create/edit/delete
class LouiseHubPage extends StatefulWidget {
  final String engineBase;
  const LouiseHubPage({super.key, required this.engineBase});

  @override
  State<LouiseHubPage> createState() => _LouiseHubPageState();
}

class _LouiseHubPageState extends State<LouiseHubPage> {
  late final EngineApi _api;
  StreamSubscription<TelemetrySnapshot>? _wsSub;
  Timer? _restFallbackTimer;

  List<BotMetrics> _bots = [];
  HubMetrics? _hubMetrics;
  WeightStatus? _weightStatus;
  List<WeightHistory> _weightHistory = [];
  final List<double> _pnlHistory = [];

  bool _wsConnected = false;
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _api = EngineApi(widget.engineBase);

    // Subscribe to WS telemetry — zero polling while connected
    _wsSub = TelemetryHub.instance.stream.listen(_onTelemetryTick);
    TelemetryHub.instance.connectionStream?.listen((connected) {
      if (!mounted) return;
      setState(() => _wsConnected = connected);
      if (!connected) _startRestFallback();
    });

    // Seed from last known snapshot if available
    final snap = TelemetryHub.instance.last;
    if (snap != null) _applySnapshot(snap);

    // REST for initial weight history + fallback bootstrap
    _loadSupplementaryData();
  }

  @override
  void dispose() {
    _wsSub?.cancel();
    _restFallbackTimer?.cancel();
    super.dispose();
  }

  // ── Data ingestion ──────────────────────────────────────────────────

  void _onTelemetryTick(TelemetrySnapshot snap) {
    if (!mounted) return;
    _applySnapshot(snap);
  }

  void _applySnapshot(TelemetrySnapshot snap) {
    if (!mounted) return;
    setState(() {
      _loading = false;
      _error = null;
      _wsConnected = TelemetryHub.instance.isWsConnected;

      if (snap.louiseBots.isNotEmpty) {
        _bots = snap.louiseBots.map(BotMetrics.fromJson).toList();
      }
      if (snap.louiseMetrics != null) {
        _hubMetrics = HubMetrics.fromJson(snap.louiseMetrics!);
        _pnlHistory.add(_hubMetrics!.hubPnlPercent);
        if (_pnlHistory.length > 100) _pnlHistory.removeAt(0);
      }
      // Weight from WS (shared infrastructure field)
      _weightStatus = WeightStatus(
        timestamp: snap.timestamp,
        currentWeight: snap.usedWeight,
        weightPerMinute: snap.usedWeight,
        weightLimit: snap.weightLimit,
        weightZone: snap.weightPct < 0.5 ? 'GREEN' : snap.weightPct < 0.8 ? 'YELLOW' : 'RED',
        statusMessage: '${(snap.weightPct * 100).toStringAsFixed(1)}% of limit used.',
      );
    });
  }

  void _startRestFallback() {
    if (_restFallbackTimer != null) return;
    _restFallbackTimer = Timer.periodic(const Duration(seconds: 8), (_) {
      if (_wsConnected) {
        _restFallbackTimer?.cancel();
        _restFallbackTimer = null;
        return;
      }
      _loadSupplementaryData();
    });
  }

  Future<void> _loadSupplementaryData() async {
    try {
      final results = await Future.wait([
        _api.louiseBots().catchError((_) => <Map<String, dynamic>>[]),
        _api.louiseMetrics().catchError((_) => <String, dynamic>{}),
        _api.louiseWeightStatus().catchError((_) => <String, dynamic>{}),
        _api.louiseWeightHistory().catchError((_) => <Map<String, dynamic>>[]),
      ]);
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = null;
        final botList = results[0] as List<Map<String, dynamic>>;
        if (botList.isNotEmpty) _bots = botList.map(BotMetrics.fromJson).toList();

        final metricsMap = results[1] as Map<String, dynamic>;
        if (metricsMap.isNotEmpty) {
          _hubMetrics = HubMetrics.fromJson(metricsMap);
        }
        final weightMap = results[2] as Map<String, dynamic>;
        if (weightMap.isNotEmpty) _weightStatus = WeightStatus.fromJson(weightMap);

        final histList = (results[3] as List<Map<String, dynamic>>);
        if (histList.isNotEmpty) {
          _weightHistory = histList.map(WeightHistory.fromJson).toList();
        }
      });
    } catch (e) {
      if (mounted) setState(() { _loading = false; _error = '$e'; });
    }
  }

  // ── Mutation helpers ────────────────────────────────────────────────

  Future<void> _mutate(Future<void> Function() action) async {
    try {
      await action();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.redAccent),
        );
      }
    }
  }

  Future<void> _pauseBot(String botId) => _mutate(() async {
    await _api.louisePauseBot(botId);
    await _loadSupplementaryData();
  });

  Future<void> _resumeBot(String botId) => _mutate(() async {
    await _api.louiseResumeBot(botId);
    await _loadSupplementaryData();
  });

  Future<void> _deleteBot(String botId) => _mutate(() async {
    await _api.louiseDeleteBot(botId);
    await _loadSupplementaryData();
  });

  Future<void> _createBot(String symbol, double budget, double targetPct) => _mutate(() async {
    await _api.louiseCreateBot(symbol: symbol, dailyBudget: budget, targetProfitPct: targetPct);
    await _loadSupplementaryData();
  });

  Future<void> _editBot(String botId, double budget, double targetPct) => _mutate(() async {
    await _api.louiseUpdateBot(botId, dailyBudget: budget, targetProfitPct: targetPct);
    await _loadSupplementaryData();
  });

  // ── Dialogs ─────────────────────────────────────────────────────────

  void _showCreateDialog() {
    final symbolCtrl = TextEditingController(text: 'BTC/USDT');
    final budgetCtrl = TextEditingController(text: '500');
    final targetCtrl = TextEditingController(text: '5.0');
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Create Louise Bot'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: symbolCtrl, decoration: const InputDecoration(labelText: 'Symbol (e.g. ETH/USDT)')),
            const SizedBox(height: 12),
            TextField(controller: budgetCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Daily budget USDT')),
            const SizedBox(height: 12),
            TextField(controller: targetCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Target PNL% per cycle')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () {
              final sym = symbolCtrl.text.trim().toUpperCase();
              final budget = double.tryParse(budgetCtrl.text) ?? 500;
              final target = double.tryParse(targetCtrl.text) ?? 5.0;
              Navigator.pop(ctx);
              _createBot(sym, budget, target);
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }

  void _showEditDialog(BotMetrics bot) {
    final budgetCtrl = TextEditingController(text: bot.dailyBudget.toStringAsFixed(0));
    final targetCtrl = TextEditingController(text: bot.targetProfitPct.toStringAsFixed(1));
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Edit ${bot.symbol}'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(controller: budgetCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Daily budget USDT')),
            const SizedBox(height: 12),
            TextField(controller: targetCtrl, keyboardType: TextInputType.number, decoration: const InputDecoration(labelText: 'Target PNL% per cycle')),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            onPressed: () {
              final budget = double.tryParse(budgetCtrl.text) ?? bot.dailyBudget;
              final target = double.tryParse(targetCtrl.text) ?? bot.targetProfitPct;
              Navigator.pop(ctx);
              _editBot(bot.id, budget, target);
            },
            child: const Text('Save'),
          ),
        ],
      ),
    );
  }

  void _showDeleteDialog(BotMetrics bot) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Bot'),
        content: Text('Delete ${bot.symbol} (${bot.id})?\nThis action cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.redAccent),
            onPressed: () { Navigator.pop(ctx); _deleteBot(bot.id); },
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }

  // ── Build ────────────────────────────────────────────────────────────

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    return CustomScrollView(
      slivers: [
        SliverToBoxAdapter(child: _buildConnectionBar()),
        if (_hubMetrics != null) SliverToBoxAdapter(child: _buildHubSummary()),
        SliverToBoxAdapter(child: const SizedBox(height: 4)),
        SliverToBoxAdapter(child: _buildChartsRow()),
        SliverToBoxAdapter(child: const SizedBox(height: 8)),
        if (_weightStatus != null) SliverToBoxAdapter(child: _buildTelemetryRow()),
        SliverToBoxAdapter(child: const SizedBox(height: 8)),
        SliverToBoxAdapter(child: _buildBotListHeader()),
        SliverList(
          delegate: SliverChildBuilderDelegate(
            (ctx, i) => i < _bots.length ? _buildBotCard(_bots[i]) : null,
            childCount: _bots.length,
          ),
        ),
        if (_bots.isEmpty)
          SliverToBoxAdapter(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Center(
                child: Column(children: [
                  const Icon(Icons.smart_toy_outlined, size: 48, color: Colors.white24),
                  const SizedBox(height: 8),
                  const Text('Sin bots activos', style: TextStyle(color: Colors.white54)),
                  const SizedBox(height: 16),
                  ElevatedButton.icon(
                    onPressed: _showCreateDialog,
                    icon: const Icon(Icons.add),
                    label: const Text('Crear primer bot'),
                  ),
                ]),
              ),
            ),
          ),
        if (_error != null) SliverToBoxAdapter(child: _buildErrorBar()),
        const SliverToBoxAdapter(child: SizedBox(height: 24)),
      ],
    );
  }

  // ── Sub-widgets ──────────────────────────────────────────────────────

  Widget _buildConnectionBar() {
    final isWs = _wsConnected;
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 6, 16, 0),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: isWs ? Colors.green.withAlpha(20) : Colors.orange.withAlpha(20),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: isWs ? Colors.greenAccent.withAlpha(80) : Colors.orangeAccent.withAlpha(80)),
      ),
      child: Row(
        children: [
          Icon(isWs ? Icons.wifi : Icons.wifi_off, size: 12,
              color: isWs ? Colors.greenAccent : Colors.orangeAccent),
          const SizedBox(width: 6),
          Text(
            isWs ? 'WebSocket conectado — datos en tiempo real' : 'WebSocket desconectado — REST polling activo',
            style: TextStyle(fontSize: 10, color: isWs ? Colors.greenAccent : Colors.orangeAccent),
          ),
        ],
      ),
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
          begin: Alignment.topLeft, end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.blue.withAlpha(80)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          const Text('Louise Hub', style: TextStyle(fontSize: 13, fontWeight: FontWeight.bold)),
          Chip(
            label: Text('${m.hubPnlPercent >= 0 ? "+" : ""}${m.hubPnlPercent.toStringAsFixed(2)}%',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: pnlColor)),
            backgroundColor: pnlColor.withAlpha(25),
            padding: EdgeInsets.zero,
          ),
        ]),
        const SizedBox(height: 10),
        GridView.count(
          crossAxisCount: 4, crossAxisSpacing: 8, mainAxisSpacing: 0,
          shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
          childAspectRatio: 1.4,
          children: [
            _summaryCard('Activos', '${m.activeBots}', Colors.blueAccent),
            _summaryCard('Portfolio', '\$${m.totalPortfolio.toStringAsFixed(0)}', Colors.greenAccent),
            _summaryCard('Libre', '\$${m.totalFreeBalance.toStringAsFixed(0)}', Colors.orangeAccent),
            _summaryCard('PNL \$', (m.totalUnrealizedPnl >= 0 ? '+' : '') + '\$${m.totalUnrealizedPnl.toStringAsFixed(2)}', pnlColor),
          ],
        ),
      ]),
    );
  }

  Widget _summaryCard(String label, String value, Color color) => Container(
    padding: const EdgeInsets.all(8),
    decoration: BoxDecoration(
      color: color.withAlpha(15),
      borderRadius: BorderRadius.circular(6),
      border: Border.all(color: color.withAlpha(60)),
    ),
    child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
      Text(label, style: const TextStyle(fontSize: 9, color: Colors.white70)),
      const SizedBox(height: 2),
      Text(value, style: TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: color)),
    ]),
  );

  Widget _buildChartsRow() => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 16),
    child: Row(children: [
      Expanded(flex: 2, child: _buildWeightHistoryChart()),
      const SizedBox(width: 8),
      Expanded(flex: 2, child: _buildPnlChart()),
    ]),
  );

  Widget _buildWeightHistoryChart() => _chartCard(
    title: '⚡ API Weight (24h)',
    child: _weightHistory.isEmpty
        ? const Center(child: Text('Sin datos', style: TextStyle(color: Colors.white38, fontSize: 11)))
        : LineChart(LineChartData(
            lineTouchData: LineTouchData(enabled: false),
            gridData: const FlGridData(show: false),
            titlesData: const FlTitlesData(show: false),
            borderData: FlBorderData(show: false),
            lineBarsData: [LineChartBarData(
              spots: _weightHistory.asMap().entries
                  .map((e) => FlSpot(e.key.toDouble(), e.value.total.toDouble())).toList(),
              isCurved: true,
              gradient: const LinearGradient(colors: [Colors.blueAccent, Colors.cyanAccent]),
              barWidth: 2, isStrokeCapRound: true,
              dotData: const FlDotData(show: false),
              belowBarData: BarAreaData(show: true, gradient: LinearGradient(
                colors: [Colors.blueAccent.withAlpha(50), Colors.blueAccent.withAlpha(5)],
                begin: Alignment.topCenter, end: Alignment.bottomCenter,
              )),
            )],
          )),
  );

  Widget _buildPnlChart() => _chartCard(
    title: '📈 Hub PNL%',
    child: _pnlHistory.length < 2
        ? const Center(child: Text('Acumulando...', style: TextStyle(color: Colors.white38, fontSize: 11)))
        : LineChart(LineChartData(
            lineTouchData: LineTouchData(enabled: false),
            gridData: const FlGridData(show: false),
            titlesData: const FlTitlesData(show: false),
            borderData: FlBorderData(show: false),
            lineBarsData: [LineChartBarData(
              spots: _pnlHistory.asMap().entries
                  .map((e) => FlSpot(e.key.toDouble(), e.value)).toList(),
              isCurved: true,
              gradient: LinearGradient(
                colors: _pnlHistory.last >= 0 ? [Colors.greenAccent, Colors.green] : [Colors.redAccent, Colors.red],
              ),
              barWidth: 2, isStrokeCapRound: true,
              dotData: const FlDotData(show: false),
              belowBarData: BarAreaData(show: true, gradient: LinearGradient(
                colors: _pnlHistory.last >= 0
                    ? [Colors.greenAccent.withAlpha(50), Colors.greenAccent.withAlpha(5)]
                    : [Colors.redAccent.withAlpha(50), Colors.redAccent.withAlpha(5)],
                begin: Alignment.topCenter, end: Alignment.bottomCenter,
              )),
            )],
          )),
  );

  Widget _chartCard({required String title, required Widget child}) => Container(
    padding: const EdgeInsets.all(12),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surface,
      borderRadius: BorderRadius.circular(8),
      border: Border.all(color: Colors.white12),
    ),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(title, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
      const SizedBox(height: 8),
      SizedBox(height: 110, child: child),
    ]),
  );

  Widget _buildTelemetryRow() {
    final w = _weightStatus!;
    final pct = w.weightPercentage;
    final barColor = pct < 70 ? Colors.greenAccent : pct < 90 ? Colors.orangeAccent : Colors.redAccent;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: Colors.white12),
        ),
        child: Row(children: [
          const Icon(Icons.speed, size: 14, color: Colors.white70),
          const SizedBox(width: 6),
          const Text('API Weight', style: TextStyle(fontSize: 11)),
          const SizedBox(width: 6),
          Text(w.zoneEmoji),
          const SizedBox(width: 8),
          Text('${w.currentWeight}/${w.weightLimit}',
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, fontFamily: 'monospace')),
          const SizedBox(width: 12),
          Expanded(child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: pct / 100,
              minHeight: 6,
              backgroundColor: Colors.white10,
              valueColor: AlwaysStoppedAnimation<Color>(barColor),
            ),
          )),
          const SizedBox(width: 8),
          Text('${pct.toStringAsFixed(1)}%', style: const TextStyle(fontSize: 10, color: Colors.white70)),
        ]),
      ),
    );
  }

  Widget _buildBotListHeader() => Padding(
    padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
    child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
      Text('Louise Bots (${_bots.length})',
          style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.bold)),
      ElevatedButton.icon(
        onPressed: _showCreateDialog,
        icon: const Icon(Icons.add, size: 15),
        label: const Text('Crear', style: TextStyle(fontSize: 12)),
        style: ElevatedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          visualDensity: VisualDensity.compact,
        ),
      ),
    ]),
  );

  Widget _buildBotCard(BotMetrics bot) {
    final pnlColor = bot.unrealizedPct >= 0 ? Colors.greenAccent : Colors.redAccent;
    final isRunning = bot.status == 'running';
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white12),
      ),
      child: Column(children: [
        // ── Header row ──────────────────────────────────────
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 10, 8, 6),
          child: Row(children: [
            Text(bot.statusEmoji),
            const SizedBox(width: 6),
            Text(bot.symbol,
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold, fontFamily: 'monospace')),
            const SizedBox(width: 8),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(
                color: pnlColor.withAlpha(25), borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                '${bot.unrealizedPct >= 0 ? "+" : ""}${bot.unrealizedPct.toStringAsFixed(2)}%',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold, color: pnlColor),
              ),
            ),
            const Spacer(),
            // Pause / Resume
            _iconBtn(
              icon: isRunning ? Icons.pause_circle_outline : Icons.play_circle_outline,
              tooltip: isRunning ? 'Pause bot' : 'Resume bot',
              color: isRunning ? Colors.orangeAccent : Colors.greenAccent,
              onTap: () => isRunning ? _pauseBot(bot.id) : _resumeBot(bot.id),
            ),
            _iconBtn(icon: Icons.edit_outlined, tooltip: 'Edit configuration',
                color: Colors.white70, onTap: () => _showEditDialog(bot)),
            _iconBtn(icon: Icons.delete_outline, tooltip: 'Delete bot',
                color: Colors.redAccent.withAlpha(200), onTap: () => _showDeleteDialog(bot)),
          ]),
        ),
        // ── Metrics grid ─────────────────────────────────────
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
          child: Row(children: [
            _metricCell('Price', '\$${bot.currentPrice.toStringAsFixed(2)}'),
            _metricCell('Position', '${bot.positionSize.toStringAsFixed(4)} ${bot.symbol.split("/")[0]}'),
            _metricCell('Free', '\$${bot.freeBalance.toStringAsFixed(2)}'),
            _metricCell('Budget', '\$${bot.dailyBudget.toStringAsFixed(0)}/day'),
            _metricCell('Trades', '${bot.tradesToday}'),
            _metricCell('PNL \$', (bot.unrealizedPnl >= 0 ? '+' : '') + '\$${bot.unrealizedPnl.toStringAsFixed(2)}',
                color: pnlColor),
          ]),
        ),
        // ── Progress bar ─────────────────────────────────────
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text('Cycle progress: ${bot.progressPercent.toStringAsFixed(1)}%',
                  style: const TextStyle(fontSize: 9, color: Colors.white54)),
              Text('Target: ${bot.targetProfitPct.toStringAsFixed(1)}%',
                  style: const TextStyle(fontSize: 9, color: Colors.white54)),
            ]),
            const SizedBox(height: 3),
            ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: (bot.progressPercent / 100).clamp(0, 1),
                minHeight: 5,
                backgroundColor: Colors.white10,
                valueColor: const AlwaysStoppedAnimation<Color>(Colors.blueAccent),
              ),
            ),
          ]),
        ),
      ]),
    );
  }

  Widget _metricCell(String label, String value, {Color? color}) => Expanded(
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(label, style: const TextStyle(fontSize: 8, color: Colors.white54)),
      Text(value, style: TextStyle(
          fontSize: 10, fontWeight: FontWeight.bold,
          fontFamily: 'monospace', color: color)),
    ]),
  );

  Widget _iconBtn({required IconData icon, required String tooltip,
      required Color color, required VoidCallback onTap}) =>
    Tooltip(
      message: tooltip,
      waitDuration: const Duration(milliseconds: 400),
      child: InkWell(
        borderRadius: BorderRadius.circular(6),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(6),
          child: Icon(icon, size: 18, color: color),
        ),
      ),
    );

  Widget _buildErrorBar() => Container(
    margin: const EdgeInsets.all(16),
    padding: const EdgeInsets.all(10),
    decoration: BoxDecoration(
      color: Colors.red.withAlpha(20),
      borderRadius: BorderRadius.circular(6),
      border: Border.all(color: Colors.redAccent.withAlpha(80)),
    ),
    child: Row(children: [
      const Icon(Icons.warning_amber_rounded, color: Colors.redAccent, size: 16),
      const SizedBox(width: 8),
      Expanded(child: Text(_error!, style: const TextStyle(color: Colors.redAccent, fontSize: 11))),
    ]),
  );
}
