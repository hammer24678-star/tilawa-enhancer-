
"""patch_android.py v12 — S19
Changes:
  S19-ICON : Resizes assets/images/logo.png to all 5 mipmap densities using PIL.
             Requires: pip install Pillow (add to build.yml before this step).
             Graceful skip if logo.png missing or PIL unavailable.
  S19-QUERY: <queries> block in manifest for Android 11+ audio player intent
             (needed by url_launcher "Open in Player" feature).
  VERSION  : versionCode=9, versionName="2.7.0" matches pubspec 2.7.0+9
"""
from pathlib import Path

ROOT = Path("android")
APP  = ROOT / "app"

# ── STEP 1: build.gradle ──────────────────────────────────────────────────────
(APP / "build.gradle").write_text(r"""
plugins {
    id "com.android.application"
    id "kotlin-android"
    id "dev.flutter.flutter-gradle-plugin"
}
android {
    namespace "com.tilawa.tilawa_enhancer"
    compileSdk 36
    ndkVersion "28.2.13676358"  // S159: highest NDK required by plugins  // S154-B12
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_17
        targetCompatibility JavaVersion.VERSION_17
        coreLibraryDesugaringEnabled true
    }
    kotlinOptions { jvmTarget = "17" }
    defaultConfig {
        applicationId "com.tilawa.tilawa_enhancer"
        minSdk 21
        targetSdk 36
        versionCode 9
        versionName "2.7.0"
    }
    buildTypes {
        release {
            signingConfig signingConfigs.debug
            minifyEnabled false
            shrinkResources false
        }
    }
    packagingOptions {
        exclude 'DebugProbesKt.bin'
        exclude 'META-INF/AL2.0'
        exclude 'META-INF/LGPL2.1'
    }
}
// Remove kotlinx-coroutines-debug — declares android.permission.DUMP
// which Samsung Knox security agent can kill the process on launch.
configurations.all {
    exclude group: 'org.jetbrains.kotlinx', module: 'kotlinx-coroutines-debug'
}
flutter { source "../.." }
dependencies {
    implementation "org.jetbrains.kotlin:kotlin-stdlib-jdk8:2.1.0"
    coreLibraryDesugaring "com.android.tools:desugar_jdk_libs:2.1.4"
}
""")
print("  build.gradle OK (v11: versionCode=9, versionName=2.7.0)")

# ── STEP 2: settings.gradle ───────────────────────────────────────────────────
(ROOT / "settings.gradle").write_text("""
pluginManagement {
    def flutterSdkPath = {
        def properties = new Properties()
        file("local.properties").withInputStream { properties.load(it) }
        def flutterSdkPath = properties.getProperty("flutter.sdk")
        assert flutterSdkPath != null
        return flutterSdkPath
    }()
    includeBuild("${flutterSdkPath}/packages/flutter_tools/gradle")
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
plugins {
    id "dev.flutter.flutter-plugin-loader" version "1.0.0"
    id "com.android.application" version "8.10.0" apply false
    id "org.jetbrains.kotlin.android" version "2.1.0" apply false
}
include ":app"
""")
print("  settings.gradle OK")

# ── STEP 3: Gradle wrapper → 8.3 ─────────────────────────────────────────────
wrapper = ROOT / "gradle" / "wrapper" / "gradle-wrapper.properties"
wrapper.parent.mkdir(parents=True, exist_ok=True)
wrapper.write_text(
    "distributionBase=GRADLE_USER_HOME\n"
    "distributionPath=wrapper/dists\n"
    "zipStoreBase=GRADLE_USER_HOME\n"
    "zipStorePath=wrapper/dists\n"
    "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.11.1-all.zip\n"
)
print("  gradle-wrapper.properties OK (Gradle 8.11.1)")  # S142: was 8.3

# ── STEP 4: network_security_config.xml ──────────────────────────────────────
res_xml = APP / "src" / "main" / "res" / "xml"
res_xml.mkdir(parents=True, exist_ok=True)
(res_xml / "network_security_config.xml").write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<network-security-config>\n'
    '    <domain-config cleartextTrafficPermitted="true">\n'
    '        <domain includeSubdomains="false">127.0.0.1</domain>\n'
    '        <domain includeSubdomains="false">localhost</domain>\n'
    '    </domain-config>\n'
    '</network-security-config>\n'
)
print("  network_security_config.xml OK")

