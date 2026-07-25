import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart'; // S31-F1
import 'package:url_launcher/url_launcher.dart';
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

  // ── S31-F2c / S32: theme color helpers ────────────────────────────────────
  bool  _isDark(BuildContext ctx)  => ThemeProvider.isDark(ctx);
  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF020D0C) : const Color(0xFFFAF7EE); // S46-SET
  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF0F2420) : const Color(0xFFF3EED9);
  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF1A4035) : const Color(0xFFD4C99A);
  Color _cText(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFC9D1D9) : const Color(0xFF1A1400);
  Color _cSub(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);
  Color _cDim(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF484F58) : const Color(0xFF8B7B5A);
  Color _cGold(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    final isAr = s.ar;

    final cBg     = _cBg(context);
    final cSub    = _cSub(context);
    final cDim    = _cDim(context);
    final cGold   = _cGold(context);
    return Scaffold(
      backgroundColor: cBg,
      appBar: AppBar(
        title: ShaderMask(
            shaderCallback: (b) => const LinearGradient(
              colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),
            child: Text(s.settings, style: const TextStyle(
              color: Colors.white, fontWeight: FontWeight.bold))),
        backgroundColor: cBg,
        iconTheme: IconThemeData(color: cGold),
        elevation: 0,
        actions: [
          // Language toggle — uses InheritedWidget, instant rebuild
          GestureDetector(
            onTap: () => LangProvider.toggle(context),
            child: Container(
              margin: const EdgeInsets.only(right: 14),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: _isDark(context) ? const Color(0xFF1A1500) : const Color(0xFFF3EED9),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(
                  color: cGold, width: 0.8)),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Text(isAr ? 'EN' : 'ع',
                  style: TextStyle(
                    color: cGold,
                    fontWeight: FontWeight.bold, fontSize: 13)),
                const SizedBox(width: 4),
                Icon(Icons.language,
                  color: cGold, size: 14),
              ]))),
        ]),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ── Language toggle ────────────────────────────────────────────────
          _section(context, s.language),
          Container(
            margin: const EdgeInsets.only(bottom: 18), // S61-LANG-PILL
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFF0A1A10),
                         Color(0xFF061810)]),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: const Color(0xFFD4AF37).withValues(alpha: 0.3))),
            child: Row(children: [
              _langPill(context, s.arabic,  active: isAr,
                onTap: () { if (!isAr) LangProvider.toggle(context); }),
              _langPill(context, s.english, active: !isAr,
                onTap: () { if (isAr) LangProvider.toggle(context); }),
            ])),

          // ── S31-F4b: Dark / Light mode toggle ─────────────────────────────
          _themeTile(context, s),
          const SizedBox(height: 4),
          // ── S31-F1: Show Tutorial button ───────────────────────────────────
          _tutorialTile(context, s),
          const SizedBox(height: 4),
          // ── S237: Local Engine health + cache management ──────────────────
          _section(context, isAr ? 'المحرك المحلي' : 'LOCAL ENGINE'),
          const _LocalEngineHealthCard(),
          const SizedBox(height: 14),
          // ── Target info ────────────────────────────────────────────────────
          Container(
            margin: const EdgeInsets.only(bottom: 20),
            padding: const EdgeInsets.symmetric(
              horizontal: 14, vertical: 10),
            decoration: BoxDecoration( // S61-TARGET
              gradient: const LinearGradient(
                colors: [Color(0xFF061810), Color(0xFF0A2015)]),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: const Color(0xFF1DB898), width: 0.8),
              boxShadow: const [BoxShadow(
                color: Color(0xFF1DB898),
                blurRadius: 12, spreadRadius: 0,
                offset: Offset(0, 0))]),
            child: Text(s.target,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Color(0xFF1DB898),
                fontSize: 11, letterSpacing: 0.5))),

          // ── Engine History ─────────────────────────────────────────────────
          _section(context, s.engineHistory),
          ..._history.map((e) => _eCard(context, e, isAr)),

          // ── About ──────────────────────────────────────────────────────────
          const SizedBox(height: 8),
          _section(context, s.about),
          Container(
            padding: const EdgeInsets.all(18), // S61-ABOUT-CARD
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color(0xFF0A1A10), Color(0xFF061015)]),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: const Color(0xFFD4AF37).withValues(alpha: 0.25)),
              boxShadow: [BoxShadow(
                color: const Color(0xFFD4AF37).withValues(alpha: 0.08),
                blurRadius: 20)]),
            child: Column(children: [
              // Small logo in About
              Container(
                width: 60, height: 60,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  boxShadow: [BoxShadow(
                    color: const Color(0xFFD4AF37).withValues(alpha: 0.2),
                    blurRadius: 12)]),
                child: ClipOval(child: Image.asset(
                  'assets/images/logo.png', fit: BoxFit.cover,
                  errorBuilder: (_,__,___) => Container(
                    color: const Color(0xFF1A1500),
                    child: const Icon(Icons.music_note,
                      color: Color(0xFFD4AF37), size: 30))))),
              const SizedBox(height: 12),
              Text('محسِّن التلاوة', style: TextStyle(
                color: cGold,
                fontWeight: FontWeight.bold, fontSize: 18)),
              const SizedBox(height: 4),
              Text(s.version,
                style: TextStyle(
                  color: cSub, fontSize: 12)),
              const SizedBox(height: 2),
              Text('Yasser Al-Dossari · 1425H',
                style: TextStyle(
                  color: cDim, fontSize: 11)),
            ])),
          // S28: Privacy policy link
          const SizedBox(height: 12),
          GestureDetector(
            onTap: () => launchUrl(
              Uri.parse('https://profound-cactus-00498c.netlify.app/privacy_policy.html'),
              mode: LaunchMode.externalApplication),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                const Icon(Icons.privacy_tip_outlined,
                  color: Color(0xFF484F58), size: 14),
                const SizedBox(width: 6),
                Text(s.privacyPolicy,
                  style: const TextStyle(
                    color: Color(0xFF484F58),
                    fontSize: 12,
                    decoration: TextDecoration.underline,
                    decorationColor: Color(0xFF484F58))),
              ]))),
          const SizedBox(height: 40),
        ],
      ),
    );
  }

  Widget _section(BuildContext ctx, String title) => Padding(
    padding: const EdgeInsets.only(bottom: 8, top: 4),
    child: Text(title, style: TextStyle(
      color: _cSub(ctx), fontSize: 11, letterSpacing: 1.5)));

  // S31-F4b
  Widget _themeTile(BuildContext context, S s) {
    return ValueListenableBuilder<bool>(
      valueListenable: ThemeProvider.of(context),
      builder: (ctx, dark, _) => Container(
        margin: const EdgeInsets.only(bottom: 18),
        decoration: BoxDecoration(
          color: _cCard(ctx),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _cBorder(ctx))),
        child: SwitchListTile(
          secondary: Icon(
            dark ? Icons.dark_mode_rounded : Icons.light_mode_rounded,
            color: const Color(0xFFD4AF37)),
          title: Text(
            s.ar ? 'الوضع الداكن' : 'Dark Mode',
            style: TextStyle(color: _cText(ctx), fontSize: 14)),
          subtitle: Text(
            dark
              ? (s.ar ? 'الوضع الحالي' : 'Currently active')
              : (s.ar ? 'الوضع الفاتح نشط' : 'Light mode active'),
            style: TextStyle(color: _cSub(ctx), fontSize: 11)),
          value: dark,
          activeThumbColor: const Color(0xFFD4AF37),
          onChanged: (_) => ThemeProvider.toggle(ctx),
        ),
      ),
    );
  }

  // S31-F1-btn
  Widget _tutorialTile(BuildContext context, S s) => Container(
    margin: const EdgeInsets.only(bottom: 18),
    decoration: BoxDecoration(
      color: _cCard(context),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: _cBorder(context))),
    child: ListTile(
      leading: const Icon(Icons.play_lesson_rounded,
        color: Color(0xFFD4AF37)),
      title: Text(
        s.ar ? 'عرض شاشة الترحيب' : 'Show Welcome Screen',
        style: TextStyle(color: _cText(context), fontSize: 14)),
      subtitle: Text(
        s.ar ? 'عرض دليل البداية مرة أخرى' : 'Re-show the onboarding guide',
        style: TextStyle(color: _cSub(context), fontSize: 11)),
      trailing: const Icon(Icons.arrow_forward_ios_rounded,
        size: 14, color: Color(0xFF484F58)),
      onTap: () async {
        final prefs = await SharedPreferences.getInstance();
        await prefs.remove('seen_welcome_v3'); // S32
        if (!context.mounted) return;
        Navigator.of(context).pushReplacement(
          PageRouteBuilder(
            pageBuilder: (_, __, ___) => const WelcomeScreen(),
            transitionsBuilder: (_, anim, __, child) =>
                FadeTransition(opacity: anim, child: child),
            transitionDuration: const Duration(milliseconds: 400),
          ));
      },
    ));

  Widget _langPill(BuildContext context, String label,
      {required bool active, required VoidCallback onTap}) =>
    Expanded(child: GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 280),
        curve: Curves.easeOutBack,
        padding: const EdgeInsets.symmetric(vertical: 11),
        decoration: BoxDecoration(
          color: active ? const Color(0xFFD4AF37) : Colors.transparent,
          borderRadius: BorderRadius.circular(10)),
        child: Text(label,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: active ? const Color(0xFF0A0C10) : _cSub(context),
            fontWeight: active ? FontWeight.bold : FontWeight.normal,
            fontSize: 14)))));

  Widget _eCard(BuildContext ctx, _EHist e, bool isAr) {
    Color bc() => e.bc == 'gold' ? const Color(0xFFD4AF37)
        : e.bc == 'green' ? const Color(0xFF3FB950)
        : e.bc == 'blue'  ? const Color(0xFF58A6FF)
        : const Color(0xFF484F58);
    Color bg() => e.bc == 'gold' ? const Color(0xFF1A1200)
        : e.bc == 'green' ? const Color(0xFF0D2015)
        : e.bc == 'blue'  ? const Color(0xFF0D1B2E)
        : const Color(0xFF161B22);

    final isLatest = e.badge == 'LATEST';
    final desc = isAr ? e.ar : e.en;

    final ec = _cCard(ctx);
    final eb = _cBorder(ctx);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isLatest ? const Color(0xFF1A1200) : ec,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isLatest
            ? _cGold(ctx)
            : eb,
          width: isLatest ? 1.2 : 0.8)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(e.v, style: TextStyle(
            color: isLatest ? const Color(0xFFD4AF37) : const Color(0xFFC9D1D9),
            fontWeight: FontWeight.bold, fontSize: 15)),
          const SizedBox(width: 8),
          Expanded(child: Text(e.name,
            style: TextStyle(
              color: _cSub(ctx), fontSize: 12))),
          if (e.badge.isNotEmpty)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(
                color: bg(), borderRadius: BorderRadius.circular(4),
                border: Border.all(color: bc().withValues(alpha: 0.5))),
              child: Text(e.badge, style: TextStyle(
                color: bc(), fontSize: 9, fontWeight: FontWeight.bold))),
          const SizedBox(width: 8),
          Text(e.score, style: TextStyle(
            color: isLatest ? const Color(0xFFD4AF37) : const Color(0xFF8B949E),
            fontSize: 11, fontWeight: FontWeight.bold)),
        ]),
        const SizedBox(height: 8),
        Text(desc,
          textDirection: isAr ? TextDirection.rtl : TextDirection.ltr,
          style: TextStyle(
            color: _cSub(ctx), fontSize: 11, height: 1.5)),
        if (e.rating.isNotEmpty) ...[
          const SizedBox(height: 10),
          Row(children: [
            Text(isAr ? 'تقييم المطوِّر:' : 'Dev Rating:',
              style: const TextStyle(
                color: Color(0xFF484F58), fontSize: 9,
                letterSpacing: 0.5)),
            const SizedBox(width: 6),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: _ratingColor(e.rating).withValues(alpha: 0.12),
                borderRadius: BorderRadius.circular(5),
                border: Border.all(
                  color: _ratingColor(e.rating).withValues(alpha: 0.5))),
              child: Text(e.rating,
                style: TextStyle(
                  color: _ratingColor(e.rating),
                  fontSize: 11, fontWeight: FontWeight.w900,
                  letterSpacing: 1.0))),
          ]),
        ],
      ]));
  }

  Color _ratingColor(String r) {
    if (r.startsWith('S')) return const Color(0xFFD4AF37);
    if (r == 'A+' || r == 'A') return const Color(0xFF3FB950);
    if (r == 'A-') return const Color(0xFF1DB898);
    if (r.startsWith('B')) return const Color(0xFF58A6FF);
    if (r.startsWith('C')) return const Color(0xFF8B949E);
    return const Color(0xFFF85149);
  }
}

