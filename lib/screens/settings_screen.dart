import 'package:flutter/material.dart';
import '../l10n/strings.dart';
import '../main.dart';

class SettingsScreen extends StatelessWidget {
  final S s;
  final VoidCallback onLangToggle;
  const SettingsScreen({super.key, required this.s, required this.onLangToggle});

  // Engine history from v6.0 to v8.0
  static const List<Map<String, String>> _engines = [
    {
      'v': 'v8.0',
      'name': 'Calibrated Precision',
      'score': '≥96/100',
      'badge': 'LATEST',
      'bc': 'gold',
      'ar': 'إصلاح 5 أخطاء في v7.6: bias معكوس، double compand، 5 limiters تراكمية، DR/LRA خطأ نوع، Crest guard ضعيف',
      'en': 'Fixes 5 v7.6 bugs: reversed bias, double compand stacking, 5 cumulative limiters, wrong DR/LRA type, weak Crest guard',
    },
    {
      'v': 'v7.6',
      'name': 'Intelligent Assessment',
      'score': '~94/100',
      'badge': 'MDS',
      'bc': 'blue',
      'ar': 'نظام MDS متعدد المقاييس: SFM + DR + Spectral Distance + Per-Band SNR. تشخيص ذكي مستمر بدل 5 تصنيفات ثنائية',
      'en': 'Multi-metric damage scoring: SFM + DR + Spectral Distance + Per-Band SNR. Continuous 0-100 score instead of 5 binary tiers',
    },
    {
      'v': 'v7.55',
      'name': 'Forensic Fix',
      'score': '~95/100',
      'badge': 'FORENSIC',
      'bc': 'green',
      'ar': 'إصلاح Crest-Aware warmth nodes. LRA target الحقيقي 4.19 (من قياس كامل الملف). SPECTRAL_BIAS_755 محدَّث',
      'en': 'Crest-aware warmth nodes. Real LRA target 4.19 from full-file measurement. Updated SPECTRAL_BIAS_755',
    },
    {
      'v': 'v7.5',
      'name': 'Disciplined Precision',
      'score': '94/100',
      'badge': 'BEST',
      'bc': 'green',
      'ar': 'مبدأ Do-No-Harm. عودة لـ v7.0 compand + 9-segment spectral + Quality Gate. أول نسخة تتجاوز 90 بثبات',
      'en': 'Do-No-Harm principle. Back to v7.0 compand + 9-segment spectral + Quality Gate. First version consistently above 90',
    },
    {
      'v': 'v7.4',
      'name': 'Forensic Precision',
      'score': '~90/100',
      'badge': '',
      'bc': '',
      'ar': 'فشل: upward compand أفسد dynamic range. 4kHz و8kHz boosts عدوانية +12dB. LRA gate رفع LUFS لـ -5.20',
      'en': 'Failed: upward compand ruined dynamic range. Aggressive +12dB boosts at 4kHz/8kHz. LRA gate pushed LUFS to -5.20',
    },
    {
      'v': 'v7.3',
      'name': 'Game Changer',
      'score': '~91/100',
      'badge': '',
      'bc': '',
      'ar': 'تجربة فاشلة: 7 Presence filters + compressors متراكمة + harmonic exciter = تشويه. أسوأ من v7.0',
      'en': 'Failed experiment: 7 presence filters + stacked compressors + harmonic exciter = distortion. Worse than v7.0',
    },
    {
      'v': 'v7.0',
      'name': 'Convergence',
      'score': '~91/100',
      'badge': 'CLASSIC',
      'bc': 'gold',
      'ar': 'THREE-PASS Pipeline. تقارب تكراري حتى score≥97. LRA feedback + RMS feedback. أفضل بنية لم تُعقَّد بعد',
      'en': 'THREE-PASS pipeline. Iterative convergence until score≥97. LRA + RMS feedback. Best unoverengineered architecture',
    },
    {
      'v': 'v6.6',
      'name': 'Scale Fix',
      'score': '~82/100',
      'badge': '',
      'bc': '',
      'ar': 'رفع scale تصحيح الطيف 0.60→0.68. ref_lra الحقيقي 2.26 بدل 4.0 خطأ. Warmth protection أذكى',
      'en': 'Spectral correction scale raised 0.60→0.68. Real ref_lra 2.26 instead of wrong 4.0. Smarter warmth protection',
    },
    {
      'v': 'v6.5',
      'name': 'Stable Reference',
      'score': '~80/100',
      'badge': '',
      'bc': '',
      'ar': 'STABLE FINGERPRINT: median من كل مقاطع المرجع. TILT-BASED WARMTH بدل bass/mid ratio. NR Guard للمصادر <96kbps',
      'en': 'STABLE FINGERPRINT: median from all reference segments. TILT-BASED WARMTH instead of unstable bass/mid ratio. NR Guard for sources <96kbps',
    },
    {
      'v': 'v6.0',
      'name': 'Psychoacoustic Pipeline',
      'score': '~75/100',
      'badge': 'FIRST',
      'bc': 'blue',
      'ar': 'البداية: De-Clipping + A-Weighting + Bark Scale EQ (24 نطاق) + Spectral Subtraction + Two-Pass LUFS. أساس كل شيء',
      'en': 'The beginning: De-Clipping + A-Weighting + Bark Scale EQ (24 bands) + Spectral Subtraction + Two-Pass LUFS. Foundation of everything',
    },
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0A0C10),
      appBar: AppBar(
        title: Text(s.settings,
          style: const TextStyle(color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF0A0C10),
        iconTheme: const IconThemeData(color: Color(0xFFD4AF37)),
        elevation: 0,
        actions: [
          // Language toggle in AppBar
          GestureDetector(
            onTap: () { onLangToggle(); },
            child: Container(
              margin: const EdgeInsets.only(right: 16),
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: const Color(0xFF1A1500),
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFFD4AF37), width: 0.8)),
              child: Text(s.isArabic ? 'EN' : 'ع',
                style: const TextStyle(
                  color: Color(0xFFD4AF37),
                  fontWeight: FontWeight.bold, fontSize: 13)),
            ),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // ── Language ─────────────────────────────────────────
          _sectionHeader(s.language),
          Container(
            margin: const EdgeInsets.only(bottom: 16),
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFF21262D))),
            child: Row(children: [
              _langBtn(context, s.arabic,   isActive: s.isArabic,  onTap: () { if (!s.isArabic)  onLangToggle(); }),
              _langBtn(context, s.english,  isActive: !s.isArabic, onTap: () { if (s.isArabic)   onLangToggle(); }),
            ]),
          ),

          // ── Target ────────────────────────────────────────────
          Container(
            margin: const EdgeInsets.only(bottom: 20),
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: const Color(0xFF0D2015),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFF3FB950).withOpacity(0.4))),
            child: Text(s.target,
              textAlign: TextAlign.center,
              style: const TextStyle(color: Color(0xFF3FB950), fontSize: 11))),

          // ── Engine History ────────────────────────────────────
          _sectionHeader(s.enginesHistory),
          ..._engines.map((e) => _engineCard(e, s)),

          // ── About ─────────────────────────────────────────────
          const SizedBox(height: 8),
          _sectionHeader(s.about),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF161B22),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: const Color(0xFF21262D))),
            child: Column(crossAxisAlignment: CrossAxisAlignment.center, children: [
              const Text('محسِّن التلاوة',
                style: TextStyle(
                  color: Color(0xFFD4AF37),
                  fontWeight: FontWeight.bold, fontSize: 18)),
              const SizedBox(height: 4),
              Text(s.version,
                style: const TextStyle(color: Color(0xFF8B949E), fontSize: 12)),
              const SizedBox(height: 4),
              const Text('Yasser Al-Dossari · 1425H',
                style: TextStyle(color: Color(0xFF484F58), fontSize: 11)),
            ])),
          const SizedBox(height: 40),
        ],
      ),
    );
  }

  Widget _sectionHeader(String title) => Padding(
    padding: const EdgeInsets.only(bottom: 10, top: 4),
    child: Text(title,
      style: const TextStyle(
        color: Color(0xFF8B949E), fontSize: 11, letterSpacing: 1.5)),
  );

  Widget _langBtn(BuildContext ctx, String label,
      {required bool isActive, required VoidCallback onTap}) =>
    Expanded(child: GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          color: isActive ? const Color(0xFFD4AF37) : Colors.transparent,
          borderRadius: BorderRadius.circular(10)),
        child: Text(label,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: isActive ? const Color(0xFF0A0C10) : const Color(0xFF8B949E),
            fontWeight: isActive ? FontWeight.bold : FontWeight.normal,
            fontSize: 14)),
      ),
    ));

  Widget _engineCard(Map<String, String> e, S s) {
    final bc = e['bc'] ?? '';
    final badgeColor = bc == 'gold' ? const Color(0xFFD4AF37)
        : bc == 'green' ? const Color(0xFF3FB950)
        : bc == 'blue' ? const Color(0xFF58A6FF)
        : const Color(0xFF484F58);
    final badgeBg = bc == 'gold' ? const Color(0xFF1A1200)
        : bc == 'green' ? const Color(0xFF0D2015)
        : bc == 'blue' ? const Color(0xFF0D1B2E)
        : const Color(0xFF161B22);
    final desc = s.isArabic ? (e['ar'] ?? '') : (e['en'] ?? '');
    final isLatest = e['badge'] == 'LATEST';

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: isLatest ? const Color(0xFF1A1200) : const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isLatest ? const Color(0xFFD4AF37) : const Color(0xFF21262D),
          width: isLatest ? 1.2 : 0.8)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(e['v']!,
            style: TextStyle(
              color: isLatest ? const Color(0xFFD4AF37) : const Color(0xFFC9D1D9),
              fontWeight: FontWeight.bold, fontSize: 15)),
          const SizedBox(width: 8),
          Expanded(child: Text(e['name']!,
            style: const TextStyle(color: Color(0xFF8B949E), fontSize: 12))),
          if ((e['badge'] ?? '').isNotEmpty)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(
                color: badgeBg, borderRadius: BorderRadius.circular(4),
                border: Border.all(color: badgeColor.withOpacity(0.5))),
              child: Text(e['badge']!,
                style: TextStyle(
                  color: badgeColor, fontSize: 9, fontWeight: FontWeight.bold))),
          const SizedBox(width: 8),
          Text(e['score']!,
            style: TextStyle(
              color: isLatest ? const Color(0xFFD4AF37) : const Color(0xFF8B949E),
              fontSize: 11, fontWeight: FontWeight.bold)),
        ]),
        const SizedBox(height: 8),
        Text(desc,
          textDirection: s.isArabic ? TextDirection.rtl : TextDirection.ltr,
          style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11, height: 1.5)),
      ]),
    );
  }
}

extension on S {
  bool get isArabic => ar;
}
