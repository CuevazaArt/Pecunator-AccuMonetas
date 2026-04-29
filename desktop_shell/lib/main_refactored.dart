import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'config/app_config.dart';
import 'providers/app_providers.dart';
import 'screens/home_screen.dart';
import 'services/preferences.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await AppPreferences.init();
  runApp(const ProviderScope(child: PecunatorDesktopApp()));
}

class PecunatorDesktopApp extends ConsumerWidget {
  const PecunatorDesktopApp({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final darkMode = ref.watch(darkModeProvider);

    return MaterialApp(
      title: 'PecunatorCore',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueGrey),
        useMaterial3: true,
      ),
      darkTheme: ThemeData.dark(useMaterial3: true),
      themeMode: darkMode ? ThemeMode.dark : ThemeMode.light,
      home: HomeScreen(
        onThemeChanged: (value) {
          ref.read(darkModeProvider.notifier).state = value;
          AppPreferences.setDarkMode(value);
        },
      ),
    );
  }
}