# ── STEP 5: AndroidManifest.xml ───────────────────────────────────────────────
# S19: Added <queries> block — Android 11+ (API 30) requires this for
# PackageManager to resolve audio player apps. Without it, launchUrl()
# for content:// audio URIs fails silently. No permission needed; this
# only declares intent filters we want to query.
manifest = APP / "src" / "main" / "AndroidManifest.xml"
manifest.parent.mkdir(parents=True, exist_ok=True)
manifest.write_text(
'<?xml version="1.0" encoding="utf-8"?>\n'
'<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
'\n'
'    <uses-permission android:name="android.permission.INTERNET"/>\n'
'    <uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>\n'
'    <uses-permission android:name="android.permission.WAKE_LOCK"/>\n'
'    <uses-permission android:name="android.permission.READ_MEDIA_AUDIO"/>\n'
'    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"\n'
'        android:maxSdkVersion="32"/>\n'
'    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"\n'
'        android:maxSdkVersion="28"/>\n'
'\n'
'    <!-- S19: package visibility for url_launcher audio ACTION_VIEW (API 30+) -->\n'
'    <queries>\n'
'        <intent>\n'
'            <action android:name="android.intent.action.VIEW" />\n'
'            <data android:mimeType="audio/mpeg" />\n'
'        </intent>\n'
'        <intent>\n'
'            <action android:name="android.intent.action.VIEW" />\n'
'            <data android:mimeType="audio/*" />\n'
'        </intent>\n'
'    </queries>\n'
'\n'
'    <application\n'
'        android:label="\u0645\u062d\u0633\u0650\u0651\u0646 \u0627\u0644\u062a\u0644\u0627\u0648\u0629"\n'
'        android:requestLegacyExternalStorage="true"\n'
'        android:name="${applicationName}"\n'
'        android:icon="@mipmap/ic_launcher"\n'
'        android:hardwareAccelerated="true"\n'
'        android:networkSecurityConfig="@xml/network_security_config"\n'
'        android:usesCleartextTraffic="true"\n'
'        android:extractNativeLibs="true">\n'
'\n'
'        <activity\n'
'            android:name=".MainActivity"\n'
'            android:exported="true"\n'
'            android:launchMode="singleTop"\n'
'            android:taskAffinity=""\n'
'            android:theme="@style/LaunchTheme"\n'
'            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|smallestScreenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode"\n'
'            android:hardwareAccelerated="true"\n'
'            android:windowSoftInputMode="adjustResize">\n'
'            <meta-data\n'
'                android:name="io.flutter.embedding.android.NormalTheme"\n'
'                android:resource="@style/NormalTheme"/>\n'
'            <intent-filter>\n'
'                <action android:name="android.intent.action.MAIN"/>\n'
'                <category android:name="android.intent.category.LAUNCHER"/>\n'
'            </intent-filter>\n'
'        </activity>\n'
'\n'
'        <meta-data android:name="flutterEmbedding" android:value="2"/>\n'
'    </application>\n'
'</manifest>\n'
)
print("  AndroidManifest.xml written (v11 — queries block for audio player)")

# ── STEP 6: Verify manifest ───────────────────────────────────────────────────
txt = manifest.read_text()
for check, label in [
    ("android.permission.INTERNET",   "INTERNET permission"),
    ("WRITE_EXTERNAL_STORAGE",        "WRITE_EXTERNAL_STORAGE (<=API28)"),
    ("READ_MEDIA_AUDIO",              "READ_MEDIA_AUDIO (API33+)"),
    ("networkSecurityConfig",         "networkSecurityConfig on <application>"),
    ('usesCleartextTraffic="true"',   "usesCleartextTraffic=true"),
    ('extractNativeLibs="true"',      "extractNativeLibs=true (minSdk=21)"),
    ("<queries>",                     "queries block (audio player, API30+)"),
    ("flutterEmbedding",              "flutterEmbedding meta-data"),
    ("applicationName",               "${applicationName}"),
    ("NormalTheme",                   "NormalTheme meta-data"),
]:
    ok = check in txt
    print(f"  {'OK' if ok else 'MISSING!'}: {label}")

