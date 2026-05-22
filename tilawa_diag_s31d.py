#!/usr/bin/env python3
from pathlib import Path
SC = Path.home() / 'tilawa-enhancer/lib/screens'
h = (SC/'home_screen.dart').read_text(encoding='utf-8')
lines = h.splitlines()

def show(label, search, ctx=5):
    for i,l in enumerate(lines):
        if search in l:
            print(f'\n=={label}== line {i+1}')
            for j in range(max(0,i-1), min(len(lines),i+ctx)):
                print(f'{j+1:5}  {repr(lines[j])}')
            return
    print(f'\n=={label}== NOT FOUND: {repr(search[:40])}')

# 1. Rotating geo — what's the ACTUAL geo painter call now
show('GEO-CALL', 'GeoPainter')
# 2. Engine card close — what comes after AnimatedCrossFade
show('CROSSFADE', 'AnimatedCrossFade')
# 3. Score ring — find score section in _resultCard
show('SCORE-OLD', 'toStringAsFixed(1)/100')
show('SCORE-OLD2', "score.toStringAsFixed")
show('SCORE-OLD3', 'fontWeight: FontWeight.w900, fontSize: 34')
# 4. Server dot — find the actual dot widget
show('SERVER-DOT', 'BoxShape.circle,\n')
show('SERVER-DOT2', 'blurRadius: 6 +')
show('SERVER-DOT3', 'color: _serverUp ? Color')
show('SERVER-DOT4', '_tGreen')
show('SERVER-DOT5', 'width: 10, height: 10')
show('SERVER-DOT6', 'statusDot')
