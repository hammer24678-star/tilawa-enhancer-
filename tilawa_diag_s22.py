#!/usr/bin/env python3
"""
tilawa_diag_s22.py — find the exact catch(_) block text in home_screen.dart
Run from repo root: python3 tilawa_diag_s22.py
"""
from pathlib import Path

text = Path("lib/screens/home_screen.dart").read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)

print(f"File: {len(text)} chars, {len(lines)} lines\n")

# Find every line containing "catch"
for i, line in enumerate(lines):
    if "catch" in line:
        start = max(0, i - 3)
        end   = min(len(lines), i + 6)
        print(f"--- catch at line {i+1} ---")
        for j in range(start, end):
            safe = lines[j].rstrip("\n")
            # show repr so we can see Unicode chars
            print(f"  {j+1:4d}  {repr(safe)}")
        print()
