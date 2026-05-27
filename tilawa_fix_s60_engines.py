#!/usr/bin/env python3
"""tilawa_fix_s60_engines — fix ENGINE_SCRIPTS to use real filenames"""
from pathlib import Path
from datetime import datetime

APP = Path.home() / 'tilawa-enhancer/app.py'
txt = APP.read_text(encoding='utf-8')
_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX',l))
def rep(old, new, lbl):
    global txt
    if old in txt: txt = txt.replace(old, new, 1); ok(lbl)
    else: xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s60_engines  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

rep(
    '    "v11.0": BASE / "engine_v100.py",  # التجلي\n'
    '    "v11.1": BASE / "engine_v100.py",  # الإتقان  (routes internally)\n'
    '    "v11.2": BASE / "engine_v100.py",  # الاسترداد (routes internally)\n'
    '    # Legacy engines\n'
    '    "v10.0": BASE / "engine_v100.py",\n'
    '    "v9.0":  BASE / "engine_v90.py",',

    '    "v11.0": BASE / "engine_tajalli_v1.py",           # التجلي\n'
    '    "v11.1": BASE / "true_engine_itiqan_v2_fixed.py", # الإتقان\n'
    '    "v11.2": BASE / "engine_isteidad_v12.py",         # الاسترداد\n'
    '    # Legacy engines\n'
    '    "v10.0": BASE / "engine_tajalli_v1.py",\n'
    '    "v9.0":  BASE / "engine_v90.py",',
    'Fix-1 correct engine filenames for v11.x / v10.0')

APP.write_text(txt, encoding='utf-8')
ok('app.py saved')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S60: correct engine filenames -- tajalli/itiqan/isteidad real paths" && git push\n')
