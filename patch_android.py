"""patch_android.py v11 — S19
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
    ndkVersion flutter.ndkVersion
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }
    kotlinOptions { jvmTarget = "1.8" }
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
    implementation "org.jetbrains.kotlin:kotlin-stdlib-jdk8:2.2.20"
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
    id "com.android.application" version "8.11.1" apply false
    id "org.jetbrains.kotlin.android" version "2.2.20" apply false
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
    "distributionUrl=https\\://services.gradle.org/distributions/gradle-8.14-all.zip\n"
)
print("  gradle-wrapper.properties OK (Gradle 8.3)")

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
'                    if (sourcePath == null || fileName == null) {\n'
'                        result.error("INVALID_ARGS", "path or filename is null", null)\n'
'                        return@setMethodCallHandler\n'
'                    }\n'
'                    try {\n'
'                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {\n'
'                            val resolver = contentResolver\n'
'                            val values = ContentValues().apply {\n'
'                                put(MediaStore.Downloads.DISPLAY_NAME, fileName)\n'
'                                put(MediaStore.Downloads.MIME_TYPE, "audio/mpeg")\n'
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
'                                        arrayOf("audio/mpeg")\n'
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
'                            val intent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {\n'
'                                type = "audio/mpeg"\n'
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
print("patch_android.py v11: DONE")

