import 'package:flutter/material.dart';
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
  late final AnimationController _waveCtrl;
  late final AnimationController _glowCtrl;
  int _page = 0;
  int _dir = 1; // +1 moving forward, -1 moving back (drives the slide)
  int _mode = 0; // 0 = local card highlighted, 1 = server (visual only)

  @override
  void initState() {
    super.initState();
    _waveCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 8))
      ..repeat();
    _glowCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2400))
      ..repeat(reverse: true);
  }

  @override
  void dispose() {
    _waveCtrl.dispose();
    _glowCtrl.dispose();
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
    final ar = s.ar;
    return PopScope(
      // S251: system back used to leave the app from page 1 or 2, because
      // the pages are internal state rather than routes. Back now walks the
      // onboarding backwards and only exits from the first page.
      canPop: _page == 0,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) _goPage(_page - 1);
      },
      child: Directionality(
        textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
        child: Scaffold(
          backgroundColor: p.bg,
          body: NurBackdrop(
            accent: _page == 2 ? p.gold : p.teal,
            child: SafeArea(
              child: Column(children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
                  child: Align(
                    alignment: AlignmentDirectional.centerEnd,
                    child: _langToggle(p, ar))),
                Expanded(
                  child: AnimatedSwitcher(
                    duration: const Duration(milliseconds: 420),
                    switchInCurve: Curves.easeOutCubic,
                    switchOutCurve: Curves.easeInCubic,
                    transitionBuilder: (child, anim) {
                      final entering = child.key == ValueKey<int>(_page);
                      final dx = 0.12 * _dir * (ar ? -1 : 1) *
                          (entering ? 1 : -1);
                      return FadeTransition(
                        opacity: anim,
                        child: SlideTransition(
                          position: Tween<Offset>(
                            begin: Offset(dx, 0), end: Offset.zero)
                              .animate(anim),
                          child: child));
                    },
                    child: _page == 0
                        ? _page0(s, p)
                        : _page == 1 ? _page1(s, p) : _page2(s, p),
                  ),
                ),
                _dots(p),
                const SizedBox(height: 6),
              ]),
            ),
          ),
        ),
      ),
    );
  }

  /// Every page scrolls when taller than the viewport (short screens, large
  /// text scale) and stays vertically centred when it is not.
  Widget _shell(int page, {required List<Widget> children}) =>
    LayoutBuilder(
      key: ValueKey<int>(page),
      builder: (_, box) => SingleChildScrollView(
        child: ConstrainedBox(
          constraints: BoxConstraints(minHeight: box.maxHeight),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 480),
              child: Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 24, vertical: 12),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: children,
                )))))));

  // ── Page 0: Brand splash ──────────────────────────────────────────────────
  Widget _page0(S s, NurPalette p) {
    final w = MediaQuery.of(context).size.width;
    final orb = (w * 0.56).clamp(150.0, 210.0).toDouble();
    final logo = orb * 0.42;
    return _shell(0, children: [
      EntranceFade(
        offsetY: 24,
        duration: const Duration(milliseconds: 700),
        child: Center(
          child: TweenAnimationBuilder<double>(
            tween: Tween<double>(begin: 0.8, end: 1.0),
            duration: const Duration(milliseconds: 1100),
            curve: Curves.easeOutBack,
            builder: (_, v, child) => Transform.scale(scale: v, child: child),
            child: NurOrb(
              animation: _waveCtrl,
              size: orb,
              energy: 0.55,
              a: p.teal,
              b: p.goldLight,
              child: AnimatedBuilder(
                animation: _glowCtrl,
                builder: (_, child) => Transform.scale(
                  scale: 0.96 + 0.06 * _glowCtrl.value, child: child),
                child: Container(
                  width: logo, height: logo,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: p.gold.withValues(alpha: 0.55), width: 1.5)),
                  child: ClipOval(
                    child: Image.asset('assets/images/logo.png',
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Container(
                        color: p.surface,
                        child: Icon(Icons.music_note,
                          color: p.gold, size: logo * 0.5)))))))))),
      const SizedBox(height: 22),
      EntranceFade(
        index: 1,
        child: GradientText(s.appName,
          gradient: p.goldGradient,
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 38, fontWeight: FontWeight.w900,
            height: 1.2, letterSpacing: -0.5))),
      const SizedBox(height: 6),
      EntranceFade(
        index: 2,
        child: Text(s.subtitle,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: p.textSub, fontSize: 11, letterSpacing: 2.0))),
      const SizedBox(height: 20),
      EntranceFade(
        index: 3,
        child: Text(s.welcomeDesc,
          textAlign: TextAlign.center,
          style: TextStyle(color: p.text, fontSize: 14, height: 1.8))),
      const SizedBox(height: 22),
      EntranceFade(
        index: 4,
        child: _modeCard(s, p)),
      const SizedBox(height: 22),
      EntranceFade(
        index: 5,
        child: NurButton(
          label: s.howItWorks,
          icon: s.ar ? Icons.arrow_back_rounded : Icons.arrow_forward_rounded,
          onTap: () => _goPage(1))),
      const SizedBox(height: 10),
      EntranceFade(
        index: 6,
        child: NurButton(
          label: s.welcomeStart,
          filled: false,
          accent: p.textSub,
          onTap: _finish)),
    ]);
  }

  Widget _modeCard(S s, NurPalette p) => Column(children: [
    _modeTile(
      selected: _mode == 0,
      accent: p.teal,
      icon: Icons.phone_android_rounded,
      badge: 'LOCAL',
      title: s.localModeEngines,
      body: s.localModeDesc,
      p: p,
      onTap: () {
        HapticFeedback.selectionClick();
        setState(() => _mode = 0);
      }),
    const SizedBox(height: 10),
    _modeTile(
      selected: _mode == 1,
      accent: p.gold,
      icon: Icons.cloud_outlined,
      badge: 'SERVER',
      title: 'v10.0 · v9.0 · v8.5 · v8.0',
      body: s.serverModeDesc,
      p: p,
      onTap: () {
        HapticFeedback.selectionClick();
        setState(() => _mode = 1);
      }),
  ]);

  Widget _modeTile({
    required bool selected,
    required Color accent,
    required IconData icon,
    required String badge,
    required String title,
    required String body,
    required NurPalette p,
    required VoidCallback onTap,
  }) => NurCard(
    selected: selected,
    accent: accent,
    radius: 18,
    padding: const EdgeInsets.all(14),
    onTap: onTap,
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOutCubic,
        width: 40, height: 40,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: accent.withValues(alpha: selected ? 0.22 : 0.08),
          border: Border.all(
            color: accent.withValues(alpha: selected ? 0.8 : 0.3))),
        child: AnimatedScale(
          scale: selected ? 1.12 : 1.0,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOutBack,
          child: Icon(icon, size: 19, color: accent))),
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
            style: TextStyle(
              color: selected ? accent : p.text,
              fontSize: 13, fontWeight: FontWeight.w700)),
          const SizedBox(height: 3),
          Text(body,
            style: TextStyle(color: p.textSub, fontSize: 11, height: 1.6)),
        ])),
    ]));

  // ── Page 1: How it works ──────────────────────────────────────────────────
  Widget _page1(S s, NurPalette p) {
    final steps = [
      (Icons.audio_file_outlined,    s.step1),
      (Icons.tune_rounded,           s.step2),
      (Icons.cloud_sync_outlined,    s.step3),
      (Icons.download_done_rounded,  s.step4),
    ];
    return _shell(1, children: [
      EntranceFade(
        child: GradientText(s.howItWorks,
          gradient: p.goldGradient,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900))),
      const SizedBox(height: 24),
      for (var i = 0; i < steps.length; i++)
        EntranceFade(
          index: i + 1,
          child: Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: NurCard(
              radius: 18,
              padding: const EdgeInsets.all(14),
              child: Row(children: [
                Container(
                  width: 46, height: 46,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: p.goldGradient),
                  child: Icon(steps[i].$1, color: p.onGold, size: 22)),
                const SizedBox(width: 14),
                Expanded(child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(s.stepLabel(i + 1),
                      style: TextStyle(
                        color: p.gold, fontSize: 10,
                        fontWeight: FontWeight.w700, letterSpacing: 0.6)),
                    const SizedBox(height: 3),
                    Text(steps[i].$2,
                      style: TextStyle(
                        color: p.text, fontSize: 13, height: 1.45)),
                  ])),
              ])))),
      const SizedBox(height: 10),
      EntranceFade(
        index: 5,
        child: NurButton(
          label: s.welcomeNext,
          icon: s.ar ? Icons.arrow_back_rounded : Icons.arrow_forward_rounded,
          onTap: () => _goPage(2))),
      const SizedBox(height: 10),
      EntranceFade(index: 6, child: _backBtn(s, p, 0)),
    ]);
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
        p.teal),
      ('v8.x',  s.ar ? 'سلسلة الدقة' : 'Precision Series',
        s.ar ? 'v8.7 · v8.5 · v8.0 — تقدم تراكمي'
              : 'v8.7 · v8.5 · v8.0 — cumulative gains',
        p.info),
      ('v7.0',  s.ar ? 'كلاسيكي' : 'Classic',
        s.ar ? 'البنية المُثبَّتة الأساس — STABLE'
              : 'Proven foundational architecture — STABLE',
        p.textSub),
    ];
    return _shell(2, children: [
      EntranceFade(
        child: GradientText(s.welcomeEngines,
          gradient: p.goldGradient,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900))),
      const SizedBox(height: 8),
      EntranceFade(
        index: 1,
        child: Text(s.welcomeEnginesSub,
          textAlign: TextAlign.center,
          style: TextStyle(color: p.textSub, fontSize: 12))),
      const SizedBox(height: 20),
      for (var i = 0; i < tiers.length; i++)
        EntranceFade(
          index: i + 2,
          child: Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: NurCard(
              radius: 16,
              accent: tiers[i].$4,
              glow: i == 0,
              padding: const EdgeInsets.symmetric(
                horizontal: 14, vertical: 12),
              child: Row(children: [
                Directionality(
                  textDirection: TextDirection.ltr,
                  child: NurChip(
                    label: tiers[i].$1,
                    color: tiers[i].$4,
                    filled: true,
                    fontSize: 11)),
                const SizedBox(width: 12),
                Expanded(child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(tiers[i].$2,
                      style: TextStyle(
                        color: tiers[i].$4, fontSize: 13,
                        fontWeight: FontWeight.w700)),
                    const SizedBox(height: 2),
                    Text(tiers[i].$3,
                      style: TextStyle(
                        color: p.textSub, fontSize: 11, height: 1.4)),
                  ])),
              ])))),
      const SizedBox(height: 8),
      EntranceFade(
        index: 6,
        child: NurButton(
          label: s.welcomeStart,
          icon: Icons.check_rounded,
          onTap: _finish)),
      const SizedBox(height: 10),
      EntranceFade(index: 7, child: _backBtn(s, p, 1)),
    ]);
  }

  /// S251: pages 1 and 2 only ever pointed forward — a visible way back.
  Widget _backBtn(S s, NurPalette p, int target) => NurButton(
    label: s.welcomeBack,
    icon: s.ar ? Icons.arrow_forward_rounded : Icons.arrow_back_rounded,
    filled: false,
    accent: p.textSub,
    onTap: () => _goPage(target));

  Widget _dots(NurPalette p) => Row(
    mainAxisAlignment: MainAxisAlignment.center,
    children: List.generate(3, (i) {
      final on = i == _page;
      return GestureDetector(
        onTap: () => _goPage(i),
        behavior: HitTestBehavior.opaque,
        // The dot stays 6px tall; the padding makes a real tap target.
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 12),
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 350),
            curve: Curves.easeOutCubic,
            width: on ? 24 : 6,
            height: 6,
            decoration: BoxDecoration(
              gradient: on ? p.goldGradient : null,
              color: on ? null : p.border,
              borderRadius: BorderRadius.circular(3),
              boxShadow: on
                ? [BoxShadow(
                    color: p.gold.withValues(alpha: 0.5), blurRadius: 8)]
                : const []))));
    }));

  Widget _langToggle(NurPalette p, bool ar) => PressScale(
    onTap: () => LangProvider.toggle(context),
    child: Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: p.surface.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: p.border)),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text(ar ? 'EN' : 'ع',
          style: TextStyle(
            color: p.gold, fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(width: 6),
        Icon(Icons.language, color: p.textSub, size: 16),
      ])));
}
