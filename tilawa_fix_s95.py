#!/usr/bin/env python3
"""
tilawa_fix_s95.py
=================
Fix LocalEngineRunner.kt — two bugs:
  Bug 1  Step 2 downloads Alpine from internet even though
         assets/alpine/alpine-rootfs.tar.gz is bundled in the APK.
         If mirrors.edge.kernel.org is unreachable → Setup Failed at 32 pct.
         Fix: try bundled asset first, fall back to internet only if asset missing.

  Bug 2  Step 6 comment says "extracted in setup above" but there is
         ZERO code to copy ref audio files from assets to refAudioDir.
         Fix: add explicit extraction loop for the three ref mp3 files.
"""
from pathlib import Path
from datetime import datetime

KT = Path('android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt')

print(f'\n{"="*54}\n  tilawa_fix_s95  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*54}')

# Read stripping null bytes (file is valid UTF-8 but Termux grep treats
# multi-byte chars as binary — the code itself is intact)
raw = KT.read_bytes()
txt = raw.replace(b'\x00', b'').decode('utf-8', errors='replace')

_log = []
def rep(old, new, lbl):
    global txt
    if old in txt:
        txt = txt.replace(old, new, 1)
        print(f'  OK  {lbl}')
        _log.append(('OK', lbl))
    else:
        print(f'  XX  NOT FOUND \u2014 {lbl}')
        _log.append(('XX', lbl))

# ═══════════════════════════════════════════════════════════
# Fix 1 \u2014 Alpine: bundled asset first, internet fallback
# Anchor: exact text from python3 file read (includes em-dash + ellipsis)
# ═══════════════════════════════════════════════════════════
rep(
    '        // 2. Alpine rootfs \u2014 download like Termux proot-distro\n'
    '        if (!File(alpineDir, "usr/bin/busybox").exists()) {\n'
    '            progress(12, "Downloading Alpine Linux (~4MB)\u2026")\n'
    '            alpineDir.mkdirs()\n'
    '            val tmp = File(dataDir, "alpine.tar.gz")\n'
    '            val _url = "https://mirrors.edge.kernel.org/alpine/v3.21/releases/aarch64/alpine-minirootfs-3.21.3-aarch64.tar.gz"\n'
    '            download(_url, tmp, "Alpine rootfs", 12, 32)\n'
    '            extractTarGz(tmp, alpineDir)\n'
    '            tmp.delete()',

    '        // 2. Alpine rootfs \u2014 bundled asset first, internet fallback\n'
    '        if (!File(alpineDir, "usr/bin/busybox").exists()) {\n'
    '            progress(12, "Extracting Alpine Linux (bundled)\u2026")\n'
    '            alpineDir.mkdirs()\n'
    '            val tmp = File(dataDir, "alpine.tar.gz")\n'
    '            // S95: try both possible Flutter asset paths\n'
    '            var assetCopied = false\n'
    '            for (ap in listOf(\n'
    '                "flutter_assets/assets/alpine/alpine-rootfs.tar.gz",\n'
    '                "flutter_assets/alpine/alpine-rootfs.tar.gz"\n'
    '            )) {\n'
    '                try {\n'
    '                    context.assets.open(ap)\n'
    '                        .use { src -> java.io.FileOutputStream(tmp).use { dst -> src.copyTo(dst) } }\n'
    '                    assetCopied = true\n'
    '                    progress(28, "Alpine bundle copied\u2026")\n'
    '                    break\n'
    '                } catch (_: Exception) {}\n'
    '            }\n'
    '            if (!assetCopied) {\n'
    '                // Fallback: download (requires internet)\n'
    '                progress(14, "Downloading Alpine Linux (~4MB)\u2026")\n'
    '                val _url = "https://mirrors.edge.kernel.org/alpine/v3.21/releases/aarch64/alpine-minirootfs-3.21.3-aarch64.tar.gz"\n'
    '                download(_url, tmp, "Alpine rootfs", 14, 32)\n'
    '            }\n'
    '            extractTarGz(tmp, alpineDir)\n'
    '            tmp.delete()',

    'Fix-1 Alpine bundled asset + internet fallback'
)

# ═══════════════════════════════════════════════════════════
# Fix 2 \u2014 Ref audio: actually extract files from assets
# ═══════════════════════════════════════════════════════════
rep(
    '        // 6. Reference audio \u2014 bundled in APK assets (extracted in setup above)\n'
    '        progress(100, "Local engine ready!")',

    '        // 6. Reference audio \u2014 extract from APK assets to refAudioDir\n'
    '        progress(93, "Extracting reference audio\u2026")\n'
    '        refAudioDir.mkdirs()\n'
    '        for (rf in listOf(\n'
    '            "ref_araf_1425h.mp3",\n'
    '            "ref_fath_1425h.mp3",\n'
    '            "ref_fatir_1425h.mp3"\n'
    '        )) {\n'
    '            val dst = java.io.File(refAudioDir, rf)\n'
    '            if (!dst.exists()) {\n'
    '                for (ap in listOf(\n'
    '                    "flutter_assets/assets/reference_audio/$rf",\n'
    '                    "flutter_assets/reference_audio/$rf"\n'
    '                )) {\n'
    '                    try {\n'
    '                        context.assets.open(ap)\n'
    '                            .use { src -> java.io.FileOutputStream(dst).use { d -> src.copyTo(d) } }\n'
    '                        break\n'
    '                    } catch (_: Exception) {}\n'
    '                }\n'
    '            }\n'
    '        }\n'
    '        progress(100, "Local engine ready!")',

    'Fix-2 ref audio extraction from bundled assets'
)

# Write back as clean UTF-8 (no null bytes)
KT.write_bytes(txt.encode('utf-8'))
print('  OK  LocalEngineRunner.kt saved')

ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n+1} OK   {xx_n} FAIL\n')
print('  git add -A && git commit -m "S95: Alpine bundled asset + ref audio extraction" && git push\n')
