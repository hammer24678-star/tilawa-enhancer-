#!/usr/bin/env python3
"""
patch_s32_wake_extend.py — Extend wake timeout 35s → 90s
HuggingFace can take up to 90s to cold-boot. 7 attempts × 5s = 35s is not enough.
Fix: 18 attempts × 5s = 90s maximum wait.
"""
import sys
from pathlib import Path

GREEN = "\033[32m"; RED = "\033[31m"; RESET = "\033[0m"
ok = 0; fail = 0

def patch(path_str, old, new, label):
    global ok, fail
    path = Path(path_str)
    if not path.exists():
        print(f"{RED}FAIL{RESET}  [{label}] file not found"); fail+=1; return
    src = path.read_text(encoding='utf-8')
    n = src.count(old)
    if n == 0:
        print(f"{RED}FAIL{RESET}  [{label}] anchor not found"); fail+=1; return
    if n > 1:
        print(f"{RED}FAIL{RESET}  [{label}] ambiguous ({n}x)"); fail+=1; return
    path.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f"{GREEN}OK{RESET}    [{label}]"); ok+=1

patch(
    'lib/screens/home_screen.dart',
    '      if (up || _wakeAttempts >= 7) { // max 35s',
    '      if (up || _wakeAttempts >= 18) { // S32: max 90s (HF cold-boot can take ~60-90s)',
    'PATCH-1 extend wake timeout 35s → 90s'
)

print(f"\nPASSED: {ok}  FAILED: {fail}")
sys.exit(0 if fail == 0 else 1)