class _EHist {
  final String v, name, score, badge, bc, ar, en, rating;
  const _EHist(this.v, this.name, this.score, this.badge, this.bc, this.ar, this.en, [this.rating = '']);
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

  static const _gold = Color(0xFFD4AF37);
  static const _teal = Color(0xFF1DB898);
  static const _red  = Color(0xFFD94040);

  bool get _dark => ThemeProvider.isDark(context);
  Color get _cCard   => _dark ? const Color(0xFF0F2420) : const Color(0xFFF3EED9);
  Color get _cBorder => _dark ? const Color(0xFF1A4035) : const Color(0xFFD4C99A);
  Color get _cText   => _dark ? const Color(0xFFC9D1D9) : const Color(0xFF1A1400);
  Color get _cSub    => _dark ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);

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
    final freed = _fmtBytes((r['freedBytes'] as num?)?.toInt() ?? 0);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      backgroundColor: _cCard, behavior: SnackBarBehavior.floating,
      content: Text('${ar ? "تم تحرير" : "Freed"} $freed',
          style: const TextStyle(color: _teal, fontSize: 12))));
    _refresh();
  }

  Future<void> _repair() async {
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
    final st = _status;
    final bool allCoreOk = st != null &&
        (st['proot'] == true) && (st['python'] == true) &&
        (st['libpython'] == true) && (st['ffmpeg'] == true) &&
        (st['numpy'] == true) && (st['deepFilter'] == true) &&
        ((st['engines'] as num? ?? 0) > 0);

    return Container(
      decoration: BoxDecoration(
        color: _cCard,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: _cBorder)),
      child: Column(children: [
        ListTile(
          leading: Icon(
            st == null ? Icons.dns_outlined
                : allCoreOk ? Icons.check_circle_rounded : Icons.error_outline_rounded,
            color: st == null ? _cSub : allCoreOk ? _teal : _red),
          title: Text(ar ? 'صحة المحرك المحلي' : 'Local Engine Health',
              style: TextStyle(color: _cText, fontSize: 14)),
          subtitle: Text(
            st == null
                ? (_loading ? (ar ? 'جارٍ الفحص…' : 'Checking…')
                            : (ar ? 'تعذر الفحص' : 'Check unavailable'))
                : allCoreOk
                    ? (ar ? 'كل المكونات سليمة ✓' : 'All components healthy ✓')
                    : (ar ? 'يوجد مكون ناقص — انظر التفاصيل' : 'Something is missing — see details'),
            style: TextStyle(color: _cSub, fontSize: 11)),
          trailing: _loading
              ? const SizedBox(width: 16, height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2, color: _gold))
              : IconButton(icon: const Icon(Icons.refresh_rounded, color: _gold, size: 20),
                  onPressed: _refresh),
        ),
        if (st != null) ...[
          Divider(height: 1, color: _cBorder),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 6),
            child: Column(children: [
              _compRow(ar ? 'بيئة العزل proot' : 'proot sandbox',       st['proot'] == true),
              _compRow('Python 3',                                       st['python'] == true && st['libpython'] == true),
              _compRow('ffmpeg',                                         st['ffmpeg'] == true),
              _compRow('numpy',                                          st['numpy'] == true),
              _compRow('scipy',                                          st['scipy'] == true,
                  optional: true, ar: ar),
              _compRow('DeepFilter (aarch64)',                           st['deepFilter'] == true),
              _compRow(ar ? 'محركات المعالجة' : 'Engine scripts',
                  (st['engines'] as num? ?? 0) > 0,
                  detail: '${st['engines'] ?? 0}'),
              _compRow(ar ? 'التلاوات المرجعية' : 'Reference audio',
                  (st['refAudio'] as num? ?? 0) > 0,
                  detail: '${st['refAudio'] ?? 0}'),
            ])),
          Divider(height: 1, color: _cBorder),
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 4),
            child: Column(children: [
              _kvRow(ar ? 'حجم بيئة التشغيل' : 'Runtime size',
                  _fmtBytes((st['runtimeBytes'] as num? ?? 0).toInt())),
              _kvRow(ar ? 'المساحة الحرة' : 'Free space',
                  _fmtBytes((st['freeBytes'] as num? ?? 0).toInt())),
              _kvRow(ar ? 'ملفات العمل المؤقتة' : 'Work cache',
                  '${_fmtBytes((st['cacheBytes'] as num? ?? 0).toInt())} · ${st['cacheFiles'] ?? 0} ${ar ? "ملف" : "files"}'),
            ])),
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 4, 12, 12),
            child: Row(children: [
              Expanded(child: OutlinedButton.icon(
                onPressed: _clearing || ((st['cacheFiles'] as num? ?? 0) == 0) ? null : _clearCache,
                style: OutlinedButton.styleFrom(
                  foregroundColor: _teal, side: BorderSide(color: _teal.withValues(alpha: 0.5)),
                  padding: const EdgeInsets.symmetric(vertical: 10)),
                icon: _clearing
                    ? const SizedBox(width: 13, height: 13,
                        child: CircularProgressIndicator(strokeWidth: 2, color: _teal))
                    : const Icon(Icons.cleaning_services_rounded, size: 15),
                label: Text(ar ? 'تفريغ المؤقت' : 'Clear Cache',
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)))),
              const SizedBox(width: 10),
              Expanded(child: OutlinedButton.icon(
                onPressed: _repair,
                style: OutlinedButton.styleFrom(
                  foregroundColor: _gold, side: BorderSide(color: _gold.withValues(alpha: 0.5)),
                  padding: const EdgeInsets.symmetric(vertical: 10)),
                icon: const Icon(Icons.build_rounded, size: 15),
                label: Text(
                    allCoreOk ? (ar ? 'إعادة الإعداد' : 'Re-run Setup')
                              : (ar ? 'إصلاح الآن' : 'Repair Now'),
                    style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700)))),
            ])),
        ],
      ]));
  }

  Widget _compRow(String label, bool ok,
      {String? detail, bool optional = false, bool ar = false}) =>
    Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(children: [
        Icon(
          ok ? Icons.check_circle_rounded
             : optional ? Icons.remove_circle_outline_rounded : Icons.cancel_rounded,
          color: ok ? _teal : optional ? _cSub : _red, size: 15),
        const SizedBox(width: 8),
        Expanded(child: Text(label, style: TextStyle(color: _cText, fontSize: 12))),
        if (detail != null)
          Text(detail, style: TextStyle(color: _cSub, fontSize: 11, fontFamily: 'monospace'))
        else if (!ok && optional)
          Text(ar ? 'اختياري' : 'optional',
              style: TextStyle(color: _cSub, fontSize: 10)),
      ]));

  Widget _kvRow(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 3),
    child: Row(children: [
      Expanded(child: Text(label, style: TextStyle(color: _cSub, fontSize: 11.5))),
      Text(value, style: TextStyle(color: _cText, fontSize: 11.5,
          fontWeight: FontWeight.w600, fontFamily: 'monospace')),
    ]));
}
