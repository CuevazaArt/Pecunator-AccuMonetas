import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_spinkit/flutter_spinkit.dart';
import '../api_client.dart';

class VmoDashboard extends StatefulWidget {
  final EngineApi api;

  const VmoDashboard({super.key, required this.api});

  @override
  State<VmoDashboard> createState() => _VmoDashboardState();
}

class _VmoDashboardState extends State<VmoDashboard> with SingleTickerProviderStateMixin {
  bool _isLoading = false;
  Map<String, dynamic> _status = {};
  Map<String, Map<String, dynamic>> _regimes = {};
  String _error = '';
  Timer? _timer;

  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    _fetchData();
    _timer = Timer.periodic(const Duration(seconds: 60), (_) => _fetchData());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _pulseController.dispose();
    super.dispose();
  }

  Future<void> _fetchData() async {
    if (_isLoading) return;
    setState(() => _isLoading = true);
    try {
      final statusResp = await widget.api.visionStatus();
      final regimesResp = await widget.api.visionRegimesLatest();
      
      if (mounted) {
        setState(() {
          _status = statusResp;
          _regimes = regimesResp.map((k, v) => MapEntry(k, Map<String, dynamic>.from(v as Map)));
          _error = '';
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = e.toString();
          _isLoading = false;
        });
      }
    }
  }

  Color _getRegimeColor(String regime) {
    switch (regime.toUpperCase()) {
      case 'TRENDING':
        return Colors.greenAccent;
      case 'RANGING':
      case 'LATERAL':
        return Colors.blueAccent;
      case 'CHOPPY':
        return Colors.orangeAccent;
      case 'BREAKOUT':
        return Colors.purpleAccent;
      default:
        return Colors.grey;
    }
  }

  Color _getBotColor(String bot) {
    switch (bot.toLowerCase()) {
      case 'dorothy':
        return Colors.greenAccent;
      case 'elphaba':
        return Colors.blueAccent;
      case 'thusnelda':
        return Colors.purpleAccent;
      case 'none':
      default:
        return Colors.grey;
    }
  }

  Widget _buildRegimeCard(String symbol, Map<String, dynamic> timeframes) {
    // Pick the most relevant timeframe to display prominently, e.g., 4h or 1d
    String primaryTf = timeframes.keys.contains('4h') ? '4h' : timeframes.keys.first;
    final primaryData = timeframes[primaryTf];
    final regime = primaryData['regime']?.toString() ?? 'UNKNOWN';
    final bot = primaryData['recommended_bot']?.toString() ?? 'none';
    final conf = (primaryData['confidence'] as num?)?.toDouble() ?? 0.0;
    
    final regimeColor = _getRegimeColor(regime);
    final botColor = _getBotColor(bot);

    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.03),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: regimeColor.withValues(alpha: 0.3), width: 1.5),
        boxShadow: [
          BoxShadow(
            color: regimeColor.withValues(alpha: 0.05),
            blurRadius: 10,
            spreadRadius: 2,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                symbol,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.1,
                  color: Colors.white,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: regimeColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: regimeColor.withValues(alpha: 0.5)),
                ),
                child: Text(
                  regime.toUpperCase(),
                  style: TextStyle(
                    color: regimeColor,
                    fontWeight: FontWeight.bold,
                    fontSize: 12,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('RECOMENDACIÓN', style: TextStyle(color: Colors.white54, fontSize: 10)),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Icon(Icons.smart_toy, color: botColor, size: 16),
                      const SizedBox(width: 4),
                      Text(
                        bot.toUpperCase(),
                        style: TextStyle(color: botColor, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                ],
              ),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  const Text('CONFIANZA', style: TextStyle(color: Colors.white54, fontSize: 10)),
                  const SizedBox(height: 4),
                  Text(
                    '${(conf * 100).toStringAsFixed(0)}%',
                    style: TextStyle(
                      color: conf > 0.7 ? Colors.greenAccent : (conf > 0.4 ? Colors.orangeAccent : Colors.redAccent),
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                ],
              ),
            ],
          ),
          if (timeframes.length > 1) ...[
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8.0),
              child: Divider(color: Colors.white10),
            ),
            Row(
              children: timeframes.entries.map((e) {
                final tf = e.key;
                final r = e.value['regime']?.toString() ?? 'UNKNOWN';
                return Padding(
                  padding: const EdgeInsets.only(right: 8.0),
                  child: Text(
                    '$tf: $r',
                    style: const TextStyle(color: Colors.white54, fontSize: 11),
                  ),
                );
              }).toList(),
            ),
          ]
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final bool isEnabled = _status['config']?['enabled'] == true;
    final String model = _status['config']?['llm_model'] ?? 'N/A';
    
    return Container(
      width: 340,
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            const Color(0xFF1A1C23),
            const Color(0xFF121318),
          ],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: Colors.white12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.5),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Header
          Container(
            padding: const EdgeInsets.all(20),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: Colors.white10)),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'VMO SENSOR',
                      style: TextStyle(
                        color: Colors.white,
                        fontSize: 16,
                        fontWeight: FontWeight.w900,
                        letterSpacing: 1.5,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      model,
                      style: const TextStyle(color: Colors.white54, fontSize: 11),
                    ),
                  ],
                ),
                Row(
                  children: [
                    if (_isLoading)
                      const SizedBox(
                        width: 14,
                        height: 14,
                        child: SpinKitDualRing(color: Colors.blueAccent, size: 14.0, lineWidth: 2.0),
                      )
                    else
                      IconButton(
                        icon: const Icon(Icons.refresh, size: 18, color: Colors.white54),
                        onPressed: _fetchData,
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(),
                        tooltip: 'Actualizar VMO',
                      ),
                    const SizedBox(width: 12),
                    AnimatedBuilder(
                      animation: _pulseController,
                      builder: (context, child) {
                        return Container(
                          width: 12,
                          height: 12,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: isEnabled 
                                ? Colors.greenAccent.withValues(alpha: 0.5 + (_pulseController.value * 0.5))
                                : Colors.redAccent,
                            boxShadow: isEnabled ? [
                              BoxShadow(
                                color: Colors.greenAccent.withValues(alpha: _pulseController.value * 0.5),
                                blurRadius: 8,
                                spreadRadius: 2,
                              )
                            ] : [],
                          ),
                        );
                      },
                    ),
                  ],
                ),
              ],
            ),
          ),
          
          // Content
          Expanded(
            child: _error.isNotEmpty
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(20),
                      child: Text('Error: $_error', style: const TextStyle(color: Colors.redAccent)),
                    ),
                  )
                : _regimes.isEmpty && !_isLoading
                    ? const Center(
                        child: Text('No hay datos del VMO', style: TextStyle(color: Colors.white54)),
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.all(20),
                        itemCount: _regimes.length,
                        itemBuilder: (context, index) {
                          final symbol = _regimes.keys.elementAt(index);
                          final tfs = _regimes[symbol]!;
                          return _buildRegimeCard(symbol, tfs);
                        },
                      ),
          ),
        ],
      ),
    );
  }
}
