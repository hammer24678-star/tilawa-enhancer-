// lib/screens/local_mode_info_screen.dart
// S147-POLISH — Sacred Cosmos art style, fully polished
// Fixes: orbit overlap, rising particles, Arabic numerals, RTL layout, footer

import 'dart:math' show pi, sin, cos, Random;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../state/lang_provider.dart';

// ── Sacred Cosmos tokens ──────────────────────────────────────────────────────
const _bgDeep    = Color(0xFF020D17);
const _bgCard    = Color(0xFF0F2420);
const _gold      = Color(0xFFD4AF37);
const _goldLight = Color(0xFFF0CF60);
const _goldMuted = Color(0xFF3A2B08);
const _teal      = Color(0xFF1DB898);
const _textA     = Color(0xFFE2CFA0);
const _textB     = Color(0xFF8AACBA);
const _textC     = Color(0xFF3D5A65);
const _ok        = Color(0xFF2ABF6E);
const _err       = Color(0xFFD94040);
const _jade      = Color(0xFF0D2B22);

// ── Screen ────────────────────────────────────────────────────────────────────
class LocalModeInfoScreen extends StatefulWidget {
  const LocalModeInfoScreen({super.key});
  @override
  State<LocalModeInfoScreen> createState() => _LocalModeInfoScreenState();
}

