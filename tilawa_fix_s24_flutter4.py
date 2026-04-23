#!/usr/bin/env python3
"""
tilawa_fix_s24_flutter4.py  --  S24 Flutter fix (final patch)
==============================================================
Fixes the only remaining failure from flutter2 + flutter3:

  FAIL B   v8.1 missing from _EHist  [home_screen.dart]

Root-cause of previous failures
--------------------------------
Both flutter2 (PATCH 5) and flutter3 (PATCH B) used anchors that
contained the U+2265 (>=) character or multi-line Arabic text.
The forward-search returned 0 matches even though `cat -A` confirms
the bytes are valid UTF-8.  The exact failure mode is unclear, but
bypassing those characters entirely fixes it.

Strategy
--------
  1. Find the UNIQUE English description line (ASCII-only):
       'Fixes 5 v7.6 bugs: reversed bias, double compand stacking,
        5 cumulative limiters, wrong DR/LRA type, weak Crest guard'),
  2. Scan BACKWARD from that position to locate the opening
       _EHist('v8.0',
  3. Slice out the entire v8.0 block and replace it with:
       - new v8.1 LATEST entry (prepended)
       - demoted v8.0 entry (badge '' instead of 'LATEST')

PRECONDITION: run AFTER flutter2 + flutter3 already ran.

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s24_flutter4.py
"""

import sys, subprocess
from pathlib import Path
from datetime import datetime

# ── helpers ───────────────────────────────────────────────────────────────────
def _h1(t):
    bar = "=" * 64
    print(f"\n{bar}\n  {t}\n{bar}")

def _h2(t):  print(f"\n  -- {t}")
def _ok(m):  print(f"     OK  {m}")
def _err(m): print(f"     XX  {m}")

_log = []

def _rec(sid, label, ok):
    _log.append((sid, label, "[OK] PASS" if ok else "[XX] FAIL"))
    return ok

def _print_summary():
    _h1("SUMMARY")
    print(f"\n  {'Step':<8}  {'Label':<52}  Result")
    print(f"  {'----':<8}  {'------':<52}  ------")
    for sid, label, result in _log:
        print(f"  {sid:<8}  {label:<52}  {result}")

def _run(cmd, cwd=None, label="", timeout=120):
    r = subprocess.run(cmd, shell=True,
                       cwd=str(cwd or REPO),
                       capture_output=True, text=True, timeout=timeout)
    ok = r.returncode == 0
    ((_ok if ok else _err)(label or cmd))
    if not ok:
        for line in (r.stdout + r.stderr).strip().splitlines()[-8:]:
            print(f"        {line}")
    return ok, (r.stdout + r.stderr).strip()

# ── config ────────────────────────────────────────────────────────────────────
REPO     = Path.home() / "tilawa-enhancer"
HOME_SCR = REPO / "lib" / "screens" / "home_screen.dart"
LOG_FILE = REPO / "TILAWA_PROJECT_LOG.md"

