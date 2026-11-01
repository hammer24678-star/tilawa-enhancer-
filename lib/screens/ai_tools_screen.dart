// lib/screens/ai_tools_screen.dart — S184 · S239 v2 · Nur redesign
// AI enhancement tools — "last resort only" warning + links.
// S239: the whole screen was hardcoded Arabic regardless of the app
// language; every string is now fully bilingual (AR/EN via LangProvider),
// tool cards gained English descriptions + risk badges, and a third
// open-source speech-restoration tool (Resemble Enhance) was added.
// Voice/speech tools only — nothing music-related.
// Nur: premium amber warning flow (pulsing badge, glowing banner, risk meters).

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';
import '../design/nur.dart';

// Tool accent colours (static const list below needs compile-time colours).
const _teal   = Color(0xFF2FD4B0);
const _violet = Color(0xFFB88CFF);
const _amber  = Color(0xFFF0A23B);

class AiToolsScreen extends StatelessWidget {
  const AiToolsScreen({super.key});

  static List<_AiTool> _tools(NurPalette p) => [
        _AiTool(
          nameAr: 'Sidon — تحسين الكلام',
          nameEn: 'Sidon Voice Enhancement',
          subEn: 'Hugging Face · academic model',
          descAr:
              'نموذج أكاديمي لتحسين جودة الكلام. مناسب للتسجيلات الهاتفية '
              'الخفيفة. يحتفظ بالصوت بشكل معقول لكنه قد يبتلع بعض الحروف الخفية.',
          descEn:
              'Academic speech-enhancement model. Suitable for lightly degraded '
              'phone recordings. Preserves the voice reasonably well, but can '
              'swallow subtle letters.',
          riskAr: 'خطر متوسط',
          riskEn: 'Medium risk',
          risk: 0.55,
          url: 'https://huggingface.co/spaces/sarulab-speech/sidon_demo_beta',
          icon: Icons.psychology_alt_rounded,
          color: p.teal,
        ),
        _AiTool(
          nameAr: 'Resemble Enhance — ترميم الكلام',
          nameEn: 'Resemble Enhance',
          subEn: 'Hugging Face · open-source restoration',
          descAr:
              'أداة مفتوحة المصدر لإزالة الضوضاء وترميم الكلام على مرحلتين. '
              'نتائجها قوية على التسجيلات القديمة، لكن راجع الحروف الدقيقة بعناية.',
          descEn:
              'Open-source two-stage speech denoise + restoration. Strong on old '
              'recordings, but review the subtle letters carefully afterwards.',
          riskAr: 'خطر متوسط',
          riskEn: 'Medium risk',
          risk: 0.6,
          url: 'https://huggingface.co/spaces/ResembleAI/resemble-enhance',
          icon: Icons.auto_fix_normal_rounded,
          color: p.dark ? const Color(0xFFB88CFF) : const Color(0xFF7A4FD6),
        ),
        _AiTool(
          nameAr: 'Adobe Podcast Enhance',
          nameEn: 'Adobe Podcast Enhance',
          subEn: 'Adobe · cloud service',
          descAr:
              'أداة Adobe لإزالة الضوضاء. قد تكون قوية جداً — خطر تغيير طابع '
              'صوت الشيخ وإفقاده الحيوية حتى يصبح اصطناعياً.',
          descEn:
              'Adobe\'s noise removal. Can be far too aggressive — real risk of '
              'changing the Sheikh\'s voice character until it sounds synthetic.',
          riskAr: 'خطر مرتفع',
          riskEn: 'High risk',
          risk: 0.88,
          url: 'https://podcast.adobe.com/enhance',
          icon: Icons.surround_sound_rounded,
          color: p.warn,
        ),
      ];

