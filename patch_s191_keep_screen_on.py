#!/usr/bin/env python3
"""
patch_s191_keep_screen_on.py — S191

  WL-1  MainActivity.kt (live file) — the "wake" channel only ever took a
        PARTIAL_WAKE_LOCK, which keeps the CPU running but does nothing for
        the display — the screen can still time out and turn off/lock
        during processing. Add FLAG_KEEP_SCREEN_ON on "acquire" (cleared on
        "release") so the screen actually stays on and bright while
        _engineProcessingOverlay() is up.
  WL-2  patch_android.py — same fix applied to the MAIN_ACTIVITY_KT template
        string, so the next time patch_android.py is re-run from scratch it
        regenerates MainActivity.kt with this fix already in it instead of
        silently reverting WL-1.

Usage:  python3 patch_s191_keep_screen_on.py /path/to/tilawa-enhancer
"""
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
if not (REPO / 'lib').exists():
    print(f'ERROR: lib/ not found in {REPO}')
    sys.exit(1)

STAMP = REPO / '.patch_s191_keep_screen_on_done'
if STAMP.exists():
    print('patch_s191 already applied — delete .patch_s191_keep_screen_on_done to re-run')
    sys.exit(0)

def patch(path, old, new, tag, required=False):
    p = REPO / path
    if not p.exists():
        print(f'  SKIP  {tag} (file missing)'); return
    src = p.read_text(encoding='utf-8')
    if new.strip() in src:
        print(f'  SKIP  {tag} (already applied)'); return
    if old not in src:
        if required:
            print(f'  FAIL  {tag}: anchor not found'); sys.exit(1)
        print(f'  WARN  {tag}: anchor not found — skipped'); return
    p.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

print(f'\n── S191  [repo: {REPO}] ──\n')

MA = 'android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/MainActivity.kt'
PA = 'patch_android.py'

# ── WL-1a: live MainActivity.kt — import ────────────────────────────────────
patch(MA,
    "import android.provider.MediaStore\n"
    "import io.flutter.embedding.android.FlutterActivity\n",
    "import android.provider.MediaStore\n"
    "import android.view.WindowManager\n"
    "import io.flutter.embedding.android.FlutterActivity\n",
    'WL-1a: MainActivity.kt import WindowManager',
    required=True)

# ── WL-1b: live MainActivity.kt — acquire/release toggle FLAG_KEEP_SCREEN_ON
patch(MA,
    "                \"acquire\" -> {\n"
    "                    _wl?.let { if (it.isHeld) it.release() }\n"
    "                    _wl = pm.newWakeLock(\n"
    "                        android.os.PowerManager.PARTIAL_WAKE_LOCK,\n"
    "                        \"tilawa:processing\"\n"
    "                    ).also { it.acquire(10 * 60 * 1000L) }\n"
    "                    result.success(null)\n"
    "                }\n"
    "                \"release\" -> {\n"
    "                    _wl?.let { if (it.isHeld) it.release() }\n"
    "                    _wl = null\n"
    "                    result.success(null)\n"
    "                }\n",

    "                \"acquire\" -> {\n"
    "                    _wl?.let { if (it.isHeld) it.release() }\n"
    "                    _wl = pm.newWakeLock(\n"
    "                        android.os.PowerManager.PARTIAL_WAKE_LOCK,\n"
    "                        \"tilawa:processing\"\n"
    "                    ).also { it.acquire(10 * 60 * 1000L) }\n"
    "                    // S191: PARTIAL_WAKE_LOCK alone only keeps the CPU running —\n"
    "                    // it does nothing for the display, so the screen could still\n"
    "                    // time out/lock during processing. Force it to stay on too.\n"
    "                    runOnUiThread { window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }\n"
    "                    result.success(null)\n"
    "                }\n"
    "                \"release\" -> {\n"
    "                    _wl?.let { if (it.isHeld) it.release() }\n"
    "                    _wl = null\n"
    "                    runOnUiThread { window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }  // S191\n"
    "                    result.success(null)\n"
    "                }\n",
    'WL-1b: MainActivity.kt FLAG_KEEP_SCREEN_ON on acquire/release',
    required=True)

# ── WL-2a: patch_android.py template — import ───────────────────────────────
patch(PA,
    "'import android.provider.MediaStore\\n'\n"
    "'import io.flutter.embedding.android.FlutterActivity\\n'\n",
    "'import android.provider.MediaStore\\n'\n"
    "'import android.view.WindowManager\\n'\n"
    "'import io.flutter.embedding.android.FlutterActivity\\n'\n",
    'WL-2a: patch_android.py template import WindowManager',
    required=True)

# ── WL-2b: patch_android.py template — acquire/release ─────────────────────
patch(PA,
    "'                \"acquire\" -> {\\n'\n"
    "'                    _wl?.let { if (it.isHeld) it.release() }\\n'\n"
    "'                    _wl = pm.newWakeLock(\\n'\n"
    "'                        android.os.PowerManager.PARTIAL_WAKE_LOCK,\\n'\n"
    "'                        \"tilawa:processing\"\\n'\n"
    "'                    ).also { it.acquire(10 * 60 * 1000L) }\\n'\n"
    "'                    result.success(null)\\n'\n"
    "'                }\\n'\n"
    "'                \"release\" -> {\\n'\n"
    "'                    _wl?.let { if (it.isHeld) it.release() }\\n'\n"
    "'                    _wl = null\\n'\n"
    "'                    result.success(null)\\n'\n"
    "'                }\\n'\n",

    "'                \"acquire\" -> {\\n'\n"
    "'                    _wl?.let { if (it.isHeld) it.release() }\\n'\n"
    "'                    _wl = pm.newWakeLock(\\n'\n"
    "'                        android.os.PowerManager.PARTIAL_WAKE_LOCK,\\n'\n"
    "'                        \"tilawa:processing\"\\n'\n"
    "'                    ).also { it.acquire(10 * 60 * 1000L) }\\n'\n"
    "'                    // S191: also force the screen to stay on, not just the CPU\\n'\n"
    "'                    runOnUiThread { window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }\\n'\n"
    "'                    result.success(null)\\n'\n"
    "'                }\\n'\n"
    "'                \"release\" -> {\\n'\n"
    "'                    _wl?.let { if (it.isHeld) it.release() }\\n'\n"
    "'                    _wl = null\\n'\n"
    "'                    runOnUiThread { window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }  // S191\\n'\n"
    "'                    result.success(null)\\n'\n"
    "'                }\\n'\n",
    'WL-2b: patch_android.py template acquire/release',
    required=True)

# ──────────────────────────────────────────────────────────────────────────
STAMP.write_text('S191\n')
print('\n✅  patch_s191 done')
print()
print('  git add android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/MainActivity.kt patch_android.py')
print('  git commit -m "S191: keep screen on (not just CPU) during processing via FLAG_KEEP_SCREEN_ON"')
print('  git push')
print()
print('  NOTE: this only takes effect after a rebuild (flutter build apk / run),')
print('  since MainActivity.kt is native Android code, not hot-reloadable Dart.')
