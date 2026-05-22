#!/usr/bin/env python3
from pathlib import Path
SC = Path.home() / 'tilawa-enhancer/lib/screens'
h = (SC/'home_screen.dart').read_text(encoding='utf-8')
lines = h.splitlines()

def dump_method(label, start_search, n=60):
    for i,l in enumerate(lines):
        if start_search in l:
            print(f'\n=={label}== from line {i+1}')
            for j in range(i, min(len(lines), i+n)):
                print(f'{j+1:5}  {repr(lines[j])}')
            return
    print(f'\n=={label}== NOT FOUND')

dump_method('RESULT_CARD', 'Widget _resultCard', 80)
dump_method('SERVER_BANNER', 'Widget _serverBanner', 60)
# Engine card close
for i,l in enumerate(lines):
    if 'AnimatedCrossFade' in l and i > 990:
        print(f'\n==AFTER_CROSSFADE== line {i+1}')
        for j in range(i, min(len(lines), i+12)):
            print(f'{j+1:5}  {repr(lines[j])}')
        break
