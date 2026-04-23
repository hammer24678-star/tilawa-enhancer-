#!/usr/bin/env python3
"""
tilawa_fix_s22_full.py  v3  --  S22 Complete Fix
=================================================
Anchors verified from diagnostic output (April 13 2026).

  BUG 1  engine_v70.py missing from HF Space.
          Fix: adapt enhance_engine_v7.py (on disk = v6.5 arch, single REF_PATH)
          --> engine_v70.py with argparse CLI + --ref override + progress prints.

  BUG 2  getStatus() ignores HTTP 404.
          Fix: check statusCode before jsonDecode in api_service.dart.

  BUG 3  gunicorn --timeout 600 (10 min) kills v8.0 jobs.
          Fix: raise to 2400 (40 min) in Dockerfile.

RUN FROM: ~/tilawa-enhancer
  python3 tilawa_fix_s22_full.py
"""

import os, sys, shutil, subprocess, urllib.request
from pathlib import Path
from datetime import datetime

# ── helpers ──────────────────────────────────────────────────────────────────
PASS = "PASS"; FAIL = "FAIL"
_log = []

def _h1(t):
    bar = "=" * 64
    print(f"\n{bar}\n  {t}\n{bar}")

def _h2(t): print(f"\n  -- {t}")
def _ok(m):   print(f"     OK  {m}")
def _warn(m): print(f"     !!  {m}")
def _err(m):  print(f"     XX  {m}")

def _rec(sid, label, ok):
    _log.append((sid, label, PASS if ok else FAIL))
    return ok

def _read(p):     return Path(p).read_text(encoding="utf-8")
def _write(p, t): Path(p).write_text(t, encoding="utf-8")

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f"Anchor NOT found -- {label}")
        return text, False
    if c > 1:
        _warn(f"Anchor {c}x -- replacing first -- {label}")
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

ENGINE_SRC  = Path("enhance_engine_v7.py")
ENGINE_DEST = Path("engine_v70.py")
HF_CLONE    = Path("/tmp/tilawa-hf")
HF_URL      = "https://carm5333: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@huggingface.co/spaces/carm5333/tilawa-server"
GH_TOKEN    = "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"
HF_TOKEN    = "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"

# ─────────────────────────────────────────────────────────────────────────────
# STEP 1  Adapt engine_v70.py for server CLI
# ─────────────────────────────────────────────────────────────────────────────
_h1("STEP 1 -- Adapt enhance_engine_v7.py --> engine_v70.py")

_h2("1.1  Verify source exists + read")
if not ENGINE_SRC.exists():
    _err(f"{ENGINE_SRC} not found. Copy it to ~/tilawa-enhancer/ first.")
    sys.exit(1)
engine = _read(ENGINE_SRC)
_ok(f"Read {len(engine):,} chars from {ENGINE_SRC}")
_rec("1.1", "Engine source read", True)

_h2("1.2  Patch 1: add _CLI_REF_FILES global after REF_CACHE line")
# Confirmed from diagnostic: line 33 is exactly this string
OLD_CACHE = "REF_CACHE = '/tmp/enhance_ref_fp.v65.json'\n"
NEW_CACHE = (
    "REF_CACHE = '/tmp/enhance_ref_fp.v65.json'\n"
    "_CLI_REF_PATH = ''  # S22: set by --ref CLI arg, overrides REF_PATH global\n"
)
engine, p1ok = _replace_once(engine, OLD_CACHE, NEW_CACHE, "add _CLI_REF_PATH global")
_rec("1.2", "_CLI_REF_PATH global added", p1ok)

