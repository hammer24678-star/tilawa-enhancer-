// nur_theme.dart — "Nur" design system: palette, ThemeData, page transitions.
//
// Nur (نور, "light") is the visual language of the redesign: a deep, living
// night-teal canvas, warm gold as the single accent of importance, and motion
// that is slow and soft rather than busy. Everything resolves its colours from
// [NurPalette.of], so dark and light mode stay in step across every screen.

import 'package:flutter/material.dart';

/// Colour tokens, resolved by the ambient [Theme] brightness.
@immutable
class NurPalette {
  final bool dark;
  final Color bg;
  final Color bgDeep;
  final Color surface;
  final Color surfaceHi;
  final Color border;
  final Color text;
  final Color textSub;
  final Color textDim;
  final Color gold;
  final Color goldLight;
  final Color teal;
  final Color ok;
  final Color err;
  final Color warn;
  final Color info;

  const NurPalette({
    required this.dark,
    required this.bg,
    required this.bgDeep,
    required this.surface,
    required this.surfaceHi,
    required this.border,
    required this.text,
    required this.textSub,
    required this.textDim,
    required this.gold,
    required this.goldLight,
    required this.teal,
    required this.ok,
    required this.err,
    required this.warn,
    required this.info,
  });

  static const NurPalette night = NurPalette(
    dark: true,
    bg: Color(0xFF050E10),
    bgDeep: Color(0xFF030809),
    surface: Color(0xFF0B1A1D),
    surfaceHi: Color(0xFF122529),
    border: Color(0xFF1F3C41),
    text: Color(0xFFEAF2EE),
    textSub: Color(0xFF9DB6B6),
    textDim: Color(0xFF5E7B7C),
    gold: Color(0xFFD9B13F),
    goldLight: Color(0xFFF5DC85),
    teal: Color(0xFF2FD4B0),
    ok: Color(0xFF3DDC97),
    err: Color(0xFFFF6B6B),
    warn: Color(0xFFF0A23B),
    info: Color(0xFF5BB8FF),
  );

  static const NurPalette day = NurPalette(
    dark: false,
    bg: Color(0xFFF8F4E9),
    bgDeep: Color(0xFFEFE8D2),
    surface: Color(0xFFFFFFFF),
    surfaceHi: Color(0xFFFCF9F0),
    border: Color(0xFFE4DAB8),
    text: Color(0xFF1B1A12),
    textSub: Color(0xFF6A6247),
    textDim: Color(0xFF9A9174),
    gold: Color(0xFFA87F14),
    goldLight: Color(0xFFC99C26),
    teal: Color(0xFF0E8C75),
    ok: Color(0xFF1E9E5E),
    err: Color(0xFFD64545),
    warn: Color(0xFFC77A12),
    info: Color(0xFF2B7FC9),
  );

  static NurPalette of(BuildContext context) =>
      Theme.of(context).brightness == Brightness.dark ? night : day;

  /// Gold, light-to-deep — the primary call-to-action and headline gradient.
  LinearGradient get goldGradient => LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [goldLight, gold],
      );

  /// Teal-to-gold — the signature "recitation light" gradient.
  LinearGradient get lightGradient => LinearGradient(
        begin: Alignment.centerLeft,
        end: Alignment.centerRight,
        colors: [teal, goldLight],
      );

  /// Text colour that stays legible on top of a gold fill.
  Color get onGold => const Color(0xFF1A1300);
}

/// Soft, bouncy scrolling everywhere; no glow overscroll indicator.
class NurScrollBehavior extends MaterialScrollBehavior {
  const NurScrollBehavior();

  @override
  ScrollPhysics getScrollPhysics(BuildContext context) =>
      const BouncingScrollPhysics(parent: AlwaysScrollableScrollPhysics());

  @override
  Widget buildOverscrollIndicator(
          BuildContext context, Widget child, ScrollableDetails details) =>
      child;
}

