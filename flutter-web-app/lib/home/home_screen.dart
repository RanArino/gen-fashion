import 'package:flutter/material.dart';

import '../auth/auth_service.dart';
import '../closet/closet_screen.dart';
import '../closet/shared_closet_gallery.dart';
import '../config.dart';
import '../coordination/coordination_screen.dart';
import '../history/history_screen.dart';
import '../l10n/app_localizations.dart';
import '../locale/locale_controller.dart';
import '../shared/attribution.dart';
import '../theme/components.dart';

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
    final l10n = AppLocalizations.of(context)!;
    final pages = [
      ClosetScreen(uid: widget.uid, embedded: true),
      CoordinationScreen(uid: widget.uid),
      const HistoryScreen(),
      const SharedClosetGallery(),
    ];
    return Scaffold(
      appBar: GlassAppBar(
        title: Text(l10n.appTitle),
        actions: [
          _LanguageSwitcher(uid: widget.uid),
          IconButton(
            tooltip: l10n.sharedClosetAbout,
            onPressed: () => showSharedClosetAboutDialog(context),
            icon: const Icon(Icons.info_outline),
          ),
          IconButton(
            tooltip: l10n.signOut,
            onPressed: () => _auth.signOut(),
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: pages[_index],
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() => _index = value),
        destinations: [
          NavigationDestination(
            icon: const Icon(Icons.checkroom_outlined),
            selectedIcon: const Icon(Icons.checkroom),
            label: l10n.navCloset,
          ),
          NavigationDestination(
            icon: const Icon(Icons.auto_awesome_outlined),
            selectedIcon: const Icon(Icons.auto_awesome),
            label: l10n.navCoordinate,
          ),
          NavigationDestination(
            icon: const Icon(Icons.history_outlined),
            selectedIcon: const Icon(Icons.history),
            label: l10n.navHistory,
          ),
          NavigationDestination(
            icon: const Icon(Icons.groups_outlined),
            selectedIcon: const Icon(Icons.groups),
            label: l10n.navShared,
          ),
        ],
      ),
    );
  }
}

class _LanguageSwitcher extends StatelessWidget {
  const _LanguageSwitcher({required this.uid});

  final String uid;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    final controller = LocaleScope.of(context);
    return Padding(
      padding: const EdgeInsets.only(right: 4),
      child: PopupMenuButton<String>(
        tooltip: l10n.language,
        initialValue: controller.languageCode,
        onSelected: (value) => controller.setLanguageForUser(uid, value),
        itemBuilder: (context) => [
          PopupMenuItem(value: 'ja', child: Text(l10n.languageJapanese)),
          PopupMenuItem(value: 'en', child: Text(l10n.languageEnglish)),
        ],
        child: Chip(
          avatar: const Icon(Icons.language, size: 16),
          label: Text(
            controller.languageCode == 'en'
                ? l10n.languageEnglish
                : l10n.languageJapanese,
          ),
        ),
      ),
    );
  }
}
