#!/usr/bin/env python3
"""
patch_s146.py — remove S142 server-only engine guard from _processLocal()
The guard was blocking local mode from being used at all.
"""
from pathlib import Path
from datetime import datetime
import sys

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

_log = []
def ok(l):  print(f'  OK  {l}'); _log.append(('OK', l))
def xx(l):  print(f'  XX  NOT FOUND — {l}'); _log.append(('XX', l)); sys.exit(1)

def rep(path, old, new, lbl):
    t = path.read_text(encoding='utf-8')
    if old in t:
        path.write_text(t.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else:
        xx(lbl)

print(f'\n{"="*60}\n  S146  {datetime.now().strftime("%H:%M:%S")}\n{"="*60}')

rep(HS,
    '    if (!_selectedEngine.localOnly) { // S142: reject server-only engines in local mode\n'
    '      final s = LangProvider.strings(context);\n'
    '      ScaffoldMessenger.of(context).showSnackBar(SnackBar(\n'
    '        content: Text(s.ar\n'
    '          ? \'هذا المحرك يعمل على الخادم فقط. اختر محركاً محلياً (v11.x)\'\n'
    '          : \'This engine is server-only. Select a v11.x local engine.\'),\n'
    '        backgroundColor: const Color(0xFF200D0D)));\n'
    '      return;\n'
    '    }\n'
    '    HapticFeedback.mediumImpact();',

    '    HapticFeedback.mediumImpact(); // S146: removed server-only guard — allow all engines in local mode',
    'S142 server-only guard removed from _processLocal()')

ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
print(f'\n  {"✅ All OK" if xx_n == 0 else "⚠  FAILED"}  {ok_n} OK\n')
print('  git add -A && git commit -m "S146: remove server-only guard — allow all engines in local mode" && git push')
