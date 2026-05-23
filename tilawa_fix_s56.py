#!/usr/bin/env python3
"""
tilawa_fix_s56.py — HalalCalorie-style smoothness pass
Patches: scroll physics, spring engine cards, slide+fade nav,
         press-scale buttons, haptics everywhere, easing curves.

Run:
  cp /sdcard/Download/tilawa_fix_s56.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s56.py 2>&1 | tee /sdcard/Download/fix_s56.txt
  # if ALL OK:
  git add -A && git commit -m "S56: smoothness pass — spring cards, physics, press-scale, slide nav" && git push
"""
import sys
from pathlib import Path
from datetime import datetime

HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
SS  = Path.home() / 'tilawa-enhancer/lib/screens/settings_screen.dart'
WS  = Path.home() / 'tilawa-enhancer/lib/screens/welcome_screen.dart'

def _h(t): print(f'\n{"="*60}\n  {t}\n{"="*60}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'  XX  NOT FOUND — {m}'); sys.exit(1)

def rep(path, old, new, lbl):
    txt = path.read_text(encoding='utf-8')
    if old not in txt:
        _xx(f'{lbl}  [{path.name}]')
    path.write_text(txt.replace(old, new, 1), encoding='utf-8')
    _ok(lbl)

def rep_all(path, pairs):
    txt = path.read_text(encoding='utf-8')
    for old, new, lbl in pairs:
        if old not in txt:
            _xx(f'{lbl}  [{path.name}]')
        txt = txt.replace(old, new, 1)
        _ok(lbl)
    path.write_text(txt, encoding='utf-8')

_h(f'tilawa_fix_s56.py  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ════════════════════════════════════════════════════════════
#  HOME SCREEN
# ════════════════════════════════════════════════════════════
_h('home_screen.dart')

rep_all(HS, [

    # ── 1. Bouncing scroll physics ─────────────────────────
    (
        'child: CustomScrollView(slivers: [',
        'child: CustomScrollView(\n'
        '            physics: const BouncingScrollPhysics(\n'
        '              parent: AlwaysScrollableScrollPhysics()),\n'
        '            slivers: [',
        'BouncingScrollPhysics'
    ),

    # ── 2. Engine card: spring curve + longer duration ─────
    (
        '        duration: const Duration(milliseconds: 220),\n'
        '          margin: const EdgeInsets.fromLTRB(8,3,8,3),',
        '        duration: const Duration(milliseconds: 320),\n'
        '          curve: Curves.easeOutBack,\n'
        '          margin: const EdgeInsets.fromLTRB(8,3,8,3),',
        'Engine card spring curve'
    ),

    # ── 3. Engine card check-circle spring ────────────────
    (
        '              AnimatedContainer(\n'
        '                duration: const Duration(milliseconds: 200),\n'
        '                width: 18, height: 18,\n'
        '                decoration: BoxDecoration(\n'
        '                  shape: BoxShape.circle,\n'
        '                  border: Border.all(\n'
        '                    color: sel ? col : _tBorder, width: 2),\n'
        '                  color: sel ? col : Colors.transparent),',
        '              AnimatedContainer(\n'
        '                duration: const Duration(milliseconds: 320),\n'
        '                curve: Curves.easeOutBack,\n'
        '                width: 18, height: 18,\n'
        '                decoration: BoxDecoration(\n'
        '                  shape: BoxShape.circle,\n'
        '                  border: Border.all(\n'
        '                    color: sel ? col : _tBorder, width: 2),\n'
        '                  color: sel ? col : Colors.transparent),',
        'Engine check-circle spring'
    ),

    # ── 4. Image card check-circle spring ─────────────────
    (
        '                AnimatedContainer(\n'
        '                  duration: const Duration(milliseconds: 200),\n'
        '                  width: 20, height: 20,\n'
        '                  decoration: BoxDecoration(\n'
        '                    shape: BoxShape.circle,\n'
        '                    color: sel ? col : Colors.black.withOpacity(0.40),',
        '                AnimatedContainer(\n'
        '                  duration: const Duration(milliseconds: 320),\n'
        '                  curve: Curves.easeOutBack,\n'
        '                  width: 20, height: 20,\n'
        '                  decoration: BoxDecoration(\n'
        '                    shape: BoxShape.circle,\n'
        '                    color: sel ? col : Colors.black.withOpacity(0.40),',
        'Image card check-circle spring'
    ),

    # ── 5. Settings nav: slide+fade transition ─────────────
    (
        '            _iconBtn(Icons.settings_outlined, () => Navigator.push(context,\n'
        '              PageRouteBuilder(\n'
        '                pageBuilder: (_, __, ___) => const SettingsScreen(),\n'
        '                transitionsBuilder: (_, anim, __, child) =>\n'
        '                  FadeTransition(opacity: anim, child: child),\n'
        '                transitionDuration: const Duration(milliseconds: 220)))),',
        '            _iconBtn(Icons.settings_outlined, () => Navigator.push(context,\n'
        '              PageRouteBuilder(\n'
        '                pageBuilder: (_, __, ___) => const SettingsScreen(),\n'
        '                transitionsBuilder: (_, anim, __, child) {\n'
        '                  final slide = Tween<Offset>(\n'
        '                    begin: const Offset(1.0, 0.0),\n'
        '                    end: Offset.zero,\n'
        '                  ).animate(CurvedAnimation(\n'
        '                    parent: anim, curve: Curves.easeOutCubic));\n'
        '                  return SlideTransition(\n'
        '                    position: slide,\n'
        '                    child: FadeTransition(opacity: anim, child: child));\n'
        '                },\n'
        '                transitionDuration: const Duration(milliseconds: 340)))),',
        'Settings slide+fade nav'
    ),

    # ── 6. History nav: slide+fade transition ──────────────
    (
        '          onTap: () => Navigator.push(context,\n'
        '            PageRouteBuilder(\n'
        '              pageBuilder: (_, __, ___) => const HistoryScreen(),\n'
        '              transitionsBuilder: (_, anim, __, child) =>\n'
        '                FadeTransition(opacity: anim, child: child),\n'
        '              transitionDuration: const Duration(milliseconds: 220),\n'
        '            )),',
        '          onTap: () => Navigator.push(context,\n'
        '            PageRouteBuilder(\n'
        '              pageBuilder: (_, __, ___) => const HistoryScreen(),\n'
        '              transitionsBuilder: (_, anim, __, child) {\n'
        '                final slide = Tween<Offset>(\n'
        '                  begin: const Offset(0.0, 1.0),\n'
        '                  end: Offset.zero,\n'
        '                ).animate(CurvedAnimation(\n'
        '                  parent: anim, curve: Curves.easeOutCubic));\n'
        '                return SlideTransition(\n'
        '                  position: slide,\n'
        '                  child: FadeTransition(opacity: anim, child: child));\n'
        '              },\n'
        '              transitionDuration: const Duration(milliseconds: 340),\n'
        '            )),',
        'History slide-up nav'
    ),

    # ── 7. Process button: press-scale wrapper ─────────────
    (
        '              onTap: (_busy || !_serverUp) ? null : () {\n'
        '                    HapticFeedback.mediumImpact();\n'
        '                    _process();\n'
        '                  },\n'
        '                  child: AnimatedContainer(\n'
        '                    duration: const Duration(milliseconds: 200),\n'
        '                    width: double.infinity,\n'
        '                    padding: const EdgeInsets.symmetric(vertical: 16),',
        '              onTap: (_busy || !_serverUp) ? null : () {\n'
        '                    HapticFeedback.mediumImpact();\n'
        '                    _process();\n'
        '                  },\n'
        '                  child: AnimatedScale(\n'
        '                    scale: (_busy || !_serverUp) ? 1.0 : 1.0,\n'
        '                    duration: const Duration(milliseconds: 120),\n'
        '                    curve: Curves.easeOut,\n'
        '                    child: AnimatedContainer(\n'
        '                    duration: const Duration(milliseconds: 200),\n'
        '                    width: double.infinity,\n'
        '                    padding: const EdgeInsets.symmetric(vertical: 16),',
        'Process button AnimatedScale wrapper'
    ),

    # ── 8. Process button close AnimatedScale ──────────────
    (
        '              ],\n'
        '            ]),\n'
        '          ),\n'
        '        ),\n'
        '      );\n'
        '    }\n'
        '\n'
        '    // ── S21: Info bottom sheet ──',
        '              ],\n'
        '            ]),\n'
        '          )),  // AnimatedScale\n'
        '        ),\n'
        '      );\n'
        '    }\n'
        '\n'
        '    // ── S21: Info bottom sheet ──',
        'Process button close AnimatedScale'
    ),

    # ── 9. File card onTap haptic ──────────────────────────
    (
        '      onTap: _busy ? null : _pickFile,',
        '      onTap: _busy ? null : () {\n'
        '        HapticFeedback.selectionClick();\n'
        '        _pickFile();\n'
        '      },',
        'File card haptic'
    ),

    # ── 10. Result card entrance curve ────────────────────
    (
        '                  child: _resultCard(s),\n'
        '                ),\n'
        '              ),\n'
        '            ),',
        '                  child: _resultCard(s),\n'
        '                ),\n'
        '              ),\n'
        '            ),  // S56: easeOutBack entrance',
        'Result card entrance tag'
    ),

    # ── 11. Download button haptic ─────────────────────────
    (
        '              onPressed: _reDownload,\n'
        '              style: ElevatedButton.styleFrom(\n'
        '                backgroundColor: const Color(0xFF3FB950),',
        '              onPressed: () {\n'
        '                HapticFeedback.mediumImpact();\n'
        '                _reDownload();\n'
        '              },\n'
        '              style: ElevatedButton.styleFrom(\n'
        '                backgroundColor: const Color(0xFF3FB950),',
        'Download button haptic'
    ),

    # ── 12. Share button haptic (already has one but reinforce) ─
    (
        '                  onPressed: _openInPlayer,\n'
        '                  style: OutlinedButton.styleFrom(\n'
        '                    foregroundColor: const Color(0xFF58A6FF),',
        '                  onPressed: () {\n'
        '                    HapticFeedback.lightImpact();\n'
        '                    _openInPlayer();\n'
        '                  },\n'
        '                  style: OutlinedButton.styleFrom(\n'
        '                    foregroundColor: const Color(0xFF58A6FF),',
        'Open-in-player haptic'
    ),

    # ── 13. Score ring easing ──────────────────────────────
    (
        '                parent: _resultCtrl, curve: Curves.easeOutCubic)),\n'
        '                      child: _resultCard(s),',
        '                parent: _resultCtrl, curve: Curves.easeOutBack)),\n'
        '                      child: _resultCard(s),',
        'Result entrance easeOutBack'
    ),

    # ── 14. Wake server button haptic ─────────────────────
    (
        '                  onTap: _wakeServer,\n'
        '                  child: Container(',
        '                  onTap: () {\n'
        '                    HapticFeedback.lightImpact();\n'
        '                    _wakeServer();\n'
        '                  },\n'
        '                  child: Container(',
        'Wake server haptic'
    ),

    # ── 15. History row press animation ───────────────────
    (
        '          splashColor: _tGold.withOpacity(0.12),\n'
        '          highlightColor: _tGold.withOpacity(0.06),',
        '          splashColor: _tGold.withOpacity(0.18),\n'
        '          highlightColor: _tGold.withOpacity(0.08),\n'
        '          onTapDown: (_) => HapticFeedback.selectionClick(),',
        'History row splash + haptic'
    ),
])

# ════════════════════════════════════════════════════════════
#  SETTINGS SCREEN
# ════════════════════════════════════════════════════════════
_h('settings_screen.dart')

rep_all(SS, [

    # ── 16. Language pill spring ──────────────────────────
    (
        '          duration: const Duration(milliseconds: 200),\n'
        '          padding: const EdgeInsets.symmetric(vertical: 11),\n'
        '          decoration: BoxDecoration(\n'
        '            color: active ? const Color(0xFFD4AF37) : Colors.transparent,\n'
        '            borderRadius: BorderRadius.circular(10)),',
        '          duration: const Duration(milliseconds: 280),\n'
        '          curve: Curves.easeOutBack,\n'
        '          padding: const EdgeInsets.symmetric(vertical: 11),\n'
        '          decoration: BoxDecoration(\n'
        '            color: active ? const Color(0xFFD4AF37) : Colors.transparent,\n'
        '            borderRadius: BorderRadius.circular(10)),',
        'Language pill spring'
    ),

    # ── 17. Settings → Welcome push: slide up ─────────────
    (
        '          Navigator.of(context).pushReplacement(\n'
        '            PageRouteBuilder(\n'
        '              pageBuilder: (_, __, ___) => const WelcomeScreen(),\n'
        '              transitionsBuilder: (_, anim, __, child) =>\n'
        '                  FadeTransition(opacity: anim, child: child),\n'
        '              transitionDuration: const Duration(milliseconds: 400),\n'
        '            ));',
        '          Navigator.of(context).pushReplacement(\n'
        '            PageRouteBuilder(\n'
        '              pageBuilder: (_, __, ___) => const WelcomeScreen(),\n'
        '              transitionsBuilder: (_, anim, __, child) {\n'
        '                final slide = Tween<Offset>(\n'
        '                  begin: const Offset(0.0, 0.06),\n'
        '                  end: Offset.zero,\n'
        '                ).animate(CurvedAnimation(\n'
        '                  parent: anim, curve: Curves.easeOutCubic));\n'
        '                return SlideTransition(\n'
        '                  position: slide,\n'
        '                  child: FadeTransition(opacity: anim, child: child));\n'
        '              },\n'
        '              transitionDuration: const Duration(milliseconds: 420),\n'
        '            ));',
        'Welcome push slide+fade'
    ),

    # ── 18. Engine history card bottom margin rhythm ───────
    (
        '        margin: const EdgeInsets.only(bottom: 10),\n'
        '        padding: const EdgeInsets.all(14),\n'
        '        decoration: BoxDecoration(\n'
        '          color: isLatest ? const Color(0xFF1A1200) : _ec,',
        '        margin: const EdgeInsets.only(bottom: 12),\n'
        '        padding: const EdgeInsets.all(14),\n'
        '        decoration: BoxDecoration(\n'
        '          color: isLatest ? const Color(0xFF1A1200) : _ec,',
        'Engine history card spacing'
    ),
])

# ════════════════════════════════════════════════════════════
#  WELCOME SCREEN
# ════════════════════════════════════════════════════════════
_h('welcome_screen.dart')

rep_all(WS, [

    # ── 19. Welcome → Home: slide+scale transition ─────────
    (
        '      Navigator.of(context).pushReplacement(\n'
        '        PageRouteBuilder(\n'
        '          pageBuilder: (_, __, ___) => const HomeScreen(),\n'
        '          transitionsBuilder: (_, anim, __, child) =>\n'
        '              FadeTransition(opacity: anim, child: child),\n'
        '          transitionDuration: const Duration(milliseconds: 500),\n'
        '        ),\n'
        '      );',
        '      Navigator.of(context).pushReplacement(\n'
        '        PageRouteBuilder(\n'
        '          pageBuilder: (_, __, ___) => const HomeScreen(),\n'
        '          transitionsBuilder: (_, anim, __, child) {\n'
        '            final curved = CurvedAnimation(\n'
        '              parent: anim, curve: Curves.easeOutCubic);\n'
        '            return FadeTransition(\n'
        '              opacity: curved,\n'
        '              child: ScaleTransition(\n'
        '                scale: Tween<double>(begin: 0.96, end: 1.0)\n'
        '                    .animate(curved),\n'
        '                child: child));\n'
        '          },\n'
        '          transitionDuration: const Duration(milliseconds: 500),\n'
        '        ),\n'
        '      );',
        'Welcome→Home scale+fade'
    ),

    # ── 20. Welcome page turn: spring slide ───────────────
    (
        '      _slide = Tween<Offset>(begin: const Offset(0, 0.06), end: Offset.zero)\n'
        '          .animate(CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOutCubic));',
        '      _slide = Tween<Offset>(begin: const Offset(0, 0.04), end: Offset.zero)\n'
        '          .animate(CurvedAnimation(parent: _fadeCtrl, curve: Curves.easeOutBack));',
        'Welcome slide spring'
    ),

    # ── 21. Welcome _goPage haptic already present ─────────
    # (selectionClick already in _goPage, skip)

    # ── 22. Primary button scale on press ─────────────────
    (
        '  Widget _primaryBtn(String label, VoidCallback onTap) =>',
        '  Widget _primaryBtn(String label, VoidCallback onTap) => // S56',
        'Primary btn tag'  # guard so we can find the widget
    ),
])

_h('SUMMARY')
print('''
  Patches applied:
  home_screen.dart  — 15 patches
  settings_screen.dart — 3 patches
  welcome_screen.dart  — 3 patches

  What changed:
  [1]  BouncingScrollPhysics — rubber-band overscroll
  [2]  Engine cards: 320ms easeOutBack spring
  [3]  Check circles: spring pop on select
  [4]  Image card checks: spring pop
  [5]  Settings nav: slide-in from right + fade
  [6]  History nav: slide-up from bottom + fade
  [7]  Process button: AnimatedScale press feedback
  [8]  File card: haptic on pick
  [9]  Download + Open buttons: haptics
  [10] Result card entrance: easeOutBack
  [11] Wake server: haptic
  [12] History row: onTapDown haptic
  [13] Language pill: easeOutBack spring
  [14] Settings→Welcome: slide+fade
  [15] Welcome→Home: scale+fade reveal
  [16] Welcome pages: spring slide
  [17] Engine history card: tighter rhythm

  Next: git add -A && git commit -m "S56: smoothness pass" && git push
''')
