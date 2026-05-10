import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

/// Staged Symbol Panel — configures Dorothy + Elphaba symmetric deployment.
///
/// Layout:
///   1. SHARED CONFIG: Single area for qty, profit, drop, loop, rungs (applies to both)
///   2. INDIVIDUAL OVERRIDES: Per-hub override areas (collapsed by default)
///      Opens only when user wants asymmetric config.
class StagedSymbolPanel extends StatefulWidget {
  final String symbol;
  final Map<String, dynamic>? initialPresetDorothy;
  final Map<String, dynamic>? initialPresetElphaba;
  final Function(Map<String, dynamic> dConfig, Map<String, dynamic> eConfig) onAcceptSymmetric;
  final VoidCallback onCancel;

  const StagedSymbolPanel({
    super.key,
    required this.symbol,
    this.initialPresetDorothy,
    this.initialPresetElphaba,
    required this.onAcceptSymmetric,
    required this.onCancel,
  });

  @override
  State<StagedSymbolPanel> createState() => _StagedSymbolPanelState();
}

class _StagedSymbolPanelState extends State<StagedSymbolPanel> with SingleTickerProviderStateMixin {
  late AnimationController _animCtrl;
  Timer? _beepTimer;

  // ── Shared (symmetric) controllers ──
  final _sharedQtyCtrl = TextEditingController(text: '6');
  final _sharedProfitCtrl = TextEditingController(text: '0.05');
  final _sharedDropCtrl = TextEditingController(text: '0.03');
  final _sharedLoopCtrl = TextEditingController(text: '450');
  final _sharedRungsCtrl = TextEditingController(text: '3');

  // ── Dorothy individual overrides ──
  final _dQtyCtrl = TextEditingController(text: '');
  final _dProfitCtrl = TextEditingController(text: '');
  final _dDropCtrl = TextEditingController(text: '');
  final _dLoopCtrl = TextEditingController(text: '');
  final _dRungsCtrl = TextEditingController(text: '');
  final _dTagCtrl = TextEditingController(text: 'dorothy');

  // ── Elphaba individual overrides ──
  final _eQtyCtrl = TextEditingController(text: '');
  final _eProfitCtrl = TextEditingController(text: '');
  final _eDropCtrl = TextEditingController(text: '');
  final _eLoopCtrl = TextEditingController(text: '');
  final _eRungsCtrl = TextEditingController(text: '');
  final _eTagCtrl = TextEditingController(text: 'elphaba');

  bool _showDorothyOverride = false;
  bool _showElphabaOverride = false;

