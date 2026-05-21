#!/usr/bin/env python3
"""
tilawa_diag_s29.py  —  Dump current anchor regions for S29 patch
Run from ~/tilawa-enhancer and paste the output back to Claude.
"""
import re
from pathlib import Path

REPO    = Path.home() / 'tilawa-enhancer'
LIB     = REPO / 'lib'
SCREENS = LIB / 'screens'
STATE   = LIB / 'state'

def bar(t): print(f'\n{"="*60}\n  {t}\n{"="*60}')
def show(label, text, start, length=30):
    lines = text.splitlines()
    end = min(start + length, len(lines))
    print(f'\n  -- {label}  (lines {start+1}–{end})')
    for i, l in enumerate(lines[start:end], start+1):
        print(f'  {i:4d}  {l}')

def grep(text, pattern, label, context=8):
    for m in re.finditer(pattern, text):
        ln = text[:m.start()].count('\n')
        lines = text.splitlines()
        s = max(0, ln - 2)
        e = min(len(lines), ln + context)
        print(f'\n  -- {label}  @ line {ln+1}')
        for i, l in enumerate(lines[s:e], s+1):
            print(f'  {i:4d}  {l}')
        break
    else:
        print(f'\n  -- {label}  *** NOT FOUND ***')

# ── main.dart ─────────────────────────────────────────────────────────────────
bar('main.dart — colorScheme block')
txt = (LIB / 'main.dart').read_text()
grep(txt, r'colorScheme', 'colorScheme', context=12)
grep(txt, r'scaffoldBackgroundColor', 'scaffoldBg', context=4)

# ── home_screen.dart ──────────────────────────────────────────────────────────
bar('home_screen.dart')
txt = (SCREENS / 'home_screen.dart').read_text()

grep(txt, r'return Scaffold\(', 'Scaffold / body structure', context=10)
grep(txt, r'Widget _header\(S s\)', '_header method', context=30)
grep(txt, r'Widget _iconBtn\(', '_iconBtn method', context=12)
grep(txt, r'_serverUp\b.*Color|banner.*color|banner.*border', 'server banner color', context=10)
grep(txt, r'_engineSelector|Widget _engine', '_engineSelector', context=12)
grep(txt, r'sel \?.*Color|sel \?.*_bg', 'engine card selected', context=6)
grep(txt, r'_file != null.*Color|_file != null.*border', 'file card border', context=8)
grep(txt, r'Widget _processBtn|onPressed.*_process|ElevatedButton.*_process', 'process button', context=14)
grep(txt, r'Widget _bottomRow', '_bottomRow', context=18)
grep(txt, r'Widget _donationCard|buymeacoffee', 'donation card', context=16)
grep(txt, r'String\s+_engine\s*=', 'default _engine field', context=3)

# ── history_screen.dart ───────────────────────────────────────────────────────
bar('history_screen.dart')
txt = (SCREENS / 'history_screen.dart').read_text()

grep(txt, r'return Scaffold\(', 'Scaffold', context=6)
grep(txt, r'AppBar\(', 'AppBar', context=14)
grep(txt, r'job.*card|Container.*job|_jobs\[', 'job card', context=12)

# ── settings_screen.dart ──────────────────────────────────────────────────────
bar('settings_screen.dart')
txt = (SCREENS / 'settings_screen.dart').read_text()

grep(txt, r'AppBar\(', 'AppBar / title', context=10)

# ── welcome_screen.dart ───────────────────────────────────────────────────────
bar('welcome_screen.dart')
txt = (SCREENS / 'welcome_screen.dart').read_text()

grep(txt, r'AnimationController _ctrl|late final.*Controller', 'controllers', context=8)
grep(txt, r'void initState', 'initState', context=16)
grep(txt, r'void dispose', 'dispose', context=8)
grep(txt, r'// Logo|ClipOval.*logo|Image\.asset.*logo', 'logo block', context=18)
grep(txt, r'Text\(s\.appName', 'appName text', context=8)

print('\n\n  *** Paste everything above back to Claude ***\n')
