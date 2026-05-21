#!/usr/bin/env python3
"""
tilawa_fix_s29_v3.py  —  S29 Sacred Cosmos  (v3 — corrected anchors)
=====================================================================
Uses exact anchors from tilawa_diag_s29 output.

Steps:
  D6   initState — init _starList/_starCtrl/_shimmer/_scoreCtrl
  D9   Body painters — inject geo + star painters inside body Stack
  D12  Logo breathing glow (exact diag anchor)
  D13  AppName gold gradient ShaderMask (exact diag anchor)
  D22  Process button haptic (exact diag anchor)
  D23  Wave progress bar (regex — replaces _progressCard)
  D26  Score ring + count-up animation
  D27  "Process Another" reset button
  D29  Donation card bg → Sacred Cosmos gold
  MA   main.dart — update _buildDarkTheme colorScheme + snackBar
  HA   History appBar title → gold gradient (exact diag anchor)
  SA   Settings appBar title → gold gradient (exact diag anchor)
  SF   Settings history → prepend v9.0 + v8.5 before v8.4

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s29_v3.py
"""

import re, sys
from pathlib import Path
from datetime import datetime

def _h1(t):
    bar = '=' * 64
    print(f'\n{bar}\n  {t}\n{bar}')

def _h2(t):  print(f'\n  -- {t}')
def _ok(m):  print(f'     OK  {m}')
def _err(m): print(f'     XX  {m}')
def _skip(m):print(f'     --  {m}')

_log = []

def _rec(sid, label, result): _log.append((sid, label, result))

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:   _err(f'Anchor NOT found -- {label}'); return text, False
    if c > 1:    print(f'     !!  {c}x — first -- {label}')
    else:        _ok(f'Replaced -- {label}')
    return text.replace(old, new, 1), True

def _re_sub(text, pattern, replacement, label, flags=re.DOTALL):
    if not re.search(pattern, text, flags):
        _err(f'Pattern NOT found -- {label}'); return text, False
    _ok(f'Replaced (regex) -- {label}')
    return re.sub(pattern, replacement, text, count=1, flags=flags), True

def _already(text, marker, label):
    if marker in text: _skip(f'Already applied -- {label}'); return True
    return False

def _read(p):     return Path(p).read_text(encoding='utf-8')
def _write(p, t): Path(p).write_text(t, encoding='utf-8')

def _require(cond, msg):
    if not cond: _err(f'FATAL: {msg}'); _summary(); sys.exit(1)

def _summary():
    _h1('SUMMARY')
    print(f"\n  {'Step':<8}  {'Label':<52}  Result")
    print(f"  {'----':<8}  {'------':<52}  ------")
    for sid, label, result in _log:
        print(f'  {sid:<8}  {label:<52}  {result}')

REPO     = Path.home() / 'tilawa-enhancer'
LIB      = REPO / 'lib'
SCREENS  = LIB / 'screens'
STATE    = LIB / 'state'

