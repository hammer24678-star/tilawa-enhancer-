// lib/screens/local_mode_info_screen.dart
// Local Engine info — Nur redesign.
// Hero orb, staggered section cards, animated engine-score bars, a living
// offline shield and expandable troubleshooting rows.

import 'dart:math' show pi, sin, cos;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../design/nur.dart';
import '../state/lang_provider.dart';

// ── Sacred Cosmos tokens ──────────────────────────────────────────────────────
const _bgDeep    = Color(0xFF050E10);
const _bgCard    = Color(0xFF0B1A1D);
const _gold      = Color(0xFFD9B13F);
const _goldLight = Color(0xFFF5DC85);
const _goldMuted = Color(0xFF3A2B08);
const _teal      = Color(0xFF2FD4B0);
const _textA     = Color(0xFFEAF2EE);
const _textB     = Color(0xFF9DB6B6);
const _textC     = Color(0xFF5E7B7C);
const _ok        = Color(0xFF3DDC97);
const _err       = Color(0xFFFF6B6B);
const _jade      = Color(0xFF122529);

// ── Screen ────────────────────────────────────────────────────────────────────
class LocalModeInfoScreen extends StatefulWidget {
  const LocalModeInfoScreen({super.key});
  @override
  State<LocalModeInfoScreen> createState() => _LocalModeInfoScreenState();
}

