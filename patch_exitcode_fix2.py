"""
patch_exitcode_fix2.py — S32 Exit Code Fix (robust anchor)

Finds the proc.wait() + returncode check dynamically regardless of
what surrounding lines were added by previous patches.

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 patch_exitcode_fix2.py
"""

import sys
import re
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

_h1("patch_exitcode_fix2.py  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

_require(HF_CLONE.exists(), "HF clone missing")
_run("git pull --ff-only", label="git pull")
_require(APP.exists(), "app.py missing")

# ── Show current state of the proc.wait() block ───────────────────────────────
_h1("Scanning current proc.wait() block")

lines = APP.read_text(encoding="utf-8").splitlines(keepends=True)
found_lines = [(i+1, l.rstrip()) for i, l in enumerate(lines)
               if "proc.wait()" in l or "returncode == 0" in l
               or "engine_rc" in l or "engine_log" in l]

print("\n  Relevant lines in current app.py:")
for lineno, content in found_lines:
    print(f"    {lineno:4d}: {content}")

# ── Patch using regex on the full text ───────────────────────────────────────
_h1("PATCH — replace returncode check with file-exists check")

app = APP.read_text(encoding="utf-8")

# Match the entire block from proc.wait() through job["engine_rc"] = ...
# Handles any extra lines inserted between proc.wait() and the if-statement
# (e.g. the debug engine_log line added by patch_v10_debug)
pattern = re.compile(
    r'( +)proc\.wait\(\)\n'            # proc.wait() with its indentation
    r'(?:.*\n)*?'                      # any lines in between (e.g. engine_log)
    r'( +)if proc\.returncode == 0 and Path\(job\["out_path"\]\)\.exists\(\):\n'
    r'\2 +success = True\n'
    r'\2else:\n'
    r'\2 +job\["engine_rc"\] = proc\.returncode',
    re.MULTILINE,
)

match = pattern.search(app)
if match:
    _ok(f"Block found at chars {match.start()}–{match.end()}")
    indent = match.group(1)   # indentation of proc.wait() line
    old_block = match.group(0)
    new_block = (
        f"{indent}proc.wait()\n"
        f"{indent}_out = Path(job[\"out_path\"])\n"
        f"{indent}# engine_v100 exits 1 for score<85 but still writes the file.\n"
        f"{indent}# Use file existence + size as the real success signal.\n"
        f"{indent}if _out.exists() and _out.stat().st_size > 0:\n"
        f"{indent}    success = True\n"
        f"{indent}else:\n"
        f"{indent}    job[\"engine_rc\"] = proc.returncode"
    )
    app = app[:match.start()] + new_block + app[match.end():]
    _ok("Block replaced successfully")
    okA = True
else:
    _err("Pattern not found — printing surrounding context for debug:")
    # Print any line containing proc.wait or returncode
    for lineno, content in found_lines:
        print(f"    {lineno:4d}: {repr(content)}")
    okA = False

_rec("A", "returncode→file-exists patch", okA)
_require(okA, "Patch A failed — see lines printed above")

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
    print("\n  ✓ HF Space rebuilding — ready in ~3 min. Should process successfully now.")
else:
    print("\n  !! Push failed — check output above.")
