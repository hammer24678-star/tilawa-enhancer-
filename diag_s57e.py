#!/usr/bin/env python3
from pathlib import Path
HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
lines = HS.read_text(encoding='utf-8').splitlines()

def show(kw, ctx=2):
    print(f'\n── {kw} ──')
    found = False
    for i,l in enumerate(lines):
        if kw in l:
            for j in range(max(0,i-ctx), min(len(lines),i+ctx+1)):
                print(f'  {">>>" if j==i else "   "} {j+1:4d} | {repr(lines[j])}')
            found = True
            break
    if not found: print('  NOT FOUND')

show('_serverBanner', ctx=0)  # find the method to locate banner
show('fromLTRB(16, 4',  ctx=1)
show('fromLTRB(16, 8',  ctx=1)
show('fromLTRB(16,10',  ctx=1)
show('fromLTRB(16,14',  ctx=1)
show('fromLTRB(16, 10', ctx=1)
show('fromLTRB(16, 14', ctx=1)
show('SizedBox(height: 16),\n', ctx=1)
show('SizedBox(height: 6),\n',  ctx=1)
show('vertical: 2),',  ctx=1)
show('SizedBox(height: 40)',  ctx=0)
