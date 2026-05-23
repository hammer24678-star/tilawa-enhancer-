#!/usr/bin/env python3
"""
tilawa_fix_s57.py — Breathing room + refined background
=========================================================
Problems being fixed:
  1. Background: 4 competing painters → 2 elegant ones
     Remove RadialPulsePainter (cheap concentric rings)
     Remove IncensePainter (noisy gold dots)
     Reduce stars 55 → 18 (quality over quantity)
     Make GeoPainter static + half opacity
  2. Spacing: every section gets proper breathing room
  3. Engine card: more padding, cleaner proportions
  4. Header: more vertical air between logo / title / pill
  5. Star quality: larger bloom glow per star (not just size)
  6. Sliver padding: bottom padding so content doesn't hug edge

Run:
  cp /sdcard/Download/tilawa_fix_s57.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s57.py 2>&1 | tee /sdcard/Download/fix_s57.txt
  git add -A && git commit -m "S57: breathing room + refined background" && git push
"""
import sys
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

def _h(t): print(f'\n{"="*58}\n  {t}\n{"="*58}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'\n  XX  NOT FOUND — {m}\n  ABORT.\n'); sys.exit(1)

def rep(old, new, lbl):
    txt = HS.read_text(encoding='utf-8')
    if old not in txt: _xx(lbl)
    HS.write_text(txt.replace(old, new, 1), encoding='utf-8')
    _ok(lbl)

_h(f'tilawa_fix_s57.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ══════════════════════════════════════════════════════════
# 1. BACKGROUND — remove RadialPulsePainter layer
# ══════════════════════════════════════════════════════════
_h('BG-1 — remove RadialPulsePainter layer')
rep(
    '          if (dark) Positioned.fill(\n'
    '            child: IgnorePointer(\n'
    '              child: AnimatedBuilder(\n'
    '                animation: _glowCtrl,\n'
    '                builder: (_, __) => CustomPaint(\n'
    '                  painter: _RadialPulsePainter(_glowCtrl.value))))),\n'
    '          if (dark) Positioned.fill(\n'
    '            child: IgnorePointer(\n'
    '              child: AnimatedBuilder(\n'
    '                animation: _starCtrl,\n'
    '                builder: (_, __) => CustomPaint(\n'
    '                  painter: _StarsPainter(_starCtrl.value, _starList))))),',
    '          if (dark) Positioned.fill(\n'
    '            child: IgnorePointer(\n'
    '              child: AnimatedBuilder(\n'
    '                animation: _starCtrl,\n'
    '                builder: (_, __) => CustomPaint(\n'
    '                  painter: _StarsPainter(_starCtrl.value, _starList))))),',
    'RadialPulsePainter layer removed'
)

# ══════════════════════════════════════════════════════════
# 2. BACKGROUND — remove IncensePainter layer
# ══════════════════════════════════════════════════════════
_h('BG-2 — remove IncensePainter layer')
rep(
    '            if (dark) Positioned.fill( // S40-INCENSE-STACK\n'
    '              child: IgnorePointer(\n'
    '                child: AnimatedBuilder(\n'
    '                  animation: _starCtrl,\n'
    '                  builder: (_, __) => CustomPaint(\n'
    '                    painter: _IncensePainter(_starCtrl.value))))),',
    '            // S57: IncensePainter removed — too noisy',
    'IncensePainter layer removed'
)

# ══════════════════════════════════════════════════════════
# 3. BACKGROUND — GeoPainter: remove rotation, static
# ══════════════════════════════════════════════════════════
_h('BG-3 — GeoPainter static (remove rotation wrapper)')
rep(
    '          if (dark) Positioned.fill(\n'
    '            child: IgnorePointer(\n'
    '              child: AnimatedBuilder(\n'
    '                animation: _geoRotCtrl,\n'
    '                builder: (_, __) => Transform.rotate(\n'
    '                  angle: _geoRotCtrl.value * 6.2832 * 0.08,\n'
    '                  child: CustomPaint(painter: _GeoPainter()))))),',
    '          if (dark) Positioned.fill(\n'
    '            child: IgnorePointer(\n'
    '              child: CustomPaint(painter: _GeoPainter()))),',
    'GeoPainter rotation removed — static'
)

# ══════════════════════════════════════════════════════════
# 4. STARS — 55 → 18
# ══════════════════════════════════════════════════════════
_h('STARS — count 55 → 18')
rep(
    '_starList = List.generate(55, (_) => _StarParticle(rng));',
    '_starList = List.generate(18, (_) => _StarParticle(rng));',
    'Stars 55 → 18'
)

# ══════════════════════════════════════════════════════════
# 5. STARS — bigger, softer glow bloom
# ══════════════════════════════════════════════════════════
_h('STARS — upgrade painter to bloom glow')
rep(
    '      final alpha = sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5;\n'
    '      final op = 0.45 + 0.55 * alpha;\n'
    '      final sz = s.size * (0.5 + 0.5 * alpha);',
    '      final alpha = sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5;\n'
    '      final op = 0.30 + 0.70 * alpha;\n'
    '      final sz = s.size * (0.6 + 0.4 * alpha);',
    'Stars opacity range + scale range refined'
)

# Add bloom glow per star (MaskFilter before draw)
rep(
    '        p.color = (i % 4 == 0 ? _gold : (i % 3 == 0 ? _teal : Colors.white))\n'
    '            .withOpacity(op);\n'
    '        p.maskFilter = null;\n'
    '        canvas.drawCircle(Offset(x, y), sz, p);',
    '        final starColor = (i % 4 == 0 ? _gold : (i % 3 == 0 ? _teal : Colors.white));\n'
    '        // Soft bloom halo\n'
    '        p.color = starColor.withOpacity(op * 0.22);\n'
    '        p.maskFilter = MaskFilter.blur(BlurStyle.normal, sz * 2.8);\n'
    '        canvas.drawCircle(Offset(x, y), sz * 2.0, p);\n'
    '        // Sharp core\n'
    '        p.color = starColor.withOpacity(op);\n'
    '        p.maskFilter = null;\n'
    '        canvas.drawCircle(Offset(x, y), sz, p);',
    'Stars: bloom halo + sharp core'
)

# ══════════════════════════════════════════════════════════
# 6. SPACING — server banner more vertical margin
# ══════════════════════════════════════════════════════════
_h('SPACING — server banner')
rep(
    'margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),\n'
    '        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),',
    'margin: const EdgeInsets.fromLTRB(16, 8, 16, 8),\n'
    '        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),',
    'Server banner margin 4→8'
)

# ══════════════════════════════════════════════════════════
# 7. SPACING — engine selector more top margin
# ══════════════════════════════════════════════════════════
_h('SPACING — engine selector')
rep(
    'margin: const EdgeInsets.fromLTRB(16,10,16,4),\n'
    '      decoration: BoxDecoration(\n'
    '        color: _bgSurface,',
    'margin: const EdgeInsets.fromLTRB(16,14,16,6),\n'
    '      decoration: BoxDecoration(\n'
    '        color: _bgSurface,',
    'Engine selector margin bottom 4→6, top 10→14'
)

# ══════════════════════════════════════════════════════════
# 8. SPACING — engine selector header row more padding
# ══════════════════════════════════════════════════════════
_h('SPACING — engine selector header padding')
rep(
    'padding: const EdgeInsets.fromLTRB(16,14,16,10),\n'
    '          child: Row(children: [\n'
    '            const Icon(Icons.tune_rounded,',
    'padding: const EdgeInsets.fromLTRB(18,16,18,12),\n'
    '          child: Row(children: [\n'
    '            const Icon(Icons.tune_rounded,',
    'Engine header padding L/R 16→18, T 14→16, B 10→12'
)

# ══════════════════════════════════════════════════════════
# 9. SPACING — engine card row padding
# ══════════════════════════════════════════════════════════
_h('SPACING — engine card row padding')
rep(
    '            padding: const EdgeInsets.fromLTRB(12,11,12,11),\n'
    '              child: Row(children: [\n'
    '                AnimatedContainer(\n'
    '                  duration: const Duration(milliseconds: 320),\n'
    '                  curve: Curves.easeOutBack,\n'
    '                  width: 18, height: 18,',
    '            padding: const EdgeInsets.fromLTRB(14,13,14,13),\n'
    '              child: Row(children: [\n'
    '                AnimatedContainer(\n'
    '                  duration: const Duration(milliseconds: 320),\n'
    '                  curve: Curves.easeOutBack,\n'
    '                  width: 18, height: 18,',
    'Engine card row padding 12/11 → 14/13'
)

# ══════════════════════════════════════════════════════════
# 10. SPACING — engine card margin between cards
# ══════════════════════════════════════════════════════════
_h('SPACING — engine card inter-card margin')
rep(
    'margin: const EdgeInsets.fromLTRB(8,3,8,3),\n'
    '          curve: Curves.easeOutBack,',
    'margin: const EdgeInsets.fromLTRB(10,4,10,4),\n'
    '          curve: Curves.easeOutBack,',
    'Engine card margin 8/3 → 10/4'
)

# ══════════════════════════════════════════════════════════
# 11. SPACING — file card more margin
# ══════════════════════════════════════════════════════════
_h('SPACING — file card margin')
rep(
    'margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),\n'
    '          decoration: BoxDecoration(\n'
    '            color: hasFile',
    'margin: const EdgeInsets.fromLTRB(16, 14, 16, 8),\n'
    '          decoration: BoxDecoration(\n'
    '            color: hasFile',
    'File card top margin 10→14, bottom 4→8'
)

# ══════════════════════════════════════════════════════════
# 12. SPACING — file card inner padding
# ══════════════════════════════════════════════════════════
_h('SPACING — file card inner padding')
rep(
    'padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),\n'
    '            child: Column(children: [',
    'padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),\n'
    '            child: Column(children: [',
    'File card inner padding 20/22→24/28'
)

# ══════════════════════════════════════════════════════════
# 13. SPACING — header: logo → title gap
# ══════════════════════════════════════════════════════════
_h('SPACING — header logo → title gap')
rep(
    '            const SizedBox(height: 16),\n'
    '            // App name — large gold gradient',
    '            const SizedBox(height: 22),\n'
    '            // App name — large gold gradient',
    'Header logo→title gap 16→22'
)

# ══════════════════════════════════════════════════════════
# 14. SPACING — header title → subtitle pill gap
# ══════════════════════════════════════════════════════════
_h('SPACING — header title → pill gap')
rep(
    '            const SizedBox(height: 6),\n'
    '            // Subtitle pill',
    '            const SizedBox(height: 10),\n'
    '            // Subtitle pill',
    'Header title→pill gap 6→10'
)

# ══════════════════════════════════════════════════════════
# 15. SPACING — geo sep vertical padding
# ══════════════════════════════════════════════════════════
_h('SPACING — geo separator vertical padding')
rep(
    'padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),\n'
    '      child: Row(children: [\n'
    '        Expanded(child: Container(height: 1,\n'
    '          decoration: const BoxDecoration(gradient: LinearGradient(',
    'padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),\n'
    '      child: Row(children: [\n'
    '        Expanded(child: Container(height: 1,\n'
    '          decoration: const BoxDecoration(gradient: LinearGradient(',
    'Geo sep vertical padding 2→6'
)

# ══════════════════════════════════════════════════════════
# 16. SPACING — bottom row more top margin
# ══════════════════════════════════════════════════════════
_h('SPACING — scroll list bottom padding')
rep(
    'const SliverToBoxAdapter(child: SizedBox(height: 40)),',
    'const SliverToBoxAdapter(child: SizedBox(height: 60)),',
    'Bottom scroll padding 40→60'
)

_h('DONE')
print(f"""
  git add -A && git commit -m "S57: breathing room + clean background" && git push
""")
