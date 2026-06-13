import 'dart:math';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../main.dart' show ThemeProvider; // S31-F2c
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../state/lang_provider.dart';
import 'home_screen.dart';

class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({super.key});
  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen>
    with TickerProviderStateMixin {
  late final AnimationController _fadeCtrl;
  late final AnimationController _pulseCtrl;
  late final AnimationController _geoRotCtrl;
  late final Animation<double> _fade;
  late final Animation<Offset> _slide;
  late final Animation<double> _pulse;
  int _page = 0;

  @override
  void initState() {
    super.initState();
    _fadeCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 600));
    _pulseCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2200))
      ..repeat(reverse: true);
    _geoRotCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 90))
      ..repeat();

    _fade  = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeIn);
    _slide = Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
        .animate(CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOutCubic));
    _pulse = Tween<double>(begin: 0.85, end: 1.15)
        .animate(CurvedAnimation(parent: _pulseCtrl, curve: Curves.easeInOut));

    _fadeCtrl.forward();
  }

  @override
  void dispose() {
    _fadeCtrl.dispose();
    _pulseCtrl.dispose();
    _geoRotCtrl.dispose();
    super.dispose();
  }

  void _goPage(int p) {
    HapticFeedback.selectionClick();
    _fadeCtrl.reset();
    setState(() => _page = p);
    _fadeCtrl.forward();
  }

  Future<void> _finish() async {
    HapticFeedback.lightImpact();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('seen_welcome_v5', true); // S108
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

  // ── S31-F2c / S32: theme color helpers ────────────────────────────────────
  bool  _isDark(BuildContext ctx)  => ThemeProvider.isDark(ctx);
  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF020D0C) : const Color(0xFFFAF7EE); // S46-WEL
  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF0F2420) : const Color(0xFFF3EED9);
  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF1A4035) : const Color(0xFFD4C99A);
  Color _cSub(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF8AAABB) : const Color(0xFF6B5E40);

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    return Scaffold(
      backgroundColor: const Color(0xFF020D0C), // S45-WEL
      body: Stack(children: [
        // Rotating geo background
        Positioned.fill(child: AnimatedBuilder(
          animation: _pulseCtrl,
          builder: (_, __) => Transform.rotate(
            angle: _pulseCtrl.value * 6.2832,
            child: CustomPaint(painter: _GeoPainter())))),
        // Star particles
        Positioned.fill(child: AnimatedBuilder(
          animation: _pulseCtrl,
          builder: (_, __) => CustomPaint(
            painter: _WelcomeStarsPainter(_pulseCtrl.value)))),
        SafeArea(
          child: FadeTransition(
            opacity: _fade,
            child: SlideTransition(
              position: _slide,
              child: _page == 0 ? _page0(s) : _page == 1 ? _page1(s) : _page2(s),
            ),
          ),
        ),
      ]),
    );
  }

  // ── Page 0: Brand splash ──────────────────────────────────────────────────
  Widget _page0(S s) => SingleChildScrollView(
    child: Padding(
    padding: const EdgeInsets.symmetric(horizontal: 32),
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
            // S44: static 130-px duplicate removed (animated 180-px logo stays)

        // Pulsing gold ring around logo
        AnimatedBuilder(
          animation: _pulse,
          builder: (_, child) => Container(
            width: 180, height: 180,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              boxShadow: [
                BoxShadow(
                  color: const Color(0xFFD4AF37)
                      .withValues(alpha: 0.28 * _pulse.value),
                  blurRadius: 50 * _pulse.value,
                  spreadRadius: 10 * _pulse.value),
              ],
            ),
            child: child),
          child: Container(
            width: 180, height: 180,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: const Color(0xFFD4AF37).withValues(alpha: 0.4),
                width: 1.5)),
            child: ClipOval(
              child: Image.asset('assets/images/logo.png', fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => Container(
                  color: const Color(0xFF1A1500),
                  child: const Icon(Icons.music_note,
                    color: Color(0xFFD4AF37), size: 70))))),
        ),
        const SizedBox(height: 40),
        ShaderMask(
          shaderCallback: (b) => const LinearGradient(
            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60), Color(0xFFD4AF37)],
            stops: [0.0, 0.5, 1.0]).createShader(b),
          child: Text(s.appName,
            textAlign: TextAlign.center,
            style: const TextStyle(
              fontSize: 42, fontWeight: FontWeight.w900,
              color: Colors.white, height: 1.15,
              letterSpacing: -0.5))),
        const SizedBox(height: 8),
        Text(s.subtitle,
          style: const TextStyle(
            color: Color(0xFF8AAABB), fontSize: 11,
            letterSpacing: 3.0)),
        const SizedBox(height: 36),
        Text(s.welcomeDesc,
          textAlign: TextAlign.center,
          style: const TextStyle(
            color: Color(0xFFF2EFE5), fontSize: 14, height: 1.9)),
        const SizedBox(height: 48),

        const SizedBox(height: 28),
        // S84: Mode info card
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 4),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.black.withOpacity(0.28),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: const Color(0xFF1DB898).withOpacity(0.30))),
          child: Column(children: [
            // Local mode
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFF1DB898).withOpacity(0.15),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFF1DB898).withOpacity(0.5))),
                child: const Text('🏠 LOCAL',
                  style: TextStyle(color: Color(0xFF1DB898),
                    fontSize: 10, fontWeight: FontWeight.bold))),
              const SizedBox(width: 12),
              const Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('الصفاء · الإتقان · الاسترداد',
                  style: TextStyle(color: Color(0xFFD4AF37),
                    fontSize: 13, fontWeight: FontWeight.bold)),
                SizedBox(height: 3),
                Text('يعمل على جهازك — بدون إنترنت — خصوصية تامة\nيتطلب إعداداً لمرة واحدة (~200MB)',
                  style: TextStyle(color: Color(0xFF8AACBA), fontSize: 10, height: 1.6)),
              ])),
            ]),
            const SizedBox(height: 14),
            Divider(color: Colors.white10, height: 1),
            const SizedBox(height: 14),
            // Server mode
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.06),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.white24)),
                child: const Text('☁ SERVER',
                  style: TextStyle(color: Color(0xFF8AACBA),
                    fontSize: 10, fontWeight: FontWeight.bold))),
              const SizedBox(width: 12),
              const Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('v10.0 · v9.0 · v8.5 · v8.0',
                  style: TextStyle(color: Color(0xFF8AACBA),
                    fontSize: 12, fontWeight: FontWeight.w600)),
                SizedBox(height: 3),
                Text('يعمل على السحابة — يحتاج إنترنت — بدون تخزين',
                  style: TextStyle(color: Color(0xFF3D5A65), fontSize: 10, height: 1.6)),
              ])),
            ]),
          ])),
        _primaryBtn(s.howItWorks, () => _goPage(1)),
        const SizedBox(height: 14),
        TextButton(
          onPressed: _finish,
          child: Text(s.welcomeStart,
            style: const TextStyle(
              color: Color(0xFF8AAABB), fontSize: 13))),
        const SizedBox(height: 14),
        _langToggle(context),
        const SizedBox(height: 8),
        // Page dots
        _dots(0),
      ],
    ),
  ));


  // ── Page 1: How it works ──────────────────────────────────────────────────
  Widget _page1(S s) {
    final steps = [
      (Icons.audio_file_outlined,    s.step1),
      (Icons.tune_rounded,           s.step2),
      (Icons.cloud_sync_outlined,    s.step3),
      (Icons.download_done_rounded,  s.step4),
    ];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 28),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(s.howItWorks,
            style: const TextStyle(
              color: Color(0xFFD4AF37),
              fontSize: 26, fontWeight: FontWeight.bold)),
          const SizedBox(height: 32),
          ...steps.asMap().entries.map((entry) => Padding(
            padding: const EdgeInsets.only(bottom: 18),
            child: Row(
              textDirection: TextDirection.rtl,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 44, height: 44,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: const Color(0xFFD4AF37), width: 1.3),
                    color: const Color(0xFF1A1500)),
                  child: Icon(entry.value.$1,
                    color: const Color(0xFFD4AF37), size: 20)),
                const SizedBox(width: 14),
                Expanded(child: Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      s.ar
                        ? 'الخطوة ${entry.key + 1}'
                        : 'Step ${entry.key + 1}',
                      textDirection: TextDirection.rtl,
                      style: const TextStyle(
                        color: Color(0xFF484F58),
                        fontSize: 9, letterSpacing: 0.5)),
                    const SizedBox(height: 2),
                    Text(entry.value.$2,
                      textDirection: TextDirection.rtl,
                      style: const TextStyle(
                        color: Color(0xFFF2EFE5),
                        fontSize: 13, height: 1.45)),
                  ],
                )),
              ],
            ),
          )),
          const SizedBox(height: 12),
          _primaryBtn(s.ar ? 'التالي' : 'Next', () => _goPage(2)),
          const SizedBox(height: 10),
          _dots(1),
        ],
      ),
    );
  }

  // ── Page 2: Engine tiers overview ────────────────────────────────────────
  Widget _page2(S s) {
    final tiers = [
      ('v10.0', s.ar ? 'الأثيريون — الأساس' : 'Aetherion Foundation',
        s.ar ? '٢٤ إصلاحاً — NR ثنائي — L-BFGS-B'
              : '24 fixes — Two-stage NR — L-BFGS-B EQ',
        const Color(0xFFD4AF37)),
      ('v9.0',  s.ar ? 'التطور' : 'The Evolution',
        s.ar ? 'بناء كامل — مُحسِّن مشترك LUFS+LRA'
              : 'Full rewrite — joint LUFS+LRA optimizer',
        const Color(0xFFD4AF37)),
      ('v8.x',  s.ar ? 'سلسلة الدقة' : 'Precision Series',
        s.ar ? 'v8.7 · v8.5 · v8.0 — تقدم تراكمي'
              : 'v8.7 · v8.5 · v8.0 — cumulative gains',
        const Color(0xFFC9A227)),
      ('v7.0',  s.ar ? 'كلاسيكي' : 'Classic',
        s.ar ? 'البنية المُثبَّتة الأساس — STABLE'
              : 'Proven foundational architecture — STABLE',
        const Color(0xFF8AAABB)),
    ];
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(s.ar ? 'محركات التحسين' : 'Enhancement Engines',
            style: const TextStyle(
              color: Color(0xFFD4AF37),
              fontSize: 24, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text(s.ar
            ? 'اختر محركك من الصفحة الرئيسية'
            : 'Choose your engine from the home screen',
            style: TextStyle(color: _cSub(context), fontSize: 12)),
          const SizedBox(height: 24),
          ...tiers.map((t) => Container(
            margin: const EdgeInsets.only(bottom: 10),
            padding: const EdgeInsets.symmetric(
              horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: _cCard(context),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: t.$4.withValues(alpha: 0.25))),
            child: Row(children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 7, vertical: 3),
                decoration: BoxDecoration(
                  color: t.$4.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(5)),
                child: Text(t.$1, style: TextStyle(
                  color: t.$4, fontSize: 10,
                  fontWeight: FontWeight.bold))),
              const SizedBox(width: 12),
              Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(t.$2, style: TextStyle(
                    color: t.$4, fontSize: 12,
                    fontWeight: FontWeight.w600)),
                  Text(t.$3, style: const TextStyle(
                    color: Color(0xFF8AAABB), fontSize: 10,
                    height: 1.4)),
                ])),
            ]))),
          const SizedBox(height: 16),
          _primaryBtn(s.welcomeStart, _finish),
          const SizedBox(height: 10),
          _dots(2),
        ],
      ),
    );
  }

  Widget _dots(int active) => Row(
    mainAxisAlignment: MainAxisAlignment.center,
    children: List.generate(3, (i) => AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      margin: const EdgeInsets.symmetric(horizontal: 4),
      width:  i == active ? 20 : 6,
      height: 6,
      decoration: BoxDecoration(
        color: i == active
          ? const Color(0xFFD4AF37)
          : const Color(0xFF30363D),
        borderRadius: BorderRadius.circular(3)))));

  Widget _primaryBtn(String label, VoidCallback onTap) =>
    SizedBox(width: double.infinity,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          gradient: const LinearGradient(
            colors: [Color(0xFF8A6C10), Color(0xFFD4AF37),
                     Color(0xFFF5E090), Color(0xFFD4AF37)],
            stops: [0.0, 0.3, 0.6, 1.0]),
          boxShadow: [BoxShadow(
            color: const Color(0xFFD4AF37).withValues(alpha: 0.35),
            blurRadius: 20, offset: const Offset(0, 6))]),
        child: Material(color: Colors.transparent,
          child: InkWell(onTap: onTap,
            borderRadius: BorderRadius.circular(16),
            splashColor: Colors.white.withValues(alpha: 0.15),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 17),
              child: Text(label, textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xFF020D17),
                  fontWeight: FontWeight.w900, fontSize: 17,
                  letterSpacing: 0.3)))))));

  Widget _langToggle(BuildContext context) {
    final langNotifier = LangProvider.of(context);
    return ValueListenableBuilder<bool>(
      valueListenable: langNotifier,
      builder: (ctx, isAr, _) => GestureDetector(
        onTap: () => LangProvider.toggle(ctx),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
          decoration: BoxDecoration(
            color: const Color(0xFF0F2420), // S46-WEL-LANG
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: const Color(0xFF1A4035))),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text(isAr ? 'EN' : 'ع',
              style: const TextStyle(
                color: Color(0xFFD4AF37),
                fontWeight: FontWeight.bold, fontSize: 14)),
            const SizedBox(width: 6),
            const Icon(Icons.language,
              color: Color(0xFF8AAABB), size: 16),
          ]))));
  }
}
// ── S33: Islamic geometric background painter ────────────────────────────────
class _GeoPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2, cy = size.height / 2;
    const r = 120.0;
    final ringPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.7;

    // Outer glow ring
    ringPaint.color = const Color(0xFFD4AF37).withValues(alpha: 0.06);
    canvas.drawCircle(Offset(cx, cy), r + 28, ringPaint);

    // Inner teal ring
    ringPaint.color = const Color(0xFF1DB898).withValues(alpha: 0.07); // S45-WEL-T
    canvas.drawCircle(Offset(cx, cy), r * 0.52, ringPaint);

    // 8-point Islamic star polygon
    final starPaint = Paint()
      ..color = const Color(0xFF1DB898).withValues(alpha: 0.08) // S45-WEL-T2
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8;
    final path = Path();
    for (int i = 0; i < 8; i++) {
      final a = (i / 8) * math.pi * 2 - math.pi / 2;
      final b = ((i + 0.5) / 8) * math.pi * 2 - math.pi / 2;
      final px = cx + r * math.cos(a);
      final py = cy + r * math.sin(a);
      final qx = cx + (r * 0.40) * math.cos(b);
      final qy = cy + (r * 0.40) * math.sin(b);
      if (i == 0) {
        path.moveTo(px, py);
      } else {
        path.lineTo(px, py);
      }
      path.lineTo(qx, qy);
    }
    path.close();
    canvas.drawPath(path, starPaint);

    // Radial spokes
    final spokePaint = Paint()
      ..color = const Color(0xFFD4AF37).withValues(alpha: 0.04)
      ..strokeWidth = 0.5;
    for (int i = 0; i < 16; i++) {
      final a = (i / 16) * math.pi * 2;
      canvas.drawLine(
        Offset(cx + (r * 0.55) * math.cos(a), cy + (r * 0.55) * math.sin(a)),
        Offset(cx + (r + 20) * math.cos(a),   cy + (r + 20) * math.sin(a)),
        spokePaint);
    }
  }

  @override
  bool shouldRepaint(_GeoPainter o) => false;
}
// ── S33: Pulsing stars background painter ────────────────────────────────────
class _WelcomeStarsPainter extends CustomPainter {
  final double pulse;
  _WelcomeStarsPainter(this.pulse);

  static final _rng = math.Random(42);
  static final List<Offset> _pts = List.generate(
    32, (_) => Offset(_rng.nextDouble(), _rng.nextDouble()));

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..style = PaintingStyle.fill;
    for (int i = 0; i < _pts.length; i++) {
      final phase = (i / _pts.length) * math.pi * 2;
      final alpha =
          ((math.sin(pulse * math.pi * 2 + phase) + 1) / 2) * 0.60 + 0.08;
      final radius = 1.0 + (i % 4) * 0.45;
      paint.color = (i % 5 == 0
              ? const Color(0xFFD4AF37)
              : const Color(0xFF1DB898)) // S46-WEL-T3
          .withValues(alpha: alpha);
      canvas.drawCircle(
        Offset(_pts[i].dx * size.width, _pts[i].dy * size.height),
        radius,
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_WelcomeStarsPainter o) => o.pulse != pulse;
}
