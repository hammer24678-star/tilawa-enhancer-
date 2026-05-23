import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'state/lang_provider.dart';
import 'screens/welcome_screen.dart';
import 'screens/home_screen.dart';

// ── S31-F2: App-wide color helpers ─────────────────────────────────────────
// Call these anywhere you have a BuildContext instead of hardcoding colours.
// Dark palette  : #080A0E bg / #161B22 card / #21262D border
// Light palette : #FAF7EE bg / #F3EED9 card / #D4C99A border
bool   _isDark(BuildContext ctx) => ThemeProvider.isDark(ctx);
Color  _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF020D0C) : const Color(0xFFFAF7EE); // S40-MAIN-CBG
Color  _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);
Color  _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);
Color  _cText(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFC9D1D9) : const Color(0xFF1A1400);
Color  _cSub(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);
Color  _cDim(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF484F58) : const Color(0xFF8B7B5A);
Color  _cGold(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  FlutterError.onError = FlutterError.presentError;
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);

  final prefs = await SharedPreferences.getInstance();
  final langAr      = prefs.getBool('lang_ar')      ?? true;
  final seenWelcome = prefs.getBool('seen_welcome_v2') ?? false; // S32
  final isDark      = prefs.getBool('is_dark')       ?? true; // S31-F4

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
    background: Color(0xFF020D0C),
  ),
  useMaterial3: true,
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
    background: Color(0xFFFAF7EE),
  ),
  useMaterial3: true,
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
          builder: (context, _lang, __) {
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
