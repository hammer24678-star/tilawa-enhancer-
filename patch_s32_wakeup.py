#!/usr/bin/env python3
"""
patch_s32_wakeup.py — Auto-wake HuggingFace Space on offline detection
Fix: _checkServer() now auto-triggers _wakeServer() when server is offline,
     instead of waiting for the user to tap the "Wake Server" button.
The banner already shows gold/spinner "waking" state — no UI changes needed.
"""

import sys
from pathlib import Path

GREEN = "\033[32m"; RED = "\033[31m"; RESET = "\033[0m"
ok_count = 0; fail_count = 0

def patch(path_str, old, new, label):
    global ok_count, fail_count
    path = Path(path_str)
    if not path.exists():
        print(f"{RED}FAIL{RESET}  [{label}] — file not found"); fail_count += 1; return False
    src = path.read_text(encoding='utf-8')
    count = src.count(old)
    if count == 0:
        print(f"{RED}FAIL{RESET}  [{label}] — anchor not found"); fail_count += 1; return False
    if count > 1:
        print(f"{RED}FAIL{RESET}  [{label}] — ambiguous ({count}x)"); fail_count += 1; return False
    path.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f"{GREEN}OK{RESET}    [{label}]"); ok_count += 1; return True

# PATCH 1: auto-trigger _wakeServer() when server is detected offline
print("\n--- PATCH-1  Auto-wake on offline detection ---\n")

patch(
    'lib/screens/home_screen.dart',
    '  // \u2500\u2500 Server check \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '  Future<void> _checkServer() async {\n'
    '    final ms = await ApiService.checkServer();\n'
    '    if (mounted) setState(() { _serverUp = ms != null; _latencyMs = ms; });\n'
    '  }',
    '  // \u2500\u2500 Server check \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '  Future<void> _checkServer() async {\n'
    '    final ms = await ApiService.checkServer();\n'
    '    if (!mounted) return;\n'
    '    setState(() { _serverUp = ms != null; _latencyMs = ms; });\n'
    '    // S32: Auto-wake when offline — no longer needs manual button tap\n'
    '    if (ms == null && !_waking) _wakeServer();\n'
    '  }',
    'PATCH-1 _checkServer: auto-trigger _wakeServer on offline'
)

# PATCH 2: add pingServer() to api_service
print("\n--- PATCH-2  api_service: add pingServer() ---\n")

patch(
    'lib/services/api_service.dart',
    '  // \u2500\u2500 S28-T2: Share audio file via Android share sheet \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '  static Future<void> shareAudio(String uri) async {',
    '  // \u2500\u2500 S32: Silent keep-alive ping \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '  static Future<void> pingServer() async {\n'
    '    try {\n'
    '      await http.get(Uri.parse(\'$_base/\')).timeout(const Duration(seconds: 8));\n'
    '    } catch (_) {}\n'
    '  }\n'
    '\n'
    '  // \u2500\u2500 S28-T2: Share audio file via Android share sheet \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '  static Future<void> shareAudio(String uri) async {',
    'PATCH-2 api_service: add pingServer()'
)

print(f"\n--- SUMMARY ---\n")
print(f"  PASSED: {ok_count}")
print(f"  FAILED: {fail_count}\n")
if fail_count > 0:
    print("STOP — fix FAIL items before pushing."); sys.exit(1)
else:
    print("All patches applied. Push and trigger a build."); sys.exit(0)
