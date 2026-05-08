import 'package:flutter_test/flutter_test.dart';
import 'package:pecunator_desktop/main.dart';

void main() {
  testWidgets('renders home shell', (WidgetTester tester) async {
    await tester.pumpWidget(const PecunatorApp());
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('PecunatorCore'), findsOneWidget);
  });
}
