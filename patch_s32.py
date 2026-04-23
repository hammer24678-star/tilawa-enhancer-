#!/usr/bin/env python3
"""
patch_s32.py — Two fixes

══════════════════════════════════════════════════════════════════════
FIX 1 — WELCOME SCREEN (show exactly ONCE on first install, never again)
══════════════════════════════════════════════════════════════════════
Root cause: SharedPreferences key 'seen_welcome' persists across
reinstalls on Android. If the user ever finished the welcome flow,
the key is permanently true → welcome screen never shows again.

Fix: rename key to 'seen_welcome_v2'.
After this change:
  • First launch: key missing → false → WelcomeScreen shows ✓
  • User presses "Get Started" → key set to true
  • Every subsequent launch: true → HomeScreen directly ✓
  • Settings "Show Tutorial" button resets the key → shows again ✓

Files: main.dart, welcome_screen.dart, settings_screen.dart

══════════════════════════════════════════════════════════════════════
FIX 2 — LIGHT MODE (theme colors actually reach every widget)
══════════════════════════════════════════════════════════════════════
Root cause: color helpers (_cBg, _cCard, etc.) are computed as LOCAL
VARIABLES inside build() only. Sub-methods (_header, _engineSelector,
_fileCard, _jobCard, etc.) are called from build() but receive no
colors — they still read hardcoded dark hex Color literals.
Switching to light mode changes only the Scaffold background.
Everything else stays dark.

Fix for StatefulWidgets (home_screen, history_screen):
  1. Add 8 INSTANCE FIELDS for theme colors (_tBg, _tCard, _tBorder,
     _tText, _tSub, _tDim, _tGold, _tDark). Default = dark values.
  2. At the top of build(), update them via the existing color helpers.
     Since all sub-methods are instance methods, they can now access
     _tBg etc. directly — no parameter threading needed.
  3. Replace all hardcoded dark Color literals file-wide with the
     appropriate field reference (protecting the helper definitions
     from circular replacement via placeholder trick).

Fix for SettingsScreen (StatelessWidget — no instance fields):
  1. Add the 5 missing color helpers (_cCard, _cBorder, _cText, _cSub, _cDim).
  2. In build(), compute all 7 color locals.
  3. Replace hardcoded darks in build() body directly.
  4. Pass context to _section() and _eCard() sub-methods so they can
     call the helpers themselves.

Fix for WelcomeScreen: fix the page-2 tier card backgrounds.
"""

from pathlib import Path
import re
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


# ─── helpers ─────────────────────────────────────────────────────────────────

def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")

def write(p: Path, t: str):
    p.write_text(t, encoding="utf-8")

def patch(path, old, new, label, skip_if=""):
    global errors
    if not path.exists():
        print(f"{ERR} [{path.name}] not found — {label}")
        errors += 1; return False
    text = read(path)
    if skip_if and skip_if in text:
        print(f"{SKIP} [{path.name}] already done — {label}")
        return True
    if old not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label}")
        hint = old.split('\n')[0]
        idx  = text.find(hint)
        if idx != -1:
            print(f"       hint at char {idx}: {repr(text[max(0,idx-20):idx+80])}")
        errors += 1; return False
    if text.count(old) > 1:
        print(f"{WARN} [{path.name}] anchor not unique ({text.count(old)}×) — {label}")
        errors += 1; return False
    write(path, text.replace(old, new, 1))
    print(f"{OK}  [{path.name}] {label}")
    return True

def insert_before(path, anchor, insertion, label, skip_if=""):
    """Insert `insertion` immediately before `anchor`."""
    return patch(path, anchor, insertion + anchor, label, skip_if)

def replace_colors(text: str, color_map: list, protect_block: str = "") -> str:
    """
    Replace `const Color(0xFFXXX)` patterns with theme field references.
    protect_block: a verbatim string that must not be touched (the helper definitions).
    """
    PLACEHOLDER = "___THEME_HELPERS_PROTECTED___"
    protected   = protect_block and protect_block in text
    if protected:
        text = text.replace(protect_block, PLACEHOLDER, 1)

    for hex_val, field in color_map:
        # Only replace explicit `const Color(hex)` — leaves non-const Color(hex)
        # (used in const Widget constructors) untouched to avoid breaking const-ness.
        text = text.replace(f"const Color({hex_val})", field)

    if protected:
        text = text.replace(PLACEHOLDER, protect_block, 1)
    return text


# ═══════════════════════════════════════════════════════════════════════════
# FIX 1 — Welcome screen: rename pref key seen_welcome → seen_welcome_v2
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "═"*60)
print("FIX 1 — Welcome screen pref key")
print("═"*60)

# 1-A main.dart: read the key
patch(MAIN,
    "  final seenWelcome = prefs.getBool('seen_welcome')  ?? false;",
    "  final seenWelcome = prefs.getBool('seen_welcome_v2') ?? false; // S32",
    label="F1-A: main.dart — read seen_welcome_v2",
    skip_if="seen_welcome_v2",
)