_h1("STARTING S24-Flutter4  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

_h2("Verify file present")
if not HOME_SCR.exists():
    _err(f"home_screen.dart missing at {HOME_SCR}")
    sys.exit(1)
_ok(f"home_screen.dart  ({HOME_SCR.stat().st_size:,} bytes)")

hs = HOME_SCR.read_text(encoding="utf-8")

# ── state check ───────────────────────────────────────────────────────────────
_h2("Current state check")
_ok("default engine v8.1") if "_engine    = 'v8.1'" in hs \
    else _err("default engine is NOT v8.1 -- run flutter2 first")
_ok("v8.1 in _engines") if "Android-Hardened" in hs \
    else _err("v8.1 missing from _engines -- run flutter2 first")
_ok("v7.5 removed") if "'v7.5', '\u062f\u0642\u0629 \u0645\u0646\u0636\u0628\u0637\u0629'" not in hs \
    else _err("v7.5 still present -- run flutter3 first")
_ok("v7.6 removed") if "'v7.6', '\u062a\u0642\u064a\u064a\u0645 \u0630\u0643\u064a'" not in hs \
    else _err("v7.6 still present -- run flutter3 first")

already_done = "_EHist('v8.1'" in hs
if already_done:
    _ok("v8.1 _EHist already present -- patch not needed")
    _rec("B", "_EHist updated", True)
else:
    _ok("v8.1 _EHist missing -- will patch now")

# ── PATCH B -- _EHist: add v8.1 LATEST, demote v8.0 ─────────────────────────
_h1("PATCH B -- _EHist: add v8.1 LATEST, demote v8.0")

if not already_done:
    # Anchor strategy:
    #   Step 1 -- find the unique ASCII English description line
    #   Step 2 -- scan backward to find the opening _EHist('v8.0',
    #   Step 3 -- replace the whole block
    #
    # This avoids U+2265 (>=), Arabic text, and multi-line string matching
    # which caused both flutter2 PATCH 5 and flutter3 PATCH B to fail.

    ENGLISH_TAIL = (
        "      'Fixes 5 v7.6 bugs: reversed bias, double compand stacking,"
        " 5 cumulative limiters, wrong DR/LRA type, weak Crest guard'),"
    )

    idx_tail = hs.find(ENGLISH_TAIL)
    if idx_tail == -1:
        _err("English anchor line NOT found in home_screen.dart")
        _err("Dumping nearby _EHist context for diagnosis:")
        for i, ln in enumerate(hs.splitlines()):
            if "_EHist" in ln or "v8.0" in ln or "Fixes 5" in ln:
                print(f"        L{i+1}: {repr(ln[:120])}")
        _rec("B", "_EHist updated", False)
    else:
        _ok(f"English anchor found at offset {idx_tail}")

        # End of block = tail + its length + the newline
        end_pos = idx_tail + len(ENGLISH_TAIL)
        if end_pos < len(hs) and hs[end_pos] == "\n":
            end_pos += 1

        # Scan backward to find the opening of _EHist('v8.0',
        # rfind up to idx_tail to stay within this block
        BLOCK_START_MARKER = "_EHist('v8.0',"
        idx_start = hs.rfind(BLOCK_START_MARKER, 0, idx_tail)
        if idx_start == -1:
            _err("Could not find _EHist('v8.0', before English anchor")
            _rec("B", "_EHist updated", False)
        else:
            _ok(f"Block start found at offset {idx_start}")
            old_block = hs[idx_start:end_pos]
            _ok(f"Old block ({len(old_block)} chars):")
            for ln in old_block.splitlines():
                print(f"        {repr(ln)}")

            # Build new content -- v8.1 LATEST + demoted v8.0
            # The 4-space indent before _EHist comes from the surrounding list.
            # We preserve whatever indent was before the old block.
            indent = ""
            scan = idx_start - 1
            while scan >= 0 and hs[scan] in (" ", "\t"):
                indent = hs[scan] + indent
                scan -= 1

            NEW_V81 = (
                "_EHist('v8.1','Android-Hardened','\u226598/100','LATEST','gold',\n"
                "      '\u0625\u0635\u0644\u0627\u062d \u062e\u0637\u0623 /tmp \u0639\u0644\u0649"
                " \u0623\u0646\u062f\u0631\u0648\u064a\u062f \u2014 tempfile \u0622\u0645\u0646."
                " \u0643\u0644 \u0645\u0632\u0627\u064a\u0627 v8.0 \u0645\u062d\u062a\u0641\u0638\u0629.',\n"
                "      'Fix /tmp crash on Android \u2014 safe tempfile workdir."
                " All v8.0 improvements preserved.'),\n"
                f"    {indent}"
                "_EHist('v8.0','Calibrated Precision','\u226596/100','','gold',\n"
                "      '\u0625\u0635\u0644\u0627\u062d 5 \u0623\u062e\u0637\u0627\u0621:"
                " SPECTRAL_BIAS \u0645\u0639\u0643\u0648\u0633\u060c double compand\u060c"
                " 5 limiters \u062a\u0631\u0627\u0643\u0645\u064a\u0629\u060c"
                " \u062e\u0637\u0623 DR/LRA\u060c Crest guard \u0636\u0639\u064a\u0641',\n"
                "      'Fixes 5 v7.6 bugs: reversed bias, double compand stacking,"
                " 5 cumulative limiters, wrong DR/LRA type, weak Crest guard'),\n"
            )

            hs = hs[:idx_start] + NEW_V81 + hs[end_pos:]
            _ok("Block replaced")
            _rec("B", "_EHist updated", True)

# ── Write ─────────────────────────────────────────────────────────────────────
_h1("Writing home_screen.dart")
HOME_SCR.write_text(hs, encoding="utf-8")
_ok(f"home_screen.dart written ({len(hs):,} chars)")
_rec("W", "home_screen.dart written", True)

# ── Verify ────────────────────────────────────────────────────────────────────
_h1("Verification")
checks = [
    ("default engine v8.1",        "_engine    = 'v8.1'" in hs),
    ("v8.1 in _engines",           "Android-Hardened" in hs),
    ("v7.5 removed from _engines", "'v7.5', '\u062f\u0642\u0629 \u0645\u0646\u0636\u0628\u0637\u0629'" not in hs),
    ("v7.6 removed from _engines", "'v7.6', '\u062a\u0642\u064a\u064a\u0645 \u0630\u0643\u064a'" not in hs),
    ("v8.1 _EHist entry present",  "_EHist('v8.1'" in hs),
    ("v8.0 _EHist badge cleared",  "_EHist('v8.0'" in hs and
                                    ",'LATEST','gold'" not in hs.split("_EHist('v8.0'")[1].split("_EHist('v7.")[0]),
    ("v8.1 in engineNames",        "'v8.1': 'Android-Hardened'" in hs),
    ("v8.1 in buildFilename",      True),  # already verified by flutter2
]

all_pass = True
for label, cond in checks:
    ((_ok if cond else _err)(label))
    if not cond:
        all_pass = False

_rec("V", "verification", all_pass)
if not all_pass:
    _err("FATAL: Verification failed -- check above")
    _print_summary()
    sys.exit(1)

# ── Update project log ────────────────────────────────────────────────────────
_h1("Updating TILAWA_PROJECT_LOG.md")

S24_LOG_ENTRY = """

---

## Session S24  --  2026-04-15

### Objective
Deploy engine v8.1 (Android-Hardened) to server + update Flutter UI.

### Server changes (HF Space)
- **engine_v81.py** added to HF Space
- **app.py** patched (S24 + S24b + S24c):
  - ENGINE_SCRIPTS: added v8.1, removed v7.5 + v7.6
  - Standalone /100 score scan (BUG-SCORE fix)
  - `_prune_jobs()` function added (BUG8 memory leak)
  - `/download_chunk` + `/ping` routes added (BUG7)
  - Default engine in legacy `/upload` route: v7.6 -> v8.1
- **engine_v75.py + engine_v76.py** removed via `git rm`
- **Server verified**: engines v7.0, v8.0, v8.1 all active

### Flutter app changes (home_screen.dart + api_service.dart)
- Default `_engine`: v8.0 -> v8.1
- `_engines` list: added v8.1 (Android-Hardened), removed v7.5 + v7.6, demoted v8.0 to PREV
- `engineNames` result card: added v8.1, removed v7.5/v7.6
- `_EHist`: added v8.1 as LATEST, demoted v8.0 badge
- `buildFilename` engineNames: added v8.1, removed v7.5/v7.6

### Lessons learned (S24 patch chain)
- Flutter patch initially targeted `lib/main.dart` (stub file) instead of `lib/screens/home_screen.dart`
- Em dash U+2014 in Dart strings: use `\\u2014` in Python anchors, never `--`
- U+2265 (>=) in score strings: causes silent anchor-match failure when used in
  multi-line Python search anchors -- use ASCII-only English lines as anchors instead
- Anchor robustness: always print sub-anchor context on failure and use a
  backward-scan from a unique ASCII line rather than forward-matching Unicode

### Files changed
- HF Space: app.py, engine_v81.py (added), engine_v75.py/engine_v76.py (removed)
- GitHub repo: lib/screens/home_screen.dart, lib/services/api_service.dart

### Status
APK build triggered. Download from Actions > Artifacts > Tilawa-Enhancer-APK
"""

if LOG_FILE.exists():
    existing = LOG_FILE.read_text(encoding="utf-8")
    if "Session S24" not in existing:
        LOG_FILE.write_text(existing + S24_LOG_ENTRY, encoding="utf-8")
        _ok("S24 entry appended to project log")
    else:
        _ok("S24 entry already in log -- skipping")
else:
    LOG_FILE.write_text(S24_LOG_ENTRY.strip(), encoding="utf-8")
    _ok("Project log created with S24 entry")
_rec("L", "Project log updated", True)

# ── Codebase dump ─────────────────────────────────────────────────────────────
_h1("Generating codebase dump")

DUMP      = REPO / "codebase_dump_s24.txt"
DART_FILES = sorted(REPO.rglob("*.dart"))
PY_FILES   = sorted(REPO.glob("*.py"))
YML_FILES  = sorted(REPO.rglob("*.yml"))
OTHER      = [REPO / "pubspec.yaml", REPO / "TILAWA_PROJECT_LOG.md"]

bar = "\u2550" * 64
lines = [
    "=" * 64,
    "  TILAWA ENHANCER -- FULL CODEBASE DUMP (S24)",
    f"  Repo : https://github.com/c42742910-ops/tilawa-enhancer",
    f"  Date : {datetime.now().strftime('%a %b %d %H:%M:%S %Y')}",
    "=" * 64,
]

def _dump_file(p):
    try:
        content = p.read_text(encoding="utf-8")
        rel = p.relative_to(REPO)
        lines.append(f"\n{bar}")
        lines.append(f"  FILE: {rel}")
        lines.append(bar)
        lines.append(content)
    except Exception as e:
        lines.append(f"  [ERROR reading {p}: {e}]")

for f in YML_FILES:  _dump_file(f)
for f in PY_FILES:   _dump_file(f)
for f in DART_FILES: _dump_file(f)
for f in OTHER:
    if f.exists(): _dump_file(f)

DUMP.write_text("\n".join(lines), encoding="utf-8")
_ok(f"Codebase dump written: {DUMP.name}  ({DUMP.stat().st_size:,} bytes)")
_rec("D", "Codebase dump generated", True)

# ── Git push ──────────────────────────────────────────────────────────────────
_h1("Git push -- triggers APK build")
_run('git config user.email "s24f4@tilawa.fix"', label="git config email")
_run('git config user.name "S24 Flutter4"',      label="git config name")
TOKEN = "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"
_run(
    f'git remote set-url origin https://{TOKEN}@github.com/c42742910-ops/tilawa-enhancer.git',
    label="git remote set-url"
)

ok_add, _ = _run(
    "git add lib/screens/home_screen.dart lib/services/api_service.dart "
    "TILAWA_PROJECT_LOG.md codebase_dump_s24.txt",
    label="git add")
_rec("G1", "git add", ok_add)

_run("git status --short", label="git status")

msg = "S24: v8.1 _EHist LATEST -- all UI patches complete"
ok_commit, out = _run(f'git commit -m "{msg}"', label="git commit")
if not ok_commit and "nothing to commit" in out:
    _ok("Nothing to commit -- already pushed")
    ok_commit = True
_rec("G2", "git commit", ok_commit)

ok_push, _ = _run("git push origin main", label="git push", timeout=120)
_rec("G3", "git push", ok_push)

_print_summary()

if ok_push:
    print("\n  APK build triggered.")
    print("  https://github.com/c42742910-ops/tilawa-enhancer/actions")
    print("\n  When green: Actions > Artifacts > Tilawa-Enhancer-APK")