_h1('tilawa_fix_s29_v3.py  --  Sacred Cosmos  --  '
    + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

_h2('Verify repo')
_require(REPO.exists(), 'REPO not found')
_require((SCREENS / 'home_screen.dart').exists(), 'home_screen.dart missing')
_ok('Repo OK')


###############################################################################
# main.dart
###############################################################################
_h1('main.dart')
txt = _read(LIB / 'main.dart')

# MA1 — colorScheme: add surface + onSurface + secondary + snackBar theme
MARKER_MA1 = 'secondary: Color(0xFF1B6B80),'
if not _already(txt, MARKER_MA1, 'colorScheme already updated'):
    OLD_CS = (
        '    colorScheme: const ColorScheme.dark(\n'
        '      primary: Color(0xFFD4AF37),\n'
        '      surface: Color(0xFF161B22),\n'
        '      onSurface: Color(0xFFC9D1D9),\n'
        '      background: Color(0xFF0A0C10),\n'
        '    ),'
    )
    NEW_CS = (
        '    colorScheme: const ColorScheme.dark(\n'
        '      primary:   Color(0xFFD4AF37),\n'
        '      surface:   Color(0xFF0C1E28),\n'
        '      onSurface: Color(0xFFE2CFA0),\n'
        '      secondary: Color(0xFF1B6B80),\n'
        '    ),'
    )
    txt, ok = _replace_once(txt, OLD_CS, NEW_CS, 'colorScheme Sacred Cosmos')
    _rec('MA1', 'colorScheme updated', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('MA1', 'colorScheme updated', '[--] SKIP')

# MA2 — appBar bg in _buildDarkTheme
OLD_APP = '      backgroundColor: Color(0xFF0A0C10),\n      foregroundColor: Color(0xFFD4AF37),\n      elevation: 0,'
NEW_APP = '      backgroundColor: Color(0xFF061218),\n      foregroundColor: Color(0xFFD4AF37),\n      elevation: 0,'
txt, ok = _replace_once(txt, OLD_APP, NEW_APP, 'appBarTheme bg → 061218')
_rec('MA2', 'AppBar bg 0A0C10 → 061218', '[OK] PASS' if ok else '[XX] FAIL')

_write(LIB / 'main.dart', txt)


###############################################################################
# home_screen.dart
###############################################################################
_h1('home_screen.dart')
txt = _read(SCREENS / 'home_screen.dart')

# D6 — initState: init _starList, _starCtrl, _shimmer, _scoreCtrl
_h2('D6 — init star/shimmer/score controllers')
MARKER_D6 = '_starList = List.generate('
if not _already(txt, MARKER_D6, 'controllers already init'):
    OLD_INIT = (
        '    _glowCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(seconds: 2))\n'
        '      ..repeat(reverse: true);\n'
        '    _checkServer();'
    )
    NEW_INIT = (
        '    final rng = Random(7777);\n'
        '    _starList = List.generate(12, (_) => _StarParticle(rng));\n'
        '    _glowCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(milliseconds: 2800))\n'
        '      ..repeat(reverse: true);\n'
        '    _starCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(seconds: 14))\n'
        '      ..repeat();\n'
        '    _shimmer = AnimationController(\n'
        '        vsync: this, duration: const Duration(milliseconds: 1500))\n'
        '      ..repeat();\n'
        '    _scoreCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(milliseconds: 1300));\n'
        '    _scoreAnim = const AlwaysStoppedAnimation(0);\n'
        '    _checkServer();'
    )
    txt, ok = _replace_once(txt, OLD_INIT, NEW_INIT, 'init controllers')
    _rec('S29-D6', 'Controllers initialised in initState', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D6', 'Controllers initialised in initState', '[--] SKIP')

# D9 — inject geo + star painters into body
# Strategy: change Container's `child: SafeArea(` to a Stack with painters
_h2('D9 — inject background painters')
MARKER_D9 = '// S29: Sacred Cosmos painters Stack'
if not _already(txt, MARKER_D9, 'painters already injected'):
    # Step 1: find `child: SafeArea(` inside the body Container and wrap with Stack
    # Using regex to match the indented `child: SafeArea(` that is direct child of Container
    pat_open = r'(          decoration: BoxDecoration\(\s*gradient: LinearGradient\([\s\S]+?\]\)\),\s*)(child: SafeArea\()'
    def _inject_stack(m):
        return (
            m.group(1) +
            '// S29: Sacred Cosmos painters Stack\n'
            '          child: Stack(children: [\n'
            '            if (dark) Positioned.fill(\n'
            '              child: IgnorePointer(child: CustomPaint(painter: _GeoPainter()))),\n'
            '            if (dark) Positioned.fill(\n'
            '              child: IgnorePointer(child: AnimatedBuilder(\n'
            '                animation: _starCtrl,\n'
            '                builder: (_, __) => CustomPaint(\n'
            '                  painter: _StarsPainter(_starCtrl.value, _starList))))),\n'
            '            SafeArea('
        )
    m = re.search(pat_open, txt, re.DOTALL)
    if m:
        txt = re.sub(pat_open, _inject_stack, txt, count=1, flags=re.DOTALL)
        _ok('Stack open injected')
        # Step 2: close the Stack — find the SizedBox(height: 40/48) sliver + close pattern
        # and add Stack close `]),` after SafeArea closes
        pat_close = r"(          const SliverToBoxAdapter\(child: SizedBox\(height: \d+\)\),\s*\]\),\s*\),\s*)(\),\s*\n  \);)"
        def _close_stack(m2):
            return m2.group(1) + '          ]),\n' + m2.group(2)
        m2 = re.search(pat_close, txt, re.DOTALL)
        if m2:
            txt = re.sub(pat_close, _close_stack, txt, count=1, flags=re.DOTALL)
            _ok('Stack close injected')
            _rec('S29-D9', 'Background painters Stack injected', '[OK] PASS')
        else:
            _err('Stack close pattern not found')
            _rec('S29-D9', 'Background painters Stack injected', '[XX] FAIL — open injected but not closed')
    else:
        _err('body child: SafeArea( pattern not found')
        _rec('S29-D9', 'Background painters Stack injected', '[XX] FAIL')
else:
    _rec('S29-D9', 'Background painters Stack injected', '[--] SKIP')

# D12 — logo breathing glow  (EXACT anchor from diag)
_h2('D12 — logo breathing glow')
MARKER_D12 = 'animation: _glowCtrl,\n        builder: (_, __) {\n          final t = _glowCtrl.value;\n          return Container(\n            width: 58'
if not _already(txt, MARKER_D12, 'logo already AnimatedBuilder breathing'):
    OLD_LOGO = (
        '      Container(\n'
        '        width: 52, height: 52,\n'
        '        decoration: BoxDecoration(\n'
        '          shape: BoxShape.circle,\n'
        '          boxShadow: [BoxShadow(\n'
        '            color: _tGold.withOpacity(0.25),\n'
        '            blurRadius: 16)]),\n'
        "        child: ClipOval(child: Image.asset('assets/images/logo.png',\n"
        '          fit: BoxFit.cover,\n'
        '          errorBuilder: (_,__,___) => Container(\n'
        '            color: const Color(0xFF1A1500),\n'
        '            child: const Icon(Icons.music_note,\n'
        '              color: Color(0xFFD4AF37), size: 28))))),\n'
    )
    NEW_LOGO = (
        '      AnimatedBuilder(\n'
        '        animation: _glowCtrl,\n'
        '        builder: (_, __) {\n'
        '          final t = _glowCtrl.value;\n'
        '          return Container(\n'
        '            width: 58, height: 58,\n'
        '            decoration: BoxDecoration(\n'
        '              shape: BoxShape.circle,\n'
        '              boxShadow: [BoxShadow(\n'
        '                color: _gold.withOpacity(0.10 + 0.22 * t),\n'
        '                blurRadius: 16 + 14 * t, spreadRadius: 1 + 2 * t)]),\n'
        '            child: Transform.scale(\n'
        '              scale: 0.97 + 0.06 * t,\n'
        "              child: ClipOval(child: Image.asset('assets/images/logo.png',\n"
        '                fit: BoxFit.cover,\n'
        '                errorBuilder: (_, __, ___) => Container(\n'
        '                  color: _bgCard,\n'
        '                  child: const Icon(Icons.menu_book_rounded,\n'
        '                    color: _gold, size: 30))))));\n'
        '        }),\n'
    )
    txt, ok = _replace_once(txt, OLD_LOGO, NEW_LOGO, 'logo breathing glow')
    _rec('S29-D12', 'Logo breathing glow', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D12', 'Logo breathing glow', '[--] SKIP')

# D13 — appName gold gradient ShaderMask  (EXACT anchor from diag)
_h2('D13 — appName gold gradient')
MARKER_D13 = 'ShaderMask(\n          shaderCallback: (b) => const LinearGradient(\n            colors: [_gold, _goldLight, _gold],'
if not _already(txt, MARKER_D13, 'appName already gold gradient'):
    OLD_NAME = (
        '        AnimatedBuilder(animation: _glowCtrl,\n'
        '          builder: (_, __) => Text(s.appName,\n'
        '            style: TextStyle(\n'
        '              fontSize: 24, fontWeight: FontWeight.bold,\n'
        '              color: Color.lerp(\n'
        '                _tGold,\n'
        '                const Color(0xFFFFF4B0),\n'
        '                _glowCtrl.value)))),\n'
    )
    NEW_NAME = (
        '        ShaderMask(\n'
        '          shaderCallback: (b) => const LinearGradient(\n'
        '            colors: [_gold, _goldLight, _gold],\n'
        '            stops: [0.0, 0.5, 1.0]).createShader(b),\n'
        '          child: Text(s.appName, style: const TextStyle(\n'
        '            fontSize: 26, fontWeight: FontWeight.w900,\n'
        '            color: Colors.white, height: 1.1))),\n'
    )
    txt, ok = _replace_once(txt, OLD_NAME, NEW_NAME, 'appName gold gradient')
    _rec('S29-D13', 'AppName gold gradient', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D13', 'AppName gold gradient', '[--] SKIP')

# D22 — process button haptic  (EXACT anchor from diag)
_h2('D22 — process button haptic')
MARKER_D22 = 'HapticFeedback.mediumImpact();\n                _process();'
if not _already(txt, MARKER_D22, 'haptic already added'):
    OLD_BTN = '                onPressed: (_busy || !_serverUp) ? null : _process,'
    NEW_BTN = (
        '                onPressed: (_busy || !_serverUp) ? null : () {\n'
        '                  HapticFeedback.mediumImpact();\n'
        '                  _process();\n'
        '                },'
    )
    txt, ok = _replace_once(txt, OLD_BTN, NEW_BTN, 'process button haptic')
    _rec('S29-D22', 'Process button haptic', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D22', 'Process button haptic', '[--] SKIP')

# D23 — wave progress bar  (regex on full _progressCard method)
_h2('D23 — wave progress bar')
MARKER_D23 = '_WaveProgressPainter('
if not _already(txt, MARKER_D23, 'wave progress already present'):
    pat_prog = (
        r'  // ── PROGRESS [─]+\n'
        r'  Widget _progressCard\(S s\) => Container\('
        r'[\s\S]+?'
        r'\n  \);'
    )
    NEW_PROG = (
        '  // ── PROGRESS ──────────────────────────────────────────────────────────────────\n'
        '  Widget _progressCard(S s) => Container(\n'
        '    margin: const EdgeInsets.fromLTRB(16,10,16,4),\n'
        '    padding: const EdgeInsets.all(20),\n'
        '    decoration: BoxDecoration(\n'
        '      color: _bgSurface,\n'
        '      borderRadius: BorderRadius.circular(16),\n'
        '      border: Border.all(color: _teal.withOpacity(0.25))),\n'
        '    child: Column(children: [\n'
        '      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [\n'
        "        Flexible(child: Text(_status.isEmpty ? s.processing : _status,\n"
        '          style: const TextStyle(color: _textA, fontSize: 13))),\n'
        '        Row(mainAxisSize: MainAxisSize.min, children: [\n'
        '          if (_busy)\n'
        '            GestureDetector(\n'
        '              onTap: () {\n'
        '                _pollTimer?.cancel();\n'
        '                setState(() {\n'
        "                  _busy = false; _progress = 0; _isMerging = false;\n"
        "                  _status = ''; _jobId = null;\n"
        '                });\n'
        '              },\n'
        '              child: Container(\n'
        '                margin: const EdgeInsets.only(right: 10),\n'
        '                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),\n'
        '                decoration: BoxDecoration(\n'
        '                  color: _errDark,\n'
        '                  borderRadius: BorderRadius.circular(8),\n'
        '                  border: Border.all(color: _err.withOpacity(0.4))),\n'
        '                child: Text(s.cancelBtn,\n'
        '                  style: const TextStyle(\n'
        '                    color: _err, fontSize: 10, fontWeight: FontWeight.bold)))),\n'
        "          Text(_isMerging ? '...' : '${(_progress * 100).toInt()}%',\n"
        '            style: const TextStyle(\n'
        '              color: _gold, fontWeight: FontWeight.bold, fontSize: 14)),\n'
        '        ]),\n'
        '      ]),\n'
        '      const SizedBox(height: 14),\n'
        '      AnimatedBuilder(\n'
        '        animation: _shimmer,\n'
        '        builder: (_, __) => ClipRRect(\n'
        '          borderRadius: BorderRadius.circular(10),\n'
        '          child: _isMerging\n'
        '            ? LinearProgressIndicator(\n'
        '                value: null, minHeight: 10,\n'
        '                backgroundColor: _teal.withOpacity(0.15),\n'
        '                valueColor: const AlwaysStoppedAnimation(_gold))\n'
        '            : CustomPaint(\n'
        '                size: const Size(double.infinity, 10),\n'
        '                painter: _WaveProgressPainter(\n'
        '                  progress: _progress,\n'
        '                  shimmer: _shimmer.value,\n'
        '                  color: _gold,\n'
        '                  bg: _teal.withOpacity(0.15))))),\n'
        '    ]),\n'
        '  );'
    )
    txt, ok = _re_sub(txt, pat_prog, NEW_PROG, 'wave progress bar')
    _rec('S29-D23', 'Wave progress bar + cancel btn', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D23', 'Wave progress bar + cancel btn', '[--] SKIP')

# D26 — score ring + count-up animation
_h2('D26 — score ring + count-up')
MARKER_D26 = '_scoreCtrl.forward();'
if not _already(txt, MARKER_D26, 'score ring already present'):
    OLD_SCORE = (
        '        // Score\n'
        '        Row(\n'
        '          mainAxisAlignment: MainAxisAlignment.center,\n'
        '          crossAxisAlignment: CrossAxisAlignment.baseline,\n'
        '          textBaseline: TextBaseline.alphabetic,\n'
        '          children: [\n'
        '            Text(label, style: TextStyle(\n'
        '              color: scoreColor,\n'
        '              fontWeight: FontWeight.bold, fontSize: 16)),\n'
        '            const SizedBox(width: 10),\n'
        "            Text('${score.toStringAsFixed(1)}/100',\n"
        '              style: TextStyle(\n'
        '                color: scoreColor,\n'
        '                fontWeight: FontWeight.w900, fontSize: 34)),\n'
        '          ]),\n'
    )
    NEW_SCORE = (
        '        // Score ring with count-up\n'
        '        Builder(builder: (_) {\n'
        '          if (_scoreCtrl.status == AnimationStatus.dismissed) {\n'
        '            _scoreAnim = Tween(begin: 0.0, end: score).animate(\n'
        '              CurvedAnimation(parent: _scoreCtrl, curve: Curves.easeOutCubic));\n'
        '            _scoreCtrl.forward();\n'
        '          }\n'
        '          return Container(\n'
        '            width: 120, height: 120,\n'
        '            decoration: BoxDecoration(\n'
        '              shape: BoxShape.circle,\n'
        '              color: scoreColor.withOpacity(0.07),\n'
        '              border: Border.all(color: scoreColor.withOpacity(0.4), width: 2),\n'
        '              boxShadow: [BoxShadow(\n'
        '                color: scoreColor.withOpacity(0.18),\n'
        '                blurRadius: 24, spreadRadius: 2)]),\n'
        '            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [\n'
        '              Text(label, style: TextStyle(\n'
        '                color: scoreColor, fontWeight: FontWeight.bold, fontSize: 13)),\n'
        '              const SizedBox(height: 2),\n'
        '              AnimatedBuilder(\n'
        '                animation: _scoreCtrl,\n'
        '                builder: (_, __) => Text(\n'
        '                  _scoreAnim.value.toStringAsFixed(1),\n'
        '                  style: TextStyle(\n'
        '                    color: scoreColor,\n'
        '                    fontWeight: FontWeight.w900, fontSize: 32))),\n'
        '              Text(\'/100\', style: TextStyle(\n'
        '                color: scoreColor.withOpacity(0.6), fontSize: 10)),\n'
        '            ]));\n'
        '        }),\n'
    )
    txt, ok = _replace_once(txt, OLD_SCORE, NEW_SCORE, 'score ring + count-up')
    _rec('S29-D26', 'Score ring + count-up', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D26', 'Score ring + count-up', '[--] SKIP')

# D27 — "Process Another" reset button (after savedTo row)
_h2('D27 — Process Another button')
MARKER_D27 = 's.processAnother'
if not _already(txt, MARKER_D27, 'Process Another already present'):
    OLD_SAVED = (
        '        if (_output != null) ...[\n'
        '          const SizedBox(height: 8),\n'
        '          Row(mainAxisAlignment: MainAxisAlignment.center, children: [\n'
        '            const Icon(Icons.check_circle_outline,\n'
        '              color: Color(0xFF3FB950), size: 14),\n'
        '            const SizedBox(width: 4),\n'
        '            Text(s.savedTo,\n'
        '              style: const TextStyle(\n'
        '                color: Color(0xFF3FB950), fontSize: 11)),\n'
        '          ]),\n'
        '        ],\n'
        '      ]),\n'
        '    );\n'
        '  }'
    )
    NEW_SAVED = (
        '        if (_output != null) ...[\n'
        '          const SizedBox(height: 8),\n'
        '          Row(mainAxisAlignment: MainAxisAlignment.center, children: [\n'
        '            const Icon(Icons.check_circle_outline, color: _ok, size: 14),\n'
        '            const SizedBox(width: 5),\n'
        '            Text(s.savedTo, style: const TextStyle(color: _ok, fontSize: 11)),\n'
        '          ]),\n'
        '        ],\n'
        '        const SizedBox(height: 12),\n'
        '        SizedBox(width: double.infinity,\n'
        '          child: OutlinedButton.icon(\n'
        '            onPressed: () => setState(() {\n'
        '              _file = null; _output = null; _result = null;\n'
        '              _busy = false; _progress = 0; _jobId = null;\n'
        "              _status = ''; _isMerging = false;\n"
        '              _scoreCtrl.reset();\n'
        '            }),\n'
        '            style: OutlinedButton.styleFrom(\n'
        '              foregroundColor: _gold,\n'
        '              side: BorderSide(color: _gold.withOpacity(0.4)),\n'
        '              padding: const EdgeInsets.symmetric(vertical: 10),\n'
        '              shape: RoundedRectangleBorder(\n'
        '                borderRadius: BorderRadius.circular(12))),\n'
        '            icon: const Icon(Icons.refresh_rounded, size: 16),\n'
        '            label: Text(s.processAnother,\n'
        '              style: const TextStyle(fontSize: 13)))),\n'
        '      ]),\n'
        '    );\n'
        '  }'
    )
    txt, ok = _replace_once(txt, OLD_SAVED, NEW_SAVED, 'Process Another button')
    _rec('S29-D27', 'Process Another button', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D27', 'Process Another button', '[--] SKIP')

# D29 — donation card bg: Material S30-P5 color update  (EXACT anchor from diag)
_h2('D29 — donation card Sacred Cosmos bg')
MARKER_D29 = 'color: _goldMuted,'
if not _already(txt, MARKER_D29, 'donation already Sacred Cosmos'):
    OLD_DON = "        color: const Color(0xFF1A1500),\n        borderRadius: BorderRadius.circular(12),"
    NEW_DON = "        color: _goldMuted,\n        borderRadius: BorderRadius.circular(14),"
    txt, ok = _replace_once(txt, OLD_DON, NEW_DON, 'donation card bg _goldMuted')
    _rec('S29-D29', 'Donation card bg', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D29', 'Donation card bg', '[--] SKIP')

_write(SCREENS / 'home_screen.dart', txt)


###############################################################################
# history_screen.dart
###############################################################################
_h1('history_screen.dart')
txt = _read(SCREENS / 'history_screen.dart')

# HA1 — title gradient  (EXACT anchor from diag line 191-192)
MARKER_HA1 = 'ShaderMask(\n          shaderCallback: (b) => const LinearGradient(\n            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),\n          child: Text(s.historyTitle,'
if not _already(txt, MARKER_HA1, 'history title already gradient'):
    OLD_HT = (
        '          title: Text(s.historyTitle, style: TextStyle(\n'
        '            color: cGold, fontWeight: FontWeight.bold)),'
    )
    NEW_HT = (
        '          title: ShaderMask(\n'
        '            shaderCallback: (b) => const LinearGradient(\n'
        '              colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),\n'
        '            child: Text(s.historyTitle, style: const TextStyle(\n'
        '              color: Colors.white, fontWeight: FontWeight.bold))),'
    )
    txt, ok = _replace_once(txt, OLD_HT, NEW_HT, 'history title gradient')
    _rec('HA1', 'History title gradient', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('HA1', 'History title gradient', '[--] SKIP')

_write(SCREENS / 'history_screen.dart', txt)


###############################################################################
# settings_screen.dart
###############################################################################
_h1('settings_screen.dart')
txt = _read(SCREENS / 'settings_screen.dart')

# SA1 — settings title gradient  (EXACT anchor from diag line 81-82)
MARKER_SA1 = 'ShaderMask(\n            shaderCallback: (b) => const LinearGradient(\n              colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),\n            child: Text(s.settings,'
if not _already(txt, MARKER_SA1, 'settings title already gradient'):
    OLD_ST = (
        '          title: Text(s.settings, style: TextStyle(\n'
        '            color: cGold, fontWeight: FontWeight.bold)),'
    )
    NEW_ST = (
        '          title: ShaderMask(\n'
        '            shaderCallback: (b) => const LinearGradient(\n'
        '              colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),\n'
        '            child: Text(s.settings, style: const TextStyle(\n'
        '              color: Colors.white, fontWeight: FontWeight.bold))),'
    )
    txt, ok = _replace_once(txt, OLD_ST, NEW_ST, 'settings title gradient')
    _rec('SA1', 'Settings title gradient', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('SA1', 'Settings title gradient', '[--] SKIP')

# SF1 — prepend v9.0 + v8.5 before v8.4 in _history list  (anchor from diag line 8)
MARKER_SF1 = "_EHist('v9.0',"
if not _already(txt, MARKER_SF1, 'v9.0 already in history'):
    OLD_V84 = "_EHist('v8.4','Source Tier Intelligence','≥98/100','LATEST','gold',"
    NEW_V84 = (
        "_EHist('v9.0','The Evolution','≥99/100','LATEST','gold',\n"
        "      'إعادة كتابة كاملة: 1,890 سطرًا. NR دائمًا قبل EQ. محسِّن LUFS+LRA مشترك.',\n"
        "      'Full rewrite: 1,890 lines. NR before EQ. Joint LUFS+LRA optimizer.'),\n"
        "    _EHist('v8.5','Tier-Adjusted Scoring','≥98/100','','gold',\n"
        "      'أوزان MDS مختلفة لكل فئة. أسقف Crest/LRA/LUFS محسوبة لكل فئة.',\n"
        "      'Different MDS weights per source tier. Per-tier ceilings.'),\n"
        "    _EHist('v8.4','Source Tier Intelligence','≥98/100','','gold',"
    )
    txt, ok = _replace_once(txt, OLD_V84, NEW_V84, 'prepend v9.0 + v8.5 to history')
    _rec('SF1', 'v9.0 + v8.5 prepended to settings history', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('SF1', 'v9.0 + v8.5 prepended to settings history', '[--] SKIP')

_write(SCREENS / 'settings_screen.dart', txt)


###############################################################################
# DONE
###############################################################################
_summary()

passed  = sum(1 for _, _, r in _log if r == '[OK] PASS')
skipped = sum(1 for _, _, r in _log if r.startswith('[--]'))
failed  = sum(1 for _, _, r in _log if r == '[XX] FAIL')

_h1(f'S29-v3 complete  —  {passed} PASS  {skipped} SKIP  {failed} FAIL')
print(f"""
  Run:
    cd ~/tilawa-enhancer
    python3 tilawa_fix_s29_v3.py
    flutter pub get && flutter build apk --release --no-tree-shake-icons
""")
