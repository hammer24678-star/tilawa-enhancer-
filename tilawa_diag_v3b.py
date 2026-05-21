#!/usr/bin/env python3
"""Print exact text for each failed anchor in v3."""
from pathlib import Path
import re

REPO = Path.home() / 'tilawa-enhancer'
LIB  = REPO / 'lib'
SC   = LIB / 'screens'

def show(label, path, pattern, ctx=4):
    txt = Path(path).read_text(encoding='utf-8')
    lines = txt.splitlines()
    m = re.search(pattern, txt, re.DOTALL)
    if not m:
        # fallback: grep
        hits = [(i+1,l) for i,l in enumerate(lines) if re.search(pattern.split('\\n')[0].replace('\\(','(').replace('\\)',')')[:30], l)]
        if hits:
            ln = hits[0][0]
            print(f'\n=== {label} ===')
            for i in range(max(0,ln-ctx-1), min(len(lines),ln+ctx)):
                print(f'  {i+1:4d}  {repr(lines[i])}')
        else:
            print(f'\n=== {label} ===  *** PATTERN NOT FOUND ***')
        return
    start = txt[:m.start()].count('\n')
    print(f'\n=== {label} (line ~{start+1}) ===')
    for i in range(max(0,start-ctx), min(len(lines),start+ctx+8)):
        print(f'  {i+1:4d}  {repr(lines[i])}')

# main.dart
show('MA1 — colorScheme block', LIB/'main.dart', r'colorScheme')
show('MA2 — appBarTheme', LIB/'main.dart', r'appBarTheme')

# home_screen — process button
show('D22 — process button onPressed', SC/'home_screen.dart', r'onPressed.*_busy.*_serverUp.*_process')

# home_screen — score section
show('D26 — score Row', SC/'home_screen.dart', r'// Score')

# home_screen — donation card
show('D29 — donation card', SC/'home_screen.dart', r'donationCard|DONATION')

# home_screen — body/SafeArea
show('D9 — body structure', SC/'home_screen.dart', r'body:')

# history title
show('HA1 — history title', SC/'history_screen.dart', r'historyTitle')

# settings title
show('SA1 — settings title', SC/'settings_screen.dart', r's\.settings')
