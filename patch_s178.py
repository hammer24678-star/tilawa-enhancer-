#!/usr/bin/env python3
"""
patch_s178.py — S178: fix v11.0 mislabel + local-engine rc=127 + AudioLab editor

Root causes found:

  BUG 1 (screenshots 1 & 4 — "we have صفاء not تجلي, completely different engines")
    v11.0 is bound to assets/engines/engine_safaa_v4.py (الصفاء) everywhere that
    matters — Kotlin's script map, home_screen.dart's _engines list, and the
    engineNames map all agree on "الصفاء". But two purely-display screens still
    say "التجلي" with a description of a "smart router" concept that was never
    actually built. Cosmetic only, but confusing/wrong.
      E1  lib/screens/local_mode_info_screen.dart  — _engineRow label+desc
      E2  lib/screens/settings_screen.dart         — _EHist label+desc

  BUG 2 (screenshots 2 & 3 — "Engine failed (rc=127): Error loading shared
         library libpython3.12.so.1.0 … Py_BytesMain: symbol not found")
    .github/workflows/build.yml builds python-env.tar.gz with an explicit file
    list for tar. It includes /usr/lib/$PY (the stdlib dir) but never includes
    /usr/lib/libpython$PY.so* — the actual shared library python3 is dynamically
    linked against. Every local engine run (الصفاء/الإتقان/الاسترداد) was
    therefore doomed from a fresh install.
      E3  .github/workflows/build.yml — add the missing .so to the tar list
      E4  LocalEngineRunner.kt (both the live CI template embedded in
          patch_android.py AND the standalone .kt file) — self-heals an
          *already*-broken extraction (python3 present, lib missing) by wiping
          and forcing a clean re-extract, and isSetupComplete() now checks for
          the lib too instead of reporting "ready" on a broken install.

  BUG 3 ("the audio editor doesn't work")
    audio_editor_screen.dart's _export() calls the raw MethodChannel directly
    with only {cmd, timeoutMin} — skipping LocalEngineService.runProotCmd(),
    which was specifically built (S161/S174-B3, see its own comment) to also
    send inputPath/outputPath so Kotlin can bind-mount the picked file's real
    directory and the output directory into the proot chroot. Without those,
    ffmpeg can't see the file it's supposed to read or write, and the export
    silently fails (or worse, the editor just claims success regardless of the
    exit code — also fixed below).
      E5  lib/screens/audio_editor_screen.dart — pass inputPath/outputPath,
          check rc instead of assuming success.

Run from repo root: python3 patch_s178.py
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

STAMP = Path('.patch_s178_done')
if STAMP.exists():
    print('patch_s178: already applied — delete .patch_s178_done to re-run'); sys.exit(0)

print('\n── S178: fix v11.0 mislabel + local-engine rc=127 + AudioLab editor ────────')

# ════════════════════════════════════════════════════════════════════════════
# E1 — local_mode_info_screen.dart: v11.0 row says التجلي, should say الصفاء
# ════════════════════════════════════════════════════════════════════════════
patch('lib/screens/local_mode_info_screen.dart',
    """      _engineRow(ar, 'v11.0', ar ? 'التجلي'     : 'Tajalli',
        ar ? 'توجيه تلقائي — الأمثل للاستخدام العام'
           : 'Auto-routes to optimal path — best for general use',
        _gold, 99.5),""",
    """      _engineRow(ar, 'v11.0', ar ? 'الصفاء'     : 'Safaa',
        ar ? 'إزالة صدى المساجد — يحافظ على أحكام التجويد كاملةً'
           : 'Mosque echo removal — full Tajweed phonology preservation',
        _gold, 99.5),""",
    'E1: local_mode_info_screen v11.0 → الصفاء')

# ════════════════════════════════════════════════════════════════════════════
# E2 — settings_screen.dart: _EHist v11.0 entry says التجلي, should say الصفاء
# ════════════════════════════════════════════════════════════════════════════
patch('lib/screens/settings_screen.dart',
    """    _EHist('v11.0','التجلي — The Manifestation','≥ 99.5/100','LATEST','gold',
      'المحرك الموحَّد والذكي. يصنِّف التسجيل في 5 مستويات ثم يوجِّهه للمسار الأمثل: الإتقان للنظيف، والاسترداد للتالف. يمرُّ الصوت عبر البيان والنور قبل الترميز النهائي مع توقيع SHA-256.',
      'The unified smart router. Classifies the recording into 5 tiers then routes to the optimal path: Itiqan for clean, Isteidad for damaged. Passes through Bayan and Noor before final TPDF encode with SHA-256 provenance.',
      'S+'),""",
    """    _EHist('v11.0','الصفاء — Purity','≥ 99.5/100','LATEST','gold',
      'محرك إزالة صدى المساجد. يجمع دي-ريفِرب وWPE وDF3 NR رباعي الفئات وJALAA على مرحلتين وTail-NR ثلاثي المراحل، مع حارس عربي يحافظ على أحكام التجويد كاملةً. يُخرج WAV مباشرة دون أي اتصال بالخادم.',
      'Mosque-echo dereverberation engine. Combines WPE, 4-class DF3 noise reduction, 2-pass JALAA, and 3-stage tail-NR with a Tajweed phonology guard. Outputs WAV directly — no server round-trip.',
      'S+'),""",
    'E2: settings_screen _EHist v11.0 → الصفاء')

# ════════════════════════════════════════════════════════════════════════════
# E3 — build.yml: python-env.tar.gz never packed libpythonX.Y.so
# ════════════════════════════════════════════════════════════════════════════
patch('.github/workflows/build.yml',
    """            /usr/lib/libopenblas.so.* /usr/lib/libgfortran.so.* \\
            2>/dev/null || true""",
    """            /usr/lib/libopenblas.so.* /usr/lib/libgfortran.so.* \\
            /usr/lib/lib$PY.so* \\
            2>/dev/null || true""",
    'E3: build.yml tar list adds libpythonX.Y.so*')

# ════════════════════════════════════════════════════════════════════════════
# E4 — LocalEngineRunner.kt: self-heal missing libpython + isSetupComplete check
#       Applied to BOTH the CI-authoritative template inside patch_android.py
#       (flutter create wipes android/ every build, then patch_android.py
#       regenerates LocalEngineRunner.kt from this string — this is what
#       actually ships) and the standalone .kt file (best-effort, non-fatal).
# ════════════════════════════════════════════════════════════════════════════
_SETUP_OLD = '''        progress(10, "proot ready (bundled libproot.so)")

        // 2. Alpine rootfs — download like Termux proot-distro'''
_SETUP_NEW = '''        progress(10, "proot ready (bundled libproot.so)")

        // S178: detect a python3 binary with no matching libpythonX.Y.so —
        // happens when python-env.tar.gz was packaged without the shared
        // library, so python3 dies with "Error loading shared library …"
        // (rc=127). Wipe before the busybox check below so this same pass
        // re-extracts everything cleanly instead of leaving a half rootfs.
        val hasLibPython = File(alpineDir, "usr/lib").listFiles()
            ?.any { it.name.startsWith("libpython") && it.name.contains(".so") } ?: false
        if (File(alpineDir, "usr/bin/python3").exists() && !hasLibPython) {
            progress(11, "Fixing missing Python shared library…")
            alpineDir.deleteRecursively()
            alpineDir.mkdirs()
            context.getSharedPreferences("tilawa_local", 0)
                .edit().putBoolean("setup_complete", false).apply()
        }

        // 2. Alpine rootfs — download like Termux proot-distro'''

_ISC_OLD = '''        if (!File(alpineDir, "usr/bin/python3").exists()) return false
        if (!File(alpineDir, "usr/bin/ffmpeg").exists()) return false'''
_ISC_NEW = '''        if (!File(alpineDir, "usr/bin/python3").exists()) return false
        // S178: python3 binary alone isn't enough — without its matching
        // libpythonX.Y.so every engine run fails with rc=127.
        val hasLibPython = File(alpineDir, "usr/lib").listFiles()
            ?.any { it.name.startsWith("libpython") && it.name.contains(".so") } ?: false
        if (!hasLibPython) return false
        if (!File(alpineDir, "usr/bin/ffmpeg").exists()) return false'''

patch('patch_android.py', _SETUP_OLD, _SETUP_NEW,
      'E4a: patch_android.py template — self-heal missing libpython')
patch('patch_android.py', _ISC_OLD, _ISC_NEW,
      'E4b: patch_android.py template — isSetupComplete checks libpython')

KT = 'android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt'
patch(KT, _SETUP_OLD, _SETUP_NEW,
      'E4c: standalone LocalEngineRunner.kt — self-heal missing libpython', required=False)
patch(KT, _ISC_OLD, _ISC_NEW,
      'E4d: standalone LocalEngineRunner.kt — isSetupComplete checks libpython', required=False)

# ════════════════════════════════════════════════════════════════════════════
# E5 — audio_editor_screen.dart: _export() never passed inputPath/outputPath
#       to runProotCmd, so Kotlin never bind-mounted the real file/output
#       dirs into proot, AND the export ignored ffmpeg's exit code entirely.
# ════════════════════════════════════════════════════════════════════════════
patch('lib/screens/audio_editor_screen.dart',
    """      setState(() => _pct = 0.2);
      await _ch.invokeMethod('runProotCmd', {'cmd': cmd, 'timeoutMin': 10});  // S161
      setState(() { _pct = 1.0; _outPath = out; _busy = false; });""",
    """      setState(() => _pct = 0.2);
      // S178: pass inputPath/outputPath so Kotlin's runProotCmd bind-mounts
      // their real directories into the proot chroot — without these the
      // picked file and the output folder are invisible inside proot and
      // ffmpeg fails to read/write them. Also check rc instead of assuming
      // success regardless of what ffmpeg actually did.
      final r = await _ch.invokeMethod<Map>('runProotCmd', {
        'cmd':        cmd,
        'inputPath':  _filePath!,
        'outputPath': out,
        'timeoutMin': 10,
      });  // S161/S178
      final rc = (r?['rc'] as int?) ?? 0;
      if (rc != 0) {
        throw Exception('ffmpeg failed (rc=$rc): ${(r?['out'] as String? ?? '').trim()}');
      }
      setState(() { _pct = 1.0; _outPath = out; _busy = false; });""",
    'E5: audio_editor_screen _export() passes inputPath/outputPath + checks rc')

STAMP.write_text('S178\n')
print('\n✅  patch_s178 done')
print('   git add lib/screens/local_mode_info_screen.dart lib/screens/settings_screen.dart \\')
print('       .github/workflows/build.yml patch_android.py \\')
print('       android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt \\')
print('       lib/screens/audio_editor_screen.dart')
print('   git commit -m "S178: E1-E2 fix v11.0 mislabel (التجلي→الصفاء), E3-E4 fix local')
print('   engine rc=127 (missing libpython.so), E5 fix AudioLab editor proot binds"')
print('   git push')
print()
print('NOTE: anyone with an already-broken alpine-318/ on their phone needs to')
print('reinstall the updated APK and the self-heal in E4 will wipe + cleanly')
print('re-extract on next "Start Setup" — no manual uninstall needed.')
print()
print("NOTE: the standalone LocalEngineRunner.kt has no \"runProotCmd\" case at all")
print("(it predates S161/S174 — patch_android.py's template is the one CI actually")
print("builds from, since `flutter create` wipes android/ before patch_android.py")
print("regenerates it). E4c/E4d above are best-effort/non-fatal for that reason —")
print("worth folding the rest of patch_android.py's template into that file too")
print("next time you touch LocalEngineRunner.kt by hand, so the two don't drift.")