# 1-B welcome_screen.dart: write the key in _finish()
patch(WELCOME,
    "    await prefs.setBool('seen_welcome', true);",
    "    await prefs.setBool('seen_welcome_v2', true); // S32",
    label="F1-B: welcome_screen — write seen_welcome_v2 in _finish()",
    skip_if="seen_welcome_v2",
)

# 1-C settings_screen.dart: remove the key in "Show Tutorial" tile
patch(SETTINGS,
    "        await prefs.remove('seen_welcome');",
    "        await prefs.remove('seen_welcome_v2'); // S32",
    label="F1-C: settings_screen — remove seen_welcome_v2 in tutorial tile",
    skip_if="seen_welcome_v2",
)


# ═══════════════════════════════════════════════════════════════════════════
# FIX 2 — Light mode
# ═══════════════════════════════════════════════════════════════════════════
print("\n" + "═"*60)
print("FIX 2 — Light mode: theme colors reach all widgets")
print("═"*60)


# ──────────────────────────────────────────────────────────────────────────
# 2-A: home_screen.dart — the big one
# ──────────────────────────────────────────────────────────────────────────
print("\n[home_screen.dart]")

# The helper block that must be protected from circular replacement
HOME_HELPER_BLOCK = (
    "  // ── S31-F2c: theme color helpers (private instance methods) ────────────────\n"
    "  bool  _isDark(BuildContext ctx)   => ThemeProvider.isDark(ctx);\n"
    "  Color _cBg(BuildContext ctx)      => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n"
    "  Color _cCard(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);\n"
    "  Color _cBorder(BuildContext ctx)  => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);\n"
    "  Color _cText(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFFC9D1D9) : const Color(0xFF1A1400);\n"
    "  Color _cSub(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);\n"
    "  Color _cDim(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF484F58) : const Color(0xFF8B7B5A);\n"
    "  Color _cGold(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);\n"
)

HOME_THEME_FIELDS = (
    "\n"
    "  // S32: theme cache — updated at top of every build() so ALL sub-methods\n"
    "  // (which are instance methods) can read current theme colors directly.\n"
    "  // Initialized to dark-mode defaults; updated before any widget is built.\n"
    "  Color _tBg     = const Color(0xFF080A0E);\n"
    "  Color _tCard   = const Color(0xFF161B22);\n"
    "  Color _tBorder = const Color(0xFF21262D);\n"
    "  Color _tText   = const Color(0xFFC9D1D9);\n"
    "  Color _tSub    = const Color(0xFF8B949E);\n"
    "  Color _tDim    = const Color(0xFF484F58);\n"
    "  Color _tGold   = const Color(0xFFD4AF37);\n"
    "  bool  _tDark   = true;\n"
)

# Step 2-A-1: inject theme field declarations
insert_before(
    HOME,
    anchor="  // S19: Wake server state\n",
    insertion=HOME_THEME_FIELDS,
    label="2-A-1: add theme cache fields to _HomeScreenState",
    skip_if="S32: theme cache",
)

# Step 2-A-2: update build() to populate the cache
OLD_BUILD_LOCALS = (
    "    final dark = _isDark(context);\n"
    "    final cBg     = _cBg(context);\n"
    "    final cCard   = _cCard(context);\n"
    "    final cBorder = _cBorder(context);\n"
    "    final cText   = _cText(context);\n"
    "    final cSub    = _cSub(context);\n"
    "    final cDim    = _cDim(context);\n"
    "    final cGold   = _cGold(context);\n"
)
NEW_BUILD_LOCALS = (
    "    // S32: populate theme cache so sub-methods see current colors\n"
    "    _tDark = _isDark(context); _tBg = _cBg(context); _tCard = _cCard(context);\n"
    "    _tBorder = _cBorder(context); _tText = _cText(context);\n"
    "    _tSub = _cSub(context); _tDim = _cDim(context); _tGold = _cGold(context);\n"
    "    final dark = _tDark; // used in gradient below\n"
    "    final cBg = _tBg;   // used in Scaffold backgroundColor\n"
)

patch(
    HOME,
    OLD_BUILD_LOCALS,
    NEW_BUILD_LOCALS,
    label="2-A-2: update build() to populate theme cache",
    skip_if="S32: populate theme cache",
)

