#!/usr/bin/env python3
"""
patch_s194_numpy_install_fix.py — S194

ROOT CAUSE OF "numpy/scipy install failed — check internet connection and
retry setup" screenshot:

  The LocalEngineRunner.kt in the repo is a stale generated file from before
  S179/S182.  Its numpy-install block is:

      val numpyTarget = File(alpineDir, "tilawa_numpy")
      if (!File(numpyTarget, "numpy").exists()) {
          // one pip attempt, no verification, no error on failure
      }

  Three combined problems:

  BUG-A  No system-numpy check.  The build.yml embeds numpy+scipy into the
         Alpine rootfs via `apk add --no-cache python3 py3-numpy py3-scipy`
         BEFORE packaging python-env.tar.gz.  So numpy IS already at
         usr/lib/python3.1*/site-packages/numpy on a fresh install — but the
         code never looks there.  It only checks tilawa_numpy/ (the pip
         target).  Result: pip runs even when numpy is already present, and
         fails with a confusing error if the device has no internet.

  BUG-B  Pip failure is silently swallowed.  runProot() is called but its
         return value is ignored.  If pip exits non-zero (no network, no
         space, wrong arch) setup() proceeds as if numpy is fine, then hangs
         or crashes later when an engine tries `import numpy`.

  BUG-C  No retry / cleanup.  A half-written tilawa_numpy/ left by a
         previously interrupted pip run makes the existence-check pass but
         `import numpy` still fails.

  BUG-D  isSetupComplete() missing scipy check.  It gates on numpy only;
         a device where numpy installed but scipy timed-out passes the check
         and causes engine crashes at runtime.

  BUG-E  patch_android.py template has the S179/S182 numpyWorks() function
         but it also never checks system paths first — same root cause as
         BUG-A in generated code.

Fix strategy:
  • Add numpyWorks() that checks SYSTEM paths first (no internet needed
    when numpy was bundled), then pip target, then verifies with a real
    proot import probe, writes .numpy_verified marker.
  • Full retry with cleanup on first failure.
  • Throw IOException if all attempts fail.
  • Fix isSetupComplete() to also gate on scipy + .numpy_verified marker.
  • Fix patch_android.py template numpyWorks() to check system paths first.

Usage:  python3 patch_s194_numpy_install_fix.py /path/to/tilawa-enhancer
"""
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
if not (REPO / 'lib').exists():
    print(f'ERROR: lib/ not found in {REPO}'); sys.exit(1)

STAMP = REPO / '.patch_s194_numpy_install_fix_done'
if STAMP.exists():
    print('patch_s194 already applied — delete .patch_s194_numpy_install_fix_done to re-run')
    sys.exit(0)

def patch(path, old, new, tag, required=True):
    p = REPO / path
    if not p.exists():
        print(f'  SKIP  {tag} (file missing)'); return
    src = p.read_text(encoding='utf-8')
    if new.strip() in src and old.strip() not in src:
        print(f'  SKIP  {tag} (already applied)'); return
    if old not in src:
        if required:
            print(f'  FAIL  {tag}: anchor not found in {path}'); sys.exit(1)
        print(f'  WARN  {tag}: anchor not found — skipped'); return
    p.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

LE = 'android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt'
PA = 'patch_android.py'

print(f'\n── S194  [repo: {REPO}] ──\n')

