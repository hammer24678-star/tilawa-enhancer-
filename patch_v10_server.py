"""
patch_v10_server.py — S32 Hotfix

ROOT CAUSE:
  app.py on the HuggingFace server maps:
      "v10.0": BASE / "engine_v100.py"
  But engine_v100.py was NEVER pushed to the HF space.
  The Flutter app sends v10.0 → server looks for the file → not found
  → script.exists() is False → immediate "Engine failed" (79% is just
  client-side animation that kept ticking until the error came back).

FIX:
  Copy engine_v100.py from the Flutter repo into the HF server clone,
  then commit + push.

Run from ~/tilawa-enhancer (the Flutter repo directory):
  cd ~/tilawa-enhancer && python3 patch_v10_server.py
"""

import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# ── helpers ──────────────────────────────────────────────────────────────────
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
    r = subprocess.run(
        cmd, shell=True,
        cwd=str(cwd or HF_CLONE),
        capture_output=True, text=True, timeout=timeout,
    )
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

# ── config ───────────────────────────────────────────────────────────────────
HF_URL   = (
    "https://carm5333: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"
    "@huggingface.co/spaces/carm5333/tilawa-server"
)
HF_CLONE    = Path.home() / "tilawa-hf-clone"
FLUTTER_DIR = Path(__file__).parent          # ~/tilawa-enhancer

SRC_ENGINE  = FLUTTER_DIR / "engine_v100.py"
DST_ENGINE  = HF_CLONE    / "engine_v100.py"

_h1("patch_v10_server.py  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("\n  ROOT CAUSE: engine_v100.py missing from HF server space")
print("  FIX:        copy from Flutter repo → HF clone → git push\n")

# ── Step 0: verify source engine exists ──────────────────────────────────────
_h1("STEP 0 — Verify source engine_v100.py")
_require(SRC_ENGINE.exists(),
         f"engine_v100.py not found in Flutter repo: {SRC_ENGINE}")
_ok(f"Source found: {SRC_ENGINE.stat().st_size:,} bytes")
_rec("S0", "source engine_v100.py present", True)

# ── Step 1: verify/clone HF repo ─────────────────────────────────────────────
_h1("STEP 1 — Verify HF clone")

if not HF_CLONE.exists():
    _h1("  Cloning HF space (first time)…")
    ok_clone, _ = _run(
        f"git clone {HF_URL} {HF_CLONE}",
        cwd=Path.home(),
        label="git clone tilawa-server",
        timeout=300,
    )
    _require(ok_clone, "git clone failed — check HF token / network")
else:
    _ok(f"HF clone exists: {HF_CLONE}")
    # pull latest to avoid conflicts
    ok_pull, _ = _run("git pull --ff-only", label="git pull")
    if not ok_pull:
        _err("git pull failed — continuing anyway (may cause push conflict)")

_require((HF_CLONE / "app.py").exists(), "app.py missing from HF clone")
_ok("app.py confirmed present in HF clone")
_rec("S1", "HF clone ready", True)

# ── Step 2: copy engine_v100.py ──────────────────────────────────────────────
_h1("STEP 2 — Copy engine_v100.py → HF clone")

shutil.copy2(str(SRC_ENGINE), str(DST_ENGINE))
_ok(f"Copied → {DST_ENGINE} ({DST_ENGINE.stat().st_size:,} bytes)")
_rec("S2", "engine_v100.py copied to HF clone", True)

# ── Step 3: verify app.py ENGINE_SCRIPTS mapping ─────────────────────────────
_h1("STEP 3 — Verify app.py mapping")

app_text = (HF_CLONE / "app.py").read_text(encoding="utf-8")
mapping_ok = '"v10.0": BASE / "engine_v100.py"' in app_text
if mapping_ok:
    _ok("app.py already maps v10.0 → engine_v100.py ✓")
else:
    _err("app.py is missing the v10.0 mapping — patching it now")
    # Insert the mapping before v9.0 line
    OLD = '"v9.0":  BASE / "engine_v90.py",'
    NEW = '"v10.0": BASE / "engine_v100.py",\n    "v9.0":  BASE / "engine_v90.py",'
    if OLD in app_text:
        app_text = app_text.replace(OLD, NEW, 1)
        (HF_CLONE / "app.py").write_text(app_text, encoding="utf-8")
        _ok("Patched app.py with v10.0 mapping")
        mapping_ok = True
    else:
        _err("Could not locate anchor in app.py — please check manually")
_rec("S3", "app.py v10.0 mapping confirmed", mapping_ok)

# ── Step 4: git operations ────────────────────────────────────────────────────
_h1("STEP 4 — Git commit + push")

_run('git config user.email "s32-hotfix@tilawa.fix"', label="git config email")
_run('git config user.name "S32 Hotfix"',             label="git config name")

ok_add, _ = _run("git add engine_v100.py app.py", label="git add")
_rec("G1", "git add", ok_add)

_run("git status --short", label="git status")

commit_msg = "S32 hotfix: add missing engine_v100.py to server space"
ok_commit, out_commit = _run(f'git commit -m "{commit_msg}"', label="git commit")
if not ok_commit and "nothing to commit" in out_commit:
    _ok("Nothing new to commit (engine_v100.py already pushed)")
    ok_commit = True
_rec("G2", "git commit", ok_commit)

ok_push, _ = _run(f"git push {HF_URL} main", label="git push to HF", timeout=300)
_rec("G3", "git push", ok_push)

# ── Summary ───────────────────────────────────────────────────────────────────
_print_summary()

if ok_push:
    print("\n  ✓ HF Space is rebuilding. Ready in ~3 min:")
    print("  https://carm5333-tilawa-server.hf.space/")
    print("\n  After rebuild, curl the health check:")
    print('  curl https://carm5333-tilawa-server.hf.space/ | python3 -m json.tool')
    print("\n  Confirm engines shows: \"v10.0\": true")
else:
    print("\n  !! Push failed. Check output above.")
    print("  Possible causes:")
    print("  - HF token expired → refresh at huggingface.co/settings/tokens")
    print("  - LFS quota exceeded → check HF space storage")
    print("  - Network issue → retry in a few seconds")
