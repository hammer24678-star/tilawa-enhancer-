#!/usr/bin/env python3
"""
patch_s31_engine_colors.py — Per-engine color for unselected cards

Problem: S31-F4 set ALL unselected engine text to the same flat grey.
  - Engine ID (v10.0, v9.0 …): 0xFFC9D1D9 for everything
  - Score (≥99, ≥96 …):        0xFF484F58 for everything

Fix: use col.withOpacity() so each engine keeps its badge colour when
unselected, just softened:
  - Engine ID  : col.withOpacity(0.55)   — readable, clearly coloured
  - Score      : col.withOpacity(0.40)   — lighter, still on-brand
  - /100 suffix: col.withOpacity(0.25)   — very soft accent

Result:
  v10.0 (gold badge) → soft gold text when unselected
  v9.0  (gold badge) → soft gold text when unselected
  v8.5  (gold badge) → soft gold text when unselected
  v8.0  (gold badge) → soft gold text when unselected
  v7.0  (no badge)   → soft grey  text when unselected  ← _badgeColor returns 0xFF484F58 for ''

Run from ~/tilawa-enhancer/ then git push.
"""

from pathlib import Path
import sys

REPO = Path(".")
HOME = REPO / "lib/screens/home_screen.dart"

OK   = "\033[92m OK  \033[0m"
SKIP = "\033[94m SKIP\033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"

errors = 0

def patch(path, old, new, label, skip_if=""):
    global errors
    if not path.exists():
        print(f"{ERR} [{path.name}] not found"); errors += 1; return False
    text = path.read_text(encoding="utf-8")
    if skip_if and skip_if in text:
        print(f"{SKIP} [{path.name}] already applied — {label}"); return True
    if old not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label}")
        # debug
        hint = old.split('\n')[0]
        idx = text.find(hint)
        if idx != -1:
            print(f"       near: {repr(text[idx:idx+80])}")
        errors += 1; return False
    if text.count(old) > 1:
        print(f"{WARN} [{path.name}] not unique — {label}"); errors += 1; return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{OK}  [{path.name}] {label}")
    return True


# ── Engine ID text (e.g. "v10.0") ───────────────────────────────────────
patch(HOME,
    "                  Text(e.id, style: TextStyle(\n"
    "                    // S31-F2b\n"
    "                    color: sel ? col : const Color(0xFFC9D1D9), // S31-F4\n"
    "                    fontWeight: FontWeight.bold, fontSize: 13)),",
    "                  Text(e.id, style: TextStyle(\n"
    "                    color: sel ? col : col.withOpacity(0.55), // S31-F5: per-engine colour\n"
    "                    fontWeight: FontWeight.bold, fontSize: 13)),",
    label="engine ID colour: col.withOpacity(0.55) when unselected",
    skip_if="col.withOpacity(0.55), // S31-F5",
)

# ── Score text (e.g. "≥99") ─────────────────────────────────────────────
patch(HOME,
    "                Text('≥${e.score.toInt()}', style: TextStyle(\n"
    "                  // S31-F2: gold engines → muted gold when unselected\n"
    "                  color: sel ? col : const Color(0xFF484F58), // S31-F4\n"
    "                  fontWeight: FontWeight.w800, fontSize: 15)),",
    "                Text('≥${e.score.toInt()}', style: TextStyle(\n"
    "                  color: sel ? col : col.withOpacity(0.40), // S31-F5\n"
    "                  fontWeight: FontWeight.w800, fontSize: 15)),",
    label="score colour: col.withOpacity(0.40) when unselected",
    skip_if="col.withOpacity(0.40), // S31-F5",
)

# ── /100 suffix ──────────────────────────────────────────────────────────
patch(HOME,
    "                Text('/100', style: TextStyle(\n"
    "                  color: sel ? col.withOpacity(0.45) : const Color(0xFF484F58),\n"
    "                  fontSize: 8)),",
    "                Text('/100', style: TextStyle(\n"
    "                  color: col.withOpacity(sel ? 0.45 : 0.25), // S31-F5\n"
    "                  fontSize: 8)),",
    label="/100 suffix: col.withOpacity(0.25) when unselected",
    skip_if="col.withOpacity(sel ? 0.45 : 0.25)",
)


print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL PATCHES APPLIED \033[0m")
    print()
    print("Effect:")
    print("  Each engine card now uses its own badge colour at reduced")
    print("  opacity when unselected:")
    print("    v10.0 / v9.0 / v8.5 / v8.0 → soft gold (0xFFD4AF37 × 0.55)")
    print("    v7.0 (no badge)              → soft grey (0xFF484F58 × 0.55)")
    print()
    print("Next:")
    print("  git add lib/screens/home_screen.dart")
    print("  git commit -m 'S31-F5: per-engine colour for unselected cards'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} PATCH(ES) FAILED \033[0m")
    sys.exit(1)
