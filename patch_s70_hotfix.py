#!/usr/bin/env python3
"""
patch_s70_hotfix.py  —  S70-HOTFIX: fix broken S70 patch in LocalEngineRunner.kt
==================================================================================
Problem:  tilawa_fix_s70.py injected pb.environment()["KEY"] lines but `pb` is
          not defined inside an apply{} block → Kotlin compile error → CI failed
          → phone still runs old APK with --env flags → same crash.

Fix:      Remove the pb.environment() S70-ENV-FIX lines and deduplicate the
          environment() calls so the block is clean and compiles.

Run:
  cp /sdcard/Download/patch_s70_hotfix.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 patch_s70_hotfix.py 2>&1 | tee /sdcard/Download/hotfix_s70.txt
  git add -A && git commit -m "S70-HOTFIX: remove pb.environment() compile error" && git push
"""

import re
from pathlib import Path
from datetime import datetime

KT = Path.home() / 'tilawa-enhancer/android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt'

_log = []
def _h(t):  print(f'\n{"="*60}\n  {t}\n{"="*60}')
def _ok(m): print(f'  OK  {m}'); _log.append(('OK', m))
def _xx(m): print(f'  XX  {m}'); _log.append(('XX', m))
def _i(m):  print(f'       {m}')

HOTFIX_MARK = '// S70-HOTFIX'

_h(f'patch_s70_hotfix.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

if not KT.exists():
    _xx(f'File not found: {KT}'); exit(1)

txt = KT.read_text(encoding='utf-8')

if HOTFIX_MARK in txt:
    _ok('S70-HOTFIX already applied'); exit(0)

# ── STEP 1: Remove pb.environment() lines (wrong — pb undefined in apply{}) ──
pb_lines = re.findall(r'.*pb\.environment\(\).*\n', txt)
_i(f'Found {len(pb_lines)} pb.environment() lines to remove:')
for l in pb_lines:
    _i(f'  {l.rstrip()}')

cleaned = re.sub(r'[ \t]*pb\.environment\(\)\[.*?\].*\n', '', txt)
removed = len(pb_lines)

if removed > 0:
    _ok(f'Removed {removed} pb.environment() lines')
else:
    _xx('No pb.environment() lines found — check if already fixed or wrong file')
    exit(1)

# ── STEP 2: Fix indentation of runEngine ProcessBuilder block ──
# The apply block has mixed indentation after the bad patch.
# Replace the malformed block with a clean version.

OLD_BLOCK = '''\
            val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {
                environment()["HOME"] = "/root"
                environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
                environment()["TERM"] = "xterm"
            environment()["LD_LIBRARY_PATH"] = dataDir.absolutePath
            val prootTmp = File(dataDir, "proot-tmp").also { it.mkdirs() }
            environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath
            environment()["PROOT_FORCE_KOMPAT"] = "1"
            }.start()'''

NEW_BLOCK = '''\
            val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {  // S70-HOTFIX
                environment()["HOME"] = "/root"
                environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
                environment()["TERM"] = "xterm"
                environment()["LD_LIBRARY_PATH"] = dataDir.absolutePath
                val prootTmp = File(dataDir, "proot-tmp").also { it.mkdirs() }
                environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath
                environment()["PROOT_FORCE_KOMPAT"] = "1"
            }.start()'''

if OLD_BLOCK in cleaned:
    cleaned = cleaned.replace(OLD_BLOCK, NEW_BLOCK, 1)
    _ok('Fixed indentation of runEngine ProcessBuilder block')
else:
    # Fallback: just fix the indentation lines individually
    _i('Exact block not matched — trying line-by-line indent fix')
    cleaned = re.sub(
        r'^            environment\(\)\["LD_LIBRARY_PATH"\]',
        '                environment()["LD_LIBRARY_PATH"]',
        cleaned, flags=re.MULTILINE
    )
    cleaned = re.sub(
        r'^            val prootTmp = File\(dataDir, "proot-tmp"\)',
        '                val prootTmp = File(dataDir, "proot-tmp")',
        cleaned, flags=re.MULTILINE
    )
    cleaned = re.sub(
        r'^            environment\(\)\["PROOT_TMP_DIR"\]',
        '                environment()["PROOT_TMP_DIR"]',
        cleaned, flags=re.MULTILINE
    )
    cleaned = re.sub(
        r'^            environment\(\)\["PROOT_FORCE_KOMPAT"\]',
        '                environment()["PROOT_FORCE_KOMPAT"]',
        cleaned, flags=re.MULTILINE
    )
    # Fix the closing brace of apply{}
    cleaned = re.sub(
        r'^            \}\.start\(\)',
        '            }.start()',
        cleaned, flags=re.MULTILINE
    )
    _ok('Applied fallback indent fix')

# ── STEP 3: Verify no pb.environment() remain ──
remaining_pb = len(re.findall(r'pb\.environment\(\)', cleaned))
if remaining_pb == 0:
    _ok('No pb.environment() references remain')
else:
    _xx(f'{remaining_pb} pb.environment() references still present')

# ── STEP 4: Verify no --env remain in cmd lists ──
remaining_env = len(re.findall(r'"--env"', cleaned))
if remaining_env == 0:
    _ok('No --env flags in command lists')
else:
    _xx(f'{remaining_env} --env flags still in command lists — manual fix needed')

# ── STEP 5: Verify file compiles structurally (brace balance) ──
open_b  = cleaned.count('{')
close_b = cleaned.count('}')
if open_b == close_b:
    _ok(f'Brace balance OK ({open_b} open = {close_b} close)')
else:
    _xx(f'Brace imbalance: {open_b} open vs {close_b} close — check file manually')

# ── STEP 6: Save ──
KT.write_text(cleaned, encoding='utf-8')
_ok('LocalEngineRunner.kt saved')

# ── SUMMARY ──
_h('SUMMARY')
ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
for s, l in _log:
    print(f'  {"OK" if s=="OK" else "XX"}  {l}')
_h(f'{ok_n} OK   {xx_n} FAIL')
if xx_n == 0:
    print("""
  git add -A && git commit -m "S70-HOTFIX: remove pb.environment() compile error" && git push
""")
else:
    print('\n  Fix incomplete — paste full output back to Claude.\n')
