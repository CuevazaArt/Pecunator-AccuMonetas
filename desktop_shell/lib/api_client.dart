import 'services/http_client.dart';

class EngineApi {
  late final RobustHttpClient _client;
  final String baseUrl;

  EngineApi(this.baseUrl, {HttpClientConfig? config}) {
    _client = RobustHttpClient(
      baseUrl: baseUrl,
      config: config ?? const HttpClientConfig(),
    );
  }

  Future<Map<String, dynamic>> health() => _client.get('/health');

  Future<Map<String, dynamic>> vaultStatus() =>
      _client.get('/api/v1/vault/status');

  Future<Map<String, dynamic>> activeCredential() =>
      _client.get('/api/v1/credentials/active');

  Future<Map<String, dynamic>> vaultCredentials() async {
    final resp = await _client.get('/api/v1/vault/credentials');
    if (resp['items'] is List) return resp;
    return {'items': resp['items'] ?? []};
  }

  Future<Map<String, dynamic>> addVaultCredential({
    required String apiKey,
    required String apiSecret,
    String? label,
  }) => _client.post(
    '/api/v1/vault/credentials',
    body: {
      'api_key': apiKey,
      'api_secret': apiSecret,
      if (label != null && label.isNotEmpty) 'label': label,
    },
  );

  Future<Map<String, dynamic>> updateVaultCredentialLabel(
    String credentialId, {
    required String label,
  }) => _client.patch(
    '/api/v1/vault/credentials/$credentialId',
    body: {'label': label},
  );

  Future<Map<String, dynamic>> deleteVaultCredential(String credentialId) =>
      _client.delete('/api/v1/vault/credentials/$credentialId');

  Future<Map<String, dynamic>> subaccountsList() =>
      _client.get('/api/v1/subaccounts/list');

  Future<Map<String, dynamic>> botConfig() => _client.get('/api/v1/bot/config');

  Future<Map<String, dynamic>> setBotConfig(Map<String, dynamic> body) =>
      _client.patch('/api/v1/bot/config', body: body);

  Future<Map<String, dynamic>> botStatus() => _client.get('/api/v1/bot/status');

  Future<Map<String, dynamic>> botStart({String? apiKey, String? apiSecret}) =>
      _client.post(
        '/api/v1/bot/start',
        body: {
          if (apiKey != null && apiKey.isNotEmpty) 'api_key': apiKey,
          if (apiSecret != null && apiSecret.isNotEmpty)
            'api_secret': apiSecret,
        },
      );

  Future<Map<String, dynamic>> botStop() => _client.post('/api/v1/bot/stop');

  Future<Map<String, dynamic>> botRunOnce({
    String? apiKey,
    String? apiSecret,
  }) => _client.post(
    '/api/v1/bot/run_once',
    body: {
      if (apiKey != null && apiKey.isNotEmpty) 'api_key': apiKey,
      if (apiSecret != null && apiSecret.isNotEmpty) 'api_secret': apiSecret,
    },
  );

  Future<Map<String, dynamic>> gatewayStart({
    String? apiKey,
    String? apiSecret,
  }) => _client.post(
    '/api/v1/gateway/start',
    body: {
      if (apiKey != null && apiKey.isNotEmpty) 'api_key': apiKey,
      if (apiSecret != null && apiSecret.isNotEmpty) 'api_secret': apiSecret,
    },
  );

  Future<Map<String, dynamic>> gatewayStop() =>
      _client.post('/api/v1/gateway/stop');

  Future<Map<String, dynamic>> gatewaySnapshot() =>
      _client.get('/api/v1/gateway/snapshot');

  Future<Map<String, dynamic>> gatewayFetchAccount() =>
      _client.post('/api/v1/gateway/fetch_account');

  Future<Map<String, dynamic>> accountWallets({String baseAsset = 'USDT'}) =>
      _client.get('/api/v1/account/wallets?base_asset=$baseAsset');

  /// Auto-resolve qty_decimals and price_decimals from Binance exchangeInfo.
  Future<Map<String, dynamic>> symbolPrecision(String symbol) =>
      _client.get('/api/v1/gateway/symbol_precision?symbol=${Uri.encodeComponent(symbol)}');

  Future<Map<String, dynamic>> terminalExecute({required String command}) =>
      _client.post('/api/v1/terminal/execute', body: {'command': command});

  Future<Map<String, dynamic>> syncTimestamp({
    String? apiKey,
    String? apiSecret,
  }) => _client.post(
    '/api/v1/time/sync',
    body: {
      if (apiKey != null && apiKey.isNotEmpty) 'api_key': apiKey,
      if (apiSecret != null && apiSecret.isNotEmpty) 'api_secret': apiSecret,
    },
  );

  Future<Map<String, dynamic>> restWeightSamples({int limit = 200}) =>
      _client.get('/api/v1/usage/rest-weight/samples?limit=$limit');