# ── STEP 7: MainActivity.kt ───────────────────────────────────────────────────
MAIN_ACTIVITY_KT = (
'package com.tilawa.tilawa_enhancer\n'
'\n'
'import android.content.ContentValues\n'
'import android.media.MediaScannerConnection\n'
'import android.os.Build\n'
'import android.os.Environment\n'
'import android.provider.MediaStore\n'
'import android.view.WindowManager\n'
'import io.flutter.embedding.android.FlutterActivity\n'
'import io.flutter.embedding.engine.FlutterEngine\n'
'import io.flutter.plugin.common.MethodChannel\n'
'\n'
'class MainActivity : FlutterActivity() {\n'
'\n'
'    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {\n'
'        super.configureFlutterEngine(flutterEngine)\n'
'        MethodChannel(\n'
'            flutterEngine.dartExecutor.binaryMessenger,\n'
'            "com.tilawa.tilawa_enhancer/media"\n'
'        ).setMethodCallHandler { call, result ->\n'
'            when (call.method) {\n'
'                "scanFile" -> {\n'
'                    val path = call.argument<String>("path")\n'
'                    if (path != null) {\n'
'                        MediaScannerConnection.scanFile(\n'
'                            this, arrayOf(path), arrayOf("audio/mpeg")\n'
'                        ) { _, _ -> result.success(null) }\n'
'                    } else {\n'
'                        result.error("INVALID_PATH", "path is null", null)\n'
'                    }\n'
'                }\n'
'                "saveToDownloads" -> {\n'
'                    val sourcePath = call.argument<String>("path")\n'
'                    val fileName   = call.argument<String>("filename")\n'
'                    val mimeType = if (fileName?.endsWith(".wav") == true) "audio/wav" else "audio/mpeg"  // S157\n'
'                    if (sourcePath == null || fileName == null) {\n'
'                        result.error("INVALID_ARGS", "path or filename is null", null)\n'
'                        return@setMethodCallHandler\n'
'                    }\n'
'                    try {\n'
'                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {\n'
'                            val resolver = contentResolver\n'
'                            val values = ContentValues().apply {\n'
'                                put(MediaStore.Downloads.DISPLAY_NAME, fileName)\n'
'                                put(MediaStore.Downloads.MIME_TYPE, mimeType)\n'
'                                put(MediaStore.Downloads.IS_PENDING, 1)\n'
'                            }\n'
'                            val collection = MediaStore.Downloads.getContentUri(\n'
'                                MediaStore.VOLUME_EXTERNAL_PRIMARY\n'
'                            )\n'
'                            val itemUri = resolver.insert(collection, values)\n'
'                            if (itemUri == null) {\n'
'                                result.error("INSERT_FAILED", "MediaStore insert returned null", null)\n'
'                                return@setMethodCallHandler\n'
'                            }\n'
'                            // RC2 FIX: explicit null check prevents phantom 0-byte MediaStore entry\n'
'                            val outputStream = resolver.openOutputStream(itemUri)\n'
'                            if (outputStream == null) {\n'
'                                resolver.delete(itemUri, null, null)\n'
'                                result.error("STREAM_FAILED", "MediaStore openOutputStream returned null", null)\n'
'                                return@setMethodCallHandler\n'
'                            }\n'
'                            outputStream.use { out ->\n'
'                                java.io.File(sourcePath).inputStream().use { input -> input.copyTo(out) }\n'
'                            }\n'
'                            values.clear()\n'
'                            values.put(MediaStore.Downloads.IS_PENDING, 0)\n'
'                            resolver.update(itemUri, values, null, null)\n'
'                            result.success(itemUri.toString())\n'
'                        } else {\n'
'                            // RC1 FIX: background Thread prevents ANR on large files\n'
'                            Thread {\n'
'                                try {\n'
'                                    val downloadsDir = Environment.getExternalStoragePublicDirectory(\n'
'                                        Environment.DIRECTORY_DOWNLOADS\n'
'                                    )\n'
'                                    downloadsDir.mkdirs()\n'
'                                    val dest = java.io.File(downloadsDir, fileName)\n'
'                                    java.io.File(sourcePath).copyTo(dest, overwrite = true)\n'
'                                    MediaScannerConnection.scanFile(\n'
'                                        this@MainActivity,\n'
'                                        arrayOf(dest.absolutePath),\n'
'                                        arrayOf(mimeType)\n'
'                                    ) { _, _ -> result.success(dest.absolutePath) }\n'
'                                } catch (e: Exception) {\n'
'                                    android.os.Handler(android.os.Looper.getMainLooper()).post {\n'
'                                        result.error("SAVE_FAILED", e.message, null)\n'
'                                    }\n'
'                                }\n'
'                            }.start()\n'
'                        }\n'
'                    } catch (e: Exception) {\n'
'                        result.error("SAVE_FAILED", e.message, null)\n'
'                    }\n'
'                }\n'
'                "shareFile" -> {\n'
'                    val uriString = call.argument<String>("uri")\n'
'                    if (uriString != null) {\n'
'                        try {\n'
'                            val shareUri = android.net.Uri.parse(uriString)\n'
'                            val shareMime = if (uriString.endsWith(".wav")) "audio/wav" else "audio/mpeg"  // S157\n'
'                            val intent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {\n'
'                                type = shareMime\n'
'                                putExtra(android.content.Intent.EXTRA_STREAM, shareUri)\n'
'                                addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)\n'
'                            }\n'
'                            startActivity(android.content.Intent.createChooser(intent, "Share"))\n'
'                            result.success(null)\n'
'                        } catch (e: Exception) {\n'
'                            result.error("SHARE_FAILED", e.message, null)\n'
'                        }\n'
'                    } else {\n'
'                        result.error("INVALID_ARGS", "uri is null", null)\n'
'                    }\n'
'                }\n'
'                else -> result.notImplemented()\n'
'            }\n'
'        }\n'
'\n'
'        // S63: CPU wake lock — keeps polling alive with screen off\n'
'        var _wl: android.os.PowerManager.WakeLock? = null\n'
'        MethodChannel(\n'
'            flutterEngine.dartExecutor.binaryMessenger,\n'
'            "com.tilawa.tilawa_enhancer/wake"\n'
'        ).setMethodCallHandler { call, result ->\n'
'            val pm = getSystemService(POWER_SERVICE) as android.os.PowerManager\n'
'            when (call.method) {\n'
'                "acquire" -> {\n'
'                    _wl?.let { if (it.isHeld) it.release() }\n'
'                    _wl = pm.newWakeLock(\n'
'                        android.os.PowerManager.PARTIAL_WAKE_LOCK,\n'
'                        "tilawa:processing"\n'
'                    ).also { it.acquire(10 * 60 * 1000L) }\n'
'                    // S191: also force the screen to stay on, not just the CPU\n'
'                    runOnUiThread { window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }\n'
'                    result.success(null)\n'
'                }\n'
'                "release" -> {\n'
'                    _wl?.let { if (it.isHeld) it.release() }\n'
'                    _wl = null\n'
'                    runOnUiThread { window.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON) }  // S191\n'
'                    result.success(null)\n'
'                }\n'
'                else -> result.notImplemented()\n'
'            }\n'
'        }\n'
'    }\n'
'}\n'
)

