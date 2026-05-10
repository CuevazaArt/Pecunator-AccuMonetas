import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import 'mini_charts.dart'; // StatusLights widget

/// Reusable template for any bot hub page.
///
/// Layout (top to bottom):
/// 1. Mini weight chart (200ms sync, 10min window)
/// 2. Mini equity chart (subaccount + global)
/// 3. Bot config/placement form
/// 4. Active bot queue
/// 5. Status lights
class BotHubTemplate extends StatefulWidget {
  final String hubName;
  final Color hubColor;
  final IconData hubIcon;
  final EngineApi api;
  final String engineBase;

  /// Fetches bot list — returns List<Map> of bots
  final Future<List<Map<String, dynamic>>> Function() fetchBots;
  /// Creates a new bot
  final Future<void> Function(Map<String, dynamic> config) createBot;
  /// Starts a bot by ID
  final Future<void> Function(String botId) startBot;
  /// Stops a bot by ID
  final Future<void> Function(String botId) stopBot;
  /// Deletes a bot by ID
  final Future<void> Function(String botId) deleteBot;
  /// Returns log entries for a bot
  final Future<List<String>> Function(String botId) fetchLogs;

  const BotHubTemplate({
    super.key,
    required this.hubName,
    required this.hubColor,
    required this.hubIcon,
    required this.api,
    required this.engineBase,
    required this.fetchBots,
    required this.createBot,
    required this.startBot,
    required this.stopBot,
    required this.deleteBot,
    required this.fetchLogs,
  });

  @override
  State<BotHubTemplate> createState() => _BotHubTemplateState();
}

class _BotHubTemplateState extends State<BotHubTemplate> {
  Timer? _refreshTimer;
  List<Map<String, dynamic>> _bots = [];
  bool _loading = true;
  String? _error;
  bool _gatewayRunning = false;
  bool _fuseTripped = false;
  String? _expandedBotId;
  final Map<String, List<String>> _botLogs = {};

  @override
  void initState() {
    super.initState();
    _refresh();
    _refreshTimer = Timer.periodic(const Duration(seconds: 5), (_) => _refreshSilent());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    setState(() => _loading = true);
    try {
      final bots = await widget.fetchBots();
      final snap = await widget.api.gatewaySnapshot();
      bool fuse = false;
      try {
        final fs = await widget.api.apiFuseStatus();
        fuse = fs['tripped'] == true;
      } catch (_) {}
      if (!mounted) return;
      setState(() {
        _bots = bots;
        _gatewayRunning = snap['gateway_running'] == true;
        _fuseTripped = fuse;
        _loading = false;
        _error = null;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = '$e';
      });
    }
  }

  Future<void> _refreshSilent() async {
    try {
      final bots = await widget.fetchBots();
      final snap = await widget.api.gatewaySnapshot();
      bool fuse = false;
      try {
        final fs = await widget.api.apiFuseStatus();
        fuse = fs['tripped'] == true;
      } catch (_) {}
      if (!mounted) return;
      setState(() {
        _bots = bots;
        _gatewayRunning = snap['gateway_running'] == true;
        _fuseTripped = fuse;
      });
      
      // Fetch logs for expanded bot to keep them fresh without flickering
      if (_expandedBotId != null) {
        final logs = await widget.fetchLogs(_expandedBotId!);
        if (mounted && _expandedBotId != null) {
          setState(() => _botLogs[_expandedBotId!] = logs);
        }
      }
    } catch (_) {}
  }