class _LocalModeInfoScreenState extends State<LocalModeInfoScreen>
    with TickerProviderStateMixin {

  late final AnimationController _glowCtrl;
  late final AnimationController _geoRotCtrl;
  late final AnimationController _orbitCtrl;
  late final AnimationController _entranceCtrl;

  late final List<Animation<double>>  _cardFades;
  late final List<Animation<Offset>>  _cardSlides;

  @override
  void initState() {
    super.initState();

    _glowCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2800))
      ..repeat(reverse: true);
    _geoRotCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 80))
      ..repeat();
    _orbitCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 12))
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
    _geoRotCtrl.dispose();
    _orbitCtrl.dispose();
    _entranceCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    final ar = s.ar;
    final p = NurPalette.of(context);

    // This screen's text colours are tuned for the night palette, so it
    // always renders in it (like the old dark-only version did).
    return Theme(
      data: buildNurTheme(dark: true),
      child: AnnotatedRegion<SystemUiOverlayStyle>(
        value: SystemUiOverlayStyle.light,
        child: Directionality(
          textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
          child: Scaffold(
            backgroundColor: _bgDeep,
            body: NurBackdrop(
              accent: _teal,
              child: SafeArea(child: CustomScrollView(
                physics: const BouncingScrollPhysics(),
                slivers: [

                SliverToBoxAdapter(child: Padding(
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 0),
                  child: Align(
                    alignment: AlignmentDirectional.centerStart,
                    child: _backBtn(context, ar)))),

                SliverToBoxAdapter(child: _hero(ar)),

                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 40),
                  sliver: SliverList(delegate: SliverChildListDelegate([
                    _animCard(0, _whatIsCard(ar)),
                    const SizedBox(height: 14),
                    _animCard(1, _enginesCard(ar)),
                    const SizedBox(height: 14),
                    _animCard(2, _privacyCard(ar)),
                    const SizedBox(height: 14),
                    _animCard(3, _setupCard(ar)),
                    const SizedBox(height: 14),
                    _animCard(4, _troubleshootCard(ar)),
                    const SizedBox(height: 8),
                    _footerVerse(ar),
                  ]))),
              ])),
            ),
          ),
        ),
      ),
    );
  }

  // ── Back button ───────────────────────────────────────────────────────────
  Widget _backBtn(BuildContext ctx, bool ar) => NurIconButton(
    icon: ar ? Icons.arrow_forward_ios_rounded : Icons.arrow_back_ios_new_rounded,
    onTap: () => Navigator.of(ctx).pop());

  // ── Hero ──────────────────────────────────────────────────────────────────
  Widget _hero(NurPalette p, bool ar) => Padding(
        padding: const EdgeInsets.fromLTRB(0, 6, 0, 18),
        child: Column(children: [
          NurOrb(
            animation: _c,
            size: 156,
            energy: 0.4,
            a: p.teal,
            b: p.goldLight,
            child: Icon(Icons.offline_bolt_rounded, color: p.gold, size: 36),
          ),
          const SizedBox(height: 14),
          GradientText(
            ar ? 'المحرك المحلي' : 'Local Engine',
            gradient: p.goldGradient,
            textAlign: TextAlign.center,
            style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w800,
                height: 1.2,
                letterSpacing: 0.6),
          ),
          const SizedBox(height: 10),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
            decoration: BoxDecoration(
              color: p.teal.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: p.teal.withValues(alpha: 0.38)),
            ),
            child: Text(
              ar
                  ? 'تشغيل كامل · خصوصية تامة · بدون إنترنت'
                  : 'Fully Offline  ·  Completely Private  ·  No Internet',
              textAlign: TextAlign.center,
              style: TextStyle(
                  color: p.textSub,
                  fontSize: 11,
                  height: 1.4,
                  letterSpacing: 0.6),
            ),
          ),
        ]),
      );

  // ── Shared card shell ─────────────────────────────────────────────────────
  Widget _card({required Color accentColor, required Widget child}) =>
    NurCard(
      radius: 22,
      accent: accentColor,
      padding: const EdgeInsets.all(18),
      child: SizedBox(width: double.infinity, child: child));

  Widget _body(NurPalette p, String text) => Text(text,
      style: TextStyle(color: p.textSub, fontSize: 12.5, height: 1.7));

  Widget _note(NurPalette p, IconData icon, Color col, String text) =>
      Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        decoration: BoxDecoration(
          color: col.withValues(alpha: 0.08),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: col.withValues(alpha: 0.28)),
        ),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(
              padding: const EdgeInsets.only(top: 1),
              child: Icon(icon, color: col, size: 15)),
          const SizedBox(width: 8),
          Expanded(
              child: Text(text,
                  style: TextStyle(color: p.textSub, fontSize: 11.5, height: 1.5))),
        ]),
      );

  // ── Card 1: What is ───────────────────────────────────────────────────────
  Widget _whatIsCard(NurPalette p, bool ar) => NurCard(
        accent: p.teal,
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          _title(p, Icons.info_outline_rounded, p.teal,
              ar ? 'ما هو الوضع المحلي؟' : 'What is Local Mode?'),
          const SizedBox(height: 12),
          _body(
              p,
              ar
                  ? 'الوضع المحلي يُشغِّل محرك الذكاء الاصطناعي مباشرةً على جهازك '
                      'من خلال بيئة Alpine Linux مدمجة (proot). '
                      'لا يُرسَل أي صوت إلى الخوادم — المعالجة بالكامل خاصة وآمنة '
                      'حتى في غياب الاتصال بالإنترنت.'
                  : 'Local Mode runs the AI audio engine directly on your device '
                      'using a bundled Alpine Linux environment (proot). '
                      'No audio is ever sent to any server — processing is entirely '
                      'private and works without an internet connection.'),
          const SizedBox(height: 16),
          _offlineShield(p, ar),
        ]),
      );

  Widget _offlineShield(NurPalette p, bool ar) => AnimatedBuilder(
        animation: _c,
        builder: (_, __) {
          final t = (sin(_c.value * 2 * pi) + 1) / 2;
          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
            decoration: BoxDecoration(
              color: p.ok.withValues(alpha: 0.06 + 0.03 * t),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: p.ok.withValues(alpha: 0.22 + 0.12 * t)),
            ),
            child: Row(children: [
              SizedBox(
                  width: 60,
                  height: 68,
                  child: CustomPaint(painter: _ShieldPainter(t, p.ok))),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _dot(p.ok, ar ? 'لا رفع صوتي' : 'No audio upload'),
                      _dot(p.ok, ar ? 'لا خوادم' : 'No servers'),
                      _dot(p.ok, ar ? 'لا تتبع' : 'No tracking'),
                      _dot(p.teal, ar ? 'معالجة محلية' : 'On-device only'),
                    ]),
              ),
            ]),
          );
        },
      );

  Widget _dot(Color c, String txt) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(children: [
          Container(
              width: 6,
              height: 6,
              decoration: BoxDecoration(shape: BoxShape.circle, color: c)),
          const SizedBox(width: 8),
          Expanded(
            child: Text(txt,
                style: TextStyle(
                    color: c, fontSize: 12, fontWeight: FontWeight.w700)),
          ),
        ]),
      );

  // ── Card 2: Engines ───────────────────────────────────────────────────────
  Widget _enginesCard(NurPalette p, bool ar) => NurCard(
        accent: p.gold,
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          _title(p, Icons.tune_rounded, p.gold,
              ar ? 'المحركات المحلية (v11.x)' : 'Local Engines (v11.x)'),
          const SizedBox(height: 8),
          Text(
              ar
                  ? 'تعمل هذه المحركات محلياً — ابحث عن شارة v11.x في قائمة المحركات:'
                  : 'These engines run locally — look for the v11.x badge in the engine list:',
              style: TextStyle(color: p.textDim, fontSize: 11, height: 1.5)),
          const SizedBox(height: 14),
          _engineRow(
              p,
              'v11.0',
              ar ? 'الصفاء' : 'Safaa',
              ar
                  ? 'إزالة صدى المساجد — يحافظ على أحكام التجويد كاملةً'
                  : 'Mosque echo removal — full Tajweed phonology preservation',
              p.gold,
              99.5),
          _engineRow(
              p,
              'v11.1',
              ar ? 'الإتقان' : 'Itiqan',
              ar
                  ? 'مسار التسجيلات النظيفة والمضغوطة'
                  : 'Path for clean & compressed recordings',
              p.gold,
              99.0),
          _engineRow(
              p,
              'v11.2',
              ar ? 'الاسترداد' : 'Isteidad',
              ar
                  ? 'مسار التسجيلات التالفة وإعادة البناء'
                  : 'Path for damaged recordings & reconstruction',
              p.goldLight,
              98.0),
          const SizedBox(height: 2),
          _note(
              p,
              Icons.info_outline_rounded,
              p.info,
              ar
                  ? 'المحركات بدون v11.x تتطلب اتصالاً بالإنترنت وتعمل على الخادم فقط.'
                  : 'Engines without v11.x require internet and run on the server only.'),
        ]),
      );

  Widget _engineRow(NurPalette p, String id, String name, String desc,
          Color col, double score) =>
      Padding(
        padding: const EdgeInsets.only(bottom: 14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            NurChip(label: id, color: col, filled: true, fontSize: 10),
            const SizedBox(width: 8),
            Expanded(
              child: Text(name,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                      color: col, fontWeight: FontWeight.w800, fontSize: 13)),
            ),
            const SizedBox(width: 8),
            Text('≥${score.toInt()}',
                style: TextStyle(
                    color: col, fontWeight: FontWeight.w800, fontSize: 13)),
          ]),
          const SizedBox(height: 8),
          TweenAnimationBuilder<double>(
            tween: Tween<double>(begin: 0, end: score / 100),
            duration: const Duration(milliseconds: 1100),
            curve: Curves.easeOutCubic,
            builder: (_, v, __) => NurProgressBar(
                value: v, height: 6, a: col.withValues(alpha: 0.55), b: col),
          ),
          const SizedBox(height: 6),
          Text(desc,
              style: TextStyle(color: p.textSub, fontSize: 11.5, height: 1.5)),
        ]),
      );

  // ── Card 3: Privacy ───────────────────────────────────────────────────────
  Widget _privacyCard(NurPalette p, bool ar) {
    final rows = <List<Object>>[
      [
        Icons.wifi_off_rounded,
        ar ? 'لا يغادر الصوت جهازك أبداً' : 'Audio never leaves your device'
      ],
      [
        Icons.cloud_off_rounded,
        ar ? 'لا اتصال بالشبكة أثناء المعالجة' : 'No network access during processing'
      ],
      [
        Icons.visibility_off_rounded,
        ar
            ? 'لا سجلات · لا رفع · لا مشاركة بيانات'
            : 'No logging · no uploads · no data sharing'
      ],
      [
        Icons.phonelink_lock_rounded,
        ar ? 'مناسب للتسجيلات الشخصية أو الحساسة' : 'Safe for personal or sensitive recordings'
      ],
      [Icons.bolt_rounded, ar ? 'يعمل في وضع الطيران' : 'Works in airplane mode'],
    ];
    return NurCard(
      accent: p.ok,
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _title(p, Icons.lock_outline_rounded, p.ok,
            ar ? 'الخصوصية والأمان' : 'Privacy & Security'),
        const SizedBox(height: 12),
        for (var i = 0; i < rows.length; i++)
          EntranceFade(
            index: i,
            offsetY: 8,
            child: _privacyRow(p, rows[i][0] as IconData, rows[i][1] as String),
          ),
      ]),
    );
  }

  Widget _privacyRow(NurPalette p, IconData icon, String text) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Row(children: [
          Container(
            width: 28,
            height: 28,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: p.ok.withValues(alpha: 0.12),
              border: Border.all(color: p.ok.withValues(alpha: 0.35)),
            ),
            child: Icon(icon, color: p.ok, size: 15),
          ),
          const SizedBox(width: 12),
          Expanded(
              child: Text(text,
                  style: TextStyle(color: p.text, fontSize: 12.5, height: 1.4))),
        ]),
      );

  // ── Card 4: Setup ─────────────────────────────────────────────────────────
  Widget _setupCard(NurPalette p, bool ar) {
    final col = p.gold;
    // Arabic-Indic digits for Arabic mode
    final digits = ar ? ['١', '٢', '٣', '٤'] : ['1', '2', '3', '4'];
    final steps = [
      ar ? 'فعِّل مفتاح الوضع المحلي' : 'Toggle the Local Mode switch',
      ar ? 'اضغط على رابط الإعداد واتبع الخطوات' : 'Tap the setup link and follow the steps',
      ar
          ? 'انتظر اكتمال التنزيل (حوالي ٢٠٠ ميغابايت)'
          : 'Wait for the download to complete (~200 MB)',
      ar
          ? 'تظهر رسالة "جاهز — تشغيل بدون إنترنت"'
          : 'You see "Ready — processes fully offline"',
    ];
    return NurCard(
      accent: col,
      padding: const EdgeInsets.all(18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        _title(p, Icons.download_rounded, col,
            ar ? 'الإعداد (مرة واحدة)' : 'One-Time Setup (~200 MB)'),
        const SizedBox(height: 12),
        _body(
            p,
            ar
                ? 'عند تفعيل الوضع المحلي للمرة الأولى، يلزم تنزيل بيئة Python '
                    'ومحركات DeepFilter (حوالي ٢٠٠ ميغابايت). '
                    'بعد الاكتمال يعمل التطبيق كاملاً بدون أي إنترنت.'
                : 'The first time you enable Local Mode, a one-time download of the '
                    'Python environment and DeepFilter engine files (~200 MB) is required. '
                    'After setup completes the app works entirely offline.'),
        const SizedBox(height: 14),
        for (var i = 0; i < steps.length; i++)
          EntranceFade(
            index: i,
            offsetY: 8,
            child: _setupStep(p, digits[i], col, steps[i], i < steps.length - 1),
          ),
        const SizedBox(height: 4),
        _note(
            p,
            Icons.storage_rounded,
            col,
            ar
                ? 'تأكد من توفر ٣٠٠ ميغابايت على الأقل من مساحة التخزين الحرة.'
                : 'Ensure at least 300 MB of free storage before starting.'),
      ]),
    );
  }

  Widget _setupStep(
          NurPalette p, String n, Color col, String text, bool connector) =>
      IntrinsicHeight(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SizedBox(
            width: 26,
            child: Column(children: [
              Container(
                width: 26,
                height: 26,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [col.withValues(alpha: 0.35), col.withValues(alpha: 0.12)],
                  ),
                  border: Border.all(color: col.withValues(alpha: 0.55)),
                ),
                child: Center(
                    child: Text(n,
                        style: TextStyle(
                            color: col,
                            fontSize: 11,
                            fontWeight: FontWeight.w800))),
              ),
              if (connector)
                Expanded(
                    child: Container(
                        width: 1.5, color: col.withValues(alpha: 0.28))),
            ]),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Padding(
              padding: EdgeInsets.only(top: 3, bottom: connector ? 14 : 8),
              child: Text(text,
                  style: TextStyle(color: p.text, fontSize: 12.5, height: 1.45)),
            ),
          ),
        ]),
      );

  // ── Card 5: Troubleshooting ───────────────────────────────────────────────
  Widget _troubleshootCard(NurPalette p, bool ar) => NurCard(
        accent: p.err,
        padding: const EdgeInsets.all(18),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          _title(p, Icons.build_circle_outlined, p.err,
              ar ? 'حل المشكلات الشائعة' : 'Troubleshooting'),
          const SizedBox(height: 10),
          _TroubleRow(
              dot: p.err,
              open: true,
              problem: ar ? '"المحرك غير مُعدّ"' : '"Engine not set up"',
              solution: ar
                  ? 'اضغط رابط الإعداد واتبع الخطوات'
                  : 'Tap the setup link and follow the steps'),
          _TroubleRow(
              dot: p.err,
              problem: ar ? 'توقف المعالجة' : 'Processing stalls',
              solution: ar ? 'اضغط إلغاء ثم أعد المحاولة' : 'Tap Cancel then retry'),
          _TroubleRow(
              dot: p.err,
              problem: ar ? 'فشل الإعداد' : 'Setup fails',
              solution: ar
                  ? 'تأكد من توفر ٣٠٠+ ميغابايت من التخزين'
                  : 'Ensure 300+ MB free storage'),
          _TroubleRow(
              dot: p.err,
              problem: ar ? 'لا يعمل بعد الإعداد' : 'Not working after setup',
              solution: ar ? 'أعد تشغيل التطبيق' : 'Restart the app'),
          // Last item is informational, not an error — use teal
          _TroubleRow(
              dot: p.teal,
              problem: ar ? 'أريد العودة للخادم' : 'I want to use the server',
              solution: ar
                  ? 'أوقف مفتاح الوضع المحلي — يستأنف الاتصال فوراً'
                  : 'Toggle Local Mode off — server connection resumes instantly'),
        ]),
      );

  // ── Footer ────────────────────────────────────────────────────────────────
  Widget _footerVerse(NurPalette p, bool ar) => NurCard(
        accent: p.gold,
        glow: true,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 18),
        child: SizedBox(
          width: double.infinity,
          child: Column(children: [
            GradientText('﷽',
                gradient: p.goldGradient,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 26, height: 1.5)),
            const SizedBox(height: 8),
            Text(
                ar ? 'صوتٌ لله — يُعطى لله' : 'A voice for Allah — given back to Allah',
                textAlign: TextAlign.center,
                style: TextStyle(
                    color: p.textSub,
                    fontSize: 12,
                    height: 1.6,
                    letterSpacing: 0.4,
                    fontStyle: FontStyle.italic)),
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
              decoration: BoxDecoration(
                color: p.gold.withValues(alpha: 0.09),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: p.gold.withValues(alpha: 0.30)),
              ),
              child: Text(
                  ar
                      ? '✦ المرجع: الشيخ ياسر الدوسري · ١٤٢٥هـ · LUFS=-6.29'
                      : '✦ Reference: Yasser Al-Dossari · 1425H · LUFS=-6.29',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                      color: p.gold,
                      fontSize: 11,
                      height: 1.4,
                      fontWeight: FontWeight.w700)),
            ),
          ]),
        ),
      );
}

