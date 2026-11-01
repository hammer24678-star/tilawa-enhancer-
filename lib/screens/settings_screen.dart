import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart'; // S31-F1
import 'package:url_launcher/url_launcher.dart';
import '../design/nur.dart';
import '../services/local_engine_service.dart'; // S237
import '../state/lang_provider.dart';
import '../main.dart' show ThemeProvider; // S31-F4b
import 'setup_screen.dart'; // S237
import 'welcome_screen.dart'; // S31-F1

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  static const _history = [
    _EHist('v11.0','الصفاء — Purity','≥ 99.5/100','LATEST','gold',
      'محرك إزالة صدى المساجد. يجمع دي-ريفِرب وWPE وDF3 NR رباعي الفئات وJALAA على مرحلتين وTail-NR ثلاثي المراحل، مع حارس عربي يحافظ على أحكام التجويد كاملةً. يُخرج WAV مباشرة دون أي اتصال بالخادم.',
      'Mosque-echo dereverberation engine. Combines WPE, 4-class DF3 noise reduction, 2-pass JALAA, and 3-stage tail-NR with a Tajweed phonology guard. Outputs WAV directly — no server round-trip.',
      'S+'),
    _EHist('v11.1','الإتقان — Perfection','≥ 99/100','','gold',
      'تسعة مراحل متتالية للتسجيلات النظيفة. يعمل بـ 48 حزمة طيفية مع محسِّن L-BFGS-B لضبط الـ EQ. يحمي مناطق الفورمانت بحدٍّ ±2dB. أفضل محرك للتسجيلات عالية الجودة.',
      '9-phase pipeline for pristine sources. Operates on 48 spectral bands with L-BFGS-B optimizer for EQ. Protects formant zones with ±2dB cap. Best engine for high-quality recordings.',
      'S'),
    _EHist('v11.2','الاسترداد — Recovery','≥ 98/100','','gold',
      'مخصَّص للتسجيلات التالفة والحرجة. يكشف ثلاثة أنواع من التلف (A/B/C) ويعالج كلاً منها بمسار مختلف. يشمل إزالة القطع وتوسيع النطاق الترددي وإعادة بناء الطيف. الخيار الأول لمسجلات الجوامع والأشرطة القديمة.',
      'Built for damaged and critical recordings. Detects three damage types (A/B/C) and treats each with a dedicated path. Includes declipping, BWE, and spectrum reconstruction. First choice for mosque recordings and old cassettes.',
      'S-'),
    _EHist('v9.0','The Evolution','≥ 99/100','LATEST','gold',
      'إعادة كتابة كاملة من الصفر: 1,890 سطراً. لأول مرة يُطبَّق NR دائماً قبل EQ. محسِّن LUFS+LRA مشترك بدل منفصل. ناقلات ثقة مستقلة لكل معامل. أقوى محرك مستقل.',
      'Complete rewrite from scratch: 1,890 lines. NR always applied before EQ for the first time. Joint LUFS+LRA optimizer instead of separate. Independent confidence vectors per parameter. Most powerful standalone engine.',
      'S'),
    _EHist('v8.5','Tier-Adjusted Scoring','≥ 99/100','DEFAULT','gold',
      'كل فئة مصدر تحصل على أوزان MDS وأسقف Crest/LRA/LUFS خاصة بها. حذف اختراق 64K_FLOOR الذي كان يرفع النتيجة زوراً. أول محرك يقيس بدقة حقيقية.',
      'Each source tier gets its own MDS weights and Crest/LRA/LUFS ceilings. Removed 64K_FLOOR hack that falsely inflated scores. First engine to measure with true accuracy.',
      'A+'),
    _EHist('v8.4','Source Tier Intelligence','≥ 98/100','LATEST','gold',
      'أول محرك يحلِّل جودة المصدر قبل المعالجة: يكشف تردد قطع الكودك، ونوع الضوضاء، والقطع. يضبط NR والـ EQ بناءً على التصنيف. مفتاح تطوُّر سلسلة v8.',
      'First engine to analyze source quality before processing: detects codec cutoff, noise type, clipping. Adapts NR and EQ based on classification. The key breakthrough of the v8 series.',
      'A'),
    _EHist('v8.1','Android-Hardened','≥ 98/100','','gold',
      'إصلاح حرج: مسار /tmp لا يعمل على أندرويد. يستخدم الآن مجلد عمل آمن عبر tempfile. كل مزايا v8.0 محتفظة. الفرق الوحيد: يعمل.',
      'Critical fix: /tmp path fails on Android. Now uses safe tempfile workdir. All v8.0 features preserved. Only difference: it actually works on Android.',
      'A'),
    _EHist('v8.0','Calibrated Precision','≥ 96/100','','gold',
      'أصلح 5 أخطاء متراكمة من v7.6: SPECTRAL_BIAS معكوس، compand مضاعف، 5 limiters متراكمة، خطأ DR/LRA، حراسة Crest ضعيفة. خطوة نظافة ضرورية.',
      'Fixed 5 bugs inherited from v7.6: reversed bias, double compand, 5 stacked limiters, wrong DR/LRA, weak Crest guard. A necessary cleanup step.',
      'A-'),
    _EHist('v7.6','Intelligent Assessment','~94/100','MDS','blue',
      'ثورة في القياس: نظام MDS يجمع SFM + DR + Spectral Distance + Per-Band SNR في نتيجة مستمرة 0-100 بدل 5 تصنيفات ثنائية. الأساس الذي بُني عليه كل شيء بعده.',
      'A measurement revolution: MDS system combines SFM + DR + Spectral Distance + Per-Band SNR into a continuous 0-100 score instead of 5 binary tiers. The foundation everything after was built on.',
      'B+'),
    _EHist('v7.55','Forensic Fix','~95/100','','green',
      'warmth nodes مرتبطة بـ Crest. هدف LRA الحقيقي 4.19 مقاساً من الملف كاملاً. تحديث SPECTRAL_BIAS_755. إصلاحات دقيقة لكن أثرها محسوس.',
      'Crest-aware warmth nodes. True LRA target 4.19 measured from full file. Updated SPECTRAL_BIAS_755. Small fixes with noticeable impact.',
      'B+'),
    _EHist('v7.5','Disciplined Precision','94/100','BEST','green',
      'مبدأ Do-No-Harm: لأول مرة يتوقف المحرك عن المعالجة إذا كانت ستضر. 9 شرائح طيفية. Quality Gate. أول نسخة تتجاوز 90 بثبات. اللحظة التي نضجت فيها الفكرة.',
      'Do-No-Harm principle: first time the engine stops processing if it would cause harm. 9 spectral segments. Quality Gate. First version consistently above 90. The moment the concept matured.',
      'B'),
    _EHist('v7.4','Forensic Precision','~90/100','FAIL','',
      'فشل: upward compand دمَّر النطاق الديناميكي. +12dB عدوانية عند 4kHz/8kHz. LRA gate رفع LUFS إلى -5.20. مثال على أن الإضافة بلا ضبط تؤدي إلى عكس المطلوب.',
      'Failed: upward compand destroyed dynamic range. Aggressive +12dB at 4kHz/8kHz. LRA gate pushed LUFS to -5.20. A lesson that adding without calibration achieves the opposite.',
      'F'),
    _EHist('v7.3','Overengineered','~91/100','FAIL','',
      'فشل: 7 فلاتر presence + compressors متراكمة + harmonic exciter = تشويه كامل. أسوأ من v7.0. درس آخر في الأقل أحياناً أكثر.',
      'Failed: 7 presence filters + stacked compressors + harmonic exciter = complete distortion. Worse than v7.0. Another lesson that less is sometimes more.',
      'D'),
    _EHist('v7.0','Convergence','~91/100','CLASSIC','gold',
      'أول بنية ناضجة: THREE-PASS Pipeline مع تقارب تكراري حتى score≥97. LRA + RMS feedback. البنية الأنظف والأبسط في كل تاريخ المشروع. الأساس الحقيقي.',
      'First mature architecture: THREE-PASS Pipeline with iterative convergence until score≥97. LRA + RMS feedback. The cleanest and simplest architecture in the entire project history. The true foundation.',
      'B'),
    _EHist('v6.6','Scale Fix','~82/100','','',
      'تصحيح scale الطيف من 0.60 إلى 0.68. ref_lra الحقيقي 2.26. warmth protection أذكى. تحسين صغير لكنه صحيح.',
      'Spectral correction scale fix 0.60→0.68. Real ref_lra 2.26. Smarter warmth protection. Small but correct improvement.',
      'C+'),
    _EHist('v6.5','Stable Reference','~80/100','','',
      'STABLE FINGERPRINT: median من كل المقاطع. TILT-BASED WARMTH. NR Guard للمصادر أقل من 96kbps. أول محاولة جدية للاستقرار.',
      'STABLE FINGERPRINT: median from all segments. TILT-BASED WARMTH. NR Guard for <96kbps sources. First serious attempt at stability.',
      'C'),
  ];

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    final isAr = s.ar;
    final p = NurPalette.of(context);

    var i = 0;
    Widget fade(Widget w) => EntranceFade(index: i++, child: w);

    return NurScaffold(
      title: s.settings,
      icon: Icons.settings_rounded,
      actions: [
        // Language quick toggle — uses InheritedWidget, instant rebuild
        PressScale(
          onTap: () => LangProvider.toggle(context),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
            decoration: BoxDecoration(
              color: p.gold.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: p.gold.withValues(alpha: 0.55))),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Text(isAr ? 'EN' : 'ع',
                style: TextStyle(
                  color: p.gold, fontWeight: FontWeight.w800, fontSize: 13)),
              const SizedBox(width: 5),
              Icon(Icons.language_rounded, color: p.gold, size: 15),
            ]))),
      ],
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 40),
        children: [
          // ── Language toggle ────────────────────────────────────────────────
          fade(_header(s.language)),
          fade(NurCard(
            padding: const EdgeInsets.all(12),
            child: NurSegmented(
              items: [
                NurSegment(s.arabic, Icons.translate_rounded),
                NurSegment(s.english, Icons.language_rounded),
              ],
              index: isAr ? 0 : 1,
              onChanged: (idx) {
                final wantAr = idx == 0;
                if (wantAr != isAr) LangProvider.toggle(context);
              }))),

          // ── S31-F4b: Dark / Light mode toggle ─────────────────────────────
          fade(_header(isAr ? 'المظهر' : 'APPEARANCE')),
          fade(_themeTile(context, s)),
          const SizedBox(height: 12),
          // ── S31-F1: Show Tutorial button ───────────────────────────────────
          fade(_tutorialTile(context, s)),

          // ── S237: Local Engine health + cache management ──────────────────
          fade(_header(isAr ? 'المحرك المحلي' : 'LOCAL ENGINE')),
          fade(const _LocalEngineHealthCard()),
          const SizedBox(height: 14),
          // ── Target info ────────────────────────────────────────────────────
          fade(NurCard(
            accent: p.teal,
            glow: true,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            child: Row(children: [
              Icon(Icons.track_changes_rounded, color: p.teal, size: 20),
              const SizedBox(width: 12),
              Expanded(child: Text(s.target,
                style: TextStyle(
                  color: p.teal, fontSize: 12, height: 1.4,
                  fontWeight: FontWeight.w600, letterSpacing: 0.3))),
            ]))),

          // ── Engine History ─────────────────────────────────────────────────
          fade(_header(s.engineHistory)),
          for (var k = 0; k < _history.length; k++)
            fade(_HistoryCard(
              entry: _history[k], isAr: isAr, initiallyOpen: k == 0)),

          // ── About ──────────────────────────────────────────────────────────
          fade(_header(s.about)),
          fade(NurCard(
            accent: p.gold,
            glow: true,
            padding: const EdgeInsets.all(20),
            child: Column(children: [
              TweenAnimationBuilder<double>(
                tween: Tween<double>(begin: 0.7, end: 1.0),
                duration: const Duration(milliseconds: 700),
                curve: Curves.easeOutBack,
                builder: (_, v, child) => Transform.scale(scale: v, child: child),
                child: Container(
                  width: 64, height: 64,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(color: p.gold.withValues(alpha: 0.6), width: 1.5),
                    boxShadow: [BoxShadow(
                      color: p.gold.withValues(alpha: 0.28), blurRadius: 22)]),
                  child: ClipOval(child: Image.asset(
                    'assets/images/logo.png', fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => Container(
                      color: p.surface,
                      child: Icon(Icons.music_note_rounded,
                        color: p.gold, size: 30)))))),
              const SizedBox(height: 14),
              GradientText('محسِّن التلاوة',
                gradient: p.goldGradient,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  fontWeight: FontWeight.w800, fontSize: 20)),
              const SizedBox(height: 6),
              Text(s.version,
                textAlign: TextAlign.center,
                style: TextStyle(color: p.textSub, fontSize: 12)),
              const SizedBox(height: 2),
              Text('Yasser Al-Dossari · 1425H',
                textAlign: TextAlign.center,
                style: TextStyle(color: p.textDim, fontSize: 11)),
            ]))),
          // S28: Privacy policy link
          const SizedBox(height: 14),
          fade(NurButton(
            label: s.privacyPolicy,
            icon: Icons.privacy_tip_outlined,
            filled: false,
            accent: p.textSub,
            height: 46,
            onTap: () => launchUrl(
              Uri.parse('https://profound-cactus-00498c.netlify.app/privacy_policy.html'),
              mode: LaunchMode.externalApplication))),
        ],
      ),
    );
  }

  Widget _header(String title) => NurSectionHeader(title,
    padding: const EdgeInsets.fromLTRB(4, 22, 4, 12));

  // S31-F4b
  Widget _themeTile(BuildContext context, S s) {
    return ValueListenableBuilder<bool>(
      valueListenable: ThemeProvider.of(context),
      builder: (ctx, dark, _) {
        final p = NurPalette.of(ctx);
        return NurCard(
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            NurOptionRow(
              icon: dark ? Icons.dark_mode_rounded : Icons.light_mode_rounded,
              active: true,
              title: s.ar ? 'الوضع الداكن' : 'Dark Mode',
              subtitle: dark
                ? (s.ar ? 'الوضع الحالي' : 'Currently active')
                : (s.ar ? 'الوضع الفاتح نشط' : 'Light mode active'),
              trailing: AnimatedSwitcher(
                duration: const Duration(milliseconds: 350),
                transitionBuilder: (child, anim) => RotationTransition(
                  turns: Tween<double>(begin: 0.85, end: 1.0).animate(anim),
                  child: FadeTransition(opacity: anim, child: child)),
                child: Icon(
                  dark ? Icons.nightlight_round : Icons.wb_sunny_rounded,
                  key: ValueKey<bool>(dark),
                  color: p.gold, size: 24))),
            const SizedBox(height: 14),
            NurSegmented(
              items: [
                NurSegment(s.ar ? 'نهاري' : 'Day', Icons.wb_sunny_rounded),
                NurSegment(s.ar ? 'ليلي' : 'Night', Icons.nightlight_round),
              ],
              index: dark ? 1 : 0,
              onChanged: (idx) {
                if ((idx == 1) != dark) ThemeProvider.toggle(ctx);
              }),
          ]));
      },
    );
  }

  // S31-F1-btn
  Widget _tutorialTile(BuildContext context, S s) => NurCard(
    onTap: () => _showTutorial(context),
    child: NurOptionRow(
      icon: Icons.play_lesson_rounded,
      title: s.ar ? 'عرض شاشة الترحيب' : 'Show Welcome Screen',
      subtitle: s.ar ? 'عرض دليل البداية مرة أخرى' : 'Re-show the onboarding guide',
      trailing: Icon(Icons.arrow_forward_ios_rounded,
        size: 14, color: NurPalette.of(context).textDim,
        matchTextDirection: true)));

  Future<void> _showTutorial(BuildContext context) async {
    final prefs = await SharedPreferences.getInstance();
    // S251: this cleared seen_welcome_v3, but main.dart has read
    // seen_welcome_v5 since S108 — so "Show Welcome Screen" pushed the
    // screen once and the app still skipped it on the next cold start.
    await prefs.remove('seen_welcome_v5');
    if (!context.mounted) return;
    Navigator.of(context).pushReplacement(
      PageRouteBuilder(
        pageBuilder: (_, __, ___) => const WelcomeScreen(),
        transitionsBuilder: (_, anim, __, child) =>
            FadeTransition(opacity: anim, child: child),
        transitionDuration: const Duration(milliseconds: 400),
      ));
  }
}

