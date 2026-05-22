#!/usr/bin/env python3
"""
tilawa_fix_s39_logo.py  —  S39-LOGO: replace wrong NetworkImage in welcome hero
=================================================================================
Bug: welcome_screen.dart circular logo hero is showing a TikTok thumbnail
     instead of the app logo. Root cause: the S32-WELCOME-LOGO patch used
     a NetworkImage URL that resolves to wrong content.
Fix: Replace every NetworkImage(...) inside the S32-WELCOME-LOGO block with
     AssetImage('assets/images/logo.png').  Also covers the fallback pattern
     of Image.network(...) wrapped in a CircleAvatar or ClipOval.

Run:
  cp /sdcard/Download/tilawa_fix_s39_logo.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s39_logo.py 2>&1 | tee /sdcard/Download/fix_s39_logo.txt
  git add -A && git commit -m "S39-LOGO: fix welcome hero — use local asset not NetworkImage" && git push
"""

import re
from pathlib import Path
from datetime import datetime

SC   = Path.home() / 'tilawa-enhancer/lib/screens'
_log = []

def _h(t):  print(f'\n{"="*62}\n  {t}\n{"="*62}')
def _ok(m): print(f'  OK  {m}'); _log.append(('OK', m))
def _xx(m): print(f'  XX  {m}'); _log.append(('XX', m))
def _sk(m): print(f'  --  {m}'); _log.append(('SK', m))
def _i(m):  print(f'       {m}')

def rep(txt, old, new, lbl):
    if old not in txt:
        _xx(f'NOT FOUND — {lbl}')
        return txt, False
    _ok(lbl)
    return txt.replace(old, new, 1), True

MARK = '// S39-LOGO-FIX'

_h(f'tilawa_fix_s39_logo.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

wtxt = (SC / 'welcome_screen.dart').read_text(encoding='utf-8')

if MARK in wtxt:
    _sk('Logo fix already applied — nothing to do')
else:

    # ── ATTEMPT 1: CircleAvatar with backgroundImage: NetworkImage(...) ──
    m1 = re.search(
        r'(CircleAvatar\([^)]*backgroundImage\s*:\s*NetworkImage\([^)]+\)[^)]*\))',
        wtxt, re.DOTALL
    )
    if m1:
        old_block = m1.group(1)
        new_block = re.sub(
            r'backgroundImage\s*:\s*NetworkImage\([^)]+\)',
            "backgroundImage: const AssetImage('assets/images/logo.png') "
            + MARK,
            old_block, count=1
        )
        wtxt = wtxt.replace(old_block, new_block, 1)
        _ok('Replaced NetworkImage in CircleAvatar.backgroundImage')
    else:
        _i('CircleAvatar+NetworkImage pattern not found — trying next')

    # ── ATTEMPT 2: ClipOval / ClipRRect wrapping Image.network(...) ──
    m2 = re.search(
        r'(Image\.network\s*\([^;]+?\))',
        wtxt, re.DOTALL
    )
    if m2:
        old_img = m2.group(1)
        new_img = (
            "Image.asset('assets/images/logo.png', "  # S39-LOGO-FIX
            "fit: BoxFit.cover) " + MARK
        )
        wtxt = wtxt.replace(old_img, new_img, 1)
        _ok('Replaced Image.network with Image.asset')
    else:
        _i('Image.network pattern not found — trying bare NetworkImage')

    # ── ATTEMPT 3: bare NetworkImage('...') anywhere in welcome_screen ──
    bare = re.search(r"NetworkImage\(['\"][^'\"]+['\"]\)", wtxt)
    if bare:
        old_ni = bare.group(0)
        new_ni = f"const AssetImage('assets/images/logo.png') {MARK}"
        wtxt = wtxt.replace(old_ni, new_ni, 1)
        _ok(f'Replaced bare NetworkImage: {old_ni[:60]}...')
    else:
        _i('No bare NetworkImage found either')

    # ── Verify at least one fix landed ──
    if MARK not in wtxt:
        _xx('NONE of the three patterns matched.')
        _i('Dumping lines that contain "Image" or "Circle" for manual diagnosis:')
        for i, l in enumerate(wtxt.splitlines(), 1):
            if any(k in l for k in ('Image', 'Circle', 'ClipO', 'decoration')):
                print(f'  {i:5}  {l[:100]}')
    else:
        (SC / 'welcome_screen.dart').write_text(wtxt, encoding='utf-8')
        _ok('welcome_screen.dart saved')

_h('SUMMARY')
ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
sk_n = sum(1 for s, _ in _log if s == 'SK')
for s, l in _log:
    icon = 'OK' if s == 'OK' else ('--' if s == 'SK' else 'XX')
    print(f'  {icon}  {l}')
_h(f'{ok_n} OK   {sk_n} SKIP   {xx_n} FAIL')

if xx_n == 0 and sk_n == 0:
    print("""
  git add -A && git commit -m "S39-LOGO: fix welcome hero — use local asset not NetworkImage" && git push
""")
elif sk_n > 0:
    print('\n  Already applied. No action needed.\n')
else:
    print('\n  Some patterns not found. Paste full output back to Claude.\n')
