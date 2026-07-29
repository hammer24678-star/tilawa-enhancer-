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
    // S251: _geoRotCtrl was created and repeated but never listened to — it
    // drove nothing while still ticking every frame. The geometry was instead
    // rotated off _pulseCtrl, which repeats with reverse:true, so the "slow
    // rotation" actually swung forward and back. Wired up as intended.
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
    if (p == _page || p < 0 || p > 2) return;
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
  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF0F2420) : const Color(0xFFF3EED9);
  Color _cSub(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF8AAABB) : const Color(0xFF6B5E40);

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    return PopScope(
      // S251: system back used to leave the app from page 1 or 2, because
      // the pages are internal state rather than routes. Back now walks the
      // onboarding backwards and only exits from the first page.
      canPop: _page == 0,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _goPage(_page - 1);
      },
      child: Scaffold(
        backgroundColor: const Color(0xFF020D0C), // S45-WEL
        body: Stack(children: [
          // Rotating geo background
          Positioned.fill(child: AnimatedBuilder(
            animation: _geoRotCtrl,
            builder: (_, child) => Transform.rotate(
              angle: _geoRotCtrl.value * 6.2832,
              child: child),
            child: CustomPaint(painter: _GeoPainter()))),
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
      ),
    );
  }

  /// S251: every page was a bare centred Column. Page 0 at least scrolled;
  /// pages 1 and 2 did not, so a short screen (or a large system text scale)
  /// overflowed them and clipped the button the page exists to show. This
  /// shell scrolls when the content is taller than the viewport and keeps the
  /// old vertical centring when it isn't.
  Widget _shell({required EdgeInsets padding, required List<Widget> children}) =>
    LayoutBuilder(builder: (_, box) => SingleChildScrollView(
      padding: padding,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          minHeight: math.max(0.0, box.maxHeight - padding.vertical)),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: children,
        ),
      ),
    ));

  // ── Page 0: Brand splash ──────────────────────────────────────────────────
  Widget _page0(S s) => _shell(
    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
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
        const SizedBox(height: 28),
        // S84: Mode info card
        Container(
          margin: const EdgeInsets.symmetric(horizontal: 4),
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.black.withValues(alpha: 0.28),
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: const Color(0xFF1DB898).withValues(alpha: 0.30))),
          child: Column(children: [
            _modeRow(
              badgeIcon: Icons.phone_android_rounded,
              badge: 'LOCAL',
              badgeColor: const Color(0xFF1DB898),
              badgeBg: const Color(0xFF1DB898).withValues(alpha: 0.15),
              badgeBorder: const Color(0xFF1DB898).withValues(alpha: 0.5),
              title: s.localModeEngines,
              titleColor: const Color(0xFFD4AF37),
              titleSize: 13,
              body: s.localModeDesc,
              bodyColor: const Color(0xFF8AACBA),
              ar: s.ar),
            const SizedBox(height: 14),
            const Divider(color: Colors.white10, height: 1),
            const SizedBox(height: 14),
            _modeRow(
              badgeIcon: Icons.cloud_outlined,
              badge: 'SERVER',
              badgeColor: const Color(0xFF8AACBA),
              badgeBg: Colors.white.withValues(alpha: 0.06),
              badgeBorder: Colors.white24,
              title: 'v10.0 · v9.0 · v8.5 · v8.0',
              titleColor: const Color(0xFF8AACBA),
              titleSize: 12,
              body: s.serverModeDesc,
              bodyColor: const Color(0xFF3D5A65),
              ar: s.ar),
          ])),
        const SizedBox(height: 20),
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
    );

  /// One row of the mode card. Mirrors for Arabic so the badge sits on the
  /// leading edge in both languages instead of always on the left.
  Widget _modeRow({
    required IconData badgeIcon,
    required String badge,
    required Color badgeColor,
    required Color badgeBg,
    required Color badgeBorder,
    required String title,
    required Color titleColor,
    required double titleSize,
    required String body,
    required Color bodyColor,
    required bool ar,
  }) => Row(
    textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        decoration: BoxDecoration(
          color: badgeBg,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: badgeBorder)),
        // S255: these labels used to carry a literal house and cloud emoji
        // inside the Text. Android resolves both through Noto Color Emoji, so
        // they did render — as full-colour emoji, at a size the font picks,
        // ignoring badgeColor entirely. Against a flat 10px gold-or-teal badge
        // that is the one element on the card not obeying the palette. Material
        // Icons ship in the APK, scale with the text and take the badge's own
        // colour, so the badge reads as one object.
        child: Row(mainAxisSize: MainAxisSize.min,
          textDirection: TextDirection.ltr,
          children: [
            Icon(badgeIcon, size: 11, color: badgeColor),
            const SizedBox(width: 4),
            Text(badge,
              textDirection: TextDirection.ltr,
              style: TextStyle(color: badgeColor,
                fontSize: 10, fontWeight: FontWeight.bold)),
          ])),
      const SizedBox(width: 12),
      Expanded(child: Column(
        crossAxisAlignment: ar
          ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          Text(title,
            textAlign: ar ? TextAlign.right : TextAlign.left,
            style: TextStyle(color: titleColor,
              fontSize: titleSize, fontWeight: FontWeight.bold)),
          const SizedBox(height: 3),
          Text(body,
            textAlign: ar ? TextAlign.right : TextAlign.left,
            style: TextStyle(color: bodyColor, fontSize: 10, height: 1.6)),
        ])),
    ]);


  // ── Page 1: How it works ──────────────────────────────────────────────────
  Widget _page1(S s) {
    final steps = [
      (Icons.audio_file_outlined,    s.step1),
      (Icons.tune_rounded,           s.step2),
      (Icons.cloud_sync_outlined,    s.step3),
      (Icons.download_done_rounded,  s.step4),
    ];
    // S251: the step rows were pinned to TextDirection.rtl regardless of
    // language, so in English the numbering read right-to-left with the icon
    // on the wrong side. Direction now follows the selected language.
    final dir = s.ar ? TextDirection.rtl : TextDirection.ltr;
    return _shell(
      padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
      children: [
          Text(s.howItWorks,
            style: const TextStyle(
              color: Color(0xFFD4AF37),
              fontSize: 26, fontWeight: FontWeight.bold)),
          const SizedBox(height: 32),
          ...steps.asMap().entries.map((entry) => Padding(
            padding: const EdgeInsets.only(bottom: 18),
            child: Row(
              textDirection: dir,
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
                  crossAxisAlignment: s.ar
                    ? CrossAxisAlignment.end : CrossAxisAlignment.start,
                  children: [
                    Text(
                      s.stepLabel(entry.key + 1),
                      textDirection: dir,
                      style: const TextStyle(
                        color: Color(0xFF484F58),
                        fontSize: 9, letterSpacing: 0.5)),
                    const SizedBox(height: 2),
                    Text(entry.value.$2,
                      textDirection: dir,
                      textAlign: s.ar ? TextAlign.right : TextAlign.left,
                      style: const TextStyle(
                        color: Color(0xFFF2EFE5),
                        fontSize: 13, height: 1.45)),
                  ],
                )),
              ],
            ),
          )),
          const SizedBox(height: 12),
          _primaryBtn(s.welcomeNext, () => _goPage(2)),
          const SizedBox(height: 6),
          _backBtn(s, 0),
          const SizedBox(height: 4),
          _dots(1),
      ],
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
    return _shell(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
      children: [
          Text(s.welcomeEngines,
            style: const TextStyle(
              color: Color(0xFFD4AF37),
              fontSize: 24, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          Text(s.welcomeEnginesSub,
            textAlign: TextAlign.center,
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
          const SizedBox(height: 6),
          _backBtn(s, 1),
          const SizedBox(height: 4),
          _dots(2),
      ],
    );
  }

  /// S251: pages 1 and 2 only ever pointed forward — no visible way back to
  /// the page before, and the dots were decoration rather than navigation.
  Widget _backBtn(S s, int target) => TextButton.icon(
    onPressed: () => _goPage(target),
    icon: Icon(
      s.ar ? Icons.arrow_forward_rounded : Icons.arrow_back_rounded,
      size: 15, color: const Color(0xFF8AAABB)),
    label: Text(s.welcomeBack,
      style: const TextStyle(color: Color(0xFF8AAABB), fontSize: 13)));

  Widget _dots(int active) => Row(
    mainAxisAlignment: MainAxisAlignment.center,
    children: List.generate(3, (i) => GestureDetector(
      onTap: () => _goPage(i),
      behavior: HitTestBehavior.opaque,
      // The dot itself stays 6px tall; the padding turns it into a real tap
      // target without leaving a 48px hole at the bottom of the page.
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 14),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          width:  i == active ? 20 : 6,
          height: 6,
          decoration: BoxDecoration(
            color: i == active
              ? const Color(0xFFD4AF37)
              : const Color(0xFF30363D),
            borderRadius: BorderRadius.circular(3)))))));

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