kt_dir = APP / "src" / "main" / "kotlin" / "com" / "tilawa" / "tilawa_enhancer"
kt_dir.mkdir(parents=True, exist_ok=True)
kt_path = kt_dir / "MainActivity.kt"
kt_path.write_text(MAIN_ACTIVITY_KT)
print(f"\n  MainActivity.kt written: {kt_path}")

# ── STEP 8: S19 App Icon ──────────────────────────────────────────────────────
print()
print("  Generating app icon from assets/images/logo.png...")

LOGO_SRC = Path("assets") / "images" / "logo.png"
DENSITIES = {
    'mipmap-mdpi':    48,
    'mipmap-hdpi':    72,
    'mipmap-xhdpi':   96,
    'mipmap-xxhdpi':  144,
    'mipmap-xxxhdpi': 192,
}

if not LOGO_SRC.exists():
    print(f"  SKIP: {LOGO_SRC} not found. Using Flutter default icon.")
else:
    try:
        from PIL import Image

        src = Image.open(LOGO_SRC).convert("RGBA")

        for density, size in DENSITIES.items():
            dest_dir = APP / "src" / "main" / "res" / density
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / "ic_launcher.png"

            # Resize with high-quality Lanczos resampling, keep RGBA (transparency).
            # DO NOT composite onto a background — Android's launcher applies
            # the icon shape (circle, squircle, etc.) itself depending on the device.
            # Adding a dark background here causes a visible black ring/border
            # around the icon in the launcher. Save as RGBA PNG with full transparency.
            resized = src.resize((size, size), Image.LANCZOS)
            resized.save(str(dest_path), "PNG")
            print(f"  OK: ic_launcher.png → {density} ({size}x{size}px)")

        print("  All 5 icon sizes generated successfully.")

    except ImportError:
        print("  SKIP: Pillow not installed.")
        print("  Add 'pip install Pillow --quiet' to build.yml BEFORE patch_android.py.")
    except Exception as ex:
        print(f"  SKIP icon generation ({type(ex).__name__}: {ex})")

