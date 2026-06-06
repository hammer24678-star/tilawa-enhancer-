#!/usr/bin/env python3
"""
patch_s140.py — 6 bugs found across home_screen.dart + pubspec.yaml
=====================================================================

Bug-1  [NOTIFICATION] _processLocal passes sc.toStringAsFixed(1) (String) to
       _fireCompletionNotif, but that function checks `score is num` → always 0.
       Fix: pass sc (double) directly.

Bug-2  [CRASH RISK] _processLocal sets _output = File('') when ev['path'] is
       null or empty. File('') blows up when played/saved. Fix: null-guard.

Bug-3  [UX SILENT FAIL] First tap on the Enhanced (B) AB-player button calls
       _abTogglePlay() → resume() on a player with no source ever loaded
       → silent no-op, but _abPlaying is set to true (UI lies, slider stuck).
       Fix: add _abEverPlayed bool; call play() if never loaded.

Bug-4  [LOCAL MODE] _cancelProcessing() cancels the poll timer + resets state
       but never calls LocalEngineService.cancelEngine() in local mode.
       The proot process keeps running in background even after cancel.
       Fix: call cancelEngine() when _localMode.

Bug-5  [REDUNDANT REBUILD] _localModeToggle's "Tap to set up" onTap block:
         setState(() => _localReady = ready);   ← sets to `ready`
         if (ready) { setState(() => _localReady = true); } ← redundant
       Fires two builds when ready == true. Remove second setState.

Bug-6  [VERSION MISMATCH] pubspec.yaml still says 1.0.0+1.
       patch_android.py sets versionCode=9 / versionName="2.7.0" in
       build.gradle, so the APK is correct — but pubspec is stale/misleading.
       Fix: sync to 2.7.0+9.
"""
from pathlib import Path
from datetime import datetime

HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
PY  = Path.home() / 'tilawa-enhancer/pubspec.yaml'

_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK', l))
def xx(l): print(f'  XX  NOT FOUND — {l}'); _log.append(('XX', l))

