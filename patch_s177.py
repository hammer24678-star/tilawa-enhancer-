#!/usr/bin/env python3
"""
patch_s177.py — S177: fix two NameError crashes in sadaa_altamayuz()
                  (assets/engines/engine_itiqan_v6_official.py)

Bugs (both inside the صدي التميز / "sadaa_altamayuz" stage — called
unconditionally on every job from the main pipeline):

  1. g_500hz/g_580hz/g_1khz/g_2khz are computed from _base_g500/_base_g580/
     _base_g1k/_base_g2k — names that don't exist anywhere in the file
     (leftover from the pre-v6.0 EQ-fingerprint approach, which the v6.0
     docstring says was replaced by the loudness/density/purity method).
     None of the 7 g_*hz variables (the 4 broken ones, or the 3 already-
     zeroed g_3khz/g_5khz/g_7khz next to them) are ever read again —
     confirmed fully dead. NameError on the very first one every time.

  2. `_sus_cap = 0.45 if _sadaa_aggressive else 0.45` references
     _sadaa_aggressive, which is never defined (no such param on
     sadaa_altamayuz, no assignment anywhere). The ternary is also a
     no-op regardless — both branches are 0.45.

Fix:
  1. Delete the 4 dead lines computing from the undefined _base_g* names
     (g_3khz/g_5khz/g_7khz are left as-is, since they were already correct).
  2. Collapse the dead ternary to the constant it always evaluated to: 0.45.
"""

import sys
from pathlib import Path

REPO = Path(__file__).parent  # run from repo root

def fail(msg):
    print(f'  FAIL  {msg}'); sys.exit(1)

def patch(path, old, new, tag):
    p = Path(path)
    if not p.exists(): fail(f'{path} not found')
    src = p.read_text(encoding='utf-8')
    if new.strip() in src and old.strip() not in src:
        print(f'  SKIP  {tag} (already applied)'); return
    if old not in src:
        fail(f'{tag}: anchor not found in {path}')
    p.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

# ── idempotency guard ─────────────────────────────────────────────────────────
STAMP = Path('.patch_s177_done')
if STAMP.exists():
    print('patch_s177: already applied — delete .patch_s177_done to re-run'); sys.exit(0)

print('\n── S177: fix NameError crashes in sadaa_altamayuz (Itiqan v6) ───────────────')

ENGINE = Path('assets/engines/engine_itiqan_v6_official.py')

# E1 — remove the 4 dead lines referencing undefined _base_g500/g580/g1k/g2k
patch(ENGINE,
'''    g_500hz = round(_base_g500, 1)   # 500Hz room mode — no scaling, always needed
    g_580hz = round(_base_g580, 1)   # H4 harmonic correction
    g_1khz  = round(_base_g1k,  1)   # presence
    g_2khz  = round(_base_g2k,  1)   # presence
    g_3khz  = 0.0
    g_5khz  = 0.0
    g_7khz  = 0.0''',
'''    # S177: removed g_500hz/g_580hz/g_1khz/g_2khz — computed from undefined
    # _base_g500/_base_g580/_base_g1k/_base_g2k (NameError every call) and,
    # like g_3khz/g_5khz/g_7khz below, never read again — confirmed dead
    # leftovers from the pre-v6.0 EQ-fingerprint approach.
    g_3khz  = 0.0
    g_5khz  = 0.0
    g_7khz  = 0.0''',
    'E1: remove dead _base_g* NameError lines')

# E2 — collapse the dead ternary referencing undefined _sadaa_aggressive
patch(ENGINE,
    "_sus_cap = 0.45 if _sadaa_aggressive else 0.45",
    "_sus_cap = 0.45  # S177: was a no-op ternary on undefined _sadaa_aggressive",
    'E2: fix _sadaa_aggressive NameError')

# ── stamp ─────────────────────────────────────────────────────────────────────
STAMP.write_text('S177\n')
print('\n✅  patch_s177 done')
print('   git add assets/engines/engine_itiqan_v6_official.py')
print('   git commit -m "S177: fix NameError crashes in sadaa_altamayuz (undefined _base_g*, _sadaa_aggressive)"')
print('   git push')
