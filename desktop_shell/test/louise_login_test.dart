import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';

import '../lib/api_client.dart';
import '../lib/main.dart';

// Mock BinanceGateway and dependencies
class MockApiClient extends Mock implements ApiClient {}

void main() {
  group('Louise Login Tests', () {
    late MockApiClient mockApiClient;

    setUp(() {
      mockApiClient = MockApiClient();
    });

    testWidgets('Login reads api.token file correctly', (WidgetTester tester) async {
      // Arrange: Mock successful token read
      when(mockApiClient.readApiToken()).thenAnswer((_) async => 'test_token_abc123');

      // Act: Build the app
      await tester.pumpWidget(MyApp());
      await tester.pumpAndSettle();

      // Assert: Verify token was read
      verify(mockApiClient.readApiToken()).called(greaterThanOrEqualTo(1));
    });

    testWidgets('Login sets Bearer header with token', (WidgetTester tester) async {
      // Arrange
      const token = 'test_bearer_token';
      when(mockApiClient.readApiToken()).thenAnswer((_) async => token);
      when(mockApiClient.setBearerToken(token)).thenAnswer((_) async {});

      // Act
      await tester.pumpWidget(MyApp());
      await tester.pumpAndSettle();

      // Assert
      verify(mockApiClient.setBearerToken(token)).called(greaterThanOrEqualTo(1));
    });

    testWidgets('Missing token file shows error dialog', (WidgetTester tester) async {
      // Arrange: Mock missing token
      when(mockApiClient.readApiToken()).thenThrow(Exception('Token file not found'));

      // Act
      await tester.pumpWidget(MyApp());
      await tester.pumpAndSettle();

      // Assert: Verify error is displayed
      expect(find.byType(AlertDialog), findsWidgets);
      expect(find.text('Token file not found'), findsWidgets);
    });

    testWidgets('Login shows home page on success', (WidgetTester tester) async {
      // Arrange
      when(mockApiClient.readApiToken()).thenAnswer((_) async => 'valid_token');
      when(mockApiClient.setBearerToken('valid_token')).thenAnswer((_) async {});

      // Act
      await tester.pumpWidget(MyApp());
      await tester.pumpAndSettle();

      // Assert: Home shell should be visible
      expect(find.byType(Scaffold), findsWidgets);
    });
  });
}