class _LocalModeInfoScreenState extends State<LocalModeInfoScreen>
    with TickerProviderStateMixin {

  late final AnimationController _glowCtrl;
  late final AnimationController _starCtrl;
  late final AnimationController _geoRotCtrl;
  late final AnimationController _orbitCtrl;
  late final AnimationController _particleCtrl; // rising incense dots
  late final AnimationController _entranceCtrl;

  late final List<_StarParticle> _starList;
  late final List<Animation<double>>  _cardFades;
  late final List<Animation<Offset>>  _cardSlides;

  @override
  void initState() {
    super.initState();
    final rng = Random(9421);
    _starList = List.generate(22, (_) => _StarParticle(rng));

    _glowCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2800))
      ..repeat(reverse: true);
    _starCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 14))
      ..repeat();
    _geoRotCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 80))
      ..repeat();
    _orbitCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 12))
      ..repeat();
    _particleCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 6))
      ..repeat();
    _entranceCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 900))
      ..forward();

    _cardFades = List.generate(5, (i) {
      final start = (i * 0.13).clamp(0.0, 0.7);
      return CurvedAnimation(
        parent: _entranceCtrl,
        curve: Interval(start, (start + 0.45).clamp(0.0, 1.0),
            curve: Curves.easeOut));
    });
    _cardSlides = List.generate(5, (i) {
      final start = (i * 0.13).clamp(0.0, 0.7);
      return Tween<Offset>(begin: const Offset(0, 0.18), end: Offset.zero)
          .animate(CurvedAnimation(
            parent: _entranceCtrl,
            curve: Interval(start, (start + 0.45).clamp(0.0, 1.0),
                curve: Curves.easeOutCubic)));
    });
  }

  @override
  void dispose() {
    _glowCtrl.dispose();
    _starCtrl.dispose();
    _geoRotCtrl.dispose();
    _orbitCtrl.dispose();
    _particleCtrl.dispose();
    _entranceCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s  = LangProvider.strings(context);
    final ar = s.ar;

    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Directionality(
        textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
        child: Scaffold(
          backgroundColor: _bgDeep,
          body: Stack(children: [

            // ── Layer 0: geo pattern ───────────────────────────────────────
            Positioned.fill(child: RepaintBoundary(
              child: CustomPaint(painter: _GeoPainter()))),

            // ── Layer 1: stars ─────────────────────────────────────────────
            Positioned.fill(child: RepaintBoundary(
              child: AnimatedBuilder(
                animation: _starCtrl,
                builder: (_, __) => CustomPaint(
                  painter: _StarsPainter(_starCtrl.value, _starList))))),

            // ── Layer 2: rising incense particles ──────────────────────────
            Positioned.fill(child: RepaintBoundary(
              child: AnimatedBuilder(
                animation: _particleCtrl,
                builder: (_, __) => CustomPaint(
                  painter: _IncensePainter(_particleCtrl.value, _gold))))),

            // ── Layer 3: content ───────────────────────────────────────────
            SafeArea(child: CustomScrollView(slivers: [

              SliverToBoxAdapter(child: Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
                child: _backBtn(context, ar))),

              SliverToBoxAdapter(child: _hero(ar)),

              SliverPadding(
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 40),
                sliver: SliverList(delegate: SliverChildListDelegate([
                  _animCard(0, _whatIsCard(ar)),
                  const SizedBox(height: 12),
                  _animCard(1, _enginesCard(ar)),
                  const SizedBox(height: 12),
                  _animCard(2, _privacyCard(ar)),
                  const SizedBox(height: 12),
                  _animCard(3, _setupCard(ar)),
                  const SizedBox(height: 12),
                  _animCard(4, _troubleshootCard(ar)),
                  const SizedBox(height: 8),
                  _footerVerse(ar),
                ]))),
            ])),
          ]),
        ),
      ),
    );
  }

  // ── Back button ───────────────────────────────────────────────────────────
  Widget _backBtn(BuildContext ctx, bool ar) => GestureDetector(
    onTap: () => Navigator.of(ctx).pop(),
    child: AnimatedBuilder(
      animation: _glowCtrl,
      builder: (_, __) => Container(
        padding: const EdgeInsets.all(9),
        decoration: BoxDecoration(
          color: _bgCard, shape: BoxShape.circle,
          border: Border.all(
            color: _teal.withValues(alpha: 0.28 + 0.22 * _glowCtrl.value)),
          boxShadow: [BoxShadow(
            color: _teal.withValues(alpha: 0.08 + 0.08 * _glowCtrl.value),
            blurRadius: 10)]),
        child: Icon(
          ar ? Icons.arrow_forward_ios_rounded : Icons.arrow_back_ios_rounded,
          color: _textB, size: 18))));

  // ── Hero ──────────────────────────────────────────────────────────────────
  Widget _hero(bool ar) => Padding(
    padding: const EdgeInsets.fromLTRB(16, 8, 16, 20),
    child: Column(children: [

      // Orbital rings + engine-orbit dots + centre icon
      // All at 140×140 so orbit dots (max r=54) stay well inside
      RepaintBoundary(child: AnimatedBuilder(
        animation: Listenable.merge([_glowCtrl, _geoRotCtrl, _orbitCtrl]),
        builder: (_, __) {
          final t = _glowCtrl.value;
          final r = _geoRotCtrl.value * 6.2832;
          return SizedBox(width: 140, height: 140,
            child: Stack(alignment: Alignment.center, children: [
              // Ring 3 — outermost, slow CW
              Transform.rotate(angle: r * 0.3,
                child: Container(width: 140, height: 140,
                  decoration: BoxDecoration(shape: BoxShape.circle,
                    border: Border.all(
                      color: _gold.withValues(alpha: 0.10 + 0.12 * t),
                      width: 0.8),
                    boxShadow: [BoxShadow(
                      color: _gold.withValues(alpha: 0.05 + 0.07 * t),
                      blurRadius: 16 + 12 * t)]))),
              // Ring 2 — teal CCW
              Transform.rotate(angle: -r * 0.5,
                child: Container(width: 116, height: 116,
                  decoration: BoxDecoration(shape: BoxShape.circle,
                    border: Border.all(
                      color: _teal.withValues(alpha: 0.22 + 0.24 * t),
                      width: 1.0)))),
              // Ring 1 — inner gold, faster CW
              Transform.rotate(angle: r * 1.2,
                child: Container(width: 96, height: 96,
                  decoration: BoxDecoration(shape: BoxShape.circle,
                    border: Border.all(
                      color: _gold.withValues(alpha: 0.24 + 0.30 * t),
                      width: 1.4),
                    boxShadow: [BoxShadow(
                      color: _gold.withValues(alpha: 0.12 + 0.16 * t),
                      blurRadius: 12 + 10 * t)]))),
              // Engine orbit dots — sized to full 140×140 canvas, r 38/47/56
              // keeps them between ring-1 inner edge and the 60px icon
              CustomPaint(
                size: const Size(140, 140),
                painter: _EngineOrbitPainter(_orbitCtrl.value, t)),
              // Centre icon — breathing scale, 60×60 so r=30 from centre
              Transform.scale(
                scale: 0.96 + 0.08 * t,
                child: Container(
                  width: 60, height: 60,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle, color: _jade,
                    boxShadow: [BoxShadow(
                      color: _gold.withValues(alpha: 0.22 + 0.28 * t),
                      blurRadius: 18 + 14 * t, spreadRadius: 1)]),
                  child: const Icon(Icons.offline_bolt_rounded,
                    color: _gold, size: 32))),
            ]));
        })),

      const SizedBox(height: 16),

      ShaderMask(
        shaderCallback: (b) => const LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [_gold, _goldLight, _gold]).createShader(b),
        child: Text(
          ar ? 'المحرك المحلي' : 'Local Engine',
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 28, fontWeight: FontWeight.w800,
            color: Colors.white, height: 1.1, letterSpacing: 1.0))),

      const SizedBox(height: 6),

      Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
        decoration: BoxDecoration(
          color: _teal.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: _teal.withValues(alpha: 0.35))),
        child: Text(
          ar ? 'تشغيل كامل · خصوصية تامة · بدون إنترنت'
             : 'Fully Offline  ·  Completely Private  ·  No Internet',
          style: const TextStyle(
            color: _textB, fontSize: 10, letterSpacing: 1.2))),
    ]));

  // ── Animated card wrapper ─────────────────────────────────────────────────
  Widget _animCard(int i, Widget child) => FadeTransition(
    opacity: _cardFades[i],
    child: SlideTransition(position: _cardSlides[i], child: child));

  // ── Card 1: What is ───────────────────────────────────────────────────────
  Widget _whatIsCard(bool ar) => _card(
    accentColor: _teal,
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _cardTitle(Icons.info_outline_rounded, _teal,
        ar ? 'ما هو الوضع المحلي؟' : 'What is Local Mode?'),
      const SizedBox(height: 10),
      Text(
        ar
          ? 'الوضع المحلي يُشغِّل محرك الذكاء الاصطناعي مباشرةً على جهازك '
            'من خلال بيئة Alpine Linux مدمجة (proot). '
            'لا يُرسَل أي صوت إلى الخوادم — المعالجة بالكامل خاصة وآمنة '
            'حتى في غياب الاتصال بالإنترنت.'
          : 'Local Mode runs the AI audio engine directly on your device '
            'using a bundled Alpine Linux environment (proot). '
            'No audio is ever sent to any server — processing is entirely '
            'private and works without an internet connection.',
        style: const TextStyle(color: _textB, fontSize: 12, height: 1.7)),
      const SizedBox(height: 14),
      Center(child: _OfflineShield(_glowCtrl, ar)),
    ]));

  // ── Card 2: Engines ───────────────────────────────────────────────────────
  Widget _enginesCard(bool ar) => _card(
    accentColor: _gold,
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _cardTitle(Icons.tune_rounded, _gold,
        ar ? 'المحركات المحلية (v11.x)' : 'Local Engines (v11.x)'),
      const SizedBox(height: 4),
      Text(
        ar
          ? 'تعمل هذه المحركات محلياً — ابحث عن شارة v11.x في قائمة المحركات:'
          : 'These engines run locally — look for the v11.x badge in the engine list:',
        style: const TextStyle(color: _textC, fontSize: 10, height: 1.5)),
      const SizedBox(height: 12),
      _engineRow(ar, 'v11.0', ar ? 'التجلي'     : 'Tajalli',
        ar ? 'توجيه تلقائي — الأمثل للاستخدام العام'
           : 'Auto-routes to optimal path — best for general use',
        _gold, 99.5),
      _engineRow(ar, 'v11.1', ar ? 'الإتقان'    : 'Itiqan',
        ar ? 'مسار التسجيلات النظيفة والمضغوطة'
           : 'Path for clean & compressed recordings',
        _gold, 99.0),
      _engineRow(ar, 'v11.2', ar ? 'الاسترداد' : 'Isteidad',
        ar ? 'مسار التسجيلات التالفة وإعادة البناء'
           : 'Path for damaged recordings & reconstruction',
        _goldLight, 98.0),
      const SizedBox(height: 4),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        decoration: BoxDecoration(
          color: _textC.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: _textC.withValues(alpha: 0.25))),
        child: Row(children: [
          const Icon(Icons.info_outline_rounded, color: _textC, size: 13),
          const SizedBox(width: 7),
          Expanded(child: Text(
            ar ? 'المحركات بدون v11.x تتطلب اتصالاً بالإنترنت وتعمل على الخادم فقط.'
               : 'Engines without v11.x require internet and run on the server only.',
            style: const TextStyle(color: _textC, fontSize: 10, height: 1.4))),
        ])),
    ]));

  Widget _engineRow(bool ar, String id, String name, String desc,
      Color col, double score) =>
    Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
            decoration: BoxDecoration(
              color: _goldMuted,
              borderRadius: BorderRadius.circular(4),
              border: Border.all(color: col.withValues(alpha: 0.5))),
            child: Text(id, style: TextStyle(
              color: col, fontSize: 9, fontWeight: FontWeight.bold))),
          const SizedBox(width: 8),
          Text(name, style: TextStyle(
            color: col, fontWeight: FontWeight.bold, fontSize: 12)),
          const Spacer(),
          Text('≥${score.toInt()}', style: TextStyle(
            color: col, fontWeight: FontWeight.bold, fontSize: 12)),
        ]),
        const SizedBox(height: 4),
        AnimatedBuilder(
          animation: _entranceCtrl,
          builder: (_, __) {
            final p = (_entranceCtrl.value * score / 100).clamp(0.0, 1.0);
            return Stack(children: [
              Container(height: 5, decoration: BoxDecoration(
                color: _textC.withValues(alpha: 0.18),
                borderRadius: BorderRadius.circular(3))),
              FractionallySizedBox(
                widthFactor: p,
                child: Container(height: 5,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(3),
                    gradient: LinearGradient(
                      colors: [col.withValues(alpha: 0.7), col]),
                    boxShadow: [BoxShadow(
                      color: col.withValues(alpha: 0.45), blurRadius: 5)]))),
            ]);
          }),
        const SizedBox(height: 3),
        Text(desc, style: const TextStyle(
          color: _textC, fontSize: 10, height: 1.4)),
      ]));

  // ── Card 3: Privacy ───────────────────────────────────────────────────────
  Widget _privacyCard(bool ar) => _card(
    accentColor: _ok,
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _cardTitle(Icons.lock_outline_rounded, _ok,
        ar ? 'الخصوصية والأمان' : 'Privacy & Security'),
      const SizedBox(height: 10),
      _privacyRow(Icons.wifi_off_rounded,
        ar ? 'لا يغادر الصوت جهازك أبداً'          : 'Audio never leaves your device'),
      _privacyRow(Icons.cloud_off_rounded,
        ar ? 'لا اتصال بالشبكة أثناء المعالجة'      : 'No network access during processing'),
      _privacyRow(Icons.visibility_off_rounded,
        ar ? 'لا سجلات · لا رفع · لا مشاركة بيانات' : 'No logging · no uploads · no data sharing'),
      _privacyRow(Icons.phonelink_lock_rounded,
        ar ? 'مناسب للتسجيلات الشخصية أو الحساسة'   : 'Safe for personal or sensitive recordings'),
      _privacyRow(Icons.bolt_rounded,
        ar ? 'يعمل في وضع الطيران'                  : 'Works in airplane mode'),
    ]));

  Widget _privacyRow(IconData icon, String text) => Padding(
    padding: const EdgeInsets.only(bottom: 8),
    child: Row(children: [
      Icon(icon, color: _ok, size: 15),
      const SizedBox(width: 10),
      Expanded(child: Text(text,
        style: const TextStyle(color: _textB, fontSize: 12, height: 1.4))),
    ]));

  // ── Card 4: Setup ─────────────────────────────────────────────────────────
  Widget _setupCard(bool ar) {
    const gold2 = Color(0xFFC8A048);
    // Arabic-Indic digits for Arabic mode
    final digits = ar ? ['١', '٢', '٣', '٤'] : ['1', '2', '3', '4'];
    return _card(
      accentColor: gold2,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _cardTitle(Icons.download_rounded, gold2,
          ar ? 'الإعداد (مرة واحدة)' : 'One-Time Setup (~200 MB)'),
        const SizedBox(height: 10),
        Text(
          ar
            ? 'عند تفعيل الوضع المحلي للمرة الأولى، يلزم تنزيل بيئة Python '
              'ومحركات DeepFilter (حوالي ٢٠٠ ميغابايت). '
              'بعد الاكتمال يعمل التطبيق كاملاً بدون أي إنترنت.'
            : 'The first time you enable Local Mode, a one-time download of the '
              'Python environment and DeepFilter engine files (~200 MB) is required. '
              'After setup completes the app works entirely offline.',
          style: const TextStyle(color: _textB, fontSize: 12, height: 1.7)),
        const SizedBox(height: 12),
        _setupStep(digits[0], gold2,
          ar ? 'فعِّل مفتاح الوضع المحلي' : 'Toggle the Local Mode switch'),
        _setupStep(digits[1], gold2,
          ar ? 'اضغط على رابط الإعداد واتبع الخطوات' : 'Tap the setup link and follow the steps'),
        _setupStep(digits[2], gold2,
          ar ? 'انتظر اكتمال التنزيل (حوالي ٢٠٠ ميغابايت)' : 'Wait for the download to complete (~200 MB)'),
        _setupStep(digits[3], gold2,
          ar ? 'تظهر رسالة "جاهز — تشغيل بدون إنترنت"' : 'You see "Ready — processes fully offline"'),
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: _goldMuted.withValues(alpha: 0.5),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: gold2.withValues(alpha: 0.3))),
          child: Row(children: [
            const Icon(Icons.storage_rounded, color: gold2, size: 14),
            const SizedBox(width: 8),
            Expanded(child: Text(
              ar ? 'تأكد من توفر ٣٠٠ ميغابايت على الأقل من مساحة التخزين الحرة.'
                 : 'Ensure at least 300 MB of free storage before starting.',
              style: const TextStyle(color: gold2, fontSize: 10, height: 1.4))),
          ])),
      ]));
  }

  Widget _setupStep(String n, Color col, String text) => Padding(
    padding: const EdgeInsets.only(bottom: 7),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Container(
        width: 20, height: 20,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: col.withValues(alpha: 0.15),
          border: Border.all(color: col.withValues(alpha: 0.45))),
        child: Center(child: Text(n,
          style: TextStyle(
            color: col, fontSize: 9, fontWeight: FontWeight.bold)))),
      const SizedBox(width: 9),
      Expanded(child: Padding(
        padding: const EdgeInsets.only(top: 2),
        child: Text(text,
          style: const TextStyle(color: _textB, fontSize: 12, height: 1.4)))),
    ]));

  // ── Card 5: Troubleshooting ───────────────────────────────────────────────
  Widget _troubleshootCard(bool ar) => _card(
    accentColor: _err,
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      _cardTitle(Icons.build_circle_outlined, _err,
        ar ? 'حل المشكلات الشائعة' : 'Troubleshooting'),
      const SizedBox(height: 10),
      _troubleRow(_err,
        ar ? '"المحرك غير مُعدّ"' : '"Engine not set up"',
        ar ? 'اضغط رابط الإعداد واتبع الخطوات' : 'Tap the setup link and follow the steps'),
      _troubleRow(_err,
        ar ? 'توقف المعالجة' : 'Processing stalls',
        ar ? 'اضغط إلغاء ثم أعد المحاولة' : 'Tap Cancel then retry'),
      _troubleRow(_err,
        ar ? 'فشل الإعداد' : 'Setup fails',
        ar ? 'تأكد من توفر ٣٠٠+ ميغابايت من التخزين' : 'Ensure 300+ MB free storage'),
      _troubleRow(_err,
        ar ? 'لا يعمل بعد الإعداد' : 'Not working after setup',
        ar ? 'أعد تشغيل التطبيق' : 'Restart the app'),
      // Last item is informational, not an error — use teal
      _troubleRow(_teal,
        ar ? 'أريد العودة للخادم' : 'I want to use the server',
        ar ? 'أوقف مفتاح الوضع المحلي — يستأنف الاتصال فوراً'
           : 'Toggle Local Mode off — server connection resumes instantly'),
    ]));

  Widget _troubleRow(Color dot, String problem, String solution) => Padding(
    padding: const EdgeInsets.only(bottom: 10),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Container(width: 6, height: 6,
          decoration: BoxDecoration(shape: BoxShape.circle, color: dot))),
      const SizedBox(width: 10),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(problem, style: const TextStyle(
            color: _textA, fontSize: 11, fontWeight: FontWeight.w600)),
          const SizedBox(height: 2),
          Text(solution, style: const TextStyle(
            color: _textB, fontSize: 11, height: 1.4)),
        ])),
    ]));

  // ── Footer ────────────────────────────────────────────────────────────────
  Widget _footerVerse(bool ar) => Padding(
    padding: const EdgeInsets.only(top: 4, bottom: 4),
    child: AnimatedBuilder(
      animation: _glowCtrl,
      builder: (_, __) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: Alignment.topLeft, end: Alignment.bottomRight,
            colors: [Color(0xFF0D1B2A), Color(0xFF06101A)]),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: _gold.withValues(alpha: 0.15 + 0.10 * _glowCtrl.value))),
        child: Column(children: [
          Text('﷽', textAlign: TextAlign.center,
            style: TextStyle(
              color: _gold.withValues(alpha: 0.75 + 0.20 * _glowCtrl.value),
              fontSize: 20, height: 1.5)),
          const SizedBox(height: 8),
          Text(
            ar ? 'صوتٌ لله — يُعطى لله' : 'A voice for Allah — given back to Allah',
            textAlign: TextAlign.center,
            style: const TextStyle(
              color: _textB, fontSize: 11, height: 1.6,
              letterSpacing: 0.4, fontStyle: FontStyle.italic)),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
            decoration: BoxDecoration(
              color: _gold.withValues(alpha: 0.07),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: _gold.withValues(alpha: 0.18))),
            child: Text(
              ar
                ? '✦ المرجع: الشيخ ياسر الدوسري · ١٤٢٥هـ · LUFS=-6.29'
                : '✦ Reference: Yasser Al-Dossari · 1425H · LUFS=-6.29',
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: _gold, fontSize: 10, fontWeight: FontWeight.bold))),
        ]))));

  // ── Shared card shell ─────────────────────────────────────────────────────
  Widget _card({required Color accentColor, required Widget child}) =>
    Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _bgCard.withValues(alpha: 0.92),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: accentColor.withValues(alpha: 0.22)),
        boxShadow: [BoxShadow(
          color: accentColor.withValues(alpha: 0.05), blurRadius: 20)]),
      child: child);

  Widget _cardTitle(IconData icon, Color col, String title) =>
    Row(children: [
      Icon(icon, color: col, size: 16),
      const SizedBox(width: 8),
      Expanded(child: Text(title,
        overflow: TextOverflow.ellipsis,
        style: TextStyle(
          color: col, fontWeight: FontWeight.bold,
          fontSize: 13, letterSpacing: 0.3))),
    ]);
}

