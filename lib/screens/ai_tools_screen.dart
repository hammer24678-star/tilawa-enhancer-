// lib/screens/ai_tools_screen.dart — S184 · S239 v2
// AI enhancement tools — "last resort only" warning + links.
// S239: the whole screen was hardcoded Arabic regardless of the app
// language; every string is now fully bilingual (AR/EN via LangProvider),
// tool cards gained English descriptions + risk badges, and a third
// open-source speech-restoration tool (Resemble Enhance) was added.
// Voice/speech tools only — nothing music-related.

import 'package:flutter/material.dart';
import '../state/lang_provider.dart'; // S196-BUG-I (S198-BUG-1: fixed path)
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

const _bg      = Color(0xFF020D0C);
const _card    = Color(0xFF0F2420);
const _gold    = Color(0xFFD4AF37);
const _teal    = Color(0xFF1DB898);
const _violet  = Color(0xFFB88CFF);
const _textA   = Color(0xFFE2CFA0);
const _textB   = Color(0xFF8AACBA);
const _border  = Color(0xFF1B3A35);
const _amber   = Color(0xFFE8A020);
const _amberDk = Color(0xFF2A1800);
const _red     = Color(0xFFD94040);
const _redDk   = Color(0xFF3D0808);

class AiToolsScreen extends StatelessWidget {
  const AiToolsScreen({super.key});

  static const _tools = [
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
      riskAr: 'خطر متوسط', riskEn: 'Medium risk',
      url: 'https://huggingface.co/spaces/sarulab-speech/sidon_demo_beta',
      icon: Icons.psychology_alt_rounded,
      color: _teal,
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
      riskAr: 'خطر متوسط', riskEn: 'Medium risk',
      url: 'https://huggingface.co/spaces/ResembleAI/resemble-enhance',
      icon: Icons.auto_fix_normal_rounded,
      color: _violet,
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
      riskAr: 'خطر مرتفع', riskEn: 'High risk',
      url: 'https://podcast.adobe.com/enhance',
      icon: Icons.surround_sound_rounded,
      color: _amber,
    ),
  ];

  void _open(BuildContext ctx, String url, bool ar) async {
    HapticFeedback.mediumImpact();
    if (!await launchUrl(Uri.parse(url),
            mode: LaunchMode.externalApplication) &&
        ctx.mounted) {
      ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(
        backgroundColor: _redDk,
        content: Text(ar ? 'تعذّر فتح الرابط' : 'Could not open the link',
            style: const TextStyle(color: _red, fontSize: 12))));
    }
  }

  @override
  Widget build(BuildContext ctx) {
    final ar = LangProvider.strings(ctx).ar;
    return Directionality(
      // S196-BUG-I: derive direction from app language (not hardcoded RTL)
      textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
      child: Scaffold(
        backgroundColor: _bg,
        body: SafeArea(child: Column(children: [

          // ── App bar ──────────────────────────────────────────────────────
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: _border, width: 0.8))),
            child: Row(children: [
              IconButton(
                icon: const Icon(Icons.arrow_back_ios_new_rounded,
                    size: 18, color: _textB),
                onPressed: () => Navigator.pop(ctx)),
              const SizedBox(width: 4),
              const Icon(Icons.auto_fix_high_rounded, color: _amber, size: 18),
              const SizedBox(width: 8),
              Text(ar ? 'أدوات الذكاء الاصطناعي' : 'AI Tools',
                  style: const TextStyle(color: _textA,
                      fontSize: 16, fontWeight: FontWeight.w700)),
            ])),

          Expanded(child: SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [

                // ── Warning banner ──────────────────────────────────────────
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: _amberDk,
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                        color: _amber.withValues(alpha: 0.55), width: 1.2),
                    boxShadow: [BoxShadow(
                        color: _amber.withValues(alpha: 0.12), blurRadius: 24)]),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(children: [
                        const Icon(Icons.warning_amber_rounded,
                            color: _amber, size: 22),
                        const SizedBox(width: 10),
                        Expanded(child: Text(
                          ar ? 'الذكاء الاصطناعي — الخيار الأخير'
                             : 'AI — the last resort',
                          style: const TextStyle(color: _amber,
                              fontSize: 15, fontWeight: FontWeight.w800))),
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
                        style: const TextStyle(
                            color: _textA, fontSize: 13, height: 1.65)),
                    ])),

                const SizedBox(height: 14),

                // ── Note from us ──────────────────────────────────────────
                Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 14, vertical: 12),
                  decoration: BoxDecoration(
                    color: const Color(0xFF06101A),
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(
                        color: _gold.withValues(alpha: 0.20), width: 0.8)),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('📝  ', style: TextStyle(fontSize: 14)),
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
                        style: const TextStyle(
                            color: _textB, fontSize: 12, height: 1.6))),
                    ])),

                const SizedBox(height: 20),
                Text(ar ? 'الأدوات المتاحة' : 'Available tools',
                    style: const TextStyle(color: _textB,
                        fontSize: 12, letterSpacing: 0.5)),
                const SizedBox(height: 10),

                // ── Tool cards ─────────────────────────────────────────────
                ..._tools.map((t) => _ToolCard(
                    tool: t, ar: ar, onTap: () => _open(ctx, t.url, ar))),

                const SizedBox(height: 24),
                Center(child: Text(
                    ar ? 'استخدم بحذر شديد ⚠️' : 'Use with extreme care ⚠️',
                    style: TextStyle(
                        color: _amber.withValues(alpha: 0.50),
                        fontSize: 11, letterSpacing: 0.8))),
                const SizedBox(height: 8),
              ]),
          )),
        ])),
      ),
    );
  }
}

