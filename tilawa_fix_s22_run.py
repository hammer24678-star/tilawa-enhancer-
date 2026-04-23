#!/usr/bin/env python3
"""
tilawa_fix_s22_run.py  --  S22 Run Script (engine_v70.py already patched)
==========================================================================
Step 1 is replaced with verify-only.
Steps 2-6 are identical to tilawa_fix_s22_final.py.

PRECONDITION:
  engine_v70.py must already be in ~/tilawa-enhancer/  (put it there first)

Run from ~/tilawa-enhancer/:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s22_run.py
"""

import os, sys, shutil, subprocess, urllib.request
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

def _run(cmd, cwd=None, label=""):
    r = subprocess.run(cmd, shell=True, cwd=cwd,
                       capture_output=True, text=True, timeout=180)
    out = (r.stdout + r.stderr).strip()
    ok  = r.returncode == 0
    ((_ok if ok else _err)(label or cmd))
    if not ok and out:
        for line in out.splitlines()[-6:]:
            print(f"        {line}")
    return ok, out

# ── paths & credentials ──────────────────────────────────────────────────────
ENGINE_DEST = Path("engine_v70.py")
API         = Path("lib/services/api_service.dart")
HF_CLONE    = Path.home() / "tilawa-hf-clone"
HF_URL = (
    "https://carm5333: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"
    "@huggingface.co/spaces/carm5333/tilawa-server"
)
GH_TOKEN = "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"
HF_TOKEN = "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"


# ======================================================================
#  STEP 1  Verify engine_v70.py  (already patched -- no regeneration)
# ======================================================================
_h1("STEP 1 -- Verify engine_v70.py  (pre-patched, skip regeneration)")

_h2("1.1  File exists")
if not ENGINE_DEST.exists():
    _err("engine_v70.py not found in current directory.")
    _err("Copy it here first:  cp /sdcard/Download/engine_v70.py ~/tilawa-enhancer/")
    sys.exit(1)
_ok(f"Found: {ENGINE_DEST}  ({ENGINE_DEST.stat().st_size:,} bytes)")
_rec("1.1", "engine_v70.py present", True)

_h2("1.2  Spot-check patches")
ev = _read(ENGINE_DEST)
checks = [
    ("_CLI_REF_FILES = []" in ev,              "_CLI_REF_FILES global"),
    ("_CLI_REF_FILES if _CLI_REF_FILES" in ev, "REF_FILES conditional"),
    ("globals()['_CLI_REF_FILES']" in ev,      "CLI wired to global"),
    ("import argparse" in ev,                  "argparse import"),
    ("ap.add_argument('--ref'" in ev,          "--ref arg"),
    ("print('Pass 1" in ev,                    "Pass 1 print"),
    ("print('Pass 3" in ev,                    "Pass 3 print"),
    ("print(f'Score:" in ev,                   "Score: print"),
    ("print(f'LUFS=" in ev,                    "LUFS= print"),
    ("enhance_engine_v64" not in ev,           "old v64 ref removed"),
    ("/mnt/user-data/uploads/" in ev,          "Termux fallback paths preserved"),
]
r1all = True
for ok, label in checks:
    ((_ok if ok else _err)(label))
    if not ok: r1all = False
_rec("1.2", "engine_v70.py spot-checks", r1all)
if not r1all:
    _err("engine_v70.py is missing patches. Use the correct pre-patched file.")
    sys.exit(1)


# ======================================================================
#  STEP 2  api_service.dart -- verify or apply getStatus 404 fix
# ======================================================================
_h1("STEP 2 -- api_service.dart: getStatus 404 fix (BUG 2)")

_h2("2.1  Read api_service.dart")
if not API.exists():
    _err("api_service.dart not found")
    sys.exit(1)
api = _read(API)
_ok(f"Read {len(api):,} chars")
_rec("2.1", "Read OK", True)

