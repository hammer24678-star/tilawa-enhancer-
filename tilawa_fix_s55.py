#!/usr/bin/env python3
"""
tilawa_fix_s55.py — Fix 2 unclosed parens (build errors)
  Error line 1771: Positioned.fill missing closing )
  Error line  894: _iconBtn RepaintBoundary missing closing )
"""
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

print(f'\n{"="*58}\n  tilawa_fix_s55  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# Fix A — line 1771: Positioned.fill needs one extra )
# Current: )]))))],   (5 parens — BoxShadow/BoxDeco/Container/FractionallySized/ClipRRect)
# Missing: Positioned.fill close before Stack-children ]
rep(
    "                                      spreadRadius: 0)]))))],\n"
    "                          ),",
    "                                      spreadRadius: 0)])))))],\n"
    "                          ),",
    'Fix-A Positioned.fill closing ) line 1771')

# Fix B — line 894: _iconBtn GestureDetector unmatched
# S59b added RepaintBoundary(child: AnimatedBuilder( at line 896
# but never added the matching ) for RepaintBoundary at widget end.
# Try the most common closing patterns:

fixed_b = False

for old, new, label in [
    (
        "        ));\n  }\n\n  Widget _engineCard",
        "        )));\n  }\n\n  Widget _engineCard",
        'Fix-B pattern-1'
    ),
    (
        "      ));\n  }\n\n  Widget _engineCard",
        "      )));\n  }\n\n  Widget _engineCard",
        'Fix-B pattern-2'
    ),
    (
        "    ));\n  }\n\n  Widget _engineCard",
        "    )));\n  }\n\n  Widget _engineCard",
        'Fix-B pattern-3'
    ),
]:
    if not fixed_b and old in txt:
        txt = txt.replace(old, new, 1); ok(label); fixed_b = True

if not fixed_b:
    xx('Fix-B NOT FOUND — paste: sed -n "894,940p" ~/tilawa-enhancer/lib/screens/home_screen.dart')

HS.write_text(txt, encoding='utf-8')
ok('home_screen.dart saved')

print(f'\n{"="*58}')
for s, l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S55: fix 2 unclosed parens -- Positioned.fill and _iconBtn RepaintBoundary" && git push\n')
