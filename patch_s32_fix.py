#!/usr/bin/env python3
"""
patch_s32_fix.py
Fix the 2 patches that failed in patch_s32.py:
  2-C-2  lang toggle pill container: anchor had wrong indentation (12 sp vs 14)
  2-C-4  lang segment container:     anchor was non-unique; use EdgeInsets.all(4) to discriminate
"""
from pathlib import Path
import sys

SETTINGS = Path("lib/screens/settings_screen.dart")

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
        hint = old.split('\n')[0]
        idx = text.find(hint)
        if idx != -1:
            print(f"       hint at {idx}: {repr(text[max(0,idx-30):idx+100])}")
        errors += 1; return
    if text.count(old) > 1:
        print(f"{WARN} [{path.name}] anchor not unique ({text.count(old)}x) — {label}")
        errors += 1; return
    write(path, text.replace(old, new, 1))
    print(f"{OK}  [{path.name}] {label}")

# ── 2-C-2: lang toggle pill container (correct indentation: 14 sp) ──────────
patch(
    SETTINGS,
    (
        "              decoration: BoxDecoration(\n"
        "                color: const Color(0xFF1A1500),\n"
        "                borderRadius: BorderRadius.circular(20),\n"
        "                border: Border.all(\n"
        "                  color: const Color(0xFFD4AF37), width: 0.8)),"
    ),
    (
        "              decoration: BoxDecoration(\n"
        "                color: _isDark(context) ? const Color(0xFF1A1500) : const Color(0xFFF3EED9),\n"
        "                borderRadius: BorderRadius.circular(20),\n"
        "                border: Border.all(\n"
        "                  color: cGold, width: 0.8)),"
    ),
    label="2-C-2 fix: lang toggle pill container theme-aware",
    skip_if="? const Color(0xFF1A1500) : const Color(0xFFF3EED9)",
)

# ── 2-C-4: lang segment container — unique via EdgeInsets.all(4) ─────────────
patch(
    SETTINGS,
    (
        "            padding: const EdgeInsets.all(4),\n"
        "            decoration: BoxDecoration(\n"
        "              color: const Color(0xFF161B22),\n"
        "              borderRadius: BorderRadius.circular(12),\n"
        "              border: Border.all(color: const Color(0xFF21262D))),\n"
        "            child: Row(children: ["
    ),
    (
        "            padding: const EdgeInsets.all(4),\n"
        "            decoration: BoxDecoration(\n"
        "              color: cCard,\n"
        "              borderRadius: BorderRadius.circular(12),\n"
        "              border: Border.all(color: cBorder)),\n"
        "            child: Row(children: ["
    ),
    label="2-C-4 fix: lang segment container → cCard/cBorder",
    skip_if="EdgeInsets.all(4),\n            decoration: BoxDecoration(\n              color: cCard,",
)

print()
print("=" * 50)
if errors == 0:
    print("\033[92m ALL 2 FIXES APPLIED \033[0m")
    print()
    print("Next:")
    print("  git add lib/screens/settings_screen.dart")
    print("  git commit -m 'S32-fix: settings 2-C-2 and 2-C-4 indentation fixes'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} FIX(ES) FAILED \033[0m")
    sys.exit(1)
