#!/usr/bin/env python3
"""
tilawa_fix_s22.py  v2  --  S22 Fix Script
==========================================
Corrected anchors based on diagnostic output (April 13 2026).

ROOT CAUSE of 79% freeze (confirmed):
  `catch (_) {}` in _startPolling silently swallows ALL poll errors.
  When the HF Space restarts (e.g. after reference files are re-deployed),
  the job_id is gone. Every 2s poll throws SocketException / gets bad JSON.
  The catch eats it. _busy stays true, _progress stays 0.79. UI frozen
  permanently. User must force-kill the app.

CHANGES (all in lib/screens/home_screen.dart):
  A. Add _pollErrors + _processStart state variables
  B. _startPolling: reset _pollErrors = 0 at session start
  C. _process: record _processStart timestamp + reset _pollErrors
  D. Polling loop: reset _pollErrors = 0 on each SUCCESSFUL poll tick
  E. Replace catch(_){} with:
       - error counter (abort + bilingual SnackBar after 5 errors ~10s)
       - 25-minute hard timeout (bilingual SnackBar)
       - _checkServer() call to immediately refresh server banner
"""

from pathlib import Path
import shutil, sys
from datetime import datetime

PASS = "PASS"
FAIL = "FAIL"
_results = []

def _h1(t):
    bar = "=" * 70
    print(f"\n{bar}\n  {t}\n{bar}")

def _h2(t): print(f"\n  -- {t}")
def _ok(m):  print(f"     OK  {m}")
def _warn(m): print(f"     !! {m}")
def _err(m): print(f"     XX {m}")

def _record(sid, label, ok):
    _results.append((sid, label, PASS if ok else FAIL))

def _read(p):  return Path(p).read_text(encoding="utf-8")
def _write(p, t): Path(p).write_text(t, encoding="utf-8")

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f"Anchor NOT found -- {label}")
        return text, False
    if c > 1:
        _warn(f"Anchor appears {c}x -- replacing FIRST -- {label}")
    _ok(f"Replaced 1 occurrence -- {label}")
    return text.replace(old, new, 1), True

# =========================================================================
_h1("STEP 1 -- PREPARATION")

_h2("1.1  Verify repo root")
REQUIRED = ["lib/screens/home_screen.dart",
            "lib/services/api_service.dart",
            "pubspec.yaml"]
missing = [p for p in REQUIRED if not Path(p).exists()]
if missing:
    for m in missing: _err(f"Not found: {m}")
    print("\n  Run from repo root (~/tilawa-enhancer).")
    sys.exit(1)
_ok("All sentinel files present")
_record("1.1", "Repo root verified", True)

_h2("1.2  Read file + detect partial patch from v1 run")
home_raw = _read("lib/screens/home_screen.dart")
_ok(f"Read {len(home_raw):,} chars")
if "_pollErrors" in home_raw:
    _warn("_pollErrors already in file -- v1 partially applied, restoring backup")
    backups = sorted(Path(".fix_backups").glob("*/home_screen.dart"))
    if backups:
        latest = backups[-1]
        shutil.copy2(latest, "lib/screens/home_screen.dart")
        home_raw = _read("lib/screens/home_screen.dart")
        _ok(f"Restored from {latest} ({len(home_raw):,} chars)")
    else:
        _err("No backup found. Cannot restore. Aborting.")
        sys.exit(1)
else:
    _ok("File is clean")
_record("1.2", "home_screen.dart ready", True)

_h2("1.3  Create backup")
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
BACKUP_DIR = Path(f".fix_backups/{TS}")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
shutil.copy2("lib/screens/home_screen.dart", BACKUP_DIR / "home_screen.dart")
_ok(f"Backed up to {BACKUP_DIR}/home_screen.dart")
_record("1.3", "Backup created", True)

# =========================================================================
_h1("STEP 2 -- DEFINE ANCHORS (verified against diagnostic output)")

home = home_raw

