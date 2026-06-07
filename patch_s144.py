#!/usr/bin/env python3
"""
patch_s144.py — 3 bugs found in S144 deep scan
================================================

Bug-17 [CRITICAL — A/B player silently fails after _reDownload() updates _output]
  S143 Bug-15 made _reDownload() update _output from a cacheDir path to a
  content://media/downloads/... URI. The A/B player uses DeviceFileSource(src.path)
  for the B (enhanced) track. Android's MediaPlayer.setDataSource(String) — which
  DeviceFileSource maps to in audioplayers 6.x — rejects content:// URIs. It only
  accepts absolute filesystem paths and HTTP/RTSP URLs. After every local engine run
  (where _reDownload() auto-fires), the A/B enhanced track silently fails to load.

  Fix: store the original cacheDir path in a new _abOutputFile field. Set it in
  the ev['done'] branch of _processLocal() alongside _output. Use
  (_abOutputFile ?? _output) for the B track in both A/B methods so the player
  always gets a real filesystem path. Clear it in _resetForNewFile().

Bug-18 [LOGIC — _resetForNewFile() doesn't stop A/B player or reset A/B state]
  When user taps "Process Another File", _resetForNewFile() hides the A/B card
  (via _output=null) but never calls _abPlayer.stop(). The previous track keeps
  playing in the background. _abEverPlayed, _abPos, _abDur are NOT reset.
  After new processing completes and the user taps A/B Play:
    !_abEverPlayed  → false (was true from old session)
    _abPos <= 0.1   → false (onPositionChanged kept updating from old track)
    _abPos >= _abDur - 0.1 → false
  All three conditions false → falls through to resume() on a player not loaded
  with the new file. Silent failure / wrong audio plays.

  Fix: stop the player and reset all A/B state in _resetForNewFile().

Bug-19 [LOW — dead 522KB asset engine_isteidad_v12.py inflates APK]
  assets/engines/engine_isteidad_v12.py (522,871 bytes) is present in the assets
  folder but is NOT in extractEngines(), NOT in the runEngine() engine map, and NOT
  referenced by any _EngineData. No code path touches it. It inflates the APK by
  ~523KB and is bundled into every install.

  Fix: manual deletion — run once in Termux:
    rm ~/tilawa-enhancer/assets/engines/engine_isteidad_v12.py
  Cannot be done via patch_android.py (it is a static asset, not generated).
  This patch prints a reminder instead.
"""
from pathlib import Path
from datetime import datetime
import sys

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'

_log = []
def ok(l):  print(f'  OK  {l}'); _log.append(('OK', l))
def xx(l):  print(f'  XX  NOT FOUND — {l}'); _log.append(('XX', l)); sys.exit(1)

