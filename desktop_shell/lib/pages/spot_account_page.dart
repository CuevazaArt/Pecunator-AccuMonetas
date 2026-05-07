import 'dart:async';
import 'package:flutter/material.dart';
import '../utils.dart';
import '../api_client.dart';

class SpotAccountPage extends StatefulWidget {
  const SpotAccountPage({
    super.key,
    required this.engineBase,
    required this.activeSymbols,
  });

  final String engineBase;
  final List<String> activeSymbols;

  @override
  State<SpotAccountPage> createState() => _SpotAccountPageState();
}

class _SpotAccountPageState extends State<SpotAccountPage> {

  bool _loading = false;
  String _error = '-';
  String _fetchedAt = '-';
  Map<String, dynamic> _summary = <String, dynamic>{};
  Map<String, dynamic> _equity = <String, dynamic>{};
  List<Map<String, dynamic>> _spot = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _futures = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _earn = <Map<String, dynamic>>[];
  List<Map<String, dynamic>> _external = <Map<String, dynamic>>[];
  List<String> _warnings = <String>[];
  final _baseAssetCtrl = TextEditingController();
  Timer? _equityTimer;

  EngineApi get _api => EngineApi(widget.engineBase);

  @override
  void initState() {
    super.initState();
    _baseAssetCtrl.text = _inferBaseAsset(widget.activeSymbols);
    _refresh();
    _startEquityTimer();
  }

  @override
  void dispose() {
    _equityTimer?.cancel();
    _baseAssetCtrl.dispose();
    super.dispose();
  }

  void _startEquityTimer() {
    _equityTimer?.cancel();
    _equityTimer = Timer.periodic(
      const Duration(seconds: 3),
      (_) => _refreshLiveEquity(),
    );
  }

  Future<void> _refreshLiveEquity() async {
    if (!mounted) return;
    try {
      final snap = await _api.gatewaySnapshot();
      final equity = Map<String, dynamic>.from(
        (snap['account_equity'] as Map?) ?? const {},
      );
      if (!mounted || equity.isEmpty) return;
      setState(() {
        _equity = equity;
      });
    } catch (_) {
      // Keep last known equity; manual refresh still reports full errors.
    }
  }

  String _inferBaseAsset(List<String> symbols) {
    if (symbols.isEmpty) return 'USDT';
    final s = symbols.first.trim().toUpperCase();
    const quotes = [
      'USDT',
      'FDUSD',
      'USDC',
      'BUSD',
      'BTC',
      'ETH',
      'BNB',
      'TRY',
      'EUR',
    ];
    for (final q in quotes) {
      if (s.endsWith(q) && s.length > q.length) return q;
    }
    return 'USDT';
  }

