#!/usr/bin/env python3
"""
tilawa_dump_local.py  —  Dump Flutter dart files from local repo
Run from ~/tilawa-enhancer:
  python3 tilawa_dump_local.py
Output goes to /sdcard/Download/tilawa_dart_dump.txt
Paste that file back to Claude.
"""
from pathlib import Path
import datetime

REPO = Path.home() / 'tilawa-enhancer'
OUT  = Path('/sdcard/Download/tilawa_dart_dump.txt')

TARGET_FILES = [
    'lib/main.dart',
    'lib/screens/home_screen.dart',
    'lib/screens/history_screen.dart',
    'lib/screens/settings_screen.dart',
    'lib/screens/welcome_screen.dart',
    'lib/state/lang_provider.dart',
    'lib/services/api_service.dart',
]

lines = []
lines.append('=' * 72)
lines.append(f'  TILAWA DART DUMP  —  {datetime.datetime.now():%Y-%m-%d %H:%M:%S}')
lines.append('=' * 72)

for rel in TARGET_FILES:
    p = REPO / rel
    lines.append('')
    lines.append('=' * 72)
    lines.append(f'  FILE: {rel}')
    if not p.exists():
        lines.append('  *** NOT FOUND ***')
        lines.append('=' * 72)
        continue
    content = p.read_text(encoding='utf-8', errors='replace')
    size = p.stat().st_size
    nlines = content.count('\n')
    lines.append(f'  SIZE: {size:,} bytes  |  {nlines} lines')
    lines.append('=' * 72)
    for i, l in enumerate(content.splitlines(), 1):
        lines.append(f'{i:5d}  {l}')

lines.append('')
lines.append('=' * 72)
lines.append('  END OF DUMP')
lines.append('=' * 72)

text = '\n'.join(lines)
OUT.write_text(text, encoding='utf-8')
print(f'Written to {OUT}')
print(f'Total lines: {len(lines):,}')
print(f'File size:   {OUT.stat().st_size:,} bytes')
print()
print('Now run:')
print('  Paste /sdcard/Download/tilawa_dart_dump.txt back to Claude')
