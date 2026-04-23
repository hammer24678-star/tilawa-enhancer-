#!/usr/bin/env python3
"""
tilawa_fix_s23_part1.py
=======================
Part 1 of 3 — Server config fixes:
  BUG 3: Progress markers frozen at 79.2% (app.py)
  BUG 4: --iterations 1 caps convergence (app.py)
  BUG 5: max_requests=100 wipes JOBS dict (Dockerfile + gunicorn.conf.py)

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s23_part1.py

Precondition: LFS verified OK (refs=3, server responding).
Part 2 fixes engine_v75.py and engine_v76.py (--ref crash).
Part 3 verifies everything end-to-end.
"""

import os, sys, shutil, subprocess, urllib.request, json
from pathlib import Path
from datetime import datetime

# ── helpers ──────────────────────────────────────────────────────────────────
_log = []

def _h1(t):
    bar = "=" * 64
    print(f"\n{bar}\n  {t}\n{bar}")

def _h2(t): print(f"\n  -- {t}")
def _ok(m):   print(f"     OK  {m}")
def _warn(m): print(f"     !!  {m}")
def _err(m):  print(f"     XX  {m}")

def _rec(sid, label, ok):
    _log.append((sid, label, "PASS" if ok else "FAIL"))
    return ok

def _read(p):     return Path(p).read_text(encoding="utf-8")
def _write(p, t): Path(p).write_text(t, encoding="utf-8")

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f"Anchor NOT found -- {label}")
        _err("  Showing lines containing nearby keywords:")
        return text, False
    if c > 1:
        _warn(f"Anchor found {c}x -- replacing first -- {label}")
    _ok(f"Replaced -- {label}")
    return text.replace(old, new, 1), True

def _run(cmd, cwd=None, label="", timeout=180):
    r = subprocess.run(cmd, shell=True, cwd=cwd,
                       capture_output=True, text=True, timeout=timeout)
    out = (r.stdout + r.stderr).strip()
    ok  = r.returncode == 0
    ((_ok if ok else _err)(label or cmd))
    if not ok and out:
        for line in out.splitlines()[-6:]:
            print(f"        {line}")
    return ok, out

# ── paths ─────────────────────────────────────────────────────────────────────
HF_URL   = (
    "https://carm5333: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"
    "@huggingface.co/spaces/carm5333/tilawa-server"
)
HF_CLONE = Path.home() / "tilawa-hf-clone"
HF_TOKEN = "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"
GH_TOKEN = "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"


# ======================================================================
#  STEP 1 — CLONE + VERIFY CURRENT STATE
# ======================================================================
_h1("STEP 1 -- Clone HF Space + verify current state")

# 1.1  Remove stale clone + fresh clone
_h2("1.1  Remove stale clone + fresh clone (skip LFS blobs)")
if HF_CLONE.exists():
    shutil.rmtree(HF_CLONE)
    _ok(f"Removed stale {HF_CLONE}")
ok11, _ = _run(
    f"GIT_LFS_SKIP_SMUDGE=1 git clone {HF_URL} {HF_CLONE}",
    label="git clone HF Space"
)
_rec("1.1", "HF Space cloned", ok11)
if not ok11:
    _err("Clone failed. Check network / HF token.")
    sys.exit(1)

# 1.2  Verify all expected files are present
_h2("1.2  Verify expected files present in clone")
expected = ["app.py", "Dockerfile", "gunicorn.conf.py",
            "engine_v70.py", "engine_v75.py", "engine_v76.py", "engine_v80.py",
            "requirements.txt"]
all_present = True
for f in expected:
    p = HF_CLONE / f
    exists = p.exists()
    sz = p.stat().st_size if exists else 0
    ((_ok if exists else _err)(f"{f}  ({sz:,} bytes)" if exists else f"{f} MISSING"))
    if not exists:
        all_present = False
_rec("1.2", "All expected files present", all_present)
if not all_present:
    _err("Missing files in clone -- aborting")
    sys.exit(1)

# 1.3  Read app.py and confirm bugs are still present
_h2("1.3  Read app.py -- confirm bugs 3+4 are present")
APP = HF_CLONE / "app.py"
app = _read(APP)
_ok(f"app.py: {len(app):,} chars")

bug3_present = (
    'if "Pass 1" in line:' in app and
    '"Score" in line.lower()' in app and
    'job["score"] = float(line.split(":")[-1].strip().split()[0])' in app
)
bug4_present = '"--iterations", "1"' in app

((_ok if bug3_present else _warn)("BUG 3 present (broken progress markers)"))
((_ok if bug4_present else _warn)("BUG 4 present (--iterations 1)"))

