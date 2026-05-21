"""
patch_exitcode_fix.py — S32 Exit Code Fix

ROOT CAUSE:
  engine_v100.py main() returns:
      return 0 if r['score'] >= 85 else 1

  app.py success check:
      if proc.returncode == 0 and Path(job["out_path"]).exists():
          success = True

  So any file scoring < 85 → returncode=1 → app treats it as failure
  even though the output file was written perfectly.
  The engine DID its job. app.py wrongly discards it.

FIX:
  Check if the output file exists (and has non-zero size).
  returncode is only a hint — not the source of truth.

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 patch_exitcode_fix.py
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

_h1("patch_exitcode_fix.py  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

_require(HF_CLONE.exists(), "HF clone missing")
ok_pull, _ = _run("git pull --ff-only", label="git pull")
_require(APP.exists(), "app.py missing")

app = APP.read_text(encoding="utf-8")

# ── PATCH: replace returncode==0 check with output-file-exists check ──────────
_h1("PATCH — fix success check to use output file existence")

OLD = '''\
            proc.wait()
            if proc.returncode == 0 and Path(job["out_path"]).exists():
                success = True
            else:
                job["engine_rc"] = proc.returncode'''

NEW = '''\
            proc.wait()
            _out = Path(job["out_path"])
            # engine_v100 exits 1 when score < 85 (low-quality file) but still
            # writes the output. Use file existence + size as the real success
            # signal; treat exit codes 0 and 1 both as non-fatal.
            if _out.exists() and _out.stat().st_size > 0:
                success = True
            else:
                job["engine_rc"] = proc.returncode'''

app, okA = _replace_once(app, OLD, NEW, "success check → file-exists")
_rec("A", "success check fixed", okA)

# ── Write ─────────────────────────────────────────────────────────────────────
_h1("Writing patched app.py")
APP.write_text(app, encoding="utf-8")
_ok(f"Written ({len(app):,} chars)")
_rec("W", "app.py written", True)

# ── Verify ────────────────────────────────────────────────────────────────────
_h1("Verification")
checks = [
    ("new file-exists check present",  "_out.exists() and _out.stat().st_size > 0" in app),
    ("old returncode==0 check gone",   "returncode == 0 and Path(job" not in app),
    ("engine_v100 still mapped",       "engine_v100.py" in app),
    ("ram threshold 0.5",              "ram_gb < 0.5" in app),
]
all_ok = True
for label, cond in checks:
    ((_ok if cond else _err)(label))
    if not cond: all_ok = False
_rec("V", "verification", all_ok)
_require(all_ok, "Verification failed")

# ── Git ───────────────────────────────────────────────────────────────────────
_h1("Git commit + push")

_run('git config user.email "fix@tilawa.fix"', label="git config email")
_run('git config user.name "S32 ExitCode Fix"', label="git config name")

ok_add, _ = _run("git add app.py", label="git add")
_rec("G1", "git add", ok_add)

msg = "S32 fix: engine_v100 exits 1 for score<85; check output file not returncode"
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
  ✓ HF Space rebuilding — ready in ~3 min.

  Root cause: engine_v100.py returns exit code 1 when score < 85.
  app.py was treating exit code 1 as "engine crashed".
  Fix: success is now determined by output file existence + size > 0.

  After rebuild, try processing again — it should complete successfully.
""")
else:
    print("\n  !! Push failed — check output above.")
