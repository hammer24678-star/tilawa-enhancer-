#!/usr/bin/env python3
"""
patch_s31_fixes.py — 4 user-reported fixes

  F1. Welcome screen shows on every app launch (not just first install)
  F2. Light mode actually changes visible UI (scaffold/appbar/card colors)
  F3. Remove v8.7 "Studied Ceiling" from engine list
  F4. Unselected engine text: remove muted gold, use neutral grey

Run from ~/tilawa-enhancer/ then git push.
"""

from pathlib import Path
import sys

REPO     = Path(".")
MAIN     = REPO / "lib/main.dart"
HOME     = REPO / "lib/screens/home_screen.dart"
HISTORY  = REPO / "lib/screens/history_screen.dart"
SETTINGS = REPO / "lib/screens/settings_screen.dart"
WELCOME  = REPO / "lib/screens/welcome_screen.dart"

OK   = "\033[92m OK  \033[0m"
SKIP = "\033[94m SKIP\033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"

errors = 0

def patch(path: Path, old: str, new: str, label: str,
          skip_if: str = "") -> bool:
    global errors
    if not path.exists():
        print(f"{ERR} [{path.name}] file not found — {label}")
        errors += 1; return False
    text = path.read_text(encoding="utf-8")
    if skip_if and skip_if in text:
        print(f"{SKIP} [{path.name}] already applied — {label}")
        return True
    if old not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label}")
        # debug: first line of anchor
        hint = old.split('\n')[0]
        idx = text.find(hint)
        if idx != -1:
            print(f"       hint at {idx}: {repr(text[max(0,idx-10):idx+60])}")
        errors += 1; return False
    if text.count(old) > 1:
        print(f"{WARN} [{path.name}] anchor not unique — {label}")
        errors += 1; return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{OK}  [{path.name}] {label}")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# F1 — Welcome screen always shows on launch
# ═══════════════════════════════════════════════════════════════════════════
print("\n[F1] main.dart — welcome screen always on launch")

patch(MAIN,
    "                  home: widget.seenWelcome\n"
    "                      ? const HomeScreen()\n"
    "                      : const WelcomeScreen(),",
    "                  home: const WelcomeScreen(), // S31-F1: always show on launch",
    label="F1: always start with WelcomeScreen",
    skip_if="S31-F1: always show on launch",
)


# ═══════════════════════════════════════════════════════════════════════════
# F2 — Light mode: make scaffold + appbar + key containers theme-aware
#
# Strategy: add _isDark(ctx) helper, replace hardcoded backgrounds with
# conditional expressions. Targets: scaffold bg, appbar bg, card bg,
# primary container bg, border color, primary text, secondary text.
# ═══════════════════════════════════════════════════════════════════════════
print("\n[F2] Light mode — scaffold/appbar/card colors theme-aware")

# ── F2-A: inject _isDark helper + color consts right after the imports
#    in main.dart (after the last import line)
# ────────────────────────────────────────────────────────────────────────
MAIN_HELPER = (
    "// ── S31-F2: App-wide color helpers ─────────────────────────────────────────\n"
    "// Call these anywhere you have a BuildContext instead of hardcoding colours.\n"
    "// Dark palette  : #080A0E bg / #161B22 card / #21262D border\n"
    "// Light palette : #FAF7EE bg / #F3EED9 card / #D4C99A border\n"
    "bool   _isDark(BuildContext ctx) => ThemeProvider.isDark(ctx);\n"
    "Color  _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n"
    "Color  _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);\n"
    "Color  _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);\n"
    "Color  _cText(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFC9D1D9) : const Color(0xFF1A1400);\n"
    "Color  _cSub(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);\n"
    "Color  _cDim(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF484F58) : const Color(0xFF8B7B5A);\n"
    "Color  _cGold(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);\n"
)

