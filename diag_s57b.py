#!/usr/bin/env python3
from pathlib import Path
HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
lines = HS.read_text(encoding='utf-8').splitlines()
def show(kw, ctx=3):
    print(f'\n── {kw} ──')
    for i,l in enumerate(lines):
        if kw in l:
            for j in range(max(0,i-ctx),min(len(lines),i+ctx+1)):
                print(f'  {">>>" if j==i else "   "} {j+1:4d} | {repr(lines[j])}')
            return
    print(f'  NOT FOUND')
show('twinkle')
show('drawCircle')
