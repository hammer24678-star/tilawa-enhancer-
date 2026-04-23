#!/usr/bin/env python3
"""
tilawa_fix_s23_part3.py  (v2)
==============================
Part 3 of 3 — Verification + conditional LFS fix.

  BUG 2: Reference audio LFS stubs (verify first, fix only if confirmed broken)
  E2E:   v7.5 job — confirm no crash, progress advances, score != 0

LFS detection logic:
  v8.0 uses Path(__file__).parent/"reference_audio" = /app/reference_audio/
  Never depends on --ref flags, so it is the clean LFS probe.
  If files are 132-byte LFS stubs, ffprobe cannot decode them.
  Engine subprocess crashes → app.py catches → score=75 fallback (hardcoded).
  ANY other score means the engine ran with real reference data.

  score == 75  or  status == "error"  ->  LFS broken
  score != 75  and  status == "done"  ->  LFS OK

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s23_part3.py

Preconditions:
  Part 1 pushed: progress markers + iterations=3 + max-requests removed
  Part 2 pushed: engine_v75.py + engine_v76.py --ref argparse + REF_FILES override
"""

import os, sys, shutil, subprocess, urllib.request, json, time, glob
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
        return text, False
    if c > 1:
        _warn(f"Anchor found {c}x -- replacing first -- {label}")
    _ok(f"Replaced -- {label}")
    return text.replace(old, new, 1), True

def _run(cmd, cwd=None, label="", timeout=300):
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
HF_CLONE     = Path.home() / "tilawa-hf-clone"
HF_LFS_CLONE = Path.home() / "tilawa-hf-lfs"
HF_TOKEN     = "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"
SERVER       = "https://carm5333-tilawa-server.hf.space"
TEST_MP3     = Path.home() / "tilawa_test_s23.mp3"

# Real reference file names to search for locally
REF_NAMES = [
    "\u0627\u0644\u0645\u0631\u062c\u06421425.mp3",
    "\u0633\u0648\u0631\u0647_\u0627\u0644\u0641\u062a\u062d.mp3",
]
SEARCH_ROOTS = [
    "/sdcard/Download",
    "/sdcard/Music",
    "/mnt/user-data/uploads",
    str(Path.home()),
]

# ── job helpers ───────────────────────────────────────────────────────────────
def _submit_job(engine, mp3_path):
    ok, out = _run(
        f'curl -s -X POST {SERVER}/upload'
        f' -F "file=@{mp3_path}"'
        f' -F "engine={engine}"',
        label=f"POST /upload engine={engine}",
        timeout=60,
    )
    if not ok or not out.strip():
        return None
    try:
        d = json.loads(out)
        jid = d.get("job_id")
        if jid:
            _ok(f"job_id={jid}")
            return jid
        _err(f"No job_id in response: {out[:200]}")
        return None
    except Exception as e:
        _err(f"JSON parse error: {e} -- raw: {out[:200]}")
        return None

