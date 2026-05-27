#!/usr/bin/env python3
"""
patch_s89_pyenv.py
==================
S89: add download fallback for python-env.tar.gz in patch_android.py.
The asset is 135MB — too big for git. CI uploads it to GitHub Releases.
App tries asset first, then downloads from release if missing.
"""
from pathlib import Path
from datetime import datetime

pa = Path.home() / 'tilawa-enhancer/patch_android.py'
wf = Path.home() / 'tilawa-enhancer/.github/workflows/build.yml'

print(f'\n{"="*56}\n  patch_s89_pyenv  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*56}')

if not pa.exists():
    print('  XX  patch_android.py not found'); exit(1)

txt = pa.read_text(encoding='utf-8')

if '// S89-PYENV' in txt:
    print('  OK  S89-PYENV already applied'); exit(0)

# ── Fix 1: python-env extraction with download fallback ──────────────────────
OLD = '''\
        // 3. Python + ffmpeg — bundled in APK assets/alpine/
        if (!File(alpineDir, "usr/bin/python3").exists()) {
            progress(38, "Extracting Python + ffmpeg (bundled)…")
            val tmp = File(dataDir, "python-env.tar.gz")
            context.assets.open("alpine/python-env.tar.gz")
                .use { it.copyTo(FileOutputStream(tmp)) }
            extractTarGz(tmp, alpineDir)
            tmp.delete()
        }
        progress(78, "Python + ffmpeg ready")'''

NEW = '''\
        // 3. Python + ffmpeg — try bundled asset, else download from release  // S89-PYENV
        if (!File(alpineDir, "usr/bin/python3").exists()) {
            val tmp = File(dataDir, "python-env.tar.gz")
            var pyOk = false
            // Try bundled asset first
            try {
                progress(38, "Extracting Python + ffmpeg (bundled)…")
                context.assets.open("alpine/python-env.tar.gz")
                    .use { it.copyTo(FileOutputStream(tmp)) }
                pyOk = true
            } catch (_: Exception) {}
            // Fallback: download from GitHub Release
            if (!pyOk) {
                progress(38, "Downloading Python + ffmpeg (~135 MB, one-time)…")
                val pyUrl = "https://github.com/hammer24678-star/tilawa-enhancer-/releases/download/latest/python-env.tar.gz"
                download(pyUrl, tmp, "Python env", 38, 75)
                pyOk = tmp.exists() && tmp.length() > 1_000_000
            }
            if (!pyOk) throw IOException("python-env.tar.gz unavailable — check internet connection")
            progress(75, "Extracting Python + ffmpeg…")
            extractTarGz(tmp, alpineDir)
            tmp.delete()
        }
        progress(78, "Python + ffmpeg ready")'''

if OLD in txt:
    txt = txt.replace(OLD, NEW, 1)
    print('  OK  python-env fallback download added')
else:
    print('  XX  python-env anchor not found')
    idx = txt.find('python-env.tar.gz')
    if idx != -1:
        print('  Snippet around python-env:')
        print(txt[max(0,idx-100):idx+300])
    exit(1)

pa.write_text(txt, encoding='utf-8')
print('  OK  patch_android.py saved')

# ── Fix 2: verify workflow already uploads python-env to release ──────────────
if wf.exists():
    wf_txt = wf.read_text(encoding='utf-8')
    if 'python-env.tar.gz' in wf_txt:
        print('  OK  build.yml already uploads python-env.tar.gz')
    else:
        print('  XX  build.yml does NOT upload python-env.tar.gz — add it manually')
else:
    print('  XX  build.yml not found')

print(f'\n{"="*56}\n  Done\n{"="*56}')
print('\n  git add -A && git commit -m "S89: python-env download fallback from GitHub Release" && git push origin revert-to-s87:master --force\n')
