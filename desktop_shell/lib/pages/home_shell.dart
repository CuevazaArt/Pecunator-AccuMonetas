import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/compact_weight_gauge.dart';
import '../widgets/system_status_bar.dart';
import 'dorothy_page.dart';
import 'masha_hub_page.dart';
import 'thusnelda_hub_page.dart';
import 'spot_account_page.dart';
import 'system_dashboard_page.dart';

/// Home shell — main app scaffold with navigation, gateway lifecycle,
/// credential management, and Binance clock.
///
/// Each bot hub is a separate page via the tab system.
class HomeShell extends StatefulWidget {
  const HomeShell({super.key});

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  static const _engineBase = 'http://127.0.0.1:8000';

  int _currentIndex = 0;
  bool _gatewayRunning = false;
  bool _gatewayWsConnected = false;
  String _activeCredential = 'none';
  String _activeCredentialId = '';
  List<Map<String, dynamic>> _vaultCredentials = [];
  Timer? _refreshTimer;
  Timer? _clockTimer;
  String _clockText = '--:--:--';
  DateTime? _binanceSrvUtc;
  DateTime? _binanceSrvObservedUtc;
  bool _loading = false;

  // Credential form controllers
  final _credLabelCtrl = TextEditingController();
  final _credKeyCtrl = TextEditingController();
  final _credSecretCtrl = TextEditingController();

  EngineApi get _api => EngineApi(_engineBase);