_h2("2.2  Check if already patched")
already = (
    "res.statusCode == 404" in api and
    "JOB_EXPIRED" in api and
    "res.statusCode != 200" in api
)
if already:
    _ok("Already patched -- skipping")
    _rec("2.2", "Already patched (skip)", True)
else:
    _warn("Not patched yet -- applying")
    TS = datetime.now().strftime("%Y%m%d_%H%M%S")
    BD = Path(f".fix_backups/{TS}")
    BD.mkdir(parents=True, exist_ok=True)
    shutil.copy2(API, BD / "api_service.dart")
    _ok(f"Backup: {BD}/api_service.dart")
    OLD_ST = (
        "  static Future<Map<String, dynamic>> getStatus(String jobId) async {\n"
        "    final res = await http\n"
        "        .get(Uri.parse('$_base/status/$jobId'))\n"
        "        .timeout(const Duration(seconds: 10));\n"
        "    return jsonDecode(res.body);\n"
        "  }\n"
    )
    NEW_ST = (
        "  static Future<Map<String, dynamic>> getStatus(String jobId) async {\n"
        "    final res = await http\n"
        "        .get(Uri.parse('$_base/status/$jobId'))\n"
        "        .timeout(const Duration(seconds: 10));\n"
        "    // S22 BUG2: 404 = job gone (server restarted).\n"
        "    // Without this, Flutter parses the 404 body as a normal response,\n"
        "    // _pollErrors never increments, and the app freezes at 79%.\n"
        "    if (res.statusCode == 404) {\n"
        "      return {'status': 'error', 'error': 'JOB_EXPIRED'};\n"
        "    }\n"
        "    if (res.statusCode != 200) {\n"
        "      throw Exception('HTTP ${res.statusCode}');\n"
        "    }\n"
        "    return jsonDecode(res.body);\n"
        "  }\n"
    )
    api, aok = _replace_once(api, OLD_ST, NEW_ST, "getStatus")
    if aok:
        _write(API, api)
        _ok("Written")
    _rec("2.2", "Patch applied", aok)

_h2("2.3  Final verify")
api_v = _read(API)
ok_a = "res.statusCode == 404" in api_v
ok_b = "JOB_EXPIRED" in api_v
ok_c = "res.statusCode != 200" in api_v
for ok, lbl in [(ok_a,"404 check"),(ok_b,"JOB_EXPIRED"),(ok_c,"non-200 throw")]:
    ((_ok if ok else _err)(lbl))
_rec("2.3", "api_service.dart verified", ok_a and ok_b and ok_c)


# ======================================================================
#  STEP 3  Clone HF Space to ~/tilawa-hf-clone
# ======================================================================
_h1("STEP 3 -- Clone HF Space  (BUG 3: ~/tilawa-hf-clone not /tmp)")

_h2("3.1  Remove stale clone + fresh clone (skip LFS blobs)")
if HF_CLONE.exists():
    shutil.rmtree(HF_CLONE)
    _ok(f"Removed stale {HF_CLONE}")
ok31, _ = _run(
    f"GIT_LFS_SKIP_SMUDGE=1 git clone {HF_URL} {HF_CLONE}",
    label="git clone HF Space"
)
_rec("3.1", "HF Space cloned", ok31)
if not ok31:
    _err("Clone failed. Check network / HF token.")
    sys.exit(1)

_h2("3.2  Copy engine_v70.py into clone")
dest_engine = HF_CLONE / "engine_v70.py"
shutil.copy2(ENGINE_DEST, dest_engine)
_ok(f"Copied ({dest_engine.stat().st_size:,} bytes)")
_rec("3.2", "engine_v70.py in clone", True)

_h2("3.3  Read Dockerfile + locate timeout anchor")
DF = HF_CLONE / "Dockerfile"
if not DF.exists():
    _err("Dockerfile missing")
    sys.exit(1)
df = _read(DF)
_ok(f"Dockerfile: {len(df)} chars")