  void _open(BuildContext ctx, String url, bool ar) async {
    HapticFeedback.mediumImpact();
    final p = NurPalette.of(ctx);
    if (!await launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication) &&
        ctx.mounted) {
      ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(
        backgroundColor: NurPalette.of(ctx).surfaceHi,
        behavior: SnackBarBehavior.floating,
        content: Text(ar ? 'تعذّر فتح الرابط' : 'Could not open the link',
            style: TextStyle(color: NurPalette.of(ctx).err, fontSize: 12))));
    }
  }

  Widget _warningCard(NurPalette p, bool ar) {
    final intro = ar
        ? 'هذه الأدوات مخصصة فقط للتسجيلات البالغة التلف '
            'التي فشلت فيها كل محركات محسِّن التلاوة.'
        : 'These tools are only for severely damaged '
            'recordings where every Tilawa Enhancer engine '
            'has already failed.';
    final risksHead = ar ? '⚠️  مخاطر الاستخدام:' : '⚠️  Risks of using them:';
    final risks = ar
        ? const [
            'ابتلاع الكلمات — يختفي حرف أو كلمة كاملة',
            'تغيير صوت الشيخ — يصبح اصطناعياً',
            'فقدان التجويد الدقيق والغنة والمدود',
          ]
        : const [
            'Swallowed words — a letter or whole word disappears',
            'The Sheikh\'s voice changes — sounds synthetic',
            'Fine Tajweed detail (ghunnah, madd) gets lost',
          ];
    final adviceHead =
        ar ? '✅  إذا اضطررت للاستخدام:' : '✅  If you must use them:';
    final advice = ar
        ? 'راجع الملف الناتج كلمةً كلمة وأضف يدوياً '
            'أي كلمة مبتلوعة في الملفات التالفة جداً.'
        : 'Review the output word by word, and manually '
            'restore any swallowed word from the damaged original.';

    return NurCard(
      accent: p.warn,
      glow: true,
      padding: const EdgeInsets.all(18),
      gradient: LinearGradient(
        begin: Alignment.topLeft,
        end: Alignment.bottomRight,
        colors: [
          p.warn.withValues(alpha: p.dark ? 0.20 : 0.14),
          p.surface,
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _WarnBadge(color: p.warn),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  ar ? 'الذكاء الاصطناعي — الخيار الأخير' : 'AI — the last resort',
                  style: TextStyle(
                      color: p.warn, fontSize: 16, fontWeight: FontWeight.w800),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          Text(intro,
              style: TextStyle(color: p.text, fontSize: 13, height: 1.65)),
          const SizedBox(height: 14),
          _RisksPanel(head: risksHead, risks: risks),
          const SizedBox(height: 10),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            decoration: BoxDecoration(
              color: p.ok.withValues(alpha: 0.08),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: p.ok.withValues(alpha: 0.30)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(adviceHead,
                    style: TextStyle(
                        color: p.ok, fontSize: 13, fontWeight: FontWeight.w800)),
                const SizedBox(height: 6),
                Text(advice,
                    style: TextStyle(color: p.text, fontSize: 13, height: 1.6)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _noteCard(NurPalette p, bool ar) => NurCard(
        accent: p.gold,
        radius: 18,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('📝  ', style: TextStyle(fontSize: 14)),
            Expanded(
              child: Text(
                ar
                    ? 'ملاحظة من الفريق: لا توجد أداة ذكاء اصطناعي تفهم '
                        'مقامات التلاوة أو أحكام التجويد. محركات محسِّن '
                        'التلاوة مُصممة خصيصاً لهذا. استخدم هذه الأدوات '
                        'فقط حين يكون الصوت بالغ التلف لدرجة أن النتيجة '
                        '"الاصطناعية" أفضل من الصمت.'
                    : 'A note from the team: no AI tool understands '
                        'recitation maqamat or Tajweed rules. The Tilawa '
                        'Enhancer engines were purpose-built for that. '
                        'Reach for these tools only when the audio is so '
                        'damaged that a "synthetic" result beats silence.',
                style: TextStyle(color: p.textSub, fontSize: 12, height: 1.6),
              ),
            ),
          ],
        ),
      );

  @override
  Widget build(BuildContext ctx) {
    final ar = LangProvider.strings(ctx).ar;
    final p = NurPalette.of(ctx);
    // NurScaffold mirrors itself for Arabic (S196-BUG-I: direction follows
    // the app language), so rows here must not flip on their own.
    return NurScaffold(
      title: ar ? 'أدوات الذكاء الاصطناعي' : 'AI Tools',
      icon: Icons.auto_fix_high_rounded,
      accent: p.warn,
      body: ListView(
        physics: const BouncingScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
        children: [

          // ── Warning banner ────────────────────────────────────────────────
          EntranceFade(index: 0, child: NurCard(
            radius: 22,
            accent: p.warn,
            glow: true,
            padding: const EdgeInsets.all(18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(children: [
                  Icon(Icons.warning_amber_rounded, color: p.warn, size: 24),
                  const SizedBox(width: 10),
                  Expanded(child: Text(
                    ar ? 'الذكاء الاصطناعي — الخيار الأخير'
                       : 'AI — the last resort',
                    style: TextStyle(color: p.warn,
                        fontSize: 16, fontWeight: FontWeight.w800))),
                ]),
                const SizedBox(height: 12),
                Text(
                  ar
                    ? 'هذه الأدوات مخصصة فقط للتسجيلات البالغة التلف '
                      'التي فشلت فيها كل محركات محسِّن التلاوة.\n\n'
                      '⚠️  مخاطر الاستخدام:\n'
                      '  • ابتلاع الكلمات — يختفي حرف أو كلمة كاملة\n'
                      '  • تغيير صوت الشيخ — يصبح اصطناعياً\n'
                      '  • فقدان التجويد الدقيق والغنة والمدود\n\n'
                      '✅  إذا اضطررت للاستخدام:\n'
                      '  راجع الملف الناتج كلمةً كلمة وأضف يدوياً '
                      'أي كلمة مبتلوعة في الملفات التالفة جداً.'
                    : 'These tools are only for severely damaged '
                      'recordings where every Tilawa Enhancer engine '
                      'has already failed.\n\n'
                      '⚠️  Risks of using them:\n'
                      '  • Swallowed words — a letter or whole word disappears\n'
                      '  • The Sheikh\'s voice changes — sounds synthetic\n'
                      '  • Fine Tajweed detail (ghunnah, madd) gets lost\n\n'
                      '✅  If you must use them:\n'
                      '  Review the output word by word, and manually '
                      'restore any swallowed word from the damaged original.',
                  style: TextStyle(color: p.text, fontSize: 13, height: 1.65)),
              ]))),

          const SizedBox(height: 14),

          // ── Note from us ──────────────────────────────────────────────────
          EntranceFade(index: 1, child: NurCard(
            radius: 18,
            accent: p.gold,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.edit_note_rounded, color: p.gold, size: 20),
                const SizedBox(width: 10),
                Expanded(child: Text(
                  ar
                    ? 'ملاحظة من الفريق: لا توجد أداة ذكاء اصطناعي تفهم '
                      'مقامات التلاوة أو أحكام التجويد. محركات محسِّن '
                      'التلاوة مُصممة خصيصاً لهذا. استخدم هذه الأدوات '
                      'فقط حين يكون الصوت بالغ التلف لدرجة أن النتيجة '
                      '"الاصطناعية" أفضل من الصمت.'
                    : 'A note from the team: no AI tool understands '
                      'recitation maqamat or Tajweed rules. The Tilawa '
                      'Enhancer engines were purpose-built for that. '
                      'Reach for these tools only when the audio is so '
                      'damaged that a "synthetic" result beats silence.',
                  style: TextStyle(
                      color: p.textSub, fontSize: 12.5, height: 1.6))),
              ]))),

          NurSectionHeader(ar ? 'الأدوات المتاحة' : 'Available tools',
              padding: const EdgeInsets.fromLTRB(4, 24, 4, 12)),

          // ── Tool cards ────────────────────────────────────────────────────
          ..._tools.asMap().entries.map((e) => EntranceFade(
              index: 2 + e.key,
              child: _ToolCard(
                  tool: e.value, ar: ar,
                  onTap: () => _open(ctx, e.value.url, ar)))),

          const SizedBox(height: 20),
          Center(child: Text(
              ar ? 'استخدم بحذر شديد ⚠️' : 'Use with extreme care ⚠️',
              style: TextStyle(
                  color: p.warn.withValues(alpha: 0.6),
                  fontSize: 11, letterSpacing: 0.8))),
        ]),
    );
  }
}

