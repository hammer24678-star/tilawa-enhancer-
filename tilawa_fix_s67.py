#!/usr/bin/env python3
"""
tilawa_fix_s67.py — Fix Kotlin writeText newline escaping
=========================================================
Root cause: S65 appended a Python string to patch_android.py
containing  \\n  (backslash-n as a Python escape sequence).
When patch_android.py runs in CI, Python converts \\n → chr(10),
writing raw newlines into the Kotlin string literal.

Result: LocalEngineRunner.kt lines 107-110 have actual line breaks
inside a regular Kotlin string, which is a syntax error:

  BROKEN (Kotlin file as generated):
    .writeText("nameserver 8.8.8.8
nameserver 1.1.1.1
")

  FIXED (Kotlin file after this patch):
    .writeText("nameserver 8.8.8.8\\nnameserver 1.1.1.1\\n")

Fix: change \\n → \\\\n in patch_android.py so that when Python
runs it later, it outputs the two-char Kotlin escape sequence,
not a raw newline byte.

Errors eliminated (LocalEngineRunner.kt):
  107:47  Syntax error: Expecting '"'
  108:1   Unresolved reference 'nameserver'
  108:15  Syntax error: Expecting ','
  108:15  Argument type mismatch: Charset expected
  109:1   Too many arguments for writeText
  110:13  Unresolved reference 'File'
"""
from pathlib import Path
from datetime import datetime

PA = Path.home() / 'tilawa-enhancer/patch_android.py'

def _h(t): print(f'\n{"="*54}\n  {t}\n{"="*54}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'  XX  NOT FOUND — {m}'); exit(1)

_h(f'S67  {datetime.now().strftime("%H:%M:%S")}')

# Read patch_android.py as raw bytes → Python sees backslash+n as \\n
txt = PA.read_text(encoding='utf-8')

# OLD: in patch_android.py the string has \n (backslash+n, two chars).
# Python interprets these as newlines when running patch_android.py → broken Kotlin.
# In this fix script's source, we write \\n to match those two chars in the file.
old = '                .writeText("nameserver 8.8.8.8\\nnameserver 1.1.1.1\\n")'

# NEW: we want \\n (three chars: backslash, backslash, n) in the file.
# When patch_android.py later runs, Python converts \\n → \n (Kotlin escape).
# In this fix script's source, we write \\\\n to produce those three chars.
new = '                .writeText("nameserver 8.8.8.8\\\\nnameserver 1.1.1.1\\\\n")'

if old not in txt:
    print(f'  -- old string not found — checking if already fixed...')
    if new in txt:
        _ok('Already fixed: \\\\n present in patch_android.py — nothing to do')
        exit(0)
    else:
        _xx('resolv.conf writeText line not found in patch_android.py')

count = txt.count(old)
print(f'  found {count} occurrence(s) of broken writeText')

txt = txt.replace(old, new, 1)
PA.write_text(txt, encoding='utf-8')
_ok('patch_android.py: writeText newline escape fixed')

# Verify
if new in PA.read_text(encoding='utf-8'):
    _ok('Verified: double-escaped newline present')
else:
    _xx('Verification failed — fix did not apply')

_h('DONE')
print()
print('  git add patch_android.py')
print('  git commit -m "S67: fix resolv.conf writeText Kotlin escape in patch_android.py"')
print('  git push')
print()
print('  Expected: LocalEngineRunner.kt compiles cleanly.')
print('  If build still fails on other Kotlin lines, run diag:')
print('    grep -n "resolv\\|nameserver\\|writeText" patch_android.py')
print()
