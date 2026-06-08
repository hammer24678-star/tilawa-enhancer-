#!/usr/bin/env python3
"""
fix_df3_progress.py — patches patch_android.py with two fixes:

  FIX-1 (DF3-ARCH):  Add ELF machine-type check in isSetupComplete() and setup().
                     If binary is x86_64 (wrong arch on aarch64 device), force
                     re-download of the correct aarch64 binary from GitHub.

  FIX-2 (PROGRESS):  Parse engine phase tags [Ax]/[Bx]/...[Lx] in runEngine()
                     and emit meaningful pct values instead of always -1.
                     home_screen.dart update also needed (see home_screen_fix.patch).
"""
import sys
from pathlib import Path

SRC = Path("patch_android.py")

if not SRC.exists():
    print("ERROR: patch_android.py not found in current directory.")
    sys.exit(1)

text = SRC.read_text(encoding="utf-8")

# ── FIX-1a: isSetupComplete() — add arch check after size check ───────────────
OLD_SETUP_COMPLETE = (
    '        val df = File(alpineDir, "usr/local/bin/deep-filter")\n'
    '        if (!df.exists() || df.length() < 1_000_000L) return false\n'
    '        if (enginesDir.list()?.isNotEmpty() != true) return false'
)
NEW_SETUP_COMPLETE = (
    '        val df = File(alpineDir, "usr/local/bin/deep-filter")\n'
    '        if (!df.exists() || df.length() < 1_000_000L) return false\n'
    '        // S-DF3ARCH: reject if binary is not aarch64 — x86_64 runs setup but\n'
    '        // silently fails inside proot on phone → engine prints [A5] and skips DF3.\n'
    '        // ELF e_machine bytes 18-19: aarch64=0xB7,0x00  x86_64=0x3E,0x00\n'
    '        val dfOkArch = try {\n'
    '            val h = ByteArray(20); FileInputStream(df).use { it.read(h) }\n'
    '            h[18] == 0xB7.toByte() && h[19] == 0x00.toByte()\n'
    '        } catch (_: Exception) { false }\n'
    '        if (!dfOkArch) return false\n'
    '        if (enginesDir.list()?.isNotEmpty() != true) return false'
)

if OLD_SETUP_COMPLETE not in text:
    print("ERROR: isSetupComplete() target string not found — check patch_android.py version.")
    sys.exit(1)

text = text.replace(OLD_SETUP_COMPLETE, NEW_SETUP_COMPLETE, 1)
print("  FIX-1a applied: isSetupComplete() arch check")

# ── FIX-1b: setup() — verify/repair arch after install ────────────────────────
OLD_DF_SETUP = (
    '        progress(88, "DeepFilter ready")'
)
NEW_DF_SETUP = (
    '        // S-DF3ARCH: verify/repair — if bundled asset was x86_64, replace with aarch64\n'
    '        val dfHdrBuf = ByteArray(20)\n'
    '        val dfIsAarch64 = try {\n'
    '            FileInputStream(dfBin).use { it.read(dfHdrBuf) }\n'
    '            dfHdrBuf[18] == 0xB7.toByte() && dfHdrBuf[19] == 0x00.toByte()\n'
    '        } catch (_: Exception) { false }\n'
    '        if (!dfIsAarch64) {\n'
    '            dfBin.delete()\n'
    '            progress(80, "DF3: wrong arch detected — downloading aarch64…")\n'
    '            try {\n'
    '                val dfUrl = "https://github.com/Rikorose/DeepFilterNet/releases/download/v0.5.6/deep-filter-0_5_6-aarch64-unknown-linux-musl"\n'
    '                download(dfUrl, dfBin, "DeepFilter aarch64", 80, 88)\n'
    '                dfBin.setExecutable(true)\n'
    '            } catch (e: Exception) {\n'
    '                throw IOException("DF3 aarch64 download failed: ${e.message}")\n'
    '            }\n'
    '        }\n'
    '        progress(88, "DeepFilter ready (aarch64 ✓)")'
)

if OLD_DF_SETUP not in text:
    print("ERROR: setup() DeepFilter progress target not found.")
    sys.exit(1)

text = text.replace(OLD_DF_SETUP, NEW_DF_SETUP, 1)
print("  FIX-1b applied: setup() arch verify/repair")

# ── FIX-2: runEngine() — emit meaningful pct from phase tags ──────────────────
OLD_PROGRESS_LINE = (
    '                ui { channel?.invokeMethod("engineProgress", mapOf("pct" to -1, "msg" to l)) }'
)
NEW_PROGRESS_LINE = (
    '                // S-PROGRESS: map engine phase-tag prefix to progress pct\n'
    '                // Phases A→L correspond to the DSP pipeline stages in الإتقان/الاسترداد.\n'
    '                val linePct = when {\n'
    '                    l.startsWith("[A1]") || l.startsWith("[A2]") || l.startsWith("[A3]") -> 5\n'
    '                    l.startsWith("[A4]") || l.startsWith("[A5]") || l.startsWith("[A6]") -> 8\n'
    '                    l.startsWith("[A7]") || l.startsWith("[A8]") || l.startsWith("[A9]") -> 12\n'
    '                    l.startsWith("[B")  -> 16\n'
    '                    l.startsWith("[C")  -> 22\n'
    '                    l.startsWith("[D")  -> 30\n'
    '                    l.startsWith("[E")  -> 38\n'
    '                    l.startsWith("[F]") && l.contains("detected") -> 22   // phrase count msg\n'
    '                    l.startsWith("[F")  -> 46\n'
    '                    l.startsWith("[G")  -> 58\n'
    '                    l.startsWith("[H")  -> 68\n'
    '                    l.startsWith("[I")  -> 76\n'
    '                    l.startsWith("[J")  -> 84\n'
    '                    l.startsWith("[K")  -> 90\n'
    '                    l.startsWith("[L")  -> 94\n'
    '                    l.contains("score") && l.contains("/100") -> 96\n'
    '                    else -> -1\n'
    '                }\n'
    '                ui { channel?.invokeMethod("engineProgress", mapOf("pct" to linePct, "msg" to l)) }'
)

if OLD_PROGRESS_LINE not in text:
    print("ERROR: runEngine() progress line not found.")
    sys.exit(1)

text = text.replace(OLD_PROGRESS_LINE, NEW_PROGRESS_LINE, 1)
print("  FIX-2  applied: runEngine() phase→pct progress mapping")

# ── Write result ───────────────────────────────────────────────────────────────
# Bump version marker
text = text.replace(
    '"""patch_android.py v11 — S19',
    '"""patch_android.py v12 — S19'
)
text = text.replace(
    'print("patch_android.py v11: DONE")',
    'print("patch_android.py v12: DONE (DF3-ARCH fix + local engine progress)")'
)

SRC.write_text(text, encoding="utf-8")
print(f"\n  patch_android.py updated in-place ({SRC.stat().st_size} bytes)")
print("  Version bumped to v12.")
print()
print("  ALSO NEEDED: apply home_screen_fix.patch to lib/home_screen.dart")
print("  (see home_screen_fix.patch in same directory)")
