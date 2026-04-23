#!/usr/bin/env python3
"""
patch_s32_compiler_fix.py
Fix two compiler errors introduced by patch_s32:

BUG A — history_screen.dart:33-39
  replace_colors() ran after inserting HISTORY_THEME_FIELDS, so the
  initializers got replaced:
    Color _tBg = const Color(0xFF080A0E)  →  Color _tBg = _tBg   (invalid)
  Fix: restore correct const-color initializers.

BUG B — home_screen.dart:1663
  replace_colors() replaced const Color(0xFF21262D) → _tBorder everywhere,
  including inside _ScoreArcPainter (a separate class with no _tBorder field).
  Fix: add a trackColor parameter to _ScoreArcPainter, pass _tBorder at the
  call site.
"""
from pathlib import Path
import sys

HOME    = Path("lib/screens/home_screen.dart")
HISTORY = Path("lib/screens/history_screen.dart")

OK   = "\033[92m OK  \033[0m"
SKIP = "\033[94m SKIP\033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"

errors = 0

def read(p): return p.read_text(encoding="utf-8")
def write(p, t): p.write_text(t, encoding="utf-8")

def patch(path, old, new, label, skip_if=""):
    global errors
    if not path.exists():
        print(f"{ERR} [{path.name}] not found — {label}"); errors += 1; return
    text = read(path)
    if skip_if and skip_if in text:
        print(f"{SKIP} [{path.name}] already done — {label}"); return
    if old not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label}")
        hint = old.strip().split('\n')[0]
        idx = text.find(hint)
        if idx != -1:
            print(f"       hint at {idx}: {repr(text[max(0,idx-30):idx+120])}")
        errors += 1; return
    if text.count(old) > 1:
        print(f"{WARN} [{path.name}] anchor not unique ({text.count(old)}x) — {label}")
        errors += 1; return
    write(path, text.replace(old, new, 1))
    print(f"{OK}  [{path.name}] {label}")


# ─── BUG A: history_screen — self-referential field initializers ─────────────

patch(
    HISTORY,
    (
        "  Color _tBg     = _tBg;\n"
        "  Color _tCard   = _tCard;\n"
        "  Color _tBorder = _tBorder;\n"
        "  Color _tText   = _tText;\n"
        "  Color _tSub    = _tSub;\n"
        "  Color _tDim    = _tDim;\n"
        "  Color _tGold   = _tGold;\n"
        "  bool  _tDark   = true;\n"
    ),
    (
        "  Color _tBg     = const Color(0xFF080A0E);\n"
        "  Color _tCard   = const Color(0xFF161B22);\n"
        "  Color _tBorder = const Color(0xFF21262D);\n"
        "  Color _tText   = const Color(0xFFC9D1D9);\n"
        "  Color _tSub    = const Color(0xFF8B949E);\n"
        "  Color _tDim    = const Color(0xFF484F58);\n"
        "  Color _tGold   = const Color(0xFFD4AF37);\n"
        "  bool  _tDark   = true;\n"
    ),
    label="BUG A: restore history field initializers (was self-referential)",
    skip_if="Color _tBg     = const Color(0xFF080A0E);",
)


# ─── BUG B: home_screen — _ScoreArcPainter.paint() uses _tBorder ────────────
# The class is separate from _HomeScreenState and has no _tBorder field.
# Fix: add trackColor parameter; pass _tBorder at the call site.

# B-1: add trackColor field + param to constructor, remove erroneous const
patch(
    HOME,
    (
        "class _ScoreArcPainter extends CustomPainter {\n"
        "  final double progress;\n"
        "  final double score;\n"
        "  final Color  color;\n"
        "  const _ScoreArcPainter({\n"
        "    required this.progress,\n"
        "    required this.score,\n"
        "    required this.color,\n"
        "  });"
    ),
    (
        "class _ScoreArcPainter extends CustomPainter {\n"
        "  final double progress;\n"
        "  final double score;\n"
        "  final Color  color;\n"
        "  final Color  trackColor; // S32-fix: passed from State, was incorrectly _tBorder\n"
        "  _ScoreArcPainter({\n"
        "    required this.progress,\n"
        "    required this.score,\n"
        "    required this.color,\n"
        "    required this.trackColor,\n"
        "  });"
    ),
    label="BUG B-1: add trackColor param to _ScoreArcPainter",
    skip_if="final Color  trackColor;",
)

# B-2: use trackColor in paint() instead of _tBorder
patch(
    HOME,
    (
        "      Paint()\n"
        "        ..color = _tBorder\n"
        "        ..style = PaintingStyle.stroke\n"
        "        ..strokeWidth = 12\n"
        "        ..strokeCap = StrokeCap.round,\n"
        "    );\n"
        "\n"
        "    // Score fill"
    ),
    (
        "      Paint()\n"
        "        ..color = trackColor\n"
        "        ..style = PaintingStyle.stroke\n"
        "        ..strokeWidth = 12\n"
        "        ..strokeCap = StrokeCap.round,\n"
        "    );\n"
        "\n"
        "    // Score fill"
    ),
    label="BUG B-2: paint() uses trackColor instead of _tBorder",
    skip_if="..color = trackColor",
)

# B-3: update shouldRepaint to include trackColor
patch(
    HOME,
    "  bool shouldRepaint(_ScoreArcPainter o) =>\n"
    "      o.progress != progress || o.color != color;",
    "  bool shouldRepaint(_ScoreArcPainter o) =>\n"
    "      o.progress != progress || o.color != color || o.trackColor != trackColor;",
    label="BUG B-3: shouldRepaint includes trackColor",
    skip_if="o.trackColor != trackColor",
)

# B-4: pass _tBorder at the call site
patch(
    HOME,
    "                  painter: _ScoreArcPainter(\n"
    "                    progress: t, score: score, color: scoreColor),",
    "                  painter: _ScoreArcPainter(\n"
    "                    progress: t, score: score, color: scoreColor,\n"
    "                    trackColor: _tBorder),",
    label="BUG B-4: pass trackColor: _tBorder at call site",
    skip_if="trackColor: _tBorder",
)


# ─── summary ─────────────────────────────────────────────────────────────────
print()
print("=" * 54)
if errors == 0:
    print("\033[92m ALL COMPILER FIXES APPLIED \033[0m")
    print()
    print("Next steps:")
    print("  git add lib/screens/home_screen.dart \\")
    print("          lib/screens/history_screen.dart")
    print("  git commit -m 'S32-fix: compiler errors (self-ref fields + _ScoreArcPainter)'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} FIX(ES) FAILED — inspect WARN lines above \033[0m")
    sys.exit(1)
