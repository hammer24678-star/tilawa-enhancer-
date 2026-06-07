#!/usr/bin/env python3
"""
patch_s145.py — 2 bugs found in S145 deep scan
================================================

Bug-20 [CRITICAL — _reDownload() crashes on second tap]
  S143 Bug-15 made _reDownload() update _output to File('content://...') after
  the first save. S144 Bug-17 introduced _abOutputFile to preserve the original
  cacheDir path for the A/B player — but _reDownload() itself was never updated.
  It still opens _output as the source:

    if (_localMode && _output != null) {
        final src = _output!;                         // content:// after first save
        final ext = src.path.endsWith('.mp3') ...     // wrong: content:// ≠ .mp3
        saveToDownloads({'path': src.path, ...})      // File(content://...) throws

  java.io.File('content://...') throws FileNotFoundException in Kotlin.
  User sees "❌ Save failed" on every Download tap after the first.

  Fix: use _abOutputFile (always the original cacheDir path) as the source,
  mirroring the same fix applied to the A/B player in S144.

Bug-21 [LOGIC — _pickFile() doesn't stop A/B player or reset A/B state]
  S144 Bug-18 fixed _resetForNewFile() to stop the player and reset all A/B
  state. _pickFile() has the identical problem and was missed. When the user
  picks a new file while the A/B player is playing, _pickFile() sets
  _output=null (hiding the A/B card) but never calls _abPlayer.stop().
  Audio keeps playing. _abEverPlayed, _abPos, _abDur, _abOutputFile remain
  stale from the previous session. When the new file is processed, the stale
  _abPos causes the same resume()-on-unloaded-player failure as S144 Bug-18.

  Fix: mirror the S144 _resetForNewFile() fix inside _pickFile().
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

print(f'\n{"="*60}\n  S145  {datetime.now().strftime("%H:%M:%S")}\n{"="*60}')

# ── Bug-20: _reDownload() — use _abOutputFile instead of _output ──────────────
print(f'\n{"="*60}\n  Bug-20: _reDownload uses _abOutputFile not _output\n{"="*60}')
rep(HS,
    '    // S100: Local mode — copy cached output to Downloads\n'
    '    if (_localMode && _output != null) {\n'
    '      final src = _output!;',

    '    // S100: Local mode — copy cached output to Downloads\n'
    '    if (_localMode && _abOutputFile != null) { // S145: use cacheDir file — _output may be content:// after first save\n'
    '      final src = _abOutputFile!;',
    'Bug-20 fixed: _reDownload() uses _abOutputFile — safe on repeated taps')

# ── Bug-21: _pickFile() — stop player and reset A/B state ────────────────────
print(f'\n{"="*60}\n  Bug-21: _pickFile — stop A/B player + reset A/B state\n{"="*60}')
rep(HS,
    '    if (r?.files.single.path != null) {\n'
    '      final f = File(r!.files.single.path!);\n'
    '      final bytes = await f.length();\n'
    '      setState(() {\n'
    '        _file = f;\n'
    '        _output = null; _result = null;\n'
    '        _status = \'\'; _progress = 0;\n'
    '        _sizeLabel = \'${(bytes / 1024 / 1024).toStringAsFixed(1)} MB\';\n'
    '        _isLarge = bytes > 8 * 1024 * 1024;\n'
    '        _fileBytes = bytes;\n'
    '      });\n'
    '    }',

    '    if (r?.files.single.path != null) {\n'
    '      final f = File(r!.files.single.path!);\n'
    '      final bytes = await f.length();\n'
    '      _abPlayer.stop(); // S145: stop audio when new file is picked\n'
    '      setState(() {\n'
    '        _abEverPlayed = false; // S145: reset A/B state\n'
    '        _abPlaying    = false;\n'
    '        _abPos        = 0.0;\n'
    '        _abDur        = 1.0;\n'
    '        _abIsB        = true;\n'
    '        _abOutputFile = null; // S145\n'
    '        _file = f;\n'
    '        _output = null; _result = null;\n'
    '        _status = \'\'; _progress = 0;\n'
    '        _sizeLabel = \'${(bytes / 1024 / 1024).toStringAsFixed(1)} MB\';\n'
    '        _isLarge = bytes > 8 * 1024 * 1024;\n'
    '        _fileBytes = bytes;\n'
    '      });\n'
    '    }',
    'Bug-21 fixed: _pickFile() stops player and resets all A/B state')

# ── Summary ────────────────────────────────────────────────────────────────────
print(f'\n{"="*60}')
ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
print(f'\n  {"✅ All OK" if xx_n == 0 else "⚠  " + str(xx_n) + " FAILED"}  {ok_n} OK\n')
print('  git add -A && git commit -m "S145: 2 bugs — reDownload content:// crash, pickFile AB state" && git push')
