import 'package:flutter/material.dart';
class BotGuidePage extends StatelessWidget {
  const BotGuidePage({super.key, required this.botName});

  final String botName;

  static const Map<String, String> _titles = {
    'Dorothy': 'Manual operativo Dorothy7.0',
    'Masha': 'Manual operativo Masha2.0',
    'Thusnelda': 'Manual operativo Thusnelda1.0',
  };

  static const Map<String, String> _intro = {
    'Dorothy':
        'Bot de ciclo perpetuo para un simbolo. Toma referencia de orden SELL ancla '
            'y compra cuando el mercado cae bajo el umbral configurado.',
    'Masha':
        'Bot DCA multi-timeframe. Evalua señal tecnica para comprar, recalcula precio '
            'promedio y consolida salida con una SELL LIMIT.',
    'Thusnelda':
        'Bot multi-simbolo por cesta. Recorre simbolos, compra por regla de promedio '
            'historico y vigila meta de equity global.',
  };

  static const Map<String, List<String>> _sections = {
    'Dorothy': [
      'Flujo principal: evalúa open orders + ticker y decide compra/espera/gestión de salida.',
      'Activación: botón ACTIVO/INACTIVO gobierna ciclo perpetuo por instancia.',
      'Guardar y aplicar: aplica cambios al instante y reinicia si estaba activo.',
      'Objetivo: recomponer posición y retornar quote/base con beneficio por spread.',
      'Control de riesgo: maxDd bloquea nuevas compras; stopLoss permite salida defensiva.',
      'Observabilidad: usar logs crudos Binance para validar filtros, cantidades y decisiones.',
    ],
    'Masha': [
      'Flujo principal: estrategia DCA con señal técnica multi-timeframe (W + H).',
      'Compra: requiere condiciones de señal y disponibilidad mínima de quote.',
      'Salida: mantiene una SELL LIMIT consolidada recalculada con cada compra.',
      'Riesgo: maxDd limita nuevas entradas; stopLoss corta deterioro extremo.',
      'Métricas: sharpe, win rate y drawdown persistidos cada metricsEvery ciclos.',
      'Observabilidad: comparar señal, precio DCA, orden de salida y logs Binance.',
    ],
    'Thusnelda': [
      'Flujo principal: recorre una cesta de símbolos en cada ciclo.',
      'Compra: compara precio actual con referencia/promedio histórico por símbolo.',
      'Salida: vigila meta de equity global y estado de cada activo de la cesta.',
      'Riesgo: maxDd bloquea entradas adicionales; stopLoss protege símbolo a símbolo.',
      'Operación: ajustar entre_symbol_sec para balancear latencia vs carga REST.',
      'Observabilidad: revisar eventos de equity, decisiones por símbolo y métricas.',
    ],
  };

  static const Map<String, List<String>> _parameterGuide = {
    'Dorothy': [
      'symbol: par spot a operar; debe existir y tener liquidez.',
      'loop sec: define frecuencia de reacción y consumo API.',
      'qty/profit/drop: núcleo de rentabilidad y ritmo de entradas.',
      'qDec/pDec: auto-resueltos desde Binance exchangeInfo al crear/guardar.',
      'maxDd/stopLoss: contención de pérdidas acumuladas y por posición.',
      'metricsEvery: costo/beneficio entre detalle histórico y carga.',
    ],
    'Masha': [
      'base/quote/symbol: coherencia obligatoria para evitar errores de mercado.',
      'min quote + buy qty: controlan cuándo y cuánto compra.',
      'TF/periods/mm/margins: sensibilidad de señal técnica.',
      'profit: objetivo de salida de la orden consolidada.',
      'maxDd/stopLoss: protección macro y micro del ciclo DCA.',
      'qDec/pDec: auto-resueltos desde Binance exchangeInfo al crear/guardar.',
    ],
    'Thusnelda': [
      'symbols CSV: universo de activos a escanear por ciclo.',
      'loop + entre sym: velocidad total de barrido y carga REST.',
      'quote qty + factor: tamaño y agresividad de cada entrada.',
      'meta equity: umbral objetivo de rendimiento agregado.',
      'maxDd/stopLoss: freno global y defensa por símbolo.',
      'refTs/qDec: soporte de referencia histórica; qDec auto-resuelto desde exchangeInfo.',
    ],
  };

  static const Map<String, List<String>> _troubleshooting = {
    'Dorothy': [
      'No compra: validar drop/profit, saldo quote y estado de órdenes ancla.',
      'Errores de filtro: qDec/pDec ahora son auto-resueltos; verificar que gateway esté activo.',
      'Mucho peso REST: subir loop o revisar monitor de peso por acciones.',
    ],
    'Masha': [
      'No dispara señal: revisar timeframe, periods y márgenes W/H.',
      'No coloca salida: verificar profit, gateway activo (decimales auto-resueltos).',
      'DCA agresivo: ajustar buy qty y maxDd para menor exposición.',
    ],
    'Thusnelda': [
      'Cesta lenta: reducir símbolos o aumentar entre_symbol_sec.',
      'Sin entradas: revisar factor, referencia y liquidez real de símbolos.',
      'Riesgo alto: endurecer maxDd/stopLoss y validar meta de equity.',
    ],
  };

  static const List<String> _quickStart = [
    '1) Crear instancia desde su Hub.',
    '2) Confirmar simbolo(s), base asset y quote qty.',
    '3) Presionar Activar para iniciar ciclo perpetuo.',
    '4) Observar logs crudos y ajustes de riesgo.',
    '5) Guardar y aplicar cuando cambies parametros.',
  ];

  @override
  Widget build(BuildContext context) {
    final title = _titles[botName] ?? 'Guia de bot';
    final intro = _intro[botName] ?? '-';
    final bullets = _sections[botName] ?? const <String>[];
    final params = _parameterGuide[botName] ?? const <String>[];
    final troubleshoot = _troubleshooting[botName] ?? const <String>[];
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Text(intro),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Guía de parámetros',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    ...params.map(
                      (text) => Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text('- $text'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Como operarlo',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    ...bullets.map(
                      (text) => Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text('- $text'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Inicio rapido',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    ..._quickStart.map(
                      (step) => Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text(step),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 10),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Troubleshooting rápido',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    ...troubleshoot.map(
                      (text) => Padding(
                        padding: const EdgeInsets.only(bottom: 6),
                        child: Text('- $text'),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

