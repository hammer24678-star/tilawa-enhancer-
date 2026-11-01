import 'package:flutter/material.dart';
import '../design/nur.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../design/nur.dart';
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
  late final Animation<double> _fade;
  late final Animation<Offset> _slide;
  int _page = 0;
  int _dir = 1; // +1 moving forward, -1 moving back (drives the slide)
  int _mode = 0; // 0 = local card highlighted, 1 = server (visual only)

  @override
  void initState() {
    super.initState();
    _fadeCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 600));
    _pulseCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2200))
      ..repeat(reverse: true);

    _fade  = CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeIn);
    _slide = Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)
        .animate(CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOutCubic));

    _fadeCtrl.forward();
  }

  @override
  void dispose() {
    _fadeCtrl.dispose();
    _pulseCtrl.dispose();
    super.dispose();
  }

  void _goPage(int p) {
    if (p == _page || p < 0 || p > 2) return;
    HapticFeedback.selectionClick();
    setState(() {
      _dir = p > _page ? 1 : -1;
      _page = p;
    });
  }

  Future<void> _finish() async {
    HapticFeedback.lightImpact();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('seen_welcome_v5', true); // S108
    if (!mounted) return;
    Navigator.of(context).pushReplacement(nurRoute(const HomeScreen()));
  }

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    final p = NurPalette.of(context);
    return PopScope(
      // S251: system back used to leave the app from page 1 or 2, because
      // the pages are internal state rather than routes. Back now walks the
      // onboarding backwards and only exits from the first page.
      canPop: _page == 0,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _goPage(_page - 1);
      },
      child: Scaffold(
        backgroundColor: p.bg,
        body: NurBackdrop(
          accent: _page == 1 ? p.teal : p.gold,
          child: SafeArea(
            child: FadeTransition(
              opacity: _fade,
              child: SlideTransition(
                position: _slide,
                child: _page == 0 ? _page0(s, p) : _page == 1 ? _page1(s, p) : _page2(s, p),
              ),
            ),
          ),
        ),
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
      physics: const BouncingScrollPhysics(),
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
  Widget _page0(S s, NurPalette p) => _shell(
    padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
    children: [
        // Orb with the logo inside
        NurOrb(
          animation: _pulseCtrl,
          size: 230,
          energy: 0.5,
          child: Container(
            width: 112, height: 112,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: p.surface,
              border: Border.all(color: p.gold.withValues(alpha: 0.55), width: 1.6),
              boxShadow: [BoxShadow(
                color: p.gold.withValues(alpha: 0.30), blurRadius: 26)]),
            child: ClipOval(
              child: Image.asset('assets/images/logo.png', fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => Icon(Icons.music_note_rounded,
                  color: p.gold, size: 52))))),
        const SizedBox(height: 22),
        GradientText(s.appName,
          textAlign: TextAlign.center,
          gradient: p.goldGradient,
          style: const TextStyle(
            fontSize: 40, fontWeight: FontWeight.w900,
            height: 1.15, letterSpacing: -0.5)),
        const SizedBox(height: 8),
        Text(s.subtitle,
          style: TextStyle(color: p.textSub, fontSize: 11, letterSpacing: 3.0)),
        const SizedBox(height: 26),
        Text(s.welcomeDesc,
          textAlign: TextAlign.center,
          style: TextStyle(color: p.text, fontSize: 14, height: 1.9)),
        const SizedBox(height: 24),
        // S84: Mode info card
        NurCard(
          radius: 22,
          padding: const EdgeInsets.all(16),
          child: Column(children: [
            _modeRow(
              p: p,
              badgeIcon: Icons.phone_android_rounded,
              badge: 'LOCAL',
              badgeColor: p.teal,
              title: s.localModeEngines,
              titleColor: p.gold,
              titleSize: 13,
              body: s.localModeDesc,
              bodyColor: p.textSub,
              ar: s.ar),
            const SizedBox(height: 14),
            Divider(color: p.border, height: 1),
            const SizedBox(height: 14),
            _modeRow(
              p: p,
              badgeIcon: Icons.cloud_outlined,
              badge: 'SERVER',
              badgeColor: p.info,
              title: 'v10.0 · v9.0 · v8.5 · v8.0',
              titleColor: p.textSub,
              titleSize: 12,
              body: s.serverModeDesc,
              bodyColor: p.textDim,
              ar: s.ar),
          ])),
        const SizedBox(height: 22),
        NurButton(label: s.howItWorks, onTap: () => _goPage(1)),
        const SizedBox(height: 10),
        TextButton(
          onPressed: _finish,
          child: Text(s.welcomeStart,
            style: TextStyle(color: p.textSub, fontSize: 13))),
        const SizedBox(height: 8),
        _langToggle(context, p),
        const SizedBox(height: 4),
        _dots(0, p),
      ],
    );

  /// One row of the mode card. Mirrors for Arabic so the badge sits on the
  /// leading edge in both languages instead of always on the left.
  Widget _modeRow({
    required NurPalette p,
    required IconData badgeIcon,
    required String badge,
    required Color badgeColor,
    required String title,
    required String body,
    required Color bodyColor,
    required bool ar,
  }) => Row(
    textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      // S255: Material Icons (not emoji) so the badge obeys the palette.
      NurChip(label: badge, color: badgeColor, icon: badgeIcon, fontSize: 10),
      const SizedBox(width: 12),
      Expanded(child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Directionality(
            textDirection: TextDirection.ltr,
            child: Align(
              alignment: AlignmentDirectional.centerStart,
              child: NurChip(label: badge, color: accent, fontSize: 10))),
          const SizedBox(height: 6),
          Text(title,
            textAlign: ar ? TextAlign.right : TextAlign.left,
            style: TextStyle(color: titleColor,
              fontSize: titleSize, fontWeight: FontWeight.w800)),
          const SizedBox(height: 3),
          Text(body,
            textAlign: ar ? TextAlign.right : TextAlign.left,
            style: TextStyle(color: bodyColor, fontSize: 11, height: 1.6)),
        ])),
    ]);

  // ── Page 1: How it works ──────────────────────────────────────────────────
  Widget _page1(S s, NurPalette p) {
    final steps = [
      (Icons.audio_file_outlined,    s.step1),
      (Icons.tune_rounded,           s.step2),
      (Icons.cloud_sync_outlined,    s.step3),
      (Icons.download_done_rounded,  s.step4),
    ];
    // S251: direction follows the selected language.
    final dir = s.ar ? TextDirection.rtl : TextDirection.ltr;
    return _shell(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
      children: [
          GradientText(s.howItWorks,
            gradient: p.goldGradient,
            style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900)),
          const SizedBox(height: 28),
          ...steps.asMap().entries.map((entry) => EntranceFade(
            index: entry.key,
            child: NurCard(
              margin: const EdgeInsets.only(bottom: 12),
              radius: 20,
              padding: const EdgeInsets.all(14),
              child: Row(
                textDirection: dir,
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Container(
                    width: 48, height: 48,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      gradient: LinearGradient(
                        begin: Alignment.topLeft, end: Alignment.bottomRight,
                        colors: [p.gold.withValues(alpha: 0.28),
                                 p.teal.withValues(alpha: 0.14)]),
                      border: Border.all(color: p.gold.withValues(alpha: 0.55))),
                    child: Icon(entry.value.$1, color: p.gold, size: 22)),
                  const SizedBox(width: 14),
                  Expanded(child: Column(
                    crossAxisAlignment: s.ar
                      ? CrossAxisAlignment.end : CrossAxisAlignment.start,
                    children: [
                      Text(
                        s.stepLabel(entry.key + 1),
                        textDirection: dir,
                        style: TextStyle(
                          color: p.teal, fontSize: 10,
                          fontWeight: FontWeight.w700, letterSpacing: 0.6)),
                      const SizedBox(height: 3),
                      Text(entry.value.$2,
                        textDirection: dir,
                        textAlign: s.ar ? TextAlign.right : TextAlign.left,
                        style: TextStyle(
                          color: p.text, fontSize: 13.5, height: 1.45)),
                    ],
                  )),
                ],
              ),
            ))),
          const SizedBox(height: 10),
          NurButton(label: s.welcomeNext, onTap: () => _goPage(2)),
          const SizedBox(height: 4),
          _backBtn(s, 0, p),
          _dots(1, p),
      ],
    );
  }

  // ── Page 2: Engine tiers overview ────────────────────────────────────────
  Widget _page2(S s, NurPalette p) {
    final tiers = [
      ('v10.0', s.ar ? 'الأثيريون — الأساس' : 'Aetherion Foundation',
        s.ar ? '٢٤ إصلاحاً — NR ثنائي — L-BFGS-B'
              : '24 fixes — Two-stage NR — L-BFGS-B EQ',
        p.gold),
      ('v9.0',  s.ar ? 'التطور' : 'The Evolution',
        s.ar ? 'بناء كامل — مُحسِّن مشترك LUFS+LRA'
              : 'Full rewrite — joint LUFS+LRA optimizer',
        p.goldLight),
      ('v8.x',  s.ar ? 'سلسلة الدقة' : 'Precision Series',
        s.ar ? 'v8.7 · v8.5 · v8.0 — تقدم تراكمي'
              : 'v8.7 · v8.5 · v8.0 — cumulative gains',
        p.teal),
      ('v7.0',  s.ar ? 'كلاسيكي' : 'Classic',
        s.ar ? 'البنية المُثبَّتة الأساس — STABLE'
              : 'Proven foundational architecture — STABLE',
        p.info),
    ];
    return _shell(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
      children: [
          GradientText(s.welcomeEngines,
            gradient: p.goldGradient,
            style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900)),
          const SizedBox(height: 8),
          Text(s.welcomeEnginesSub,
            textAlign: TextAlign.center,
            style: TextStyle(color: p.textSub, fontSize: 12.5)),
          const SizedBox(height: 22),
          ...tiers.asMap().entries.map((en) {
            final t = en.value;
            return EntranceFade(
              index: en.key,
              child: NurCard(
                margin: const EdgeInsets.only(bottom: 10),
                radius: 18,
                accent: t.$4,
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                child: Row(children: [
                  NurChip(label: t.$1, color: t.$4, filled: true, fontSize: 11),
                  const SizedBox(width: 12),
                  Expanded(child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(t.$2, style: TextStyle(
                        color: t.$4, fontSize: 13,
                        fontWeight: FontWeight.w700)),
                      const SizedBox(height: 2),
                      Text(t.$3, style: TextStyle(
                        color: p.textSub, fontSize: 11, height: 1.4)),
                    ])),
                ])));
          }),
          const SizedBox(height: 14),
          NurButton(label: s.welcomeStart, onTap: _finish),
          const SizedBox(height: 4),
          _backBtn(s, 1, p),
          _dots(2, p),
      ],
    );
  }

  /// S251: pages 1 and 2 only ever pointed forward — no visible way back.
  Widget _backBtn(S s, int target, NurPalette p) => TextButton.icon(
    onPressed: () => _goPage(target),
    icon: Icon(
      s.ar ? Icons.arrow_forward_rounded : Icons.arrow_back_rounded,
      size: 15, color: p.textSub),
    label: Text(s.welcomeBack,
      style: TextStyle(color: p.textSub, fontSize: 13)));

  Widget _dots(int active, NurPalette p) => Row(
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
          curve: Curves.easeOutCubic,
          width:  i == active ? 22 : 6,
          height: 6,
          decoration: BoxDecoration(
            color: i == active ? p.gold : p.border,
            borderRadius: BorderRadius.circular(3)))))));

  Widget _langToggle(BuildContext context, NurPalette p) {
    final langNotifier = LangProvider.of(context);
    return ValueListenableBuilder<bool>(
      valueListenable: langNotifier,
      builder: (ctx, isAr, _) => GestureDetector(
        onTap: () => LangProvider.toggle(ctx),
        child: NurChip(
          label: isAr ? 'EN' : 'ع',
          icon: Icons.language_rounded,
          color: p.gold,
          fontSize: 13)));
  }
}
