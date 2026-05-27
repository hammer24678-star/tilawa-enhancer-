#!/usr/bin/env python3
"""
patch_s92_scroll.py
===================
S92: auto-scroll to result card when processing completes.
No scroll controller existed — result card appeared above viewport, invisible.
"""
from pathlib import Path
from datetime import datetime

hs = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
print(f'\n{"="*56}\n  patch_s92_scroll  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*56}')

if not hs.exists():
    print('  XX  home_screen.dart not found'); exit(1)

txt = hs.read_text(encoding='utf-8')

if '// S92-SCROLL' in txt:
    print('  OK  S92-SCROLL already applied'); exit(0)

# ── Fix 1: add ScrollController declaration ───────────────────────────────────
OLD1 = "  late final AnimationController _resultCtrl; // S29: result card entrance"
NEW1 = "  late final AnimationController _resultCtrl; // S29: result card entrance\n  final ScrollController _scrollCtrl = ScrollController(); // S92-SCROLL"

if OLD1 in txt:
    txt = txt.replace(OLD1, NEW1, 1)
    print('  OK  ScrollController declared')
else:
    print('  XX  _resultCtrl declaration not found'); exit(1)

# ── Fix 2: dispose ScrollController ──────────────────────────────────────────
OLD2 = "    _resultCtrl.dispose();"
NEW2 = "    _resultCtrl.dispose();\n    _scrollCtrl.dispose(); // S92-SCROLL"

if OLD2 in txt:
    txt = txt.replace(OLD2, NEW2, 1)
    print('  OK  ScrollController disposed')
else:
    print('  XX  dispose anchor not found')

# ── Fix 3: attach to CustomScrollView ────────────────────────────────────────
OLD3 = "          CustomScrollView(slivers: [ // S62b"
NEW3 = "          CustomScrollView(controller: _scrollCtrl, slivers: [ // S62b S92-SCROLL"

if OLD3 in txt:
    txt = txt.replace(OLD3, NEW3, 1)
    print('  OK  ScrollController attached to CustomScrollView')
else:
    print('  XX  CustomScrollView anchor not found')

# ── Fix 4: scroll to top after result in server mode ─────────────────────────
OLD4 = "    if (file != null) _resultCtrl.forward(from: 0); // S29: animate in"
NEW4 = """\
    if (file != null) _resultCtrl.forward(from: 0); // S29: animate in
    if (file != null) { // S92-SCROLL: scroll to result card
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scrollCtrl.hasClients) {
          _scrollCtrl.animateTo(0,
            duration: const Duration(milliseconds: 600),
            curve: Curves.easeOutCubic);
        }
      });
    }"""

if OLD4 in txt:
    txt = txt.replace(OLD4, NEW4, 1)
    print('  OK  Scroll-to-top added for server mode')
else:
    print('  XX  server mode resultCtrl.forward anchor not found')

# ── Fix 5: scroll to top after result in local mode ──────────────────────────
OLD5 = "        _scoreCtrl.forward(from: 0);\n        _resultCtrl.forward(from: 0);\n        return;"
NEW5 = """\
        _scoreCtrl.forward(from: 0);
        _resultCtrl.forward(from: 0);
        WidgetsBinding.instance.addPostFrameCallback((_) { // S92-SCROLL
          if (_scrollCtrl.hasClients) {
            _scrollCtrl.animateTo(0,
              duration: const Duration(milliseconds: 600),
              curve: Curves.easeOutCubic);
          }
        });
        return;"""

if OLD5 in txt:
    txt = txt.replace(OLD5, NEW5, 1)
    print('  OK  Scroll-to-top added for local mode')
else:
    print('  XX  local mode resultCtrl.forward anchor not found')

hs.write_text(txt, encoding='utf-8')
print('  OK  home_screen.dart saved')
print(f'\n{"="*56}\n  Done\n{"="*56}')
print('\n  git add -A && git commit -m "S92: auto-scroll to result card on completion" && git push origin revert-to-s87:master --force\n')
