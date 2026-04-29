/// Bots management screen (refactored, modular version).

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../providers/app_providers.dart';
import '../widgets/error_display.dart';
import '../widgets/gateway_status.dart';

class BotsScreen extends ConsumerStatefulWidget {
  final ValueChanged<bool> onThemeChanged;

  const BotsScreen({
    super.key,
    required this.onThemeChanged,
  });

  @override
  ConsumerState<BotsScreen> createState() => _BotsScreenState();
}

class _BotsScreenState extends ConsumerState<BotsScreen> {
  String _error = '';

  @override
  Widget build(BuildContext context) {
    // Watch gateway status
    final gatewayAsync = ref.watch(gatewaySnapshotProvider);
    final botsAsync = ref.watch(hubBotsProvider);
    final activeCredAsync = ref.watch(activeCredentialProvider);

    return RefreshIndicator(
      onRefresh: () async {
        // Trigger refreshes
        ref.refresh(hubBotsProvider);
        ref.refresh(gatewaySnapshotProvider);
        ref.refresh(activeCredentialProvider);
      },
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Error display
            if (_error.isNotEmpty)
              ErrorDisplay(
                error: _error,
                onDismiss: () => setState(() => _error = ''),
              ),

            // Gateway status + controls
            gatewayAsync.when(
              data: (data) => _buildGatewayBar(data),
              loading: () => const SizedBox(height: 40),
              error: (err, _) => _buildGatewayBarError(),
            ),

            const SizedBox(height: 12),

            // Active credential info
            activeCredAsync.when(
              data: (data) => _buildActiveCredentialInfo(data),
              loading: () => const Padding(
                padding: EdgeInsets.only(bottom: 8),
                child: LinearProgressIndicator(),
              ),
              error: (err, _) => const SizedBox.shrink(),
            ),

            // Bots list
            botsAsync.when(
              data: (data) => _buildBotsList(data),
              loading: () => const Center(
                child: Padding(
                  padding: EdgeInsets.all(20),
                  child: CircularProgressIndicator(),
                ),
              ),
              error: (err, stack) {
                WidgetsBinding.instance.addPostFrameCallback((_) {
                  setState(() => _error = err.toString());
                });
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Text(
                      'Error: $err',
                      style: const TextStyle(color: Colors.redAccent),
                    ),
                  ),
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGatewayBar(Map<String, dynamic> data) {
    final running = data['gateway_running'] == true;
    final wsConnected = data['ws_connected'] == true;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            GatewayStatus(isRunning: running, wsConnected: wsConnected),
            const Spacer(),
            FilledButton.icon(
              onPressed: () => _startGateway(),
              icon: const Icon(Icons.cloud_upload_outlined, size: 18),
              label: const Text('Iniciar'),
            ),
            const SizedBox(width: 8),
            FilledButton.icon(
              onPressed: () => _stopGateway(),
              icon: const Icon(Icons.cloud_off_outlined, size: 18),
              label: const Text('Detener'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildGatewayBarError() {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Icon(
              Icons.cloud_off_outlined,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
              size: 18,
            ),
            const SizedBox(width: 8),
            Text(
              'Gateway: No disponible',
              style: TextStyle(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                fontSize: 12,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildActiveCredentialInfo(Map<String, dynamic> data) {
    final label = (data['label'] ?? '').toString().trim();
    final last4 = (data['public_key_last4'] ?? '-').toString();
    final source = (data['source'] ?? 'none').toString();
    final display = label.isNotEmpty
        ? label
        : (data['active_credential_id'] ?? '-').toString();

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        'API activa: $display · $last4 · $source',
        style: TextStyle(
          fontSize: 12,
          color: Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
    );
  }

  Widget _buildBotsList(Map<String, dynamic> data) {
    final bots = (data['bots'] as List?) ?? [];

    if (bots.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Text(
            'Sin instancias Dorothy. Crea la primera desde el panel de control.',
            style: TextStyle(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
      );
    }

    return Column(
      children: [
        Text(
          '${bots.length} instancia${bots.length != 1 ? 's' : ''} disponible${bots.length != 1 ? 's' : ''}',
          style: const TextStyle(fontSize: 12),
        ),
        const SizedBox(height: 12),
        ...bots.map<Widget>((bot) {
          final botData = Map<String, dynamic>.from(bot as Map);
          final botId = (botData['bot_id'] ?? '').toString();
          final tag = (botData['tag'] ?? 'Dorothy').toString();
          final symbol = (botData['symbol'] ?? 'XRPUSDT').toString();
          final running = botData['running'] == true;

          return Card(
            margin: const EdgeInsets.only(bottom: 8),
            child: ListTile(
              leading: Icon(
                Icons.circle,
                size: 12,
                color: running ? Colors.greenAccent : Colors.redAccent,
              ),
              title: Text(
                '$tag · $symbol',
                style: const TextStyle(fontFamily: 'monospace'),
              ),
              subtitle: Text(botId, style: const TextStyle(fontSize: 11)),
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  FilledButton.tonal(
                    onPressed: () {},
                    child: Text(running ? 'ACTIVO' : 'INACTIVO'),
                  ),
                  const SizedBox(width: 8),
                  IconButton(
                    onPressed: () {},
                    icon: const Icon(Icons.delete_outline, size: 18),
                  ),
                ],
              ),
            ),
          );
        }).toList(),
      ],
    );
  }

  Future<void> _startGateway() async {
    final api = ref.read(engineApiProvider);
    try {
      await api.gatewayStart();
      ref.refresh(gatewaySnapshotProvider);
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }

  Future<void> _stopGateway() async {
    final api = ref.read(engineApiProvider);
    try {
      await api.gatewayStop();
      ref.refresh(gatewaySnapshotProvider);
    } catch (e) {
      setState(() => _error = e.toString());
    }
  }
}
