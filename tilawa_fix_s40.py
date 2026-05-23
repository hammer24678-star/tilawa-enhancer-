#!/usr/bin/env python3
"""
tilawa_fix_s40.py — S40: Void Teal theme from tilawa_design_s40.html
=====================================================================
Inspired by the HTML design mockup:

PALETTE-1  Background: navy #020D17 → void-teal #020D0C  (dark)
PALETTE-2  Cards: deep-navy #0B2233 → jade-marble #0F2420
PALETTE-3  Teal accent: cyan-blue #1C8EA8 → bright teal #1DB898
PALETTE-4  Darker bg: #000810 → #010908 / #071929 → #0A1C1A

DESIGN-1   BG gradient → void teal
DESIGN-2   SliverAppBar + FlexibleSpaceBar gradient → jade/void
DESIGN-3   File card → jade marble
DESIGN-4   Progress card gradient → jade
DESIGN-5   Engine card non-selected → jade + new teal border
DESIGN-6   Geo diamond separators between sections
DESIGN-7   Rising incense particle painter in background
DESIGN-8   main.dart dark theme → void teal palette

Run:
  cp /sdcard/Download/tilawa_fix_s40.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s40.py 2>&1 | tee /sdcard/Download/fix_s40.txt
  git add -A && git commit -m "S40: void-teal palette + jade cards + geo separators + incense particles" && git push
"""

from pathlib import Path
from datetime import datetime

SC  = Path.home() / 'tilawa-enhancer/lib/screens'
ML  = Path.home() / 'tilawa-enhancer/lib/main.dart'
_log = []

def _h(t):  print(f'\n{"="*62}\n  {t}\n{"="*62}')
def _ok(m): print(f'  OK  {m}'); _log.append(('OK', m))
def _xx(m): print(f'  XX  {m}'); _log.append(('XX', m))
def _sk(m): print(f'  --  {m}'); _log.append(('SK', m))

def rep(txt, old, new, lbl):
    if old not in txt:
        _xx(f'NOT FOUND — {lbl}')
        return txt, False
    n = txt.count(old)
    if n > 1:
        print(f'  WW  {lbl}: {n} occurrences — replacing first only')
    _ok(lbl)
    return txt.replace(old, new, 1), True

