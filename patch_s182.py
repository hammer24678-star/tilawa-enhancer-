#!/usr/bin/env python3
"""
patch_s182.py — S182: isSetupComplete() never re-triggers a broken numpy
                       install, so S179's fix never actually runs for
                       anyone who already has a broken tilawa_numpy/

Root cause:
    S179 made setupAll() verify numpy/scipy with a real `import` probe and
    repair it if broken — but setupAll() (the function that does that
    work) only runs when the UI calls "startSetup", and the UI only calls
    "startSetup" when isSetupComplete() returns false. isSetupComplete()
    still just checks "does tilawa_numpy/numpy exist as a folder" — the
    exact check S179 already proved isn't good enough. So anyone whose
    numpy install was already broken (Story's exact screenshots) has
    isSetupComplete() permanently reporting "ready", the repair code in
    setupAll() never runs, and the app never recovers on its own.

    isSetupComplete() is called very often (history_screen, home_screen on
    multiple triggers) so it can't shell out to proot every time — that'd
    be slow. Fix: write a small marker file the moment numpyWorks() is
    verified true inside setupAll(); isSetupComplete() checks for that
    marker (fast, no proot) instead of just the numpy/ folder's existence.
    If the marker is missing — first run after this patch, or a previously
    broken install — isSetupComplete() reports false, the UI re-runs
    "Start Setup", and S179's verify+repair logic actually gets a chance
    to run and write the marker once it confirms numpy really imports.

Run from repo root: python3 patch_s182.py
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

STAMP = Path('.patch_s182_done')
if STAMP.exists():
    print('patch_s182: already applied — delete .patch_s182_done to re-run'); sys.exit(0)

print('\n── S182: make isSetupComplete() actually detect a broken numpy install ──')

F = 'patch_android.py'

# ════════════════════════════════════════════════════════════════════════════
# E1 — setupAll(): write a marker file once numpyWorks() is genuinely
#      verified true (covers both the "already fine" early-return and the
#      "just repaired it" path, since both flow through the same check).
# ════════════════════════════════════════════════════════════════════════════
patch(F,
    '''        fun numpyWorks(): Boolean {
            if (!File(numpyTarget, "numpy").exists() || !File(numpyTarget, "scipy").exists()) return false
            val probe = runProot(listOf("/usr/bin/python3", "-c", "import numpy, scipy"), timeoutMin=2)
            return probe.first == 0
        }
        if (!numpyWorks()) {''',
    '''        // S182: marker isSetupComplete() can check cheaply (no proot) instead
        // of trusting the numpy/ folder's mere existence forever.
        val numpyVerifiedMarker = File(alpineDir, ".numpy_verified")
        fun numpyWorks(): Boolean {
            if (!File(numpyTarget, "numpy").exists() || !File(numpyTarget, "scipy").exists()) return false
            val probe = runProot(listOf("/usr/bin/python3", "-c", "import numpy, scipy"), timeoutMin=2)
            val ok = probe.first == 0
            if (ok) numpyVerifiedMarker.writeText("ok") else numpyVerifiedMarker.delete()
            return ok
        }
        if (!numpyWorks()) {''',
    'E1: numpyWorks() now writes/clears a .numpy_verified marker')

# ════════════════════════════════════════════════════════════════════════════
# E2 — isSetupComplete(): check the marker instead of the numpy/scipy dir
#      existence. Missing marker (never verified, or repaired-but-unmarked
#      from before this patch) → report incomplete → UI re-runs setup →
#      setupAll()'s numpyWorks() probes for real and writes the marker.
# ════════════════════════════════════════════════════════════════════════════
patch(F,
    '''        val numpyOk = File(alpineDir, "usr/lib/python3.11/site-packages/numpy").exists() ||
            File(alpineDir, "usr/lib/python3.12/site-packages/numpy").exists() ||
            File(alpineDir, "tilawa_numpy/numpy").exists()
        val scipyOk = File(alpineDir, "usr/lib/python3.11/site-packages/scipy").exists() ||
            File(alpineDir, "usr/lib/python3.12/site-packages/scipy").exists() ||
            File(alpineDir, "tilawa_numpy/scipy").exists()
        if (!numpyOk || !scipyOk) return false  // S148: scipy required by v11.2''',
    '''        // S182: a system-site-packages numpy (rare, bundled-in-image case) is
        // still trusted by existence — only the tilawa_numpy/ pip-installed
        // path is the one that can end up partially-written, so only that
        // path needs the stronger .numpy_verified marker check (S179/S182).
        val numpySystemOk = File(alpineDir, "usr/lib/python3.11/site-packages/numpy").exists() ||
            File(alpineDir, "usr/lib/python3.12/site-packages/numpy").exists()
        val numpyOk = numpySystemOk || File(alpineDir, ".numpy_verified").exists()
        val scipySystemOk = File(alpineDir, "usr/lib/python3.11/site-packages/scipy").exists() ||
            File(alpineDir, "usr/lib/python3.12/site-packages/scipy").exists()
        val scipyOk = scipySystemOk || File(alpineDir, ".numpy_verified").exists()
        if (!numpyOk || !scipyOk) return false  // S148: scipy required by v11.2''',
    'E2: isSetupComplete() now requires the .numpy_verified marker for the tilawa_numpy path')

STAMP.write_text('S182\n')
print('\n✅  patch_s182 done')
print('   git add patch_android.py')
print('   git commit -m "S182: isSetupComplete() now requires a verified numpy install,')
print('   so a broken tilawa_numpy/ from before S179 actually gets repaired"')
print('   git push')
print()
print('NOTE: anyone with an already-broken local setup (your exact screenshots)')
print('will see isSetupComplete() flip to false after updating, "Start Setup"')
print('will re-run, and S179\'s verify+retry logic will repair tilawa_numpy/ and')
print('write the marker — no manual uninstall needed.')
