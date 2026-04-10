import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../state/lang_provider.dart';
import 'home_screen.dart';

class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});
  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl;
  late final Animation<double> _fade;
  late final Animation<Offset> _slide;
  int _page = 0;

  @override
  void initState() {
    super.initState();
    _ctrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 700));
    _fade  = CurvedAnimation(parent: _ctrl, curve: Curves.easeIn);
    _slide = Tween<Offset>(begin: const Offset(0, 0.08), end: Offset.zero)
        .animate(CurvedAnimation(parent: _ctrl, curve: Curves.easeOut));
    _ctrl.forward();
  }

  @override
  void dispose() { _ctrl.dispose(); super.dispose(); }

  void _nextPage() {
    _ctrl.reset();
    setState(() => _page = 1);
    _ctrl.forward();
  }

  Future<void> _finish() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('seen_welcome', true);
    if (!mounted) return;
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        pageBuilder: (_, __, ___) => const HomeScreen(),
        transitionsBuilder: (_, anim, __, child) =>
            FadeTransition(opacity: anim, child: child),
        transitionDuration: const Duration(milliseconds: 500),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    return Scaffold(
      backgroundColor: const Color(0xFF0A0C10),
      body: SafeArea(
        child: FadeTransition(
          opacity: _fade,
          child: SlideTransition(
            position: _slide,
            child: _page == 0 ? _page0(s) : _page1(s),
          ),
        ),
      ),
    );
  }

  Widget _page0(S s) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 32),
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        // Logo with glow
        Container(
          width: 150, height: 150,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: const Color(0xFFD4AF37).withOpacity(0.35),
                blurRadius: 50, spreadRadius: 8),
            ],
          ),
          child: ClipOval(
            child: Image.asset('assets/images/logo.png', fit: BoxFit.cover,
              errorBuilder: (_,__,___) => Container(
                color: const Color(0xFF1A1500),
                child: const Icon(Icons.music_note,
                  color: Color(0xFFD4AF37), size: 70))))),
        const SizedBox(height: 36),
        Text(s.appName,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 34, fontWeight: FontWeight.bold,
            color: Color(0xFFD4AF37), height: 1.2)),
        const SizedBox(height: 10),
        Text(s.subtitle,
          style: const TextStyle(
            color: Color(0xFF8B949E), fontSize: 12, letterSpacing: 2.5)),
        const SizedBox(height: 32),
        Text(s.welcomeDesc,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: Color(0xFFC9D1D9), fontSize: 14, height: 1.8)),
        const SizedBox(height: 44),
        _primaryBtn(s.howItWorks, _nextPage),
        const SizedBox(height: 12),
        TextButton(
          onPressed: _finish,
          child: Text(s.welcomeStart,
            style: const TextStyle(
              color: Color(0xFF8B949E), fontSize: 13))),
        const SizedBox(height: 12),
        // Language toggle on welcome
        _langToggle(context),
      ],
    ),
  );

  Widget _page1(S s) {
    final steps = [
      (Icons.audio_file_outlined, s.step1),
      (Icons.tune_rounded,        s.step2),
      (Icons.cloud_sync_outlined, s.step3),
      (Icons.download_done_rounded, s.step4),
    ];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(s.howItWorks,
            style: const TextStyle(
              color: Color(0xFFD4AF37),
              fontSize: 26, fontWeight: FontWeight.bold)),
          const SizedBox(height: 36),
          ...steps.asMap().entries.map((entry) => Padding(
            padding: const EdgeInsets.only(bottom: 22),
            child: Row(
              textDirection: TextDirection.rtl,
              children: [
                Container(
                  width: 50, height: 50,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: const Color(0xFFD4AF37), width: 1.5),
                    color: const Color(0xFF1A1500)),
                  child: Icon(entry.value.$1,
                    color: const Color(0xFFD4AF37), size: 22)),
                const SizedBox(width: 16),
                Expanded(child: Text(entry.value.$2,
                  textDirection: TextDirection.rtl,
                  style: const TextStyle(
                    color: Color(0xFFC9D1D9),
                    fontSize: 14, height: 1.4))),
              ],
            ),
          )),
          const SizedBox(height: 20),
          _primaryBtn(s.welcomeStart, _finish),
        ],
      ),
    );
  }

  Widget _primaryBtn(String label, VoidCallback onTap) =>
    SizedBox(width: double.infinity,
      child: ElevatedButton(
        onPressed: onTap,
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFFD4AF37),
          foregroundColor: const Color(0xFF0A0C10),
          padding: const EdgeInsets.symmetric(vertical: 16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14))),
        child: Text(label,
          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16))));

  Widget _langToggle(BuildContext context) {
    final langNotifier = LangProvider.of(context);
    return ValueListenableBuilder<bool>(
      valueListenable: langNotifier,
      builder: (ctx, isAr, _) => GestureDetector(
        onTap: () => LangProvider.toggle(ctx),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
          decoration: BoxDecoration(
            color: const Color(0xFF161B22),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: const Color(0xFF21262D))),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text(isAr ? 'EN' : 'ع',
              style: const TextStyle(
                color: Color(0xFFD4AF37),
                fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(width: 6),
            const Icon(Icons.language,
              color: Color(0xFF8B949E), size: 16),
          ]))));
  }
}
