import 'package:flutter/material.dart';
import '../api_client.dart';

/// Dual hemisphere toggle for Louise bots.
///
/// Displays independent on/off switches for the Louise (LONG) and
/// AntiLouise (SHORT) hemispheres. Each toggle calls the backend
/// independently so one side can be enabled while the other is off.
class HemisphereToggle extends StatefulWidget {
  final String botId;
  final bool louiseEnabled;
  final bool antiLouiseEnabled;
  final EngineApi api;
  final VoidCallback onChanged;

  const HemisphereToggle({
    super.key,
    required this.botId,
    required this.louiseEnabled,
    required this.antiLouiseEnabled,
    required this.api,
    required this.onChanged,
  });

  @override
  State<HemisphereToggle> createState() => _HemisphereToggleState();
}

class _HemisphereToggleState extends State<HemisphereToggle> {
  late bool _louiseOn;
  late bool _antiOn;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _louiseOn = widget.louiseEnabled;
    _antiOn = widget.antiLouiseEnabled;
  }

  @override
  void didUpdateWidget(HemisphereToggle old) {
    super.didUpdateWidget(old);
    // Sync when parent pushes a fresh snapshot (WS update)
    if (!_busy) {
      _louiseOn = widget.louiseEnabled;
      _antiOn = widget.antiLouiseEnabled;
    }
  }

  Future<void> _toggle({required bool louiseEnabled, required bool antiEnabled}) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await widget.api.louisePatchHemispheres(
        widget.botId,
        louiseEnabled: louiseEnabled,
        antiLouiseEnabled: antiEnabled,
      );
      setState(() {
        _louiseOn = louiseEnabled;
        _antiOn = antiEnabled;
      });
      widget.onChanged();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Error al cambiar hemisferio: $e'),
            backgroundColor: Colors.redAccent,
            duration: const Duration(seconds: 3),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withAlpha(5),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white10),
      ),
      child: Row(
        children: [
          const Text(
            'Hemisferios',
            style: TextStyle(fontSize: 11, color: Colors.white54),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Row(
              children: [
                _hemisphereChip(
                  label: 'LONG',
                  sublabel: 'Louise',
                  enabled: _louiseOn,
                  activeColor: Colors.greenAccent,
                  icon: Icons.trending_up,
                  onToggle: _busy
                      ? null
                      : (val) => _toggle(louiseEnabled: val, antiEnabled: _antiOn),
                ),
                const SizedBox(width: 12),
                _hemisphereChip(
                  label: 'SHORT',
                  sublabel: 'AntiLouise',
                  enabled: _antiOn,
                  activeColor: Colors.redAccent,
                  icon: Icons.trending_down,
                  onToggle: _busy
                      ? null
                      : (val) => _toggle(louiseEnabled: _louiseOn, antiEnabled: val),
                ),
              ],
            ),
          ),
          if (_busy)
            const Padding(
              padding: EdgeInsets.only(left: 8),
              child: SizedBox(
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
        ],
      ),
    );
  }

  Widget _hemisphereChip({
    required String label,
    required String sublabel,
    required bool enabled,
    required Color activeColor,
    required IconData icon,
    required void Function(bool)? onToggle,
  }) {
    final color = enabled ? activeColor : Colors.white24;
    return Expanded(
      child: GestureDetector(
        onTap: onToggle == null ? null : () => onToggle(!enabled),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          decoration: BoxDecoration(
            color: color.withAlpha(enabled ? 20 : 8),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: color.withAlpha(enabled ? 80 : 30)),
          ),
          child: Row(
            children: [
              Icon(icon, size: 16, color: color),
              const SizedBox(width: 8),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      label,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.bold,
                        color: color,
                      ),
                    ),
                    Text(
                      sublabel,
                      style: const TextStyle(
                        fontSize: 9,
                        color: Colors.white38,
                      ),
                    ),
                  ],
                ),
              ),
              Switch(
                value: enabled,
                onChanged: onToggle,
                activeColor: activeColor,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
