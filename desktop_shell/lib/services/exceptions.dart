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
    message: 'Conexión agotada: el servidor tardó demasiado en responder',
  );

  factory NetworkException.connectionRefused() => NetworkException(
    message: 'No se pudo conectar al motor. ¿Está ejecutando python main.py?',
  );
}

/// HTTP or API errors (4xx, 5xx).
class ApiException extends AppException {
  final int? statusCode;

  ApiException({required super.message, this.statusCode, super.originalError});

  factory ApiException.unauthorized() => ApiException(
    message: 'No autorizado: credenciales inválidas o sesión expirada',
    statusCode: 401,
  );

  factory ApiException.badRequest(String details) =>
      ApiException(message: 'Solicitud inválida: $details', statusCode: 400);

  factory ApiException.notFound() => ApiException(
    message: 'Recurso no encontrado en el servidor',
    statusCode: 404,
  );

  factory ApiException.serverError([String? details]) => ApiException(
    message: 'Error en el servidor${details != null ? ': $details' : ''}',
    statusCode: 500,
  );
}

/// Validation or business logic errors.
class ValidationException extends AppException {
  ValidationException({required super.message, super.originalError});

  factory ValidationException.emptyCredential() =>
      ValidationException(message: 'API key y secret son requeridos');

  factory ValidationException.invalidSymbol(String symbol) =>
      ValidationException(message: 'Símbolo inválido: $symbol');
}

/// Credential/security related errors.
class AuthException extends AppException {
  AuthException({required super.message, super.originalError});

  factory AuthException.credentialNotFound() =>
      AuthException(message: 'Credencial no encontrada en el vault');

  factory AuthException.vaultLocked() =>
      AuthException(message: 'Vault no disponible o ilegible');
}
