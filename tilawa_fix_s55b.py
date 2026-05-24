#!/usr/bin/env python3
"""tilawa_fix_s55b — Fix-B: _iconBtn RepaintBoundary missing )"""
from pathlib import Path
from datetime import datetime

HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = HS.read_text(encoding='utf-8')
_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX',l))
def rep(old, new, lbl):
    global txt
    if old in txt: txt = txt.replace(old, new, 1); ok(lbl)
    else: xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s55b  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# S59b added RepaintBoundary(child: AnimatedBuilder( — one extra (
# Closing was 4 parens (Icon+Container+AnimatedBuilder+GestureDetector)
# Now needs 5: add RepaintBoundary close before GestureDetector close
rep(
    "          child: Icon(icon, color: _textB, size: 20))));",
    "          child: Icon(icon, color: _textB, size: 20)))));",
    'Fix-B _iconBtn RepaintBoundary ) (line ~907)')

HS.write_text(txt, encoding='utf-8')
ok('home_screen.dart saved')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S55b: fix _iconBtn RepaintBoundary unclosed paren" && git push\n')
