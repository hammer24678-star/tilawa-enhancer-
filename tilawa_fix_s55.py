#!/usr/bin/env python3
"""
tilawa_fix_s55 — Rich background animations
============================================
Strict methodology: sys.exit(1) on first missing anchor.
Verify after every patch. One commit.

Changes:
  1. Stars: 28 → 55, size bigger, brighter, scale-pulse like HTML
  2. GeoPainter: wrapped in slow rotation (uses existing _geoRotCtrl)
  3. IncensePainter: particles larger, more opaque, wider drift
  4. Add radial gold pulse layer (new AnimatedBuilder behind everything)
"""
import sys
from pathlib import Path

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = HS.read_text(encoding='utf-8')

def rep(old, new, lbl):
    global txt
    if old not in txt:
        print(f'\n  XX  NOT FOUND — {lbl}')
        print('       ABORT. Fix anchor then re-run.\n')
        sys.exit(1)
    txt = txt.replace(old, new, 1)
    if new not in txt:
        print(f'\n  XX  VERIFY FAILED after replace — {lbl}\n')
        sys.exit(1)
    print(f'  OK  {lbl}')

# ── 1. Stars: 28 → 55 ────────────────────────────────────────────────────────
rep(
    "_starList = List.generate(28, (_) => _StarParticle(rng));",
    "_starList = List.generate(55, (_) => _StarParticle(rng));",
    'Stars count 28 → 55'
)

# ── 2. Star size bigger ───────────────────────────────────────────────────────
rep(
    "          size = 1.4 + r.nextDouble() * 2.8,",
    "          size = 1.8 + r.nextDouble() * 3.2,",
    'Star size 1.4+2.8 → 1.8+3.2'
)

# ── 3. Stars brighter + scale pulse matching HTML twinkle ────────────────────
rep(
    "      final op = 0.40 + 0.60 * (sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5);",
    "      final alpha = sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5;\n"
    "      final op = 0.45 + 0.55 * alpha;\n"
    "      final sz = s.size * (0.5 + 0.5 * alpha);",
    'Stars opacity + scale pulse'
)

rep(
    "        canvas.drawCircle(Offset(x, y), s.size, p);",
    "        canvas.drawCircle(Offset(x, y), sz, p);",
    'Stars use scaled size'
)

# ── 4. GeoPainter: slow rotation via _geoRotCtrl ────────────────────────────
rep(
    "          if (dark) Positioned.fill(\n"
    "            child: IgnorePointer(\n"
    "              child: CustomPaint(painter: _GeoPainter()))),",
    "          if (dark) Positioned.fill(\n"
    "            child: IgnorePointer(\n"
    "              child: AnimatedBuilder(\n"
    "                animation: _geoRotCtrl,\n"
    "                builder: (_, __) => Transform.rotate(\n"
    "                  angle: _geoRotCtrl.value * 6.2832 * 0.08,\n"
    "                  child: CustomPaint(painter: _GeoPainter()))))),",
    'GeoPainter slow rotation'
)

# ── 5. Incense: larger dots, more opaque, wider drift ────────────────────────
rep(
    "      final op = phase < 0.12 ? phase / 0.12\n"
    "          : phase > 0.75 ? (1.0 - phase) / 0.25 : 0.42;\n"
    "      p.color = const Color(0xFFC8A048).withOpacity(op * 0.5);\n"
    "      canvas.drawCircle(Offset(dx, dy), 1.4 + (i % 2) * 0.7, p);",
    "      final op = phase < 0.12 ? phase / 0.12\n"
    "          : phase > 0.75 ? (1.0 - phase) / 0.25 : 0.62;\n"
    "      p.color = const Color(0xFFC8A048).withOpacity(op * 0.72);\n"
    "      canvas.drawCircle(Offset(dx, dy), 2.0 + (i % 3) * 0.9, p);",
    'Incense dots larger + more opaque'
)

