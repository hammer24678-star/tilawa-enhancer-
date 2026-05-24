#!/usr/bin/env python3
"""
tilawa_fix_s59b.py — wrap 5 remaining AnimatedBuilders in RepaintBoundary
Run:
  cp /sdcard/Download/tilawa_fix_s59b.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s59b.py && git add -A && git commit -m "S59b: remaining RepaintBoundary" && git push
"""
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
ok_n = xx_n = sk_n = 0

def ok(m):  global ok_n; print(f'  OK  {m}'); ok_n += 1
def xx(m):  global xx_n; print(f'  XX  {m}'); xx_n += 1
def sk(m):  global sk_n; print(f'  --  {m}'); sk_n += 1

def rep(t, old, new, lbl):
    if old not in t: xx(f'NOT FOUND — {lbl}'); return t
    ok(lbl); return t.replace(old, new, 1)

print(f'\n=== tilawa_fix_s59b.py  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ===\n')

ht = HS.read_text(encoding='utf-8')

# 1. Orbital ring (line 781) — merges _glowCtrl + _geoRotCtrl
if '// S59b-ORBITAL-RB' in ht:
    sk('orbital ring RB already done')
else:
    ht = rep(ht,
        '          // Orbital ring + logo\n'
        '          // S31-3RINGS\n'
        '          AnimatedBuilder(\n'
        '            animation: Listenable.merge([_glowCtrl, _geoRotCtrl]),',
        '          // Orbital ring + logo\n'
        '          // S31-3RINGS\n'
        '          RepaintBoundary(child: AnimatedBuilder( // S59b-ORBITAL-RB\n'
        '            animation: Listenable.merge([_glowCtrl, _geoRotCtrl]),',
        'orbital ring AnimatedBuilder')

# 2. Icon button glow (line 879) — _glowCtrl on each icon
if '// S59b-ICONBTN-RB' in ht:
    sk('icon button RB already done')
else:
    ht = rep(ht,
        '      child: AnimatedBuilder(\n'
        '        animation: _glowCtrl,\n'
        '        builder: (_, __) => Container(\n'
        '          padding: const EdgeInsets.all(10),\n'
        '          decoration: BoxDecoration(\n'
        '            color: _bgCard, shape: BoxShape.circle,',
        '      child: RepaintBoundary(child: AnimatedBuilder( // S59b-ICONBTN-RB\n'
        '        animation: _glowCtrl,\n'
        '        builder: (_, __) => Container(\n'
        '          padding: const EdgeInsets.all(10),\n'
        '          decoration: BoxDecoration(\n'
        '            color: _bgCard, shape: BoxShape.circle,',
        'icon button glow AnimatedBuilder')

# 3. Server dot pulse (line 926) — _glowCtrl
if '// S59b-SRVDOT-RB' in ht:
    sk('server dot RB already done')
else:
    ht = rep(ht,
        '              AnimatedBuilder(\n'
        '                animation: _glowCtrl,\n'
        '                builder: (_, __) {\n'
        '                  final t = _glowCtrl.value;\n'
        '                  final c = _serverUp ? _ok : _err;',
        '              RepaintBoundary(child: AnimatedBuilder( // S59b-SRVDOT-RB\n'
        '                animation: _glowCtrl,\n'
        '                builder: (_, __) {\n'
        '                  final t = _glowCtrl.value;\n'
        '                  final c = _serverUp ? _ok : _err;',
        'server dot AnimatedBuilder')

# 4. Engine selector glow ring (line 1056)
if '// S59b-ENGRING-RB' in ht:
    sk('engine ring RB already done')
else:
    ht = rep(ht,
        '        AnimatedBuilder(\n'
        '          animation: _glowCtrl,\n'
        '          builder: (_, __) {\n'
        '            final g = _glowCtrl.value;',
        '        RepaintBoundary(child: AnimatedBuilder( // S59b-ENGRING-RB\n'
        '          animation: _glowCtrl,\n'
        '          builder: (_, __) {\n'
        '            final g = _glowCtrl.value;',
        'engine selector ring AnimatedBuilder')

# 5. _scoreAnim / score arc — find via _scoreAnim usage
if '// S59b-SCORE-RB' in ht:
    sk('score arc RB already done')
else:
    # Score arc is the AnimatedBuilder wrapping _scoreAnim
    import re
    m = re.search(
        r'(        child: AnimatedBuilder\(\n'
        r'          animation: _scoreAnim,\n'
        r'          builder: \(_, __\) => CustomPaint\()',
        ht)
    if m:
        old = m.group(0)
        new = (
            '        child: RepaintBoundary(child: AnimatedBuilder( // S59b-SCORE-RB\n'
            '          animation: _scoreAnim,\n'
            '          builder: (_, __) => CustomPaint('
        )
        ht = ht.replace(old, new, 1)
        ok('score arc AnimatedBuilder')
    else:
        # fallback — search more loosely
        m2 = re.search(r'animation: _scoreAnim,', ht)
        if m2:
            # dump context
            lines = ht.splitlines()
            ln = ht[:m2.start()].count('\n')
            for i in range(max(0,ln-3), min(len(lines), ln+4)):
                print(f'  {i+1:5}  {repr(lines[i][:110])}')
        xx('score arc AnimatedBuilder — check dump above')

HS.write_text(ht, encoding='utf-8')
print(f'\n  OK  saved  |  {ok_n} OK  {sk_n} SKIP  {xx_n} FAIL\n')
if xx_n == 0:
    print('git add -A && git commit -m "S59b: remaining RepaintBoundary" && git push')
else:
    print('Paste output back to Claude.')
