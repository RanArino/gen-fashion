import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

import 'auth/auth_gate.dart';
import 'config.dart';
import 'l10n/app_localizations.dart';
import 'locale/locale_controller.dart';
import 'theme/app_theme.dart';

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
  runApp(GenFashionApp());
}

class GenFashionApp extends StatelessWidget {
  GenFashionApp({super.key});

  final LocaleController _localeController = LocaleController();

  @override
  Widget build(BuildContext context) {
    return LocaleScope(
      controller: _localeController,
      child: AnimatedBuilder(
        animation: _localeController,
        builder: (context, _) {
          return MaterialApp(
            title: 'gen-fashion',
            theme: AppTheme.light,
            locale: _localeController.value,
            localizationsDelegates: const [
              AppLocalizations.delegate,
              GlobalMaterialLocalizations.delegate,
              GlobalWidgetsLocalizations.delegate,
              GlobalCupertinoLocalizations.delegate,
            ],
            supportedLocales: AppLocalizations.supportedLocales,
            home: const AuthGate(),
          );
        },
      ),
    );
  }
}
