#!/usr/bin/env python3
"""
patch_s198_fix_s196_s197_imports.py — S198

Two import bugs from the last two patches that will break the build:

  BUG-1  ai_tools_screen.dart (S196-BUG-I) — added
         `import '../providers/lang_provider.dart';` but the file actually
         lives at lib/state/lang_provider.dart (same path every other
         screen uses — see audio_editor_screen.dart, home_screen.dart).
         There is no lib/providers/ directory, so this is a "Target of URI
         doesn't exist" compile error. Fix: correct the path to '../state/...'.

  BUG-2  audio_editor_screen.dart (S197-BUG-B) — added three
         `StreamSubscription<...>` fields but StreamSubscription lives in
         dart:async, which this file never imports (only dart:math,
         dart:io, and flutter/audioplayers packages). home_screen.dart
         already does `import 'dart:async';` for the exact same reason —
         audio_editor_screen.dart needs the same import or it won't
         resolve the type.

Usage:  python3 patch_s198_fix_s196_s197_imports.py /path/to/tilawa-enhancer
"""
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
if not (REPO / 'lib').exists():
    print(f'ERROR: lib/ not found in {REPO}')
    sys.exit(1)

STAMP = REPO / '.patch_s198_fix_s196_s197_imports_done'
if STAMP.exists():
    print('patch_s198 already applied — delete .patch_s198_fix_s196_s197_imports_done to re-run')
    sys.exit(0)

def patch(path, old, new, tag, required=False):
    p = REPO / path
    if not p.exists():
        print(f'  SKIP  {tag} (file missing)'); return
    src = p.read_text(encoding='utf-8')
    if new.strip() in src:
        print(f'  SKIP  {tag} (already applied)'); return
    if old not in src:
        if required:
            print(f'  FAIL  {tag}: anchor not found'); sys.exit(1)
        print(f'  WARN  {tag}: anchor not found — skipped'); return
    p.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

print(f'\n── S198  [repo: {REPO}] ──\n')

AI = 'lib/screens/ai_tools_screen.dart'
AE = 'lib/screens/audio_editor_screen.dart'

# ── BUG-1: wrong LangProvider import path ───────────────────────────────────
patch(AI,
    "import '../providers/lang_provider.dart'; // S196-BUG-I\n",
    "import '../state/lang_provider.dart'; // S196-BUG-I (S198-BUG-1: fixed path)\n",
    'BUG-1/AI: fix LangProvider import path (providers -> state)',
    required=True)

# ── BUG-2: missing dart:async import for StreamSubscription ────────────────
patch(AE,
    "import 'dart:math' show pi, sin, cos, pow, Random;  // S197-BUG-A: pow for pitch\n",
    "import 'dart:async';  // S198-BUG-2: needed for StreamSubscription (S197-BUG-B)\n"
    "import 'dart:math' show pi, sin, cos, pow, Random;  // S197-BUG-A: pow for pitch\n",
    'BUG-2/AE: add dart:async import for StreamSubscription',
    required=True)

# ──────────────────────────────────────────────────────────────────────────
STAMP.write_text('S198\n')
print('\n✅  patch_s198 done')
print()
print('  git add lib/screens/ai_tools_screen.dart lib/screens/audio_editor_screen.dart')
print('  git commit -m "S198: fix wrong LangProvider import path + missing dart:async import"')
print('  git push')
