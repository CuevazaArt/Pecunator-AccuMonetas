/// Gateway status indicator widget.
library;

import 'package:flutter/material.dart';

class GatewayStatus extends StatelessWidget {
  final bool isRunning;
  final bool wsConnected;

  const GatewayStatus({
    super.key,
    required this.isRunning,
    required this.wsConnected,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4),
      child: Center(
        child: Text(
          'GW ${isRunning ? "ON" : "OFF"}'
          '${wsConnected ? " · WS" : ""}',
          style: TextStyle(
            fontSize: 11,
            fontFamily: 'monospace',
            color: isRunning
                ? Theme.of(context).colorScheme.primary
                : Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}
