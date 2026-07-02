#!/usr/bin/env python3
"""
patch_s173.py — S173: Safaa v4 S167 engine + Standard/Aggressive mode toggle

Changes:
  E1  assets/engines/engine_safaa_v4.py   → replace with S167
        (windNR stage, soft RL-16 band blend, 4-class DF3, 3-stage tailNR, 2-pass JALAA)
  E2  LocalEngineRunner.kt                → accept `aggressive` bool → append --aggressive
  E3  lib/services/local_engine_service.dart → add `aggressive` param to runEngine()
  E4  lib/screens/home_screen.dart        → _aggressive state + toggle widget + pass to runEngine
"""

import os, sys, shutil, ast
from pathlib import Path

REPO = Path(__file__).parent  # run from repo root

def fail(msg):
    print(f'  FAIL  {msg}'); sys.exit(1)

def patch(path, old, new, tag):
    p = Path(path)
    if not p.exists(): fail(f'{path} not found')
    src = p.read_text(encoding='utf-8')
    if new.strip() in src:
        print(f'  SKIP  {tag} (already applied)'); return
    if old not in src:
        fail(f'{tag}: anchor not found in {path}')
    p.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

# ── idempotency guard ─────────────────────────────────────────────────────────
STAMP = Path('.patch_s173_done')
if STAMP.exists():
    print('patch_s173: already applied — delete .patch_s173_done to re-run'); sys.exit(0)

print('\n── S173: Safaa S167 + Aggressive Mode ──────────────────────────────────────')

# ════════════════════════════════════════════════════════════════════════════════
# E1 — Replace engine_safaa_v4.py with S167 version
# ════════════════════════════════════════════════════════════════════════════════
SRC_ENGINE = Path('engine_safaa_v4_S167.py')     # expected in repo root
DST_ENGINE = Path('assets/engines/engine_safaa_v4.py')

if not SRC_ENGINE.exists():
    # Also check Downloads
    alt = Path('/sdcard/Download/engine_safaa_v4_S167.py')
    if alt.exists():
        SRC_ENGINE = alt
    else:
        fail('engine_safaa_v4_S167.py not found — copy it to repo root or /sdcard/Download/')

DST_ENGINE.parent.mkdir(parents=True, exist_ok=True)
shutil.copy2(SRC_ENGINE, DST_ENGINE)
print(f'  OK    E1: engine_safaa_v4.py replaced with S167 ({DST_ENGINE.stat().st_size:,} bytes)')

# Quick AST check
try:
    ast.parse(DST_ENGINE.read_text(encoding='utf-8'))
    print('  OK    E1: AST valid')
except SyntaxError as e:
    fail(f'E1: AST error in engine: {e}')

# ════════════════════════════════════════════════════════════════════════════════
# E2 — LocalEngineRunner.kt: accept `aggressive` + append --aggressive to cmd
# ════════════════════════════════════════════════════════════════════════════════
KT = Path('android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt')

# E2a — pass aggressive from method call args
patch(KT,
    '''                    scope.launch {
                        runEngine(a["engineId"] as String, a["inputPath"] as String)
                    }''',
    '''                    scope.launch {
                        runEngine(a["engineId"] as String, a["inputPath"] as String,
                            (a["aggressive"] as? Boolean) ?: false)  // S173
                    }''',
    'E2a: runEngine dispatch passes aggressive')

# E2b — function signature
patch(KT,
    'private suspend fun runEngine(engineId: String, inputPath: String) =',
    'private suspend fun runEngine(engineId: String, inputPath: String,\n        aggressive: Boolean = false) =  // S173',
    'E2b: runEngine signature adds aggressive param')

# E2c — append --aggressive flag after cmd list is built
# Insert after the ref-audio block (F8 guard), before ProcessBuilder
patch(KT,
    '            val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {',
    '''            // S173: --aggressive flag for الصفاء v4 only
            if (script.startsWith("engine_safaa_v4") && aggressive) {
                cmd += listOf("--aggressive")
            }

            val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {''',
    'E2c: append --aggressive to cmd when set')

# ════════════════════════════════════════════════════════════════════════════════
# E3 — local_engine_service.dart: add aggressive param to runEngine()
# ════════════════════════════════════════════════════════════════════════════════
DART = Path('lib/services/local_engine_service.dart')

# E3a — function signature
patch(DART,
    '''  static Stream<Map<String, dynamic>> runEngine({  // S157
    required String engineId,
    required String inputPath,
  }) {''',
    '''  static Stream<Map<String, dynamic>> runEngine({  // S157
    required String engineId,
    required String inputPath,
    bool aggressive = false,  // S173: standard / aggressive mode
  }) {''',
    'E3a: runEngine signature adds aggressive param')

# E3b — pass aggressive in invokeMethod payload
patch(DART,
    """    _ch.invokeMethod('runEngine', {
      'engineId':  engineId,
      'inputPath': inputPath,
    }).catchError""",
    """    _ch.invokeMethod('runEngine', {
      'engineId':   engineId,
      'inputPath':  inputPath,
      'aggressive': aggressive,  // S173
    }).catchError""",
    'E3b: invokeMethod payload includes aggressive')

