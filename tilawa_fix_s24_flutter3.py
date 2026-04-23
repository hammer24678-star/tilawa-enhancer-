#!/usr/bin/env python3
"""
tilawa_fix_s24_flutter3.py  -- S24 Flutter fix (remaining 2 patches)
=====================================================================
Fixes only what flutter2 left broken:
  FAIL 2b  v7.6 + v7.5 still in _engines   [home_screen.dart]
  FAIL 5   v8.1 missing from _EHist         [home_screen.dart]

Also:
  - Updates TILAWA_PROJECT_LOG.md with S24 session entry
  - Dumps full current codebase to ~/tilawa-enhancer/codebase_dump_s24.txt
  - Commits + pushes everything -> triggers APK build

PRECONDITION: run AFTER tilawa_fix_s24_flutter2.py already ran.

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s24_flutter3.py
"""

import sys, subprocess, glob
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

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f"Anchor NOT found -- {label}")
        # Print nearby context to help diagnose
        # Try to find a 20-char sub-anchor
        sub = old[:40].strip()
        if sub in text:
            idx = text.index(sub)
            print(f"        (sub-anchor found at {idx}: {repr(text[idx:idx+80])})")
        else:
            print(f"        (sub-anchor '{sub[:30]}' also NOT found)")
        return text, False
    if c > 1:
        print(f"     !!  Anchor found {c}x -- using first -- {label}")
    _ok(f"Replaced -- {label}")
    return text.replace(old, new, 1), True

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

# ── config ────────────────────────────────────────────────────────────────────
REPO     = Path.home() / "tilawa-enhancer"
HOME_SCR = REPO / "lib" / "screens" / "home_screen.dart"
LOG_FILE = REPO / "TILAWA_PROJECT_LOG.md"

