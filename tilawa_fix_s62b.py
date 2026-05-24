#!/usr/bin/env python3
"""tilawa_fix_s62b — top gap + Telegram + about jade"""
import sys
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
def _h(t): print(f'\n{"="*52}\n  {t}\n{"="*52}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'\n  XX  {m}\n'); sys.exit(1)
def rep(old, new, lbl):
    t = HS.read_text(encoding='utf-8')
    if old not in t: _xx(f'NOT FOUND — {lbl}')
    HS.write_text(t.replace(old, new, 1), encoding='utf-8'); _ok(lbl)

_h(f'S62b  {datetime.now().strftime("%H:%M:%S")}')

# 1 — Remove SafeArea top gap
_h('1 — SafeArea → top gap fix')
rep(
    '          SafeArea(\n'
    '          child: CustomScrollView(slivers: [\n'
    '            SliverAppBar( // S61-APPBAR',
    '          CustomScrollView(slivers: [ // S62b\n'
    '            SliverAppBar( // S61-APPBAR',
    'SafeArea removed from scroll view'
)
# Remove extra closing paren SafeArea left
rep(
    '          ]),\n'
    '        ),\n'
    '        ),\n'
    '      ],\n'
    '    );\n'
    '  }\n'
    '\n'
    '  // ── Server banner',
    '          ]),\n'
    '        ),\n'
    '      ],\n'
    '    );\n'
    '  }\n'
    '\n'
    '  // ── Server banner',
    'SafeArea extra ) removed'
)

# 2 — About sheet bg → jade
_h('2 — About bg jade')
rep(
    '            color: Color(0xFF0D1117),\n'
    '            borderRadius: BorderRadius.vertical(top: Radius.circular(20))),',
    '            color: Color(0xFF061A14),\n'
    '            borderRadius: BorderRadius.vertical(top: Radius.circular(20))),',
    'About bg jade'
)

# 3 — Telegram card before Reference Standard
_h('3 — Telegram card')
rep(
    "                _infoSectionLabel(s.ar ? '🎯 المرجع الصوتي' : '🎯 Reference Standard'),",
    "                _infoSectionLabel(s.ar ? '✈️ تيليغرام' : '✈️ Telegram'),\n"
    "                GestureDetector(\n"
    "                  onTap: () => launchUrl(\n"
    "                    Uri.parse('https://t.me/TilawaEhnacher'),\n"
    "                    mode: LaunchMode.externalApplication),\n"
    "                  child: Container(\n"
    "                    margin: const EdgeInsets.only(bottom: 16),\n"
    "                    padding: const EdgeInsets.all(14),\n"
    "                    decoration: BoxDecoration(\n"
    "                      color: const Color(0xFF0A1620),\n"
    "                      borderRadius: BorderRadius.circular(12),\n"
    "                      border: Border.all(\n"
    "                        color: const Color(0xFF2AABEE).withValues(alpha: 0.35))),\n"
    "                    child: Row(children: [\n"
    "                      Container(\n"
    "                        width: 40, height: 40,\n"
    "                        decoration: BoxDecoration(\n"
    "                          color: const Color(0xFF2AABEE),\n"
    "                          borderRadius: BorderRadius.circular(10)),\n"
    "                        child: const Icon(Icons.send_rounded,\n"
    "                          color: Colors.white, size: 22)),\n"
    "                      const SizedBox(width: 12),\n"
    "                      Expanded(child: Column(\n"
    "                        crossAxisAlignment: CrossAxisAlignment.start,\n"
    "                        children: [\n"
    "                        Text(s.ar ? 'قناة تيليغرام' : 'Telegram Channel',\n"
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
    'Telegram card'
)

_h('DONE')
print('\n  git add -A && git commit -m "S62b: top gap + Telegram + about jade" && git push\n')
