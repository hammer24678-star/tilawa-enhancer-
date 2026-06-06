#!/usr/bin/env python3
"""
patch_s141.py — 5 bugs found in full repo scan
===============================================

Bug-1  [CRITICAL — local mode never saves files]
  _reDownload() calls saveToDownloads on the WAKE channel
  ('com.tilawa.tilawa_enhancer/wake') instead of the MEDIA channel
  ('com.tilawa.tilawa_enhancer/media'). The wake channel only handles
  acquire/release → notImplemented() for everything else. Result:
  every local-mode save silently fails with a PlatformException.
  Users see the error snackbar every time. Fix: use media channel.

Bug-2  [CRITICAL — numpy/scipy always import-fails in local engine]
  PYTHONPATH in _LOCAL_RUNNER_KT (patch_android.py) does not include
  /tilawa_numpy, yet that is exactly where S106 pip-installs numpy and
  scipy (pip3 install --target /tilawa_numpy ...). The system Python
  site-packages path is present but only a fallback. Without /tilawa_numpy
  in PYTHONPATH, every engine that imports numpy crashes immediately.
  Fix: append :/tilawa_numpy to the PYTHONPATH value.

Bug-3  [LOGIC — wake lock never acquired for local engine]
  _startPolling() acquires a CPU wake lock so the server-mode poll
  timer survives screen-off. _processLocal() never acquires this lock,
  so Android can kill the proot process mid-run when the screen turns
  off. Fix: add wake lock acquire at the start of _processLocal().

Bug-4  [PERF — _ScoreBurstPainter rendered twice]
  The result card wraps two nested Stacks. The outer Stack and the inner
  Stack both contain an AnimatedBuilder(_ScoreBurstPainter) for score≥85.
  The outer one is completely occluded by the inner Stack — it renders
  but is never visible. Fix: remove the outer duplicate.

Bug-5  [UX — engineNames map in _resultCard missing all v11.x engines]
  The map has entries for v8.4 and v8.9 (removed engines) but nothing
  for v11.0/v11.1/v11.2. When any v11.x engine completes, engineName
  falls back to the raw ID string ('v11.0') instead of a proper name.
  Fix: add v11.x entries, drop dead v8.4/v8.9.
"""
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
PA = Path.home() / 'tilawa-enhancer/patch_android.py'

_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK', l))
def xx(l): print(f'  XX  NOT FOUND — {l}'); _log.append(('XX', l))

