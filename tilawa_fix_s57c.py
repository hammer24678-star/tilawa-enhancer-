#!/usr/bin/env python3
"""
tilawa_fix_s57c.py — Correct anchors from diag_s57 output
"""
import sys
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

def _h(t): print(f'\n{"="*58}\n  {t}\n{"="*58}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'\n  XX  NOT FOUND — {m}\n'); sys.exit(1)

def rep(old, new, lbl):
    txt = HS.read_text(encoding='utf-8')
    if old not in txt: _xx(lbl)
    HS.write_text(txt.replace(old, new, 1), encoding='utf-8')
    _ok(lbl)

_h(f'tilawa_fix_s57c  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# BG-2: Remove IncensePainter (exact from diag line 651-656, 10-space indent)
_h('BG-2 — remove IncensePainter')
rep(
    '          if (dark) Positioned.fill(\n'
    '            child: IgnorePointer(\n'
    '              child: AnimatedBuilder(\n'
    '                animation: _geoRotCtrl,\n'
    '                builder: (_, __) => CustomPaint(\n'
    '                  painter: _IncensePainter(_geoRotCtrl.value))))),'
    ,
    '          // S57: IncensePainter removed'
    ,
    'IncensePainter removed'
)

# BG-3: GeoPainter already static — skip

# BG-4: Stars 28 → 18  (diag shows 28, not 55)
_h('BG-4 — Stars 28 → 18')
rep(
    '_starList = List.generate(28, (_) => _StarParticle(rng));',
    '_starList = List.generate(18, (_) => _StarParticle(rng));',
    'Stars 28 → 18'
)

# BG-5: Star opacity — current is the original from dart dump
_h('BG-5 — Stars opacity range softer')
rep(
    '      final op = 0.40 + 0.60 * (sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5);',
    '      final alpha = sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5;\n'
    '      final op = 0.28 + 0.72 * alpha;\n'
    '      final sz = s.size * (0.6 + 0.4 * alpha);',
    'Stars opacity range'
)

_h('BG-5b — Stars use sz not s.size')
rep(
    '        canvas.drawCircle(Offset(x, y), s.size, p);',
    '        // Bloom halo\n'
    '        p.color = p.color.withOpacity(op * 0.20);\n'
    '        p.maskFilter = MaskFilter.blur(BlurStyle.normal, sz * 3.0);\n'
    '        canvas.drawCircle(Offset(x, y), sz * 2.2, p);\n'
    '        p.maskFilter = null;\n'
    '        canvas.drawCircle(Offset(x, y), sz, p);',
    'Stars bloom halo + use sz'
)

# SPACING
_h('SPACING — server banner')
rep(
    'margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),\n'
    '        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),',
    'margin: const EdgeInsets.fromLTRB(16, 8, 16, 8),\n'
    '        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),',
    'Server banner margin'
)

_h('SPACING — engine selector margin')
rep(
    'margin: const EdgeInsets.fromLTRB(16,10,16,4),\n'
    '      decoration: BoxDecoration(\n'
    '        color: _bgSurface,',
    'margin: const EdgeInsets.fromLTRB(16,14,16,6),\n'
    '      decoration: BoxDecoration(\n'
    '        color: _bgSurface,',
    'Engine selector margin'
)

_h('SPACING — engine selector header')
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

_h('SPACING — engine card margin')
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

_h('SPACING — geo sep vertical padding')
rep(
    'padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),\n'
    '      child: Row(children: [\n'
    '        Expanded(child: Container(height: 1,\n'
    '          decoration: const BoxDecoration(gradient: LinearGradient(',
    'padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),\n'
    '      child: Row(children: [\n'
    '        Expanded(child: Container(height: 1,\n'
    '          decoration: const BoxDecoration(gradient: LinearGradient(',
    'Geo sep padding'
)

_h('SPACING — scroll bottom')
rep(
    'const SliverToBoxAdapter(child: SizedBox(height: 40)),',
    'const SliverToBoxAdapter(child: SizedBox(height: 60)),',
    'Bottom padding'
)

_h('DONE')
print('\n  git add -A && git commit -m "S57: clean background + breathing room" && git push\n')
