class BotMetrics {
  final String id;
  final String name;
  final String symbol;
  final String status; // running, paused, shutdown
  final double currentPrice;
  final double positionSize;
  final double costBasis;
  final double unrealizedPnl;
  final double unrealizedPct;
  final double freeBalance;
  final double targetProfitPct;
  final double progressPercent;
  final double dailyBudget;
  final int tradesToday;

  BotMetrics({
    required this.id,
    required this.name,
    required this.symbol,
    required this.status,
    required this.currentPrice,
    required this.positionSize,
    required this.costBasis,
    required this.unrealizedPnl,
    required this.unrealizedPct,
    required this.freeBalance,
    required this.targetProfitPct,
    required this.progressPercent,
    required this.dailyBudget,
    required this.tradesToday,
  });

  factory BotMetrics.fromJson(Map<String, dynamic> json) => BotMetrics(
    id: json['id'] as String? ?? '',
    name: json['name'] as String? ?? '',
    symbol: json['symbol'] as String? ?? '',
    status: json['status'] as String? ?? 'unknown',
    currentPrice: (json['current_price'] as num?)?.toDouble() ?? 0.0,
    positionSize: (json['position_size'] as num?)?.toDouble() ?? 0.0,
    costBasis: (json['cost_basis'] as num?)?.toDouble() ?? 0.0,
    unrealizedPnl: (json['unrealized_pnl'] as num?)?.toDouble() ?? 0.0,
    unrealizedPct: (json['unrealized_pct'] as num?)?.toDouble() ?? 0.0,
    freeBalance: (json['free_balance'] as num?)?.toDouble() ?? 0.0,
    targetProfitPct: (json['target_profit_pct'] as num?)?.toDouble() ?? 0.0,
    progressPercent: (json['progress_percent'] as num?)?.toDouble() ?? 0.0,
    dailyBudget: (json['daily_budget'] as num?)?.toDouble() ?? 0.0,
    tradesToday: (json['trades_today'] as int?) ?? 0,
  );

  String get statusEmoji {
    switch (status.toLowerCase()) {
      case 'running':
        return '🟢';
      case 'paused':
        return '🟡';
      case 'shutdown':
        return '⚫';
      default:
        return '❓';
    }
  }

  String get pnlColor {
    if (unrealizedPct > 0) return '🟢'; // Green
    if (unrealizedPct < 0) return '🔴'; // Red
    return '⚪'; // Neutral
  }
}

class HubMetrics {
  final int activeBots;
  final double totalPortfolio;
  final double totalFreeBalance;
  final double totalUnrealizedPnl;
  final double hubPnlPercent;
  final int completedEpochs;

  HubMetrics({
    required this.activeBots,
    required this.totalPortfolio,
    required this.totalFreeBalance,
    required this.totalUnrealizedPnl,
    required this.hubPnlPercent,
    required this.completedEpochs,
  });

  factory HubMetrics.fromJson(Map<String, dynamic> json) => HubMetrics(
    activeBots: json['active_bots'] as int? ?? 0,
    totalPortfolio: (json['total_portfolio'] as num?)?.toDouble() ?? 0.0,
    totalFreeBalance: (json['total_free_balance'] as num?)?.toDouble() ?? 0.0,
    totalUnrealizedPnl: (json['total_unrealized_pnl'] as num?)?.toDouble() ?? 0.0,
    hubPnlPercent: (json['hub_pnl_percent'] as num?)?.toDouble() ?? 0.0,
    completedEpochs: json['completed_epochs'] as int? ?? 0,
  );
}

class WeightStatus {
  final DateTime timestamp;
  final int currentWeight;
  final int weightPerMinute;
  final int weightLimit;
  final String weightZone; // GREEN, YELLOW, RED
  final String statusMessage;

  WeightStatus({
    required this.timestamp,
    required this.currentWeight,
    required this.weightPerMinute,
    required this.weightLimit,
    required this.weightZone,
    required this.statusMessage,
  });

  factory WeightStatus.fromJson(Map<String, dynamic> json) => WeightStatus(
    timestamp: json['timestamp'] is String
        ? DateTime.parse(json['timestamp'] as String)
        : DateTime.now(),
    currentWeight: json['current_weight'] as int? ?? 0,
    weightPerMinute: json['weight_per_minute'] as int? ?? 0,
    weightLimit: json['weight_limit'] as int? ?? 0,
    weightZone: json['weight_zone'] as String? ?? 'UNKNOWN',
    statusMessage: json['status_message'] as String? ?? '',
  );

  double get weightPercentage => (currentWeight / weightLimit * 100).clamp(0, 100);

  String get zoneEmoji {
    switch (weightZone.toUpperCase()) {
      case 'GREEN':
        return '🟢';
      case 'YELLOW':
        return '🟡';
      case 'RED':
        return '🔴';
      default:
        return '⚪';
    }
  }
}

class WeightHistory {
  final String time;
  final int louiseBtc001;
  final int louiseEth001;
  final int louiseSol001;

  WeightHistory({
    required this.time,
    required this.louiseBtc001,
    required this.louiseEth001,
    required this.louiseSol001,
  });

  factory WeightHistory.fromJson(Map<String, dynamic> json) => WeightHistory(
    time: json['time'] as String? ?? '',
    louiseBtc001: json['louise_btc_001'] as int? ?? 0,
    louiseEth001: json['louise_eth_001'] as int? ?? 0,
    louiseSol001: json['louise_sol_001'] as int? ?? 0,
  );

  int get total => louiseBtc001 + louiseEth001 + louiseSol001;
}

class RequestsStats {
  final int louiseBtc001;
  final int louiseEth001;
  final int louiseSol001;
  final int total;

  RequestsStats({
    required this.louiseBtc001,
    required this.louiseEth001,
    required this.louiseSol001,
    required this.total,
  });

  factory RequestsStats.fromJson(Map<String, dynamic> json) => RequestsStats(
    louiseBtc001: json['louise_btc_001'] as int? ?? 0,
    louiseEth001: json['louise_eth_001'] as int? ?? 0,
    louiseSol001: json['louise_sol_001'] as int? ?? 0,
    total: json['total'] as int? ?? 0,
  );
}

class BandwidthStats {
  final int louiseBtc001;
  final int louiseEth001;
  final int louiseSol001;
  final int total;

  BandwidthStats({
    required this.louiseBtc001,
    required this.louiseEth001,
    required this.louiseSol001,
    required this.total,
  });

  factory BandwidthStats.fromJson(Map<String, dynamic> json) => BandwidthStats(
    louiseBtc001: json['louise_btc_001'] as int? ?? 0,
    louiseEth001: json['louise_eth_001'] as int? ?? 0,
    louiseSol001: json['louise_sol_001'] as int? ?? 0,
    total: json['total'] as int? ?? 0,
  );

  String get totalMb => (total / 1000000).toStringAsFixed(2);
}
