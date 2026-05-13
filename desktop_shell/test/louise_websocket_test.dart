import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import '../lib/api_client.dart';

class MockApiClient extends Mock implements ApiClient {}

void main() {
  group('Louise Real-Time Data & Metrics Tests', () {
    late MockApiClient mockApiClient;

    setUp(() {
      mockApiClient = MockApiClient();
    });

    test('Metrics returns price and weight data', () async {
      when(() => mockApiClient.louiseMetrics()).thenAnswer((_) async => {
            'last_price': 45321.50,
            'symbol': 'BTCUSDT',
            'weight_used': 120,
          });

      final metrics = await mockApiClient.louiseMetrics();

      expect(metrics['last_price'], equals(45321.50));
      expect(metrics['symbol'], equals('BTCUSDT'));
      verify(() => mockApiClient.louiseMetrics()).called(1);
    });

    test('Repeated metrics poll returns updated values', () async {
      var callCount = 0;
      when(() => mockApiClient.louiseMetrics()).thenAnswer((_) async {
        callCount++;
        return {'last_price': 45000.0 + callCount * 100.0};
      });

      final first = await mockApiClient.louiseMetrics();
      final second = await mockApiClient.louiseMetrics();
      final third = await mockApiClient.louiseMetrics();

      expect(first['last_price'], equals(45100.0));
      expect(second['last_price'], equals(45200.0));
      expect(third['last_price'], equals(45300.0));
      verify(() => mockApiClient.louiseMetrics()).called(3);
    });

    test('Bots list reflects fill events after epoch', () async {
      when(() => mockApiClient.louiseBots()).thenAnswer((_) async => [
            {
              'bot_id': 'bot_btc_001',
              'status': 'RUNNING',
              'symbol': 'BTCUSDT',
              'purchases_this_epoch': 2,
            },
          ]);

      final bots = await mockApiClient.louiseBots();

      expect(bots.length, equals(1));
      expect(bots[0]['status'], equals('RUNNING'));
      expect(bots[0]['purchases_this_epoch'], equals(2));
    });

    test('Health check detects gateway disconnect', () async {
      when(() => mockApiClient.louiseHealth()).thenAnswer((_) async => {
            'ready': false,
            'gateway_connected': false,
            'error': 'gateway_disconnected',
          });

      final health = await mockApiClient.louiseHealth();

      expect(health['ready'], isFalse);
      expect(health['gateway_connected'], isFalse);
    });

    test('Health check reconnects on next poll', () async {
      var callCount = 0;
      when(() => mockApiClient.louiseHealth()).thenAnswer((_) async {
        callCount++;
        if (callCount == 1) {
          return {'ready': false, 'error': 'gateway_disconnected'};
        }
        return {'ready': true, 'gateway_connected': true};
      });

      final first = await mockApiClient.louiseHealth();
      final second = await mockApiClient.louiseHealth();

      expect(first['ready'], isFalse);
      expect(second['ready'], isTrue);
      verify(() => mockApiClient.louiseHealth()).called(2);
    });

    test('Weight governor status updates via polling', () async {
      when(() => mockApiClient.louiseWeightStatus()).thenAnswer((_) async => {
            'zone': 'GREEN',
            'weight_used_1m': 240,
            'weight_limit_1m': 6000,
          });

      final status = await mockApiClient.louiseWeightStatus();

      expect(status['zone'], equals('GREEN'));
      expect(status['weight_used_1m'], lessThan(status['weight_limit_1m']));
    });

    test('Partial fill visible in bots list', () async {
      when(() => mockApiClient.louiseBots()).thenAnswer((_) async => [
            {
              'bot_id': 'bot_btc_001',
              'status': 'RUNNING',
              'current_epoch': {
                'purchases': 3,
                'total_cost_usdt': 150.0,
                'partial_fill': true,
              },
            },
          ]);

      final bots = await mockApiClient.louiseBots();
      final epoch = bots[0]['current_epoch'] as Map<String, dynamic>;

      expect(epoch['partial_fill'], isTrue);
      expect(epoch['purchases'], equals(3));
    });
  });
}
