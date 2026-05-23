#!/usr/bin/env python3
from pathlib import Path

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = HS.read_text(encoding='utf-8')
lines = txt.splitlines()

def show(label, keyword, ctx=4):
    print(f'\n── {label} ──')
    for i, l in enumerate(lines):
        if keyword in l:
            for j in range(max(0,i-ctx), min(len(lines),i+ctx+1)):
                m = '>>>' if j==i else '   '
                print(f'  {m} {j+1:4d} | {repr(lines[j])}')
            return
    print(f'  *** NOT FOUND: {repr(keyword)}')

show('IncensePainter in stack', 'IncensePainter')
show('GeoPainter in stack', 'GeoPainter()')
show('Stars generate', 'List.generate')
show('StarsPainter in stack', 'StarsPainter')
show('S40-INCENSE', 'S40-INCENSE')
show('S57 comment', 'S57:')
