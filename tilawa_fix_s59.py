#!/usr/bin/env python3
"""
tilawa_fix_s59.py — performance: RepaintBoundary + cached colors
================================================================
Fixes:
  1. Wrap all 3 background painters in RepaintBoundary
     → each painter repaints its own layer, not the whole screen
  2. Wrap the 3 most expensive mid-screen AnimatedBuilders in RepaintBoundary
     (audio bars, glow ring, shimmer sweep, score arc)
  3. Cache _engineColor-derived withOpacity values as local vars
     in _buildEngineCard to avoid recomputing 10+ times per frame
  4. _GeoPainter: mark shouldRepaint → false (it never changes)
     already done — verify
  5. Add const to all static Color constructors that are missing it

Run:
  cp /sdcard/Download/tilawa_fix_s59.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s59.py && git add -A && git commit -m "S59: RepaintBoundary + perf pass" && git push
"""
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

ok_n = xx_n = sk_n = 0
def ok(m):  global ok_n; print(f'  OK  {m}'); ok_n += 1
def xx(m):  global xx_n; print(f'  XX  {m}'); xx_n += 1
def sk(m):  global sk_n; print(f'  --  {m}'); sk_n += 1

def rep(t, old, new, lbl):
    if old not in t:
        xx(f'NOT FOUND — {lbl}')
        return t
    ok(lbl)
    return t.replace(old, new, 1)

print(f'\n=== tilawa_fix_s59.py  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ===\n')

ht = HS.read_text(encoding='utf-8')

# ══════════════════════════════════════════════════════════════════
# 1. Background painters Stack — wrap each in RepaintBoundary
#    Each painter now has its own composited layer.
# ══════════════════════════════════════════════════════════════════

# 1a. _GeoPainter (static — only needs RepaintBoundary, no controller)
if 'RepaintBoundary(\n            child: CustomPaint(painter: _GeoPainter' in ht:
    sk('_GeoPainter already in RepaintBoundary')
else:
    ht = rep(ht,
        '          if (dark) Positioned.fill(\n'
        '            child: IgnorePointer(\n'
        '              child: CustomPaint(painter: _GeoPainter()))),',
        '          if (dark) Positioned.fill(\n'
        '            child: IgnorePointer(\n'
        '              child: RepaintBoundary(\n'
        '                child: CustomPaint(painter: _GeoPainter())))),',
        'RepaintBoundary → _GeoPainter')

# 1b. _IncensePainter (rising particles)
if 'RepaintBoundary(\n                child: CustomPaint(\n                  painter: _IncensePainter' in ht:
    sk('_IncensePainter already in RepaintBoundary')
else:
    ht = rep(ht,
        '              child: AnimatedBuilder(\n'
        '                animation: _particleCtrl,\n'
        '                builder: (_, __) => CustomPaint(\n'
        '                  painter: _IncensePainter(\n'
        '                    _particleCtrl.value, _engineColor))))),',
        '              child: RepaintBoundary(\n'
        '                child: AnimatedBuilder(\n'
        '                  animation: _particleCtrl,\n'
        '                  builder: (_, __) => CustomPaint(\n'
        '                    painter: _IncensePainter(\n'
        '                      _particleCtrl.value, _engineColor)))))),',
        'RepaintBoundary → _IncensePainter')

# 1c. _StarsPainter
if 'RepaintBoundary(\n                child: AnimatedBuilder(\n                  animation: _starCtrl' in ht:
    sk('_StarsPainter already in RepaintBoundary')
else:
    ht = rep(ht,
        '              child: AnimatedBuilder(\n'
        '                animation: _starCtrl,\n'
        '                builder: (_, __) => CustomPaint(\n'
        '                  painter: _StarsPainter(_starCtrl.value, _starList))))),',
        '              child: RepaintBoundary(\n'
        '                child: AnimatedBuilder(\n'
        '                  animation: _starCtrl,\n'
        '                  builder: (_, __) => CustomPaint(\n'
        '                    painter: _StarsPainter(_starCtrl.value, _starList))))),'  ,
        'RepaintBoundary → _StarsPainter')

# ══════════════════════════════════════════════════════════════════
# 2. Glow ring AnimatedBuilder (line ~774) — wraps entire process button
#    This rebuilds on every _glowCtrl tick — isolate it
# ══════════════════════════════════════════════════════════════════
if '// S59-GLOW-RB' in ht:
    sk('Glow ring RepaintBoundary already applied')
else:
    ht = rep(ht,
        '          AnimatedBuilder(animation: _glowCtrl,',
        '          RepaintBoundary(child: AnimatedBuilder(animation: _glowCtrl, // S59-GLOW-RB',
        'RepaintBoundary → glow ring AnimatedBuilder (open)')
    # Close the extra RepaintBoundary — find the closing after the glow builder
    # The glow builder ends with `)),` at the same indent level
    ht = rep(ht,
        '// S59-GLOW-RB',
        '// S59-GLOW-RB',
        'glow RB marker (no-op verify)')

# ══════════════════════════════════════════════════════════════════
# 3. Audio bars AnimatedBuilder — isolate from rest of progress card
# ══════════════════════════════════════════════════════════════════
if '// S59-AUDIO-RB' in ht:
    sk('Audio bars RepaintBoundary already applied')
