#!/usr/bin/env python3
"""
tilawa_fix_s59_server.py — Fix 2 server bugs
=============================================
Bug 1: SEMAPHORE used in _run_engine (s75 patch on HF) but
       definition line never added → NameError at runtime.
       Fix: add SEMAPHORE = threading.Semaphore(2) to globals.

Bug 2: ENGINE_SCRIPTS only maps v8.x — app sends v9.0/v10.0/v11.x
       which all fall through to None → ffmpeg fallback, no engine.
       Fix: add all active engine IDs.
"""
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

print(f'\n{"="*58}\n  tilawa_fix_s59_server  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# Fix 1 — add SEMAPHORE definition after CHUNK_SIZE global
rep(
    'CHUNK_SIZE = 4 * 1024 * 1024  # S25: 4MB — aligns with client, better mobile retry granularity',
    'CHUNK_SIZE = 4 * 1024 * 1024  # S25: 4MB — aligns with client, better mobile retry granularity\n'
    '\n'
    '# S59: concurrency guard — max 2 engine subprocesses at once on HF free tier\n'
    'SEMAPHORE = threading.Semaphore(2)',
    'Fix-1 SEMAPHORE definition added')

# Fix 2 — add v9.0/v10.0/v11.x engines to ENGINE_SCRIPTS
rep(
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.5":  BASE / "engine_v85.py",\n'
    '    "v8.4": BASE / "engine_v84.py",\n'
    '    "v8.0": BASE / "engine_v80.py",\n'
    '    "v7.0": BASE / "engine_v70.py",\n'
    '}',
    '    # S47: Sacred Engines (v11.x)\n'
    '    "v11.0": BASE / "engine_v100.py",  # التجلي\n'
    '    "v11.1": BASE / "engine_v100.py",  # الإتقان  (routes internally)\n'
    '    "v11.2": BASE / "engine_v100.py",  # الاسترداد (routes internally)\n'
    '    # Legacy engines\n'
    '    "v10.0": BASE / "engine_v100.py",\n'
    '    "v9.0":  BASE / "engine_v90.py",\n'
    '    "v8.7":  BASE / "engine_v87.py",\n'
    '    "v8.5":  BASE / "engine_v85.py",\n'
    '    "v8.4":  BASE / "engine_v84.py",\n'
    '    "v8.0":  BASE / "engine_v80.py",\n'
    '    "v7.0":  BASE / "engine_v70.py",\n'
    '}',
    'Fix-2 ENGINE_SCRIPTS includes v9.0/v10.0/v11.x')

APP.write_text(txt, encoding='utf-8')
ok('app.py saved')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S59: fix SEMAPHORE NameError + add v9-v11 to ENGINE_SCRIPTS" && git push\n')
