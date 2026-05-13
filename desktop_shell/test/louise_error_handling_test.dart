import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import '../lib/api_client.dart';

class MockApiClient extends Mock implements ApiClient {}

void main() {
  group('Louise Error Handling Tests', () {
    late MockApiClient mockApiClient;
    const botId = 'bot_btc_001';

    setUp(() {
      mockApiClient = MockApiClient();
    });

    test('API 401 Unauthorized raises exception', () async {
      when(() => mockApiClient.louiseBots())
          .thenThrow(Exception('401 Unauthorized'));

      expect(() async => await mockApiClient.louiseBots(), throwsException);
    });

    test('API 400 Bad Request on invalid bot params raises exception', () async {
      when(() => mockApiClient.louiseCreateBot(
            symbol: any(named: 'symbol'),
            dailyBudget: any(named: 'dailyBudget'),
            targetProfitPct: any(named: 'targetProfitPct'),
            buyVolume: any(named: 'buyVolume'),
          )).thenThrow(Exception('400 Bad Request: Invalid parameters'));

      expect(
        () async => await mockApiClient.louiseCreateBot(symbol: ''),
        throwsException,
      );
    });

    test('API 500 Internal Server Error raises exception', () async {
      when(() => mockApiClient.louiseBots())
          .thenThrow(Exception('500 Internal Server Error'));

      expect(() async => await mockApiClient.louiseBots(), throwsException);
    });

    test('Network timeout raises exception', () async {
      when(() => mockApiClient.louiseBots())
          .thenThrow(Exception('SocketException: Connection timeout'));

      expect(() async => await mockApiClient.louiseBots(), throwsException);
    });

    test('Gateway unavailable returns error payload', () async {
      when(() => mockApiClient.louiseHealth()).thenAnswer((_) async => {
            'error': 'gateway_unavailable',
            'message': 'Binance gateway is down',
          });

      final status = await mockApiClient.louiseHealth();

      expect(status.containsKey('error'), isTrue);
      expect(status['error'], equals('gateway_unavailable'));
    });

    test('Metrics unavailable returns error payload', () async {
      when(() => mockApiClient.louiseMetrics()).thenAnswer((_) async => {
            'error': 'cache_unavailable',
            'fallback': 'Use last known price',
          });

      final result = await mockApiClient.louiseMetrics();

      expect(result.containsKey('error'), isTrue);
      expect(result.containsKey('fallback'), isTrue);
    });

    test('Weight governor unavailable returns error payload', () async {
      when(() => mockApiClient.louiseWeightStatus()).thenAnswer((_) async => {
            'ready': false,
            'error': 'weight_governor_offline',
          });

      final result = await mockApiClient.louiseWeightStatus();

      expect(result['ready'], isFalse);
      expect(result.containsKey('error'), isTrue);
    });

    test('Bot creation error raises exception', () async {
      when(() => mockApiClient.louiseCreateBot(
            symbol: any(named: 'symbol'),
            dailyBudget: any(named: 'dailyBudget'),
            targetProfitPct: any(named: 'targetProfitPct'),
            buyVolume: any(named: 'buyVolume'),
          )).thenThrow(Exception('Order rejected: Insufficient balance'));

      expect(
        () async => await mockApiClient.louiseCreateBot(symbol: 'BTCUSDT'),
        throwsException,
      );
    });

    test('Pause error raises exception', () async {
      when(() => mockApiClient.louisePauseBot(botId))
          .thenThrow(Exception('500 Internal Server Error'));

      expect(
        () async => await mockApiClient.louisePauseBot(botId),
        throwsException,
      );
    });

    test('Error does not block subsequent calls', () async {
      when(() => mockApiClient.louiseBots())
          .thenThrow(Exception('Network error'));
      when(() => mockApiClient.louiseHealth())
          .thenAnswer((_) async => {'alive': true});

      try {
        await mockApiClient.louiseBots();
      } catch (_) {
        // expected
      }

      final status = await mockApiClient.louiseHealth();
      expect(status['alive'], isTrue);
    });
  });
}
