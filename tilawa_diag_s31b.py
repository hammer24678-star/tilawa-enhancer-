#!/usr/bin/env python3
from pathlib import Path
SC = Path.home() / 'tilawa-enhancer/lib/screens'

def show(label, path, search, ctx=4):
    txt = Path(path).read_text(encoding='utf-8')
    lines = txt.splitlines()
    for i,l in enumerate(lines):
        if search in l:
            print(f'\n=={label}== line {i+1}')
            for j in range(max(0,i-ctx), min(len(lines),i+ctx+6)):
                print(f'{j+1:5}  {repr(lines[j])}')
            return
    print(f'\n=={label}== NOT FOUND')

h = str(SC/'home_screen.dart')
w = str(SC/'welcome_screen.dart')

# Score ring exact location
show('SCORE-RING', h, 'Builder(builder: (_)')
show('SCORE-RING-2', h, '_scoreCtrl.status')
# Server dot exact
show('SERVER-DOT', h, 'shape: BoxShape.circle,\n')
show('SERVER-DOT-2', h, '_serverUp ? _ok')
show('SERVER-DOT-3', h, 'blurRadius: 6 + 6')
# Welcome geo
show('WELCOME-STACK', w, 'Stack(children:')
show('WELCOME-POSITIONED', w, 'Positioned.fill')