# Step 2-A-3: file-wide color replacement
# Only dark-palette UI colors are replaced. Semantic colors (green/red/blue),
# intentional dark overlays (0xFF1A1500 gold tint, 0xFF0D2015 green tint, etc.),
# and gradient-end colors are left unchanged.
HOME_COLOR_MAP = [
    ("0xFF080A0E", "_tBg"),       # main dark background
    ("0xFF0D1117", "_tCard"),     # dark modal/sheet surface
    ("0xFF161B22", "_tCard"),     # card / container background
    ("0xFF1C1C1C", "_tCard"),     # neutral dark badge background
    ("0xFF21262D", "_tBorder"),   # border
    ("0xFF30363D", "_tBorder"),   # lighter border variant
    ("0xFFC9D1D9", "_tText"),     # primary text
    ("0xFF8B949E", "_tSub"),      # secondary / subtitle text
    ("0xFF484F58", "_tDim"),      # dim / tertiary text
    ("0xFFD4AF37", "_tGold"),     # gold accent
    # NOT replaced: 0xFF0A0C10 (dark fg on gold buttons — intentional contrast)
    # NOT replaced: 0xFF3FB950, 0xFFF85149, 0xFF58A6FF (semantic status colors)
    # NOT replaced: 0xFF1A1500, 0xFF1A1200, 0xFF0D1B2E, 0xFF0D2015 (intentional tints)
    # NOT replaced: 0xFF0C1018 (gradient dark end — already in dark-conditional branch)
    # NOT replaced: 0xFFFFF4B0 (very-light gold glow)
    # NOT replaced: 0xFFC9A227 (mid-gold — tier card accent in welcome)
]

if HOME.exists():
    skip_marker = "// S32-COLORS-APPLIED"
    text = read(HOME)
    if skip_marker in text:
        print(f"{SKIP} [home_screen.dart] color replacement already applied")
    else:
        orig_len = len(text)
        text = replace_colors(text, HOME_COLOR_MAP, HOME_HELPER_BLOCK)
        # Mark as applied
        text = text.replace(
            HOME_HELPER_BLOCK,
            HOME_HELPER_BLOCK + "  // S32-COLORS-APPLIED\n"
        )
        write(HOME, text)
        replacements = orig_len - len(text)  # rough indicator (lengths differ)
        print(f"{OK}  [home_screen.dart] 2-A-3: replaced dark palette colors with theme fields")
else:
    print(f"{ERR} [home_screen.dart] file not found — 2-A-3: color replacement")
    errors += 1


# ──────────────────────────────────────────────────────────────────────────
# 2-B: history_screen.dart
# ──────────────────────────────────────────────────────────────────────────
print("\n[history_screen.dart]")

HISTORY_HELPER_BLOCK = (
    "  // ── S31-F2c: theme color helpers (private instance methods) ────────────────\n"
    "  bool  _isDark(BuildContext ctx) => ThemeProvider.isDark(ctx);\n"
    "  Color _cBg(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n"
    "  Color _cGold(BuildContext ctx)  => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);\n"
)

# Expanded helper block for history (add missing helpers)
HISTORY_HELPER_BLOCK_FULL = (
    "  // ── S31-F2c / S32: theme color helpers ────────────────────────────────────\n"
    "  bool  _isDark(BuildContext ctx)  => ThemeProvider.isDark(ctx);\n"
    "  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n"
    "  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);\n"
    "  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);\n"
    "  Color _cText(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFC9D1D9) : const Color(0xFF1A1400);\n"
    "  Color _cSub(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);\n"
    "  Color _cDim(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF484F58) : const Color(0xFF8B7B5A);\n"
    "  Color _cGold(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);\n"
)

HISTORY_THEME_FIELDS = (
    "\n"
    "  // S32: theme cache (see home_screen.dart for rationale)\n"
    "  Color _tBg     = const Color(0xFF080A0E);\n"
    "  Color _tCard   = const Color(0xFF161B22);\n"
    "  Color _tBorder = const Color(0xFF21262D);\n"
    "  Color _tText   = const Color(0xFFC9D1D9);\n"
    "  Color _tSub    = const Color(0xFF8B949E);\n"
    "  Color _tDim    = const Color(0xFF484F58);\n"
    "  Color _tGold   = const Color(0xFFD4AF37);\n"
    "  bool  _tDark   = true;\n"
)

# Expand helper block (old small one → new full one)
patch(
    HISTORY,
    HISTORY_HELPER_BLOCK,
    HISTORY_HELPER_BLOCK_FULL,
    label="2-B-0: expand history color helpers to full set",
    skip_if="_cCard(BuildContext ctx)   => _isDark(ctx)",
)

# Add theme cache fields
insert_before(
    HISTORY,
    anchor="  @override\n  void initState() {\n    super.initState();\n    _load();",
    insertion=HISTORY_THEME_FIELDS,
    label="2-B-1: add theme cache fields to _HistoryScreenState",
    skip_if="S32: theme cache",
)

