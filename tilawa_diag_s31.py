#!/usr/bin/env python3
"""Dump exact text for all 9 failed anchors"""
from pathlib import Path
SC = Path.home() / 'tilawa-enhancer/lib/screens'

def show(label, path, search, ctx=3):
    txt = Path(path).read_text(encoding='utf-8')
    lines = txt.splitlines()
    for i,l in enumerate(lines):
        if search in l:
            print(f'\n=={label}== line {i+1}')
            for j in range(max(0,i-ctx), min(len(lines),i+ctx+4)):
                print(f'{j+1:5}  {repr(lines[j])}')
            return
    print(f'\n=={label}== *** NOT FOUND *** searching: {repr(search[:50])}')

h = str(SC/'home_screen.dart')
w = str(SC/'welcome_screen.dart')

show('GEO-PAINTER-CALL',   h, '_GeoPainter()')
show('ENGINE-CARD-DECO',   h, 'sel ? _tCard')
show('FILE-CARD-DECO',     h, '_file != null ? _tGold')
show('PROG-STATUS-TEXT',   h, 's.processing : _status')
show('RESULT-SLIVER',      h, '_result != null')
show('SCORE-RING-CONTENT', h, 'mainAxisAlignment: MainAxisAlignment.center, children')
show('SERVER-DOT',         h, 'width: 9, height: 9,')
show('WELCOME-GEO',        w, '_GeoPainter()')
