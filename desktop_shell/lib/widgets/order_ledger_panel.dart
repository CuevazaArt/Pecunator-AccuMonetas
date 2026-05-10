import 'dart:async';
import 'package:flutter/material.dart';
import '../api_client.dart';
import '../services/telemetry_hub.dart';

/// Improved Order Ledger panel — list view with expandable order details.
/// Shows recent orders with side color coding, timestamps, and full
/// order metadata when expanded.
///
/// Data flow: WebSocket push (primary) → REST fallback (120s).
class OrderLedgerPanel extends StatefulWidget {
  final EngineApi api;
  const OrderLedgerPanel({super.key, required this.api});

  @override
  State<OrderLedgerPanel> createState() => _OrderLedgerPanelState();
}

class _OrderLedgerPanelState extends State<OrderLedgerPanel> {
  Timer? _timer;
  StreamSubscription<TelemetrySnapshot>? _hubSub;
  Map<String, dynamic> _stats = {};
  List<dynamic> _orders = [];
  String? _expandedOrderId;

  @override
  void initState() {
    super.initState();
    _poll(); // initial load via REST
    // WebSocket push — primary data source
    _hubSub = TelemetryHub.instance.stream.listen(_onTelemetryTick);
    // REST fallback — reduced to 120s (WS delivers every 10s)
    _timer = Timer.periodic(const Duration(seconds: 120), (_) => _poll());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _hubSub?.cancel();
    super.dispose();
  }

  void _onTelemetryTick(TelemetrySnapshot snap) {
    if (!mounted) return;
    final wsStats = snap.orderLedgerStats;
    final wsRecent = snap.orderLedgerRecent;
    if (wsStats == null && wsRecent.isEmpty) return; // no ledger data in this tick
    setState(() {
      if (wsStats != null) _stats = wsStats;
      if (wsRecent.isNotEmpty) _orders = wsRecent;
    });
  }

