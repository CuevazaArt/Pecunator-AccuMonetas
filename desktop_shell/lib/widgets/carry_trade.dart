import 'package:flutter/material.dart';

class CarryTradePage extends StatelessWidget {
  const CarryTradePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Carry Trade (Arbitraje de Tasas)'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Sincronizar Tasas',
            onPressed: () {},
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Matriz de Oportunidades de Apalancamiento',
              style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: Colors.blueAccent),
            ),
            const SizedBox(height: 12),
            _buildDetailedManual(),
            const SizedBox(height: 24),
            Expanded(
              child: GridView.count(
                crossAxisCount: 2,
                crossAxisSpacing: 16,
                mainAxisSpacing: 16,
                childAspectRatio: 2,
                children: [
                  _buildMetricCard('Tasa Base USDT (Préstamo)', '3.45% APR', Colors.redAccent),
                  _buildMetricCard('Rendimiento Máximo (Flexible)', '12.10% APR', Colors.greenAccent),
                  _buildMetricCard('Spread de Arbitraje', '+8.65% NETO', Colors.blueAccent),
                  _buildMetricCard('Riesgo de Liquidación', 'Mínimo (Stable/Stable)', Colors.blueGrey),
                ],
              ),
            ),
            const Expanded(
              child: Center(
                child: Text(
                  'El motor de cálculos cruzados se está sincronizando...',
                  style: TextStyle(color: Colors.white54, fontStyle: FontStyle.italic),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetricCard(String title, String value, Color color) {
    return Card(
      color: Colors.black45,
      shape: RoundedRectangleBorder(
        side: BorderSide(color: color.withOpacity(0.3), width: 1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(title, style: const TextStyle(color: Colors.grey, fontSize: 14)),
            const SizedBox(height: 8),
            Text(value, style: TextStyle(color: color, fontSize: 22, fontWeight: FontWeight.bold)),
          ],
        ),
      ),
    );
  }

  Widget _buildDetailedManual() {
    return Card(
      color: Colors.blueGrey.withOpacity(0.1),
      shape: RoundedRectangleBorder(
        side: const BorderSide(color: Colors.blueAccent, width: 0.5),
        borderRadius: BorderRadius.circular(8),
      ),
      child: const ExpansionTile(
        leading: Icon(Icons.menu_book, color: Colors.blueAccent),
        title: Text(
          'Manual Detallado de Operación (Carry Trade)',
          style: TextStyle(fontWeight: FontWeight.bold, color: Colors.blueAccent),
        ),
        subtitle: Text('Instrucciones, Fórmulas y Gestión de Riesgos', style: TextStyle(fontSize: 12)),
        childrenPadding: EdgeInsets.all(16),
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('1. Mecánica del Arbitraje', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white70)),
                    SizedBox(height: 4),
                    Text(
                      'El "Carry Trade" ocurre cuando tomas prestado un activo a una tasa de interés baja (ej. USDT al 4% anual) '
                      'y lo inviertes en un vehículo que paga una tasa mayor (ej. Staking de FDUSD al 12%). '
                      'El algoritmo extrae esta rentabilidad pasiva asumiendo un riesgo direccional igual a cero, ya que '
                      'ambos activos son Stablecoins ancladas al Dólar 1:1.',
                      style: TextStyle(color: Colors.white60, fontSize: 13),
                    ),
                    SizedBox(height: 12),
                    Text('2. Fórmula de Spread', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white70)),
                    SizedBox(height: 4),
                    Text(
                      'Spread Neto = (Rendimiento Simple Earn APR) - (Tasa de Interés de Préstamo Anualizada)\n'
                      'Ejemplo: 12% (Earn) - 4% (Loan) = +8% Beneficio Libre de Riesgo.',
                      style: TextStyle(color: Colors.greenAccent, fontSize: 13),
                    ),
                  ],
                ),
              ),
              SizedBox(width: 24),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('3. Gestión de Riesgos (Liquidación)', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.redAccent)),
                    SizedBox(height: 4),
                    Text(
                      'A pesar de ser mercado neutral, Binance requiere un Colateral (Garantía) para emitir el préstamo. '
                      'El bot de Carry Trade debe asegurar que el índice LTV (Loan-To-Value) nunca exceda el nivel de Margin Call. '
                      'El cruce ideal para apalancamiento máximo es usar colaterales de baja volatilidad (Stablecoins contra Stablecoins) '
                      'lo que permite apalancarse hasta 10x con riesgo de liquidación casi nulo.',
                      style: TextStyle(color: Colors.white60, fontSize: 13),
                    ),
                    SizedBox(height: 12),
                    Text('4. Frecuencia de Actualización', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white70)),
                    SizedBox(height: 4),
                    Text(
                      'Las tasas de Margin y Crypto Loans de Binance fluctúan horariamente. El motor se sincroniza '
                      'cada hora y ejecuta "Repay" (Pagar préstamo) si el spread se vuelve negativo.',
                      style: TextStyle(color: Colors.white60, fontSize: 13),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
