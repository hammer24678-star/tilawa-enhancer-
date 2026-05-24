#!/usr/bin/env python3
"""Fix 4 unclosed RepaintBoundary parens from S59b"""
from pathlib import Path

hs = Path('lib/screens/home_screen.dart')
t = hs.read_text(encoding='utf-8')
fixes = 0

# Each RepaintBoundary(child: AnimatedBuilder( added 2 opens.
# The builder closes with }), — that closes AnimatedBuilder only.
# Need one extra ) after each }), to close RepaintBoundary.

patches = [
    # 1. Orbital ring — closes after the SizedBox return
    # The AnimatedBuilder builder ends with: `            })),`
    # followed by `          const SizedBox(height: 16),`
    (
        '            })),\n'
        '          const SizedBox(height: 16),\n'
        '          // S61-HEADER-NAME',
        '            }))),\n'
        '          const SizedBox(height: 16),\n'
        '          // S61-HEADER-NAME',
        'orbital ring RB close'
    ),
    # 2. Server dot — closes after the SizedBox return
    # builder ends with `                })),` before `            Text(`
    (
        '                })),\n'
        '            Text(',
        '                }))),\n'
        '            Text(',
        'server dot RB close'
    ),
    # 3. Khatam badge — closes after `          }),`
    # at line ~1098: `          }),\n        ShaderMask(`
    (
        '          }),\n'
        '        ShaderMask(\n'
        '          shaderCallback: (b) => LinearGradient(',
        '          })),\n'
        '        ShaderMask(\n'
        '          shaderCallback: (b) => LinearGradient(',
        'khatam badge RB close'
    ),
    # 4. Card image — closes after `            }),`
    # at line ~1259: `            }),\n          // S50: JSX khatam card`
    (
        '            }),\n'
        '          // S50: JSX khatam card',
        '            })),\n'
        '          // S50: JSX khatam card',
        'card image RB close'
    ),
]

for old, new, lbl in patches:
    if old in t:
        t = t.replace(old, new, 1)
        print(f'  OK  {lbl}')
        fixes += 1
    else:
        print(f'  XX  NOT FOUND — {lbl}')

hs.write_text(t, encoding='utf-8')
print(f'\n  {fixes}/4 fixed')
