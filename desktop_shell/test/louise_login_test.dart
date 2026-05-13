import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:pecunator_desktop/api_client.dart';

class MockEngineApi extends Mock implements EngineApi {}

void main() {
  group('Louise Auth & Health Tests', () {
    late MockEngineApi mockApi;

    setUp(() {
      mockApi = MockEngineApi();
    });

    test('Health check returns ok status', () async {
      when(() => mockApi.louiseHealth())
          .thenAnswer((_) async => {'status': 'ok', 'ready': true});

      final result = await mockApi.louiseHealth();

      expect(result['status'], equals('ok'));
      expect(result['ready'], isTrue);
      verify(() => mockApi.louiseHealth()).called(1);
    });

    test('Unauthorized engine raises exception', () async {
      when(() => mockApi.louiseHealth())
          .thenThrow(Exception('401 Unauthorized'));

      expect(() async => await mockApi.louiseHealth(), throwsException);
    });

    test('Engine not ready returns ready=false payload', () async {
      when(() => mockApi.louiseHealth()).thenAnswer((_) async => {
            'ready': false,
            'error': 'engine_not_ready',
          });

      final result = await mockApi.louiseHealth();

      expect(result['ready'], isFalse);
      expect(result.containsKey('error'), isTrue);
    });

    test('After health check, bot list is accessible', () async {
      when(() => mockApi.louiseHealth())
          .thenAnswer((_) async => {'status': 'ok', 'ready': true});
      when(() => mockApi.louiseBots()).thenAnswer((_) async => []);

      await mockApi.louiseHealth();
      final bots = await mockApi.louiseBots();

      expect(bots, isA<List>());
      verify(() => mockApi.louiseHealth()).called(1);
      verify(() => mockApi.louiseBots()).called(1);
    });
  });
}
