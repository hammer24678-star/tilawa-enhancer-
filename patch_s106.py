#!/usr/bin/env python3
"""
patch_s106.py
=============
S106: three critical fixes for local engine:
1. PROOT_TMP_DIR: use dataDir/proot-tmp not codeCacheDir in runEngine
2. numpy: install to fixed /tilawa_numpy path during setup, use as PYTHONPATH
3. ref audio: extract BEFORE writing setup_complete flag
"""
from pathlib import Path
from datetime import datetime

pa = Path('patch_android.py')
print(f'\n{"="*56}\n  patch_s106  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*56}')

t = pa.read_text(encoding='utf-8')

fixes = 0

# ── Fix 1: PROOT_TMP_DIR in runEngine — use dataDir not codeCacheDir ─────────
old1 = '                val prootTmp = context.codeCacheDir.also { it.mkdirs() }\n            environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath\n            if (prootLoader.exists()) environment()["PROOT_LOADER"] = prootLoader.absolutePath\n            }.start()'
new1 = '                val prootTmp = File(dataDir, "proot-tmp").also { it.mkdirs() }  // S106\n                environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath\n                if (prootLoader.exists()) environment()["PROOT_LOADER"] = prootLoader.absolutePath\n            }.start()'
if old1 in t:
    t = t.replace(old1, new1, 1); fixes += 1; print('  OK  Fix1: proot tmp → dataDir/proot-tmp in runEngine')
else:
    # Try variant
    old1b = '                val prootTmp = context.codeCacheDir.also { it.mkdirs() }\n                environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath\n                if (prootLoader.exists()) environment()["PROOT_LOADER"] = prootLoader.absolutePath\n            }.start()'
    new1b = '                val prootTmp = File(dataDir, "proot-tmp").also { it.mkdirs() }  // S106\n                environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath\n                if (prootLoader.exists()) environment()["PROOT_LOADER"] = prootLoader.absolutePath\n            }.start()'
    if old1b in t:
        t = t.replace(old1b, new1b, 1); fixes += 1; print('  OK  Fix1b: proot tmp → dataDir/proot-tmp in runEngine')
    else:
        print('  XX  Fix1: proot tmp anchor not found')
        # Show what's there
        idx = t.find('codeCacheDir')
        if idx != -1:
            print(f'  codeCacheDir context: {repr(t[idx-20:idx+80])}')

# ── Fix 2: numpy install to fixed /tilawa_numpy during setup ─────────────────
old2 = '        // S102: install numpy/scipy via pip to ensure correct Python version path\n        if (!File(alpineDir, "usr/lib/python3/dist-packages/numpy").exists() &&\n            !File(alpineDir, "usr/lib/python3.11/site-packages/numpy").exists() &&\n            !File(alpineDir, "usr/lib/python3.12/site-packages/numpy").exists()) {\n            progress(79, "Installing numpy + scipy via pip…")\n            runProot(listOf("/bin/sh", "-c",\n                "pip3 install --quiet --no-cache-dir numpy scipy 2>&1 || " +\n                "pip install --quiet --no-cache-dir numpy scipy 2>&1"), timeoutMin=15)\n        }'
new2 = '        // S106: install numpy/scipy to fixed known path — no Python version guessing\n        val numpyTarget = File(alpineDir, "tilawa_numpy")\n        if (!File(numpyTarget, "numpy").exists()) {\n            progress(79, "Installing numpy + scipy (one-time ~2 min)…")\n            numpyTarget.mkdirs()\n            runProot(listOf("/bin/sh", "-c",\n                "pip3 install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1 || " +\n                "pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1"),\n                timeoutMin=20)\n        }'
if old2 in t:
    t = t.replace(old2, new2, 1); fixes += 1; print('  OK  Fix2: numpy install to fixed /tilawa_numpy path')
