#!/usr/bin/env python3
"""
patch_s30_hotfix.py — Fix missing ternary `?` in server banner (S30-S regression)

Root cause:
  patch_polish_s30r.py S-patch replaced
      ? '\${s.serverOnline} · \${_latencyMs}ms'
  with
      '${s.serverOnline} · ${_latencyMs}ms' // S30-S
  stripping the leading `?` from the inner ternary arm.

Result: Dart sees a string literal where it expects a ternary operator.
  Error: Expected ')' before this.

Fix: re-insert the missing `?`.
"""

from pathlib import Path
import sys

REPO = Path(".")
HOME = REPO / "lib/screens/home_screen.dart"

OK   = "\033[92m OK  \033[0m"
SKIP = "\033[94m SKIP\033[0m"
ERR  = "\033[91m ERR \033[0m"

if not HOME.exists():
    print(f"{ERR} home_screen.dart not found"); sys.exit(1)

text = HOME.read_text(encoding="utf-8")

# Already fixed?
FIXED = "? '${s.serverOnline} \u00b7 ${_latencyMs}ms' // S30-S"
if FIXED in text:
    print(f"{SKIP} already fixed — nothing to do"); sys.exit(0)

# The broken line (no leading `?`)
OLD = "                        '${s.serverOnline} \u00b7 ${_latencyMs}ms' // S30-S"
NEW = "                        ? '${s.serverOnline} \u00b7 ${_latencyMs}ms' // S30-S"

if OLD not in text:
    # Fallback: try without middot (in case dump encoding differs)
    OLD2 = "                        '${s.serverOnline} · ${_latencyMs}ms' // S30-S"
    NEW2 = "                        ? '${s.serverOnline} · ${_latencyMs}ms' // S30-S"
    if OLD2 in text:
        text = text.replace(OLD2, NEW2, 1)
        HOME.write_text(text, encoding="utf-8")
        print(f"{OK}  [home_screen.dart] hotfix: re-inserted missing `?` (fallback middot)")
        sys.exit(0)
    print(f"{ERR} anchor not found — file may have changed")
    print("       looking for:")
    print(f"       {repr(OLD)}")
    # Print surrounding context for diagnosis
    idx = text.find("S30-S")
    if idx != -1:
        print(f"       found 'S30-S' at {idx}:")
        print(f"       {repr(text[max(0,idx-60):idx+80])}")
    sys.exit(1)

text = text.replace(OLD, NEW, 1)
HOME.write_text(text, encoding="utf-8")
print(f"{OK}  [home_screen.dart] hotfix: re-inserted missing `?` before serverOnline string")
print()
print("Next:")
print("  git add lib/screens/home_screen.dart")
print("  git commit -m 'S30-hotfix: restore missing ? in banner ternary (S30-S regression)'")
print("  git push origin master")
