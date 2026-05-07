/// Reusable logs viewer widget.
library;

import 'dart:convert';

import 'package:flutter/material.dart';

class LogsViewer extends StatefulWidget {
  final String logs;
  final int minHeight;
  final int maxHeight;
  final bool autoScroll;

  const LogsViewer({
    super.key,
    required this.logs,
    this.minHeight = 80,
    this.maxHeight = 240,
    this.autoScroll = true,
  });

  @override
  State<LogsViewer> createState() => _LogsViewerState();
}

class _LogsViewerState extends State<LogsViewer> {
  late final ScrollController _scrollController;

  @override
  void initState() {
    super.initState();
    _scrollController = ScrollController();
    WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
  }

  @override
  void didUpdateWidget(LogsViewer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.autoScroll && widget.logs != oldWidget.logs) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());
    }
  }

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      _scrollController.jumpTo(_scrollController.position.maxScrollExtent);
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        minHeight: widget.minHeight.toDouble(),
        maxHeight: widget.maxHeight.toDouble(),
      ),
      decoration: BoxDecoration(
        border: Border.all(color: Theme.of(context).dividerColor),
        borderRadius: BorderRadius.circular(8),
      ),
      child: SingleChildScrollView(
        controller: _scrollController,
        padding: const EdgeInsets.all(8),
        child: SelectableText(
          widget.logs.isEmpty ? '(sin logs)' : widget.logs,
          style: const TextStyle(fontFamily: 'monospace', fontSize: 12),
        ),
      ),
    );
  }
}

/// Format bot logs from API response.
String formatBotLogs(Map<String, dynamic> payload) {
  final rows = (payload['logs'] as List?) ?? const [];
  if (rows.isEmpty) return '(sin logs)';

  final out = <String>[];
  for (final row in rows) {
    final m = Map<String, dynamic>.from(row as Map);
    final ts = (m['ts_utc'] ?? '-').toString();
    final level = (m['level'] ?? '-').toString();
    final msg = (m['message'] ?? '').toString();
    final payloadText = _formatLogPayload(m['payload']);
    out.add('$ts [$level] $msg${payloadText.isEmpty ? '' : ' | $payloadText'}');
  }
  return out.join('\n');
}

String _formatLogPayload(dynamic payload) {
  if (payload == null) return '';
  if (payload is String) return payload;
  if (payload is! Map) return payload.toString();

  final p = Map<String, dynamic>.from(payload);
  final response = p['response'];
  if (response != null) {
    return jsonEncode(response);
  }

  final reportRaw = p['last_report'];
  if (reportRaw is Map) {
    final rep = Map<String, dynamic>.from(reportRaw);
    if (!rep.containsKey('decision')) {
      return '';
    }
    final decision = (rep['decision'] ?? '-').toString();
    final execution = (rep['execution'] ?? '-').toString();
    final symbol = (rep['symbol'] ?? p['symbol'] ?? '-').toString();
    final market = (rep['market_price'] ?? '-').toString();
    final plannedBuy = (rep['planned_buy_price'] ?? '-').toString();
    final plannedSell = (rep['planned_sell_price'] ?? '-').toString();
    return 'decision=$decision execution=$execution symbol=$symbol market=$market buy=$plannedBuy sell=$plannedSell';
  }

  final report = p['report'];
  if (report is Map<String, dynamic>) {
    return jsonEncode(report);
  }

  final decision = p['decision'];
  if (decision != null) {
    return 'decision=${decision.toString()}';
  }

  return jsonEncode(p);
}
