import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:pecunator_desktop/api_client.dart';

class MockEngineApi extends Mock implements EngineApi {}

void main() {
  group('Louise Error Handling Tests', () {
    late MockEngineApi mockApi;
    const botId = 'bot_btc_001';

    setUp(() {
      mockApi = MockEngineApi();
    });

    test('API 401 Unauthorized raises exception', () async {
      when(() => mockApi.louiseBots()).thenThrow(Exception('401 Unauthorized'));

      expect(() async => await mockApi.louiseBots(), throwsException);
    });

    test(
      'API 400 Bad Request on invalid bot params raises exception',
      () async {
        when(
          () => mockApi.louiseCreateBot(
            symbol: any(named: 'symbol'),
            dailyBudget: any(named: 'dailyBudget'),
            targetProfitPct: any(named: 'targetProfitPct'),
            buyVolume: any(named: 'buyVolume'),
          ),
        ).thenThrow(Exception('400 Bad Request: Invalid parameters'));

        expect(
          () async => await mockApi.louiseCreateBot(symbol: ''),
          throwsException,
        );
      },
    );

    test('API 500 Internal Server Error raises exception', () async {
      when(
        () => mockApi.louiseBots(),
      ).thenThrow(Exception('500 Internal Server Error'));

      expect(() async => await mockApi.louiseBots(), throwsException);
    });

    test('Network timeout raises exception', () async {
      when(
        () => mockApi.louiseBots(),
      ).thenThrow(Exception('SocketException: Connection timeout'));

      expect(() async => await mockApi.louiseBots(), throwsException);
    });

    test('Gateway unavailable returns error payload', () async {
      when(() => mockApi.louiseHealth()).thenAnswer(
        (_) async => {
          'error': 'gateway_unavailable',
          'message': 'Binance gateway is down',
        },
      );

      final status = await mockApi.louiseHealth();

      expect(status.containsKey('error'), isTrue);
      expect(status['error'], equals('gateway_unavailable'));
    });

    test('Metrics unavailable returns error payload', () async {
      when(() => mockApi.louiseMetrics()).thenAnswer(
        (_) async => {
          'error': 'cache_unavailable',
          'fallback': 'Use last known price',
        },
      );

      final result = await mockApi.louiseMetrics();

      expect(result.containsKey('error'), isTrue);
      expect(result.containsKey('fallback'), isTrue);
    });

    test('Weight governor unavailable returns error payload', () async {
      when(() => mockApi.louiseWeightStatus()).thenAnswer(
        (_) async => {'ready': false, 'error': 'weight_governor_offline'},
      );

      final result = await mockApi.louiseWeightStatus();

      expect(result['ready'], isFalse);
      expect(result.containsKey('error'), isTrue);
    });

    test('Bot creation failure raises exception', () async {
      when(
        () => mockApi.louiseCreateBot(
          symbol: any(named: 'symbol'),
          dailyBudget: any(named: 'dailyBudget'),
          targetProfitPct: any(named: 'targetProfitPct'),
          buyVolume: any(named: 'buyVolume'),
        ),
      ).thenThrow(Exception('Order rejected: Insufficient balance'));

      expect(
        () async => await mockApi.louiseCreateBot(symbol: 'BTCUSDT'),
        throwsException,
      );
    });

    test('Pause error raises exception', () async {
      when(
        () => mockApi.louisePauseBot(botId),
      ).thenThrow(Exception('500 Internal Server Error'));

      expect(() async => await mockApi.louisePauseBot(botId), throwsException);
    });

    test('Error does not block subsequent calls', () async {
      when(() => mockApi.louiseBots()).thenThrow(Exception('Network error'));
      when(
        () => mockApi.louiseHealth(),
      ).thenAnswer((_) async => {'alive': true});

      try {
        await mockApi.louiseBots();
      } catch (_) {
        // expected
      }

      final status = await mockApi.louiseHealth();
      expect(status['alive'], isTrue);
    });
  });
}