/// One engine-history entry: a card that expands to show its description.
class _HistoryCard extends StatefulWidget {
  final _EHist entry;
  final bool isAr;
  final bool initiallyOpen;
  const _HistoryCard({
    required this.entry, required this.isAr, required this.initiallyOpen});
  @override
  State<_HistoryCard> createState() => _HistoryCardState();
}

class _HistoryCardState extends State<_HistoryCard> {
  late bool _open = widget.initiallyOpen;

  Color _badgeColor(NurPalette p, String bc) =>
      bc == 'gold' ? p.gold
      : bc == 'green' ? p.ok
      : bc == 'blue' ? p.info
      : p.textDim;

  Color _ratingColor(NurPalette p, String r) {
    if (r.startsWith('S')) return p.gold;
    if (r == 'A+' || r == 'A') return p.ok;
    if (r == 'A-') return p.teal;
    if (r.startsWith('B')) return p.info;
    if (r.startsWith('C')) return p.textSub;
    return p.err;
  }

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final e = widget.entry;
    final isAr = widget.isAr;
    final isLatest = e.badge == 'LATEST';
    final desc = isAr ? e.ar : e.en;
    final bc = _badgeColor(p, e.bc);

    final details = Column(
      key: const ValueKey<String>('open'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 12),
        Text(desc, style: TextStyle(
          color: p.textSub, fontSize: 12, height: 1.6)),
        if (e.rating.isNotEmpty) ...[
          const SizedBox(height: 12),
          Wrap(
            spacing: 8, runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(isAr ? 'تقييم المطوِّر:' : 'Dev Rating:',
                style: TextStyle(
                  color: p.textDim, fontSize: 11, letterSpacing: 0.5)),
              NurChip(
                label: e.rating,
                color: _ratingColor(p, e.rating),
                filled: true,
                fontSize: 12),
            ]),
        ],
      ]);

    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: NurCard(
        accent: isLatest ? p.gold : p.teal,
        selected: isLatest,
        radius: 18,
        padding: const EdgeInsets.all(14),
        onTap: () => setState(() => _open = !_open),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            isLatest
              ? GradientText(e.v,
                  gradient: p.goldGradient,
                  style: const TextStyle(
                    fontWeight: FontWeight.w800, fontSize: 16))
              : Text(e.v, style: TextStyle(
                  color: p.text, fontWeight: FontWeight.w800, fontSize: 16)),
            const SizedBox(width: 10),
            Expanded(child: Text(e.name,
              maxLines: 2, overflow: TextOverflow.ellipsis,
              style: TextStyle(color: p.textSub, fontSize: 12.5))),
            const SizedBox(width: 8),
            AnimatedRotation(
              turns: _open ? 0.5 : 0.0,
              duration: const Duration(milliseconds: 300),
              curve: Curves.easeOutCubic,
              child: Icon(Icons.keyboard_arrow_down_rounded,
                color: p.textDim, size: 22)),
          ]),
          const SizedBox(height: 8),
          Wrap(spacing: 8, runSpacing: 6, children: [
            if (e.badge.isNotEmpty)
              NurChip(label: e.badge, color: bc, fontSize: 10),
            NurChip(
              label: e.score,
              color: isLatest ? p.gold : p.textSub,
              icon: Icons.bolt_rounded,
              fontSize: 11),
          ]),
          AnimatedSize(
            duration: const Duration(milliseconds: 320),
            curve: Curves.easeOutCubic,
            alignment: Alignment.topCenter,
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 260),
              switchInCurve: Curves.easeOut,
              switchOutCurve: Curves.easeIn,
              child: _open
                ? details
                : const SizedBox(
                    key: ValueKey<String>('closed'),
                    width: double.infinity)),
          ),
        ])));
  }
}

