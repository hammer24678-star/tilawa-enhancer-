#!/usr/bin/env python3
"""
tilawa_fix_s46.py — fix all 10 anchors that failed in s45
==========================================================
Every old string is taken verbatim from diag_s46.txt.

Run:
  cp /sdcard/Download/tilawa_fix_s46.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s46.py 2>&1 | tee /sdcard/Download/fix_s46.txt
  git add -A && git commit -m "S46: mihrab arch + portal label + format hint + mandala + void palette" && git push
"""

from pathlib import Path
from datetime import datetime

SC  = Path.home() / 'tilawa-enhancer/lib/screens'
_log = []

def _h(t):  print(f'\n{"="*60}\n  {t}\n{"="*60}')
def _ok(m): print(f'  OK  {m}'); _log.append(('OK', m))
def _xx(m): print(f'  XX  {m}'); _log.append(('XX', m))
def _sk(m): print(f'  --  {m}'); _log.append(('SK', m))

def rep(txt, old, new, lbl):
    if old not in txt:
        _xx(f'NOT FOUND — {lbl}')
        return txt, False
    n = txt.count(old)
    if n > 1:
        print(f'  WW  {n}x — using first — {lbl}')
    _ok(lbl)
    return txt.replace(old, new, 1), True

_h(f'tilawa_fix_s46.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ══════════════════════════════════════════════════════════════════
# HOME SCREEN
# ══════════════════════════════════════════════════════════════════
hf = SC / 'home_screen.dart'
ht = hf.read_text(encoding='utf-8')

# H1 — Mihrab arch corners on file card
# Anchor is unique: surrounded by hasFile colour lines (diag line 1201-1204)
_h('H1 — File card mihrab arch corners')
if '// S46-ARCH' in ht:
    _sk('Arch already applied')
else:
    ht, _ = rep(ht,
        '          color: hasFile\n'
        '            ? const Color(0xFF0D2B22)\n'
        '            : const Color(0xFF071A14),\n'
        '          borderRadius: BorderRadius.circular(22),',
        '          color: hasFile\n'
        '            ? const Color(0xFF0D2B22)\n'
        '            : const Color(0xFF071A14),\n'
        '          borderRadius: const BorderRadius.only( // S46-ARCH\n'
        '            topLeft: Radius.circular(200),\n'
        '            topRight: Radius.circular(200),\n'
        '            bottomLeft: Radius.circular(22),\n'
        '            bottomRight: Radius.circular(22)),',
        'file card → mihrab arch corners')

# H2 — Sacred portal pick label
_h('H2 — File card empty label → sacred portal')
if '// S46-PORTAL' in ht:
    _sk('Portal label already applied')
else:
    ht, _ = rep(ht,
        "              hasFile ? _file!.path.split('/').last : s.pickFile,",
        "              hasFile ? _file!.path.split('/').last // S46-PORTAL\n"
        "                : (s.ar ? 'أسقط تلاوتك في هذا المحراب'\n"
        "                        : 'Drop your Quran audio into this sacred portal'),",
        'file card → sacred portal label')

# H3 — mp3 · wav · m4a format hint
# Unique anchor: lines 1310-1312 in diag (after ], ],)
_h('H3 — File card format hint mp3 · wav · m4a')
if '// S46-FMT' in ht:
    _sk('Format hint already present')
else:
    ht, _ = rep(ht,
        '            ],\n'
        '            const SizedBox(height: 6),\n'
        '            Text(s.sizeLimit,',
        '            ],\n'
        '            const SizedBox(height: 3),\n'
        "            if (!hasFile) Text('mp3  ·  wav  ·  m4a', // S46-FMT\n"
        '              textAlign: TextAlign.center,\n'
        '              style: const TextStyle(\n'
        '                color: Color(0xFF1DB898),\n'
        '                fontSize: 9, letterSpacing: 1.4)),\n'
        '            const SizedBox(height: 3),\n'
        '            Text(s.sizeLimit,',
        'format hint mp3/wav/m4a')

# H4 — Mandala spinner in progress card
# Exact anchor from diag lines 1639-1643
_h('H4 — Progress card mandala spinner')
if '// S46-MANDALA' in ht:
    _sk('Mandala already in progress card')
else:
    ht, _ = rep(ht,
        '      const SizedBox(height: 12),\n'
        '      ClipRRect(\n'
        '        borderRadius: BorderRadius.circular(8),\n'
        '        // S20-A: null = indeterminate (animated pulse) during server merge\n'
        '        child: LinearProgressIndicator(',
        '      const SizedBox(height: 6),\n'
        '      Center(child: SizedBox(width: 90, height: 90, // S46-MANDALA\n'
        '        child: AnimatedBuilder(\n'
        '          animation: _geoRotCtrl,\n'
        '          builder: (_, __) => CustomPaint(\n'
        '            painter: _MandalaPainter(_geoRotCtrl.value))))),\n'
        '      const SizedBox(height: 6),\n'
        '      ClipRRect(\n'
        '        borderRadius: BorderRadius.circular(8),\n'
        '        // S20-A: null = indeterminate (animated pulse) during server merge\n'
        '        child: LinearProgressIndicator(',
        'mandala spinner before progress bar')

hf.write_text(ht, encoding='utf-8')
_ok('home_screen.dart saved')

# ══════════════════════════════════════════════════════════════════
# SETTINGS SCREEN
# Diag lines 58-60: 2-space indent, no leading spaces before Color
# ══════════════════════════════════════════════════════════════════
_h('S1 — settings_screen.dart void/jade palette')
sf = SC / 'settings_screen.dart'
st = sf.read_text(encoding='utf-8')

if '// S46-SET' in st:
    _sk('Settings palette already updated')
else:
    st, _ = rep(st,
        '  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n'
        '  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);\n'
        '  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);',
        '  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF020D0C) : const Color(0xFFFAF7EE); // S46-SET\n'
        '  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF0F2420) : const Color(0xFFF3EED9);\n'
        '  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF1A4035) : const Color(0xFFD4C99A);',
        'settings _cBg/_cCard/_cBorder → void/jade')

sf.write_text(st, encoding='utf-8')
_ok('settings_screen.dart saved')

# ══════════════════════════════════════════════════════════════════
# HISTORY SCREEN
# Has TWO sets of colours: state field initialisers + method helpers
# Diag: state fields at lines 33-35, method helpers at lines 114-116
# ══════════════════════════════════════════════════════════════════
_h('V1 — history_screen.dart void/jade palette')
vf = SC / 'history_screen.dart'
vt = vf.read_text(encoding='utf-8')

if '// S46-HIST' in vt:
    _sk('History palette already updated')
else:
    # State field initialisers
    vt, _ = rep(vt,
        '  Color _tBg     = const Color(0xFF080A0E);\n'
        '  Color _tCard   = const Color(0xFF161B22);\n'
        '  Color _tBorder = const Color(0xFF21262D);',
        '  Color _tBg     = const Color(0xFF020D0C); // S46-HIST\n'
        '  Color _tCard   = const Color(0xFF0F2420);\n'
        '  Color _tBorder = const Color(0xFF1A4035);',
        'history _tBg/_tCard/_tBorder state fields → void/jade')

    # Method helpers
    vt, _ = rep(vt,
        '  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n'
        '  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);\n'
        '  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);',
        '  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF020D0C) : const Color(0xFFFAF7EE); // S46-HIST-M\n'
        '  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF0F2420) : const Color(0xFFF3EED9);\n'
        '  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF1A4035) : const Color(0xFFD4C99A);',
        'history _cBg/_cCard/_cBorder methods → void/jade')

vf.write_text(vt, encoding='utf-8')
_ok('history_screen.dart saved')

# ══════════════════════════════════════════════════════════════════
# WELCOME SCREEN
# W2: _cBg/_cCard/_cBorder (no _cText line — welcome has fewer helpers)
# W3b: _WelcomeStarsPainter teal  (diag line 466-467)
# W3c: lang toggle bg (diag lines 376-378)
# ══════════════════════════════════════════════════════════════════
_h('W2/W3b/W3c — welcome_screen.dart void/jade + teal')
wf = SC / 'welcome_screen.dart'
wt = wf.read_text(encoding='utf-8')

# W2 — color helpers (welcome has _cBg/_cCard/_cBorder/_cSub, no _cText)
if '// S46-WEL' in wt:
    _sk('Welcome palette already updated')
else:
    wt, _ = rep(wt,
        '  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n'
        '  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);\n'
        '  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);',
        '  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF020D0C) : const Color(0xFFFAF7EE); // S46-WEL\n'
        '  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF0F2420) : const Color(0xFFF3EED9);\n'
        '  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF1A4035) : const Color(0xFFD4C99A);',
        'welcome _cBg/_cCard/_cBorder → void/jade')

# W3b — _WelcomeStarsPainter teal 1C8EA8 → 1DB898 (diag lines 466-467)
if '// S46-WEL-T3' in wt:
    _sk('WelcomeStarsPainter teal already updated')
else:
    wt, _ = rep(wt,
        '              : const Color(0xFF1C8EA8))\n'
        '          .withOpacity(alpha);',
        '              : const Color(0xFF1DB898)) // S46-WEL-T3\n'
        '          .withOpacity(alpha);',
        '_WelcomeStarsPainter teal → #1DB898')

# W3c — lang toggle bg (diag lines 376-378)
if '// S46-WEL-LANG' in wt:
    _sk('Lang toggle bg already updated')
else:
    wt, _ = rep(wt,
        '            color: const Color(0xFF161B22),\n'
        '            borderRadius: BorderRadius.circular(20),\n'
        '            border: Border.all(color: const Color(0xFF21262D))),',
        '            color: const Color(0xFF0F2420), // S46-WEL-LANG\n'
        '            borderRadius: BorderRadius.circular(20),\n'
        '            border: Border.all(color: const Color(0xFF1A4035))),',
        'welcome lang toggle bg → jade')

wf.write_text(wt, encoding='utf-8')
_ok('welcome_screen.dart saved')

# ══════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════
_h('SUMMARY')
ok_n = sum(1 for s, _ in _log if s == 'OK')
sk_n = sum(1 for s, _ in _log if s == 'SK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
for s, l in _log:
    print(f'  {"OK" if s=="OK" else "--" if s=="SK" else "XX"}  {l}')
_h(f'{ok_n} OK   {sk_n} SKIP   {xx_n} FAIL')

if xx_n == 0:
    print("""
  git add -A && git commit -m "S46: mihrab arch + portal label + format hint + mandala + void palette" && git push
""")
else:
    print('\n  Some anchors still not found — paste output back to Claude.\n')
