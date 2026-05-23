#!/usr/bin/env python3
"""
diag_s52b.py — Show exact raw content around the 4 S52 target areas
Run: python3 diag_s52b.py
"""
from pathlib import Path

HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = HS.read_text(encoding='utf-8')
lines = txt.splitlines(keepends=True)

def show_around(needle, label, ctx=3):
    """Find needle in file and print ctx lines before/after with repr."""
    idx = txt.find(needle)
    if idx == -1:
        print(f'  !! NOT FOUND: {repr(needle)}\n')
        return
    # count line number
    ln = txt[:idx].count('\n')
    print(f'  [found at line {ln+1}]')
    start = max(0, ln - ctx)
    end   = min(len(lines), ln + ctx + 3)
    for i in range(start, end):
        marker = '>>>' if i == ln else '   '
        print(f'  {marker} L{i+1:4d} | {repr(lines[i])}')
    print()

print('\n' + '='*60)
print('  diag_s52b — exact content around 4 target areas')
print('='*60 + '\n')

print('── 1. _selectedEngine getter ──────────────────────────────')
show_around('_selectedEngine =>', '_selectedEngine', ctx=2)

print('── 2. BG gradient colors ──────────────────────────────────')
show_around('S34-BG-GRADIENT', 'bg gradient', ctx=3)

print('── 3. Image card opening ──────────────────────────────────')
show_around('S47-ENGINE-CARD', 'image card', ctx=3)

print('── 4. Score badge in engine selector header ───────────────')
show_around('chooseEngine', 'score badge header', ctx=12)

print('── 5. File stats ──────────────────────────────────────────')
print(f'  Total lines : {len(lines)}')
print(f'  Total bytes : {len(txt.encode("utf-8"))}')
print(f'  Line endings: {"CRLF" if chr(13) in txt else "LF"}')
print()