// ── Offline shield (uses AnimationController directly) ────────────────────────
class _OfflineShield extends StatelessWidget {
  final AnimationController glowCtrl;
  final bool ar;
  const _OfflineShield(this.glowCtrl, this.ar);

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: glowCtrl,
      builder: (_, __) => Row(
        mainAxisSize: MainAxisSize.min,
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          SizedBox(width: 60, height: 68,
            child: CustomPaint(painter: _ShieldPainter(glowCtrl.value))),
          const SizedBox(width: 16),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _dot(_ok,   ar ? 'لا رفع صوتي'    : 'No audio upload'),
            _dot(_ok,   ar ? 'لا خوادم'        : 'No servers'),
            _dot(_ok,   ar ? 'لا تتبع'         : 'No tracking'),
            _dot(_teal, ar ? 'معالجة محلية'    : 'On-device only'),
          ]),
        ]));
  }

  Widget _dot(Color c, String txt) => Padding(
    padding: const EdgeInsets.only(bottom: 5),
    child: Row(mainAxisSize: MainAxisSize.min, children: [
      Container(width: 6, height: 6,
        decoration: BoxDecoration(shape: BoxShape.circle, color: c)),
      const SizedBox(width: 6),
      Text(txt, style: TextStyle(
        color: c, fontSize: 11, fontWeight: FontWeight.w600)),
    ]));
}

