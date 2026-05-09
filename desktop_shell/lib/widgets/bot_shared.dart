import 'package:flutter/material.dart';

/// Reusable KPI (Key Performance Indicator) card widget used across all bot hub pages.
/// Shows a label/value pair in a compact, styled container.
class KpiCard extends StatelessWidget {
  final String label;
  final String value;
  final Color? valueColor;
  final IconData? icon;

  const KpiCard({
    super.key,
    required this.label,
    required this.value,
    this.valueColor,
    this.icon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: Colors.black26,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.grey.withAlpha(50)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 16, color: Colors.grey),
            const SizedBox(height: 4),
          ],
          Text(
            label,
            style: const TextStyle(fontSize: 10, color: Colors.grey),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 2),
          Text(
            value,
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.bold,
              color: valueColor ?? Colors.white,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }
}


/// Reusable bot action button row (Start/Stop/RunOnce/Delete).
/// Used by Dorothy and Elphaba hub pages.
class BotActionRow extends StatelessWidget {
  final bool isRunning;
  final bool isLoading;
  final VoidCallback? onStart;
  final VoidCallback? onStop;
  final VoidCallback? onRunOnce;
  final VoidCallback? onDelete;

  const BotActionRow({
    super.key,
    required this.isRunning,
    this.isLoading = false,
    this.onStart,
    this.onStop,
    this.onRunOnce,
    this.onDelete,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Tooltip(
          message: isRunning ? 'Detener bot' : 'Iniciar bot',
          child: IconButton(
            icon: Icon(
              isRunning ? Icons.stop_circle : Icons.play_circle,
              color: isRunning ? Colors.redAccent : Colors.greenAccent,
            ),
            onPressed: isLoading ? null : (isRunning ? onStop : onStart),
          ),
        ),
        if (onRunOnce != null)
          Tooltip(
            message: 'Ejecutar 1 ciclo',
            child: IconButton(
              icon: const Icon(Icons.skip_next, color: Colors.orangeAccent),
              onPressed: isLoading || isRunning ? null : onRunOnce,
            ),
          ),
        if (onDelete != null)
          Tooltip(
            message: 'Eliminar bot',
            child: IconButton(
              icon: const Icon(Icons.delete_outline, color: Colors.grey),
              onPressed: isLoading || isRunning ? null : onDelete,
            ),
          ),
      ],
    );
  }
}


/// Reusable bot status indicator (running/stopped/error).
class BotStatusBadge extends StatelessWidget {
  final bool isRunning;
  final bool hasError;
  final String? errorText;

  const BotStatusBadge({
    super.key,
    required this.isRunning,
    this.hasError = false,
    this.errorText,
  });

  @override
  Widget build(BuildContext context) {
    final Color color;
    final String label;

    if (hasError) {
      color = Colors.redAccent;
      label = 'ERROR';
    } else if (isRunning) {
      color = Colors.greenAccent;
      label = 'RUNNING';
    } else {
      color = Colors.grey;
      label = 'STOPPED';
    }

    return Tooltip(
      message: errorText ?? label,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: color.withAlpha(30),
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: color.withAlpha(100)),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: color,
            fontSize: 10,
            fontWeight: FontWeight.bold,
          ),
        ),
      ),
    );
  }
}


/// Reusable bot log viewer panel.
class BotLogPanel extends StatelessWidget {
  final String logs;
  final ScrollController? scrollController;
  final double height;

  const BotLogPanel({
    super.key,
    required this.logs,
    this.scrollController,
    this.height = 200,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: height,
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(4),
      ),
      child: SingleChildScrollView(
        controller: scrollController,
        child: SelectableText(
          logs.isEmpty ? '(sin logs)' : logs,
          style: const TextStyle(
            fontFamily: 'monospace',
            fontSize: 11,
            color: Colors.grey,
          ),
        ),
      ),
    );
  }
}


/// Reusable labeled form field for bot configuration.
class BotFormField extends StatelessWidget {
  final String label;
  final String? tooltip;
  final TextEditingController controller;
  final TextInputType? keyboardType;
  final double width;

  const BotFormField({
    super.key,
    required this.label,
    required this.controller,
    this.tooltip,
    this.keyboardType,
    this.width = 120,
  });

  @override
  Widget build(BuildContext context) {
    final field = SizedBox(
      width: width,
      child: TextField(
        controller: controller,
        keyboardType: keyboardType,
        decoration: InputDecoration(
          labelText: label,
          isDense: true,
          contentPadding:
              const EdgeInsets.symmetric(horizontal: 8, vertical: 10),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(6),
          ),
        ),
        style: const TextStyle(fontSize: 12),
      ),
    );

    if (tooltip != null) {
      return Tooltip(message: tooltip!, child: field);
    }
    return field;
  }
}