  Future<void> _refresh({String? forceBaseAsset}) async {
    if (_loading) return;
    final base = (forceBaseAsset ?? _baseAssetCtrl.text).trim().toUpperCase();
    if (base.isEmpty) {
      if (mounted) setState(() => _error = 'Base asset requerido (ej. USDT)');
      return;
    }
    _baseAssetCtrl.text = base;
    if (mounted) {
      setState(() {
        _loading = true;
        _error = '-';
      });
    }
    try {
      await _api.gatewayStart();
      final snapFuture = _api.gatewayFetchAccount();
      final walletsFuture = _api.accountWallets(baseAsset: base);
      final snap = await snapFuture;
      final wallets = await walletsFuture;
      final summary = Map<String, dynamic>.from(
        (snap['account_summary'] as Map?) ?? const {},
      );
      final equity = Map<String, dynamic>.from(
        (snap['account_equity'] as Map?) ?? const {},
      );
      final spot = ((wallets['spot'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final futures = ((wallets['futures'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final earn = ((wallets['stake_earn'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final external = ((wallets['external'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      final warnings = ((wallets['warnings'] as List?) ?? const [])
          .map((e) => e.toString())
          .toList();
      final walletEquity = Map<String, dynamic>.from(
        (wallets['equity'] as Map?) ?? const {},
      );
      if (mounted) {
        setState(() {
          _summary = summary;
          _equity = equity.isNotEmpty ? equity : walletEquity;
          _spot = spot;
          _futures = futures;
          _earn = earn;
          _external = external;
          _warnings = warnings;
          _fetchedAt = DateTime.now().toLocal().toString();
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = e.toString());
    } finally {
      if (mounted) {
        setState(() => _loading = false);
      }
    }
  }

  Widget _kpi(String label, String value) {
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontSize: 12)),
              const SizedBox(height: 4),
              Text(
                value,
                style: const TextStyle(fontFamily: 'monospace', fontSize: 14),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _walletColumn(
    String title,
    List<Map<String, dynamic>> rows, {
    required String primaryKey,
    String? secondaryKey,
  }) {
    final base = _baseAssetCtrl.text.trim().toUpperCase();
    final highlighted = rows.where((r) {
      final asset = (r['asset'] ?? '').toString().toUpperCase();
      return asset == base || asset == 'LD$base';
    }).toList();
    final ordered = [
      ...highlighted,
      ...rows.where((r) => !highlighted.contains(r)),
    ];
    final list = ordered.take(120).toList();
    return Expanded(
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(8),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '$title (${rows.length})',
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 6),
              if (list.isEmpty)
                const Text('(vacío)', style: TextStyle(fontSize: 12))
              else
                SizedBox(
                  height: 350,
                  child: ListView.separated(
                    itemCount: list.length,
                    separatorBuilder: (_, separatorIndex) =>
                        const Divider(height: 8),
                    itemBuilder: (ctx, i) {
                      final row = list[i];
                      final asset = (row['asset'] ?? '').toString();
                      final primary = (row[primaryKey] ?? '0').toString();
                      final secondary = secondaryKey == null
                          ? null
                          : (row[secondaryKey] ?? '0').toString();
                      final isBase =
                          asset.toUpperCase() == base ||
                          asset.toUpperCase() == 'LD$base';
                      return Row(
                        children: [
                          SizedBox(
                            width: 88,
                            child: Text(
                              asset,
                              style: TextStyle(
                                fontFamily: 'monospace',
                                color: isBase ? Colors.amberAccent : null,
                                fontWeight: isBase
                                    ? FontWeight.w700
                                    : FontWeight.w400,
                              ),
                            ),
                          ),
                          Expanded(
                            child: Text(
                              secondary == null
                                  ? '$primaryKey ${plainNum(primary)}'
                                  : '$primaryKey ${plainNum(primary)} · $secondaryKey ${plainNum(secondary)}',
                              style: const TextStyle(
                                fontFamily: 'monospace',
                                fontSize: 11,
                              ),
                            ),
                          ),
                        ],
                      );
                    },
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _baseTotalsCard() {
    final base = _baseAssetCtrl.text.trim().toUpperCase();
    String pick(
      List<Map<String, dynamic>> rows,
      String key, {
      bool withLd = false,
    }) {
      final target = withLd ? 'LD$base' : base;
      final row = rows.cast<Map<String, dynamic>?>().firstWhere(
        (r) => (r?['asset'] ?? '').toString().toUpperCase() == target,
        orElse: () => null,
      );
      return (row?[key] ?? '0').toString();
    }

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Row(
          children: [
            _kpi('$base Spot', plainNum(pick(_spot, 'total'))),
            _kpi('$base Futures', plainNum(pick(_futures, 'total'))),
            _kpi('LD$base Earn', plainNum(pick(_earn, 'total', withLd: true))),
            _kpi('$base Ext', plainNum(pick(_external, 'total'))),
          ],
        ),
      ),
    );
  }

  Widget _equityCard() {
    final base =
        (_equity['base_asset'] ?? _baseAssetCtrl.text.trim().toUpperCase())
            .toString();
    final current = plainNum(_equity['current']);
    final avg = plainNum(_equity['avg']);
    final highAvg = plainNum(_equity['high_avg']);
    final missing = (_equity['missing_assets_count'] ?? 0).toString();
    final updatedAt = (_equity['updated_at'] ?? _fetchedAt).toString();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Monitoreo Equity (tiempo real)',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 6),
            Row(
              children: [
                _kpi('Equity $base', current),
                _kpi('Promedio', avg),
                _kpi('Máx prom', highAvg),
                _kpi('Sin precio', missing),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              'Actualizado: $updatedAt',
              style: const TextStyle(fontSize: 12),
            ),
          ],
        ),
      ),
    );
  }

  Widget _warningsBlock() {
    if (_warnings.isEmpty) return const SizedBox.shrink();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Observaciones de lectura',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(height: 4),
            ..._warnings.map(
              (w) => Text('â€¢ $w', style: const TextStyle(fontSize: 12)),
            ),
          ],
        ),
      ),
    );
  }

  Widget _baseAssetBar() {
    final symbols = widget.activeSymbols.join(', ');
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Row(
          children: [
            const Text(
              'Activo base Dorothy:',
              style: TextStyle(fontWeight: FontWeight.w600),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 110,
              child: TextField(
                controller: _baseAssetCtrl,
                textCapitalization: TextCapitalization.characters,
                decoration: const InputDecoration(
                  isDense: true,
                  border: OutlineInputBorder(),
                ),
              ),
            ),
            const SizedBox(width: 8),
            FilledButton.tonal(
              onPressed: _loading
                  ? null
                  : () => _refresh(forceBaseAsset: _baseAssetCtrl.text),
              child: const Text('Aplicar'),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'Símbolos activos Dorothy: ${symbols.isEmpty ? '-' : symbols}',
                style: const TextStyle(fontSize: 12),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _consolidatedPanel() {
    final base = _baseAssetCtrl.text.trim().toUpperCase();
    // Compute totals per wallet type
    double spotTotal = 0, futTotal = 0, earnTotal = 0, extTotal = 0;
    double spotFree = 0, spotLocked = 0;
    for (final r in _spot) {
      final asset = (r['asset'] ?? '').toString().toUpperCase();
      if (asset == base) {
        spotFree = double.tryParse((r['free'] ?? '0').toString()) ?? 0;
        spotLocked = double.tryParse((r['locked'] ?? '0').toString()) ?? 0;
        spotTotal = double.tryParse((r['total'] ?? '0').toString()) ?? (spotFree + spotLocked);
      }
    }
    for (final r in _futures) {
      final asset = (r['asset'] ?? '').toString().toUpperCase();
      if (asset == base) {
        futTotal = double.tryParse((r['total'] ?? r['wallet_balance'] ?? '0').toString()) ?? 0;
      }
    }
    for (final r in _earn) {
      final asset = (r['asset'] ?? '').toString().toUpperCase();
      if (asset == base || asset == 'LD$base') {
        earnTotal += double.tryParse((r['total'] ?? '0').toString()) ?? 0;
      }
    }
    for (final r in _external) {
      final asset = (r['asset'] ?? '').toString().toUpperCase();
      if (asset == base) {
        extTotal = double.tryParse((r['total'] ?? '0').toString()) ?? 0;
      }
    }
    final grandTotal = spotTotal + futTotal + earnTotal + extTotal;
    final liquidAvailable = spotFree; // Immediately tradeable

    // Equity data
    final equityCurrent = plainNum(_equity['current']);
    final equityAvg = plainNum(_equity['avg']);
    final equityHighAvg = plainNum(_equity['high_avg']);

    // Account health
    final canTrade = _summary['canTrade'] == true;
    final canWithdraw = _summary['canWithdraw'] == true;
    final nonBaseAssets = _spot.where((r) {
      final a = (r['asset'] ?? '').toString().toUpperCase();
      return a != base && a.isNotEmpty;
    }).length;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              children: [
                const Icon(Icons.dashboard, size: 16),
                const SizedBox(width: 6),
                const Text('Panel Consolidado',
                    style: TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
                const Spacer(),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: canTrade ? const Color(0x2200E676) : const Color(0x22FF1744),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    canTrade ? 'TRADE OK' : 'TRADE OFF',
                    style: TextStyle(
                      fontSize: 9, fontWeight: FontWeight.w800,
                      color: canTrade ? Colors.greenAccent : Colors.redAccent,
                    ),
                  ),
                ),
                const SizedBox(width: 4),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color: canWithdraw ? const Color(0x2200E676) : const Color(0x22FF1744),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text(
                    canWithdraw ? 'WITHDRAW OK' : 'WITHDRAW OFF',
                    style: TextStyle(
                      fontSize: 9, fontWeight: FontWeight.w800,
                      color: canWithdraw ? Colors.greenAccent : Colors.redAccent,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 8),
            // Row 1: Liquidity breakdown
            Row(
              children: [
                _panelKpi('Líquido disponible', plainNum(liquidAvailable.toString()),
                    Colors.greenAccent),
                _panelKpi('Spot total $base', plainNum(spotTotal.toString()),
                    Colors.cyanAccent),
                _panelKpi('Bloqueado', plainNum(spotLocked.toString()),
                    spotLocked > 0 ? Colors.orangeAccent : Colors.grey),
                _panelKpi('Futures $base', plainNum(futTotal.toString()),
                    futTotal > 0 ? Colors.amberAccent : Colors.grey),
                _panelKpi('Earn/Stake', plainNum(earnTotal.toString()),
                    earnTotal > 0 ? Colors.purpleAccent : Colors.grey),
                _panelKpi('GRAN TOTAL', plainNum(grandTotal.toString()),
                    Colors.white),
              ],
            ),
            const SizedBox(height: 4),
            // Row 2: Equity + portfolio
            Row(
              children: [
                _panelKpi('Equity actual', equityCurrent, Colors.cyanAccent),
                _panelKpi('Equity promedio', equityAvg, Colors.blueAccent),
                _panelKpi('Equity máx prom', equityHighAvg, Colors.amberAccent),
                _panelKpi('Activos Spot', '${_spot.length}', Colors.cyanAccent),
                _panelKpi('No-$base', '$nonBaseAssets', nonBaseAssets > 0 ? Colors.orangeAccent : Colors.grey),
                _panelKpi('Wallets', '${_spot.length + _futures.length + _earn.length + _external.length}',
                    Colors.grey),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _panelKpi(String label, String value, Color valueColor) {
    return Expanded(
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 2),
        child: Column(
          children: [
            Text(label, style: const TextStyle(fontSize: 9), textAlign: TextAlign.center),
            const SizedBox(height: 1),
            Text(value,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontFamily: 'monospace',
                  fontWeight: FontWeight.w800,
                  fontSize: 12,
                  color: valueColor,
                )),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Cuenta Spot · Binance'),
        actions: [
          IconButton(
            onPressed: _loading
                ? null
                : () => _refresh(forceBaseAsset: _baseAssetCtrl.text),
            tooltip: 'Refrescar resumen Spot',
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (_loading) const LinearProgressIndicator(),
            if (_error != '-')
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Text(
                  _error,
                  style: const TextStyle(color: Colors.redAccent),
                ),
              ),
            _baseAssetBar(),
            // ── Consolidated Command Panel ──
            _consolidatedPanel(),
            _equityCard(),
            _baseTotalsCard(),
            _warningsBlock(),
            Text(
              'Última lectura: $_fetchedAt',
              style: const TextStyle(fontSize: 12),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                _kpi(
                  'Account type',
                  (_summary['accountType'] ?? '-').toString(),
                ),
                _kpi('Can trade', (_summary['canTrade'] ?? '-').toString()),
                _kpi(
                  'Can withdraw',
                  (_summary['canWithdraw'] ?? '-').toString(),
                ),
                _kpi('Can deposit', (_summary['canDeposit'] ?? '-').toString()),
              ],
            ),
            Row(
              children: [
                _kpi(
                  'Maker fee',
                  (_summary['makerCommission'] ?? '-').toString(),
                ),
                _kpi(
                  'Taker fee',
                  (_summary['takerCommission'] ?? '-').toString(),
                ),
                _kpi(
                  'Buyer fee',
                  (_summary['buyerCommission'] ?? '-').toString(),
                ),
                _kpi(
                  'Seller fee',
                  (_summary['sellerCommission'] ?? '-').toString(),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _walletColumn(
                  'Spot',
                  _spot,
                  primaryKey: 'free',
                  secondaryKey: 'locked',
                ),
                _walletColumn(
                  'Futures',
                  _futures,
                  primaryKey: 'wallet_balance',
                  secondaryKey: 'cross_wallet_balance',
                ),
                _walletColumn(
                  'Stake/Earn',
                  _earn,
                  primaryKey: 'free',
                  secondaryKey: 'locked',
                ),
                _walletColumn(
                  'Ext',
                  _external,
                  primaryKey: 'free',
                  secondaryKey: 'locked',
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