class _ShieldPainter extends CustomPainter {
  final double t;
  const _ShieldPainter(this.t);
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2;
    final shield = Path()
      ..moveTo(cx, 4)
      ..lineTo(size.width - 5, 16)
      ..lineTo(size.width - 5, size.height * 0.55)
      ..quadraticBezierTo(cx, size.height - 4, 5, size.height * 0.55)
      ..lineTo(5, 16)
      ..close();
    final p = Paint()..style = PaintingStyle.stroke;
    // Glow
    p.maskFilter = MaskFilter.blur(BlurStyle.normal, 7 + 4 * t);
    p.color = _ok.withValues(alpha: 0.18 + 0.14 * t);
    p.strokeWidth = 3;
    canvas.drawPath(shield, p);
    // Border
    p.maskFilter = null;
    p.color = _ok.withValues(alpha: 0.55 + 0.35 * t);
    p.strokeWidth = 1.5;
    canvas.drawPath(shield, p);
    // Lock body
    final lx = cx - 6.0, ly = size.height * 0.44;
    p.style = PaintingStyle.fill;
    p.color = _ok.withValues(alpha: 0.8 + 0.2 * t);
    canvas.drawRRect(
      RRect.fromRectAndRadius(Rect.fromLTWH(lx, ly, 12, 9),
        const Radius.circular(2)), p);
    // Lock shackle
    p.style = PaintingStyle.stroke;
    p.strokeWidth = 2.0;
    canvas.drawArc(
      Rect.fromLTWH(cx - 3.5, ly - 6.5, 7, 8),
      3.14, 3.14, false, p);
  }
  @override bool shouldRepaint(_ShieldPainter o) => o.t != t;
}

