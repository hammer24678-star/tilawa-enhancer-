#!/usr/bin/env python3
"""tilawa_diag_s40.py — print exact lines around failing anchors"""
from pathlib import Path

SC = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = SC.read_text(encoding='utf-8')
lines = txt.splitlines()

def show(label, keyword, ctx=3):
    print(f'\n{"─"*60}')
    print(f'  SEARCH: {label}')
    print(f'  KEYWORD: {repr(keyword[:60])}')
    for i, l in enumerate(lines):
        if keyword in l:
            start = max(0, i - ctx)
            end   = min(len(lines), i + ctx + 1)
            for j in range(start, end):
                marker = '>>>' if j == i else '   '
                print(f'  {marker} {j+1:4}  {repr(lines[j])}')
            return
    print('  *** NOT FOUND ***')
    # print nearby lines if we can guess location
    print()

# ── 1. _bgCard constant ──────────────────────────────────────────
show('_bgCard constant', '_bgCard')

# ── 2. BG gradient ───────────────────────────────────────────────
show('BG gradient S34', 'S34-BG-GRADIENT')
show('BG gradient color array', '0xFF020D17')

# ── 3. AppBar gradient colors ────────────────────────────────────
show('AppBar gradient 061F32', '0xFF061F32')
show('FlexibleSpaceBar gradient', 'FlexibleSpaceBar')

# ── 4. File card ─────────────────────────────────────────────────
show('S32-FILE-CARD', 'S32-FILE-CARD')
show('File card color 071929', '0xFF071929')
show('File card border 1C8EA8', '1C8EA8')

# ── 5. Progress card ─────────────────────────────────────────────
show('S35-PROGRESS-CARD', 'S35-PROGRESS-CARD')
show('Progress gradient colors', '0xFF0B2233')

# ── 6. Engine card non-sel ───────────────────────────────────────
show('Engine card non-sel bg', 'S32-ENGINE-GLASS')
show('Engine card 0B2233', 'Color(0xFF0B2233).withOpacity')

# ── 7. Sliver list ───────────────────────────────────────────────
show('_serverBanner sliver', '_serverBanner')
show('_engineSelector sliver', '_engineSelector')
show('_fileCard sliver', '_fileCard')

# ── 8. Background Stack painters ────────────────────────────────
show('_StarsPainter in Stack', '_StarsPainter(_starCtrl')
show('_GeoPainter in Stack', 'CustomPaint(painter: _GeoPainter')
