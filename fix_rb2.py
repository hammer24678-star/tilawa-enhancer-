#!/usr/bin/env python3
from pathlib import Path

hs = Path('lib/screens/home_screen.dart')
t = hs.read_text(encoding='utf-8')

patches = [
    # Orbital ring — builder ends with `            }),` then `          const SizedBox(height: 16),`
    (
        '                ]));\n'
        '            }),\n'
        '          const SizedBox(height: 16),',
        '                ]));\n'
        '            })),\n'
        '          const SizedBox(height: 16),',
        'orbital ring'
    ),
    # Server dot — builder ends with `                }),` then newline + `            const SizedBox(width: 8),`
    (
        '                    ]));\n'
        '                }),\n'
        '            const SizedBox(width: 8),',
        '                    ]));\n'
        '                })),\n'
        '            const SizedBox(width: 8),',
        'server dot'
    ),
]

for old, new, lbl in patches:
    if old in t:
        t = t.replace(old, new, 1)
        print(f'  OK  {lbl}')
    else:
        print(f'  XX  NOT FOUND — {lbl}')

hs.write_text(t, encoding='utf-8')
