import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../widgets/compact_weight_gauge.dart';
import '../widgets/system_status_bar.dart';
import 'spot_account_page.dart';
import 'symmetric_hub_page.dart';

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
          _navBtn(Icons.dashboard_rounded, 'Dashboard', 0),
          Container(width: 1, height: 18, margin: const EdgeInsets.symmetric(horizontal: 2), color: Colors.white12),
          _navBtn(Icons.sync_alt, 'Hub Simétrico', 1),
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
                SymmetricHubPage(engineBase: _engineBase),
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
    List<Map<String, dynamic>> subaccounts = [];
    // Load subaccounts on dialog open
    _api.subaccountsList().then((resp) {
      subaccounts = (resp['accounts'] as List?)?.cast<Map<String, dynamic>>() ?? [];
    }).catchError((_) {});

    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDialogState) {
          // Reload subaccounts if empty
          if (subaccounts.isEmpty) {
            _api.subaccountsList().then((resp) {
              if (ctx.mounted) {
                setDialogState(() {
                  subaccounts = (resp['accounts'] as List?)?.cast<Map<String, dynamic>>() ?? [];
                });
              }
            }).catchError((_) {});
          }
          return AlertDialog(
            title: Row(
              children: [
                const Icon(Icons.key, size: 18),
                const SizedBox(width: 8),
                const Text('Credenciales & Sub-Cuentas'),
                const Spacer(),
                Text('Activa: $_activeCredential',
                    style: const TextStyle(fontSize: 10, color: Colors.white38)),
              ],
            ),
            content: SizedBox(
              width: 560,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    // ── Section: Vault Credentials ──
                    const Text('VAULT (API Keys)', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, letterSpacing: 1, color: Colors.white38)),
                    const SizedBox(height: 4),
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
                    const SizedBox(height: 4),
                    // List existing vault credentials
                    if (_vaultCredentials.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(8),
                        child: Text('Sin credenciales en vault', style: TextStyle(color: Colors.white24, fontSize: 10)),
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

                    const Divider(height: 16),

                    // ── Section: Sub-Account Registry ──
                    const Text('SUB-CUENTAS (Registry)', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, letterSpacing: 1, color: Colors.white38)),
                    const SizedBox(height: 4),
                    if (subaccounts.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(8),
                        child: Text('Cargando sub-cuentas...', style: TextStyle(color: Colors.white24, fontSize: 10)),
                      )
                    else
                      ...(subaccounts.map((sa) {
                        final hasKey = sa['credential_available'] == true;
                        final enabled = sa['enabled'] == true;
                        final botType = sa['bot_type'] ?? '—';
                        final role = sa['role'] ?? '';
                        final desc = sa['description'] ?? '';
                        final keyLabel = sa['api_key_label'] ?? '';
                        return Container(
                          margin: const EdgeInsets.symmetric(vertical: 2),
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                          decoration: BoxDecoration(
                            color: enabled ? Colors.white.withValues(alpha: 0.04) : Colors.white.withValues(alpha: 0.01),
                            borderRadius: BorderRadius.circular(6),
                            border: Border.all(color: hasKey ? Colors.greenAccent.withValues(alpha: 0.2) : Colors.grey.withValues(alpha: 0.1)),
                          ),
                          child: Row(
                            children: [
                              // Credential status indicator
                              Tooltip(
                                message: hasKey ? 'API key detectada en .env' : 'Sin API key en .env',
                                child: Container(
                                  width: 8, height: 8,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    color: hasKey ? Colors.greenAccent : Colors.grey.withValues(alpha: 0.3),
                                    boxShadow: hasKey ? [BoxShadow(color: Colors.greenAccent.withValues(alpha: 0.4), blurRadius: 4)] : null,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              // Account info
                              Expanded(
                                child: Column(
                                  crossAxisAlignment: CrossAxisAlignment.start,
                                  children: [
                                    Row(children: [
                                      Text(
                                        '${sa['account_id']}'.toUpperCase(),
                                        style: TextStyle(
                                          fontSize: 11, fontWeight: FontWeight.w700,
                                          color: enabled ? Colors.white : Colors.white38,
                                        ),
                                      ),
                                      const SizedBox(width: 6),
                                      Container(
                                        padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                                        decoration: BoxDecoration(
                                          color: role == 'bot' ? const Color(0xFF00E676).withValues(alpha: 0.1) : Colors.blueAccent.withValues(alpha: 0.1),
                                          borderRadius: BorderRadius.circular(3),
                                        ),
                                        child: Text(role, style: TextStyle(fontSize: 7, fontWeight: FontWeight.w600, color: role == 'bot' ? const Color(0xFF00E676) : Colors.blueAccent)),
                                      ),
                                      if (!enabled) ...[
                                        const SizedBox(width: 4),
                                        const Text('DISABLED', style: TextStyle(fontSize: 7, color: Colors.white24)),
                                      ],
                                    ]),
                                    Text(desc, style: const TextStyle(fontSize: 9, color: Colors.white38)),
                                  ],
                                ),
                              ),
                              // Key label
                              Text(keyLabel, style: const TextStyle(fontSize: 8, fontFamily: 'monospace', color: Colors.white24)),
                            ],
                          ),
                        );
                      })),
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(ctx),
                child: const Text('Cerrar'),
              ),
            ],
          );
        },
      ),
    );
  }
}