_h(f'tilawa_fix_s40.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ══════════════════════════════════════════════════════════════════
# home_screen.dart
# ══════════════════════════════════════════════════════════════════
htxt = (SC / 'home_screen.dart').read_text(encoding='utf-8')

# ── PALETTE CONSTANTS ──────────────────────────────────────────────
_h('PALETTE — _teal #1C8EA8 → bright teal #1DB898')
if '// S40-TEAL' in htxt:
    _sk('_teal already updated')
else:
    htxt, _ = rep(htxt,
        'const _teal      = Color(0xFF1C8EA8);',
        'const _teal      = Color(0xFF1DB898); // S40-TEAL',
        '_teal constant → #1DB898')

_h('PALETTE — _bgCard #0B2233 → jade marble #0F2420')
if '// S40-JADE' in htxt:
    _sk('_bgCard already updated')
else:
    htxt, _ = rep(htxt,
        'const _bgCard    = Color(0xFF0B2233);',
        'const _bgCard    = Color(0xFF0F2420); // S40-JADE',
        '_bgCard constant → #0F2420')

# ── DESIGN-1: Background gradient ──────────────────────────────────
_h('DESIGN-1 — Background gradient void teal')
if '// S40-BG-VOID' in htxt:
    _sk('BG gradient already void-teal')
else:
    htxt, _ = rep(htxt,
        '                ? [const Color(0xFF020D17), const Color(0xFF000810)]',
        '                ? [const Color(0xFF020D0C), const Color(0xFF010908)] // S40-BG-VOID',
        'BG gradient dark branch → void teal')

# ── DESIGN-2: SliverAppBar ─────────────────────────────────────────
_h('DESIGN-2 — SliverAppBar backgroundColor void')
if '// S40-AB-VOID' in htxt:
    _sk('SliverAppBar bg already void')
else:
    htxt, _ = rep(htxt,
        '              pinned: true,\n'
        '              floating: false,\n'
        '              backgroundColor: const Color(0xFF020D17),',
        '              pinned: true,\n'
        '              floating: false,\n'
        '              backgroundColor: const Color(0xFF020D0C), // S40-AB-VOID',
        'SliverAppBar bg → void')

_h('DESIGN-2 — AppBar FlexibleSpaceBar gradient jade')
if '// S40-AB-JADE' in htxt:
    _sk('AppBar gradient already jade')
else:
    htxt, _ = rep(htxt,
        '                          Color(0xFF061F32),\n'
        '                          Color(0xFF020D17),',
        '                          Color(0xFF0F2420), // S40-AB-JADE\n'
        '                          Color(0xFF020D0C),',
        'AppBar gradient colors → jade/void')

# ── DESIGN-3: File card ────────────────────────────────────────────
_h('DESIGN-3 — File card jade marble')
if '// S40-FILE-JADE' in htxt:
    _sk('File card already jade')
else:
    htxt, _ = rep(htxt,
        '          // S32-FILE-CARD\n'
        '          color: _file != null\n'
        '            ? const Color(0xFF0B2233)\n'
        '            : const Color(0xFF071929),',
        '          // S32-FILE-CARD / S40-FILE-JADE\n'
        '          color: _file != null\n'
        '            ? const Color(0xFF0F2420)\n'
        '            : const Color(0xFF0A1C1A),',
        'File card bg → jade/dark-jade')
    htxt, _ = rep(htxt,
        '              : const Color(0xFF1C8EA8).withOpacity(0.20),',
        '              : const Color(0xFF1DB898).withOpacity(0.20), // S40-FILE-TEAL',
        'File card empty border teal → #1DB898')

# ── DESIGN-4: Progress card ────────────────────────────────────────
_h('DESIGN-4 — Progress card gradient jade')
if '// S40-PROG-JADE' in htxt:
    _sk('Progress card already jade')
else:
    htxt, _ = rep(htxt,
        '          colors: [Color(0xFF0B2233), Color(0xFF071929)]),',
        '          colors: [Color(0xFF0F2420), Color(0xFF0A1C1A)]), // S40-PROG-JADE',
        'Progress card gradient → jade')
    # Progress card teal glow shadow
    htxt, _ = rep(htxt,
        '          BoxShadow(\n'
        '            color: const Color(0xFF1C8EA8).withOpacity(0.06),\n'
        '            blurRadius: 60, spreadRadius: 2),',
        '          BoxShadow(\n'
        '            color: const Color(0xFF1DB898).withOpacity(0.06), // S40-PROG-TEAL\n'
        '            blurRadius: 60, spreadRadius: 2),',
        'Progress card teal shadow → #1DB898')

# ── DESIGN-5: Engine card ──────────────────────────────────────────
_h('DESIGN-5 — Engine card non-selected jade + teal border')
if '// S40-ENG-JADE' in htxt:
    _sk('Engine card already jade')
else:
    htxt, _ = rep(htxt,
        '              : const Color(0xFF0B2233).withOpacity(0.7),',
        '              : const Color(0xFF0F2420).withOpacity(0.7), // S40-ENG-JADE',
        'Engine card non-sel bg → jade')
    htxt, _ = rep(htxt,
        '                : const Color(0xFF1C8EA8).withOpacity(0.15),',
        '                : const Color(0xFF1DB898).withOpacity(0.15), // S40-ENG-TEAL',
        'Engine card teal border → #1DB898')

# ── DESIGN-6: Geo diamond separators ──────────────────────────────
_h('DESIGN-6 — Add _geoSep + _geoDiamond widget methods')
MARK_GEO = '// S40-GEO-SEP'
if MARK_GEO in htxt:
    _sk('Geo separator methods already present')
else:
    GEO_METHODS = (
        '\n'
        '  // S40-GEO-SEP — sacred geometry section divider from HTML design\n'
        '  Widget _geoSep(String label) => Padding(\n'
        '    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),\n'
        '    child: Row(children: [\n'
        '      Expanded(child: Container(height: 1,\n'
        '        decoration: const BoxDecoration(gradient: LinearGradient(\n'
        '          colors: [Colors.transparent, Color(0xFFC8A048)],\n'
        '          stops: [0.0, 1.0])))),\n'
        '      Padding(\n'
        '        padding: const EdgeInsets.symmetric(horizontal: 8),\n'
        '        child: Row(mainAxisSize: MainAxisSize.min, children: [\n'
        '          _geoDiamond(),\n'
        '          if (label.isNotEmpty) Padding(\n'
        '            padding: const EdgeInsets.symmetric(horizontal: 6),\n'
        '            child: Text(label.toUpperCase(), style: const TextStyle(\n'
        '              color: Color(0xFFC8A048), fontSize: 9,\n'
        '              letterSpacing: 0.22, fontWeight: FontWeight.w500))),\n'
        '          _geoDiamond(),\n'
        '        ])),\n'
        '      Expanded(child: Container(height: 1,\n'
        '        decoration: const BoxDecoration(gradient: LinearGradient(\n'
        '          colors: [Color(0xFFC8A048), Colors.transparent],\n'
        '          stops: [0.0, 1.0])))),\n'
        '    ]));\n'
        '\n'
        '  Widget _geoDiamond() => Transform.rotate(\n'
        '    angle: 0.7854, // 45 degrees\n'
        '    child: Container(\n'
        '      width: 6, height: 6,\n'
        '      decoration: BoxDecoration(\n'
        '        color: const Color(0xFFC8A048),\n'
        '        borderRadius: BorderRadius.circular(1),\n'
        '        boxShadow: [const BoxShadow(\n'
        '          color: Color(0x80C8A048), blurRadius: 5)])));\n'
    )
    OLD_BADGE = '\n  Color _badgeColor(String bc) =>'
    htxt, _ = rep(htxt, OLD_BADGE,
                  GEO_METHODS + '\n  Color _badgeColor(String bc) =>',
                  'Geo separator methods inserted before _badgeColor')

_h('DESIGN-6 — Insert geo separators in build sliver list')
if '// S40-GEO-1' in htxt:
    _sk('Geo sep 1 already inserted')
else:
    htxt, _ = rep(htxt,
        '              SliverToBoxAdapter(child: _serverBanner(s)),\n'
        '              SliverToBoxAdapter(child: _engineSelector(s)),',
        '              SliverToBoxAdapter(child: _serverBanner(s)),\n'
        "              SliverToBoxAdapter(child: _geoSep(s.ar ? '\u0627\u062e\u062a\u0631 \u0627\u0644\u0645\u062d\u0631\u0643' : 'Engine')), // S40-GEO-1\n"
        '              SliverToBoxAdapter(child: _engineSelector(s)),',
        'Geo sep 1 — server banner / engine selector')

if '// S40-GEO-2' in htxt:
    _sk('Geo sep 2 already inserted')
else:
    htxt, _ = rep(htxt,
        '              SliverToBoxAdapter(child: _engineSelector(s)),\n'
        '              SliverToBoxAdapter(child: _fileCard(s)),',
        '              SliverToBoxAdapter(child: _engineSelector(s)),\n'
        "              SliverToBoxAdapter(child: _geoSep(s.ar ? '\u0631\u0641\u0639 \u0627\u0644\u0635\u0648\u062a' : 'Upload')), // S40-GEO-2\n"
        '              SliverToBoxAdapter(child: _fileCard(s)),',
        'Geo sep 2 — engine selector / file card')

# ── DESIGN-7: Incense painter class ───────────────────────────────
_h('DESIGN-7 — Add _IncensePainter class')
if '// S40-INCENSE' in htxt:
    _sk('IncensePainter already present')
else:
    INC = (
        '// S40-INCENSE — rising gold particle dots from HTML design\n'
        'class _IncensePainter extends CustomPainter {\n'
        '  final double t;\n'
        '  _IncensePainter(this.t);\n'
        '  static const _xs = [0.15, 0.28, 0.42, 0.50, 0.62, 0.72, 0.82, 0.45, 0.58, 0.68];\n'
        '  @override\n'
        '  void paint(Canvas canvas, Size size) {\n'
        '    final p = Paint()..style = PaintingStyle.fill;\n'
        '    for (int i = 0; i < _xs.length; i++) {\n'
        '      final phase = ((t * 0.65) + i / _xs.length) % 1.0;\n'
        '      final dx = _xs[i] * size.width + sin(phase * 6.2832 * 1.5 + i) * 9;\n'
        '      final dy = size.height * (1.0 - phase * 0.72);\n'
        '      final op = phase < 0.12 ? phase / 0.12\n'
        '          : phase > 0.75 ? (1.0 - phase) / 0.25 : 0.42;\n'
        '      p.color = const Color(0xFFC8A048).withOpacity(op * 0.5);\n'
        '      canvas.drawCircle(Offset(dx, dy), 1.4 + (i % 2) * 0.7, p);\n'
        '    }\n'
        '  }\n'
        '  @override bool shouldRepaint(_IncensePainter o) => o.t != t;\n'
        '}\n'
        '\n'
    )
    OLD_GEO_CLASS = 'class _GeoPainter extends CustomPainter {'
    htxt, _ = rep(htxt, OLD_GEO_CLASS,
                  INC + 'class _GeoPainter extends CustomPainter {',
                  '_IncensePainter class added before _GeoPainter')

_h('DESIGN-7 — Add incense layer to background Stack')
if '// S40-INCENSE-STACK' in htxt:
    _sk('Incense layer already in Stack')
else:
    htxt, _ = rep(htxt,
        '            if (dark) Positioned.fill(\n'
        '              child: IgnorePointer(\n'
        '                child: AnimatedBuilder(\n'
        '                  animation: _starCtrl,\n'
        '                  builder: (_, __) => CustomPaint(\n'
        '                    painter: _StarsPainter(_starCtrl.value, _starList))))),',
        '            if (dark) Positioned.fill(\n'
        '              child: IgnorePointer(\n'
        '                child: AnimatedBuilder(\n'
        '                  animation: _starCtrl,\n'
        '                  builder: (_, __) => CustomPaint(\n'
        '                    painter: _StarsPainter(_starCtrl.value, _starList))))),\n'
        '            if (dark) Positioned.fill( // S40-INCENSE-STACK\n'
        '              child: IgnorePointer(\n'
        '                child: AnimatedBuilder(\n'
        '                  animation: _starCtrl,\n'
        '                  builder: (_, __) => CustomPaint(\n'
        '                    painter: _IncensePainter(_starCtrl.value))))),',
        'Incense painter added to background Stack')

# Save home_screen.dart
_h('Saving home_screen.dart')
(SC / 'home_screen.dart').write_text(htxt, encoding='utf-8')
_ok('home_screen.dart saved')

# ══════════════════════════════════════════════════════════════════
# main.dart — dark theme void teal palette
# ══════════════════════════════════════════════════════════════════
_h('DESIGN-8 — main.dart dark theme void teal palette')
mtxt = ML.read_text(encoding='utf-8')

if '// S40-MAIN' in mtxt:
    _sk('main.dart already updated')
else:
    mtxt, _ = rep(mtxt,
        '    surface:    Color(0xFF0C1E28),\n'
        '    onSurface:  Color(0xFFE2CFA0),\n'
        '    secondary:  Color(0xFF1B6B80),\n'
        '    background: Color(0xFF061218),',
        '    surface:    Color(0xFF0F2420), // S40-MAIN\n'
        '    onSurface:  Color(0xFFE2CFA0),\n'
        '    secondary:  Color(0xFF1DB898),\n'
        '    background: Color(0xFF020D0C),',
        'dark theme surface + secondary + background → jade/teal/void')

    mtxt, _ = rep(mtxt,
        '  scaffoldBackgroundColor: const Color(0xFF061218),\n'
        '  appBarTheme: const AppBarTheme(\n'
        '    backgroundColor: Color(0xFF061218),',
        '  scaffoldBackgroundColor: const Color(0xFF020D0C),\n'
        '  appBarTheme: const AppBarTheme(\n'
        '    backgroundColor: Color(0xFF020D0C),',
        'scaffold + appbar bg → void #020D0C')

    # Also update the helper color in _cBg default
    mtxt, _ = rep(mtxt,
        "Color  _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);",
        "Color  _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF020D0C) : const Color(0xFFFAF7EE); // S40-MAIN-CBG",
        '_cBg dark default → void #020D0C')

    ML.write_text(mtxt, encoding='utf-8')
    _ok('main.dart saved')

# ══════════════════════════════════════════════════════════════════
# Summary
# ══════════════════════════════════════════════════════════════════
_h('SUMMARY')
ok_n = sum(1 for s, _ in _log if s == 'OK')
sk_n = sum(1 for s, _ in _log if s == 'SK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
for s, l in _log:
    icon = 'OK' if s == 'OK' else ('--' if s == 'SK' else 'XX')
    print(f'  {icon}  {l}')
_h(f'{ok_n} OK   {sk_n} SKIP   {xx_n} FAIL')

if xx_n == 0:
    print("""
  git add -A && git commit -m "S40: void-teal palette + jade cards + geo separators + incense particles" && git push
""")
else:
    print('\n  Some anchors not found — paste the output above back to Claude.\n')
