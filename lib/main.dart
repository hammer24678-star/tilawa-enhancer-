import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'state/lang_provider.dart';
import 'screens/welcome_screen.dart';
import 'screens/home_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  FlutterError.onError = FlutterError.presentError;
  await SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);

  final prefs = await SharedPreferences.getInstance();
  final langAr = prefs.getBool('lang_ar') ?? true;
  final seenWelcome = prefs.getBool('seen_welcome') ?? false;

  runApp(TilawaApp(langAr: langAr, seenWelcome: seenWelcome));
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
  const TilawaApp({super.key, required this.langAr, required this.seenWelcome});

  @override
  State<TilawaApp> createState() => _TilawaAppState();
}

class _TilawaAppState extends State<TilawaApp> {
  late final ValueNotifier<bool> _langNotifier;

  @override
  void initState() {
    super.initState();
    // Created ONCE here — never again until the widget is destroyed.
    _langNotifier = ValueNotifier<bool>(widget.langAr);
  }

  @override
  void dispose() {
    _langNotifier.dispose(); // properly released
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return LangProvider(
      notifier: _langNotifier,
      child: ValueListenableBuilder<bool>(
        valueListenable: _langNotifier,
        builder: (context, _, __) {
          final s = S(ar: _langNotifier.value);
          return MaterialApp(
            title: s.appName,
            debugShowCheckedModeBanner: false,
            theme: ThemeData(
              colorScheme: const ColorScheme.dark(
                primary: Color(0xFFD4AF37),
                surface: Color(0xFF161B22),
              ),
              useMaterial3: true,
              scaffoldBackgroundColor: const Color(0xFF0A0C10),
              appBarTheme: const AppBarTheme(
                backgroundColor: Color(0xFF0A0C10),
                foregroundColor: Color(0xFFD4AF37),
                elevation: 0,
              ),
            ),
            home: widget.seenWelcome ? const HomeScreen() : const WelcomeScreen(),
          );
        },
      ),
    );
  }
}