  Future<Map<String, dynamic>> restWeightEvents({int limit = 300}) =>
      _client.get('/api/v1/usage/rest-weight/events?limit=$limit');

  Future<Map<String, dynamic>> restWeightReport() =>
      _client.get('/api/v1/usage/rest-weight/report');

  Future<Map<String, dynamic>> protocolOpsStatus() =>
      _client.get('/api/v1/ops/protocol/status');

  Future<Map<String, dynamic>> executeCloseProtocol({
    String baseAsset = 'USDT',
  }) => _client.post(
    '/api/v1/ops/protocol/close?base_asset=${Uri.encodeComponent(baseAsset)}',
  );

  Future<Map<String, dynamic>> executeRedButton({String baseAsset = 'USDT'}) =>
      _client.post(
        '/api/v1/ops/red_button?base_asset=${Uri.encodeComponent(baseAsset)}',
      );

  Future<Map<String, dynamic>> executeOrderCleanupLimit({
    String baseAsset = 'USDT',
  }) => _client.post(
    '/api/v1/ops/orders/cleanup/limit?base_asset=${Uri.encodeComponent(baseAsset)}',
  );

  Future<Map<String, dynamic>> executeOrderCleanupStop({
    String baseAsset = 'USDT',
  }) => _client.post(
    '/api/v1/ops/orders/cleanup/stop?base_asset=${Uri.encodeComponent(baseAsset)}',
  );

  Future<Map<String, dynamic>> executeOrderCleanupAll({
    String baseAsset = 'USDT',
  }) => _client.post(
    '/api/v1/ops/orders/cleanup/all?base_asset=${Uri.encodeComponent(baseAsset)}',
  );

  Future<Map<String, dynamic>> hubBots() => _client.get('/api/v1/hub/bots');

  Future<Map<String, dynamic>> hubCreateBot(Map<String, dynamic> body) =>
      _client.post('/api/v1/hub/bots', body: body);

  Future<Map<String, dynamic>> hubUpdateBot(
    String botId,
    Map<String, dynamic> body,
  ) => _client.patch('/api/v1/hub/bots/$botId', body: body);

  Future<Map<String, dynamic>> hubDeleteBot(String botId) =>
      _client.delete('/api/v1/hub/bots/$botId');

  Future<Map<String, dynamic>> hubStartBot(
    String botId, {
    String? apiKey,
    String? apiSecret,
  }) => _client.post(
    '/api/v1/hub/bots/$botId/start',
    body: {
      if (apiKey != null && apiKey.isNotEmpty) 'api_key': apiKey,
      if (apiSecret != null && apiSecret.isNotEmpty) 'api_secret': apiSecret,
    },
  );

  Future<Map<String, dynamic>> hubStopBot(String botId) =>
      _client.post('/api/v1/hub/bots/$botId/stop');

  Future<Map<String, dynamic>> hubRunOnce(
    String botId, {
    String? apiKey,
    String? apiSecret,
  }) => _client.post(
    '/api/v1/hub/bots/$botId/run_once',
    body: {
      if (apiKey != null && apiKey.isNotEmpty) 'api_key': apiKey,
      if (apiSecret != null && apiSecret.isNotEmpty) 'api_secret': apiSecret,
    },
  );

  Future<Map<String, dynamic>> hubLogs(String botId, {int limit = 120}) =>
      _client.get('/api/v1/hub/bots/$botId/logs?limit=$limit');

  Future<Map<String, dynamic>> elphabaBots() => _client.get('/api/v1/elphaba/bots');

  Future<Map<String, dynamic>> elphabaCreateBot(Map<String, dynamic> body) =>
      _client.post('/api/v1/elphaba/bots', body: body);

  Future<Map<String, dynamic>> elphabaUpdateBot(
    String botId,
    Map<String, dynamic> body,
  ) => _client.patch('/api/v1/elphaba/bots/$botId', body: body);

  Future<Map<String, dynamic>> elphabaDeleteBot(String botId) =>
      _client.delete('/api/v1/elphaba/bots/$botId');

  Future<Map<String, dynamic>> elphabaStartBot(
    String botId, {
    String? apiKey,
    String? apiSecret,
  }) => _client.post(
    '/api/v1/elphaba/bots/$botId/start',
    body: {
      if (apiKey != null && apiKey.isNotEmpty) 'api_key': apiKey,
      if (apiSecret != null && apiSecret.isNotEmpty) 'api_secret': apiSecret,
    },
  );

  Future<Map<String, dynamic>> elphabaStopBot(String botId) =>
      _client.post('/api/v1/elphaba/bots/$botId/stop');

  Future<Map<String, dynamic>> elphabaRunOnce(
    String botId, {
    String? apiKey,
    String? apiSecret,
  }) => _client.post(
    '/api/v1/elphaba/bots/$botId/run_once',
    body: {
      if (apiKey != null && apiKey.isNotEmpty) 'api_key': apiKey,
      if (apiSecret != null && apiSecret.isNotEmpty) 'api_secret': apiSecret,
    },
  );

