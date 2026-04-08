"""patch_android.py v6"""
from pathlib import Path

ROOT = Path("android")
APP  = ROOT / "app"

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

manifest = APP / "src" / "main" / "AndroidManifest.xml"
manifest.parent.mkdir(parents=True, exist_ok=True)
manifest.write_text("""<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <!-- FIX 1: INTERNET — was MISSING from ALL previous versions v1-v5 -->
    <uses-permission android:name="android.permission.INTERNET"/>
    <uses-permission android:name="android.permission.READ_MEDIA_AUDIO"/>
    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"
        android:maxSdkVersion="32"/>

    <application
        android:label="tilawa_enhancer"
        android:name="${applicationName}"
        android:icon="@mipmap/ic_launcher"
        android:hardwareAccelerated="true"
        android:networkSecurityConfig="@xml/network_security_config"
        android:usesCleartextTraffic="false">

        <!-- FIX 2+3: networkSecurityConfig and usesCleartextTraffic
             are on <application> tag — were wrongly on <activity> in v4-v5 -->

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

        <!-- url_launcher: exported=false required Android 12+ -->
        <activity
            android:name="io.flutter.plugins.urllauncher.WebViewActivity"
            android:exported="false"
            android:theme="@android:style/Theme.Black.NoTitleBar"
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode"
            android:hardwareAccelerated="true"
            android:windowSoftInputMode="adjustResize"/>

        <meta-data android:name="flutterEmbedding" android:value="2"/>
    </application>
</manifest>
""")
print("  AndroidManifest.xml written (v6 correct)")

txt = manifest.read_text()
for check, label in [
    ("android.permission.INTERNET", "INTERNET permission"),
    ("networkSecurityConfig",        "networkSecurityConfig on <application>"),
    ("usesCleartextTraffic",         "usesCleartextTraffic on <application>"),
    ("flutterEmbedding",             "flutterEmbedding meta-data"),
    ("applicationName",              "${applicationName}"),
    ("NormalTheme",                  "NormalTheme meta-data"),
]:
    ok = check in txt
    print(f"  {'OK' if ok else 'MISSING!'}: {label}")

print()
print("patch_android.py v6: DONE")
