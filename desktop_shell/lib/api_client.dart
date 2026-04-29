import 'services/exceptions.dart';
import 'services/http_client.dart';

class EngineApi {
  late final RobustHttpClient _client;
  final String baseUrl;

  EngineApi(
    this.baseUrl, {
    HttpClientConfig? config,
  }) {
    _client = RobustHttpClient(
      baseUrl: baseUrl,
      config: config ?? const HttpClientConfig(),
    );
  }

  Future<Map<String, dynamic>> health() => _client.get('/health');

  Future<Map<String, dynamic>> vaultStatus() => _client.get('/api/v1/vault/status');

  Future<Map<String, dynamic>> activeCredential() => _client.get('/api/v1/credentials/active');

  Future<Map<String, dynamic>> vaultCredentials() async {
    final resp = await _client.get('/api/v1/vault/credentials');
    if (resp['items'] is List) return resp;
    // Handle legacy list response
    return {'items': resp['items'] ?? []};
  }

  Future<Map<String, dynamic>> addVaultCredential({
    required String apiKey,
    required String apiSecret,
    String? label,
    String? masterPassword,
  }) =>
      _client.post(
        '/api/v1/vault/credentials',
        body: {
          'api_key': apiKey,
          'api_secret': apiSecret,
          'label': label,
          'master_password': masterPassword,
        },
      );

  Future<Map<String, dynamic>> updateVaultCredentialLabel(
    String credentialId, {
    required String label,
    String? masterPassword,
  }) =>
      _client.patch(
        '/api/v1/vault/credentials/$credentialId',
        body: {'label': label, 'master_password': masterPassword},
      );

  Future<Map<String, dynamic>> activateVaultCredential(String credentialId) =>
      _client.post('/api/v1/vault/credentials/$credentialId/activate');

  Future<Map<String, dynamic>> deleteVaultCredential(
    String credentialId, {
    String? masterPassword,
  }) =>
      _client.post(
        '/api/v1/vault/credentials/$credentialId/delete',
        body: {'master_password': masterPassword},
      );

  Future<Map<String, dynamic>> unlockVault(String masterPassword) =>
      _client.post(
        '/api/v1/vault/session',
        body: {'master_password': masterPassword},
      );

  Future<Map<String, dynamic>> botConfig() => _client.get('/api/v1/bot/config');

  Future<Map<String, dynamic>> setBotConfig(Map<String, dynamic> body) =>
      _client.patch('/api/v1/bot/config', body: body);

  Future<Map<String, dynamic>> botStatus() => _client.get('/api/v1/bot/status');

  Future<Map<String, dynamic>> botStart({
    String? masterPassword,
    String? apiKey,
    String? apiSecret,
  }) =>
      _client.post(
        '/api/v1/bot/start',
        body: {
          'master_password': masterPassword,
          'api_key': apiKey,
          'api_secret': apiSecret,
        },
      );

  Future<Map<String, dynamic>> botStop() => _client.post('/api/v1/bot/stop');

  Future<Map<String, dynamic>> botRunOnce({
    String? masterPassword,
    String? apiKey,
    String? apiSecret,
  }) =>
      _client.post(
        '/api/v1/bot/run_once',
        body: {
          'master_password': masterPassword,
          'api_key': apiKey,
          'api_secret': apiSecret,
        },
      );

  Future<Map<String, dynamic>> gatewayStart({
    String? masterPassword,
    String? apiKey,
    String? apiSecret,
  }) =>
      _client.post(
        '/api/v1/gateway/start',
        body: {
          'master_password': masterPassword,
          'api_key': apiKey,
          'api_secret': apiSecret,
        },
      );

  Future<Map<String, dynamic>> gatewayStop() => _client.post('/api/v1/gateway/stop');

  Future<Map<String, dynamic>> gatewaySnapshot() => _client.get('/api/v1/gateway/snapshot');

  Future<Map<String, dynamic>> gatewayFetchAccount() =>
      _client.post('/api/v1/gateway/fetch_account');

  Future<Map<String, dynamic>> accountWallets({
    String baseAsset = 'USDT',
  }) =>
      _client.get('/api/v1/account/wallets?base_asset=$baseAsset');

  Future<Map<String, dynamic>> terminalExecute({
    required String command,
    String? masterPassword,
  }) =>
      _client.post(
        '/api/v1/terminal/execute',
        body: {'command': command, 'master_password': masterPassword},
      );

  Future<Map<String, dynamic>> syncTimestamp({
    String? masterPassword,
    String? apiKey,
    String? apiSecret,
  }) =>
      _client.post(
        '/api/v1/time/sync',
        body: {
          'master_password': masterPassword,
          'api_key': apiKey,
          'api_secret': apiSecret,
        },
      );

  Future<Map<String, dynamic>> hubBots() => _client.get('/api/v1/hub/bots');

  Future<Map<String, dynamic>> hubCreateBot(Map<String, dynamic> body) =>
      _client.post('/api/v1/hub/bots', body: body);

  Future<Map<String, dynamic>> hubUpdateBot(
    String botId,
    Map<String, dynamic> body,
  ) =>
      _client.patch('/api/v1/hub/bots/$botId', body: body);

  Future<Map<String, dynamic>> hubDeleteBot(String botId) =>
      _client.delete('/api/v1/hub/bots/$botId');

  Future<Map<String, dynamic>> hubStartBot(
    String botId, {
    String? masterPassword,
    String? apiKey,
    String? apiSecret,
  }) =>
      _client.post(
        '/api/v1/hub/bots/$botId/start',
        body: {
          'master_password': masterPassword,
          'api_key': apiKey,
          'api_secret': apiSecret,
        },
      );

  Future<Map<String, dynamic>> hubStopBot(String botId) =>
      _client.post('/api/v1/hub/bots/$botId/stop');

  Future<Map<String, dynamic>> hubRunOnce(
    String botId, {
    String? masterPassword,
    String? apiKey,
    String? apiSecret,
  }) =>
      _client.post(
        '/api/v1/hub/bots/$botId/run_once',
        body: {
          'master_password': masterPassword,
          'api_key': apiKey,
          'api_secret': apiSecret,
        },
      );

  Future<Map<String, dynamic>> hubLogs(String botId, {int limit = 120}) =>
      _client.get('/api/v1/hub/bots/$botId/logs?limit=$limit');
}