def rep(path, old, new, lbl):
    t = path.read_text(encoding='utf-8')
    if old in t:
        path.write_text(t.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else:
        xx(lbl)

print(f'\n{"="*60}\n  S144  {datetime.now().strftime("%H:%M:%S")}\n{"="*60}')

# ── Bug-17a: add _abOutputFile field alongside _output ────────────────────────
print(f'\n{"="*60}\n  Bug-17a: add _abOutputFile field\n{"="*60}')
rep(HS,
    '  File?   _output;\n'
    '  // S104: A/B comparison player',

    '  File?   _output;\n'
    '  File?   _abOutputFile; // S144: cacheDir path for A/B — unaffected by _reDownload()\n'
    '  // S104: A/B comparison player',
    'Bug-17a fixed: _abOutputFile field added')

# ── Bug-17b: set _abOutputFile in _processLocal() done branch ─────────────────
print(f'\n{"="*60}\n  Bug-17b: set _abOutputFile in _processLocal done branch\n{"="*60}')
rep(HS,
    '        final _outPath = ev[\'path\'] as String? ?? \'\'; // S140: null-safe\n'
    '        setState(() { // S92: ALL result state inside setState\n'
    '          _busy = false; _progress = 0;\n'
    '          _status = \'Local engine complete\';\n'
    '          _output = _outPath.isNotEmpty ? File(_outPath) : null;\n'
    '          _result = resultData;\n'
    '        });',

    '        final _outPath = ev[\'path\'] as String? ?? \'\'; // S140: null-safe\n'
    '        _abOutputFile = _outPath.isNotEmpty ? File(_outPath) : null; // S144: preserve cacheDir path for A/B\n'
    '        setState(() { // S92: ALL result state inside setState\n'
    '          _busy = false; _progress = 0;\n'
    '          _status = \'Local engine complete\';\n'
    '          _output = _outPath.isNotEmpty ? File(_outPath) : null;\n'
    '          _result = resultData;\n'
    '        });',
    'Bug-17b fixed: _abOutputFile set to cacheDir path in done branch')

# ── Bug-17c: use _abOutputFile in _abToggleTrack() ────────────────────────────
print(f'\n{"="*60}\n  Bug-17c: use _abOutputFile in _abToggleTrack\n{"="*60}')
rep(HS,
    '    setState(() { _abIsB = !_abIsB; _abPos = 0; _abDur = 1.0; }); // S138: reset dur\n'
    '    final src = _abIsB ? _output : _file;',

    '    setState(() { _abIsB = !_abIsB; _abPos = 0; _abDur = 1.0; }); // S138: reset dur\n'
    '    final src = _abIsB ? (_abOutputFile ?? _output) : _file; // S144: use cacheDir path — content:// fails DeviceFileSource',
    'Bug-17c fixed: _abToggleTrack uses _abOutputFile for B track')

# ── Bug-17d: use _abOutputFile in _abTogglePlay() ─────────────────────────────
print(f'\n{"="*60}\n  Bug-17d: use _abOutputFile in _abTogglePlay\n{"="*60}')
rep(HS,
    '      final src = _abIsB ? _output : _file;\n'
    '      if (src == null) return;\n'
    '      if (!_abEverPlayed || _abPos <= 0.1 || _abPos >= _abDur - 0.1) { // S142: also replay when pos reset to 0',

    '      final src = _abIsB ? (_abOutputFile ?? _output) : _file; // S144: use cacheDir path — content:// fails DeviceFileSource\n'
    '      if (src == null) return;\n'
    '      if (!_abEverPlayed || _abPos <= 0.1 || _abPos >= _abDur - 0.1) { // S142: also replay when pos reset to 0',
    'Bug-17d fixed: _abTogglePlay uses _abOutputFile for B track')

# ── Bug-18: _resetForNewFile — stop player and reset A/B state ────────────────
print(f'\n{"="*60}\n  Bug-18: _resetForNewFile — stop A/B player + reset A/B state\n{"="*60}')
rep(HS,
    '  void _resetForNewFile() {\n'
    '    setState(() {\n'
    '      _file = null; _result = null; _output = null;\n'
    '      _progress = 0; _status = \'\';\n'
    '      _jobId = null; _busy = false;\n'
    '      _isMerging = false; _sizeLabel = \'\';\n'
    '      _isLarge = false; _fileBytes = 0;\n'
    '    });\n'
    '    ApiService.clearJobId(); // S57\n'
    '  }',

    '  void _resetForNewFile() {\n'
    '    _abPlayer.stop(); // S144: stop audio when picking new file\n'
    '    setState(() {\n'
    '      _abEverPlayed = false; // S144: reset A/B state for clean start\n'
    '      _abPlaying    = false;\n'
    '      _abPos        = 0.0;\n'
    '      _abDur        = 1.0;\n'
    '      _abIsB        = true;\n'
    '      _abOutputFile = null; // S144\n'
    '      _file = null; _result = null; _output = null;\n'
    '      _progress = 0; _status = \'\';\n'
    '      _jobId = null; _busy = false;\n'
    '      _isMerging = false; _sizeLabel = \'\';\n'
    '      _isLarge = false; _fileBytes = 0;\n'
    '    });\n'
    '    ApiService.clearJobId(); // S57\n'
    '  }',
    'Bug-18 fixed: _resetForNewFile stops player and resets all A/B state')

# ── Bug-19: dead asset reminder ───────────────────────────────────────────────
print(f'\n{"="*60}\n  Bug-19: dead asset reminder\n{"="*60}')
dead = Path.home() / 'tilawa-enhancer/assets/engines/engine_isteidad_v12.py'
if dead.exists():
    dead.unlink()
    ok('Bug-19 fixed: engine_isteidad_v12.py deleted (522KB dead asset)')
else:
    ok('Bug-19: engine_isteidad_v12.py already absent — nothing to do')

# ── Summary ────────────────────────────────────────────────────────────────────
print(f'\n{"="*60}')
ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
print(f'\n  {"✅ All OK" if xx_n == 0 else "⚠  " + str(xx_n) + " FAILED"}  {ok_n} OK\n')
print('  git add -A && git commit -m "S144: 3 bugs — AB DeviceFileSource content://, resetForNewFile AB state, dead 522KB asset" && git push')