  int get _botsRunning => _bots.where((b) => b['running'] == true).length;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // ── Hub Header ──────────────────────────────────────────
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Row(
              children: [
                Icon(widget.hubIcon, size: 18, color: widget.hubColor),
                const SizedBox(width: 6),
                Text(widget.hubName,
                    style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: widget.hubColor, letterSpacing: 0.5)),
                const SizedBox(width: 8),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: _botsRunning > 0 ? Colors.greenAccent.withValues(alpha: 0.15) : Colors.white.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text(
                    '$_botsRunning/${_bots.length} active',
                    style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, fontFamily: 'monospace',
                        color: _botsRunning > 0 ? Colors.greenAccent : Colors.white38),
                  ),
                ),
              ],
            ),
          ),
          
          // ── Section 3: Bot Queue ────────────────────────────────
          if (_loading && _bots.isEmpty)
            const Center(child: Padding(
              padding: EdgeInsets.all(20),
              child: CircularProgressIndicator(strokeWidth: 2),
            ))
          else if (_error != null && _bots.isEmpty)
            Center(child: Text('Error: $_error', style: const TextStyle(color: Colors.redAccent, fontSize: 11)))
          else
            ..._bots.map((bot) => _buildBotCard(bot)),
        ],
      ),
    );
  }

  Widget _buildBotCard(Map<String, dynamic> bot) {
    final botId = '${bot['bot_id'] ?? ''}';
    final symbol = '${bot['symbol'] ?? bot['tag'] ?? ''}';
    final running = bot['running'] == true;
    final desired = bot['desired_running'] == true;
    final isExpanded = _expandedBotId == botId;

    // Extract useful info
    final loop = bot['loop_interval_sec'] ?? bot['interval_sec'] ?? '';
    final preset = bot['preset_id'] ?? bot['tag'] ?? '';
    final cycles = bot['cycles'] ?? bot['total_cycles'] ?? 0;
    final lastDecision = bot['last_decision'] ?? '';
    final equity = bot['last_equity_usdt'];

    final statusColor = running
        ? Colors.greenAccent
        : desired
            ? Colors.orangeAccent
            : Colors.grey;

    return Container(
      margin: const EdgeInsets.only(bottom: 3),
      decoration: BoxDecoration(
        color: const Color(0xFF16213E),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(color: statusColor.withValues(alpha: 0.2)),
      ),
      child: Column(
        children: [
          InkWell(
            onTap: () {
              setState(() {
                if (isExpanded) {
                  _expandedBotId = null;
                } else {
                  _expandedBotId = botId;
                  _botLogs.remove(botId); // Clear old logs to show loading
                }
              });
              if (_expandedBotId == botId) {
                widget.fetchLogs(botId).then((logs) {
                  if (mounted && _expandedBotId == botId) {
                    setState(() => _botLogs[botId] = logs);
                  }
                });
              }
            },
            borderRadius: BorderRadius.circular(6),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
              child: Row(
                children: [
                  // Status dot
                  Container(
                    width: 8, height: 8,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: statusColor,
                      boxShadow: running ? [BoxShadow(color: statusColor.withValues(alpha: 0.5), blurRadius: 4)] : null,
                    ),
                  ),
                  const SizedBox(width: 6),
                  // Symbol
                  Text(symbol, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, fontFamily: 'monospace')),
                  const SizedBox(width: 8),
                  // Preset tag
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                    decoration: BoxDecoration(
                      color: widget.hubColor.withValues(alpha: 0.15),
                      borderRadius: BorderRadius.circular(4),
                    ),
                    child: Text('$preset', style: TextStyle(fontSize: 8, color: widget.hubColor, fontFamily: 'monospace')),
                  ),
                  const SizedBox(width: 6),
                  // Loop interval
                  Text('${loop}s', style: const TextStyle(fontSize: 9, color: Colors.white38, fontFamily: 'monospace')),
                  const SizedBox(width: 6),
                  // Cycles
                  Text('#$cycles', style: const TextStyle(fontSize: 9, color: Colors.white38, fontFamily: 'monospace')),
                  const SizedBox(width: 6),
                  // Decision
                  Expanded(
                    child: Text('$lastDecision', style: TextStyle(
                      fontSize: 9, fontFamily: 'monospace',
                      color: lastDecision.toString().contains('BUY')
                          ? Colors.greenAccent
                          : lastDecision.toString().contains('BLOCKED')
                              ? Colors.orangeAccent
                              : Colors.white30,
                    ), overflow: TextOverflow.ellipsis),
                  ),
                  // Equity
                  if (equity != null)
                    Text('\$$equity', style: const TextStyle(fontSize: 9, color: Colors.white54, fontFamily: 'monospace')),
                  const SizedBox(width: 4),
                  // Controls
                  if (running)
                    Tooltip(message: 'Detener bot', child: _miniBtn(Icons.stop, Colors.orangeAccent, () => widget.stopBot(botId).then((_) => _refresh())))
                  else
                    Tooltip(message: 'Iniciar bot', child: _miniBtn(Icons.play_arrow, Colors.greenAccent, () => widget.startBot(botId).then((_) => _refresh()))),
                  Tooltip(message: 'Eliminar bot', child: _miniBtn(Icons.delete_outline, Colors.redAccent, () => _confirmDelete(botId, symbol))),
                  Tooltip(message: 'Ver logs', child: Icon(isExpanded ? Icons.expand_less : Icons.expand_more, size: 14, color: Colors.white24)),
                ],
              ),
            ),
          ),
          // Expanded logs
          if (isExpanded)
            Container(
              constraints: const BoxConstraints(maxHeight: 150),
              margin: const EdgeInsets.fromLTRB(8, 0, 8, 6),
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: Colors.black26,
                borderRadius: BorderRadius.circular(4),
              ),
              child: _botLogs[botId] == null
                  ? const Padding(padding: EdgeInsets.all(8), child: LinearProgressIndicator(minHeight: 2))
                  : ListView.builder(
                      reverse: true,
                      itemCount: _botLogs[botId]!.length,
                      itemBuilder: (_, i) => Text(
                        _botLogs[botId]![_botLogs[botId]!.length - 1 - i],
                        style: const TextStyle(fontSize: 9, fontFamily: 'monospace', color: Colors.white54),
                      ),
                    ),
            ),
        ],
      ),
    );
  }

  Widget _miniBtn(IconData icon, Color color, VoidCallback onTap) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(4),
      child: Padding(
        padding: const EdgeInsets.all(3),
        child: Icon(icon, size: 14, color: color),
      ),
    );
  }

  Future<void> _confirmDelete(String botId, String symbol) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Eliminar bot'),
        content: Text('¿Eliminar $symbol ($botId)?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar')),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(backgroundColor: Colors.redAccent),
            child: const Text('Eliminar'),
          ),
        ],
      ),
    );
    if (ok == true) {
      await widget.deleteBot(botId);
      await _refresh();
    }
  }
}