class _ToolCard extends StatelessWidget {
  final _AiTool tool;
  final bool ar;
  final VoidCallback onTap;
  const _ToolCard({required this.tool, required this.ar, required this.onTap});

  @override
  Widget build(BuildContext ctx) {
    final p = NurPalette.of(ctx);
    return NurCard(
      margin: const EdgeInsets.only(bottom: 12),
      radius: 20,
      accent: tool.color,
      onTap: onTap,
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Container(
              width: 42, height: 42,
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(13),
                gradient: LinearGradient(
                  begin: Alignment.topLeft, end: Alignment.bottomRight,
                  colors: [tool.color.withValues(alpha: 0.30),
                           tool.color.withValues(alpha: 0.10)]),
                border: Border.all(color: tool.color.withValues(alpha: 0.45))),
              child: Icon(tool.icon, color: tool.color, size: 21)),
            const SizedBox(width: 12),
            Expanded(child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(ar ? tool.nameAr : tool.nameEn,
                    style: TextStyle(color: tool.color,
                        fontSize: 14, fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text(ar ? tool.nameEn : tool.subEn,
                    style: TextStyle(color: p.textDim, fontSize: 11)),
              ])),
            const SizedBox(width: 8),
            // S239 — risk badge
            NurChip(label: ar ? tool.riskAr : tool.riskEn,
                color: tool.color, fontSize: 10),
          ]),
          const SizedBox(height: 12),
          Text(ar ? tool.descAr : tool.descEn,
              style: TextStyle(color: p.textSub, fontSize: 12.5, height: 1.6)),
          const SizedBox(height: 10),
          Row(children: [
            Icon(Icons.open_in_new_rounded,
                color: tool.color.withValues(alpha: 0.7), size: 14),
            const SizedBox(width: 6),
            Text(ar ? 'فتح في المتصفح' : 'Open in browser',
                style: TextStyle(color: tool.color.withValues(alpha: 0.8),
                    fontSize: 11, fontWeight: FontWeight.w700)),
          ]),
        ]));
  }
}

class _AiTool {
  final String nameAr, nameEn, subEn, descAr, descEn, riskAr, riskEn, url;
  final double risk;
  final IconData icon;
  final Color color;
  const _AiTool({
    required this.nameAr, required this.nameEn, required this.subEn,
    required this.descAr, required this.descEn,
    required this.riskAr, required this.riskEn, required this.risk,
    required this.url, required this.icon, required this.color});
}
