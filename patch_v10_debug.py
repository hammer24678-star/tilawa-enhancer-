"""
patch_v10_debug.py — S32 Debug

PROBLEM:
  engine_v100.py reaches score (~95%) then crashes.
  The exception is swallowed — we can't see why.

FIX:
  1. Store last 40 lines of engine stdout/stderr in job["engine_log"]
  2. Expose it in /status when status == "error"

After this push, trigger a job and curl /status/<job_id>
to see the actual Python traceback.

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 patch_v10_debug.py
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime

def _h1(t):
    bar = "=" * 64
    print(f"\n{bar}\n  {t}\n{bar}")

def _ok(m):  print(f"     OK  {m}")
def _err(m): print(f"     XX  {m}")

_log = []
def _rec(sid, label, ok):
    _log.append((sid, label, "[OK] PASS" if ok else "[XX] FAIL"))
    return ok

def _run(cmd, cwd=None, label="", timeout=180):
    r = subprocess.run(cmd, shell=True, cwd=str(cwd or HF_CLONE),
                       capture_output=True, text=True, timeout=timeout)
    ok = r.returncode == 0
    ((_ok if ok else _err)(label or cmd))
    if not ok:
        for line in (r.stdout + r.stderr).strip().splitlines()[-8:]:
            print(f"        {line}")
    return ok, (r.stdout + r.stderr).strip()

def _require(cond, msg):
    if not cond:
        _err(f"FATAL: {msg}")
        _print_summary()
        sys.exit(1)

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f"Anchor NOT found -- {label}")
        return text, False
    if c > 1:
        print(f"     !!  Found {c}x -- using first -- {label}")
    _ok(f"Replaced -- {label}")
    return text.replace(old, new, 1), True

def _print_summary():
    _h1("SUMMARY")
    print(f"\n  {'Step':<8}  {'Label':<52}  Result")
    print(f"  {'----':<8}  {'------':<52}  ------")
    for sid, label, result in _log:
        print(f"  {sid:<8}  {label:<52}  {result}")

HF_URL   = (
    "https://carm5333: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"
    "@huggingface.co/spaces/carm5333/tilawa-server"
)
HF_CLONE = Path.home() / "tilawa-hf-clone"
APP      = HF_CLONE / "app.py"

_h1("patch_v10_debug.py  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

_require(HF_CLONE.exists(), "HF clone missing")
_require(APP.exists(), "app.py missing")
_ok(f"app.py found ({APP.stat().st_size:,} bytes)")

app = APP.read_text(encoding="utf-8")

# Check if already patched
if "engine_log" in app and "engine_lines" in app:
    _ok("Debug patch already applied — skipping text patches")
    already_patched = True
else:
    already_patched = False

if not already_patched:
    # ── PATCH A: collect all output lines into engine_lines buffer ────────────
    _h1("PATCH A — collect engine output lines")

    OLD_A = """            for line in proc.stdout:
                line = line.strip()
                # Progress markers — plain scalar writes, no lock needed
                if "Pass 1" in line or "[٧]" in line or "[١]" in line:"""

    NEW_A = """            engine_lines = []   # DEBUG: capture all output
            for line in proc.stdout:
                line = line.strip()
                engine_lines.append(line)        # DEBUG
                if len(engine_lines) > 60:       # DEBUG: keep last 60 lines
                    engine_lines.pop(0)          # DEBUG
                # Progress markers — plain scalar writes, no lock needed
                if "Pass 1" in line or "[٧]" in line or "[١]" in line:"""

    app, okA = _replace_once(app, OLD_A, NEW_A, "add engine_lines buffer")
    _rec("A", "engine output buffer added", okA)

    # ── PATCH B: store engine_lines in job after proc.wait() ─────────────────
    _h1("PATCH B — store engine_lines in job on failure")

    OLD_B = """            proc.wait()
            if proc.returncode == 0 and Path(job["out_path"]).exists():
                success = True
            else:
                job["engine_rc"] = proc.returncode"""

    NEW_B = """            proc.wait()
            job["engine_log"] = engine_lines[-40:]   # DEBUG: last 40 lines
            if proc.returncode == 0 and Path(job["out_path"]).exists():
                success = True
            else:
                job["engine_rc"] = proc.returncode"""

    app, okB = _replace_once(app, OLD_B, NEW_B, "store engine_log in job")
    _rec("B", "engine_log stored in job", okB)

    # ── PATCH C: expose engine_log in /status when error ─────────────────────
    _h1("PATCH C — expose engine_log in /status")

    OLD_C = """    if "error" in job:
        resp["error"] = job["error"]

    return jsonify(resp)"""

    NEW_C = """    if "error" in job:
        resp["error"] = job["error"]

    # DEBUG: expose last engine output lines so we can see the crash
    if job.get("status") == "error" and "engine_log" in job:
        resp["engine_log"] = job["engine_log"]
        resp["engine_rc"]  = job.get("engine_rc")

    return jsonify(resp)"""

    app, okC = _replace_once(app, OLD_C, NEW_C, "expose engine_log in /status")
    _rec("C", "engine_log exposed in /status", okC)

    _h1("Writing patched app.py")
    APP.write_text(app, encoding="utf-8")
    _ok(f"app.py written ({len(app):,} chars)")
    _rec("W", "app.py written", True)

# ── Git ───────────────────────────────────────────────────────────────────────
_h1("Git commit + push")

_run('git config user.email "debug@tilawa.fix"', label="git config email")
_run('git config user.name "S32 Debug"',         label="git config name")

ok_add, _ = _run("git add app.py", label="git add app.py")
_rec("G1", "git add", ok_add)

_run("git status --short", label="git status")

msg = "S32 debug: capture engine stdout in job for crash diagnosis"
ok_commit, out = _run(f'git commit -m "{msg}"', label="git commit")
if not ok_commit and "nothing to commit" in out:
    _ok("Nothing to commit")
    ok_commit = True
_rec("G2", "git commit", ok_commit)

ok_push, _ = _run(f"git push {HF_URL} main", label="git push", timeout=300)
_rec("G3", "git push", ok_push)

_print_summary()

if ok_push:
    print("""
  ✓ Pushed. Wait ~3 min for rebuild, then:

  1. Trigger a job (upload any small mp3 via the app)
  2. While it's running, note the job_id from the URL or wait for error
  3. Then poll status:

     curl https://carm5333-tilawa-server.hf.space/status/<JOB_ID> | python3 -m json.tool

  The response will include "engine_log": [...] showing the
  actual Python traceback so we can fix the real crash.

  Alternatively, check the HuggingFace Space logs at:
  https://huggingface.co/spaces/carm5333/tilawa-server (Logs tab)
""")
else:
    print("\n  !! Push failed.")
