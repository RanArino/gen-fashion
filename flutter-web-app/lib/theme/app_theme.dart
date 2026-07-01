import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class AppColors {
  const AppColors._();

  static const scaffold = Color(0xFFECE8DF);
  static const card = Color(0xFFFBF9F4);
  static const panel = Color(0xFFF6F3EC);
  static const text = Color(0xFF1B1915);
  static const muted = Color(0xFF8B8578);
  static const tertiary = Color(0xFF514C42);
  static const accent = Color(0xFFB0563C);
  static const success = Color(0xFF6F7D5A);
  static const error = Color(0xFFA2463A);
  static const border = Color(0x1F1B1915);
}

class AppTheme {
  const AppTheme._();

  static ThemeData get light {
    final baseText = GoogleFonts.archivoTextTheme();
    final colorScheme = ColorScheme.fromSeed(
      seedColor: AppColors.accent,
      brightness: Brightness.light,
      primary: AppColors.accent,
      surface: AppColors.card,
      error: AppColors.error,
    ).copyWith(
      onPrimary: AppColors.card,
      onSurface: AppColors.text,
      surfaceContainerHighest: AppColors.panel,
      outline: AppColors.border,
    );

    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: AppColors.scaffold,
      colorScheme: colorScheme,
      textTheme: baseText.copyWith(
        displayLarge: GoogleFonts.instrumentSerif(
          fontSize: 54,
          height: 0.95,
          color: AppColors.text,
        ),
        headlineMedium: GoogleFonts.instrumentSerif(
          fontSize: 38,
          height: 1.05,
          color: AppColors.text,
        ),
        titleLarge: GoogleFonts.instrumentSerif(
          fontSize: 28,
          height: 1.05,
          color: AppColors.text,
        ),
        titleMedium: GoogleFonts.archivo(
          fontSize: 16,
          fontWeight: FontWeight.w700,
          color: AppColors.text,
        ),
        bodySmall: GoogleFonts.archivo(
          fontSize: 12,
          color: AppColors.tertiary,
        ),
        labelSmall: eyebrow,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        foregroundColor: AppColors.text,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: AppColors.card,
        elevation: 0,
        margin: EdgeInsets.zero,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(3),
          side: const BorderSide(color: AppColors.border),
        ),
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: AppColors.text,
          foregroundColor: AppColors.scaffold,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(2)),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: AppColors.accent,
          foregroundColor: AppColors.card,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(2)),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: AppColors.text,
          side: const BorderSide(color: AppColors.border),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(2)),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.panel,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(2),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(2),
          borderSide: const BorderSide(color: AppColors.border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(2),
          borderSide: const BorderSide(color: AppColors.accent),
        ),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.scaffold,
        indicatorColor: AppColors.accent.withValues(alpha: 0.14),
        labelTextStyle: WidgetStateProperty.all(eyebrow),
        iconTheme: WidgetStateProperty.resolveWith(
          (states) => IconThemeData(
            color: states.contains(WidgetState.selected)
                ? AppColors.accent
                : AppColors.tertiary,
          ),
        ),
      ),
      chipTheme: ChipThemeData(
        backgroundColor: AppColors.panel,
        side: const BorderSide(color: AppColors.border),
        labelStyle: eyebrow.copyWith(color: AppColors.tertiary),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      dividerTheme: const DividerThemeData(color: AppColors.border),
    );
  }

  static TextStyle get eyebrow => GoogleFonts.spaceMono(
        fontSize: 10,
        letterSpacing: 1.8,
        fontWeight: FontWeight.w700,
        color: AppColors.muted,
      );
}
