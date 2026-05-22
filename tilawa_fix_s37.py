#!/usr/bin/env python3
"""
tilawa_fix_s37.py  —  S37: two build errors after S36
======================================================
BUG 1  home_screen.dart:1447-1530
  Root cause: S35-FIX-A2 changed `]),  // S34-PAREN-FIX …` → `],  …`
  stripping a STRUCTURAL `)` that closed the Row widget inside
  _progressCard.  S36 only renamed the comment; it never restored
  the paren.  Dart error: "Can't find ] to match [" (line 1468)
  and "Can't find ) to match (" (line 1447).
  Fix: change `],  // S36-BRACKET-FIX …` → `]),  // S37-PAREN-FIX …`

BUG 2  welcome_screen.dart
  _GeoPainter and _WelcomeStarsPainter use math.pi / math.cos /
  math.sin but the file has no `import 'dart:math' as math;`.
  Fix: insert the import after the existing dart:math show pi line
  (or the flutter/material.dart import if the former is absent).

Run:
  cp /sdcard/Download/tilawa_fix_s37.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s37.py 2>&1 | tee /sdcard/Download/fix_s37.txt
  git add -A && git commit -m "S37: restore structural ) in _progressCard; add math import to welcome_screen" && git push
"""

import re
from pathlib import Path
from datetime import datetime

SC   = Path.home() / 'tilawa-enhancer/lib/screens'
_log = []

def _h(t):  print(f'\n{"="*64}\n  {t}\n{"="*64}')
def _ok(m): print(f'  OK  {m}'); _log.append(('OK', m))
def _xx(m): print(f'  XX  {m}'); _log.append(('XX', m))
def _i(m):  print(f'  --  {m}')

def rep(txt, old, new, lbl):
    c = txt.count(old)
    if c == 0:
        _xx(f'NOT FOUND — {lbl}')
        return txt, False
    if c > 1:
        print(f'  !! {c}x — using first — {lbl}')
    else:
        _ok(lbl)
    return txt.replace(old, new, 1), True

def bracket_net(txt): return txt.count('[') - txt.count(']')
def paren_net(txt):   return txt.count('(') - txt.count(')')

def dump_lines(txt, lo, hi, label=''):
    lines = txt.splitlines()
    if label:
        _i(f'Lines {lo}-{hi}  [{label}]')
    for i in range(max(0, lo-1), min(len(lines), hi)):
        print(f'  {i+1:5}  {repr(lines[i][:100])}')

_h(f'tilawa_fix_s37.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')


###########################################################################
# BUG 1  home_screen.dart — restore structural ) in _progressCard
###########################################################################
_h('BUG 1  home_screen.dart — restore ) in _progressCard closing line')

htxt = (SC / 'home_screen.dart').read_text(encoding='utf-8')
_i(f'On load:  [ {bracket_net(htxt):+d}   ( {paren_net(htxt):+d}')

# Dump lines ~1520-1540 so we can see the current state regardless
lines_h = htxt.splitlines()
prog_start = next((i for i, l in enumerate(lines_h)
                   if '_progressCard' in l and 'Widget' in l), None)
if prog_start is not None:
    _i(f'_progressCard starts at line {prog_start+1}')
    # find the S36-BRACKET-FIX or S35-PAREN-FIX2 line near there
    fix_line = next((i for i in range(prog_start, min(prog_start+120, len(lines_h)))
                     if 'S36-BRACKET-FIX' in lines_h[i] or 'S35-PAREN-FIX2' in lines_h[i]), None)
    if fix_line is not None:
        _i(f'Fix-marker line: {fix_line+1}')
        dump_lines(htxt, fix_line-8, fix_line+6, 'context around fix-marker')

# ── Primary: exact S36 marker ────────────────────────────────────────────
OLD_B1 = '],  // S36-BRACKET-FIX (removed orphan ) from bracket-paren)'
NEW_B1 = ']),  // S37-PAREN-FIX (restored structural ) — S35 FIX-A2 over-stripped)'

htxt, ok1 = rep(htxt, OLD_B1, NEW_B1, 'restore ) — S36-BRACKET-FIX line')