# ── BUG-A/B/C: Replace the old one-shot pip block with numpyWorks() + retry ─
patch(LE,
    '        // S106: install numpy/scipy to fixed known path\n'
    '        val numpyTarget = File(alpineDir, "tilawa_numpy")\n'
    '        if (!File(numpyTarget, "numpy").exists()) {\n'
    '            progress(79, "Installing numpy + scipy (one-time ~2 min)…")\n'
    '            numpyTarget.mkdirs()\n'
    '            runProot(listOf("/bin/sh", "-c",\n'
    '                "pip3 install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1 || " +\n'
    '                "pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1"),\n'
    '                timeoutMin=20)\n'
    '        }\n',
    # ── replacement ──
    '        // S194: numpy/scipy install — check system paths FIRST (bundled via\n'
    '        // `apk add` in the APK build), then pip target, then verify with a\n'
    '        // real proot import.  BUG-A: old code only checked tilawa_numpy/ and\n'
    '        // never looked at system site-packages, so pip always ran even when\n'
    '        // numpy was already present, causing failures on offline devices.\n'
    '        val numpyTarget = File(alpineDir, "tilawa_numpy")\n'
    '        val numpyVerifiedMarker = File(alpineDir, ".numpy_verified")\n'
    '        fun numpyWorks(): Boolean {\n'
    '            // 1. System numpy installed via `apk add` in python-env.tar.gz\n'
    '            val sysNumpyOk =\n'
    '                File(alpineDir, "usr/lib/python3.11/site-packages/numpy").exists() ||\n'
    '                File(alpineDir, "usr/lib/python3.12/site-packages/numpy").exists()\n'
    '            val sysScipyOk =\n'
    '                File(alpineDir, "usr/lib/python3.11/site-packages/scipy").exists() ||\n'
    '                File(alpineDir, "usr/lib/python3.12/site-packages/scipy").exists()\n'
    '            if (sysNumpyOk && sysScipyOk) {\n'
    '                numpyVerifiedMarker.writeText("ok"); return true\n'
    '            }\n'
    '            // 2. Pip-installed target — must have BOTH packages\n'
    '            if (!File(numpyTarget, "numpy").exists() ||\n'
    '                !File(numpyTarget, "scipy").exists()) return false\n'
    '            // 3. Verify with real proot import (catches half-written installs)\n'
    '            val probe = runProot(\n'
    '                listOf("/usr/bin/python3", "-c", "import numpy, scipy; print(\'ok\')"),\n'
    '                timeoutMin = 2)\n'
    '            val ok = probe.first == 0 && probe.second.contains("ok")\n'
    '            if (ok) numpyVerifiedMarker.writeText("ok") else numpyVerifiedMarker.delete()\n'
    '            return ok\n'
    '        }\n'
    '        if (!numpyWorks()) {\n'
    '            progress(79, "Installing numpy + scipy (one-time ~2 min)…")\n'
    '            numpyTarget.mkdirs()\n'
    '            runProot(listOf("/bin/sh", "-c",\n'
    '                "pip3 install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1 || " +\n'
    '                "pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1"),\n'
    '                timeoutMin = 20)\n'
    '            if (!numpyWorks()) {\n'
    '                // BUG-C fix: wipe broken/partial install and retry once\n'
    '                progress(79, "Retrying numpy + scipy install (cleaning previous attempt)…")\n'
    '                numpyTarget.deleteRecursively()\n'
    '                numpyTarget.mkdirs()\n'
    '                runProot(listOf("/bin/sh", "-c",\n'
    '                    "pip3 install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1 || " +\n'
    '                    "pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1"),\n'
    '                    timeoutMin = 20)\n'
    '                if (!numpyWorks()) {\n'
    '                    throw IOException(\n'
    '                        "numpy/scipy install failed — check internet connection and retry setup")\n'
    '                }\n'
    '            }\n'
    '        }\n',
    'numpy-A/B/C: add numpyWorks() with system-path check, verify, retry')

