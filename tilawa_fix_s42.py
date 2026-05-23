#!/usr/bin/env python3
"""tilawa_fix_s42 — fix 4 remaining anchors via targeted grep"""
from pathlib import Path
from datetime import datetime

f = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = f.read_text(encoding='utf-8')
lines = txt.splitlines()

def show(search, ctx=4):
    for i,l in enumerate(lines):
        if search in l:
            print(f'line {i+1}: {repr(l)}')
            for j in range(max(0,i-1), min(len(lines),i+ctx)):
                print(f'  {j+1:5}  {repr(lines[j])}')
            return
    print(f'NOT FOUND: {repr(search)}')

# Show exact current text for 4 failures
print('=== BG gradient ===')
show('0xFF020D17')
show('0xFF000810')

print('\n=== Progress teal shadow ===')
show('blurRadius: 60, spreadRadius: 2')

print('\n=== Engine card teal border ===')
show('width: sel ? 1.6 : 0.7')
show('width: sel ? 1.8 : 0.8')

print('\n=== Background Stack geo line ===')
show('_GeoPainter())')
