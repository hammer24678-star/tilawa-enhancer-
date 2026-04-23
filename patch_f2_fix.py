#!/usr/bin/env python3
"""
patch_f2_fix.py — Fix broken S31-F2 color helpers

ROOT CAUSE
----------
patch_s31_fixes.py F2 injected call sites (_cBg(context), _cBorder(context),
etc.) into each screen's build() method, but defined the functions in main.dart
as library-PRIVATE top-level functions (names start with '_').

In Dart, library-private symbols (leading _) are invisible outside their
defining library — even with `import 'x.dart' show _foo`. The compiler
simply ignores private names in show clauses. Result: every screen gets
"method not defined" compile errors.

FIX APPLIED
-----------
1. Remove the broken `import '../main.dart' show _isDark, _cBg, ...` line
   from each screen (it does nothing useful).
2. Ensure `import '../main.dart' show ThemeProvider;` is present (ThemeProvider
   is public and already has a static isDark(ctx) method).
3. Inject the color helpers as PRIVATE INSTANCE METHODS directly into each
   affected class. Private inside the class = valid; private in another
   library = not visible.

FILES CHANGED
-------------
  lib/screens/home_screen.dart      (_HomeScreenState)
  lib/screens/history_screen.dart   (_HistoryScreenState)
  lib/screens/settings_screen.dart  (SettingsScreen — StatelessWidget)
  lib/screens/welcome_screen.dart   (_WelcomeScreenState)

Run from ~/tilawa-enhancer/ root, then commit + push.
"""

from pathlib import Path
import sys

REPO     = Path(".")
HOME     = REPO / "lib/screens/home_screen.dart"
HISTORY  = REPO / "lib/screens/history_screen.dart"
SETTINGS = REPO / "lib/screens/settings_screen.dart"
WELCOME  = REPO / "lib/screens/welcome_screen.dart"

OK   = "\033[92m OK  \033[0m"
SKIP = "\033[94m SKIP\033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"

errors = 0


def rw(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def ww(path: Path, text: str):
    path.write_text(text, encoding="utf-8")


# ── Step 1: fix imports in a file ────────────────────────────────────────────
def fix_imports(path: Path, label: str):
    """
    - Remove the broken 'show _isDark, _cBg, ...' import line if present.
    - Ensure 'import '../main.dart' show ThemeProvider;' is present.
    """
    global errors
    if not path.exists():
        print(f"{ERR} [{path.name}] file not found — {label}")
        errors += 1
        return

    text = rw(path)
    changed = False

    # ── Remove the broken private-show import ────────────────────────────────
    BAD = (
        "import '../main.dart' show "
        "_isDark, _cBg, _cCard, _cBorder, _cText, _cSub, _cDim, _cGold; // S31-F2\n"
    )
    if BAD in text:
        text = text.replace(BAD, "", 1)
        changed = True
        print(f"{OK}  [{path.name}] removed broken 'show _isDark' import")
    else:
        print(f"{SKIP} [{path.name}] broken import already absent")

    # ── Ensure ThemeProvider import is present ───────────────────────────────
    GOOD_MARKERS = [
        "show ThemeProvider",
        "import '../main.dart'",
    ]
    already = any(m in text for m in GOOD_MARKERS)
    if already:
        print(f"{SKIP} [{path.name}] ThemeProvider import already present")
    else:
        # Insert after `import 'package:flutter/material.dart';`
        FL = "import 'package:flutter/material.dart';"
        if FL in text:
            text = text.replace(
                FL,
                FL + "\nimport '../main.dart' show ThemeProvider; // S31-F2c",
                1,
            )
            changed = True
            print(f"{OK}  [{path.name}] added ThemeProvider import")
        else:
            print(f"{WARN} [{path.name}] flutter import line not found — {label}")
            errors += 1

    if changed:
        ww(path, text)


# ── Step 2: inject instance methods before a stable anchor ───────────────────
def inject_methods(path: Path, anchor: str, methods: str,
                   label: str, skip_if: str):
    global errors
    if not path.exists():
        print(f"{ERR} [{path.name}] file not found — {label}")
        errors += 1
        return

    text = rw(path)

    if skip_if in text:
        print(f"{SKIP} [{path.name}] already injected — {label}")
        return

    if anchor not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label}")
        # debug: show where first line of anchor appears
        first_line = anchor.split("\n")[0]
        idx = text.find(first_line)
        if idx != -1:
            print(
                f"       hint — first line found at char {idx}:\n"
                f"       {repr(text[max(0, idx - 30):idx + 100])}"
            )
        else:
            print(f"       first anchor line '{first_line}' NOT found in file")
        errors += 1
        return

    if text.count(anchor) > 1:
        print(f"{WARN} [{path.name}] anchor not unique — {label}")
        errors += 1
        return

    ww(path, text.replace(anchor, methods + anchor, 1))
    print(f"{OK}  [{path.name}] {label}")


# ═══════════════════════════════════════════════════════════════════════════
# Color helper bodies
# ═══════════════════════════════════════════════════════════════════════════

