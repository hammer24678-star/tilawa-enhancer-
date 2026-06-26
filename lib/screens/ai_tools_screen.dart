// lib/screens/ai_tools_screen.dart — S184
// AI enhancement tools — "last resort only" warning + links

import 'package:flutter/material.dart';
import '../state/lang_provider.dart'; // S196-BUG-I (S198-BUG-1: fixed path)
import 'package:flutter/services.dart';
import 'package:url_launcher/url_launcher.dart';

const _bg      = Color(0xFF020D0C);
const _card    = Color(0xFF0F2420);
const _gold    = Color(0xFFD4AF37);
const _teal    = Color(0xFF1DB898);
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
      nameEn: 'Sidon Voice Enhancement (Hugging Face)',
      descAr:
          'نموذج أكاديمي لتحسين جودة الكلام. مناسب للتسجيلات الهاتفية '
          'الخفيفة. يحتفظ بالصوت بشكل معقول لكنه قد يبتلع بعض الحروف الخفية.',
      url: 'https://huggingface.co/spaces/sarulab-speech/sidon_demo_beta',
      icon: Icons.psychology_alt_rounded,
      color: _teal,
    ),
    _AiTool(
      nameAr: 'Adobe Podcast Enhance',
      nameEn: 'Adobe Podcast Enhance',
      descAr:
          'أداة Adobe لإزالة الضوضاء. قد تكون قوية جداً — خطر تغيير طابع '
          'صوت الشيخ وإفقاده الحيوية حتى يصبح كالبكسلات.',
      url: 'https://podcast.adobe.com/enhance',
      icon: Icons.surround_sound_rounded,
      color: _amber,
    ),
  ];

  void _open(BuildContext ctx, String url) async {
    HapticFeedback.mediumImpact();
    if (!await launchUrl(Uri.parse(url),
            mode: LaunchMode.externalApplication) &&
        ctx.mounted) {
      ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(
        backgroundColor: _redDk,
        content: Text('تعذّر فتح الرابط',
            style: const TextStyle(color: _red, fontSize: 12))));
    }
  }

  @override
  Widget build(BuildContext ctx) => Directionality(
    // S196-BUG-I: derive direction from app language (not hardcoded RTL)
    textDirection: LangProvider.of(ctx).value ? TextDirection.rtl : TextDirection.ltr,
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
            const Text('أدوات الذكاء الاصطناعي',
                style: TextStyle(color: _textA,
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
                      const Expanded(child: Text(
                        'الذكاء الاصطناعي — الخيار الأخير',
                        style: TextStyle(color: _amber,
                            fontSize: 15, fontWeight: FontWeight.w800))),
                    ]),
                    const SizedBox(height: 12),
                    const Text(
                      'هذه الأدوات مخصصة فقط للتسجيلات البالغة التلف '
                      'التي فشلت فيها كل محركات محسِّن التلاوة.\n\n'
                      '⚠️  مخاطر الاستخدام:\n'
                      '  • ابتلاع الكلمات — يختفي حرف أو كلمة كاملة\n'
                      '  • تغيير صوت الشيخ — يصبح كالبكسلات أو اصطناعياً\n'
                      '  • فقدان التجويد الدقيق والغنة والمدود\n\n'
                      '✅  إذا اضطررت للاستخدام:\n'
                      '  راجع الملف الناتج كلمةً كلمة وأضف يدوياً '
                      'أي كلمة مبتلوعة في الملفات التالفة جداً.',
                      style: TextStyle(
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
                child: const Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('📝  ', style: TextStyle(fontSize: 14)),
                    Expanded(child: Text(
                      'ملاحظة من الفريق: لا توجد أداة ذكاء اصطناعي تفهم '
                      'مقامات التلاوة أو أحكام التجويد. محركات محسِّن '
                      'التلاوة مُصممة خصيصاً لهذا. استخدم هذه الأدوات '
                      'فقط حين يكون الصوت بالغ التلف لدرجة أن النتيجة '
                      '"الاصطناعية" أفضل من الصمت.',
                      style: TextStyle(
                          color: _textB, fontSize: 12, height: 1.6))),
                  ])),

              const SizedBox(height: 20),
              const Text('الأدوات المتاحة',
                  style: TextStyle(color: _textB,
                      fontSize: 12, letterSpacing: 0.5)),
              const SizedBox(height: 10),

              // ── Tool cards ─────────────────────────────────────────────
              ..._tools.map((t) => _ToolCard(
                  tool: t, onTap: () => _open(ctx, t.url))),

              const SizedBox(height: 24),
              Center(child: Text('استخدم بحذر شديد ⚠️',
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

class _ToolCard extends StatelessWidget {
  final _AiTool tool;
  final VoidCallback onTap;
  const _ToolCard({required this.tool, required this.onTap});

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
                    Text(tool.nameAr,
                        style: TextStyle(color: tool.color,
                            fontSize: 14, fontWeight: FontWeight.w700)),
                    Text(tool.nameEn,
                        style: const TextStyle(
                            color: _textB, fontSize: 10)),
                  ])),
                Icon(Icons.open_in_new_rounded,
                    color: tool.color.withValues(alpha: 0.55), size: 16),
              ]),
              const SizedBox(height: 10),
              Text(tool.descAr,
                  style: const TextStyle(
                      color: _textA, fontSize: 12, height: 1.55)),
            ])),
      ),
    ),
  );
}

class _AiTool {
  final String nameAr, nameEn, descAr, url;
  final IconData icon;
  final Color color;
  const _AiTool({
    required this.nameAr, required this.nameEn,
    required this.descAr, required this.url,
    required this.icon, required this.color});
}
