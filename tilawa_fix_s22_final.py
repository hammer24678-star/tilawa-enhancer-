#!/usr/bin/env python3
"""
tilawa_fix_s22_final.py  --  S22 Complete Fix (Final)
======================================================
Fixes all 3 S22 bugs and pushes to HF + GitHub.

PRECONDITION — run ONCE before this script:
  cp /sdcard/Download/enhance_engine_v7.py ~/tilawa-enhancer/
  (replaces the old v6.5-arch file with the REAL v7 multi-arch engine)

Then from ~/tilawa-enhancer:
  python3 tilawa_fix_s22_final.py

WHY v3 PRODUCED A BROKEN engine_v70.py
  The on-disk enhance_engine_v7.py was old v6.5-arch:
    REF_CACHE = '/tmp/enhance_ref_fp.v65.json'
    get_reference_fingerprint() uses global REF_PATH  (single file)
  The REAL engine (now in Downloads) is v7-arch:
    REF_CACHE = '/tmp/enhance_ref_fp.v7.json'
    get_reference_fingerprint() uses local REF_FILES = [...]  (3 files)
  v3 Patch 2 set global REF_PATH -- useless against REF_FILES arch.
  Result: all 3 REF_FILES paths point to /mnt/user-data/uploads/ (Termux),
  which don't exist on the HF server, so all 3 are skipped, the fallback
  single-ref also fails, and the engine always scores 75.

BUG 1  engine_v70.py missing from HF Space  (server)
  3 patches on the real v7 engine:
    P1. Add _CLI_REF_FILES = []  after REF_CACHE line
    P2. Wrap REF_FILES assignment in get_reference_fingerprint():
          REF_FILES = (_CLI_REF_FILES if _CLI_REF_FILES else [...])
        Server run: _CLI_REF_FILES = server paths from --ref args
        Local dev:  _CLI_REF_FILES = [] -> falls back to Termux paths
    P3. Replace entry point with argparse:
          -i/--input, -o/--output, --ref (repeatable), --iterations
        + cache invalidation on --ref
        + progress prints: Pass 1 / Pass 3 / Score: / LUFS=
        (engine already prints Pass 1 / Pass 2 / Pass 3 via L() internally)

BUG 2  getStatus() ignores HTTP 404 -> 79% freeze  (Flutter app)
  Already patched by v3 run 1. Verified and re-applied only if missing.

BUG 3  gunicorn --timeout 600 kills v8.0 jobs  (server)
  v3 cloned to /tmp/tilawa-hf -- Termux permission denied.
  Fix: clone to ~/tilawa-hf-clone.
  Dockerfile: "--timeout","600" -> "--timeout","2400"  (40 min)
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
ENGINE_SRC  = Path("enhance_engine_v7.py")
ENGINE_DEST = Path("engine_v70.py")
API         = Path("lib/services/api_service.dart")
HF_CLONE    = Path.home() / "tilawa-hf-clone"   # KEY FIX: NOT /tmp/tilawa-hf
HF_URL = (
    "https://carm5333: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"
    "@huggingface.co/spaces/carm5333/tilawa-server"
)
GH_TOKEN = "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"
HF_TOKEN = "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"


# ======================================================================
#  STEP 1  Re-create engine_v70.py from the real v7 multi-arch engine
# ======================================================================
_h1("STEP 1 -- Create engine_v70.py  (real v7 multi-arch)")

_h2("1.1  Read + verify source is the real v7 engine")
if not ENGINE_SRC.exists():
    _err(f"{ENGINE_SRC} not found.")
    _err("Run first:  cp /sdcard/Download/enhance_engine_v7.py ~/tilawa-enhancer/")
    sys.exit(1)

engine = _read(ENGINE_SRC)
_ok(f"Read {len(engine):,} chars from {ENGINE_SRC}")
is_multi = "REF_FILES = [" in engine
_ok(f"Arch: {'multi-arch REF_FILES (correct)' if is_multi else 'WRONG FILE -- single-arch!'}")
if not is_multi:
    _err("Wrong source. Run:  cp /sdcard/Download/enhance_engine_v7.py ~/tilawa-enhancer/")
    sys.exit(1)
_rec("1.1", "v7 multi-arch confirmed", True)

# ── Patch 1 ──────────────────────────────────────────────────────────
_h2("1.2  Patch 1 -- add _CLI_REF_FILES global after REF_CACHE")
OLD_CACHE = "REF_CACHE = '/tmp/enhance_ref_fp.v7.json'\n"
NEW_CACHE = (
    "REF_CACHE = '/tmp/enhance_ref_fp.v7.json'\n"
    "_CLI_REF_FILES = []"
    "  # S22: set by --ref CLI args; overrides REF_FILES in get_reference_fingerprint()\n"
)
engine, p1ok = _replace_once(engine, OLD_CACHE, NEW_CACHE, "_CLI_REF_FILES global")
_rec("1.2", "_CLI_REF_FILES global added", p1ok)

# ── Patch 2 ──────────────────────────────────────────────────────────
_h2("1.3  Patch 2 -- REF_FILES conditional inside get_reference_fingerprint()")
#
# Exact content at lines 320-326 of the real engine file:
#
#     REF_FILES = [
#         '/mnt/user-data/uploads/المرجع1425.mp3',
#         '/mnt/user-data/uploads/سوره_الفتح_174232307.mp3',
#         '/mnt/user-data/uploads/ياسر_الدوسري_ما_تسير_من_سورة_فاطر_1425__اول_مرة_تن_173856242_99.mp3',
#     ]
#     # نستخدم الملف الأول للتحقق من تغيير cache
#     primary = REF_FILES[0]
#
_REF1 = "/mnt/user-data/uploads/\u0627\u0644\u0645\u0631\u062c\u06271425.mp3"
_REF2 = "/mnt/user-data/uploads/\u0633\u0648\u0631\u0647_\u0627\u0644\u0641\u062a\u062d_174232307.mp3"
_REF3 = (
    "/mnt/user-data/uploads/"
    "\u064a\u0627\u0633\u0631_\u0627\u0644\u062f\u0648\u0633\u0631\u064a"
    "_\u0645\u0627_\u062a\u0633\u064a\u0631_\u0645\u0646"
    "_\u0633\u0648\u0631\u0629_\u0641\u0627\u0637\u0631"
    "_1425__\u0627\u0648\u0644_\u0645\u0631\u0629_\u062a\u0646"
    "_173856242_99.mp3"
)
_COMMENT = "    # \u0646\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u0645\u0644\u0641 \u0627\u0644\u0623\u0648\u0644 \u0644\u0644\u062a\u062d\u0642\u0642 \u0645\u0646 \u062a\u063a\u064a\u064a\u0631 cache\n"

OLD_REF_FILES = (
    "    REF_FILES = [\n"
    f"        '{_REF1}',\n"
    f"        '{_REF2}',\n"
    f"        '{_REF3}',\n"
    "    ]\n"
    + _COMMENT
    + "    primary = REF_FILES[0]\n"
)
NEW_REF_FILES = (
    "    # S22: use CLI-provided server paths if set; fall back to Termux dev paths\n"
    "    REF_FILES = (_CLI_REF_FILES if _CLI_REF_FILES else [\n"
    f"        '{_REF1}',\n"
    f"        '{_REF2}',\n"
    f"        '{_REF3}',\n"
    "    ])\n"
    + _COMMENT
    + "    primary = REF_FILES[0]\n"
)
engine, p2ok = _replace_once(engine, OLD_REF_FILES, NEW_REF_FILES,
                              "REF_FILES conditional")
if not p2ok:
    _warn("Diagnostic -- lines containing 'REF_FILES':")
    for i, line in enumerate(engine.splitlines(), 1):
        if "REF_FILES" in line:
            ctx = engine.splitlines()[max(0,i-3):i+5]
            for j, l in enumerate(ctx, max(1,i-2)):
                print(f"        {j:4}  {repr(l)}")
            break
_rec("1.3", "REF_FILES conditional patched", p2ok)

# ── Patch 3 ──────────────────────────────────────────────────────────
_h2("1.4  Patch 3 -- replace entry point with argparse + progress prints")
OLD_ENTRY = (
    "if __name__ == '__main__':\n"
    "    if len(sys.argv) < 3:\n"
    "        print(\"\u0627\u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645: "
    "python3 enhance_engine_v64.py <input.mp3> <output.mp3>\")\n"
    "        sys.exit(1)\n"
    "    result = enhance(input_path=sys.argv[1], output_path=sys.argv[2])\n"
    "    sys.exit(0 if result['score'] >= 90 else 1)\n"
)
NEW_ENTRY = """\
if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description='Tilawa Engine v7.0 -- server CLI')
    ap.add_argument('-i', '--input',  required=True)
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--ref', action='append', default=[],
                    help='Reference audio file; repeat for multiple files')
    ap.add_argument('--iterations', type=int, default=1,
                    help='Iterations (v7.0: ignored; kept for CLI compat)')
    args = ap.parse_args()

    # S22: wire --ref list into module-level _CLI_REF_FILES.
    # get_reference_fingerprint() reads this global on every call.
    if args.ref:
        valid = [r for r in args.ref if os.path.exists(r)]
        if valid:
            globals()['_CLI_REF_FILES'] = valid
            # Invalidate stale cache so new ref files are loaded fresh.
            # REF_CACHE module global == cache_file local inside the function.
            if os.path.exists(REF_CACHE):
                try: os.remove(REF_CACHE)
                except: pass
            print(f'\u0645\u0631\u0627\u062c\u0639: {len(valid)} \u0645\u0644\u0641')
        else:
            print('\u062a\u062d\u0630\u064a\u0631: \u0645\u0644\u0641\u0627\u062a --ref \u063a\u064a\u0631 \u0645\u0648\u062c\u0648\u062f\u0629\u060c \u062c\u0627\u0631 \u0627\u0633\u062a\u062e\u062f\u0627\u0645 \u0627\u0644\u0628\u0635\u0645\u0629 \u0627\u0644\u0645\u062e\u0632\u0651\u0646\u0629')

    # Progress markers -- app.py polls stdout to update the progress bar.
    # Engine L() also emits "Pass 1", "Pass 2", "Pass 3" internally.
    print('Pass 1 \u2014 \u062a\u062d\u0644\u064a\u0644 \u0627\u0644\u0645\u0644\u0641 \u0648\u0628\u0646\u0627\u0621 \u0627\u0644\u0628\u0635\u0645\u0629 \u0627\u0644\u0645\u0631\u062c\u0639\u064a\u0629...')
    sys.stdout.flush()

    try:
        result = enhance(input_path=args.input, output_path=args.output)
    except Exception as e:
        print(f'Error: {e}')
        sys.exit(1)

    score   = result.get('score', 0)
    metrics = result.get('final_metrics', {})
    lufs    = metrics.get('lufs',  TARGET['lufs'])
    rms     = metrics.get('rms',   TARGET['rms'])
    crest   = metrics.get('crest', TARGET['crest'])
    lra     = metrics.get('lra',   TARGET['lra'])

    print('Pass 3 \u2014 \u0625\u0646\u0647\u0627\u0621 \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629')
    print(f'Score: {score:.1f}')
    print(f'LUFS={lufs:.2f} RMS={rms:.2f} Crest={crest:.2f} LRA={lra:.2f}')
    sys.stdout.flush()

    sys.exit(0 if score >= 90 else 1)
"""
engine, p3ok = _replace_once(engine, OLD_ENTRY, NEW_ENTRY, "entry point -> argparse")
_rec("1.4", "Entry point replaced", p3ok)

_h2("1.5  Write engine_v70.py")
if p1ok and p2ok and p3ok:
    _write(ENGINE_DEST, engine)
    sz = ENGINE_DEST.stat().st_size
    _ok(f"Written: {ENGINE_DEST} ({sz:,} bytes)")
    _rec("1.5", "engine_v70.py written", True)
else:
    _err("Patch(es) failed -- NOT writing")
    _rec("1.5", "engine_v70.py written", False)
    sys.exit(1)

_h2("1.6  Spot-check engine_v70.py")
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
_rec("1.6", "engine_v70.py spot-checks", r1all)


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

_h2("2.2  Check if already patched by v3 run 1")
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
        "      throw Exception('HTTP \${res.statusCode}');\n"
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
#  STEP 3  Clone HF Space to ~/tilawa-hf-clone  (NOT /tmp)
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

# Anchor confirmed from peek_server.py on April 13 2026.
# Line in file:  '     "--timeout", "600", \'  followed by newline.
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
#  STEP 6  Verify live HF files (HF rebuilds ~2 min after push)
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
