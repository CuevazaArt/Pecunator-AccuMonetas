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
        'Bot DCA multi-timeframe. Evalua seÃ±al tecnica para comprar, recalcula precio '
            'promedio y consolida salida con una SELL LIMIT.',
    'Thusnelda':
        'Bot multi-simbolo por cesta. Recorre simbolos, compra por regla de promedio '
            'historico y vigila meta de equity global.',
  };

  static const Map<String, List<String>> _sections = {
    'Dorothy': [
      'Flujo principal: evalÃºa open orders + ticker y decide compra/espera/gestiÃ³n de salida.',
      'ActivaciÃ³n: botÃ³n ACTIVO/INACTIVO gobierna ciclo perpetuo por instancia.',
      'Guardar y aplicar: aplica cambios al instante y reinicia si estaba activo.',
      'Objetivo: recomponer posiciÃ³n y retornar quote/base con beneficio por spread.',
      'Control de riesgo: maxDd bloquea nuevas compras; stopLoss permite salida defensiva.',
      'Observabilidad: usar logs crudos Binance para validar filtros, cantidades y decisiones.',
    ],
    'Masha': [
      'Flujo principal: estrategia DCA con seÃ±al tÃ©cnica multi-timeframe (W + H).',
      'Compra: requiere condiciones de seÃ±al y disponibilidad mÃ­nima de quote.',
      'Salida: mantiene una SELL LIMIT consolidada recalculada con cada compra.',
      'Riesgo: maxDd limita nuevas entradas; stopLoss corta deterioro extremo.',
      'MÃ©tricas: sharpe, win rate y drawdown persistidos cada metricsEvery ciclos.',
      'Observabilidad: comparar seÃ±al, precio DCA, orden de salida y logs Binance.',
    ],
    'Thusnelda': [
      'Flujo principal: recorre una cesta de sÃ­mbolos en cada ciclo.',
      'Compra: compara precio actual con referencia/promedio histÃ³rico por sÃ­mbolo.',
      'Salida: vigila meta de equity global y estado de cada activo de la cesta.',
      'Riesgo: maxDd bloquea entradas adicionales; stopLoss protege sÃ­mbolo a sÃ­mbolo.',
      'OperaciÃ³n: ajustar entre_symbol_sec para balancear latencia vs carga REST.',
      'Observabilidad: revisar eventos de equity, decisiones por sÃ­mbolo y mÃ©tricas.',
    ],
  };

  static const Map<String, List<String>> _parameterGuide = {
    'Dorothy': [
      'symbol: par spot a operar; debe existir y tener liquidez.',
      'loop sec: define frecuencia de reacciÃ³n y consumo API.',
      'qty/profit/drop: nÃºcleo de rentabilidad y ritmo de entradas.',
      'qDec/pDec: imprescindibles para cumplir filtros Binance.',
      'maxDd/stopLoss: contenciÃ³n de pÃ©rdidas acumuladas y por posiciÃ³n.',
      'metricsEvery: costo/beneficio entre detalle histÃ³rico y carga.',
    ],
    'Masha': [
      'base/quote/symbol: coherencia obligatoria para evitar errores de mercado.',
      'min quote + buy qty: controlan cuÃ¡ndo y cuÃ¡nto compra.',
      'TF/periods/mm/margins: sensibilidad de seÃ±al tÃ©cnica.',
      'profit: objetivo de salida de la orden consolidada.',
      'maxDd/stopLoss: protecciÃ³n macro y micro del ciclo DCA.',
      'qDec/pDec: adaptar al instrumento para evitar rechazos.',
    ],
    'Thusnelda': [
      'symbols CSV: universo de activos a escanear por ciclo.',
      'loop + entre sym: velocidad total de barrido y carga REST.',
      'quote qty + factor: tamaÃ±o y agresividad de cada entrada.',
      'meta equity: umbral objetivo de rendimiento agregado.',
      'maxDd/stopLoss: freno global y defensa por sÃ­mbolo.',
      'refTs/qDec: soporte de referencia histÃ³rica y cumplimiento de filtros.',
    ],
  };

  static const Map<String, List<String>> _troubleshooting = {
    'Dorothy': [
      'No compra: validar drop/profit, saldo quote y estado de Ã³rdenes ancla.',
      'Errores de filtro: ajustar qDec/pDec al tick size y lot size.',
      'Mucho peso REST: subir loop o revisar monitor de peso por acciones.',
    ],
    'Masha': [
      'No dispara seÃ±al: revisar timeframe, periods y mÃ¡rgenes W/H.',
      'No coloca salida: validar pDec/profit y restricciones del sÃ­mbolo.',
      'DCA agresivo: ajustar buy qty y maxDd para menor exposiciÃ³n.',
    ],
    'Thusnelda': [
      'Cesta lenta: reducir sÃ­mbolos o aumentar entre_symbol_sec.',
      'Sin entradas: revisar factor, referencia y liquidez real de sÃ­mbolos.',
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
                      'GuÃ­a de parÃ¡metros',
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
                      'Troubleshooting rÃ¡pido',
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

