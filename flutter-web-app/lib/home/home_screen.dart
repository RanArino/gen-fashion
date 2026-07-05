import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../auth/auth_service.dart';
import '../closet/closet_screen.dart';
import '../closet/shared_closet_gallery.dart';
import '../config.dart';
import '../coordination/coordination_screen.dart';
import '../history/history_screen.dart';
import '../l10n/app_localizations.dart';
import '../locale/locale_controller.dart';
import '../shared/help_dialog.dart';
import '../theme/components.dart';

const _kSectionIdByTabIndex = [
  helpSectionCloset,
  helpSectionCoordinate,
  helpSectionHistory,
  helpSectionShared,
];

/// Fires when a coordination session completes off-tab, so `HistoryScreen`
/// can refetch without a full reload (MP-4).
class _HistoryRefreshSignal extends ChangeNotifier {
  void fire() => notifyListeners();
}

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.uid});

  final String uid;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SingleTickerProviderStateMixin {
  int _index = AppConfig.e2eAutoRun ? 1 : 0;
  late final Set<int> _visitedTabs = {_index};
  final AuthService _auth = AuthService();
  final _HistoryRefreshSignal _historyRefreshSignal = _HistoryRefreshSignal();
  bool _helpNudgeDismissed = false;

  late final AnimationController _nudgeController = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  )..repeat(reverse: true);

  late final Stream<QuerySnapshot<Map<String, dynamic>>> _closetStream =
      FirebaseFirestore.instance
          .collection('users')
          .doc(widget.uid)
          .collection('closet')
          .limit(1)
          .snapshots();

  late final Future<DocumentSnapshot<Map<String, dynamic>>> _userDocFuture =
      FirebaseFirestore.instance.collection('users').doc(widget.uid).get();

  @override
  void dispose() {
    _nudgeController.dispose();
    _historyRefreshSignal.dispose();
    super.dispose();
  }

  /// Surfaces a coordination session reaching COMPLETED/ERROR. Called by
  /// CoordinationScreen even while it isn't the visible tab, since its
  /// State is kept alive by the IndexedStack below rather than destroyed
  /// on tab switch.
  void _handleSessionTerminal(String sessionId, String status) {
    if (status == 'COMPLETED') _historyRefreshSignal.fire();
    if (!mounted || _index == 1) return; // already viewing Coordinate
    final l10n = AppLocalizations.of(context)!;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(status == 'COMPLETED'
            ? l10n.coordinateReadyNotification
            : l10n.coordinateFailedNotification),
        action: SnackBarAction(
          label: l10n.viewAction,
          onPressed: () => setState(() => _index = 1),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context)!;
    // Each tab's real widget is built only after its first visit and then
    // stays built (kept alive by the IndexedStack below), so switching tabs
    // never disposes a screen's State again once it's been opened once.
    final pages = [
      _visitedTabs.contains(0)
          ? ClosetScreen(uid: widget.uid, embedded: true)
          : const SizedBox.shrink(),
      _visitedTabs.contains(1)
          ? CoordinationScreen(
              uid: widget.uid,
              onSessionTerminal: _handleSessionTerminal,
            )
          : const SizedBox.shrink(),
      _visitedTabs.contains(2)
          ? HistoryScreen(refreshOn: _historyRefreshSignal)
          : const SizedBox.shrink(),
      _visitedTabs.contains(3)
          ? const SharedClosetGallery()
          : const SizedBox.shrink(),
    ];
    return Scaffold(
      appBar: GlassAppBar(
        title: Text(l10n.appTitle),
        actions: [
          _LanguageSwitcher(uid: widget.uid),
          _HelpIconButton(
            tooltip: l10n.appHelpTooltip,
            nudgeController: _nudgeController,
            dismissed: _helpNudgeDismissed,
            closetStream: _closetStream,
            userDocFuture: _userDocFuture,
            onPressed: () {
              setState(() => _helpNudgeDismissed = true);
              showAppHelpDialog(
                context,
                initialSection: _kSectionIdByTabIndex[_index],
              );
            },
          ),
          IconButton(
            tooltip: l10n.signOut,
            onPressed: () => _auth.signOut(),
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: IndexedStack(index: _index, children: pages),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() {
          _index = value;
          _visitedTabs.add(value);
        }),
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

/// Header help icon. Pulses (via [nudgeController]) whenever the user's
/// closet is empty or their account was created in the last 24h, so a new
/// user is guided toward the one place all page explanations live. Stops
/// pulsing for the rest of this session once [dismissed] (tapped).
class _HelpIconButton extends StatelessWidget {
  const _HelpIconButton({
    required this.tooltip,
    required this.nudgeController,
    required this.dismissed,
    required this.closetStream,
    required this.userDocFuture,
    required this.onPressed,
  });

  final String tooltip;
  final AnimationController nudgeController;
  final bool dismissed;
  final Stream<QuerySnapshot<Map<String, dynamic>>> closetStream;
  final Future<DocumentSnapshot<Map<String, dynamic>>> userDocFuture;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) {
    final icon = IconButton(
      tooltip: tooltip,
      onPressed: onPressed,
      icon: const Icon(Icons.info_outline),
    );
    if (dismissed) return icon;

    return StreamBuilder<QuerySnapshot<Map<String, dynamic>>>(
      stream: closetStream,
      builder: (context, closetSnap) {
        final closetEmpty = closetSnap.data?.docs.isEmpty ?? true;
        return FutureBuilder<DocumentSnapshot<Map<String, dynamic>>>(
          future: userDocFuture,
          builder: (context, userSnap) {
            final createdAt =
                (userSnap.data?.data()?['createdAt'] as Timestamp?)?.toDate();
            final recentSignup = createdAt != null &&
                DateTime.now().difference(createdAt) <
                    const Duration(hours: 24);
            if (!closetEmpty && !recentSignup) return icon;
            return ScaleTransition(
              scale: Tween<double>(begin: 1.0, end: 1.15).animate(
                CurvedAnimation(
                  parent: nudgeController,
                  curve: Curves.easeInOut,
                ),
              ),
              child: icon,
            );
          },
        );
      },
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
    final color = Theme.of(context).colorScheme.onSurfaceVariant;
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
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.language, size: 16, color: color),
              const SizedBox(width: 4),
              Text(
                controller.languageCode == 'en'
                    ? l10n.languageEnglish
                    : l10n.languageJapanese,
                style: Theme.of(context)
                    .textTheme
                    .labelLarge
                    ?.copyWith(color: color),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