patch(MAIN,
    "import 'screens/home_screen.dart';\n"
    "\n"
    "void main()",
    "import 'screens/home_screen.dart';\n"
    "\n"
    + MAIN_HELPER
    + "\nvoid main()",
    label="F2-A: inject _isDark / _cBg / _cCard / _cGold helpers in main.dart",
    skip_if="S31-F2: App-wide color helpers",
)

# ── F2-B: home_screen.dart — Scaffold + gradient background
patch(HOME,
    "    return Scaffold(\n"
    "      backgroundColor: const Color(0xFF080A0E),\n"
    "      body: Container(\n"
    "        decoration: const BoxDecoration(\n"
    "          gradient: LinearGradient(\n"
    "            begin: Alignment.topCenter,\n"
    "            end: Alignment.bottomCenter,\n"
    "            colors: [Color(0xFF080A0E), Color(0xFF0C1018)])),",
    "    final dark = _isDark(context);\n"
    "    final cBg     = _cBg(context);\n"
    "    final cCard   = _cCard(context);\n"
    "    final cBorder = _cBorder(context);\n"
    "    final cText   = _cText(context);\n"
    "    final cSub    = _cSub(context);\n"
    "    final cDim    = _cDim(context);\n"
    "    final cGold   = _cGold(context);\n"
    "    return Scaffold(\n"
    "      backgroundColor: cBg,\n"
    "      body: Container(\n"
    "        decoration: BoxDecoration(\n"
    "          gradient: LinearGradient(\n"
    "            begin: Alignment.topCenter,\n"
    "            end: Alignment.bottomCenter,\n"
    "            colors: dark\n"
    "              ? [const Color(0xFF080A0E), const Color(0xFF0C1018)]\n"
    "              : [const Color(0xFFFAF7EE), const Color(0xFFF5F0E0)])),",
    label="F2-B: home_screen Scaffold + gradient theme-aware",
    skip_if="final dark = _isDark(context);",
)

# ── F2-C: history_screen.dart Scaffold + AppBar
patch(HISTORY,
    "    return Scaffold(\n"
    "      backgroundColor: const Color(0xFF0A0C10),\n"
    "      appBar: AppBar(\n"
    "        title: Text(s.historyTitle, style: const TextStyle(\n"
    "          color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),\n"
    "        backgroundColor: const Color(0xFF0A0C10),\n"
    "        iconTheme: const IconThemeData(color: Color(0xFFD4AF37)),",
    "    final cBg   = _cBg(context);\n"
    "    final cGold = _cGold(context);\n"
    "    return Scaffold(\n"
    "      backgroundColor: cBg,\n"
    "      appBar: AppBar(\n"
    "        title: Text(s.historyTitle, style: TextStyle(\n"
    "          color: cGold, fontWeight: FontWeight.bold)),\n"
    "        backgroundColor: cBg,\n"
    "        iconTheme: IconThemeData(color: cGold),",
    label="F2-C: history_screen Scaffold + AppBar theme-aware",
    skip_if="final cGold = _cGold(context);\n    return Scaffold(",
)

# history needs the import of main helpers — they're top-level functions
# in main.dart which is imported by main.dart itself. But history_screen
# doesn't import main.dart. Add a relative import.
HIST_TEXT = HISTORY.read_text(encoding="utf-8") if HISTORY.exists() else ""
if "../main.dart" not in HIST_TEXT and "package:tilawa_enhancer/main.dart" not in HIST_TEXT:
    patch(HISTORY,
        "import 'package:flutter/material.dart';",
        "import 'package:flutter/material.dart';\n"
        "import '../main.dart' show _isDark, _cBg, _cCard, _cBorder, _cText, _cSub, _cDim, _cGold; // S31-F2",
        label="F2-C2: history_screen imports color helpers",
        skip_if="show _isDark",
    )

