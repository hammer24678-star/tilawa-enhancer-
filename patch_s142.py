#!/usr/bin/env python3
"""
patch_s142.py — 7 bugs found in S142 deep scan
================================================

Bug-6  [CRITICAL — wake lock never released on local engine error or cancel]
  _processLocal() error branch does setState+return with no release().
  _cancelProcessing() calls LocalEngineService.cancelEngine() for local mode
  but has no _wakeCh.invokeMethod('release'). Both paths leave the CPU wake
  lock held until Android kills the app → sustained battery drain.

Bug-7  [CRITICAL — A/B player replay silently broken after track completes]
  onPlayerComplete resets _abPos=0 but keeps _abEverPlayed=true.
  _abTogglePlay() condition: !_abEverPlayed||_abPos>=_abDur-0.1
  After completion: _abEverPlayed=true, _abPos=0, _abDur=120000 →
  both sub-conditions false → falls through to resume() → does nothing.
  User can never replay a track after it finishes.

Bug-8  [LOGIC — server-only engines (v7–v10) silently fall back to v11.0]
  No guard in _processLocal() prevents non-localOnly engines from running
  locally. The Kotlin default fallback quietly runs engine_tajalli_v1.py
  (v11.0) and attributes the result to the wrong engine.

Bug-9  [UX — Open in Player + Share buttons hidden for local mode results]
  The outer gate and both inner button conditions all check
  path.startsWith('content://') — local mode returns file:// paths.
  _openInPlayer() and _shareFile() already handle file:// correctly;
  the buttons just aren't rendered.

Bug-10 [PERF — setup() re-downloads python-env.tar.gz (135 MB) on retry]
  setup() numpyOk does not include the tilawa_numpy path, but that is
  exactly where pip installs numpy (S106). After a first successful install,
  if setup runs again numpyOk=false → full 135 MB re-download + reinstall.
  isSetupComplete() already has the correct path; setup() does not.

Bug-11 [LOW — _StarsPainter uses O(n²) stars.indexOf in every paint frame]
  18 stars × 60 fps → linear scan every frame. Replace for-each with
  index-based loop.

Bug-12 [TRIVIAL — Gradle version print says 8.3, actual is 8.11.1]
  Misleading CI output.
"""
from pathlib import Path
from datetime import datetime
import sys

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
PA = Path.home() / 'tilawa-enhancer/patch_android.py'

_log = []
def ok(l):  print(f'  OK  {l}'); _log.append(('OK', l))
def xx(l):  print(f'  XX  NOT FOUND — {l}'); _log.append(('XX', l)); sys.exit(1)