if not ok1:
    # ── Fallback A: S35 marker ────────────────────────────────────────────
    OLD_B2 = '],  // S35-PAREN-FIX2 (removed orphan ) from bracket-paren)'
    NEW_B2 = ']),  // S37-PAREN-FIX (restored structural ) — S35 FIX-A2 over-stripped)'
    htxt, ok1 = rep(htxt, OLD_B2, NEW_B2, 'restore ) — S35-PAREN-FIX2 variant')

if not ok1:
    # ── Fallback B: regex — any Sx-PAREN-FIX / S36-BRACKET-FIX after ],
    m = re.search(
        r'^(\s*\],\s*//\s*S3[0-9]+-(?:PAREN-FIX|BRACKET-FIX)\b[^\n]*)',
        htxt, re.MULTILINE
    )
    if m:
        replacement = m.group(1).replace('],', ']),', 1)
        htxt = htxt[:m.start()] + replacement + htxt[m.end():]
        _ok('restore ) — regex fallback S3x-FIX marker')
        ok1 = True
    else:
        _xx('Could not find fix-marker line in any variant')
        _i('Dumping lines 1440-1545 for manual diagnosis:')
        dump_lines(htxt, 1440, 1545, 'full-prog-card')

_i(f'After BUG1 fix:  [ {bracket_net(htxt):+d}   ( {paren_net(htxt):+d}')

# Verify structure: scan for first bracket-negative and paren-negative line
def first_neg(txt, op, cl, kind):
    depth = 0
    for i, l in enumerate(txt.splitlines(), 1):
        depth += l.count(op) - l.count(cl)
        if depth < 0:
            return i
    return None

bn = first_neg(htxt, '[', ']', 'bracket')
pn = first_neg(htxt, '(', ')', 'paren')
if bn: _i(f'First bracket-negative line: {bn}')
else:  _i('Brackets look balanced in raw scan')
if pn: _i(f'First paren-negative line: {pn}')
else:  _i('Parens look balanced in raw scan')

(SC / 'home_screen.dart').write_text(htxt, encoding='utf-8')
_ok('home_screen.dart saved')


###########################################################################
# BUG 2  welcome_screen.dart — add missing `import 'dart:math' as math;`
###########################################################################
_h("BUG 2  welcome_screen.dart — add import 'dart:math' as math;")

wtxt = (SC / 'welcome_screen.dart').read_text(encoding='utf-8')

MATH_IMPORT = "import 'dart:math' as math;"

if MATH_IMPORT in wtxt:
    _ok("import 'dart:math' as math; already present — skip")
else:
    # Try to insert after any existing dart:math import (e.g. show pi)
    added = False
    for anchor in [
        "import 'dart:math' show pi;",
        "import 'dart:math';",
        "import 'package:flutter/material.dart';",
    ]:
        if anchor in wtxt:
            wtxt = wtxt.replace(anchor, anchor + "\nimport 'dart:math' as math;", 1)
            _ok(f"import added after: {anchor}")
            added = True
            break

    if not added:
        # Last resort: prepend at top
        wtxt = MATH_IMPORT + '\n' + wtxt
        _ok("import prepended at top of file")

    (SC / 'welcome_screen.dart').write_text(wtxt, encoding='utf-8')
    _ok('welcome_screen.dart saved')

# Sanity check welcome_screen
wbkt = bracket_net(wtxt); wparen = paren_net(wtxt)
wcurl = wtxt.count('{') - wtxt.count('}')
status = 'OK' if wbkt == 0 and wparen == 0 and wcurl == 0 else 'XX'
_i(f'welcome_screen balance: [ {wbkt:+d}  ( {wparen:+d}  {{ {wcurl:+d}  [{status}]')


###########################################################################
# SUMMARY
###########################################################################
_h('SUMMARY')
ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
for s, l in _log:
    print(f'  {"OK" if s == "OK" else "XX"}  {l}')
_h(f'{ok_n} OK   {xx_n} XX')

if xx_n == 0:
    print("""
  All fixed. Commit and push:
    git add -A && git commit -m "S37: restore structural ) in _progressCard; add math import to welcome_screen" && git push
""")
else:
    print("""
  Some steps failed. Paste the full output above back to Claude.
  The dump lines above will show the exact current state of the file.
""")