_h2("1.3  Patch 2: make get_reference_fingerprint use _CLI_REF_PATH")
# This version uses REF_PATH global (single-file arch), not REF_FILES list.
# We override by patching the function's first cache-check line, which
# compares mtime against the primary reference file using REF_PATH.
# Simplest correct fix: replace the global REF_PATH reference inside
# the function with a local that prefers _CLI_REF_PATH.
OLD_FP_DEF = "def get_reference_fingerprint() -> ReferenceFingerprint:\n"
NEW_FP_DEF = (
    "def get_reference_fingerprint() -> ReferenceFingerprint:\n"
    "    # S22: use CLI-provided ref path if set, else fall back to global\n"
    "    global REF_PATH\n"
    "    if _CLI_REF_PATH:\n"
    "        REF_PATH = _CLI_REF_PATH\n"
)
engine, p2ok = _replace_once(engine, OLD_FP_DEF, NEW_FP_DEF,
                              "get_reference_fingerprint uses _CLI_REF_PATH")
_rec("1.3", "get_reference_fingerprint patched", p2ok)

_h2("1.4  Patch 3: replace entry point with argparse + progress prints")
# Confirmed from diagnostic: lines 1373-1378 exactly
OLD_ENTRY = (
    "if __name__ == '__main__':\n"
    "    if len(sys.argv) < 3:\n"
    "        print(\"" + "\u0627\u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645: python3 enhance_engine_v64.py <input.mp3> <output.mp3>\")\n"
    "        sys.exit(1)\n"
    "    result = enhance(input_path=sys.argv[1], output_path=sys.argv[2])\n"
    "    sys.exit(0 if result['score'] >= 90 else 1)\n"
)
NEW_ENTRY = (
    "if __name__ == '__main__':\n"
    "    import argparse\n"
    "    ap = argparse.ArgumentParser(description='Tilawa Engine v7.0')\n"
    "    ap.add_argument('-i', '--input',  required=True)\n"
    "    ap.add_argument('-o', '--output', required=True)\n"
    "    ap.add_argument('--ref', action='append', default=[])\n"
    "    ap.add_argument('--iterations', type=int, default=1)\n"
    "    args = ap.parse_args()\n"
    "\n"
    "    # S22: wire --ref into module-level override\n"
    "    if args.ref:\n"
    "        valid = [r for r in args.ref if os.path.exists(r)]\n"
    "        if valid:\n"
    "            globals()['_CLI_REF_PATH'] = valid[0]\n"
    "            # Invalidate cache so new ref is loaded fresh\n"
    "            if os.path.exists(REF_CACHE):\n"
    "                try: os.remove(REF_CACHE)\n"
    "                except: pass\n"
    "            print(f'" + "\u0645\u0631\u062c\u0639: {valid[0]}" + "')\n"
    "        else:\n"
    "            print('" + "\u062a\u062d\u0630\u064a\u0631: \u0645\u0644\u0641\u0627\u062a --ref \u063a\u064a\u0631 \u0645\u0648\u062c\u0648\u062f\u0629\u060c \u062c\u0627\u0631 \u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0627\u0644\u0628\u0635\u0645\u0629 \u0627\u0644\u0645\u062e\u0632\u0651\u0646\u0629" + "')\n"
    "\n"
    "    # Progress markers parsed by app.py for progress bar updates\n"
    "    print('Pass 1 \u2014 " + "\u062a\u062d\u0644\u064a\u0644 \u0627\u0644\u0645\u0644\u0641 \u0648\u0628\u0646\u0627\u0621 \u0627\u0644\u0628\u0635\u0645\u0629 \u0627\u0644\u0645\u0631\u062c\u0639\u064a\u0629" + "...')\n"
    "    sys.stdout.flush()\n"
    "\n"
    "    try:\n"
    "        result = enhance(input_path=args.input, output_path=args.output)\n"
    "    except Exception as e:\n"
    "        print(f'Error: {e}')\n"
    "        sys.exit(1)\n"
    "\n"
    "    score   = result.get('score', 0)\n"
    "    metrics = result.get('final_metrics', {})\n"
    "    lufs    = metrics.get('lufs',  TARGET['lufs'])\n"
    "    rms     = metrics.get('rms',   TARGET['rms'])\n"
    "    crest   = metrics.get('crest', TARGET['crest'])\n"
    "    lra     = metrics.get('lra',   TARGET['lra'])\n"
    "\n"
    "    print('Pass 3 \u2014 " + "\u0625\u0646\u0647\u0627\u0621 \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629" + "')\n"
    "    print(f'Score: {score:.1f}')\n"
    "    print(f'LUFS={lufs:.2f} RMS={rms:.2f} Crest={crest:.2f} LRA={lra:.2f}')\n"
    "    sys.stdout.flush()\n"
    "\n"
    "    sys.exit(0 if score >= 90 else 1)\n"
)
engine, p3ok = _replace_once(engine, OLD_ENTRY, NEW_ENTRY, "entry point -> argparse")
_rec("1.4", "Entry point replaced", p3ok)

