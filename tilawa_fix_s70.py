#!/usr/bin/env python3
"""
tilawa_fix_s70.py  —  S70: fix proot --env unknown option
==========================================================
Error:  proot error: unknown option '--env'
Cause:  proot binary doesn't support --env flag
Fix:    Strip all "--env","KEY=VAL" pairs from command list
        Inject them into ProcessBuilder.environment() instead
        Also try: use `env KEY=VAL` prepended inside proot as fallback

Run:
  cp /sdcard/Download/tilawa_fix_s70.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s70.py 2>&1 | tee /sdcard/Download/fix_s70.txt
  git add -A && git commit -m "S70: fix proot --env unknown option" && git push
"""

import re
from pathlib import Path
from datetime import datetime

KT = Path.home() / 'tilawa-enhancer/android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt'

_log = []
def _h(t):  print(f'\n{"="*60}\n  {t}\n{"="*60}')
def _ok(m): print(f'  OK  {m}'); _log.append(('OK', m))
def _xx(m): print(f'  XX  {m}'); _log.append(('XX', m))
def _sk(m): print(f'  --  {m}'); _log.append(('SK', m))
def _i(m):  print(f'       {m}')

MARK = '// S70-ENV-FIX'

_h(f'tilawa_fix_s70.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

if not KT.exists():
    _xx(f'File not found: {KT}')
    exit(1)

txt = KT.read_text(encoding='utf-8')

if MARK in txt:
    _sk('S70 already applied')
    exit(0)

# ── STEP 1: Find all "--env","KEY=VAL" pairs in command list ──
# Handles both:
#   "--env", "KEY=VAL"
#   "--env", "KEY=$var"
env_pairs = re.findall(r'"--env",\s*"([^"]+)"', txt)
_i(f'Found {len(env_pairs)} --env pairs: {env_pairs}')

# ── STEP 2: Remove "--env","VAL" from the command list ──
# Remove each pair (with any trailing comma+whitespace)
env_pattern = re.compile(r'\s*"--env",\s*"[^"]+",?\s*')

# Count occurrences
matches = list(re.finditer(r'"--env",\s*"[^"]+"', txt))
_i(f'Regex matched {len(matches)} occurrences to remove')

if not matches:
    _xx('No --env flags found in file — wrong file or already fixed')
    # Show lines with proot to help diagnose
    for i, line in enumerate(txt.splitlines(), 1):
        if 'proot' in line.lower() or '--env' in line:
            _i(f'  {i}: {line[:100]}')
    exit(1)

# Remove all --env pairs from command list
# We do this carefully — remove ", \"--env\", \"VAL\"" or "\"--env\", \"VAL\"," 
cleaned = txt

# Remove pattern: "\"--env\", \"...\","  (with trailing comma)
cleaned = re.sub(r'"--env",\s*"[^"]+",\s*\n?', '', cleaned)
# Remove pattern: "\"--env\", \"...\"" (without trailing comma, e.g. last in list)
cleaned = re.sub(r',?\s*"--env",\s*"[^"]+"', '', cleaned)

removed = len(re.findall(r'"--env"', txt)) - len(re.findall(r'"--env"', cleaned))
_i(f'Removed {removed} --env entries from command list')

# ── STEP 3: Inject env vars via ProcessBuilder.environment() ──
# Build the Kotlin lines to add after ProcessBuilder creation
if env_pairs:
    env_lines = '\n'.join(
        f'        pb.environment()["{pair.split("=")[0]}"] = "{("=".join(pair.split("=")[1:]))}"  {MARK}'
        for pair in env_pairs
    )
else:
    # Common proot env vars if none found (safe defaults)
    env_lines = f'''        pb.environment()["HOME"] = "/root"  {MARK}
        pb.environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"  {MARK}
        pb.environment()["TMPDIR"] = "/tmp"  {MARK}'''

# Find ProcessBuilder instantiation to inject after it
# Matches: val pb = ProcessBuilder(...) or val process = ProcessBuilder(
pb_pattern = re.compile(
    r'(val \w+ = ProcessBuilder\([^)]+\)\.?\w*\([^)]*\)?\s*\n)',
    re.MULTILINE
)

# Try simpler match too
pb_simple = re.compile(
    r'(val \w+ = ProcessBuilder\(.*?\n)',
    re.MULTILINE
)

m = pb_pattern.search(cleaned) or pb_simple.search(cleaned)

if m:
    insert_after = m.group(0)
    replacement = insert_after + env_lines + '\n'
    cleaned = cleaned.replace(insert_after, replacement, 1)
    _ok(f'Injected {len(env_pairs) or 3} env vars into ProcessBuilder.environment()')
else:
    # Fallback: find "val pb" or "ProcessBuilder" line manually
    lines = cleaned.splitlines()
    insert_idx = None
    for i, line in enumerate(lines):
        if 'ProcessBuilder' in line:
            insert_idx = i + 1
            break
    if insert_idx:
        lines.insert(insert_idx, env_lines)
        cleaned = '\n'.join(lines)
        _ok(f'Injected env vars after ProcessBuilder (fallback line insert)')
    else:
        _xx('Could not find ProcessBuilder line — cannot inject env vars')

# ── STEP 4: Verify no --env left ──
remaining = len(re.findall(r'"--env"', cleaned))
if remaining == 0:
    _ok('All --env flags removed from command list')
else:
    _xx(f'Still {remaining} --env flags remaining — check output')

# ── STEP 5: Write file ──
if '// S70-ENV-FIX' in cleaned or remaining == 0:
    KT.write_text(cleaned, encoding='utf-8')
    _ok('LocalEngineRunner.kt saved')
else:
    _xx('File NOT saved — fix incomplete')

# ── SUMMARY ──
_h('SUMMARY')
ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
for s, l in _log:
    print(f'  {"OK" if s=="OK" else ("--" if s=="SK" else "XX")}  {l}')
_h(f'{ok_n} OK   {xx_n} FAIL')
if xx_n == 0:
    print("""
  git add -A && git commit -m "S70: fix proot --env unknown option" && git push
""")
else:
    print('\n  Fix incomplete — paste full output back to Claude.\n')
