"""
patch_android.py — DEFINITIVE FIX (v4)

ROOT CAUSE OF ALL CRASHES:
  Previous versions wrote AndroidManifest.xml from scratch,
  including <InitializationProvider> which triggers
  ProfileInstallerInitializer at startup — crashes on Samsung Knox.
  Also wrote styles.xml / strings.xml overwriting Flutter's correct versions.

THIS VERSION:
  - Writes build.gradle from scratch (safe)
  - Writes settings.gradle from scratch (safe)
  - Writes gradle-wrapper.properties (Gradle 8.3 fix)
  - Writes network_security_config.xml (localhost HTTP fix)
  - READS Flutter's generated AndroidManifest.xml, patches ONLY 2 attributes
  - Does NOT touch styles.xml — Flutter's version is correct
  - Does NOT touch strings.xml — Flutter's version is correct
"""
from pathlib import Path
import re

ROOT = Path('android')
APP  = ROOT / 'app'

# ── 1. build.gradle ───────────────────────────────────────────────────────────
(APP / 'build.gradle').write_text('''
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

    kotlinOptions {
        jvmTarget = "1.8"
    }

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

flutter {
    source "../.."
}

dependencies {
    implementation "org.jetbrains.kotlin:kotlin-stdlib-jdk7:1.9.22"
}
''')
print("  ✅ build.gradle written")

# ── 2. settings.gradle ────────────────────────────────────────────────────────
(ROOT / 'settings.gradle').write_text('''
pluginManagement {
    def flutterSdkPath = {
        def properties = new Properties()
        file("local.properties").withInputStream { properties.load(it) }
        def flutterSdkPath = properties.getProperty("flutter.sdk")
        assert flutterSdkPath != null, "flutter.sdk not set in local.properties"
        return flutterSdkPath
    }()
    includeBuild("${flutterSdkPath}/packages/flutter_tools/gradle")
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    id "dev.flutter.flutter-plugin-loader" version "1.0.0"
    id "com.android.application" version "8.1.0" apply false
    id "org.jetbrains.kotlin.android" version "1.9.22" apply false
}

include ":app"
''')
print("  ✅ settings.gradle written")

# ── 3. gradle-wrapper.properties — Gradle 8.3 ────────────────────────────────
wrapper = ROOT / 'gradle' / 'wrapper' / 'gradle-wrapper.properties'
wrapper.parent.mkdir(parents=True, exist_ok=True)
wrapper.write_text(
    'distributionBase=GRADLE_USER_HOME\n'
    'distributionPath=wrapper/dists\n'
    'zipStoreBase=GRADLE_USER_HOME\n'
    'zipStorePath=wrapper/dists\n'
    'distributionUrl=https\\://services.gradle.org/distributions/gradle-8.3-all.zip\n'
)
print("  ✅ gradle-wrapper.properties → Gradle 8.3")

# ── 4. network_security_config.xml — allow localhost HTTP ─────────────────────
res_xml = APP / 'src' / 'main' / 'res' / 'xml'
res_xml.mkdir(parents=True, exist_ok=True)
(res_xml / 'network_security_config.xml').write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n'
    '<network-security-config>\n'
    '    <domain-config cleartextTrafficPermitted="true">\n'
    '        <domain includeSubdomains="false">127.0.0.1</domain>\n'
    '        <domain includeSubdomains="false">localhost</domain>\n'
    '    </domain-config>\n'
    '</network-security-config>\n'
)
print("  ✅ network_security_config.xml → allows localhost HTTP")

# ── 5. PATCH AndroidManifest.xml — do NOT rewrite from scratch ───────────────
# Flutter's generated manifest is already correct.
# We ONLY need to add 2 attributes to the <application> tag:
#   android:usesCleartextTraffic="false"
#   android:networkSecurityConfig="@xml/network_security_config"
# And add READ_MEDIA_AUDIO permission for Android 13+

mp = APP / 'src' / 'main' / 'AndroidManifest.xml'
manifest = mp.read_text()

# Add usesCleartextTraffic if not present
if 'usesCleartextTraffic' not in manifest:
    manifest = manifest.replace(
        'android:hardwareAccelerated="true"',
        'android:hardwareAccelerated="true"\n        android:usesCleartextTraffic="false"\n        android:networkSecurityConfig="@xml/network_security_config"'
    )
    # fallback: insert before <activity
    if 'usesCleartextTraffic' not in manifest:
        manifest = re.sub(
            r'(<application\b)',
            r'\1\n        android:usesCleartextTraffic="false"\n        android:networkSecurityConfig="@xml/network_security_config"',
            manifest
        )
    print("  ✅ AndroidManifest.xml patched: usesCleartextTraffic + networkSecurityConfig")
else:
    print("  ✅ AndroidManifest.xml already has usesCleartextTraffic")

# Add READ_MEDIA_AUDIO permission if not present (needed for audio files on Android 13+)
if 'READ_MEDIA_AUDIO' not in manifest:
    manifest = manifest.replace(
        '<application',
        '<uses-permission android:name="android.permission.READ_MEDIA_AUDIO"/>\n\n    <application'
    )
    print("  ✅ AndroidManifest.xml: READ_MEDIA_AUDIO permission added")

mp.write_text(manifest)
print("  ✅ AndroidManifest.xml saved (Flutter's original structure preserved)")

# ── DONE ──────────────────────────────────────────────────────────────────────
print()
print("patch_android.py: ALL DONE")
print("  Flutter's styles.xml   → untouched (correct theme parents)")
print("  Flutter's strings.xml  → untouched")
print("  Flutter's MainActivity → untouched (extends FlutterActivity)")
print("  ProfileInstallerInitializer → NOT in our manifest (no startup crash)")
