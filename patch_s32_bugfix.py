#!/usr/bin/env python3
"""
patch_s32_bugfix.py — Session 32 comprehensive bug fixes
Run from Flutter repo root: python3 patch_s32_bugfix.py

BUG MANIFEST (7 bugs):
  BUG-1  CRITICAL  Firebase in pubspec/main/api_service without Google Services
                   Gradle plugin → build failure or silent init crash.
                   Fix: remove Firebase entirely (it's optional + not configured).

  BUG-2  HIGH      _fallbackRetries reset to 0 UNCONDITIONALLY inside _process()
                   on every call — auto-retry limit of 2 is never enforced.
                   The code even has a comment saying NOT to reset it there.
                   Fix: add {bool userInitiated=true} param; reset only when true.

  BUG-3  HIGH      Fallback warning shown when score <= 78, but score 78 gets
                   the "Good" (decent) label — not a fallback score.
                   Fix: change <= 78 to < 78 in the warning guard.

  BUG-4  MEDIUM    buildFilename() has no entry for v10.0, v9.0, v8.5 — the
                   three most-used engines. Falls back to ugly 'v10_0' etc.
                   Fix: add all current engines to the map.

  BUG-5  LOW       loadLastEngine() catch block returns 'v9.0' but normal path
                   defaults to 'v10.0'. Inconsistent.
                   Fix: catch block also returns 'v10.0'.

  BUG-6  MEDIUM    Clear-All dialog in history_screen uses hardcoded dark-mode
                   text colors → invisible / wrong in light mode.
                   Fix: use _tText / _tSub cached theme colors.

  BUG-7  MEDIUM    Job card original_name text uses hardcoded dark-mode color
                   Color(0xFFC9D1D9) → light gray on parchment in light mode.
                   Fix: use _tText.
"""

import sys
from pathlib import Path

# ── Colour codes for terminal ─────────────────────────────────────────────────
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
RESET  = "\033[0m"

ok_count   = 0
fail_count = 0
results    = []

def patch(path_str: str, old: str, new: str, label: str) -> bool:
    global ok_count, fail_count
    path = Path(path_str)
    if not path.exists():
        msg = f"{RED}FAIL{RESET}  [{label}] — file not found: {path_str}"
        print(msg); results.append(msg); fail_count += 1; return False
    src = path.read_text(encoding='utf-8')
    count = src.count(old)
    if count == 0:
        msg = f"{RED}FAIL{RESET}  [{label}] — anchor not found in {path_str}"
        print(msg); results.append(msg); fail_count += 1; return False
    if count > 1:
        msg = f"{RED}FAIL{RESET}  [{label}] — anchor matched {count}× (ambiguous)"
        print(msg); results.append(msg); fail_count += 1; return False
    path.write_text(src.replace(old, new, 1), encoding='utf-8')
    msg = f"{GREEN}OK{RESET}    [{label}]"
    print(msg); results.append(msg); ok_count += 1; return True

# ═══════════════════════════════════════════════════════════════════════════════
print("\n─── BUG-1  Remove Firebase (critical — not properly configured) ───\n")
# ═══════════════════════════════════════════════════════════════════════════════

# 1a: pubspec.yaml — remove firebase dependencies
patch(
    'pubspec.yaml',
    '  firebase_core: ^3.0.0\n'
    '  firebase_messaging: ^15.0.0\n'
    '  http: ^1.2.0',
    '  http: ^1.2.0',
    'BUG-1a pubspec: remove firebase_core + firebase_messaging'
)

# 1b: main.dart — remove Firebase imports
patch(
    'lib/main.dart',
    'import \'package:firebase_core/firebase_core.dart\';\n'
    'import \'package:firebase_messaging/firebase_messaging.dart\';\n'
    'import \'package:flutter/material.dart\';',
    'import \'package:flutter/material.dart\';',
    'BUG-1b main.dart: remove Firebase imports'
)

# 1c: main.dart — remove Firebase init block
patch(
    'lib/main.dart',
    '  try {\n'
    '    await Firebase.initializeApp();\n'
    '    final messaging = FirebaseMessaging.instance;\n'
    '    await messaging.requestPermission(alert: true, badge: true, sound: true);\n'
    '  } catch (_) {\n'
    '    // FCM not configured — app runs normally without push notifications\n'
    '  }\n'
    '  FlutterError.onError = FlutterError.presentError;',
    '  FlutterError.onError = FlutterError.presentError;',
    'BUG-1c main.dart: remove Firebase.initializeApp() block'
)

