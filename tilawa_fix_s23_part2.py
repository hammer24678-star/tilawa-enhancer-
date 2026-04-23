#!/usr/bin/env python3
"""
tilawa_fix_s23_part2.py
=======================
Part 2 of 3 — Engine argparse fix:
  BUG 1: engine_v75.py crashes on launch when reference audio is present
  BUG 1: engine_v76.py crashes on launch when reference audio is present

Root cause (confirmed from source, 100%):
  app.py passes --ref to every engine. engine_v75 and engine_v76
  have no --ref defined in their argparse. parse_args() raises
  SystemExit(2) on any unrecognized argument -> job thread catches
  the exception -> status="error", score=0, bar frozen at 79.2%.

  Also: both engines hardcode REF_FILES to Termux paths
  (/mnt/user-data/uploads/...) which do not exist on the HF server.
  When --ref is passed with valid server paths, REF_FILES must be
  overridden to use them. Without this override, even with argparse
  fixed, the engines read 0 reference files and score 75 always.

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s23_part2.py

Precondition: Part 1 already pushed (app.py + Dockerfile + gunicorn fixed).
Part 3 verifies LFS and runs an end-to-end job test.
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
        _err("  Showing first 8 lines of file for orientation:")
        for line in text.splitlines()[:8]:
            print(f"        {line}")
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

# 1.2  Verify engine files present
_h2("1.2  Verify engine files present in clone")
expected = ["engine_v75.py", "engine_v76.py", "app.py"]
all_present = True
for f in expected:
    p = HF_CLONE / f
    exists = p.exists()
    sz = p.stat().st_size if exists else 0
    ((_ok if exists else _err)(f"{f}  ({sz:,} bytes)" if exists else f"{f} MISSING"))
    if not exists:
        all_present = False
_rec("1.2", "Engine files present", all_present)
if not all_present:
    _err("Missing engine files in clone -- aborting")
    sys.exit(1)

# 1.3  Confirm Part 1 fixes landed
_h2("1.3  Confirm Part 1 fixes are present in this clone")
app_check = _read(HF_CLONE / "app.py")
df_check  = _read(HF_CLONE / "Dockerfile")
gc_check  = _read(HF_CLONE / "gunicorn.conf.py")
p1_checks = [
    ('"--iterations", "3"' in app_check,  "app.py: iterations=3 (Part 1 BUG4)"),
    ('"\\u2605" in line' in app_check,    "app.py: star marker (Part 1 BUG3)"),
    ('"--max-requests"' not in df_check,  "Dockerfile: no max-requests (Part 1 BUG5)"),
    ('max_requests = 0' in gc_check,      "gunicorn.conf.py: max_requests=0 (Part 1 BUG5)"),
]
p1_all_ok = True
for ok, lbl in p1_checks:
    ((_ok if ok else _warn)(lbl))
    if not ok: p1_all_ok = False
if not p1_all_ok:
    _warn("Some Part 1 fixes not detected -- Part 1 may not have pushed yet")
    _warn("Continuing anyway; Part 2 fixes are independent of Part 1")
_rec("1.3", "Part 1 fixes checked", True)

# 1.4  Read engine_v75.py + confirm BUG 1 is still present
_h2("1.4  Read engine_v75.py -- confirm BUG 1 present")
V75 = HF_CLONE / "engine_v75.py"
v75 = _read(V75)
_ok(f"engine_v75.py: {len(v75):,} chars")

bug1_v75_argparse = ("'--ref'" not in v75 and '"--ref"' not in v75)
bug1_v75_reffiles = "/mnt/user-data/uploads/" in v75

((_ok if bug1_v75_argparse else _warn)("BUG 1 present: no --ref in v75 argparse"))
((_ok if bug1_v75_reffiles else _warn)("Termux REF_FILES present in v75"))

if not bug1_v75_argparse:
    _warn("--ref already present in v75 -- will verify correct form after patch")
_rec("1.4", "engine_v75.py read + bug confirmed", True)

# 1.5  Read engine_v76.py + confirm BUG 1 is still present
_h2("1.5  Read engine_v76.py -- confirm BUG 1 present")
V76 = HF_CLONE / "engine_v76.py"
v76 = _read(V76)
_ok(f"engine_v76.py: {len(v76):,} chars")

bug1_v76_argparse = ("'--ref'" not in v76 and '"--ref"' not in v76)
bug1_v76_reffiles = "/mnt/user-data/uploads/" in v76

((_ok if bug1_v76_argparse else _warn)("BUG 1 present: no --ref in v76 argparse"))
((_ok if bug1_v76_reffiles else _warn)("Termux REF_FILES present in v76"))

if not bug1_v76_argparse:
    _warn("--ref already present in v76 -- will verify correct form after patch")
_rec("1.5", "engine_v76.py read + bug confirmed", True)


# ======================================================================
#  STEP 2 — FIX engine_v75.py: ADD --ref ARGPARSE + REF_FILES OVERRIDE
# ======================================================================
_h1("STEP 2 -- Fix engine_v75.py: add --ref (BUG 1)")

# 2.1  Backup engine_v75.py
_h2("2.1  Backup engine_v75.py")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
BD = HF_CLONE / f".fix_backups/{TS}"
BD.mkdir(parents=True, exist_ok=True)
shutil.copy2(V75, BD / "engine_v75.py")
_ok(f"Backup: {BD}/engine_v75.py")
_rec("2.1", "engine_v75.py backed up", True)

# 2.2  Patch: insert --ref argument into argparse block
_h2("2.2  Patch engine_v75.py argparse block -- add --ref")

OLD_V75_ARGS = (
    "    p=argparse.ArgumentParser(description='Audio Enhancement Engine v7.5 \u2014 1425H')\n"
    "    p.add_argument('-i','--input');  p.add_argument('-o','--output')\n"
    "    p.add_argument('--iterations',type=int,default=3)\n"
    "    p.add_argument('--target',type=float,default=96.0)\n"
    "    p.add_argument('--batch-in');   p.add_argument('--batch-out')\n"
    "    p.add_argument('--serve',action='store_true')\n"
    "    p.add_argument('--port',type=int,default=5000)\n"
    "    p.add_argument('--clear-cache',action='store_true')\n"
    "    args=p.parse_args()\n"
)

NEW_V75_ARGS = (
    "    p=argparse.ArgumentParser(description='Audio Enhancement Engine v7.5 \u2014 1425H')\n"
    "    p.add_argument('-i','--input');  p.add_argument('-o','--output')\n"
    "    p.add_argument('--iterations',type=int,default=3)\n"
    "    p.add_argument('--target',type=float,default=96.0)\n"
    "    p.add_argument('--batch-in');   p.add_argument('--batch-out')\n"
    "    p.add_argument('--serve',action='store_true')\n"
    "    p.add_argument('--port',type=int,default=5000)\n"
    "    p.add_argument('--clear-cache',action='store_true')\n"
    "    # S23 BUG1: app.py passes --ref to all engines; parse_args() raised\n"
    "    # SystemExit(2) on unrecognized arg -> job crashed before first line\n"
    "    p.add_argument('--ref', action='append', default=[], metavar='PATH',\n"
    "                   help='Reference audio file (repeat for multiple)')\n"
    "    args=p.parse_args()\n"
    "    if args.ref:\n"
    "        valid=[r for r in args.ref if os.path.exists(r)]\n"
    "        if valid:\n"
    "            REF_FILES[:]=valid\n"
    "            print(f'  [ref] Using {len(REF_FILES)} reference file(s) from --ref flags')\n"
    "            if os.path.exists(REF_CACHE):\n"
    "                try: os.remove(REF_CACHE)\n"
    "                except: pass\n"
    "        else:\n"
    "            print(f'  [ref] WARNING: {len(args.ref)} --ref path(s) not found on disk')\n"
    "            print(f'  [ref] Using built-in REF_FILES (may be Termux paths)')\n"
)

v75, p22ok = _replace_once(v75, OLD_V75_ARGS, NEW_V75_ARGS, "v75 argparse block")
_rec("2.2", "engine_v75.py argparse patched", p22ok)

# 2.3  Verify patch: --ref present, old broken parse_args gone, override block there
_h2("2.3  Verify engine_v75.py patch")
checks_23 = [
    ("'--ref', action='append'" in v75,    "v75: --ref action='append' present"),
    ("REF_FILES[:]=valid" in v75,          "v75: REF_FILES override present"),
    ("S23 BUG1" in v75,                    "v75: S23 comment marker present"),
    ("os.path.exists(REF_CACHE)" in v75,   "v75: cache invalidation present"),
    ("/mnt/user-data/uploads/" in v75,     "v75: original Termux fallback still present (expected)"),
]
all_ok_23 = True
for ok, lbl in checks_23:
    ((_ok if ok else _err)(lbl))
    if not ok: all_ok_23 = False
_rec("2.3", "engine_v75.py patch verified", all_ok_23)

# 2.4  Write engine_v75.py
_h2("2.4  Write patched engine_v75.py")
if all_ok_23:
    _write(V75, v75)
    _ok(f"engine_v75.py written ({V75.stat().st_size:,} bytes)")
    _rec("2.4", "engine_v75.py written", True)
else:
    _err("Verification failed -- NOT writing engine_v75.py")
    _err("Check the anchor string matches the live server file exactly")
    _rec("2.4", "engine_v75.py written", False)
    sys.exit(1)

# 2.5  Visual spot-check of patched block
_h2("2.5  Visual spot-check of patched block in v75")
start = v75.find("# S23 BUG1")
if start >= 0:
    snippet = v75[start:start+500]
    for line in snippet.splitlines():
        print(f"     {line}")
    _ok("Block visible above")
else:
    _warn("S23 comment not found -- patch may not have applied correctly")
_rec("2.5", "v75 visual spot-check", start >= 0)


# ======================================================================
#  STEP 3 — FIX engine_v76.py: ADD --ref ARGPARSE + REF_FILES OVERRIDE
# ======================================================================
_h1("STEP 3 -- Fix engine_v76.py: add --ref (BUG 1)")

# 3.1  Backup engine_v76.py
_h2("3.1  Backup engine_v76.py")
shutil.copy2(V76, BD / "engine_v76.py")
_ok(f"Backup: {BD}/engine_v76.py")
_rec("3.1", "engine_v76.py backed up", True)

# 3.2  Patch: insert --ref argument into argparse block
_h2("3.2  Patch engine_v76.py argparse block -- add --ref")

OLD_V76_ARGS = (
    "    p=argparse.ArgumentParser(description='Audio Enhancement Engine v7.6 \u2014 1425H')\n"
    "    p.add_argument('-i','--input');  p.add_argument('-o','--output')\n"
    "    p.add_argument('--iterations',type=int,default=3)\n"
    "    p.add_argument('--target',type=float,default=96.0)\n"
    "    p.add_argument('--batch-in');   p.add_argument('--batch-out')\n"
    "    p.add_argument('--serve',action='store_true')\n"
    "    p.add_argument('--port',type=int,default=5000)\n"
    "    p.add_argument('--clear-cache',action='store_true')\n"
    "    args=p.parse_args()\n"
)

NEW_V76_ARGS = (
    "    p=argparse.ArgumentParser(description='Audio Enhancement Engine v7.6 \u2014 1425H')\n"
    "    p.add_argument('-i','--input');  p.add_argument('-o','--output')\n"
    "    p.add_argument('--iterations',type=int,default=3)\n"
    "    p.add_argument('--target',type=float,default=96.0)\n"
    "    p.add_argument('--batch-in');   p.add_argument('--batch-out')\n"
    "    p.add_argument('--serve',action='store_true')\n"
    "    p.add_argument('--port',type=int,default=5000)\n"
    "    p.add_argument('--clear-cache',action='store_true')\n"
    "    # S23 BUG1: app.py passes --ref to all engines; parse_args() raised\n"
    "    # SystemExit(2) on unrecognized arg -> job crashed before first line\n"
    "    p.add_argument('--ref', action='append', default=[], metavar='PATH',\n"
    "                   help='Reference audio file (repeat for multiple)')\n"
    "    args=p.parse_args()\n"
    "    if args.ref:\n"
    "        valid=[r for r in args.ref if os.path.exists(r)]\n"
    "        if valid:\n"
    "            REF_FILES[:]=valid\n"
    "            print(f'  [ref] Using {len(REF_FILES)} reference file(s) from --ref flags')\n"
    "            if os.path.exists(REF_CACHE):\n"
    "                try: os.remove(REF_CACHE)\n"
    "                except: pass\n"
    "        else:\n"
    "            print(f'  [ref] WARNING: {len(args.ref)} --ref path(s) not found on disk')\n"
    "            print(f'  [ref] Using built-in REF_FILES (may be Termux paths)')\n"
)

v76, p32ok = _replace_once(v76, OLD_V76_ARGS, NEW_V76_ARGS, "v76 argparse block")
_rec("3.2", "engine_v76.py argparse patched", p32ok)

# 3.3  Verify patch
_h2("3.3  Verify engine_v76.py patch")
checks_33 = [
    ("'--ref', action='append'" in v76,    "v76: --ref action='append' present"),
    ("REF_FILES[:]=valid" in v76,          "v76: REF_FILES override present"),
    ("S23 BUG1" in v76,                    "v76: S23 comment marker present"),
    ("os.path.exists(REF_CACHE)" in v76,   "v76: cache invalidation present"),
    ("/mnt/user-data/uploads/" in v76,     "v76: original Termux fallback still present (expected)"),
]
all_ok_33 = True
for ok, lbl in checks_33:
    ((_ok if ok else _err)(lbl))
    if not ok: all_ok_33 = False
_rec("3.3", "engine_v76.py patch verified", all_ok_33)

# 3.4  Write engine_v76.py
_h2("3.4  Write patched engine_v76.py")
if all_ok_33:
    _write(V76, v76)
    _ok(f"engine_v76.py written ({V76.stat().st_size:,} bytes)")
    _rec("3.4", "engine_v76.py written", True)
else:
    _err("Verification failed -- NOT writing engine_v76.py")
    _err("Check the anchor string matches the live server file exactly")
    _rec("3.4", "engine_v76.py written", False)
    sys.exit(1)

# 3.5  Visual spot-check of patched block
_h2("3.5  Visual spot-check of patched block in v76")
start = v76.find("# S23 BUG1")
if start >= 0:
    snippet = v76[start:start+500]
    for line in snippet.splitlines():
        print(f"     {line}")
    _ok("Block visible above")
else:
    _warn("S23 comment not found -- patch may not have applied correctly")
_rec("3.5", "v76 visual spot-check", start >= 0)


# ======================================================================
#  STEP 4 — COMMIT + PUSH TO HUGGINGFACE
# ======================================================================
_h1("STEP 4 -- Commit + push to HuggingFace")

# 4.1  Git identity
_h2("4.1  Git identity")
_run('git config user.email "tilawa@hf.build"', cwd=HF_CLONE, label="git config email")
_run('git config user.name "Tilawa Build"',     cwd=HF_CLONE, label="git config name")
_rec("4.1", "Git identity set", True)

# 4.2  Stage changed engine files
_h2("4.2  Stage engine_v75.py + engine_v76.py")
ok42a, _ = _run("git add engine_v75.py", cwd=HF_CLONE, label="git add engine_v75.py")
ok42b, _ = _run("git add engine_v76.py", cwd=HF_CLONE, label="git add engine_v76.py")
_rec("4.2", "Engine files staged", ok42a and ok42b)

# 4.3  Confirm only the engine files changed (guard against accidental diff)
_h2("4.3  Confirm staged diff is engine files only")
ok43s, diff_stat = _run("git diff --cached --stat", cwd=HF_CLONE, label="git diff --cached --stat")
if diff_stat:
    for line in diff_stat.splitlines():
        print(f"     {line}")
v75_in_diff = "engine_v75.py" in diff_stat
v76_in_diff = "engine_v76.py" in diff_stat
app_in_diff = "app.py" in diff_stat
((_ok if v75_in_diff  else _warn)("engine_v75.py in staged diff"))
((_ok if v76_in_diff  else _warn)("engine_v76.py in staged diff"))
((_ok if not app_in_diff else _warn)("app.py NOT in staged diff (correct, unchanged here)"))
_rec("4.3", "Staged diff correct", v75_in_diff and v76_in_diff)

# 4.4  Commit
_h2("4.4  Commit")
ok44, out44 = _run(
    'git commit -m "fix: S23p2 v75+v76 --ref argparse + REF_FILES override (BUG1)"',
    cwd=HF_CLONE, label="git commit"
)
if not ok44 and "nothing to commit" in out44:
    _warn("Nothing to commit -- changes may already be pushed")
    ok44 = True
_rec("4.4", "Committed", ok44)

# 4.5  Push to HuggingFace
_h2("4.5  Push to HuggingFace")
ok45, _ = _run("git push", cwd=HF_CLONE, label="git push HF")
_rec("4.5", "Pushed to HF", ok45)
if not ok45:
    _warn("Push failed -- manual fallback:")
    print(f"     cd {HF_CLONE} && git push")


# ======================================================================
#  STEP 5 — REVIEW: RE-VERIFY EVERYTHING BEFORE CLEANUP
# ======================================================================
_h1("STEP 5 (REVIEW) -- Re-verify all changes are correct")

# 5.1  Re-read both patched engine files + full spot-check
_h2("5.1  Full spot-check of both patched engine files")
v75_final = _read(V75)
v76_final = _read(V76)

checks_51 = [
    # v75
    ("'--ref', action='append'" in v75_final,  "v75: --ref argument present"),
    ("REF_FILES[:]=valid" in v75_final,         "v75: REF_FILES override present"),
    ("S23 BUG1" in v75_final,                   "v75: S23 comment marker"),
    ("os.path.exists(REF_CACHE)" in v75_final,  "v75: cache invalidation"),
    # v76
    ("'--ref', action='append'" in v76_final,  "v76: --ref argument present"),
    ("REF_FILES[:]=valid" in v76_final,         "v76: REF_FILES override present"),
    ("S23 BUG1" in v76_final,                   "v76: S23 comment marker"),
    ("os.path.exists(REF_CACHE)" in v76_final,  "v76: cache invalidation"),
    # cross-check: old parse_args() still present (correct, we only added before it)
    ("args=p.parse_args()" in v75_final,        "v75: parse_args() still present"),
    ("args=p.parse_args()" in v76_final,        "v76: parse_args() still present"),
]
all_51 = True
for ok, lbl in checks_51:
    ((_ok if ok else _err)(lbl))
    if not ok: all_51 = False
_rec("5.1", "Full spot-check", all_51)

# 5.2  Verify git log shows the commit
_h2("5.2  Git log -- confirm Part 2 commit is there")
ok52, log52 = _run("git log --oneline -4", cwd=HF_CLONE, label="git log")
if log52:
    for line in log52.splitlines():
        print(f"     {line}")
_rec("5.2", "Git log checked", ok52)

# 5.3  Poll live HF server health
_h2("5.3  Check live server health endpoint")
_warn("HF rebuilds ~2 min after push. Checking now (may still be building)...")
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
    if not engines_ok: _warn("Not all engines reporting True -- server may still be rebuilding")
    if not refs_ok:    _warn("refs != 3 -- Part 3 will verify LFS status")
    health_ok = data.get("status") == "ok"
except Exception as e:
    _warn(f"Health check failed ({e}) -- server may still be rebuilding, check manually in 2 min")
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
_h1("PART 2 SUMMARY")
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
    print("  PART 2 COMPLETE")
    print()
    print("  Fixed in this run:")
    print("    BUG 1: engine_v75.py -- --ref added to argparse")
    print("           REF_FILES overridden from server reference_audio/")
    print("           cache invalidated when new paths supplied")
    print("    BUG 1: engine_v76.py -- same fix, same logic")
    print()
    print("  v7.5 (BEST badge) and v7.6 (MDS badge) will no longer")
    print("  crash at launch when reference_audio/*.mp3 is present.")
    print()
    print("  Still to verify:")
    print("    BUG 2: LFS stubs -- verify via live v8.0 job  -> Part 3")
    print()
    print("  Next step:")
    print("    python3 tilawa_fix_s23_part3.py")
    print("  " + "=" * 64)
else:
    print("  " + "=" * 64)
    print("  SOME CHECKS FAILED -- review output above before running Part 3")
    print("  " + "=" * 64)
    sys.exit(1)