/// The shared route transition: the incoming page fades and rises a few
/// pixels; the page underneath recedes and dims slightly.
Widget nurTransition(
    Animation<double> animation, Animation<double> secondary, Widget child) {
  final enter = animation.drive(CurveTween(curve: Curves.easeOutCubic));
  final exit = secondary.drive(CurveTween(curve: Curves.easeInOutCubic));
  return FadeTransition(
    opacity: Tween<double>(begin: 1.0, end: 0.86).animate(exit),
    child: ScaleTransition(
      scale: Tween<double>(begin: 1.0, end: 0.965).animate(exit),
      child: FadeTransition(
        opacity: enter,
        child: SlideTransition(
          position: Tween<Offset>(
            begin: const Offset(0, 0.04),
            end: Offset.zero,
          ).animate(enter),
          child: child,
        ),
      ),
    ),
  );
}

/// Applied through [ThemeData.pageTransitionsTheme] so every MaterialPageRoute
/// in the app picks the transition up without being touched.
class NurPageTransitions extends PageTransitionsBuilder {
  const NurPageTransitions();

  @override
  Widget buildTransitions<T>(
    PageRoute<T> route,
    BuildContext context,
    Animation<double> animation,
    Animation<double> secondaryAnimation,
    Widget child,
  ) =>
      nurTransition(animation, secondaryAnimation, child);
}

/// Drop-in replacement for the hand-rolled `PageRouteBuilder(... FadeTransition
/// ...)` calls scattered through the screens.
Route<T> nurRoute<T>(Widget page) => PageRouteBuilder<T>(
      pageBuilder: (_, __, ___) => page,
      transitionDuration: const Duration(milliseconds: 460),
      reverseTransitionDuration: const Duration(milliseconds: 340),
      transitionsBuilder: (_, animation, secondary, child) =>
          nurTransition(animation, secondary, child),
    );

/// Builds the app-wide [ThemeData] for either brightness.
ThemeData buildNurTheme({required bool dark}) {
  final p = dark ? NurPalette.night : NurPalette.day;
  final base = dark ? const ColorScheme.dark() : const ColorScheme.light();
  final scheme = base.copyWith(
    primary: p.gold,
    onPrimary: p.onGold,
    secondary: p.teal,
    onSecondary: p.onGold,
    surface: p.surface,
    onSurface: p.text,
    error: p.err,
    outline: p.border,
  );

  const builder = NurPageTransitions();

  return ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    fontFamily: 'Tajawal',
    scaffoldBackgroundColor: p.bg,
    cardColor: p.surface,
    dividerColor: p.border,
    canvasColor: p.surface,
    pageTransitionsTheme: const PageTransitionsTheme(builders: {
      TargetPlatform.android: builder,
      TargetPlatform.iOS: builder,
      TargetPlatform.fuchsia: builder,
      TargetPlatform.linux: builder,
      TargetPlatform.macOS: builder,
      TargetPlatform.windows: builder,
    }),
    appBarTheme: AppBarTheme(
      backgroundColor: p.bg,
      foregroundColor: p.gold,
      elevation: 0,
      scrolledUnderElevation: 0,
      surfaceTintColor: Colors.transparent,
    ),
    snackBarTheme: SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: p.surfaceHi,
      contentTextStyle: TextStyle(
        color: p.text,
        fontSize: 13,
        fontFamily: 'Tajawal',
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: BorderSide(color: p.border),
      ),
      insetPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: Colors.transparent,
      surfaceTintColor: Colors.transparent,
    ),
    sliderTheme: SliderThemeData(
      trackHeight: 4,
      activeTrackColor: p.gold,
      inactiveTrackColor: p.border,
      thumbColor: p.goldLight,
      overlayColor: p.gold.withValues(alpha: 0.16),
    ),
    progressIndicatorTheme: ProgressIndicatorThemeData(
      color: p.gold,
      linearTrackColor: p.border,
      circularTrackColor: p.border,
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith(
        (states) =>
            states.contains(WidgetState.selected) ? p.goldLight : p.textDim,
      ),
      trackColor: WidgetStateProperty.resolveWith(
        (states) => states.contains(WidgetState.selected)
            ? p.gold.withValues(alpha: 0.45)
            : p.border,
      ),
      trackOutlineColor: WidgetStateProperty.all(Colors.transparent),
    ),
    textSelectionTheme: TextSelectionThemeData(
      cursorColor: p.gold,
      selectionHandleColor: p.gold,
      selectionColor: p.gold.withValues(alpha: 0.28),
    ),
    dividerTheme: DividerThemeData(color: p.border, thickness: 1, space: 1),
  );
}
