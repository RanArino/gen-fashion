import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

class LocaleController extends ValueNotifier<Locale> {
  LocaleController([Locale? locale]) : super(locale ?? const Locale('ja'));

  static const supportedLanguageCodes = {'ja', 'en'};

  String get languageCode => value.languageCode;

  Future<void> loadForUser(String uid) async {
    final ref = FirebaseFirestore.instance.collection('users').doc(uid);
    final snap = await ref.get();
    final raw = snap.data()?['language'];
    final code = raw is String ? raw : 'ja';
    final normalized = _normalize(code);
    value = Locale(normalized);
    if (raw != normalized) {
      await ref.set({'language': normalized}, SetOptions(merge: true));
    }
  }

  Future<void> setLanguageForUser(String uid, String languageCode) async {
    final normalized = _normalize(languageCode);
    if (value.languageCode != normalized) {
      value = Locale(normalized);
    }
    await FirebaseFirestore.instance.collection('users').doc(uid).set(
      {'language': normalized},
      SetOptions(merge: true),
    );
  }

  static String _normalize(String languageCode) {
    return supportedLanguageCodes.contains(languageCode) ? languageCode : 'ja';
  }
}

class LocaleScope extends InheritedNotifier<LocaleController> {
  const LocaleScope({
    super.key,
    required LocaleController controller,
    required super.child,
  }) : super(notifier: controller);

  static LocaleController of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<LocaleScope>();
    assert(scope != null, 'LocaleScope not found in context');
    return scope!.notifier!;
  }
}
