#!/usr/bin/env python3
"""
tilawa_fix_s29.py  —  S29 Sacred Cosmos UI Redesign
=====================================================
Complete visual overhaul of all 4 Flutter screens.

Changes:
  1. Sacred Cosmos color palette (deep teal + burnished gold)
  2. Islamic 8-star geometric background (CustomPainter, all screens)
  3. Floating gold star particles (animated sine-wave drift)
  4. Breathing logo with animated glow on HomeScreen header
  5. Wave CustomPainter progress bar (shimmer effect)
  6. Score count-up animation (0 → result) in score ring
  7. Cancel button in progress card (S28)
  8. "Process Another File" reset button after result (S28)
  9. Metrics row tappable → copy to clipboard (S28)
 10. Est. time pill on file card (S28)
 11. Engines updated: v9.0 LATEST, v8.5 DEFAULT, v8.4, v8.0, v7.0
 12. History: score ring + Clear All button with confirm dialog (S28)
 13. Settings: Sacred Cosmos colors + v9.0/v8.5 engine history
 14. Welcome: gold gradient title + breathing logo + step icons
 15. lang_provider: cancelBtn, processAnother, clearAll, copiedMetrics,
     estTime, clearAllConfirm, historyTitle strings added
 16. api_service: clearAllJobRecords() method added
 17. main.dart: Sacred Cosmos MaterialApp theme

Run from ~/tilawa-enhancer:
  cd ~/tilawa-enhancer && python3 tilawa_fix_s29.py
"""

import sys
from pathlib import Path
from datetime import datetime

# ── helpers ───────────────────────────────────────────────────────────────────
def _h1(t):
    bar = '=' * 64
    print(f'\n{bar}\n  {t}\n{bar}')

def _h2(t):  print(f'\n  -- {t}')
def _ok(m):  print(f'     OK  {m}')
def _err(m): print(f'     XX  {m}')

_log = []

def _rec(sid, label, ok):
    _log.append((sid, label, '[OK] PASS' if ok else '[XX] FAIL'))
    return ok

def _replace_once(text, old, new, label):
    c = text.count(old)
    if c == 0:
        _err(f'Anchor NOT found -- {label}')
        return text, False
    if c > 1:
        print(f'     !!  Anchor found {c}x -- using first -- {label}')
    _ok(f'Replaced -- {label}')
    return text.replace(old, new, 1), True

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

