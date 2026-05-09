import 'package:flutter_test/flutter_test.dart';
import 'package:pecunator_desktop/main.dart';

import 'package:shared_preferences/shared_preferences.dart';
import 'dart:ui';

void main() {
  testWidgets('renders home shell', (WidgetTester tester) async {
    tester.view.physicalSize = const Size(1920, 1080);
    tester.view.devicePixelRatio = 1.0;
    
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const PecunatorApp());
    await tester.pump(const Duration(milliseconds: 500));

    expect(find.text('PecunatorCore'), findsOneWidget);
    
    // reset
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
  });
}
