import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';

import '../config.dart';
import '../home/home_screen.dart';
import '../locale/locale_controller.dart';
import 'auth_service.dart';
import 'login_screen.dart';

/// Gates the closet behind sign-in (M2-1). Unauthenticated visitors see only
/// the login screen; on sign-in the gate flips to the closet via the
/// `authStateChanges` stream.
class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  bool _autoSignInStarted = false;
  String? _loadedLocaleUid;
  final _auth = AuthService();

  Future<void> _startE2eAutoSignIn() async {
    if (_autoSignInStarted || !AppConfig.e2eAutoSignIn) return;
    _autoSignInStarted = true;
    await _auth.signInWithGoogle(
      onLanguage: (language) =>
          LocaleScope.of(context).value = Locale(language),
    );
  }

  void _loadLocale(User user) {
    if (_loadedLocaleUid == user.uid) return;
    _loadedLocaleUid = user.uid;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      LocaleScope.of(context).loadForUser(user.uid);
    });
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.authStateChanges(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator()),
          );
        }
        final user = snapshot.data;
        if (user == null) {
          _loadedLocaleUid = null;
          if (AppConfig.e2eAutoSignIn) {
            _startE2eAutoSignIn();
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          return const LoginScreen();
        }
        _loadLocale(user);
        return HomeScreen(uid: user.uid);
      },
    );
  }
}
