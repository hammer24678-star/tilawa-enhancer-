#!/usr/bin/env python3
"""patch_s32_wakeup2.py — PATCH-1 retry with minimal anchor"""
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

# Use the body only — no comment line with box-drawing chars
patch(
    'lib/screens/home_screen.dart',
    '  Future<void> _checkServer() async {\n'
    '    final ms = await ApiService.checkServer();\n'
    '    if (mounted) setState(() { _serverUp = ms != null; _latencyMs = ms; });\n'
    '  }',
    '  Future<void> _checkServer() async {\n'
    '    final ms = await ApiService.checkServer();\n'
    '    if (!mounted) return;\n'
    '    setState(() { _serverUp = ms != null; _latencyMs = ms; });\n'
    '    // S32: auto-wake when offline — no manual tap needed\n'
    '    if (ms == null && !_waking) _wakeServer();\n'
    '  }',
    'PATCH-1 _checkServer auto-wake'
)

print(f"\nPASSED: {ok}  FAILED: {fail}")
sys.exit(0 if fail == 0 else 1)
