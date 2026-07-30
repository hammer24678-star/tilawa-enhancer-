import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'state/lang_provider.dart';
import 'services/local_engine_service.dart';
import 'screens/welcome_screen.dart';
import 'screens/home_screen.dart';

// S250: the seven per-colour helpers that used to live here were never called
// from main.dart — every screen defines its own copies — so they were dead
// code the analyzer flagged on every run. Removed; ThemeProvider.isDark() is
// the shared entry point those screens actually use.

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  FlutterError.onError = FlutterError.presentError;
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);

  final prefs = await SharedPreferences.getInstance();
  final langAr      = prefs.getBool('lang_ar')      ?? true;
  final seenWelcome = prefs.getBool('seen_welcome_v5') ?? false; // S32
  final isDark      = prefs.getBool('is_dark')       ?? true; // S31-F4

  // S256: start unpacking the offline engine now, before the first frame.
  //
  // Everything it needs already ships inside the APK — Python, numpy, scipy,
  // the fourteen audio packages, ffmpeg, DeepFilter, the engine scripts and the
  // reference recordings. Nothing is downloaded. proot simply cannot execute a
  // Python that lives inside an archive, so the bundle is unpacked to the
  // filesystem exactly once, and that unpack is the only thing between a fresh
  // install and a working offline engine.
  //
  // Kicking it off here rather than when the home screen mounts means it runs
  // underneath the welcome tour on a fresh install — time that was dead anyway.
  // Deliberately not awaited: the UI must come up immediately, and every screen
  // that cares can attach to the same broadcast stream.
  unawaited(LocalEngineService.ensurePrepared().drain<void>().catchError((_) {
    // Reported in the UI by whoever is listening; nothing to do here.
  }));

  runApp(TilawaApp(
    langAr: langAr, seenWelcome: seenWelcome, isDark: isDark));
}

// ── S31-F4: Theme helpers & ThemeProvider ─────────────────────────────────────
ThemeData _buildDarkTheme() => ThemeData(
  colorScheme: const ColorScheme.dark(
    primary:    Color(0xFFD4AF37),
    surface:    Color(0xFF0F2420), // S40-MAIN
    onSurface:  Color(0xFFE2CFA0),
    secondary:  Color(0xFF1DB898),
  ),
  useMaterial3: true,
  fontFamily: 'Tajawal',  // S241: custom typeface (bundled, offline)
  scaffoldBackgroundColor: const Color(0xFF020D0C),
  appBarTheme: const AppBarTheme(
    backgroundColor: Color(0xFF020D0C),
    foregroundColor: Color(0xFFD4AF37),
    elevation: 0,
  ),
);

ThemeData _buildLightTheme() => ThemeData(
  colorScheme: const ColorScheme.light(
    primary: Color(0xFFB8941F),   // deeper gold for light bg
    surface: Color(0xFFF3EED9),   // warm parchment
    onSurface: Color(0xFF1A1400),
  ),
  useMaterial3: true,
  fontFamily: 'Tajawal',  // S241: custom typeface (bundled, offline)
  scaffoldBackgroundColor: const Color(0xFFFAF7EE),
  cardColor: const Color(0xFFF3EED9),
  appBarTheme: const AppBarTheme(
    backgroundColor: Color(0xFFFAF7EE),
    foregroundColor: Color(0xFFB8941F),
    elevation: 0,
  ),
);

// InheritedWidget so any screen can read and toggle the theme
class ThemeProvider extends InheritedNotifier<ValueNotifier<bool>> {
  const ThemeProvider({
    super.key,
    required ValueNotifier<bool> notifier,
    required super.child,
  }) : super(notifier: notifier);

  static ValueNotifier<bool> of(BuildContext ctx) =>
      ctx.dependOnInheritedWidgetOfExactType<ThemeProvider>()!.notifier!;

  static bool isDark(BuildContext ctx) => of(ctx).value;

  static Future<void> toggle(BuildContext ctx) async {
    final n = of(ctx);
    n.value = !n.value;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('is_dark', n.value);
  }
}

// ── FIX F1: TilawaApp must be StatefulWidget ────────────────────────────────
// Bug: was StatelessWidget, creating ValueNotifier inside build().
// build() can be called multiple times — each call created a NEW notifier,
// resetting the language silently. The notifier was also never disposed.
// Fix: move notifier into State (initState → dispose lifecycle).
// ────────────────────────────────────────────────────────────────────────────
class TilawaApp extends StatefulWidget {
  final bool langAr;
  final bool seenWelcome;
  final bool isDark;
  const TilawaApp({super.key,
    required this.langAr,
    required this.seenWelcome,
    required this.isDark, // S31-F4
  });

  @override
  State<TilawaApp> createState() => _TilawaAppState();
}

class _TilawaAppState extends State<TilawaApp> {
  late final ValueNotifier<bool> _langNotifier;
  late final ValueNotifier<bool> _themeNotifier; // S31-F4: true = dark

  @override
  void initState() {
    super.initState();
    _langNotifier  = ValueNotifier<bool>(widget.langAr);
    _themeNotifier = ValueNotifier<bool>(widget.isDark);
  }

  @override
  void dispose() {
    _langNotifier.dispose();
    _themeNotifier.dispose(); // S31-F4
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ThemeProvider( // S31-F4
      notifier: _themeNotifier,
      child: LangProvider(
        notifier: _langNotifier,
        child: ValueListenableBuilder<bool>(
          valueListenable: _langNotifier,
          builder: (context, lang, __) {
            return ValueListenableBuilder<bool>(
              valueListenable: _themeNotifier,
              builder: (context, isDark, __) {
                final s = S(ar: _langNotifier.value);
                return MaterialApp(
                  title: s.appName,
                  debugShowCheckedModeBanner: false,
                  themeMode: isDark ? ThemeMode.dark : ThemeMode.light,
                  darkTheme: _buildDarkTheme(),
                  theme: _buildLightTheme(),
                  home: widget.seenWelcome
                      ? const HomeScreen()
                      : const WelcomeScreen(),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