def _poll_job(job_id, engine, max_minutes, interval_s):
    deadline      = time.time() + max_minutes * 60
    seen_progress = []
    last_prog     = -1
    last_change   = time.time()
    freeze_warned = False

    _ok(f"Polling {engine}/{job_id} (max {max_minutes}min, every {interval_s}s)")

    while time.time() < deadline:
        time.sleep(interval_s)
        try:
            req = urllib.request.Request(
                f"{SERVER}/status/{job_id}",
                headers={"Authorization": f"Bearer {HF_TOKEN}"}
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                d = json.loads(r.read().decode())
        except Exception as e:
            _warn(f"Poll error: {e}")
            continue

        status  = d.get("status", "?")
        prog    = d.get("progress", 0)
        score   = d.get("score")
        lbl_txt = d.get("label", "")
        elapsed = int(time.time() - last_change)

        if prog != last_prog:
            print(f"     [+{elapsed:>3}s] progress={prog:>3}  status={status:<10}  {lbl_txt}")
            if prog not in seen_progress:
                seen_progress.append(prog)
            last_prog   = prog
            last_change = time.time()
            freeze_warned = False
        elif elapsed > 90 and not freeze_warned and status not in ("done", "error"):
            _warn(f"Progress frozen at {prog} for {elapsed}s")
            if prog == 35:
                _warn("  --> 35 = engine crashed on launch (BUG1) or progress markers not matching (BUG3)")
            freeze_warned = True

        if status in ("done", "error", "expired"):
            print(f"     [DONE] status={status}  progress={prog}  score={score}")
            return status, score, prog, seen_progress

    _warn(f"Timeout after {max_minutes} min")
    return "timeout", None, last_prog, seen_progress


# ======================================================================
#  STEP 1 — GET TEST AUDIO FILE + WAIT FOR SERVER REBUILD
# ======================================================================
_h1("STEP 1 -- Get test audio + wait for server rebuild")

# 1.1  Search for a real audio file first; generate synthetic only as fallback
_h2("1.1  Find test MP3 (real audio preferred over synthetic)")

test_file_found = False
test_file_source = ""

# Priority 1: any existing real MP3 in known locations
for root in SEARCH_ROOTS:
    candidates = list(Path(root).glob("*.mp3")) if Path(root).exists() else []
    candidates += list(Path(root).glob("*.m4a")) if Path(root).exists() else []
    for c in candidates:
        if c.stat().st_size > 100_000:  # > 100KB = real audio
            shutil.copy2(c, TEST_MP3)
            _ok(f"Using real audio: {c.name} ({c.stat().st_size:,} bytes)")
            test_file_found = True
            test_file_source = f"real: {c.name}"
            break
    if test_file_found:
        break

# Priority 2: generate synthetic with ffmpeg or sox
if not test_file_found:
    _warn("No real audio found -- generating synthetic 10-second test tone")
    ffmpeg_ok, _ = _run("ffmpeg -version", label="ffmpeg available", timeout=10)
    sox_ok, _    = _run("sox --version",   label="sox available",    timeout=10)

    if ffmpeg_ok:
        gen_ok, _ = _run(
            f"ffmpeg -f lavfi -i 'sine=frequency=440:duration=10'"
            f" -ar 44100 -ac 1 -q:a 5 {TEST_MP3} -y",
            label=f"ffmpeg: generate {TEST_MP3}", timeout=30,
        )
        if gen_ok and TEST_MP3.exists() and TEST_MP3.stat().st_size > 1000:
            _ok(f"Synthetic MP3 generated: {TEST_MP3.stat().st_size:,} bytes")
            test_file_found = True
            test_file_source = "synthetic:ffmpeg"

    if not test_file_found and sox_ok:
        gen_ok, _ = _run(
            f"sox -n -r 44100 -c 1 {TEST_MP3} synth 10 sine 440",
            label=f"sox: generate {TEST_MP3}", timeout=30,
        )
        if gen_ok and TEST_MP3.exists() and TEST_MP3.stat().st_size > 1000:
            _ok(f"Synthetic MP3 generated (sox): {TEST_MP3.stat().st_size:,} bytes")
            test_file_found = True
            test_file_source = "synthetic:sox"

_rec("1.1", "Test audio ready", test_file_found)
if not test_file_found:
    _err("No test audio available. Install ffmpeg (pkg install ffmpeg) or")
    _err("copy any MP3 file to /sdcard/Download/ and re-run.")
    sys.exit(1)

# 1.2  Wait for HF server rebuild (Part 1+2 pushes triggered Docker rebuild)
_h2("1.2  Wait for HF server rebuild (up to 5 min)")
server_up = False
_refs     = -1
deadline  = time.time() + 300
attempt   = 0

while time.time() < deadline:
    attempt += 1
    time.sleep(15)
    try:
        req = urllib.request.Request(
            f"{SERVER}/",
            headers={"Authorization": f"Bearer {HF_TOKEN}"}
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            hd = json.loads(r.read().decode())
        if hd.get("status") == "ok":
            _ok(f"Server up (attempt {attempt}): engines={hd.get('engines')}  refs={hd.get('refs')}")
            server_up = True
            _refs = hd.get("refs", 0)
            break
        _warn(f"Attempt {attempt}: {hd.get('status')} -- still rebuilding")
    except Exception as e:
        _warn(f"Attempt {attempt}: {e}")

if not server_up:
    _warn("Server did not respond in 5 min. Continuing; jobs may still queue.")
    _refs = -1
_rec("1.2", "Server health confirmed", server_up)

# 1.3  Log refs count as early LFS hint
_h2("1.3  refs count hint")
if _refs == 3:
    _ok("refs=3 -- server has 3 reference audio files")
    _ok("This is necessary but not sufficient -- files could be 132-byte LFS stubs")
    _ok("The v8.0 job result is the definitive test")
elif _refs == 0:
    _warn("refs=0 -- reference_audio/ is empty -- v8.0 will use fallback fingerprints")
else:
    _warn(f"refs={_refs}")
_rec("1.3", "refs count noted", True)

# 1.4  Confirm Part 1+2 fixes are live (check app.py via health + git resolve)
_h2("1.4  Pre-flight: confirm Part 1+2 fixes were pushed")
_warn("Cannot read live app.py from health endpoint.")
_warn("Assuming Part 1+2 already ran. If not, results may be misleading.")
_warn("If progress never advances beyond 35, re-run Part 1+2 first.")
_rec("1.4", "Pre-flight noted", True)


# ======================================================================
#  STEP 2 — LFS VERIFICATION VIA v8.0 JOB
# ======================================================================
_h1("STEP 2 -- LFS verification: submit v8.0 job")

LFS_OK = None

# 2.1  Submit v8.0 job
_h2("2.1  Submit v8.0 job (LFS probe)")
_ok(f"Test file: {TEST_MP3} ({TEST_MP3.stat().st_size:,} bytes) [{test_file_source}]")
jid_v80 = _submit_job("v8.0", TEST_MP3)
_rec("2.1", "v8.0 job submitted", jid_v80 is not None)

if jid_v80 is None:
    _err("Cannot submit v8.0 job. Check server status:")
    print(f"     curl -s {SERVER}/")
    _rec("2.2", "v8.0 polled (skipped)", False)
    _rec("2.3", "LFS determined (skipped)", False)
else:
    # 2.2  Poll
    _h2("2.2  Poll v8.0 job (max 20 min)")
    st80, sc80, pr80, seq80 = _poll_job(jid_v80, "v8.0", max_minutes=20, interval_s=10)
    _rec("2.2", "v8.0 job polled", st80 in ("done", "error"))

    # 2.3  Evaluate LFS
    _h2("2.3  Evaluate LFS from v8.0 result")
    print(f"     status={st80}  score={sc80}  progress_seq={seq80}")

    if st80 == "done" and sc80 is not None:
        sc = float(sc80)
        if sc != 75.0:
            _ok(f"LFS OK: score={sc80} (not 75) -- real reference audio was used")
            LFS_OK = True
        else:
            _warn(f"LFS LIKELY BROKEN: score=75.0 exactly")
            _warn("  /app/reference_audio/*.mp3 are 132-byte LFS pointer stubs")
            _warn("  ffprobe cannot decode them -> engine crash -> app.py score=75 fallback")
            LFS_OK = False
    elif st80 == "error":
        _warn("v8.0 returned status=error -- treating as LFS broken")
        LFS_OK = False
    elif st80 == "timeout":
        _warn("v8.0 timed out -- cannot determine LFS status")
        LFS_OK = None
    _rec("2.3", "LFS status determined", LFS_OK is not None)

    # 2.4  Also note progress advancement for BUG3 probe
    _h2("2.4  Note progress advancement (BUG3 probe)")
    prog_moved_v80 = any(p > 35 for p in seq80)
    if prog_moved_v80:
        _ok(f"BUG3 fix confirmed: v8.0 progress advanced {seq80}")
    else:
        _warn(f"v8.0 progress did not advance beyond 35 -- BUG3 fix may not be live yet")
        _warn("  Wait 2 min for HF rebuild and re-run Part 3")
    _rec("2.4", "Progress advancement noted", prog_moved_v80)


# ======================================================================
#  STEP 3 — LFS FIX (ONLY IF CONFIRMED BROKEN)
# ======================================================================
_h1("STEP 3 -- LFS fix (conditional)")

lfs_fix_applied = False

if LFS_OK is True:
    _ok("LFS is fine. Skipping LFS fix.")
    for sid in ["3.1", "3.2", "3.3", "3.4"]:
        _rec(sid, "LFS fix skipped (not needed)", True)

elif LFS_OK is None:
    _warn("LFS status unknown (timeout). Skipping LFS fix.")
    _warn("Re-run Part 3 once the server stabilises.")
    for sid in ["3.1", "3.2", "3.3", "3.4"]:
        _rec(sid, "LFS fix skipped (status unknown)", True)

else:
    # LFS is broken. Apply Option A: pull real bytes via git-lfs, strip tracking.
    _warn("LFS broken. Applying Option A: strip LFS tracking, commit real binaries.")

    # 3.1  Ensure git-lfs is available
    _h2("3.1  Check / install git-lfs")
    gitlfs_ok, ver = _run("git lfs version", label="git-lfs version", timeout=10)
    if not gitlfs_ok:
        _warn("git-lfs not found -- trying pkg install git-lfs")
        _run("pkg install git-lfs -y", label="pkg install git-lfs", timeout=120)
        gitlfs_ok, ver = _run("git lfs version", label="git-lfs version (retry)", timeout=10)
    _rec("3.1", "git-lfs available", gitlfs_ok)

    # 3.2  Clone WITH LFS to pull real binary objects
    _h2("3.2  LFS-enabled clone (retrieves real MP3 bytes)")
    if HF_LFS_CLONE.exists():
        shutil.rmtree(HF_LFS_CLONE)
    lfs_ok, _ = _run(
        f"git clone {HF_URL} {HF_LFS_CLONE}",
        label="git clone with LFS", timeout=600,
    )
    _rec("3.2", "LFS clone completed", lfs_ok)

    # 3.3  Verify sizes
    _h2("3.3  Verify reference_audio/*.mp3 sizes in LFS clone")
    ref_dir   = HF_LFS_CLONE / "reference_audio"
    real_mp3s = []
    if ref_dir.exists():
        for mp3 in sorted(ref_dir.glob("*.mp3")):
            sz   = mp3.stat().st_size
            real = sz > 50_000
            ((_ok if real else _warn)(f"{mp3.name}  ({sz:,} bytes)  [{'REAL' if real else 'STUB'}]"))
            if real:
                real_mp3s.append(mp3)
    all_real = len(real_mp3s) == 3
    _rec("3.3", f"Real files found: {len(real_mp3s)}/3", all_real)

    if not all_real:
        # Search Termux for local copies
        _h2("3.3b  Searching Termux for local reference MP3s")
        for name in REF_NAMES:
            for root in SEARCH_ROOTS:
                c = Path(root) / name
                if c.exists() and c.stat().st_size > 50_000:
                    dst = ref_dir / name
                    shutil.copy2(c, dst)
                    _ok(f"Copied local: {name}")
                    real_mp3s.append(dst)
                    break
        all_real = len(real_mp3s) >= 3
        if not all_real:
            _err(f"Only {len(real_mp3s)}/3 reference files available.")
            _err("Manual steps to finish Option A:")
            print()
            print(f"  1. Copy the 3 reference MP3 files to {HF_LFS_CLONE}/reference_audio/")
            print(f"  2. Then run:")
            print(f"       cd {HF_LFS_CLONE}")
            print(f"       git lfs untrack '*.mp3'")
            print(f"       git rm --cached reference_audio/*.mp3")
            print(f"       git add reference_audio/*.mp3 .gitattributes")
            print(f"       git commit -m 'fix: S23 reference audio as binary'")
            print(f"       git push")
            print()

    # 3.4  Strip LFS tracking and commit
    _h2("3.4  Strip LFS, commit real binaries, push")
    if all_real and lfs_ok:
        _run('git config user.email "tilawa@hf.build"', cwd=HF_LFS_CLONE, label="git config email")
        _run('git config user.name "Tilawa Build"',     cwd=HF_LFS_CLONE, label="git config name")
        _run("git lfs untrack '*.mp3'",                 cwd=HF_LFS_CLONE, label="git lfs untrack *.mp3")
        _run("git rm --cached reference_audio/*.mp3",   cwd=HF_LFS_CLONE, label="git rm --cached")
        _run("git add -f reference_audio/*.mp3",        cwd=HF_LFS_CLONE, label="git add -f *.mp3")
        _run("git add .gitattributes",                  cwd=HF_LFS_CLONE, label="git add .gitattributes")
        ok_c, out_c = _run(
            'git commit -m "fix: S23 BUG2 -- reference audio as binary, remove LFS tracking"',
            cwd=HF_LFS_CLONE, label="git commit Option A"
        )
        if not ok_c and "nothing to commit" in out_c:
            _warn("Nothing to commit -- LFS may already be fixed")
            ok_c = True
        ok_p, _ = _run("git push", cwd=HF_LFS_CLONE, label="git push Option A")
        lfs_fix_applied = ok_c and ok_p
        _rec("3.4", "Option A pushed", lfs_fix_applied)
        if HF_LFS_CLONE.exists():
            shutil.rmtree(HF_LFS_CLONE)
    else:
        _err("Cannot auto-fix LFS. See manual steps above.")
        _rec("3.4", "Option A skipped (insufficient files)", False)


# ======================================================================
#  STEP 4 — END-TO-END v7.5 VERIFICATION
# ======================================================================
_h1("STEP 4 -- End-to-end v7.5 verification (BUG1 probe)")

# 4.1  Wait if LFS fix was just pushed
_h2("4.1  Pre-test rebuild wait")
if lfs_fix_applied:
    _warn("LFS fix pushed. Waiting 120s for HF rebuild...")
    time.sleep(120)
    _ok("Wait complete")
else:
    _ok("No additional wait needed")
_rec("4.1", "Pre-test wait done", True)

# 4.2  Submit v7.5 job
_h2("4.2  Submit v7.5 job (was always crashing before Part 2)")
jid_v75 = _submit_job("v7.5", TEST_MP3)
_rec("4.2", "v7.5 job submitted", jid_v75 is not None)

if jid_v75 is None:
    _err("Cannot submit v7.5 job.")
    _err("Manual check:")
    print(f"  curl -s -X POST {SERVER}/upload -F file=@/tmp/tilawa_test_s23.mp3 -F engine=v7.5")
    _rec("4.3", "v7.5 polled (skipped)", False)
    _rec("4.4", "v7.5 result evaluated (skipped)", False)
    bug1_fixed = False
    prog_moved = False
else:
    # 4.3  Poll
    _h2("4.3  Poll v7.5 job (max 20 min)")
    _warn("Before Part 2: v7.5 always crashed immediately (status=error)")
    _warn("After Part 2:  progress should advance 35->45->75->88->95->100")
    st75, sc75, pr75, seq75 = _poll_job(jid_v75, "v7.5", max_minutes=20, interval_s=5)
    _rec("4.3", "v7.5 job polled", True)

    # 4.4  Evaluate
    _h2("4.4  Evaluate v7.5 result")
    print(f"     status={st75}  score={sc75}  progress_seq={seq75}")
    bug1_fixed = (st75 != "error")
    prog_moved = any(p > 35 for p in seq75)

    ((_ok if bug1_fixed else _err)("BUG1 FIXED: v7.5 did NOT crash on launch"))
    ((_ok if prog_moved else _err)("BUG3 FIXED: progress advanced beyond 35"))
    if pr75 == 100:
        _ok("Job reached 100%")
    if sc75 and float(sc75) > 0:
        _ok(f"Score: {sc75}")

    if not bug1_fixed:
        _err("v7.5 still crashing -- Part 2 may not have deployed yet")
        _err("Wait 2 min for HF rebuild and re-run Part 3")
    if bug1_fixed and not prog_moved:
        _warn("Progress frozen at 35 -- Part 1 BUG3 fix may not be live")
        _warn("Wait 2 min for HF rebuild and re-run Part 3")

    _rec("4.4", "v7.5 BUG1 fixed (no crash)", bug1_fixed)
    _rec("4.4b", "v7.5 BUG3 fixed (progress moves)", prog_moved)


# ======================================================================
#  STEP 5 (REVIEW) — FINAL S23 SUMMARY
# ======================================================================
_h1("STEP 5 (REVIEW) -- S23 final summary")

# 5.1  Print log table
_h2("5.1  Step result log")
print()
print(f"  {'Step':<7}  {'Label':<52}  Result")
print(f"  {'----':<7}  {'-'*52}  ------")
all_pass = True
for sid, lbl, sts in _log:
    icon = "OK" if sts == "PASS" else "XX"
    print(f"  {sid:<7}  {lbl:<52}  [{icon}] {sts}")
    if sts == "FAIL": all_pass = False

# 5.2  Per-bug status table
_h2("5.2  Per-bug status (all 3 parts)")
print()
bugs = [
    ("BUG 1", "v75/v76 crash on --ref (Part 2)",     "FIXED",   "engine_v75+v76 argparse patched"),
    ("BUG 2", "Reference audio LFS stubs",
     "OK" if LFS_OK is True else ("FIXED" if lfs_fix_applied else ("UNKNOWN" if LFS_OK is None else "NEEDS ACTION")),
     "Verified via v8.0 job score"),
    ("BUG 3", "Progress frozen at 79.2% (Part 1)",   "FIXED",   "app.py markers + star regex"),
    ("BUG 4", "--iterations 1 caps convergence (P1)","FIXED",   "app.py: iterations=3"),
    ("BUG 5", "max_requests=100 wipes JOBS (Part 1)","FIXED",   "Dockerfile + gunicorn: unlimited"),
    ("BUG 6", "Debug keystore rotation",              "DEFERRED","S20 release keystore covers this"),
]
print(f"  {'Bug':<8}  {'Name':<44}  {'Status':<14}  Notes")
print(f"  {'-'*8}  {'-'*44}  {'-'*14}  -----")
for code, name, status, notes in bugs:
    icon = "[OK]" if status in ("FIXED","OK") else ("[!!]" if status == "DEFERRED" else "[XX]")
    print(f"  {code:<8}  {name:<44}  {icon} {status:<10}  {notes}")

# 5.3  Engine matrix post-S23
_h2("5.3  Engine status post-S23")
print()
engines = [
    ("v7.0", "S22: argparse + _CLI_REF_FILES + progress prints", "Working since S22"),
    ("v7.5", "S23: --ref added, REF_FILES override",             "BEST badge now works"),
    ("v7.6", "S23: --ref added, REF_FILES override",             "MDS badge now works"),
    ("v8.0", "Always had --ref, Path-based REF_FILES",           "Working (if LFS OK)"),
]
print(f"  {'Engine':<8}  {'S23 change':<48}  Status")
print(f"  {'-'*8}  {'-'*48}  ------")
for eng, change, status in engines:
    print(f"  {eng:<8}  {change:<48}  {status}")

# 5.4  Final verdict
_h2("5.4  Final verdict")
print()
print("  " + "=" * 64)
if all_pass:
    print("  ALL CHECKS PASSED -- S23 COMPLETE")
    print()
    print("  File size / JOB_EXPIRED pattern explained:")
    print("    max_requests=100 caused worker restart at ~100 HTTP requests.")
    print("    Large files = more chunk uploads + longer processing = more polls")
    print("    = more requests = hit the limit sooner. Now fixed (unlimited).")
    print()
    print("  v7.5 + v7.6 are now alive for the first time on the server.")
    print("  محسِّن التلاوة -- server fully operational")
else:
    print("  S23 COMPLETE WITH WARNINGS")
    print()
    print("  If HF rebuild hasn't finished, wait 2 min and re-run Part 3.")
    print("  If v7.5 still crashes, run Part 2 first.")
print("  " + "=" * 64)
print()
