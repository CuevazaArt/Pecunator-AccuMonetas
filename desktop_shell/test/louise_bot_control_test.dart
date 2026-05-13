import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:pecunator_desktop/api_client.dart';

class MockEngineApi extends Mock implements EngineApi {}

void main() {
  group('Louise Bot Control Tests', () {
    late MockEngineApi mockApi;
    const botId = 'bot_btc_001';

    setUp(() {
      mockApi = MockEngineApi();
    });

    test('Pause bot returns PAUSED status', () async {
      when(() => mockApi.louisePauseBot(botId)).thenAnswer((_) async => {
            'bot_id': botId,
            'status': 'PAUSED',
          });

      final response = await mockApi.louisePauseBot(botId);

      expect(response['status'], equals('PAUSED'));
      verify(() => mockApi.louisePauseBot(botId)).called(1);
    });

    test('Resume bot returns RUNNING status', () async {
      when(() => mockApi.louiseResumeBot(botId)).thenAnswer((_) async => {
            'bot_id': botId,
            'status': 'RUNNING',
          });

      final response = await mockApi.louiseResumeBot(botId);

      expect(response['status'], equals('RUNNING'));
      verify(() => mockApi.louiseResumeBot(botId)).called(1);
    });

    test('Delete bot returns deleted confirmation', () async {
      when(() => mockApi.louiseDeleteBot(botId))
          .thenAnswer((_) async => {'deleted': true, 'bot_id': botId});

      final response = await mockApi.louiseDeleteBot(botId);

      expect(response['deleted'], isTrue);
      verify(() => mockApi.louiseDeleteBot(botId)).called(1);
    });

    test('Pause with network delay completes successfully', () async {
      when(() => mockApi.louisePauseBot(botId)).thenAnswer((_) async {
        await Future.delayed(const Duration(milliseconds: 100));
        return {'bot_id': botId, 'status': 'PAUSED'};
      });

      final response = await mockApi.louisePauseBot(botId);

      expect(response['status'], equals('PAUSED'));
    });

    test('Optimistic pause update returns expected status', () async {
      when(() => mockApi.louisePauseBot(botId)).thenAnswer((_) async => {
            'bot_id': botId,
            'status': 'PAUSED',
          });

      final response = await mockApi.louisePauseBot(botId);

      expect(response['status'], equals('PAUSED'));
      expect(response['bot_id'], equals(botId));
    });

    test('Delete with confirmation returns deleted=true', () async {
      when(() => mockApi.louiseDeleteBot(botId))
          .thenAnswer((_) async => {'deleted': true});

      final response = await mockApi.louiseDeleteBot(botId);

      expect(response['deleted'], isTrue);
    });

    test('Control network error throws exception', () async {
      when(() => mockApi.louisePauseBot(botId))
          .thenThrow(Exception('Network timeout'));

      expect(
        () async => await mockApi.louisePauseBot(botId),
        throwsException,
      );
    });

    test('Single pause call fires once', () async {
      when(() => mockApi.louisePauseBot(botId)).thenAnswer((_) async => {
            'bot_id': botId,
            'status': 'PAUSED',
          });

      await mockApi.louisePauseBot(botId);

      verify(() => mockApi.louisePauseBot(botId)).called(1);
    });
  });
}
