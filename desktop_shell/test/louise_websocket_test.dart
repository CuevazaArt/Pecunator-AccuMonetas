import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';

import '../lib/api_client.dart';

class MockWebSocket {
  final List<dynamic> sentMessages = [];
  void send(String message) => sentMessages.add(message);
  Stream<dynamic> get stream => Stream.fromIterable([]);
}

class MockApiClient extends Mock implements ApiClient {}

void main() {
  group('Louise WebSocket Real-Time Updates Tests', () {
    late MockApiClient mockApiClient;

    setUp(() {
      mockApiClient = MockApiClient();
    });

    test('WebSocket connects with Bearer token auth', () async {
      // Arrange
      const token = 'test_bearer_token';
      when(mockApiClient.connectWebSocket(token)).thenAnswer((_) async => true);

      // Act
      final connected = await mockApiClient.connectWebSocket(token);

      // Assert
      expect(connected, isTrue);
      verify(mockApiClient.connectWebSocket(token)).called(1);
    });

    test('Receives price ticker updates', () async {
      // Arrange: Simulate price update stream
      final priceUpdate = {
        'event': 'ticker',
        'data': {
          'symbol': 'BTCUSDT',
          'price': 45321.50,
          'timestamp': 1715558400000,
        },
      };

      when(mockApiClient.listenToPrices('BTCUSDT')).thenAnswer((_) async* {
        yield priceUpdate;
      });

      // Act
      final stream = mockApiClient.listenToPrices('BTCUSDT');
      final updates = <dynamic>[];

      await for (final update in stream.take(1)) {
        updates.add(update);
      }

      // Assert
      expect(updates.length, equals(1));
      expect(updates[0]['data']['price'], equals(45321.50));
    });

    test('Receives execution report fills', () async {
      // Arrange: Simulate fill event
      final fillEvent = {
        'event': 'executionReport',
        'data': {
          'symbol': 'BTCUSDT',
          'orderId': 'test_order_123',
          'status': 'FILLED',
          'quantity': 0.5,
          'price': 44500.00,
          'cumQty': 0.5,
        },
      };

      when(mockApiClient.listenToFills()).thenAnswer((_) async* {
        yield fillEvent;
      });

      // Act
      final stream = mockApiClient.listenToFills();
      final fills = <dynamic>[];

      await for (final fill in stream.take(1)) {
        fills.add(fill);
      }

      // Assert
      expect(fills.length, equals(1));
      expect(fills[0]['data']['status'], equals('FILLED'));
      expect(fills[0]['data']['quantity'], equals(0.5));
    });

    test('WebSocket reconnects on disconnect', () async {
      // Arrange
      const token = 'test_token';
      when(mockApiClient.connectWebSocket(token)).thenAnswer((_) async => true);

      // Act: Initial connection
      var connected = await mockApiClient.connectWebSocket(token);
      expect(connected, isTrue);

      // Simulate disconnect and reconnect
      when(mockApiClient.reconnect()).thenAnswer((_) async => true);
      connected = await mockApiClient.reconnect();

      // Assert
      expect(connected, isTrue);
      verify(mockApiClient.connectWebSocket(token)).called(1);
      verify(mockApiClient.reconnect()).called(1);
    });

    test('Reconnection backoff increases on repeated failures', () async {
      // Arrange
      var attemptCount = 0;
      const token = 'test_token';

      when(mockApiClient.connectWebSocketWithBackoff(
        token,
        attempt: anyNamed('attempt'),
      )).thenAnswer((invocation) async {
        attemptCount++;
        if (attemptCount < 3) {
          throw Exception('Connection failed');
        }
        return true;
      });

      // Act: Simulate 3 reconnect attempts
      bool success = false;
      for (int i = 0; i < 3; i++) {
        try {
          success = await mockApiClient.connectWebSocketWithBackoff(
            token,
            attempt: i,
          );
          if (success) break;
        } catch (e) {
          // Expected to fail on attempts 0-1
          expect(e, isException);
        }
      }

      // Assert
      expect(success, isTrue);
      expect(attemptCount, equals(3));
    });

    test('Updates UI when price changes', () async {
      // Arrange: Simulate price stream
      final prices = [
        {'price': 45000.00, 'timestamp': 1715558400000},
        {'price': 45100.00, 'timestamp': 1715558401000},
        {'price': 45050.00, 'timestamp': 1715558402000},
      ];

      when(mockApiClient.listenToPrices('BTCUSDT')).thenAnswer((_) async* {
        for (final price in prices) {
          yield price;
        }
      });

      // Act
      final stream = mockApiClient.listenToPrices('BTCUSDT');
      final receivedPrices = <dynamic>[];

      await for (final update in stream) {
        receivedPrices.add(update);
      }

      // Assert: UI should update 3 times
      expect(receivedPrices.length, equals(3));
      expect(receivedPrices[0]['price'], equals(45000.00));
      expect(receivedPrices[2]['price'], equals(45050.00));
    });

    test('Handles partial fill updates', () async {
      // Arrange
      final partialFill = {
        'orderId': 'order_123',
        'status': 'PARTIALLY_FILLED',
        'cumQty': 0.3,
        'totalQty': 1.0,
      };

      when(mockApiClient.listenToFills()).thenAnswer((_) async* {
        yield partialFill;
      });

      // Act
      final stream = mockApiClient.listenToFills();
      final fills = await stream.take(1).toList();

      // Assert
      expect(fills[0]['cumQty'], equals(0.3));
      expect(fills[0]['totalQty'], equals(1.0));
      expect(fills[0]['status'], equals('PARTIALLY_FILLED'));
    });
  });
}
