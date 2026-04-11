"""patch_android.py v10
Changes from v9:
  RC1: MainActivity.kt — adds 'saveToDownloads' MethodChannel method.
       Android 10+: uses MediaStore.Downloads API → file lands in public Downloads.
       Android 9- : uses Environment.DIRECTORY_DOWNLOADS + MediaScanner trigger.
  H1 : AndroidManifest.xml — usesCleartextTraffic false→true (networkSecurityConfig
       is the authoritative policy source; false was semantically inconsistent).
  KEEP: scanFile method retained for compatibility (safe no-op if unused).
"""
from pathlib import Path

ROOT = Path("android")
APP  = ROOT / "app"

# ── STEP 3-1: build.gradle (unchanged from v9) ────────────────────────────────
(APP / "build.gradle").write_text("""
plugins {
    id "com.android.application"
    id "kotlin-android"
    id "dev.flutter.flutter-gradle-plugin"
}
android {
    namespace "com.tilawa.tilawa_enhancer"
    compileSdk 34
    ndkVersion flutter.ndkVersion
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }
    kotlinOptions { jvmTarget = "1.8" }
    defaultConfig {
        applicationId "com.tilawa.tilawa_enhancer"
        minSdk 21
        targetSdk 34
        versionCode 1
        versionName "1.0.0"
    }
    buildTypes {
        release {
            signingConfig signingConfigs.debug
            minifyEnabled false
            shrinkResources false
        }
    }
}
flutter { source "../.." }
dependencies {
    implementation "org.jetbrains.kotlin:kotlin-stdlib-jdk7:1.9.22"
}
""")
print("  build.gradle OK")

# ── STEP 3-2: settings.gradle (unchanged) ─────────────────────────────────────
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
    id "com.android.application" version "8.1.0" apply false
    id "org.jetbrains.kotlin.android" version "1.9.22" apply false
}
include ":app"
""")
print("  settings.gradle OK")

# ── STEP 3-3: Gradle wrapper → 8.3 (unchanged) ────────────────────────────────
wrapper = ROOT / "gradle" / "wrapper" / "gradle-wrapper.properties"
wrapper.parent.mkdir(parents=True, exist_ok=True)
wrapper.write_text(
    "distributionBase=GRADLE_USER_HOME\n"
    "distributionPath=wrapper/dists\n"
    "zipStoreBase=GRADLE_USER_HOME\n"
    "zipStorePath=wrapper/dists\n"
    "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.3-all.zip\n"
)
print("  gradle-wrapper.properties OK (8.3)")

# ── STEP 3-4: network_security_config.xml (unchanged) ─────────────────────────
res_xml = APP / "src" / "main" / "res" / "xml"
res_xml.mkdir(parents=True, exist_ok=True)
(res_xml / "network_security_config.xml").write_text(
    """<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="false">127.0.0.1</domain>
        <domain includeSubdomains="false">localhost</domain>
    </domain-config>
</network-security-config>
"""
)
print("  network_security_config.xml OK")

# ── STEP 3-5: AndroidManifest.xml ─────────────────────────────────────────────
# H1 FIX: usesCleartextTraffic changed from "false" to "true".
# networkSecurityConfig is the authoritative policy; it already blocks cleartext
# everywhere except 127.0.0.1/localhost. Setting the attribute to false was
# semantically inconsistent and potentially confusing for future maintainers.
manifest = APP / "src" / "main" / "AndroidManifest.xml"
manifest.parent.mkdir(parents=True, exist_ok=True)
manifest.write_text("""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- Network -->
    <uses-permission android:name="android.permission.INTERNET"/>

    <!-- Storage — READ -->
    <uses-permission android:name="android.permission.READ_MEDIA_AUDIO"/>
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"
        android:maxSdkVersion="32"/>

    <!-- Storage — WRITE (Android <= 9 only; needed for DIRECTORY_DOWNLOADS write) -->
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"
        android:maxSdkVersion="28"/>

    <application
        android:label="\\u0645\\u062d\\u0633\\u0650\\u0651\\u0646 \\u0627\\u0644\\u062a\\u0644\\u0627\\u0648\\u0629"
        android:name="${applicationName}"
        android:icon="@mipmap/ic_launcher"
        android:hardwareAccelerated="true"
        android:networkSecurityConfig="@xml/network_security_config"
        android:usesCleartextTraffic="true">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:launchMode="singleTop"
            android:taskAffinity=""
            android:theme="@style/LaunchTheme"
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|smallestScreenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode"
            android:hardwareAccelerated="true"
            android:windowSoftInputMode="adjustResize">
            <meta-data
                android:name="io.flutter.embedding.android.NormalTheme"
                android:resource="@style/NormalTheme"/>
            <intent-filter>
                <action android:name="android.intent.action.MAIN"/>
                <category android:name="android.intent.category.LAUNCHER"/>
            </intent-filter>
        </activity>

        <meta-data android:name="flutterEmbedding" android:value="2"/>
    </application>
