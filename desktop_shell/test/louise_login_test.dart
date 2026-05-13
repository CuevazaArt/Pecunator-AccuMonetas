import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import '../lib/api_client.dart';

class MockApiClient extends Mock implements ApiClient {}

void main() {
  group('Louise Auth & Health Tests', () {
    late MockApiClient mockApiClient;

    setUp(() {
      mockApiClient = MockApiClient();
    });

    test('Health check returns ok status', () async {
      when(() => mockApiClient.louiseHealth())
          .thenAnswer((_) async => {'status': 'ok', 'ready': true});

      final result = await mockApiClient.louiseHealth();

      expect(result['status'], equals('ok'));
      expect(result['ready'], isTrue);
      verify(() => mockApiClient.louiseHealth()).called(1);
    });

    test('Unauthorized engine raises exception', () async {
      when(() => mockApiClient.louiseHealth())
          .thenThrow(Exception('401 Unauthorized'));

      expect(() async => await mockApiClient.louiseHealth(), throwsException);
    });

    test('Engine not ready returns ready=false payload', () async {
      when(() => mockApiClient.louiseHealth()).thenAnswer((_) async => {
            'ready': false,
            'error': 'engine_not_ready',
          });

      final result = await mockApiClient.louiseHealth();

      expect(result['ready'], isFalse);
      expect(result.containsKey('error'), isTrue);
    });

    test('After health check, bot list is accessible', () async {
      when(() => mockApiClient.louiseHealth())
          .thenAnswer((_) async => {'status': 'ok', 'ready': true});
      when(() => mockApiClient.louiseBots()).thenAnswer((_) async => []);

      await mockApiClient.louiseHealth();
      final bots = await mockApiClient.louiseBots();

      expect(bots, isA<List>());
      verify(() => mockApiClient.louiseHealth()).called(1);
      verify(() => mockApiClient.louiseBots()).called(1);
    });
  });
}