class _EHist {
  final String v, name, score, badge, bc, ar, en, rating;
  const _EHist(this.v, this.name, this.score, this.badge, this.bc, this.ar, this.en, [this.rating = '']);
}

class _Comp {
  final String label;
  final bool ok;
  final bool optional;
  final String? detail;
  const _Comp(this.label, this.ok, {this.optional = false, this.detail});
}

// ── S237: Local Engine health panel ──────────────────────────────────────────
// Component-by-component diagnostics for the proot local engine, plus cache
// size + one-tap cleanup and a direct entry into setup/repair. Before this,
// the only signal a user ever got was a binary "setup required" — with no way
// to see WHICH piece (numpy? DeepFilter? ffmpeg?) was actually broken, and no
// way to reclaim the work files that accumulated in the engine cache.
class _LocalEngineHealthCard extends StatefulWidget {
  const _LocalEngineHealthCard();
  @override State<_LocalEngineHealthCard> createState() => _LocalEngineHealthCardState();
}

class _LocalEngineHealthCardState extends State<_LocalEngineHealthCard> {
  Map<String, dynamic>? _status;
  bool _loading  = false;
  bool _clearing = false;

  @override
  void initState() {
    super.initState();
    _refresh();
  }

  Future<void> _refresh() async {
    if (_loading) return;
    setState(() => _loading = true);
    final st = await LocalEngineService.getSetupStatus();
    if (!mounted) return;
    setState(() { _status = st.isEmpty ? null : st; _loading = false; });
  }

