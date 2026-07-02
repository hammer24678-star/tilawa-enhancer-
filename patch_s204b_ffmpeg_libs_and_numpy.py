#!/usr/bin/env python3
"""patch_s204b — BUG-2: ffmpeg missing libs (rc=127), BUG-3: numpy pip flag"""
import sys, subprocess
from pathlib import Path

REPO = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
if not (REPO / 'lib').exists():
    print(f'ERROR: lib/ not found in {REPO}'); sys.exit(1)

STAMP = REPO / '.patch_s204b_done'
if STAMP.exists():
    print('patch_s204b already applied — delete .patch_s204b_done to re-run'); sys.exit(0)

def rep(old, new, tag, src, required=True):
    p = REPO / src
    if not p.exists():
        if required: print(f'  FAIL  {tag}: {src} missing'); sys.exit(1)
        print(f'  SKIP  {tag} (file missing)'); return
    text = p.read_text(encoding='utf-8')
    if old not in text:
        if new.split('#')[0].strip() in text or new in text:
            print(f'  SKIP  {tag} (already applied)'); return
        if required: print(f'  FAIL  {tag}: anchor not found in {src}'); sys.exit(1)
        print(f'  WARN  {tag}: anchor not found — skipped'); return
    p.write_text(text.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

print(f'\n── S204b  [repo: {REPO}] ──\n')

# ── BUG-2: build.yml — ffmpeg missing libavfilter/libswscale/libpostproc ─────
# python-env.tar.gz bundles ffmpeg binary but not all libs it needs.
# Result: "Error relocating ffmpeg: avfilter_*: symbol not found" (rc=127).
rep(
    '/usr/lib/libavutil.so.* /usr/lib/libswresample.so.* \\\\',
    '/usr/lib/libavutil.so.* /usr/lib/libswresample.so.* \\\\\n'
    '            /usr/lib/libavfilter.so.* /usr/lib/libswscale.so.* /usr/lib/libpostproc.so.* \\\\  # S204b',
    'BUG-2: add libavfilter/libswscale/libpostproc to python-env tar',
    '.github/workflows/build.yml',
    required=True,
)

# ── BUG-3: numpy pip fallback missing --break-system-packages ────────────────
OLD_PIP = '"pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1")'
NEW_PIP = '"pip install --quiet --no-cache-dir --break-system-packages --target /tilawa_numpy numpy scipy 2>&1")  # S204b'

p = REPO / 'patch_android.py'
text = p.read_text(encoding='utf-8')
count = text.count(OLD_PIP)
if count == 0:
    if '--break-system-packages' in text:
        print('  SKIP  BUG-3: numpy pip flag (already applied)')
    else:
        print('  WARN  BUG-3: numpy pip anchor not found — skipped')
else:
    p.write_text(text.replace(OLD_PIP, NEW_PIP), encoding='utf-8')
    print(f'  OK    BUG-3: numpy pip --break-system-packages ({count} occurrence(s) patched)')

# ── commit ───────────────────────────────────────────────────────────────────
r = subprocess.run(
    ['git', '-C', str(REPO), 'add', 'patch_android.py', '.github/workflows/build.yml'],
    capture_output=True, text=True)
if r.returncode == 0:
    cr = subprocess.run(
        ['git', '-C', str(REPO), 'commit', '-m',
         'S204b: ffmpeg missing libs (rc=127) + numpy pip --break-system-packages'],
        capture_output=True, text=True)
    print(f'\n  git commit: {cr.stdout.strip() or cr.stderr.strip()}')
else:
    print(f'\n  git warning: {r.stderr.strip()}')

STAMP.write_text('ok\n')
print('''
Done — S204b applied.

  BUG-1  Already fixed in your file (lines 823-833) — no action needed
  BUG-2  libavfilter/libswscale/libpostproc added to python-env tar
  BUG-3  pip numpy fallback now uses --break-system-packages

  Next:  git push  →  wait for CI APK rebuild  →  reinstall on device
''')