# Update build() to populate cache
HIST_OLD_BUILD = (
    "    final s = LangProvider.strings(context);\n"
    "    final cBg   = _cBg(context);\n"
    "    final cGold = _cGold(context);\n"
    "    return Scaffold(\n"
    "      backgroundColor: cBg,"
)
HIST_NEW_BUILD = (
    "    final s = LangProvider.strings(context);\n"
    "    // S32: update theme cache\n"
    "    _tDark = _isDark(context); _tBg = _cBg(context); _tCard = _cCard(context);\n"
    "    _tBorder = _cBorder(context); _tText = _cText(context);\n"
    "    _tSub = _cSub(context); _tDim = _cDim(context); _tGold = _cGold(context);\n"
    "    final cBg = _tBg; final cGold = _tGold;\n"
    "    return Scaffold(\n"
    "      backgroundColor: cBg,"
)

patch(
    HISTORY,
    HIST_OLD_BUILD,
    HIST_NEW_BUILD,
    label="2-B-2: update history build() to populate theme cache",
    skip_if="S32: update theme cache",
)

# File-wide color replacement
HISTORY_COLOR_MAP = [
    ("0xFF0A0C10", "_tBg"),
    ("0xFF080A0E", "_tBg"),
    ("0xFF161B22", "_tCard"),
    ("0xFF21262D", "_tBorder"),
    ("0xFF30363D", "_tBorder"),
    ("0xFFC9D1D9", "_tText"),
    ("0xFF8B949E", "_tSub"),
    ("0xFF484F58", "_tDim"),
    ("0xFFD4AF37", "_tGold"),
]

if HISTORY.exists():
    skip_marker = "// S32-COLORS-APPLIED"
    text = read(HISTORY)
    if skip_marker in text:
        print(f"{SKIP} [history_screen.dart] color replacement already applied")
    else:
        text = replace_colors(text, HISTORY_COLOR_MAP, HISTORY_HELPER_BLOCK_FULL)
        text = text.replace(
            HISTORY_HELPER_BLOCK_FULL,
            HISTORY_HELPER_BLOCK_FULL + "  // S32-COLORS-APPLIED\n"
        )
        write(HISTORY, text)
        print(f"{OK}  [history_screen.dart] 2-B-3: replaced dark palette colors")
else:
    print(f"{ERR} [history_screen.dart] not found — 2-B-3")
    errors += 1


# ──────────────────────────────────────────────────────────────────────────
# 2-C: settings_screen.dart — StatelessWidget, use method parameters
# ──────────────────────────────────────────────────────────────────────────
print("\n[settings_screen.dart]")

SETT_HELPER_OLD = (
    "  // ── S31-F2c: theme color helpers (private instance methods) ────────────────\n"
    "  bool  _isDark(BuildContext ctx) => ThemeProvider.isDark(ctx);\n"
    "  Color _cBg(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n"
    "  Color _cGold(BuildContext ctx)  => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);\n"
)

SETT_HELPER_NEW = (
    "  // ── S31-F2c / S32: theme color helpers ────────────────────────────────────\n"
    "  bool  _isDark(BuildContext ctx)  => ThemeProvider.isDark(ctx);\n"
    "  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n"
    "  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);\n"
    "  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);\n"
    "  Color _cText(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFC9D1D9) : const Color(0xFF1A1400);\n"
    "  Color _cSub(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);\n"
    "  Color _cDim(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF484F58) : const Color(0xFF8B7B5A);\n"
    "  Color _cGold(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);\n"
)

patch(
    SETTINGS,
    SETT_HELPER_OLD,
    SETT_HELPER_NEW,
    label="2-C-0: expand settings color helpers",
    skip_if="_cCard(BuildContext ctx)   => _isDark(ctx)",
)

# Update build() local vars to include all colors
SETT_OLD_BUILD_START = (
    "    final cBg   = _cBg(context);\n"
    "    final cGold = _cGold(context);\n"
    "    return Scaffold("
)
SETT_NEW_BUILD_START = (
    "    final cBg     = _cBg(context);\n"
    "    final cCard   = _cCard(context);\n"
    "    final cBorder = _cBorder(context);\n"
    "    final cText   = _cText(context);\n"
    "    final cSub    = _cSub(context);\n"
    "    final cDim    = _cDim(context);\n"
    "    final cGold   = _cGold(context);\n"
    "    return Scaffold("
)

patch(
    SETTINGS,
    SETT_OLD_BUILD_START,
    SETT_NEW_BUILD_START,
    label="2-C-1: settings build() — compute all color locals",
    skip_if="final cCard   = _cCard(context);",
)

# Replace hardcoded dark colors in build() method body
# settings_screen.dart containers: language pill container, theme tile, tutorial tile,
# target info box (keep as-is — intentional green tint), about box, privacy.

# Language toggle container
patch(
    SETTINGS,
    (
        "            decoration: BoxDecoration(\n"
        "              color: const Color(0xFF1A1500),\n"
        "              borderRadius: BorderRadius.circular(20),\n"
        "              border: Border.all(\n"
        "                color: const Color(0xFFD4AF37), width: 0.8)),"
    ),
    (
        "            decoration: BoxDecoration(\n"
        "              color: _isDark(context) ? const Color(0xFF1A1500) : const Color(0xFFF3EED9),\n"
        "              borderRadius: BorderRadius.circular(20),\n"
        "              border: Border.all(\n"
        "                color: cGold, width: 0.8)),"
    ),
    label="2-C-2: settings lang toggle pill container theme-aware",
    skip_if="? const Color(0xFF1A1500) : const Color(0xFFF3EED9)",
)

