#!/usr/bin/env python3
"""patch_s28_t5.py — Remove 2 remaining duplicate lines"""

from pathlib import Path, sys
import sys

REPO = Path(".")

def remove_second_line_containing(path: Path, marker: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    lines = text.split('\n')
    found = []
    for i, line in enumerate(lines):
        if marker in line:
            found.append(i)
    if len(found) < 2:
        print(f"  OK   [{path.name}] {label}: only {len(found)} occurrence(s) — nothing to fix")
        return
    # Remove the SECOND occurrence
    del lines[found[1]]
    path.write_text('\n'.join(lines), encoding="utf-8")
    print(f"  FIXED [{path.name}] {label}: removed line {found[1]+1} (duplicate)")

# Fix 1: shareBtn duplicate in lang_provider.dart
remove_second_line_containing(
    REPO / "lib/state/lang_provider.dart",
    "shareBtn",
    "shareBtn duplicate"
)

# Fix 2: originalName duplicate parameter in api_service.dart
remove_second_line_containing(
    REPO / "lib/services/api_service.dart",
    "String? originalName",
    "originalName param duplicate"
)

print()
print("Done. Next:")
print("  git add lib/state/lang_provider.dart lib/services/api_service.dart")
print("  git commit -m 'S28-T5: remove 2 duplicate lines'")
print("  git push origin master")
