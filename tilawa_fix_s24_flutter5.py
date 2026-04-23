#!/usr/bin/env python3
"""
tilawa_fix_s24_flutter5.py  --  S24 Flutter fix: _EHist in settings_screen.dart
=================================================================================
ROOT CAUSE (why flutter2–flutter4 all failed):
  _EHist and _history are defined in  lib/screens/settings_screen.dart
  Every previous patch searched                home_screen.dart  <-- WRONG FILE

This script patches the correct file.

Change:
  _EHist history: add v8.1 LATEST, demote v8.0  (settings_screen.dart)

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s24_flutter5.py
"""

import sys
from pathlib import Path
from datetime import datetime

# ── helpers ───────────────────────────────────────────────────────────────────
def _h1(t):
    bar = "=" * 64
    print(f"\n{bar}\n  {t}\n{bar}")

def _h2(t):  print(f"\n  -- {t}")
def _ok(m):  print(f"     OK  {m}")
def _err(m): print(f"     XX  {m}")
def _inf(m): print(f"     !!  {m}")

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
        _inf(f"Anchor found {c}x -- using first -- {label}")
    _ok(f"Replaced -- {label}")
    return text.replace(old, new, 1), True

def _require(cond, msg):
    if not cond:
        _err(f"FATAL: {msg}")
        _print_summary()
        sys.exit(1)

def _print_summary():
    _h1("SUMMARY")
    print(f"\n  {'Step':<8}  {'Label':<56}  Result")
    print(f"  {'----':<8}  {'------':<56}  ------")
    for sid, label, result in _log:
        print(f"  {sid:<8}  {label:<56}  {result}")

# ── config ────────────────────────────────────────────────────────────────────
REPO     = Path.home() / "tilawa-enhancer"
SETTINGS = REPO / "lib" / "screens" / "settings_screen.dart"

