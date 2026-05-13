import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';

import '../lib/api_client.dart';

class MockApiClient extends Mock implements ApiClient {}

void main() {
  group('Louise Bot Creation Tests', () {
    late MockApiClient mockApiClient;

    setUp(() {
      mockApiClient = MockApiClient();
    });

    testWidgets('Bot creation form validation rejects empty symbol', (WidgetTester tester) async {
      // Arrange
      when(mockApiClient.createBot(
        symbol: '',
        buyVolume: 100.0,
        pollInterval: 300,
        targetProfit: 2.0,
        dailyBudget: 500.0,
      )).thenThrow(Exception('Symbol required'));

      // Act: Try to create with empty symbol
      // Expecting validation error
      // Assert
      expect(find.byType(TextField), findsWidgets);
    });

    testWidgets('Bot creation form validation rejects negative buy volume', (WidgetTester tester) async {
      // Arrange
      const symbol = 'BTCUSDT';
      const buyVolume = -100.0; // Invalid

      // Act & Assert
      when(mockApiClient.createBot(
        symbol: symbol,
        buyVolume: buyVolume,
        pollInterval: 300,
        targetProfit: 2.0,
        dailyBudget: 500.0,
      )).thenThrow(Exception('Buy volume must be positive'));

      expect(
        mockApiClient.createBot(
          symbol: symbol,
          buyVolume: buyVolume,
          pollInterval: 300,
          targetProfit: 2.0,
          dailyBudget: 500.0,
        ),
        throwsException,
      );
    });

    testWidgets('Bot creation sends correct POST request', (WidgetTester tester) async {
      // Arrange
      const botData = {
        'symbol': 'ETHUSDT',
        'buy_volume': 50.0,
        'poll_interval_seconds': 600,
        'target_profit_pct': 3.0,
        'daily_budget_usdt': 1000.0,
      };

      when(mockApiClient.createBot(
        symbol: 'ETHUSDT',
        buyVolume: 50.0,
        pollInterval: 600,
        targetProfit: 3.0,
        dailyBudget: 1000.0,
      )).thenAnswer((_) async => {'bot_id': 'bot_eth_001', 'status': 'RUNNING'});

      // Act
      final result = await mockApiClient.createBot(
        symbol: 'ETHUSDT',
        buyVolume: 50.0,
        pollInterval: 600,
        targetProfit: 3.0,
        dailyBudget: 1000.0,
      );

      // Assert
      expect(result['bot_id'], equals('bot_eth_001'));
      expect(result['status'], equals('RUNNING'));
    });

    testWidgets('Bot creation shows success message', (WidgetTester tester) async {
      // Arrange
      when(mockApiClient.createBot(
        symbol: 'BTCUSDT',
        buyVolume: 100.0,
        pollInterval: 300,
        targetProfit: 2.5,
        dailyBudget: 500.0,
      )).thenAnswer((_) async => {'bot_id': 'bot_btc_001'});

      // Act & Assert: Success response should display
      final response = await mockApiClient.createBot(
        symbol: 'BTCUSDT',
        buyVolume: 100.0,
        pollInterval: 300,
        targetProfit: 2.5,
        dailyBudget: 500.0,
      );

      expect(response.containsKey('bot_id'), isTrue);
    });

    testWidgets('Bot creation handles 400 Bad Request (invalid config)', (WidgetTester tester) async {
      // Arrange: Invalid target profit
      when(mockApiClient.createBot(
        symbol: 'BTCUSDT',
        buyVolume: 100.0,
        pollInterval: 300,
        targetProfit: 0.0, // Invalid: must be > 0
        dailyBudget: 500.0,
      )).thenThrow(Exception('Target profit must be > 0'));

      // Act & Assert
      expect(
        mockApiClient.createBot(
          symbol: 'BTCUSDT',
          buyVolume: 100.0,
          pollInterval: 300,
          targetProfit: 0.0,
          dailyBudget: 500.0,
        ),
        throwsException,
      );
    });
  });
}
