#!/usr/bin/env python3
"""
tilawa_diag_s38.py — dump _progressCard full body with depth tracking
Run:
  cp /sdcard/Download/tilawa_diag_s38.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_diag_s38.py 2>&1 | tee /sdcard/Download/diag_s38.txt
"""
from pathlib import Path

SC = Path.home() / 'tilawa-enhancer/lib/screens'
txt = (SC / 'home_screen.dart').read_text(encoding='utf-8')
lines = txt.splitlines()

# Find _progressCard
start = next(i for i, l in enumerate(lines)
             if 'Widget _progressCard' in l and '=>' in l)
# Find next top-level Widget method after it
end = next(i for i in range(start + 1, len(lines))
           if lines[i].startswith('  Widget ') or lines[i].startswith('  // ──'))

print(f'\n=== _progressCard: lines {start+1}–{end+1} ===\n')

# Print with running paren/bracket/brace depth
pd = bd = cd = 0
for i in range(start, end + 2):
    if i >= len(lines): break
    l = lines[i]
    pd += l.count('(') - l.count(')')
    bd += l.count('[') - l.count(']')
    cd += l.count('{') - l.count('}')
    flag = ' <<<<' if pd < 0 or bd < 0 or cd < 0 else ''
    print(f'  {i+1:5}  ({pd:+d} [{bd:+d} {{{cd:+d}  {repr(l[:95])}{flag}')

# Also check welcome_screen.dart first 10 lines
print('\n=== welcome_screen.dart: first 15 lines ===\n')
wlines = (SC / 'welcome_screen.dart').read_text(encoding='utf-8').splitlines()
for i, l in enumerate(wlines[:15]):
    print(f'  {i+1:5}  {repr(l[:100])}')