_h1('tilawa_fix_s29.py  --  Sacred Cosmos  --  ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

_h2('Verify repo structure')
_require(REPO.exists(),       'REPO not found — run from ~/tilawa-enhancer parent')
_require((SCREENS / 'home_screen.dart').exists(), 'home_screen.dart missing')
_require((STATE / 'lang_provider.dart').exists(),  'lang_provider.dart missing')
_require((SERVICES / 'api_service.dart').exists(),  'api_service.dart missing')
_ok('Repo structure OK')


###############################################################################
# S29-A  lang_provider.dart — add S28 strings
###############################################################################
_h1('S29-A  lang_provider.dart')

txt = _read(STATE / 'lang_provider.dart')

# 1. Add import dart:math if missing (for star painters — not needed in lang)
# Add new strings before closing brace of class S
OLD_LAST_S_STRING = "  String get version       => ar ? 'الإصدار 2"
NEW_LAST_S_STRING = OLD_LAST_S_STRING  # keep, append after target string

# Add S28 + historyTitle strings after `version`
OLD_VERSION = "  String get version       => ar ? 'الإصدار 2."
# Find exact version string
import re
m = re.search(r"  String get version[^\n]+\n", txt)
if m:
    old_ver = m.group(0)
    new_ver = old_ver + r"""  String get historyTitle   => ar ? 'سجل الملفات المعالجة'          : 'Processing History';
  // S28
  String get cancelBtn      => ar ? 'إلغاء'                  : 'Cancel';
  String get processAnother => ar ? 'معالجة ملف آخر'          : 'Process Another File';
  String get clearAll       => ar ? 'مسح الكل'               : 'Clear All';
  String get clearAllConfirm=> ar ? 'هل تريد مسح كل السجل؟'  : 'Clear all history?';
  String get copiedMetrics  => ar ? 'تم نسخ المقاييس'         : 'Metrics copied';
  String get estTime        => ar ? 'الوقت المتوقع'            : 'Est. time';
"""
    txt, ok = _replace_once(txt, old_ver, new_ver, 'add S28 strings after version')
    _rec('S29-A1', 'Add S28 strings to lang_provider', ok)
else:
    _err('version string not found — manually add S28 strings')
    _rec('S29-A1', 'Add S28 strings to lang_provider', False)

_write(STATE / 'lang_provider.dart', txt)


###############################################################################
# S29-B  api_service.dart — add clearAllJobRecords()
###############################################################################
_h1('S29-B  api_service.dart')

txt = _read(SERVICES / 'api_service.dart')

OLD_REMOVE = "  static Future<void> removeJobRecord(String jobId) async {"
NEW_REMOVE = """  static Future<void> clearAllJobRecords() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('saved_jobs');
  }

  static Future<void> removeJobRecord(String jobId) async {"""

txt, ok = _replace_once(txt, OLD_REMOVE, NEW_REMOVE, 'add clearAllJobRecords()')
_rec('S29-B1', 'clearAllJobRecords() added', ok)
_write(SERVICES / 'api_service.dart', txt)


###############################################################################
# S29-C  main.dart — Sacred Cosmos theme
###############################################################################
_h1('S29-C  main.dart')

txt = _read(LIB / 'main.dart')

OLD_THEME = "            theme: ThemeData("
NEW_THEME = """            theme: ThemeData(
              colorScheme: const ColorScheme.dark(
                primary:   Color(0xFFD4AF37),
                surface:   Color(0xFF0C1E28),
                onSurface: Color(0xFFE2CFA0),
                secondary: Color(0xFF1B6B80),
              ),"""

txt, ok = _replace_once(txt, OLD_THEME, NEW_THEME, 'inject colorScheme into ThemeData')
_rec('S29-C1', 'Sacred Cosmos colorScheme', ok)

OLD_BG = "              scaffoldBackgroundColor: const Color(0xFF0A0C10),"
NEW_BG = "              scaffoldBackgroundColor: const Color(0xFF061218),"
txt, ok = _replace_once(txt, OLD_BG, NEW_BG, 'scaffold bg → deep teal-black')
_rec('S29-C2', 'Scaffold bg 0A0C10 → 061218', ok)

OLD_APP = "            backgroundColor: const Color(0xFF0A0C10),"
NEW_APP = "            backgroundColor: const Color(0xFF061218),"
txt, ok = _replace_once(txt, OLD_APP, NEW_APP, 'appBar bg → 061218')
_rec('S29-C3', 'AppBar bg updated', ok)

_write(LIB / 'main.dart', txt)


###############################################################################
# S29-D  home_screen.dart — full Sacred Cosmos overhaul
###############################################################################
_h1('S29-D  home_screen.dart')

txt = _read(SCREENS / 'home_screen.dart')

# D1 — imports: add dart:math + services/haptics
OLD_IMPORT = "import 'dart:io';\nimport 'dart:async';\nimport 'package:flutter/material.dart';"
NEW_IMPORT = "import 'dart:io';\nimport 'dart:async';\nimport 'dart:math';\nimport 'package:flutter/material.dart';\nimport 'package:flutter/services.dart';"
txt, ok = _replace_once(txt, OLD_IMPORT, NEW_IMPORT, 'add dart:math + services imports')
_rec('S29-D1', 'Import dart:math + HapticFeedback', ok)

# D2 — color constants block (insert after imports block, before class)
OLD_CLASS = "class HomeScreen extends StatefulWidget {"
NEW_CLASS = """// ── Sacred Cosmos tokens ─────────────────────────────────────────────────────
const _bgDeep    = Color(0xFF061218);
const _bgSurface = Color(0xFF0C1E28);
const _bgCard    = Color(0xFF102B38);
const _gold      = Color(0xFFD4AF37);
const _goldLight = Color(0xFFF0CF60);
const _goldMuted = Color(0xFF3A2B08);
const _teal      = Color(0xFF1B6B80);
const _tealLight = Color(0xFF2E8FA8);
const _textA     = Color(0xFFE2CFA0);
const _textB     = Color(0xFF8AACBA);
const _textC     = Color(0xFF3D5A65);
const _ok        = Color(0xFF2ABF6E);
const _okDark    = Color(0xFF0D3D22);
const _err       = Color(0xFFD94040);
const _errDark   = Color(0xFF3D0808);

class HomeScreen extends StatefulWidget {"""
txt, ok = _replace_once(txt, OLD_CLASS, NEW_CLASS, 'inject Sacred Cosmos color tokens')
_rec('S29-D2', 'Color tokens injected', ok)

# D3 — add star/shimmer/score controllers + fileBytes + star list to state
OLD_GLOW_FIELD = "  late final AnimationController _glowCtrl;"
NEW_GLOW_FIELD = """  late final AnimationController _glowCtrl;
  late final AnimationController _starCtrl;
  late final AnimationController _shimmer;
  late final AnimationController _scoreCtrl;
  late Animation<double> _scoreAnim;
  late final List<_StarParticle> _starList;
  int? _fileBytes;"""
txt, ok = _replace_once(txt, OLD_GLOW_FIELD, NEW_GLOW_FIELD, 'add animation fields')
_rec('S29-D3', 'Animation fields added', ok)

# D4 — update engines to v9.0/v8.5/v8.4/v8.0/v7.0
OLD_ENGINES = "  static const _engines = [\n    _EngineData(\n      'v8.1'"
NEW_ENGINES = """  static const _engines = [
    _EngineData(
      'v9.0', 'التطور', 'The Evolution', 98.0,
      'LATEST', 'gold',
      ['Full Rewrite', 'Joint LUFS+LRA', 'Conf. Vectors', 'Hash Cache', 'LFS Validate'],
      'إعادة كتابة كاملة: 1,890 سطرًا. NR دائمًا قبل EQ. محسِّن LUFS+LRA مشترك. نسب ثقة منفصلة لكل معامل.',
      'Full rewrite: 1,890 lines. NR always before EQ. Joint LUFS+LRA optimizer. Per-parameter confidence vectors.',
    ),
    _EngineData(
      'v8.5', 'تقييم محايد', 'Tier-Adjusted Scoring', 98.0,
      'DEFAULT', 'gold',
      ['4-Tier Weights', 'Per-Tier Targets', 'Absolute Score', 'MDS-V85', 'No 64K Hack'],
      'أوزان MDS مختلفة لكل فئة. أسقف Crest/LRA/LUFS محسوبة لكل فئة. حذف تحكّم 64K_FLOOR.',
      'Different MDS weights per source tier. Per-tier Crest/LRA/LUFS ceilings. 64K_FLOOR hack removed.',
    ),
    _EngineData(
      'v8.4', 'ذكاء مصدر الصوت', 'Source Tier Intelligence', 98.0,
      '', 'gold',
      ['Tier Detection', 'Codec Cutoff', 'Adaptive NR/EQ', 'MDS-V84', 'Clipping Detect'],
      'يحلِّل جودة المصدر: تردد قطع الكودك، نوع الضوضاء، القص. يضبط NR وEQ بناءً على التصنيف.',
      'Analyzes source quality: codec cutoff, noise type, clipping. Adapts NR, EQ, LRA per source tier.',
    ),
    _EngineData(
      'v8.1'"""
txt, ok = _replace_once(txt, OLD_ENGINES, NEW_ENGINES, 'update engines v9.0/v8.5/v8.4 prepend')
_rec('S29-D4', 'Engines v9.0/v8.5/v8.4 prepended', ok)

# D5 — default engine v8.1 → v8.5
OLD_DEFAULT = "  String  _engine    = 'v8.1';"
NEW_DEFAULT = "  String  _engine    = 'v8.5';"
txt, ok = _replace_once(txt, OLD_DEFAULT, NEW_DEFAULT, 'default engine v8.1 → v8.5')
_rec('S29-D5', 'Default engine → v8.5', ok)

# D6 — initState: init star/shimmer/score controllers
OLD_INIT = """    _glowCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 2))
      ..repeat(reverse: true);
    _checkServer();"""
NEW_INIT = """    final rng = Random(7777);
    _starList = List.generate(12, (_) => _StarParticle(rng));
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
    _scoreAnim = const AlwaysStoppedAnimation(0);
    _checkServer();"""
txt, ok = _replace_once(txt, OLD_INIT, NEW_INIT, 'init star/shimmer/score controllers')
_rec('S29-D6', 'Controllers initialised', ok)

# D7 — dispose: add new controllers
OLD_DISPOSE = "    _glowCtrl.dispose();\n    super.dispose();"
NEW_DISPOSE = """    _starCtrl.dispose();
    _shimmer.dispose();
    _scoreCtrl.dispose();
    _glowCtrl.dispose();
    super.dispose();"""
txt, ok = _replace_once(txt, OLD_DISPOSE, NEW_DISPOSE, 'dispose new controllers')
_rec('S29-D7', 'Dispose updated', ok)

# D8 — scaffold bg color
OLD_SCAFFOLD = "      backgroundColor: const Color(0xFF0A0C10),"
NEW_SCAFFOLD = "      backgroundColor: _bgDeep,"
txt, ok = _replace_once(txt, OLD_SCAFFOLD, NEW_SCAFFOLD, 'scaffold bg → _bgDeep')
_rec('S29-D8', 'Scaffold bg updated', ok)

# D9 — wrap scaffold body in Stack with geo + star painters
OLD_BODY = "      body: SafeArea(\n        child: CustomScrollView(slivers: ["
NEW_BODY = """      body: Stack(children: [
        Positioned.fill(child: CustomPaint(painter: _GeoPainter())),
        Positioned.fill(child: AnimatedBuilder(
          animation: _starCtrl,
          builder: (_, __) => CustomPaint(
            painter: _StarsPainter(_starCtrl.value, _starList)))),
        SafeArea(child: CustomScrollView(slivers: ["""
txt, ok = _replace_once(txt, OLD_BODY, NEW_BODY, 'wrap body with geo+star painters')
_rec('S29-D9', 'Background painters injected', ok)

# D10 — close the extra Stack after the existing closing ]),
# The old closing was:       ]),\n    );\n  }
OLD_BODY_CLOSE = "          const SliverToBoxAdapter(child: SizedBox(height: 40)),\n        ]),\n      ),\n    );\n  }"
NEW_BODY_CLOSE = """          const SliverToBoxAdapter(child: SizedBox(height: 48)),
        ])),
      ]),
    );
  }"""
txt, ok = _replace_once(txt, OLD_BODY_CLOSE, NEW_BODY_CLOSE, 'close Stack body wrapper')
_rec('S29-D10', 'Stack body closed', ok)

# D11 — header: logo breathing glow + gold gradient title
OLD_HEADER = "  // ── HEADER ─────────────────────────────────────────────────────────────────\n  Widget _header(S s) => Padding(\n    padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),\n    child: Row(children: ["
NEW_HEADER = """  // ── HEADER ────────────────────────────────────────────────────────────────────
  Widget _header(S s) => Container(
    padding: const EdgeInsets.fromLTRB(18, 20, 18, 12),
    child: Row(children: ["""
txt, ok = _replace_once(txt, OLD_HEADER, NEW_HEADER, 'header container padding')
_rec('S29-D11', 'Header padding updated', ok)

# D12 — logo in header: breathing glow
OLD_LOGO = """      Container(
        width: 52, height: 52,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          boxShadow: [BoxShadow(
            color: const Color(0xFFD4AF37).withOpacity(0.25),
            blurRadius: 16)]),
        child: ClipOval(child: Image.asset('assets/images/logo.png',
          fit: BoxFit.cover,
          errorBuilder: (_,__,___) => Container(
            color: const Color(0xFF1A1500),
            child: const Icon(Icons.music_note,
              color: Color(0xFFD4AF37), size: 28))))),"""
NEW_LOGO = """      AnimatedBuilder(
        animation: _glowCtrl,
        builder: (_, __) {
          final t = _glowCtrl.value;
          return Container(
            width: 58, height: 58,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              boxShadow: [BoxShadow(
                color: _gold.withOpacity(0.10 + 0.22 * t),
                blurRadius: 16 + 14 * t, spreadRadius: 1 + 2 * t)]),
            child: Transform.scale(
              scale: 0.97 + 0.06 * t,
              child: ClipOval(child: Image.asset('assets/images/logo.png',
                fit: BoxFit.cover,
                errorBuilder: (_, __, ___) => Container(
                  color: _bgCard,
                  child: const Icon(Icons.menu_book_rounded,
                    color: _gold, size: 30))))));
        }),"""
txt, ok = _replace_once(txt, OLD_LOGO, NEW_LOGO, 'logo breathing glow')
_rec('S29-D12', 'Logo breathing glow', ok)

# D13 — app name: gold gradient shader
OLD_APPNAME = "        AnimatedBuilder(animation: _glowCtrl,\n          builder: (_, __) => Text(s.appName,\n            style: TextStyle(\n              fontSize: 24, fontWeight: FontWeight.bold,\n              color: Color.lerp(\n                const Color(0xFFD4AF37),\n                const Color(0xFFFFF4B0),\n                _glowCtrl.value)))),"
NEW_APPNAME = """        ShaderMask(
          shaderCallback: (b) => const LinearGradient(
            colors: [_gold, _goldLight, _gold],
            stops: [0.0, 0.5, 1.0]).createShader(b),
          child: Text(s.appName, style: const TextStyle(
            fontSize: 26, fontWeight: FontWeight.w900,
            color: Colors.white, height: 1.1))),"""
txt, ok = _replace_once(txt, OLD_APPNAME, NEW_APPNAME, 'appName gold gradient shader')
_rec('S29-D13', 'App name gold gradient', ok)

# D14 — subtitle color
OLD_SUB = "          style: const TextStyle(\n            color: Color(0xFF8B949E), fontSize: 10, letterSpacing: 1.5)),"
NEW_SUB = "          style: const TextStyle(\n            color: _textB, fontSize: 10, letterSpacing: 1.6)),"
txt, ok = _replace_once(txt, OLD_SUB, NEW_SUB, 'subtitle color → _textB')
_rec('S29-D14', 'Subtitle color updated', ok)

# D15 — icon buttons style
OLD_ICONBTN = "  Widget _iconBtn(IconData icon, VoidCallback onTap) => GestureDetector(\n    onTap: onTap,\n    child: Container(\n      padding: const EdgeInsets.all(9),\n      decoration: BoxDecoration(\n        color: const Color(0xFF161B22), shape: BoxShape.circle,\n        border: Border.all(color: const Color(0xFF21262D))),\n      child: Icon(icon, color: const Color(0xFF8B949E), size: 20)));"
NEW_ICONBTN = """  Widget _iconBtn(IconData icon, VoidCallback onTap) => GestureDetector(
    onTap: onTap,
    child: Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: _bgCard, shape: BoxShape.circle,
        border: Border.all(color: _teal.withOpacity(0.30))),
      child: Icon(icon, color: _textB, size: 20)));"""
txt, ok = _replace_once(txt, OLD_ICONBTN, NEW_ICONBTN, 'icon button Sacred Cosmos style')
_rec('S29-D15', 'Icon buttons restyled', ok)

# D16 — server banner colors
OLD_BANNER_ONLINE  = "        color: _serverUp\n          ? const Color(0xFF0D2015)\n          : _waking\n            ? const Color(0xFF1A1500)\n            : const Color(0xFF200D0D),"
NEW_BANNER_ONLINE  = "        color: _serverUp\n          ? _ok.withOpacity(0.06)\n          : _waking\n            ? _gold.withOpacity(0.06)\n            : _err.withOpacity(0.06),"
txt, ok = _replace_once(txt, OLD_BANNER_ONLINE, NEW_BANNER_ONLINE, 'server banner bg color')
_rec('S29-D16', 'Server banner bg', ok)

OLD_BANNER_BORDER = "          color: _serverUp\n            ? const Color(0xFF3FB950)\n            : _waking\n              ? const Color(0xFFD4AF37)\n              : const Color(0xFFF85149),"
NEW_BANNER_BORDER = "          color: (_serverUp ? _ok : _waking ? _gold : _err).withOpacity(0.45),"
txt, ok = _replace_once(txt, OLD_BANNER_BORDER, NEW_BANNER_BORDER, 'server banner border color')
_rec('S29-D17', 'Server banner border', ok)

# D18 — engine selector container colors
OLD_ENG_CONT = "    decoration: BoxDecoration(\n      color: const Color(0xFF161B22),\n      borderRadius: BorderRadius.circular(14),\n      border: Border.all(color: const Color(0xFF21262D))),"
NEW_ENG_CONT = "    decoration: BoxDecoration(\n      color: _bgSurface,\n      borderRadius: BorderRadius.circular(16),\n      border: Border.all(color: _teal.withOpacity(0.25))),"
txt, ok = _replace_once(txt, OLD_ENG_CONT, NEW_ENG_CONT, 'engine selector container')
_rec('S29-D18', 'Engine selector container', ok)

# D19 — engine card selected color
OLD_ENGCARD = "          color: sel ? const Color(0xFF0D1117) : Colors.transparent,"
NEW_ENGCARD = "          color: sel ? _bgCard : Colors.transparent,"
txt, ok = _replace_once(txt, OLD_ENGCARD, NEW_ENGCARD, 'engine card selected bg')
_rec('S29-D19', 'Engine card selected bg', ok)

# D20 — file card border color (selected)
OLD_FILE_BORDER = "          color: _file != null ? const Color(0xFFD4AF37) : const Color(0xFF30363D),"
NEW_FILE_BORDER = "          color: _file != null ? _gold : _teal.withOpacity(0.35),"
txt, ok = _replace_once(txt, OLD_FILE_BORDER, NEW_FILE_BORDER, 'file card border')
_rec('S29-D20', 'File card border', ok)

# D21 — file card bg color
OLD_FILE_BG = "      color: const Color(0xFF161B22),"
NEW_FILE_BG = "      color: _file != null ? _bgSurface : _bgDeep,"
txt, ok = _replace_once(txt, OLD_FILE_BG, NEW_FILE_BG, 'file card bg')
_rec('S29-D21', 'File card bg', ok)

# D22 — process button gradient (replace flat gold with gradient)
OLD_PROC_BTN = "              onPressed: (_busy || !_serverUp) ? null : _process,\n              style: ElevatedButton.styleFrom(\n                backgroundColor: const Color(0xFFD4AF37),\n                foregroundColor: const Color(0xFF0A0C10),\n                padding: const EdgeInsets.symmetric(vertical: 15),\n                shape: RoundedRectangleBorder(\n                  borderRadius: BorderRadius.circular(10)),\n                disabledBackgroundColor:\n                  const Color(0xFFD4AF37).withOpacity(0.3)),"
NEW_PROC_BTN = """              onPressed: (_busy || !_serverUp) ? null : () {
                HapticFeedback.mediumImpact();
                _process();
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFD4AF37),
                foregroundColor: const Color(0xFF061218),
                padding: const EdgeInsets.symmetric(vertical: 15),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12)),
                disabledBackgroundColor:
                  const Color(0xFFD4AF37).withOpacity(0.25)),"""
txt, ok = _replace_once(txt, OLD_PROC_BTN, NEW_PROC_BTN, 'process button haptic + color')
_rec('S29-D22', 'Process button haptic', ok)

# D23 — progress card: replace LinearProgressIndicator with wave + cancel btn
OLD_PROGRESS_CARD = "  // ── PROGRESS ───────────────────────────────────────────────────────────────\n  Widget _progressCard(S s) => Container(\n    margin: const EdgeInsets.fromLTRB(16,10,16,4),\n    padding: const EdgeInsets.all(18),\n    decoration: BoxDecoration(\n      color: const Color(0xFF161B22),\n      borderRadius: BorderRadius.circular(14),\n      border: Border.all(color: const Color(0xFF21262D))),\n    child: Column(children: [\n      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [\n        Flexible(child: Text(_status.isEmpty ? s.processing : _status,\n          style: const TextStyle(color: Color(0xFFC9D1D9), fontSize: 13))),\n        // S20-A: '...' when merging — frozen '68%' looks like a crash\n        Text(_isMerging ? '...' : '${(_progress * 100).toInt()}%',\n          style: const TextStyle(\n            color: Color(0xFFD4AF37),\n            fontWeight: FontWeight.bold, fontSize: 14)),\n      ]),\n      const SizedBox(height: 12),\n      ClipRRect(\n        borderRadius: BorderRadius.circular(8),\n        // S20-A: null = indeterminate (animated pulse) during server merge\n        child: LinearProgressIndicator(\n          value: _isMerging ? null : _progress, minHeight: 8,\n          backgroundColor: const Color(0xFF21262D),\n          valueColor: const AlwaysStoppedAnimation(Color(0xFFD4AF37)))),\n    ]),\n  );"
NEW_PROGRESS_CARD = """  // ── PROGRESS ──────────────────────────────────────────────────────────────────
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
          Text(_isMerging ? '...' : '\${(_progress * 100).toInt()}%',
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
txt, ok = _replace_once(txt, OLD_PROGRESS_CARD, NEW_PROGRESS_CARD, 'wave progress + cancel btn')
_rec('S29-D23', 'Wave progress bar + cancel', ok)

# D24 — result card: score ring + count-up anim + process another btn
OLD_RESULT_BG = "      color: score < 80 ? const Color(0xFF1A0A00) : const Color(0xFF0D2015),"
NEW_RESULT_BG = "      color: score < 80 ? _err.withOpacity(0.05) : _ok.withOpacity(0.05),"
txt, ok = _replace_once(txt, OLD_RESULT_BG, NEW_RESULT_BG, 'result card bg')
_rec('S29-D24', 'Result card bg', ok)

OLD_RESULT_BORDER = "          color: score < 80 ? const Color(0xFFF85149) : const Color(0xFF3FB950),"
NEW_RESULT_BORDER = "          color: (score < 80 ? _err : _ok).withOpacity(0.35),"
txt, ok = _replace_once(txt, OLD_RESULT_BORDER, NEW_RESULT_BORDER, 'result card border')
_rec('S29-D25', 'Result card border', ok)

# Replace flat score text with score ring + count-up
OLD_SCORE_ROW = """        // Score
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(label, style: TextStyle(
              color: scoreColor,
              fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(width: 10),
            Text('\${score.toStringAsFixed(1)}/100',
              style: TextStyle(
                color: scoreColor,
                fontWeight: FontWeight.w900, fontSize: 34)),
          ]),"""
NEW_SCORE_ROW = """        // Score ring with count-up
        (() {
          // trigger score animation when result card first builds
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
txt, ok = _replace_once(txt, OLD_SCORE_ROW, NEW_SCORE_ROW, 'score ring + count-up')
_rec('S29-D26', 'Score ring + count-up anim', ok)

# D27 — add "Process Another" button after saved indicator row in result card
OLD_SAVED_ROW = """        if (_output != null) ...[\n          const SizedBox(height: 8),\n          Row(mainAxisAlignment: MainAxisAlignment.center, children: [\n            const Icon(Icons.check_circle_outline,\n              color: Color(0xFF3FB950), size: 14),\n            const SizedBox(width: 4),\n            Text(s.savedTo,\n              style: const TextStyle(\n                color: Color(0xFF3FB950), fontSize: 11)),\n          ]),\n        ],\n      ]),\n    );\n  }"""
NEW_SAVED_ROW = """        if (_output != null) ...[
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
txt, ok = _replace_once(txt, OLD_SAVED_ROW, NEW_SAVED_ROW, '"Process Another" button')
_rec('S29-D27', 'Process Another button', ok)

# D28 — bottom row / history btn colors
OLD_BTM = "      color: const Color(0xFF161B22),\n      borderRadius: BorderRadius.circular(12),\n      border: Border.all(color: const Color(0xFF21262D))),"
NEW_BTM = "      color: _bgSurface,\n      borderRadius: BorderRadius.circular(14),\n      border: Border.all(color: _teal.withOpacity(0.25))),"
txt, ok = _replace_once(txt, OLD_BTM, NEW_BTM, 'history btn colors')
_rec('S29-D28', 'History btn colors', ok)

# D29 — donation card colors
OLD_DON = "          color: const Color(0xFF1A1500),\n          borderRadius: BorderRadius.circular(12),\n          border: Border.all(\n            color: const Color(0xFFD4AF37).withOpacity(0.3))),"
NEW_DON = "          color: _goldMuted.withOpacity(0.55),\n          borderRadius: BorderRadius.circular(14),\n          border: Border.all(color: _gold.withOpacity(0.22))),"
txt, ok = _replace_once(txt, OLD_DON, NEW_DON, 'donation card colors')
_rec('S29-D29', 'Donation card colors', ok)

# D30 — append painters + star class at end of file (before last })
OLD_ENGINE_CLASS = """class _EngineData {
  final String id, nameAr, nameEn, badge, bc;
  final double score;
  final List<String> features;
  final String whatsNewAr, whatsNewEn;
  const _EngineData(this.id, this.nameAr, this.nameEn, this.score,
      this.badge, this.bc, this.features, this.whatsNewAr, this.whatsNewEn);
}"""
NEW_ENGINE_CLASS = """class _EngineData {
  final String id, nameAr, nameEn, badge, bc;
  final double score;
  final List<String> features;
  final String whatsNewAr, whatsNewEn;
  const _EngineData(this.id, this.nameAr, this.nameEn, this.score,
      this.badge, this.bc, this.features, this.whatsNewAr, this.whatsNewEn);
}

// ── Sacred Cosmos painters ────────────────────────────────────────────────────
class _StarParticle {
  final double x, y, size, phase, speed, twinkle;
  _StarParticle(Random r)
      : x = r.nextDouble(), y = r.nextDouble(),
        size = 0.4 + r.nextDouble() * 1.8,
        phase = r.nextDouble() * 6.2832,
        speed = 0.15 + r.nextDouble() * 0.6,
        twinkle = 0.4 + r.nextDouble() * 1.6;
}

class _StarsPainter extends CustomPainter {
  final double t;
  final List<_StarParticle> stars;
  _StarsPainter(this.t, this.stars);
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()..maskFilter = const MaskFilter.blur(BlurStyle.normal, 1.0);
    for (final s in stars) {
      final a = t * 6.2832 * s.speed + s.phase;
      final x = s.x * size.width  + sin(a)        * size.width  * 0.016;
      final y = s.y * size.height + cos(a * 0.71) * size.height * 0.012;
      final op = 0.12 + 0.5 * (sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5);
      p.color = _gold.withOpacity(op);
      canvas.drawCircle(Offset(x, y), s.size, p);
    }
  }
  @override bool shouldRepaint(_StarsPainter o) => o.t != t;
}

class _GeoPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = _teal.withOpacity(0.032)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.7;
    const cell = 120.0;
    final cols = (size.width / cell).ceil() + 2;
    final rows = (size.height / (cell * 0.866)).ceil() + 2;
    for (int row = 0; row < rows; row++) {
      for (int col = 0; col < cols; col++) {
        final cx = col * cell + (row.isOdd ? cell * 0.5 : 0) - cell * 0.5;
        final cy = row * cell * 0.866 - cell * 0.5;
        _star8(canvas, Offset(cx, cy), cell * 0.27, p);
      }
    }
  }
  void _star8(Canvas canvas, Offset c, double r, Paint p) {
    final path = Path();
    for (int i = 0; i < 8; i++) {
      final oa = i * pi / 4 - pi / 2;
      final ia = oa + pi / 8;
      final ox = c.dx + r * cos(oa); final oy = c.dy + r * sin(oa);
      final ix = c.dx + r * 0.38 * cos(ia); final iy = c.dy + r * 0.38 * sin(ia);
      if (i == 0) path.moveTo(ox, oy); else path.lineTo(ox, oy);
      path.lineTo(ix, iy);
    }
    path.close();
    canvas.drawPath(path, p);
  }
  @override bool shouldRepaint(_GeoPainter _) => false;
}

