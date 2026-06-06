#!/usr/bin/env python3
"""
tilawa_fix_s138.py — Remaining s70 fixes (S94 covered Fix-1f/1j already)
=========================================================================
Fix-3:  servers.json: add background8 (6th server, 18 slots total)
Fix-4+6: AB player: set listeners in _abToggleTrack + reset _abDur on track switch
Fix-5:  Uri.file() instead of Uri.parse() for local output file paths
Fix-7:  Remove dead ternary  s.ar ? s.jobExpired : s.jobExpired  → s.jobExpired
"""
import sys, json
from pathlib import Path
from datetime import datetime

HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
SRV = Path.home() / 'tilawa-enhancer/assets/servers.json'
_log = []

def ok(l): print(f'  OK  {l}'); _log.append(('OK', l))
def xx(l): print(f'  XX  NOT FOUND — {l}'); _log.append(('XX', l))

def rep(path, old, new, lbl):
    t = path.read_text(encoding='utf-8')
    if old in t:
        path.write_text(t.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else:
        xx(lbl)

print(f'\n{"="*56}\n  S138  {datetime.now().strftime("%H:%M:%S")}\n{"="*56}')

# ── Fix-3: servers.json — add bg8 ────────────────────────────────────────────
print(f'\n{"="*56}\n  Fix-3 — servers.json: add background8\n{"="*56}')
if SRV.exists():
    data = json.loads(SRV.read_text())
    servers = data.get('servers', [])
    bg8 = 'https://carm5333-background8.hf.space'
    if bg8 not in servers:
        servers.append(bg8)
        data['servers'] = servers
        SRV.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        ok(f'background8 added ({len(servers)} servers, {len(servers)*3} slots)')
    else:
        ok('background8 already in list')
else:
    xx('servers.json not found')

# ── Fix-4+6: AB player — listeners in _abToggleTrack + reset _abDur ──────────
print(f'\n{"="*56}\n  Fix-4+6 — AB player: listeners + _abDur reset\n{"="*56}')
rep(HS,
    "  Future<void> _abToggleTrack() async {\n"
    "    setState(() { _abIsB = !_abIsB; _abPos = 0; });\n"
    "    final src = _abIsB ? _output : _file;\n"
    "    if (src == null) return;\n"
    "    await _abPlayer.stop();\n"
    "    await _abPlayer.play(DeviceFileSource(src.path));\n"
    "    setState(() { _abPlaying = true; });\n"
    "  }",

    "  Future<void> _abToggleTrack() async {\n"
    "    setState(() { _abIsB = !_abIsB; _abPos = 0; _abDur = 1.0; }); // S138: reset dur\n"
    "    final src = _abIsB ? _output : _file;\n"
    "    if (src == null) return;\n"
    "    if (!_abListenersSet) { // S138: set listeners before first play\n"
    "      _abListenersSet = true;\n"
    "      _abPlayer.onDurationChanged.listen((d) {\n"
    "        if (mounted) setState(() { _abDur = d.inMilliseconds.toDouble().clamp(1, 1e9); });\n"
    "      });\n"
    "      _abPlayer.onPositionChanged.listen((p) {\n"
    "        if (mounted) setState(() { _abPos = p.inMilliseconds.toDouble(); });\n"
    "      });\n"
    "      _abPlayer.onPlayerComplete.listen((_) {\n"
    "        if (mounted) setState(() { _abPlaying = false; _abPos = 0; });\n"
    "      });\n"
    "    }\n"
    "    await _abPlayer.stop();\n"
    "    await _abPlayer.play(DeviceFileSource(src.path));\n"
    "    setState(() { _abPlaying = true; });\n"
    "  }",
    'AB listeners in _abToggleTrack + _abDur reset')

# ── Fix-5: Uri.file() for local output file paths ────────────────────────────
print(f'\n{"="*56}\n  Fix-5 — Uri.file() for local file paths\n{"="*56}')
rep(HS,
    "      final uri = Uri.parse(_output!.path);\n"
    "      await launchUrl(uri, mode: LaunchMode.externalApplication);",
    "      final uri = Uri.file(_output!.path); // S138: Uri.file for local paths\n"
    "      await launchUrl(uri, mode: LaunchMode.externalApplication);",
    'Uri.file() for local output path')

# ── Fix-7: Dead ternary s.ar ? s.jobExpired : s.jobExpired ───────────────────
print(f'\n{"="*56}\n  Fix-7 — remove dead ternary s.jobExpired\n{"="*56}')
rep(HS,
    "      ? (s.ar ? s.jobExpired : s.jobExpired)",
    "      ? s.jobExpired",
    'dead ternary s.jobExpired removed')

# ── Summary ───────────────────────────────────────────────────────────────────
print(f'\n{"="*56}')
ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
print(f'\n  {"✅ All OK" if xx_n == 0 else "⚠  " + str(xx_n) + " FAILED"}  {ok_n} OK\n')
print('  git add -A && git commit -m "S138: bg8 server + AB player fix + Uri.file + dead ternary" && git push')