OLD_TO = '     "--timeout", "600", \\\n'
c_to = df.count(OLD_TO)
((_ok if c_to == 1 else _warn)(f"Primary anchor found {c_to}x"))
if c_to != 1:
    for alt in [
        '    "--timeout", "600", \\\n',
        '      "--timeout", "600", \\\n',
        '"--timeout", "600", \\\n',
    ]:
        if df.count(alt) == 1:
            _warn(f"Using alternate anchor: {repr(alt)}")
            OLD_TO = alt; c_to = 1; break
    if c_to != 1:
        _err("Timeout anchor not found. Dockerfile content:")
        for i, line in enumerate(df.splitlines(), 1):
            print(f"        {i:3}  {repr(line)}")
        sys.exit(1)
_rec("3.3", "Dockerfile anchor found", c_to == 1)

_h2("3.4  Patch timeout 600 -> 2400 + write")
NEW_TO = OLD_TO.replace('"600"', '"2400"')
df, dfok = _replace_once(df, OLD_TO, NEW_TO, "gunicorn timeout 600 -> 2400")
if dfok:
    _write(DF, df)
    _ok("Dockerfile written (--timeout 2400)")
_rec("3.4", "Dockerfile patched", dfok)

_h2("3.5  List clone files")
for f in sorted(HF_CLONE.iterdir()):
    if f.name.startswith('.'): continue
    tag = "F" if f.is_file() else "D"
    sz = f"  ({f.stat().st_size:,} bytes)" if f.is_file() else ""
    print(f"     [{tag}] {f.name}{sz}")
eng_ok = (HF_CLONE / "engine_v70.py").exists()
to_ok  = '"2400"' in _read(DF)
((_ok if eng_ok else _err)("engine_v70.py present"))
((_ok if to_ok  else _err)('Dockerfile has "2400"'))
_rec("3.5", "Clone contents verified", eng_ok and to_ok)


# ======================================================================
#  STEP 4  Commit + push to HuggingFace
# ======================================================================
_h1("STEP 4 -- Commit + push to HuggingFace")

_h2("4.1  Git identity")
_run('git config user.email "tilawa@hf.build"', cwd=HF_CLONE, label="git config email")
_run('git config user.name "Tilawa Build"',     cwd=HF_CLONE, label="git config name")
_rec("4.1", "Git identity", True)

_h2("4.2  Stage engine_v70.py + Dockerfile")
ok42a, _ = _run("git add engine_v70.py", cwd=HF_CLONE, label="git add engine_v70.py")
ok42b, _ = _run("git add Dockerfile",    cwd=HF_CLONE, label="git add Dockerfile")
_rec("4.2", "Staged", ok42a and ok42b)

_h2("4.3  Commit")
ok43, out43 = _run(
    'git commit -m "fix: S22 engine_v70.py (v7 multi-arch CLI) + gunicorn timeout 2400"',
    cwd=HF_CLONE, label="git commit"
)
if not ok43 and "nothing to commit" in out43:
    _warn("Nothing new (already pushed)")
    ok43 = True
_rec("4.3", "Committed", ok43)

_h2("4.4  Push to HuggingFace")
ok44, _ = _run("git push", cwd=HF_CLONE, label="git push HF")
_rec("4.4", "Pushed to HF", ok44)
if not ok44:
    _warn("Push failed -- manual fallback:")
    print(f"     cd {HF_CLONE} && git push")

_h2("4.5  Clean up clone")
try:
    shutil.rmtree(HF_CLONE)
    _ok(f"Removed {HF_CLONE}")
except Exception as e:
    _warn(f"Could not remove: {e}")
_rec("4.5", "Clone removed", True)


# ======================================================================
#  STEP 5  Push api_service.dart to GitHub
# ======================================================================
_h1("STEP 5 -- Push api_service.dart to GitHub")

