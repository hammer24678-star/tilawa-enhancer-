import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'screens/welcome_screen.dart';
import 'screens/home_screen.dart';
import 'l10n/strings.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  FlutterError.onError = FlutterError.presentError;
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);

  final prefs = await SharedPreferences.getInstance();
  final seenWelcome = prefs.getBool('seen_welcome') ?? false;
  final langAr = prefs.getBool('lang_ar') ?? true;

  runApp(TilawaApp(seenWelcome: seenWelcome, langAr: langAr));
}

class TilawaApp extends StatefulWidget {
  final bool seenWelcome;
  final bool langAr;
  const TilawaApp({super.key, required this.seenWelcome, required this.langAr});

  static _TilawaAppState? of(BuildContext context) =>
      context.findAncestorStateOfType<_TilawaAppState>();

  @override
  State<TilawaApp> createState() => _TilawaAppState();
}

class _TilawaAppState extends State<TilawaApp> {
  late bool _langAr;

  @override
  void initState() {
    super.initState();
    _langAr = widget.langAr;
  }

  void toggleLanguage() async {
    setState(() => _langAr = !_langAr);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('lang_ar', _langAr);
  }

  S get s => S(_langAr);
  bool get isArabic => _langAr;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'محسِّن التلاوة',
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
      home: widget.seenWelcome
          ? HomeScreen(s: s, onLangToggle: () {
              TilawaApp.of(context)?.toggleLanguage();
            })
          : WelcomeScreen(s: s),
    );
  }
}