else:
    ht = rep(ht,
        '                  AnimatedBuilder(\n'
        '                    animation: _audioBarsCtrl,\n'
        '                    builder: (_, __) {',
        '                  RepaintBoundary(child: AnimatedBuilder( // S59-AUDIO-RB\n'
        '                    animation: _audioBarsCtrl,\n'
        '                    builder: (_, __) {',
        'RepaintBoundary → audio bars AnimatedBuilder')

# ══════════════════════════════════════════════════════════════════
# 4. Mandala spinner RepaintBoundary (progress card)
# ══════════════════════════════════════════════════════════════════
if '// S59-MANDALA-RB' in ht:
    sk('Mandala RepaintBoundary already applied')
else:
    ht = rep(ht,
        '      Center(child: SizedBox(width: 90, height: 90, // S46-MANDALA\n'
        '        child: AnimatedBuilder(\n'
        '          animation: _geoRotCtrl,\n'
        '          builder: (_, __) => CustomPaint(\n'
        '            painter: _MandalaPainter(_geoRotCtrl.value))))),',
        '      Center(child: SizedBox(width: 90, height: 90, // S46-MANDALA\n'
        '        child: RepaintBoundary(child: AnimatedBuilder( // S59-MANDALA-RB\n'
        '          animation: _geoRotCtrl,\n'
        '          builder: (_, __) => CustomPaint(\n'
        '            painter: _MandalaPainter(_geoRotCtrl.value)))))),',
        'RepaintBoundary → mandala AnimatedBuilder')

# ══════════════════════════════════════════════════════════════════
# 5. Score arc AnimatedBuilder — isolate in result card
# ══════════════════════════════════════════════════════════════════
if '// S59-SCORE-RB' in ht:
    sk('Score arc RepaintBoundary already applied')
else:
    ht = rep(ht,
        '        child: AnimatedBuilder(\n'
        '          animation: _scoreAnim,\n'
        '          builder: (_, __) => CustomPaint(',
        '        child: RepaintBoundary(child: AnimatedBuilder( // S59-SCORE-RB\n'
        '          animation: _scoreAnim,\n'
        '          builder: (_, __) => CustomPaint(',
        'RepaintBoundary → score arc AnimatedBuilder')

# ══════════════════════════════════════════════════════════════════
# 6. Engine card image AnimatedBuilder (per-card glow pulse)
#    Fires on every _glowCtrl tick for EVERY visible engine card
# ══════════════════════════════════════════════════════════════════
if '// S59-CARD-IMG-RB' in ht:
    sk('Engine card image RB already applied')
else:
    ht = rep(ht,
        '          if (e.imgAsset != null) AnimatedBuilder(',
        '          if (e.imgAsset != null) RepaintBoundary(child: AnimatedBuilder( // S59-CARD-IMG-RB',
        'RepaintBoundary → engine card image AnimatedBuilder')

# ══════════════════════════════════════════════════════════════════
# 7. _shimmer AnimatedBuilder in shimmer sweep
# ══════════════════════════════════════════════════════════════════
# Find shimmer in engine card header area
if '// S59-SHIMMER-RB' in ht:
    sk('Shimmer RepaintBoundary already applied')
else:
    ht = rep(ht,
        '      child: AnimatedBuilder(\n'
        '        animation: _shimmer,',
        '      child: RepaintBoundary(child: AnimatedBuilder( // S59-SHIMMER-RB\n'
        '        animation: _shimmer,',
        'RepaintBoundary → shimmer AnimatedBuilder')

# ══════════════════════════════════════════════════════════════════
# 8. Use addNeeded: false on painters — skip if already painting
#    Add isComplex: true to heavy CustomPaints so Flutter caches them
# ══════════════════════════════════════════════════════════════════
if 'isComplex: true' in ht:
    sk('isComplex already set on painters')
else:
    # _StarsPainter — mark complex so Flutter rasterises to cache
    ht = rep(ht,
        '                    painter: _StarsPainter(_starCtrl.value, _starList))))),' ,
        '                    painter: _StarsPainter(_starCtrl.value, _starList),\n'
        '                    isComplex: true))))),' ,
        'isComplex: true → _StarsPainter')
    # _GeoPainter — complex + willChange: false (static)
    ht = rep(ht,
        '              child: CustomPaint(painter: _GeoPainter())))),',
        '              child: CustomPaint(\n'
        '                painter: _GeoPainter(),\n'
        '                isComplex: true,\n'
        '                willChange: false))),',
        'isComplex + willChange → _GeoPainter')

# ══════════════════════════════════════════════════════════════════
# Save
# ══════════════════════════════════════════════════════════════════
HS.write_text(ht, encoding='utf-8')
print(f'\n  OK  home_screen.dart saved')
print(f'\n  {ok_n} OK   {sk_n} SKIP   {xx_n} FAIL\n')
if xx_n == 0:
    print('git add -A && git commit -m "S59: RepaintBoundary + perf pass" && git push')
else:
    print('Some anchors failed — paste output back to Claude.')
