#!/usr/bin/env python3
from pathlib import Path
HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
lines = HS.read_text(encoding='utf-8').splitlines()
# Show lines around StarsPainter class
for i,l in enumerate(lines):
    if '_StarsPainter' in l and 'class' in l:
        for j in range(i, min(len(lines), i+30)):
            print(f'  {j+1:4d} | {repr(lines[j])}')
        break