  Future<void> _poll() async {
    if (!mounted) return;
    try {
      final results = await Future.wait([
        widget.api.orderLedgerStats().catchError((_) => <String, dynamic>{}),
        widget.api.orderLedgerRecent(limit: 20).catchError((_) => <String, dynamic>{}),
      ]);
      if (!mounted) return;
      setState(() {
        _stats = results[0];
        _orders = (results[1]['items'] as List?) ?? [];
      });
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final total = _stats['total_orders'] ?? 0;
    final live = _stats['live_orders'] ?? 0;

    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFF0D1117).withValues(alpha: 0.5),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: Colors.white.withValues(alpha: 0.06)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          // Header
          Row(
            children: [
              Icon(Icons.receipt_long, size: 12,
                  color: Colors.purpleAccent.withValues(alpha: 0.7)),
              const SizedBox(width: 5),
              Text(
                'ORDER LEDGER',
                style: TextStyle(
                  fontSize: 9,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.8,
                  color: Colors.purpleAccent.withValues(alpha: 0.7),
                ),
              ),
              const Spacer(),
              // Stats chips
              _statChip('Activas', '$live',
                  live > 0 ? Colors.orangeAccent : Colors.white30),
              const SizedBox(width: 6),
              _statChip('Total', '$total', Colors.white38),
            ],
          ),
          const SizedBox(height: 8),

          // Orders list
          if (_orders.isEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Center(
                child: Text(
                  'Sin órdenes registradas',
                  style: TextStyle(
                    fontSize: 9,
                    color: Colors.white.withValues(alpha: 0.2),
                    fontStyle: FontStyle.italic,
                  ),
                ),
              ),
            )
          else
            ..._orders.take(12).map((o) => _buildOrderTile(o as Map)),
        ],
      ),
    );
  }

  Widget _statChip(String label, String value, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(3),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(label, style: TextStyle(fontSize: 7, color: color.withValues(alpha: 0.6))),
          const SizedBox(width: 3),
          Text(value, style: TextStyle(fontSize: 8, fontWeight: FontWeight.w800, color: color, fontFamily: 'monospace')),
        ],
      ),
    );
  }

  Widget _buildOrderTile(Map order) {
    final id = '${order['order_id'] ?? order['id'] ?? ''}';
    final side = '${order['side'] ?? ''}'.toUpperCase();
    final symbol = '${order['symbol'] ?? ''}';
    final botType = '${order['bot_type'] ?? ''}';
    final reason = '${order['reason'] ?? ''}';
    final price = '${order['price'] ?? ''}';
    final qty = '${order['qty'] ?? order['quantity'] ?? ''}';
    final status = '${order['status'] ?? ''}';
    final timestamp = '${order['timestamp'] ?? order['created_at'] ?? ''}';
    final isBuy = side == 'BUY';
    final sideColor = isBuy ? const Color(0xFF00E676) : Colors.redAccent;
    final isExpanded = _expandedOrderId == id;

    return GestureDetector(
      onTap: () {
        setState(() {
          _expandedOrderId = isExpanded ? null : id;
        });
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        margin: const EdgeInsets.only(bottom: 3),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
        decoration: BoxDecoration(
          color: isExpanded
              ? sideColor.withValues(alpha: 0.06)
              : Colors.white.withValues(alpha: 0.02),
          borderRadius: BorderRadius.circular(5),
          border: Border.all(
            color: isExpanded
                ? sideColor.withValues(alpha: 0.2)
                : Colors.white.withValues(alpha: 0.03),
          ),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Main row
            Row(
              children: [
                // Side badge
                Container(
                  width: 28,
                  padding: const EdgeInsets.symmetric(vertical: 1),
                  decoration: BoxDecoration(
                    color: sideColor.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(2),
                  ),
                  child: Center(
                    child: Text(
                      side,
                      style: TextStyle(
                        fontSize: 7,
                        fontWeight: FontWeight.w900,
                        color: sideColor,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 6),
                // Symbol
                Text(
                  symbol,
                  style: const TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    fontFamily: 'monospace',
                    color: Colors.white,
                  ),
                ),
                const SizedBox(width: 6),
                // Bot type chip
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(2),
                  ),
                  child: Text(
                    botType,
                    style: TextStyle(
                      fontSize: 7,
                      fontFamily: 'monospace',
                      color: Colors.white.withValues(alpha: 0.4),
                    ),
                  ),
                ),
                const Spacer(),
                // Reason
                Flexible(
                  child: Text(
                    reason,
                    style: TextStyle(
                      fontSize: 8,
                      color: Colors.white.withValues(alpha: 0.35),
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                const SizedBox(width: 4),
                // Expand indicator
                Icon(
                  isExpanded ? Icons.expand_less : Icons.expand_more,
                  size: 12,
                  color: Colors.white24,
                ),
              ],
            ),
            // Expanded details
            if (isExpanded) ...[
              const SizedBox(height: 6),
              Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(4),
                ),
                child: Column(
                  children: [
                    _detailRow('Price', price),
                    _detailRow('Quantity', qty),
                    _detailRow('Status', status),
                    _detailRow('Timestamp', _formatTime(timestamp)),
                    _detailRow('Order ID', id.length > 20 ? '${id.substring(0, 20)}...' : id),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _detailRow(String label, String value) {
    if (value.isEmpty || value == 'null') return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 1),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 65,
            child: Text(
              label,
              style: TextStyle(
                fontSize: 8,
                color: Colors.white.withValues(alpha: 0.35),
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: const TextStyle(
                fontSize: 8,
                fontFamily: 'monospace',
                color: Colors.white70,
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _formatTime(String raw) {
    try {
      final dt = DateTime.parse(raw);
      final local = dt.toLocal();
      return '${local.month.toString().padLeft(2, '0')}-${local.day.toString().padLeft(2, '0')} '
          '${local.hour.toString().padLeft(2, '0')}:${local.minute.toString().padLeft(2, '0')}:${local.second.toString().padLeft(2, '0')}';
    } catch (_) {
      return raw;
    }
  }
}
