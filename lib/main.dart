import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/home_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  FlutterError.onError = (d) => FlutterError.presentError(d);
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  runApp(const TilawaApp());
}

class TilawaApp extends StatelessWidget {
  const TilawaApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'محسن التلاوة',
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
      home: const HomeScreen(),
    );
  }
}
