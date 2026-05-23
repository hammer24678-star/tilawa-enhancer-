#!/usr/bin/env python3
"""tilawa_fix_s57d — stars upgrade + all spacing (S57c aborted at BG-5)"""
import sys
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

def _h(t): print(f'\n{"="*56}\n  {t}\n{"="*56}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'\n  XX  NOT FOUND — {m}\n'); sys.exit(1)
def rep(old, new, lbl):
    txt = HS.read_text(encoding='utf-8')
    if old not in txt: _xx(lbl)
    HS.write_text(txt.replace(old, new, 1), encoding='utf-8')
    _ok(lbl)

_h(f'tilawa_fix_s57d  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ── BG-5: Stars — bloom glow + color variety ─────────────────────
_h('BG-5 — Stars bloom + gold/teal/white mix')
rep(
    '      final op = 0.45 + 0.55 * alpha;\n'
    '      final sz = s.size * (0.5 + 0.5 * alpha);\n'
    '      p.color = _gold.withOpacity(op);\n'
    '      canvas.drawCircle(Offset(x, y), sz, p);',

    '      final op = 0.22 + 0.78 * alpha;\n'
    '      final sz = s.size * (0.55 + 0.45 * alpha);\n'
    '      final idx = stars.indexOf(s);\n'
    '      final sc = idx % 5 == 0 ? _teal\n'
    '          : idx % 3 == 0 ? const Color(0xFFF0E8C8)\n'
    '          : _gold;\n'
    '      // Soft bloom\n'
    '      p.maskFilter = MaskFilter.blur(BlurStyle.normal, sz * 2.5);\n'
    '      p.color = sc.withOpacity(op * 0.25);\n'
    '      canvas.drawCircle(Offset(x, y), sz * 2.0, p);\n'
    '      // Sharp core\n'
    '      p.maskFilter = null;\n'
    '      p.color = sc.withOpacity(op);\n'
    '      canvas.drawCircle(Offset(x, y), sz, p);',

    'Stars bloom glow + color variety'
)

# ── SPACING ──────────────────────────────────────────────────────
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
print('\n  git add -A && git commit -m "S57: clean bg + bloom stars + breathing room" && git push\n')