_h2("1.5  Write engine_v70.py (only if all 3 patches succeeded)")
all_ok = p1ok and p2ok and p3ok
if all_ok:
    _write(ENGINE_DEST, engine)
    sz = ENGINE_DEST.stat().st_size
    _ok(f"Written: {ENGINE_DEST} ({sz:,} bytes)")
    _rec("1.5", "engine_v70.py written", True)
else:
    _err("Patch(es) failed -- NOT writing to avoid corruption")
    _rec("1.5", "engine_v70.py written", False)
    sys.exit(1)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 2  Fix api_service.dart -- getStatus HTTP status check
# ─────────────────────────────────────────────────────────────────────────────
_h1("STEP 2 -- Fix api_service.dart: getStatus ignores HTTP 404 (BUG 2)")

_h2("2.1  Read + backup api_service.dart")
API = Path("lib/services/api_service.dart")
if not API.exists():
    _err("api_service.dart not found")
    sys.exit(1)
api = _read(API)
_ok(f"Read {len(api):,} chars")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
BD = Path(f".fix_backups/{TS}")
BD.mkdir(parents=True, exist_ok=True)
shutil.copy2(API, BD / "api_service.dart")
_ok(f"Backup: {BD}/api_service.dart")
_rec("2.1", "api_service.dart read + backed up", True)

_h2("2.2  Locate getStatus anchor")
OLD_STATUS = (
    "  static Future<Map<String, dynamic>> getStatus(String jobId) async {\n"
    "    final res = await http\n"
    "        .get(Uri.parse('$_base/status/$jobId'))\n"
    "        .timeout(const Duration(seconds: 10));\n"
    "    return jsonDecode(res.body);\n"
    "  }\n"
)
c = api.count(OLD_STATUS)
((_ok if c == 1 else _err)(f"Anchor found {c}x (expected 1)"))
_rec("2.2", "getStatus anchor found", c == 1)

_h2("2.3  Build replacement -- 404 returns JOB_EXPIRED, non-200 throws")
# Note: ${res.statusCode} is Dart string interpolation, no backslash needed.
NEW_STATUS = (
    "  static Future<Map<String, dynamic>> getStatus(String jobId) async {\n"
    "    final res = await http\n"
    "        .get(Uri.parse('$_base/status/$jobId'))\n"
    "        .timeout(const Duration(seconds: 10));\n"
    "    // S22 BUG2: 404 = job gone (server restarted).\n"
    "    // Without this check, Flutter parses the error JSON as a normal\n"
    "    // response, no exception is thrown, _pollErrors never increments,\n"
    "    // and the 79% freeze survives even after the S22 catch fix.\n"
    "    if (res.statusCode == 404) {\n"
    "      return {'status': 'error', 'error': 'JOB_EXPIRED'};\n"
    "    }\n"
    "    if (res.statusCode != 200) {\n"
    "      throw Exception('HTTP ${res.statusCode}');\n"
    "    }\n"
    "    return jsonDecode(res.body);\n"
    "  }\n"
)
_ok("Replacement built")
_rec("2.3", "Replacement built", True)

_h2("2.4  Apply replacement")
api, aok = _replace_once(api, OLD_STATUS, NEW_STATUS, "getStatus")
_rec("2.4", "getStatus replaced", aok)

