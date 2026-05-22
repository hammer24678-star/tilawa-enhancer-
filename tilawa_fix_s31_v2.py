#!/usr/bin/env python3
"""tilawa_fix_s31_v2.py — exact anchors from diag_s31c"""
import re
from pathlib import Path
from datetime import datetime

SC  = Path.home() / 'tilawa-enhancer/lib/screens'
_log = []

def _h(t): print(f'\n{"═"*58}\n  {t}\n{"═"*58}')
def _ok(m): print(f'  ✅  {m}'); _log.append(('OK',m))
def _xx(m): print(f'  ❌  {m}'); _log.append(('XX',m))

def rep(txt, old, new, lbl):
    if old in txt:
        _ok(lbl); return txt.replace(old, new, 1), True
    _xx(f'NOT FOUND — {lbl}'); return txt, False

_h(f'tilawa_fix_s31_v2  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ═══════════════════════════════════════════════════════════
# home_screen.dart
# ═══════════════════════════════════════════════════════════
_h('home_screen.dart')
txt = (SC/'home_screen.dart').read_text(encoding='utf-8')

# 1 — Rotating geo (exact from diag line 623-625)
OLD_GEO = (
    "          if (dark) Positioned.fill(\n"
    "            child: IgnorePointer(\n"
    "              child: CustomPaint(painter: _GeoPainter())))),"
)
NEW_GEO = (
    "          if (dark) Positioned.fill(\n"
    "            child: IgnorePointer(\n"
    "              child: AnimatedBuilder(\n"
    "                animation: _geoRotCtrl,\n"
    "                builder: (_, __) => Transform.rotate(\n"
    "                  angle: _geoRotCtrl.value * 6.2832,\n"
    "                  child: CustomPaint(painter: _GeoPainter()))))),"
)
txt, _ = rep(txt, OLD_GEO, NEW_GEO, 'rotating geo background')

# 2 — Engine card decoration (exact from diag lines 929-934)
OLD_ENG = (
    "        decoration: BoxDecoration(\n"
    "          color: sel ? _tCard : Colors.transparent,\n"
    "          borderRadius: BorderRadius.circular(11),\n"
    "          border: Border.all(\n"
    "            color: sel ? col : _tBorder,\n"
    "            width: sel ? 1.4 : 0.8)),"
)
NEW_ENG = (
    "        decoration: BoxDecoration(\n"
    "          color: sel ? col.withOpacity(0.07) : Colors.transparent,\n"
    "          borderRadius: BorderRadius.circular(13),\n"
    "          border: Border.all(\n"
    "            color: sel ? col : _teal.withOpacity(0.18),\n"
    "            width: sel ? 1.8 : 0.7),\n"
    "          boxShadow: sel ? [BoxShadow(\n"
    "            color: col.withOpacity(0.18), blurRadius: 18)] : null),"
)
txt, _ = rep(txt, OLD_ENG, NEW_ENG, 'engine card: gold glow + tint')

# 3 — Engine card: left gold accent bar (inject Stack inside child:)
OLD_ENG_COL = (
    "        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [\n"
    "          // ── Collapsed header (always visible) ───────────────────────"
)
NEW_ENG_COL = (
    "        child: Stack(children: [\n"
    "          // Left accent bar\n"
    "          if (sel) Positioned(left: 0, top: 0, bottom: 0,\n"
    "            child: AnimatedContainer(\n"
    "              duration: const Duration(milliseconds: 280),\n"
    "              width: 3.5,\n"
    "              decoration: BoxDecoration(\n"
    "                color: col,\n"
    "                borderRadius: const BorderRadius.only(\n"
    "                  topLeft: Radius.circular(13),\n"
    "                  bottomLeft: Radius.circular(13)),\n"
    "                boxShadow: [BoxShadow(\n"
    "                  color: col.withOpacity(0.55), blurRadius: 8)]))),\n"
    "          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [\n"
    "          // ── Collapsed header (always visible) ───────────────────────"
)
txt, _ = rep(txt, OLD_ENG_COL, NEW_ENG_COL, 'engine card left accent bar Stack')

# Close the extra Stack — find AnimatedCrossFade that ends engine card
OLD_CROSSFADE = (
    "          AnimatedCrossFade(\n"
    "            duration: const Duration(milliseconds: 260),"
)
NEW_CROSSFADE = (
    "          ]), // end Column\n"
    "          ]), // end Stack (accent bar)\n"
    "          AnimatedCrossFade(\n"
    "            duration: const Duration(milliseconds: 260),"
)
txt, _ = rep(txt, OLD_CROSSFADE, ''.join(NEW_CROSSFADE), 'engine card close Stack/Column')

# 4 — File card decoration (exact from diag lines 1067-1074)
OLD_FILE = (
    "        color: _tCard,\n"
    "        borderRadius: BorderRadius.circular(14),\n"
    "        border: Border.all(\n"
    "          color: _file != null ? _tGold : _tBorder,\n"
    "          width: 1.5),\n"
    "        boxShadow: const [BoxShadow(\n"
    "          color: Color(0x26000000),\n"
    "          blurRadius: 12, offset: Offset(0, 3))]),"
)
NEW_FILE = (
    "        color: _file != null ? _bgSurface : _bgDeep,\n"
    "        borderRadius: BorderRadius.circular(16),\n"
    "        border: Border.all(\n"
    "          color: _file != null ? _gold : _teal.withOpacity(0.28),\n"
    "          width: _file != null ? 1.8 : 0.8),\n"
    "        boxShadow: _file != null ? [BoxShadow(\n"
    "          color: _gold.withOpacity(0.14),\n"
    "          blurRadius: 22, offset: const Offset(0, 4))] : null),"
)
txt, _ = rep(txt, OLD_FILE, NEW_FILE, 'file card Sacred Cosmos style')

# 5 — Audio bars in progress (exact from diag lines 1359-1363)
OLD_PROG = (
    "          child: Text(\n"
    "            _status.isEmpty ? s.processing : _status,\n"
    "            key: ValueKey(_status),\n"
    "            style: const TextStyle(\n"
    "              color: Color(0xFFC9D1D9), fontSize: 13)))),"
)
NEW_PROG = (
    "          child: Column(\n"
    "            crossAxisAlignment: CrossAxisAlignment.start,\n"
    "            mainAxisSize: MainAxisSize.min, children: [\n"
    "            Text(\n"
    "              _status.isEmpty ? s.processing : _status,\n"
    "              key: ValueKey(_status),\n"
    "              style: const TextStyle(\n"
    "                color: _textA, fontSize: 13)),\n"
    "            const SizedBox(height: 10),\n"
    "            AnimatedBuilder(\n"
    "              animation: _audioBarsCtrl,\n"
    "              builder: (_, __) {\n"
    "                const n = 14;\n"
    "                return Row(\n"
    "                  mainAxisSize: MainAxisSize.min,\n"
    "                  crossAxisAlignment: CrossAxisAlignment.end,\n"
    "                  children: List.generate(n, (i) {\n"
    "                    final h = 4.0 + 14.0 * (sin(\n"
    "                      (_audioBarsCtrl.value + i/n) * 6.2832 * 1.5\n"
    "                    ) * 0.5 + 0.5);\n"
    "                    final lit = (i / n) < _progress;\n"
    "                    return Container(\n"
    "                      width: 3.5, height: h,\n"
    "                      margin: const EdgeInsets.only(right: 2.5),\n"
    "                      decoration: BoxDecoration(\n"
    "                        color: lit\n"
    "                          ? _gold.withOpacity(0.65 + 0.35 * _audioBarsCtrl.value)\n"
    "                          : _teal.withOpacity(0.22),\n"
    "                        borderRadius: BorderRadius.circular(2)));\n"
    "                  }));\n"
    "              }),\n"
    "          ])))),"
)
txt, _ = rep(txt, OLD_PROG, NEW_PROG, 'audio bars in progress card')

# 6 — Result card entrance easing (exact from diag lines 642-644)
OLD_EASE = "            parent: _resultCtrl, curve: Curves.easeOut),"
NEW_EASE = "            parent: _resultCtrl, curve: Curves.easeOutCubic),"
txt, _ = rep(txt, OLD_EASE, NEW_EASE, 'result entrance easeOutCubic')

# 7 — Score ring + count-up (find score label in _resultCard)
OLD_SCORE = (
    "        // Score\n"
    "        Row(\n"
    "          mainAxisAlignment: MainAxisAlignment.center,\n"
    "          crossAxisAlignment: CrossAxisAlignment.baseline,\n"
    "          textBaseline: TextBaseline.alphabetic,\n"
    "          children: [\n"
    "            Text(label, style: TextStyle(\n"
    "              color: scoreColor,\n"
    "              fontWeight: FontWeight.bold, fontSize: 16)),\n"
    "            const SizedBox(width: 10),\n"
    "            Text('${score.toStringAsFixed(1)}/100',\n"
    "              style: TextStyle(\n"
    "                color: scoreColor,\n"
    "                fontWeight: FontWeight.w900, fontSize: 34)),\n"
    "          ]),"
)
NEW_SCORE = (
    "        // Score ring with count-up\n"
    "        Builder(builder: (_) {\n"
    "          if (_scoreCtrl.status == AnimationStatus.dismissed) {\n"
    "            _scoreAnim = Tween(begin: 0.0, end: score).animate(\n"
    "              CurvedAnimation(parent: _scoreCtrl,\n"
    "                curve: Curves.easeOutCubic));\n"
    "            _scoreCtrl.forward();\n"
    "          }\n"
    "          return Stack(alignment: Alignment.center, children: [\n"
    "            // Burst particles\n"
    "            if (score >= 85) AnimatedBuilder(\n"
    "              animation: _scoreCtrl,\n"
    "              builder: (_, __) => CustomPaint(\n"
    "                size: const Size(130, 130),\n"
    "                painter: _ScoreBurstPainter(\n"
    "                  progress: _scoreCtrl.value, color: scoreColor))),\n"
    "            // Ring\n"
    "            Container(\n"
    "              width: 130, height: 130,\n"
    "              decoration: BoxDecoration(\n"
    "                shape: BoxShape.circle,\n"
    "                color: scoreColor.withOpacity(0.07),\n"
    "                border: Border.all(\n"
    "                  color: scoreColor.withOpacity(0.45), width: 2.5),\n"
    "                boxShadow: [BoxShadow(\n"
    "                  color: scoreColor.withOpacity(0.20),\n"
    "                  blurRadius: 28, spreadRadius: 3)]),\n"
    "              child: Column(\n"
    "                mainAxisAlignment: MainAxisAlignment.center,\n"
    "                children: [\n"
    "                  Text(label, style: TextStyle(\n"
    "                    color: scoreColor,\n"
    "                    fontWeight: FontWeight.bold, fontSize: 13)),\n"
    "                  const SizedBox(height: 2),\n"
    "                  AnimatedBuilder(\n"
    "                    animation: _scoreCtrl,\n"
    "                    builder: (_, __) => Text(\n"
    "                      _scoreAnim.value.toStringAsFixed(1),\n"
    "                      style: TextStyle(\n"
    "                        color: scoreColor,\n"
    "                        fontWeight: FontWeight.w900, fontSize: 34))),\n"
    "                  Text('/100', style: TextStyle(\n"
    "                    color: scoreColor.withOpacity(0.55), fontSize: 10)),\n"
    "                ])),\n"
    "          ]);\n"
    "        }),"
)
txt, _ = rep(txt, OLD_SCORE, NEW_SCORE, 'score ring + count-up + burst')

# 8 — Server dot ripple (find the actual dot in _serverBanner)
OLD_DOT = (
    "            AnimatedBuilder(\n"
    "              animation: _glowCtrl,\n"
    "              builder: (_, __) => Container(\n"
    "                width: 9, height: 9,\n"
    "                decoration: BoxDecoration(\n"
    "                  shape: BoxShape.circle,\n"
    "                  color: _serverUp ? _ok : _err,\n"
    "                  boxShadow: [BoxShadow(\n"
    "                    color: (_serverUp ? _ok : _err)\n"
    "                      .withOpacity(0.4 + 0.4 * _glowCtrl.value),\n"
    "                    blurRadius: 6 + 6 * _glowCtrl.value)]))),"
)
NEW_DOT = (
    "            AnimatedBuilder(\n"
    "              animation: _glowCtrl,\n"
    "              builder: (_, __) {\n"
    "                final t = _glowCtrl.value;\n"
    "                final c = _serverUp ? _ok : _err;\n"
    "                return SizedBox(width: 22, height: 22,\n"
    "                  child: Stack(alignment: Alignment.center, children: [\n"
    "                    if (_serverUp) Container(\n"
    "                      width: 9 + 11 * t, height: 9 + 11 * t,\n"
    "                      decoration: BoxDecoration(\n"
    "                        shape: BoxShape.circle,\n"
    "                        border: Border.all(\n"
    "                          color: c.withOpacity(0.55 * (1 - t)),\n"
    "                          width: 1.5))),\n"
    "                    Container(width: 9, height: 9,\n"
    "                      decoration: BoxDecoration(\n"
    "                        shape: BoxShape.circle, color: c,\n"
    "                        boxShadow: [BoxShadow(\n"
    "                          color: c.withOpacity(0.45 + 0.45 * t),\n"
    "                          blurRadius: 6 + 8 * t)])),\n"
    "                  ]));\n"
    "              }),"
)
txt, _ = rep(txt, OLD_DOT, NEW_DOT, 'server dot ripple ring')

(SC/'home_screen.dart').write_text(txt, encoding='utf-8')
_ok('home_screen.dart saved')


# ═══════════════════════════════════════════════════════════
# welcome_screen.dart — wrap body with geo Stack
# ═══════════════════════════════════════════════════════════
_h('welcome_screen.dart')
txt = (SC/'welcome_screen.dart').read_text(encoding='utf-8')

# Welcome has no Stack/painters — wrap body SafeArea with Stack
OLD_W_BODY = (
    "      body: SafeArea(\n"
    "        child: FadeTransition(\n"
    "          opacity: _fade,\n"
    "          child: SlideTransition(\n"
    "            position: _slide,\n"
    "            child: _page == 0 ? _page0(s) : _page == 1 ? _page1(s) : _page2(s),\n"
    "          ),\n"
    "        ),\n"
    "      ),"
)
NEW_W_BODY = (
    "      body: Stack(children: [\n"
    "        // Rotating geo background\n"
    "        Positioned.fill(child: AnimatedBuilder(\n"
    "          animation: _geoRotCtrl,\n"
    "          builder: (_, __) => Transform.rotate(\n"
    "            angle: _geoRotCtrl.value * 6.2832,\n"
    "            child: CustomPaint(painter: _GeoPainter())))),\n"
    "        // Star particles\n"
    "        Positioned.fill(child: AnimatedBuilder(\n"
    "          animation: _pulseCtrl,\n"
    "          builder: (_, __) => CustomPaint(\n"
    "            painter: _WelcomeStarsPainter(_pulseCtrl.value)))),\n"
    "        SafeArea(\n"
    "          child: FadeTransition(\n"
    "            opacity: _fade,\n"
    "            child: SlideTransition(\n"
    "              position: _slide,\n"
    "              child: _page == 0 ? _page0(s) : _page == 1 ? _page1(s) : _page2(s),\n"
    "            ),\n"
    "          ),\n"
    "        ),\n"
    "      ]),"
)
txt, _ = rep(txt, OLD_W_BODY, NEW_W_BODY, 'welcome: wrap body with geo+stars Stack')

# Append _GeoPainter + _WelcomeStarsPainter to welcome_screen if not present
if '_GeoPainter' not in txt:
    txt = txt.rstrip() + '''

// ── Welcome background painters ──────────────────────────────────────────────
class _GeoPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = const Color(0xFF1B6B80).withOpacity(0.08)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8;
    const cell = 110.0;
    final cols = (size.width / cell).ceil() + 2;
    final rows = (size.height / (cell * 0.866)).ceil() + 2;
    for (int row = 0; row < rows; row++) {
      for (int col = 0; col < cols; col++) {
        final cx = col * cell + (row.isOdd ? cell * 0.5 : 0) - cell * 0.5;
        final cy = row * cell * 0.866 - cell * 0.5;
        _star8(canvas, Offset(cx, cy), cell * 0.28, p);
      }
    }
  }
  void _star8(Canvas canvas, Offset c, double r, Paint p) {
    final path = Path();
    for (int i = 0; i < 8; i++) {
      final oa = i * 3.14159 / 4 - 3.14159 / 2;
      final ia = oa + 3.14159 / 8;
      final ox = c.dx + r * cos(oa); final oy = c.dy + r * sin(oa);
      final ix = c.dx + r * 0.38 * cos(ia); final iy = c.dy + r * 0.38 * sin(ia);
      if (i == 0) path.moveTo(ox, oy); else path.lineTo(ox, oy);
      path.lineTo(ix, iy);
    }
    path.close(); canvas.drawPath(path, p);
  }
  @override bool shouldRepaint(_GeoPainter _) => false;
}

class _WelcomeStarsPainter extends CustomPainter {
  final double t;
  _WelcomeStarsPainter(this.t);
  static final _rng = List.generate(26, (i) => [
    (i * 0.618033) % 1.0,  // x
    (i * 0.381966) % 1.0,  // y
    0.5 + (i % 5) * 0.45,  // size
    i * 0.7,                // phase
    0.3 + (i % 3) * 0.35,  // speed
  ]);
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()..maskFilter = const MaskFilter.blur(BlurStyle.normal, 1.2);
    for (final s in _rng) {
      final a = t * 6.2832 * s[4] + s[3];
      final x = s[0] * size.width  + sin(a) * size.width  * 0.018;
      final y = s[1] * size.height + cos(a * 0.73) * size.height * 0.013;
      final op = 0.20 + 0.65 * (sin(t * 6.2832 * 1.2 + s[3]) * 0.5 + 0.5);
      p.color = const Color(0xFFD4AF37).withOpacity(op);
      canvas.drawCircle(Offset(x, y), s[2], p);
    }
  }
  @override bool shouldRepaint(_WelcomeStarsPainter o) => o.t != t;
}
'''
    _ok('Welcome painters appended')

# Add dart:math import if missing
if "import 'dart:math'" not in txt:
    OLD_IMP = "import 'package:flutter/material.dart';"
    NEW_IMP = "import 'dart:math';\nimport 'package:flutter/material.dart';"
    txt, _ = rep(txt, OLD_IMP, NEW_IMP, 'add dart:math to welcome')

(SC/'welcome_screen.dart').write_text(txt, encoding='utf-8')
_ok('welcome_screen.dart saved')


# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
_h('SUMMARY')
ok = sum(1 for s,_ in _log if s=='OK')
xx = sum(1 for s,_ in _log if s=='XX')
for s,l in _log: print(f'  {"✅" if s=="OK" else "❌"}  {l}')
_h(f'{ok} ✅   {xx} ❌')
print('\n  git add -A && git commit -m "S31v2: score ring, audio bars, orbital rings, ripple, welcome painters" && git push\n')
