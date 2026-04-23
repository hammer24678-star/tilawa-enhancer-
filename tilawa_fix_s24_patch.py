#!/usr/bin/env python3
"""
tilawa_fix_s24_patch.py
=======================
Finishes what S24 couldn't — engine_v81.py wasn't in Termux during S24.

Fixes:
  + Copy engine_v81.py into repo
  - git rm engine_v75.py + engine_v76.py
  + Patch Dockerfile: add --preload
  + Update README engine list
  + Commit + push

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s24_patch.py
"""

import sys, shutil, subprocess, urllib.request, json
from pathlib import Path
from datetime import datetime

# ── helpers ───────────────────────────────────────────────────────────────────
def _h1(t):
    print(f"\n{'='*64}\n  {t}\n{'='*64}")

def _h2(t):  print(f"\n  -- {t}")
def _ok(m):  print(f"     OK  {m}")
def _err(m): print(f"     XX  {m}")
def _warn(m):print(f"     !!  {m}")

_log = []
def _rec(sid, label, ok):
    _log.append((sid, label, "[OK] PASS" if ok else "[XX] FAIL"))
    return ok

def _run(cmd, cwd=None, timeout=120):
    r = subprocess.run(cmd, shell=True, cwd=str(cwd or HF_CLONE),
                       capture_output=True, text=True, timeout=timeout)
    ok = r.returncode == 0
    out = (r.stdout + r.stderr).strip()
    ((_ok if ok else _err)(cmd))
    if not ok and out:
        for line in out.splitlines()[-4:]:
            print(f"        {line}")
    return ok, out

def _require(cond, msg):
    if not cond:
        _err(f"FATAL: {msg}")
        _summary()
        sys.exit(1)

def _read(p):     return Path(p).read_text(encoding="utf-8")
def _write(p, t): Path(p).write_text(t, encoding="utf-8")

def _replace_once(text, old, new, label):
    if old not in text:
        _err(f"Anchor not found -- {label}")
        return text, False
    _ok(f"Patched -- {label}")
    return text.replace(old, new, 1), True

def _summary():
    _h1("SUMMARY")
    print(f"\n  {'Step':<6}  {'Label':<50}  Result")
    print(f"  {'----':<6}  {'------':<50}  ------")
    for sid, label, result in _log:
        print(f"  {sid:<6}  {label:<50}  {result}")

# ── config ────────────────────────────────────────────────────────────────────
HF_URL   = (
    "https://carm5333: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"
    "@huggingface.co/spaces/carm5333/tilawa-server"
)
HF_CLONE = Path.home() / "tilawa-hf-clone"
SERVER   = "https://carm5333-tilawa-server.hf.space"
V81_SRC  = Path.home() / "tilawa-enhancer" / "engine_v81.py"

