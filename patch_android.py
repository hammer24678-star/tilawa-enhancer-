"""patch_android.py v7 — read+patch, never write from scratch (Rule 10)"""
from pathlib import Path
import re

ROOT = Path("android")
APP  = ROOT / "app"

(APP / "build.gradle").write_text(
'plugins {\n'
'    id "com.android.application"\n'
'    id "kotlin-android"\n'
'    id "dev.flutter.flutter-gradle-plugin"\n'
'}\n'
'android {\n'
'    namespace "com.tilawa.tilawa_enhancer"\n'
'    compileSdk 34\n'
'    ndkVersion flutter.ndkVersion\n'
'    compileOptions {\n'
'        sourceCompatibility JavaVersion.VERSION_1_8\n'
'        targetCompatibility JavaVersion.VERSION_1_8\n'
'    }\n'
'    kotlinOptions { jvmTarget = "1.8" }\n'
'    defaultConfig {\n'
'        applicationId "com.tilawa.tilawa_enhancer"\n'
'        minSdk 21\n'
'        targetSdk 34\n'
'        versionCode 3\n'
'        versionName "2.1.0"\n'
'    }\n'
'    buildTypes {\n'
'        release {\n'
'            signingConfig signingConfigs.debug\n'
'            minifyEnabled false\n'
'            shrinkResources false\n'
'        }\n'
'    }\n'
'}\n'
'flutter { source "../.." }\n'
'dependencies {\n'
'    implementation "org.jetbrains.kotlin:kotlin-stdlib-jdk7:1.9.22"\n'
'}\n'
)
print("  build.gradle OK")

(ROOT / "settings.gradle").write_text(
'pluginManagement {\n'
'    def flutterSdkPath = {\n'
'        def properties = new Properties()\n'
'        file("local.properties").withInputStream { properties.load(it) }\n'
'        def flutterSdkPath = properties.getProperty("flutter.sdk")\n'
'        assert flutterSdkPath != null\n'
'        return flutterSdkPath\n'
'    }()\n'
'    includeBuild("${flutterSdkPath}/packages/flutter_tools/gradle")\n'
'    repositories { google(); mavenCentral(); gradlePluginPortal() }\n'
'}\n'
'plugins {\n'
'    id "dev.flutter.flutter-plugin-loader" version "1.0.0"\n'
'    id "com.android.application" version "8.1.0" apply false\n'
'    id "org.jetbrains.kotlin.android" version "1.9.22" apply false\n'
'}\n'
'include ":app"\n'
)
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
print("  gradle-wrapper.properties OK (Gradle 8.3)")

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

# MANIFEST: read Flutter's version, patch it — NEVER write from scratch (Rule 10)
manifest_path = APP / "src" / "main" / "AndroidManifest.xml"
txt = manifest_path.read_text()
print(f"  Manifest read ({len(txt)} bytes)")

# A8 fix: add permissions before <application (Flutter default has none)
if "android.permission.INTERNET" not in txt:
    perms = (
        '    <uses-permission android:name="android.permission.INTERNET"/>\n'
        '    <uses-permission android:name="android.permission.READ_MEDIA_AUDIO"/>\n'
        '    <uses-permission android:name="android.permission.READ_EXTERNAL_STORAGE"'
        ' android:maxSdkVersion="32"/>\n\n'
    )
    txt = txt.replace("\n    <application", "\n" + perms + "    <application", 1)
    print("  INTERNET + READ_MEDIA_AUDIO inserted")
else:
    print("  INTERNET already present")

# A9 fix: add network attrs to <application> tag, NOT <activity>
# Target the closing > of Flutter's <application attribute list specifically
if "networkSecurityConfig" not in txt:
    OLD = 'android:icon="@mipmap/ic_launcher">'
    NEW = ('android:icon="@mipmap/ic_launcher"\n'
           '        android:networkSecurityConfig="@xml/network_security_config"\n'
           '        android:usesCleartextTraffic="false">')
    if OLD in txt:
        txt = txt.replace(OLD, NEW, 1)
        print("  networkSecurityConfig added to <application>")
    else:
        # Regex fallback: match <application ...> spanning multiple lines
        txt = re.sub(
            r'(<application\b(?:[^<])*?)(>)',
            lambda m: m.group(1)
                + '\n        android:networkSecurityConfig="@xml/network_security_config"'
                + '\n        android:usesCleartextTraffic="false"'
                + m.group(2),
            txt, count=1, flags=re.DOTALL
        )
        print("  networkSecurityConfig added via regex fallback")
else:
    print("  networkSecurityConfig already present")

manifest_path.write_text(txt)
print("  AndroidManifest.xml patched and saved")

# Verification
final = manifest_path.read_text()
checks = [
    ("android.permission.INTERNET",         "INTERNET permission"),
    ("android.permission.READ_MEDIA_AUDIO", "READ_MEDIA_AUDIO"),
    ("networkSecurityConfig",               "networkSecurityConfig"),
    ("usesCleartextTraffic",                "usesCleartextTraffic"),
    ("NormalTheme",                          "NormalTheme meta-data"),
    ("flutterEmbedding",                     "flutterEmbedding meta-data"),
]
ok = True
for token, label in checks:
    found = token in final
    print(f"  {'OK' if found else 'MISSING!'}: {label}")
    if not found:
        ok = False

# Confirm networkSecurityConfig is on <application>, not <activity>
before_activity = final[:final.find("<activity")] if "<activity" in final else final
if "networkSecurityConfig" in before_activity:
    print("  OK: networkSecurityConfig is on <application> (not <activity>)")
else:
    print("  WRONG: networkSecurityConfig ended up on <activity>!")
    ok = False

print()
print("patch_android.py v7:", "ALL OK" if ok else "ERRORS — check above")