  @override
  void initState() {
    super.initState();
    _tickClock();
    _refresh();
    _refreshTimer = Timer.periodic(const Duration(seconds: 15), (_) => _silentRefresh());
    _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(_tickClock);
    });
    // Auto-start gateway
    WidgetsBinding.instance.addPostFrameCallback((_) => _autoStartGateway());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    _clockTimer?.cancel();
    _credLabelCtrl.dispose();
    _credKeyCtrl.dispose();
    _credSecretCtrl.dispose();
    super.dispose();
  }

  void _tickClock() {
    if (_binanceSrvUtc != null && _binanceSrvObservedUtc != null) {
      final elapsed = DateTime.now().difference(_binanceSrvObservedUtc!);
      final estimated = _binanceSrvUtc!.add(elapsed);
      _clockText = '${_pad(estimated.hour)}:${_pad(estimated.minute)}:${_pad(estimated.second)} UTC';
    } else {
      final now = DateTime.now().toUtc();
      _clockText = '${_pad(now.hour)}:${_pad(now.minute)}:${_pad(now.second)} UTC*';
    }
  }

  String _pad(int n) => n.toString().padLeft(2, '0');

  Future<void> _refresh() async {
    setState(() => _loading = true);
    await _fetchState();
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _silentRefresh() async {
    await _fetchState();
  }

  Future<void> _fetchState() async {
    try {
      final snap = await _api.gatewaySnapshot();
      if (!mounted) return;
      setState(() {
        _gatewayRunning = snap['gateway_running'] == true;
        _gatewayWsConnected = snap['ws_connected'] == true;

        // Parse Binance server time
        final srvMs = snap['binance_server_time_ms'];
        if (srvMs is int && srvMs > 0) {
          _binanceSrvUtc = DateTime.fromMillisecondsSinceEpoch(srvMs, isUtc: true);
          _binanceSrvObservedUtc = DateTime.now();
        }
      });
    } catch (_) {}

    // Fetch credentials
    try {
      final active = await _api.activeCredential();
      final vault = await _api.vaultCredentials();
      if (!mounted) return;
      setState(() {
        final label = active['label'] ?? '';
        final keyLast4 = (active['api_key_last4'] ?? '');
        _activeCredential = '$label · ...$keyLast4';
        _activeCredentialId = '${active['credential_id'] ?? ''}';
        _vaultCredentials = (vault['items'] as List?)?.cast<Map<String, dynamic>>() ?? [];
      });
    } catch (_) {}
  }

  Future<void> _autoStartGateway() async {
    try {
      final snap = await _api.gatewaySnapshot();
      if (snap['gateway_running'] != true) {
        await _api.gatewayStart();
        await _refresh();
      }
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
          SnackBar(content: Text('Gateway error: $e'), backgroundColor: Colors.redAccent),
        );
      }
    }
  }

  Future<void> _syncTimestamp() async {
    try {
      await _api.syncTimestamp();
      await _refresh();
    } catch (_) {}
  }

  Widget _navBtn(IconData icon, String tooltip, int idx) {
    final active = _currentIndex == idx;
    return IconButton(
      onPressed: () => setState(() => _currentIndex = idx),
      tooltip: tooltip,
      icon: Icon(icon, size: 18,
          color: active ? Theme.of(context).colorScheme.primary : null),
      style: active
          ? IconButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.primary.withValues(alpha: 0.15),
            )
          : null,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PecunatorCore'),
        automaticallyImplyLeading: false,
        actions: [
          // ── Page navigation ──
          _navBtn(Icons.home_rounded, 'Home', 0),
          Container(width: 1, height: 18, margin: const EdgeInsets.symmetric(horizontal: 2), color: Colors.white12),
          _navBtn(Icons.trending_up, 'Dorothy', 1),
          _navBtn(Icons.psychology_alt_outlined, 'Masha', 2),
          _navBtn(Icons.hub_outlined, 'Thusnelda', 3),
          Container(width: 1, height: 18, margin: const EdgeInsets.symmetric(horizontal: 2), color: Colors.white12),
          _navBtn(Icons.settings_outlined, 'Sistema', 4),
          const SizedBox(width: 4),
          Container(width: 1, height: 24, color: Colors.white24),
          const SizedBox(width: 4),
          // Credential management
          IconButton(
            onPressed: _openCredentialManager,
            tooltip: 'API keys',
            icon: const Icon(Icons.key, size: 18),
          ),
          // Gateway toggle
          IconButton(
            onPressed: _toggleGateway,
            tooltip: _gatewayRunning
                ? 'Gateway ON${_gatewayWsConnected ? " · WS" : ""}'
                : 'Gateway OFF',
            icon: Icon(
              _gatewayRunning ? Icons.power_settings_new : Icons.power_off,
              size: 18,
              color: _gatewayRunning ? Colors.greenAccent : Colors.grey,
            ),
          ),
          // Clock + sync
          GestureDetector(
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
          // Refresh
          IconButton(
            onPressed: _loading ? null : _refresh,
            tooltip: 'Refrescar',
            icon: const Icon(Icons.refresh, size: 18),
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: IndexedStack(
              index: _currentIndex,
              children: [
                AccountDashboardPage(
                  engineBase: _engineBase,
                  activeSymbols: const [],
                ),
                DorothyPage(engineBase: _engineBase),
                MashaHubPage(engineBase: _engineBase),
                ThusneldaHubPage(engineBase: _engineBase),
                SystemDashboardPage(api: _api),
              ],
            ),
          ),
          // Persistent footer
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

  // ── Credential Manager Dialog ──────────────────────────────────

  void _openCredentialManager() {
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) => AlertDialog(
          title: Row(
            children: [
              const Icon(Icons.key, size: 18),
              const SizedBox(width: 8),
              const Text('API Credentials'),
              const Spacer(),
              Text('Active: $_activeCredential',
                  style: const TextStyle(fontSize: 10, color: Colors.white38)),
            ],
          ),
          content: SizedBox(
            width: 500,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // Add new credential
                Row(
                  children: [
                    SizedBox(width: 80, child: TextField(
                      controller: _credLabelCtrl,
                      style: const TextStyle(fontSize: 11),
                      decoration: const InputDecoration(
                        labelText: 'Label', isDense: true,
                        contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                      ),
                    )),
                    const SizedBox(width: 4),
                    Expanded(child: TextField(
                      controller: _credKeyCtrl,
                      style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
                      decoration: const InputDecoration(
                        labelText: 'API Key', isDense: true,
                        contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                      ),
                    )),
                    const SizedBox(width: 4),
                    Expanded(child: TextField(
                      controller: _credSecretCtrl,
                      obscureText: true,
                      style: const TextStyle(fontSize: 11, fontFamily: 'monospace'),
                      decoration: const InputDecoration(
                        labelText: 'Secret', isDense: true,
                        contentPadding: EdgeInsets.symmetric(horizontal: 6, vertical: 6),
                      ),
                    )),
                    const SizedBox(width: 4),
                    FilledButton(
                      onPressed: () async {
                        final key = _credKeyCtrl.text.trim();
                        final secret = _credSecretCtrl.text.trim();
                        if (key.isEmpty || secret.isEmpty) return;
                        try {
                          await _api.addVaultCredential(
                            apiKey: key,
                            apiSecret: secret,
                            label: _credLabelCtrl.text.trim(),
                          );
                          _credKeyCtrl.clear();
                          _credSecretCtrl.clear();
                          _credLabelCtrl.clear();
                          await _refresh();
                          final vault = await _api.vaultCredentials();
                          setDialogState(() {
                            _vaultCredentials = (vault['items'] as List?)?.cast<Map<String, dynamic>>() ?? [];
                          });
                        } catch (e) {
                          if (ctx.mounted) {
                            ScaffoldMessenger.of(ctx).showSnackBar(
                              SnackBar(content: Text('$e'), backgroundColor: Colors.redAccent),
                            );
                          }
                        }
                      },
                      child: const Text('Add', style: TextStyle(fontSize: 11)),
                    ),
                  ],
                ),
                const Divider(),
                // List existing
                if (_vaultCredentials.isEmpty)
                  const Padding(
                    padding: EdgeInsets.all(12),
                    child: Text('No credentials stored', style: TextStyle(color: Colors.white38)),
                  )
                else
                  ...(_vaultCredentials.map((cred) {
                    final id = '${cred['credential_id'] ?? ''}';
                    final label = '${cred['label'] ?? 'unnamed'}';
                    final last4 = '${cred['api_key_last4'] ?? ''}';
                    final isActive = id == _activeCredentialId;
                    return ListTile(
                      dense: true,
                      leading: Icon(
                        isActive ? Icons.check_circle : Icons.circle_outlined,
                        color: isActive ? Colors.greenAccent : Colors.grey,
                        size: 18,
                      ),
                      title: Text('$label · ...$last4',
                          style: TextStyle(fontSize: 12, fontWeight: isActive ? FontWeight.w800 : FontWeight.normal)),
                      trailing: IconButton(
                        icon: const Icon(Icons.delete_outline, size: 16, color: Colors.redAccent),
                        onPressed: () async {
                          await _api.deleteVaultCredential(id);
                          await _refresh();
                          final vault = await _api.vaultCredentials();
                          setDialogState(() {
                            _vaultCredentials = (vault['items'] as List?)?.cast<Map<String, dynamic>>() ?? [];
                          });
                        },
                      ),
                    );
                  })),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cerrar'),
            ),
          ],
        ),
      ),
    );
  }
}