# ── STEP 9: Delete dead duplicate S class if still present ───────────────────
dead = Path("lib") / "l10n" / "strings.dart"
if dead.exists():
    dead.unlink()
    print("\n  Deleted lib/l10n/strings.dart (dead duplicate S class)")

print()
print("patch_android.py v12: DONE (DF3-ARCH fix + local engine progress)")



# ── S65-LOCAL-ENGINE ── appended by tilawa_fix_s65.py ─────────────────────────

import os as _os65

_LOCAL_RUNNER_KT = """package com.tilawa.tilawa_enhancer

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
    }

    private val dataDir     = context.filesDir
    private val alpineDir   = File(dataDir, "alpine-318")
    private val enginesDir  = File(dataDir, "engines")
    private val refAudioDir = File(dataDir, "reference_audio")
    private val prootBin    get() = File(context.applicationInfo.nativeLibraryDir, "libproot.so")
    private val prootLoader get() = File(context.applicationInfo.nativeLibraryDir, "libprootloader.so")
    private val cacheDir    = context.cacheDir.canonicalFile

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
                "runProotCmd" -> {  // S172b+S174-B2: returns real rc/out via result.success
                    val a       = call.arguments as Map<*, *>
                    val cmd     = (a["cmd"] as? String) ?: ""
                    val inFile  = (a["inputPath"] as? String) ?: ""
                    val outFile = (a["outputPath"] as? String) ?: ""
                    val tmMin   = (a["timeoutMin"] as? Int) ?: 10
                    scope.launch {
                        val extra = mutableListOf<String>()
                        listOf(inFile, outFile).forEach { p ->
                            if (p.isNotEmpty()) {
                                val dir = File(p).parent ?: return@forEach
                                extra += listOf("-b", "$dir:$dir")
                            }
                        }
                        extra += listOf("-b", "${cacheDir.absolutePath}:${cacheDir.absolutePath}")
                        context.getExternalFilesDir(null)?.absolutePath?.let { ed ->
                            extra += listOf("-b", "$ed:$ed") }
                        val (rc, out) = runProotWithBinds(listOf("/bin/sh", "-c", cmd), extra, tmMin)
                        ui { result.success(mapOf("rc" to rc, "out" to out)) }  // S174-B2
                    }
                }
                else -> result.notImplemented()
            }
        }
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
        // S182: a system-site-packages numpy (rare, bundled-in-image case) is
        // still trusted by existence — only the tilawa_numpy/ pip-installed
        // path is the one that can end up partially-written, so only that
        // path needs the stronger .numpy_verified marker check (S179/S182).
        val numpySystemOk = File(alpineDir, "usr/lib/python3.11/site-packages/numpy").exists() ||
            File(alpineDir, "usr/lib/python3.12/site-packages/numpy").exists()
        val numpyOk = numpySystemOk || File(alpineDir, ".numpy_verified").exists()
        val scipySystemOk = File(alpineDir, "usr/lib/python3.11/site-packages/scipy").exists() ||
            File(alpineDir, "usr/lib/python3.12/site-packages/scipy").exists()
        val scipyOk = scipySystemOk || File(alpineDir, ".numpy_verified").exists()
        if (!numpyOk || !scipyOk) return false  // S148: scipy required by v11.2
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

        // 2. Alpine rootfs — download like Termux proot-distro
        if (!File(alpineDir, "usr/bin/busybox").exists()) {
            progress(12, "Extracting Alpine Linux (bundled)…")
            alpineDir.mkdirs()
            val tmp = File(dataDir, "alpine.tar.gz")
            var alpineOk = false
            try {
                context.assets.open("alpine/alpine-rootfs.tar.gz")
                    .use { it.copyTo(java.io.FileOutputStream(tmp)) }
                alpineOk = true
            } catch (_: Exception) {}
            if (!alpineOk) {
                progress(12, "Downloading Alpine Linux (~4MB)…")
                download("https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/aarch64/alpine-minirootfs-3.21.3-aarch64.tar.gz", tmp, "Alpine rootfs", 12, 32)
            }
            extractTarGz(tmp, alpineDir)
            tmp.delete()
            File(alpineDir, "etc/resolv.conf")
                .writeText("nameserver 8.8.8.8\\nnameserver 1.1.1.1\\n")
            for (d in listOf("proc","dev","sys")) File(alpineDir, d).mkdirs()

        }
        // S124: detect Python version conflict — wipe if wrong version
        val py312lib = File(alpineDir, "usr/lib/libpython3.12.so.1.0")
        val py311lib = File(alpineDir, "usr/lib/python3.11")
        if (py312lib.exists() && !py311lib.exists()) {
            progress(11, "Fixing Python version conflict…")
            alpineDir.deleteRecursively()
            alpineDir.mkdirs()
            context.getSharedPreferences("tilawa_local", 0)
                .edit().putBoolean("setup_complete", false).apply()
        }
        progress(35, "Alpine ready")

        // 3. Python + ffmpeg — try bundled asset, else download from release  // S89-PYENV
        val numpyOk = File(alpineDir, "usr/lib/python3.11/site-packages/numpy").exists() ||
            File(alpineDir, "usr/lib/python3.12/site-packages/numpy").exists() ||
            File(alpineDir, "usr/lib/python3/dist-packages/numpy").exists() ||
            File(alpineDir, "tilawa_numpy/numpy").exists()  // S142: match isSetupComplete()
        if (!File(alpineDir, "usr/bin/python3").exists() || !numpyOk) {  // S115: re-extract if numpy missing
            val tmp2 = File(dataDir, "python-env.tar.gz")
            var pyOk = false
            // Try bundled asset first
            try {
                progress(38, "Extracting Python + ffmpeg (bundled)…")
                context.assets.open("alpine/python-env.tar.gz")
                    .use { it.copyTo(FileOutputStream(tmp2)) }
                pyOk = true
            } catch (_: Exception) {}
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
                // S106: install numpy/scipy to fixed known path
        val numpyTarget = File(alpineDir, "tilawa_numpy")
        // S179: a dir existing doesn't mean the install is good — pip can fail
        // partway (no network, interrupted) and leave a broken numpy/ folder
        // that "exists" forever after, so it's never retried and every engine
        // run hits a half-written package ("import numpy from its source
        // directory" ImportError). Probe with a real import, not just exists().
        // S182: marker isSetupComplete() can check cheaply (no proot) instead
        // of trusting the numpy/ folder's mere existence forever.
        val numpyVerifiedMarker = File(alpineDir, ".numpy_verified")
        fun numpyWorks(): Boolean {
            if (!File(numpyTarget, "numpy").exists() || !File(numpyTarget, "scipy").exists()) return false
            val probe = runProot(listOf("/usr/bin/python3", "-c", "import numpy, scipy"), timeoutMin=2)
            val ok = probe.first == 0
            if (ok) numpyVerifiedMarker.writeText("ok") else numpyVerifiedMarker.delete()
            return ok
        }
        if (!numpyWorks()) {
            progress(79, "Installing numpy + scipy (one-time ~2 min)…")
            numpyTarget.mkdirs()
            runProot(listOf("/bin/sh", "-c",
                "pip3 install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1 || " +
                "pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1"),
                timeoutMin=20)
            if (!numpyWorks()) {
                // S179: one clean retry — wipe whatever partial/broken state pip left behind
                progress(79, "Retrying numpy + scipy install (previous attempt was broken)…")
                numpyTarget.deleteRecursively()
                numpyTarget.mkdirs()
                runProot(listOf("/bin/sh", "-c",
                    "pip3 install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1 || " +
                    "pip install --quiet --no-cache-dir --target /tilawa_numpy numpy scipy 2>&1"),
                    timeoutMin=20)
                if (!numpyWorks()) {
                    throw IOException("numpy/scipy install failed — check internet connection and retry setup")
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
                    val dfVer = "0_5_6"
                    val url = "https://github.com/Rikorose/DeepFilterNet/releases/download/v0.5.6/deep-filter-${dfVer}-aarch64-unknown-linux-musl"
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
                val dfUrl = "https://github.com/Rikorose/DeepFilterNet/releases/download/v0.5.6/deep-filter-0_5_6-aarch64-unknown-linux-musl"
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
        File(dataDir, ".tilawa_setup_done").writeText("ok")
        context.getSharedPreferences("tilawa_local", 0)
            .edit().putBoolean("setup_complete", true).apply()  // S106
        progress(100, "Local engine ready!")
    }

    private suspend fun runEngine(engineId: String, inputPath: String,
            aggressive: Boolean = false) =  // S173
        withContext(Dispatchers.IO) {
        try {
            val script = mapOf(
                "v11.0" to "engine_safaa_v4.py",  // S172 // S149
                "v11.1" to "engine_itiqan_v6_official.py",
                "v11.2" to "engine_isteidad_v21.py",
                // v10.0-v7.0 are server-only — no local engine files // S156
            )[engineId] ?: "engine_safaa_v4.py"  // S172b

            // v11.0 (safaa) outputs WAV; v11.1/v11.2 output MP3 // S149
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
            val inParent  = cacheDir.absolutePath  // S174-B5: removed dead refMp3 var
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
                // S172b: safaa v4 = positional; others = -i/-o
                *( if (script.startsWith("engine_safaa_v4"))
                    arrayOf(actualInput, outputPath)
                else
                    arrayOf("-i", actualInput, "-o", outputPath, "--iterations", "3")),
            )
            // F8: engine_safaa_v4 argparse has no --ref flag — crash if ref files exist
            if (!script.startsWith("engine_safaa_v4")) {
                // S118: pass all 3 reference files
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
                environment()["PYTHONPATH"] = "/usr/lib/python3.11/site-packages:/usr/lib/python3.12/site-packages:/usr/lib/python3/dist-packages:/tilawa_numpy" // S141: tilawa_numpy path
                environment()["TERM"] = "xterm"
                environment()["LD_LIBRARY_PATH"] = dataDir.absolutePath
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
                // F9b: also detect safaa_v4 compact JSON (drr_before/drr_gain keys)
                if (l.startsWith("{") && (l.contains("score") || l.contains("version")
                        || l.contains("drr_before") || l.contains("drr_gain"))) lastJson = l
                if (lastJson == null && l.contains("/100")) {
                    val sc = Regex("([0-9]+[.][0-9]+)/100").findAll(l).lastOrNull()?.groupValues?.getOrNull(1)
                    if (sc != null) lastJson = "{\\"score\\": $sc, \\"lufs\\": 0.0, \\"rms\\": 0.0, \\"crest\\": 0.0, \\"lra\\": 0.0}"
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
    // S154: itiqan v6 emits ── phase_X ── tags; map to progress pct
                    l.contains("── phase_A5") || l.contains("── phase_A5_adaptive") -> 8
                    l.contains("── phase_A") -> 5
                    l.contains("── phase_B") -> 16
                    l.contains("── phase_C") -> 22
                    l.contains("── phase_D5") -> 34
                    l.contains("── phase_D") -> 30
                    l.contains("── phase_E") -> 38
                    l.contains("── phase_F") -> 46
                    l.contains("── phase_G5_sadaa") -> 62
                    l.contains("── phase_G5_crest") -> 65
                    l.contains("── phase_G6") -> 70
                    l.contains("── phase_G") -> 58
                    l.contains("── phase_H") -> 76
                    l.contains("── phase_I") -> 84
                    l.contains("── phase_J") -> 90
                    l.contains("score") && l.contains("/100") -> 96
                    // F9: engine_safaa_v4 stage tags → progress
                    l.startsWith("[S1]")                                              -> 10
                    l.startsWith("[S2-LF]")                                           -> 20
                    l.startsWith("[S3-WPE]")                                          -> 30
                    l.startsWith("[S4-ADF]") || l.startsWith("[S4-DF3]")              -> 45
                    l.startsWith("[S5-JALAA]")                                        -> 60
                    l.startsWith("[S6-tailNR]")                                       -> 72
                    l.startsWith("[S6.5-WIND]")                                       -> 82
                    l.startsWith("[S7-PASS]") || l.startsWith("[S7-WARN]") || l.startsWith("[S7]") -> 90
                    l == "[REPORT]"                                                   -> 96
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

    private fun runProotWithBinds(args: List<String>, extra: List<String>, tmMin: Int = 10): Pair<Int, String> {  // S172b
        val cmd = mutableListOf(prootBin.absolutePath,
            "--link2symlink", "-0",
            "-r", alpineDir.absolutePath,
            "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys") + extra +
            listOf("-w", "/", "--kill-on-exit") + args
        val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {
            environment()["HOME"] = "/root"; environment()["TERM"] = "xterm"
            environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            environment()["LD_LIBRARY_PATH"] = dataDir.absolutePath
            environment()["PROOT_TMP_DIR"] = File(dataDir, "proot-tmp").also { it.mkdirs() }.absolutePath
            if (prootLoader.exists()) environment()["PROOT_LOADER"] = prootLoader.absolutePath
        }.start()
        val output = proc.inputStream.bufferedReader().readText().takeLast(800)
        val code = try {
            if (!proc.waitFor(tmMin.toLong(), TimeUnit.MINUTES)) { proc.destroyForcibly(); -1 }
            else proc.exitValue()
        } catch (_: Exception) { proc.destroyForcibly(); -1 }
        return Pair(code, output)
}

    private fun runProot(args: List<String>, timeoutMin: Int = 35): Pair<Int, String> {
        val cmd = mutableListOf(prootBin.absolutePath,
            "--link2symlink",
            "-0",
            "-r", alpineDir.absolutePath,
            "-b", "/proc:/proc", "-b", "/dev:/dev", "-b", "/sys:/sys",
                        "-w", "/",
            "--kill-on-exit") + args +
            if (File(alpineDir, "etc/resolv.conf").exists())
                listOf("-b", "${alpineDir.absolutePath}/etc/resolv.conf:/etc/resolv.conf")
            else emptyList()
        val proc = ProcessBuilder(cmd).redirectErrorStream(true).apply {
            environment()["HOME"] = "/root"
            environment()["PATH"] = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            environment()["TERM"] = "xterm"
            environment()["LD_LIBRARY_PATH"] = dataDir.absolutePath
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
        listOf("engine_safaa_v4.py","engine_safaa_v3_fixed.py","engine_itiqan_v6_official.py", // S179: v4 is what runEngine() actually invokes (S172) — v3_fixed was never replaced here, so /engines/engine_safaa_v4.py never existed on disk (rc=2)
               "engine_isteidad_v21.py","idrak_text_v2.py","miraat_ref_v2.py","hakim_gen_v2.py","naqaa_v1_tested.py","bayan_ve_v2fix.py",
               "noor_v5.py","ihyaa_ve.py").forEach { name ->  // S156: v7-v10 are server-only
            val dest = File(enginesDir, name)
            if (dest.exists() && dest.length() > 1024) return@forEach  // S88
            try { context.assets.open("flutter_assets/assets/engines/$name").use { inp ->
                FileOutputStream(dest).use { inp.copyTo(it) } }
            } catch (_: Exception) {
                try { context.assets.open("engines/$name").use { inp ->
                    FileOutputStream(dest).use { inp.copyTo(it) } }
                } catch (_: Exception) {}
            }
        }
    }

    // downloadRefAudio() removed — ref audio now bundled in APK assets

    private fun ui(block: () -> Unit) = activity.runOnUiThread(block)
}
"""

