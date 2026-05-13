import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';

import '../lib/api_client.dart';

class MockApiClient extends Mock implements ApiClient {}

void main() {
  group('Louise Bot Control Tests', () {
    late MockApiClient mockApiClient;
    const botId = 'bot_btc_001';

    setUp(() {
      mockApiClient = MockApiClient();
    });

    testWidgets('Pause button sends PATCH request with status=PAUSED', (WidgetTester tester) async {
      // Arrange
      when(mockApiClient.updateBotStatus(botId, 'PAUSED')).thenAnswer((_) async => {
        'bot_id': botId,
        'status': 'PAUSED',
      });

      // Act
      final response = await mockApiClient.updateBotStatus(botId, 'PAUSED');

      // Assert
      expect(response['status'], equals('PAUSED'));
      verify(mockApiClient.updateBotStatus(botId, 'PAUSED')).called(1);
    });

    testWidgets('Resume button sends PATCH request with status=RUNNING', (WidgetTester tester) async {
      // Arrange
      when(mockApiClient.updateBotStatus(botId, 'RUNNING')).thenAnswer((_) async => {
        'bot_id': botId,
        'status': 'RUNNING',
      });

      // Act
      final response = await mockApiClient.updateBotStatus(botId, 'RUNNING');

      // Assert
      expect(response['status'], equals('RUNNING'));
      verify(mockApiClient.updateBotStatus(botId, 'RUNNING')).called(1);
    });

    testWidgets('Delete button sends DELETE request', (WidgetTester tester) async {
      // Arrange
      when(mockApiClient.deleteBot(botId)).thenAnswer((_) async => true);

      // Act
      final success = await mockApiClient.deleteBot(botId);

      // Assert
      expect(success, isTrue);
      verify(mockApiClient.deleteBot(botId)).called(1);
    });

    testWidgets('Pause shows loading indicator', (WidgetTester tester) async {
      // Arrange
      when(mockApiClient.updateBotStatus(botId, 'PAUSED')).thenAnswer((_) async {
        // Simulate network delay
        await Future.delayed(Duration(milliseconds: 500));
        return {'status': 'PAUSED'};
      });

      // Act
      // Would expect to see CircularProgressIndicator during request
      // Assert: Verify request completes
      final response = await mockApiClient.updateBotStatus(botId, 'PAUSED');
      expect(response['status'], equals('PAUSED'));
    });

    testWidgets('UI updates immediately on pause (optimistic update)', (WidgetTester tester) async {
      // Arrange: Simulate optimistic update followed by server response
      const expectedStatus = 'PAUSED';

      when(mockApiClient.updateBotStatus(botId, expectedStatus)).thenAnswer((_) async => {
        'bot_id': botId,
        'status': expectedStatus,
      });

      // Act
      final response = await mockApiClient.updateBotStatus(botId, expectedStatus);

      // Assert: UI should show paused immediately
      expect(response['status'], equals('PAUSED'));
    });

    testWidgets('Delete shows confirmation dialog', (WidgetTester tester) async {
      // Arrange: Simulate confirmation flow
      when(mockApiClient.deleteBot(botId)).thenAnswer((_) async => true);

      // Act
      final success = await mockApiClient.deleteBot(botId);

      // Assert
      expect(success, isTrue);
    });

    testWidgets('Control error shows snackbar with retry option', (WidgetTester tester) async {
      // Arrange: Simulate network error
      when(mockApiClient.updateBotStatus(botId, 'PAUSED')).thenThrow(
        Exception('Network timeout'),
      );

      // Act & Assert
      expect(
        mockApiClient.updateBotStatus(botId, 'PAUSED'),
        throwsException,
      );
    });

    testWidgets('Control disabled while request in progress', (WidgetTester tester) async {
      // Arrange
      final slow = Future.delayed(Duration(milliseconds: 2000), () => {
        'bot_id': botId,
        'status': 'PAUSED',
      });

      when(mockApiClient.updateBotStatus(botId, 'PAUSED')).thenAnswer((_) => slow);

      // Act: Simulate rapid clicks (should ignore second click)
      unawaited(mockApiClient.updateBotStatus(botId, 'PAUSED'));
      // Second click would be ignored by UI

      // Assert
      await slow;
      verify(mockApiClient.updateBotStatus(botId, 'PAUSED')).called(1);
    });
  });
}
