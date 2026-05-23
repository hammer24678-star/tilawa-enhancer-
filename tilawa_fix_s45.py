#!/usr/bin/env python3
"""
tilawa_fix_s45.py — S45: Full HTML parity + every-page theming
================================================================
Addresses all gap areas identified after S44:

HOME SCREEN
  H1  File card → mihrab arch top corners
  H2  File card empty label → "Drop your Quran audio into this sacred portal"
  H3  File card → mp3 · wav · m4a format hint
  H4  Progress card → mandala spinner above progress bar
  H5  Result card → khatam (two-squares star) behind score arc
  H6  New painters: _MandalaPainter, _KhatamPainter

SETTINGS SCREEN  (S1)
  S1  _cBg/_cCard/_cBorder dark → void/jade palette

HISTORY SCREEN  (V1)
  V1  _cBg/_cCard/_cBorder dark → void/jade palette

WELCOME SCREEN  (W1-W3)
  W1  Scaffold bg → void #020D0C
  W2  _cBg/_cCard/_cBorder dark → void/jade palette
  W3  _GeoPainter + _WelcomeStarsPainter teal → #1DB898

Run:
  cp /sdcard/Download/tilawa_fix_s45.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s45.py 2>&1 | tee /sdcard/Download/fix_s45.txt
  git add -A && git commit -m "S45: mihrab arch + mandala + khatam + every-page void palette" && git push
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
        print(f'  WW  {lbl}: {n} occurrences — replacing first only')
    _ok(lbl)
    return txt.replace(old, new, 1), True

_h(f'tilawa_fix_s45.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ══════════════════════════════════════════════════════════════════
# HOME SCREEN
# ══════════════════════════════════════════════════════════════════
hf = SC / 'home_screen.dart'
ht = hf.read_text(encoding='utf-8')

# H1 — File card: mihrab arch top corners
_h('H1 — File card mihrab arch corners')
if '// S45-ARCH' in ht:
    _sk('Arch corners already applied')
else:
    ht, _ = rep(ht,
        '            borderRadius: BorderRadius.circular(22),',
        '            borderRadius: const BorderRadius.only( // S45-ARCH\n'
        '              topLeft: Radius.circular(200),\n'
        '              topRight: Radius.circular(200),\n'
        '              bottomLeft: Radius.circular(22),\n'
        '              bottomRight: Radius.circular(22)),',
        'file card → arch top corners')

# H2 — File card: sacred portal label
_h('H2 — File card empty label → sacred portal')
if '// S45-PORTAL' in ht:
    _sk('Portal label already applied')
else:
    ht, _ = rep(ht,
        "                hasFile ? _file!.path.split('/').last : s.pickFile,",
        "                hasFile ? _file!.path.split('/').last // S45-PORTAL\n"
        "                  : (s.ar ? 'أسقط تلاوتك في هذا المحراب'\n"
        "                          : 'Drop your Quran audio into this sacred portal'),",
        'file card → sacred portal label')

# H3 — File card: mp3/wav/m4a format hint
_h('H3 — File card format hint mp3 · wav · m4a')
if '// S45-FMT' in ht:
    _sk('Format hint already present')
else:
    ht, _ = rep(ht,
        '              const SizedBox(height: 6),\n'
        '              Text(s.sizeLimit,',
        '              const SizedBox(height: 3),\n'
        "              if (!hasFile) Text('mp3  ·  wav  ·  m4a', // S45-FMT\n"
        '                textAlign: TextAlign.center,\n'
        '                style: const TextStyle(\n'
        '                  color: Color(0xFF1DB898),\n'
        '                  fontSize: 9, letterSpacing: 1.4)),\n'
        '              const SizedBox(height: 3),\n'
        '              Text(s.sizeLimit,',
        'format hint mp3/wav/m4a')

# H4 — Progress card: mandala spinner above progress bar
_h('H4 — Progress card mandala spinner')
if '// S45-MANDALA' in ht:
    _sk('Mandala already in progress card')
else:
    ht, _ = rep(ht,
        '        const SizedBox(height: 12),\n'
        '        ClipRRect(\n'
        '          borderRadius: BorderRadius.circular(8),\n'
        '          // S20-A: null = indeterminate (animated pulse) during server merge\n'
        '          child: LinearProgressIndicator(',
        '        const SizedBox(height: 6),\n'
        '        Center(child: SizedBox(width: 90, height: 90, // S45-MANDALA\n'
        '          child: AnimatedBuilder(\n'
        '            animation: _geoRotCtrl,\n'
        '            builder: (_, __) => CustomPaint(\n'
        '              painter: _MandalaPainter(_geoRotCtrl.value))))),\n'
        '        const SizedBox(height: 6),\n'
        '        ClipRRect(\n'
        '          borderRadius: BorderRadius.circular(8),\n'
        '          // S20-A: null = indeterminate (animated pulse) during server merge\n'
        '          child: LinearProgressIndicator(',
        'mandala spinner inserted before progress bar')

# H5 — Result card: khatam behind score arc
_h('H5 — Result card khatam star painter')
if '// S45-KHATAM' in ht:
    _sk('Khatam already in result card')
else:
    ht, _ = rep(ht,
        '              Stack(alignment: Alignment.center, children: [\n'
        '              // Burst particles on reveal\n'
        '              if (score >= 85) AnimatedBuilder(\n'
        '                animation: _resultCtrl,\n'
        '                builder: (_, __) => CustomPaint(\n'
        '                  size: const Size(170, 170),\n'
        '                  painter: _ScoreBurstPainter(\n'
        '                    progress: _resultCtrl.value,\n'
        '                    color: scoreColor))),',
        '              Stack(alignment: Alignment.center, children: [\n'
        '              // S45-KHATAM sacred geometry layer\n'
        '              AnimatedBuilder(\n'
        '                animation: _glowCtrl,\n'
        '                builder: (_, __) => CustomPaint(\n'
        '                  size: const Size(170, 170),\n'
        '                  painter: _KhatamPainter(\n'
        '                    t: _glowCtrl.value, color: scoreColor))),\n'
        '              // Burst particles on reveal\n'
        '              if (score >= 85) AnimatedBuilder(\n'
        '                animation: _resultCtrl,\n'
        '                builder: (_, __) => CustomPaint(\n'
        '                  size: const Size(170, 170),\n'
        '                  painter: _ScoreBurstPainter(\n'
        '                    progress: _resultCtrl.value,\n'
        '                    color: scoreColor))),',
        'khatam star added to result card Stack')

# H6 — Add _MandalaPainter + _KhatamPainter classes
_h('H6 — Add _MandalaPainter and _KhatamPainter classes')
if '// S45-MANDALA-CLASS' in ht:
    _sk('Painter classes already present')
else:
    NEW_PAINTERS = (
        '// S45-MANDALA-CLASS — 8-petal spinning mandala for processing screen\n'
        'class _MandalaPainter extends CustomPainter {\n'
        '  final double t; // 0..1 geoRotCtrl value\n'
        '  const _MandalaPainter(this.t);\n'
        '  @override\n'
        '  void paint(Canvas canvas, Size size) {\n'
        '    final cx = size.width / 2, cy = size.height / 2;\n'
        '    final r  = size.width / 2 - 4;\n'
        '    final angle = t * pi * 2;\n'
        '    final p = Paint()..style = PaintingStyle.stroke;\n'
        '    // 8 overlapping petal circles\n'
        '    p.color = const Color(0xFFC8A048).withOpacity(0.50);\n'
        '    p.strokeWidth = 0.9;\n'
        '    for (int i = 0; i < 8; i++) {\n'
        '      final a = (i / 8) * pi * 2 + angle;\n'
        '      canvas.drawCircle(\n'
        '        Offset(cx + r * 0.52 * cos(a), cy + r * 0.52 * sin(a)),\n'
        '        r * 0.40, p);\n'
        '    }\n'
        '    // Outer gold ring\n'
        '    p.color = const Color(0xFFD4AF37).withOpacity(0.38);\n'
        '    p.strokeWidth = 1.0;\n'
        '    canvas.drawCircle(Offset(cx, cy), r, p);\n'
        '    // Counter-rotating hexagon\n'
        '    p.color = const Color(0xFF1DB898).withOpacity(0.32);\n'
        '    p.strokeWidth = 0.8;\n'
        '    final hex = Path();\n'
        '    for (int i = 0; i < 6; i++) {\n'
        '      final a = (i / 6) * pi * 2 - angle * 0.5;\n'
        '      final x = cx + r * 0.50 * cos(a);\n'
        '      final y = cy + r * 0.50 * sin(a);\n'
        '      if (i == 0) hex.moveTo(x, y); else hex.lineTo(x, y);\n'
        '    }\n'
        '    hex.close();\n'
        '    canvas.drawPath(hex, p);\n'
        '    // 8-point inner star\n'
        '    p.color = const Color(0xFFD4AF37).withOpacity(0.45);\n'
        '    p.strokeWidth = 1.0;\n'
        '    final star = Path();\n'
        '    for (int i = 0; i < 16; i++) {\n'
        '      final a = (i / 16) * pi * 2 + angle * 0.25;\n'
        '      final rr = i.isEven ? r * 0.28 : r * 0.14;\n'
        '      final x = cx + rr * cos(a), y = cy + rr * sin(a);\n'
        '      if (i == 0) star.moveTo(x, y); else star.lineTo(x, y);\n'
        '    }\n'
        '    star.close();\n'
        '    canvas.drawPath(star, p);\n'
        '    canvas.drawCircle(Offset(cx, cy), 3,\n'
        '      Paint()..color = const Color(0xFFD4AF37).withOpacity(0.72)\n'
        '             ..style = PaintingStyle.fill);\n'
        '  }\n'
        '  @override bool shouldRepaint(_MandalaPainter o) => o.t != t;\n'
        '}\n'
        '\n'
        '// S45-KHATAM-CLASS — two rotated squares star for result screen\n'
        'class _KhatamPainter extends CustomPainter {\n'
        '  final double t;     // glow animation 0..1\n'
        '  final Color color;\n'
        '  const _KhatamPainter({required this.t, required this.color});\n'
        '  @override\n'
        '  void paint(Canvas canvas, Size size) {\n'
        '    final cx = size.width / 2, cy = size.height / 2;\n'
        '    final r  = size.width / 2 - 10;\n'
        '    final p  = Paint()..style = PaintingStyle.stroke;\n'
        '    // Square 1\n'
        '    p.color = color.withOpacity(0.12 + 0.10 * t);\n'
        '    p.strokeWidth = 1.0;\n'
        '    final sq1 = Path();\n'
        '    for (int i = 0; i < 4; i++) {\n'
        '      final a = (i / 4) * pi * 2 - pi / 4;\n'
        '      if (i == 0) sq1.moveTo(cx + r * cos(a), cy + r * sin(a));\n'
        '      else sq1.lineTo(cx + r * cos(a), cy + r * sin(a));\n'
        '    }\n'
        '    sq1.close();\n'
        '    canvas.drawPath(sq1, p);\n'
        '    // Square 2 (rotated 45°)\n'
        '    final sq2 = Path();\n'
        '    for (int i = 0; i < 4; i++) {\n'
        '      final a = (i / 4) * pi * 2 + pi / 4;\n'
        '      if (i == 0) sq2.moveTo(cx + r * cos(a), cy + r * sin(a));\n'
        '      else sq2.lineTo(cx + r * cos(a), cy + r * sin(a));\n'
        '    }\n'
        '    sq2.close();\n'
        '    canvas.drawPath(sq2, p);\n'
        '    // Pulsing outer glow ring\n'
        '    p.color = color.withOpacity(0.07 + 0.07 * t);\n'
        '    p.strokeWidth = 0.7;\n'
        '    canvas.drawCircle(Offset(cx, cy), r + 8, p);\n'
        '    // Inner circle\n'
        '    p.color = color.withOpacity(0.08 + 0.06 * t);\n'
        '    p.strokeWidth = 0.5;\n'
        '    canvas.drawCircle(Offset(cx, cy), r * 0.40, p);\n'
        '  }\n'
        '  @override bool shouldRepaint(_KhatamPainter o) =>\n'
        '      o.t != t || o.color != color;\n'
        '}\n'
        '\n'
    )
    ht, _ = rep(ht,
        '// S40-INCENSE — rising gold particle dots from HTML design',
        NEW_PAINTERS + '// S40-INCENSE — rising gold particle dots from HTML design',
        '_MandalaPainter + _KhatamPainter added before _IncensePainter')

_h('Saving home_screen.dart')
hf.write_text(ht, encoding='utf-8')
_ok('home_screen.dart saved')

# ══════════════════════════════════════════════════════════════════
# SETTINGS SCREEN
# ══════════════════════════════════════════════════════════════════
_h('S1 — settings_screen.dart: void/jade palette')
sf = SC / 'settings_screen.dart'
st = sf.read_text(encoding='utf-8')

if '// S45-SET' in st:
    _sk('Settings palette already updated')
else:
    # This is a StatelessWidget so color helpers are defined once
    st, _ = rep(st,
        '    Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n'
        '    Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);\n'
        '    Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);',
        '    Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF020D0C) : const Color(0xFFFAF7EE); // S45-SET\n'
        '    Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF0F2420) : const Color(0xFFF3EED9);\n'
        '    Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF1A4035) : const Color(0xFFD4C99A);',
        'settings _cBg/_cCard/_cBorder → void/jade')
    # Also update the Alert Dialog background
    st, _ = rep(st,
        "          backgroundColor: const Color(0xFF0C1E28),",
        "          backgroundColor: const Color(0xFF0F2420), // S45-SET-DLG",
        'settings dialog bg → jade')
    sf.write_text(st, encoding='utf-8')
    _ok('settings_screen.dart saved')

# ══════════════════════════════════════════════════════════════════
# HISTORY SCREEN
# ══════════════════════════════════════════════════════════════════
_h('V1 — history_screen.dart: void/jade palette')
vf = SC / 'history_screen.dart'
vt = vf.read_text(encoding='utf-8')

if '// S45-HIST' in vt:
    _sk('History palette already updated')
else:
    vt, _ = rep(vt,
        '    Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n'
        '    Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);\n'
        '    Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);',
        '    Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF020D0C) : const Color(0xFFFAF7EE); // S45-HIST\n'
        '    Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF0F2420) : const Color(0xFFF3EED9);\n'
        '    Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF1A4035) : const Color(0xFFD4C99A);',
        'history _cBg/_cCard/_cBorder → void/jade')
    vf.write_text(vt, encoding='utf-8')
    _ok('history_screen.dart saved')

# ══════════════════════════════════════════════════════════════════
# WELCOME SCREEN
# ══════════════════════════════════════════════════════════════════
_h('W1 — welcome_screen.dart: Scaffold bg → void #020D0C')
wf = SC / 'welcome_screen.dart'
wt = wf.read_text(encoding='utf-8')

if '// S45-WEL' in wt:
    _sk('Welcome screen already updated')
else:
    wt, _ = rep(wt,
        '      backgroundColor: const Color(0xFF020D17),',
        '      backgroundColor: const Color(0xFF020D0C), // S45-WEL',
        'welcome Scaffold bg → void')

    _h('W2 — welcome_screen.dart: color helpers → void/jade palette')
    wt, _ = rep(wt,
        '    Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n'
        '    Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);\n'
        '    Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);',
        '    Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF020D0C) : const Color(0xFFFAF7EE); // S45-WEL\n'
        '    Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF0F2420) : const Color(0xFFF3EED9);\n'
        '    Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF1A4035) : const Color(0xFFD4C99A);',
        'welcome _cBg/_cCard/_cBorder → void/jade')

    _h('W3 — welcome_screen.dart: _GeoPainter teal → #1DB898')
    wt, _ = rep(wt,
        "    ringPaint.color = const Color(0xFF1C8EA8).withOpacity(0.07);",
        "    ringPaint.color = const Color(0xFF1DB898).withOpacity(0.07); // S45-WEL-T",
        '_GeoPainter inner teal ring → #1DB898')
    wt, _ = rep(wt,
        "      ..color = const Color(0xFF1C8EA8).withOpacity(0.08)",
        "      ..color = const Color(0xFF1DB898).withOpacity(0.08) // S45-WEL-T2",
        '_GeoPainter star paint teal → #1DB898')

    _h('W3b — welcome_screen.dart: _WelcomeStarsPainter teal → #1DB898')
    wt, _ = rep(wt,
        "                : const Color(0xFF1C8EA8))\n"
        "            .withOpacity(alpha);",
        "                : const Color(0xFF1DB898)) // S45-WEL-T3\n"
        "            .withOpacity(alpha);",
        '_WelcomeStarsPainter teal → #1DB898')

    # Also update the lang toggle bg in welcome to match void palette
    wt, _ = rep(wt,
        "            color: const Color(0xFF161B22),\n"
        "              borderRadius: BorderRadius.circular(20),\n"
        "              border: Border.all(color: const Color(0xFF21262D))),",
        "            color: const Color(0xFF0F2420), // S45-WEL-LANG\n"
        "              borderRadius: BorderRadius.circular(20),\n"
        "              border: Border.all(color: const Color(0xFF1A4035))),",
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
    icon = 'OK' if s == 'OK' else ('--' if s == 'SK' else 'XX')
    print(f'  {icon}  {l}')
_h(f'{ok_n} OK   {sk_n} SKIP   {xx_n} FAIL')
if xx_n == 0:
    print("""
  git add -A && git commit -m "S45: mihrab arch + mandala + khatam + every-page void palette" && git push
""")
else:
    print('\n  Some anchors not found — paste output back to Claude.\n')
