#!/usr/bin/env python3
"""
patch_v10_flutter.py — Add v10.0 engine, remove v8.9, update defaults

Changes:
  home_screen.dart  — _engines list: add v10.0 at top, remove v8.9
  home_screen.dart  — default _engine state: 'v9.0' → 'v10.0'
  home_screen.dart  — engineNames map in result card: add v10.0 entry
  api_service.dart  — loadLastEngine default: 'v9.0' → 'v10.0'
"""

from pathlib import Path
import sys

REPO = Path(".")
HOME = REPO / "lib/screens/home_screen.dart"
API  = REPO / "lib/services/api_service.dart"

OK   = "\033[92m OK  \033[0m"
SKIP = "\033[94m SKIP\033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"
errors = 0

def patch(path, old, new, label):
    global errors
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label}"); return False
    if text.count(old) > 1:
        print(f"{WARN} [{path.name}] anchor not unique — {label}"); errors += 1; return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{OK}  [{path.name}] {label}")
    return True

def already(path, marker, label):
    if marker in path.read_text(encoding="utf-8"):
        print(f"{SKIP} [{path.name}] already applied — {label}")
        return True
    return False

print("\n[home_screen.dart]")

# ── 1. Default engine state ────────────────────────────────────────────────
if not already(HOME, "  String  _engine    = 'v10.0';", "1: default engine v10.0"):
    patch(HOME,
        "  String  _engine    = 'v9.0';",
        "  String  _engine    = 'v10.0';",
        "1: default _engine → v10.0")

# ── 2. Add v10.0 to _engines list, remove v8.9 ────────────────────────────
if not already(HOME, "'v10.0', '\u0627\u0644\u0623\u062b\u064a\u0631\u064a\u0648\u0646", "2: v10.0 engine entry"):
    patch(HOME,
        "    _EngineData(\n"
        "      'v9.0', '\u0627\u0644\u062a\u0637\u0648\u0631', 'The Evolution', 99.0,\n"
        "      'LATEST', 'gold',",
        "    _EngineData(\n"
        "      'v10.0', '\u0627\u0644\u0623\u062b\u064a\u0631\u064a\u0648\u0646 \u2014 \u0627\u0644\u0623\u0633\u0627\u0633', 'Aetherion Foundation', 99.0,\n"
        "      'NEW', 'gold',\n"
        "      ['24 Fixes', 'Two-Stage NR', 'L-BFGS-B EQ', 'Joint Opt', 'Declip', 'v10 NR'],\n"
        "      '\u0662\u0664 \u0625\u0635\u0644\u0627\u062d\u0627\u064b \u062a\u0631\u0627\u0643\u0645\u064a\u0627\u064b \u0645\u0646 v9.0: \u062a\u062e\u0641\u064a\u0636 \u0636\u0648\u0636\u0627\u0621 \u062b\u0646\u0627\u0626\u064a \u2014 \u062a\u062d\u0633\u064a\u0646 \u0637\u064a\u0641\u064a L-BFGS-B \u2014 8 \u0625\u0635\u0644\u0627\u062d\u0627\u062a \u062d\u0631\u062c\u0629 \u0641\u064a LUFS \u0648LRA \u0648\u0645\u062f\u0649 \u0627\u0644\u062a\u0636\u062e\u064a\u0645.',\n"
        "      '24 cumulative fixes from v9.0: two-stage NR (hum + broadband), L-BFGS-B spectral EQ, 8 critical bug fixes including LUFS measurement and \u00b118dB joint gain range.',\n"
        "    ),\n"
        "    _EngineData(\n"
        "      'v9.0', '\u0627\u0644\u062a\u0637\u0648\u0631', 'The Evolution', 99.0,\n"
        "      'LATEST', 'gold',",
        "2: v10.0 added above v9.0")

# ── 3. Remove v8.9 from _engines list ─────────────────────────────────────
if not already(HOME, "// v8.9 removed S31", "3: v8.9 removed"):
    patch(HOME,
        "    _EngineData(\n"
        "      'v8.9', '\u062e\u0637\u0648\u0637 \u0646\u0627\u0639\u0645\u0629', 'Soft Tiers + LPC', 99.0,\n"
        "      '', 'gold',\n"
        "      ['Soft Tiers', 'LPC Sibilants', 'NR Guard', 'LUFS Fix', 'Smear EQ', 'dur_s'],\n"
        "      '\u0641\u0626\u0627\u062a \u062a\u062f\u0631\u064a\u062c\u064a\u0629 \u0628\u062f\u0644\u0627\u064b \u0645\u0646 \u0627\u0644\u062d\u062f\u0648\u062f \u0627\u0644\u062d\u0627\u062f\u0629 \u2014 \u062a\u062d\u0633\u064a\u0646 \u062f\u0642\u064a\u0642 \u0644\u0644\u062d\u0631\u0648\u0641 \u0627\u0644\u0627\u062d\u062a\u0643\u0627\u0643\u064a\u0629 \u0628\u0640 LPC \u2014 \u0625\u0635\u0644\u0627\u062d LUFS \u0628\u0639\u062f BSR.',\n"
        "      'Soft tier boundaries, LPC sibilant EQ, LUFS fix after BSR, NR depth guard.',\n"
        "    ),",
        "    // v8.9 removed S31",
        "3: v8.9 entry removed")

# ── 4. engineNames map in result card — add v10.0 ─────────────────────────
if not already(HOME, "'v10.0': 'Aetherion Foundation'", "4: v10.0 in engineNames map"):
    patch(HOME,
        "    const engineNames = {\n"
        "      'v9.0': 'The Evolution',",
        "    const engineNames = {\n"
        "      'v10.0': 'Aetherion Foundation',\n"
        "      'v9.0': 'The Evolution',",
        "4: v10.0 added to engineNames map")

# ── 5. Change v9.0 badge from LATEST to empty (v10 is new latest) ─────────
if not already(HOME, "// v9.0 badge cleared S31", "5: v9.0 LATEST badge cleared"):
    patch(HOME,
        "      'v9.0', '\u0627\u0644\u062a\u0637\u0648\u0631', 'The Evolution', 99.0,\n"
        "      'LATEST', 'gold',",
        "      'v9.0', '\u0627\u0644\u062a\u0637\u0648\u0631', 'The Evolution', 99.0,\n"
        "      '', 'gold', // v9.0 badge cleared S31",
        "5: v9.0 LATEST badge → empty")

print("\n[api_service.dart]")

# ── 6. loadLastEngine default engine ──────────────────────────────────────
if not already(API, "?? 'v10.0'", "6: loadLastEngine default v10.0"):
    patch(API,
        "      return prefs.getString(_lastEngineKey) ?? 'v9.0';",
        "      return prefs.getString(_lastEngineKey) ?? 'v10.0'; // S31",
        "6: loadLastEngine default → v10.0")

print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL PATCHES APPLIED \033[0m")
    print()
    print("Next:")
    print("  git add lib/screens/home_screen.dart \\")
    print("          lib/services/api_service.dart")
    print("  git commit -m 'S31: Add v10.0 Aetherion, remove v8.9'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} FAILED \033[0m"); sys.exit(1)