  Future<void> _clearCache() async {
    final ar = LangProvider.strings(context).ar;
    if (_clearing) return;
    setState(() => _clearing = true);
    final r = await LocalEngineService.clearEngineCache();
    if (!mounted) return;
    setState(() => _clearing = false);
    final p = NurPalette.of(context);
    final freed = _fmtBytes((r['freedBytes'] as num?)?.toInt() ?? 0);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      backgroundColor: p.surface, behavior: SnackBarBehavior.floating,
      content: Text('${ar ? "تم تحرير" : "Freed"} $freed',
          style: TextStyle(color: p.teal, fontSize: 12))));
    _refresh();
  }

  /// Deliberate re-extraction, for a rootfs that has gone bad. This is the one
  /// place SetupScreen is still reachable from, and it stays: it is a repair
  /// tool, not the ordinary path.
  ///
  /// S258: but it must not start a second extraction over a directory the
  /// automatic first-launch run is still writing into. If preparation is in
  /// flight, say so and leave it alone.
  Future<void> _repair() async {
    if (LocalEngineService.preparationRunning) {
      final ar = LangProvider.strings(context).ar;
      final pct = (LocalEngineService.preparationProgress['pct'] as num?)?.toInt() ?? 0;
      if (!mounted) return;
      final p = NurPalette.of(context);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        backgroundColor: p.surface, behavior: SnackBarBehavior.floating,
        content: Text(
            ar ? 'التجهيز جارٍ بالفعل… $pct٪' : 'Preparation is already running… $pct%',
            style: TextStyle(color: p.gold, fontSize: 12))));
      return;
    }
    await Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => SetupScreen(
            onDone: () => Navigator.of(context).pop(),
            onSkip: () => Navigator.of(context).pop())));
    _refresh();
  }

  static String _fmtBytes(int b) {
    if (b >= 1073741824) return '${(b / 1073741824).toStringAsFixed(1)} GB';
    if (b >= 1048576)    return '${(b / 1048576).toStringAsFixed(0)} MB';
    if (b >= 1024)       return '${(b / 1024).toStringAsFixed(0)} KB';
    return '$b B';
  }

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    final ar = s.ar;
    final p = NurPalette.of(context);
    final st = _status;
    final bool allCoreOk = st != null &&
        (st['proot'] == true) && (st['python'] == true) &&
        (st['libpython'] == true) && (st['ffmpeg'] == true) &&
        (st['numpy'] == true) && (st['deepFilter'] == true) &&
        ((st['engines'] as num? ?? 0) > 0);

    final Color statusColor =
        st == null ? p.textDim : allCoreOk ? p.ok : p.err;
    final IconData statusIcon = st == null
        ? Icons.dns_outlined
        : allCoreOk ? Icons.check_circle_rounded : Icons.error_outline_rounded;
    final String subtitle = st == null
        ? (_loading ? (ar ? 'جارٍ الفحص…' : 'Checking…')
                    : (ar ? 'تعذر الفحص' : 'Check unavailable'))
        : allCoreOk
            ? (ar ? 'كل المكونات سليمة ✓' : 'All components healthy ✓')
            : (ar ? 'يوجد مكون ناقص — انظر التفاصيل' : 'Something is missing — see details');

    return NurCard(
      accent: statusColor,
      glow: allCoreOk,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 300),
            width: 44, height: 44,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: statusColor.withValues(alpha: 0.14),
              border: Border.all(color: statusColor.withValues(alpha: 0.5))),
            child: AnimatedSwitcher(
              duration: const Duration(milliseconds: 350),
              transitionBuilder: (child, anim) =>
                  ScaleTransition(scale: anim, child: child),
              child: Icon(statusIcon,
                key: ValueKey<IconData>(statusIcon),
                color: statusColor, size: 24))),
          const SizedBox(width: 12),
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(ar ? 'صحة المحرك المحلي' : 'Local Engine Health',
                style: TextStyle(
                  color: p.text, fontSize: 14.5, fontWeight: FontWeight.w700)),
              const SizedBox(height: 2),
              AnimatedSwitcher(
                duration: const Duration(milliseconds: 250),
                child: Text(subtitle,
                  key: ValueKey<String>(subtitle),
                  style: TextStyle(color: p.textSub, fontSize: 11.5, height: 1.3))),
            ])),
          const SizedBox(width: 8),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 250),
            child: _loading
              ? SizedBox(
                  key: const ValueKey<String>('loading'),
                  width: 38, height: 38,
                  child: Center(child: SizedBox(width: 18, height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2, color: p.gold))))
              : NurIconButton(
                  key: const ValueKey<String>('refresh'),
                  icon: Icons.refresh_rounded,
                  color: p.gold,
                  size: 38,
                  onTap: _refresh)),
        ]),
        AnimatedSize(
          duration: const Duration(milliseconds: 380),
          curve: Curves.easeOutCubic,
          alignment: Alignment.topCenter,
          child: st == null
            ? const SizedBox(width: double.infinity)
            : _details(st, ar, p, allCoreOk)),
      ]));
  }

  Widget _details(Map<String, dynamic> st, bool ar, NurPalette p, bool allCoreOk) {
    final comps = <_Comp>[
      _Comp(ar ? 'بيئة العزل proot' : 'proot sandbox', st['proot'] == true),
      _Comp('Python 3', st['python'] == true && st['libpython'] == true),
      _Comp('ffmpeg', st['ffmpeg'] == true),
      _Comp('numpy', st['numpy'] == true),
      _Comp('scipy', st['scipy'] == true, optional: true),
      _Comp('DeepFilter (aarch64)', st['deepFilter'] == true),
      _Comp(ar ? 'محركات المعالجة' : 'Engine scripts',
          (st['engines'] as num? ?? 0) > 0, detail: '${st['engines'] ?? 0}'),
      _Comp(ar ? 'التلاوات المرجعية' : 'Reference audio',
          (st['refAudio'] as num? ?? 0) > 0, detail: '${st['refAudio'] ?? 0}'),
    ];
    final required = comps.where((c) => !c.optional).toList();
    final okCount = required.where((c) => c.ok).length;
    final ratio = required.isEmpty ? 0.0 : okCount / required.length;

    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      const SizedBox(height: 16),
      NurProgressBar(
        value: ratio, height: 6,
        a: allCoreOk ? p.teal : p.warn,
        b: allCoreOk ? p.goldLight : p.err),
      const SizedBox(height: 6),
      Align(
        alignment: AlignmentDirectional.centerEnd,
        child: Text('$okCount / ${required.length}',
          style: TextStyle(
            color: p.textDim, fontSize: 10.5, fontFamily: 'monospace'))),
      const SizedBox(height: 8),
      for (var k = 0; k < comps.length; k++)
        EntranceFade(index: k, offsetY: 8, child: _compRow(comps[k], ar, p)),
      const SizedBox(height: 10),
      Container(height: 1, color: p.border),
      const SizedBox(height: 10),
      _kvRow(ar ? 'حجم بيئة التشغيل' : 'Runtime size',
          _fmtBytes((st['runtimeBytes'] as num? ?? 0).toInt()), p),
      _kvRow(ar ? 'المساحة الحرة' : 'Free space',
          _fmtBytes((st['freeBytes'] as num? ?? 0).toInt()), p),
      _kvRow(ar ? 'ملفات العمل المؤقتة' : 'Work cache',
          '${_fmtBytes((st['cacheBytes'] as num? ?? 0).toInt())} · ${st['cacheFiles'] ?? 0} ${ar ? "ملف" : "files"}', p),
      const SizedBox(height: 14),
      NurButton(
        label: ar ? 'تفريغ المؤقت' : 'Clear Cache',
        icon: Icons.cleaning_services_rounded,
        filled: false,
        accent: p.teal,
        height: 46,
        loading: _clearing,
        onTap: _clearing || ((st['cacheFiles'] as num? ?? 0) == 0) ? null : _clearCache),
      const SizedBox(height: 10),
      NurButton(
        label: allCoreOk ? (ar ? 'إعادة الإعداد' : 'Re-run Setup')
                         : (ar ? 'إصلاح الآن' : 'Repair Now'),
        icon: Icons.build_rounded,
        filled: !allCoreOk,
        accent: p.gold,
        height: 46,
        onTap: _repair),
    ]);
  }

  Widget _compRow(_Comp c, bool ar, NurPalette p) {
    final Color col = c.ok ? p.ok : c.optional ? p.textDim : p.err;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Icon(
          c.ok ? Icons.check_circle_rounded
               : c.optional ? Icons.remove_circle_outline_rounded : Icons.cancel_rounded,
          color: col, size: 16),
        const SizedBox(width: 10),
        Expanded(child: Text(c.label,
          style: TextStyle(color: p.text, fontSize: 12.5))),
        if (c.detail != null)
          Text(c.detail!, style: TextStyle(
            color: p.textSub, fontSize: 11, fontFamily: 'monospace'))
        else if (!c.ok && c.optional)
          Text(ar ? 'اختياري' : 'optional',
              style: TextStyle(color: p.textDim, fontSize: 10.5)),
      ]));
  }

  Widget _kvRow(String label, String value, NurPalette p) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 3),
    child: Row(children: [
      Expanded(child: Text(label, style: TextStyle(color: p.textSub, fontSize: 11.5))),
      const SizedBox(width: 8),
      Flexible(child: Text(value,
        textAlign: TextAlign.end,
        style: TextStyle(color: p.text, fontSize: 11.5,
            fontWeight: FontWeight.w600, fontFamily: 'monospace'))),
    ]));
}