# Lang toggle text colors (the EN/ع label and icon)
patch(
    SETTINGS,
    (
        "                Text(isAr ? 'EN' : 'ع',\n"
        "                  style: const TextStyle(\n"
        "                    color: Color(0xFFD4AF37),\n"
        "                    fontWeight: FontWeight.bold, fontSize: 13)),\n"
        "                const SizedBox(width: 4),\n"
        "                const Icon(Icons.language,\n"
        "                  color: Color(0xFFD4AF37), size: 14),"
    ),
    (
        "                Text(isAr ? 'EN' : 'ع',\n"
        "                  style: TextStyle(\n"
        "                    color: cGold,\n"
        "                    fontWeight: FontWeight.bold, fontSize: 13)),\n"
        "                const SizedBox(width: 4),\n"
        "                Icon(Icons.language,\n"
        "                  color: cGold, size: 14),"
    ),
    label="2-C-3: settings lang toggle icon/text color → cGold",
    skip_if="color: cGold,\n                    fontWeight: FontWeight.bold, fontSize: 13",
)

# Language segment container (the AR / EN pill row)
patch(
    SETTINGS,
    (
        "            decoration: BoxDecoration(\n"
        "              color: const Color(0xFF161B22),\n"
        "              borderRadius: BorderRadius.circular(12),\n"
        "              border: Border.all(color: const Color(0xFF21262D))),"
    ),
    (
        "            decoration: BoxDecoration(\n"
        "              color: cCard,\n"
        "              borderRadius: BorderRadius.circular(12),\n"
        "              border: Border.all(color: cBorder)),"
    ),
    label="2-C-4: settings language segment container → cCard/cBorder",
    skip_if="color: cCard,\n              borderRadius: BorderRadius.circular(12),\n              border: Border.all(color: cBorder))",
)

# _themeTile container
patch(
    SETTINGS,
    (
        "        margin: const EdgeInsets.only(bottom: 18),\n"
        "        decoration: BoxDecoration(\n"
        "          color: const Color(0xFF161B22),\n"
        "          borderRadius: BorderRadius.circular(12),\n"
        "          border: Border.all(color: const Color(0xFF21262D))),\n"
        "        child: SwitchListTile("
    ),
    (
        "        margin: const EdgeInsets.only(bottom: 18),\n"
        "        decoration: BoxDecoration(\n"
        "          color: _cCard(context),\n"
        "          borderRadius: BorderRadius.circular(12),\n"
        "          border: Border.all(color: _cBorder(context))),\n"
        "        child: SwitchListTile("
    ),
    label="2-C-5: _themeTile container → theme-aware",
    skip_if="color: _cCard(context),\n          borderRadius: BorderRadius.circular(12),\n          border: Border.all(color: _cBorder(context))),\n        child: SwitchListTile(",
)

# SwitchListTile title/subtitle in _themeTile
patch(
    SETTINGS,
    (
        "          title: Text(\n"
        "            s.ar ? 'الوضع الداكن' : 'Dark Mode',\n"
        "            style: const TextStyle(color: Color(0xFFC9D1D9), fontSize: 14)),\n"
        "          subtitle: Text(\n"
        "            dark\n"
        "              ? (s.ar ? 'الوضع الحالي' : 'Currently active')\n"
        "              : (s.ar ? 'الوضع الفاتح نشط' : 'Light mode active'),\n"
        "            style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),"
    ),
    (
        "          title: Text(\n"
        "            s.ar ? 'الوضع الداكن' : 'Dark Mode',\n"
        "            style: TextStyle(color: _cText(context), fontSize: 14)),\n"
        "          subtitle: Text(\n"
        "            dark\n"
        "              ? (s.ar ? 'الوضع الحالي' : 'Currently active')\n"
        "              : (s.ar ? 'الوضع الفاتح نشط' : 'Light mode active'),\n"
        "            style: TextStyle(color: _cSub(context), fontSize: 11)),"
    ),
    label="2-C-6: _themeTile title/subtitle text → theme-aware",
    skip_if="style: TextStyle(color: _cText(context), fontSize: 14)),",
)

