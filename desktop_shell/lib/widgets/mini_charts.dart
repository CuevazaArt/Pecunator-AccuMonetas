/// Barrel export for all mini chart widgets.
///
/// Previously this was a 978-line monolith. Now decomposed into:
///   - chart_primitives.dart (ChartSample, SparklinePainter)
///   - mini_weight_chart.dart (MiniWeightChart)
///   - mini_order_rate_chart.dart (MiniOrderRateChart)
///   - mini_equity_chart.dart (MiniEquityChart)
///   - status_lights.dart (StatusLights, WeightOscillator)
library;

export 'chart_primitives.dart';
export 'mini_weight_chart.dart';
export 'mini_order_rate_chart.dart';
export 'mini_equity_chart.dart';
export 'status_lights.dart';
