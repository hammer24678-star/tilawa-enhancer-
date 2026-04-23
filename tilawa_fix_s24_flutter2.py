#!/usr/bin/env python3
"""
tilawa_fix_s24_flutter2.py  -- S24 Flutter app update (fixed)
=============================================================
Patches the correct files:
  lib/screens/home_screen.dart  -- patches 1, 2, 3, 5
  lib/services/api_service.dart -- patch 4

Changes:
  1. Default _engine: v8.0 -> v8.1               (home_screen.dart)
  2. _engines list: remove v7.5/v7.6, add v8.1   (home_screen.dart)
  3. engineNames map (result card)                (home_screen.dart)
  4. buildFilename engineNames map                (api_service.dart)
  5. _EHist history: add v8.1, demote v8.0        (home_screen.dart)

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s24_flutter2.py
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

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f"Anchor NOT found -- {label}")
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
API_SVC  = REPO / "lib" / "services" / "api_service.dart"

_h1("STARTING S24-Flutter2  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

_h2("Verify files present")
_require(HOME_SCR.exists(), f"home_screen.dart missing at {HOME_SCR}")
_require(API_SVC.exists(),  f"api_service.dart missing at {API_SVC}")
_ok(f"home_screen.dart  ({HOME_SCR.stat().st_size:,} bytes)")
_ok(f"api_service.dart  ({API_SVC.stat().st_size:,} bytes)")

hs = HOME_SCR.read_text(encoding="utf-8")
ap = API_SVC.read_text(encoding="utf-8")

# ── PATCH 1 -- Default engine ─────────────────────────────────────────────────
_h1("PATCH 1 -- Default engine v8.0 -> v8.1  [home_screen.dart]")
hs, ok1 = _replace_once(hs,
    "  String  _engine    = 'v8.0';",
    "  String  _engine    = 'v8.1';",
    "default _engine")
_rec("1", "Default engine updated", ok1)

# ── PATCH 2 -- _engines list ─────────────────────────────────────────────────
_h1("PATCH 2 -- _engines list  [home_screen.dart]")
OLD2 = (
    "    _EngineData(\n"
    "      'v8.0', '\u062f\u0642\u0629 \u0645\u064f\u0639\u0627\u064a\u064e\u0631\u0629', 'Calibrated Precision', 96.0,\n"
    "      'NEW', 'gold',"
)
NEW2 = (
    "    _EngineData(\n"
    "      'v8.1', '\u0645\u062a\u0635\u0644\u0628 \u0623\u0646\u062f\u0631\u0648\u064a\u062f', 'Android-Hardened', 98.0,\n"
    "      'LATEST', 'gold',\n"
    "      ['Android /tmp Fix', 'BIAS V8.1', 'Crest Guard', 'SFM-NR', 'Single Compand', 'MDS'],\n"
    "      '\u0625\u0635\u0644\u0627\u062d \u062e\u0637\u0623 \u062d\u0631\u062c \u0641\u064a v8.0: \u0645\u0633\u0627\u0631 /tmp \u063a\u064a\u0631 \u0645\u062a\u0627\u062d \u0639\u0644\u0649 \u0623\u0646\u062f\u0631\u0648\u064a\u062f \u2014 \u064a\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u0622\u0646 \u0645\u062c\u0644\u062f \u0639\u0645\u0644 \u0622\u0645\u0646 \u0639\u0628\u0631 tempfile. \u0643\u0644 \u0645\u0632\u0627\u064a\u0627 v8.0 \u0645\u062d\u062a\u0641\u0638\u0629.',\n"
    "      'Critical fix from v8.0: /tmp path inaccessible on Android \u2014 now uses safe tempfile workdir. All v8.0 improvements preserved.',\n"
    "    ),\n"
    "    _EngineData(\n"
    "      'v8.0', '\u062f\u0642\u0629 \u0645\u064f\u0639\u0627\u064a\u064e\u0631\u0629', 'Calibrated Precision', 96.0,\n"
    "      'PREV', 'gold',"
)
hs, ok2 = _replace_once(hs, OLD2, NEW2, "add v8.1 to _engines, demote v8.0")

# Remove v7.6 entry
OLD2b = (
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
    "      '\u0645\u0628\u062f\u0623 \"\u0644\u0627 \u0636\u0631\u0631\": Quality Gate \u064a\u062d\u0645\u064a \u0627\u0644\u062c\u0648\u062f\u0629 \u0628\u0639\u062f \u0643\u0644 pass\u060c Crest-Aware \u064a\u0645\u0646\u0639 bass boost \u0639\u0646\u062f \u0627\u0646\u0647\u064a\u0627\u0631 Crest\u060c compand \u0648\u0627\u062d\u062f \u0646\u0638\u064a\u0641 \u0641\u0642\u0637 \u2014 \u0644\u0627 \u062a\u0643\u062f\u064a\u0633. \u0627\u0644\u0639\u0648\u062f\u0629 \u0644\u0628\u0646\u064a\u0629 v7.0 \u0627\u0644\u0645\u064f\u062b\u0628\u064e\u0651\u062a\u0629.',\n"
    "      '\"Do-No-Harm\": Quality Gate protects output after each pass, Crest-Aware blocks bass boost when Crest degrades, single clean compand only -- no stacking. Return to proven v7.0 architecture.',\n"
    "    ),\n"
)
hs, ok2b = _replace_once(hs, OLD2b, "", "remove v7.6 + v7.5 from _engines")
_rec("2", "_engines list updated", ok2 and ok2b)

# ── PATCH 3 -- engineNames result card  ──────────────────────────────────────
_h1("PATCH 3 -- engineNames map result card  [home_screen.dart]")
OLD3 = (
    "    const engineNames = {\n"
    "      'v8.0': 'Calibrated Precision',\n"
    "      'v7.6': 'Intelligent Assessment',\n"
    "      'v7.5': 'Disciplined Precision',\n"
    "      'v7.0': 'Classic',\n"
    "    };"
)
NEW3 = (
    "    const engineNames = {\n"
    "      'v8.1': 'Android-Hardened',\n"
    "      'v8.0': 'Calibrated Precision',\n"
    "      'v7.0': 'Classic',\n"
    "    };"
)
hs, ok3 = _replace_once(hs, OLD3, NEW3, "engineNames result card")
_rec("3", "engineNames result card updated", ok3)

# ── PATCH 4 -- buildFilename engineNames  [api_service.dart] ─────────────────
_h1("PATCH 4 -- buildFilename engineNames  [api_service.dart]")
OLD4 = (
    "    const engineNames = {\n"
    "      'v8.0': 'Calibrated_Precision',\n"
    "      'v7.6': 'Intelligent_Assessment',\n"
    "      'v7.5': 'Disciplined_Precision',\n"
    "      'v7.0': 'Classic',\n"
    "    };"
)
NEW4 = (
    "    const engineNames = {\n"
    "      'v8.1': 'Android_Hardened',\n"
    "      'v8.0': 'Calibrated_Precision',\n"
    "      'v7.0': 'Classic',\n"
    "    };"
)
ap, ok4 = _replace_once(ap, OLD4, NEW4, "buildFilename engineNames")
_rec("4", "buildFilename engineNames updated", ok4)

# ── PATCH 5 -- _EHist  ────────────────────────────────────────────────────────
_h1("PATCH 5 -- _EHist: add v8.1 LATEST, demote v8.0  [home_screen.dart]")
OLD5 = "_EHist('v8.0','Calibrated Precision','\u226596/100','LATEST','gold',"
NEW5 = (
    "_EHist('v8.1','Android-Hardened','\u226598/100','LATEST','gold',\n"
    "      '\u0625\u0635\u0644\u0627\u062d \u062e\u0637\u0623 /tmp \u0639\u0644\u0649 \u0623\u0646\u062f\u0631\u0648\u064a\u062f. \u0643\u0644 \u0645\u0632\u0627\u064a\u0627 v8.0 \u0645\u062d\u062a\u0641\u0638\u0629.',\n"
    "      'Fix /tmp path crash on Android. All v8.0 improvements preserved.'),\n"
    "    _EHist('v8.0','Calibrated Precision','\u226596/100','','gold',"
)
hs, ok5 = _replace_once(hs, OLD5, NEW5, "_EHist v8.1 + demote v8.0")
_rec("5", "_EHist updated", ok5)

# ── Write files ───────────────────────────────────────────────────────────────
_h1("Writing files")
HOME_SCR.write_text(hs, encoding="utf-8")
_ok(f"home_screen.dart written ({len(hs):,} chars)")
API_SVC.write_text(ap, encoding="utf-8")
_ok(f"api_service.dart written ({len(ap):,} chars)")
_rec("W", "files written", True)

# ── Verify ────────────────────────────────────────────────────────────────────
_h1("Verification")
checks = [
    ("default engine v8.1",            "_engine    = 'v8.1'" in hs),
    ("v8.1 in _engines",               "'v8.1', 'متصلب أندرويد'" in hs),
    ("v7.5 removed from _engines",     "'v7.5', 'دقة منضبطة'" not in hs),
    ("v7.6 removed from _engines",     "'v7.6', 'تقييم ذكي'" not in hs),
    ("v8.1 in engineNames (card)",     "'v8.1': 'Android-Hardened'" in hs),
    ("v7.6 removed from engineNames",  "'v7.6': 'Intelligent Assessment'" not in hs),
    ("v8.1 in buildFilename",          "'v8.1': 'Android_Hardened'" in ap),
    ("v7.5 removed buildFilename",     "'v7.5': 'Disciplined_Precision'" not in ap),
    ("v8.1 _EHist entry",              "_EHist('v8.1'" in hs),
    ("v8.0 _EHist badge cleared",      "_EHist('v8.0','Calibrated Precision','≥96/100','LATEST'" not in hs),
]
all_pass = True
for label, cond in checks:
    ((_ok if cond else _err)(label))
    if not cond:
        all_pass = False

_rec("V", "verification", all_pass)
if not all_pass:
    _err("FATAL: Verification failed -- check patches above")
    _print_summary()
    sys.exit(1)

# ── Git push ──────────────────────────────────────────────────────────────────
_h1("Git push -- triggers APK build")
_run('git config user.email "s24f@tilawa.fix"', label="git config email")
_run('git config user.name "S24 Flutter"',      label="git config name")

ok_add, _ = _run(
    "git add lib/screens/home_screen.dart lib/services/api_service.dart",
    label="git add")
_rec("G1", "git add", ok_add)

_run("git status --short", label="git status")

msg = "S24: add engine v8.1, remove v7.5/v7.6 from UI"
ok_commit, out = _run(f'git commit -m "{msg}"', label="git commit")
if not ok_commit and "nothing to commit" in out:
    _ok("Nothing to commit")
    ok_commit = True
_rec("G2", "git commit", ok_commit)

ok_push, _ = _run("git push origin main", label="git push", timeout=120)
_rec("G3", "git push", ok_push)

_print_summary()

if ok_push:
    print("\n  GitHub Actions build triggered.")
    print("  https://github.com/c42742910-ops/tilawa-enhancer/actions")
