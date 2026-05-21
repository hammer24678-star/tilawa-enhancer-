#!/usr/bin/env python3
"""
tilawa_fix_s29_v2b.py  —  S29 Sacred Cosmos  (supplement to v2)
================================================================
Covers the steps that v2 did not include:

  S29-D1  dart:math + flutter/services imports
  S29-D4  Engine list: prepend v9.0 / v8.5 / v8.4 before v8.1
  S29-D5  Default engine v8.1 → v8.5
  S29-D12 Home logo: breathing glow AnimatedBuilder
  S29-D13 App name: gold gradient ShaderMask
  S29-D28 Bottom-row / history button (corrected 6-space indent anchor)

Also fixes the D23 progressCard regex so it works correctly on files
that still have the S25 _progressCard structure (no cancel btn yet).

Run AFTER tilawa_fix_s29_v2.py:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s29_v2b.py

Session: S29-v2b  (2026-05-21)
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

def _re_replace(text, pattern, replacement, label):
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        _err(f'Pattern NOT found -- {label}')
        return text, False
    _ok(f'Replaced (regex) -- {label}')
    return re.sub(pattern, replacement, text, count=1, flags=re.DOTALL), True

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

REPO    = Path.home() / 'tilawa-enhancer'
LIB     = REPO / 'lib'
SCREENS = LIB / 'screens'

_h1('tilawa_fix_s29_v2b.py  --  Sacred Cosmos Supplement  --  '
    + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

_h2('Verify repo structure')
_require(REPO.exists(), 'REPO not found — run from ~/tilawa-enhancer parent')
_require((SCREENS / 'home_screen.dart').exists(), 'home_screen.dart missing')
_ok('Repo structure OK')


###############################################################################
# home_screen.dart — remaining steps
###############################################################################
_h1('home_screen.dart  —  D1 / D4 / D5 / D12 / D13 / D23fix / D28')
txt = _read(SCREENS / 'home_screen.dart')

# ── D1: dart:math + flutter/services imports ──────────────────────────────────
_h2('D1 — dart:math + flutter/services imports')
MARKER_D1 = "import 'dart:math'"
if not _already(txt, MARKER_D1, 'dart:math already imported'):
    OLD_IMP = (
        "import 'dart:io';\n"
        "import 'dart:async';\n"
        "import 'package:flutter/material.dart';"
    )
    NEW_IMP = (
        "import 'dart:io';\n"
        "import 'dart:async';\n"
        "import 'dart:math';\n"
        "import 'package:flutter/material.dart';\n"
        "import 'package:flutter/services.dart';"
    )
    txt, ok = _replace_once(txt, OLD_IMP, NEW_IMP, 'add dart:math + services imports')
    # If services already there, just add math
    if not ok and "import 'package:flutter/services.dart';" in txt:
        OLD_IMP2 = "import 'dart:async';\nimport 'package:flutter/material.dart';"
        NEW_IMP2 = "import 'dart:async';\nimport 'dart:math';\nimport 'package:flutter/material.dart';"
        txt, ok = _replace_once(txt, OLD_IMP2, NEW_IMP2, 'add dart:math only (services exists)')
    _rec('S29-D1', 'Import dart:math + HapticFeedback', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D1', 'Import dart:math + HapticFeedback', '[--] SKIP')

# ── D4: engine list — prepend v9.0 / v8.5 / v8.4 ────────────────────────────
_h2('D4 — prepend v9.0 / v8.5 / v8.4 to engine list')
MARKER_D4 = "_EngineData(\n      'v9.0'"
if not _already(txt, MARKER_D4, 'v9.0 already first engine'):
    OLD_ENG = "  static const _engines = [\n    _EngineData(\n      'v8.1'"
    NEW_ENG = """\
  static const _engines = [
    _EngineData(
      'v9.0', 'التطور', 'The Evolution', 99.0,
      'LATEST', 'gold',
      ['NR→EQ Order', 'Joint LUFS+LRA', 'Conf. Vectors', 'Hash Cache', 'LFS Validate'],
      'إعادة كتابة كاملة: 1,890 سطرًا. NR دائمًا قبل EQ. محسِّن LUFS+LRA مشترك. نسب ثقة منفصلة لكل معامل.',
      'Full rewrite: 1,890 lines. NR always before EQ. Joint LUFS+LRA optimizer. Per-parameter confidence vectors.',
    ),
    _EngineData(
      'v8.5', 'تقييم محايد', 'Honest Ceiling', 99.0,
      'DEFAULT', 'gold',
      ['4-Tier Weights', 'Per-Tier Targets', 'Absolute Score', 'MDS-V85', 'No 64K Hack'],
      'أوزان MDS مختلفة لكل فئة. أسقف Crest/LRA/LUFS محسوبة لكل فئة. حذف تحكّم 64K_FLOOR.',
      'Different MDS weights per source tier. Per-tier Crest/LRA/LUFS ceilings. 64K_FLOOR hack removed.',
    ),
    _EngineData(
      'v8.4', 'ذكاء مصدر الصوت', 'Source Tier Intelligence', 98.0,
      '', 'gold',
      ['Tier Detection', 'Codec Cutoff', 'Adaptive NR/EQ', 'Clipping Detect', 'MDS-V84'],
      'يحلِّل جودة المصدر: تردد قطع الكودك، نوع الضوضاء، القص. يضبط NR وEQ بناءً على التصنيف.',
      'Analyzes source quality: codec cutoff, noise type, clipping. Adapts NR, EQ, LRA per source tier.',
    ),
    _EngineData(
      'v8.1'"""
    txt, ok = _replace_once(txt, OLD_ENG, NEW_ENG, 'engines v9.0/v8.5/v8.4 prepended')
    _rec('S29-D4', 'Engines v9.0/v8.5/v8.4 prepended', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D4', 'Engines v9.0/v8.5/v8.4 prepended', '[--] SKIP')

# ── D5: default engine → v8.5 ────────────────────────────────────────────────
_h2('D5 — default engine → v8.5')
MARKER_D5_V85 = "_engine    = 'v8.5';"
MARKER_D5_V90 = "_engine    = 'v9.0';"   # also acceptable
if _already(txt, MARKER_D5_V85, 'default already v8.5') or \
   _already(txt, MARKER_D5_V90, 'default already v9.0 (loaded from prefs)'):
    _rec('S29-D5', 'Default engine → v8.5', '[--] SKIP')
else:
    for old_d in ["  String  _engine    = 'v8.1';",
                  "  String _engine     = 'v8.1';",
                  "  String  _engine = 'v8.1';"]:
        if old_d in txt:
            new_d = old_d.replace("'v8.1'", "'v8.5'")
            txt, ok = _replace_once(txt, old_d, new_d, 'default engine → v8.5')
            _rec('S29-D5', 'Default engine → v8.5', '[OK] PASS' if ok else '[XX] FAIL')
            break
    else:
        _err('Default engine anchor not found')
        _rec('S29-D5', 'Default engine → v8.5', '[XX] FAIL')

# ── D12: logo breathing glow ─────────────────────────────────────────────────
_h2('D12 — logo breathing glow in _header()')
MARKER_D12 = 'animation: _glowCtrl,\n        builder: (_, __) {\n          final t = _glowCtrl.value;\n          return Container(\n            width: 58'
if not _already(txt, MARKER_D12, 'logo glow already AnimatedBuilder'):
    OLD_LOGO = (
        "      Container(\n"
        "        width: 52, height: 52,\n"
        "        decoration: BoxDecoration(\n"
        "          shape: BoxShape.circle,\n"
        "          boxShadow: [BoxShadow(\n"
        "            color: const Color(0xFFD4AF37).withOpacity(0.25),\n"
        "            blurRadius: 16)]),\n"
        "        child: ClipOval(child: Image.asset('assets/images/logo.png',\n"
        "          fit: BoxFit.cover,\n"
        "          errorBuilder: (_,__,___) => Container(\n"
        "            color: const Color(0xFF1A1500),\n"
        "            child: const Icon(Icons.music_note,\n"
        "              color: Color(0xFFD4AF37), size: 28))))),\n"
    )
    NEW_LOGO = (
        "      AnimatedBuilder(\n"
        "        animation: _glowCtrl,\n"
        "        builder: (_, __) {\n"
        "          final t = _glowCtrl.value;\n"
        "          return Container(\n"
        "            width: 58, height: 58,\n"
        "            decoration: BoxDecoration(\n"
        "              shape: BoxShape.circle,\n"
        "              boxShadow: [BoxShadow(\n"
        "                color: _gold.withOpacity(0.10 + 0.22 * t),\n"
        "                blurRadius: 16 + 14 * t, spreadRadius: 1 + 2 * t)]),\n"
        "            child: Transform.scale(\n"
        "              scale: 0.97 + 0.06 * t,\n"
        "              child: ClipOval(child: Image.asset('assets/images/logo.png',\n"
        "                fit: BoxFit.cover,\n"
        "                errorBuilder: (_, __, ___) => Container(\n"
        "                  color: _bgCard,\n"
        "                  child: const Icon(Icons.menu_book_rounded,\n"
        "                    color: _gold, size: 30))))));\n"
        "        }),\n"
    )
    txt, ok = _replace_once(txt, OLD_LOGO, NEW_LOGO, 'logo breathing glow')
    _rec('S29-D12', 'Logo breathing glow', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D12', 'Logo breathing glow', '[--] SKIP')

# ── D13: app name gold gradient ShaderMask ────────────────────────────────────
_h2('D13 — app name gold gradient shader')
MARKER_D13 = 'ShaderMask(\n          shaderCallback: (b) => const LinearGradient(\n            colors: [_gold, _goldLight, _gold],'
if not _already(txt, MARKER_D13, 'app name already gold gradient'):
    OLD_APPNAME = (
        "        AnimatedBuilder(animation: _glowCtrl,\n"
        "          builder: (_, __) => Text(s.appName,\n"
        "            style: TextStyle(\n"
        "              fontSize: 24, fontWeight: FontWeight.bold,\n"
        "              color: Color.lerp(\n"
        "                const Color(0xFFD4AF37),\n"
        "                const Color(0xFFFFF4B0),\n"
        "                _glowCtrl.value)))),"
    )
    NEW_APPNAME = (
        "        ShaderMask(\n"
        "          shaderCallback: (b) => const LinearGradient(\n"
        "            colors: [_gold, _goldLight, _gold],\n"
        "            stops: [0.0, 0.5, 1.0]).createShader(b),\n"
        "          child: Text(s.appName, style: const TextStyle(\n"
        "            fontSize: 26, fontWeight: FontWeight.w900,\n"
        "            color: Colors.white, height: 1.1))),"
    )
    txt, ok = _replace_once(txt, OLD_APPNAME, NEW_APPNAME, 'app name gold gradient')
    _rec('S29-D13', 'App name gold gradient', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D13', 'App name gold gradient', '[--] SKIP')

# ── D23: progressCard wave — fix / re-apply if v2 regex failed ────────────────
_h2('D23 — wave progress bar (fix/verify)')
MARKER_D23 = '_WaveProgressPainter('
if not _already(txt, MARKER_D23, 'wave progress already present'):
    # Use regex on the full method — safe for both S25 structure and S28 + cancel variant
    PROG_PAT = (
        r'// ── PROGRESS [─]+\n'
        r'  Widget _progressCard\(S s\) => Container\('
        r'.+?'
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
        '                setState(() { _busy = false; _progress = 0;\n'
        "                              _isMerging = false; _status = ''; _jobId = null; });\n"
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
    txt, ok = _re_replace(txt, PROG_PAT, NEW_PROG, 'wave progress + cancel btn')
    _rec('S29-D23', 'Wave progress bar + cancel', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D23', 'Wave progress bar + cancel', '[--] SKIP')

# ── D28: bottom-row / history button (corrected 6-space indent) ───────────────
_h2('D28 — history bottom-row Sacred Cosmos colors')
MARKER_D28 = 'color: _bgSurface,\n          borderRadius: BorderRadius.circular(14),\n          border: Border.all(color: _teal.withOpacity(0.25)))'
if not _already(txt, MARKER_D28, 'history btn already Sacred Cosmos'):
    OLD_BTM = (
        "          color: const Color(0xFF161B22),\n"
        "          borderRadius: BorderRadius.circular(12),\n"
        "          border: Border.all(color: const Color(0xFF21262D))),"
    )
    NEW_BTM = (
        "          color: _bgSurface,\n"
        "          borderRadius: BorderRadius.circular(14),\n"
        "          border: Border.all(color: _teal.withOpacity(0.25))),"
    )
    txt, ok = _replace_once(txt, OLD_BTM, NEW_BTM, 'history btn colors (6-space indent)')
    _rec('S29-D28', 'History btn colors', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _rec('S29-D28', 'History btn colors', '[--] SKIP')

_write(SCREENS / 'home_screen.dart', txt)


###############################################################################
# DONE
###############################################################################
_summary()

passed  = sum(1 for _, _, r in _log if r == '[OK] PASS')
skipped = sum(1 for _, _, r in _log if r.startswith('[--]'))
failed  = sum(1 for _, _, r in _log if r == '[XX] FAIL')

_h1(f'S29-v2b complete  —  {passed} PASS  {skipped} SKIP  {failed} FAIL')
print(f"""
  Run order on device:
    cd ~/tilawa-enhancer
    python3 tilawa_fix_s29_v2.py
    python3 tilawa_fix_s29_v2b.py
    flutter pub get
    flutter build apk --release --no-tree-shake-icons

  If any FAIL, run:
    grep -n '<anchor>' lib/screens/home_screen.dart
  to find the current form of the anchor and report back.
""")