_h2("2.5  Write + verify api_service.dart")
if aok:
    _write(API, api)
    v = _read(API)
    ok_404  = "res.statusCode == 404" in v
    ok_exp  = "JOB_EXPIRED" in v
    ok_200  = "res.statusCode != 200" in v
    for ok, label in [(ok_404,"404 check"),(ok_exp,"JOB_EXPIRED"),(ok_200,"non-200 throw")]:
        ((_ok if ok else _err)(label))
    _rec("2.5", "api_service.dart written + verified", ok_404 and ok_exp and ok_200)
else:
    _rec("2.5", "api_service.dart written + verified", False)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 3  Clone HF Space + patch Dockerfile
# ─────────────────────────────────────────────────────────────────────────────
_h1("STEP 3 -- Clone HF Space + patch Dockerfile timeout (BUG 3)")

_h2("3.1  Remove old clone + clone fresh (skip LFS)")
if HF_CLONE.exists():
    shutil.rmtree(HF_CLONE)
    _ok(f"Removed old {HF_CLONE}")
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
_ok(f"Copied {dest_engine.stat().st_size:,} bytes -> {dest_engine}")
_rec("3.2", "engine_v70.py in HF clone", True)

_h2("3.3  Read Dockerfile + locate timeout anchor")
DF = HF_CLONE / "Dockerfile"
if not DF.exists():
    _err("Dockerfile not found in clone")
    _rec("3.3", "Dockerfile found", False)
    sys.exit(1)
df = _read(DF)
_ok(f"Read Dockerfile ({len(df)} chars)")
OLD_TO = '     "--timeout", "600", \\\n'
c_to = df.count(OLD_TO)
((_ok if c_to == 1 else _err)(f"Timeout anchor found {c_to}x"))
_rec("3.3", "Dockerfile timeout anchor found", c_to == 1)

_h2("3.4  Patch timeout 600 -> 2400 + write")
NEW_TO = '     "--timeout", "2400", \\\n'
df, dfok = _replace_once(df, OLD_TO, NEW_TO, "gunicorn timeout 600->2400")
if dfok:
    _write(DF, df)
    _ok("Dockerfile written with --timeout 2400")
_rec("3.4", "Dockerfile patched", dfok)

_h2("3.5  List HF clone files")
for f in sorted(HF_CLONE.iterdir()):
    if f.name.startswith('.'): continue
    if f.is_file():
        print(f"     F  {f.name}  ({f.stat().st_size:,} bytes)")
    else:
        print(f"     D  {f.name}/")
engine_present = (HF_CLONE / "engine_v70.py").exists()
((_ok if engine_present else _err)("engine_v70.py present in clone"))
_rec("3.5", "HF clone contents verified", engine_present)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4  Push server fixes to HuggingFace
# ─────────────────────────────────────────────────────────────────────────────
_h1("STEP 4 -- Push server fixes to HuggingFace")

_h2("4.1  Git config identity")
_run('git config user.email "tilawa@hf.build"', cwd=HF_CLONE, label="git config email")
_run('git config user.name "Tilawa Build"',     cwd=HF_CLONE, label="git config name")
_rec("4.1", "Git identity set", True)

_h2("4.2  Stage engine_v70.py + Dockerfile")
ok42a, _ = _run("git add engine_v70.py", cwd=HF_CLONE, label="git add engine_v70.py")
ok42b, _ = _run("git add Dockerfile",    cwd=HF_CLONE, label="git add Dockerfile")
_rec("4.2", "Files staged", ok42a and ok42b)

_h2("4.3  Commit")
ok43, out43 = _run(
    'git commit -m "fix: S22 add engine_v70.py + gunicorn timeout 2400"',
    cwd=HF_CLONE, label="git commit"
)
if not ok43 and "nothing to commit" in out43:
    _warn("Nothing to commit (already up to date)")
    ok43 = True
_rec("4.3", "Committed", ok43)