_h2("5.1  Verify fix is present")
v5 = _read(API)
ok51 = "res.statusCode == 404" in v5 and "JOB_EXPIRED" in v5
((_ok if ok51 else _err)("S22 fix confirmed"))
_rec("5.1", "Fix present", ok51)

_h2("5.2  Stage")
ok52, _ = _run("git add lib/services/api_service.dart",
               label="git add api_service.dart")
_rec("5.2", "Staged", ok52)

_h2("5.3  Commit")
ok53, out53 = _run(
    'git commit -m "fix: S22 getStatus checks HTTP 404 -- ends 79% freeze on server restart"',
    label="git commit"
)
if not ok53 and "nothing to commit" in out53:
    _warn("Nothing new (already committed)")
    ok53 = True
_rec("5.3", "Committed", ok53)

_h2("5.4  Push to GitHub")
REMOTE = (
    f"https://c42742910-ops:{GH_TOKEN}"
    "@github.com/c42742910-ops/tilawa-enhancer.git"
)
ok54, _ = _run(f"git push {REMOTE} HEAD:master", label="git push GitHub")
_rec("5.4", "Pushed to GitHub", ok54)

_h2("5.5  Recent commits")
_run("git log --oneline -5", label="git log")
_rec("5.5", "Done", True)


# ======================================================================
#  STEP 6  Verify live HF files
# ======================================================================
_h1("STEP 6 -- Verify live HF files")

_h2("6.1  Check live Dockerfile timeout")
try:
    RAW = "https://huggingface.co/spaces/carm5333/tilawa-server/resolve/main/Dockerfile"
    req = urllib.request.Request(RAW,
          headers={"Authorization": f"Bearer {HF_TOKEN}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        df_live = r.read().decode()
    has_2400 = "2400" in df_live
    ((_ok if has_2400 else _warn)(
        f"Live Dockerfile: {'timeout 2400 OK' if has_2400 else 'still 600 (HF may be rebuilding)'}"))
    _rec("6.1", "Live Dockerfile timeout 2400", has_2400)
except Exception as e:
    _warn(f"Cannot fetch live Dockerfile ({e})")
    _rec("6.1", "Live Dockerfile checked", False)

_h2("6.2  Check live engine_v70.py")
try:
    RAW2 = "https://huggingface.co/spaces/carm5333/tilawa-server/resolve/main/engine_v70.py"
    req2 = urllib.request.Request(RAW2,
           headers={"Authorization": f"Bearer {HF_TOKEN}"})
    with urllib.request.urlopen(req2, timeout=15) as r2:
        head = r2.read(400).decode(errors="replace")
    has_it = any(s in head for s in ["_CLI_REF_FILES", "argparse", "enhance"])
    ((_ok if has_it else _warn)(
        f"Live engine_v70.py: {'exists, v7 arch OK' if has_it else 'exists (content not in first 400 bytes)'}"))
    _rec("6.2", "Live engine_v70.py exists", True)
except Exception as e:
    _warn(f"engine_v70.py not visible yet ({e})")
    _warn("Normal -- HF rebuilds ~2 min after push")
    _rec("6.2", "Live engine_v70.py checked", False)


# ======================================================================
#  FINAL SUMMARY
# ======================================================================
_h1("FINAL SUMMARY")
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
    print("  ALL CHECKS PASSED")
    print()
    print("  HF Space rebuilds ~2 min after push.")
    print("  GitHub Actions APK builds ~4 min.")
    print()
    print("  VERIFICATION:")
    print("  1. Install new APK from GitHub Actions Artifacts")
    print("  2. Open app -> wake server -> green banner")
    print("  3. Upload file -> v7.0 engine -> expect score >= 91")
    print("  4. Upload file -> v8.0 engine -> expect score >= 96")
    print("  5. Start job -> kill app at 79% -> reopen -> NOT frozen")
    print("  " + "=" * 64)
else:
    print("  " + "=" * 64)
    print("  SOME CHECKS FAILED -- review above")
    print("  " + "=" * 64)
    sys.exit(1)