def rep(path, old, new, lbl):
    t = path.read_text(encoding='utf-8')
    if old in t:
        path.write_text(t.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else:
        xx(lbl)

print(f'\n{"="*60}\n  S141  {datetime.now().strftime("%H:%M:%S")}\n{"="*60}')

# ── Bug-1: wrong channel in _reDownload (local mode save always fails) ─────────
print(f'\n{"="*60}\n  Bug-1: _reDownload → media channel (not wake)\n{"="*60}')
rep(HS,
    "        const wakeChannel = MethodChannel('com.tilawa.tilawa_enhancer/wake');\n"
    "        await wakeChannel.invokeMethod<String>(\n"
    "          'saveToDownloads', {'path': src.path, 'filename': fname});",

    "        const mediaChannel = MethodChannel('com.tilawa.tilawa_enhancer/media'); // S141: was /wake\n"
    "        await mediaChannel.invokeMethod<String>(\n"
    "          'saveToDownloads', {'path': src.path, 'filename': fname});",
    'Bug-1 fixed: _reDownload now uses media channel for saveToDownloads')

# ── Bug-2: PYTHONPATH missing /tilawa_numpy (in patch_android.py) ──────────────
print(f'\n{"="*60}\n  Bug-2: PYTHONPATH += :/tilawa_numpy\n{"="*60}')
rep(PA,
    'environment()["PYTHONPATH"] = "/usr/lib/python3.11/site-packages:/usr/lib/python3.12/site-packages:/usr/lib/python3/dist-packages"',
    'environment()["PYTHONPATH"] = "/usr/lib/python3.11/site-packages:/usr/lib/python3.12/site-packages:/usr/lib/python3/dist-packages:/tilawa_numpy" // S141: tilawa_numpy path',
    'Bug-2 fixed: /tilawa_numpy added to PYTHONPATH in _LOCAL_RUNNER_KT')

# ── Bug-3: _processLocal never acquires wake lock ──────────────────────────────
print(f'\n{"="*60}\n  Bug-3: wake lock acquire in _processLocal\n{"="*60}')
rep(HS,
    '    HapticFeedback.mediumImpact();\n'
    '    setState(() {\n'
    '      _busy      = true;\n'
    '      _progress  = 0.02;\n'
    '      _status    = \'Starting local engine…\';\n'
    '      _localMsg  = \'\';\n'
    '    });',

    '    HapticFeedback.mediumImpact();\n'
    '    _wakeCh.invokeMethod(\'acquire\').catchError((_) {}); // S141: keep CPU alive during proot\n'
    '    setState(() {\n'
    '      _busy      = true;\n'
    '      _progress  = 0.02;\n'
    '      _status    = \'Starting local engine…\';\n'
    '      _localMsg  = \'\';\n'
    '    });',
    'Bug-3 fixed: wake lock acquired at start of _processLocal')

# ── Bug-4: duplicate _ScoreBurstPainter in outer Stack ─────────────────────────
print(f'\n{"="*60}\n  Bug-4: remove duplicate outer ScoreBurstPainter\n{"="*60}')
rep(HS,
    '              // Burst particles on reveal\n'
    '              if (score >= 85) AnimatedBuilder(\n'
    '                animation: _resultCtrl,\n'
    '                builder: (_, __) => CustomPaint(\n'
    '                  size: const Size(170, 170),\n'
    '                  painter: _ScoreBurstPainter(\n'
    '                    progress: _resultCtrl.value,\n'
    '                    color: scoreColor))),\n'
    '              Stack(alignment: Alignment.center, children: [\n'
    '              // Burst particles on reveal',

    '              // S141: outer burst removed (was identical duplicate of inner)\n'
    '              Stack(alignment: Alignment.center, children: [\n'
    '              // Burst particles on reveal',
    'Bug-4 fixed: duplicate outer _ScoreBurstPainter removed')

# ── Bug-5: engineNames map missing v11.x, has dead v8.4/v8.9 ──────────────────
print(f'\n{"="*60}\n  Bug-5: engineNames map — add v11.x, drop dead entries\n{"="*60}')
rep(HS,
    "    const engineNames = {\n"
    "      'v10.0': 'Aetherion Foundation',\n"
    "      'v9.0': 'The Evolution',\n"
    "      'v8.9': 'Soft Tiers + LPC',\n"
    "      'v8.5': 'Honest Ceiling',\n"
    "      'v8.4': 'Source Tier Intelligence',\n"
    "      'v8.0': 'Calibrated Precision',\n"
    "      'v7.0': 'Classic',\n"
    "    };",

    "    const engineNames = { // S141: added v11.x, removed dead v8.4/v8.9\n"
    "      'v11.0': 'التجلي — The Manifestation',\n"
    "      'v11.1': 'الإتقان — Perfection',\n"
    "      'v11.2': 'الاسترداد — Recovery',\n"
    "      'v10.0': 'Aetherion Foundation',\n"
    "      'v9.0': 'The Evolution',\n"
    "      'v8.5': 'Honest Ceiling',\n"
    "      'v8.0': 'Calibrated Precision',\n"
    "      'v7.0': 'Classic',\n"
    "    };",
    'Bug-5 fixed: engineNames now includes v11.0/v11.1/v11.2')

# ── Summary ────────────────────────────────────────────────────────────────────
print(f'\n{"="*60}')
ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
print(f'\n  {"✅ All OK" if xx_n == 0 else "⚠  " + str(xx_n) + " FAILED"}  {ok_n} OK\n')
print('  git add -A && git commit -m "S141: 5 bugs — media channel, PYTHONPATH, wake lock, dup painter, engineNames" && git push')
