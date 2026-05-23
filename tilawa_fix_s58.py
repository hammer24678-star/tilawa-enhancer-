#!/usr/bin/env python3
"""
tilawa_fix_s58.py — restore & upgrade rising particle animation
===============================================================
- Adds _particleCtrl (6s repeat) — faster than _starCtrl
- Upgrades _IncensePainter: more particles (18), engine-tinted color,
  teal accent every 5th dot, faster rise, wider drift (matches JSX)
- Re-inserts IncensePainter into the body Stack (was removed in S57)

Run:
  cp /sdcard/Download/tilawa_fix_s58.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s58.py && git add -A && git commit -m "S58: rising particle animation restored + engine-tinted" && git push
"""
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

def ok(m):  print(f'OK  {m}')
def xx(m):  print(f'XX  {m}'); raise SystemExit(1)
def sk(m):  print(f'--  {m}')

def rep(t, old, new, lbl):
    if old not in t: xx(f'NOT FOUND — {lbl}')
    ok(lbl); return t.replace(old, new, 1)

print(f'\n=== tilawa_fix_s58.py  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ===\n')

ht = HS.read_text(encoding='utf-8')

# ── 1. Add _particleCtrl field declaration ───────────────────────────────────
if '_particleCtrl' in ht:
    sk('_particleCtrl already declared')
else:
    ht = rep(ht,
        '  late final AnimationController _resultCtrl; // S29: result card entrance',
        '  late final AnimationController _resultCtrl; // S29: result card entrance\n'
        '  late final AnimationController _particleCtrl; // S58: rising particles',
        '_particleCtrl field declaration')

# ── 2. Init _particleCtrl in initState ───────────────────────────────────────
if '_particleCtrl = AnimationController' in ht:
    sk('_particleCtrl already initialised')
else:
    ht = rep(ht,
        '    _resultCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(milliseconds: 600));',
        '    _resultCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(milliseconds: 600));\n'
        '    _particleCtrl = AnimationController( // S58\n'
        '        vsync: this, duration: const Duration(seconds: 6))\n'
        '      ..repeat();',
        '_particleCtrl init')

# ── 3. Dispose _particleCtrl ─────────────────────────────────────────────────
if '_particleCtrl.dispose()' in ht:
    sk('_particleCtrl already disposed')
else:
    ht = rep(ht,
        '    _resultCtrl.dispose();',
        '    _resultCtrl.dispose();\n'
        '    _particleCtrl.dispose(); // S58',
        '_particleCtrl dispose')

# ── 4. Re-insert IncensePainter into body Stack ──────────────────────────────
if '_IncensePainter(_particleCtrl' in ht:
    sk('IncensePainter already in Stack')
else:
    ht = rep(ht,
        '          // S57: IncensePainter removed\n'
        '          if (dark) Positioned.fill(\n'
        '            child: IgnorePointer(\n'
        '              child: AnimatedBuilder(\n'
        '                animation: _starCtrl,\n'
        '                builder: (_, __) => CustomPaint(\n'
        '                  painter: _StarsPainter(_starCtrl.value, _starList))))),',
        '          // S58: rising particles (engine-tinted incense dots)\n'
        '          if (dark) Positioned.fill(\n'
        '            child: IgnorePointer(\n'
        '              child: AnimatedBuilder(\n'
        '                animation: _particleCtrl,\n'
        '                builder: (_, __) => CustomPaint(\n'
        '                  painter: _IncensePainter(\n'
        '                    _particleCtrl.value, _engineColor))))),\n'
        '          if (dark) Positioned.fill(\n'
        '            child: IgnorePointer(\n'
        '              child: AnimatedBuilder(\n'
        '                animation: _starCtrl,\n'
        '                builder: (_, __) => CustomPaint(\n'
        '                  painter: _StarsPainter(_starCtrl.value, _starList))))),',
        'IncensePainter re-inserted into Stack')

