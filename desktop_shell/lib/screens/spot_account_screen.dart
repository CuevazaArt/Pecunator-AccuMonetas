/// Spot account view (refactored for modularity).

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../config/app_config.dart';
import '../providers/app_providers.dart';
import '../utils/number_formatter.dart';

class SpotAccountScreen extends ConsumerWidget {
  const SpotAccountScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: const EdgeInsets.all(12),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Resumen de cuenta Spot en Binance',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 12),
            ref.watch(gatewaySnapshotProvider).when(
              data: (_) => const Text(
                'Gateway disponible. Cargar resumen...',
                style: TextStyle(fontSize: 12),
              ),
              loading: () => const CircularProgressIndicator(),
              error: (err, _) => Text(
                'Error: $err',
                style: const TextStyle(color: Colors.redAccent),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