// ── Expandable troubleshooting row ────────────────────────────────────────────
class _TroubleRow extends StatefulWidget {
  final Color dot;
  final String problem;
  final String solution;
  final bool open;
  const _TroubleRow({
    required this.dot,
    required this.problem,
    required this.solution,
    this.open = false,
  });

  @override
  State<_TroubleRow> createState() => _TroubleRowState();
}

class _TroubleRowState extends State<_TroubleRow> {
  late bool _open = widget.open;

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: () => setState(() => _open = !_open),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 7),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Container(
                width: 7,
                height: 7,
                decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: widget.dot,
                    boxShadow: [
                      BoxShadow(
                          color: widget.dot.withValues(alpha: 0.5),
                          blurRadius: 6)
                    ])),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(widget.problem,
                  style: TextStyle(
                      color: p.text,
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                      height: 1.4)),
              AnimatedSize(
                duration: const Duration(milliseconds: 260),
                curve: Curves.easeOutCubic,
                alignment: Alignment.topCenter,
                child: _open
                    ? SizedBox(
                        width: double.infinity,
                        child: Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(widget.solution,
                              style: TextStyle(
                                  color: p.textSub, fontSize: 12, height: 1.5)),
                        ),
                      )
                    : const SizedBox(width: double.infinity, height: 0),
              ),
            ]),
          ),
          const SizedBox(width: 8),
          AnimatedRotation(
            turns: _open ? 0.5 : 0,
            duration: const Duration(milliseconds: 260),
            curve: Curves.easeOutCubic,
            child: Icon(Icons.keyboard_arrow_down_rounded,
                color: p.textDim, size: 20),
          ),
        ]),
      ),
    );
  }
}

// ── Offline shield painter ────────────────────────────────────────────────────
class _ShieldPainter extends CustomPainter {
  final double t;
  final Color color;
  const _ShieldPainter(this.t, this.color);
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
    p.color = color.withValues(alpha: 0.18 + 0.14 * t);
    p.strokeWidth = 3;
    canvas.drawPath(shield, p);
    // Border
    p.maskFilter = null;
    p.color = color.withValues(alpha: 0.55 + 0.35 * t);
    p.strokeWidth = 1.5;
    canvas.drawPath(shield, p);
    // Lock body
    final lx = cx - 6.0, ly = size.height * 0.44;
    p.style = PaintingStyle.fill;
    p.color = color.withValues(alpha: 0.8 + 0.2 * t);
    canvas.drawRRect(
        RRect.fromRectAndRadius(
            Rect.fromLTWH(lx, ly, 12, 9), const Radius.circular(2)),
        p);
    // Lock shackle
    p.style = PaintingStyle.stroke;
    p.strokeWidth = 2.0;
    canvas.drawArc(Rect.fromLTWH(cx - 3.5, ly - 6.5, 7, 8), 3.14, 3.14, false, p);
  }

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