# ── 5. Upgrade _IncensePainter class ─────────────────────────────────────────
if '// S58-PARTICLES' in ht:
    sk('_IncensePainter already upgraded')
else:
    OLD_PAINTER = (
        'class _IncensePainter extends CustomPainter {\n'
        '  final double t;\n'
        '  _IncensePainter(this.t);\n'
        '  static const _xs = [0.15, 0.28, 0.42, 0.50, 0.62, 0.72, 0.82, 0.45, 0.58, 0.68];\n'
        '  @override\n'
        '  void paint(Canvas canvas, Size size) {\n'
        '    final p = Paint()..style = PaintingStyle.fill;\n'
        '    for (int i = 0; i < _xs.length; i++) {\n'
        '      final phase = ((t * 0.65) + i / _xs.length) % 1.0;\n'
        '      final dx = _xs[i] * size.width + sin(phase * 6.2832 * 1.5 + i) * 18;\n'
        '      final dy = size.height * (1.0 - phase * 0.72);\n'
        '      final op = phase < 0.12 ? phase / 0.12\n'
        '          : phase > 0.75 ? (1.0 - phase) / 0.25 : 0.42;\n'
        '      p.color = const Color(0xFFC8A048).withOpacity(op * 0.5);\n'
        '      canvas.drawCircle(Offset(dx, dy), 1.4 + (i % 2) * 0.7, p);\n'
        '    }\n'
        '  }\n'
        '  @override bool shouldRepaint(_IncensePainter o) => o.t != t;\n'
        '}'
    )
    NEW_PAINTER = (
        'class _IncensePainter extends CustomPainter {\n'
        '  // S58-PARTICLES — 18 rising dots, engine-tinted, matches JSX Particles()\n'
        '  final double t;\n'
        '  final Color engCol;\n'
        '  _IncensePainter(this.t, this.engCol);\n'
        '  static const _xs = [\n'
        '    0.08, 0.15, 0.22, 0.30, 0.38, 0.45,\n'
        '    0.52, 0.58, 0.65, 0.72, 0.80, 0.88,\n'
        '    0.18, 0.35, 0.55, 0.68, 0.78, 0.42,\n'
        '  ];\n'
        '  static const _teal = Color(0xFF1DB898);\n'
        '  @override\n'
        '  void paint(Canvas canvas, Size size) {\n'
        '    final p = Paint()..style = PaintingStyle.fill;\n'
        '    for (int i = 0; i < _xs.length; i++) {\n'
        '      // stagger each particle with a fixed offset so they cover full height\n'
        '      final phase = ((t + i / _xs.length) % 1.0);\n'
        '      final drift = sin(phase * 6.2832 * 1.8 + i * 1.3) * 22;\n'
        '      final dx = _xs[i] * size.width + drift;\n'
        '      final dy = size.height * (1.0 - phase);\n'
        '      // fade in at bottom, fade out near top (matches JSX: 10%→50%→100%)\n'
        '      final op = phase < 0.10 ? phase / 0.10\n'
        '          : phase > 0.72 ? (1.0 - phase) / 0.28 : 0.55;\n'
        '      final isTeal = i % 5 == 3;\n'
        '      final baseCol = isTeal ? _teal : engCol;\n'
        '      p.color = baseCol.withOpacity(op * 0.52);\n'
        '      final r = (i % 3 == 0) ? 2.0 : 1.4;\n'
        '      canvas.drawCircle(Offset(dx, dy), r, p);\n'
        '    }\n'
        '  }\n'
        '  @override bool shouldRepaint(_IncensePainter o) =>\n'
        '      o.t != t || o.engCol != engCol;\n'
        '}'
    )
    ht = rep(ht, OLD_PAINTER, NEW_PAINTER, '_IncensePainter upgraded (18 dots, engine-tinted)')

HS.write_text(ht, encoding='utf-8')
ok('home_screen.dart saved')
print('\ngit add -A && git commit -m "S58: rising particle animation restored + engine-tinted" && git push')
