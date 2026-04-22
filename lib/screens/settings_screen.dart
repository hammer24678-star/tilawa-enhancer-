import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart'; // S31-F1
import 'package:url_launcher/url_launcher.dart';
import '../state/lang_provider.dart';
import '../main.dart' show ThemeProvider; // S31-F4b
import 'welcome_screen.dart'; // S31-F1

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  static const _history = [
        _EHist('v8.4','Source Tier Intelligence','≥98/100','LATEST','gold',
      'يحلِّل جودة المصدر: يكشف تردد قطع الكودك، نوع الضوضاء، والقطع. يضبط NR والـ EQ بناءً على التصنيف.',
      'Analyzes source quality: detects codec cutoff, noise type, clipping. Adapts NR, EQ, LRA per tier.'),
_EHist('v8.1','Android-Hardened','≥98/100','','gold',
      'إصلاح خطأ حرج في v8.0: مسار /tmp غير متاح على أندرويد — يستخدم الآن مجلد عمل آمن عبر tempfile. كل مزايا v8.0 محتفظة.',
      'Critical fix from v8.0: /tmp path inaccessible on Android — now uses safe tempfile workdir. All v8.0 improvements preserved.'),
    _EHist('v8.0','Calibrated Precision','≥96/100','','gold',
      'إصلاح 5 أخطاء: SPECTRAL_BIAS معكوس، double compand، 5 limiters تراكمية، خطأ DR/LRA، Crest guard ضعيف',
      'Fixes 5 v7.6 bugs: reversed bias, double compand stacking, 5 cumulative limiters, wrong DR/LRA type, weak Crest guard'),
    _EHist('v7.6','Intelligent Assessment','~94/100','MDS','blue',
      'نظام MDS: SFM + DR + Spectral Distance + Per-Band SNR. تشخيص مستمر 0-100 بدل 5 تصنيفات',
      'MDS system: SFM + DR + Spectral Distance + Per-Band SNR. Continuous 0-100 score instead of 5 binary tiers'),
    _EHist('v7.55','Forensic Fix','~95/100','','green',
      'Crest-aware warmth nodes. LRA target الحقيقي 4.19 من قياس كامل الملف. SPECTRAL_BIAS_755 محدَّث',
      'Crest-aware warmth nodes. True LRA target 4.19 from full-file measurement. Updated SPECTRAL_BIAS_755'),
    _EHist('v7.5','Disciplined Precision','94/100','BEST','green',
      'مبدأ Do-No-Harm. v7.0 compand + 9-segment spectral + Quality Gate. أول نسخة تتجاوز 90 بثبات',
      'Do-No-Harm principle. v7.0 compand + 9-segment spectral + Quality Gate. First consistently above 90'),
    _EHist('v7.4','Forensic Precision','~90/100','','',
      'فشل: upward compand أفسد dynamic range. +12dB عدوانية 4kHz/8kHz. LRA gate رفع LUFS لـ -5.20',
      'Failed: upward compand ruined dynamic range. Aggressive +12dB at 4kHz/8kHz. LRA gate pushed LUFS to -5.20'),
    _EHist('v7.3','Game Changer','~91/100','','',
      '7 Presence filters + compressors متراكمة + harmonic exciter = تشويه. أسوأ من v7.0',
      '7 presence filters + stacked compressors + harmonic exciter = distortion. Worse than v7.0'),
    _EHist('v7.0','Convergence','~91/100','CLASSIC','gold',
      'THREE-PASS Pipeline. تقارب تكراري حتى score≥97. LRA + RMS feedback. أفضل بنية غير معقدة',
      'THREE-PASS pipeline. Iterative convergence until score≥97. LRA + RMS feedback. Best clean architecture'),
    _EHist('v6.6','Scale Fix','~82/100','','',
      'scale تصحيح الطيف 0.60→0.68. ref_lra الحقيقي 2.26. Warmth protection أذكى',
      'Spectral correction scale 0.60→0.68. Real ref_lra 2.26. Smarter warmth protection'),
    _EHist('v6.5','Stable Reference','~80/100','','',
      'STABLE FINGERPRINT: median من كل المقاطع. TILT-BASED WARMTH. NR Guard <96kbps',
      'STABLE FINGERPRINT: median from all segments. TILT-BASED WARMTH. NR Guard for <96kbps sources'),
    _EHist('v6.0','Psychoacoustic Pipeline','~75/100','FIRST','blue',
      'البداية: De-Clipping + A-Weighting + Bark Scale EQ (24 نطاق) + Two-Pass LUFS. أساس كل شيء',
      'The beginning: De-Clipping + A-Weighting + Bark Scale EQ (24 bands) + Two-Pass LUFS. The foundation'),
  ];

  // ── S31-F2c / S32: theme color helpers ────────────────────────────────────
  bool  _isDark(BuildContext ctx)  => ThemeProvider.isDark(ctx);
  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);
  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);
  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);
  Color _cText(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFC9D1D9) : const Color(0xFF1A1400);
  Color _cSub(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);
  Color _cDim(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF484F58) : const Color(0xFF8B7B5A);
  Color _cGold(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    final isAr = s.ar;

    final cBg     = _cBg(context);
    final cCard   = _cCard(context);
    final cBorder = _cBorder(context);
    final cText   = _cText(context);
    final cSub    = _cSub(context);
    final cDim    = _cDim(context);
    final cGold   = _cGold(context);
    return Scaffold(
      backgroundColor: cBg,
      appBar: AppBar(
        title: Text(s.settings, style: TextStyle(
          color: cGold, fontWeight: FontWeight.bold)),
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
            margin: const EdgeInsets.only(bottom: 18),
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: cCard,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: cBorder)),
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
          // ── Target info ────────────────────────────────────────────────────
          Container(
            margin: const EdgeInsets.only(bottom: 20),
            padding: const EdgeInsets.symmetric(
              horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: const Color(0xFF0A1A0F),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(
                color: const Color(0xFF3FB950).withOpacity(0.35))),
            child: Text(s.target,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Color(0xFF3FB950), fontSize: 11))),

          // ── Engine History ─────────────────────────────────────────────────
          _section(context, s.engineHistory),
          ..._history.map((e) => _eCard(context, e, isAr)),

          // ── About ──────────────────────────────────────────────────────────
          const SizedBox(height: 8),
          _section(context, s.about),
          Container(
            padding: const EdgeInsets.all(18),
            decoration: BoxDecoration(
              color: cCard,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: cBorder)),
            child: Column(children: [
              // Small logo in About
              Container(
                width: 60, height: 60,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  boxShadow: [BoxShadow(
                    color: const Color(0xFFD4AF37).withOpacity(0.2),
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
          color: _cCard(context),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: _cBorder(context))),
        child: SwitchListTile(
          secondary: Icon(
            dark ? Icons.dark_mode_rounded : Icons.light_mode_rounded,
            color: const Color(0xFFD4AF37)),
          title: Text(
            s.ar ? 'الوضع الداكن' : 'Dark Mode',
            style: TextStyle(color: _cText(context), fontSize: 14)),
          subtitle: Text(
            dark
              ? (s.ar ? 'الوضع الحالي' : 'Currently active')
              : (s.ar ? 'الوضع الفاتح نشط' : 'Light mode active'),
            style: TextStyle(color: _cSub(context), fontSize: 11)),
          value: dark,
          activeColor: const Color(0xFFD4AF37),
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
        await prefs.remove('seen_welcome_v2'); // S32
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
        duration: const Duration(milliseconds: 200),
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

    final _ec = _cCard(ctx);
    final _eb = _cBorder(ctx);
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isLatest ? const Color(0xFF1A1200) : _ec,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isLatest
            ? _cGold(ctx)
            : _eb,
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
                border: Border.all(color: bc().withOpacity(0.5))),
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
      ]));
  }
}

class _EHist {
  final String v, name, score, badge, bc, ar, en;
  const _EHist(this.v, this.name, this.score, this.badge, this.bc, this.ar, this.en);
}
