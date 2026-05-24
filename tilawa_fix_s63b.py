#!/usr/bin/env python3
"""tilawa_fix_s63b — fix _wakeCh declaration anchor + patches 3-5"""
import sys
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

def _h(t): print(f'\n{"="*52}\n  {t}\n{"="*52}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'\n  XX  NOT FOUND — {m}\n'); sys.exit(1)
def rep(old, new, lbl):
    t = HS.read_text(encoding='utf-8')
    if old not in t: _xx(lbl)
    HS.write_text(t.replace(old, new, 1), encoding='utf-8'); _ok(lbl)

_h(f'S63b  {datetime.now().strftime("%H:%M:%S")}')

_h('2 — declare _wakeCh')
rep(
    '  // ── Engines (S21: full data from documentation) ─────────────────────────────',
    '  static const _wakeCh = MethodChannel(\'com.tilawa.tilawa_enhancer/wake\'); // S63\n'
    '  // ── Engines (S21: full data from documentation) ─────────────────────────────',
    '_wakeCh declared'
)

_h('3 — acquire on poll start')
rep(
    '    _pollErrors = 0; // S22: fresh counter for each new polling session\n'
    '    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {',
    '    _pollErrors = 0; // S22: fresh counter for each new polling session\n'
    '    _wakeCh.invokeMethod(\'acquire\').catchError((_) {}); // S63\n'
    '    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {',
    'acquire on poll start'
)

_h('4 — release on error')
rep(
    "        if (status == 'error') {\n"
    "          _pollTimer?.cancel();\n"
    "          setState(() {\n"
    "            _busy = false;\n"
    "            _isMerging = false;  // S20-B: clear merge animation on server error",
    "        if (status == 'error') {\n"
    "          _pollTimer?.cancel();\n"
    "          _wakeCh.invokeMethod('release').catchError((_) {}); // S63\n"
    "          setState(() {\n"
    "            _busy = false;\n"
    "            _isMerging = false;  // S20-B: clear merge animation on server error",
    'release on error'
)

_h('5 — release on done')
rep(
    "        if (status == 'done') {\n"
    "          _pollTimer?.cancel();\n"
    "          if (_downloading) return; // RC3",
    "        if (status == 'done') {\n"
    "          _pollTimer?.cancel();\n"
    "          _wakeCh.invokeMethod('release').catchError((_) {}); // S63\n"
    "          if (_downloading) return; // RC3",
    'release on done'
)

_h('DONE')
print('\n  git add -A && git commit -m "S63: wake lock patches 2-5" && git push\n')