rep(
    "        final dx = _xs[i] * size.width + sin(phase * 6.2832 * 1.5 + i) * 9;",
    "        final dx = _xs[i] * size.width + sin(phase * 6.2832 * 1.5 + i) * 18;",
    'Incense wider horizontal drift'
)

# ── 6. Add radial gold pulse layer between geo and stars ─────────────────────
rep(
    "          if (dark) Positioned.fill(\n"
    "            child: IgnorePointer(\n"
    "              child: AnimatedBuilder(\n"
    "                animation: _starCtrl,\n"
    "                builder: (_, __) => CustomPaint(\n"
    "                  painter: _StarsPainter(_starCtrl.value, _starList))))),",
    "          if (dark) Positioned.fill(\n"
    "            child: IgnorePointer(\n"
    "              child: AnimatedBuilder(\n"
    "                animation: _glowCtrl,\n"
    "                builder: (_, __) => CustomPaint(\n"
    "                  painter: _RadialPulsePainter(_glowCtrl.value))))),\n"
    "          if (dark) Positioned.fill(\n"
    "            child: IgnorePointer(\n"
    "              child: AnimatedBuilder(\n"
    "                animation: _starCtrl,\n"
    "                builder: (_, __) => CustomPaint(\n"
    "                  painter: _StarsPainter(_starCtrl.value, _starList))))),",
    'Radial pulse layer added'
)

# ── 7. Add _RadialPulsePainter class before _StarParticle ────────────────────
rep(
    "// ── Sacred Cosmos painters ────────────────────────────────────────────────────",
    "// ── Sacred Cosmos painters ────────────────────────────────────────────────────\n"
    "\n"
    "// S55: Central radial gold pulse — breathes with _glowCtrl (2.8s)\n"
    "class _RadialPulsePainter extends CustomPainter {\n"
    "  final double t;\n"
    "  _RadialPulsePainter(this.t);\n"
    "  @override\n"
    "  void paint(Canvas canvas, Size size) {\n"
    "    final cx = size.width * 0.5;\n"
    "    final cy = size.height * 0.38; // slightly above center like a mihrab\n"
    "    final p = Paint()..style = PaintingStyle.fill;\n"
    "    // 3 concentric pulse rings\n"
    "    for (int i = 0; i < 3; i++) {\n"
    "      final phase = (t + i * 0.33) % 1.0;\n"
    "      final r = 60.0 + phase * 220.0;\n"
    "      final op = (1.0 - phase) * (i == 0 ? 0.10 : 0.06);\n"
    "      p.color = const Color(0xFFC8A048).withOpacity(op);\n"
    "      p.maskFilter = const MaskFilter.blur(BlurStyle.normal, 18);\n"
    "      canvas.drawCircle(Offset(cx, cy), r, p);\n"
    "    }\n"
    "    // Central soft glow core\n"
    "    p.maskFilter = const MaskFilter.blur(BlurStyle.normal, 40);\n"
    "    p.color = const Color(0xFFC8A048).withOpacity(0.06 + 0.06 * t);\n"
    "    canvas.drawCircle(Offset(cx, cy), 80, p);\n"
    "    // Teal counter-pulse\n"
    "    p.maskFilter = const MaskFilter.blur(BlurStyle.normal, 24);\n"
    "    p.color = const Color(0xFF1DB898).withOpacity(0.04 + 0.04 * (1 - t));\n"
    "    canvas.drawCircle(Offset(cx, cy), 120 + 40 * t, p);\n"
    "  }\n"
    "  @override bool shouldRepaint(_RadialPulsePainter o) => o.t != t;\n"
    "}",
    'RadialPulsePainter class added'
)

HS.write_text(txt, encoding='utf-8')
print('\n  ✅ All patches applied. Verify:')
print('  grep -n "_RadialPulsePainter\\|55.*StarParticle\\|0.08.*geoRot" lib/screens/home_screen.dart')
print('\n  git add -A && git commit -m "S55: rich background — 55 stars, scale pulse, geo rotation, radial glow, bigger incense" && git push')