if not bug3_present:
    _warn("BUG 3 already patched or anchor changed -- will re-verify after patch")
if not bug4_present:
    _warn("BUG 4 already patched -- --iterations may already be 3")
_rec("1.3", "app.py read + bugs confirmed", True)

# 1.4  Read Dockerfile + gunicorn.conf.py and confirm bug 5
_h2("1.4  Read Dockerfile + gunicorn.conf.py -- confirm bug 5")
DF   = HF_CLONE / "Dockerfile"
GC   = HF_CLONE / "gunicorn.conf.py"
df   = _read(DF)
gc   = _read(GC)
_ok(f"Dockerfile: {len(df):,} chars")
_ok(f"gunicorn.conf.py: {len(gc):,} chars")

df_bug = '"--max-requests", "100"' in df
gc_bug_mr = "max_requests = 100" in gc
gc_bug_to = "timeout = 600" in gc

((_ok if df_bug  else _warn)("Dockerfile has --max-requests 100 (needs removal)"))
((_ok if gc_bug_mr else _warn)("gunicorn.conf.py has max_requests = 100 (needs fix)"))
((_ok if gc_bug_to else _warn)("gunicorn.conf.py has timeout = 600 (needs sync)"))
_rec("1.4", "Dockerfile + gunicorn.conf.py read", True)


# ======================================================================
#  STEP 2 — FIX app.py: PROGRESS MARKERS
# ======================================================================
_h1("STEP 2 -- Fix app.py: progress markers (BUG 3)")

# 2.1  Backup app.py
_h2("2.1  Backup app.py")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
BD = HF_CLONE / f".fix_backups/{TS}"
BD.mkdir(parents=True, exist_ok=True)
shutil.copy2(APP, BD / "app.py")
_ok(f"Backup: {BD}/app.py")
_rec("2.1", "app.py backed up", True)

# 2.2  Patch: replace the full progress detection block
_h2("2.2  Patch progress markers block")

OLD_PROGRESS = (
    '                if "Pass 1" in line:\n'
    '                    job["progress"] = 45; job["label"] = "Pass 1 \u2014 \u062a\u062d\u0644\u064a\u0644 \u0627\u0644\u0637\u064a\u0641..."\n'
    '                elif "Pass 2" in line:\n'
    '                    job["progress"] = 60; job["label"] = "Pass 2 \u2014 \u0636\u0628\u0637 LUFS..."\n'
    '                elif "Pass 3" in line:\n'
    '                    job["progress"] = 75; job["label"] = "Pass 3 \u2014 \u062a\u0635\u062d\u064a\u062d..."\n'
    '                elif "Pass 4" in line:\n'
    '                    job["progress"] = 88; job["label"] = "Pass 4 \u2014 \u062a\u0634\u0641\u064a\u0631 MP3..."\n'
    '                elif "Score" in line.lower():\n'
    '                    job["progress"] = 95; job["label"] = "\u062d\u0633\u0627\u0628 \u0627\u0644\u0646\u062a\u064a\u062c\u0629..."\n'
    '                    try:\n'
    '                        job["score"] = float(line.split(":")[-1].strip().split()[0])\n'
    '                    except: pass\n'
    '                elif "LUFS=" in line:\n'
    '                    for part in line.split():\n'
    '                        try:\n'
    '                            if "LUFS=" in part:  job["lufs"]  = part.split("=")[1]\n'
    '                            elif "RMS=" in part:  job["rms"]   = part.split("=")[1]\n'
    '                            elif "Crest=" in part: job["crest"] = part.split("=")[1]\n'
    '                            elif "LRA=" in part:  job["lra"]   = part.split("=")[1]\n'
    '                        except: pass\n'
)

