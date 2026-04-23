#!/usr/bin/env python3
"""
tilawa_fix_s24b.py  -- S24 supplementary patch
================================================
Fixes the 3 items that failed in the main s24 run:

  FAIL 2.5  _prune_jobs() function  (anchor dash-count mismatch)
  FAIL 2.7  /download_chunk + /ping (anchor dash-count mismatch)
  FAIL      "v7.6" still present    (upload_start / upload_finalize defaults)

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s24b.py
"""

import sys, subprocess
from pathlib import Path
from datetime import datetime

# ── helpers ──────────────────────────────────────────────────────────────────
def _h1(t):
    bar = "=" * 64
    print(f"\n{bar}\n  {t}\n{bar}")

def _h2(t):  print(f"\n  -- {t}")
def _ok(m):  print(f"     OK  {m}")
def _err(m): print(f"     XX  {m}")

_log = []

def _rec(sid, label, ok):
    _log.append((sid, label, "[OK] PASS" if ok else "[XX] FAIL"))
    return ok

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f"Anchor NOT found -- {label}")
        return text, False
    if c > 1:
        print(f"     !!  Anchor found {c}x -- using first -- {label}")
    _ok(f"Replaced -- {label}")
    return text.replace(old, new, 1), True

def _run(cmd, cwd=None, label="", timeout=180):
    r = subprocess.run(cmd, shell=True,
                       cwd=str(cwd or HF_CLONE),
                       capture_output=True, text=True, timeout=timeout)
    ok = r.returncode == 0
    ((_ok if ok else _err)(label or cmd))
    if not ok:
        for line in (r.stdout + r.stderr).strip().splitlines()[-6:]:
            print(f"        {line}")
    return ok, (r.stdout + r.stderr).strip()

def _require(cond, msg):
    if not cond:
        _err(f"FATAL: {msg}")
        _print_summary()
        sys.exit(1)

def _print_summary():
    _h1("SUMMARY")
    print(f"\n  {'Step':<8}  {'Label':<52}  Result")
    print(f"  {'----':<8}  {'------':<52}  ------")
    for sid, label, result in _log:
        print(f"  {sid:<8}  {label:<52}  {result}")

# ── config ───────────────────────────────────────────────────────────────────
HF_URL   = (
    "https://carm5333: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"
    "@huggingface.co/spaces/carm5333/tilawa-server"
)
HF_CLONE = Path.home() / "tilawa-hf-clone"
APP      = HF_CLONE / "app.py"

