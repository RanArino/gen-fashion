import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';

import '../closet/closet_screen.dart';
import 'login_screen.dart';

/// Gates the closet behind sign-in (M2-1). Unauthenticated visitors see only
/// the login screen; on sign-in the gate flips to the closet via the
/// `authStateChanges` stream.
class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

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
          return const LoginScreen();
        }
        return ClosetScreen(uid: user.uid);
      },
    );
  }
}