# 1d: api_service.dart — remove Firebase import
patch(
    'lib/services/api_service.dart',
    'import \'package:firebase_messaging/firebase_messaging.dart\';\n'
    'import \'dart:io\';',
    'import \'dart:io\';',
    'BUG-1d api_service.dart: remove firebase_messaging import'
)

# 1e: api_service.dart — remove _getFcmToken() method
patch(
    'lib/services/api_service.dart',
    '  }  // ── Upload — auto-selects direct or chunked ────────────────────────────────\n'
    '\n'
    '  /// Get FCM token for push notifications (null if not available)\n'
    '  static Future<String?> _getFcmToken() async {\n'
    '    try {\n'
    '      final messaging = FirebaseMessaging.instance;\n'
    '      return await messaging.getToken();\n'
    '    } catch (_) {\n'
    '      return null;\n'
    '    }\n'
    '  }\n'
    '\n'
    '  static Future<Map<String, dynamic>> uploadFile(',
    '  }  // ── Upload — auto-selects direct or chunked ────────────────────────────────\n'
    '\n'
    '  static Future<Map<String, dynamic>> uploadFile(',
    'BUG-1e api_service.dart: remove _getFcmToken() method'
)

# 1f: api_service.dart — replace _getFcmToken() call with empty string
patch(
    'lib/services/api_service.dart',
    "          'fcm_token': await _getFcmToken() ?? '',",
    "          'fcm_token': '',",
    'BUG-1f api_service.dart: replace _getFcmToken() call with empty string'
)

# ═══════════════════════════════════════════════════════════════════════════════
print("\n─── BUG-2  _fallbackRetries reset unconditionally in _process() ───\n")
# ═══════════════════════════════════════════════════════════════════════════════

# 2a: Change _process() signature + move reset outside setState + remove wrong comment
patch(
    'lib/screens/home_screen.dart',
    '  Future<void> _process() async {\n'
    '    if (_file == null || !_serverUp) return;\n'
    '    HapticFeedback.mediumImpact();\n'
    '    setState(() {\n'
    '      _busy = true; _progress = 0.02;\n'
    '      _status = LangProvider.strings(context).uploading;\n'
    '      _output = null; _result = null;\n'
    '      _fallbackRetries = 0; // S32: reset for new file\n'
    '    });\n'
    '    _processStart = DateTime.now(); // S22: start clock for timeout\n'
    '    _pollErrors = 0;               // S22: reset in case of re-process\n'
    '    // S32: do NOT reset _fallbackRetries here — it must persist across\n'
    '    // auto-retries triggered by _downloadAndSave. Only reset on user-\n'
    '    // initiated process (detected by _fallbackRetries already being 0).\n'
    '    try {',
    '  // S32-BUG2-FIX: userInitiated=true for button tap, false for auto-retry.\n'
    '  // Previously _fallbackRetries was reset inside setState() unconditionally,\n'
    '  // meaning auto-retries always reset the counter → limit of 2 was never hit.\n'
    '  Future<void> _process({bool userInitiated = true}) async {\n'
    '    if (_file == null || !_serverUp) return;\n'
    '    HapticFeedback.mediumImpact();\n'
    '    if (userInitiated) _fallbackRetries = 0; // reset only on fresh user action\n'
    '    setState(() {\n'
    '      _busy = true; _progress = 0.02;\n'
    '      _status = LangProvider.strings(context).uploading;\n'
    '      _output = null; _result = null;\n'
    '    });\n'
    '    _processStart = DateTime.now(); // S22: start clock for timeout\n'
    '    _pollErrors = 0;               // S22: reset in case of re-process\n'
    '    try {',
    'BUG-2a home_screen: _process() signature + reset guard'
)

# 2b: auto-retry call passes userInitiated: false
patch(
    'lib/screens/home_screen.dart',
    '        if (mounted) _process();',
    '        if (mounted) _process(userInitiated: false);',
    'BUG-2b home_screen: auto-retry calls _process(userInitiated: false)'
)

# ═══════════════════════════════════════════════════════════════════════════════
print("\n─── BUG-3  Fallback warning threshold: <= 78 → < 78 ───\n")
# ═══════════════════════════════════════════════════════════════════════════════

# The guard in _resultCard shows the warning for score <= 78.
# But score 78 gets the "Good" (decent) label — it's not fallback.
# The true fallback score is 75. Only scores < 78 should show the warning.
patch(
    'lib/screens/home_screen.dart',
    '        if (score <= 78) ...[',
    '        if (score < 78) ...[  // S32-BUG3-FIX: 78 = Good label, not fallback',
    'BUG-3 home_screen: fallback warning guard <= 78 → < 78'
)

