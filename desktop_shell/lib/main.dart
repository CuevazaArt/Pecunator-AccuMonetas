import 'package:flutter/material.dart';

import 'pages/dorothy_hub_page.dart';

void main() {
  // ── Error boundary: prevent widget crashes from killing the entire app ──
  // Critical for production: if a widget build() throws, the bots in the
  // backend keep running. Without this, an uncaught widget error kills
  // the Flutter process and all bots lose their coordinated state.
  FlutterError.onError = (FlutterErrorDetails details) {
    FlutterError.presentError(details);
    // Log but do NOT crash — bots must keep running
    debugPrint('FlutterError caught: ${details.exceptionAsString()}');
  };

  ErrorWidget.builder = (FlutterErrorDetails details) {
    return Material(
      color: Colors.transparent,
      child: Container(
        padding: const EdgeInsets.all(16),
        margin: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: Colors.red.withAlpha(25),
          border: Border.all(color: Colors.redAccent.withAlpha(100)),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.warning_amber_rounded, color: Colors.redAccent, size: 32),
            const SizedBox(height: 8),
            const Text(
              'Error de renderizado',
              style: TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 4),
            Text(
              details.exceptionAsString(),
              style: const TextStyle(color: Colors.grey, fontSize: 11),
              maxLines: 3,
              overflow: TextOverflow.ellipsis,
            ),
            const SizedBox(height: 4),
            const Text(
              'Los bots siguen operando normalmente.',
              style: TextStyle(color: Colors.orangeAccent, fontSize: 10),
            ),
          ],
        ),
      ),
    );
  };

  runApp(const PecunatorDesktopApp());
}

class PecunatorDesktopApp extends StatefulWidget {
  const PecunatorDesktopApp({super.key});

  @override
  State<PecunatorDesktopApp> createState() => _PecunatorDesktopAppState();
}

class _PecunatorDesktopAppState extends State<PecunatorDesktopApp> {
  bool _darkMode = true;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Pecunator Desktop',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.blueGrey),
      ),
      darkTheme: ThemeData.dark(useMaterial3: true),
      themeMode: _darkMode ? ThemeMode.dark : ThemeMode.light,
      home: BotControlPage(
        darkMode: _darkMode,
        onThemeChanged: (v) => setState(() => _darkMode = v),
      ),
    );
  }
}