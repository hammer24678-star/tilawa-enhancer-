#!/usr/bin/env python3
\"\"\"
patch_signing.py
Patches android/app/build.gradle to read key.properties and use release signing.
Called by GitHub Actions before flutter build appbundle.
\"\"\"
from pathlib import Path
import re, sys

GRADLE = Path("android/app/build.gradle")
if not GRADLE.exists():
    print(f"ABORT: {GRADLE} not found")
    sys.exit(1)

src = GRADLE.read_text(encoding="utf-8")

# 1. Add keyProperties loader at top of android { block
KEY_LOADER = '''
    // S26: load signing config from key.properties
    def keyPropertiesFile = rootProject.file("key.properties")
    def keyProperties = new Properties()
    if (keyPropertiesFile.exists()) {
        keyProperties.load(new FileInputStream(keyPropertiesFile))
    }
'''

SIGNING_CONFIG = '''
    signingConfigs {
        release {
            keyAlias keyProperties['keyAlias']
            keyPassword keyProperties['keyPassword']
            storeFile keyProperties['storeFile'] ? file(keyProperties['storeFile']) : null
            storePassword keyProperties['storePassword']
        }
    }
'''

# Insert keyProperties loader + signingConfigs before buildTypes
if 'keyPropertiesFile' not in src:
    src = src.replace(
        '    buildTypes {',
        KEY_LOADER + SIGNING_CONFIG + '    buildTypes {',
        1
    )
    print("✓ signingConfigs added")
else:
    print("✓ signingConfigs already present")

# 2. Replace signingConfig in release buildType
if 'signingConfig signingConfigs.release' not in src:
    src = re.sub(
        r'(release\s*\{)',
        r'\1\n            signingConfig signingConfigs.release',
        src, count=1
    )
    print("✓ release buildType: signingConfig set")
else:
    print("✓ release signingConfig already set")

GRADLE.write_text(src, encoding="utf-8")
print(f"✓ {GRADLE} patched")