// ── Engine orbit painter — dots at r=38/47/56, well outside 60px icon ────────
class _EngineOrbitPainter extends CustomPainter {
  final double t; // orbit 0..1
  final double g; // glow 0..1
  _EngineOrbitPainter(this.t, this.g);

  static const _orbits = [
    (speed: 1.00, color: _gold,      r: 56.0),
    (speed: 0.72, color: _gold,      r: 47.0),
    (speed: 0.51, color: _goldLight, r: 38.0),
  ];

  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2, cy = size.height / 2;
    final p = Paint()..style = PaintingStyle.fill;
    for (final o in _orbits) {
      final angle = t * 6.2832 * o.speed;
      final x = cx + o.r * cos(angle);
      final y = cy + o.r * sin(angle);
      // Bloom
      p.maskFilter = const MaskFilter.blur(BlurStyle.normal, 5);
      p.color = o.color.withValues(alpha: 0.22 + 0.18 * g);
      canvas.drawCircle(Offset(x, y), 5.0, p);
      // Core
      p.maskFilter = null;
      p.color = o.color.withValues(alpha: 0.72 + 0.22 * g);
      canvas.drawCircle(Offset(x, y), 3.0, p);
    }
  }
  @override bool shouldRepaint(_EngineOrbitPainter o) => o.t != t || o.g != g;
}

