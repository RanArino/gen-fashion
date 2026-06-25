import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';

import 'auth/auth_gate.dart';
import 'config.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp(
    options: AppConfig.firebaseOptions,
  );
  if (AppConfig.useEmulators) {
    await FirebaseAuth.instance.useAuthEmulator(
      AppConfig.authEmulatorHost,
      AppConfig.authEmulatorPort,
    );
    FirebaseFirestore.instance.useFirestoreEmulator(
      AppConfig.firestoreEmulatorHost,
      AppConfig.firestoreEmulatorPort,
    );
  }
  runApp(const GenFashionApp());
}

class GenFashionApp extends StatelessWidget {
  const GenFashionApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'gen-fashion',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.indigo),
        useMaterial3: true,
      ),
      home: const AuthGate(),
    );
  }
}