class _ToolCard extends StatelessWidget {
  final _AiTool tool;
  final bool ar;
  final VoidCallback onTap;
  const _ToolCard({required this.tool, required this.ar, required this.onTap});

  @override
  Widget build(BuildContext ctx) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: Material(
      color: _card,
      borderRadius: BorderRadius.circular(12),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        splashColor: tool.color.withValues(alpha: 0.12),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            border: Border.all(
                color: tool.color.withValues(alpha: 0.28))),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(children: [
                Container(
                  padding: const EdgeInsets.all(8),
                  decoration: BoxDecoration(
                    color: tool.color.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(8)),
                  child: Icon(tool.icon, color: tool.color, size: 20)),
                const SizedBox(width: 12),
                Expanded(child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(ar ? tool.nameAr : tool.nameEn,
                        style: TextStyle(color: tool.color,
                            fontSize: 14, fontWeight: FontWeight.w700)),
                    Text(ar ? tool.nameEn : tool.subEn,
                        style: const TextStyle(
                            color: _textB, fontSize: 10)),
                  ])),
                // S239 — risk badge
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: tool.color.withValues(alpha: 0.10),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(color: tool.color.withValues(alpha: 0.4))),
                  child: Text(ar ? tool.riskAr : tool.riskEn,
                      style: TextStyle(color: tool.color, fontSize: 9,
                          fontWeight: FontWeight.w800))),
                const SizedBox(width: 8),
                Icon(Icons.open_in_new_rounded,
                    color: tool.color.withValues(alpha: 0.55), size: 16),
              ]),
              const SizedBox(height: 10),
              Text(ar ? tool.descAr : tool.descEn,
                  style: const TextStyle(
                      color: _textA, fontSize: 12, height: 1.55)),
            ])),
      ),
    ),
  );
}

class _AiTool {
  final String nameAr, nameEn, subEn, descAr, descEn, riskAr, riskEn, url;
  final IconData icon;
  final Color color;
  const _AiTool({
    required this.nameAr, required this.nameEn, required this.subEn,
    required this.descAr, required this.descEn,
    required this.riskAr, required this.riskEn, required this.url,
    required this.icon, required this.color});
}
