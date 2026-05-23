#!/usr/bin/env python3
"""
tilawa_fix_s47c.py — fix engine card header anchor (correct 10sp indent)
Run:
  cp /sdcard/Download/tilawa_fix_s47c.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s47c.py 2>&1 | tee /sdcard/Download/fix_s47c.txt
"""
from pathlib import Path
from datetime import datetime

SC = Path.home() / 'tilawa-enhancer/lib/screens'

def _h(t): print(f'\n{"="*56}\n  {t}\n{"="*56}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'  XX  {m}')
def _sk(m): print(f'  --  {m}')

_h(f'tilawa_fix_s47c.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

hf = SC / 'home_screen.dart'
ht = hf.read_text(encoding='utf-8')

_h('Engine card header — dump exact lines 1056-1095')
lines = ht.splitlines()
for i, l in enumerate(lines[1053:1098], start=1054):
    print(f'  {i:5}  {repr(l[:110])}')
