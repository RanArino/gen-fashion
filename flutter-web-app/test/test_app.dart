import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:gen_fashion_web/l10n/app_localizations.dart';
import 'package:gen_fashion_web/locale/locale_controller.dart';

Widget localizedTestApp(Widget child, {Locale? locale}) {
  final controller = LocaleController(locale);
  return LocaleScope(
    controller: controller,
    child: MaterialApp(
      locale: locale,
      localizationsDelegates: const [
        AppLocalizations.delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
      ],
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: child),
    ),
  );
}
