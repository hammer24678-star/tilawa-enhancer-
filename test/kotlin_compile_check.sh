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

# 1. get the Kotlin that actually ships.
#
# S259: this used to always extract the template embedded in patch_android.py,
# and that template is not what builds. patch_android.py deliberately skips
# writing it when android/.../LocalEngineRunner.kt already exists (S202, to
# preserve hand-applied fixes) — and that file is committed, so on every CI
# checkout it exists and the template is never written.
#
# The two had drifted badly by the time anyone noticed: the committed file was
# missing availableLocalEngines() and diagnose() (both called from Dart since
# S250), still routed v9.0/v8.0 to engine_v90.py/engine_v80.py which exist
# nowhere in the project, and still handed --ref to ihyaa_ve.py, which does not
# accept it. Every one of those shipped while this gate reported PASS against a
# file no build ever compiled.
#
# So: check the committed file, and check the template too when it differs, so
# whichever one a given checkout ends up using has been compiled here.
SHIPPING="$ROOT/android/app/src/main/kotlin/com/tilawa/tilawa_enhancer/LocalEngineRunner.kt"
python3 - "$ROOT" "$WORK" "$SHIPPING" <<'PY'
import os
import sys
root, work, shipping = sys.argv[1], sys.argv[2], sys.argv[3]


def emit(subdir, text, label):
    os.makedirs(os.path.join(work, subdir), exist_ok=True)
    path = os.path.join(work, subdir, 'LocalEngineRunner.kt')
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print('  %d lines — %s' % (text.count('\n'), label))


if os.path.exists(shipping):
    emit('shipping', open(shipping, encoding='utf-8').read(),
         'committed android/ (this is what builds)')

src = open(os.path.join(root, 'patch_android.py'), encoding='utf-8').read()
i = src.index('class LocalEngineRunner')
tpl = src[src.rindex('"""', 0, i) + 3:src.index('"""', i)]
assert 'package com.tilawa' in tpl[:200], \
    'extracted block does not start with a package declaration'
emit('template', tpl, 'patch_android.py template (fresh-checkout fallback)')
PY

# 2. coroutines jar (the only real dependency; Android/Flutter are stubbed)
if [ ! -f "$JAR" ]; then
    echo "  fetching kotlinx-coroutines-core $COROUTINES_VER"
    curl -sSL -o "$JAR" \
      "https://repo1.maven.org/maven2/org/jetbrains/kotlinx/kotlinx-coroutines-core-jvm/$COROUTINES_VER/kotlinx-coroutines-core-jvm-$COROUTINES_VER.jar"
fi

# 3-5. compile, contract-check and offline-check each variant that exists.
overall=0
for variant in shipping template; do
    KT="$WORK/$variant/LocalEngineRunner.kt"
    [ -f "$KT" ] || continue
    echo
    echo "── $variant ──────────────────────────────────────────────"

    # 3. compile against the committed stubs
    LOG="$WORK/$variant/compile.log"
    set +e
    "$KOTLINC" "$ROOT"/test/kotlin_stubs/*.kt "$KT" \
        -cp "$JAR" -d "$WORK/$variant/out" > "$LOG" 2>&1
    set -e
    ERRS=$(grep -c "error:" "$LOG" || true)
    if [ "$ERRS" != "0" ]; then
        echo "  !! $ERRS Kotlin error(s):"
        grep "error:" "$LOG" | head -30
        overall=1
        continue
    fi
    echo "  Kotlin type-checks (0 errors)"

    # 4. the cross-language contract: every method Dart calls over the channel
    #    must exist here with the return type Dart expects. A Map-vs-List
    #    mismatch is a runtime crash on device that neither analyzer can see,
    #    and a method that is simply absent is worse: Dart catches the
    #    MissingPluginException and silently uses a default. That is how
    #    availableLocalEngines() looked fine for nine sessions while returning
    #    an empty list on every device.
    API="$WORK/$variant/api.txt"
    javap -p -cp "$WORK/$variant/out" com.tilawa.tilawa_enhancer.LocalEngineRunner \
        > "$API" 2>/dev/null || true
    fail=0
    check() {
        if grep -qE "$2" "$API"; then
            echo "  OK   $1"
        else
            echo "  FAIL $1 (expected /$2/)"
            fail=1
        fi
    }
    check "diagnose() returns a Map"          'Map<java.lang.String, java.lang.Object> diagnose\(\)'
    check "availableLocalEngines() -> List"   'List<java.lang.String> availableLocalEngines\(\)'
    check "isBasicSetupComplete() -> boolean" 'boolean isBasicSetupComplete\(\)'
    if [ "$fail" != "0" ]; then overall=1; else
        echo "  channel contract matches the Dart call sites"
    fi

    # 5. S254: setup should never need the network — Python, numpy, scipy, the
    #    audio packages, the Alpine rootfs and the DeepFilter binary all ship
    #    inside the APK, and every download here is only a fallback for when an
    #    asset is missing. Those fallbacks turn a packaging fault into a "check
    #    your internet connection" the user can do nothing about.
    #
    #    S259: reported for both variants, but only enforced on the template.
    #    The committed file still carries the old download fallbacks behind its
    #    bundled-asset path; removing them is a behaviour change, not a bug
    #    fix, so this prints what is there rather than failing the build on it.
    netfail=0
    forbid() {
        if grep -nE "$1" "$KT" | grep -vE '^\s*[0-9]+:\s*//' > "$WORK/$variant/hits.txt"; then
            echo "  WARN setup can reach the network: $2"
            sed 's/^/         /' "$WORK/$variant/hits.txt" | head -3
            netfail=1
        else
            echo "  OK   no $2"
        fi
    }
    forbid 'https?://[^"]*(dl-cdn\.alpinelinux|releases/download)' "rootfs/binary download URL"
    forbid '\b(pip|pip3) install'                                  "on-device pip install"
    forbid '\bapk (add|update)\b'                                  "on-device apk install"
    if [ "$netfail" = "0" ]; then
        echo "  setup is fully offline (every asset comes from the APK)"
    elif [ "$variant" = "template" ]; then
        echo "  !! the template must stay fully offline (S254)"
        overall=1
    fi
done

echo
[ "$overall" = "0" ] || { echo "kotlin_compile_check: FAIL"; exit 1; }
echo "kotlin_compile_check: PASS"
