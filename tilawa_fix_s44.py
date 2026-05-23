#!/usr/bin/env python3
"""
tilawa_fix_s44 — Fix the 2 failed S43 patches
===============================================
S43 had 2 NOT FOUND failures because the search strings used wrong indentation.

  Fix A: Stars min size  0.8 → 1.4
          S43 searched 10-space indent; file has 8-space indent.

  Fix B: Welcome screen — remove duplicate static 130-px logo
          S43 searched 10-space indent for top-level anchor;
          file has 12-space indent (all inner lines proportionally +2).

Anchor evidence (from grep run after S43):
  home_screen.dart:2129:        size = 0.8 + r.nextDouble() * 2.6,
  welcome_screen.dart:120:            // S33-WELCOME-LOGO
  welcome_screen.dart:124:                width: 130, height: 130,
  welcome_screen.dart:136:                  fit: BoxFit.cover, width: 130, height: 130)))),
"""
from pathlib import Path

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
WS = Path.home() / 'tilawa-enhancer/lib/screens/welcome_screen.dart'
_log = []

def rep(txt, old, new, lbl):
    if old in txt:
        print(f'  OK  {lbl}')
        _log.append(('OK', lbl))
        return txt.replace(old, new, 1)
    print(f'  XX  NOT FOUND — {lbl}')
    _log.append(('XX', lbl))
    return txt

# ═══════════════════════════════════════════════════════════════════════════════
# home_screen.dart — Fix A: Stars min size (8-space indent, not 10)
# ═══════════════════════════════════════════════════════════════════════════════
htxt = HS.read_text(encoding='utf-8')

htxt = rep(htxt,
    "        size = 0.8 + r.nextDouble() * 2.6,",
    "        size = 1.4 + r.nextDouble() * 2.8,",
    'Stars min size 0.8 → 1.4 (corrected indent)')

HS.write_text(htxt, encoding='utf-8')
print('  → home_screen.dart saved')

# ═══════════════════════════════════════════════════════════════════════════════
# welcome_screen.dart — Fix B: remove duplicate static 130-px logo
# All lines are +2 spaces vs what S43 searched (12-space top-level anchor).
# ═══════════════════════════════════════════════════════════════════════════════
wtxt = WS.read_text(encoding='utf-8')

wtxt = rep(wtxt,
    "            // S33-WELCOME-LOGO\n"
    "            Center(\n"
    "              child: Container(\n"
    "                margin: const EdgeInsets.only(bottom: 20, top: 8),\n"
    "                width: 130, height: 130,\n"
    "                decoration: const BoxDecoration(\n"
    "                  shape: BoxShape.circle,\n"
    "                  boxShadow: [\n"
    "                    BoxShadow(\n"
    "                      color: Color(0x59D4AF37),\n"
    "                      blurRadius: 40, spreadRadius: 4),\n"
    "                    BoxShadow(\n"
    "                      color: Color(0x331C8EA8),\n"
    "                      blurRadius: 70, spreadRadius: 10),\n"
    "                  ]),\n"
    "                child: ClipOval(child: Image.asset('assets/images/logo.png',\n"
    "                  fit: BoxFit.cover, width: 130, height: 130)))),",
    "            // S44: static 130-px duplicate removed (animated 180-px logo stays)",
    'Welcome: remove duplicate static 130-px logo (corrected indent)')

WS.write_text(wtxt, encoding='utf-8')
print('  → welcome_screen.dart saved')

# ═══════════════════════════════════════════════════════════════════════════════
ok  = sum(1 for s, _ in _log if s == 'OK')
xx  = sum(1 for s, _ in _log if s == 'XX')
print(f'\n  {"✅ All OK" if xx == 0 else "⚠ " + str(xx) + " FAILED"}  {ok} OK')
if xx:
    print('  Run grep to re-check anchors — indentation may still differ.')
print('\n  git add -A && git commit -m "S44: fix stars size + welcome logo (corrected indent)" && git push')