_FULL_HELPERS = """\
  // ── S31-F2c: theme color helpers (private instance methods) ────────────────
  // Dart library-private functions (_name) can't cross library boundaries, so
  // we define them here inside the class instead of importing from main.dart.
  bool  _isDark(BuildContext ctx)   => ThemeProvider.isDark(ctx);
  Color _cBg(BuildContext ctx)      => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);
  Color _cCard(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);
  Color _cBorder(BuildContext ctx)  => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);
  Color _cText(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFFC9D1D9) : const Color(0xFF1A1400);
  Color _cSub(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);
  Color _cDim(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF484F58) : const Color(0xFF8B7B5A);
  Color _cGold(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);

"""

_SMALL_HELPERS = """\
  // ── S31-F2c: theme color helpers (private instance methods) ────────────────
  bool  _isDark(BuildContext ctx) => ThemeProvider.isDark(ctx);
  Color _cBg(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);
  Color _cGold(BuildContext ctx)  => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);

"""

_WELC_HELPERS = """\
  // ── S31-F2c: theme color helpers (private instance methods) ────────────────
  bool  _isDark(BuildContext ctx) => ThemeProvider.isDark(ctx);
  Color _cBg(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);

"""

# ═══════════════════════════════════════════════════════════════════════════
# home_screen.dart — _HomeScreenState needs all 8 helpers
# Anchor: the BUILD section comment is stable and unique.
# ═══════════════════════════════════════════════════════════════════════════
print("\n[home_screen.dart]")

fix_imports(HOME, "home")

inject_methods(
    HOME,
    anchor=(
        "  // ── BUILD ──────────────────────────────────────────────────────────────────\n"
        "  @override\n"
        "  Widget build(BuildContext context) {"
    ),
    methods=_FULL_HELPERS,
    label="inject all 8 helpers into _HomeScreenState",
    skip_if="S31-F2c: theme color helpers",
)

# ═══════════════════════════════════════════════════════════════════════════
# history_screen.dart — _HistoryScreenState needs _cBg + _cGold
# Anchor: the build() signature + first two injected local vars.
# After F2-C, history build() starts with:
#   final s = ...
#   final cBg   = _cBg(context);
#   final cGold = _cGold(context);
# ═══════════════════════════════════════════════════════════════════════════
print("\n[history_screen.dart]")

fix_imports(HISTORY, "history")

inject_methods(
    HISTORY,
    anchor=(
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        "    final s = LangProvider.strings(context);\n"
        "    final cBg   = _cBg(context);"
    ),
    methods=_SMALL_HELPERS,
    label="inject _cBg/_cGold helpers into _HistoryScreenState",
    skip_if="S31-F2c: theme color helpers",
)

# ═══════════════════════════════════════════════════════════════════════════
# settings_screen.dart — SettingsScreen (StatelessWidget) needs _cBg + _cGold
# settings already had `import '../main.dart' show ThemeProvider;` (S31-F4b).
# Anchor: build() signature + isAr + first injected local var.
# After F2-D, settings build() looks like:
#   final s = ...
#   final isAr = s.ar;
#
#   final cBg   = _cBg(context);
# ═══════════════════════════════════════════════════════════════════════════
print("\n[settings_screen.dart]")

fix_imports(SETTINGS, "settings")

inject_methods(
    SETTINGS,
    anchor=(
        "  @override\n"
        "  Widget build(BuildContext context) {\n"
        "    final s = LangProvider.strings(context);\n"
        "    final isAr = s.ar;\n"
        "\n"
        "    final cBg   = _cBg(context);"
    ),
    methods=_SMALL_HELPERS,
    label="inject _cBg/_cGold helpers into SettingsScreen",
    skip_if="S31-F2c: theme color helpers",
)

# ═══════════════════════════════════════════════════════════════════════════
# welcome_screen.dart — _WelcomeScreenState needs only _cBg
# After F2-E, welcome scaffold has: backgroundColor: _cBg(context),
# Anchor: the build() override signature (unique in this file).
# ═══════════════════════════════════════════════════════════════════════════
print("\n[welcome_screen.dart]")

fix_imports(WELCOME, "welcome")

welc_text = rw(WELCOME) if WELCOME.exists() else ""
if "_cBg(context)" not in welc_text:
    print(f"{SKIP} [welcome_screen.dart] _cBg not used — skipping method inject")
else:
    inject_methods(
        WELCOME,
        anchor=(
            "  @override\n"
            "  Widget build(BuildContext context) {"
        ),
        methods=_WELC_HELPERS,
        label="inject _cBg helper into _WelcomeScreenState",
        skip_if="S31-F2c: theme color helpers",
    )

# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL FIXES APPLIED \033[0m")
    print()
    print("Root cause fixed: library-private _cBg etc. are now instance")
    print("methods inside each class, not imported from main.dart.")
    print()
    print("Next steps:")
    print("  git add lib/screens/home_screen.dart \\")
    print("          lib/screens/history_screen.dart \\")
    print("          lib/screens/settings_screen.dart \\")
    print("          lib/screens/welcome_screen.dart")
    print("  git commit -m 'S31-F2c: fix color helpers — instance methods per class'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} FIX(ES) FAILED — check WARN lines above \033[0m")
    print()
    print("If anchors didn't match, run this to inspect the live file:")
    print("  head -20 lib/screens/home_screen.dart")
    print("  grep -n 'BUILD\\|_cBg\\|_isDark\\|ThemeProvider' lib/screens/home_screen.dart")
    sys.exit(1)
