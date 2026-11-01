import 'package:flutter/material.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Tilawa Enhancer — central design tokens and ThemeData.
//
// Before this file every screen carried its own hard-coded palette, and the
// palettes disagreed: Home used GitHub-style blue-greys (#080A0E / #161B22)
// while the rest of the app used teal-black (#020D0C), and the audio editor
// used a navy-black (#020D17). This file is the single source of truth.
//
// The brand is unchanged — gold #D4AF37 and teal #1DB898 on deep green-black —
// but the neutrals are now all tinted toward the same teal hue, text is warmer
// and higher-contrast, and Material components (buttons, dialogs, sheets,
// snackbars, switches, sliders) share one shape language.
// ─────────────────────────────────────────────────────────────────────────────

/// Brand and neutral colours. Screens still keep their private aliases
/// (`_gold`, `_bg`, …); their values now match these tokens.
class AppColors {
  AppColors._();

  // Brand
  static const gold      = Color(0xFFD4AF37);
  static const goldLight = Color(0xFFF0CF60);
  static const goldMuted = Color(0xFF3A2B08);
  static const teal      = Color(0xFF1DB898);

  // Dark neutrals (all tinted toward the brand teal)
  static const bg      = Color(0xFF03100E); // scaffold
  static const surface = Color(0xFF0A1C1A); // sheets, panels
  static const card    = Color(0xFF0F2623); // cards
  static const border  = Color(0xFF1D3F39);

  // Dark text
  static const text    = Color(0xFFF0E6C8); // primary — warm cream
  static const textSub = Color(0xFF9DB8B3); // secondary
  static const textDim = Color(0xFF5C7873); // hints, disabled

  // Status
  static const ok   = Color(0xFF2ABF6E);
  static const err  = Color(0xFFE0524A);
  static const info = Color(0xFF5BB0E0);
}

/// Corner radii used by every component theme below.
class AppRadius {
  AppRadius._();
  static const double sm = 10;
  static const double md = 14;
  static const double lg = 20;
  static const double xl = 28;
}

class _Palette {
  final Brightness brightness;
  final Color bg, surface, card, border, text, textSub, textDim, accent, onAccent;
  const _Palette({
    required this.brightness,
    required this.bg,
    required this.surface,
    required this.card,
    required this.border,
    required this.text,
    required this.textSub,
    required this.textDim,
    required this.accent,
    required this.onAccent,
  });

  static const dark = _Palette(
    brightness: Brightness.dark,
    bg:       AppColors.bg,
    surface:  AppColors.surface,
    card:     AppColors.card,
    border:   AppColors.border,
    text:     AppColors.text,
    textSub:  AppColors.textSub,
    textDim:  AppColors.textDim,
    accent:   AppColors.gold,
    onAccent: AppColors.bg,
  );

  static const light = _Palette(
    brightness: Brightness.light,
    bg:       Color(0xFFFAF7EE), // warm parchment
    surface:  Color(0xFFF6F1E0),
    card:     Color(0xFFF3EED9),
    border:   Color(0xFFD4C99A),
    text:     Color(0xFF1A1400),
    textSub:  Color(0xFF5E5338), // darker than before for contrast
    textDim:  Color(0xFF786A49),
    accent:   Color(0xFFB8941F), // deeper gold for light backgrounds
    onAccent: Color(0xFFFFFDF5),
  );
}

class AppTheme {
  AppTheme._();

  static ThemeData dark()  => _build(_Palette.dark);
  static ThemeData light() => _build(_Palette.light);

  static ThemeData _build(_Palette p) {
    final isDark = p.brightness == Brightness.dark;

    final scheme = ColorScheme(
      brightness: p.brightness,
      primary: p.accent,
      onPrimary: p.onAccent,
      secondary: AppColors.teal,
      onSecondary: isDark ? AppColors.bg : Colors.white,
      error: AppColors.err,
      onError: Colors.white,
      surface: p.card,
      onSurface: p.text,
      outline: p.border,
      outlineVariant: p.border,
      surfaceTint: Colors.transparent,
    );

    final base = ThemeData(
      useMaterial3: true,
      brightness: p.brightness,
      fontFamily: 'Tajawal', // bundled, works offline
      colorScheme: scheme,
      scaffoldBackgroundColor: p.bg,
      cardColor: p.card,
    );

    // Arabic needs a little more line height than Latin to keep diacritics
    // from colliding with the line above.
    final text = base.textTheme
        .apply(bodyColor: p.text, displayColor: p.text)
        .copyWith(
          titleLarge:  TextStyle(fontSize: 20, fontWeight: FontWeight.w800, height: 1.35, color: p.text),
          titleMedium: TextStyle(fontSize: 16, fontWeight: FontWeight.w700, height: 1.4,  color: p.text),
          titleSmall:  TextStyle(fontSize: 14, fontWeight: FontWeight.w700, height: 1.4,  color: p.text),
          bodyLarge:   TextStyle(fontSize: 16, fontWeight: FontWeight.w400, height: 1.55, color: p.text),
          bodyMedium:  TextStyle(fontSize: 14, fontWeight: FontWeight.w400, height: 1.55, color: p.text),
          bodySmall:   TextStyle(fontSize: 12, fontWeight: FontWeight.w400, height: 1.5,  color: p.textSub),
          labelLarge:  TextStyle(fontSize: 14, fontWeight: FontWeight.w700, height: 1.3,  color: p.text),
        )
        // The slots above replace the stock styles wholesale, so re-apply the
        // bundled typeface or they would fall back to the platform font.
        .apply(fontFamily: 'Tajawal');

    final shapeMd = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(AppRadius.md),
    );

