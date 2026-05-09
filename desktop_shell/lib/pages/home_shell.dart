import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/compact_weight_gauge.dart';
import '../widgets/system_status_bar.dart';
import '../widgets/credential_manager_dialog.dart';
import 'unified_hub_page.dart';

/// Root scaffold — thin AppBar orchestrator.
///
/// All page content lives in [UnifiedHubPage].
/// Credential management is delegated to [showCredentialManagerDialog].
class PecunatorShell extends StatefulWidget {
  const PecunatorShell({super.key});

  @override
  State<PecunatorShell> createState() => _PecunatorShellState();
}

class _PecunatorShellState extends State<PecunatorShell> {
  static const _engineBase = 'http://127.0.0.1:8000';
  late final EngineApi _api;
  Timer? _timer;
  Timer? _clockTimer;

  // AppBar state
  bool _loading = false;
  String _activeCredential = '—';
  String _activeCredentialId = '';
  List<Map<String, dynamic>> _vaultCredentials = [];
  bool _gatewayRunning = false;
  bool _gatewayWsConnected = false;
  String _clockText = '--:--:-- UTC';

  static const _tooltipDecoration = BoxDecoration(
    color: Color(0xEE1A1A2E),
    borderRadius: BorderRadius.all(Radius.circular(8)),
    border: Border.fromBorderSide(BorderSide(color: Colors.white24)),
  );
  static const _tooltipStyle = TextStyle(fontSize: 11, color: Colors.white);

  @override
  void initState() {
    super.initState();
    _api = EngineApi(_engineBase);
    _refresh();
    _timer = Timer.periodic(const Duration(seconds: 10), (_) => _refreshSilent());
    _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) => _updateClock());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _clockTimer?.cancel();
    super.dispose();
  }

  void _updateClock() {
    if (!mounted) return;
    final now = DateTime.now().toUtc();
    final text = '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}:${now.second.toString().padLeft(2, '0')} UTC';
    setState(() => _clockText = text);
  }

  Future<void> _refresh() async {
    setState(() => _loading = true);
    await _fetchState();
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _refreshSilent() async {
    await _fetchState();
  }

  Future<void> _fetchState() async {
    try {
      final snap = await _api.gatewaySnapshot();
      if (!mounted) return;
      setState(() {
        _gatewayRunning = snap['gateway_running'] == true;
        _gatewayWsConnected = snap['ws_connected'] == true;
      });
    } catch (_) {}

    try {
      final vault = await _api.vaultCredentials();
      if (!mounted) return;
      setState(() {
        _vaultCredentials = (vault['items'] as List?)?.cast<Map<String, dynamic>>() ?? [];
      });
    } catch (_) {}

    try {
      final active = await _api.activeCredential();
      if (!mounted) return;
      setState(() {
        _activeCredential = '${active['label'] ?? '—'}';
        _activeCredentialId = '${active['credential_id'] ?? ''}';
      });
    } catch (_) {}
  }

  Future<void> _toggleGateway() async {
    try {
      if (_gatewayRunning) {
        await _api.gatewayStop();
      } else {
        await _api.gatewayStart();
      }
      await _refresh();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$e'), backgroundColor: Colors.redAccent),
        );
      }
    }
  }

  Future<void> _syncTimestamp() async {
    try {
      await _api.syncTimestamp();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Timestamp synced'), duration: Duration(seconds: 1)),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Sync failed: $e'), backgroundColor: Colors.redAccent),
        );
      }
    }
  }

  void _openCredentialManager() {
    showCredentialManagerDialog(
      context: context,
      api: _api,
      activeCredential: _activeCredential,
      activeCredentialId: _activeCredentialId,
      vaultCredentials: _vaultCredentials,
      onRefresh: _refresh,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 38,
        titleSpacing: 8,
        title: Row(
          children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(6),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.memory, size: 14, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(width: 4),
                  const Text('PecunatorCore',
                      style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, letterSpacing: 0.5)),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Text('v2.6.1', style: TextStyle(fontSize: 9, color: Colors.white.withValues(alpha: 0.3))),
          ],
        ),
        automaticallyImplyLeading: false,
        actions: [
          // Credential management
          Tooltip(
            message: 'Credenciales — Administra API keys y sub-cuentas del vault',
            waitDuration: const Duration(milliseconds: 300),
            textStyle: _tooltipStyle,
            decoration: _tooltipDecoration,
            child: IconButton(
              onPressed: _openCredentialManager,
              icon: const Icon(Icons.key, size: 18),
            ),
          ),
          // Gateway toggle
          Tooltip(
            message: _gatewayRunning
                ? 'Gateway ON${_gatewayWsConnected ? " + WS" : " (sin WS)"}\nClick para APAGAR conexión Binance'
                : 'Gateway OFF\nClick para INICIAR conexión REST+WS',
            waitDuration: const Duration(milliseconds: 300),
            textStyle: _tooltipStyle,
            decoration: _tooltipDecoration,
            child: IconButton(
              onPressed: _toggleGateway,
              icon: Icon(
                _gatewayRunning ? Icons.power_settings_new : Icons.power_off,
                size: 18,
                color: _gatewayRunning ? Colors.greenAccent : Colors.grey,
              ),
            ),
          ),
          // Clock + sync
          Tooltip(
            message: 'Reloj Binance (UTC) — Click para re-sincronizar timestamp',
            waitDuration: const Duration(milliseconds: 300),
            textStyle: _tooltipStyle,
            decoration: _tooltipDecoration,
            child: GestureDetector(
              onTap: _syncTimestamp,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 6),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.public, size: 13, color: Theme.of(context).colorScheme.primary),
                    const SizedBox(width: 3),
                    Text(_clockText, style: const TextStyle(fontSize: 11, fontFamily: 'monospace')),
                  ],
                ),
              ),
            ),
          ),
          // Refresh
          Tooltip(
            message: 'Refrescar — Actualiza gateway, credenciales y estado de servicios',
            waitDuration: const Duration(milliseconds: 300),
            textStyle: _tooltipStyle,
            decoration: _tooltipDecoration,
            child: IconButton(
              onPressed: _loading ? null : _refresh,
              icon: const Icon(Icons.refresh, size: 18),
            ),
          ),
        ],
      ),
      body: Column(
        children: [
          // ── Main unified page ──────────────────────────
          Expanded(
            child: UnifiedHubPage(engineBase: _engineBase),
          ),
          // ── Persistent footer ──────────────────────────
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            child: Row(
              children: [
                Expanded(child: CompactWeightGauge(api: _api)),
                const SizedBox(width: 8),
                SystemStatusBar(api: _api),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
