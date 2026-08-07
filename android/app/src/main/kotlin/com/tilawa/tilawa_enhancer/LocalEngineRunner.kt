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
        private const val ALPINE_VER   = "3.21.3"
        private const val PROOT_VER    = "5.3.0"
        // S229: bump whenever the bundled alpine-rootfs/python-env ABI
        // pairing changes. A mismatch (or missing stamp) on an existing
        // alpineDir means it was extracted by a pre-S229 build that could
        // have mixed Alpine versions (3.18 rootfs + 3.21 ffmpeg/numpy) —
        // force one clean wipe so upgrading the app actually fixes a
        // phone that already hit the ffmpeg "symbol not found" bug.
        private const val PYENV_BUILD_ID = "s229-alpine3213-unified"

        // S259: one table for engine id -> script, used by BOTH runEngine()
        // and extractEngines().
        //
        // Those were two independent literal lists and they had drifted:
        // extraction asked the APK for engine_v90.py and engine_v80.py, which
        // exist nowhere in this project, while runEngine() pointed v9.0/v8.0
        // at them. Every extraction failure was swallowed, setup still
        // reported success, and picking either engine died inside proot with
        // "can't open file" and no explanation. v9.0 and v8.0 are gone from
        // here because they have no script anywhere — availableLocalEngines()
        // now tells the UI that, instead of offering a guaranteed failure.
        val ENGINE_SCRIPTS: Map<String, String> = mapOf(
            "v11.0" to "engine_safaa_v4.py",           // S199-BUG-2: tajalli file never existed
            "v11.1" to "engine_itiqan_v6_official.py", // S199-BUG-3: ditto
            "v11.2" to "engine_isteidad_v21.py",
            "v11.3" to "ihyaa_ve.py",                  // S199-BUG-4: real bundled filename
            "v10.0" to "engine_v100.py",
            "v8.5"  to "engine_v85.py",
            "v7.0"  to "engine_v70.py",
        )

        // Helper scripts the engines above import or shell out to.
        val SUPPORT_SCRIPTS = listOf(
            "idrak_text_v2.py", "miraat_ref_v2.py", "hakim_gen_v2.py",
            "naqaa_v1_tested.py", "bayan_ve_v2fix.py", "noor_v5.py",
        )

        // S259: engines whose argparse actually declares --ref.
        //
        // argparse exits 2 on an unrecognised flag before doing any work, so
        // handing --ref to an engine that does not declare it means that
        // engine can never run offline — it dies with "unrecognized
        // arguments" and writes no output at all.
        //
        // This used to be inferred from the script name (everything not named
        // engine_safaa* got --ref). ihyaa_ve.py is not named engine_safaa* and
        // does not declare --ref, so v11.3 — the newest engine — was handed
        // three --ref flags on every run and had never once worked offline.
        val REF_SCRIPTS = setOf(
            "engine_itiqan_v6_official.py", "engine_isteidad_v21.py",
            "engine_v100.py", "engine_v85.py", "engine_v70.py",
        )
    }

    private val dataDir     = context.filesDir
    private val alpineDir   = File(dataDir, "alpine-318")
    private val enginesDir  = File(dataDir, "engines")
    private val refAudioDir = File(dataDir, "reference_audio")
    private val prootBin    get() = File(context.applicationInfo.nativeLibraryDir, "libproot.so")
    private val prootLoader get() = File(context.applicationInfo.nativeLibraryDir, "libprootloader.so")
    private val cacheDir    = context.cacheDir.canonicalFile

    // S212: dynamic Python-version detection. Alpine bumps its default
    // Python minor version over time (3.11 → 3.12 → 3.14 observed so far);
    // hardcoding "python3.11"/"python3.12" caused numpy/scipy detection to
    // silently fail — and PYTHONPATH to omit the real site-packages dir —
    // the moment a freshly-built python-env.tar.gz shipped a newer Python.
    private fun pySiteVersionDirs(): List<File> =
        File(alpineDir, "usr/lib").listFiles { f ->
            f.isDirectory && f.name.matches(Regex("python3\\.\\d+")) &&
                File(f, "site-packages").exists()
        }?.toList() ?: emptyList()

    private fun hasPySysPackage(name: String): Boolean {
        if (pySiteVersionDirs().any { File(it, "site-packages/$name").exists() }) return true
        return File(alpineDir, "usr/lib/python3/dist-packages/$name").exists()
    }

    private fun pythonPathForProot(): String {
        val versioned = pySiteVersionDirs().map { "/usr/lib/${it.name}/site-packages" }
        return (versioned + listOf("/usr/lib/python3/dist-packages", "/tilawa_numpy")).joinToString(":")
    }

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
                        runEngine(a["engineId"] as String, a["inputPath"] as String,
                            (a["aggressive"] as? Boolean) ?: false)  // S173
                    }
                }
                "cancelEngine" -> { engineProc?.destroyForcibly(); engineProc = null; result.success(null) }
                "scanFile" -> {
                    val path = (call.arguments as Map<*, *>)["path"] as String
                    android.media.MediaScannerConnection.scanFile(
                        context, arrayOf(path), null, null)
                    result.success(null)
                }
                "isBasicSetupComplete" -> result.success(isBasicSetupComplete()) // S193
                // S259: the Dart side has called this since S250 and it was
                // never registered here, so every call threw
                // MissingPluginException, was caught, and came back as an
                // empty list — which callers read as "unknown, don't restrict
                // anything". That is how local mode kept offering engines
                // whose script is not in the APK.
                "availableLocalEngines" -> result.success(availableLocalEngines())
                // S237: component-level diagnostics for the Settings health panel —
                // shows the user exactly WHICH piece of local mode is missing/broken
                // instead of a single opaque "setup required" boolean.
                "getSetupStatus" -> scope.launch {
                    val st = computeSetupStatus()
                    ui { result.success(st) }
                }
                // S259: probes the environment by running it — see diagnose().
                // Off the main thread: it starts two proot processes.
                "diagnose" -> scope.launch {
                    val d = diagnose()
                    ui { result.success(d) }
                }
                // S237: frees tilawa_* work files (engine inputs/outputs, editor
                // temp exports) that used to accumulate in cacheDir forever.
                "clearEngineCache" -> scope.launch {
                    val r = clearEngineCache(0L)  // 0 = everything, any age
                    ui { result.success(r) }
                }
                "runProotCmd" -> {  // S202: was missing entirely — every audio-editor
                    // export (and any LocalEngineService.runProotCmd caller) fell through
                    // to notImplemented() below and threw a MissingPluginException in Dart.
                    val a       = call.arguments as Map<*, *>
                    val cmd     = (a["cmd"] as? String) ?: ""
                    val inFile  = (a["inputPath"] as? String) ?: ""
                    val outFile = (a["outputPath"] as? String) ?: ""
                    val tmMin   = (a["timeoutMin"] as? Int) ?: 10
                    scope.launch {
                        val extra = mutableListOf<String>()
                        listOf(inFile, outFile).forEach { p ->
                            if (p.isEmpty()) return@forEach
                            val dir = File(p).parent ?: return@forEach
                            extra += listOf("-b", "$dir:$dir")
                        }
                        extra += listOf("-b", "${cacheDir.absolutePath}:${cacheDir.absolutePath}")
                        context.getExternalFilesDir(null)?.absolutePath?.let { ed ->
                            extra += listOf("-b", "$ed:$ed") }
                        val (rc, out) = runProotWithBinds(listOf("/bin/sh", "-c", cmd), extra, tmMin)
                        ui { result.success(mapOf("rc" to rc, "out" to out)) }
                    }
                }
                else -> result.notImplemented()
            }
        }
    }

    // S193: lightweight check for callers that only need proot + ffmpeg
    // (e.g. the audio editor's plain ffmpeg trim/EQ/export) — unlike
    // isSetupComplete() below, this does NOT require numpy, deep-filter,
    // or any downloaded restoration engine, none of which plain ffmpeg
    // filter chains touch.
    fun isBasicSetupComplete(): Boolean {
        if (!prootBin.exists()) return false
        if (!File(alpineDir, "usr/bin/python3").exists()) return false
        val hasLibPython = File(alpineDir, "usr/lib").listFiles()
            ?.any { it.name.startsWith("libpython") && it.name.contains(".so") } ?: false
        if (!hasLibPython) return false
        if (!File(alpineDir, "usr/bin/ffmpeg").exists()) return false
        return true
    }

    fun isSetupComplete(): Boolean {
        if (!File(dataDir, ".tilawa_setup_done").exists()) return false
        if (!prootBin.exists()) return false
        if (!File(alpineDir, "usr/bin/python3").exists()) return false
        // S178: python3 binary alone isn't enough — without its matching
        // libpythonX.Y.so every engine run fails with rc=127.
        val hasLibPython = File(alpineDir, "usr/lib").listFiles()
            ?.any { it.name.startsWith("libpython") && it.name.contains(".so") } ?: false
        if (!hasLibPython) return false
        if (!File(alpineDir, "usr/bin/ffmpeg").exists()) return false
        // S223: gate on .numpy_verified ONLY. That marker is now written by
        // numpyWorks() strictly after a real proot import probe passes (see
        // S223 fix above) — a directory existing is no longer enough, since
        // a dropped shared-library symlink can leave numpy's folder present
        // but the module unimportable. This is what actually gates whether
        // the setup screen is allowed to say "ready".
        if (!File(alpineDir, ".numpy_verified").exists()) return false  // S148/S223
        val df = File(alpineDir, "usr/local/bin/deep-filter")
        if (!df.exists() || df.length() < 1_000_000L) return false
        // S-DF3ARCH: reject if binary is not aarch64 — x86_64 runs setup but
        // silently fails inside proot on phone → engine prints [A5] and skips DF3.
        // ELF e_machine bytes 18-19: aarch64=0xB7,0x00  x86_64=0x3E,0x00
        val dfOkArch = try {
            val h = ByteArray(20); FileInputStream(df).use { it.read(h) }
            h[18] == 0xB7.toByte() && h[19] == 0x00.toByte()
        } catch (_: Exception) { false }
        if (!dfOkArch) return false
        if (enginesDir.list()?.isNotEmpty() != true) return false
        return true
    }

    // ── S237: health status + cache management ──────────────────────────────

    private fun dirSizeBytes(dir: File): Long {
        if (!dir.exists()) return 0L
        var total = 0L
        try { dir.walkTopDown().forEach { if (it.isFile) total += it.length() } }
        catch (_: Exception) {}
        return total
    }

    private fun computeSetupStatus(): Map<String, Any> {
        val df = File(alpineDir, "usr/local/bin/deep-filter")
        val dfArchOk = try {
            val h = ByteArray(20); FileInputStream(df).use { it.read(h) }
            h[18] == 0xB7.toByte() && h[19] == 0x00.toByte()
        } catch (_: Exception) { false }
        val hasLibPython = File(alpineDir, "usr/lib").listFiles()
            ?.any { it.name.startsWith("libpython") && it.name.contains(".so") } ?: false
        val cacheFiles = cacheDir.listFiles()?.filter { it.isFile && it.name.startsWith("tilawa_") } ?: emptyList()
        return mapOf(
            "proot"        to prootBin.exists(),
            "python"       to File(alpineDir, "usr/bin/python3").exists(),
            "libpython"    to hasLibPython,
            "ffmpeg"       to File(alpineDir, "usr/bin/ffmpeg").exists(),
            "numpy"        to File(alpineDir, ".numpy_verified").exists(),
            "scipy"        to File(alpineDir, ".scipy_verified").exists(),
            "deepFilter"   to (df.exists() && df.length() > 1_000_000L && dfArchOk),
            "engines"      to (enginesDir.list()?.count { it.endsWith(".py") } ?: 0),
            "refAudio"     to (refAudioDir.list()?.count { it.endsWith(".mp3") } ?: 0),
            "setupDone"    to File(dataDir, ".tilawa_setup_done").exists(),
            "buildId"      to (File(alpineDir, ".pyenv_build_id").takeIf { it.exists() }?.readText()?.trim() ?: ""),
            "cacheBytes"   to cacheFiles.sumOf { it.length() },
            "cacheFiles"   to cacheFiles.size,
            "runtimeBytes" to dirSizeBytes(alpineDir),
            "freeBytes"    to dataDir.usableSpace,
        )
    }

    /** S259: what actually WORKS, probed by running it.
     *
     *  computeSetupStatus() above answers with File.exists() only, which is
     *  why a rootfs that extracted but cannot execute anything presented as
     *  "everything fine" while every operation failed. The Dart side has
     *  asked for this map since S250h — the audio editor uses it to tell
     *  "not set up" apart from "set up but broken", and to show the
     *  "ffmpeg is installed but cannot start" message — but the method was
     *  never registered on the channel, so the call always threw
     *  MissingPluginException and the diagnostics panel stayed empty.
     *
     *  Runs two short commands inside proot, so call it off the main thread.
     */
    fun diagnose(): Map<String, Any> {
        val pythonFile = File(alpineDir, "usr/bin/python3").exists()
        val ffmpegFile = File(alpineDir, "usr/bin/ffmpeg").exists()
        val filesOk    = prootBin.exists() && pythonFile && ffmpegFile

        var ffOk = false; var ffErr = ""
        var npOk = false; var npErr = ""
        if (filesOk) {
            try {
                val (rc, out) = runProot(
                    listOf("/usr/bin/ffmpeg", "-hide_banner", "-version"), 2)
                ffOk = rc == 0; ffErr = if (rc == 0) "" else out
            } catch (e: Exception) { ffErr = e.message ?: "ffmpeg probe failed" }
            try {
                val (rc, out) = runProot(listOf("/usr/bin/python3", "-c",
                    "import numpy; print(numpy.__version__)"), 3)
                npOk = rc == 0; npErr = if (rc == 0) "" else out
            } catch (e: Exception) { npErr = e.message ?: "numpy probe failed" }
        }

        val stamp = File(alpineDir, ".pyenv_build_id")
        return mapOf(
            "proot"         to prootBin.exists(),
            "python_file"   to pythonFile,
            "ffmpeg_file"   to ffmpegFile,
            "ffmpeg_runs"   to ffOk,
            "numpy_imports" to npOk,
            "env_stamp_ok"  to (stamp.exists() &&
                                stamp.readText().trim() == PYENV_BUILD_ID),
            "ffmpeg_error"  to ffErr.takeLast(400),
            "numpy_error"   to npErr.takeLast(400),
        )
    }

    /** Deletes tilawa_* work files in cacheDir older than [maxAgeMs] (0 = all).
     *  Returns {freedBytes, deletedFiles}. */
    private fun clearEngineCache(maxAgeMs: Long): Map<String, Any> {
        var freed = 0L; var count = 0
        val cutoff = System.currentTimeMillis() - maxAgeMs
        cacheDir.listFiles()?.forEach { f ->
            if (f.isFile && f.name.startsWith("tilawa_") &&
                (maxAgeMs == 0L || f.lastModified() < cutoff)) {
                val len = f.length()
                if (f.delete()) { freed += len; count++ }
            }
        }
        return mapOf("freedBytes" to freed, "deletedFiles" to count)
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

        // S237: disk-space preflight — extraction needs the tar.gz + the
        // unpacked rootfs simultaneously (~700 MB worst case). Fail with a
        // clear message now instead of a cryptic mid-extraction write error.
        val alreadyInstalled = File(alpineDir, "usr/bin/busybox").exists() &&
            File(alpineDir, "usr/bin/python3").exists()
        if (!alreadyInstalled) {
            val freeMb = dataDir.usableSpace / 1_048_576L
            if (freeMb < 700) throw IOException(
                "Not enough storage: ${freeMb} MB free, ~700 MB needed during setup. " +
                "Free up space and retry.")
        }

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

        // S229: one-time wipe if this alpineDir predates the Alpine
        // rootfs/python-env version-unification fix (or was built by a
        // CI run that mixed two different Alpine versions — see this
        // script's header). Cheap check; only touches disk when the
        // stamp is missing/stale, i.e. at most once per app upgrade.
        val buildIdMarker = File(alpineDir, ".pyenv_build_id")
        val buildIdOk = buildIdMarker.exists() &&
            buildIdMarker.readText().trim() == PYENV_BUILD_ID
        if (File(alpineDir, "usr/bin/busybox").exists() && !buildIdOk) {
            progress(11, "Updating local engine runtime (one-time)…")
            alpineDir.deleteRecursively()
            alpineDir.mkdirs()
            context.getSharedPreferences("tilawa_local", 0)
                .edit().putBoolean("setup_complete", false).apply()
        }

        // 2. Alpine rootfs — download like Termux proot-distro
        if (!File(alpineDir, "usr/bin/busybox").exists()) {
            progress(12, "Extracting Alpine Linux (bundled)…")
            alpineDir.mkdirs()
            val tmp = File(dataDir, "alpine.tar.gz")
            var alpineOk = false
            try {
                context.assets.open("flutter_assets/assets/alpine/alpine-rootfs.tar.gz")
                    .use { it.copyTo(java.io.FileOutputStream(tmp)) }
                alpineOk = true
            } catch (_: Exception) {
                // S206: fall back to the old (wrong) un-prefixed path just in case —
                // the prefixed attempt above is the one that actually matches
                // Flutter's AssetManager namespace and will now succeed.
                try {
                    context.assets.open("alpine/alpine-rootfs.tar.gz")
                        .use { it.copyTo(java.io.FileOutputStream(tmp)) }
                    alpineOk = true
                } catch (_: Exception) {}
            }
            if (!alpineOk) {
                progress(12, "Downloading Alpine Linux (~4MB)…")
                download("https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/${archStr}/alpine-minirootfs-3.21.3-${archStr}.tar.gz", tmp, "Alpine rootfs", 12, 32)  // S195-BUG5
            }
            extractTarGz(tmp, alpineDir)
            tmp.delete()
            File(alpineDir, "etc/resolv.conf")
                .writeText("nameserver 8.8.8.8\nnameserver 1.1.1.1\n")
            for (d in listOf("proc","dev","sys")) File(alpineDir, d).mkdirs()

        }
        // S195-BUG7: detect any non-3.11 Python so (3.12, 3.13, …)
        val py311lib  = File(alpineDir, "usr/lib/python3.11")
        val pyLibDir  = File(alpineDir, "usr/lib")
        val wrongPyLib = pyLibDir.listFiles { f ->
            f.name.matches(Regex("libpython3\\.(1[2-9]|[2-9]\\d*)\\.so.*"))  // S200: fix wrongPyLib escape seqs
        }?.isNotEmpty() == true
        // S201-BUG1: only wipe if numpy is NOT available for the current Python.
        // The bundle ships Python 3.12; wiping destroys a working installation.
        val sysNumpyOk = hasPySysPackage("numpy")  // S212: was hardcoded 3.11/3.12 —
            // false-triggered a full alpine rootfs wipe on every setup() run
            // once python-env.tar.gz shipped Python 3.14 (S211's fixed ffmpeg
            // bundle was being silently deleted by this exact check).
        if (wrongPyLib && !py311lib.exists() && !sysNumpyOk) {
            progress(11, "Fixing Python version conflict…")
            alpineDir.deleteRecursively()
            alpineDir.mkdirs()
            context.getSharedPreferences("tilawa_local", 0)
                .edit().putBoolean("setup_complete", false).apply()
        }
        progress(35, "Alpine ready")

        // 3. Python + ffmpeg — try bundled asset, else download from release  // S89-PYENV
        // S229: a bare "numpy" folder existing is not enough — a pip
        // install that fell back to an unbuildable sdist (no C/Fortran
        // toolchain in this proot) can leave numpy's raw *source* tree
        // here, which numpy's own import guard refuses to load. Only
        // trust the cache if a compiled extension module is present.
        val pipNumpyDir = File(alpineDir, "tilawa_numpy/numpy")
        val pipNumpyReallyBuilt = pipNumpyDir.exists() &&
            (pipNumpyDir.walkTopDown().any { it.name.endsWith(".so") })
        if (pipNumpyDir.exists() && !pipNumpyReallyBuilt) {
            File(alpineDir, "tilawa_numpy").deleteRecursively()  // broken source tree
        }
        val numpyOk = hasPySysPackage("numpy") ||  // S212: was hardcoded 3.11/3.12
            pipNumpyReallyBuilt  // S142/S229: match isSetupComplete(), require a real build
        if (!File(alpineDir, "usr/bin/python3").exists() || !numpyOk) {  // S115: re-extract if numpy missing
            val tmp2 = File(dataDir, "python-env.tar.gz")
            var pyOk = false
            // Try bundled asset first
            try {
                progress(38, "Extracting Python + ffmpeg (bundled)…")
                context.assets.open("flutter_assets/assets/alpine/python-env.tar.gz")
                    .use { it.copyTo(FileOutputStream(tmp2)) }
                pyOk = true
            } catch (_: Exception) {
                // S206: same missing-prefix bug as alpine-rootfs above — see this
                // script's header for why this one mattered most (it gates both
                // isBasicSetupComplete() and isSetupComplete()).
                try {
                    context.assets.open("alpine/python-env.tar.gz")
                        .use { it.copyTo(FileOutputStream(tmp2)) }
                    pyOk = true
                } catch (_: Exception) {}
            }
            // Fallback: download from GitHub Release
            if (!pyOk) {
                progress(38, "Downloading Python + ffmpeg (~135 MB, one-time)…")
                val pyUrl = "https://github.com/hammer24678-star/tilawa-enhancer-/releases/download/latest/python-env.tar.gz"
                download(pyUrl, tmp2, "Python env", 38, 75)
                pyOk = tmp2.exists() && tmp2.length() > 1_000_000
            }
            if (!pyOk) throw IOException("python-env.tar.gz unavailable — check internet connection")
            progress(75, "Extracting Python + ffmpeg…")
            extractTarGz(tmp2, alpineDir)
            tmp2.delete()
        }
        // S223: numpyWorks() now ALWAYS runs a real proot import probe —
        // trusting bare directory existence for the "system" path let a
        // rootfs with a present-but-unimportable numpy/scipy (e.g. a
        // shared-library symlink dropped by extractTarGz — see S223 fix
        // below) report setup as permanently "complete". Install order is
        // apk (Alpine's own prebuilt musl binaries — free, no compiler
        // needed) → pip → pip retry-after-wipe, and a final failure now
        // surfaces the real apk/pip/import output instead of a generic
        // "check internet connection" message.
        val numpyTarget = File(alpineDir, "tilawa_numpy")
        val numpyVerifiedMarker = File(alpineDir, ".numpy_verified")
        val scipyVerifiedMarker = File(alpineDir, ".scipy_verified")  // S226
        var lastNumpyProbe = ""
        // S226 BUG FIX: this used to be ONE probe — `import numpy, scipy; ... import
        // scipy.linalg` — so a scipy-only failure (very common on-device: scipy has no
        // prebuilt pip wheel for most Android aarch64 targets and needs a Fortran/BLAS
        // toolchain to build from source, unlike numpy which installs from a wheel
        // almost everywhere) permanently failed setup and deleted .numpy_verified, even
        // though S225 already made every local engine run fine on numpy alone. numpy
        // and scipy are now probed and gated completely independently.
        fun numpyWorks(): Boolean {
            val probe = runProot(
                listOf("/usr/bin/python3", "-c",
                    "import numpy; import numpy.core._multiarray_umath as _m; print('ok')"),
                timeoutMin = 2)
            lastNumpyProbe = probe.second
            val ok = probe.first == 0 && probe.second.contains("ok")
            if (ok) {
                numpyVerifiedMarker.writeText("ok")
            } else {
                numpyVerifiedMarker.delete()
                // S229: this exact message means /tilawa_numpy holds a raw,
                // unbuilt numpy source tree (see this file's header) — delete
                // it now so the very next install attempt starts clean instead
                // of silently reusing the same broken tree forever.
                if (probe.second.contains("source directory")) {
                    File(alpineDir, "tilawa_numpy").deleteRecursively()
                }
            }
            return ok
        }
        fun scipyWorks(): Boolean {
            val probe = runProot(
                listOf("/usr/bin/python3", "-c",
                    "import scipy.linalg as _l; print('ok')"),
                timeoutMin = 2)
            val ok = probe.first == 0 && probe.second.contains("ok")
            if (ok) scipyVerifiedMarker.writeText("ok") else scipyVerifiedMarker.delete()
            return ok
        }
        if (!numpyWorks() || !scipyWorks()) {
            progress(79, "Installing numpy + scipy (apk, one-time)…")
            // S229: pin the exact mirror/version instead of trusting
            // whatever /etc/apk/repositories the minirootfs shipped with —
            // a stale or unreachable default entry was silently pushing
            // every device down the much less reliable pip-sdist path.
            try {
                File(alpineDir, "etc/apk/repositories").writeText(
                    "https://dl-cdn.alpinelinux.org/alpine/v3.21/main\n" +
                    "https://dl-cdn.alpinelinux.org/alpine/v3.21/community\n")
            } catch (_: Exception) {}
            val apkResult = runProot(listOf("/bin/sh", "-c",
                "apk update --no-progress 2>&1 | tail -3 && " +
                "apk add --no-progress --no-cache py3-numpy py3-scipy 2>&1 | tail -8"),
                timeoutMin = 10)
            if (!numpyWorks() || !scipyWorks()) {
                progress(79, "apk unavailable — installing via pip (one-time ~2 min)…")
                numpyTarget.mkdirs()
                val pip1 = runProot(listOf("/bin/sh", "-c",
                    // S229: --only-binary=:all: — this proot has no C/Fortran
                    // toolchain, so an sdist fallback cannot actually build;
                    // without this flag pip could leave a broken, unimportable
                    // numpy *source* tree behind instead of failing cleanly.
                    "pip3 install --quiet --no-cache-dir --only-binary=:all: --target /tilawa_numpy numpy scipy 2>&1 || " +
                    "pip install --quiet --no-cache-dir --break-system-packages --only-binary=:all: --target /tilawa_numpy numpy scipy 2>&1"),  // S213/S229
                    timeoutMin = 20)
                if (!numpyWorks() || !scipyWorks()) {
                    // BUG-C fix: wipe broken/partial install and retry once
                    progress(79, "Retrying numpy + scipy install (cleaning previous attempt)…")
                    numpyTarget.deleteRecursively()
                    numpyTarget.mkdirs()
                    val pip2 = runProot(listOf("/bin/sh", "-c",
                        "pip3 install --quiet --no-cache-dir --only-binary=:all: --target /tilawa_numpy numpy scipy 2>&1 || " +
                        "pip install --quiet --no-cache-dir --break-system-packages --only-binary=:all: --target /tilawa_numpy numpy scipy 2>&1"),  // S213/S229
                        timeoutMin = 20)
                    numpyWorks(); scipyWorks()  // S226: refresh both markers after final attempt
                    if (!numpyVerifiedMarker.exists()) {
                        // S226 (was S223): only numpy failing to import is fatal now —
                        // every local engine (S225) runs fine on numpy alone. A scipy
                        // shortfall just disables naqaa's full 8-phase DSP path, which
                        // already falls back to numpy-only analysis on its own.
                        throw IOException(
                            "numpy install failed.\n" +
                            "apk: " + apkResult.second.takeLast(400) + "\n" +
                            "pip: " + pip1.second.takeLast(200) + " / " + pip2.second.takeLast(400) + "\n" +
                            "import probe: " + lastNumpyProbe.takeLast(300))
                    }
                }
            }
        }
        // S104: discover actual Python site-packages path at runtime
        val pyPathResult = runProot(listOf("/usr/bin/python3", "-c",
            "import sys; print('PYPATH:' + ':'.join(sys.path))"), timeoutMin=2)
        val pyPath = pyPathResult.second.lines()
            .firstOrNull { it.startsWith("PYPATH:") }
            ?.removePrefix("PYPATH:") ?: ""
        if (pyPath.isNotEmpty()) {
            File(dataDir, "python_path.txt").writeText(pyPath)
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
                    // S240: the old ...-0_5_6-aarch64-unknown-linux-musl URL has always
                    // 404'd — v0.5.6 ships no musl aarch64 asset. The real asset is
                    // dot-versioned -gnu (same binary the APK bundles).
                    val url = "https://github.com/Rikorose/DeepFilterNet/releases/download/v0.5.6/deep-filter-0.5.6-aarch64-unknown-linux-gnu"
                    download(url, dfBin, "DeepFilter", 80, 88)
                    dfBin.setExecutable(true)
                } catch (_: Exception) {
                    throw IOException("DeepFilter install failed — check internet and retry setup")
                }
            }
        }
        // S-DF3ARCH: verify/repair — if bundled asset was x86_64, replace with aarch64
        val dfHdrBuf = ByteArray(20)
        val dfIsAarch64 = try {
            FileInputStream(dfBin).use { it.read(dfHdrBuf) }
            dfHdrBuf[18] == 0xB7.toByte() && dfHdrBuf[19] == 0x00.toByte()
        } catch (_: Exception) { false }
        if (!dfIsAarch64) {
            dfBin.delete()
            progress(80, "DF3: wrong arch detected — downloading aarch64…")
            try {
                // S240: same URL fix as above — musl asset never existed, gnu is real
                val dfUrl = "https://github.com/Rikorose/DeepFilterNet/releases/download/v0.5.6/deep-filter-0.5.6-aarch64-unknown-linux-gnu"
                download(dfUrl, dfBin, "DeepFilter aarch64", 80, 88)
                dfBin.setExecutable(true)
            } catch (e: Exception) {
                throw IOException("DF3 aarch64 download failed: ${e.message}")
            }
        }
        progress(88, "DeepFilter ready (aarch64 ✓)")

        // 5. Engine scripts from APK assets
        progress(89, "Extracting engine scripts…")
        extractEngines()
        progress(92, "Engine scripts ready")

        // 6. Reference audio — extract from APK assets
        refAudioDir.mkdirs()
        listOf("ref_araf_1425h.mp3", "ref_fath_1425h.mp3", "ref_fatir_1425h.mp3").forEach { rf ->
            val dest = File(refAudioDir, rf)
            if (!dest.exists() || dest.length() < 10_000) {
                try {
                    context.assets.open("flutter_assets/assets/reference_audio/$rf")
                        .use { it.copyTo(java.io.FileOutputStream(dest)) }
                } catch (_: Exception) {
                    try {
                        context.assets.open("assets/reference_audio/$rf")
                            .use { it.copyTo(java.io.FileOutputStream(dest)) }
                    } catch (_: Exception) {}
                }
            }
        }
        File(alpineDir, ".pyenv_build_id").writeText(PYENV_BUILD_ID)  // S229
        File(dataDir, ".tilawa_setup_done").writeText("ok")
        context.getSharedPreferences("tilawa_local", 0)
            .edit().putBoolean("setup_complete", true).apply()  // S106
        progress(100, "Local engine ready!")
    }

    private suspend fun runEngine(engineId: String, inputPath: String,
        aggressive: Boolean = false) =  // S173
        withContext(Dispatchers.IO) {
        try {
            // S237: keep cacheDir from growing forever — every run used to leave
            // its tilawa_input_* copy and output behind permanently. Anything
            // older than 24h is safely stale (results are re-downloaded/saved
            // by the Dart side right after each run finishes).
            try { clearEngineCache(24L * 60 * 60 * 1000) } catch (_: Exception) {}
            val script = ENGINE_SCRIPTS[engineId] ?: "engine_safaa_v4.py"

            // S259: fail with something the user can act on. Falling through
            // to a missing script meant proot printed "can't open file" and
            // the app showed that raw, with no hint that this engine simply
            // is not available offline.
            if (!File(enginesDir, script).exists()) {
                throw Exception(
                    "Engine $engineId is not available offline (missing $script). " +
                    "Use one of: " + availableLocalEngines().joinToString(", "))
            }

            // v11.0 (tajalli) outputs WAV; v11.1/v11.2 output MP3
            val outExt = if (engineId == "v11.0") "wav" else "mp3"
            val outputPath = "${cacheDir.absolutePath}/tilawa_${engineId.replace('.','_')}_${System.currentTimeMillis()}.$outExt"
            refAudioDir.mkdirs()
            // S106: re-extract ref audio if missing (in case setup ran before S105)
            listOf("ref_araf_1425h.mp3", "ref_fath_1425h.mp3", "ref_fatir_1425h.mp3").forEach { rf ->
                val dest = File(refAudioDir, rf)
                if (!dest.exists() || dest.length() < 10_000) {
                    try { context.assets.open("flutter_assets/assets/reference_audio/$rf")
                        .use { it.copyTo(java.io.FileOutputStream(dest)) }
                    } catch (_: Exception) {
                        try { context.assets.open("assets/reference_audio/$rf")
                            .use { it.copyTo(java.io.FileOutputStream(dest)) }
                        } catch (_: Exception) {} }
                }
            }
            // S128: copy input to cacheDir — file_picker paths use /data/user/0/ symlinks
            // that proot cannot resolve. cacheDir is always directly accessible.
            val safeInput = File(cacheDir, "tilawa_input_${System.currentTimeMillis()}.${inputPath.substringAfterLast('.')}")
            try {
                File(inputPath).copyTo(safeInput, overwrite = true)
            } catch (_: Exception) {
                safeInput.delete()
                safeInput.outputStream().use { out ->
                    android.net.Uri.parse(inputPath).let { uri ->
                        context.contentResolver.openInputStream(uri)?.use { it.copyTo(out) }
                    }
                }
            }
            val actualInput = if (safeInput.exists() && safeInput.length() > 0) safeInput.absolutePath else inputPath
            val refMp3 = File(refAudioDir, "ref_araf_1425h.mp3")
            val inParent  = cacheDir.absolutePath
            File(inParent).mkdirs()

            val cmd = mutableListOf(
                prootBin.absolutePath,
                "--link2symlink", "-0",
                "-r", alpineDir.absolutePath,
                "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys",
                "-b", "${enginesDir.absolutePath}:/engines",
                // S89: only bind if dir exists
                *( if (refAudioDir.exists()) arrayOf("-b", "${refAudioDir.absolutePath}:/reference_audio") else emptyArray() ),
                "-b", "$inParent:$inParent",
                "-b", "${cacheDir.absolutePath}:${cacheDir.absolutePath}",
                "-w", "/", "--kill-on-exit",
                "/usr/bin/python3", "/engines/$script",
                // S213 (was S204-BUG-1, never applied to the live file): Safaa's
                // argparse takes positional `input output`, not -i/-o/--iterations/--ref.
                *( if (script.startsWith("engine_safaa"))
                    arrayOf(actualInput, outputPath)
                else
                    arrayOf("-i", actualInput, "-o", outputPath, "--iterations", "3")),
            )
            // S118/S213/S259: only engines that declare --ref get one. See
            // REF_SCRIPTS above — a script name is not evidence of its CLI.
            if (script in REF_SCRIPTS) {
                listOf("ref_araf_1425h.mp3", "ref_fath_1425h.mp3", "ref_fatir_1425h.mp3").forEach { rf ->
                    val refFile = File(refAudioDir, rf)
                    if (refFile.exists()) cmd += listOf("--ref", "/reference_audio/$rf")
                }
            }

            // S173: --aggressive flag for الصفاء v4 only
            if (script.startsWith("engine_safaa_v4") && aggressive) {
                cmd += listOf("--aggressive")
            }

            val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {
                environment()["HOME"] = "/root"
                environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
                environment()["PYTHONPATH"] = pythonPathForProot() // S212: dynamic (was hardcoded 3.11/3.12)
                environment()["TERM"] = "xterm"
                // S201-BUG2: /usr/lib first so numpy/.so deps (libopenblas etc.)
                // resolve inside Alpine proot; append dataDir for proot-loader.
                environment()["LD_LIBRARY_PATH"] = "/usr/lib:${dataDir.absolutePath}"
                val prootTmp = File(dataDir, "proot-tmp").also { it.mkdirs() }  // S106
                environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath
            if (prootLoader.exists()) environment()["PROOT_LOADER"] = prootLoader.absolutePath
            }.start()
            engineProc = proc

            ui { channel?.invokeMethod("engineProgress", mapOf("pct" to 5, "msg" to "Engine started…")) }

            val reader = BufferedReader(InputStreamReader(proc.inputStream))
            var lastLine = ""; var lastJson: String? = null; var line: String?
            val allOutput = StringBuilder()
            while (reader.readLine().also { line = it } != null) {
                val l = line!!.trim(); if (l.isEmpty()) continue
                lastLine = l
                allOutput.appendLine(l)
                if (l.startsWith("{") && (l.contains("score") || l.contains("version"))) lastJson = l
                if (lastJson == null && l.contains("/100")) {
                    val sc = Regex("([0-9]+[.][0-9]+)/100").findAll(l).lastOrNull()?.groupValues?.getOrNull(1)
                    if (sc != null) lastJson = "{\"score\": $sc, \"lufs\": 0.0, \"rms\": 0.0, \"crest\": 0.0, \"lra\": 0.0}"
                }
                // S-PROGRESS: map engine phase-tag prefix to progress pct
                // Phases A→L correspond to the DSP pipeline stages in الإتقان/الاسترداد.
                val linePct = when {
                    l.startsWith("[A1]") || l.startsWith("[A2]") || l.startsWith("[A3]") -> 5
                    l.startsWith("[A4]") || l.startsWith("[A5]") || l.startsWith("[A6]") -> 8
                    l.startsWith("[A7]") || l.startsWith("[A8]") || l.startsWith("[A9]") -> 12
                    l.startsWith("[B")  -> 16
                    l.startsWith("[C")  -> 22
                    l.startsWith("[D")  -> 30
                    l.startsWith("[E")  -> 38
                    l.startsWith("[F]") && l.contains("detected") -> 22   // phrase count msg
                    l.startsWith("[F")  -> 46
                    l.startsWith("[G")  -> 58
                    l.startsWith("[H")  -> 68
                    l.startsWith("[I")  -> 76
                    l.startsWith("[J")  -> 84
                    l.startsWith("[K")  -> 90
                    l.startsWith("[L")  -> 94
                    l.contains("score") && l.contains("/100") -> 96
                    else -> -1
                }
                ui { channel?.invokeMethod("engineProgress", mapOf("pct" to linePct, "msg" to l)) }
            }

            val rc = try {
                if (!proc.waitFor(90, TimeUnit.MINUTES)) { proc.destroyForcibly(); -1 }
                else proc.exitValue()
            } catch (_: Exception) { -1 }

            var outFile = File(outputPath)
            // S137: if output missing at expected path, search cacheDir for recent file
            var resolvedOutput = outputPath
            if (rc == 0 && !File(outputPath).let { it.exists() && it.length() > 500 }) {
                val startMs = System.currentTimeMillis() - 300_000L
                val found = cacheDir.listFiles()
                    ?.filter { it.name.startsWith("tilawa_") && it.lastModified() > startMs && it.length() > 500 }
                    ?.maxByOrNull { it.lastModified() }
                if (found != null) resolvedOutput = found.absolutePath
            }
            outFile = File(resolvedOutput)
            if (outFile.exists() && outFile.length() > 500) {
                val extra = if (lastJson != null) mapOf("json" to lastJson) else emptyMap<String,Any>()
                ui { channel?.invokeMethod("engineDone", mapOf("path" to resolvedOutput) + extra) }
            } else {
                val errDetail = allOutput.takeLast(400).trim().ifEmpty { lastLine }
                ui { channel?.invokeMethod("engineError", mapOf("msg" to "Engine failed (rc=$rc): $errDetail")) }
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
            // S195-BUG9: resolv.conf bind must precede args (proot ignores flags after cmd)
            "--kill-on-exit") +
            (if (File(alpineDir, "etc/resolv.conf").exists())
                listOf("-b", "${alpineDir.absolutePath}/etc/resolv.conf:/etc/resolv.conf")
            else emptyList()) +
            args
        val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {
            environment()["HOME"] = "/root"
            environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            environment()["TERM"] = "xterm"
            // S202: completes S201-BUG2 — this is a second, differently-indented
            // copy of the same bug (runEngine()'s ProcessBuilder was already fixed,
            // this one inside runProot() — used by numpyWorks()'s real-import probe
            // and the site-packages path probe — was not). /usr/lib first so the
            // probe can actually dlopen libopenblas/libgfortran inside Alpine proot.
            environment()["LD_LIBRARY_PATH"] = "/usr/lib:${dataDir.absolutePath}"
            val prootTmp = File(dataDir, "proot-tmp").also { it.mkdirs() }  // S106
            environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath
            if (prootLoader.exists()) environment()["PROOT_LOADER"] = prootLoader.absolutePath
        }.start()
        val output = proc.inputStream.bufferedReader().readText().takeLast(800)
        val code = try {
            if (!proc.waitFor(timeoutMin.toLong(), TimeUnit.MINUTES)) { proc.destroyForcibly(); -1 }
            else proc.exitValue()
        } catch (_: Exception) { proc.destroyForcibly(); -1 }
        return Pair(code, output)
    }

    // S202: like runProot() but accepts caller-supplied extra bind mounts — used
    // by the "runProotCmd" channel case for the audio editor's ffmpeg trim/EQ/
    // export, whose input/output files live outside alpineDir/cacheDir.
    private fun runProotWithBinds(args: List<String>, extra: List<String>, tmMin: Int = 10): Pair<Int, String> {
        val cmd = mutableListOf(prootBin.absolutePath,
            "--link2symlink",
            "-0",
            "-r", alpineDir.absolutePath,
            "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys") +
            extra +
            listOf("-w", "/",
            // S195-BUG9: resolv.conf bind must precede args (proot ignores flags after cmd)
            "--kill-on-exit") +
            (if (File(alpineDir, "etc/resolv.conf").exists())
                listOf("-b", "${alpineDir.absolutePath}/etc/resolv.conf:/etc/resolv.conf")
            else emptyList()) +
            args
        val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {
            environment()["HOME"] = "/root"
            environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            environment()["TERM"] = "xterm"
            // S202: same /usr/lib fix as runProot()/runEngine() (S201-BUG2)
            environment()["LD_LIBRARY_PATH"] = "/usr/lib:${dataDir.absolutePath}"
            val prootTmp = File(dataDir, "proot-tmp").also { it.mkdirs() }  // S106
            environment()["PROOT_TMP_DIR"] = prootTmp.absolutePath
            if (prootLoader.exists()) environment()["PROOT_LOADER"] = prootLoader.absolutePath
        }.start()
        val output = proc.inputStream.bufferedReader().readText().takeLast(800)
        val code = try {
            if (!proc.waitFor(tmMin.toLong(), TimeUnit.MINUTES)) { proc.destroyForcibly(); -1 }
            else proc.exitValue()
        } catch (_: Exception) { proc.destroyForcibly(); -1 }
        return Pair(code, output)
    }

    // S237: hardened download — up to 4 attempts with exponential backoff, HTTP
    // Range resume so a dropped connection continues where it left off instead
    // of restarting a ~135 MB file from zero, and live speed in the phase text.
    private fun download(url: String, dest: File, label: String, p0: Int, p1: Int) {
        dest.parentFile?.mkdirs()
        val part = File(dest.parentFile, dest.name + ".part")
        var lastErr: Exception? = null
        for (attempt in 1..4) {
            var conn: HttpURLConnection? = null
            try {
                var already = if (part.exists()) part.length() else 0L
                conn = URL(url).openConnection() as HttpURLConnection
                conn.connectTimeout = 30_000; conn.readTimeout = 120_000
                conn.instanceFollowRedirects = true
                if (already > 0) conn.setRequestProperty("Range", "bytes=$already-")
                conn.connect()
                val code = conn.responseCode
                if (already > 0 && code == 200) {
                    // server ignored Range — restart from scratch
                    part.delete(); already = 0L
                } else if (code !in 200..299) {
                    throw IOException("HTTP $code for $url")
                }
                val total = already + conn.contentLengthLong.coerceAtLeast(0)
                var done = already
                var lastUiMs = 0L
                var speedWindowStart = System.currentTimeMillis()
                var speedWindowBytes = 0L
                var speedStr = ""
                conn.inputStream.use { inp ->
                    FileOutputStream(part, already > 0).use { out ->
                        val buf = ByteArray(65_536); var n: Int
                        while (inp.read(buf).also { n = it } != -1) {
                            out.write(buf, 0, n); done += n; speedWindowBytes += n
                            val now = System.currentTimeMillis()
                            if (now - speedWindowStart >= 1000) {
                                val mbps = speedWindowBytes / 1_048_576.0 / ((now - speedWindowStart) / 1000.0)
                                speedStr = "  ·  %.1f MB/s".format(mbps)
                                speedWindowStart = now; speedWindowBytes = 0
                            }
                            if (total > already && now - lastUiMs >= 250) {  // throttle UI spam
                                lastUiMs = now
                                val pct = p0 + ((done.toDouble() / total) * (p1 - p0)).toInt()
                                val mb = "%.0f/%.0f MB".format(done / 1_048_576.0, total / 1_048_576.0)
                                ui { channel?.invokeMethod("setupProgress",
                                    mapOf("pct" to pct, "phase" to "Downloading $label…  $mb$speedStr")) }
                            }
                        }
                    }
                }
                if (!part.exists() || part.length() == 0L) throw IOException("empty download for $url")
                dest.delete()
                if (!part.renameTo(dest)) { part.copyTo(dest, overwrite = true); part.delete() }
                return
            } catch (e: Exception) {
                lastErr = e
                if (attempt < 4) {
                    val backoffS = 1L shl attempt  // 2s, 4s, 8s
                    ui { channel?.invokeMethod("setupProgress", mapOf("pct" to p0,
                        "phase" to "Connection dropped — retrying $label (attempt ${attempt + 1}/4)…")) }
                    try { Thread.sleep(backoffS * 1000) } catch (_: InterruptedException) {}
                }
            } finally { conn?.disconnect() }
        }
        part.delete()
        throw IOException("Download failed after 4 attempts: $label — ${lastErr?.message}")
    }

    private fun extractTarGz(tarGz: File, destDir: File) {
        destDir.mkdirs()
        // S223: symlink() can fail silently (see the '2' case below) and used
        // to just be dropped, leaving critical .so version-symlinks — e.g.
        // libopenblas.so -> libopenblas.so.0, libgfortran.so -> libgfortran.so.5
        // — missing. numpy/scipy's compiled extensions dlopen those at import
        // time, so site-packages looked complete while numpy was actually
        // unimportable. Failed links are queued here and resolved in a
        // second pass once every real file has been extracted.
        val pendingSymlinks = mutableListOf<Pair<File, String>>()
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
            fun str(start: Int, len: Int) = String(hdr, start, len).trimEnd('\u0000').trim()
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
                    '0', '\u0000', '7' -> {
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
                        var linked = false
                        try { android.system.Os.symlink(linkName, dest.absolutePath); linked = true }
                        catch (_: Exception) { /* queued below instead of silently dropped — S223 */ }
                        if (!linked) pendingSymlinks.add(dest to linkName)
                        skipPadded(size)
                    }
                    '5' -> { dest.mkdirs(); skipPadded(size) }
                    else -> skipPadded(size)
                }
                } catch (_: Exception) { /* skip bad entry, continue */ }
            }
            // S223: second pass — resolve symlinks that failed above now that
            // every regular file in the archive has been written. Retry the
            // real symlink first (order-independent once extraction is done);
            // if the OS still refuses, copy the target's bytes so the path at
            // least resolves to real content instead of silently vanishing.
            for ((dest, linkName) in pendingSymlinks) {
                try {
                    dest.parentFile?.mkdirs(); dest.delete()
                    android.system.Os.symlink(linkName, dest.absolutePath)
                    continue
                } catch (_: Exception) {}
                try {
                    val target = File(dest.parentFile, linkName)
                    if (target.exists() && target.isFile) {
                        target.copyTo(dest, overwrite = true)
                        if (target.canExecute()) dest.setExecutable(true, false)
                    }
                } catch (_: Exception) {}
            }
        }
    }

    // S259: engine ids that can actually run offline — i.e. whose script is
    // present on disk after extraction. The Dart side uses this to stop
    // offering an engine that cannot possibly work.
    fun availableLocalEngines(): List<String> =
        ENGINE_SCRIPTS.filter { (_, script) ->
            File(enginesDir, script).let { it.exists() && it.length() > 1024 }
        }.keys.toList()

    private fun extractEngines() {
        enginesDir.mkdirs()
        // S259: derived from the one table above rather than a second literal
        // list. The two had drifted — this list used to name engine_v90.py and
        // engine_v80.py, which are in no APK because they exist nowhere in the
        // project, while runEngine() happily routed v9.0/v8.0 to them.
        val failed = mutableListOf<String>()
        (ENGINE_SCRIPTS.values.distinct() + SUPPORT_SCRIPTS).forEach { name ->
            val dest = File(enginesDir, name)
            if (dest.exists() && dest.length() > 1024) return@forEach  // S88
            try { context.assets.open("flutter_assets/assets/engines/$name").use { inp ->
                FileOutputStream(dest).use { inp.copyTo(it) } }
            } catch (_: Exception) {
                try { context.assets.open("engines/$name").use { inp ->
                    FileOutputStream(dest).use { inp.copyTo(it) } }
                } catch (e: Exception) {
                    // S259: this pair of empty catches is how the drift above
                    // stayed invisible — a script that was not in the APK
                    // failed silently and setup still reported success.
                    failed += name
                    android.util.Log.w("LocalEngineRunner",
                        "extractEngines: could not extract $name from assets " +
                        "(${e.message})")
                }
            }
        }
        if (failed.isNotEmpty()) {
            android.util.Log.w("LocalEngineRunner",
                "engines unavailable offline: ${failed.joinToString(", ")}")
        }
    }

    // downloadRefAudio() removed — ref audio now bundled in APK assets

    private fun ui(block: () -> Unit) = activity.runOnUiThread(block)
}
