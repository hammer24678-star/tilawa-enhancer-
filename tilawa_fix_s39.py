#!/usr/bin/env python3
"""
tilawa_fix_s39.py — fix unmatched bracket in _progressCard
===========================================================
Root cause: line 1505 has '])))),` = ] + 4 parens.
Correct:    ']))),' = ] + 3 parens.

The 4th ')' prematurely closed the Row, pushing ShaderMask
(percent text) and cancel button outside the Row into Column
directly, leaving the Row's '[' unmatched.
"""
from pathlib import Path
from datetime import datetime

f = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = f.read_text(encoding='utf-8')

OLD = "                }));\n            })),\n          ])))),\n"
NEW = "                }));\n            }),\n          ]))),\n"

if OLD in txt:
    txt = txt.replace(OLD, NEW, 1)
    f.write_text(txt, encoding='utf-8')
    print('✅ Fixed: ]))))  →  ]))),  (removed extra ) that closed Row early)')
else:
    # Try alternate whitespace
    print('Primary anchor not found — trying line-by-line search...')
    lines = txt.splitlines()
    fixed = False
    for i, l in enumerate(lines):
        if l.strip() == '])))),':
            # Check context: line before should end with }),
            ctx = '\n'.join(lines[max(0,i-3):i+2])
            print(f'Found at line {i+1}:\n{ctx}\n')
            lines[i] = lines[i].replace('])))),', ']))),', 1)
            f.write_text('\n'.join(lines), encoding='utf-8')
            print(f'✅ Fixed line {i+1}: ])))))  →  ]),),')
            fixed = True
            break
    if not fixed:
        # Print context around line 1505
        for i,l in enumerate(lines[1500:1510], 1501):
            print(f'{i:5}  {repr(l)}')
        print('❌ Could not find anchor — paste output above')

print('\n  git add -A && git commit -m "S39: fix unmatched bracket in progressCard" && git push')