def rep(path, old, new, lbl):
    t = path.read_text(encoding='utf-8')
    if old in t:
        path.write_text(t.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else:
        xx(lbl)

print(f'\n{"="*60}\n  S140  {datetime.now().strftime("%H:%M:%S")}\n{"="*60}')

# ── Bug-1: _fireCompletionNotif score type ─────────────────────────────────────
print(f'\n{"="*60}\n  Bug-1: notification score String → num\n{"="*60}')
rep(HS,
    '          _fireCompletionNotif(fn, sc.toStringAsFixed(1));',
    '          _fireCompletionNotif(fn, sc); // S140: pass num, not String',
    'Bug-1 fixed: notification score is now num (shows correct value)')

# ── Bug-2: _processLocal null output path ──────────────────────────────────────
print(f'\n{"="*60}\n  Bug-2: _processLocal null-safe output path\n{"="*60}')
rep(HS,
    '        _wakeCh.invokeMethod(\'release\').catchError((_) {});\n'
    '        setState(() { // S92: ALL result state inside setState\n'
    '          _busy = false; _progress = 0;\n'
    '          _status = \'Local engine complete\';\n'
    '          _output = File(ev[\'path\'] as String? ?? \'\');',

    '        _wakeCh.invokeMethod(\'release\').catchError((_) {});\n'
    '        final _outPath = ev[\'path\'] as String? ?? \'\'; // S140: null-safe\n'
    '        setState(() { // S92: ALL result state inside setState\n'
    '          _busy = false; _progress = 0;\n'
    '          _status = \'Local engine complete\';\n'
    '          _output = _outPath.isNotEmpty ? File(_outPath) : null;',
    'Bug-2 fixed: null-safe output path in _processLocal')

# ── Bug-3: _abEverPlayed field + _abToggleTrack mark + _abTogglePlay fix ───────
print(f'\n{"="*60}\n  Bug-3: AB player first-play guard\n{"="*60}')

# 3a: add field next to _abListenersSet
rep(HS,
    '  bool _abListenersSet = false;',
    '  bool _abListenersSet = false;\n'
    '  bool _abEverPlayed   = false; // S140: guard resume() on unloaded player',
    'Bug-3a: _abEverPlayed field added')

# 3b: mark played in _abToggleTrack (after play() call, before setState)
rep(HS,
    '    await _abPlayer.stop();\n'
    '    await _abPlayer.play(DeviceFileSource(src.path));\n'
    '    setState(() { _abPlaying = true; })\n'
    '  }',

    '    await _abPlayer.stop();\n'
    '    await _abPlayer.play(DeviceFileSource(src.path));\n'
    '    _abEverPlayed = true; // S140\n'
    '    setState(() { _abPlaying = true; })\n'
    '  }',
    'Bug-3b: _abToggleTrack marks player as ever-played')

# 3c: _abTogglePlay: use _abEverPlayed guard so first tap plays, not resumes
rep(HS,
    '      if (_abPos >= _abDur - 0.1) {\n'
    '        await _abPlayer.play(DeviceFileSource(src.path));\n'
    '      } else {\n'
    '        await _abPlayer.resume();\n'
    '      }\n'
    '      setState(() { _abPlaying = true; });',

    '      if (!_abEverPlayed || _abPos >= _abDur - 0.1) { // S140: play if never loaded\n'
    '        await _abPlayer.play(DeviceFileSource(src.path));\n'
    '        _abEverPlayed = true;\n'
    '      } else {\n'
    '        await _abPlayer.resume();\n'
    '      }\n'
    '      setState(() { _abPlaying = true; });',
    'Bug-3c: _abTogglePlay guards against resume() on unloaded player')

# ── Bug-4: _cancelProcessing doesn't cancel local engine ───────────────────────
print(f'\n{"="*60}\n  Bug-4: _cancelProcessing → cancel local engine\n{"="*60}')
rep(HS,
    '    _pollTimer?.cancel();\n'
    '    HapticFeedback.mediumImpact();\n'
    '    setState(() {\n'
    '      _busy = false; _progress = 0;\n'
    '      _status = \'\'; _isMerging = false;\n'
    '      _jobId = null;\n'
    '    });\n'
    '    ApiService.clearJobId(); // S57\n'
    '  }',

    '    _pollTimer?.cancel();\n'
    '    HapticFeedback.mediumImpact();\n'
    '    if (_localMode) LocalEngineService.cancelEngine(); // S140: stop proot process\n'
    '    setState(() {\n'
    '      _busy = false; _progress = 0;\n'
    '      _status = \'\'; _isMerging = false;\n'
    '      _jobId = null;\n'
    '    });\n'
    '    ApiService.clearJobId(); // S57\n'
    '  }',
    'Bug-4 fixed: _cancelProcessing now cancels local proot process')

# ── Bug-5: redundant setState in _localModeToggle ──────────────────────────────
print(f'\n{"="*60}\n  Bug-5: remove redundant setState in _localModeToggle\n{"="*60}')
rep(HS,
    '                  LocalEngineService.isSetupComplete().then((ready) {\n'
    '                    if (mounted) setState(() => _localReady = ready);\n'
    '                    if (!mounted) return;\n'
    '                    if (ready) {\n'
    '                      setState(() => _localReady = true);\n'
    '                    } else {',

    '                  LocalEngineService.isSetupComplete().then((ready) {\n'
    '                    if (!mounted) return;\n'
    '                    setState(() => _localReady = ready); // S140: single setState\n'
    '                    if (ready) {\n'
    '                      // already set above\n'
    '                    } else {',
    'Bug-5 fixed: single setState in _localModeToggle ready check')

# ── Bug-6: pubspec.yaml version ────────────────────────────────────────────────
print(f'\n{"="*60}\n  Bug-6: pubspec.yaml version sync\n{"="*60}')
rep(PY,
    'version: 1.0.0+1',
    'version: 2.7.0+9',
    'Bug-6 fixed: pubspec.yaml now 2.7.0+9')

# ── Summary ────────────────────────────────────────────────────────────────────
print(f'\n{"="*60}')
ok_n = sum(1 for s,_ in _log if s == 'OK')
xx_n = sum(1 for s,_ in _log if s == 'XX')
print(f'\n  {"✅ All OK" if xx_n == 0 else "⚠  " + str(xx_n) + " FAILED"}  {ok_n} OK\n')
print('  git add -A && git commit -m "S140: 6 bugs — notif score, null path, AB first-play, cancel local, redux setState, pubspec version" && git push')