# ════════════════════════════════════════════════════════════════════════════════
# E4 — home_screen.dart: state var + toggle widget + pass to runEngine
# ════════════════════════════════════════════════════════════════════════════════
HOME = Path('lib/screens/home_screen.dart')

# E4a — add _aggressive state variable
patch(HOME,
    "  bool   _localMode  = false;  // S65: run via proot (offline)\n"
    "  bool   _localReady = false;  // S65: setup confirmed complete\n"
    "  String _localMsg   = '';     // S65: last line from engine stdout",
    "  bool   _localMode  = false;  // S65: run via proot (offline)\n"
    "  bool   _localReady = false;  // S65: setup confirmed complete\n"
    "  bool   _aggressive = false;  // S173: safaa standard / aggressive mode\n"
    "  String _localMsg   = '';     // S65: last line from engine stdout",
    'E4a: _aggressive state variable')

# E4b — pass aggressive to runEngine call
patch(HOME,
    "    await for (final ev in LocalEngineService.runEngine(\n"
    "      engineId:  _engine,\n"
    "      inputPath: _file!.path,\n"
    "    )) {",
    "    await for (final ev in LocalEngineService.runEngine(\n"
    "      engineId:   _engine,\n"
    "      inputPath:  _file!.path,\n"
    "      aggressive: _aggressive,  // S173\n"
    "    )) {",
    'E4b: pass aggressive to runEngine')

# E4c — insert aggressive toggle into sliver list (after _localModeToggle)
patch(HOME,
    "            SliverToBoxAdapter(child: _localModeToggle(s)), // S65",
    "            SliverToBoxAdapter(child: _localModeToggle(s)), // S65\n"
    "            if (_localMode && _localReady && _engine == 'v11.0')\n"
    "              SliverToBoxAdapter(child: _aggressiveModeToggle(s)), // S173",
    'E4c: aggressive toggle in sliver list')

# E4d — add _aggressiveModeToggle widget method (after _localModeToggle closing brace)
_AGG_WIDGET = '''
  // S173: Standard / Aggressive mode toggle — shown only for الصفاء (v11.0) in local mode
  Widget _aggressiveModeToggle(S s) {
    const gold    = Color(0xFFC8A048);
    const orange  = Color(0xFFE07040);
    const jade    = Color(0xFF0D2B22);
    const burnedBg = Color(0xFF1E0E04);
    const textB   = Color(0xFF8AACBA);
    final isAggr  = _aggressive;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 250),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: isAggr
              ? burnedBg.withValues(alpha: 0.90)
              : jade.withValues(alpha: 0.55),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isAggr
                ? orange.withValues(alpha: 0.55)
                : gold.withValues(alpha: 0.25),
            width: 1.0)),
        child: Row(children: [
          Icon(
            isAggr ? Icons.bolt_rounded : Icons.tune_rounded,
            color: isAggr ? orange : gold, size: 18),
          const SizedBox(width: 10),
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                isAggr
                    ? (s.ar ? 'الوضع الهجومي — تنظيف أعمق' : 'Aggressive — deeper cleaning')
                    : (s.ar ? 'الوضع القياسي — معالجة متوازنة' : 'Standard — balanced processing'),
                style: TextStyle(
                  color: isAggr ? orange : gold,
                  fontSize: 12, fontWeight: FontWeight.w700)),
              Text(
                isAggr
                    ? (s.ar
                        ? 'تضخيم ×٤ — حدود DF3 مرتفعة — JALAA أقوى'
                        : '4× volume boost · wider DF3 caps · stronger JALAA')
                    : (s.ar
                        ? 'تضخيم ×١.٨٥ — حماية كاملة للتجويد'
                        : '1.85× boost · full Tajweed protection'),
                style: const TextStyle(color: Color(0xFF3D5A65), fontSize: 10)),
            ])),
          Switch(
            value: isAggr,
            onChanged: _busy ? null : (v) {
              setState(() => _aggressive = v);
            },
            activeColor: orange,
            inactiveThumbColor: gold.withValues(alpha: 0.5),
            inactiveTrackColor: const Color(0xFF1A2733)),
        ]),
      ),
    );
  }
'''

home_src = HOME.read_text(encoding='utf-8')
ANCHOR = '  Widget _serverBanner(S s) {'
if '_aggressiveModeToggle' in home_src:
    print('  SKIP  E4d: _aggressiveModeToggle already exists')
elif ANCHOR not in home_src:
    fail(f'E4d: anchor "_serverBanner" not found in home_screen.dart')
else:
    HOME.write_text(home_src.replace(ANCHOR, _AGG_WIDGET + '  ' + ANCHOR[2:], 1), encoding='utf-8')
    print('  OK    E4d: _aggressiveModeToggle widget added')

# ── stamp ─────────────────────────────────────────────────────────────────────
STAMP.write_text('S173\n')
print('\n✅  patch_s173 done')
print('   git add assets/engines/engine_safaa_v4.py \\')
print('       android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt \\')
print('       lib/services/local_engine_service.dart \\')
print('       lib/screens/home_screen.dart')
print('   git commit -m "S173: E1 Safaa S167 engine, E2-E4 standard/aggressive mode toggle"')
print('   git push')