# ── A: state variables ────────────────────────────────────────────────────
OLD_STATE = (
    "  bool    _isMerging  = false; // S20-A: true during server chunk-merge phase\n"
)
NEW_STATE = (
    "  bool    _isMerging  = false; // S20-A: true during server chunk-merge phase\n"
    "  int     _pollErrors = 0;     // S22: consecutive poll error counter\n"
    "  DateTime? _processStart;     // S22: start time for 25-min hard timeout\n"
)

# ── B: reset at _startPolling() entry ────────────────────────────────────
OLD_STARTPOLL = (
    "  void _startPolling() {\n"
    "    _pollTimer?.cancel();\n"
    "    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {\n"
)
NEW_STARTPOLL = (
    "  void _startPolling() {\n"
    "    _pollTimer?.cancel();\n"
    "    _pollErrors = 0; // S22: fresh counter for each new polling session\n"
    "    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {\n"
)

# ── C: timestamp in _process() ───────────────────────────────────────────
OLD_PROCESS = (
    "    setState(() {\n"
    "      _busy = true; _progress = 0.02;\n"
    "      _status = LangProvider.strings(context).uploading;\n"
    "      _output = null; _result = null;\n"
    "    });\n"
)
NEW_PROCESS = (
    "    setState(() {\n"
    "      _busy = true; _progress = 0.02;\n"
    "      _status = LangProvider.strings(context).uploading;\n"
    "      _output = null; _result = null;\n"
    "    });\n"
    "    _processStart = DateTime.now(); // S22: start clock for timeout\n"
    "    _pollErrors = 0;               // S22: reset in case of re-process\n"
)

# ── D: reset on successful poll ──────────────────────────────────────────
OLD_MID = (
    "        setState(() { _progress = display; _status = st['label'] ?? ''; _isMerging = isMerging && _busy; });\n"
)
NEW_MID = (
    "        _pollErrors = 0; // S22: reset on successful poll\n"
    "        setState(() { _progress = display; _status = st['label'] ?? ''; _isMerging = isMerging && _busy; });\n"
)

# ── E: replace silent catch block (anchor confirmed from diagnostic) ──────
# Line 205: '      } catch (_) {} // only poll errors silently ignored'
# Line 206: '    });'
# Line 207: '  }'
# No Unicode box-drawing chars in this anchor.
OLD_CATCH = (
    "      } catch (_) {} // only poll errors silently ignored\n"
    "    });\n"
    "  }\n"
)