// ── Rising incense particles (same as home_screen.dart _IncensePainter) ───────
class _IncensePainter extends CustomPainter {
  final double t;
  final Color engCol;
  _IncensePainter(this.t, this.engCol);
  static const _xs = [
    0.08, 0.15, 0.22, 0.30, 0.38, 0.45,
    0.52, 0.58, 0.65, 0.72, 0.80, 0.88,
    0.18, 0.35, 0.55, 0.68, 0.78, 0.42,
  ];
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()..style = PaintingStyle.fill;
    for (int i = 0; i < _xs.length; i++) {
      final phase = ((t + i / _xs.length) % 1.0);
      final drift = sin(phase * 6.2832 * 1.8 + i * 1.3) * 22;
      final dx = _xs[i] * size.width + drift;
      final dy = size.height * (1.0 - phase);
      final op = phase < 0.10 ? phase / 0.10
          : phase > 0.72 ? (1.0 - phase) / 0.28 : 0.55;
      final isTeal = i % 5 == 3;
      final baseCol = isTeal ? _teal : engCol;
      p.color = baseCol.withValues(alpha: op * 0.52);
      final r = (i % 3 == 0) ? 2.0 : 1.4;
      canvas.drawCircle(Offset(dx, dy), r, p);
    }
  }
  @override bool shouldRepaint(_IncensePainter o) => o.t != t || o.engCol != engCol;
}