# ═══════════════════════════════════════════════════════════════════════════════
print("\n─── BUG-4  buildFilename missing v10.0, v9.0, v8.5 ───\n")
# ═══════════════════════════════════════════════════════════════════════════════

patch(
    'lib/services/api_service.dart',
    "    const engineNames = {\n"
    "      'v8.0': 'Calibrated_Precision',\n"
    "      'v7.6': 'Intelligent_Assessment',\n"
    "      'v7.5': 'Disciplined_Precision',\n"
    "      'v7.0': 'Classic',\n"
    "    };",
    "    const engineNames = {\n"
    "      'v10.0': 'Aetherion_Foundation',   // S32-BUG4-FIX\n"
    "      'v9.0':  'The_Evolution',\n"
    "      'v8.5':  'Honest_Ceiling',\n"
    "      'v8.0':  'Calibrated_Precision',\n"
    "      'v7.6':  'Intelligent_Assessment',\n"
    "      'v7.5':  'Disciplined_Precision',\n"
    "      'v7.0':  'Classic',\n"
    "    };",
    'BUG-4 api_service: buildFilename add v10.0, v9.0, v8.5'
)

# ═══════════════════════════════════════════════════════════════════════════════
print("\n─── BUG-5  loadLastEngine catch returns v9.0 (should be v10.0) ───\n")
# ═══════════════════════════════════════════════════════════════════════════════

patch(
    'lib/services/api_service.dart',
    "      return prefs.getString(_lastEngineKey) ?? 'v10.0'; // S31\n"
    "    } catch (_) {\n"
    "      return 'v9.0';\n"
    "    }",
    "      return prefs.getString(_lastEngineKey) ?? 'v10.0'; // S31\n"
    "    } catch (_) {\n"
    "      return 'v10.0'; // S32-BUG5-FIX: was 'v9.0', inconsistent with normal path\n"
    "    }",
    "BUG-5 api_service: loadLastEngine catch → v10.0"
)

# ═══════════════════════════════════════════════════════════════════════════════
print("\n─── BUG-6  History dialog hardcoded dark text in light mode ───\n")
# ═══════════════════════════════════════════════════════════════════════════════

patch(
    'lib/screens/history_screen.dart',
    "        content: Text(s.clearAllConfirm,\n"
    "          style: const TextStyle(color: Color(0xFFC9D1D9))),\n"
    "        actions: [\n"
    "          TextButton(\n"
    "            onPressed: () => Navigator.pop(ctx, false),\n"
    "            child: Text(s.ar ? 'لا' : 'No',\n"
    "              style: const TextStyle(color: Color(0xFF8B949E)))),",
    "        content: Text(s.clearAllConfirm,\n"
    "          style: TextStyle(color: _tText)), // S32-BUG6-FIX: theme-aware\n"
    "        actions: [\n"
    "          TextButton(\n"
    "            onPressed: () => Navigator.pop(ctx, false),\n"
    "            child: Text(s.ar ? 'لا' : 'No',\n"
    "              style: TextStyle(color: _tSub))), // S32-BUG6-FIX",
    'BUG-6 history: dialog text colors → _tText / _tSub'
)

# ═══════════════════════════════════════════════════════════════════════════════
print("\n─── BUG-7  Job card original_name hardcoded dark color ───\n")
# ═══════════════════════════════════════════════════════════════════════════════

patch(
    'lib/screens/history_screen.dart',
    "                style: const TextStyle(\n"
    "                  color: Color(0xFFC9D1D9), fontSize: 11,\n"
    "                  fontWeight: FontWeight.bold)),",
    "                style: TextStyle(\n"
    "                  color: _tText, fontSize: 11, // S32-BUG7-FIX: theme-aware\n"
    "                  fontWeight: FontWeight.bold)),",
    'BUG-7 history: original_name text color → _tText'
)

# ═══════════════════════════════════════════════════════════════════════════════
print("\n─── SUMMARY ─────────────────────────────────────────────────────────\n")
# ═══════════════════════════════════════════════════════════════════════════════

print(f"  {GREEN}PASSED{RESET}: {ok_count}")
print(f"  {RED}FAILED{RESET}: {fail_count}")
print()

if fail_count > 0:
    print(f"{RED}STOP — fix FAIL items above before pushing.{RESET}")
    sys.exit(1)
else:
    print(f"{GREEN}All patches applied. Push and trigger a build.{RESET}")
    sys.exit(0)