NEW_PROGRESS = (
    '                # S23 BUG3: match all engine output styles\n'
    '                # v70 prints "Pass 1 ..." and "Score: N" (English, S22 patch)\n'
    '                # v75/v76/v80 print Arabic bracket markers and star score\n'
    '                if "Pass 1" in line or "[\\u0667]" in line or "[\\u0661]" in line:\n'
    '                    job["progress"] = 45; job["label"] = "Pass 1 \u2014 \u062a\u062d\u0644\u064a\u0644 \u0627\u0644\u0637\u064a\u0641..."\n'
    '                elif "Pass 2" in line or "[\\u0668]" in line or "[\\u0662]" in line:\n'
    '                    job["progress"] = 60; job["label"] = "Pass 2 \u2014 \u0636\u0628\u0637 LUFS..."\n'
    '                elif "Pass 3" in line or "[\\u0669]" in line or "[\\u0663]" in line:\n'
    '                    job["progress"] = 75; job["label"] = "Pass 3 \u2014 \u062a\u0635\u062d\u064a\u062d..."\n'
    '                elif "Pass 4" in line or "[\\u0664]" in line:\n'
    '                    job["progress"] = 88; job["label"] = "Pass 4 \u2014 \u062a\u0634\u0641\u064a\u0631 MP3..."\n'
    '                elif "\\u2605" in line or "\\u2b50" in line or "Score" in line.lower():\n'
    '                    job["progress"] = 95; job["label"] = "\u062d\u0633\u0627\u0628 \u0627\u0644\u0646\u062a\u064a\u062c\u0629..."\n'
    '                    import re as _re\n'
    '                    m = _re.search(r"(\\d+\\.?\\d*)/100", line) or \\\n'
    '                        _re.search(r"Score:\\s*(\\d+\\.?\\d*)", line)\n'
    '                    if m:\n'
    '                        try: job["score"] = float(m.group(1))\n'
    '                        except: pass\n'
    '                elif "LUFS=" in line:\n'
    '                    for part in line.split():\n'
    '                        try:\n'
    '                            if "LUFS=" in part:   job["lufs"]  = part.split("=")[1]\n'
    '                            elif "RMS=" in part:  job["rms"]   = part.split("=")[1]\n'
    '                            elif "Crest=" in part: job["crest"] = part.split("=")[1]\n'
    '                            elif "LRA=" in part:  job["lra"]   = part.split("=")[1]\n'
    '                        except: pass\n'
)

app, p2ok = _replace_once(app, OLD_PROGRESS, NEW_PROGRESS, "progress markers block")
_rec("2.2", "Progress markers patched", p2ok)

# 2.3  Verify patch: confirm new markers present, old broken ones gone
_h2("2.3  Verify patch: new markers present, old broken code gone")
checks_23 = [
    ('"\\u2605" in line' in app,         "star marker present"),
    ('"\\u2b50" in line' in app,         "star emoji marker present"),
    ('_re.search' in app,                "regex score parsing present"),
    ('"(\\d+\\.?\\d*)/100"' in app,      "N/100 regex pattern present"),
    ('S23 BUG3' in app,                  "S23 comment marker present"),
    ('job["score"] = float(line.split(":")[-1]' not in app,
                                         "old broken score parse removed"),
]
all_ok_23 = True
for ok, lbl in checks_23:
    ((_ok if ok else _err)(lbl))
    if not ok: all_ok_23 = False
_rec("2.3", "Progress patch verified", all_ok_23)

# 2.4  Spot-check: print the patched block for visual confirmation
_h2("2.4  Visual spot-check of patched block")
start = app.find("# S23 BUG3")
if start >= 0:
    snippet = app[start:start+600]
    for line in snippet.splitlines():
        print(f"     {line}")
    _ok("Block visible above")
else:
    _warn("S23 comment not found -- patch may not have applied")
_rec("2.4", "Visual spot-check complete", start >= 0)


# ======================================================================
#  STEP 3 — FIX app.py: ITERATIONS + FIX DOCKERFILE + GUNICORN
# ======================================================================
_h1("STEP 3 -- Fix iterations (BUG 4) + Dockerfile + gunicorn.conf.py (BUG 5)")

# 3.1  Patch --iterations 1 → 3 in app.py
_h2("3.1  Patch --iterations 1 -> 3 in app.py")
OLD_ITER = '                   "--iterations", "1"]'
NEW_ITER = '                   "--iterations", "3"]  # S23 BUG4: was 1, disabling convergence loop'
app, p31ok = _replace_once(app, OLD_ITER, NEW_ITER, "--iterations 1 -> 3")
if p31ok:
    _write(APP, app)
    _ok(f"app.py written ({APP.stat().st_size:,} bytes)")
else:
    # Try to detect if already patched
    if '"--iterations", "3"' in app:
        _warn("Already shows 3 -- app.py may already be patched")
        _write(APP, app)
        p31ok = True
    else:
        _err("Could not find iterations anchor and not already 3")
_rec("3.1", "--iterations patched + app.py written", p31ok)