// ── Shared painters ───────────────────────────────────────────────────────────
class _StarParticle {
  final double x, y, size, phase, speed, twinkle;
  _StarParticle(Random r)
      : x = r.nextDouble(), y = r.nextDouble(),
        size = 1.4 + r.nextDouble() * 2.8,
        phase = r.nextDouble() * 6.2832,
        speed = 0.15 + r.nextDouble() * 0.6,
        twinkle = 0.4 + r.nextDouble() * 1.6;
}

class _StarsPainter extends CustomPainter {
  final double t;
  final List<_StarParticle> stars;
  _StarsPainter(this.t, this.stars);
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint();
    for (int idx = 0; idx < stars.length; idx++) {
      final s = stars[idx];
      final a = t * 6.2832 * s.speed + s.phase;
      final x = s.x * size.width  + sin(a) * size.width  * 0.016;
      final y = s.y * size.height + cos(a * 0.71) * size.height * 0.012;
      final alpha = sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5;
      final op = 0.22 + 0.78 * alpha;
      final sz = s.size * (0.55 + 0.45 * alpha);
      final sc = idx % 5 == 0 ? _teal
          : idx % 3 == 0 ? const Color(0xFFF0E8C8) : _gold;
      p.maskFilter = MaskFilter.blur(BlurStyle.normal, sz * 2.5);
      p.color = sc.withValues(alpha: op * 0.25);
      canvas.drawCircle(Offset(x, y), sz * 2.0, p);
      p.maskFilter = null;
      p.color = sc.withValues(alpha: op);
      canvas.drawCircle(Offset(x, y), sz, p);
    }
  }
  @override bool shouldRepaint(_StarsPainter o) => o.t != t;
}

