#!/usr/bin/env python3
"""
tilawa_fix_s75.py — Two fixes in patch_android.py:

  FIX A: Bundle everything into APK (no downloads at runtime)
         Alpine rootfs tar.gz + Python env tar.gz go into assets/
         Setup just extracts them — no internet needed, instant.

  FIX B: Fix Alpine extraction — /bin/sh missing because Android's
         tar doesn't handle symlinks. Use our custom extractTarGz
         which already handles this, but add fallback /bin/sh symlink.

Run from ~/tilawa-enhancer
"""
from pathlib import Path
from datetime import datetime

F = Path('patch_android.py')
content = F.read_text(encoding='utf-8')
ok = 0; fail = 0

print(f'\n{"="*58}')
print(f'  tilawa_fix_s75  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
print(f'{"="*58}\n')

def rep(old, new, lbl):
    global content, ok, fail
    if old in content:
        content = content.replace(old, new, 1)
        print(f'  OK  {lbl}'); ok += 1
    else:
        print(f'  XX  NOT FOUND — {lbl}'); fail += 1

# ── FIX A+B: Replace entire setup() with bundled-asset version ───────────────
rep(
    '''    private suspend fun setup() = withContext(Dispatchers.IO) {
        val arch   = System.getProperty("os.arch") ?: "aarch64"
        val isArm  = arch.contains("aarch64") || arch.contains("arm")
        val archStr = if (isArm) "aarch64" else "x86_64"

        progress(1, "Detecting device ($archStr)…")

        // 1. Use bundled libproot.so from nativeLibraryDir (always executable on Android)
        //    Android 10+ marks filesDir as noexec — downloaded binaries cannot run there.
        //    libproot.so lives in /data/app/.../lib/ which has exec permission.
        if (!prootBin.exists()) throw Exception("libproot.so not found in nativeLibraryDir")
        if (!prootBin.canExecute()) prootBin.setExecutable(true)
        // libtalloc.so.2 must be in filesDir so the dynamic linker finds it
        val tallocSrc = File(context.applicationInfo.nativeLibraryDir, "libtalloc2.so")
        val tallocDst = File(dataDir, "libtalloc.so.2")
        if (tallocSrc.exists() && !tallocDst.exists())
            tallocSrc.copyTo(tallocDst, overwrite = true)
        progress(10, "proot ready (bundled libproot.so)")

        // 2. Alpine rootfs
        if (!File(alpineDir, "usr/bin/busybox").exists()) {
            progress(12, "Downloading Alpine Linux $ALPINE_VER…")
            val url = "https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/$archStr/" +
                      "alpine-minirootfs-$ALPINE_VER-$archStr.tar.gz"
            val tar = File(dataDir, "alpine.tar.gz")
            download(url, tar, "Alpine rootfs", 12, 32)
            progress(32, "Extracting Alpine…")
            alpineDir.mkdirs()
            extractTarGz(tar, alpineDir)
            tar.delete()
            File(alpineDir, "etc/resolv.conf")
                .writeText("nameserver 8.8.8.8\\nnameserver 1.1.1.1\\n")
            File(alpineDir, "proc").mkdirs()
            File(alpineDir, "dev").mkdirs()
            File(alpineDir, "sys").mkdirs()
            // Fix Alpine 3.19+ symlinks that Android tar may not create
            val root = alpineDir.toPath()
            for (pair in listOf("bin" to "usr/bin", "lib" to "usr/lib", "sbin" to "usr/sbin")) {
                val link = root.resolve(pair.first)
                if (!java.nio.file.Files.exists(link)) {
                    try { java.nio.file.Files.createSymbolicLink(link, java.nio.file.Paths.get(pair.second)) }
                    catch (_: Exception) {}
                }
            }
        }
        // Diagnose what tar actually extracted
        val binDir = File(alpineDir, "bin")
        val binContents = binDir.listFiles()?.joinToString(",") { it.name } ?: "bin/ missing"
        val usrBinContents = File(alpineDir, "usr/bin").listFiles()?.take(5)?.joinToString(",") { it.name } ?: "usr/bin/ missing"
        val libExists = File(alpineDir, "lib/ld-musl-aarch64.so.1").exists()
        progress(36, "Alpine: bin=[$binContents] usrbin=[$usrBinContents] musl=$libExists")
        android.os.SystemClock.sleep(8000) // pause so user can read

        // 3. Python + scipy + ffmpeg
        if (!File(alpineDir, "usr/bin/python3").exists()) {
            progress(38, "Installing Python + ffmpeg (4–8 min, ~120 MB)…")
            val (rc1, out1) = runProot(listOf("/bin/sh", "-c", "apk update --no-progress 2>&1"), timeoutMin = 10)
            if (rc1 != 0) throw IOException("apk update failed rc=$rc1: $out1")
            val (rc, out) = runProot(listOf("/bin/sh", "-c",
                "apk add --no-progress python3 py3-numpy py3-scipy ffmpeg 2>&1"), timeoutMin = 20)
            if (rc != 0) throw IOException("apk add failed rc=$rc: $out")
        }
        progress(78, "Python + ffmpeg ready")

        // 4. DeepFilter binary
        val dfBin = File(alpineDir, "usr/local/bin/deep-filter")
        if (!dfBin.exists()) {
            progress(80, "Downloading DeepFilter v$DF_VERSION…")
            val dfVer = DF_VERSION.replace(".", "_")
            val dfUrl = "https://github.com/Rikorose/DeepFilterNet/releases/download/" +
                        "v$DF_VERSION/deep-filter-${dfVer}-$archStr-unknown-linux-musl"
            dfBin.parentFile?.mkdirs()
            download(dfUrl, dfBin, "DeepFilter", 80, 88)
            dfBin.setExecutable(true)
        }
        progress(88, "DeepFilter ready")

        // 5. Engine scripts from APK assets
        progress(89, "Extracting engine scripts…")
        extractEngines()
        progress(92, "Engine scripts ready")

        // 6. Reference audio
        progress(93, "Downloading reference audio…")
        downloadRefAudio()
        progress(100, "Local engine ready!")
    }''',

    '''    private suspend fun setup() = withContext(Dispatchers.IO) {
        progress(1, "Preparing local engine…")

        // 1. proot + libtalloc — from nativeLibraryDir (always executable)
        if (!prootBin.exists()) throw Exception("libproot.so missing from APK")
        if (!prootBin.canExecute()) prootBin.setExecutable(true)
        val tallocSrc = File(context.applicationInfo.nativeLibraryDir, "libtalloc2.so")
        val tallocDst = File(dataDir, "libtalloc.so.2")
        if (tallocSrc.exists() && !tallocDst.exists())
            tallocSrc.copyTo(tallocDst, overwrite = true)
        progress(5, "proot ready")

        // 2. Alpine rootfs — bundled in APK assets (no download needed)
        if (!File(alpineDir, "usr/bin/busybox").exists()) {
            progress(10, "Extracting Alpine Linux (bundled)…")
            alpineDir.mkdirs()
            context.assets.open("alpine/alpine-rootfs.tar.gz").use { inp ->
                val tmp = File(dataDir, "alpine.tar.gz")
                tmp.outputStream().use { inp.copyTo(it) }
                extractTarGz(tmp, alpineDir)
                tmp.delete()
            }
            File(alpineDir, "etc/resolv.conf")
                .writeText("nameserver 8.8.8.8\\nnameserver 1.1.1.1\\n")
            File(alpineDir, "proc").mkdirs()
            File(alpineDir, "dev").mkdirs()
            File(alpineDir, "sys").mkdirs()
            // Ensure /bin/sh exists (symlink or copy from busybox)
            val sh = File(alpineDir, "bin/sh")
            if (!sh.exists()) {
                val busybox = File(alpineDir, "bin/busybox")
                if (busybox.exists()) busybox.copyTo(sh, overwrite = true)
                else {
                    val usrBusybox = File(alpineDir, "usr/bin/busybox")
                    if (usrBusybox.exists()) usrBusybox.copyTo(sh, overwrite = true)
                }
                sh.setExecutable(true)
            }
        }
        progress(35, "Alpine ready")

        // 3. Python env — bundled in APK assets (no apk add needed)
        if (!File(alpineDir, "usr/bin/python3").exists()) {
            progress(38, "Extracting Python + ffmpeg (bundled)…")
            context.assets.open("alpine/python-env.tar.gz").use { inp ->
                val tmp = File(dataDir, "python-env.tar.gz")
                tmp.outputStream().use { inp.copyTo(it) }
                extractTarGz(tmp, alpineDir)
                tmp.delete()
            }
        }
        progress(78, "Python + ffmpeg ready")

        // 4. DeepFilter binary — bundled in APK assets
        val dfBin = File(alpineDir, "usr/local/bin/deep-filter")
        if (!dfBin.exists()) {
            progress(80, "Extracting DeepFilter (bundled)…")
            dfBin.parentFile?.mkdirs()
            context.assets.open("alpine/deep-filter").use { inp ->
                FileOutputStream(dfBin).use { inp.copyTo(it) }
            }
            dfBin.setExecutable(true)
        }
        progress(88, "DeepFilter ready")

        // 5. Engine scripts from APK assets
        progress(89, "Extracting engine scripts…")
        extractEngines()
        progress(95, "Engine scripts ready")

        // 6. Reference audio — bundled in APK assets
        progress(96, "Extracting reference audio…")
        refAudioDir.mkdirs()
        for (f in listOf("ref_araf_1425h.mp3","ref_fath_1425h.mp3","ref_fatir_1425h.mp3")) {
            val dest = File(refAudioDir, f)
            if (!dest.exists()) {
                try {
                    context.assets.open("reference_audio/$f").use { inp ->
                        FileOutputStream(dest).use { inp.copyTo(it) }
                    }
                } catch (_: Exception) {}
            }
        }
        progress(100, "Local engine ready — fully offline!")
    }''',
    'setup(): full offline bundle — Alpine + Python + DeepFilter from APK assets'
)

# ── Remove downloadRefAudio() since it's no longer called ────────────────────
rep(
    '''    private fun downloadRefAudio() {
        refAudioDir.mkdirs()
        val base = "https://carm5333-tilawa-server.hf.space/reference_audio/"
        listOf("ref_araf_1425h.mp3","ref_fath_1425h.mp3","ref_fatir_1425h.mp3")
            .forEach { f ->
                val dest = File(refAudioDir, f)
                if (dest.exists() && dest.length() > 10_000) return@forEach
                try { download("$base$f", dest, f, 93, 99) } catch (_: Exception) {}
            }
    }''',
    '''    // downloadRefAudio() removed — ref audio now bundled in APK assets''',
    'remove downloadRefAudio() — now bundled'
)

F.write_text(content, encoding='utf-8')
print(f'\n  {ok} OK   {fail} FAIL')
if fail == 0:
    print('''
  NEXT STEPS — build the asset bundles on the server:
  See build_assets.sh for instructions.
  Then: git add -A && git commit -m "S75: fully offline APK — all assets bundled" && git push
''')
