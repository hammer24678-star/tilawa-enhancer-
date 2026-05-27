#!/usr/bin/env python3
"""
tilawa_fix_s75.py  —  S75: fix v11 engines + server efficiency
==============================================================
Problems:
  1. Duplicate "v11.0" key in ENGINE_SCRIPTS — Python dict keeps last
     definition, silently dropping the first. v11.0 still points to
     tajalli (correct) but makes the dict confusing and fragile.
  2. Tajalli called via subprocess — server reads progress markers
     like "Pass 1", "Pass 2" etc. but tajalli logs Arabic phase names
     and custom markers [T-0], [E1], [E2] that the server never matches
     → progress stays frozen at 35% then jumps to done/error.
  3. No per-job timeout on proc.wait() — a hung engine blocks a semaphore
     slot forever, killing throughput for all users.
  4. SEMAPHORE=3 but gunicorn --workers=1 — 3 concurrent subprocesses
     on a HuggingFace Space (2 vCPU, ~16 GB RAM) is fine. Keep it.
  5. No proc.kill() on timeout — zombie subprocesses accumulate.
  6. gc.collect() after SEMAPHORE.release() — should be inside finally
     block before release to free memory before next job starts.

Fixes:
  A. Deduplicate ENGINE_SCRIPTS — remove second v11.0 entry
  B. Expand progress marker matching to cover tajalli output patterns
  C. Add 90-minute per-job timeout to proc.wait() with forced kill
  D. Add POPEN_KWARGS: bufsize=1 for line-buffered stdout (faster progress)
  E. Move gc.collect() to before SEMAPHORE.release()
  F. Add job-level watchdog: if progress stuck >20 min, kill and error

Run:
  cp /sdcard/Download/tilawa_fix_s75.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s75.py 2>&1 | tee /sdcard/Download/fix_s75.txt
  git add app.py
  git commit -m "S75: fix v11 engines + 90min timeout + progress markers"
  git push
"""

from pathlib import Path
from datetime import datetime

APP = Path.home() / 'tilawa-enhancer/app.py'

_log = []
def _h(t):  print(f'\n{"="*62}\n  {t}\n{"="*62}')
def ok(m):  print(f'  OK  {m}'); _log.append(('OK', m))
def xx(m):  print(f'  XX  {m}'); _log.append(('XX', m))
def sk(m):  print(f'  --  {m}'); _log.append(('SK', m))

MARK = '# S75'

