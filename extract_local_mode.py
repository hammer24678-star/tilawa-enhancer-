#!/usr/bin/env python3
"""
extract_local_mode.py
=====================
Extracts all local mode related code from home_screen.dart and patch_android.py
"""
from pathlib import Path
import re

hs = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
pa = Path.home() / 'tilawa-enhancer/patch_android.py'
out = Path('/sdcard/Download/local_mode_code.txt')

lines_hs = hs.read_text(encoding='utf-8').splitlines()
lines_pa = pa.read_text(encoding='utf-8').splitlines()

KEYWORDS = [
    '_localMode', '_localReady', '_localMsg', '_processLocal',
    'LocalEngineService', 'isSetupComplete', 'setupDone', 'setupError',
    'setupProgress', 'engineDone', 'engineError', 'engineProgress',
    'runEngine', 'cancelEngine', 'startSetup', '_process(', '_process(',
    'localOnly', 'SetupScreen', 'localModeToggle', '_localModeToggle',
    'CHANNEL', 'LocalEngineRunner', 'isSetupComplete', 'setup_complete',
    'safeSetup', 'prootBin', 'alpineDir', 'enginesDir',
]

result = []

def extract_sections(lines, filename, keywords):
    result.append(f'\n{"="*70}')
    result.append(f'  FILE: {filename}')
    result.append(f'{"="*70}\n')
    
    # Find all matching line numbers
    matches = set()
    for i, line in enumerate(lines, 1):
        for kw in keywords:
            if kw in line:
                # Include context: 3 lines before, 3 after
                for j in range(max(0, i-4), min(len(lines), i+4)):
                    matches.add(j)
                break
    
    if not matches:
        result.append('  No matches found.')
        return
    
    # Group consecutive lines into blocks
    sorted_lines = sorted(matches)
    blocks = []
    if sorted_lines:
        block = [sorted_lines[0]]
        for ln in sorted_lines[1:]:
            if ln - block[-1] <= 5:
                block.append(ln)
            else:
                blocks.append(block)
                block = [ln]
        blocks.append(block)
    
    for block in blocks:
        start = block[0]
        end = block[-1]
        result.append(f'  ── Lines {start+1}–{end+1} ──')
        for i in range(start, end+1):
            result.append(f'  {i+1:4d}  {lines[i]}')
        result.append('')

extract_sections(lines_hs, 'home_screen.dart', KEYWORDS)
extract_sections(lines_pa, 'patch_android.py', KEYWORDS)

# Also dump full _processLocal function
result.append(f'\n{"="*70}')
result.append('  FULL _processLocal() FUNCTION')
result.append(f'{"="*70}\n')

in_func = False
brace_depth = 0
for i, line in enumerate(lines_hs, 1):
    if '_processLocal()' in line and 'Future' in line:
        in_func = True
    if in_func:
        result.append(f'  {i:4d}  {line}')
        brace_depth += line.count('{') - line.count('}')
        if in_func and brace_depth <= 0 and i > 1:
            break

# Full isSetupComplete
result.append(f'\n{"="*70}')
result.append('  FULL isSetupComplete() in patch_android.py')
result.append(f'{"="*70}\n')

in_func = False
for i, line in enumerate(lines_pa, 1):
    if 'isSetupComplete' in line and 'fun ' in line:
        in_func = True
    if in_func:
        result.append(f'  {i:4d}  {line}')
        if in_func and '}' in line and i > 1:
            break

text = '\n'.join(result)
out.write_text(text, encoding='utf-8')
print(f'Written to {out}')
print(f'Total lines extracted: {len(result)}')
