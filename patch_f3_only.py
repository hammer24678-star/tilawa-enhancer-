#!/usr/bin/env python3
"""
patch_f3_only.py  —  remove v8.7 engine entry from home_screen.dart

The original patch_s31_fixes.py F3 failed because the Arabic description
in the file has 'يُشغِّل' (with kasra U+0650 before shadda) while the
anchor had 'يُشغّل' (no kasra).  This script uses ASCII-only anchors
that cannot have diacritic mismatches.

Run from ~/tilawa-enhancer/ then commit+push.
"""

import re
from pathlib import Path

HOME = Path("lib/screens/home_screen.dart")

OK   = "\033[92m OK  \033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"

if not HOME.exists():
    print(f"{ERR} {HOME} not found — run from repo root")
    raise SystemExit(1)

text = HOME.read_text(encoding="utf-8")

SKIP_MARKER = "v8.7 removed S31-F3"
if SKIP_MARKER in text:
    print(f"\033[94m SKIP\033[0m already applied — F3")
    raise SystemExit(0)

# ── Locate the block using ASCII-only boundaries ────────────────────────
# Start: the comment line just before the _EngineData( for v8.7
START_ANCHOR = "    // v8.9 removed S31\n    _EngineData(\n      'v8.7',"

# End: the closing paren of that _EngineData block.
# Strategy: find START_ANCHOR, then scan forward for the next standalone
# "    )," that closes this block (not nested).
start_idx = text.find(START_ANCHOR)
if start_idx == -1:
    print(f"{WARN} start anchor not found — is v8.7 already gone?")
    raise SystemExit(1)

# Scan from start_idx forward for the closing "),"
# The block ends at the first "    )," that appears on its own line.
close_pat = re.compile(r'\n    \),')
m = close_pat.search(text, start_idx + len(START_ANCHOR))
if not m:
    print(f"{WARN} closing '), ' not found after v8.7 anchor")
    raise SystemExit(1)

end_idx = m.end()   # position just after the closing  ),

block = text[start_idx:end_idx]
print("Block to remove:")
print("  first line:", repr(block.split('\n')[0]))
print("  last line: ", repr(block.split('\n')[-1]))
print(f"  chars: {len(block)}")

replacement = "    // v8.9 removed S31 | v8.7 removed S31-F3"

new_text = text[:start_idx] + replacement + text[end_idx:]

HOME.write_text(new_text, encoding="utf-8")
print(f"{OK}  [home_screen.dart] F3: v8.7 entry removed")

print()
print("Next:")
print("  git add lib/screens/home_screen.dart")
print("  git commit -m 'S31-F3: remove v8.7 engine entry (diacritic fix)'")
print("  git push origin master")