# ── F2-D: settings_screen.dart Scaffold + AppBar
patch(SETTINGS,
    "    return Scaffold(\n"
    "      backgroundColor: const Color(0xFF0A0C10),\n"
    "      appBar: AppBar(\n"
    "        title: Text(s.settings, style: const TextStyle(\n"
    "          color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),\n"
    "        backgroundColor: const Color(0xFF0A0C10),\n"
    "        iconTheme: const IconThemeData(color: Color(0xFFD4AF37)),",
    "    final cBg   = _cBg(context);\n"
    "    final cGold = _cGold(context);\n"
    "    return Scaffold(\n"
    "      backgroundColor: cBg,\n"
    "      appBar: AppBar(\n"
    "        title: Text(s.settings, style: TextStyle(\n"
    "          color: cGold, fontWeight: FontWeight.bold)),\n"
    "        backgroundColor: cBg,\n"
    "        iconTheme: IconThemeData(color: cGold),",
    label="F2-D: settings_screen Scaffold + AppBar theme-aware",
    skip_if="final cBg   = _cBg(context);\n    final cGold = _cGold(context);\n    return Scaffold(\n      backgroundColor: cBg,\n      appBar: AppBar(\n        title: Text(s.settings",
)

SETT_TEXT = SETTINGS.read_text(encoding="utf-8") if SETTINGS.exists() else ""
if "show _isDark" not in SETT_TEXT:
    patch(SETTINGS,
        "import 'package:flutter/material.dart';",
        "import 'package:flutter/material.dart';\n"
        "import '../main.dart' show _isDark, _cBg, _cCard, _cBorder, _cText, _cSub, _cDim, _cGold; // S31-F2",
        label="F2-D2: settings_screen imports color helpers",
        skip_if="show _isDark",
    )

# ── F2-E: welcome_screen.dart Scaffold
patch(WELCOME,
    "    return Scaffold(\n"
    "      backgroundColor: const Color(0xFF0A0C10),",
    "    return Scaffold(\n"
    "      backgroundColor: _cBg(context),",
    label="F2-E: welcome_screen Scaffold theme-aware",
    skip_if="backgroundColor: _cBg(context),",
)

WELC_TEXT = WELCOME.read_text(encoding="utf-8") if WELCOME.exists() else ""
if "show _isDark" not in WELC_TEXT:
    patch(WELCOME,
        "import 'package:flutter/material.dart';",
        "import 'package:flutter/material.dart';\n"
        "import '../main.dart' show _isDark, _cBg, _cCard, _cBorder, _cText, _cSub, _cDim, _cGold; // S31-F2",
        label="F2-E2: welcome_screen imports color helpers",
        skip_if="show _isDark",
    )

# ── F2-F: home_screen imports color helpers from main.dart
HOME_TEXT = HOME.read_text(encoding="utf-8") if HOME.exists() else ""
if "show _isDark" not in HOME_TEXT:
    patch(HOME,
        "import 'dart:async';",
        "import 'dart:async';\n"
        "import '../main.dart' show _isDark, _cBg, _cCard, _cBorder, _cText, _cSub, _cDim, _cGold; // S31-F2",
        label="F2-F: home_screen imports color helpers",
        skip_if="show _isDark",
    )


# ═══════════════════════════════════════════════════════════════════════════
# F3 — Remove v8.7 from engine list in home_screen.dart
# ═══════════════════════════════════════════════════════════════════════════
print("\n[F3] home_screen.dart — remove v8.7 engine entry")

