import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

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

  // Dorothy controllers
  final _dQtyCtrl = TextEditingController(text: '6');
  final _dProfitCtrl = TextEditingController(text: '0.05');
  final _dDropCtrl = TextEditingController(text: '0.03');
  final _dLoopCtrl = TextEditingController(text: '450');
  final _dMaxRungsCtrl = TextEditingController(text: '3');
  final _dTagCtrl = TextEditingController(text: 'dorothy');

  // Elphaba controllers
  final _eQtyCtrl = TextEditingController(text: '6');
  final _eProfitCtrl = TextEditingController(text: '0.05');
  final _eDropCtrl = TextEditingController(text: '0.03');
  final _eLoopCtrl = TextEditingController(text: '450');
  final _eMaxRungsCtrl = TextEditingController(text: '3');
  final _eTagCtrl = TextEditingController(text: 'elphaba');

  @override
  void initState() {
    super.initState();
    _animCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 500))..repeat(reverse: true);
    
    // Apply initial preset if available
    if (widget.initialPresetDorothy != null) {
      _dQtyCtrl.text = widget.initialPresetDorothy!['quote_order_qty']?.toString() ?? '6';
      _dProfitCtrl.text = widget.initialPresetDorothy!['profit_factor']?.toString() ?? '0.05';
      _dDropCtrl.text = widget.initialPresetDorothy!['margin_drop_factor']?.toString() ?? '0.03';
      _dLoopCtrl.text = widget.initialPresetDorothy!['loop_interval_sec']?.toString() ?? '450';
      _dMaxRungsCtrl.text = widget.initialPresetDorothy!['max_rungs_per_symbol']?.toString() ?? '3';
      _dTagCtrl.text = widget.initialPresetDorothy!['tag']?.toString() ?? 'dorothy';
    }

    if (widget.initialPresetElphaba != null) {
      _eQtyCtrl.text = widget.initialPresetElphaba!['quote_order_qty']?.toString() ?? '6';
      _eProfitCtrl.text = widget.initialPresetElphaba!['profit_factor']?.toString() ?? '0.05';
      _eDropCtrl.text = widget.initialPresetElphaba!['margin_drop_factor']?.toString() ?? '0.03';
      _eLoopCtrl.text = widget.initialPresetElphaba!['loop_interval_sec']?.toString() ?? '450';
      _eMaxRungsCtrl.text = widget.initialPresetElphaba!['max_rungs_per_symbol']?.toString() ?? '3';
      _eTagCtrl.text = widget.initialPresetElphaba!['tag']?.toString() ?? 'elphaba';
    }

    // Pulse immediately on start
    SystemSound.play(SystemSoundType.alert);
    // Beep every 60 seconds
    _beepTimer = Timer.periodic(const Duration(seconds: 60), (_) {
      SystemSound.play(SystemSoundType.alert);
    });
  }

  @override
  void dispose() {
    _animCtrl.dispose();
    _beepTimer?.cancel();
    _dQtyCtrl.dispose();
    _dProfitCtrl.dispose();
    _dDropCtrl.dispose();
    _dLoopCtrl.dispose();
    _dMaxRungsCtrl.dispose();
    _dTagCtrl.dispose();
    _eQtyCtrl.dispose();
    _eProfitCtrl.dispose();
    _eDropCtrl.dispose();
    _eLoopCtrl.dispose();
    _eMaxRungsCtrl.dispose();
    _eTagCtrl.dispose();
    super.dispose();
  }

  void _accept() {
    // Validate Dorothy
    final dQty = double.tryParse(_dQtyCtrl.text) ?? 0;
    final dProfit = double.tryParse(_dProfitCtrl.text) ?? 0;
    final dDrop = double.tryParse(_dDropCtrl.text) ?? 0;
    final dLoop = int.tryParse(_dLoopCtrl.text) ?? 0;
    final dRungs = int.tryParse(_dMaxRungsCtrl.text) ?? 0;

    // Validate Elphaba
    final eQty = double.tryParse(_eQtyCtrl.text) ?? 0;
    final eProfit = double.tryParse(_eProfitCtrl.text) ?? 0;
    final eDrop = double.tryParse(_eDropCtrl.text) ?? 0;
    final eLoop = int.tryParse(_eLoopCtrl.text) ?? 0;
    final eRungs = int.tryParse(_eMaxRungsCtrl.text) ?? 0;

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
      'trading_enabled': true,
      'simulated': false,
    };

    final eConfig = {
      'symbol': widget.symbol,
      'quote_order_qty': eQty.toString(),
      'profit_factor': eProfit.toString(),
      'margin_drop_factor': eDrop.toString(),
      'loop_interval_sec': eLoop.toString(),
      'max_rungs_per_symbol': eRungs.toString(),
      'tag': _eTagCtrl.text.trim(),
      'trading_enabled': true,
      'simulated': false,
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
          Row(
            children: [
              const Icon(Icons.warning_amber_rounded, color: Colors.yellowAccent, size: 24),
              const SizedBox(width: 8),
              const Text(
                'SÍMBOLO EN STAGING (L0 REQUIERE VALIDACIÓN)',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: Colors.yellowAccent, letterSpacing: 1),
              ),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.close, color: Colors.white54),
                onPressed: widget.onCancel,
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              const Text('Symbol: ', style: TextStyle(fontSize: 12, color: Colors.white70)),
              Text(widget.symbol, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white, fontFamily: 'monospace')),
            ],
          ),
          const SizedBox(height: 12),
          // Stacked forms
          _buildHubForm('Dorothy (Long)', Colors.tealAccent, _dQtyCtrl, _dProfitCtrl, _dDropCtrl, _dLoopCtrl, _dMaxRungsCtrl, _dTagCtrl),
          const SizedBox(height: 12),
          _buildHubForm('Elphaba (Short)', Colors.purpleAccent, _eQtyCtrl, _eProfitCtrl, _eDropCtrl, _eLoopCtrl, _eMaxRungsCtrl, _eTagCtrl),
          
          const SizedBox(height: 16),
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
                label: const Text('ACEPTAR Y DESPLEGAR SIMÉTRICO', style: TextStyle(fontWeight: FontWeight.bold)),
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

  Widget _buildHubForm(String title, Color accentColor, TextEditingController qty, TextEditingController profit, TextEditingController drop, TextEditingController loop, TextEditingController rungs, TextEditingController tag) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: Colors.black26,
        border: Border.all(color: accentColor.withAlpha(100)),
        borderRadius: BorderRadius.circular(6)
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: TextStyle(color: accentColor, fontWeight: FontWeight.bold, fontSize: 13)),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              _buildField('Qty USDT', qty),
              _buildField('Profit %', profit),
              _buildField('Drop %', drop),
              _buildField('Loop (s)', loop),
              _buildField('Max Rungs', rungs),
              _buildField('Tag', tag, width: 120),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildField(String label, TextEditingController ctrl, {double width = 80}) {
    return SizedBox(
      width: width,
      child: TextField(
        controller: ctrl,
        style: const TextStyle(fontSize: 12, fontFamily: 'monospace', color: Colors.white, fontWeight: FontWeight.bold),
        decoration: InputDecoration(
          labelText: label,
          labelStyle: const TextStyle(color: Colors.white54, fontSize: 10),
          filled: true,
          fillColor: Colors.black45,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(6), borderSide: BorderSide.none),
          contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
        ),
      ),
    );
  }
}