NEW_CATCH = (
    "      } catch (_) {\n"
    "        // S22: surface poll errors -- do NOT silently swallow.\n"
    "        // Root cause of the 79% freeze: server restart kills the job.\n"
    "        // Every poll throws SocketException / returns bad JSON.\n"
    "        // Old catch(_){} hid this completely forever.\n"
    "        _pollErrors++;\n"
    "        if (_pollErrors >= 5 && mounted) {\n"
    "          // 5 errors = ~10 seconds of failure. Server is gone.\n"
    "          _pollTimer?.cancel();\n"
    "          final s = LangProvider.strings(context);\n"
    "          setState(() {\n"
    "            _busy = false; _isMerging = false;\n"
    "            _progress = 0; _status = '';\n"
    "          });\n"
    "          _checkServer(); // S22: immediately refresh server status banner\n"
    "          ScaffoldMessenger.of(context).showSnackBar(SnackBar(\n"
    "            content: Text(\n"
    "              s.ar\n"
    "                ? '\u26a0\ufe0f \u0627\u0646\u0642\u0637\u0639 \u0627\u0644\u0627\u062a\u0635\u0627\u0644 \u0628\u0627\u0644\u062e\u0627\u062f\u0645. \u0627\u0646\u062a\u0638\u0631 30 \u062b\u0627\u0646\u064a\u0629\u060c \u0646\u0628\u0651\u0647 \u0627\u0644\u062e\u0627\u062f\u0645\u060c \u062b\u0645 \u0623\u0639\u062f \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629.'\n"
    "                : '\u26a0\ufe0f Lost connection to server. Wait 30s, wake the server, then retry.',\n"
    "              style: const TextStyle(fontSize: 12)),\n"
    "            backgroundColor: const Color(0xFF200D0D),\n"
    "            duration: const Duration(seconds: 10),\n"
    "            action: SnackBarAction(\n"
    "              label: s.ar ? '\u062d\u0633\u0646\u0627\u064b' : 'OK',\n"
    "              textColor: const Color(0xFFD4AF37),\n"
    "              onPressed: () {})));\n"
    "          return;\n"
    "        }\n"
    "      }\n"
    "      // S22: 25-minute hard timeout. v8.0 on a large file runs 4 WAV\n"
    "      // passes which can take 20-40 min on free HF CPU. Show this\n"
    "      // instead of freezing at whatever % the server was at.\n"
    "      if (_busy && _processStart != null && mounted) {\n"
    "        final elapsed = DateTime.now().difference(_processStart!);\n"
    "        if (elapsed.inMinutes >= 25) {\n"
    "          _pollTimer?.cancel();\n"
    "          final s = LangProvider.strings(context);\n"
    "          setState(() {\n"
    "            _busy = false; _isMerging = false;\n"
    "            _progress = 0; _status = '';\n"
    "          });\n"
    "          _checkServer();\n"
    "          ScaffoldMessenger.of(context).showSnackBar(SnackBar(\n"
    "            content: Text(\n"
    "              s.ar\n"
    "                ? '\u23f1\ufe0f \u0627\u0633\u062a\u063a\u0631\u0642\u062a \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629 \u0623\u0643\u062b\u0631 \u0645\u0646 25 \u062f\u0642\u064a\u0642\u0629. \u062c\u0631\u0651\u0628 \u0645\u062d\u0631\u0643 v7.0 \u0623\u0648 \u0623\u0639\u062f \u0627\u0644\u0645\u062d\u0627\u0648\u0644\u0629 \u0644\u0627\u062d\u0642\u0627\u064b.'\n"
    "                : '\u23f1\ufe0f Processing exceeded 25 min. Try v7.0 engine or retry later.',\n"
    "              style: const TextStyle(fontSize: 12)),\n"
    "            backgroundColor: const Color(0xFF200D0D),\n"
    "            duration: const Duration(seconds: 12),\n"
    "            action: SnackBarAction(\n"
    "              label: s.ar ? '\u062d\u0633\u0646\u0627\u064b' : 'OK',\n"
    "              textColor: const Color(0xFFD4AF37),\n"
    "              onPressed: () {})));\n"
    "        }\n"
    "      }\n"
    "    });\n"
    "  }\n"
)

_h2("2.1  Verify all 5 anchors exist before touching the file")
anchors = [
    (OLD_STATE,     "A: state variables"),
    (OLD_STARTPOLL, "B: _startPolling entry"),
    (OLD_PROCESS,   "C: _process setState"),
    (OLD_MID,       "D: mid-poll setState"),
    (OLD_CATCH,     "E: silent catch block"),
]
all_found = True
for old, label in anchors:
    c = home.count(old)
    found = c == 1
    ((_ok if found else _err)(f"{'FOUND' if found else f'MISSING (count={c})'} -- {label}"))
    if not found: all_found = False

_record("2.1", "All 5 anchors found", all_found)
if not all_found:
    print("\n  Aborting -- one or more anchors missing. File NOT modified.")
    sys.exit(1)

# =========================================================================
_h1("STEP 3 -- APPLY")

_h2("3.1  A: state variables")
home, r1 = _replace_once(home, OLD_STATE,     NEW_STATE,     "state vars")
_record("3.1", "State vars", r1)

_h2("3.2  B: _startPolling reset")
home, r2 = _replace_once(home, OLD_STARTPOLL, NEW_STARTPOLL, "_startPolling reset")
_record("3.2", "_startPolling reset", r2)

