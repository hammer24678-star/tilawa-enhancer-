#!/usr/bin/env python3
"""
tilawa_fix_s29_v5.py  —  S29 Sacred Cosmos (v5 — two remaining fixes)
======================================================================
Fixes:
  MA1  — colorScheme in _buildDarkTheme(): anchor now includes `background:`
          (v3/v4 failed because they omitted that line from the old text)
  API  — duplicate clearAllJobRecords() in api_service.dart will crash the
          build; remove the broken first copy (no try/catch, wrong key).

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s29_v5.py

Session: S29-v5  (2026-05-21)
"""

import sys
from pathlib import Path
from datetime import datetime

def _h1(t):
    bar = '=' * 64
    print(f'\n{bar}\n  {t}\n{bar}')

def _h2(t):   print(f'\n  -- {t}')
def _ok(m):   print(f'     OK  {m}')
def _err(m):  print(f'     XX  {m}')
def _skip(m): print(f'     --  {m}')

_log = []

def _rec(sid, label, result): _log.append((sid, label, result))

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f'Anchor NOT found -- {label}')
        return text, False
    if c > 1:
        print(f'     !!  {c}x — using first -- {label}')
    else:
        _ok(f'Replaced -- {label}')
    return text.replace(old, new, 1), True

def _already(text, marker, label):
    if marker in text:
        _skip(f'Already applied -- {label}')
        return True
    return False

def _read(p):     return Path(p).read_text(encoding='utf-8')
def _write(p, t): Path(p).write_text(t, encoding='utf-8')

def _require(cond, msg):
    if not cond:
        _err(f'FATAL: {msg}')
        _summary()
        sys.exit(1)

def _summary():
    _h1('SUMMARY')
    print(f"\n  {'Step':<8}  {'Label':<52}  Result")
    print(f"  {'----':<8}  {'------':<52}  ------")
    for sid, label, result in _log:
        print(f'  {sid:<8}  {label:<52}  {result}')

REPO     = Path.home() / 'tilawa-enhancer'
LIB      = REPO / 'lib'
SERVICES = LIB / 'services'

_h1('tilawa_fix_s29_v5.py  --  Sacred Cosmos v5  --  '
    + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

_h2('Verify repo')
_require(REPO.exists(), 'REPO not found')
_require((LIB / 'main.dart').exists(), 'main.dart missing')
_require((SERVICES / 'api_service.dart').exists(), 'api_service.dart missing')
_ok('Repo OK')


###############################################################################
# MA1  main.dart — colorScheme in _buildDarkTheme()
# Exact old text from dump lines 37-42 (2sp/4sp, includes `background:`)
###############################################################################
_h1('MA1  main.dart — colorScheme')
txt = _read(LIB / 'main.dart')

MARKER_MA1 = 'secondary: Color(0xFF1B6B80),'
if not _already(txt, MARKER_MA1, 'colorScheme already Sacred Cosmos'):
    OLD_CS = (
        '  colorScheme: const ColorScheme.dark(\n'
        '    primary: Color(0xFFD4AF37),\n'
        '    surface: Color(0xFF161B22),\n'
        '    onSurface: Color(0xFFC9D1D9),\n'
        '    background: Color(0xFF0A0C10),\n'
        '  ),'
    )
    NEW_CS = (
        '  colorScheme: const ColorScheme.dark(\n'
        '    primary:   Color(0xFFD4AF37),\n'
        '    surface:   Color(0xFF0C1E28),\n'
        '    onSurface: Color(0xFFE2CFA0),\n'
        '    secondary: Color(0xFF1B6B80),\n'
        '  ),'
    )
    txt, ok = _replace_once(txt, OLD_CS, NEW_CS, 'colorScheme Sacred Cosmos (with background:)')
    _rec('MA1', 'colorScheme → Sacred Cosmos', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('MA1', 'colorScheme → Sacred Cosmos', '[--] SKIP')

_write(LIB / 'main.dart', txt)


###############################################################################
# API  api_service.dart — remove duplicate clearAllJobRecords()
# The first copy (no try/catch, wrong key 'saved_jobs') was added by S29-B1.
# The correct version (with try/catch, uses _jobsKey) was already present.
# Two methods with the same name = compile error.
###############################################################################
_h1('API  api_service.dart — remove duplicate clearAllJobRecords()')
txt = _read(SERVICES / 'api_service.dart')

MARKER_DUP = 'clearAllJobRecords() async {\n    final prefs = await SharedPreferences.getInstance();\n    await prefs.remove(\'saved_jobs\');'
BAD_COPY = (
    "  static Future<void> clearAllJobRecords() async {\n"
    "    final prefs = await SharedPreferences.getInstance();\n"
    "    await prefs.remove('saved_jobs');\n"
    "  }\n"
    "\n"
)

if BAD_COPY in txt:
    txt = txt.replace(BAD_COPY, '', 1)
    _ok('Removed bad duplicate clearAllJobRecords() (wrong key, no try/catch)')
    _rec('API1', 'Duplicate clearAllJobRecords() removed', '[OK] PASS')
elif txt.count('clearAllJobRecords()') == 1:
    _skip('Only one clearAllJobRecords() found — already clean')
    _rec('API1', 'Duplicate clearAllJobRecords() removed', '[--] SKIP')
else:
    _err('Could not find the bad duplicate — check api_service.dart manually')
    _rec('API1', 'Duplicate clearAllJobRecords() removed', '[XX] FAIL')

_write(SERVICES / 'api_service.dart', txt)


###############################################################################
# VERIFY — confirm no duplicate remains
###############################################################################
txt = _read(SERVICES / 'api_service.dart')
count = txt.count('clearAllJobRecords()')
if count == 1:
    _ok(f'api_service.dart now has exactly 1 clearAllJobRecords() ✓')
elif count == 0:
    _err('clearAllJobRecords() missing entirely — check file manually')
else:
    _err(f'{count} copies of clearAllJobRecords() still present — manual fix needed')


###############################################################################
# DONE
###############################################################################
_summary()

passed  = sum(1 for _, _, r in _log if r == '[OK] PASS')
skipped = sum(1 for _, _, r in _log if r.startswith('[--]'))
failed  = sum(1 for _, _, r in _log if r == '[XX] FAIL')

_h1(f'S29-v5 complete  —  {passed} PASS  {skipped} SKIP  {failed} FAIL')

if failed == 0:
    print("""
  All clean. Now build:
    cd ~/tilawa-enhancer
    flutter pub get
    flutter build apk --release --no-tree-shake-icons
""")
else:
    print("""
  To diagnose MA1, run:
    grep -n 'colorScheme' ~/tilawa-enhancer/lib/main.dart
  and paste back to Claude.
""")