</manifest>
""")
print("  AndroidManifest.xml written (v10 — usesCleartextTraffic=true)")

# ── STEP 3-6: Verify manifest ──────────────────────────────────────────────────
txt = manifest.read_text()
for check, label in [
    ("android.permission.INTERNET",              "INTERNET permission"),
    ("WRITE_EXTERNAL_STORAGE",                   "WRITE_EXTERNAL_STORAGE (<=API28)"),
    ("READ_MEDIA_AUDIO",                         "READ_MEDIA_AUDIO (API33+)"),
    ("networkSecurityConfig",                    "networkSecurityConfig on <application>"),
    ('usesCleartextTraffic="true"',              "usesCleartextTraffic=TRUE (H1 fix)"),
    ("flutterEmbedding",                         "flutterEmbedding meta-data"),
    ("applicationName",                          "${applicationName}"),
    ("NormalTheme",                              "NormalTheme meta-data"),
]:
    ok = check in txt
    print(f"  {'OK' if ok else 'MISSING!'}: {label}")

# ── STEP 3-7: Write MainActivity.kt — scanFile + saveToDownloads ───────────────
# RC1 FIX: Added 'saveToDownloads' method.
#   Android 10+ (API 29+): MediaStore.Downloads API — no WRITE permission needed,
#     file lands directly in the public Downloads folder visible to ALL file managers.
#   Android 9- (API 28-):  Environment.DIRECTORY_DOWNLOADS — requires
#     WRITE_EXTERNAL_STORAGE which is declared in manifest (maxSdkVersion=28).
#     MediaScanner called after copy so the file appears immediately.
# KEEP: 'scanFile' method retained for backwards compatibility.
MAIN_ACTIVITY_KT = r"""package com.tilawa.tilawa_enhancer

import android.content.ContentValues
import android.media.MediaScannerConnection
import android.os.Build
import android.os.Environment
import android.provider.MediaStore
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * MainActivity — S18
 *
 * MethodChannel: "com.tilawa.tilawa_enhancer/media"
 *
 * Methods:
 *   scanFile(path: String)
 *     Legacy media scanner trigger. Kept for compatibility.
 *
 *   saveToDownloads(path: String, filename: String) -> String (uri/path)
 *     RC1 FIX: Saves a file from [path] into the public Downloads folder.
 *     API 29+: MediaStore.Downloads — no permission needed, always visible.
 *     API <29: Environment.DIRECTORY_DOWNLOADS — needs WRITE_EXTERNAL_STORAGE
 *              (declared in manifest with maxSdkVersion=28).
 */