_h1("S24-PATCH  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# ── pre-flight ────────────────────────────────────────────────────────────────
_h1("STEP 0 -- Pre-flight checks")

_h2("0.1  engine_v81.py present in tilawa-enhancer")
ok01 = V81_SRC.exists()
sz   = V81_SRC.stat().st_size if ok01 else 0
((_ok if ok01 else _err)(f"engine_v81.py  ({sz:,} bytes)" if ok01
                          else f"NOT FOUND: {V81_SRC}"))
_rec("0.1", "engine_v81.py source present", ok01)
_require(ok01, f"engine_v81.py missing. Run: cp /sdcard/Download/engine_v81.py ~/tilawa-enhancer/")

# ── clone ─────────────────────────────────────────────────────────────────────
_h1("STEP 1 -- Clone HF Space")

_h2("1.1  Fresh clone (skip LFS blobs)")
if HF_CLONE.exists():
    shutil.rmtree(HF_CLONE)
ok11, _ = _run(
    f"GIT_LFS_SKIP_SMUDGE=1 git clone {HF_URL} {HF_CLONE}",
    cwd=Path.home()
)
_rec("1.1", "HF Space cloned", ok11)
_require(ok11, "Clone failed")

_h2("1.2  Confirm S24 app.py already landed")
app_txt = _read(HF_CLONE / "app.py")
s24_ok  = '"v8.1": BASE / "engine_v81.py"' in app_txt
((_ok if s24_ok else _warn)(
    "app.py already has v8.1 ENGINE_SCRIPTS (S24 landed)" if s24_ok
    else "app.py does NOT have v8.1 -- S24 app.py patch may have failed"
))
_rec("1.2", "S24 app.py confirmed", s24_ok)

_h2("1.3  Confirm v7.5 + v7.6 still need removal")
v75_exists = (HF_CLONE / "engine_v75.py").exists()
v76_exists = (HF_CLONE / "engine_v76.py").exists()
v81_exists = (HF_CLONE / "engine_v81.py").exists()
((_ok if v75_exists  else _warn)("engine_v75.py present (will remove)"))
((_ok if v76_exists  else _warn)("engine_v76.py present (will remove)"))
((_warn if v81_exists else _ok)("engine_v81.py NOT in repo yet (will add)" if not v81_exists
                                 else "engine_v81.py already in repo"))
_rec("1.3", "State verified", True)

# ── engine operations ─────────────────────────────────────────────────────────
_h1("STEP 2 -- Engine file operations")

_h2("2.1  Copy engine_v81.py into clone")
shutil.copy2(V81_SRC, HF_CLONE / "engine_v81.py")
sz81 = (HF_CLONE / "engine_v81.py").stat().st_size
ok21 = sz81 > 50_000
((_ok if ok21 else _err)(f"engine_v81.py copied ({sz81:,} bytes)"))
_rec("2.1", "engine_v81.py copied", ok21)
_require(ok21, "engine_v81.py too small -- source file may be corrupt")

_h2("2.2  Stage engine_v81.py")
ok22, _ = _run("git add engine_v81.py")
_rec("2.2", "engine_v81.py staged", ok22)

_h2("2.3  git rm engine_v75.py")
if v75_exists:
    ok23, _ = _run("git rm engine_v75.py")
else:
    _warn("engine_v75.py already gone -- skipping")
    ok23 = True
_rec("2.3", "engine_v75.py removed", ok23)

_h2("2.4  git rm engine_v76.py")
if v76_exists:
    ok24, _ = _run("git rm engine_v76.py")
else:
    _warn("engine_v76.py already gone -- skipping")
    ok24 = True
_rec("2.4", "engine_v76.py removed", ok24)

# ── dockerfile ────────────────────────────────────────────────────────────────
_h1("STEP 3 -- Patch Dockerfile")

_h2("3.1  Add --preload to gunicorn CMD")
DF  = HF_CLONE / "Dockerfile"
df  = _read(DF)
has_preload = "--preload" in df
if has_preload:
    _warn("--preload already present -- skipping")
    ok31 = True
else:
    OLD = (
        'CMD ["gunicorn", "app:app", \\\n'
        '     "--bind", "0.0.0.0:7860", \\\n'
        '     "--timeout", "2400", \\\n'
        '     "--workers", "1", \\\n'
        '     "--keep-alive", "5"]'
    )
    NEW = (
        '# S24p: --preload loads app before first request (reduces cold-start lag)\n'
        'CMD ["gunicorn", "app:app", \\\n'
        '     "--bind", "0.0.0.0:7860", \\\n'
        '     "--timeout", "2400", \\\n'
        '     "--workers", "1", \\\n'
        '     "--preload", \\\n'
        '     "--keep-alive", "5"]'
    )
    df, ok31 = _replace_once(df, OLD, NEW, "--preload in Dockerfile CMD")
    _write(DF, df)
_rec("3.1", "Dockerfile --preload", ok31)

_h2("3.2  Stage Dockerfile")
ok32, _ = _run("git add Dockerfile")
_rec("3.2", "Dockerfile staged", ok32)

# ── readme ────────────────────────────────────────────────────────────────────
_h1("STEP 4 -- Update README")

_h2("4.1  Fix engine list in README")
RM  = HF_CLONE / "README.md"
rm  = _read(RM)
already_updated = "v8.1" in rm
if already_updated:
    _warn("README already updated -- skipping")
    ok41 = True
else:
    OLD_RM = "Flask API serving engines v7.0, v7.5, v7.6"
    NEW_RM = (
        "Flask API serving engines "
        "v8.1 (Android-Hardened), v8.0 (Calibrated), v7.0 (Stable)"
    )
    rm, ok41 = _replace_once(rm, OLD_RM, NEW_RM, "README engine list")
    _write(RM, rm)
_rec("4.1", "README updated", ok41)

_h2("4.2  Stage README")
ok42, _ = _run("git add README.md")
_rec("4.2", "README staged", ok42)

# ── verify staged diff ────────────────────────────────────────────────────────
_h1("STEP 5 -- Verify staged diff")

_h2("5.1  git diff --cached --stat")
ok51, stat = _run("git diff --cached --stat")
for line in stat.splitlines():
    _ok(f"  {line}")

v81_in  = "engine_v81.py" in stat
v75_out = "engine_v75.py" in stat
v76_out = "engine_v76.py" in stat
((_ok if v81_in  else _err)("engine_v81.py in diff (add)"))
((_ok if v75_out else _err)("engine_v75.py in diff (delete)"))
((_ok if v76_out else _err)("engine_v76.py in diff (delete)"))
_rec("5.1", "Staged diff correct", v81_in and v75_out and v76_out)

# ── commit + push ─────────────────────────────────────────────────────────────
_h1("STEP 6 -- Commit + push")

_h2("6.1  Git identity")
_run('git config user.email "fix@s24p"')
_run('git config user.name "S24-Patch"')

_h2("6.2  Commit")
msg = "fix: S24-patch add engine_v81 + rm v7.5/v7.6 + Dockerfile preload + README"
ok62, _ = _run(f'git commit -m "{msg}"')
_rec("6.2", "Committed", ok62)
_require(ok62, "git commit failed")

_h2("6.3  Push to HuggingFace")
ok63, _ = _run("git push", timeout=120)
_rec("6.3", "Pushed to HF", ok63)
_require(ok63, "git push failed")

# ── post-push ─────────────────────────────────────────────────────────────────
_h1("STEP 7 -- Post-push verification")

_h2("7.1  Git log")
_, log = _run("git log --oneline -5")
for line in log.splitlines():
    _ok(f"  {line}")
_rec("7.1", "Git log checked", True)

_h2("7.2  Live health check (HF rebuilds ~2 min after push)")
_warn("HF is rebuilding. Checking current state...")
try:
    req = urllib.request.Request(
        SERVER + "/", headers={"User-Agent": "s24patch"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    engines = data.get("engines", {})
    _ok(f"status={data.get('status')}  engines={engines}  refs={data.get('refs')}")
    v81_live = engines.get("v8.1", False)
    ((_ok if v81_live else _warn)(
        "v8.1: True -- engine file confirmed on server" if v81_live
        else "v8.1: False -- server still rebuilding, check again in 2 min"
    ))
    _rec("7.2", "Health check", True)
except Exception as e:
    _warn(f"Health check error: {e}")
    _warn(f"Check manually: curl -s {SERVER}/")
    _rec("7.2", "Health check", False)

_h2("7.3  Cleanup clone")
shutil.rmtree(HF_CLONE)
_ok(f"Removed {HF_CLONE}")
_rec("7.3", "Clone cleaned up", True)

# ── summary ───────────────────────────────────────────────────────────────────
_summary()

fails = [x for x in _log if "FAIL" in x[2]]
print(f"""
  ================================================================
  S24-PATCH {'COMPLETE' if not fails else f'FAILED ({len(fails)} step(s) -- see above)'}

  After HF rebuilds (~2 min), verify:
    curl -s {SERVER}/
    Expected: v8.1=true, v8.0=true, v7.0=true, status=ok

  Next step -- new APK build with updated engine cards:
    v8.1  Android-Hardened  (replace v7.5 BEST + v7.6 MDS)
    v8.0  Calibrated Precision
    v7.0  Stable Classic
  ================================================================
""")

if fails:
    sys.exit(1)
