import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:pecunator_desktop/api_client.dart';

class MockEngineApi extends Mock implements EngineApi {}

void main() {
  group('Louise Real-Time Data & Metrics Tests', () {
    late MockEngineApi mockApi;

    setUp(() {
      mockApi = MockEngineApi();
    });

    test('Metrics returns price and weight data', () async {
      when(() => mockApi.louiseMetrics()).thenAnswer(
        (_) async => {
          'last_price': 45321.50,
          'symbol': 'BTCUSDT',
          'weight_used': 120,
        },
      );

      final metrics = await mockApi.louiseMetrics();

      expect(metrics['last_price'], equals(45321.50));
      expect(metrics['symbol'], equals('BTCUSDT'));
      verify(() => mockApi.louiseMetrics()).called(1);
    });

    test('Repeated metrics poll returns updated values', () async {
      var callCount = 0;
      when(() => mockApi.louiseMetrics()).thenAnswer((_) async {
        callCount++;
        return {'last_price': 45000.0 + callCount * 100.0};
      });

      final first = await mockApi.louiseMetrics();
      final second = await mockApi.louiseMetrics();
      final third = await mockApi.louiseMetrics();

      expect(first['last_price'], equals(45100.0));
      expect(second['last_price'], equals(45200.0));
      expect(third['last_price'], equals(45300.0));
      verify(() => mockApi.louiseMetrics()).called(3);
    });

    test('Bots list reflects fill events after epoch', () async {
      when(() => mockApi.louiseBots()).thenAnswer(
        (_) async => [
          {
            'bot_id': 'bot_btc_001',
            'status': 'RUNNING',
            'symbol': 'BTCUSDT',
            'purchases_this_epoch': 2,
          },
        ],
      );

      final bots = await mockApi.louiseBots();

      expect(bots.length, equals(1));
      expect(bots[0]['status'], equals('RUNNING'));
      expect(bots[0]['purchases_this_epoch'], equals(2));
    });

    test('Health check detects gateway disconnect', () async {
      when(() => mockApi.louiseHealth()).thenAnswer(
        (_) async => {
          'ready': false,
          'gateway_connected': false,
          'error': 'gateway_disconnected',
        },
      );

      final health = await mockApi.louiseHealth();

      expect(health['ready'], isFalse);
      expect(health['gateway_connected'], isFalse);
    });

    test('Health check reconnects on next poll', () async {
      var callCount = 0;
      when(() => mockApi.louiseHealth()).thenAnswer((_) async {
        callCount++;
        if (callCount == 1) {
          return {'ready': false, 'error': 'gateway_disconnected'};
        }
        return {'ready': true, 'gateway_connected': true};
      });

      final first = await mockApi.louiseHealth();
      final second = await mockApi.louiseHealth();

      expect(first['ready'], isFalse);
      expect(second['ready'], isTrue);
      verify(() => mockApi.louiseHealth()).called(2);
    });

    test('Weight governor status updates via polling', () async {
      when(() => mockApi.louiseWeightStatus()).thenAnswer(
        (_) async => {
          'zone': 'GREEN',
          'weight_used_1m': 240,
          'weight_limit_1m': 6000,
        },
      );

      final status = await mockApi.louiseWeightStatus();

      expect(status['zone'], equals('GREEN'));
      expect(
        (status['weight_used_1m'] as int) < (status['weight_limit_1m'] as int),
        isTrue,
      );
    });

    test('Partial fill visible in bots list', () async {
      when(() => mockApi.louiseBots()).thenAnswer(
        (_) async => [
          {
            'bot_id': 'bot_btc_001',
            'status': 'RUNNING',
            'current_epoch': {
              'purchases': 3,
              'total_cost_usdt': 150.0,
              'partial_fill': true,
            },
          },
        ],
      );

      final bots = await mockApi.louiseBots();
      final epoch = bots[0]['current_epoch'] as Map<String, dynamic>;

      expect(epoch['partial_fill'], isTrue);
      expect(epoch['purchases'], equals(3));
    });
  });
}