  @override
  void initState() {
    super.initState();
    _animCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 500))..repeat(reverse: true);

    // Apply initial preset to shared values
    final dp = widget.initialPresetDorothy;
    if (dp != null) {
      _sharedQtyCtrl.text = dp['quote_order_qty']?.toString() ?? '6';
      _sharedProfitCtrl.text = dp['profit_factor']?.toString() ?? '0.05';
      _sharedDropCtrl.text = dp['margin_drop_factor']?.toString() ?? '0.03';
      _sharedLoopCtrl.text = dp['loop_interval_sec']?.toString() ?? '450';
      _sharedRungsCtrl.text = dp['max_rungs_per_symbol']?.toString() ?? '3';
      _dTagCtrl.text = dp['tag']?.toString() ?? 'dorothy';
    }
    final ep = widget.initialPresetElphaba;
    if (ep != null) {
      _eTagCtrl.text = ep['tag']?.toString() ?? 'elphaba';
    }

    SystemSound.play(SystemSoundType.alert);
    _beepTimer = Timer.periodic(const Duration(seconds: 60), (_) {
      SystemSound.play(SystemSoundType.alert);
    });
  }

  @override
  void dispose() {
    _animCtrl.dispose();
    _beepTimer?.cancel();
    _sharedQtyCtrl.dispose(); _sharedProfitCtrl.dispose(); _sharedDropCtrl.dispose();
    _sharedLoopCtrl.dispose(); _sharedRungsCtrl.dispose();
    _dQtyCtrl.dispose(); _dProfitCtrl.dispose(); _dDropCtrl.dispose();
    _dLoopCtrl.dispose(); _dRungsCtrl.dispose(); _dTagCtrl.dispose();
    _eQtyCtrl.dispose(); _eProfitCtrl.dispose(); _eDropCtrl.dispose();
    _eLoopCtrl.dispose(); _eRungsCtrl.dispose(); _eTagCtrl.dispose();
    super.dispose();
  }

  /// Gets the effective value: override if set, otherwise shared.
  String _effective(TextEditingController override, TextEditingController shared) {
    final ov = override.text.trim();
    return ov.isNotEmpty ? ov : shared.text.trim();
  }

  void _accept() {
    final dQty = double.tryParse(_effective(_dQtyCtrl, _sharedQtyCtrl)) ?? 0;
    final dProfit = double.tryParse(_effective(_dProfitCtrl, _sharedProfitCtrl)) ?? 0;
    final dDrop = double.tryParse(_effective(_dDropCtrl, _sharedDropCtrl)) ?? 0;
    final dLoop = int.tryParse(_effective(_dLoopCtrl, _sharedLoopCtrl)) ?? 0;
    final dRungs = int.tryParse(_effective(_dRungsCtrl, _sharedRungsCtrl)) ?? 0;

    final eQty = double.tryParse(_effective(_eQtyCtrl, _sharedQtyCtrl)) ?? 0;
    final eProfit = double.tryParse(_effective(_eProfitCtrl, _sharedProfitCtrl)) ?? 0;
    final eDrop = double.tryParse(_effective(_eDropCtrl, _sharedDropCtrl)) ?? 0;
    final eLoop = int.tryParse(_effective(_eLoopCtrl, _sharedLoopCtrl)) ?? 0;
    final eRungs = int.tryParse(_effective(_eRungsCtrl, _sharedRungsCtrl)) ?? 0;

    if (dQty <= 0 || dProfit <= 0 || dDrop <= 0 || dLoop <= 0 || dRungs <= 0 ||
        eQty <= 0 || eProfit <= 0 || eDrop <= 0 || eLoop <= 0 || eRungs <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Valores inválidos. Revisa la configuración.'), backgroundColor: Colors.redAccent),
      );
      return;
    }

    final dConfig = {
      'symbol': widget.symbol,
      'quote_order_qty': dQty.toString(),
      'profit_factor': dProfit.toString(),
      'margin_drop_factor': dDrop.toString(),
      'loop_interval_sec': dLoop.toString(),
      'max_rungs_per_symbol': dRungs.toString(),
      'tag': _dTagCtrl.text.trim(),
    };

    final eConfig = {
      'symbol': widget.symbol,
      'quote_order_qty': eQty.toString(),
      'profit_factor': eProfit.toString(),
      'margin_drop_factor': eDrop.toString(),
      'loop_interval_sec': eLoop.toString(),
      'max_rungs_per_symbol': eRungs.toString(),
      'tag': _eTagCtrl.text.trim(),
    };

    widget.onAcceptSymmetric(dConfig, eConfig);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _animCtrl,
      builder: (ctx, child) {
        final flashColor = Color.lerp(Colors.redAccent.withAlpha(50), Colors.redAccent.withAlpha(150), _animCtrl.value)!;
        final borderColor = Color.lerp(Colors.redAccent, Colors.yellowAccent, _animCtrl.value)!;

        return Container(
          margin: const EdgeInsets.symmetric(vertical: 8),
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: flashColor,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: borderColor, width: 2),
            boxShadow: [
              BoxShadow(color: borderColor.withAlpha(100), blurRadius: 10, spreadRadius: 2),
            ],
          ),
          child: child,
        );
      },
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // ── Header ──
          Row(
            children: [
              const Icon(Icons.warning_amber_rounded, color: Colors.yellowAccent, size: 24),
              const SizedBox(width: 8),
              const Text(
                'SÍMBOLO EN STAGING',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: Colors.yellowAccent, letterSpacing: 1),
              ),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.close, color: Colors.white54),
                onPressed: widget.onCancel,
              ),
            ],
          ),
          const SizedBox(height: 4),
          Row(
            children: [
              const Text('Symbol: ', style: TextStyle(fontSize: 12, color: Colors.white70)),
              Text(widget.symbol, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white, fontFamily: 'monospace')),
            ],
          ),
          const SizedBox(height: 10),

          // ── SHARED SYMMETRIC CONFIG ──
          _buildSharedSection(),

          const SizedBox(height: 8),

          // ── INDIVIDUAL OVERRIDES ──
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(child: _buildOverrideSection('Dorothy (Long)', Colors.tealAccent, _showDorothyOverride, () {
                setState(() => _showDorothyOverride = !_showDorothyOverride);
              }, _dQtyCtrl, _dProfitCtrl, _dDropCtrl, _dLoopCtrl, _dRungsCtrl, _dTagCtrl)),
              const SizedBox(width: 8),
              Expanded(child: _buildOverrideSection('Elphaba (Short)', Colors.purpleAccent, _showElphabaOverride, () {
                setState(() => _showElphabaOverride = !_showElphabaOverride);
              }, _eQtyCtrl, _eProfitCtrl, _eDropCtrl, _eLoopCtrl, _eRungsCtrl, _eTagCtrl)),
            ],
          ),

          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              TextButton(
                onPressed: widget.onCancel,
                child: const Text('Descartar', style: TextStyle(color: Colors.white54)),
              ),
              const SizedBox(width: 12),
              FilledButton.icon(
                onPressed: _accept,
                icon: const Icon(Icons.check_circle_outline),
                label: const Text('DESPLEGAR SIMÉTRICO', style: TextStyle(fontWeight: FontWeight.bold)),
                style: FilledButton.styleFrom(
                  backgroundColor: Colors.greenAccent.shade700,
                  foregroundColor: Colors.white,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// Shared config section — applies to both hubs symmetrically.
  Widget _buildSharedSection() {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.white.withAlpha(10),
        border: Border.all(color: Colors.cyanAccent.withAlpha(80)),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(Icons.link, size: 14, color: Colors.cyanAccent.withAlpha(180)),
              const SizedBox(width: 6),
              Text('CONFIG SIMÉTRICA', style: TextStyle(
                color: Colors.cyanAccent.withAlpha(200),
                fontWeight: FontWeight.w900,
                fontSize: 11,
                letterSpacing: 0.5,
              )),
              const Spacer(),
              Text('Aplica a ambos hubs', style: TextStyle(
                color: Colors.white.withAlpha(100),
                fontSize: 9,
              )),
            ],
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _buildField('Qty USDT', _sharedQtyCtrl),
              _buildField('Profit %', _sharedProfitCtrl),
              _buildField('Drop %', _sharedDropCtrl),
              _buildField('Loop (s)', _sharedLoopCtrl),
              _buildField('Max Rungs', _sharedRungsCtrl),
            ],
          ),
        ],
      ),
    );
  }

  /// Individual override section — collapsed by default. When expanded,
  /// empty fields inherit from shared config, filled fields override.
  Widget _buildOverrideSection(String title, Color accentColor, bool expanded, VoidCallback onToggle,
      TextEditingController qty, TextEditingController profit, TextEditingController drop,
      TextEditingController loop, TextEditingController rungs, TextEditingController tag) {
    return Container(
      padding: const EdgeInsets.all(6),
      decoration: BoxDecoration(
        color: Colors.black26,
        border: Border.all(color: accentColor.withAlpha(expanded ? 120 : 50)),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          InkWell(
            onTap: onToggle,
            child: Row(
              children: [
                Text(title, style: TextStyle(color: accentColor, fontWeight: FontWeight.bold, fontSize: 11)),
                const Spacer(),
                Text(expanded ? 'override activo' : 'usar simétrico',
                    style: TextStyle(fontSize: 8, color: accentColor.withAlpha(120))),
                const SizedBox(width: 4),
                Icon(expanded ? Icons.expand_less : Icons.expand_more, size: 14, color: accentColor.withAlpha(120)),
              ],
            ),
          ),
          if (!expanded)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Wrap(
                spacing: 6,
                children: [
                  _buildField('Tag', tag, width: 100),
                ],
              ),
            ),
          if (expanded) ...[
            const SizedBox(height: 4),
            Text('Dejar vacío = hereda config simétrica',
                style: TextStyle(fontSize: 8, color: Colors.white.withAlpha(80), fontStyle: FontStyle.italic)),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                _buildField('Qty USDT', qty, hint: _sharedQtyCtrl.text),
                _buildField('Profit %', profit, hint: _sharedProfitCtrl.text),
                _buildField('Drop %', drop, hint: _sharedDropCtrl.text),
                _buildField('Loop (s)', loop, hint: _sharedLoopCtrl.text),
                _buildField('Rungs', rungs, hint: _sharedRungsCtrl.text),
                _buildField('Tag', tag, width: 100),
              ],
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildField(String label, TextEditingController ctrl, {double width = 75, String? hint}) {
    return SizedBox(
      width: width,
      child: TextField(
        controller: ctrl,
        style: const TextStyle(fontSize: 11, fontFamily: 'monospace', color: Colors.white, fontWeight: FontWeight.bold),
        decoration: InputDecoration(
          labelText: label,
          hintText: hint,
          hintStyle: TextStyle(color: Colors.white.withAlpha(40), fontSize: 10),
          labelStyle: const TextStyle(color: Colors.white54, fontSize: 9),
          filled: true,
          fillColor: Colors.black45,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: BorderSide.none),
          contentPadding: const EdgeInsets.symmetric(horizontal: 6, vertical: 6),
          isDense: true,
        ),
      ),
    );
  }
}