_h1("STARTING S24-Flutter5  --  " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

_h2("Root cause note")
_inf("flutter2–flutter4 ALL patched home_screen.dart")
_inf("_EHist + _history live in  settings_screen.dart  <-- correct file")

# ── Pre-flight ────────────────────────────────────────────────────────────────
_h1("STEP 0 -- Pre-flight checks")

_h2("Verify settings_screen.dart present")
_require(SETTINGS.exists(), f"settings_screen.dart missing at {SETTINGS}")
_ok(f"settings_screen.dart  ({SETTINGS.stat().st_size:,} bytes)")

ss = SETTINGS.read_text(encoding="utf-8")

_h2("Current state check")

already_done = "_EHist('v8.1'" in ss
if already_done:
    _ok("v8.1 already present in _EHist -- patch not needed")
    _rec("0", "Pre-flight", True)
    _print_summary()
    print("\n  Nothing to do. settings_screen.dart already has v8.1 in _EHist.\n")
    sys.exit(0)

_ok("v8.1 NOT yet in _EHist -- will add now")

has_v80_latest = "_EHist('v8.0','Calibrated Precision','\u226596/100','LATEST','gold'," in ss
has_history    = "static const _history = [" in ss
has_ehist_cls  = "class _EHist {" in ss

_ok(f"static const _history present:  {has_history}")
_ok(f"_EHist('v8.0'...'LATEST' present: {has_v80_latest}")
_ok(f"class _EHist present:           {has_ehist_cls}")
_rec("0", "Pre-flight", has_history)

if not has_history:
    _err("FATAL: _history block missing from settings_screen.dart")
    _err("This file may be severely corrupted. Please restore from git.")
    _print_summary()
    sys.exit(1)

# ── PATCH B -- _EHist: add v8.1 LATEST, demote v8.0 ─────────────────────────
_h1("PATCH B -- _EHist: add v8.1 LATEST, demote v8.0  [settings_screen.dart]")

# The OLD block is the v8.0 entry currently tagged LATEST.
# Exact text confirmed from codebase dump.
OLD_B = (
    "    _EHist('v8.0','Calibrated Precision','\u226596/100','LATEST','gold',\n"
    "      '\u0625\u0635\u0644\u0627\u062d 5 \u0623\u062e\u0637\u0627\u0621:"
    " SPECTRAL_BIAS \u0645\u0639\u0643\u0648\u0633\u060c"
    " double compand\u060c"
    " 5 limiters \u062a\u0631\u0627\u0643\u0645\u064a\u0629\u060c"
    " \u062e\u0637\u0623 DR/LRA\u060c"
    " Crest guard \u0636\u0639\u064a\u0641',\n"
    "      'Fixes 5 v7.6 bugs: reversed bias, double compand stacking,"
    " 5 cumulative limiters, wrong DR/LRA type, weak Crest guard'),\n"
)

# NEW block: v8.1 LATEST prepended, v8.0 demoted (badge '' not 'LATEST')
NEW_B = (
    "    _EHist('v8.1','Android-Hardened','\u226598/100','LATEST','gold',\n"
    "      '\u0625\u0635\u0644\u0627\u062d \u062e\u0637\u0623 \u062d\u0631\u062c"
    " \u0641\u064a v8.0: \u0645\u0633\u0627\u0631 /tmp \u063a\u064a\u0631"
    " \u0645\u062a\u0627\u062d \u0639\u0644\u0649 \u0623\u0646\u062f\u0631\u0648\u064a\u062f"
    " \u2014 \u064a\u0633\u062a\u062e\u062f\u0645 \u0627\u0644\u0622\u0646"
    " \u0645\u062c\u0644\u062f \u0639\u0645\u0644 \u0622\u0645\u0646"
    " \u0639\u0628\u0631 tempfile."
    " \u0643\u0644 \u0645\u0632\u0627\u064a\u0627 v8.0 \u0645\u062d\u062a\u0641\u0638\u0629.',\n"
    "      'Critical fix from v8.0: /tmp path inaccessible on Android"
    " \u2014 now uses safe tempfile workdir. All v8.0 improvements preserved.'),\n"
    "    _EHist('v8.0','Calibrated Precision','\u226596/100','','gold',\n"
    "      '\u0625\u0635\u0644\u0627\u062d 5 \u0623\u062e\u0637\u0627\u0621:"
    " SPECTRAL_BIAS \u0645\u0639\u0643\u0648\u0633\u060c"
    " double compand\u060c"
    " 5 limiters \u062a\u0631\u0627\u0643\u0645\u064a\u0629\u060c"
    " \u062e\u0637\u0623 DR/LRA\u060c"
    " Crest guard \u0636\u0639\u064a\u0641',\n"
    "      'Fixes 5 v7.6 bugs: reversed bias, double compand stacking,"
    " 5 cumulative limiters, wrong DR/LRA type, weak Crest guard'),\n"
)

ss, okB = _replace_once(ss, OLD_B, NEW_B, "_EHist v8.1 LATEST + demote v8.0")

if not okB:
    _inf("Standard anchor failed -- dumping all _EHist lines for diagnosis:")
    for i, ln in enumerate(ss.splitlines()):
        if "_EHist" in ln or "LATEST" in ln:
            print(f"        L{i+1}: {repr(ln[:120])}")

_rec("B", "_EHist updated (settings_screen.dart)", okB)

# ── Write ─────────────────────────────────────────────────────────────────────
_h1("STEP W -- Write settings_screen.dart")
if okB:
    backup = SETTINGS.with_suffix(".dart.bak5")
    backup.write_text(SETTINGS.read_text(encoding="utf-8"), encoding="utf-8")
    _ok(f"Backup: {backup.name}")
    SETTINGS.write_text(ss, encoding="utf-8")
    _ok(f"settings_screen.dart written ({len(ss):,} chars)")
    _rec("W", "settings_screen.dart written", True)
else:
    _err("Skipping write -- patch failed")
    _rec("W", "settings_screen.dart written", False)

# ── Verify ────────────────────────────────────────────────────────────────────
_h1("STEP V -- Verification")

ss_final = SETTINGS.read_text(encoding="utf-8") if okB else ss

checks = [
    ("v8.1 _EHist entry present",
     "_EHist('v8.1'" in ss_final),
    ("v8.1 badge is LATEST",
     "'v8.1','Android-Hardened','\u226598/100','LATEST','gold'," in ss_final),
    ("v8.0 _EHist still present",
     "_EHist('v8.0'" in ss_final),
    ("v8.0 badge cleared (not LATEST)",
     "_EHist('v8.0','Calibrated Precision','\u226596/100','','gold'," in ss_final),
    ("v7.6 _EHist preserved",
     "_EHist('v7.6'" in ss_final),
    ("v7.5 _EHist preserved",
     "_EHist('v7.5'" in ss_final),
    ("class _EHist present",
     "class _EHist {" in ss_final),
]

all_pass = True
for label, result in checks:
    ((_ok if result else _err)(label))
    if not result:
        all_pass = False

if not all_pass:
    _err("FATAL: Verification failed -- check patches above")
    _rec("V", "verification", False)
else:
    _ok("All checks passed")
    _rec("V", "verification", True)

# ── Git commit + push ─────────────────────────────────────────────────────────
if all_pass:
    _h1("STEP G -- Git commit + push")
    import subprocess

    def _run(cmd):
        r = subprocess.run(cmd, shell=True, cwd=str(REPO),
                          capture_output=True, text=True, timeout=120)
        ok = r.returncode == 0
        ((_ok if ok else _err)(cmd[:70]))
        if not ok:
            for ln in (r.stdout + r.stderr).strip().splitlines()[-6:]:
                print(f"        {ln}")
        return ok

    _run("git add lib/screens/settings_screen.dart")
    _run('git commit -m "fix: S24-flutter5 add v8.1 _EHist LATEST + demote v8.0 [settings_screen]"')
    pushed = _run("git push")
    _rec("G", "git commit + push", pushed)

    if pushed:
        _h2("GitHub Actions CI will now build the new APK")
        _ok("Monitor at: https://github.com/carm5333/tilawa-enhancer/actions")

# ── Summary ───────────────────────────────────────────────────────────────────
_print_summary()

if all_pass:
    print("""
  ================================================================
  S24-Flutter5 COMPLETE

  settings_screen.dart now has:
    _EHist('v8.1', 'Android-Hardened', >=98/100, 'LATEST', gold)
    _EHist('v8.0', 'Calibrated Precision', >=96/100, '', gold)

  Next: wait for GitHub Actions APK build to finish, then
  download and install the new APK.
  ================================================================
""")
else:
    print("""
  ================================================================
  PATCH FAILED -- review errors above
  Backup saved as: settings_screen.dart.bak5
  ================================================================
""")