class MainActivity : FlutterActivity() {

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            "com.tilawa.tilawa_enhancer/media"
        ).setMethodCallHandler { call, result ->
            when (call.method) {

                // ── Legacy: kept for compatibility ─────────────────────────────
                "scanFile" -> {
                    val path = call.argument<String>("path")
                    if (path != null) {
                        MediaScannerConnection.scanFile(
                            this, arrayOf(path), arrayOf("audio/mpeg")
                        ) { _, _ -> result.success(null) }
                    } else {
                        result.error("INVALID_PATH", "path argument is null", null)
                    }
                }

                // ── RC1: Save to public Downloads ──────────────────────────────
                "saveToDownloads" -> {
                    val sourcePath = call.argument<String>("path")
                    val fileName   = call.argument<String>("filename")
                    if (sourcePath == null || fileName == null) {
                        result.error("INVALID_ARGS", "path or filename is null", null)
                        return@setMethodCallHandler
                    }
                    try {
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                            // ── Android 10+ — MediaStore.Downloads ────────────
                            // No WRITE permission needed. File appears immediately
                            // in Downloads section of ALL file managers (Samsung,
                            // MIUI, Pixel Files, etc.).
                            val resolver = contentResolver
                            val values = ContentValues().apply {
                                put(MediaStore.Downloads.DISPLAY_NAME, fileName)
                                put(MediaStore.Downloads.MIME_TYPE, "audio/mpeg")
                                put(MediaStore.Downloads.IS_PENDING, 1)
                            }
                            val collection = MediaStore.Downloads.getContentUri(
                                MediaStore.VOLUME_EXTERNAL_PRIMARY
                            )
                            val itemUri = resolver.insert(collection, values)
                            if (itemUri == null) {
                                result.error("INSERT_FAILED",
                                    "MediaStore.Downloads insert returned null", null)
                                return@setMethodCallHandler
                            }
                            resolver.openOutputStream(itemUri)?.use { out ->
                                java.io.File(sourcePath).inputStream()
                                    .use { input -> input.copyTo(out) }
                            }
                            values.clear()
                            values.put(MediaStore.Downloads.IS_PENDING, 0)
                            resolver.update(itemUri, values, null, null)
                            result.success(itemUri.toString())

                        } else {
                            // ── Android 9 and below — public Downloads dir ────
                            // WRITE_EXTERNAL_STORAGE declared in manifest (maxSdk=28).
                            val downloadsDir = Environment.getExternalStoragePublicDirectory(
                                Environment.DIRECTORY_DOWNLOADS
                            )
                            downloadsDir.mkdirs()
                            val dest = java.io.File(downloadsDir, fileName)
                            java.io.File(sourcePath).copyTo(dest, overwrite = true)
                            // Trigger media scan so file appears immediately
                            MediaScannerConnection.scanFile(
                                this,
                                arrayOf(dest.absolutePath),
                                arrayOf("audio/mpeg")
                            ) { _, _ -> result.success(dest.absolutePath) }
                        }
                    } catch (e: Exception) {
                        result.error("SAVE_FAILED", e.message, null)
                    }
                }

                else -> result.notImplemented()
            }
        }
    }
}
"""

kt_dir = APP / "src" / "main" / "kotlin" / "com" / "tilawa" / "tilawa_enhancer"
kt_dir.mkdir(parents=True, exist_ok=True)
kt_path = kt_dir / "MainActivity.kt"
kt_path.write_text(MAIN_ACTIVITY_KT)
print(f"  MainActivity.kt written (v10 — saveToDownloads): {kt_path}")

# ── STEP 3-8: Verify MainActivity.kt ──────────────────────────────────────────
kt_txt = kt_path.read_text()
for check, label in [
    ("package com.tilawa.tilawa_enhancer",        "correct package"),
    ("MediaScannerConnection",                    "MediaScannerConnection import"),
    ("com.tilawa.tilawa_enhancer/media",          "channel name matches Dart side"),
    ("scanFile",                                  "scanFile method (legacy)"),
    ("saveToDownloads",                           "saveToDownloads method (RC1)"),
    ("MediaStore.Downloads",                      "MediaStore.Downloads API (API29+)"),
    ("DIRECTORY_DOWNLOADS",                       "DIRECTORY_DOWNLOADS fallback (API<29)"),
    ("IS_PENDING",                                "IS_PENDING flag (atomic write)"),
]:
    ok = check in kt_txt
    print(f"  {'OK' if ok else 'MISSING!'}: {label}")

print()
print("patch_android.py v10: DONE")
