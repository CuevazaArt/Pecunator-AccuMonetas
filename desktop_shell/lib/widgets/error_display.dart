/// Error display widget with classification-based messaging.

import 'package:flutter/material.dart';

import '../services/exceptions.dart';

class ErrorDisplay extends StatelessWidget {
  final Object? error;
  final VoidCallback? onDismiss;

  const ErrorDisplay({
    super.key,
    this.error,
    this.onDismiss,
  });

  String _getErrorMessage() {
    if (error == null) return '';
    if (error is NetworkException) return (error as NetworkException).message;
    if (error is ApiException) return (error as ApiException).message;
    if (error is ValidationException) {
      return (error as ValidationException).message;
    }
    if (error is AuthException) return (error as AuthException).message;
    return error.toString();
  }

  @override
  Widget build(BuildContext context) {
    if (error == null) return const SizedBox.shrink();

    final message = _getErrorMessage();
    final isNetworkError = error is NetworkException;
    final isAuthError = error is AuthException;

    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: isAuthError
            ? Colors.red[900]
            : isNetworkError
                ? Colors.orange[900]
                : Colors.red[700],
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Row(
            children: [
              Icon(
                isAuthError
                    ? Icons.lock_outline
                    : isNetworkError
                        ? Icons.cloud_off
                        : Icons.error_outline,
                color: Colors.white,
                size: 20,
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  message,
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 13,
                  ),
                ),
              ),
              if (onDismiss != null)
                IconButton(
                  onPressed: onDismiss,
                  icon: const Icon(Icons.close, size: 18, color: Colors.white),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
