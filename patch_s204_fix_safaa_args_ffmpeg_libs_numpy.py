#!/usr/bin/env python3
"""patch_s204 — fix safaa args (rc=2), ffmpeg missing libs (rc=127), numpy pip"""
import sys, subprocess
from pathlib import Path

REPO = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
if not (REPO / 'lib').exists():
    print(f'ERROR: lib/ not found in {REPO}'); sys.exit(1)

STAMP = REPO / '.patch_s204_done'
if STAMP.exists():
    print('patch_s204 already applied — delete .patch_s204_done to re-run'); sys.exit(0)

def rep(old, new, tag, src, required=True):
    p = REPO / src
    if not p.exists():
        if required: print(f'  FAIL  {tag}: {src} missing'); sys.exit(1)
        print(f'  SKIP  {tag} (file missing)'); return
    text = p.read_text(encoding='utf-8')
    if old not in text:
        if new in text:
            print(f'  SKIP  {tag} (already applied)'); return
        if required: print(f'  FAIL  {tag}: anchor not found in {src}'); sys.exit(1)
        print(f'  WARN  {tag}: anchor not found — skipped'); return
    p.write_text(text.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

print(f'\n── S204  [repo: {REPO}] ──\n')

# ── BUG-1: patch_android.py template — safaa gets wrong args (rc=2) ──────────
# The Kotlin template always passes -i/-o/--iterations/--ref to all engines.
# Safaa uses positional args (input output) and has no --ref/--iterations flags.
# Note: the template stores Kotlin strings as \" (escaped quotes).
rep(
    r'''                \"-i\", actualInput, \"-o\", outputPath,
                \"--iterations\", \"3\",
            )
            // S118: pass all 3 reference files
            listOf(\"ref_araf_1425h.mp3\", \"ref_fath_1425h.mp3\", \"ref_fatir_1425h.mp3\").forEach { rf ->
                val refFile = File(refAudioDir, rf)
                if (refFile.exists()) cmd += listOf(\"--ref\", \"/reference_audio/$rf\")
            }''',

    r'''                // S204-BUG-1: safaa uses positional args, no -i/-o/--iterations/--ref
                *( if (script.startsWith(\"engine_safaa\"))
                    arrayOf(actualInput, outputPath)
                else
                    arrayOf(\"-i\", actualInput, \"-o\", outputPath, \"--iterations\", \"3\")),
            )
            // S118/S204: safaa has no --ref flag — skip for safaa engines
            if (!script.startsWith(\"engine_safaa\")) {
                listOf(\"ref_araf_1425h.mp3\", \"ref_fath_1425h.mp3\", \"ref_fatir_1425h.mp3\").forEach { rf ->
                    val refFile = File(refAudioDir, rf)
                    if (refFile.exists()) cmd += listOf(\"--ref\", \"/reference_audio/$rf\")
                }
            }''',

    'BUG-1: safaa positional args + guard --ref in patch_android.py template',
    'patch_android.py',
    required=True,
)

# ── BUG-2: build.yml — ffmpeg missing libavfilter/libswscale/libpostproc ─────
# python-env.tar.gz bundles ffmpeg binary but not the filter/scaler libs.
# Result: "Error relocating ffmpeg: avfilter_*: symbol not found" (rc=127).
rep(
    '/usr/lib/libavutil.so.* /usr/lib/libswresample.so.* \\\\',
    '/usr/lib/libavutil.so.* /usr/lib/libswresample.so.* \\\\\n'
    '            /usr/lib/libavfilter.so.* /usr/lib/libswscale.so.* /usr/lib/libpostproc.so.* \\\\',
    'BUG-2: add libavfilter/libswscale/libpostproc to python-env tar',
    '.github/workflows/build.yml',
    required=True,
)

# ── BUG-3: numpy pip fallback missing --break-system-packages ────────────────
# Python 3.12 Alpine refuses plain pip install without this flag.
# There are two occurrences — patch both.
OLD_PIP = '"pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1")'
NEW_PIP = '"pip install --quiet --no-cache-dir --break-system-packages --target /tilawa_numpy numpy scipy 2>&1")  # S204-BUG-3'

text = (REPO / 'patch_android.py').read_text(encoding='utf-8')
count = text.count(OLD_PIP)
if count == 0:
    if NEW_PIP.split('  #')[0] in text:
        print('  SKIP  BUG-3: numpy pip flag (already applied)')
    else:
        print('  WARN  BUG-3: numpy pip anchor not found — skipped')
else:
    text = text.replace(OLD_PIP, NEW_PIP)
    (REPO / 'patch_android.py').write_text(text, encoding='utf-8')
    print(f'  OK    BUG-3: numpy pip --break-system-packages ({count} occurrence(s))')

# ── commit ───────────────────────────────────────────────────────────────────
r = subprocess.run(
    ['git', '-C', str(REPO), 'add', 'patch_android.py', '.github/workflows/build.yml'],
    capture_output=True, text=True)
if r.returncode == 0:
    subprocess.run(
        ['git', '-C', str(REPO), 'commit', '-m',
         'S204: fix safaa args (rc=2), ffmpeg libs (rc=127), numpy pip'],
        capture_output=True, text=True)
    print('\n  git commit done')
else:
    print(f'\n  git warning: {r.stderr.strip()}')

STAMP.write_text('ok\n')
print('''
Done — S204 applied.

  BUG-1  Safaa now gets positional args in template (no more rc=2)
  BUG-2  libavfilter/libswscale/libpostproc added to ffmpeg tar (no more rc=127)
  BUG-3  pip numpy fallback uses --break-system-packages (Python 3.12 fix)

  Next:  git push  →  wait for CI  →  reinstall APK  →  re-run Setup on device
''')