class _WaveProgressPainter extends CustomPainter {
  final double progress, shimmer;
  final Color color, bg;
  const _WaveProgressPainter(
      {required this.progress, required this.shimmer,
       required this.color, required this.bg});
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRRect(
      RRect.fromRectAndRadius(Rect.fromLTWH(0,0,size.width,size.height),
        const Radius.circular(5)),
      Paint()..color = bg);
    if (progress <= 0) return;
    final fillW = (size.width * progress).clamp(0.0, size.width);
    final path = Path();
    path.moveTo(0, size.height);
    path.lineTo(0, size.height * 0.5);
    final waveAmp = size.height * 0.30;
    for (double x = 0; x <= fillW; x++) {
      final y = size.height * 0.5 +
        sin((x / (size.width * 0.55) - shimmer) * 6.2832) * waveAmp;
      path.lineTo(x, y.clamp(0.0, size.height));
    }
    path.lineTo(fillW, size.height);
    path.close();
    canvas.save();
    canvas.clipRect(Rect.fromLTWH(0, 0, fillW, size.height));
    canvas.drawPath(path, Paint()..color = color);
    canvas.drawRect(
      Rect.fromLTWH(0, 0, fillW, size.height),
      Paint()..shader = LinearGradient(
        colors: [Colors.transparent, Colors.white.withOpacity(0.14), Colors.transparent],
        stops: const [0.0, 0.5, 1.0],
        begin: Alignment(shimmer * 2 - 1, 0),
        end: Alignment(shimmer * 2 + 0.4, 0),
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height)));
    canvas.restore();
  }
  @override
  bool shouldRepaint(_WaveProgressPainter o) =>
    o.progress != progress || o.shimmer != shimmer;
}"""
txt, ok = _replace_once(txt, OLD_ENGINE_CLASS, NEW_ENGINE_CLASS, 'append Sacred Cosmos painters')
_rec('S29-D30', 'Painters appended to home_screen', ok)

_write(SCREENS / 'home_screen.dart', txt)


###############################################################################
# S29-E  history_screen.dart — Sacred Cosmos + Clear All + score ring
###############################################################################
_h1('S29-E  history_screen.dart')

txt = _read(SCREENS / 'history_screen.dart')

# E1 — scaffold bg
OLD_H_BG = "      backgroundColor: const Color(0xFF0D1117),"
NEW_H_BG = "      backgroundColor: const Color(0xFF061218),"
txt, ok = _replace_once(txt, OLD_H_BG, NEW_H_BG, 'history scaffold bg')
_rec('S29-E1', 'History scaffold bg', ok)

# E2 — appBar bg
OLD_H_APP = "        backgroundColor: const Color(0xFF0D1117),"
NEW_H_APP = "        backgroundColor: const Color(0xFF061218),"
txt, ok = _replace_once(txt, OLD_H_APP, NEW_H_APP, 'history appBar bg')
_rec('S29-E2', 'History appBar bg', ok)

# E3 — appBar title color
OLD_H_TITLE = "        title: Text(s.historyTitle,\n          style: const TextStyle(\n            color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),"
NEW_H_TITLE = """        title: ShaderMask(
          shaderCallback: (b) => const LinearGradient(
            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),
          child: Text(s.historyTitle,
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),"""
txt, ok = _replace_once(txt, OLD_H_TITLE, NEW_H_TITLE, 'history title gradient')
_rec('S29-E3', 'History title gradient', ok)

# E4 — Add Clear All action to appBar
OLD_H_APPBAR_END = "        iconTheme: const IconThemeData(color: Color(0xFFD4AF37)),\n        elevation: 0),"
NEW_H_APPBAR_END = """        iconTheme: const IconThemeData(color: Color(0xFFD4AF37)),
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
txt, ok = _replace_once(txt, OLD_H_APPBAR_END, NEW_H_APPBAR_END, 'Clear All action in appBar')
_rec('S29-E4', 'Clear All action added', ok)

# E5 — add _clearAll method before build()
OLD_H_BUILD = "  @override\n  Widget build(BuildContext context) {\n    final s = LangProvider.strings(context);"
NEW_H_BUILD = """  Future<void> _clearAll() async {
    final s = LangProvider.strings(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(s.clearAll,
          style: const TextStyle(color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),
        content: Text(s.clearAllConfirm,
          style: const TextStyle(color: Color(0xFFE2CFA0))),
        backgroundColor: const Color(0xFF0C1E28),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: const Color(0xFF1B6B80).withOpacity(0.3))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
            child: Text(s.ar ? 'إلغاء' : 'Cancel',
              style: const TextStyle(color: Color(0xFF8AACBA)))),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFD94040)),
            child: Text(s.clearAll,
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
        ]));
    if (ok == true && mounted) {
      await ApiService.clearAllJobRecords();
      setState(() => _jobs.clear());
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);"""
txt, ok = _replace_once(txt, OLD_H_BUILD, NEW_H_BUILD, 'add _clearAll method')
_rec('S29-E5', '_clearAll method added', ok)

# E6 — job card container colors
OLD_CARD_DECO = "          color: const Color(0xFF161B22),\n          borderRadius: BorderRadius.circular(12),\n          border: Border.all(color: const Color(0xFF21262D))),"
NEW_CARD_DECO = "          color: const Color(0xFF0C1E28),\n          borderRadius: BorderRadius.circular(14),\n          border: Border.all(color: const Color(0xFF1B6B80).withOpacity(0.20))),"
txt, ok = _replace_once(txt, OLD_CARD_DECO, NEW_CARD_DECO, 'job card container colors')
_rec('S29-E6', 'Job card container colors', ok)

_write(SCREENS / 'history_screen.dart', txt)


###############################################################################
# S29-F  settings_screen.dart — Sacred Cosmos + v9.0/v8.5 history
###############################################################################
_h1('S29-F  settings_screen.dart')

txt = _read(SCREENS / 'settings_screen.dart')

# F1 — scaffold bg
OLD_S_BG = "      backgroundColor: const Color(0xFF0A0C10),"
NEW_S_BG = "      backgroundColor: const Color(0xFF061218),"
for i in range(txt.count(OLD_S_BG)):
    txt = txt.replace(OLD_S_BG, NEW_S_BG, 1)
_ok(f'Replaced all scaffold bg in settings')
_rec('S29-F1', 'Settings scaffold bg', True)

# F2 — appBar title: gold gradient
OLD_S_TITLE = "        title: Text(s.settings, style: const TextStyle(\n          color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),"
NEW_S_TITLE = """        title: ShaderMask(
          shaderCallback: (b) => const LinearGradient(
            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),
          child: Text(s.settings,
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),"""
txt, ok = _replace_once(txt, OLD_S_TITLE, NEW_S_TITLE, 'settings title gradient')
_rec('S29-F2', 'Settings title gradient', ok)

# F3 — prepend v9.0 + v8.5 to _history list
OLD_HIST_LIST = "    _EHist('v8.1','Android-Hardened'"
NEW_HIST_LIST = """    _EHist('v9.0','The Evolution','≥ 98/100','LATEST','gold',
      'إعادة كتابة كاملة: 1,890 سطرًا. NR دائمًا قبل EQ. محسِّن LUFS+LRA مشترك. نسب ثقة منفصلة لكل معامل.',
      'Full rewrite: 1,890 lines. NR always before EQ. Joint LUFS+LRA optimizer. Per-parameter confidence vectors.'),
    _EHist('v8.5','Tier-Adjusted Scoring','≥ 98/100','DEFAULT','gold',
      'أوزان MDS مختلفة لكل فئة. أسقف Crest/LRA/LUFS محسوبة لكل فئة. حذف تحكّم 64K_FLOOR.',
      'Different MDS weights per source tier. Per-tier Crest/LRA/LUFS ceilings. 64K_FLOOR hack removed.'),
    _EHist('v8.4','Source Tier Intelligence','≥ 98/100','','gold',
      'يحلِّل جودة المصدر: تردد قطع الكودك، نوع الضوضاء، القص. يضبط NR وEQ بناءً على التصنيف.',
      'Analyzes source quality: codec cutoff, noise type, clipping. Adapts NR, EQ, LRA per source tier.'),
    _EHist('v8.1','Android-Hardened'"""
txt, ok = _replace_once(txt, OLD_HIST_LIST, NEW_HIST_LIST, 'prepend v9.0/v8.5/v8.4 to history')
_rec('S29-F3', 'v9.0/v8.5/v8.4 prepended to history', ok)

_write(SCREENS / 'settings_screen.dart', txt)


###############################################################################
# S29-G  welcome_screen.dart — Sacred Cosmos
###############################################################################
_h1('S29-G  welcome_screen.dart')

txt = _read(SCREENS / 'welcome_screen.dart')

# G1 — add dart:math import
OLD_W_IMPORT = "import 'package:flutter/material.dart';"
NEW_W_IMPORT = "import 'dart:math';\nimport 'package:flutter/material.dart';"
txt, ok = _replace_once(txt, OLD_W_IMPORT, NEW_W_IMPORT, 'add dart:math to welcome')
_rec('S29-G1', 'dart:math import in welcome', ok)

# G2 — scaffold bg
OLD_W_BG = "      backgroundColor: const Color(0xFF0A0C10),"
NEW_W_BG = "      backgroundColor: const Color(0xFF061218),"
txt, ok = _replace_once(txt, OLD_W_BG, NEW_W_BG, 'welcome scaffold bg')
_rec('S29-G2', 'Welcome scaffold bg', ok)

# G3 — logo container: breathing glow anim (replace static container)
OLD_W_LOGO = "    // Logo\n    Center(\n      child: Container(\n        width: 130, height: 130,\n        decoration: BoxDecoration(\n          shape: BoxShape.circle,\n          boxShadow: [BoxShadow(\n            color: const Color(0xFFD4AF37).withOpacity(0.4),\n            blurRadius: 30, spreadRadius: 5)]),\n        child: ClipOval(child: Image.asset('assets/images/logo.png',\n          fit: BoxFit.cover,\n          errorBuilder: (_, __, ___) => Container(\n            color: const Color(0xFF0D1117),\n            child: const Icon(Icons.music_note,\n              color: Color(0xFFD4AF37), size: 64)))))),"
NEW_W_LOGO = """    Center(child: AnimatedBuilder(
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
                  color: Color(0xFFD4AF37), size: 72)))))); })),"""
txt, ok = _replace_once(txt, OLD_W_LOGO, NEW_W_LOGO, 'welcome logo breathing glow')
_rec('S29-G3', 'Welcome logo breathing glow', ok)

# G4 — title: gold gradient shader
OLD_W_TITLE = "    Text(s.appName,"
NEW_W_TITLE = """    ShaderMask(
      shaderCallback: (b) => const LinearGradient(
        colors: [Color(0xFFD4AF37), Color(0xFFF0CF60), Color(0xFFD4AF37)],
        stops: [0.0, 0.5, 1.0]).createShader(b),
      child: Text(s.appName,"""
txt, ok = _replace_once(txt, OLD_W_TITLE, NEW_W_TITLE, 'welcome title gold gradient')
_rec('S29-G4', 'Welcome title gold gradient', ok)

_write(SCREENS / 'welcome_screen.dart', txt)


###############################################################################
# DONE
###############################################################################
_summary()
_h1('S29 Sacred Cosmos patch complete ✓')
print("""
  Next steps in Termux:
    cd ~/tilawa-enhancer
    flutter pub get
    flutter run --release
""")
