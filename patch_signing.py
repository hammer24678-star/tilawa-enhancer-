#!/usr/bin/env python3
from pathlib import Path
import sys

GRADLE = Path("android/app/build.gradle")
if not GRADLE.exists():
    print(f"ABORT: {GRADLE} not found"); sys.exit(1)

src = GRADLE.read_text(encoding="utf-8")

# 1. Insert keystoreProperties loader BEFORE android { block
LOADER = '''
def keystoreProperties = new Properties()
def keystorePropertiesFile = rootProject.file('key.properties')
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(new FileInputStream(keystorePropertiesFile))
}

'''

if 'keystoreProperties' not in src:
    src = src.replace('android {', LOADER + 'android {', 1)
    print("keystoreProperties loader added")

# 2. Insert signingConfigs INSIDE android { before buildTypes
SIGNING = '''
    signingConfigs {
        release {
            keyAlias keystoreProperties['keyAlias']
            keyPassword keystoreProperties['keyPassword']
            storeFile keystoreProperties['storeFile'] ? file(keystoreProperties['storeFile']) : null
            storePassword keystoreProperties['storePassword']
        }
    }
'''

if 'signingConfigs' not in src:
    src = src.replace('    buildTypes {', SIGNING + '    buildTypes {', 1)
    print("signingConfigs block added")

# 3. Set signingConfig inside release buildType
if 'signingConfig signingConfigs.release' not in src:
    src = src.replace(
        'buildTypes {\n        release {',
        'buildTypes {\n        release {\n            signingConfig signingConfigs.release',
        1
    )
    # fallback pattern
    if 'signingConfig signingConfigs.release' not in src:
        import re
        src = re.sub(
            r'buildTypes\s*\{\s*release\s*\{',
            'buildTypes {\n        release {\n            signingConfig signingConfigs.release',
            src, count=1
        )
    print("release signingConfig set")

GRADLE.write_text(src, encoding="utf-8")
print("done")
