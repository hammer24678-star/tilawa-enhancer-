#!/usr/bin/env python3
"""tilawa_fix_s63_about — improve About page: Telegram + developer lore + cleaner layout"""
import sys
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

def _h(t): print(f'\n{"="*52}\n  {t}\n{"="*52}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'\n  XX  NOT FOUND — {m}\n'); sys.exit(1)
def rep(old, new, lbl):
    t = HS.read_text(encoding='utf-8')
    if old not in t: _xx(lbl)
    HS.write_text(t.replace(old, new, 1), encoding='utf-8'); _ok(lbl)

_h(f'S63-ABOUT  {datetime.now().strftime("%H:%M:%S")}')

# ── PATCH 1 — Add Telegram card after YouTube card ──────────────────────────
_h('1 — Add Telegram card + community section label')
rep(
    "                _infoSectionLabel(s.ar ? '🎯 المرجع الصوتي' : '🎯 Reference Standard'),",

    "                _infoSectionLabel(s.ar ? '💬 قناة تيليغرام' : '💬 Telegram Channel'),\n"
    "                GestureDetector(\n"
    "                  onTap: () => launchUrl(\n"
    "                    Uri.parse('https://t.me/TilawaEhnacher'),\n"
    "                    mode: LaunchMode.externalApplication),\n"
    "                  child: Container(\n"
    "                    margin: const EdgeInsets.only(bottom: 16),\n"
    "                    padding: const EdgeInsets.all(14),\n"
    "                    decoration: BoxDecoration(\n"
    "                      color: const Color(0xFF0A0F1A),\n"
    "                      borderRadius: BorderRadius.circular(12),\n"
    "                      border: Border.all(\n"
    "                        color: const Color(0xFF2AABEE).withValues(alpha: 0.35))),\n"
    "                    child: Row(children: [\n"
    "                      Container(\n"
    "                        width: 40, height: 40,\n"
    "                        decoration: BoxDecoration(\n"
    "                          gradient: const LinearGradient(\n"
    "                            colors: [Color(0xFF2AABEE), Color(0xFF229ED9)]),\n"
    "                          borderRadius: BorderRadius.circular(10)),\n"
    "                        child: const Icon(Icons.send_rounded,\n"
    "                          color: Colors.white, size: 22)),\n"
    "                      const SizedBox(width: 12),\n"
    "                      Expanded(child: Column(\n"
    "                        crossAxisAlignment: CrossAxisAlignment.start,\n"
    "                        children: [\n"
    "                        Text(s.ar ? 'قناة التيليغرام' : 'Telegram Channel',\n"
    "                          style: const TextStyle(\n"
    "                            color: Color(0xFFC9D1D9),\n"
    "                            fontWeight: FontWeight.bold, fontSize: 13)),\n"
    "                        const SizedBox(height: 2),\n"
    "                        const Text('@TilawaEhnacher',\n"
    "                          style: TextStyle(\n"
    "                            color: Color(0xFF8B949E), fontSize: 11)),\n"
    "                      ])),\n"
    "                      const Icon(Icons.open_in_new_rounded,\n"
    "                        color: Color(0xFF484F58), size: 16),\n"
    "                    ]))),\n"
    "                _infoSectionLabel(s.ar ? '🎯 المرجع الصوتي' : '🎯 Reference Standard'),",

    'Telegram card inserted'
)

# ── PATCH 2 — Add developer lore card before the version card ────────────────
_h('2 — Add developer lore card before version card')
rep(
    "                Container(\n"
    "                  padding: const EdgeInsets.all(14),\n"
    "                  decoration: BoxDecoration(\n"
    "                    color: _tCard,\n"
    "                    borderRadius: BorderRadius.circular(12),\n"
    "                    border: Border.all(color: _tBorder)),\n"
    "                  child: Row(children: [\n"
    "                    ClipOval(child: Image.asset('assets/images/logo.png',",

    "                _infoSectionLabel(s.ar ? '📖 من المطوِّر' : '📖 Developer Notes'),\n"
    "                Container(\n"
    "                  margin: const EdgeInsets.only(bottom: 16),\n"
    "                  padding: const EdgeInsets.all(16),\n"
    "                  decoration: BoxDecoration(\n"
    "                    gradient: const LinearGradient(\n"
    "                      begin: Alignment.topLeft, end: Alignment.bottomRight,\n"
    "                      colors: [Color(0xFF0D1B2A), Color(0xFF06101A)]),\n"
    "                    borderRadius: BorderRadius.circular(14),\n"
    "                    border: Border.all(\n"
    "                      color: const Color(0xFFD4AF37).withValues(alpha: 0.18))),\n"
    "                  child: Column(\n"
    "                    crossAxisAlignment: CrossAxisAlignment.start,\n"
    "                    children: [\n"
    "                    Text(\n"
    "                      s.ar ? '﷽' : '﷽',\n"
    "                      style: const TextStyle(\n"
    "                        color: Color(0xFFD4AF37),\n"
    "                        fontSize: 22, height: 1.4)),\n"
    "                    const SizedBox(height: 10),\n"
    "                    Text(\n"
    "                      s.ar\n"
    "                        ? 'هذا التطبيق وُلد من حبٍّ خالص لكتاب الله.\\n\\n'\n"
    "                          'أكثر من ٦٠ جلسة، مئات الإصلاحات، ومحرك واحد لا يهدأ: '\n"
    "                          'أن تُسمع التلاوة كما ينبغي لها أن تُسمع.\\n\\n'\n"
    "                          'لا فريق، لا ميزانية — فقط هاتف، وطرفية، ومحبة للقرآن الكريم. '\n"
    "                          'كل محرك بُني كأنه عبادة، وكل معامل ضُبط كأنه دعاء.\\n\\n'\n"
    "                          'الهدف لم يتغيّر: أن يُعاد للصوت القرآني جماله الأصيل،'\n"
    "                          ' حتى وإن جاء من تسجيل قديم أو ملف تالف.'\n"
    "                        : 'This app was born from pure love for the Book of Allah.\\n\\n'\n"
    "                          'Over 60 sessions, hundreds of fixes, one relentless goal: '\n"
    "                          'to make Quranic recitation sound as it deserves to be heard.\\n\\n'\n"
    "                          'No team, no budget — just a phone, Termux, and a deep love for the Quran. '\n"
    "                          'Every engine was built like an act of worship, every parameter tuned like a prayer.\\n\\n'\n"
    "                          'The mission never changed: restore the original beauty of the Quranic voice, '\n"
    "                          'even from an old recording or a damaged file.',\n"
    "                      style: const TextStyle(\n"
    "                        color: Color(0xFFA8B8C8),\n"
    "                        fontSize: 12, height: 1.75)),\n"
    "                    const SizedBox(height: 14),\n"
    "                    Container(\n"
    "                      padding: const EdgeInsets.symmetric(\n"
    "                        horizontal: 10, vertical: 6),\n"
    "                      decoration: BoxDecoration(\n"
    "                        color: const Color(0xFFD4AF37).withValues(alpha: 0.08),\n"
    "                        borderRadius: BorderRadius.circular(8),\n"
    "                        border: Border.all(\n"
    "                          color: const Color(0xFFD4AF37).withValues(alpha: 0.2))),\n"
    "                      child: Text(\n"
    "                        s.ar\n"
    "                          ? '🎯 المرجع: الشيخ ياسر الدوسري · ١٤٢٥هـ · LUFS=-6.29'\n"
    "                          : '🎯 Reference: Yasser Al-Dossari · 1425H · LUFS=-6.29',\n"
    "                        style: const TextStyle(\n"
    "                          color: Color(0xFFD4AF37),\n"
    "                          fontSize: 10, fontWeight: FontWeight.bold))),\n"
    "                  ])),\n"
    "                Container(\n"
    "                  padding: const EdgeInsets.all(14),\n"
    "                  decoration: BoxDecoration(\n"
    "                    color: _tCard,\n"
    "                    borderRadius: BorderRadius.circular(12),\n"
    "                    border: Border.all(color: _tBorder)),\n"
    "                  child: Row(children: [\n"
    "                    ClipOval(child: Image.asset('assets/images/logo.png',",

    'Developer lore card inserted'
)

_h('DONE')
print('\n  git add -A && git commit -m "S63: About page — Telegram + developer lore" && git push\n')
