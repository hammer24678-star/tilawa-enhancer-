#!/usr/bin/env bash
# kotlin_compile_check.sh — S250j: type-check the generated LocalEngineRunner.kt.
#
# patch_android.py emits ~960 lines of Kotlin as a string literal, and nothing
# in this repo ever compiled it. Every Kotlin change was therefore verified only
# by reading, and a single typo means a failed CI build discovered ~40 minutes
# in — after the Alpine/Python asset stage. This gate takes seconds and runs
# first.
#
# It found nothing on introduction (0 errors), but it does check things reading
# cannot: that the Kotlin type-checks at all, and that the channel methods the
# Dart side calls have the return types Dart expects — diagnose() must be a
# Map, availableLocalEngines() a List<String>.
#
# Usage:  bash test/kotlin_compile_check.sh
# Needs:  kotlinc on PATH (or KOTLINC=/path/to/kotlinc), JDK 17+, network once
#         for the coroutines jar (cached in .kotlin_check/).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORK="$ROOT/.kotlin_check"
KOTLINC="${KOTLINC:-$(command -v kotlinc || true)}"
COROUTINES_VER="1.8.1"
JAR="$WORK/kotlinx-coroutines-core-jvm-$COROUTINES_VER.jar"

if [ -z "$KOTLINC" ]; then
    echo "SKIP: kotlinc not found (set KOTLINC=/path/to/kotlinc)"
    exit 0
fi
mkdir -p "$WORK"

# 1. extract the Kotlin exactly as patch_android.py will write it
python3 - "$ROOT" "$WORK" <<'PY'
import sys
root, work = sys.argv[1], sys.argv[2]
src = open(f'{root}/patch_android.py', encoding='utf-8').read()
i = src.index('class LocalEngineRunner')
start = src.rindex('"""', 0, i) + 3
end = src.index('"""', i)
kt = src[start:end]
assert 'package com.tilawa' in kt.split('\n')[1] or 'package com.tilawa' in kt[:200], \
    'extracted block does not start with a package declaration'
open(f'{work}/LocalEngineRunner.kt', 'w', encoding='utf-8').write(kt)
print(f'  extracted {kt.count(chr(10))} lines of Kotlin')
PY

# 2. coroutines jar (the only real dependency; Android/Flutter are stubbed)
if [ ! -f "$JAR" ]; then
    echo "  fetching kotlinx-coroutines-core $COROUTINES_VER"
    curl -sSL -o "$JAR" \
      "https://repo1.maven.org/maven2/org/jetbrains/kotlinx/kotlinx-coroutines-core-jvm/$COROUTINES_VER/kotlinx-coroutines-core-jvm-$COROUTINES_VER.jar"
fi

# 3. compile against the committed stubs
echo "  compiling..."
LOG="$WORK/compile.log"
set +e
"$KOTLINC" "$ROOT"/test/kotlin_stubs/*.kt "$WORK/LocalEngineRunner.kt" \
    -cp "$JAR" -d "$WORK/out" > "$LOG" 2>&1
set -e
ERRS=$(grep -c "error:" "$LOG" || true)
if [ "$ERRS" != "0" ]; then
    echo "  !! $ERRS Kotlin error(s):"
    grep "error:" "$LOG" | head -30
    exit 1
fi
echo "  Kotlin type-checks (0 errors)"

# 4. the cross-language contract: Dart's invokeMethod calls must match the
#    Kotlin signatures. A Map<String,Object> vs List mismatch here is a
#    runtime crash on device that neither analyzer can see.
javap -p -cp "$WORK/out" com.tilawa.tilawa_enhancer.LocalEngineRunner \
    > "$WORK/api.txt" 2>/dev/null || true
fail=0
check() {
    if grep -qE "$2" "$WORK/api.txt"; then
        echo "  OK   $1"
    else
        echo "  FAIL $1 (expected /$2/)"
        fail=1
    fi
}
check "diagnose() returns a Map"          'Map<java.lang.String, java.lang.Object> diagnose\(\)'
check "availableLocalEngines() -> List"   'List<java.lang.String> availableLocalEngines\(\)'
check "isBasicSetupComplete() -> boolean" 'boolean isBasicSetupComplete\(\)'
check "ffmpegWorks() -> boolean"          'boolean ffmpegWorks\(\)'
check "numpyImports() -> boolean"         'boolean numpyImports\(\)'
[ "$fail" = "0" ] || exit 1
echo "  channel contract matches the Dart call sites"

# 5. S254: setup must never reach the network. Python, numpy, scipy, the audio
#    packages, the Alpine rootfs and the DeepFilter binary all ship inside the
#    APK. Every download fallback that used to sit here was unreachable in
#    practice — the Alpine CDN and a GitHub Release are no use to an offline
#    app, pip is not in the bundle to begin with, and the DeepFilter URL was a
#    permanent 404 — but each one turned a packaging fault into a "check your
#    internet connection" the user could do nothing about. They are gone; this
#    keeps them gone.
KT="$WORK/LocalEngineRunner.kt"
netfail=0
forbid() {
    if grep -nE "$1" "$KT" | grep -vE '^\s*[0-9]+:\s*//' > "$WORK/hits.txt"; then
        echo "  FAIL setup reaches the network: $2"
        sed 's/^/         /' "$WORK/hits.txt" | head -5
        netfail=1
    else
        echo "  OK   no $2"
    fi
}
forbid 'https?://[^"]*(dl-cdn\.alpinelinux|releases/download)' "rootfs/binary download URL"
forbid '\b(pip|pip3) install'                                  "on-device pip install"
forbid '\bapk (add|update)\b'                                  "on-device apk install"
[ "$netfail" = "0" ] || exit 1
echo "  setup is fully offline (every asset comes from the APK)"
echo "kotlin_compile_check: PASS"