def rep(path, old, new, lbl):
    t = path.read_text(encoding='utf-8')
    if old in t:
        path.write_text(t.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else:
        xx(lbl)

print(f'\n{"="*60}\n  S142  {datetime.now().strftime("%H:%M:%S")}\n{"="*60}')

# ── Bug-6a: wake lock release missing on local engine error ────────────────────
print(f'\n{"="*60}\n  Bug-6a: release wake lock on local engine error\n{"="*60}')
rep(HS,
    '      if (ev[\'error\'] == true) {\n'
    '        setState(() {\n'
    '          _busy     = false;\n'
    '          _status   = ev[\'msg\'] as String? ?? \'Local engine error\';\n'
    '        });\n'
    '        return;\n'
    '      }',

    '      if (ev[\'error\'] == true) {\n'
    '        _wakeCh.invokeMethod(\'release\').catchError((_) {}); // S142: release on error\n'
    '        setState(() {\n'
    '          _busy     = false;\n'
    '          _status   = ev[\'msg\'] as String? ?? \'Local engine error\';\n'
    '        });\n'
    '        return;\n'
    '      }',
    'Bug-6a fixed: wake lock released on local engine error')

# ── Bug-6b: wake lock release missing in _cancelProcessing (local mode) ────────
print(f'\n{"="*60}\n  Bug-6b: release wake lock in _cancelProcessing local branch\n{"="*60}')
rep(HS,
    '    if (_localMode) LocalEngineService.cancelEngine(); // S140: stop proot process\n'
    '    setState(() {',

    '    if (_localMode) {\n'
    '      LocalEngineService.cancelEngine(); // S140: stop proot process\n'
    '      _wakeCh.invokeMethod(\'release\').catchError((_) {}); // S142: release on local cancel\n'
    '    }\n'
    '    setState(() {',
    'Bug-6b fixed: wake lock released on local cancel')

# ── Bug-7: A/B replay broken after track completes ─────────────────────────────
print(f'\n{"="*60}\n  Bug-7: A/B replay — add _abPos <= 0.1 to play condition\n{"="*60}')
rep(HS,
    '      if (!_abEverPlayed || _abPos >= _abDur - 0.1) { // S140: play if never loaded\n'
    '        await _abPlayer.play(DeviceFileSource(src.path));\n'
    '        _abEverPlayed = true;\n'
    '      } else {\n'
    '        await _abPlayer.resume();\n'
    '      }',

    '      if (!_abEverPlayed || _abPos <= 0.1 || _abPos >= _abDur - 0.1) { // S142: also replay when pos reset to 0\n'
    '        await _abPlayer.play(DeviceFileSource(src.path));\n'
    '        _abEverPlayed = true;\n'
    '      } else {\n'
    '        await _abPlayer.resume();\n'
    '      }',
    'Bug-7 fixed: A/B replay works after track completes')

# ── Bug-8: server-only engines silently fall back to v11.0 in local mode ───────
print(f'\n{"="*60}\n  Bug-8: guard server-only engines in _processLocal\n{"="*60}')
rep(HS,
    '    if (_file == null || _busy) return;\n'
    '    HapticFeedback.mediumImpact();\n'
    '    _wakeCh.invokeMethod(\'acquire\').catchError((_) {}); // S141: keep CPU alive during proot',

    '    if (_file == null || _busy) return;\n'
    '    if (!_selectedEngine.localOnly) { // S142: reject server-only engines in local mode\n'
    '      final s = LangProvider.strings(context);\n'
    '      ScaffoldMessenger.of(context).showSnackBar(SnackBar(\n'
    '        content: Text(s.ar\n'
    '          ? \'هذا المحرك يعمل على الخادم فقط. اختر محركاً محلياً (v11.x)\'\n'
    '          : \'This engine is server-only. Select a v11.x local engine.\'),\n'
    '        backgroundColor: const Color(0xFF200D0D)));\n'
    '      return;\n'
    '    }\n'
    '    HapticFeedback.mediumImpact();\n'
    '    _wakeCh.invokeMethod(\'acquire\').catchError((_) {}); // S141: keep CPU alive during proot',
    'Bug-8 fixed: server-only engines blocked in local mode with snackbar')

# ── Bug-9: Open/Share buttons hidden for local mode (file:// paths) ────────────
print(f'\n{"="*60}\n  Bug-9: Open+Share buttons — include local file:// paths\n{"="*60}')

# 9a: outer gate
rep(HS,
    '        if (hasContentUri || (_output?.path.startsWith(\'content://\') ?? false)) ...[',
    '        if (hasContentUri || (_localMode && _output != null)) ...[ // S142: include local file:// outputs',
    'Bug-9a fixed: outer gate includes local file:// paths')

# 9b: Open in Player button condition
rep(HS,
    '            if (hasContentUri) Expanded(\n'
    '              child: OutlinedButton.icon(\n'
    '                onPressed: _openInPlayer,',
    '            if (hasContentUri || (_localMode && _output != null)) Expanded( // S142\n'
    '              child: OutlinedButton.icon(\n'
    '                onPressed: _openInPlayer,',
    'Bug-9b fixed: Open in Player button shown for local mode')

# 9c: spacer condition between the two buttons
rep(HS,
    '            if (hasContentUri && (_output?.path.startsWith(\'content://\') ?? false))\n'
    '              const SizedBox(width: 8),',
    '            if (hasContentUri || (_localMode && _output != null))\n'
    '              const SizedBox(width: 8), // S142: spacer shown when both buttons present',
    'Bug-9c fixed: spacer condition updated')

# 9d: Share button condition
rep(HS,
    '            if (_output?.path.startsWith(\'content://\') ?? false) Expanded(\n'
    '              child: OutlinedButton.icon(\n'
    '                onPressed: _shareFile,',
    '            if (hasContentUri || (_localMode && _output != null)) Expanded( // S142\n'
    '              child: OutlinedButton.icon(\n'
    '                onPressed: _shareFile,',
    'Bug-9d fixed: Share button shown for local mode')

# ── Bug-10: setup() numpyOk missing tilawa_numpy path (PA) ────────────────────
print(f'\n{"="*60}\n  Bug-10: setup() numpyOk — add tilawa_numpy path\n{"="*60}')
rep(PA,
    '        val numpyOk = File(alpineDir, "usr/lib/python3.11/site-packages/numpy").exists() ||\n'
    '            File(alpineDir, "usr/lib/python3.12/site-packages/numpy").exists() ||\n'
    '            File(alpineDir, "usr/lib/python3/dist-packages/numpy").exists()\n'
    '        if (!File(alpineDir, "usr/bin/python3").exists() || !numpyOk) {  // S115: re-extract if numpy missing',

    '        val numpyOk = File(alpineDir, "usr/lib/python3.11/site-packages/numpy").exists() ||\n'
    '            File(alpineDir, "usr/lib/python3.12/site-packages/numpy").exists() ||\n'
    '            File(alpineDir, "usr/lib/python3/dist-packages/numpy").exists() ||\n'
    '            File(alpineDir, "tilawa_numpy/numpy").exists()  // S142: match isSetupComplete()\n'
    '        if (!File(alpineDir, "usr/bin/python3").exists() || !numpyOk) {  // S115: re-extract if numpy missing',
    'Bug-10 fixed: tilawa_numpy path added to setup() numpyOk')

# ── Bug-11: _StarsPainter O(n²) indexOf → index-based loop ────────────────────
print(f'\n{"="*60}\n  Bug-11: _StarsPainter — replace indexOf with index loop\n{"="*60}')
rep(HS,
    '    for (final s in stars) {\n'
    '      final a = t * 6.2832 * s.speed + s.phase;\n'
    '      final x = s.x * size.width  + sin(a)        * size.width  * 0.016;\n'
    '      final y = s.y * size.height + cos(a * 0.71) * size.height * 0.012;\n'
    '      final alpha = sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5;\n'
    '      final op = 0.22 + 0.78 * alpha;\n'
    '      final sz = s.size * (0.55 + 0.45 * alpha);\n'
    '      final idx = stars.indexOf(s);',

    '    for (int idx = 0; idx < stars.length; idx++) { // S142: O(n) not O(n²)\n'
    '      final s = stars[idx];\n'
    '      final a = t * 6.2832 * s.speed + s.phase;\n'
    '      final x = s.x * size.width  + sin(a)        * size.width  * 0.016;\n'
    '      final y = s.y * size.height + cos(a * 0.71) * size.height * 0.012;\n'
    '      final alpha = sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5;\n'
    '      final op = 0.22 + 0.78 * alpha;\n'
    '      final sz = s.size * (0.55 + 0.45 * alpha);',
    'Bug-11 fixed: _StarsPainter uses index-based loop')

# ── Bug-12: Gradle version print says 8.3, should be 8.11.1 (PA) ──────────────
print(f'\n{"="*60}\n  Bug-12: fix Gradle version in print statement\n{"="*60}')
rep(PA,
    'print("  gradle-wrapper.properties OK (Gradle 8.3)")',
    'print("  gradle-wrapper.properties OK (Gradle 8.11.1)")  # S142: was 8.3',
    'Bug-12 fixed: Gradle version print corrected to 8.11.1')

# ── Summary ────────────────────────────────────────────────────────────────────
print(f'\n{"="*60}')
ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
print(f'\n  {"✅ All OK" if xx_n == 0 else "⚠  " + str(xx_n) + " FAILED"}  {ok_n} OK\n')
print('  git add -A && git commit -m "S142: 7 bugs — wake lock release, AB replay, server-only guard, open/share local, numpyOk, indexOf, gradle print" && git push')