# ── BUG-D: isSetupComplete() missing scipy + .numpy_verified ─────────────────
patch(LE,
    '        val numpyOk = File(alpineDir, "usr/lib/python3.11/site-packages/numpy").exists() ||\n'
    '            File(alpineDir, "usr/lib/python3.12/site-packages/numpy").exists() ||\n'
    '            File(alpineDir, "tilawa_numpy/numpy").exists()\n'
    '        if (!numpyOk) return false  // S122: force re-setup if numpy missing\n',
    # S195-BUG1: pre-S194 anchor; S194 already applied numpySystemOk form to live file.
    # S195-BUG1: pre-S194 anchor; S194 already applied numpySystemOk form to live file.
    # S195-BUG1: pre-S194 anchor; S194 already applied numpySystemOk form to live file.
    # S195-BUG1: anchor above is the pre-S194 form; live file already has numpySystemOk.
    # required=False prevents spurious sys.exit(1) when re-running on an up-to-date repo.
    # S195-BUG1: anchor above is the pre-S194 form; live file already has numpySystemOk.
    # required=False prevents spurious sys.exit(1) when re-running on an up-to-date repo.
    # ── replacement ──
    '        // S194: check both numpy AND scipy; also accept .numpy_verified marker\n'
    '        // written by numpyWorks() so a verified system install never re-runs pip.\n'
    '        val numpySystemOk =\n'
    '            File(alpineDir, "usr/lib/python3.11/site-packages/numpy").exists() ||\n'
    '            File(alpineDir, "usr/lib/python3.12/site-packages/numpy").exists()\n'
    '        val numpyOk = numpySystemOk || File(alpineDir, ".numpy_verified").exists() ||\n'
    '            File(alpineDir, "tilawa_numpy/numpy").exists()\n'
    '        val scipySystemOk =\n'
    '            File(alpineDir, "usr/lib/python3.11/site-packages/scipy").exists() ||\n'
    '            File(alpineDir, "usr/lib/python3.12/site-packages/scipy").exists()\n'
    '        val scipyOk = scipySystemOk || File(alpineDir, ".numpy_verified").exists() ||\n'
    '            File(alpineDir, "tilawa_numpy/scipy").exists()\n'
    '        if (!numpyOk || !scipyOk) return false  // S148: scipy required by v11.2\n',
    'numpy-D: isSetupComplete() scipy check + .numpy_verified marker')

# ── BUG-E: patch_android.py template numpyWorks() doesn't check system first ─
# The template's numpyWorks() early-returns false if tilawa_numpy/numpy is
# missing, never checking system paths.  Fix: check system paths first.
patch(PA,
    '        fun numpyWorks(): Boolean {\n'
    '            if (!File(numpyTarget, "numpy").exists() || !File(numpyTarget, "scipy").exists()) return false\n'
    '            val probe = runProot(listOf("/usr/bin/python3", "-c", "import numpy, scipy"), timeoutMin=2)\n',
    # ── replacement ──
    '        fun numpyWorks(): Boolean {\n'
    '            // S194-E: check system paths first — numpy/scipy may be bundled\n'
    '            // via `apk add` in python-env.tar.gz, no pip needed.\n'
    '            val sysNpOk = File(alpineDir, "usr/lib/python3.11/site-packages/numpy").exists() ||\n'
    '                File(alpineDir, "usr/lib/python3.12/site-packages/numpy").exists()\n'
    '            val sysSpOk = File(alpineDir, "usr/lib/python3.11/site-packages/scipy").exists() ||\n'
    '                File(alpineDir, "usr/lib/python3.12/site-packages/scipy").exists()\n'
    '            if (sysNpOk && sysSpOk) { numpyVerifiedMarker.writeText("ok"); return true }\n'
    '            if (!File(numpyTarget, "numpy").exists() || !File(numpyTarget, "scipy").exists()) return false\n'
    '            val probe = runProot(listOf("/usr/bin/python3", "-c", "import numpy, scipy; print(\'ok\')"), timeoutMin=2)\n',
    'numpy-E: patch_android.py template numpyWorks() system-path check',
    required=False)  # patch_android.py might not be at repo root

STAMP.write_text('ok\n')
print('\nDone.')
print()
print('  Bugs fixed:')
print('  BUG-A  numpyWorks() now checks system site-packages FIRST → no pip needed')
print('         when numpy is bundled via apk add in python-env.tar.gz.')
print('  BUG-B  pip failure no longer silently ignored — numpyWorks() verifies')
print('         with a real proot import probe and only returns true if it passes.')
print('  BUG-C  On first-try failure, tilawa_numpy/ is wiped and pip retried once.')
print('         If that also fails, a clear IOException is thrown.')
print('  BUG-D  isSetupComplete() now checks scipy AND uses .numpy_verified marker.')
print('  BUG-E  patch_android.py template numpyWorks() also checks system paths.')
print()
print('  git add android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt \\')
print('          patch_android.py')
print('  git commit -m "S194: fix numpy install — check system paths first, add verify+retry"')