_h1("STARTING S24-Flutter3  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

_h2("Verify files present")
_require(HOME_SCR.exists(), f"home_screen.dart missing")
_ok(f"home_screen.dart  ({HOME_SCR.stat().st_size:,} bytes)")

hs = HOME_SCR.read_text(encoding="utf-8")

# Quick state check
_h2("Current state check")
_ok("_engine = 'v8.1' present") if "_engine    = 'v8.1'" in hs else _err("default engine NOT v8.1 -- run flutter2 first")
_ok("v8.1 in _engines") if "'v8.1'" in hs else _err("v8.1 missing from _engines")
_ok("v7.6 still present (expected -- fixing now)") if "'v7.6', '\u062a\u0642\u064a\u064a\u0645 \u0630\u0643\u064a'" in hs else _ok("v7.6 already removed")
_ok("v7.5 still present (expected -- fixing now)") if "'v7.5', '\u062f\u0642\u0629 \u0645\u0646\u0636\u0628\u0637\u0629'" in hs else _ok("v7.5 already removed")

# ── PATCH A -- Remove v7.6 + v7.5 from _engines ─────────────────────────────
_h1("PATCH A -- Remove v7.6 + v7.5 from _engines")

# Use short, reliable anchors. The em dash U+2014 is the key character
# that caused the previous failure (script used -- instead of \u2014).
EM = "\u2014"   # — em dash, present in the v7.5 en description

OLD_A = (
    "    _EngineData(\n"
    "      'v7.6', '\u062a\u0642\u064a\u064a\u0645 \u0630\u0643\u064a', 'Intelligent Assessment', 94.0,\n"
    "      'MDS', 'blue',\n"
    "      ['MDS System', 'SFM-NR', 'DR-Calibrated', 'Spectral Dist EQ', '4-Pass WAV', 'A-Weighting'],\n"
    "      '\u0623\u0648\u0644 \u0646\u0633\u062e\u0629 \u0628\u0646\u0638\u0627\u0645 MDS: \u0627\u0644\u0627\u0646\u0628\u0633\u0627\u0637 \u0627\u0644\u0637\u064a\u0641\u064a SFM + \u0627\u0644\u0646\u0637\u0627\u0642 \u0627\u0644\u062f\u064a\u0646\u0627\u0645\u064a\u0643\u064a + \u0627\u0644\u0645\u0633\u0627\u0641\u0629 \u0627\u0644\u0637\u064a\u0641\u064a\u0629 + \u0628\u0635\u0645\u0629 \u062a\u0644\u0641 \u0627\u0644\u0643\u0648\u062f\u0643. \u062a\u0634\u062e\u064a\u0635 \u0645\u0633\u062a\u0645\u0631 0-100 \u0628\u062f\u0644 5 \u062a\u0635\u0646\u064a\u0641\u0627\u062a \u062b\u0646\u0627\u0626\u064a\u0629.',\n"
    "      'First with MDS (Multi-Metric Damage Score): Spectral Flatness + Dynamic Range + Spectral Distance + Codec Damage Fingerprint. Continuous 0-100 diagnosis replacing 5 binary tiers.',\n"
    "    ),\n"
    "    _EngineData(\n"
    "      'v7.5', '\u062f\u0642\u0629 \u0645\u0646\u0636\u0628\u0637\u0629', 'Disciplined Precision', 94.0,\n"
    "      'BEST', 'green',\n"
    "      ['Do-No-Harm', 'Crest-Aware', 'Quality Gate', '4-Pass WAV', 'Bark EQ', 'Single Compand'],\n"
    "      '\u0645\u0628\u062f\u0623 \"\u0644\u0627 \u0636\u0631\u0631\": Quality Gate \u064a\u062d\u0645\u064a \u0627\u0644\u062c\u0648\u062f\u0629 \u0628\u0639\u062f \u0643\u0644 pass\u060c Crest-Aware \u064a\u0645\u0646\u0639 bass boost \u0639\u0646\u062f \u0627\u0646\u0647\u064a\u0627\u0631 Crest\u060c compand \u0648\u0627\u062d\u062f \u0646\u0638\u064a\u0641 \u0641\u0642\u0637 " + EM + " \u0644\u0627 \u062a\u0643\u062f\u064a\u0633. \u0627\u0644\u0639\u0648\u062f\u0629 \u0644\u0628\u0646\u064a\u0629 v7.0 \u0627\u0644\u0645\u064f\u062b\u0628\u064e\u0651\u062a\u0629.',\n"
    "      '\"Do-No-Harm\": Quality Gate protects output after each pass, Crest-Aware blocks bass boost when Crest degrades, single clean compand only " + EM + " no stacking. Return to proven v7.0 architecture.',\n"
    "    ),\n"
)
hs, okA = _replace_once(hs, OLD_A, "", "remove v7.6 + v7.5 from _engines")
_rec("A", "v7.6 + v7.5 removed from _engines", okA)

# ── PATCH B -- Add v8.1 to _EHist, demote v8.0 ───────────────────────────────
_h1("PATCH B -- _EHist: add v8.1 LATEST, demote v8.0")

# Anchor: the unique English description line of v8.0 _EHist entry.
# Avoids the ≥ character entirely.
OLD_B = (
    "_EHist('v8.0','Calibrated Precision','\u226596/100','LATEST','gold',\n"
    "      '\u0625\u0635\u0644\u0627\u062d 5 \u0623\u062e\u0637\u0627\u0621: SPECTRAL_BIAS \u0645\u0639\u0643\u0648\u0633\u060c double compand\u060c 5 limiters \u062a\u0631\u0627\u0643\u0645\u064a\u0629\u060c \u062e\u0637\u0623 DR/LRA\u060c Crest guard \u0636\u0639\u064a\u0641',\n"
    "      'Fixes 5 v7.6 bugs: reversed bias, double compand stacking, 5 cumulative limiters, wrong DR/LRA type, weak Crest guard'),\n"
)
NEW_B = (
    "_EHist('v8.1','Android-Hardened','\u226598/100','LATEST','gold',\n"
    "      '\u0625\u0635\u0644\u0627\u062d \u062e\u0637\u0623 /tmp \u0639\u0644\u0649 \u0623\u0646\u062f\u0631\u0648\u064a\u062f \u2014 tempfile \u0622\u0645\u0646. \u0643\u0644 \u0645\u0632\u0627\u064a\u0627 v8.0 \u0645\u062d\u062a\u0641\u0638\u0629.',\n"
    "      'Fix /tmp crash on Android \u2014 safe tempfile workdir. All v8.0 improvements preserved.'),\n"
    "    _EHist('v8.0','Calibrated Precision','\u226596/100','','gold',\n"
    "      '\u0625\u0635\u0644\u0627\u062d 5 \u0623\u062e\u0637\u0627\u0621: SPECTRAL_BIAS \u0645\u0639\u0643\u0648\u0633\u060c double compand\u060c 5 limiters \u062a\u0631\u0627\u0643\u0645\u064a\u0629\u060c \u062e\u0637\u0623 DR/LRA\u060c Crest guard \u0636\u0639\u064a\u0641',\n"
    "      'Fixes 5 v7.6 bugs: reversed bias, double compand stacking, 5 cumulative limiters, wrong DR/LRA type, weak Crest guard'),\n"
)
hs, okB = _replace_once(hs, OLD_B, NEW_B, "_EHist v8.1 + demote v8.0")
_rec("B", "_EHist updated", okB)

# ── Write ─────────────────────────────────────────────────────────────────────
_h1("Writing home_screen.dart")
HOME_SCR.write_text(hs, encoding="utf-8")
_ok(f"home_screen.dart written ({len(hs):,} chars)")
_rec("W", "home_screen.dart written", True)

# ── Verify ────────────────────────────────────────────────────────────────────
_h1("Verification")
checks = [
    ("default engine v8.1",           "_engine    = 'v8.1'" in hs),
    ("v8.1 in _engines",              "'v8.1'" in hs and "Android-Hardened" in hs),
    ("v7.5 removed from _engines",    "'v7.5', '\u062f\u0642\u0629 \u0645\u0646\u0636\u0628\u0637\u0629'" not in hs),
    ("v7.6 removed from _engines",    "'v7.6', '\u062a\u0642\u064a\u064a\u0645 \u0630\u0643\u064a'" not in hs),
    ("v8.1 _EHist entry",             "_EHist('v8.1'" in hs),
    ("v8.0 _EHist badge cleared",     "'v8.0','Calibrated Precision','\u226596/100','LATEST'" not in hs),
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
- **engine_v81.py** added to HF Space (86,693 bytes)
- **app.py** patched (S24 + S24b + S24c):
  - ENGINE_SCRIPTS: added v8.1, removed v7.5 + v7.6
  - Standalone /100 score scan (BUG-SCORE fix)
  - `_prune_jobs()` function added (BUG8 memory leak)
  - `/download_chunk` + `/ping` routes added (BUG7)
  - Default engine in legacy `/upload` route: v7.6 → v8.1
  - Docstring updated to v3
- **engine_v75.py + engine_v76.py** removed via `git rm`
- **Server verified**: `{"engines":{"v7.0":true,"v8.0":true,"v8.1":true},"status":"ok"}`

### Flutter app changes
- **home_screen.dart**:
  - Default `_engine`: `v8.0` → `v8.1`
  - `_engines` list: added v8.1 (Android-Hardened, ≥98/100, LATEST), removed v7.5 + v7.6, demoted v8.0 to PREV
  - `engineNames` result card map: added v8.1, removed v7.5/v7.6
  - `_EHist`: added v8.1 as LATEST, demoted v8.0 badge
- **api_service.dart**:
  - `buildFilename` engineNames map: added v8.1, removed v7.5/v7.6

### Lessons learned
- S24 fix script anchors failed 2x:
  - `_prune_jobs` anchor: HISTORY section header dash count wrong, then `HISTORY.pop()\\n\\n@app.route` failed because comment sits between. Fixed by anchoring on the unique `if len(HISTORY) > 50:` line.
  - `v7.6` still in legacy `/upload`: s24b only patched `upload_start`/`upload_finalize`, missed the third occurrence in the old `/upload` route.
- Flutter patch targeted `lib/main.dart` (2,990 bytes stub) instead of `lib/screens/home_screen.dart` where engine UI code lives.
- Em dash `—` (U+2014) in Dart string literals: must use `\\u2014` in Python anchor strings, not `--`.
- `≥` (U+2265) in `_EHist` score strings: embed as `\\u2265` in Python to avoid encoding ambiguity.

### Files changed
- HF Space: `app.py`, `engine_v81.py` (added), `engine_v75.py`/`engine_v76.py` (removed)
- GitHub repo: `lib/screens/home_screen.dart`, `lib/services/api_service.dart`

### Status
APK build triggered via GitHub Actions push. Pending download.
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

# ── Full codebase dump ────────────────────────────────────────────────────────
_h1("Generating codebase dump")

DUMP = REPO / "codebase_dump_s24.txt"
DART_FILES = sorted(REPO.rglob("*.dart"))
PY_FILES   = sorted(REPO.glob("*.py"))
YML_FILES  = sorted(REPO.rglob("*.yml"))
OTHER      = [REPO / "pubspec.yaml", REPO / "TILAWA_PROJECT_LOG.md"]

bar = "\u2550" * 64

lines = [
    "=" * 64,
    "  TILAWA ENHANCER \u2014 FULL CODEBASE DUMP (S24)",
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
_run('git config user.email "s24f3@tilawa.fix"', label="git config email")
_run('git config user.name "S24 Flutter3"',      label="git config name")

ok_add, _ = _run(
    "git add lib/screens/home_screen.dart lib/services/api_service.dart "
    "TILAWA_PROJECT_LOG.md codebase_dump_s24.txt",
    label="git add")
_rec("G1", "git add", ok_add)

_run("git status --short", label="git status")

msg = "S24: v8.1 UI complete -- remove v7.5/v7.6, update _EHist, log + dump"
ok_commit, out = _run(f'git commit -m "{msg}"', label="git commit")
if not ok_commit and "nothing to commit" in out:
    _ok("Nothing to commit")
    ok_commit = True
_rec("G2", "git commit", ok_commit)

ok_push, _ = _run("git push origin main", label="git push", timeout=120)
_rec("G3", "git push", ok_push)

_print_summary()

if ok_push:
    print("\n  APK build triggered.")
    print("  https://github.com/c42742910-ops/tilawa-enhancer/actions")
    print("\n  When green, download from Actions > Artifacts > Tilawa-Enhancer-APK")
