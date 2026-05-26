#!/usr/bin/env python3
"""
patch_s84_badge.py
==================
S84-BADGE: inject LOCAL/SERVER mode badge on engine list cards.
The main S84 patch failed because it searched for .withOpacity() but
the file uses .withValues(alpha: ...).  This patch uses the exact anchor.
"""
from pathlib import Path
from datetime import datetime

hs = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

print(f'\n{"="*56}\n  patch_s84_badge  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*56}')

if not hs.exists():
    print('  XX  home_screen.dart not found'); exit(1)

txt = hs.read_text(encoding='utf-8')

if '// S84-BADGE' in txt:
    print('  OK  S84-BADGE already applied'); exit(0)

OLD = (
    "                  if (e.badge.isNotEmpty) ...[\n"
    "                    const SizedBox(width: 8),\n"
    "                    Container(\n"
    "                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),\n"
    "                      decoration: BoxDecoration(\n"
    "                        color: col.withValues(alpha: 0.12),\n"
    "                        borderRadius: BorderRadius.circular(5),\n"
    "                        border: Border.all(color: col.withValues(alpha: 0.45))),\n"
    "                      child: Text(e.badge, style: TextStyle(\n"
    "                        color: col, fontSize: 8, fontWeight: FontWeight.bold,\n"
    "                        letterSpacing: 0.8))),\n"
    "                  ],\n"
)

NEW = (
    "                  const SizedBox(width: 8),\n"
    "                  // S84-BADGE: LOCAL / SERVER mode badge\n"
    "                  Container(\n"
    "                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),\n"
    "                    decoration: BoxDecoration(\n"
    "                      color: e.localOnly\n"
    "                        ? _teal.withValues(alpha: 0.18)\n"
    "                        : _tBorder.withValues(alpha: 0.5),\n"
    "                      borderRadius: BorderRadius.circular(5),\n"
    "                      border: Border.all(\n"
    "                        color: e.localOnly ? _teal : _tSub.withValues(alpha: 0.5))),\n"
    "                    child: Text(\n"
    "                      e.localOnly ? '🏠 LOCAL' : '☁ SERVER',\n"
    "                      style: TextStyle(\n"
    "                        color: e.localOnly ? _teal : _tSub,\n"
    "                        fontSize: 7, fontWeight: FontWeight.bold,\n"
    "                        letterSpacing: 0.6))),\n"
    "                  if (e.badge.isNotEmpty) ...[\n"
    "                    const SizedBox(width: 6),\n"
    "                    Container(\n"
    "                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),\n"
    "                      decoration: BoxDecoration(\n"
    "                        color: col.withValues(alpha: 0.12),\n"
    "                        borderRadius: BorderRadius.circular(5),\n"
    "                        border: Border.all(color: col.withValues(alpha: 0.45))),\n"
    "                      child: Text(e.badge, style: TextStyle(\n"
    "                        color: col, fontSize: 8, fontWeight: FontWeight.bold,\n"
    "                        letterSpacing: 0.8))),\n"
    "                  ],\n"
)

if OLD in txt:
    txt = txt.replace(OLD, NEW, 1)
    hs.write_text(txt, encoding='utf-8')
    print('  OK  LOCAL/SERVER badge injected into engine list card')
    print('  OK  home_screen.dart saved')
    print(f'\n{"="*56}\n  1 OK   0 FAIL\n{"="*56}')
    print('\n  git add -A && git commit -m "S84-BADGE: inject LOCAL/SERVER badge on engine cards" && git push\n')
else:
    # Show a snippet around badge.isNotEmpty for diagnosis
    idx = txt.find('if (e.badge.isNotEmpty) ...[')
    if idx != -1:
        snippet = txt[max(0,idx-200):idx+400]
        print('  XX  Anchor not matched. Actual text around badge block:')
        print('--- SNIPPET START ---')
        print(snippet)
        print('--- SNIPPET END ---')
    else:
        print('  XX  badge.isNotEmpty not found at all')
    print('\n  Fix incomplete — paste output back to Claude.\n')
    exit(1)