# _tutorialTile container
patch(
    SETTINGS,
    (
        "  Widget _tutorialTile(BuildContext context, S s) => Container(\n"
        "    margin: const EdgeInsets.only(bottom: 18),\n"
        "    decoration: BoxDecoration(\n"
        "      color: const Color(0xFF161B22),\n"
        "      borderRadius: BorderRadius.circular(12),\n"
        "      border: Border.all(color: const Color(0xFF21262D))),"
    ),
    (
        "  Widget _tutorialTile(BuildContext context, S s) => Container(\n"
        "    margin: const EdgeInsets.only(bottom: 18),\n"
        "    decoration: BoxDecoration(\n"
        "      color: _cCard(context),\n"
        "      borderRadius: BorderRadius.circular(12),\n"
        "      border: Border.all(color: _cBorder(context))),"
    ),
    label="2-C-7: _tutorialTile container → theme-aware",
    skip_if="color: _cCard(context),\n      borderRadius: BorderRadius.circular(12),\n      border: Border.all(color: _cBorder(context))),",
)

# _tutorialTile ListTile title/subtitle
patch(
    SETTINGS,
    (
        "      title: Text(\n"
        "        s.ar ? 'عرض شاشة الترحيب' : 'Show Welcome Screen',\n"
        "        style: const TextStyle(color: Color(0xFFC9D1D9), fontSize: 14)),\n"
        "      subtitle: Text(\n"
        "        s.ar ? 'عرض دليل البداية مرة أخرى' : 'Re-show the onboarding guide',\n"
        "        style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),"
    ),
    (
        "      title: Text(\n"
        "        s.ar ? 'عرض شاشة الترحيب' : 'Show Welcome Screen',\n"
        "        style: TextStyle(color: _cText(context), fontSize: 14)),\n"
        "      subtitle: Text(\n"
        "        s.ar ? 'عرض دليل البداية مرة أخرى' : 'Re-show the onboarding guide',\n"
        "        style: TextStyle(color: _cSub(context), fontSize: 11)),"
    ),
    label="2-C-8: _tutorialTile list tile text → theme-aware",
    skip_if="style: TextStyle(color: _cText(context), fontSize: 14)),\n      subtitle:",
)

# About section container
patch(
    SETTINGS,
    (
        "            padding: const EdgeInsets.all(18),\n"
        "            decoration: BoxDecoration(\n"
        "              color: const Color(0xFF161B22),\n"
        "              borderRadius: BorderRadius.circular(12),\n"
        "              border: Border.all(color: const Color(0xFF21262D))),"
    ),
    (
        "            padding: const EdgeInsets.all(18),\n"
        "            decoration: BoxDecoration(\n"
        "              color: cCard,\n"
        "              borderRadius: BorderRadius.circular(12),\n"
        "              border: Border.all(color: cBorder)),"
    ),
    label="2-C-9: about section container → cCard/cBorder",
    skip_if="color: cCard,\n              borderRadius: BorderRadius.circular(12),\n              border: Border.all(color: cBorder)),",
)

# About text colors
patch(
    SETTINGS,
    (
        "              const Text('محسِّن التلاوة', style: TextStyle(\n"
        "                color: Color(0xFFD4AF37),\n"
        "                fontWeight: FontWeight.bold, fontSize: 18)),\n"
        "              const SizedBox(height: 4),\n"
        "              Text(s.version,\n"
        "                style: const TextStyle(\n"
        "                  color: Color(0xFF8B949E), fontSize: 12)),\n"
        "              const SizedBox(height: 2),\n"
        "              const Text('Yasser Al-Dossari · 1425H',\n"
        "                style: TextStyle(\n"
        "                  color: Color(0xFF484F58), fontSize: 11)),"
    ),
    (
        "              Text('محسِّن التلاوة', style: TextStyle(\n"
        "                color: cGold,\n"
        "                fontWeight: FontWeight.bold, fontSize: 18)),\n"
        "              const SizedBox(height: 4),\n"
        "              Text(s.version,\n"
        "                style: TextStyle(\n"
        "                  color: cSub, fontSize: 12)),\n"
        "              const SizedBox(height: 2),\n"
        "              Text('Yasser Al-Dossari · 1425H',\n"
        "                style: TextStyle(\n"
        "                  color: cDim, fontSize: 11)),"
    ),
    label="2-C-10: about section text colors → cGold/cSub/cDim",
    skip_if="color: cGold,\n                fontWeight: FontWeight.bold, fontSize: 18",
)

# _section helper: add context param and use cSub color
patch(
    SETTINGS,
    (
        "  Widget _section(String title) => Padding(\n"
        "    padding: const EdgeInsets.only(bottom: 8, top: 4),\n"
        "    child: Text(title, style: const TextStyle(\n"
        "      color: Color(0xFF8B949E), fontSize: 11, letterSpacing: 1.5)));"
    ),
    (
        "  Widget _section(BuildContext ctx, String title) => Padding(\n"
        "    padding: const EdgeInsets.only(bottom: 8, top: 4),\n"
        "    child: Text(title, style: TextStyle(\n"
        "      color: _cSub(ctx), fontSize: 11, letterSpacing: 1.5)));"
    ),
    label="2-C-11: _section() add context, use _cSub",
    skip_if="Widget _section(BuildContext ctx,",
)

