/// API and domain exceptions with proper classification.
library;

abstract class AppException implements Exception {
  final String message;
  final String? originalError;

  AppException({required this.message, this.originalError});

  @override
  String toString() => message;
}

/// Network or transport errors (timeouts, connection refused).
class NetworkException extends AppException {
  NetworkException({required super.message, super.originalError});

  factory NetworkException.timeout() => NetworkException(
    message: 'Connection timed out: the server took too long to respond',
  );

  factory NetworkException.connectionRefused() => NetworkException(
    message: 'Could not connect to the engine. Is python main.py running?',
  );
}

/// HTTP or API errors (4xx, 5xx).
class ApiException extends AppException {
  final int? statusCode;

  ApiException({required super.message, this.statusCode, super.originalError});

  factory ApiException.unauthorized() => ApiException(
    message: 'Unauthorized: invalid credentials or session expired',
    statusCode: 401,
  );

  factory ApiException.badRequest(String details) =>
      ApiException(message: 'Invalid request: $details', statusCode: 400);

  factory ApiException.notFound() => ApiException(
    message: 'Resource not found on the server',
    statusCode: 404,
  );

  factory ApiException.serverError([String? details]) => ApiException(
    message: 'Server error${details != null ? ': $details' : ''}',
    statusCode: 500,
  );
}

/// Validation or business logic errors.
class ValidationException extends AppException {
  ValidationException({required super.message, super.originalError});

  factory ValidationException.emptyCredential() =>
      ValidationException(message: 'API key and secret are required');

  factory ValidationException.invalidSymbol(String symbol) =>
      ValidationException(message: 'Invalid symbol: $symbol');
}

/// Credential/security related errors.
class AuthException extends AppException {
  AuthException({required super.message, super.originalError});

  factory AuthException.credentialNotFound() =>
      AuthException(message: 'Credential not found in the vault');

  factory AuthException.vaultLocked() =>
      AuthException(message: 'Vault unavailable or unreadable');
}
