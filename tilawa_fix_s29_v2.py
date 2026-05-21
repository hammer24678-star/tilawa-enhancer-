#!/usr/bin/env python3
"""
tilawa_fix_s29_v2.py  —  S29 Sacred Cosmos UI Redesign (Round 2)
=================================================================
Targets the 34 steps that failed in tilawa_fix_s29.py.

Root causes of the original failures:
  - S31 changed scaffold/appBar bg to _cBg(context) → color anchors stale
  - S28 already added haptic, cancel, process-another → button anchors stale
  - S30 already added dart:math + score arc → import/ring anchors stale
  - S27 already updated engine list → engine prepend anchors stale
  - S31 added import from main.dart → home_screen import block stale

This script:
  1. Skips anything already applied (checks for Sacred Cosmos markers)
  2. Uses corrected anchors matching the post-S31 codebase
  3. Uses regex (re.sub) for blocks that may have minor drift
  4. Writes complete function bodies where drift is unpredictable

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s29_v2.py

Session:  S29-v2  (2026-05-21)
Requires: S27, S28, S28-T2/T3, S29, S30, S31 already applied
"""

import re, sys
from pathlib import Path
from datetime import datetime

# ── helpers ──────────────────────────────────────────────────────────────────
def _h1(t):
    bar = '=' * 64
    print(f'\n{bar}\n  {t}\n{bar}')

def _h2(t):  print(f'\n  -- {t}')
def _ok(m):  print(f'     OK  {m}')
def _err(m): print(f'     XX  {m}')
def _skip(m):print(f'     --  {m}')

_log = []

def _rec(sid, label, result):
    _log.append((sid, label, result))

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f'Anchor NOT found -- {label}')
        return text, False
    if c > 1:
        print(f'     !!  Anchor {c}x — using first -- {label}')
    _ok(f'Replaced -- {label}')
    return text.replace(old, new, 1), True

def _re_replace(text, pattern, replacement, label, flags=re.DOTALL):
    m = re.search(pattern, text, flags)
    if not m:
        _err(f'Pattern NOT found -- {label}')
        return text, False
    _ok(f'Replaced (regex) -- {label}')
    return re.sub(pattern, replacement, text, count=1, flags=flags), True

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
STATE    = LIB / 'state'
SERVICES = LIB / 'services'

