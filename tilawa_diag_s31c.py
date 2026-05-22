#!/usr/bin/env python3
import subprocess, re
from pathlib import Path

h = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
w = Path.home() / 'tilawa-enhancer/lib/screens/welcome_screen.dart'

def grep(path, term, ctx=5):
    txt = Path(path).read_text(encoding='utf-8')
    lines = txt.splitlines()
    results = [(i,l) for i,l in enumerate(lines) if term in l]
    if not results:
        print(f'  NOT FOUND: {repr(term)}')
        return
    i,l = results[0]
    print(f'  line {i+1}: {repr(l.strip())}')
    for j in range(max(0,i-ctx), min(len(lines),i+ctx+4)):
        print(f'    {j+1:5}  {repr(lines[j])}')

print('\n=== SCORE RING — search _resultCard method ===')
grep(h, 'Widget _resultCard')

print('\n=== SERVER BANNER — search _serverBanner method ===')
grep(h, 'Widget _serverBanner')

print('\n=== WELCOME — search body: ===')
grep(w, 'body:')

print('\n=== WELCOME — search Positioned.fill ===')
txt_w = Path(w).read_text(encoding='utf-8')
lines_w = txt_w.splitlines()
for i,l in enumerate(lines_w):
    if 'Positioned.fill' in l or '_GeoPainter' in l or 'Stack(children' in l:
        print(f'  {i+1:5}  {repr(l)}')
