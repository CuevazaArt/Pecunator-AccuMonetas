/// UI tests for refactored architecture.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pecunator_desktop/config/app_config.dart';
import 'package:pecunator_desktop/services/exceptions.dart';

import 'package:pecunator_desktop/widgets/error_display.dart';
import 'package:pecunator_desktop/widgets/gateway_status.dart';
import 'package:pecunator_desktop/widgets/logs_viewer.dart';

void main() {
  group('PecunatorCore Refactored UI Tests', () {
    testWidgets('ErrorDisplay shows NetworkException', (WidgetTester tester) async {
      final error = NetworkException.timeout();

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ErrorDisplay(error: error),
          ),
        ),
      );

      expect(find.text(error.message), findsOneWidget);
      expect(find.byIcon(Icons.cloud_off), findsOneWidget);
    });

    testWidgets('ErrorDisplay shows ApiException', (WidgetTester tester) async {
      final error = ApiException.unauthorized();

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ErrorDisplay(error: error),
          ),
        ),
      );

      expect(find.text(error.message), findsOneWidget);
      expect(find.byIcon(Icons.lock_outline), findsOneWidget);
    });

    testWidgets('ErrorDisplay dismiss callback works', (WidgetTester tester) async {
      bool dismissed = false;
      final error = NetworkException(message: 'Test error');

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ErrorDisplay(
              error: error,
              onDismiss: () => dismissed = true,
            ),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.close));
      expect(dismissed, true);
    });

    testWidgets('GatewayStatus shows ON when running', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: GatewayStatus(isRunning: true, wsConnected: true),
          ),
        ),
      );

      expect(find.text('GW ON · WS'), findsOneWidget);
    });

    testWidgets('GatewayStatus shows OFF when not running', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: GatewayStatus(isRunning: false, wsConnected: false),
          ),
        ),
      );

      expect(find.text('GW OFF'), findsOneWidget);
    });

    testWidgets('LogsViewer displays logs correctly', (WidgetTester tester) async {
      const logs = '''2026-04-29T10:15:30Z [INFO] Cycle start
2026-04-29T10:15:31Z [INFO] decision=BUY execution=success
2026-04-29T10:15:32Z [INFO] Cycle end''';

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: LogsViewer(logs: logs),
          ),
        ),
      );

      expect(find.text(logs), findsOneWidget);
    });

    testWidgets('LogsViewer shows empty state', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: LogsViewer(logs: ''),
          ),
        ),
      );

      expect(find.text('(sin logs)'), findsOneWidget);
    });

    testWidgets('AppConfig constants are accessible', (WidgetTester tester) async {
      expect(AppConfig.engineDefaultHost, '127.0.0.1');
      expect(AppConfig.engineDefaultPort, 8765);
      expect(AppConfig.defaultSymbol, 'XRPUSDT');
      expect(AppConfig.networkTimeout, const Duration(seconds: 10));
    });

    testWidgets('AppConfig buildEngineUrl works', (WidgetTester tester) async {
      final url = AppConfig.buildEngineUrl();
      expect(url, 'http://127.0.0.1:8765');

      final customUrl = AppConfig.buildEngineUrl(host: '192.168.1.1', port: 9000);
      expect(customUrl, 'http://192.168.1.1:9000');
    });
  });

  group('Exception Classification Tests', () {
    test('NetworkException timeout factory', () {
      final error = NetworkException.timeout();
      expect(error.message.contains('agotada'), true);
    });

    test('NetworkException connection refused factory', () {
      final error = NetworkException.connectionRefused();
      expect(error.message.contains('No se pudo conectar'), true);
    });

    test('ApiException unauthorized factory', () {
      final error = ApiException.unauthorized();
      expect(error.statusCode, 401);
    });

    test('ApiException badRequest factory', () {
      final error = ApiException.badRequest('Invalid input');
      expect(error.statusCode, 400);
      expect(error.message.contains('Invalid input'), true);
    });

    test('ValidationException emptyCredential factory', () {
      final error = ValidationException.emptyCredential();
      expect(error.message.contains('requeridos'), true);
    });

    test('AuthException vaultLocked factory', () {
      final error = AuthException.vaultLocked();
      expect(error.message.contains('Vault'), true);
    });
  });




  group('Widget Integration Tests', () {
    testWidgets('ErrorDisplay + GatewayStatus together', (WidgetTester tester) async {
      final error = ApiException.serverError('DB unavailable');

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: Column(
              children: [
                ErrorDisplay(error: error),
                const GatewayStatus(isRunning: false, wsConnected: false),
              ],
            ),
          ),
        ),
      );

      expect(find.text(error.message), findsOneWidget);
      expect(find.text('GW OFF'), findsOneWidget);
    });

    testWidgets('LogsViewer auto-scrolls', (WidgetTester tester) async {
      const initialLogs = 'Line 1\nLine 2\nLine 3';
      const newLogs = 'Line 1\nLine 2\nLine 3\nLine 4 (new)';

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, setState) {
                String logs = initialLogs;
                return Column(
                  children: [
                    Expanded(child: LogsViewer(logs: logs, autoScroll: true)),
                    ElevatedButton(
                      onPressed: () {
                        setState(() {
                          logs = newLogs;
                        });
                      },
                      child: const Text('Add log'),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('Line 3'), findsOneWidget);
      await tester.tap(find.text('Add log'));
      await tester.pump();
      expect(find.text('Line 4 (new)'), findsOneWidget);
    });
  });
}
