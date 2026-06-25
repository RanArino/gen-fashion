import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

/// Encapsulates the Google popup sign-in and the first-login `users/{uid}`
/// bootstrap (M2-1, Decision Log: client creates the profile doc).
class AuthService {
  /// Pops the Google sign-in dialog (against the Auth Emulator's mock provider
  /// locally; the real provider in production) and ensures the `users/{uid}`
  /// document exists.
  Future<UserCredential> signInWithGoogle() async {
    final cred = await FirebaseAuth.instance
        .signInWithPopup(GoogleAuthProvider());
    final user = cred.user;
    if (user != null) {
      await _ensureUserDoc(user);
    }
    return cred;
  }

  Future<void> _ensureUserDoc(User user) async {
    final ref =
        FirebaseFirestore.instance.collection('users').doc(user.uid);
    final snap = await ref.get();
    if (!snap.exists) {
      await ref.set({
        'displayName': user.displayName ?? '',
        'createdAt': FieldValue.serverTimestamp(),
      });
    }
  }

  Future<void> signOut() => FirebaseAuth.instance.signOut();
}
