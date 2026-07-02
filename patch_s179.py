#!/usr/bin/env python3
"""
patch_s179.py — S179: fix missing engine_safaa_v4.py extraction + unreliable
                       numpy/scipy install (the 3 new errors after S178)

Root causes found (from the 3 screenshots, all post-S178):

  BUG 1 (screenshot 1 — "Engine failed (rc=2): can't open file
         '/engines/engine_safaa_v4.py': No such file or directory")
    runEngine() maps v11.0 -> "engine_safaa_v4.py" (S172), but
    extractEngines() — the function that actually copies engine .py files
    from APK assets into the proot-visible engines/ dir — still lists the
    OLD filename "engine_safaa_v3_fixed.py". engine_safaa_v4.py is never
    extracted, so /engines/engine_safaa_v4.py never exists on disk and every
    v11.0 (الصفاء) run fails immediately with rc=2.
      E1  patch_android.py (LocalEngineRunner.kt template) — extractEngines()
          filename list: v3_fixed -> v4

  BUG 2 (screenshots 2 & 3 — "Engine failed (rc=1): pip install numpy scipy"
         then "ImportError: ... you should not try to import numpy from its
         source directory")
    The numpy/scipy "install" step only checks whether
    tilawa_numpy/numpy *as a directory* exists — not whether it's a real,
    working install. pip3/pip install --target /tilawa_numpy can fail
    partway (no network in proot, interrupted, etc.) and still leave a
    partial/broken numpy/ folder behind. Once that folder exists,
    numpyOk/isSetupComplete report "fine" forever, so the broken install is
    never retried — every later engine run hits that half-written package
    and numpy's own safety check refuses to import from what looks like a
    source checkout.
      E2  patch_android.py (LocalEngineRunner.kt template) — after pip
          install, verify with a real `python3 -c "import numpy, scipy"`
          probe; if it fails, wipe tilawa_numpy and retry once; if it still
          fails, throw a clear error instead of silently continuing.

  BUG 3 ("our audio editor is completely broken")
    audio_editor_screen.dart's _export() builds the ffmpeg -i argument
    straight from the raw file_picker path (_filePath!) and passes that same
    raw path as 'inputPath' to runProotCmd for bind-mounting. But S128
    (in runEngine(), the OTHER place a picked file is fed to proot) already
    documented why this doesn't work: file_picker paths frequently resolve
    through /data/user/0/... symlinks that proot's bind-mount can't follow,
    so ffmpeg inside the chroot can't see the file even with S178's bind
    fix. runEngine() works around this by copying the picked file into
    cacheDir first (a real, directly-bindable path) — _export() never got
    the same treatment, so editor exports fail (or silently misbehave)
    regardless of the S178 bind-mount fix.
      E3  lib/screens/audio_editor_screen.dart — copy the picked file into
          a temp dir before building the ffmpeg command, same pattern as
          runEngine()'s safeInput.

Run from repo root: python3 patch_s179.py
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

STAMP = Path('.patch_s179_done')
if STAMP.exists():
    print('patch_s179: already applied — delete .patch_s179_done to re-run'); sys.exit(0)

print('\n── S179: fix missing engine_safaa_v4.py + unreliable numpy/scipy install ──')

# ════════════════════════════════════════════════════════════════════════════
# E1 — extractEngines(): was still packaging engine_safaa_v3_fixed.py;
#      runEngine() needs engine_safaa_v4.py (S172). Extract the v4 file
#      (also keep v3_fixed around in case anything legacy still refs it).
# ════════════════════════════════════════════════════════════════════════════
patch('patch_android.py',
    '''        listOf("engine_safaa_v3_fixed.py","engine_itiqan_v6_official.py", // S155: was true_engine_itiqan_v2_fixed
               "engine_isteidad_v21.py","idrak_text_v2.py","miraat_ref_v2.py","hakim_gen_v2.py","naqaa_v1_tested.py","bayan_ve_v2fix.py",
               "noor_v5.py","ihyaa_ve.py").forEach { name ->  // S156: v7-v10 are server-only''',
    '''        listOf("engine_safaa_v4.py","engine_safaa_v3_fixed.py","engine_itiqan_v6_official.py", // S179: v4 is what runEngine() actually invokes (S172) — v3_fixed was never replaced here, so /engines/engine_safaa_v4.py never existed on disk (rc=2)
               "engine_isteidad_v21.py","idrak_text_v2.py","miraat_ref_v2.py","hakim_gen_v2.py","naqaa_v1_tested.py","bayan_ve_v2fix.py",
               "noor_v5.py","ihyaa_ve.py").forEach { name ->  // S156: v7-v10 are server-only''',
    'E1: extractEngines() now packages engine_safaa_v4.py')

# ════════════════════════════════════════════════════════════════════════════
# E2 — numpy/scipy install: verify the install actually works before trusting
#      it. Wipe + retry once on failure; throw a clear error if it still
#      doesn't work, instead of letting the engine hit a broken numpy later.
# ════════════════════════════════════════════════════════════════════════════
patch('patch_android.py',
    '''        val numpyTarget = File(alpineDir, "tilawa_numpy")
        if (!File(numpyTarget, "numpy").exists() || !File(numpyTarget, "scipy").exists()) { // S148
            progress(79, "Installing numpy + scipy (one-time ~2 min)…")
            numpyTarget.mkdirs()
            runProot(listOf("/bin/sh", "-c",
                "pip3 install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1 || " +
                "pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1"),
                timeoutMin=20)
        }''',
    '''        val numpyTarget = File(alpineDir, "tilawa_numpy")
        // S179: a dir existing doesn't mean the install is good — pip can fail
        // partway (no network, interrupted) and leave a broken numpy/ folder
        // that "exists" forever after, so it's never retried and every engine
        // run hits a half-written package ("import numpy from its source
        // directory" ImportError). Probe with a real import, not just exists().
        fun numpyWorks(): Boolean {
            if (!File(numpyTarget, "numpy").exists() || !File(numpyTarget, "scipy").exists()) return false
            val probe = runProot(listOf("/usr/bin/python3", "-c", "import numpy, scipy"), timeoutMin=2)
            return probe.first == 0
        }
        if (!numpyWorks()) {
            progress(79, "Installing numpy + scipy (one-time ~2 min)…")
            numpyTarget.mkdirs()
            runProot(listOf("/bin/sh", "-c",
                "pip3 install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1 || " +
                "pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1"),
                timeoutMin=20)
            if (!numpyWorks()) {
                // S179: one clean retry — wipe whatever partial/broken state pip left behind
                progress(79, "Retrying numpy + scipy install (previous attempt was broken)…")
                numpyTarget.deleteRecursively()
                numpyTarget.mkdirs()
                runProot(listOf("/bin/sh", "-c",
                    "pip3 install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1 || " +
                    "pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1"),
                    timeoutMin=20)
                if (!numpyWorks()) {
                    throw IOException("numpy/scipy install failed — check internet connection and retry setup")
                }
            }
        }''',
    'E2: numpy/scipy install now verified + retried instead of trusted on dir existence')

# ════════════════════════════════════════════════════════════════════════════
# E3 — audio_editor_screen.dart: _export() fed the raw file_picker path
#      straight to ffmpeg/runProotCmd. Copy it into a temp dir first (same
#      fix runEngine() already uses for the same reason — S128), so proot's
#      bind-mount always points at a real, directly-bindable path.
# ════════════════════════════════════════════════════════════════════════════
patch('lib/screens/audio_editor_screen.dart',
    '''      final ss  = (_trimStart * _durationSec).toStringAsFixed(3);
      final dur = ((_trimEnd - _trimStart) * _durationSec).toStringAsFixed(3);''',
    '''      // S179: copy the picked file into a temp dir before handing it to
      // ffmpeg/proot — file_picker paths often resolve through
      // /data/user/0/... symlinks that proot's bind-mount can't follow
      // (same root cause runEngine() already works around for engine runs,
      // S128). Without this, ffmpeg can't see the source file inside the
      // chroot even with S178's bind-mount fix.
      final tmpDir = await getTemporaryDirectory();
      final safeInput = File(
          '${tmpDir.path}/tilawa_edit_input_${DateTime.now().millisecondsSinceEpoch}.${_filePath!.split('.').last}');
      await File(_filePath!).copy(safeInput.path);
      final realInput = safeInput.path;

      final ss  = (_trimStart * _durationSec).toStringAsFixed(3);
      final dur = ((_trimEnd - _trimStart) * _durationSec).toStringAsFixed(3);''',
    'E3a: audio_editor_screen copies picked file to a proot-safe temp path')

patch('lib/screens/audio_editor_screen.dart',
    '''      final cmd = 'ffmpeg -y -ss $ss -i "${_filePath!}" -t $dur '
          '-af $afStr -acodec $codec $bitrateFlag "$out"';''',
    '''      final cmd = 'ffmpeg -y -ss $ss -i "$realInput" -t $dur '
          '-af $afStr -acodec $codec $bitrateFlag "$out"';''',
    'E3b: ffmpeg -i now uses the safe-copied input path')

patch('lib/screens/audio_editor_screen.dart',
    '''      final r = await _ch.invokeMethod<Map>('runProotCmd', {
        'cmd':        cmd,
        'inputPath':  _filePath!,
        'outputPath': out,
        'timeoutMin': 10,
      });  // S161/S178''',
    '''      final r = await _ch.invokeMethod<Map>('runProotCmd', {
        'cmd':        cmd,
        'inputPath':  realInput,
        'outputPath': out,
        'timeoutMin': 10,
      });  // S161/S178/S179''',
    'E3c: runProotCmd bind-mount now uses the safe-copied input path')

STAMP.write_text('S179\n')
print('\n✅  patch_s179 done')
print('   git add patch_android.py lib/screens/audio_editor_screen.dart')
print('   git commit -m "S179: E1 fix missing engine_safaa_v4.py extraction (rc=2),')
print('   E2 verify+retry numpy/scipy install instead of trusting dir existence,')
print('   E3 fix AudioLab editor feeding unresolvable file_picker path to proot"')
print('   git push')
print()
print('NOTE: this only edits patch_android.py (the CI-authoritative template).')
print('`flutter create` wipes android/ every build, then patch_android.py')
print('regenerates LocalEngineRunner.kt from it — that regenerated file is what')
print('actually ships, so no separate .kt edit is needed here (unlike S178 E4,')
print('which also had a standalone-.kt code path to patch).')
print()
print('NOTE: anyone with an already-broken alpine-318/ (missing engine_safaa_v4.py')
print('and/or a broken tilawa_numpy/) needs to reinstall the updated APK — the')
print('existing setup_complete checks will detect the missing file / failed import')
print('and re-run extraction/install on next "Start Setup".')
