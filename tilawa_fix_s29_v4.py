#!/usr/bin/env python3
"""
tilawa_fix_s29_v4.py  —  S29 Sacred Cosmos  (v4 — exact anchors)
=================================================================
Fixes all steps that failed in tilawa_fix_s29_v3.py.

Root causes of v3 failures (from tilawa_diag_v3b output):
  MA1  — colorScheme anchor had 4sp/6sp; _buildDarkTheme() uses 2sp/4sp
  MA2  — appBarTheme anchor had 6sp; actual code has 4sp
  D9   — regex used 10sp for `decoration:`; actual code has 8sp
  D22  — onPressed: anchor had 16sp; actual code has 14sp
  HA1  — title: anchor had 10sp/12sp; actual code has 8sp/10sp
  SA1  — same indent error as HA1

Run from ~/tilawa-enhancer (after v1 + v2 + v2b + v3):
  cd ~/tilawa-enhancer && python3 tilawa_fix_s29_v4.py

Session: S29-v4  (2026-05-21)
Requires: S27, S28, S28-T2/T3, S29, S30, S31, v2, v2b, v3 already applied.
All steps are idempotent (_already guards).
"""

import re, sys
from pathlib import Path
from datetime import datetime

# ── helpers ──────────────────────────────────────────────────────────────────
def _h1(t):
    bar = '=' * 64
    print(f'\n{bar}\n  {t}\n{bar}')

def _h2(t):   print(f'\n  -- {t}')
def _ok(m):   print(f'     OK  {m}')
def _err(m):  print(f'     XX  {m}')
def _skip(m): print(f'     --  {m}')

_log = []

def _rec(sid, label, result):
    _log.append((sid, label, result))

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f'Anchor NOT found -- {label}')
        return text, False
    if c > 1:
        print(f'     !!  {c}x — using first -- {label}')
    else:
        _ok(f'Replaced -- {label}')
    return text.replace(old, new, 1), True

def _already(text, marker, label):
    if marker in text:
        _skip(f'Already applied -- {label}')
        return True
    return False

def _read(p):     return Path(p).read_text(encoding='utf-8')
def _write(p, t): Path(p).write_text(t, encoding='utf-8')

def _require(cond, msg):
    if not cond:
        _err(f'FATAL: {msg}')
        _summary()
        sys.exit(1)

def _summary():
    _h1('SUMMARY')
    print(f"\n  {'Step':<8}  {'Label':<52}  Result")
    print(f"  {'----':<8}  {'------':<52}  ------")
    for sid, label, result in _log:
        print(f'  {sid:<8}  {label:<52}  {result}')

# ── config ────────────────────────────────────────────────────────────────────
REPO     = Path.home() / 'tilawa-enhancer'
LIB      = REPO / 'lib'
SCREENS  = LIB / 'screens'

