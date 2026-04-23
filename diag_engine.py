#!/usr/bin/env python3
"""
diag_engine.py — find exact anchor text in enhance_engine_v7.py
Run from ~/tilawa-enhancer: python3 diag_engine.py
"""
from pathlib import Path

text  = Path("enhance_engine_v7.py").read_text(encoding="utf-8")
lines = text.splitlines(keepends=True)
print(f"File: {len(text)} chars, {len(lines)} lines\n")

KEYWORDS = ["REF_CACHE", "REF_FILES", "__main__", "enhance_engine_v64"]

for kw in KEYWORDS:
    for i, line in enumerate(lines):
        if kw in line:
            start = max(0, i - 1)
            end   = min(len(lines), i + 6)
            print(f"--- '{kw}' at line {i+1} ---")
            for j in range(start, end):
                print(f"  {j+1:4d}  {repr(lines[j])}")
            print()
            break  # only first occurrence per keyword
