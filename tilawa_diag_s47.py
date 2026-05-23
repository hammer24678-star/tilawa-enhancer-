#!/usr/bin/env python3
"""tilawa_diag_s47.py — dump exact anchors for s47b"""
from pathlib import Path

SC = Path.home() / 'tilawa-enhancer/lib/screens'
ht = (SC / 'home_screen.dart').read_text(encoding='utf-8')
lines = ht.splitlines()

def show(label, nums):
    print(f'\n=== {label} ===')
    for n in nums:
        lo, hi = max(0, n-1), min(len(lines), n+5)
        for i in range(lo, hi):
            print(f'  {i+1:5}  {repr(lines[i][:110])}')
        print()

# _engines list start
ei = next(i for i,l in enumerate(lines) if 'static const _engines' in l)
show('_engines open + first entry (lines around engine list)', [ei, ei+1, ei+2, ei+3, ei+4, ei+5])

# _engineCard column header
for i,l in enumerate(lines):
    if 'Column(crossAxisAlignment: CrossAxisAlignment.start, children: [' in l:
        # check context — look for the accent bar Stack above it
        ctx = '\n'.join(lines[max(0,i-8):i+3])
        if 'Left accent bar' in ctx or 'accent-bar' in ctx or 'S32-ENGINE' in ctx:
            print(f'\n=== _engineCard Column (line {i+1}) ===')
            for j in range(max(0,i-3), min(len(lines), i+25)):
                print(f'  {j+1:5}  {repr(lines[j][:110])}')
            break

# version name map
for i,l in enumerate(lines):
    if "'v10.0': 'Aetherion" in l or "'v10.0': 'Aetherion_Foundation'" in l:
        print(f'\n=== version map (line {i+1}) ===')
        for j in range(max(0,i-2), min(len(lines), i+8)):
            print(f'  {j+1:5}  {repr(lines[j][:110])}')
        break

# settings screen
st = (SC / 'settings_screen.dart').read_text(encoding='utf-8')
slines = st.splitlines()
for i,l in enumerate(slines):
    if 'v10.0' in l and ('Aetherion' in l or 'الأثير' in l):
        print(f'\n=== settings v10.0 entry (line {i+1}) ===')
        for j in range(max(0,i-2), min(len(slines), i+6)):
            print(f'  {j+1:5}  {repr(slines[j][:110])}')
        break
# also check the _history tuple list
for i,l in enumerate(slines):
    if "('v10.0'" in l or '("v10.0"' in l:
        print(f'\n=== settings tuple list (line {i+1}) ===')
        for j in range(max(0,i-2), min(len(slines), i+8)):
            print(f'  {j+1:5}  {repr(slines[j][:110])}')
        break
