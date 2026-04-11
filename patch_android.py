"""patch_android.py v9
Changes from v6:
  + WRITE_EXTERNAL_STORAGE permission (maxSdkVersion=28) — needed for Android ≤ 9
  + Writes MainActivity.kt with MediaScannerConnection MethodChannel
    (build.yml Fix MainActivity step creates the dir first; we overwrite the file)
"""
from pathlib import Path
import os

ROOT = Path("android")
APP  = ROOT / "app"

# ── STEP 3-1: build.gradle (unchanged from v6) ─────────────────────────────────
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

# ── STEP 3-5: AndroidManifest.xml — adds WRITE_EXTERNAL_STORAGE ───────────────
# CRITICAL: WRITE_EXTERNAL_STORAGE with maxSdkVersion=28 is required for
# Android ≤ 9 (API 28) to write to getExternalStorageDirectory().
# Android 10+ (API 29+): no permission needed (app-scoped storage exemption).
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

    <!-- Storage — WRITE (Android ≤ 9 only; API 29+ uses app-scoped dir, no permission needed) -->
    <uses-permission android:name="android.permission.WRITE_EXTERNAL_STORAGE"
        android:maxSdkVersion="28"/>

    <application
        android:label="محسِّن التلاوة"
        android:name="${applicationName}"
        android:icon="@mipmap/ic_launcher"
        android:hardwareAccelerated="true"
        android:networkSecurityConfig="@xml/network_security_config"
        android:usesCleartextTraffic="false">

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
print("  AndroidManifest.xml written (v9 — WRITE_EXTERNAL_STORAGE added)")

# ── STEP 3-6: Verify manifest ──────────────────────────────────────────────────
txt = manifest.read_text()
for check, label in [
    ("android.permission.INTERNET",              "INTERNET permission"),
    ("WRITE_EXTERNAL_STORAGE",                   "WRITE_EXTERNAL_STORAGE (≤API28)"),
    ("READ_MEDIA_AUDIO",                         "READ_MEDIA_AUDIO (API33+)"),
    ("networkSecurityConfig",                    "networkSecurityConfig on <application>"),
    ("usesCleartextTraffic",                     "usesCleartextTraffic on <application>"),
    ("flutterEmbedding",                         "flutterEmbedding meta-data"),
    ("applicationName",                          "${applicationName}"),
    ("NormalTheme",                              "NormalTheme meta-data"),
]:
    ok = check in txt
    print(f"  {'OK' if ok else 'MISSING!'}: {label}")

# ── STEP 3-7: Write MainActivity.kt with MediaScanner MethodChannel ────────────
# build.yml "Fix MainActivity package" step runs BEFORE this script.
# It creates com/tilawa/tilawa_enhancer/ and moves the file there.
# We OVERWRITE it here with the full MediaScanner implementation.
# The directory already exists — makedirs is a no-op safety call.
MAIN_ACTIVITY_KT = r"""package com.tilawa.tilawa_enhancer

import android.media.MediaScannerConnection
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

/**
 * MainActivity — S17
 * Adds MethodChannel "com.tilawa.tilawa_enhancer/media" with method "scanFile".
 *
 * Purpose: After downloadFile() writes a file to /Android/data/.../files/,
 * it calls this channel. MediaScannerConnection.scanFile() notifies Android's
 * media database, making the file visible in:
 *   - Samsung My Files → Downloads
 *   - Xiaomi MIUI Files → Recent
 *   - Any stock file manager's "Downloads" section
 * Without this call, the file is a ghost — invisible until device reboot.
 */
class MainActivity : FlutterActivity() {

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            "com.tilawa.tilawa_enhancer/media"
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "scanFile" -> {
                    val path = call.argument<String>("path")
                    if (path != null) {
                        MediaScannerConnection.scanFile(
                            this,
                            arrayOf(path),
                            arrayOf("audio/mpeg")
                        ) { _, _ ->
                            result.success(null)
                        }
                    } else {
                        result.error("INVALID_PATH", "path argument is null", null)
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
print(f"  MainActivity.kt written with MediaScanner channel: {kt_path}")

# ── STEP 3-8: Verify MainActivity.kt ──────────────────────────────────────────
kt_txt = kt_path.read_text()
for check, label in [
    ("package com.tilawa.tilawa_enhancer",               "correct package"),
    ("MediaScannerConnection",                           "MediaScannerConnection import"),
    ("com.tilawa.tilawa_enhancer/media",                 "channel name matches Dart side"),
    ("scanFile",                                         "scanFile method handler"),
]:
    ok = check in kt_txt
    print(f"  {'OK' if ok else 'MISSING!'}: {label}")

print()
print("patch_android.py v9: DONE")