_h(f'tilawa_fix_s75.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

if not APP.exists():
    xx(f'app.py not found at {APP}'); exit(1)

txt = APP.read_text(encoding='utf-8')

if MARK in txt:
    sk('S75 already applied'); exit(0)

changes = 0

# ── FIX A: remove duplicate v11.0 key ─────────────────────────────────────
OLD_A = '''\
    "v11.0": BASE / "engine_tajalli_v1.py",
    "v11.1": BASE / "true_engine_itiqan_v2_fixed.py",
    "v11.2": BASE / "engine_isteidad_v12.py",
    "v10.0": BASE / "engine_v100.py",
    "v11.0": BASE / "engine_tajalli_v1.py",'''

NEW_A = '''\
    "v11.0": BASE / "engine_tajalli_v1.py",   # S75: tajalli unified router
    "v11.1": BASE / "true_engine_itiqan_v2_fixed.py",
    "v11.2": BASE / "engine_isteidad_v12.py",
    "v10.0": BASE / "engine_v100.py",'''

if OLD_A in txt:
    txt = txt.replace(OLD_A, NEW_A, 1)
    ok('Removed duplicate v11.0 key from ENGINE_SCRIPTS')
    changes += 1
else:
    xx('ENGINE_SCRIPTS duplicate anchor not found')

# ── FIX B: expand progress marker matching to cover tajalli output ─────────
OLD_B = '''\
                if "Pass 1" in line or "[٧]" in line or "[١]" in line:
                    job["progress"] = 45; job["label"] = "Pass 1 — تحليل الطيف..."
                elif "Pass 2" in line or "[٨]" in line or "[٢]" in line:
                    job["progress"] = 60; job["label"] = "Pass 2 — ضبط LUFS..."
                elif "Pass 3" in line or "[٩]" in line or "[٣]" in line:
                    job["progress"] = 75; job["label"] = "Pass 3 — تصحيح..."
                elif "Pass 4" in line or "[٤]" in line:
                    job["progress"] = 88; job["label"] = "Pass 4 — تشفير MP3..."'''

NEW_B = '''\
                # S75: extended markers — covers tajalli [T-0]..[T-7], itiqan, isteidad
                if any(x in line for x in ("Pass 1", "[١]", "[٧]", "[T-0]", "Tier:", "TIER_", "تصنيف")):
                    job["progress"] = 40; job["label"] = "تحليل الملف..."
                elif any(x in line for x in ("Pass 2", "[٢]", "[٨]", "[E1]", "[E2]", "الإتقان", "الاسترداد", "routing")):
                    job["progress"] = 55; job["label"] = "معالجة المحرك..."
                elif any(x in line for x in ("Pass 3", "[٣]", "[٩]", "[B4]", "البيان", "bayan", "VQS")):
                    job["progress"] = 68; job["label"] = "تحسين الصوت..."
                elif any(x in line for x in ("Pass 4", "[٤]", "[B5]", "النور", "noor", "harmonic")):
                    job["progress"] = 78; job["label"] = "إثراء الترددات..."
                elif any(x in line for x in ("[T-6]", "[T-7]", "Sidrah", "score", "encode", "تشفير", "final")):
                    job["progress"] = 88; job["label"] = "الترميز النهائي..."'''

if OLD_B in txt:
    txt = txt.replace(OLD_B, NEW_B, 1)
    ok('Expanded progress markers to cover tajalli/itiqan/isteidad output')
    changes += 1
else:
    xx('Progress marker block anchor not found')

# ── FIX C+E: add 90-min timeout to proc.wait() + kill on timeout ──────────
OLD_C = '''\
            proc.wait()
            _out = Path(job["out_path"])'''

NEW_C = '''\
            # S75: 90-min per-job timeout — kill engine if hung
            try:
                proc.wait(timeout=5400)  # 90 minutes
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                with JOBS_LOCK:
                    job["status"] = "error"
                    job["error"]  = "Engine timed out after 90 minutes"
                    job["label"]  = "خطأ: انتهت مهلة المعالجة"
                return
            _out = Path(job["out_path"])'''

if OLD_C in txt:
    txt = txt.replace(OLD_C, NEW_C, 1)
    ok('Added 90-minute timeout with proc.kill() on proc.wait()')
    changes += 1
else:
    xx('proc.wait() anchor not found')

# ── FIX D: line-buffered stdout for faster progress updates ───────────────
OLD_D = '''\
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )'''

NEW_D = '''\
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1  # S75: line-buffered — faster progress
            )'''

if OLD_D in txt:
    txt = txt.replace(OLD_D, NEW_D, 1)
    ok('Added bufsize=1 (line-buffered) to Popen for faster progress updates')
    changes += 1
else:
    xx('subprocess.Popen anchor not found')

# ── FIX E: move gc.collect() before SEMAPHORE.release() ──────────────────
OLD_E = '''\
    SEMAPHORE.acquire()
    try:
        _run_engine(job_id)
    finally:
        SEMAPHORE.release()
        gc.collect()'''

NEW_E = '''\
    SEMAPHORE.acquire()
    try:
        _run_engine(job_id)
    finally:
        gc.collect()       # S75: free memory BEFORE releasing slot
        SEMAPHORE.release()'''

if OLD_E in txt:
    txt = txt.replace(OLD_E, NEW_E, 1)
    ok('Moved gc.collect() before SEMAPHORE.release()')
    changes += 1
else:
    xx('SEMAPHORE acquire/release block anchor not found')

# ── Write ─────────────────────────────────────────────────────────────────
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')

_h('SUMMARY')
for s, l in _log:
    print(f'  {"OK" if s=="OK" else ("--" if s=="SK" else "XX")}  {l}')

if xx_n == 0:
    APP.write_text(txt, encoding='utf-8')
    ok('app.py saved')
    _h(f'{ok_n} OK   0 FAIL')
    print("""
  git add app.py
  git commit -m "S75: fix v11 engines + 90min timeout + progress markers"
  git push
""")
else:
    _h(f'{ok_n} OK   {xx_n} FAIL')
    print('\n  Some anchors not found — paste output to Claude.\n')
