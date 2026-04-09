import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../l10n/strings.dart';
import '../main.dart';
import 'home_screen.dart';

class WelcomeScreen extends StatefulWidget {
  final S s;
  const WelcomeScreen({super.key, required this.s});
  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen>
    with SingleTickerProviderStateMixin {
  late AnimationController _ctrl;
  late Animation<double> _fadeIn;
  late Animation<double> _slideUp;
  int _page = 0;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 900));
    _fadeIn  = CurvedAnimation(parent: _ctrl, curve: Curves.easeIn);
    _slideUp = Tween<double>(begin: 40, end: 0).animate(
        CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
    _ctrl.forward();
  }

  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }

  S get s => widget.s;

  Future<void> _finish() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('seen_welcome', true);
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        pageBuilder: (_, __, ___) => HomeScreen(
          s: s,
          onLangToggle: () => TilawaApp.of(context)?.toggleLanguage(),
        ),
        transitionsBuilder: (_, anim, __, child) =>
            FadeTransition(opacity: anim, child: child),
        transitionDuration: const Duration(milliseconds: 400),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0C10),
      body: SafeArea(
        child: AnimatedBuilder(
          animation: _ctrl,
          builder: (_, __) => Opacity(
            opacity: _fadeIn.value,
            child: Transform.translate(
              offset: Offset(0, _slideUp.value),
              child: _page == 0 ? _buildPage0() : _buildPage1(),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildPage0() => Padding(
    padding: const EdgeInsets.all(32),
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // Logo
        Container(
          width: 140, height: 140,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [BoxShadow(
              color: const Color(0xFFD4AF37).withOpacity(0.3),
              blurRadius: 40, spreadRadius: 5)],
          ),
          child: ClipOval(child: Image.asset(
            'assets/images/logo.png',
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => Container(
              color: const Color(0xFF1A1500),
              child: const Icon(Icons.music_note,
                color: Color(0xFFD4AF37), size: 60)),
          )),
        ),
        const SizedBox(height: 40),
        Text(s.appName,
          textDirection: TextDirection.rtl,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 36, fontWeight: FontWeight.bold,
            color: Color(0xFFD4AF37))),
        const SizedBox(height: 12),
        Text(s.subtitle,
          style: const TextStyle(
            color: Color(0xFF8B949E), fontSize: 13, letterSpacing: 2)),
        const SizedBox(height: 32),
        Text(s.welcomeDesc,
          textDirection: TextDirection.rtl,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: Color(0xFFC9D1D9), fontSize: 15, height: 1.7)),
        const SizedBox(height: 48),
        SizedBox(width: double.infinity,
          child: ElevatedButton(
            onPressed: () {
              _ctrl.reset();
              setState(() => _page = 1);
              _ctrl.forward();
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFD4AF37),
              foregroundColor: const Color(0xFF0A0C10),
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14))),
            child: Text(s.welcomeHowTitle,
              style: const TextStyle(
                  fontWeight: FontWeight.bold, fontSize: 16)))),
        const SizedBox(height: 12),
        TextButton(
          onPressed: _finish,
          child: Text(s.welcomeStart,
            style: const TextStyle(
                color: Color(0xFF8B949E), fontSize: 14))),
      ],
    ),
  );

  Widget _buildPage1() {
    final steps = [
      (Icons.audio_file_outlined, s.step1),
      (Icons.tune,                s.step2),
      (Icons.hourglass_top,       s.step3),
      (Icons.download_done,       s.step4),
    ];
    return Padding(
      padding: const EdgeInsets.all(32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(s.welcomeHowTitle,
            style: const TextStyle(
              color: Color(0xFFD4AF37),
              fontSize: 28, fontWeight: FontWeight.bold)),
          const SizedBox(height: 40),
          ...steps.asMap().entries.map((e) => Padding(
            padding: const EdgeInsets.only(bottom: 24),
            child: Row(
              textDirection: TextDirection.rtl,
              children: [
                Container(
                  width: 48, height: 48,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: const Color(0xFFD4AF37), width: 1.5),
                    color: const Color(0xFF1A1500)),
                  child: Icon(e.value.$1, color: const Color(0xFFD4AF37), size: 22)),
                const SizedBox(width: 16),
                Expanded(child: Text(e.value.$2,
                  textDirection: TextDirection.rtl,
                  style: const TextStyle(
                    color: Color(0xFFC9D1D9), fontSize: 15))),
              ],
            ),
          )),
          const SizedBox(height: 24),
          SizedBox(width: double.infinity,
            child: ElevatedButton(
              onPressed: _finish,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFD4AF37),
                foregroundColor: const Color(0xFF0A0C10),
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(14))),
              child: Text(s.welcomeStart,
                style: const TextStyle(
                    fontWeight: FontWeight.bold, fontSize: 16)))),
        ],
      ),
    );
  }
}
