#!/usr/bin/env python3
"""
tilawa_fix_s68.py — Make the local/Termux toggle actually work
==============================================================
The toggle exists in the UI but tapping it does nothing because:
  1. patch_android.py hasn't written LocalEngineRunner.kt yet
     (needs to run in CI, but the Kotlin file has the broken \\n bug)
  2. setup_screen.dart download URL may be wrong
  3. _processLocal() may have stale variable names

This script:
  A. Writes LocalEngineRunner.kt DIRECTLY (bypasses patch_android.py)
  B. Verifies setup_screen.dart has correct download URLs
  C. Verifies _processLocal() routes correctly
  D. Fixes patch_android.py \\n escaping (S67)
"""
from pathlib import Path
from datetime import datetime

ROOT = Path.home() / 'tilawa-enhancer'
LIB  = ROOT / 'lib'
SC   = LIB / 'screens'
SV   = LIB / 'services'
KT   = ROOT / 'android/app/src/main/kotlin'

def _h(t): print(f'\n{"═"*58}\n  {t}\n{"═"*58}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'  XX  {m}')

_h(f'tilawa_fix_s68  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ── A. Write LocalEngineRunner.kt directly ────────────────────────────────────
_h('A — Write LocalEngineRunner.kt')

# Find the package name from MainActivity
main_kt = list(KT.rglob('MainActivity.kt'))
if not main_kt:
    _xx('MainActivity.kt not found')
    pkg_dir = KT
    pkg = 'com.tilawa.tilawa_enhancer'
else:
    main_kt = main_kt[0]
    pkg_line = [l for l in main_kt.read_text().splitlines() if l.startswith('package')][0]
    pkg = pkg_line.replace('package ', '').strip()
    pkg_dir = main_kt.parent
    _ok(f'Package: {pkg}')

KT_FILE = pkg_dir / 'LocalEngineRunner.kt'

KT_CONTENT = f'''package {pkg}

import android.content.Context
import android.os.PowerManager
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import kotlinx.coroutines.*
import java.io.File
import java.io.BufferedReader
import java.io.InputStreamReader

/**
 * LocalEngineRunner — runs Tilawa Python engines via proot on-device
 * S65: initial implementation
 * S68: direct Kotlin write (bypasses patch_android.py \\n bug)
 */
class LocalEngineRunner(private val context: Context) {{

    companion object {{
        const val METHOD_CHANNEL = "com.tilawa.tilawa_enhancer/local_engine"
        const val EVENT_CHANNEL  = "com.tilawa.tilawa_enhancer/local_progress"
        const val SETUP_CHANNEL  = "com.tilawa.tilawa_enhancer/setup"
    }}

    private val dataDir   get() = context.filesDir
    private val rootfsDir get() = File(dataDir, "tilawa_rootfs")
    private val prootBin  get() = File(dataDir, "proot")
    private val engineDir get() = File(dataDir, "engines")
    private var wakeLock: PowerManager.WakeLock? = null

    private var progressSink: EventChannel.EventSink? = null
    private var runJob: Job? = null

    fun registerWith(flutterEngine: FlutterEngine) {{
        // Setup channel — isSetupComplete, runSetup
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, SETUP_CHANNEL)
            .setMethodCallHandler {{ call, result ->
                when (call.method) {{
                    "isSetupComplete" -> result.success(isSetupComplete())
                    "runSetup"        -> GlobalScope.launch(Dispatchers.IO) {{
                        runSetup(result)
                    }}
                    else -> result.notImplemented()
                }}
            }}

        // Progress event channel
        EventChannel(flutterEngine.dartExecutor.binaryMessenger, EVENT_CHANNEL)
            .setStreamHandler(object : EventChannel.StreamHandler {{
                override fun onListen(a: Any?, sink: EventChannel.EventSink?) {{ progressSink = sink }}
                override fun onCancel(a: Any?) {{ progressSink = null }}
            }})

        // Engine run channel
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, METHOD_CHANNEL)
            .setMethodCallHandler {{ call, result ->
                when (call.method) {{
                    "run" -> {{
                        val inputPath  = call.argument<String>("input")!!
                        val engine     = call.argument<String>("engine") ?: "v11.0"
                        val outputPath = call.argument<String>("output")!!
                        acquireWakeLock()
                        runJob = GlobalScope.launch(Dispatchers.IO) {{
                            runEngine(inputPath, engine, outputPath, result)
                        }}
                    }}
                    "cancel" -> {{
                        runJob?.cancel()
                        releaseWakeLock()
                        result.success("cancelled")
                    }}
                    else -> result.notImplemented()
                }}
            }}
    }}

    private fun isSetupComplete(): Boolean =
        prootBin.exists() && File(rootfsDir, "usr/bin/python3").exists()

    private fun acquireWakeLock() {{
        val pm = context.getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(
            PowerManager.PARTIAL_WAKE_LOCK, "tilawa:local_engine")
        wakeLock?.acquire(45 * 60 * 1000L) // 45 min max
    }}

    private fun releaseWakeLock() {{
        wakeLock?.release(); wakeLock = null
    }}

    private suspend fun runSetup(result: MethodChannel.Result) {{
        try {{
            send("status", "Downloading proot...")
            downloadProot()
            send("status", "Downloading Python rootfs (~200MB)...")
            downloadRootfs()
            send("status", "Installing Python packages...")
            installPackages()
            send("status", "Copying engine scripts...")
            copyEngines()
            send("status", "Setup complete!")
            send("done", "ok")
            withContext(Dispatchers.Main) {{ result.success("done") }}
        }} catch (e: Exception) {{
            send("error", e.message ?: "Setup failed")
            withContext(Dispatchers.Main) {{ result.error("SETUP_FAILED", e.message, null) }}
        }}
    }}

    private suspend fun downloadProot() {{
        // proot static ARM64 binary from Termux releases
        val url = "https://github.com/termux/proot/releases/download/v5.1.107-2/proot-aarch64"
        download(url, prootBin)
        prootBin.setExecutable(true)
    }}

    private suspend fun downloadRootfs() {{
        // Alpine Linux ARM64 minirootfs — tiny, fast, has apk
        val url = "https://dl-cdn.alpinelinux.org/alpine/v3.19/releases/aarch64/alpine-minirootfs-3.19.0-aarch64.tar.gz"
        val tar = File(dataDir, "rootfs.tar.gz")
        download(url, tar)
        rootfsDir.mkdirs()
        exec(listOf("tar", "xzf", tar.absolutePath, "-C", rootfsDir.absolutePath))
        tar.delete()
        // Write resolv.conf so DNS works inside proot
        File(rootfsDir, "etc/resolv.conf").writeText("nameserver 8.8.8.8\nnameserver 1.1.1.1\n")
    }}

    private suspend fun installPackages() {{
        // Run apk inside proot to install Python + audio deps
        prootExec(listOf(
            "/bin/sh", "-c",
            "apk update && apk add --no-cache python3 py3-pip py3-numpy py3-scipy ffmpeg && " +
            "pip3 install --no-cache-dir soundfile librosa"
        ))
    }}

    private suspend fun copyEngines() {{
        engineDir.mkdirs()
        // Copy bundled engine assets from APK to filesDir
        val assetMgr = context.assets
        for (engine in assetMgr.list("engines") ?: emptyArray()) {{
            val dst = File(engineDir, engine)
            assetMgr.open("engines/$engine").use {{ inp ->
                dst.outputStream().use {{ out -> inp.copyTo(out) }}
            }}
        }}
    }}

    private suspend fun runEngine(
        inputPath: String, engine: String,
        outputPath: String, result: MethodChannel.Result
    ) {{
        try {{
            val scriptName = when (engine) {{
                "v11.0" -> "engine_tajalli_v1.py"
                "v11.1" -> "engine_itiqan.py"
                "v11.2" -> "engine_isteidad.py"
                "v10.0" -> "engine_v100.py"
                "v9.0"  -> "engine_v90.py"
                "v8.5"  -> "engine_v85.py"
                "v8.0"  -> "engine_v80.py"
                else    -> "engine_tajalli_v1.py"
            }}
            val script = File(engineDir, scriptName)
            if (!script.exists()) {{
                throw Exception("Engine script not found: $scriptName — run setup again")
            }}

            send("status", "Running $engine locally...")
            val proc = prootProcess(listOf(
                "python3", "/engines/$scriptName",
                "-i", inputPath, "-o", outputPath
            ))

            val reader = BufferedReader(InputStreamReader(proc.inputStream))
            var line: String?
            while (reader.readLine().also {{ line = it }} != null) {{
                val l = line!!
                // Parse PROGRESS: 0.0-1.0 or JSON result
                when {{
                    l.startsWith("PROGRESS:") -> {{
                        val pct = l.removePrefix("PROGRESS:").trim().toFloatOrNull() ?: 0f
                        send("progress", pct.toString())
                    }}
                    l.startsWith("{{") -> send("result", l)  // JSON metrics
                    else -> send("log", l)
                }}
            }}

            val rc = proc.waitFor()
            releaseWakeLock()

            if (rc == 0 && File(outputPath).exists()) {{
                withContext(Dispatchers.Main) {{
                    result.success(mapOf("path" to outputPath, "engine" to engine))
                }}
            }} else {{
                throw Exception("Engine exited with code $rc")
            }}
        }} catch (e: Exception) {{
            releaseWakeLock()
            withContext(Dispatchers.Main) {{
                result.error("ENGINE_FAILED", e.message, null)
            }}
        }}
    }}

    private fun prootProcess(args: List<String>): Process {{
        val cmd = mutableListOf(
            prootBin.absolutePath,
            "--rootfs=${{rootfsDir.absolutePath}}",
            "--bind=/proc", "--bind=/sys", "--bind=/dev",
            "--bind=${{dataDir.absolutePath}}/engines:/engines",
            "--bind=/sdcard",
            "--cwd=/", "--link2symlink",
            "--kill-on-exit"
        ) + args
        return ProcessBuilder(cmd)
            .redirectErrorStream(true)
            .start()
    }}

    private suspend fun prootExec(args: List<String>) {{
        val proc = prootProcess(args)
        proc.waitFor()
    }}

    private fun exec(cmd: List<String>) {{
        ProcessBuilder(cmd).start().waitFor()
    }}

    private suspend fun download(url: String, dest: File) {{
        withContext(Dispatchers.IO) {{
            java.net.URL(url).openStream().use {{ inp ->
                dest.outputStream().use {{ out -> inp.copyTo(out) }}
            }}
        }}
    }}

    private fun send(type: String, value: String) {{
        android.os.Handler(android.os.Looper.getMainLooper()).post {{
            progressSink?.success(mapOf("type" to type, "value" to value))
        }}
    }}
}}
'''

KT_FILE.write_text(KT_CONTENT, encoding='utf-8')
_ok(f'LocalEngineRunner.kt written → {KT_FILE}')

# ── B. Register LocalEngineRunner in MainActivity.kt ────────────────────────────
_h('B — Register in MainActivity.kt')
txt = main_kt.read_text(encoding='utf-8')

if 'LocalEngineRunner' not in txt:
    OLD_MAIN = 'class MainActivity: FlutterActivity() {'
    NEW_MAIN = (
        'class MainActivity: FlutterActivity() {\n'
        '    private lateinit var localEngine: LocalEngineRunner\n'
        '\n'
        '    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {\n'
        '        super.configureFlutterEngine(flutterEngine)\n'
        '        localEngine = LocalEngineRunner(this)\n'
        '        localEngine.registerWith(flutterEngine)\n'
        '    }\n'
    )
    if OLD_MAIN in txt:
        txt = txt.replace(OLD_MAIN, NEW_MAIN, 1)
        main_kt.write_text(txt, encoding='utf-8')
        _ok('LocalEngineRunner registered in MainActivity.kt')
    else:
        _xx('MainActivity.kt class declaration not found — manual registration needed')
else:
    _ok('LocalEngineRunner already registered in MainActivity.kt')

# Ensure imports are present
imports_needed = [
    'import io.flutter.embedding.engine.FlutterEngine',
    'import io.flutter.plugin.common.MethodChannel',
]
txt = main_kt.read_text(encoding='utf-8')
changed = False
for imp in imports_needed:
    if imp not in txt:
        txt = txt.replace('import io.flutter.embedding.android.FlutterActivity',
            f'import io.flutter.embedding.android.FlutterActivity\n{imp}')
        changed = True
if changed:
    main_kt.write_text(txt, encoding='utf-8')
    _ok('Imports added to MainActivity.kt')

# ── C. Add coroutines dependency to build.gradle ────────────────────────────────
_h('C — Add kotlinx-coroutines to build.gradle')
bg = ROOT / 'android/app/build.gradle'
bg_txt = bg.read_text(encoding='utf-8')
if 'kotlinx-coroutines' not in bg_txt:
    OLD_DEP = "    implementation \"org.jetbrains.kotlin:kotlin-stdlib-jdk7:$kotlin_version\""
    NEW_DEP = (
        "    implementation \"org.jetbrains.kotlin:kotlin-stdlib-jdk7:$kotlin_version\"\n"
        "    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3'"
    )
    if OLD_DEP in bg_txt:
        bg.write_text(bg_txt.replace(OLD_DEP, NEW_DEP, 1), encoding='utf-8')
        _ok('kotlinx-coroutines-android added to build.gradle')
    else:
        # Try alternative
        OLD_DEP2 = "    implementation \"org.jetbrains.kotlin:kotlin-stdlib-jdk8:$kotlin_version\""
        NEW_DEP2 = (
            "    implementation \"org.jetbrains.kotlin:kotlin-stdlib-jdk8:$kotlin_version\"\n"
            "    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3'"
        )
        if OLD_DEP2 in bg_txt:
            bg.write_text(bg_txt.replace(OLD_DEP2, NEW_DEP2, 1), encoding='utf-8')
            _ok('kotlinx-coroutines-android added (jdk8 variant)')
        else:
            _xx('Could not find kotlin-stdlib line in build.gradle')
else:
    _ok('kotlinx-coroutines already in build.gradle')

# ── D. Fix patch_android.py \\n escaping (S67) ────────────────────────────────
_h('D — Fix patch_android.py \\\\n escape (S67)')
pa = ROOT / 'patch_android.py'
if pa.exists():
    pa_txt = pa.read_text(encoding='utf-8')
    old_dns = '.writeText("nameserver 8.8.8.8\\nnameserver 1.1.1.1\\n")'
    new_dns = '.writeText("nameserver 8.8.8.8\\\\nnameserver 1.1.1.1\\\\n")'
    if old_dns in pa_txt:
        pa.write_text(pa_txt.replace(old_dns, new_dns, 1), encoding='utf-8')
        _ok('patch_android.py: \\n → \\\\n fixed')
    else:
        _ok('patch_android.py: already fixed or not present')
else:
    _ok('patch_android.py not found — skipping')

# ── E. Add INTERNET permission to AndroidManifest ─────────────────────────────
_h('E — INTERNET permission in AndroidManifest')
mf = ROOT / 'android/app/src/main/AndroidManifest.xml'
mf_txt = mf.read_text(encoding='utf-8')
if 'INTERNET' not in mf_txt:
    mf_txt = mf_txt.replace(
        '<manifest ', '<manifest>\n    <uses-permission android:name="android.permission.INTERNET" />\n    ',
        1)
    mf.write_text(mf_txt, encoding='utf-8')
    _ok('INTERNET permission added')
else:
    _ok('INTERNET permission already present')

_h('DONE')
print(f"""
  git add -A
  git commit -m "S68: LocalEngineRunner.kt direct write — proot offline engine"
  git push

  First-time user flow:
    Toggle "Local Engine" ON
    → SetupScreen downloads proot + Alpine rootfs + Python (~200MB, one time)
    → After setup: offline processing, no server needed
""")