# Update all _section() call sites to pass context
if SETTINGS.exists():
    text = read(SETTINGS)
    # Replace _section(s.xxx) → _section(context, s.xxx)
    new_text = re.sub(
        r'_section\(s\.(\w+)\)',
        r'_section(context, s.\1)',
        text,
    )
    if new_text != text:
        write(SETTINGS, new_text)
        print(f"{OK}  [settings_screen.dart] 2-C-12: updated _section() call sites")
    else:
        print(f"{SKIP} [settings_screen.dart] _section() calls already updated")

# _eCard: add context param and use theme colors for container
patch(
    SETTINGS,
    "  Widget _eCard(_EHist e, bool isAr) {",
    "  Widget _eCard(BuildContext ctx, _EHist e, bool isAr) {",
    label="2-C-13: _eCard() add context param",
    skip_if="Widget _eCard(BuildContext ctx,",
)

# Replace _eCard container hardcoded colors with context-aware ones
patch(
    SETTINGS,
    (
        "    return Container(\n"
        "      margin: const EdgeInsets.only(bottom: 10),\n"
        "      padding: const EdgeInsets.all(14),\n"
        "      decoration: BoxDecoration(\n"
        "        color: isLatest ? const Color(0xFF1A1200) : const Color(0xFF161B22),\n"
        "        borderRadius: BorderRadius.circular(12),\n"
        "        border: Border.all(\n"
        "          color: isLatest\n"
        "            ? const Color(0xFFD4AF37)\n"
        "            : const Color(0xFF21262D),\n"
        "          width: isLatest ? 1.2 : 0.8)),"
    ),
    (
        "    final _ec = _cCard(ctx);\n"
        "    final _eb = _cBorder(ctx);\n"
        "    return Container(\n"
        "      margin: const EdgeInsets.only(bottom: 10),\n"
        "      padding: const EdgeInsets.all(14),\n"
        "      decoration: BoxDecoration(\n"
        "        color: isLatest ? const Color(0xFF1A1200) : _ec,\n"
        "        borderRadius: BorderRadius.circular(12),\n"
        "        border: Border.all(\n"
        "          color: isLatest\n"
        "            ? _cGold(ctx)\n"
        "            : _eb,\n"
        "          width: isLatest ? 1.2 : 0.8)),"
    ),
    label="2-C-14: _eCard container colors → theme-aware",
    skip_if="final _ec = _cCard(ctx);",
)

# _eCard text colors
patch(
    SETTINGS,
    (
        "          Expanded(child: Text(e.name,\n"
        "            style: const TextStyle(\n"
        "              color: Color(0xFF8B949E), fontSize: 12))),"
    ),
    (
        "          Expanded(child: Text(e.name,\n"
        "            style: TextStyle(\n"
        "              color: _cSub(ctx), fontSize: 12))),"
    ),
    label="2-C-15: _eCard engine name text → _cSub",
    skip_if="color: _cSub(ctx), fontSize: 12))),",
)

patch(
    SETTINGS,
    (
        "        Text(desc,\n"
        "          textDirection: isAr ? TextDirection.rtl : TextDirection.ltr,\n"
        "          style: const TextStyle(\n"
        "            color: Color(0xFF8B949E), fontSize: 11, height: 1.5)),"
    ),
    (
        "        Text(desc,\n"
        "          textDirection: isAr ? TextDirection.rtl : TextDirection.ltr,\n"
        "          style: TextStyle(\n"
        "            color: _cSub(ctx), fontSize: 11, height: 1.5)),"
    ),
    label="2-C-16: _eCard description text → _cSub",
    skip_if="color: _cSub(ctx), fontSize: 11, height: 1.5",
)

# Update _eCard call sites to pass context
if SETTINGS.exists():
    text = read(SETTINGS)
    new_text = re.sub(
        r'_eCard\(e, isAr\)',
        '_eCard(context, e, isAr)',
        text,
    )
    if new_text != text:
        write(SETTINGS, new_text)
        print(f"{OK}  [settings_screen.dart] 2-C-17: updated _eCard() call sites")
    else:
        print(f"{SKIP} [settings_screen.dart] _eCard() calls already updated")

# _langPill — active pill colors (gold bg stays, inactive text uses cSub)
patch(
    SETTINGS,
    (
        "        child: Text(label,\n"
        "          textAlign: TextAlign.center,\n"
        "          style: TextStyle(\n"
        "            color: active ? const Color(0xFF0A0C10) : const Color(0xFF8B949E),\n"
        "            fontWeight: active ? FontWeight.bold : FontWeight.normal,\n"
        "            fontSize: 14))))"
    ),
    (
        "        child: Text(label,\n"
        "          textAlign: TextAlign.center,\n"
        "          style: TextStyle(\n"
        "            color: active ? const Color(0xFF0A0C10) : _cSub(context),\n"
        "            fontWeight: active ? FontWeight.bold : FontWeight.normal,\n"
        "            fontSize: 14))))"
    ),
    label="2-C-18: _langPill inactive text → _cSub",
    skip_if="color: active ? const Color(0xFF0A0C10) : _cSub(context),",
)


