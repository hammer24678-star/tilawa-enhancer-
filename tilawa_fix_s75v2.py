#!/usr/bin/env python3
"""
tilawa_fix_s75v2.py  —  S75: fix v11 engines in actual app.py
Run:
  cp /sdcard/Download/tilawa_fix_s75v2.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s75v2.py 2>&1 | tee /sdcard/Download/fix_s75v2.txt
  git add app.py
  git commit -m "S75: add v11 engines + timeout + fix success check"
  git push
"""
from pathlib import Path
from datetime import datetime

APP = Path.home() / 'tilawa-enhancer/app.py'
_log = []
def _h(t):  print(f'\n{"="*60}\n  {t}\n{"="*60}')
def ok(m):  print(f'  OK  {m}'); _log.append(('OK',m))
def xx(m):  print(f'  XX  {m}'); _log.append(('XX',m))

_h(f'tilawa_fix_s75v2.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

txt = APP.read_text(encoding='utf-8')

if '# S75' in txt:
    print('  -- S75 already applied'); exit(0)

# ── FIX 1: replace the whole ENGINE_SCRIPTS block ─────────────────────────
OLD_ENGINES = '''\
ENGINE_SCRIPTS = {
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.5":  BASE / "engine_v85.py",
    "v8.4": BASE / "engine_v84.py",
    "v8.0": BASE / "engine_v80.py",
    "v7.0": BASE / "engine_v70.py",
}'''

NEW_ENGINES = '''\
ENGINE_SCRIPTS = {  # S75: added v11 series, deduplicated v8.7
    "v11.0": BASE / "engine_tajalli_v1.py",
    "v11.1": BASE / "true_engine_itiqan_v2_fixed.py",
    "v11.2": BASE / "engine_isteidad_v12.py",
    "v8.7":  BASE / "engine_v87.py",
    "v8.5":  BASE / "engine_v85.py",
    "v8.4":  BASE / "engine_v84.py",
    "v8.0":  BASE / "engine_v80.py",
    "v7.0":  BASE / "engine_v70.py",
}'''

if OLD_ENGINES in txt:
    txt = txt.replace(OLD_ENGINES, NEW_ENGINES, 1)
    ok('ENGINE_SCRIPTS fixed — added v11.0/v11.1/v11.2, removed 11x duplicate v8.7')
else:
    xx('ENGINE_SCRIPTS anchor not found')

# ── FIX 2: expand progress markers to cover tajalli output ────────────────
OLD_PROG = '''\
                if "Pass 1" in line or "[\u0667]" in line or "[\u0661]" in line:
                    job["progress"] = 45; job["label"] = "Pass 1 — تحليل الطيف..."
                elif "Pass 2" in line or "[\u0668]" in line or "[\u0662]" in line:
                    job["progress"] = 60; job["label"] = "Pass 2 — ضبط LUFS..."
                elif "Pass 3" in line or "[\u0669]" in line or "[\u0663]" in line:
                    job["progress"] = 75; job["label"] = "Pass 3 — تصحيح..."
                elif "Pass 4" in line or "[\u0664]" in line:
                    job["progress"] = 88; job["label"] = "Pass 4 — تشفير MP3..."'''

NEW_PROG = '''\
                # S75: covers old engines (Pass 1-4) + tajalli ([T-0],[E1],[E2],البيان,النور)
                if any(x in line for x in ("Pass 1","[\u0667]","[\u0661]","[T-0]","Tier:","TIER_","تصنيف")):
                    job["progress"] = 40; job["label"] = "تحليل الملف..."
                elif any(x in line for x in ("Pass 2","[\u0668]","[\u0662]","[E1]","[E2]","الإتقان","الاسترداد")):
                    job["progress"] = 55; job["label"] = "معالجة المحرك..."
                elif any(x in line for x in ("Pass 3","[\u0669]","[\u0663]","[B4]","البيان","VQS")):
                    job["progress"] = 70; job["label"] = "تحسين الصوت..."
                elif any(x in line for x in ("Pass 4","[\u0664]","[B5]","النور","harmonic","[T-6]","[T-7]")):
                    job["progress"] = 85; job["label"] = "الترميز النهائي..."'''

if OLD_PROG in txt:
    txt = txt.replace(OLD_PROG, NEW_PROG, 1)
    ok('Progress markers expanded for tajalli/itiqan/isteidad output')
else:
    xx('Progress marker anchor not found')

# ── FIX 3: proc.wait() → timeout + kill; fix success check ───────────────
OLD_WAIT = '''\
            proc.wait()
            if proc.returncode == 0 and Path(job["out_path"]).exists():
                success = True'''

NEW_WAIT = '''\
            try:  # S75: 90-min timeout, kill on hang
                proc.wait(timeout=5400)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait()
                job["status"] = "error"
                job["error"]  = "Engine timed out"
                job["label"]  = "خطأ: انتهت مهلة المعالجة"
                return
            # S75: use file existence as success signal — engines may exit 1 but write valid file
            _out = Path(job["out_path"])
            if _out.exists() and _out.stat().st_size > 500:
                success = True'''

if OLD_WAIT in txt:
    txt = txt.replace(OLD_WAIT, NEW_WAIT, 1)
    ok('proc.wait() → 90-min timeout + kill; success check uses file size not rc')
else:
    xx('proc.wait() anchor not found')

# ── Write + summary ────────────────────────────────────────────────────────
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
_h('SUMMARY')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
_h(f'{ok_n} OK   {xx_n} FAIL')

if xx_n == 0:
    APP.write_text(txt, encoding='utf-8')
    ok('app.py saved')
    print("""
  git add app.py
  git commit -m "S75: add v11 engines + timeout + fix success check"
  git push
""")
else:
    print('\n  NOT saved — paste output to Claude.\n')
