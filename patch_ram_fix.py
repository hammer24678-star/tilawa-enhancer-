"""
patch_ram_fix.py — S32 RAM Guard Fix

ROOT CAUSE:
  _available_ram_gb() reads /proc/meminfo → MemAvailable = 0 on HuggingFace
  Docker containers (cgroup memory reporting quirk).
  So the 3.5 GB guard fires on EVERY job and immediately returns:
    "Insufficient RAM (0.0 GB free, need 3.5 GB)"

FIX:
  1. If MemAvailable is 0, fall back to reading MemTotal instead.
  2. Lower the guard threshold from 3.5 GB → 0.5 GB (safety margin only).

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 patch_ram_fix.py
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

_h1("patch_ram_fix.py  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

_require(HF_CLONE.exists(), "HF clone missing")
ok_pull, _ = _run("git pull --ff-only", label="git pull")
_require(APP.exists(), "app.py missing")

app = APP.read_text(encoding="utf-8")

# ── PATCH A: fix _available_ram_gb to handle 0 from /proc/meminfo ────────────
_h1("PATCH A — fix _available_ram_gb()")

OLD_A = '''def _available_ram_gb() -> float:
    """Return available RAM in GB via /proc/meminfo. Returns 999 on failure."""
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / (1024 * 1024)
    except Exception:
        pass
    return 999.0'''

NEW_A = '''def _available_ram_gb() -> float:
    """Return available RAM in GB via /proc/meminfo.
    HuggingFace Docker containers report MemAvailable=0 due to cgroup quirk;
    fall back to MemTotal in that case. Returns 999 on any failure."""
    try:
        mem = {}
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith(("MemAvailable:", "MemTotal:")):
                    k, v = line.split(":", 1)
                    mem[k.strip()] = int(v.split()[0])
        available = mem.get("MemAvailable", 0)
        if available > 0:
            return available / (1024 * 1024)
        # Fallback: MemTotal (container may not expose MemAvailable)
        total = mem.get("MemTotal", 0)
        if total > 0:
            return total / (1024 * 1024)
    except Exception:
        pass
    return 999.0'''

app, okA = _replace_once(app, OLD_A, NEW_A, "_available_ram_gb fallback to MemTotal")
_rec("A", "_available_ram_gb fixed", okA)

# ── PATCH B: lower threshold from 3.5 → 0.5 GB ───────────────────────────────
_h1("PATCH B — lower RAM threshold 3.5 → 0.5 GB")

OLD_B = '    if ram_gb < 3.5:'
NEW_B = '    if ram_gb < 0.5:'

app, okB = _replace_once(app, OLD_B, NEW_B, "threshold 3.5 → 0.5 GB")
_rec("B", "RAM threshold lowered", okB)

OLD_C = '"Insufficient RAM ({ram_gb:.1f} GB free, need 3.5 GB)"'
NEW_C = '"Insufficient RAM ({ram_gb:.1f} GB free, need 0.5 GB)"'
app, okC = _replace_once(app, OLD_C, NEW_C, "error message updated")
_rec("C", "error message updated", okC)

# ── Write ─────────────────────────────────────────────────────────────────────
_h1("Writing patched app.py")
APP.write_text(app, encoding="utf-8")
_ok(f"Written ({len(app):,} chars)")
_rec("W", "app.py written", True)

# ── Verify ────────────────────────────────────────────────────────────────────
_h1("Verification")
checks = [
    ("MemAvailable + MemTotal fallback", "MemTotal" in app),
    ("threshold 0.5 present",           "ram_gb < 0.5" in app),
    ("old 3.5 threshold gone",          "ram_gb < 3.5" not in app),
    ("engine_v100 in ENGINE_SCRIPTS",   "engine_v100.py" in app),
]
all_ok = True
for label, cond in checks:
    ((_ok if cond else _err)(label))
    if not cond: all_ok = False
_rec("V", "verification", all_ok)
_require(all_ok, "Verification failed")

# ── Git ───────────────────────────────────────────────────────────────────────
_h1("Git commit + push")

_run('git config user.email "ramfix@tilawa.fix"', label="git config email")
_run('git config user.name "S32 RAM Fix"',        label="git config name")

ok_add, _ = _run("git add app.py", label="git add")
_rec("G1", "git add", ok_add)

msg = "S32 fix: RAM guard broken on HF Docker (0.0 GB); fallback to MemTotal + lower threshold"
ok_commit, out = _run(f'git commit -m "{msg}"', label="git commit")
if not ok_commit and "nothing to commit" in out:
    _ok("Nothing to commit")
    ok_commit = True
_rec("G2", "git commit", ok_commit)

ok_push, _ = _run(f"git push {HF_URL} main", label="git push", timeout=300)
_rec("G3", "git push", ok_push)

_print_summary()

if ok_push:
    print("\n  ✓ HF Space rebuilding — ready in ~3 min.")
    print("  The RAM guard was blocking every job. This is the real fix.")
else:
    print("\n  !! Push failed — check output above.")