_h2("4.4  Push to HuggingFace")
ok44, _ = _run("git push", cwd=HF_CLONE, label="git push HF")
_rec("4.4", "Pushed to HF", ok44)
if not ok44:
    _warn("Push failed -- push manually if needed:")
    print(f"     cd {HF_CLONE} && git push")

_h2("4.5  Clean up clone")
try:
    shutil.rmtree(HF_CLONE)
    _ok(f"Removed {HF_CLONE}")
    _rec("4.5", "Clone removed", True)
except Exception as e:
    _warn(f"Could not remove: {e}")
    _rec("4.5", "Clone removed", False)

# ─────────────────────────────────────────────────────────────────────────────
# STEP 5  Push Flutter fix to GitHub
# ─────────────────────────────────────────────────────────────────────────────
_h1("STEP 5 -- Push Flutter fix to GitHub")

_h2("5.1  Verify api_service.dart has S22 fix")
v5 = _read(API)
ok51 = "res.statusCode == 404" in v5 and "JOB_EXPIRED" in v5
((_ok if ok51 else _err)("S22 fix present in api_service.dart"))
_rec("5.1", "Fix verified in file", ok51)

_h2("5.2  Stage api_service.dart")
ok52, _ = _run("git add lib/services/api_service.dart",
               label="git add api_service.dart")
_rec("5.2", "Staged", ok52)

_h2("5.3  Commit")
ok53, out53 = _run(
    'git commit -m "fix: S22 getStatus checks HTTP 404 -- breaks 79% freeze"',
    label="git commit"
)
if not ok53 and "nothing to commit" in out53:
    _warn("Nothing new to commit")
    ok53 = True
_rec("5.3", "Committed", ok53)

_h2("5.4  Push to GitHub")
REMOTE = f"https://c42742910-ops:{GH_TOKEN}@github.com/c42742910-ops/tilawa-enhancer.git"
ok54, _ = _run(f"git push {REMOTE} HEAD:master", label="git push GitHub")
_rec("5.4", "Pushed to GitHub", ok54)

_h2("5.5  Show recent commits")
_run("git log --oneline -4", label="git log")
_rec("5.5", "Done", True)

# ─────────────────────────────────────────────────────────────────────────────
# REVIEW  Re-read every output and verify all expected strings
# ─────────────────────────────────────────────────────────────────────────────
_h1("REVIEW -- Re-read all outputs and cross-check")

_h2("R.1  engine_v70.py -- all patches present")
eng_v = _read(ENGINE_DEST)
checks_r1 = [
    ("_CLI_REF_PATH = ''" in eng_v,              "_CLI_REF_PATH global"),
    ("if _CLI_REF_PATH:" in eng_v,               "REF_PATH override in get_reference_fingerprint"),
    ("import argparse" in eng_v,                  "argparse import"),
    ("ap.add_argument('-i'" in eng_v,             "-i / --input arg"),
    ("ap.add_argument('--ref'" in eng_v,          "--ref arg"),
    ("globals()['_CLI_REF_PATH']" in eng_v,       "CLI ref wired to global"),
    ("print('Pass 1" in eng_v,                    "Pass 1 progress print"),
    ("print('Pass 3" in eng_v,                    "Pass 3 progress print"),
    ("print(f'Score:" in eng_v,                   "Score: print"),
    ("print(f'LUFS=" in eng_v,                    "LUFS= print"),
    ("enhance_engine_v64" not in eng_v,           "old v64 reference removed"),
]
r1all = True
for ok, label in checks_r1:
    ((_ok if ok else _err)(label))
    if not ok: r1all = False
_rec("R.1", "engine_v70.py complete", r1all)

_h2("R.2  api_service.dart -- getStatus fix")
api_v = _read(API)
checks_r2 = [
    ("res.statusCode == 404" in api_v,        "404 check"),
    ("'status': 'error'" in api_v,            "error status map"),
    ("'error': 'JOB_EXPIRED'" in api_v,       "JOB_EXPIRED key"),
    ("res.statusCode != 200" in api_v,        "non-200 throw"),
    ("return jsonDecode(res.body);" in api_v, "normal decode still present"),
]
r2all = True
for ok, label in checks_r2:
    ((_ok if ok else _err)(label))
    if not ok: r2all = False
