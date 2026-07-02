#!/usr/bin/env python3
"""
patch_s181.py — S181: align audio editor's colors with the app's theme

The rest of the app (home_screen.dart, history_screen.dart, etc.) shares one
"Sacred Cosmos" palette:
    _bgDeep=#020D17  _bgSurface=#0C1E28  _bgCard=#0F2420
    _gold=#D4AF37  _goldLight=#F0CF60  _goldMuted=#3A2B08
    _textA=#E2CFA0 (warm gold-tinted)  _textB=#8AACBA  _textC=#3D5A65
    _err=#D94040

audio_editor_screen.dart was built with its own slightly different,
cooler/greener palette (_bg=#070F0B, _surface=#0C1E14, _card=#0F2418,
_textA=#CDD9CF, _textB=#7A9E8A, _textDim=#3A5040, _red=#E05252) — close
enough to not look "broken," but different enough that the editor reads as
a visually distinct screen instead of part of the same app.

This patch re-points the editor's existing color constants (same names, so
no other line in the 987-line file needs to change) to the shared palette's
actual values, and gives the app-bar title the same gold gradient treatment
used elsewhere (e.g. history_screen's ShaderMask title).

Run from repo root: python3 patch_s181.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).parent

def fail(msg):
    print(f'  FAIL  {msg}'); sys.exit(1)

def patch(path, old, new, tag, required=True):
    p = Path(path)
    if not p.exists():
        if required: fail(f'{path} not found')
        print(f'  SKIP  {tag} ({path} not found)'); return
    src = p.read_text(encoding='utf-8')
    if new.strip() in src:
        print(f'  SKIP  {tag} (already applied)'); return
    if old not in src:
        if required: fail(f'{tag}: anchor not found in {path}')
        print(f'  WARN  {tag}: anchor not found in {path} — skipped (non-fatal)'); return
    p.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

STAMP = Path('.patch_s181_done')
if STAMP.exists():
    print('patch_s181: already applied — delete .patch_s181_done to re-run'); sys.exit(0)

print('\n── S181: align audio editor colors + app-bar title with app theme ──')

F = 'lib/screens/audio_editor_screen.dart'

# ════════════════════════════════════════════════════════════════════════════
# E1 — re-point the editor's palette constants to the shared Sacred Cosmos
#      values (same const names everywhere else in the file — zero other
#      lines need to change).
# ════════════════════════════════════════════════════════════════════════════
patch(F,
    '''const _bg      = Color(0xFF070F0B);
const _surface = Color(0xFF0C1E14);
const _card    = Color(0xFF0F2418);
const _gold    = Color(0xFFD4AF37);
const _goldDim = Color(0xFF8B6914);
const _teal    = Color(0xFF1DB898);
const _tealDk  = Color(0xFF0A3D2A);
const _red     = Color(0xFFE05252);
const _textA   = Color(0xFFCDD9CF);
const _textB   = Color(0xFF7A9E8A);
const _textDim = Color(0xFF3A5040);
const _border  = Color(0xFF1A2E20);''',
    '''// S181: re-pointed to the app's shared "Sacred Cosmos" palette (same
// constant names used throughout this file — see home_screen.dart for
// the canonical values) so this screen matches the rest of the app
// instead of its own slightly cooler/greener one-off colors.
const _bg      = Color(0xFF020D17);
const _surface = Color(0xFF0C1E28);
const _card    = Color(0xFF0F2420);
const _gold    = Color(0xFFD4AF37);
const _goldDim = Color(0xFF3A2B08);
const _teal    = Color(0xFF1DB898);
const _tealDk  = Color(0xFF0A3D2A);
const _red     = Color(0xFFD94040);
const _textA   = Color(0xFFE2CFA0);
const _textB   = Color(0xFF8AACBA);
const _textDim = Color(0xFF3D5A65);
const _border  = Color(0xFF1A2E20);''',
    'E1: editor palette re-pointed to shared app theme')

# ════════════════════════════════════════════════════════════════════════════
# E2 — app-bar title: plain gold text -> gold gradient ShaderMask, matching
#      the treatment other screens (e.g. history_screen) give their titles.
# ════════════════════════════════════════════════════════════════════════════
patch(F,
    '''      const Expanded(child: Text('محرر الصوت',
          textAlign: TextAlign.center,
          style: TextStyle(color: _gold, fontSize: 17,
              fontWeight: FontWeight.w700, letterSpacing: 0.3))),''',
    '''      Expanded(child: ShaderMask(  // S181: match other screens' gold gradient titles
        shaderCallback: (b) => const LinearGradient(
            colors: [_gold, Color(0xFFF0CF60)]).createShader(b),
        child: const Text('محرر الصوت',
            textAlign: TextAlign.center,
            style: TextStyle(color: Colors.white, fontSize: 17,
                fontWeight: FontWeight.w700, letterSpacing: 0.3)))),''',
    'E2: app-bar title now uses gold gradient ShaderMask')

STAMP.write_text('S181\n')
print('\n✅  patch_s181 done')
print('   git add lib/screens/audio_editor_screen.dart')
print('   git commit -m "S181: align audio editor colors + app-bar title with app theme"')
print('   git push')