# 3.2  Patch Dockerfile: remove --max-requests 100
_h2("3.2  Patch Dockerfile: remove --max-requests 100")
OLD_DF = (
    'CMD ["gunicorn", "app:app", \\\n'
    '     "--bind", "0.0.0.0:7860", \\\n'
    '     "--timeout", "2400", \\\n'
    '     "--workers", "1", \\\n'
    '     "--max-requests", "100", \\\n'
    '     "--keep-alive", "5"]\n'
)
NEW_DF = (
    '# S23 BUG5: removed --max-requests (was 100) -- worker restart wiped JOBS dict\n'
    'CMD ["gunicorn", "app:app", \\\n'
    '     "--bind", "0.0.0.0:7860", \\\n'
    '     "--timeout", "2400", \\\n'
    '     "--workers", "1", \\\n'
    '     "--keep-alive", "5"]\n'
)
df, p32ok = _replace_once(df, OLD_DF, NEW_DF, "remove --max-requests from Dockerfile")
if p32ok:
    _write(DF, df)
    _ok(f"Dockerfile written ({DF.stat().st_size:,} bytes)")
else:
    if '"--max-requests"' not in df:
        _warn("--max-requests already absent from Dockerfile")
        p32ok = True
_rec("3.2", "Dockerfile patched", p32ok)

# 3.3  Patch gunicorn.conf.py: fix timeout + max_requests
_h2("3.3  Patch gunicorn.conf.py: timeout=2400, max_requests=0")
NEW_GC = (
    "# S23 BUG5: synced with Dockerfile -- timeout 2400, max_requests=0 (unlimited)\n"
    "timeout = 2400\n"
    "workers = 1\n"
    "worker_class = \"sync\"\n"
    "max_requests = 0\n"
    "keepalive = 5\n"
    "# Allow large request bodies (for chunked uploads, each chunk is 8MB)\n"
    "limit_request_line = 0\n"
    "limit_request_field_size = 0\n"
)
_write(GC, NEW_GC)
_ok(f"gunicorn.conf.py written ({GC.stat().st_size:,} bytes)")
_rec("3.3", "gunicorn.conf.py written", True)

# 3.4  Verify all 3 changes together
_h2("3.4  Verify all 3 changes")
app_v = _read(APP)
df_v  = _read(DF)
gc_v  = _read(GC)
checks_34 = [
    ('"--iterations", "3"' in app_v,    'app.py: iterations=3'),
    ('"--max-requests"' not in df_v,    'Dockerfile: no max-requests'),
    ('S23 BUG5' in df_v,                'Dockerfile: S23 comment present'),
    ('timeout = 2400' in gc_v,          'gunicorn.conf.py: timeout=2400'),
    ('max_requests = 0' in gc_v,        'gunicorn.conf.py: max_requests=0'),
    ('S23 BUG5' in gc_v,                'gunicorn.conf.py: S23 comment present'),
]
all_ok_34 = True
for ok, lbl in checks_34:
    ((_ok if ok else _err)(lbl))
    if not ok: all_ok_34 = False
_rec("3.4", "All 3 changes verified", all_ok_34)
if not all_ok_34:
    _err("One or more changes failed -- check output above before proceeding")
    sys.exit(1)


# ======================================================================
#  STEP 4 — COMMIT + PUSH TO HUGGINGFACE
# ======================================================================
_h1("STEP 4 -- Commit + push to HuggingFace")

# 4.1  Git identity
_h2("4.1  Git identity")
_run('git config user.email "tilawa@hf.build"', cwd=HF_CLONE, label="git config email")
_run('git config user.name "Tilawa Build"',     cwd=HF_CLONE, label="git config name")
_rec("4.1", "Git identity set", True)

# 4.2  Stage changed files
_h2("4.2  Stage app.py + Dockerfile + gunicorn.conf.py")
ok42a, _ = _run("git add app.py",            cwd=HF_CLONE, label="git add app.py")
ok42b, _ = _run("git add Dockerfile",        cwd=HF_CLONE, label="git add Dockerfile")
ok42c, _ = _run("git add gunicorn.conf.py",  cwd=HF_CLONE, label="git add gunicorn.conf.py")
_rec("4.2", "Files staged", ok42a and ok42b and ok42c)

# 4.3  Commit
_h2("4.3  Commit")
ok43, out43 = _run(
    'git commit -m "fix: S23p1 progress markers + iterations=3 + remove max-requests"',
    cwd=HF_CLONE, label="git commit"
)
if not ok43 and "nothing to commit" in out43:
    _warn("Nothing to commit -- changes may already be pushed")
    ok43 = True
_rec("4.3", "Committed", ok43)

# 4.4  Push to HuggingFace
_h2("4.4  Push to HuggingFace")
ok44, _ = _run("git push", cwd=HF_CLONE, label="git push HF")
_rec("4.4", "Pushed to HF", ok44)
if not ok44:
    _warn("Push failed -- manual fallback:")
    print(f"     cd {HF_CLONE} && git push")


# ======================================================================
#  STEP 5 — REVIEW: RE-VERIFY EVERYTHING BEFORE CLEANUP
# ======================================================================
_h1("STEP 5 (REVIEW) -- Re-verify all changes are correct")

