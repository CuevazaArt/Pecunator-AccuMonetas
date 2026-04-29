/// Main application screen with tabbed navigation.

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'bots_screen.dart';
import 'spot_account_screen.dart';

class HomeScreen extends ConsumerStatefulWidget {
  final ValueChanged<bool> onThemeChanged;

  const HomeScreen({
    super.key,
    required this.onThemeChanged,
  });

  @override
  ConsumerState<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends ConsumerState<HomeScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('PecunatorCore · Dorothy Hub'),
        bottom: TabBar(
          controller: _tabController,
          tabs: const [
            Tab(icon: Icon(Icons.smart_toy), text: 'Bots'),
            Tab(icon: Icon(Icons.account_balance_wallet), text: 'Cuenta Spot'),
          ],
        ),
        actions: [
          IconButton(
            onPressed: () => widget.onThemeChanged(
              Theme.of(context).brightness == Brightness.dark ? false : true,
            ),
            tooltip: 'Cambiar tema',
            icon: Icon(
              Theme.of(context).brightness == Brightness.dark
                  ? Icons.light_mode
                  : Icons.dark_mode,
              size: 18,
            ),
          ),
        ],
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          BotsScreen(
            onThemeChanged: widget.onThemeChanged,
          ),
          const SpotAccountScreen(),
        ],
      ),
    );
  }
}