  Future<Map<String, dynamic>> elphabaLogs(String botId, {int limit = 120}) =>
      _client.get('/api/v1/elphaba/bots/$botId/logs?limit=$limit');



  Future<Map<String, dynamic>> sandboxRequest({
    required String method,
    required String endpoint,
    dynamic body,
  }) => _client.request(
    method,
    endpoint,
    body: body,
  );

  Future<Map<String, dynamic>> saveSandboxCurated(Map<String, dynamic> payload) =>
      _client.post('/api/v1/sandbox/curated/save', body: payload);

  Future<Map<String, dynamic>> listSandboxCurated({int limit = 50}) =>
      _client.get('/api/v1/sandbox/curated/list?limit=$limit');

  Future<Map<String, dynamic>> sandboxRestCatalog() =>
      _client.get('/api/v1/sandbox/rest/catalog');

  Future<Map<String, dynamic>> sandboxRestQuery({
    String? queryId,
    String? callExpression,
    String? symbol,
    int limit = 50,
  }) => _client.post(
    '/api/v1/sandbox/rest/query',
    body: {
      if (queryId != null && queryId.trim().isNotEmpty)
        'query_id': queryId.trim(),
      if (callExpression != null && callExpression.trim().isNotEmpty)
        'call': callExpression.trim(),
      if (symbol != null && symbol.trim().isNotEmpty)
        'symbol': symbol.trim().toUpperCase(),
      'limit': limit,
    },
  );

  // ── API Fuse & Binance Log endpoints ──────────────────────────

  Future<Map<String, dynamic>> apiFuseStatus() =>
      _client.get('/api-fuse/status');

  Future<Map<String, dynamic>> apiFuseReset() =>
      _client.post('/api-fuse/reset');

  Future<Map<String, dynamic>> gatewaySettings() =>
      _client.get('/gateway/settings');

  Future<Map<String, dynamic>> updateGatewaySettings(Map<String, dynamic> body) =>
      _client.post('/gateway/settings', body: body);

  Future<Map<String, dynamic>> apiLogRecent({int limit = 100, String? source, bool errorsOnly = false}) async {
    final q = StringBuffer('/api-log/recent?limit=$limit');
    if (source != null && source.isNotEmpty) q.write('&source=$source');
    if (errorsOnly) q.write('&errors_only=true');
    // Endpoint returns a list; wrap in map for consistency.
    final resp = await _client.get(q.toString());
    return resp;
  }

  Future<Map<String, dynamic>> apiLogWeightSummary() =>
      _client.get('/api-log/weight-summary');

  Future<Map<String, dynamic>> apiLogDbStats() =>
      _client.get('/api-log/db-stats');

  // ── Vision / VMO endpoints ──────────────────────────────────────

  Future<Map<String, dynamic>> visionStatus() =>
      _client.get('/api/v1/vision/status');

  Future<Map<String, dynamic>> visionRegimesLatest() =>
      _client.get('/api/v1/vision/regimes/latest');

  // ── Market Events endpoints ───────────────────────────────────

  Future<Map<String, dynamic>> eventsSummary() =>
      _client.get('/api/v1/events/summary');

  Future<Map<String, dynamic>> eventsCalendar() =>
      _client.get('/api/v1/events/calendar');

  Future<Map<String, dynamic>> eventsHeatmap() =>
      _client.get('/api/v1/events/activity_heatmap');

  Future<Map<String, dynamic>> eventsGeopolitical() =>
      _client.get('/api/v1/events/geopolitical');

  Future<Map<String, dynamic>> eventsFearGreed() =>
      _client.get('/api/v1/events/fear_greed');

  // ── v0.11 Risk Control endpoints ─────────────────────────────────

  Future<Map<String, dynamic>> orderLedgerStats() =>
      _client.get('/api/v1/order-ledger/stats');

  Future<Map<String, dynamic>> orderLedgerRecent({int limit = 50}) =>
      _client.get('/api/v1/order-ledger/recent?limit=$limit');

  // regimeFilterStatus removed in v2.0 — replaced by GTI

  Future<Map<String, dynamic>> healthDeep() =>
      _client.get('/api/v1/health/deep');

  Future<Map<String, dynamic>> healthV1() =>
      _client.get('/api/v1/health');

  // ── Prospector endpoints ──────────────────────────────────────

  Future<Map<String, dynamic>> prospectorScan({int topN = 15}) =>
      _client.get(
        '/prospector/scan?top_n=$topN',
        timeout: const Duration(seconds: 120),
      );

  Future<Map<String, dynamic>> prospectorLast() =>
      _client.get('/prospector/last');

  Future<Map<String, dynamic>> prospectorScore(String symbol) =>
      _client.get('/prospector/score/${Uri.encodeComponent(symbol)}');
}