_h1("STARTING S24b  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

_h2("Verify HF clone and app.py present")
_require(HF_CLONE.exists(), f"HF clone missing at {HF_CLONE} -- run s24 first")
_require(APP.exists(),      f"app.py missing in clone")
_ok(f"app.py found ({APP.stat().st_size:,} bytes)")

app = APP.read_text(encoding="utf-8")

# ======================================================================
#  PATCH A -- _prune_jobs() function  (was step 2.5)
# ======================================================================
_h1("PATCH A -- _prune_jobs() function")

# Anchor: the _add_history function body ends, then the Status section begins.
# Use the unique '_add_history' tail + '@app.route("/status/' as the anchor.
# This does NOT depend on dash counts.
OLD_A = (
    '    if len(HISTORY) > 50: HISTORY.pop()\n'
    '\n'
    '@app.route("/status/<job_id>")'
)
NEW_A = (
    '    if len(HISTORY) > 50: HISTORY.pop()\n'
    '\n'
    '# S24 BUG8: prune JOBS dict to prevent unbounded memory growth\n'
    'def _prune_jobs():\n'
    '    """Remove oldest done/error jobs once JOBS exceeds 200 entries."""\n'
    '    if len(JOBS) <= 200:\n'
    '        return\n'
    '    removable = [jid for jid, j in list(JOBS.items())\n'
    '                 if j.get("status") in ("done", "error")]\n'
    '    for jid in removable[:-100]:\n'
    '        JOBS.pop(jid, None)\n'
    '\n'
    '@app.route("/status/<job_id>")'
)
app, okA = _replace_once(app, OLD_A, NEW_A, "_prune_jobs function")
_rec("A", "_prune_jobs() function added", okA)

# ======================================================================
#  PATCH B -- /download_chunk + /ping routes  (was step 2.7)
# ======================================================================
_h1("PATCH B -- /download_chunk + /ping routes")

# Anchor: the exact history route body.  Does not depend on section header dashes.
OLD_B = (
    '@app.route("/history")\n'
    'def history():\n'
    '    return jsonify({"jobs": HISTORY})'
)
NEW_B = (
    '# S24 BUG7: /download_chunk was in docstring since v2 but never implemented\n'
    '@app.route("/download_chunk/<job_id>")\n'
    'def download_chunk(job_id):\n'
    '    job = JOBS.get(job_id)\n'
    '    if not job or job["status"] != "done":\n'
    '        return jsonify({"error": "not ready"}), 404\n'
    '    path = Path(job["out_path"])\n'
    '    if not path.exists():\n'
    '        return jsonify({"error": "file missing"}), 404\n'
    '    offset    = int(request.args.get("offset", 0))\n'
    '    size      = int(request.args.get("size", CHUNK_SIZE))\n'
    '    file_size = path.stat().st_size\n'
    '    with open(path, "rb") as f:\n'
    '        f.seek(offset)\n'
    '        data = f.read(size)\n'
    '    return Response(data, headers={\n'
    '        "Content-Type":   "audio/mpeg",\n'
    '        "Content-Length": str(len(data)),\n'
    '        "X-File-Size":    str(file_size),\n'
    '        "X-Offset":       str(offset),\n'
    '    })\n'
    '\n'
    '# S24: fast endpoint for Flutter wake detection\n'
    '@app.route("/ping")\n'
    'def ping():\n'
    '    return jsonify({"ok": True, "t": time.time()})\n'
    '\n'
    '@app.route("/history")\n'
    'def history():\n'
    '    return jsonify({"jobs": HISTORY})'
)
app, okB = _replace_once(app, OLD_B, NEW_B, "/download_chunk + /ping routes")
_rec("B", "/download_chunk + /ping routes added", okB)

# ======================================================================
#  PATCH C -- Remove lingering "v7.6" default values
# ======================================================================
_h1("PATCH C -- Remove lingering v7.6 defaults")

# upload_start default engine
OLD_C1 = '"engine": "v7.6",'
NEW_C1 = '"engine": "v8.1",'
app, okC1 = _replace_once(app, OLD_C1, NEW_C1, "upload_start default engine v7.6 -> v8.1")
_rec("C1", "upload_start default updated", okC1)

# upload_finalize default engine
OLD_C2 = 'engine = data.get("engine", "v7.6")'
NEW_C2 = 'engine = data.get("engine", "v8.1")'
app, okC2 = _replace_once(app, OLD_C2, NEW_C2, "upload_finalize default engine v7.6 -> v8.1")
_rec("C2", "upload_finalize default updated", okC2)

# ======================================================================
#  Write patched app.py
# ======================================================================
_h1("Writing patched app.py")
APP.write_text(app, encoding="utf-8")
_ok(f"app.py written ({len(app):,} chars)")
_rec("W", "app.py written", True)

# ======================================================================
#  Verify
# ======================================================================
_h1("Verification")
checks = [
    ("v8.1 in ENGINE_SCRIPTS",   '"v8.1": BASE / "engine_v81.py"' in app),
    ("v8.0 in ENGINE_SCRIPTS",   '"v8.0": BASE / "engine_v80.py"' in app),
    ("v7.0 in ENGINE_SCRIPTS",   '"v7.0": BASE / "engine_v70.py"' in app),
    ("v7.5 REMOVED",             '"v7.5"' not in app),
    ("v7.6 REMOVED",             '"v7.6"' not in app),
    ("docstring v3 present",     "v3 (S24 overhaul)" in app),
    ("/ping endpoint",           'def ping()' in app),
    ("score elif REMOVED",       '"\\u2605" in line' not in app),
    ("/100 standalone scan",     "BUG-SCORE" in app),
    ("/download_chunk route",    'def download_chunk' in app),
    ("_prune_jobs function",     'def _prune_jobs' in app),
    ("_prune_jobs called",       '_prune_jobs()  # S24 BUG8' in app),
    ("S24 comment marker",       "S24" in app),
]
all_pass = True
for label, cond in checks:
    ((_ok if cond else _err)(label))
    if not cond: all_pass = False

_rec("V", "app.py full verification", all_pass)
_require(all_pass, "Verification failed -- check patches above")

# ======================================================================
#  Git push
# ======================================================================
_h1("STEP 7 -- Git operations")

_h2("7.1  git config")
_run('git config user.email "s24b@tilawa.fix"', label="git config email")
_run('git config user.name "S24b Fix"',         label="git config name")

_h2("7.2  git add")
ok_add, _ = _run("git add app.py", label="git add app.py")
_rec("7.2", "git add", ok_add)

_h2("7.3  git status")
_run("git status --short", label="git status")

_h2("7.4  git commit")
msg = "S24b: add _prune_jobs, /download_chunk, /ping; fix v7.6 defaults"
ok_commit, _ = _run(f'git commit -m "{msg}"', label="git commit")
_rec("7.4", "git commit", ok_commit)

_h2("7.5  git push")
ok_push, _ = _run(f"git push {HF_URL} main", label="git push", timeout=120)
_rec("7.5", "git push", ok_push)

_print_summary()

if ok_push:
    print("\n  HF Space is rebuilding. Check live in ~3 min:")
    print("  https://carm5333-tilawa-server.hf.space/")
else:
    print("\n  !! Push failed. Check output above.")
