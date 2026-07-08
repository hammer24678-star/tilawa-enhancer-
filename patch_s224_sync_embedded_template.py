#!/usr/bin/env python3
"""
patch_s224_sync_embedded_template.py — S224

BUG FOUND (real, currently live in your repo):

  patch_android.py embeds a full copy of LocalEngineRunner.kt as the
  `_LOCAL_RUNNER_KT` string. It's only written to disk on a fresh
  checkout — the S202 guard skips the write if the .kt file already
  exists. That's correct in principle, but the embedded copy was never
  updated when S223 landed (commit 6b55f0c). The live .kt file has the
  S223 fixes; the embedded template inside patch_android.py still has
  the pre-S223 code:

    - numpyWorks() trusts hasPySysPackage() dir-existence for the
      "system" path instead of always running the real proot import
      probe (BUG-A)
    - isSetupComplete() accepts tilawa_numpy/{numpy,scipy} existing on
      disk instead of gating on the real-import-verified
      .numpy_verified marker only (BUG-A)
    - extractTarGz()'s symlink case still does a bare
      `catch (_: Exception) {}` — no queue/second-pass retry for
      dropped .so version symlinks (BUG-B)
    - install order/error message is still the old
      pip -> pip-retry -> generic "check internet connection" (BUG-C)

  Net effect: any FRESH checkout — a new device, a clean CI runner, or
  LocalEngineRunner.kt getting deleted and regenerated — silently
  resurrects all three S223 bugs even though the file you're looking
  at right now is fixed. This is the same class of bug as S207/S208
  (embedded template drifting from the live file).

FIX: read the live, already-S223-fixed LocalEngineRunner.kt straight
off disk and use it to replace the stale _LOCAL_RUNNER_KT string in
patch_android.py, so the two can't silently diverge again.

Usage: python3 patch_s224_sync_embedded_template.py /path/to/tilawa-enhancer
"""
import re
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
PA = REPO / 'patch_android.py'
LE = REPO / 'android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt'
STAMP = REPO / '.patch_s224_sync_embedded_template_done'

if STAMP.exists():
    print('patch_s224 already applied — delete .patch_s224_sync_embedded_template_done to re-run')
    sys.exit(0)
if not PA.exists():
    print(f'ERROR: patch_android.py not found in {REPO}'); sys.exit(1)
if not LE.exists():
    print(f'ERROR: live LocalEngineRunner.kt not found at {LE}'); sys.exit(1)

live_kt = LE.read_text(encoding='utf-8').rstrip('\n')

if 'S223' not in live_kt:
    print('WARN: live LocalEngineRunner.kt has no "S223" marker in it.')
    print('      Refusing to sync — make sure patch_s223 has actually been')
    print('      applied to the live .kt file before running this.')
    sys.exit(1)

if '"""' in live_kt:
    print('ERROR: live .kt contains a literal triple-quote — cannot safely')
    print('       embed it as a python r"""...""" string. Aborting.')
    sys.exit(1)

src = PA.read_text(encoding='utf-8')
m = re.search(r'_LOCAL_RUNNER_KT = r"""(.*?)\n"""\n', src, re.DOTALL)
if not m:
    print('FAIL: could not find the _LOCAL_RUNNER_KT = r"""..."""  block')
    print('      in patch_android.py — has its structure changed?')
    sys.exit(1)

old_block = m.group(0)
old_template = m.group(1)

if old_template.strip() == live_kt.strip():
    print('SKIP: embedded template already matches the live .kt file — nothing to sync')
    STAMP.write_text('ok\n')
    sys.exit(0)

new_block = f'_LOCAL_RUNNER_KT = r"""{live_kt}\n"""\n'
src = src.replace(old_block, new_block, 1)
PA.write_text(src, encoding='utf-8')
STAMP.write_text('ok\n')

print('OK  patch_android.py\'s embedded _LOCAL_RUNNER_KT synced to the')
print('    live, S223-fixed LocalEngineRunner.kt.')
print()
print('  git add patch_android.py')
print('  git commit -m "S224: sync embedded LocalEngineRunner.kt template to live')
print('  S223-fixed file — fresh checkouts / clean CI no longer resurrect the')
print('  numpy/scipy setup bugs (numpyWorks dir-trust, isSetupComplete gate,')
print('  dropped .so symlinks)"')