else:
    print('  XX  Fix2: numpy setup anchor not found — checking for simpler version')
    old2b = '        progress(79, "Installing numpy + scipy via pip…")\n            runProot(listOf("/bin/sh", "-c",\n                "pip3 install --quiet --no-cache-dir numpy scipy 2>&1 || " +\n                "pip install --quiet --no-cache-dir numpy scipy 2>&1"), timeoutMin=15)\n        }'
    if old2b in t:
        print('  XX  Found partial match — manual fix needed')
    # Try finding and replacing the whole numpy block
    import re
    m = re.search(r'// S102.*?}\n', t, re.DOTALL)
    if m:
        old2c = m.group(0)
        new2c = '        // S106: install numpy/scipy to fixed known path\n        val numpyTarget = File(alpineDir, "tilawa_numpy")\n        if (!File(numpyTarget, "numpy").exists()) {\n            progress(79, "Installing numpy + scipy (one-time ~2 min)…")\n            numpyTarget.mkdirs()\n            runProot(listOf("/bin/sh", "-c",\n                "pip3 install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1 || " +\n                "pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1"),\n                timeoutMin=20)\n        }\n'
        t = t.replace(old2c, new2c, 1); fixes += 1
        print('  OK  Fix2 (regex): numpy install to fixed /tilawa_numpy path')

# ── Fix 3: PYTHONPATH → /tilawa_numpy ────────────────────────────────────────
# Find and replace ALL PYTHONPATH env settings
import re
old3_pattern = r'environment\(\)\["PYTHONPATH"\] = "[^"]*"'
matches3 = re.findall(old3_pattern, t)
if matches3:
    t = re.sub(old3_pattern,
        'environment()["PYTHONPATH"] = "/tilawa_numpy"  // S106',
        t)
    fixes += 1
    print(f'  OK  Fix3: PYTHONPATH → /tilawa_numpy (replaced {len(matches3)} occurrence(s))')
else:
    # Add PYTHONPATH after HOME
    old3b = '                environment()["HOME"] = "/root"\n                environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"'
    new3b = '                environment()["HOME"] = "/root"\n                environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"\n                environment()["PYTHONPATH"] = "/tilawa_numpy"  // S106'
    if old3b in t:
        t = t.replace(old3b, new3b, 1); fixes += 1
        print('  OK  Fix3b: PYTHONPATH added after HOME')
    else:
        print('  XX  Fix3: PYTHONPATH anchor not found')

# ── Fix 4: ref audio extraction — ensure it happens even if setup was done ───
# The ref audio should be re-extracted on every engine run if files missing
old4 = '            refAudioDir.mkdirs()  // S89: ensure exists before proot bind\n            val refMp3 = File(refAudioDir, "ref_araf_1425h.mp3")'
new4 = '''            refAudioDir.mkdirs()
            // S106: re-extract ref audio if missing (in case setup ran before S105)
            listOf("ref_araf_1425h.mp3", "ref_fath_1425h.mp3", "ref_fatir_1425h.mp3").forEach { rf ->
                val dest = File(refAudioDir, rf)
                if (!dest.exists() || dest.length() < 10_000) {
                    try { context.assets.open("flutter_assets/assets/reference_audio/$rf")
                        .use { it.copyTo(java.io.FileOutputStream(dest)) }
                    } catch (_: Exception) {
                        try { context.assets.open("assets/reference_audio/$rf")
                            .use { it.copyTo(java.io.FileOutputStream(dest)) }
                        } catch (_: Exception) {} }
                }
            }
            val refMp3 = File(refAudioDir, "ref_araf_1425h.mp3")'''
if old4 in t:
    t = t.replace(old4, new4, 1); fixes += 1
    print('  OK  Fix4: ref audio re-extracted before every engine run')
else:
    print('  XX  Fix4: ref audio anchor not found')

pa.write_text(t, encoding='utf-8')
print(f'\n{"="*56}\n  {fixes} fixes applied\n{"="*56}')
if fixes >= 3:
    print('\n  git add -A && git commit -m "S106: proot-tmp + numpy fixed path + ref audio on run" && git push origin master --force -v\n')
else:
    print('\n  Some fixes failed — paste output back to Claude\n')
