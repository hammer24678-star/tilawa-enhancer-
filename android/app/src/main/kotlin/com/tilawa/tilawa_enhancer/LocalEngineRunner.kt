package com.tilawa.tilawa_enhancer

import android.app.Activity
import android.content.Context
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import kotlinx.coroutines.*
import java.io.*
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit

/** S65 — proot-based offline audio engine runner. */
class LocalEngineRunner(
    private val activity: Activity,
    private val context: Context
) {
    companion object {
        const val CHANNEL = "com.tilawa.tilawa_enhancer/local_engine"
        private const val DF_VERSION   = "0.5.6"
        private const val ALPINE_VER   = "3.18.9"
        private const val PROOT_VER    = "5.3.0"
    }

    private val dataDir     = context.filesDir
    private val alpineDir   = File(dataDir, "alpine-318")
    private val enginesDir  = File(dataDir, "engines")
    private val refAudioDir = File(dataDir, "reference_audio")
    private val prootBin    get() = File(context.applicationInfo.nativeLibraryDir, "libproot.so")
        private val prootLoader get() = File(context.applicationInfo.nativeLibraryDir, "libprootloader.so")
    private val cacheDir    = context.cacheDir

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var engineProc: Process? = null
    private var channel: MethodChannel? = null

    fun registerWith(flutterEngine: FlutterEngine) {
        channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
        channel!!.setMethodCallHandler { call, result ->
            when (call.method) {
                "isSetupComplete" -> result.success(isSetupComplete())
                "startSetup" -> { result.success(null); scope.launch { safeSetup() } }
                "runEngine"  -> {
                    result.success(null)
                    val a = call.arguments as Map<*, *>
                    scope.launch {
                        runEngine(a["engineId"] as String, a["inputPath"] as String)
                    }
                }
                "cancelEngine" -> { engineProc?.destroyForcibly(); engineProc = null; result.success(null) }
                else -> result.notImplemented()
            }
        }
    }

    fun isSetupComplete(): Boolean {
        // S76: check actual files on disk — never trust stale SharedPreferences
        if (!prootBin.exists()) return false
        if (!File(alpineDir, "usr/bin/python3").exists()) return false
        if (!File(alpineDir, "usr/bin/ffmpeg").exists()) return false
        if (!File(alpineDir, "usr/local/bin/deep-filter").exists()) return false
        if (enginesDir.list()?.isNotEmpty() != true) return false
        if (!File(dataDir, "libtalloc.so.2").exists()) return false
        return true
    }

    private suspend fun safeSetup() {
        try { setup(); ui { channel?.invokeMethod("setupDone", null) } }
        catch (e: Exception) {
            ui { channel?.invokeMethod("setupError", mapOf("msg" to (e.message ?: "Setup failed"))) }
        }
    }

    private fun progress(pct: Int, phase: String) {
        ui { channel?.invokeMethod("setupProgress", mapOf("pct" to pct, "phase" to phase)) }
    }

    private suspend fun setup() = withContext(Dispatchers.IO) {
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

        // 2. Alpine rootfs — bundled asset first, internet fallback
        if (!File(alpineDir, "usr/bin/busybox").exists()) {
            progress(12, "Extracting Alpine Linux (bundled)…")
            alpineDir.mkdirs()
            val tmp = File(dataDir, "alpine.tar.gz")
            // S95: try both possible Flutter asset paths
            var assetCopied = false
            for (ap in listOf(
                "flutter_assets/assets/alpine/alpine-rootfs.tar.gz",
                "assets/alpine/alpine-rootfs.tar.gz"
            )) {
                try {
                    context.assets.open(ap)
                        .use { src -> java.io.FileOutputStream(tmp).use { dst -> src.copyTo(dst) } }
                    assetCopied = true
                    progress(28, "Alpine bundle copied…")
                    break
                } catch (_: Exception) {}
            }
            if (!assetCopied) {
                // Fallback: download (requires internet)
                progress(14, "Downloading Alpine Linux (~4MB)…")
                val _url = "https://mirrors.edge.kernel.org/alpine/v3.21/releases/aarch64/alpine-minirootfs-3.21.3-aarch64.tar.gz"
                download(_url, tmp, "Alpine rootfs", 14, 32)
            }
            extractTarGz(tmp, alpineDir)
            tmp.delete()
            File(alpineDir, "etc/resolv.conf")
                .writeText("nameserver 8.8.8.8\nnameserver 1.1.1.1\n")
            for (d in listOf("proc","dev","sys")) File(alpineDir, d).mkdirs()

        }
        progress(35, "Alpine ready")

        // 3. Python + ffmpeg — installed via apk add
        if (!File(alpineDir, "usr/bin/python3").exists()) {
            progress(38, "Installing Python + ffmpeg via apk (4-8 min)…")
            val (rc1, out1) = runProot(listOf("/sbin/apk", "update", "--no-progress"), timeoutMin=10)
            if (rc1 != 0) throw IOException("apk update failed rc=$rc1: $out1")
            val (rc2, out2) = runProot(listOf("/sbin/apk", "add", "--no-progress", "python3", "py3-numpy", "py3-scipy", "ffmpeg"), timeoutMin=25)
            if (rc2 != 0) throw IOException("apk add failed rc=$rc2: $out2")
        }
        progress(78, "Python + ffmpeg ready")

        // 4. DeepFilter — bundled in APK assets/alpine/
        val dfBin = File(alpineDir, "usr/local/bin/deep-filter")
        if (!dfBin.exists()) {
            dfBin.parentFile?.mkdirs()
            try {
                progress(80, "Extracting DeepFilter…")
                context.assets.open("flutter_assets/assets/alpine/deep-filter")
                    .use { it.copyTo(FileOutputStream(dfBin)) }
                dfBin.setExecutable(true)
            } catch (_: Exception) {
                try {
                    progress(80, "Downloading DeepFilter…")
                    val dfVer = "0_5_6"
                    val url = "https://github.com/Rikorose/DeepFilterNet/releases/download/v0.5.6/deep-filter-${dfVer}-aarch64-unknown-linux-musl"
                    download(url, dfBin, "DeepFilter", 80, 88)
                    dfBin.setExecutable(true)
                } catch (_: Exception) {
                    progress(88, "DeepFilter unavailable — NR-only engines active")
                }
            }
        }
        progress(88, "DeepFilter ready")

        // 5. Engine scripts from APK assets
        progress(89, "Extracting engine scripts…")
        extractEngines()
        progress(92, "Engine scripts ready")

        // 6. Reference audio — extract from APK assets to refAudioDir
        progress(93, "Extracting reference audio…")
        refAudioDir.mkdirs()
        for (rf in listOf(
            "ref_araf_1425h.mp3",
            "ref_fath_1425h.mp3",
            "ref_fatir_1425h.mp3"
        )) {
            val dst = java.io.File(refAudioDir, rf)
            if (!dst.exists()) {
                for (ap in listOf(
                    "assets/reference_audio/$rf",
                    "assets/reference_audio/$rf"
                )) {
                    try {
                        context.assets.open(ap)
                            .use { src -> java.io.FileOutputStream(dst).use { d -> src.copyTo(d) } }
                        break
                    } catch (_: Exception) {}
                }
            }
        }
        progress(100, "Local engine ready!")
    }

    private suspend fun runEngine(engineId: String, inputPath: String) =
        withContext(Dispatchers.IO) {
        try {
            val script = mapOf(
                "v11.0" to "engine_tajalli_v1.py",
                "v11.1" to "true_engine_itiqan_v2_fixed.py",
                "v11.2" to "engine_isteidad_v12.py",
                "v10.0" to "engine_v100.py",
                "v9.0"  to "engine_v90.py",
                "v8.5"  to "engine_v85.py",
                "v8.0"  to "engine_v80.py",
                "v7.0"  to "engine_v70.py",
            )[engineId] ?: "engine_tajalli_v1.py"

            val outputPath = "${cacheDir.absolutePath}/tilawa_${engineId.replace('.','_')}_${System.currentTimeMillis()}.wav"
            val refMp3 = File(refAudioDir, "ref_araf_1425h.mp3")
            val inParent  = File(inputPath).parent ?: cacheDir.absolutePath

            val cmd = mutableListOf(
                prootBin.absolutePath,
                "--link2symlink", "-0",
                "-r", alpineDir.absolutePath,
                "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys",
                "-b", "${enginesDir.absolutePath}:/engines",
                "-b", "${refAudioDir.absolutePath}:/reference_audio",
                "-b", "$inParent:$inParent",
                "-b", "${cacheDir.absolutePath}:${cacheDir.absolutePath}",
                "-w", "/", "--kill-on-exit",
                "/usr/bin/python3", "/engines/$script",
                "-i", inputPath, "-o", outputPath,
                "--iterations", "3",
            )
            if (refMp3.exists()) cmd += listOf("--ref", "/reference_audio/ref_araf_1425h.mp3")

            val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {
                environment()["HOME"] = "/root"
                environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
                environment()["TERM"] = "xterm"
                environment()["LD_LIBRARY_PATH"] = dataDir.absolutePath
                val prootTmp = context.codeCacheDir.also { it.mkdirs() }
                environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath
            environment()["PROOT_LOADER"] = prootLoader.absolutePath
            }.start()
            engineProc = proc

            ui { channel?.invokeMethod("engineProgress", mapOf("pct" to 5, "msg" to "Engine started…")) }

            val reader = BufferedReader(InputStreamReader(proc.inputStream))
            var lastLine = ""; var lastJson: String? = null; var line: String?
            while (reader.readLine().also { line = it } != null) {
                val l = line!!.trim(); if (l.isEmpty()) continue
                lastLine = l
                if (l.startsWith("{") && l.contains("score")) lastJson = l
                ui { channel?.invokeMethod("engineProgress", mapOf("pct" to -1, "msg" to l)) }
            }

            val rc = try {
                if (!proc.waitFor(90, TimeUnit.MINUTES)) { proc.destroyForcibly(); -1 }
                else proc.exitValue()
            } catch (_: Exception) { -1 }

            val outFile = File(outputPath)
            if (rc == 0 && outFile.exists() && outFile.length() > 500) {
                val extra = if (lastJson != null) mapOf("json" to lastJson) else emptyMap<String,Any>()
                ui { channel?.invokeMethod("engineDone", mapOf("path" to outputPath) + extra) }
            } else {
                ui { channel?.invokeMethod("engineError", mapOf("msg" to "Engine failed (rc=$rc): $lastLine")) }
            }
        } catch (e: Exception) {
            ui { channel?.invokeMethod("engineError", mapOf("msg" to (e.message ?: "Unknown error"))) }
        } finally { engineProc = null }
    }

    private fun runProot(args: List<String>, timeoutMin: Int = 35): Pair<Int, String> {
        val cmd = mutableListOf(prootBin.absolutePath,
            "--link2symlink",
            "-0",
            "-r", alpineDir.absolutePath,
            "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys",
                        "-w", "/",
            "--kill-on-exit") + args
        val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {
            environment()["HOME"] = "/root"
            environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            environment()["TERM"] = "xterm"
            environment()["LD_LIBRARY_PATH"] = dataDir.absolutePath
            val prootTmp = context.codeCacheDir.also { it.mkdirs() }
            environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath
            environment()["PROOT_LOADER"] = prootLoader.absolutePath
        }.start()
        val output = proc.inputStream.bufferedReader().readText().takeLast(800)
        val code = try {
            if (!proc.waitFor(timeoutMin.toLong(), TimeUnit.MINUTES)) { proc.destroyForcibly(); -1 }
            else proc.exitValue()
        } catch (_: Exception) { proc.destroyForcibly(); -1 }
        return Pair(code, output)
    }

    private fun download(url: String, dest: File, label: String, p0: Int, p1: Int) {
        dest.parentFile?.mkdirs()
        var conn: HttpURLConnection? = null
        try {
            conn = URL(url).openConnection() as HttpURLConnection
            conn.connectTimeout = 30_000; conn.readTimeout = 300_000
            conn.instanceFollowRedirects = true; conn.connect()
            if (conn.responseCode !in 200..299)
                throw IOException("HTTP ${conn.responseCode} for $url")
            val total = conn.contentLengthLong; var done = 0L
            conn.inputStream.use { inp ->
                FileOutputStream(dest).use { out ->
                    val buf = ByteArray(65_536); var n: Int
                    while (inp.read(buf).also { n = it } != -1) {
                        out.write(buf, 0, n); done += n
                        if (total > 0) {
                            val pct = p0 + ((done.toDouble() / total) * (p1 - p0)).toInt()
                            ui { channel?.invokeMethod("setupProgress",
                                mapOf("pct" to pct, "phase" to "Downloading $label…")) }
                        }
                    }
                }
            }
        } finally { conn?.disconnect() }
    }

    private fun extractTarGz(tarGz: File, destDir: File) {
        destDir.mkdirs()
        java.util.zip.GZIPInputStream(tarGz.inputStream().buffered(65536)).use { gz ->
            val hdr = ByteArray(512)
            fun readFull(buf: ByteArray): Boolean {
                var off = 0
                while (off < buf.size) {
                    val n = gz.read(buf, off, buf.size - off)
                    if (n == -1) return false
                    off += n
                }
                return true
            }
            fun str(start: Int, len: Int) = String(hdr, start, len).trimEnd('').trim()
            fun skipPadded(size: Long) {
                if (size <= 0) return
                val pad = ((size + 511) / 512 * 512)
                var rem = pad; val tmp = ByteArray(4096)
                while (rem > 0) { val n = gz.read(tmp, 0, minOf(rem, 4096L).toInt()); if (n == -1) break; rem -= n }
            }
            while (true) {
                if (!readFull(hdr)) break
                if (hdr.all { it == 0.toByte() }) break
                val rawName = str(0, 100)
                val prefix  = str(345, 155)
                val size    = str(124, 12).toLongOrNull(8) ?: 0L
                val mode    = str(100, 8).toLongOrNull(8) ?: 0L
                val typeFlag= hdr[156].toInt().and(0xFF).toChar()
                val linkName= str(157, 100)
                val fullName= (if (prefix.isEmpty()) rawName else "$prefix/$rawName").trimStart('/')
                if (fullName.isEmpty() || fullName == "." || fullName.contains("..")) { skipPadded(size); continue }
                val dest = File(destDir, fullName)
                try {
                when (typeFlag) {
                    '1' -> { // Hardlink — copy source file
                        dest.parentFile?.mkdirs()
                        val src = File(destDir, linkName.trimStart('/'))
                        if (src.exists()) { src.copyTo(dest, overwrite = true)
                            if (mode and 0b001_000_001L != 0L) dest.setExecutable(true, false) }
                        skipPadded(size)
                    }
                    '0', '', '7' -> {
                        dest.parentFile?.mkdirs()
                        FileOutputStream(dest).use { out ->
                            var rem = size; val buf = ByteArray(8192)
                            while (rem > 0) { val n = gz.read(buf, 0, minOf(rem, 8192L).toInt()); if (n == -1) break; out.write(buf, 0, n); rem -= n }
                        }
                        // Proper padded skip loop (single gz.read may return partial)
                        var remPad = ((512 - (size % 512)) % 512)
                        val padBuf = ByteArray(512)
                        while (remPad > 0) { val n = gz.read(padBuf, 0, minOf(remPad, 512L).toInt()); if (n == -1) break; remPad -= n }
                        if (mode and 0b001_000_001L != 0L) dest.setExecutable(true, false)
                    }
                    '2' -> {
                        dest.parentFile?.mkdirs(); dest.delete()
                        try { android.system.Os.symlink(linkName, dest.absolutePath) } catch (_: Exception) {}
                        skipPadded(size)
                    }
                    '5' -> { dest.mkdirs(); skipPadded(size) }
                    else -> skipPadded(size)
                }
                } catch (_: Exception) { /* skip bad entry, continue */ }
            }
        }
    }

    private fun extractEngines() {
        enginesDir.mkdirs()
        listOf("engine_tajalli_v1.py","true_engine_itiqan_v2_fixed.py",
               "engine_isteidad_v12.py","naqaa_v1_tested.py","bayan_ve_v2fix.py",
               "noor_v5.py","ihyaa_ve.py","engine_v100.py","engine_v90.py",
               "engine_v85.py","engine_v80.py","engine_v70.py").forEach { name ->
            val dest = File(enginesDir, name)
            if (dest.exists() && dest.length() > 1024) return@forEach  // S88: skip only if real file
            try { context.assets.open("flutter_assets/assets/engines/$name").use { inp ->
                FileOutputStream(dest).use { inp.copyTo(it) } }
            } catch (_: Exception) {
                try { context.assets.open("assets/engines/$name").use { inp ->
                    FileOutputStream(dest).use { inp.copyTo(it) } }
                } catch (_: Exception) {}
            }
        }
    }

    // downloadRefAudio() removed — ref audio now bundled in APK assets

    private fun ui(block: () -> Unit) = activity.runOnUiThread(block)
}
