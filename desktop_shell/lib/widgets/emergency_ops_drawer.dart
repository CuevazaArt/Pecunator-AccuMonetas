import 'package:flutter/material.dart';
import '../api_client.dart';

/// Collapsible emergency operations panel — collapsed by default.
/// Provides one-click access to Close Protocol, Cancel Limits,
/// RED BUTTON, and Fuse Reset.
class EmergencyOpsDrawer extends StatefulWidget {
  final EngineApi api;
  const EmergencyOpsDrawer({super.key, required this.api});

  @override
  State<EmergencyOpsDrawer> createState() => _EmergencyOpsDrawerState();
}

class _EmergencyOpsDrawerState extends State<EmergencyOpsDrawer> {
  bool _expanded = false;
  bool _operating = false;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.redAccent.withValues(alpha: _expanded ? 0.06 : 0.02),
        borderRadius: BorderRadius.circular(6),
        border: Border.all(
          color: Colors.redAccent.withValues(alpha: _expanded ? 0.2 : 0.08),
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            borderRadius: BorderRadius.circular(6),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              child: Row(
                children: [
                  Icon(
                    Icons.warning_amber_rounded,
                    size: 11,
                    color: Colors.redAccent.withValues(alpha: 0.5),
                  ),
                  const SizedBox(width: 5),
                  Text(
                    'EMERGENCY OPS',
                    style: TextStyle(
                      fontSize: 8,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 0.8,
                      color: Colors.redAccent.withValues(alpha: 0.5),
                    ),
                  ),
                  const Spacer(),
                  Icon(
                    _expanded ? Icons.expand_less : Icons.expand_more,
                    size: 14,
                    color: Colors.white24,
                  ),
                ],
              ),
            ),
          ),
          if (_expanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(10, 0, 10, 8),
              child: Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  _opBtn('Close Protocol', Icons.cancel, Colors.orangeAccent, 'close'),
                  _opBtn('Cancel Limits', Icons.remove_circle, Colors.amber, 'cancel_limits'),
                  _opBtn('RED BUTTON', Icons.emergency, Colors.redAccent, 'red_button'),
                  _opBtn('Reset Fuse', Icons.flash_on, Colors.cyanAccent, 'reset_fuse'),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _opBtn(String label, IconData icon, Color color, String action) {
    return SizedBox(
      height: 24,
      child: OutlinedButton.icon(
        onPressed: _operating ? null : () => _confirmOp(label, action),
        icon: Icon(icon, size: 10, color: color),
        label: Text(label, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w700, color: color)),
        style: OutlinedButton.styleFrom(
          side: BorderSide(color: color.withValues(alpha: 0.25)),
          padding: const EdgeInsets.symmetric(horizontal: 8),
          backgroundColor: color.withValues(alpha: 0.04),
        ),
      ),
    );
  }

  Future<void> _confirmOp(String label, String action) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF1A1A1A),
        title: Text('¿Ejecutar $label?', style: const TextStyle(color: Colors.white)),
        content: const Text('Esta operación es irreversible.', style: TextStyle(color: Colors.white70)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancelar', style: TextStyle(color: Colors.white54))),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(backgroundColor: Colors.redAccent),
            child: const Text('Ejecutar', style: TextStyle(fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
    if (ok == true && mounted) {
      _executeOp(action);
    }
  }

  Future<void> _executeOp(String op) async {
    setState(() => _operating = true);
    try {
      if (op == 'close') {
        await widget.api.executeCloseProtocol();
      } else if (op == 'cancel_limits') {
        await widget.api.executeOrderCleanupLimit();
      } else if (op == 'red_button') {
        await widget.api.executeRedButton();
      } else if (op == 'reset_fuse') {
        await widget.api.apiFuseReset();
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('$op completado'), backgroundColor: Colors.green),
        );
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Error: $e'), backgroundColor: Colors.redAccent),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _operating = false);
      }
    }
  }
}