def _patch_local_engine():
    """Write LocalEngineRunner.kt and register it in MainActivity.kt."""
    kt_dir = _os65.path.join(
        'android','app','src','main','kotlin','com','tilawa','tilawa_enhancer')
    if not _os65.path.isdir(kt_dir):
        print(f'  --  S65: {kt_dir} not found (CI will create it) — skipping local engine patch')
        return

    # 1. Write LocalEngineRunner.kt
    runner_path = _os65.path.join(kt_dir, 'LocalEngineRunner.kt')
    with open(runner_path, 'w') as f:
        f.write(_LOCAL_RUNNER_KT)
    print('  OK  S65: LocalEngineRunner.kt written')

    # 2. Patch MainActivity.kt — add registration after super.configureFlutterEngine
    main_path = _os65.path.join(kt_dir, 'MainActivity.kt')
    if not _os65.path.exists(main_path):
        print('  XX  S65: MainActivity.kt not found — cannot register LocalEngineRunner')
        return
    src = open(main_path).read()
    anchor  = 'super.configureFlutterEngine(flutterEngine)'
    inject  = '    LocalEngineRunner(this, applicationContext).registerWith(flutterEngine) // S65'
    if inject in src:
        print('  OK  S65: LocalEngineRunner already registered in MainActivity.kt')
    elif anchor in src:
        src = src.replace(anchor, anchor + '\n' + inject, 1)
        open(main_path, 'w').write(src)
        print('  OK  S65: LocalEngineRunner registered in MainActivity.kt')
    else:
        print('  XX  S65: super.configureFlutterEngine not found in MainActivity.kt')

_patch_local_engine()
# ── end S65-LOCAL-ENGINE ────────────────────────────────────────────────────
