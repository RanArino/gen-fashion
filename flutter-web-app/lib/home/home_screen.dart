import 'package:flutter/material.dart';

import '../auth/auth_service.dart';
import '../closet/closet_screen.dart';
import '../closet/shared_closet_gallery.dart';
import '../config.dart';
import '../coordination/coordination_screen.dart';
import '../history/history_screen.dart';
import '../shared/attribution.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.uid});

  final String uid;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _index = AppConfig.e2eAutoRun ? 1 : 0;
  final AuthService _auth = AuthService();

  @override
  Widget build(BuildContext context) {
    final pages = [
      ClosetScreen(uid: widget.uid, embedded: true),
      CoordinationScreen(uid: widget.uid),
      const HistoryScreen(),
      const SharedClosetGallery(),
    ];
    return Scaffold(
      appBar: AppBar(
        title: const Text('gen-fashion'),
        actions: [
          IconButton(
            tooltip: '共有クローゼットについて',
            onPressed: () => showSharedClosetAboutDialog(context),
            icon: const Icon(Icons.info_outline),
          ),
          IconButton(
            tooltip: 'Sign out',
            onPressed: () => _auth.signOut(),
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: pages[_index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() => _index = value),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.checkroom_outlined),
            selectedIcon: Icon(Icons.checkroom),
            label: 'Closet',
          ),
          NavigationDestination(
            icon: Icon(Icons.auto_awesome_outlined),
            selectedIcon: Icon(Icons.auto_awesome),
            label: 'Coordinate',
          ),
          NavigationDestination(
            icon: Icon(Icons.history_outlined),
            selectedIcon: Icon(Icons.history),
            label: 'History',
          ),
          NavigationDestination(
            icon: Icon(Icons.groups_outlined),
            selectedIcon: Icon(Icons.groups),
            label: 'Shared',
          ),
        ],
      ),
    );
  }
}
