import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'state/lang_provider.dart';
import 'screens/welcome_screen.dart';
import 'screens/home_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  FlutterError.onError = FlutterError.presentError;
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);

  final prefs = await SharedPreferences.getInstance();
  final langAr = prefs.getBool('lang_ar') ?? true;
  final seenWelcome = prefs.getBool('seen_welcome') ?? false;

  runApp(TilawaApp(langAr: langAr, seenWelcome: seenWelcome));
}

class TilawaApp extends StatelessWidget {
  final bool langAr;
  final bool seenWelcome;
  const TilawaApp({super.key, required this.langAr, required this.seenWelcome});

  @override
  Widget build(BuildContext context) {
    final langNotifier = ValueNotifier<bool>(langAr);

    return LangProvider(
      notifier: langNotifier,
      child: ValueListenableBuilder<bool>(
        valueListenable: langNotifier,
        builder: (context, _, __) => MaterialApp(
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
          home: seenWelcome ? const HomeScreen() : const WelcomeScreen(),
        ),
      ),
    );
  }
}
