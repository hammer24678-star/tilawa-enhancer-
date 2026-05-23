#!/usr/bin/env python3
"""
tilawa_fix_s57b.py — Continue S57 from BG-2 onward
BG-1 already applied. BG-2 failed: IncensePainter uses _geoRotCtrl not _starCtrl.
This script fixes that + runs all remaining S57 patches (3-16).

Run:
  cp /sdcard/Download/tilawa_fix_s57b.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s57b.py 2>&1 | tee /sdcard/Download/fix_s57b.txt
  git add -A && git commit -m "S57: breathing room + clean background" && git push
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

def skip_if_absent(old, new, lbl):
    txt = HS.read_text(encoding='utf-8')
    if old not in txt:
        print(f'  --  SKIP (already done) — {lbl}')
        return
    HS.write_text(txt.replace(old, new, 1), encoding='utf-8')
    _ok(lbl)

_h(f'tilawa_fix_s57b.py  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ══════════════════════════════════════════════════════════
# BG-2 — IncensePainter uses _geoRotCtrl (correct anchor)
# ══════════════════════════════════════════════════════════
_h('BG-2 — remove IncensePainter layer (correct anchor)')
rep(
    '            if (dark) Positioned.fill( // S40-INCENSE-STACK\n'
    '              child: IgnorePointer(\n'
    '                child: AnimatedBuilder(\n'
    '                  animation: _geoRotCtrl,\n'
    '                  builder: (_, __) => CustomPaint(\n'
    '                    painter: _IncensePainter(_geoRotCtrl.value))))),',
    '            // S57: IncensePainter removed',
    'IncensePainter removed'
)

# ══════════════════════════════════════════════════════════
# BG-3 — GeoPainter static
# ══════════════════════════════════════════════════════════
_h('BG-3 — GeoPainter static')
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
    'GeoPainter static'
)

# ══════════════════════════════════════════════════════════
# BG-4 — Stars 55 → 18
# ══════════════════════════════════════════════════════════
_h('BG-4 — Stars 55 → 18')
rep(
    '_starList = List.generate(55, (_) => _StarParticle(rng));',
    '_starList = List.generate(18, (_) => _StarParticle(rng));',
    'Stars 55 → 18'
)

# ══════════════════════════════════════════════════════════
# BG-5 — Star opacity range
# ══════════════════════════════════════════════════════════
_h('BG-5 — Stars: softer opacity range')
rep(
    '      final op = 0.45 + 0.55 * alpha;\n'
    '      final sz = s.size * (0.5 + 0.5 * alpha);',
    '      final op = 0.28 + 0.72 * alpha;\n'
    '      final sz = s.size * (0.6 + 0.4 * alpha);',
    'Stars opacity + scale range refined'
)

# ══════════════════════════════════════════════════════════
# BG-6 — Star bloom halo
# ══════════════════════════════════════════════════════════
_h('BG-6 — Stars bloom glow halo')
rep(
    '        canvas.drawCircle(Offset(x, y), sz, p);',
    '        // Bloom halo\n'
    '        p.color = p.color.withOpacity(op * 0.18);\n'
    '        p.maskFilter = MaskFilter.blur(BlurStyle.normal, sz * 3.0);\n'
    '        canvas.drawCircle(Offset(x, y), sz * 2.2, p);\n'
    '        p.maskFilter = null;\n'
    '        canvas.drawCircle(Offset(x, y), sz, p);',
    'Stars bloom halo added'
)

# ══════════════════════════════════════════════════════════
# SPACING — server banner
# ══════════════════════════════════════════════════════════
_h('SPACING — server banner')
rep(
    'margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),\n'
    '        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),',
    'margin: const EdgeInsets.fromLTRB(16, 8, 16, 8),\n'
    '        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),',
    'Server banner margin'
)

# ══════════════════════════════════════════════════════════
# SPACING — engine selector
# ══════════════════════════════════════════════════════════
_h('SPACING — engine selector outer margin')
rep(
    'margin: const EdgeInsets.fromLTRB(16,10,16,4),\n'
    '      decoration: BoxDecoration(\n'
    '        color: _bgSurface,',
    'margin: const EdgeInsets.fromLTRB(16,14,16,6),\n'
    '      decoration: BoxDecoration(\n'
    '        color: _bgSurface,',
    'Engine selector margin'
)

_h('SPACING — engine selector header padding')
rep(
    'padding: const EdgeInsets.fromLTRB(16,14,16,10),\n'
    '          child: Row(children: [\n'
    '            const Icon(Icons.tune_rounded,',
    'padding: const EdgeInsets.fromLTRB(18,16,18,12),\n'
    '          child: Row(children: [\n'
    '            const Icon(Icons.tune_rounded,',
    'Engine header padding'
)

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
    'Engine card row padding'
)

_h('SPACING — engine card inter-card margin')
rep(
    'margin: const EdgeInsets.fromLTRB(8,3,8,3),\n'
    '          curve: Curves.easeOutBack,',
    'margin: const EdgeInsets.fromLTRB(10,5,10,5),\n'
    '          curve: Curves.easeOutBack,',
    'Engine card margin'
)

_h('SPACING — file card margin')
rep(
    'margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),\n'
    '          decoration: BoxDecoration(\n'
    '            color: hasFile',
    'margin: const EdgeInsets.fromLTRB(16, 14, 16, 8),\n'
    '          decoration: BoxDecoration(\n'
    '            color: hasFile',
    'File card margin'
)

_h('SPACING — file card inner padding')
rep(
    'padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),\n'
    '            child: Column(children: [',
    'padding: const EdgeInsets.fromLTRB(24, 28, 24, 24),\n'
    '            child: Column(children: [',
    'File card inner padding'
)

_h('SPACING — header logo→title gap')
rep(
    '            const SizedBox(height: 16),\n'
    '            // App name — large gold gradient',
    '            const SizedBox(height: 22),\n'
    '            // App name — large gold gradient',
    'Header logo→title gap'
)

_h('SPACING — header title→pill gap')
rep(
    '            const SizedBox(height: 6),\n'
    '            // Subtitle pill',
    '            const SizedBox(height: 10),\n'
    '            // Subtitle pill',
    'Header title→pill gap'
)

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
    'Geo sep vertical padding'
)

_h('SPACING — scroll bottom padding')
rep(
    'const SliverToBoxAdapter(child: SizedBox(height: 40)),',
    'const SliverToBoxAdapter(child: SizedBox(height: 60)),',
    'Bottom scroll padding'
)

_h('DONE')
print('\n  git add -A && git commit -m "S57: breathing room + clean background" && git push\n')
