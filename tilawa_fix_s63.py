#!/usr/bin/env python3
"""
tilawa_fix_s63.py — Fix fallback auto-retry threshold
======================================================
S32 set score <= 78 as fallback detection, but real engines
(especially الإتقان on low-quality input) can legitimately
score 60-78. This caused valid results to be discarded and
retried endlessly.

Fix: lower threshold to <= 55 (true ffmpeg fallback always
scores exactly 75, so anything above 55 is a real engine result)
AND only retry if score is exactly 75 (the hardcoded fallback value).
"""
from pathlib import Path
from datetime import datetime

HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = HS.read_text(encoding='utf-8')
_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX',l))
def rep(old, new, lbl):
    global txt
    if old in txt: txt = txt.replace(old, new, 1); ok(lbl)
    else: xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s63  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

rep(
    "    // S32: fallback auto-retry ────────────────────────────────────────────\n"
    "    // score ≤ 78 with a valid file = server was in fallback mode (reference\n"
    "    // audio not loaded yet).  Auto-reprocess up to 2 times.\n"
    "    if (score <= 78 && file != null && _fallbackRetries < 2) {",

    "    // S63: fallback auto-retry — only retry if score == 75.0 exactly\n"
    "    // (ffmpeg fallback always returns hardcoded score=75).\n"
    "    // Real engines can score anywhere from 55-100; never discard them.\n"
    "    if (score == 75.0 && file != null && _fallbackRetries < 2) {",
    'Fix fallback threshold: score==75.0 exact instead of <=78')

HS.write_text(txt, encoding='utf-8')
ok('home_screen.dart saved')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S63: fix fallback retry threshold -- accept any real engine score" && git push\n')
