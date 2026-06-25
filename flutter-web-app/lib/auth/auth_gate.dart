import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';

import '../config.dart';
import '../home/home_screen.dart';
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

  Future<void> _startE2eAutoSignIn() async {
    if (_autoSignInStarted || !AppConfig.e2eAutoSignIn) return;
    _autoSignInStarted = true;
    await FirebaseAuth.instance.signInAnonymously();
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
          if (AppConfig.e2eAutoSignIn) {
            _startE2eAutoSignIn();
            return const Scaffold(
              body: Center(child: CircularProgressIndicator()),
            );
          }
          return const LoginScreen();
        }
        return HomeScreen(uid: user.uid);
      },
    );
  }
}
