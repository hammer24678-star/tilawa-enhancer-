#!/usr/bin/env python3
"""tilawa_fix_s42b — 4 exact fixes from diag_s42"""
from pathlib import Path
from datetime import datetime

f = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = f.read_text(encoding='utf-8')
_log = []

def rep(old, new, lbl):
    global txt
    if old in txt:
        txt = txt.replace(old, new, 1)
        print(f'  OK  {lbl}'); _log.append(('OK', lbl))
    else:
        print(f'  XX  {lbl}'); _log.append(('XX', lbl))

# 1 — BG gradient (exact line 619-621)
rep(
    "            colors: dark\n"
    "              ? [const Color(0xFF020D17), const Color(0xFF000810)]\n"
    "              : [const Color(0xFFFAF7EE), const Color(0xFFF5F0E0)]),",
    "            colors: dark\n"
    "              ? [const Color(0xFF020D0C), const Color(0xFF051A14)]\n"
    "              : [const Color(0xFFFAF7EE), const Color(0xFFF5F0E0)]),",
    'BG gradient → void teal')

# 2 — Progress teal shadow (exact lines 1501-1502)
rep(
    "          color: const Color(0xFF1C8EA8).withOpacity(0.06),\n"
    "          blurRadius: 60, spreadRadius: 2),",
    "          color: const Color(0xFF1DB898).withOpacity(0.08),\n"
    "          blurRadius: 60, spreadRadius: 2),",
    'Progress teal shadow → #1DB898')

# 3 — Engine card border width (exact line 1002-1003)
rep(
    "              : const Color(0xFF1DB898).withOpacity(0.22),\n"
    "            width: sel ? 1.6 : 0.7),",
    "              : const Color(0xFF1DB898).withOpacity(0.22),\n"
    "            width: sel ? 1.8 : 0.8),",
    'Engine card border width 1.6→1.8')

# 4 — Incense painter in Stack (exact line 625-627)
rep(
    "            child: IgnorePointer(\n"
    "              child: CustomPaint(painter: _GeoPainter())))),"
    "\n          if (dark) Positioned.fill(\n"
    "            child: IgnorePointer(\n"
    "              child: AnimatedBuilder(",
    "            child: IgnorePointer(\n"
    "              child: CustomPaint(painter: _GeoPainter()))),"
    "\n          if (dark) Positioned.fill(\n"
    "            child: IgnorePointer(\n"
    "              child: CustomPaint(painter: _IncensePainter(_geoRotCtrl.value)))),"
    "\n          if (dark) Positioned.fill(\n"
    "            child: IgnorePointer(\n"
    "              child: AnimatedBuilder(",
    'Incense painter in background Stack')

f.write_text(txt, encoding='utf-8')
print(f'\n  {"✅" if all(s=="OK" for s,_ in _log) else "⚠"} Done — '
      f'{sum(1 for s,_ in _log if s=="OK")} OK  '
      f'{sum(1 for s,_ in _log if s=="XX")} FAIL')
print('\n  git add -A && git commit -m "S42: void teal bg + incense + border fixes" && git push')