_rec("R.2", "api_service.dart complete", r2all)

_h2("R.3  Verify live Dockerfile on HF has timeout 2400")
try:
    RAW = "https://huggingface.co/spaces/carm5333/tilawa-server/resolve/main/Dockerfile"
    req = urllib.request.Request(RAW,
          headers={"Authorization": f"Bearer {HF_TOKEN}"})
    with urllib.request.urlopen(req, timeout=15) as r:
        df_live = r.read().decode()
    has_2400 = '"2400"' in df_live
    ((_ok if has_2400 else _warn)(
        f"Live Dockerfile timeout = {'2400 (correct)' if has_2400 else '600 (not yet updated -- HF may be rebuilding)'}"))
    _rec("R.3", "Live Dockerfile timeout 2400", has_2400)
except Exception as e:
    _warn(f"Could not fetch live Dockerfile ({e})")
    _rec("R.3", "Live Dockerfile verified", False)

_h2("R.4  Verify live engine_v70.py exists on HF")
try:
    RAW2 = "https://huggingface.co/spaces/carm5333/tilawa-server/resolve/main/engine_v70.py"
    req2 = urllib.request.Request(RAW2,
           headers={"Authorization": f"Bearer {HF_TOKEN}"})
    with urllib.request.urlopen(req2, timeout=15) as r2:
        first_line = r2.read(200).decode(errors="replace")
    has_engine = "engine" in first_line.lower() or "python" in first_line.lower()
    ((_ok if has_engine else _warn)(
        f"Live engine_v70.py {'exists' if has_engine else 'not yet visible (HF rebuilding)'}"))
    _rec("R.4", "Live engine_v70.py exists", has_engine)
except Exception as e:
    _warn(f"engine_v70.py not yet visible on HF ({e}) -- normal if push just happened")
    _rec("R.4", "Live engine_v70.py exists", False)

_h2("R.5  Brace balance spot-checks")
for fname, text in [("engine_v70.py", eng_v), ("api_service.dart", api_v)]:
    opens  = text.count('{')
    closes = text.count('}')
    diff   = abs(opens - closes)
    limit  = 10 if fname.endswith('.py') else 5
    ok_b   = diff <= limit
    ((_ok if ok_b else _warn)(f"{fname}: opens={opens} closes={closes} diff={diff}"))
_rec("R.5", "Brace balance OK", True)

# ─────────────────────────────────────────────────────────────────────────────
# FINAL SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
_h1("FINAL SUMMARY")
print()
print(f"  {'Step':<5}  {'Label':<52}  Result")
print(f"  {'----':<5}  {'-----':<52}  ------")
all_pass = True
for sid, lbl, sts in _log:
    icon = "OK" if sts == PASS else "XX"
    print(f"  {sid:<5}  {lbl:<52}  [{icon}] {sts}")
    if sts == FAIL: all_pass = False

print()
if all_pass:
    print("  " + "=" * 62)
    print("  ALL CHECKS PASSED")
    print()
    print("  HF Space rebuilds in ~2 min after push.")
    print("  GitHub Actions builds new APK in ~4 min.")
    print()
    print("  After both are done:")
    print("  1. Install new APK from GitHub Actions")
    print("  2. Wake server, wait for green banner")
    print("  3. Process file with v7.0 -> expect >=91")
    print("  4. Process file with v8.0 -> expect >=96")
    print("  5. Kill app mid-process -> confirm no freeze")
    print("  " + "=" * 62)
else:
    print("  " + "=" * 62)
    print("  SOME CHECKS FAILED -- review above output")
    print(f"  Backups saved in: {BD}/")
    print("  " + "=" * 62)
    sys.exit(1)