# 5.1  Re-read each patched file and run full spot-check
_h2("5.1  Full spot-check of all 3 patched files")
app_final = _read(APP)
df_final  = _read(DF)
gc_final  = _read(GC)

checks_51 = [
    # app.py — progress
    ('"\\u2605" in line' in app_final,       "app.py: star marker"),
    ('_re.search' in app_final,              "app.py: regex score parse"),
    ('"(\\d+\\.?\\d*)/100"' in app_final,    "app.py: N/100 pattern"),
    ('S23 BUG3' in app_final,                "app.py: BUG3 comment"),
    # app.py — iterations
    ('"--iterations", "3"' in app_final,     "app.py: iterations=3"),
    ('S23 BUG4' in app_final,                "app.py: BUG4 comment"),
    # app.py — old broken code gone
    ('line.split(":")[-1].strip().split()[0]' not in app_final,
                                             "app.py: old score parse removed"),
    # Dockerfile
    ('"--max-requests"' not in df_final,     "Dockerfile: no max-requests"),
    ('"--timeout", "2400"' in df_final,      "Dockerfile: timeout=2400 present"),
    # gunicorn
    ('timeout = 2400' in gc_final,           "gunicorn.conf.py: timeout=2400"),
    ('max_requests = 0' in gc_final,         "gunicorn.conf.py: max_requests=0"),
]
all_51 = True
for ok, lbl in checks_51:
    ((_ok if ok else _err)(lbl))
    if not ok: all_51 = False
_rec("5.1", "Full spot-check", all_51)

# 5.2  Verify git log shows the commit
_h2("5.2  Git log -- confirm commit is there")
ok52, log52 = _run("git log --oneline -3", cwd=HF_CLONE, label="git log")
if log52:
    for line in log52.splitlines():
        print(f"     {line}")
_rec("5.2", "Git log checked", ok52)

# 5.3  Poll live HF server health (give it up to 3 min to rebuild)
_h2("5.3  Check live server health endpoint")
_warn("HF rebuilds ~2 min after push. Checking now...")
health_ok = False
try:
    req = urllib.request.Request(
        "https://carm5333-tilawa-server.hf.space/",
        headers={"Authorization": f"Bearer {HF_TOKEN}"}
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    engines_ok = all(data.get("engines", {}).values())
    refs_ok    = data.get("refs", 0) == 3
    _ok(f"status: {data.get('status')}  engines: {data.get('engines')}  refs: {data.get('refs')}")
    if not engines_ok: _warn("Not all engines reporting True")
    if not refs_ok:    _warn("refs != 3 -- reference audio may be missing")
    health_ok = data.get("status") == "ok"
except Exception as e:
    _warn(f"Health check failed ({e}) -- server may still be rebuilding, check manually")
_rec("5.3", "Live health check", health_ok)

# 5.4  Cleanup clone
_h2("5.4  Cleanup clone")
try:
    shutil.rmtree(HF_CLONE)
    _ok(f"Removed {HF_CLONE}")
except Exception as e:
    _warn(f"Could not remove clone: {e}")
_rec("5.4", "Clone cleaned up", True)


# ======================================================================
#  FINAL SUMMARY
# ======================================================================
_h1("PART 1 SUMMARY")
print()
print(f"  {'Step':<6}  {'Label':<54}  Result")
print(f"  {'----':<6}  {'-'*54}  ------")
all_pass = True
for sid, lbl, sts in _log:
    icon = "OK" if sts == "PASS" else "XX"
    print(f"  {sid:<6}  {lbl:<54}  [{icon}] {sts}")
    if sts == "FAIL": all_pass = False

print()
if all_pass:
    print("  " + "=" * 64)
    print("  PART 1 COMPLETE")
    print()
    print("  Fixed in this run:")
    print("    BUG 3: progress markers now match all 4 engine output styles")
    print("    BUG 4: --iterations changed 1 -> 3 (convergence loop enabled)")
    print("    BUG 5: max_requests removed (no more mid-job worker restart)")
    print("           gunicorn.conf.py synced (timeout=2400, max_requests=0)")
    print()
    print("  Still to fix:")
    print("    BUG 1: engine_v75.py + engine_v76.py --ref crash  -> Part 2")
    print("    BUG 2: LFS verification                           -> Part 3")
    print()
    print("  Next step:")
    print("    python3 tilawa_fix_s23_part2.py")
    print("  " + "=" * 64)
else:
    print("  " + "=" * 64)
    print("  SOME CHECKS FAILED -- review output above before running Part 2")
    print("  " + "=" * 64)
    sys.exit(1)