# ──────────────────────────────────────────────────────────────────────────
# 2-D: welcome_screen.dart — fix page-2 tier card backgrounds
# ──────────────────────────────────────────────────────────────────────────
print("\n[welcome_screen.dart]")

WELC_HELPER_BLOCK = (
    "  // ── S31-F2c: theme color helpers (private instance methods) ────────────────\n"
    "  bool  _isDark(BuildContext ctx) => ThemeProvider.isDark(ctx);\n"
    "  Color _cBg(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n"
)

# Add _cCard helper to welcome
WELC_HELPER_EXPANDED = (
    "  // ── S31-F2c / S32: theme color helpers ────────────────────────────────────\n"
    "  bool  _isDark(BuildContext ctx)  => ThemeProvider.isDark(ctx);\n"
    "  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);\n"
    "  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);\n"
    "  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);\n"
    "  Color _cSub(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);\n"
)

patch(
    WELCOME,
    WELC_HELPER_BLOCK,
    WELC_HELPER_EXPANDED,
    label="2-D-0: expand welcome color helpers",
    skip_if="_cCard(BuildContext ctx)   => _isDark(ctx)",
)

# Fix page2 tier card containers: const Color(0xFF161B22) → _cCard(context)
patch(
    WELCOME,
    (
        "          ...tiers.map((t) => Container(\n"
        "            margin: const EdgeInsets.only(bottom: 10),\n"
        "            padding: const EdgeInsets.symmetric(\n"
        "              horizontal: 14, vertical: 10),\n"
        "            decoration: BoxDecoration(\n"
        "              color: const Color(0xFF161B22),\n"
        "              borderRadius: BorderRadius.circular(10),\n"
        "              border: Border.all(\n"
        "                color: t.$4.withOpacity(0.25))),"
    ),
    (
        "          ...tiers.map((t) => Container(\n"
        "            margin: const EdgeInsets.only(bottom: 10),\n"
        "            padding: const EdgeInsets.symmetric(\n"
        "              horizontal: 14, vertical: 10),\n"
        "            decoration: BoxDecoration(\n"
        "              color: _cCard(context),\n"
        "              borderRadius: BorderRadius.circular(10),\n"
        "              border: Border.all(\n"
        "                color: t.$4.withOpacity(0.25))),"
    ),
    label="2-D-1: welcome page-2 tier card bg → _cCard",
    skip_if="color: _cCard(context),\n              borderRadius: BorderRadius.circular(10),",
)

# Fix welcome page-2 subtitle text
patch(
    WELCOME,
    (
        "          Text(s.ar\n"
        "            ? 'اختر محركك من الصفحة الرئيسية'\n"
        "            : 'Choose your engine from the home screen',\n"
        "            style: const TextStyle(color: Color(0xFF8B949E), fontSize: 12)),"
    ),
    (
        "          Text(s.ar\n"
        "            ? 'اختر محركك من الصفحة الرئيسية'\n"
        "            : 'Choose your engine from the home screen',\n"
        "            style: TextStyle(color: _cSub(context), fontSize: 12)),"
    ),
    label="2-D-2: welcome page-2 subtitle text → _cSub",
    skip_if="style: TextStyle(color: _cSub(context), fontSize: 12)),",
)


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL PATCHES APPLIED \033[0m")
    print()
    print("FIX 1 (Welcome): pref key renamed → seen_welcome_v2")
    print("  • First launch after update: shows welcome ✓")
    print("  • After finishing: never shows again ✓")
    print("  • Settings 'Show Tutorial': still works ✓")
    print()
    print("FIX 2 (Light mode): theme colors propagate to all widgets")
    print("  • home_screen:    _tBg/_tCard/_tBorder/_tText/_tSub/_tDim/_tGold")
    print("  • history_screen: same instance-field pattern")
    print("  • settings:       _cCard/_cBorder/_cText/_cSub/_cDim helpers added")
    print("  • welcome page2:  tier card backgrounds fixed")
    print()
    print("Next:")
    print("  git add lib/main.dart \\")
    print("          lib/screens/home_screen.dart \\")
    print("          lib/screens/history_screen.dart \\")
    print("          lib/screens/settings_screen.dart \\")
    print("          lib/screens/welcome_screen.dart")
    print("  git commit -m 'S32: welcome once on install + proper light mode'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} PATCH(ES) FAILED \033[0m")
    print()
    print("For each WARN above, the anchor text didn't match exactly.")
    print("Check the WARN lines and inspect the relevant file:")
    print("  grep -n 'seen_welcome\\|_tBg\\|_cCard\\|S32' lib/main.dart")
    print("  grep -n 'S32\\|_tBg\\|_tCard' lib/screens/home_screen.dart")
    sys.exit(1)