    return base.copyWith(
      textTheme: text,
      splashColor: p.accent.withValues(alpha: 0.10),
      highlightColor: p.accent.withValues(alpha: 0.05),
      dividerColor: p.border,

      appBarTheme: AppBarTheme(
        backgroundColor: p.bg,
        foregroundColor: p.accent,
        elevation: 0,
        scrolledUnderElevation: 0,
        surfaceTintColor: Colors.transparent,
        centerTitle: true,
        titleTextStyle: TextStyle(
          fontFamily: 'Tajawal',
          fontSize: 18,
          fontWeight: FontWeight.w800,
          color: p.accent,
        ),
      ),

      cardTheme: CardThemeData(
        color: p.card,
        elevation: 0,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.lg),
          side: BorderSide(color: p.border),
        ),
      ),

      dialogTheme: DialogThemeData(
        backgroundColor: p.surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.xl),
          side: BorderSide(color: p.border),
        ),
        titleTextStyle: TextStyle(
          fontFamily: 'Tajawal',
          fontSize: 18,
          fontWeight: FontWeight.w800,
          color: p.text,
        ),
      ),

      bottomSheetTheme: BottomSheetThemeData(
        backgroundColor: p.surface,
        modalBackgroundColor: p.surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        dragHandleColor: p.border,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(AppRadius.xl)),
        ),
      ),

      snackBarTheme: SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
        backgroundColor: isDark ? p.card : p.text,
        contentTextStyle: TextStyle(
          fontFamily: 'Tajawal',
          fontSize: 14,
          fontWeight: FontWeight.w500,
          color: isDark ? p.text : p.bg,
        ),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
          side: isDark ? BorderSide(color: p.border) : BorderSide.none,
        ),
      ),

      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: p.accent,
          foregroundColor: p.onAccent,
          elevation: 0,
          shape: shapeMd,
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
          textStyle: const TextStyle(fontFamily: 'Tajawal', fontSize: 15, fontWeight: FontWeight.w800),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(
          backgroundColor: p.accent,
          foregroundColor: p.onAccent,
          shape: shapeMd,
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
          textStyle: const TextStyle(fontFamily: 'Tajawal', fontSize: 15, fontWeight: FontWeight.w800),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: p.accent,
          side: BorderSide(color: p.accent.withValues(alpha: 0.55)),
          shape: shapeMd,
          padding: const EdgeInsets.symmetric(horizontal: 22, vertical: 14),
          textStyle: const TextStyle(fontFamily: 'Tajawal', fontSize: 15, fontWeight: FontWeight.w700),
        ),
      ),
      textButtonTheme: TextButtonThemeData(
        style: TextButton.styleFrom(
          foregroundColor: p.accent,
          shape: shapeMd,
          textStyle: const TextStyle(fontFamily: 'Tajawal', fontSize: 14, fontWeight: FontWeight.w700),
        ),
      ),

      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith((s) =>
            s.contains(WidgetState.selected) ? p.accent : p.textDim),
        trackColor: WidgetStateProperty.resolveWith((s) =>
            s.contains(WidgetState.selected)
                ? p.accent.withValues(alpha: 0.35)
                : p.border),
        trackOutlineColor: WidgetStateProperty.all(Colors.transparent),
      ),

      sliderTheme: SliderThemeData(
        trackHeight: 3,
        activeTrackColor: p.accent,
        inactiveTrackColor: p.border,
        thumbColor: isDark ? AppColors.goldLight : p.accent,
        overlayColor: p.accent.withValues(alpha: 0.12),
      ),

      progressIndicatorTheme: ProgressIndicatorThemeData(
        color: p.accent,
        linearTrackColor: p.border,
      ),

      dividerTheme: DividerThemeData(color: p.border, thickness: 1),

      textSelectionTheme: TextSelectionThemeData(
        cursorColor: p.accent,
        selectionColor: p.accent.withValues(alpha: 0.30),
        selectionHandleColor: p.accent,
      ),
    );
  }
}
