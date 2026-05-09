import 'package:flutter/material.dart';
import '../api_client.dart';
import 'prospector_panel.dart';

/// Collapsible Prospector section — toggle icon + ProspectorPanel + manual input.
///
/// Extracted from SymmetricHubPage to keep layout orchestrators thin.
class ProspectorExpander extends StatefulWidget {
  final EngineApi api;
  final void Function(String symbol) onSymbolSelected;

  const ProspectorExpander({
    super.key,
    required this.api,
    required this.onSymbolSelected,
  });

  @override
  State<ProspectorExpander> createState() => _ProspectorExpanderState();
}

class _ProspectorExpanderState extends State<ProspectorExpander> {
  bool _expanded = false;
  final _manualCtrl = TextEditingController();

  @override
  void dispose() {
    _manualCtrl.dispose();
    super.dispose();
  }

  void _submitManual() {
    final raw = _manualCtrl.text.trim().toUpperCase();
    if (raw.isEmpty) return;
    final symbol = raw.endsWith('USDT') ? raw : '${raw}USDT';
    widget.onSymbolSelected(symbol);
    _manualCtrl.clear();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // ── Header row: toggle + manual input ───────────────
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: Row(
            children: [
              // ── Prospector toggle ─────────────────────────
              Tooltip(
                message: 'SEVI-M Prospector — Escanea Binance para encontrar el\nmejor activo eléctrico según volatilidad, liquidez y seguridad.\nAbre/cierra el panel de escaneo y resultados.',
                waitDuration: const Duration(milliseconds: 300),
                textStyle: const TextStyle(fontSize: 11, color: Colors.white),
                decoration: BoxDecoration(
                  color: const Color(0xEE1A1A2E),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.greenAccent.withValues(alpha: 0.4)),
                ),
                child: InkWell(
                  onTap: () => setState(() => _expanded = !_expanded),
                  borderRadius: BorderRadius.circular(6),
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 350),
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(6),
                      color: _expanded
                          ? Colors.greenAccent.withValues(alpha: 0.08)
                          : Colors.transparent,
                      boxShadow: _expanded
                          ? [
                              BoxShadow(
                                color: Colors.greenAccent.withValues(alpha: 0.25),
                                blurRadius: 12,
                                spreadRadius: 1,
                              ),
                            ]
                          : null,
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        // Emphasized icon with glow container
                        AnimatedContainer(
                          duration: const Duration(milliseconds: 350),
                          width: 22, height: 22,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: _expanded
                                ? Colors.greenAccent.withValues(alpha: 0.18)
                                : Colors.white.withValues(alpha: 0.04),
                            border: Border.all(
                              color: _expanded
                                  ? Colors.greenAccent.withValues(alpha: 0.6)
                                  : Colors.white.withValues(alpha: 0.1),
                              width: 1.5,
                            ),
                            boxShadow: _expanded
                                ? [
                                    BoxShadow(
                                      color: Colors.greenAccent.withValues(alpha: 0.4),
                                      blurRadius: 8,
                                    ),
                                  ]
                                : null,
                          ),
                          child: Icon(Icons.radar, size: 13,
                              color: _expanded ? Colors.greenAccent : Colors.white38),
                        ),
                        const SizedBox(width: 6),
                        Text(
                          'PROSPECTOR',
                          style: TextStyle(
                            fontSize: 10,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 1.2,
                            color: _expanded ? Colors.greenAccent : Colors.white38,
                          ),
                        ),
                        const SizedBox(width: 4),
                        Icon(
                          _expanded ? Icons.expand_less : Icons.expand_more,
                          size: 16,
                          color: Colors.white30,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const Spacer(),
              // ── Manual symbol input ───────────────────────
              SizedBox(
                width: 110,
                height: 24,
                child: TextField(
                  controller: _manualCtrl,
                  style: const TextStyle(fontSize: 10, fontFamily: 'monospace', color: Colors.amberAccent, fontWeight: FontWeight.bold),
                  textCapitalization: TextCapitalization.characters,
                  decoration: InputDecoration(
                    hintText: 'SYMBOL...',
                    hintStyle: TextStyle(fontSize: 9, color: Colors.amberAccent.withValues(alpha: 0.4)),
                    isDense: true,
                    filled: true,
                    fillColor: Colors.amberAccent.withValues(alpha: 0.1),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                    border: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(4),
                      borderSide: const BorderSide(color: Colors.amberAccent),
                    ),
                    enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(4),
                      borderSide: BorderSide(color: Colors.amberAccent.withValues(alpha: 0.6)),
                    ),
                  ),
                  onSubmitted: (_) => _submitManual(),
                ),
              ),
              const SizedBox(width: 4),
              Tooltip(
                message: 'Inyectar símbolo manualmente — envía el par a Dorothy y Elphaba sin escaneo SEVI-M',
                waitDuration: const Duration(milliseconds: 300),
                textStyle: const TextStyle(fontSize: 11, color: Colors.white),
                decoration: BoxDecoration(
                  color: const Color(0xEE1A1A2E),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.amberAccent.withValues(alpha: 0.4)),
                ),
                child: SizedBox(
                  height: 24,
                  child: OutlinedButton(
                    onPressed: _submitManual,
                    style: OutlinedButton.styleFrom(
                      side: BorderSide(color: Colors.amberAccent.withValues(alpha: 0.5)),
                      foregroundColor: Colors.amberAccent,
                      padding: const EdgeInsets.symmetric(horizontal: 8),
                      minimumSize: Size.zero,
                    ),
                    child: const Text('Go', style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700)),
                  ),
                ),
              ),
            ],
          ),
        ),
        // ── Prospector panel body ────────────────────────────
        if (_expanded)
          ProspectorPanel(
            api: widget.api,
            onSymbolSelected: widget.onSymbolSelected,
          ),
      ],
    );
  }
}