_h1('tilawa_fix_s29_v4.py  --  Sacred Cosmos v4  --  '
    + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

_h2('Verify repo')
_require(REPO.exists(),                              'REPO not found')
_require((LIB     / 'main.dart').exists(),           'main.dart missing')
_require((SCREENS / 'home_screen.dart').exists(),    'home_screen.dart missing')
_require((SCREENS / 'history_screen.dart').exists(), 'history_screen.dart missing')
_require((SCREENS / 'settings_screen.dart').exists(),'settings_screen.dart missing')
_ok('Repo OK')


###############################################################################
# MA  main.dart — colorScheme + appBarTheme
# FIX: v3 used 4sp/6sp indentation; _buildDarkTheme() actually uses 2sp/4sp
###############################################################################
_h1('MA  main.dart')
txt = _read(LIB / 'main.dart')

# MA1 — colorScheme: add surface + onSurface + secondary  (2sp/4sp inside func)
MARKER_MA1 = 'secondary: Color(0xFF1B6B80),'
if not _already(txt, MARKER_MA1, 'colorScheme already Sacred Cosmos'):
    OLD_CS = (
        '  colorScheme: const ColorScheme.dark(\n'
        '    primary: Color(0xFFD4AF37),\n'
        '    surface: Color(0xFF161B22),\n'
        '    onSurface: Color(0xFFC9D1D9),\n'
        '    background: Color(0xFF0A0C10),\n'
        '  ),'
    )
    NEW_CS = (
        '  colorScheme: const ColorScheme.dark(\n'
        '    primary:   Color(0xFFD4AF37),\n'
        '    surface:   Color(0xFF0C1E28),\n'
        '    onSurface: Color(0xFFE2CFA0),\n'
        '    secondary: Color(0xFF1B6B80),\n'
        '  ),'
    )
    txt, ok = _replace_once(txt, OLD_CS, NEW_CS, 'colorScheme → Sacred Cosmos (2sp/4sp)')
    _rec('MA1', 'colorScheme updated', '[OK] PASS' if ok else '[XX] FAIL')
    if not ok:
        # Fallback: MaterialApp inline ThemeData (pre-S31 layout)
        OLD_CS2 = (
            '              colorScheme: const ColorScheme.dark(\n'
            '                primary: Color(0xFFD4AF37),\n'
            '                surface: Color(0xFF161B22),\n'
            '              ),'
        )
        NEW_CS2 = (
            '              colorScheme: const ColorScheme.dark(\n'
            '                primary:   Color(0xFFD4AF37),\n'
            '                surface:   Color(0xFF0C1E28),\n'
            '                onSurface: Color(0xFFE2CFA0),\n'
            '                secondary: Color(0xFF1B6B80),\n'
            '              ),'
        )
        txt, ok2 = _replace_once(txt, OLD_CS2, NEW_CS2,
                                  'colorScheme → Sacred Cosmos (fallback 14sp)')
        _rec('MA1-fallback', 'colorScheme fallback (pre-S31 layout)',
             '[OK] PASS' if ok2 else '[XX] FAIL')
else:
    _rec('MA1', 'colorScheme updated', '[--] SKIP')

# MA2 — appBarTheme backgroundColor: 0A0C10 → 061218  (4sp inside func)
MARKER_MA2 = '    backgroundColor: Color(0xFF061218),\n    foregroundColor: Color(0xFFD4AF37),'
if not _already(txt, MARKER_MA2, 'appBar bg already 061218'):
    OLD_APP = (
        '    backgroundColor: Color(0xFF0A0C10),\n'
        '    foregroundColor: Color(0xFFD4AF37),\n'
        '    elevation: 0,'
    )
    NEW_APP = (
        '    backgroundColor: Color(0xFF061218),\n'
        '    foregroundColor: Color(0xFFD4AF37),\n'
        '    elevation: 0,'
    )
    txt, ok = _replace_once(txt, OLD_APP, NEW_APP, 'appBar bg 0A0C10→061218 (4sp)')
    _rec('MA2', 'AppBar bg → 061218', '[OK] PASS' if ok else '[XX] FAIL')
    if not ok:
        # Fallback: inline MaterialApp layout (various const/non-const combos)
        for old_a, lbl in [
            ("                backgroundColor: const Color(0xFF0A0C10),\n"
             "                foregroundColor: const Color(0xFFD4AF37),\n"
             "                elevation: 0,",
             "14sp const"),
            ("              backgroundColor: const Color(0xFF0A0C10),\n"
             "              foregroundColor: const Color(0xFFD4AF37),\n"
             "              elevation: 0,",
             "12sp const"),
        ]:
            if old_a in txt:
                new_a = old_a.replace('0xFF0A0C10', '0xFF061218')
                txt, ok2 = _replace_once(txt, old_a, new_a,
                                          f'appBar bg fallback ({lbl})')
                _rec(f'MA2-{lbl}', f'AppBar bg fallback ({lbl})',
                     '[OK] PASS' if ok2 else '[XX] FAIL')
                break
else:
    _rec('MA2', 'AppBar bg → 061218', '[--] SKIP')

_write(LIB / 'main.dart', txt)


###############################################################################
# D9  home_screen.dart — inject Sacred Cosmos background painters Stack
# FIX: v3 regex used 10sp for `decoration:`; actual is 8sp
###############################################################################
_h1('D9  home_screen.dart — background painters')
txt = _read(SCREENS / 'home_screen.dart')

MARKER_D9 = '// S29: Sacred Cosmos painters Stack'
if not _already(txt, MARKER_D9, 'painters Stack already injected'):
    # Step 1: Replace `child: SafeArea(` (direct child of gradient Container) with Stack
    # Pattern: capture decoration block + `        child: SafeArea(`
    pat_open = (
        r'(        decoration: BoxDecoration\([\s\S]+?\]\)\),\n)'
        r'(        child: SafeArea\()'
    )
    m = re.search(pat_open, txt, re.DOTALL)
    if m:
        inject = (
            m.group(1) +
            '        // S29: Sacred Cosmos painters Stack\n'
            '        child: Stack(children: [\n'
            '          if (dark) Positioned.fill(\n'
            '            child: IgnorePointer(\n'
            '              child: CustomPaint(painter: _GeoPainter()))),\n'
            '          if (dark) Positioned.fill(\n'
            '            child: IgnorePointer(\n'
            '              child: AnimatedBuilder(\n'
            '                animation: _starCtrl,\n'
            '                builder: (_, __) => CustomPaint(\n'
            '                  painter: _StarsPainter(_starCtrl.value, _starList))))),\n'
            '          SafeArea('
        )
        txt = re.sub(pat_open, inject, txt, count=1, flags=re.DOTALL)
        _ok('Stack opener injected (SafeArea wrapped)')

        # Step 2: Close the Stack — insert `          ]),` between SafeArea-close and
        # Container-close.  Matches the unique build() ending from diag D29 lines 633-638.
        pat_close = (
            r'(            const SliverToBoxAdapter\(child: SizedBox\(height: \d+\)\),\n'
            r'          \]\),\n'
            r'        \),\n)'    # ← SafeArea closes here
            r'(      \),\n'      # ← Container closes here (we insert Stack close before this)
            r'    \);\n'
            r'  \})'
        )
        m2 = re.search(pat_close, txt, re.DOTALL)
        if m2:
            def _close_stack(mx):
                return mx.group(1) + '          ]),\n' + mx.group(2)
            txt = re.sub(pat_close, _close_stack, txt, count=1, flags=re.DOTALL)
            _ok('Stack closer injected')
            _rec('S29-D9', 'Background painters Stack', '[OK] PASS')
        else:
            _err('Stack close pattern not found — Stack is open without close!')
            _rec('S29-D9', 'Background painters Stack', '[XX] FAIL — open only, not closed')
    else:
        _err('body Container decoration + child: SafeArea( pattern not found')
        _rec('S29-D9', 'Background painters Stack', '[XX] FAIL')
else:
    _rec('S29-D9', 'Background painters Stack', '[--] SKIP')


# D22 — process button haptic feedback
# FIX: v3 used 16sp; actual onPressed: is at 14sp inside _fileCard()
_h2('D22 — process button haptic')
MARKER_D22 = 'HapticFeedback.mediumImpact();\n                  _process();'
MARKER_D22b = 'HapticFeedback.mediumImpact();\n                _process();'
if _already(txt, MARKER_D22, 'haptic (16sp style) already') or \
   _already(txt, MARKER_D22b, 'haptic (14sp style) already'):
    _rec('S29-D22', 'Process button haptic', '[--] SKIP')
else:
    OLD_BTN = '              onPressed: (_busy || !_serverUp) ? null : _process,'
    NEW_BTN = (
        '              onPressed: (_busy || !_serverUp) ? null : () {\n'
        '                HapticFeedback.mediumImpact();\n'
        '                _process();\n'
        '              },'
    )
    txt, ok = _replace_once(txt, OLD_BTN, NEW_BTN, 'haptic (14sp anchor)')
    _rec('S29-D22', 'Process button haptic', '[OK] PASS' if ok else '[XX] FAIL')

_write(SCREENS / 'home_screen.dart', txt)


###############################################################################
# HA  history_screen.dart — AppBar title → gold gradient
# FIX: v3 used 10sp/12sp; actual `title:` is at 8sp, `color:` at 10sp
###############################################################################
_h1('HA  history_screen.dart')
txt = _read(SCREENS / 'history_screen.dart')

MARKER_HA1 = (
    'ShaderMask(\n'
    '          shaderCallback: (b) => const LinearGradient(\n'
    '            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),\n'
    '          child: Text(s.historyTitle,'
)
if not _already(txt, MARKER_HA1, 'history title already gradient'):
    # Exact anchor from diag lines 191-192: 8sp for title:, 10sp for color:
    OLD_HT = (
        '        title: Text(s.historyTitle, style: TextStyle(\n'
        '          color: cGold, fontWeight: FontWeight.bold)),'
    )
    NEW_HT = (
        '        title: ShaderMask(\n'
        '          shaderCallback: (b) => const LinearGradient(\n'
        '            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),\n'
        '          child: Text(s.historyTitle, style: const TextStyle(\n'
        '            color: Colors.white, fontWeight: FontWeight.bold))),'
    )
    txt, ok = _replace_once(txt, OLD_HT, NEW_HT, 'history title gradient (8sp/10sp)')
    _rec('HA1', 'History title gradient', '[OK] PASS' if ok else '[XX] FAIL')
    if not ok:
        # Fallback: pre-S31 layout uses const Color(0xFFD4AF37) not cGold
        OLD_HT2 = (
            '        title: Text(s.historyTitle, style: const TextStyle(\n'
            '          color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),'
        )
        txt, ok2 = _replace_once(txt, OLD_HT2, NEW_HT,
                                  'history title gradient (pre-S31 fallback)')
        _rec('HA1-fallback', 'History title gradient (pre-S31)',
             '[OK] PASS' if ok2 else '[XX] FAIL')
else:
    _rec('HA1', 'History title gradient', '[--] SKIP')

_write(SCREENS / 'history_screen.dart', txt)


###############################################################################
# SA  settings_screen.dart — AppBar title gradient + engine history
# FIX: same indent error as HA1
###############################################################################
_h1('SA  settings_screen.dart')
txt = _read(SCREENS / 'settings_screen.dart')

# SA1 — settings title gradient  (8sp/10sp — exact from diag lines 81-82)
MARKER_SA1 = (
    'ShaderMask(\n'
    '            shaderCallback: (b) => const LinearGradient(\n'
    '              colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),\n'
    '            child: Text(s.settings,'
)
if not _already(txt, MARKER_SA1, 'settings title already gradient'):
    OLD_ST = (
        '        title: Text(s.settings, style: TextStyle(\n'
        '          color: cGold, fontWeight: FontWeight.bold)),'
    )
    NEW_ST = (
        '        title: ShaderMask(\n'
        '            shaderCallback: (b) => const LinearGradient(\n'
        '              colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),\n'
        '            child: Text(s.settings, style: const TextStyle(\n'
        '              color: Colors.white, fontWeight: FontWeight.bold))),'
    )
    txt, ok = _replace_once(txt, OLD_ST, NEW_ST, 'settings title gradient (8sp/10sp)')
    _rec('SA1', 'Settings title gradient', '[OK] PASS' if ok else '[XX] FAIL')
    if not ok:
        # Fallback: pre-S31 const Color layout
        OLD_ST2 = (
            '        title: Text(s.settings, style: const TextStyle(\n'
            '          color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),'
        )
        txt, ok2 = _replace_once(txt, OLD_ST2, NEW_ST,
                                  'settings title gradient (pre-S31 fallback)')
        _rec('SA1-fallback', 'Settings title gradient (pre-S31)',
             '[OK] PASS' if ok2 else '[XX] FAIL')
else:
    _rec('SA1', 'Settings title gradient', '[--] SKIP')

# SF1 — prepend v9.0 + v8.5 before v8.4 in engine history list
MARKER_SF1 = "_EHist('v9.0',"
if not _already(txt, MARKER_SF1, 'v9.0 already in settings history'):
    OLD_V84 = "_EHist('v8.4','Source Tier Intelligence','≥98/100','LATEST','gold',"
    NEW_V84 = (
        "_EHist('v9.0','The Evolution','≥99/100','LATEST','gold',\n"
        "      'إعادة كتابة كاملة: 1,890 سطرًا. NR دائمًا قبل EQ. محسِّن LUFS+LRA مشترك.',\n"
        "      'Full rewrite: 1,890 lines. NR before EQ. Joint LUFS+LRA optimizer.'),\n"
        "    _EHist('v8.5','Tier-Adjusted Scoring','≥99/100','','gold',\n"
        "      'أوزان MDS مختلفة لكل فئة. أسقف Crest/LRA/LUFS محسوبة لكل فئة.',\n"
        "      'Different MDS weights per source tier. Per-tier ceilings.'),\n"
        "    _EHist('v8.4','Source Tier Intelligence','≥98/100','','gold',"
    )
    txt, ok = _replace_once(txt, OLD_V84, NEW_V84, 'prepend v9.0+v8.5 to history')
    _rec('SF1', 'v9.0+v8.5 prepended to settings history',
         '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('SF1', 'v9.0+v8.5 prepended to settings history', '[--] SKIP')

_write(SCREENS / 'settings_screen.dart', txt)


###############################################################################
# DONE
###############################################################################
_summary()

passed  = sum(1 for _, _, r in _log if r == '[OK] PASS')
skipped = sum(1 for _, _, r in _log if r.startswith('[--]'))
failed  = sum(1 for _, _, r in _log if r == '[XX] FAIL')

_h1(f'S29-v4 complete  —  {passed} PASS  {skipped} SKIP  {failed} FAIL')

if failed > 0:
    print(f"""
  {failed} step(s) failed. To diagnose, search for the anchor text:
    grep -n 'colorScheme' ~/tilawa-enhancer/lib/main.dart
    grep -n 'title: Text' ~/tilawa-enhancer/lib/screens/history_screen.dart
    grep -n 'title: Text' ~/tilawa-enhancer/lib/screens/settings_screen.dart
    grep -n 'onPressed.*_busy' ~/tilawa-enhancer/lib/screens/home_screen.dart

  Then paste the grep output back to Claude to get a corrected v5.
""")
else:
    print("""
  All steps passed or already applied.

  Next steps:
    cd ~/tilawa-enhancer
    flutter pub get
    flutter build apk --release --no-tree-shake-icons
""")

print("""
  SKIP = already applied by v2 / v2b / v3 (safe to ignore)
  FAIL = anchor not found — run grep above and report back
""")