_h2("3.3  C: _process timestamp")
home, r3 = _replace_once(home, OLD_PROCESS,   NEW_PROCESS,   "_process timestamp")
_record("3.3", "_process timestamp", r3)

_h2("3.4  D: mid-poll reset")
home, r4 = _replace_once(home, OLD_MID,       NEW_MID,       "mid-poll reset")
_record("3.4", "mid-poll reset", r4)

_h2("3.5  E: catch block")
home, r5 = _replace_once(home, OLD_CATCH,     NEW_CATCH,     "catch block")
_record("3.5", "catch block", r5)

_h2("3.6  Write (only if all 5 succeeded)")
if r1 and r2 and r3 and r4 and r5:
    _write("lib/screens/home_screen.dart", home)
    wrote = len(_read("lib/screens/home_screen.dart"))
    _ok(f"Written {wrote:,} chars (was {len(home_raw):,}, delta +{wrote - len(home_raw):,})")
    _record("3.6", "File written", True)
else:
    _err("One or more replacements failed -- NOT writing")
    _record("3.6", "File written", False)
    sys.exit(1)

# =========================================================================
_h1("STEP 4 -- VERIFY")

v = _read("lib/screens/home_screen.dart")

checks = [
    ("_pollErrors = 0;     // S22" in v,                    "4.1", "_pollErrors declaration"),
    ("_processStart;     // S22" in v,                      "4.2", "_processStart declaration"),
    ("fresh counter for each new polling session" in v,     "4.3", "_startPolling reset comment"),
    ("_processStart = DateTime.now();" in v,                "4.4", "_processStart = DateTime.now()"),
    ("reset in case of re-process" in v,                    "4.5", "_pollErrors reset in _process"),
    ("_pollErrors = 0; // S22: reset on successful poll" in v, "4.6", "successful-poll reset"),
    ("} catch (_) {} // only poll errors silently ignored" not in v, "4.7", "old silent catch GONE"),
    ("_pollErrors++;" in v,                                 "4.8", "_pollErrors++ counter"),
    ("_pollErrors >= 5" in v,                               "4.9", "5-error abort threshold"),
    ("_checkServer();" in v,                                "4.10","_checkServer() after abort"),
    ("inMinutes >= 25" in v,                                "4.11","25-min timeout check"),
    ("Lost connection to server" in v,                      "4.12","EN disconnect message"),
    ("Processing exceeded 25 min" in v,                     "4.13","EN timeout message"),
]

all_ok = True
for ok, sid, label in checks:
    ((_ok if ok else _err)(f"[{sid}] {label}"))
    _record(sid, label, ok)
    if not ok: all_ok = False

_h2("Brace balance")
opens  = v.count('{')
closes = v.count('}')
diff   = abs(opens - closes)
bal_ok = diff <= 5
((_ok if bal_ok else _warn)(f"opens={opens} closes={closes} diff={diff}"))
_record("4.B", "Brace balance", bal_ok)

# =========================================================================
_h1("STEP 5 -- SUMMARY")

print()
print(f"     {'Step':<6}  {'Label':<50}  Result")
print(f"     {'----':<6}  {'-----':<50}  ------")
all_pass = True
for sid, lbl, sts in _results:
    icon = "OK" if sts == PASS else "XX"
    print(f"     {sid:<6}  {lbl:<50}  [{icon}] {sts}")
    if sts == FAIL: all_pass = False

print()
if all_pass:
    print("  " + "=" * 68)
    print("  ALL CHECKS PASSED")
    print()
    print("  git add lib/screens/home_screen.dart")
    print("  git commit -m \"fix: S22 surface poll errors + 25min timeout\"")
    print("  git push")
    print()
    print(f"  Backup: {BACKUP_DIR}/home_screen.dart")
    print("  " + "=" * 68)
else:
    print("  " + "=" * 68)
    print("  SOME CHECKS FAILED")
    print(f"  Backup: {BACKUP_DIR}/home_screen.dart")
    print("  " + "=" * 68)
    sys.exit(1)
