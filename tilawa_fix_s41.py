#!/usr/bin/env python3
"""tilawa_fix_s41.py — fix 12 failed anchors from s40"""
from pathlib import Path
from datetime import datetime

SC  = Path.home() / 'tilawa-enhancer/lib/screens'
LIB = Path.home() / 'tilawa-enhancer/lib'
_log = []

def _h(t): print(f'\n{"═"*56}\n  {t}\n{"═"*56}')
def _ok(m): print(f'  OK  {m}'); _log.append(('OK', m))
def _xx(m): print(f'  XX  {m}'); _log.append(('XX', m))

def rep(txt, old, new, lbl):
    if old in txt: _ok(lbl); return txt.replace(old, new, 1), True
    _xx(f'NOT FOUND — {lbl}'); return txt, False

_h(f'tilawa_fix_s41  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

txt = (SC/'home_screen.dart').read_text(encoding='utf-8')

# ── 1. _bgCard token (line 18 exact) ─────────────────────────────────────────
txt, _ = rep(txt,
    "const _bgCard    = Color(0xFF102B38);",
    "const _bgCard    = Color(0xFF0F2420);",
    '_bgCard → jade marble #0F2420')

# ── 2. BG gradient dark branch (lines 619-620 exact) ─────────────────────────
txt, _ = rep(txt,
    "            colors: dark\n"
    "              ? [const Color(0xFF020D17), const Color(0xFF000810)]\n"
    "              : [const Color(0xFFFAF7EE), const Color(0xFFF5F0E0)]),",
    "            colors: dark\n"
    "              ? [const Color(0xFF020D0C), const Color(0xFF051A14)]\n"
    "              : [const Color(0xFFFAF7EE), const Color(0xFFF5F0E0)]),",
    'BG gradient → void teal')

# ── 3. AppBar FlexibleSpaceBar gradient (lines 649-651 exact) ────────────────
txt, _ = rep(txt,
    "                      colors: [\n"
    "                        Color(0xFF061F32),\n"
    "                        Color(0xFF020D17),\n"
    "                      ]))),"  ,
    "                      colors: [\n"
    "                        Color(0xFF0A2A1E),\n"
    "                        Color(0xFF020D0C),\n"
    "                      ]))),"  ,
    'AppBar gradient → jade/void')

# ── 4. File card bg (lines 1193-1195 exact) ───────────────────────────────────
txt, _ = rep(txt,
    "        color: _file != null\n"
    "          ? const Color(0xFF0B2233)\n"
    "          : const Color(0xFF071929),",
    "        color: _file != null\n"
    "          ? const Color(0xFF0D2B22)\n"
    "          : const Color(0xFF071A14),",
    'File card bg → jade')

# ── 5. File card empty border (line 1000 exact) ───────────────────────────────
txt, _ = rep(txt,
    "              : const Color(0xFF1C8EA8).withOpacity(0.15),",
    "              : const Color(0xFF1DB898).withOpacity(0.22),",
    'File card empty border → bright teal')

# ── 6. Progress card gradient (line 1487-1491 exact) ─────────────────────────
txt, _ = rep(txt,
    "      gradient: const LinearGradient(\n"
    "        begin: Alignment.topLeft, end: Alignment.bottomRight,\n"
    "        colors: [Color(0xFF0B2233), Color(0xFF071929)]),",
    "      gradient: const LinearGradient(\n"
    "        begin: Alignment.topLeft, end: Alignment.bottomRight,\n"
    "        colors: [Color(0xFF0D2B22), Color(0xFF071A14)]),",
    'Progress card gradient → jade')

# ── 7. Progress card teal shadow (search for the shadow color) ────────────────
txt, _ = rep(txt,
    "            color: const Color(0xFF1C8EA8).withOpacity(0.06),\n"
    "            blurRadius: 60, spreadRadius: 2),",
    "            color: const Color(0xFF1DB898).withOpacity(0.08),\n"
    "            blurRadius: 60, spreadRadius: 2),",
    'Progress card teal shadow → #1DB898')

# ── 8. Engine card non-sel bg (lines 993-995 exact) ───────────────────────────
txt, _ = rep(txt,
    "          color: sel\n"
    "            ? col.withOpacity(0.09)\n"
    "            : const Color(0xFF0B2233).withOpacity(0.7),",
    "          color: sel\n"
    "            ? col.withOpacity(0.09)\n"
    "            : const Color(0xFF0D2B22).withOpacity(0.75),",
    'Engine card non-sel bg → jade')

# ── 9. Engine card teal border (lines 999-1000 exact) ────────────────────────
txt, _ = rep(txt,
    "              : const Color(0xFF1C8EA8).withOpacity(0.15),\n"
    "            width: sel ? 1.6 : 0.7),",
    "              : const Color(0xFF1DB898).withOpacity(0.20),\n"
    "            width: sel ? 1.8 : 0.8),",
    'Engine card teal border → #1DB898')

# ── 10. Geo separators between slivers (lines 683-685 exact) ─────────────────
txt, _ = rep(txt,
    "            SliverToBoxAdapter(child: _serverBanner(s)),\n"
    "            SliverToBoxAdapter(child: _engineSelector(s)),\n"
    "            SliverToBoxAdapter(child: _fileCard(s)),",
    "            SliverToBoxAdapter(child: _serverBanner(s)),\n"
    "            SliverToBoxAdapter(child: _geoSep()),\n"
    "            SliverToBoxAdapter(child: _engineSelector(s)),\n"
    "            SliverToBoxAdapter(child: _geoDiamond()),\n"
    "            SliverToBoxAdapter(child: _fileCard(s)),",
    'Geo separators inserted between slivers')

# ── 11. Incense painter in background Stack (line 626 exact) ─────────────────
txt, _ = rep(txt,
    "              child: CustomPaint(painter: _GeoPainter())))),"
    "\n          if (dark) Positioned.fill(",
    "              child: CustomPaint(painter: _GeoPainter()))),\n"
    "          // Incense smoke\n"
    "          if (dark) Positioned.fill(\n"
    "            child: IgnorePointer(\n"
    "              child: CustomPaint(painter: _IncensePainter(\n"
    "                _geoRotCtrl.value)))),\n"
    "          if (dark) Positioned.fill(",
    'Incense painter in background Stack')

(SC/'home_screen.dart').write_text(txt, encoding='utf-8')
_ok('home_screen.dart saved')

# ── Summary ───────────────────────────────────────────────────────────────────
_h('SUMMARY')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok = sum(1 for s,_ in _log if s=='OK')
xx = sum(1 for s,_ in _log if s=='XX')
_h(f'{ok} OK   {xx} FAIL')
print('\n  git add -A && git commit -m "S41: fix all jade/void palette + geo sep + incense" && git push\n')
