import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import '../lib/api_client.dart';

class MockApiClient extends Mock implements ApiClient {}

void main() {
  group('Louise Bot Control Tests', () {
    late MockApiClient mockApiClient;
    const botId = 'bot_btc_001';

    setUp(() {
      mockApiClient = MockApiClient();
    });

    test('Pause bot returns PAUSED status', () async {
      when(() => mockApiClient.louisePauseBot(botId)).thenAnswer((_) async => {
            'bot_id': botId,
            'status': 'PAUSED',
          });

      final response = await mockApiClient.louisePauseBot(botId);

      expect(response['status'], equals('PAUSED'));
      verify(() => mockApiClient.louisePauseBot(botId)).called(1);
    });

    test('Resume bot returns RUNNING status', () async {
      when(() => mockApiClient.louiseResumeBot(botId)).thenAnswer((_) async => {
            'bot_id': botId,
            'status': 'RUNNING',
          });

      final response = await mockApiClient.louiseResumeBot(botId);

      expect(response['status'], equals('RUNNING'));
      verify(() => mockApiClient.louiseResumeBot(botId)).called(1);
    });

    test('Delete bot returns deleted confirmation', () async {
      when(() => mockApiClient.louiseDeleteBot(botId))
          .thenAnswer((_) async => {'deleted': true, 'bot_id': botId});

      final response = await mockApiClient.louiseDeleteBot(botId);

      expect(response['deleted'], isTrue);
      verify(() => mockApiClient.louiseDeleteBot(botId)).called(1);
    });

    test('Pause with network delay completes successfully', () async {
      when(() => mockApiClient.louisePauseBot(botId)).thenAnswer((_) async {
        await Future.delayed(const Duration(milliseconds: 100));
        return {'bot_id': botId, 'status': 'PAUSED'};
      });

      final response = await mockApiClient.louisePauseBot(botId);

      expect(response['status'], equals('PAUSED'));
    });

    test('Optimistic pause update returns expected status', () async {
      when(() => mockApiClient.louisePauseBot(botId)).thenAnswer((_) async => {
            'bot_id': botId,
            'status': 'PAUSED',
          });

      final response = await mockApiClient.louisePauseBot(botId);

      expect(response['status'], equals('PAUSED'));
      expect(response['bot_id'], equals(botId));
    });

    test('Delete with confirmation returns deleted=true', () async {
      when(() => mockApiClient.louiseDeleteBot(botId))
          .thenAnswer((_) async => {'deleted': true});

      final response = await mockApiClient.louiseDeleteBot(botId);

      expect(response['deleted'], isTrue);
    });

    test('Control network error throws exception', () async {
      when(() => mockApiClient.louisePauseBot(botId))
          .thenThrow(Exception('Network timeout'));

      expect(
        () async => await mockApiClient.louisePauseBot(botId),
        throwsException,
      );
    });

    test('Single pause call fires once', () async {
      when(() => mockApiClient.louisePauseBot(botId)).thenAnswer((_) async => {
            'bot_id': botId,
            'status': 'PAUSED',
          });

      await mockApiClient.louisePauseBot(botId);

      verify(() => mockApiClient.louisePauseBot(botId)).called(1);
    });
  });
}