patch(HOME,
    "    // v8.9 removed S31\n"
    "    _EngineData(\n"
    "      'v8.7', '\u0633\u0642\u0641 \u0645\u062f\u0631\u0648\u0633', 'Studied Ceiling', 99.0,\n"
    "      '', 'gold',\n"
    "      ['Bitrate Floor', 'Phrase 3s Min', 'Do-No-Harm Fix', 'LUFS \u00b118dB', 'LRA Sliding', 'Joint \u00b118dB'],\n"
    "      '\u0625\u0635\u0644\u0627\u062d 6 \u0623\u062e\u0637\u0627\u0621 \u062d\u0631\u062c\u0629 \u0645\u0646 v8.5: \u062d\u062f \u0623\u062f\u0646\u0649 \u0644\u0645\u0639\u062f\u0644 \u0627\u0644\u0628\u062a \u064a\u0645\u0646\u0639 \u062a\u0635\u0646\u064a\u0641 \u0627\u0644\u0645\u0644\u0641\u0627\u062a \u0627\u0644\u0647\u0627\u062f\u0626\u0629 \u062e\u0637\u0623\u064b\u060c \u0644\u0627 \u064a\u064f\u0634\u063a\u0651\u0644 \u062a\u0642\u062f\u064a\u0631 LRA \u0625\u0644\u0627 \u0644\u0645\u0642\u0627\u0637\u0639 \u0623\u0637\u0648\u0644 \u0645\u0646 3 \u062b\u0648\u0627\u0646\u060c \u0645\u0642\u0627\u0631\u0646\u0629 Do-No-Harm \u0628\u0640 Crest \u0627\u0644\u0642\u0627\u0628\u0644 \u0644\u0644\u062a\u062d\u0642\u0642\u060c \u0646\u0637\u0627\u0642 \u0642\u0637\u0639 LUFS \u00b118dB\u060c \u0646\u0627\u0641\u0630\u0629 \u0627\u0646\u0632\u0644\u0627\u0642 \u0648\u0633\u064a\u0637\u0629 \u0644\u0640 LRA\u060c \u0646\u0637\u0627\u0642 \u00b118dB \u0644\u0644\u0643\u0633\u0628 \u0627\u0644\u0645\u0634\u062a\u0631\u0643.',\n"
    "      '6 critical fixes from v8.5: bitrate floor stops quiet-file misclassification, phrase LRA requires 3s minimum, Do-No-Harm compares to achievable Crest, \u00b118dB LUFS trim range, sliding window median for LRA, \u00b118dB joint gain range.',\n"
    "    ),",
    "    // v8.9 removed S31 | v8.7 removed S31-F3",
    label="F3: v8.7 entry removed from engine list",
    skip_if="v8.7 removed S31-F3",
)


# ═══════════════════════════════════════════════════════════════════════════
# F4 — Unselected engine text: remove muted-gold, use clean grey
# ═══════════════════════════════════════════════════════════════════════════
print("\n[F4] home_screen.dart — unselected engine text colour")

# Engine ID text (name like "v9.0")
patch(HOME,
    "                    color: sel ? col\n"
    "                      : (e.bc == 'gold'\n"
    "                          ? const Color(0xFF8B7535)\n"
    "                          : const Color(0xFFC9D1D9)),",
    "                    color: sel ? col : const Color(0xFFC9D1D9), // S31-F4",
    label="F4a: engine ID text — no muted gold when unselected",
    skip_if="S31-F4",
)

# Score text ("≥99")
patch(HOME,
    "                  color: sel ? col\n"
    "                    : (e.bc == 'gold'\n"
    "                        ? const Color(0xFF6B5A2A)\n"
    "                        : const Color(0xFF484F58)),",
    "                  color: sel ? col : const Color(0xFF484F58), // S31-F4",
    label="F4b: engine score text — no muted gold when unselected",
    skip_if="0xFF484F58), // S31-F4",
)


# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL FIXES APPLIED \033[0m")
    print()
    print("Changes:")
    print("  F1. Welcome screen shows on every app launch")
    print("  F2. Light mode: scaffold/appbar backgrounds adapt to theme")
    print("  F3. v8.7 removed from engine selector")
    print("  F4. Unselected engine text is clean grey (not muted gold)")
    print()
    print("Next:")
    print("  git add lib/main.dart \\")
    print("          lib/screens/home_screen.dart \\")
    print("          lib/screens/history_screen.dart \\")
    print("          lib/screens/settings_screen.dart \\")
    print("          lib/screens/welcome_screen.dart")
    print("  git commit -m 'S31: welcome always, light mode, rm v8.7, grey engine text'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} FIX(ES) FAILED — check WARN lines above \033[0m")
    sys.exit(1)
