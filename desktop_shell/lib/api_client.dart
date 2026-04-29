import 'dart:convert';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  final String message;
  ApiException(this.message);

  @override
  String toString() => message;
}

class EngineApi {
  EngineApi(this.baseUrl);
  final String baseUrl;

  Uri _u(String path) => Uri.parse('$baseUrl$path');

  Future<Map<String, dynamic>> health() async {
    final r = await http.get(_u('/health'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> vaultStatus() async {
    final r = await http.get(_u('/api/v1/vault/status'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> activeCredential() async {
    final r = await http.get(_u('/api/v1/credentials/active'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> vaultCredentials() async {
    final r = await http.get(_u('/api/v1/vault/credentials'));
    _ensure(r);
    final obj = jsonDecode(r.body);
    if (obj is List) return {'items': obj};
    throw ApiException('Invalid vault credentials response');
  }

  Future<Map<String, dynamic>> addVaultCredential({
    required String apiKey,
    required String apiSecret,
    String? label,
    String? masterPassword,
  }) async {
    final r = await http.post(
      _u('/api/v1/vault/credentials'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'api_key': apiKey,
        'api_secret': apiSecret,
        'label': label,
        'master_password': masterPassword,
      }),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> updateVaultCredentialLabel(
    String credentialId, {
    required String label,
    String? masterPassword,
  }) async {
    final r = await http.patch(
      _u('/api/v1/vault/credentials/$credentialId'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'label': label,
        'master_password': masterPassword,
      }),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> activateVaultCredential(String credentialId) async {
    final r = await http.post(_u('/api/v1/vault/credentials/$credentialId/activate'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> deleteVaultCredential(
    String credentialId, {
    String? masterPassword,
  }) async {
    final r = await http.post(
      _u('/api/v1/vault/credentials/$credentialId/delete'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'master_password': masterPassword}),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> unlockVault(String masterPassword) async {
    final r = await http.post(
      _u('/api/v1/vault/session'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'master_password': masterPassword}),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> botConfig() async {
    final r = await http.get(_u('/api/v1/bot/config'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> setBotConfig(Map<String, dynamic> body) async {
    final r = await http.put(
      _u('/api/v1/bot/config'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> botStatus() async {
    final r = await http.get(_u('/api/v1/bot/status'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> botStart({String? masterPassword, String? apiKey, String? apiSecret}) async {
    final r = await http.post(
      _u('/api/v1/bot/start'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'master_password': masterPassword,
        'api_key': apiKey,
        'api_secret': apiSecret,
      }),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> botStop() async {
    final r = await http.post(_u('/api/v1/bot/stop'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> botRunOnce({String? masterPassword, String? apiKey, String? apiSecret}) async {
    final r = await http.post(
      _u('/api/v1/bot/run_once'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'master_password': masterPassword,
        'api_key': apiKey,
        'api_secret': apiSecret,
      }),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> gatewayStart({String? masterPassword, String? apiKey, String? apiSecret}) async {
    final r = await http.post(
      _u('/api/v1/gateway/start'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'master_password': masterPassword,
        'api_key': apiKey,
        'api_secret': apiSecret,
      }),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> gatewayStop() async {
    final r = await http.post(_u('/api/v1/gateway/stop'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> gatewaySnapshot() async {
    final r = await http.get(_u('/api/v1/gateway/snapshot'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> terminalExecute({
    required String command,
    String? masterPassword,
  }) async {
    final r = await http.post(
      _u('/api/v1/terminal/execute'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'command': command,
        'master_password': masterPassword,
      }),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> syncTimestamp({String? masterPassword, String? apiKey, String? apiSecret}) async {
    final r = await http.post(
      _u('/api/v1/time/sync'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'master_password': masterPassword,
        'api_key': apiKey,
        'api_secret': apiSecret,
      }),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> hubBots() async {
    final r = await http.get(_u('/api/v1/hub/bots'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> hubCreateBot(Map<String, dynamic> body) async {
    final r = await http.post(
      _u('/api/v1/hub/bots'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> hubUpdateBot(String botId, Map<String, dynamic> body) async {
    final r = await http.patch(
      _u('/api/v1/hub/bots/$botId'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> hubDeleteBot(String botId) async {
    final r = await http.delete(_u('/api/v1/hub/bots/$botId'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> hubStartBot(
    String botId, {
    String? masterPassword,
    String? apiKey,
    String? apiSecret,
  }) async {
    final r = await http.post(
      _u('/api/v1/hub/bots/$botId/start'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'master_password': masterPassword,
        'api_key': apiKey,
        'api_secret': apiSecret,
      }),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> hubStopBot(String botId) async {
    final r = await http.post(_u('/api/v1/hub/bots/$botId/stop'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> hubRunOnce(
    String botId, {
    String? masterPassword,
    String? apiKey,
    String? apiSecret,
  }) async {
    final r = await http.post(
      _u('/api/v1/hub/bots/$botId/run_once'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'master_password': masterPassword,
        'api_key': apiKey,
        'api_secret': apiSecret,
      }),
    );
    _ensure(r);
    return _jsonMap(r.body);
  }

  Future<Map<String, dynamic>> hubLogs(String botId, {int limit = 120}) async {
    final r = await http.get(_u('/api/v1/hub/bots/$botId/logs?limit=$limit'));
    _ensure(r);
    return _jsonMap(r.body);
  }

  void _ensure(http.Response r) {
    if (r.statusCode >= 200 && r.statusCode < 300) return;
    final body = r.body.isNotEmpty ? r.body : 'HTTP ${r.statusCode}';
    throw ApiException(body);
  }

  Map<String, dynamic> _jsonMap(String body) {
    final obj = jsonDecode(body);
    if (obj is Map<String, dynamic>) return obj;
    throw ApiException('Invalid JSON object response');
  }
}