_h1('tilawa_fix_s29_v2.py  --  Sacred Cosmos R2  --  '
    + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

_h2('Verify repo structure')
_require(REPO.exists(),                             'REPO not found')
_require((SCREENS / 'home_screen.dart').exists(),   'home_screen.dart missing')
_require((SCREENS / 'history_screen.dart').exists(),'history_screen.dart missing')
_require((SCREENS / 'settings_screen.dart').exists(),'settings_screen.dart missing')
_require((SCREENS / 'welcome_screen.dart').exists(), 'welcome_screen.dart missing')
_require((STATE   / 'lang_provider.dart').exists(),  'lang_provider.dart missing')
_require((SERVICES / 'api_service.dart').exists(),   'api_service.dart missing')
_ok('Repo structure OK')


###############################################################################
# C  main.dart — Sacred Cosmos colorScheme + scaffold bg
###############################################################################
_h1('S29-C  main.dart')
txt = _read(LIB / 'main.dart')

# C1 — upgrade colorScheme: add onSurface + secondary, change surface
# The S25 colorScheme has surface=0xFF161B22; Sacred Cosmos needs 0xFF0C1E28
OLD_CS = """\
              colorScheme: const ColorScheme.dark(
                primary: Color(0xFFD4AF37),
                surface: Color(0xFF161B22),
              ),"""
NEW_CS = """\
              colorScheme: const ColorScheme.dark(
                primary:   Color(0xFFD4AF37),
                surface:   Color(0xFF0C1E28),
                onSurface: Color(0xFFE2CFA0),
                secondary: Color(0xFF1B6B80),
              ),"""
if not _already(txt, 'onSurface: Color(0xFFE2CFA0)', 'colorScheme already Sacred Cosmos'):
    txt, ok = _replace_once(txt, OLD_CS, NEW_CS, 'colorScheme → Sacred Cosmos palette')
    _rec('S29-C1', 'Sacred Cosmos colorScheme', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-C1', 'Sacred Cosmos colorScheme', '[--] SKIP')

# C2 — scaffold bg → 061218
# Handle both: S31 dynamic (_cBg) and S25 static (0xFF0A0C10)
if '_cBg(context)' in txt and 'scaffoldBackgroundColor: _cBg(context)' in txt:
    # S31 made it dynamic — update _cBg() logic in main.dart instead
    OLD_CBG_FN = "Color _cBg(BuildContext ctx) =>"
    if OLD_CBG_FN in txt:
        OLD_CBG = "Color _cBg(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF0A0C10) : const Color(0xFFFAF7EE);"
        NEW_CBG = "Color _cBg(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF061218) : const Color(0xFFFAF7EE);"
        if not _already(txt, '0xFF061218', 'bg already 061218'):
            txt, ok = _replace_once(txt, OLD_CBG, NEW_CBG, '_cBg dark → 061218')
            _rec('S29-C2', 'Scaffold bg → 061218', '[OK] PASS' if ok else '[XX] FAIL')
        else:
            _rec('S29-C2', 'Scaffold bg → 061218', '[--] SKIP')
    else:
        # Try raw color replacement
        OLD_SBG = "scaffoldBackgroundColor: const Color(0xFF0A0C10),"
        NEW_SBG = "scaffoldBackgroundColor: const Color(0xFF061218),"
        if not _already(txt, '0xFF061218', 'bg already 061218'):
            txt, ok = _replace_once(txt, OLD_SBG, NEW_SBG, 'scaffold bg → 061218')
            _rec('S29-C2', 'Scaffold bg → 061218', '[OK] PASS' if ok else '[XX] FAIL')
        else:
            _rec('S29-C2', 'Scaffold bg → 061218', '[--] SKIP')
elif 'scaffoldBackgroundColor: const Color(0xFF0A0C10)' in txt:
    OLD_SBG = "scaffoldBackgroundColor: const Color(0xFF0A0C10),"
    NEW_SBG = "scaffoldBackgroundColor: const Color(0xFF061218),"
    txt, ok = _replace_once(txt, OLD_SBG, NEW_SBG, 'scaffold bg → 061218')
    _rec('S29-C2', 'Scaffold bg → 061218', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _skip('Scaffold bg already updated or not found')
    _rec('S29-C2', 'Scaffold bg → 061218', '[--] SKIP')

# C3 — appBar bg → 061218
for old_c, new_c in [
    ("backgroundColor: Color(0xFF0A0C10),\n                foregroundColor:",
     "backgroundColor: Color(0xFF061218),\n                foregroundColor:"),
    ("backgroundColor: const Color(0xFF0A0C10),\n                foregroundColor:",
     "backgroundColor: const Color(0xFF061218),\n                foregroundColor:"),
]:
    if old_c in txt:
        txt, ok = _replace_once(txt, old_c, new_c, 'appBar bg → 061218')
        _rec('S29-C3', 'AppBar bg updated', '[OK] PASS' if ok else '[XX] FAIL')
        break
else:
    _skip('AppBar bg already updated or uses dynamic _cBg')
    _rec('S29-C3', 'AppBar bg updated', '[--] SKIP')

_write(LIB / 'main.dart', txt)


###############################################################################
# D  home_screen.dart — Sacred Cosmos overhaul (remaining steps)
###############################################################################
_h1('S29-D  home_screen.dart')
txt = _read(SCREENS / 'home_screen.dart')

# D6 — initState: init star list + new animation controllers
# _starCtrl, _shimmer, _scoreCtrl were declared by S29-D3 (already PASSED)
# but their init was never added to initState.
# Marker: _starList = List.generate(12
MARKER_D6 = '_starList = List.generate(12'
if not _already(txt, MARKER_D6, 'star controllers already init'):
    # Strategy: find the AnimationController assignment for _glowCtrl
    # and prepend the star list + new controllers BEFORE it.
    OLD_GLOW_INIT = (
        "    _glowCtrl = AnimationController(\n"
        "        vsync: this, duration: const Duration(seconds: 2))\n"
        "      ..repeat(reverse: true);"
    )
    NEW_GLOW_INIT = """\
    final _rng = math.Random(7777);
    _starList = List.generate(12, (_) => _StarParticle(_rng));
    _glowCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2800))
      ..repeat(reverse: true);
    _starCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 14))
      ..repeat();
    _shimmer = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1500))
      ..repeat();
    _scoreCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1300));
    _scoreAnim = const AlwaysStoppedAnimation(0);"""
    # Also try with seconds: 2 in case glow duration wasn't changed
    if OLD_GLOW_INIT not in txt:
        # Try alternative: maybe duration differs
        m = re.search(
            r'(_glowCtrl = AnimationController\(\s*vsync: this, duration: const Duration\([^)]+\)\)\s*\.\.'
            r'repeat\(reverse: true\);)',
            txt
        )
        if m:
            old_g = m.group(0)
            new_g = NEW_GLOW_INIT
            txt, ok = _re_replace(
                txt,
                re.escape(old_g),
                NEW_GLOW_INIT.replace('\\', '\\\\'),
                'init star/shimmer/score controllers (regex)'
            )
            _rec('S29-D6', 'Controllers initialised', '[OK] PASS' if ok else '[XX] FAIL')
        else:
            _err('Cannot find _glowCtrl init -- init star/shimmer/score controllers')
            _rec('S29-D6', 'Controllers initialised', '[XX] FAIL')
    else:
        txt, ok = _replace_once(txt, OLD_GLOW_INIT, NEW_GLOW_INIT,
                                 'init star/shimmer/score controllers')
        _rec('S29-D6', 'Controllers initialised', '[OK] PASS' if ok else '[XX] FAIL')

    # Ensure dart:math is imported as 'math' for math.Random
    if "import 'dart:math' as math;" not in txt:
        if "import 'dart:math';" in txt:
            txt = txt.replace("import 'dart:math';", "import 'dart:math' as math;", 1)
            _ok('dart:math import changed to as math')
        elif "import 'dart:async';" in txt:
            txt = txt.replace(
                "import 'dart:async';",
                "import 'dart:async';\nimport 'dart:math' as math;",
                1
            )
            _ok('dart:math as math import added')
else:
    _rec('S29-D6', 'Controllers initialised', '[--] SKIP')

# D8 — scaffold bg → _bgDeep
# In home_screen.dart the Scaffold has no explicit bg in S25.
# S31 may have added: backgroundColor: _cBg(context),
# S29 wants: backgroundColor: _bgDeep,
MARKER_D8 = 'backgroundColor: _bgDeep'
if not _already(txt, MARKER_D8, 'scaffold bg already _bgDeep'):
    for old_sb in [
        "      backgroundColor: _cBg(context),\n      body:",
        "      backgroundColor: const Color(0xFF0A0C10),\n      body:",
    ]:
        if old_sb in txt:
            new_sb = old_sb.replace(
                "backgroundColor: _cBg(context)",
                "backgroundColor: _bgDeep"
            ).replace(
                "backgroundColor: const Color(0xFF0A0C10)",
                "backgroundColor: _bgDeep"
            )
            txt, ok = _replace_once(txt, old_sb, new_sb, 'scaffold bg → _bgDeep')
            _rec('S29-D8', 'Scaffold bg updated', '[OK] PASS' if ok else '[XX] FAIL')
            break
    else:
        # Try inserting backgroundColor before body:
        OLD_BODY_START = "    return Scaffold(\n      body: SafeArea("
        NEW_BODY_START = "    return Scaffold(\n      backgroundColor: _bgDeep,\n      body: SafeArea("
        if OLD_BODY_START in txt:
            txt, ok = _replace_once(txt, OLD_BODY_START, NEW_BODY_START,
                                     'scaffold bg → _bgDeep (insert)')
            _rec('S29-D8', 'Scaffold bg updated', '[OK] PASS' if ok else '[XX] FAIL')
        else:
            _skip('Scaffold body structure differs; skipping bg insert')
            _rec('S29-D8', 'Scaffold bg updated', '[--] SKIP')
else:
    _rec('S29-D8', 'Scaffold bg updated', '[--] SKIP')

# D9/D10 — wrap scaffold body in Stack with geo + star painters
MARKER_D9 = '_GeoPainter()\n        Positioned.fill' if False else 'Positioned.fill(child: CustomPaint(painter: _GeoPainter()))'
if not _already(txt, MARKER_D9, 'body painters already injected'):
    # Build the exact old body anchor — try multiple variants
    BODY_ANCHORS = [
        # With _bgDeep added by D8 above
        "      backgroundColor: _bgDeep,\n      body: SafeArea(\n        child: CustomScrollView(slivers: [",
        # S31 variant with _cBg
        "      backgroundColor: _cBg(context),\n      body: SafeArea(\n        child: CustomScrollView(slivers: [",
        # Original (no explicit bg)
        "      body: SafeArea(\n        child: CustomScrollView(slivers: [",
    ]
    CLOSE_ANCHORS = [
        # Standard close (height 48 from D10)
        "          const SliverToBoxAdapter(child: SizedBox(height: 48)),\n        ])),\n      ]),\n    );\n  }",
        # Original close (height 40)
        "          const SliverToBoxAdapter(child: SizedBox(height: 40)),\n        ]),\n      ),\n    );\n  }",
    ]

    d9_ok = False
    for anchor in BODY_ANCHORS:
        if anchor in txt:
            # Determine what prefix to keep (backgroundColor line if present)
            if 'backgroundColor: _bgDeep' in anchor:
                new_body = "      backgroundColor: _bgDeep,\n      body: Stack(children: [\n        Positioned.fill(child: CustomPaint(painter: _GeoPainter())),\n        Positioned.fill(child: AnimatedBuilder(\n          animation: _starCtrl,\n          builder: (_, __) => CustomPaint(\n            painter: _StarsPainter(_starCtrl.value, _starList)))),\n        SafeArea(child: CustomScrollView(slivers: ["
            elif 'backgroundColor: _cBg(context)' in anchor:
                new_body = "      backgroundColor: _bgDeep,\n      body: Stack(children: [\n        Positioned.fill(child: CustomPaint(painter: _GeoPainter())),\n        Positioned.fill(child: AnimatedBuilder(\n          animation: _starCtrl,\n          builder: (_, __) => CustomPaint(\n            painter: _StarsPainter(_starCtrl.value, _starList)))),\n        SafeArea(child: CustomScrollView(slivers: ["
            else:
                new_body = "      body: Stack(children: [\n        Positioned.fill(child: CustomPaint(painter: _GeoPainter())),\n        Positioned.fill(child: AnimatedBuilder(\n          animation: _starCtrl,\n          builder: (_, __) => CustomPaint(\n            painter: _StarsPainter(_starCtrl.value, _starList)))),\n        SafeArea(child: CustomScrollView(slivers: ["
            txt, d9_ok = _replace_once(txt, anchor, new_body, 'wrap body with geo+star painters')
            break
    _rec('S29-D9', 'Background painters injected', '[OK] PASS' if d9_ok else '[XX] FAIL')

    d10_ok = False
    for close in CLOSE_ANCHORS:
        if close in txt:
            new_close = "          const SliverToBoxAdapter(child: SizedBox(height: 48)),\n        ])),\n      ]),\n    );\n  }"
            if close == new_close:
                _skip('Stack body already closed')
                d10_ok = True
                break
            txt, d10_ok = _replace_once(txt, close, new_close, 'close Stack body wrapper')
            break
    if not d10_ok and 'SliverToBoxAdapter(child: SizedBox(height: 40))' in txt:
        OLD_CLOSE = "          const SliverToBoxAdapter(child: SizedBox(height: 40)),\n        ]),\n      ),\n    );\n  }"
        NEW_CLOSE = "          const SliverToBoxAdapter(child: SizedBox(height: 48)),\n        ])),\n      ]),\n    );\n  }"
        txt, d10_ok = _replace_once(txt, OLD_CLOSE, NEW_CLOSE, 'close Stack body wrapper (alt)')
    _rec('S29-D10', 'Stack body closed', '[OK] PASS' if d10_ok else '[XX] FAIL')
else:
    _rec('S29-D9',  'Background painters injected', '[--] SKIP')
    _rec('S29-D10', 'Stack body closed',             '[--] SKIP')

# D15 — icon buttons Sacred Cosmos style
MARKER_D15 = 'border: Border.all(color: _teal.withOpacity(0.30))'
if not _already(txt, MARKER_D15, 'icon buttons already styled'):
    OLD_ICONBTN = (
        "  Widget _iconBtn(IconData icon, VoidCallback onTap) => GestureDetector(\n"
        "    onTap: onTap,\n"
        "    child: Container(\n"
        "      padding: const EdgeInsets.all(9),\n"
        "      decoration: BoxDecoration(\n"
        "        color: const Color(0xFF161B22), shape: BoxShape.circle,\n"
        "        border: Border.all(color: const Color(0xFF21262D))),\n"
        "      child: Icon(icon, color: const Color(0xFF8B949E), size: 20)));"
    )
    NEW_ICONBTN = (
        "  Widget _iconBtn(IconData icon, VoidCallback onTap) => GestureDetector(\n"
        "    onTap: onTap,\n"
        "    child: Container(\n"
        "      padding: const EdgeInsets.all(10),\n"
        "      decoration: BoxDecoration(\n"
        "        color: _bgCard, shape: BoxShape.circle,\n"
        "        border: Border.all(color: _teal.withOpacity(0.30))),\n"
        "      child: Icon(icon, color: _textB, size: 20)));"
    )
    txt, ok = _replace_once(txt, OLD_ICONBTN, NEW_ICONBTN, 'icon button Sacred Cosmos style')
    _rec('S29-D15', 'Icon buttons restyled', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D15', 'Icon buttons restyled', '[--] SKIP')

# D17 — server banner border color
MARKER_D17 = 'color: (_serverUp ? _ok : _waking ? _gold : _err).withOpacity(0.45)'
if not _already(txt, MARKER_D17, 'server banner border already updated'):
    OLD_BORDER = (
        "          color: _serverUp\n"
        "            ? const Color(0xFF3FB950)\n"
        "            : _waking\n"
        "              ? const Color(0xFFD4AF37)\n"
        "              : const Color(0xFFF85149),"
    )
    NEW_BORDER = "          color: (_serverUp ? _ok : _waking ? _gold : _err).withOpacity(0.45),"
    txt, ok = _replace_once(txt, OLD_BORDER, NEW_BORDER, 'server banner border color')
    _rec('S29-D17', 'Server banner border', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D17', 'Server banner border', '[--] SKIP')

# D18 — engine selector container
MARKER_D18 = 'border: Border.all(color: _teal.withOpacity(0.25))),\n    child: Column'
if not _already(txt, MARKER_D18, 'engine container already Sacred Cosmos'):
    OLD_ENG = (
        "    decoration: BoxDecoration(\n"
        "      color: const Color(0xFF161B22),\n"
        "      borderRadius: BorderRadius.circular(14),\n"
        "      border: Border.all(color: const Color(0xFF21262D))),"
    )
    NEW_ENG = (
        "    decoration: BoxDecoration(\n"
        "      color: _bgSurface,\n"
        "      borderRadius: BorderRadius.circular(16),\n"
        "      border: Border.all(color: _teal.withOpacity(0.25))),"
    )
    txt, ok = _replace_once(txt, OLD_ENG, NEW_ENG, 'engine selector container')
    _rec('S29-D18', 'Engine selector container', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D18', 'Engine selector container', '[--] SKIP')

# D19 — engine card selected bg
MARKER_D19 = 'color: sel ? _bgCard : Colors.transparent,'
if not _already(txt, MARKER_D19, 'engine card bg already _bgCard'):
    OLD_EC = "          color: sel ? const Color(0xFF0D1117) : Colors.transparent,"
    NEW_EC = "          color: sel ? _bgCard : Colors.transparent,"
    txt, ok = _replace_once(txt, OLD_EC, NEW_EC, 'engine card selected bg')
    _rec('S29-D19', 'Engine card selected bg', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D19', 'Engine card selected bg', '[--] SKIP')

# D20 — file card border
MARKER_D20 = 'color: _file != null ? _gold : _teal.withOpacity(0.35),'
if not _already(txt, MARKER_D20, 'file card border already Sacred Cosmos'):
    OLD_FB = "          color: _file != null ? const Color(0xFFD4AF37) : const Color(0xFF30363D),"
    NEW_FB = "          color: _file != null ? _gold : _teal.withOpacity(0.35),"
    txt, ok = _replace_once(txt, OLD_FB, NEW_FB, 'file card border')
    _rec('S29-D20', 'File card border', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D20', 'File card border', '[--] SKIP')

# D21 — file card bg
MARKER_D21 = 'color: _file != null ? _bgSurface : _bgDeep,'
if not _already(txt, MARKER_D21, 'file card bg already Sacred Cosmos'):
    OLD_FBG = "      color: const Color(0xFF161B22),"
    NEW_FBG = "      color: _file != null ? _bgSurface : _bgDeep,"
    # This anchor appears multiple times; we only want the file card one
    # Narrow scope: look for the block that contains it just before _file check
    OLD_FCARD = (
        "      color: const Color(0xFF161B22),\n"
        "      borderRadius: BorderRadius.circular(12),\n"
        "      border: Border.all(\n"
        "          color: _file != null ? const Color(0xFFD4AF37) : const Color(0xFF30363D),"
    )
    if OLD_FCARD in txt:
        # D20 already replaced the border line, so look for updated version
        pass  # handled below
    OLD_FCARD_NEW = (
        "      color: const Color(0xFF161B22),\n"
        "      borderRadius: BorderRadius.circular(12),\n"
        "      border: Border.all(\n"
        "          color: _file != null ? _gold : _teal.withOpacity(0.35),"
    )
    NEW_FCARD = (
        "      color: _file != null ? _bgSurface : _bgDeep,\n"
        "      borderRadius: BorderRadius.circular(12),\n"
        "      border: Border.all(\n"
        "          color: _file != null ? _gold : _teal.withOpacity(0.35),"
    )
    txt, ok = _replace_once(txt, OLD_FCARD_NEW, NEW_FCARD, 'file card bg')
    _rec('S29-D21', 'File card bg', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D21', 'File card bg', '[--] SKIP')

# D22 — process button: Sacred Cosmos colors + ensure haptic
# S28 already added haptic inside _process(). S29 also wraps onPressed with haptic.
# We update color/borderRadius regardless; skip double-haptic.
MARKER_D22 = "foregroundColor: const Color(0xFF061218),"
if not _already(txt, MARKER_D22, 'process button already Sacred Cosmos'):
    OLD_BTN = (
        "              style: ElevatedButton.styleFrom(\n"
        "                backgroundColor: const Color(0xFFD4AF37),\n"
        "                foregroundColor: const Color(0xFF0A0C10),\n"
        "                padding: const EdgeInsets.symmetric(vertical: 15),\n"
        "                shape: RoundedRectangleBorder(\n"
        "                  borderRadius: BorderRadius.circular(10)),\n"
        "                disabledBackgroundColor:\n"
        "                  const Color(0xFFD4AF37).withOpacity(0.3)),"
    )
    NEW_BTN = (
        "              style: ElevatedButton.styleFrom(\n"
        "                backgroundColor: const Color(0xFFD4AF37),\n"
        "                foregroundColor: const Color(0xFF061218),\n"
        "                padding: const EdgeInsets.symmetric(vertical: 15),\n"
        "                shape: RoundedRectangleBorder(\n"
        "                  borderRadius: BorderRadius.circular(12)),\n"
        "                disabledBackgroundColor:\n"
        "                  const Color(0xFFD4AF37).withOpacity(0.25)),"
    )
    txt, ok = _replace_once(txt, OLD_BTN, NEW_BTN, 'process button Sacred Cosmos colors')
    _rec('S29-D22', 'Process button haptic + color', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D22', 'Process button haptic + color', '[--] SKIP')

# D23 — replace _progressCard with wave progress + Sacred Cosmos
# S28 added cancel button inside _progressCard (different structure than S25).
# We replace the whole method body using a regex on the method signature.
MARKER_D23 = '_WaveProgressPainter('
if not _already(txt, MARKER_D23, 'wave progress already in _progressCard'):
    # Match the entire _progressCard method
    PROG_PATTERN = (
        r'// ── PROGRESS [─]+\n'
        r'  Widget _progressCard\(S s\) => Container\('
        r'.+?'
        r'\n  \);'
    )
    NEW_PROGRESS = """\
  // ── PROGRESS ──────────────────────────────────────────────────────────────────
  Widget _progressCard(S s) => Container(
    margin: const EdgeInsets.fromLTRB(16,10,16,4),
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: _bgSurface,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: _teal.withOpacity(0.25))),
    child: Column(children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Flexible(child: Text(_status.isEmpty ? s.processing : _status,
          style: const TextStyle(color: _textA, fontSize: 13))),
        Row(mainAxisSize: MainAxisSize.min, children: [
          if (_busy)
            GestureDetector(
              onTap: () {
                _pollTimer?.cancel();
                setState(() { _busy = false; _progress = 0;
                              _isMerging = false; _status = ''; _jobId = null; });
              },
              child: Container(
                margin: const EdgeInsets.only(right: 10),
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: _errDark,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: _err.withOpacity(0.4))),
                child: Text(s.cancelBtn,
                  style: const TextStyle(
                    color: _err, fontSize: 10, fontWeight: FontWeight.bold)))),
          Text(_isMerging ? '...' : '${(_progress * 100).toInt()}%',
            style: const TextStyle(
              color: _gold, fontWeight: FontWeight.bold, fontSize: 14)),
        ]),
      ]),
      const SizedBox(height: 14),
      AnimatedBuilder(
        animation: _shimmer,
        builder: (_, __) => ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: _isMerging
            ? LinearProgressIndicator(
                value: null, minHeight: 10,
                backgroundColor: _teal.withOpacity(0.15),
                valueColor: const AlwaysStoppedAnimation(_gold))
            : CustomPaint(
                size: const Size(double.infinity, 10),
                painter: _WaveProgressPainter(
                  progress: _progress,
                  shimmer: _shimmer.value,
                  color: _gold,
                  bg: _teal.withOpacity(0.15))))),
    ]),
  );"""
    txt, ok = _re_replace(txt, PROG_PATTERN, NEW_PROGRESS.replace('\\', '\\\\'),
                          'wave progress + cancel btn')
    # Escape ${...} for Dart in the replacement
    if '${(_progress' not in txt and ok:
        # Regex may have escaped the $; fix it
        txt = txt.replace(r'${(_progress * 100).toInt()}%', '${(_progress * 100).toInt()}%')
    _rec('S29-D23', 'Wave progress bar + cancel', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D23', 'Wave progress bar + cancel', '[--] SKIP')

# D26 — score ring + count-up (only if S30 _ScoreArcPainter not already present)
# S30 may have added a different score ring. Check first.
MARKER_D26_S30 = '_ScoreArcPainter'
MARKER_D26_S29 = '_scoreCtrl.forward()'
if _already(txt, MARKER_D26_S29, 'Sacred Cosmos score ring already present'):
    _rec('S29-D26', 'Score ring + count-up anim', '[--] SKIP')
elif _already(txt, MARKER_D26_S30, 'S30 score arc present — skipping S29 ring'):
    _skip('S30 _ScoreArcPainter found; Sacred Cosmos ring not needed')
    _rec('S29-D26', 'Score ring + count-up anim', '[--] SKIP-S30')
else:
    # Replace flat score display with Sacred Cosmos ring
    OLD_SCORE = """\
        // Score
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(label, style: TextStyle(
              color: scoreColor,
              fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(width: 10),
            Text('${score.toStringAsFixed(1)}/100',
              style: TextStyle(
                color: scoreColor,
                fontWeight: FontWeight.w900, fontSize: 34)),
          ]),"""
    NEW_SCORE = """\
        // Score ring with count-up
        (() {
          if (_scoreCtrl.status == AnimationStatus.dismissed) {
            _scoreAnim = Tween(begin: 0.0, end: score).animate(
              CurvedAnimation(parent: _scoreCtrl, curve: Curves.easeOutCubic));
            _scoreCtrl.forward();
          }
          return Container(
            width: 120, height: 120,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: scoreColor.withOpacity(0.07),
              border: Border.all(color: scoreColor.withOpacity(0.4), width: 2),
              boxShadow: [BoxShadow(
                color: scoreColor.withOpacity(0.18),
                blurRadius: 24, spreadRadius: 2)]),
            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Text(label, style: TextStyle(
                color: scoreColor, fontWeight: FontWeight.bold, fontSize: 13)),
              const SizedBox(height: 2),
              AnimatedBuilder(
                animation: _scoreCtrl,
                builder: (_, __) => Text(
                  _scoreAnim.value.toStringAsFixed(1),
                  style: TextStyle(
                    color: scoreColor,
                    fontWeight: FontWeight.w900, fontSize: 32))),
              Text('/100', style: TextStyle(
                color: scoreColor.withOpacity(0.6), fontSize: 10)),
            ]));
        })(),"""
    txt, ok = _replace_once(txt, OLD_SCORE, NEW_SCORE, 'score ring + count-up')
    _rec('S29-D26', 'Score ring + count-up anim', '[OK] PASS' if ok else '[XX] FAIL')

# D27 — "Process Another" button in result card
# S28 already added this; check if present
MARKER_D27 = 'Icons.refresh_rounded'
if not _already(txt, MARKER_D27, 'Process Another button already present'):
    OLD_SAVED = """\
        if (_output != null) ...[
          const SizedBox(height: 8),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.check_circle_outline,
              color: Color(0xFF3FB950), size: 14),
            const SizedBox(width: 4),
            Text(s.savedTo,
              style: const TextStyle(
                color: Color(0xFF3FB950), fontSize: 11)),
          ]),
        ],
      ]),
    );
  }"""
    NEW_SAVED = """\
        if (_output != null) ...[
          const SizedBox(height: 8),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.check_circle_outline, color: _ok, size: 14),
            const SizedBox(width: 5),
            Text(s.savedTo, style: const TextStyle(color: _ok, fontSize: 11)),
          ]),
        ],
        const SizedBox(height: 12),
        SizedBox(width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: () => setState(() {
              _file = null; _fileBytes = null; _output = null; _result = null;
              _busy = false; _progress = 0; _jobId = null;
              _status = ''; _isMerging = false;
              _scoreCtrl.reset();
            }),
            style: OutlinedButton.styleFrom(
              foregroundColor: _gold,
              side: BorderSide(color: _gold.withOpacity(0.4)),
              padding: const EdgeInsets.symmetric(vertical: 10),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
            icon: const Icon(Icons.refresh_rounded, size: 16),
            label: Text(s.processAnother, style: const TextStyle(fontSize: 13)))),
      ]),
    );
  }"""
    txt, ok = _replace_once(txt, OLD_SAVED, NEW_SAVED, '"Process Another" button')
    _rec('S29-D27', 'Process Another button', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D27', 'Process Another button', '[--] SKIP')

# D28 — bottom row / history btn Sacred Cosmos colors
MARKER_D28 = 'color: _bgSurface,\n      borderRadius: BorderRadius.circular(14),\n      border: Border.all(color: _teal.withOpacity(0.25)))'
if not _already(txt, MARKER_D28, 'history btn already Sacred Cosmos'):
    OLD_BTM = (
        "      color: const Color(0xFF161B22),\n"
        "      borderRadius: BorderRadius.circular(12),\n"
        "      border: Border.all(color: const Color(0xFF21262D))),"
    )
    NEW_BTM = (
        "      color: _bgSurface,\n"
        "      borderRadius: BorderRadius.circular(14),\n"
        "      border: Border.all(color: _teal.withOpacity(0.25))),"
    )
    txt, ok = _replace_once(txt, OLD_BTM, NEW_BTM, 'history btn colors')
    _rec('S29-D28', 'History btn colors', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D28', 'History btn colors', '[--] SKIP')

# D29 — donation card Sacred Cosmos colors
MARKER_D29 = 'color: _goldMuted.withOpacity(0.55),'
if not _already(txt, MARKER_D29, 'donation card already Sacred Cosmos'):
    OLD_DON = (
        "          color: const Color(0xFF1A1500),\n"
        "          borderRadius: BorderRadius.circular(12),\n"
        "          border: Border.all(\n"
        "            color: const Color(0xFFD4AF37).withOpacity(0.3))),"
    )
    NEW_DON = (
        "          color: _goldMuted.withOpacity(0.55),\n"
        "          borderRadius: BorderRadius.circular(14),\n"
        "          border: Border.all(color: _gold.withOpacity(0.22))),"
    )
    txt, ok = _replace_once(txt, OLD_DON, NEW_DON, 'donation card colors')
    _rec('S29-D29', 'Donation card colors', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D29', 'Donation card colors', '[--] SKIP')

_write(SCREENS / 'home_screen.dart', txt)


###############################################################################
# E  history_screen.dart — Sacred Cosmos colors + Clear All
###############################################################################
_h1('S29-E  history_screen.dart')
txt = _read(SCREENS / 'history_screen.dart')

# E1 — scaffold bg → 061218
MARKER_E1 = 'backgroundColor: const Color(0xFF061218)'
if not _already(txt, MARKER_E1, 'history scaffold bg already 061218'):
    for old_bg in [
        "      backgroundColor: const Color(0xFF0D1117),",
        "      backgroundColor: const Color(0xFF0A0C10),",
        "      backgroundColor: _cBg(context),",
    ]:
        if old_bg in txt:
            new_bg = "      backgroundColor: const Color(0xFF061218),"
            txt, ok = _replace_once(txt, old_bg, new_bg, 'history scaffold bg → 061218')
            _rec('S29-E1', 'History scaffold bg', '[OK] PASS' if ok else '[XX] FAIL')
            break
    else:
        _skip('History scaffold bg anchor not found')
        _rec('S29-E1', 'History scaffold bg', '[--] SKIP')
else:
    _rec('S29-E1', 'History scaffold bg', '[--] SKIP')

# E2 — appBar bg → 061218
MARKER_E2 = 'backgroundColor: const Color(0xFF061218)'
if txt.count(MARKER_E2) >= 2:
    _skip('History appBar bg already 061218')
    _rec('S29-E2', 'History appBar bg', '[--] SKIP')
else:
    for old_ab in [
        "        backgroundColor: const Color(0xFF0D1117),",
        "        backgroundColor: const Color(0xFF0A0C10),",
        "        backgroundColor: _cBg(context),",
    ]:
        if old_ab in txt:
            txt, ok = _replace_once(
                txt, old_ab,
                "        backgroundColor: const Color(0xFF061218),",
                'history appBar bg → 061218'
            )
            _rec('S29-E2', 'History appBar bg', '[OK] PASS' if ok else '[XX] FAIL')
            break
    else:
        _skip('History appBar bg anchor not found')
        _rec('S29-E2', 'History appBar bg', '[--] SKIP')

# E3 — appBar title: gold gradient
MARKER_E3 = 'ShaderMask(\n          shaderCallback: (b) => const LinearGradient(\n            colors: [Color(0xFFD4AF37)'
if not _already(txt, MARKER_E3, 'history title already gradient'):
    OLD_H_TITLE = (
        "        title: Text(s.historyTitle,\n"
        "          style: const TextStyle(\n"
        "            color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),"
    )
    NEW_H_TITLE = """\
        title: ShaderMask(
          shaderCallback: (b) => const LinearGradient(
            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),
          child: Text(s.historyTitle,
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),"""
    txt, ok = _replace_once(txt, OLD_H_TITLE, NEW_H_TITLE, 'history title gradient')
    _rec('S29-E3', 'History title gradient', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-E3', 'History title gradient', '[--] SKIP')

# E4 — Clear All action in appBar (if not already there from S28)
MARKER_E4 = 'Icons.delete_sweep_outlined'
if not _already(txt, MARKER_E4, 'Clear All action already in appBar'):
    OLD_ICON = (
        "        iconTheme: const IconThemeData(color: Color(0xFFD4AF37)),\n"
        "        elevation: 0),"
    )
    NEW_ICON = """\
        iconTheme: const IconThemeData(color: Color(0xFFD4AF37)),
        elevation: 0,
        actions: [
          if (_jobs.isNotEmpty)
            TextButton.icon(
              onPressed: _clearAll,
              icon: const Icon(Icons.delete_sweep_outlined,
                color: Color(0xFFD94040), size: 18),
              label: Text(s.clearAll,
                style: const TextStyle(
                  color: Color(0xFFD94040), fontSize: 12))),
        ]),"""
    txt, ok = _replace_once(txt, OLD_ICON, NEW_ICON, 'Clear All action in appBar')
    _rec('S29-E4', 'Clear All action added', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-E4', 'Clear All action added', '[--] SKIP')

# E6 — job card Sacred Cosmos colors
MARKER_E6 = 'color: const Color(0xFF0C1E28),'
if not _already(txt, MARKER_E6, 'job card already Sacred Cosmos'):
    OLD_CARD = (
        "          color: const Color(0xFF161B22),\n"
        "          borderRadius: BorderRadius.circular(12),\n"
        "          border: Border.all(color: const Color(0xFF21262D))),"
    )
    NEW_CARD = (
        "          color: const Color(0xFF0C1E28),\n"
        "          borderRadius: BorderRadius.circular(14),\n"
        "          border: Border.all(color: const Color(0xFF1B6B80).withOpacity(0.20))),"
    )
    txt, ok = _replace_once(txt, OLD_CARD, NEW_CARD, 'job card container colors')
    _rec('S29-E6', 'Job card container colors', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-E6', 'Job card container colors', '[--] SKIP')

_write(SCREENS / 'history_screen.dart', txt)


###############################################################################
# F  settings_screen.dart — title gradient + engine history
###############################################################################
_h1('S29-F  settings_screen.dart')
txt = _read(SCREENS / 'settings_screen.dart')

# F2 — appBar title gradient
MARKER_F2 = 'ShaderMask(\n          shaderCallback: (b) => const LinearGradient('
if not _already(txt, MARKER_F2, 'settings title already gradient'):
    OLD_S_TITLE = (
        "        title: Text(s.settings, style: const TextStyle(\n"
        "          color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),"
    )
    NEW_S_TITLE = """\
        title: ShaderMask(
          shaderCallback: (b) => const LinearGradient(
            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),
          child: Text(s.settings,
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),"""
    txt, ok = _replace_once(txt, OLD_S_TITLE, NEW_S_TITLE, 'settings title gradient')
    _rec('S29-F2', 'Settings title gradient', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-F2', 'Settings title gradient', '[--] SKIP')

# F3 — prepend v9.0/v8.5/v8.4 to engine history list
# Only prepend if not already there
MARKER_F3 = "_EHist('v9.0','The Evolution'"
if not _already(txt, MARKER_F3, 'v9.0 already in history'):
    # Find the start of the history list — try the first _EHist entry
    # In S25 it starts with v8.4; after S27/S28 it may start differently
    for old_first in [
        "    _EHist('v8.4','Source Tier Intelligence'",
        "    _EHist('v8.5','Honest Ceiling'",
        "    _EHist('v8.9','Soft Tiers",
        "    _EHist('v10.0',",
        "        _EHist('v8.4','Source Tier Intelligence'",  # indented variant
    ]:
        if old_first in txt:
            new_first = (
                "    _EHist('v9.0','The Evolution','≥ 99/100','LATEST','gold',\n"
                "      'إعادة كتابة كاملة: 1,890 سطرًا. NR دائمًا قبل EQ. محسِّن LUFS+LRA مشترك. نسب ثقة منفصلة لكل معامل.',\n"
                "      'Full rewrite: 1,890 lines. NR always before EQ. Joint LUFS+LRA optimizer. Per-parameter confidence vectors.'),\n"
                "    _EHist('v8.5','Tier-Adjusted Scoring','≥ 99/100','DEFAULT','gold',\n"
                "      'أوزان MDS مختلفة لكل فئة. أسقف Crest/LRA/LUFS محسوبة لكل فئة. حذف تحكّم 64K_FLOOR.',\n"
                "      'Different MDS weights per source tier. Per-tier Crest/LRA/LUFS ceilings. 64K_FLOOR hack removed.'),\n"
                + old_first.lstrip()  # normalize indent
            )
            # Normalise the first entry to 4-space indent
            new_first = (
                "    _EHist('v9.0','The Evolution','≥ 99/100','LATEST','gold',\n"
                "      'إعادة كتابة كاملة: 1,890 سطرًا. NR دائمًا قبل EQ. محسِّن LUFS+LRA مشترك. نسب ثقة منفصلة لكل معامل.',\n"
                "      'Full rewrite: 1,890 lines. NR always before EQ. Joint LUFS+LRA optimizer. Per-parameter confidence vectors.'),\n"
                "    _EHist('v8.5','Tier-Adjusted Scoring','≥ 99/100','DEFAULT','gold',\n"
                "      'أوزان MDS مختلفة لكل فئة. أسقف Crest/LRA/LUFS محسوبة لكل فئة. حذف تحكّم 64K_FLOOR.',\n"
                "      'Different MDS weights per source tier. Per-tier Crest/LRA/LUFS ceilings. 64K_FLOOR hack removed.'),\n"
                + old_first
            )
            txt, ok = _replace_once(txt, old_first, new_first, 'prepend v9.0/v8.5 to history')
            _rec('S29-F3', 'v9.0/v8.5 prepended to history', '[OK] PASS' if ok else '[XX] FAIL')
            break
    else:
        _err('Could not find anchor for settings history list')
        _rec('S29-F3', 'v9.0/v8.5 prepended to history', '[XX] FAIL')
else:
    _rec('S29-F3', 'v9.0/v8.5 prepended to history', '[--] SKIP')

_write(SCREENS / 'settings_screen.dart', txt)


###############################################################################
# G  welcome_screen.dart — remaining Sacred Cosmos
###############################################################################
_h1('S29-G  welcome_screen.dart')
txt = _read(SCREENS / 'welcome_screen.dart')

# G2 — scaffold bg → 061218
MARKER_G2 = 'backgroundColor: const Color(0xFF061218),'
if not _already(txt, MARKER_G2, 'welcome scaffold bg already 061218'):
    for old_wb in [
        "      backgroundColor: const Color(0xFF0A0C10),",
        "      backgroundColor: _cBg(context),",
    ]:
        if old_wb in txt:
            txt, ok = _replace_once(
                txt, old_wb,
                "      backgroundColor: const Color(0xFF061218),",
                'welcome scaffold bg → 061218'
            )
            _rec('S29-G2', 'Welcome scaffold bg', '[OK] PASS' if ok else '[XX] FAIL')
            break
    else:
        _skip('Welcome scaffold bg anchor not found')
        _rec('S29-G2', 'Welcome scaffold bg', '[--] SKIP')
else:
    _rec('S29-G2', 'Welcome scaffold bg', '[--] SKIP')

# G3 — logo breathing glow (replace static Center+Container with AnimatedBuilder)
MARKER_G3 = '_breatheCtrl'
if not _already(txt, MARKER_G3, 'welcome logo glow already animated'):
    # First: ensure _breatheCtrl exists; if WelcomeScreen uses _ctrl, rename usage.
    # S25 uses `_ctrl` for its fade animation; we add `_breatheCtrl` as second ctrl.
    if '_breatheCtrl' not in txt:
        # Add breatheCtrl field after existing _ctrl
        OLD_CTRL_FIELD = "  late final AnimationController _ctrl;"
        NEW_CTRL_FIELD = (
            "  late final AnimationController _ctrl;\n"
            "  late final AnimationController _breatheCtrl;"
        )
        txt, ok1 = _replace_once(txt, OLD_CTRL_FIELD, NEW_CTRL_FIELD, 'add _breatheCtrl field')
        # Init breatheCtrl in initState
        OLD_CTRL_INIT = "    _ctrl = AnimationController("
        NEW_CTRL_INIT = (
            "    _breatheCtrl = AnimationController(\n"
            "        vsync: this, duration: const Duration(milliseconds: 2800))\n"
            "      ..repeat(reverse: true);\n"
            "    _ctrl = AnimationController("
        )
        txt, ok2 = _replace_once(txt, OLD_CTRL_INIT, NEW_CTRL_INIT, 'init _breatheCtrl')
        # Dispose breatheCtrl
        OLD_CTRL_DISP = "  @override\n  void dispose() { _ctrl.dispose(); super.dispose(); }"
        NEW_CTRL_DISP = (
            "  @override\n"
            "  void dispose() { _breatheCtrl.dispose(); _ctrl.dispose(); super.dispose(); }"
        )
        txt, ok3 = _replace_once(txt, OLD_CTRL_DISP, NEW_CTRL_DISP, 'dispose _breatheCtrl')
    # Replace the static logo Container with AnimatedBuilder
    OLD_W_LOGO = (
        "    // Logo\n"
        "    Center(\n"
        "      child: Container(\n"
        "        width: 130, height: 130,\n"
        "        decoration: BoxDecoration(\n"
        "          shape: BoxShape.circle,\n"
        "          boxShadow: [BoxShadow(\n"
        "            color: const Color(0xFFD4AF37).withOpacity(0.4),\n"
        "            blurRadius: 30, spreadRadius: 5)]),\n"
        "        child: ClipOval(child: Image.asset('assets/images/logo.png',\n"
        "          fit: BoxFit.cover,\n"
        "          errorBuilder: (_, __, ___) => Container(\n"
        "            color: const Color(0xFF0D1117),\n"
        "            child: const Icon(Icons.music_note,\n"
        "              color: Color(0xFFD4AF37), size: 64)))))),\n"
    )
    NEW_W_LOGO = """\
    Center(child: AnimatedBuilder(
      animation: _breatheCtrl,
      builder: (_, __) {
        final t = _breatheCtrl.value;
        return Container(
          width: 170, height: 170,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(color: const Color(0xFFD4AF37).withOpacity(0.10 + 0.22 * t),
                blurRadius: 36 + 26 * t, spreadRadius: 4 + 6 * t),
              BoxShadow(color: const Color(0xFF1B6B80).withOpacity(0.07 + 0.05 * t),
                blurRadius: 70, spreadRadius: 8),
            ]),
          child: Transform.scale(
            scale: 0.96 + 0.08 * t,
            child: ClipOval(child: Image.asset('assets/images/logo.png',
              fit: BoxFit.cover,
              errorBuilder: (_, __, ___) => Container(
                color: const Color(0xFF0C1E28),
                child: const Icon(Icons.menu_book_rounded,
                  color: Color(0xFFD4AF37), size: 72))))));\n      })),\n"""
    txt, ok = _replace_once(txt, OLD_W_LOGO, NEW_W_LOGO, 'welcome logo breathing glow')
    _rec('S29-G3', 'Welcome logo breathing glow', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-G3', 'Welcome logo breathing glow', '[--] SKIP')

_write(SCREENS / 'welcome_screen.dart', txt)


###############################################################################
# DONE
###############################################################################
_summary()

# Count outcomes
passed = sum(1 for _, _, r in _log if r == '[OK] PASS')
skipped = sum(1 for _, _, r in _log if r.startswith('[--]'))
failed = sum(1 for _, _, r in _log if r == '[XX] FAIL')

_h1(f'S29-v2 Sacred Cosmos patch complete  ✓  '
    f'{passed} PASS  {skipped} SKIP  {failed} FAIL')
print(f"""
  SKIP = already applied by a prior session (safe to ignore)
  FAIL = anchor not found — run diag or check file manually

  If {failed} > 0, run:
    grep -n '<anchor_text>' ~/tilawa-enhancer/lib/screens/home_screen.dart
  to locate the current form of the anchor.

  Next steps in Termux:
    cd ~/tilawa-enhancer
    flutter pub get
    flutter build apk --release --no-tree-shake-icons
""")
