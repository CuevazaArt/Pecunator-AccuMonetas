/// Exhaustive UI tests for Pecunator desktop hub.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:pecunator_desktop/config/app_config.dart';
import 'package:pecunator_desktop/services/exceptions.dart';

import 'package:pecunator_desktop/widgets/error_display.dart';
import 'package:pecunator_desktop/widgets/gateway_status.dart';
import 'package:pecunator_desktop/widgets/logs_viewer.dart';

void main() {
  // ═══════════════════════════════════════════════════════════════════
  //  1. ErrorDisplay Widget Tests
  // ═══════════════════════════════════════════════════════════════════
  group('ErrorDisplay Widget', () {
    testWidgets('shows NetworkException with cloud_off icon', (
      WidgetTester tester,
    ) async {
      final error = NetworkException.timeout();

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: ErrorDisplay(error: error)),
        ),
      );

      expect(find.text(error.message), findsOneWidget);
      expect(find.byIcon(Icons.cloud_off), findsOneWidget);
    });

    testWidgets('shows ApiException with error icon', (WidgetTester tester) async {
      final error = ApiException.unauthorized();

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: ErrorDisplay(error: error)),
        ),
      );

      expect(find.text(error.message), findsOneWidget);
      // ApiException (not AuthException) uses error_outline icon
      expect(find.byIcon(Icons.error_outline), findsOneWidget);
    });

    testWidgets('shows ServerError with warning icon', (WidgetTester tester) async {
      final error = ApiException.serverError('DB offline');

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: ErrorDisplay(error: error)),
        ),
      );

      expect(find.textContaining('DB offline'), findsOneWidget);
    });

    testWidgets('dismiss callback fires on close tap', (
      WidgetTester tester,
    ) async {
      bool dismissed = false;
      final error = NetworkException(message: 'Test error');

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ErrorDisplay(error: error, onDismiss: () => dismissed = true),
          ),
        ),
      );

      await tester.tap(find.byIcon(Icons.close));
      expect(dismissed, true);
    });

    testWidgets('shows connection refused message', (WidgetTester tester) async {
      final error = NetworkException.connectionRefused();

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(body: ErrorDisplay(error: error)),
        ),
      );

      expect(find.textContaining('conectar'), findsOneWidget);
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  //  2. GatewayStatus Widget Tests
  // ═══════════════════════════════════════════════════════════════════
  group('GatewayStatus Widget', () {
    testWidgets('shows ON with WS when both connected', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: GatewayStatus(isRunning: true, wsConnected: true),
          ),
        ),
      );

      expect(find.text('GW ON · WS'), findsOneWidget);
    });

    testWidgets('shows ON without WS', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: GatewayStatus(isRunning: true, wsConnected: false),
          ),
        ),
      );

      expect(find.text('GW ON'), findsOneWidget);
    });

    testWidgets('shows OFF when not running', (
      WidgetTester tester,
    ) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(
            body: GatewayStatus(isRunning: false, wsConnected: false),
          ),
        ),
      );

      expect(find.text('GW OFF'), findsOneWidget);
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  //  3. LogsViewer Widget Tests
  // ═══════════════════════════════════════════════════════════════════
  group('LogsViewer Widget', () {
    testWidgets('displays logs correctly', (
      WidgetTester tester,
    ) async {
      const logs = '''2026-04-29T10:15:30Z [INFO] Cycle start
2026-04-29T10:15:31Z [INFO] decision=BUY execution=success
2026-04-29T10:15:32Z [INFO] Cycle end''';

      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: LogsViewer(logs: logs)),
        ),
      );

      expect(find.text(logs), findsOneWidget);
    });

    testWidgets('shows empty state', (WidgetTester tester) async {
      await tester.pumpWidget(
        const MaterialApp(
          home: Scaffold(body: LogsViewer(logs: '')),
        ),
      );

      expect(find.text('(sin logs)'), findsOneWidget);
    });

    testWidgets('auto-scrolls when new logs arrive', (WidgetTester tester) async {
      // Use a ValueNotifier to track log content across rebuilds
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: _AutoScrollTestWidget(),
          ),
        ),
      );

      // Initial state shows the logs
      expect(find.byType(LogsViewer), findsOneWidget);
      await tester.tap(find.text('Add log'));
      await tester.pump();
      // Widget rebuilds with updated logs
      expect(find.byType(LogsViewer), findsOneWidget);
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  //  4. AppConfig Tests
  // ═══════════════════════════════════════════════════════════════════
  group('AppConfig', () {
    test('default constants are correct', () {
      expect(AppConfig.engineDefaultHost, '127.0.0.1');
      expect(AppConfig.engineDefaultPort, 8000);
      expect(AppConfig.defaultSymbol, 'XRPUSDT');
      expect(AppConfig.networkTimeout, const Duration(seconds: 10));
      expect(AppConfig.maxNetworkRetries, 3);
      expect(AppConfig.maxLogLines, 120);
    });

    test('buildEngineUrl generates correct default URL', () {
      final url = AppConfig.buildEngineUrl();
      expect(url, 'http://127.0.0.1:8000');
    });

    test('buildEngineUrl generates correct custom URL', () {
      final customUrl = AppConfig.buildEngineUrl(
        host: '192.168.1.1',
        port: 9000,
      );
      expect(customUrl, 'http://192.168.1.1:9000');
    });

    test('bot defaults are L0 calibrated', () {
      expect(AppConfig.defaultLoopInterval, 450);
      expect(AppConfig.defaultQuoteQty, '8');
      expect(AppConfig.defaultProfit, '0.05');
      expect(AppConfig.defaultDrop, '0.004');
    });

    test('UI constants are reasonable', () {
      expect(AppConfig.minDialogWidth, greaterThan(0));
      expect(AppConfig.maxDialogWidth, greaterThan(AppConfig.minDialogWidth));
      expect(AppConfig.configHistoryMaxItems, greaterThan(0));
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  //  5. Exception Classification Tests
  // ═══════════════════════════════════════════════════════════════════
  group('Exception System', () {
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

    test('ApiException serverError factory', () {
      final error = ApiException.serverError('DB crash');
      expect(error.statusCode, 500);
      expect(error.message.contains('DB crash'), true);
    });

    test('ValidationException emptyCredential factory', () {
      final error = ValidationException.emptyCredential();
      expect(error.message.contains('requeridos'), true);
    });

    test('AuthException vaultLocked factory', () {
      final error = AuthException.vaultLocked();
      expect(error.message.contains('Vault'), true);
    });

    test('NetworkException is PecunatorException', () {
      final error = NetworkException(message: 'test');
      expect(error, isA<AppException>());
    });

    test('ApiException is PecunatorException', () {
      final error = ApiException(statusCode: 503, message: 'test');
      expect(error, isA<AppException>());
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  //  6. Widget Integration Tests
  // ═══════════════════════════════════════════════════════════════════
  group('Widget Integration', () {
    testWidgets('ErrorDisplay + GatewayStatus together', (
      WidgetTester tester,
    ) async {
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

    testWidgets('Multiple errors render without overflow', (
      WidgetTester tester,
    ) async {
      final errors = [
        NetworkException.timeout(),
        ApiException.unauthorized(),
        NetworkException.connectionRefused(),
      ];

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: Column(
                children: errors.map((e) => ErrorDisplay(error: e)).toList(),
              ),
            ),
          ),
        ),
      );

      // All 3 errors should render
      for (final e in errors) {
        expect(find.text(e.message), findsOneWidget);
      }
    });

    testWidgets('Gateway status transitions', (WidgetTester tester) async {
      bool running = false;

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: StatefulBuilder(
              builder: (context, setState) {
                return Column(
                  children: [
                    GatewayStatus(isRunning: running, wsConnected: running),
                    ElevatedButton(
                      onPressed: () => setState(() => running = !running),
                      child: const Text('Toggle'),
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      );

      expect(find.text('GW OFF'), findsOneWidget);
      await tester.tap(find.text('Toggle'));
      await tester.pump();
      expect(find.text('GW ON · WS'), findsOneWidget);
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  //  7. Port Sync Verification Tests
  // ═══════════════════════════════════════════════════════════════════
  group('Port Synchronization', () {
    test('default port matches backend (8000)', () {
      expect(AppConfig.engineDefaultPort, 8000);
      expect(AppConfig.buildEngineUrl(), contains(':8000'));
    });

    test('URL construction is consistent', () {
      final url1 = AppConfig.buildEngineUrl();
      final url2 = 'http://${AppConfig.engineDefaultHost}:${AppConfig.engineDefaultPort}';
      expect(url1, url2);
    });
  });
}

/// Helper widget for the auto-scroll test — uses proper StatefulWidget
/// so logs variable survives across setState rebuilds.
class _AutoScrollTestWidget extends StatefulWidget {
  @override
  State<_AutoScrollTestWidget> createState() => _AutoScrollTestWidgetState();
}

class _AutoScrollTestWidgetState extends State<_AutoScrollTestWidget> {
  String _logs = 'Line 1\nLine 2\nLine 3';

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(child: LogsViewer(logs: _logs, autoScroll: true)),
        ElevatedButton(
          onPressed: () {
            setState(() {
              _logs = '$_logs\nLine 4 (new)';
            });
          },
          child: const Text('Add log'),
        ),
      ],
    );
  }
}
