// HTTP client with retry logic, timeouts, and error classification.

import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import 'exceptions.dart';

class HttpClientConfig {
  final Duration timeout;
  final int maxRetries;
  final Duration retryDelay;

  const HttpClientConfig({
    this.timeout = const Duration(seconds: 10),
    this.maxRetries = 3,
    this.retryDelay = const Duration(milliseconds: 500),
  });
}

class RobustHttpClient {
  final String baseUrl;
  final http.Client _inner;
  final HttpClientConfig config;

  RobustHttpClient({
    required this.baseUrl,
    http.Client? httpClient,
    this.config = const HttpClientConfig(),
  }) : _inner = httpClient ?? http.Client();

  /// Perform GET request with retry and error handling.
  Future<Map<String, dynamic>> get(
    String endpoint, {
    Map<String, String>? headers,
  }) =>
      _requestWithRetry(
        () => _inner.get(
          Uri.parse('$baseUrl$endpoint'),
          headers: headers,
        ),
      );

  static const _jsonHeaders = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };

  Map<String, String> _mergeHeaders(Map<String, String>? headers) =>
      {..._jsonHeaders, ...?headers};

  /// Perform POST request with retry and error handling.
  Future<Map<String, dynamic>> post(
    String endpoint, {
    Map<String, String>? headers,
    dynamic body,
  }) =>
      _requestWithRetry(
        () => _inner.post(
          Uri.parse('$baseUrl$endpoint'),
          headers: _mergeHeaders(headers),
          body: body != null ? jsonEncode(body) : null,
        ),
      );

  /// Perform PATCH request with retry and error handling.
  Future<Map<String, dynamic>> patch(
    String endpoint, {
    Map<String, String>? headers,
    dynamic body,
  }) =>
      _requestWithRetry(
        () => _inner.patch(
          Uri.parse('$baseUrl$endpoint'),
          headers: _mergeHeaders(headers),
          body: body != null ? jsonEncode(body) : null,
        ),
      );

  /// Perform DELETE request with retry and error handling.
  Future<Map<String, dynamic>> delete(
    String endpoint, {
    Map<String, String>? headers,
  }) =>
      _requestWithRetry(
        () => _inner.delete(
          Uri.parse('$baseUrl$endpoint'),
          headers: headers,
        ),
      );

  /// Perform arbitrary HTTP request with retry and error handling.
  Future<Map<String, dynamic>> request(
    String method,
    String endpoint, {
    Map<String, String>? headers,
    dynamic body,
  }) {
    final m = method.trim().toUpperCase();
    final url = Uri.parse('$baseUrl$endpoint');
    switch (m) {
      case 'GET':
        return _requestWithRetry(() => _inner.get(url, headers: headers));
      case 'POST':
        return _requestWithRetry(
          () => _inner.post(
            url,
            headers: _mergeHeaders(headers),
            body: body != null ? jsonEncode(body) : null,
          ),
        );
      case 'PATCH':
        return _requestWithRetry(
          () => _inner.patch(
            url,
            headers: _mergeHeaders(headers),
            body: body != null ? jsonEncode(body) : null,
          ),
        );
      case 'DELETE':
        return _requestWithRetry(
          () => _inner.delete(
            url,
            headers: _mergeHeaders(headers),
          ),
        );
      default:
        throw ValidationException(message: 'Método HTTP no soportado: $method');
    }
  }

  /// Internal: retry logic with exponential backoff.
  Future<Map<String, dynamic>> _requestWithRetry(
    Future<http.Response> Function() fn,
  ) async {
    int attempt = 0;
    while (true) {
      try {
        final response = await fn().timeout(
          config.timeout,
          onTimeout: () => throw TimeoutException('Request timeout'),
        );
        return _parseResponse(response);
      } on TimeoutException {
        attempt++;
        if (attempt >= config.maxRetries) {
          throw NetworkException.timeout();
        }
        await Future.delayed(
          Duration(
            milliseconds: (config.retryDelay.inMilliseconds *
                    (1.5 * attempt).toInt())
                .clamp(0, 10000),
          ),
        );
      } catch (e) {
        if (e is AppException) rethrow;
        attempt++;
        if (attempt >= config.maxRetries) {
          throw NetworkException(
            message: 'No se pudo conectar al motor. ¿Está en línea?',
            originalError: e.toString(),
          );
        }
        await Future.delayed(
          Duration(
            milliseconds: (config.retryDelay.inMilliseconds *
                    (1.5 * attempt).toInt())
                .clamp(0, 10000),
          ),
        );
      }
    }
  }

  /// Parse HTTP response and classify errors.
  Map<String, dynamic> _parseResponse(http.Response response) {
    final contentType = response.headers['content-type'] ?? '';
    final isJson = contentType.contains('application/json');

    try {
      if (response.statusCode >= 200 && response.statusCode < 300) {
        if (response.body.isEmpty) return {};
        if (!isJson) return {'data': response.body};
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) return decoded;
        if (decoded is Map) return Map<String, dynamic>.from(decoded);
        if (decoded is List) return {'items': decoded};
        return {'data': decoded};
      }

      // Parse error response
      final errorBodyRaw = isJson ? jsonDecode(response.body) : <String, dynamic>{};
      final errorBody = errorBodyRaw is Map
          ? Map<String, dynamic>.from(errorBodyRaw)
          : <String, dynamic>{'detail': errorBodyRaw.toString()};
      final detail = errorBody['detail'] ?? '';

      switch (response.statusCode) {
        case 400:
          throw ValidationException(message: 'Solicitud inválida: $detail');
        case 401:
          throw ApiException.unauthorized();
        case 403:
          throw ApiException(
            message: 'Acceso prohibido: permisos insuficientes',
            statusCode: 403,
          );
        case 404:
          throw ApiException.notFound();
        case 422:
          throw ValidationException(
            message: 'Datos inválidos: $detail',
          );
        case >= 500:
          throw ApiException.serverError(detail);
        default:
          throw ApiException(
            message: 'Error HTTP ${response.statusCode}: $detail',
            statusCode: response.statusCode,
          );
      }
    } on AppException {
      rethrow;
    } catch (e) {
      throw ApiException(
        message: 'Error al procesar respuesta del servidor',
        originalError: e.toString(),
      );
    }
  }
}
