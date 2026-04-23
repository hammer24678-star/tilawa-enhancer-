#!/usr/bin/env python3
"""
tilawa_fix_s24c.py  -- S24 final patch
========================================
Fixes the 2 items still failing after s24 + s24b:

  FAIL A  _prune_jobs() function missing
          (both previous anchors were wrong -- this script uses
           a simple single-line anchor that cannot fail)

  FAIL B  "v7.6" still in legacy /upload route
          (s24b only patched upload_start and upload_finalize)

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s24c.py
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

_h1("STARTING S24c  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

_h2("Verify HF clone and app.py present")
_require(HF_CLONE.exists(), f"HF clone missing -- run s24 first")
_require(APP.exists(),      f"app.py missing in clone")
_ok(f"app.py found ({APP.stat().st_size:,} bytes)")

app = APP.read_text(encoding="utf-8")

# Quick pre-check: warn if _prune_jobs already present
if "def _prune_jobs" in app:
    _ok("_prune_jobs already present -- skipping patch A")
    okA = True
    _rec("A", "_prune_jobs() function added", True)
else:
    # ======================================================================
    #  PATCH A -- _prune_jobs() function
    # ======================================================================
    _h1("PATCH A -- _prune_jobs() function")

    # Anchor: the last line of _add_history().
    # This line is unique in the file and has no Unicode section-header
    # dependency -- it will match regardless of what comment follows it.
    OLD_A = '    if len(HISTORY) > 50: HISTORY.pop()\n'
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
    )
    app, okA = _replace_once(app, OLD_A, NEW_A, "_prune_jobs function")
    _rec("A", "_prune_jobs() function added", okA)

# ======================================================================
#  PATCH B -- legacy /upload route still uses "v7.6" default
# ======================================================================
_h1("PATCH B -- legacy /upload default engine v7.6 -> v8.1")

OLD_B = 'engine = request.form.get("engine", "v7.6")'
NEW_B = 'engine = request.form.get("engine", "v8.1")'
app, okB = _replace_once(app, OLD_B, NEW_B,
                         "legacy /upload default engine v7.6 -> v8.1")
_rec("B", "legacy /upload default updated", okB)

# ======================================================================
#  Write patched app.py
# ======================================================================
_h1("Writing patched app.py")
APP.write_text(app, encoding="utf-8")
_ok(f"app.py written ({len(app):,} chars)")
_rec("W", "app.py written", True)

# ======================================================================
#  Verification
# ======================================================================
_h1("Verification")
checks = [
    ("v8.1 in ENGINE_SCRIPTS",   '"v8.1": BASE / "engine_v81.py"' in app),
    ("v8.0 in ENGINE_SCRIPTS",   '"v8.0": BASE / "engine_v80.py"' in app),
    ("v7.0 in ENGINE_SCRIPTS",   '"v7.0": BASE / "engine_v70.py"' in app),
    ("v7.5 REMOVED",             '"v7.5"' not in app),
    ("v7.6 REMOVED",             '"v7.6"' not in app),
    ("docstring v3 present",     "v3 (S24 overhaul)" in app),
    ("/ping endpoint",           "def ping()" in app),
    ("score elif REMOVED",       '"\u2605" in line' not in app),
    ("/100 standalone scan",     "BUG-SCORE" in app),
    ("/download_chunk route",    "def download_chunk" in app),
    ("_prune_jobs function",     "def _prune_jobs" in app),
    ("_prune_jobs called",       "_prune_jobs()  # S24 BUG8" in app),
    ("S24 comment marker",       "S24" in app),
]
all_pass = True
for label, cond in checks:
    ((_ok if cond else _err)(label))
    if not cond:
        all_pass = False

_rec("V", "app.py full verification", all_pass)
_require(all_pass, "Verification failed -- check patches above")

# ======================================================================
#  Git operations
# ======================================================================
_h1("Git operations")

_h2("git config")
_run('git config user.email "s24c@tilawa.fix"', label="git config email")
_run('git config user.name "S24c Fix"',         label="git config name")

_h2("git add")
ok_add, _ = _run("git add app.py", label="git add app.py")
_rec("G1", "git add", ok_add)

_h2("git status")
_run("git status --short", label="git status")

_h2("git commit")
msg = "S24c: add _prune_jobs func; fix legacy /upload v7.6 default"
ok_commit, out_commit = _run(f'git commit -m "{msg}"', label="git commit")
if not ok_commit and "nothing to commit" in out_commit:
    _ok("Nothing to commit (patches already in tree)")
    ok_commit = True
_rec("G2", "git commit", ok_commit)

_h2("git push")
ok_push, _ = _run(f"git push {HF_URL} main", label="git push", timeout=120)
_rec("G3", "git push", ok_push)

_print_summary()

if ok_push:
    print("\n  HF Space is rebuilding. Ready in ~3 min:")
    print("  https://carm5333-tilawa-server.hf.space/")
else:
    print("\n  !! Push failed. Check output above.")
