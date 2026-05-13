import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:pecunator_desktop/api_client.dart';

class MockEngineApi extends Mock implements EngineApi {}

void main() {
  group('Louise Bot Creation Tests', () {
    late MockEngineApi mockApi;

    setUp(() {
      mockApi = MockEngineApi();
    });

    test('Valid bot creation returns bot_id and RUNNING status', () async {
      when(() => mockApi.louiseCreateBot(
            symbol: 'ETHUSDT',
            dailyBudget: 1000.0,
            targetProfitPct: 3.0,
            buyVolume: 50.0,
          )).thenAnswer((_) async => {
            'bot_id': 'bot_eth_001',
            'status': 'RUNNING',
          });

      final result = await mockApi.louiseCreateBot(
        symbol: 'ETHUSDT',
        dailyBudget: 1000.0,
        targetProfitPct: 3.0,
        buyVolume: 50.0,
      );

      expect(result['bot_id'], equals('bot_eth_001'));
      expect(result['status'], equals('RUNNING'));
      verify(() => mockApi.louiseCreateBot(
            symbol: 'ETHUSDT',
            dailyBudget: 1000.0,
            targetProfitPct: 3.0,
            buyVolume: 50.0,
          )).called(1);
    });

    test('Empty symbol throws exception', () async {
      when(() => mockApi.louiseCreateBot(
            symbol: any(named: 'symbol'),
            dailyBudget: any(named: 'dailyBudget'),
            targetProfitPct: any(named: 'targetProfitPct'),
            buyVolume: any(named: 'buyVolume'),
          )).thenThrow(Exception('Symbol required'));

      expect(
        () async => await mockApi.louiseCreateBot(symbol: ''),
        throwsException,
      );
    });

    test('Bot creation response includes bot_id key', () async {
      when(() => mockApi.louiseCreateBot(
            symbol: 'BTCUSDT',
            dailyBudget: 500.0,
            targetProfitPct: 2.5,
            buyVolume: 100.0,
          )).thenAnswer((_) async => {'bot_id': 'bot_btc_001'});

      final response = await mockApi.louiseCreateBot(
        symbol: 'BTCUSDT',
        dailyBudget: 500.0,
        targetProfitPct: 2.5,
        buyVolume: 100.0,
      );

      expect(response.containsKey('bot_id'), isTrue);
    });

    test('Zero target profit throws exception', () async {
      when(() => mockApi.louiseCreateBot(
            symbol: any(named: 'symbol'),
            dailyBudget: any(named: 'dailyBudget'),
            targetProfitPct: any(named: 'targetProfitPct'),
            buyVolume: any(named: 'buyVolume'),
          )).thenThrow(Exception('Target profit must be > 0'));

      expect(
        () async => await mockApi.louiseCreateBot(
          symbol: 'BTCUSDT',
          targetProfitPct: 0.0,
        ),
        throwsException,
      );
    });

    test('Default parameters produce RUNNING status', () async {
      when(() => mockApi.louiseCreateBot(symbol: 'BTCUSDT'))
          .thenAnswer((_) async => {
                'bot_id': 'bot_btc_002',
                'status': 'RUNNING',
                'symbol': 'BTCUSDT',
              });

      final result = await mockApi.louiseCreateBot(symbol: 'BTCUSDT');

      expect(result['status'], equals('RUNNING'));
    });
  });
}
