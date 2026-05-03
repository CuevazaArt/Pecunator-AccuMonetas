import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'dart:convert';

class EarnManagerPage extends StatefulWidget {
  const EarnManagerPage({super.key});

  @override
  State<EarnManagerPage> createState() => _EarnManagerPageState();
}

class _EarnManagerPageState extends State<EarnManagerPage> {
  bool _isSyncing = false;
  String _syncStatus = 'Esperando sincronización...';

  Future<void> _forceSync() async {
    setState(() {
      _isSyncing = true;
      _syncStatus = 'Sincronizando con Binance Earn...';
    });
    
    try {
      final res = await http.post(Uri.parse('http://127.0.0.1:8000/api/v1/earn/sync'));
      if (res.statusCode == 200) {
        final data = jsonDecode(res.body);
        setState(() {
          _syncStatus = 'Sincronización exitosa. Registros insertados: ${data['inserted']}';
        });
      } else {
        setState(() {
          _syncStatus = 'Error HTTP: ${res.statusCode}';
        });
      }
    } catch (e) {
      setState(() {
        _syncStatus = 'Error: $e';
      });
    } finally {
      setState(() {
        _isSyncing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rendimiento Pasivo (Earn Manager)'),
        actions: [
          IconButton(
            icon: const Icon(Icons.menu_book),
            tooltip: 'Manual del Operador',
            onPressed: () {
              showDialog(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Manual: Motor de Rebalanceo Earn', style: TextStyle(color: Colors.orangeAccent)),
                  content: const SingleChildScrollView(
                    child: Text(
                      'Objetivo Estratégico:\n'
                      'Mantener la liquidez ociosa trabajando en productos de Binance Simple Earn '
                      'para generar rendimiento pasivo garantizado.\n\n'
                      'Táctica:\n'
                      '1. El sistema escanea la API de Earn 3 veces al día buscando los mejores APR.\n'
                      '2. Identifica saldo Spot libre que no esté siendo utilizado por bots activos.\n'
                      '3. Traspasa el capital al producto (Flexible) de mayor rendimiento.\n'
                      '4. Si un bot Masha/Dorothy requiere liquidez inmediata, el motor hace un "Redeem" automático en milisegundos.',
                    ),
                  ),
                  actions: [
                    TextButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('Entendido')),
                  ],
                ),
              );
            },
          ),
          IconButton(
            icon: const Icon(Icons.sync),
            tooltip: 'Forzar Sincronización',
            onPressed: _isSyncing ? null : _forceSync,
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Motor de Rebalanceo de Rendimiento',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.orangeAccent),
            ),
            const SizedBox(height: 8),
            const Text(
              'El algoritmo de Pecunator evalúa constantemente el saldo en Spot y lo mueve hacia los productos '
              'de Simple Earn con mayor rendimiento, asegurando liquidez inmediata cuando Masha o Dorothy lo requieren.',
              style: TextStyle(color: Colors.grey),
            ),
            const SizedBox(height: 24),
            Row(
              children: [
                Expanded(
                  child: Card(
                    color: Colors.black45,
                    child: Padding(
                      padding: const EdgeInsets.all(16.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Text('Estado del Motor', style: TextStyle(fontWeight: FontWeight.bold)),
                          const SizedBox(height: 8),
                          Row(
                            children: [
                              Icon(
                                _isSyncing ? Icons.sync_problem : Icons.check_circle,
                                color: _isSyncing ? Colors.orange : Colors.greenAccent,
                              ),
                              const SizedBox(width: 8),
                              Expanded(child: Text(_syncStatus)),
                            ],
                          )
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),
            const Expanded(
              child: Center(
                child: Text(
                  'Panel de Estadísticas y Gráficas de Oportunidades en construcción...',
                  style: TextStyle(color: Colors.white54, fontStyle: FontStyle.italic),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