class _GeoPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = const Color(0xFFC8A048).withValues(alpha: 0.05)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.7;
    const cell = 120.0;
    final cols = (size.width / cell).ceil() + 2;
    final rows = (size.height / (cell * 0.866)).ceil() + 2;
    for (int row = 0; row < rows; row++) {
      for (int col = 0; col < cols; col++) {
        final cx = col * cell + (row.isOdd ? cell * 0.5 : 0) - cell * 0.5;
        final cy = row * cell * 0.866 - cell * 0.5;
        _star8(canvas, Offset(cx, cy), cell * 0.27, p);
      }
    }
  }
  void _star8(Canvas canvas, Offset c, double r, Paint p) {
    final path = Path();
    for (int i = 0; i < 8; i++) {
      final oa = i * pi / 4 - pi / 2;
      final ia = oa + pi / 8;
      final ox = c.dx + r * cos(oa); final oy = c.dy + r * sin(oa);
      final ix = c.dx + r * 0.38 * cos(ia); final iy = c.dy + r * 0.38 * sin(ia);
      if (i == 0) path.moveTo(ox, oy); else path.lineTo(ox, oy);
      path.lineTo(ix, iy);
    }
    path.close();
    canvas.drawPath(path, p);
  }
  @override bool shouldRepaint(_GeoPainter _) => false;
}
