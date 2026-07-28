#!/bin/bash
# build_assets.sh — CI asset builder (S82: Docker-based, reliable in GH Actions)
set -euo pipefail

ARCH="aarch64"
ALPINE_VER="3.21.3"  # S229: was 3.18.9 — the CI workflow (build.yml) separately
                     # rebuilds python-env.tar.gz from alpine:3.21 and overwrites
                     # this script's output, so a 3.18 rootfs + a 3.21 ffmpeg/numpy
                     # bundle were shipping together — different musl/libav ABI —
                     # causing "Error relocating ffmpeg: ...: symbol not found" on
                     # every Split/Merge/Export/Preview. Must match LocalEngineRunner
                     # .kt's ALPINE_VER and its download-fallback URL (both 3.21.3).
ASSETS="assets/alpine"
REF_ASSETS="assets/reference_audio"
DF_VERSION="0.5.6"

mkdir -p "$ASSETS" "$REF_ASSETS"

# ── 1. Alpine minirootfs (raw tarball — extracted on device) ──────────────────
echo "==> Downloading Alpine $ALPINE_VER $ARCH"
curl -fsSL --retry 3 \
    "https://dl-cdn.alpinelinux.org/alpine/v3.21/releases/$ARCH/alpine-minirootfs-$ALPINE_VER-$ARCH.tar.gz" \
    -o "$ASSETS/alpine-rootfs.tar.gz"
echo "    alpine-rootfs.tar.gz: $(du -sh $ASSETS/alpine-rootfs.tar.gz | cut -f1)"

# ── 2. Python env via Docker (arm64 — reliable in GH Actions) ─────────────────
echo "==> Setting up QEMU for arm64 Docker"
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

echo "==> Building Python env inside arm64 Alpine Docker"
# ── S250 FIX: the S247/S248 offline install NEVER WORKED ──────────────────────
# The previous command was:
#   pip install --no-index --find-links=/pip_wheels noisereduce nara_wpe pystoi
#       pyloudnorm webrtcvad soundfile soxr audioread decorator joblib
#       lazy_loader pooch tqdm msgpack librosa   2>&1 | tail -30
# It fails, every run, for three independent reasons — and because it is piped
# into `tail` inside a `sh -c` with no `set -e`, the pipeline's exit status is
# tail's (0), so the failure was swallowed and a python-env.tar.gz containing
# NONE of the packages shipped as if all was well. That is why the S248 Cleanup
# and Quality tabs did nothing on-device: noisereduce/webrtcvad/pystoi were
# never actually installed.
#   1. 12 of the 15 entries are sdists, and building an sdist needs the PEP 517
#      backend (setuptools / poetry-core / scikit-build-core / Cython) in an
#      isolated build env that pip fetches from an index — which --no-index
#      forbids. It dies at "Could not find a version that satisfies the
#      requirement setuptools".
#   2. The wheels' own runtime dependencies were never vendored: cffi +
#      pycparser (soundfile), click (nara_wpe), packaging (lazy_loader),
#      platformdirs + requests (pooch), typing_extensions. Resolution fails
#      even if the build backends were present.
#   3. librosa hard-imports numba → llvmlite, which publishes no musl/aarch64
#      wheel at all, so it could only be satisfied by compiling LLVM under
#      QEMU on every CI run — the precise trap S240 had to undo for
#      DeepFilter. librosa is therefore dropped; tilawa_dsp_studio.py now
#      implements HPSS, F0 tracking, spectral centroid and onset detection
#      natively in numpy/scipy (faster on-device too: no numba JIT warm-up).
#
# The fix: install the 14 remaining packages *with* the network CI already has,
# from pinned versions, preferring the committed pip_wheels copies, with the
# transitive closure listed explicitly (--no-deps) so pip can never quietly
# replace the apk-provided numpy/scipy with a different build. Then VERIFY by
# importing all 14 and failing the build if any is missing — this class of
# silent shipping failure must not be possible again.
docker run --rm \
    --platform linux/arm64 \
    --volume "$PWD/$ASSETS:/out" \
    --volume "$PWD/pip_wheels:/pip_wheels:ro" \
    --volume "$PWD/test/env_closure_check.py:/closure_check.py:ro" \
    alpine:3.21 \
    sh -eu -c "
        apk update --no-progress 2>&1 | tail -2
        # libgcc/libstdc++ are named explicitly so the 'apk del build-base'
        # below cannot take them with it — the compiled C extensions link them.
        # Required — a missing name here must fail the build (sh -e).
        apk add --no-progress python3 py3-pip py3-numpy py3-scipy ffmpeg \
            build-base python3-dev libsndfile libsndfile-dev \
            libgcc libstdc++ 2>&1 | tail -5
        # Optional build accelerators: soxr's scikit-build-core backend prefers
        # cmake+ninja but falls back to make from build-base, and pip can fetch
        # musl/aarch64 cmake+ninja wheels itself — so never fail on these.
        apk add --no-progress cmake samurai 2>&1 | tail -2 || \
            echo '    (cmake/samurai unavailable — pip will supply them)'
        # S250e: belt-and-braces for the exact runtime libs the committed
        # python-env.tar.gz turned out to be missing (verified under
        # qemu-aarch64): openblas backs numpy's _multiarray_umath, and
        # libdrm/libxcb back ffmpeg's libavdevice. They SHOULD already arrive
        # as dependencies of py3-numpy and ffmpeg — naming them explicitly also
        # marks them world-installed so no later 'apk del' can reclaim them.
        # Kept in the non-fatal group: if a name is wrong on some future Alpine
        # this must not fail the build, and the tarball gate below is the real
        # check either way.
        apk add --no-progress openblas libdrm libxcb 2>&1 | tail -2 || \
            echo '    (openblas/libdrm/libxcb not added explicitly — relying on deps)'

        # ── S252: this step died on every run since S250 ─────────────────────
        # soxr 1.1.0 and webrtcvad 2.0.10 publish no musllinux/aarch64 wheel, so
        # pip compiles both from their sdist — and that compile runs under
        # qemu-user emulation, where g++ died:
        #
        #   ninja: job terminated due to signal 11: /usr/bin/g++ ... -O3 ...
        #          nanobind/src/nb_func.cpp
        #
        # nb_func.cpp is nanobind's heaviest translation unit, and ninja was
        # compiling several like it at once (the log reaches [23/30] before the
        # segfault). Under qemu-user the C++ frontend runs out of stack on it.
        # Two settings remove that without touching any DSP hot path: compile
        # one translation unit at a time, and give the frontend a real stack.
        # libsoxr's resampler is C and keeps its own optimisation either way.
        export CMAKE_BUILD_PARALLEL_LEVEL=1
        export MAKEFLAGS=-j1
        ulimit -s 65536 2>/dev/null || true

        # Everything that ships a usable wheel goes first, so a compiler crash
        # can never take the pure-Python packages down with it.
        # --no-deps + explicit closure: nothing here may pull in a second numpy.
        # Status is checked explicitly — piping into tail would hide a failure
        # behind tail's exit code, which is how the S247 breakage went unnoticed.
        echo '==> Installing the 12 wheel-provided packages (S250)'
        if pip install --no-cache-dir --break-system-packages --prefer-binary \\
            --find-links=/pip_wheels --no-deps \\
            'nara_wpe==0.0.11' 'noisereduce==3.0.3' 'pystoi==0.4.1' \\
            'pyloudnorm==0.2.0' 'soundfile==0.14.0' \\
            'audioread==3.1.0' 'joblib==1.5.3' \\
            'decorator==5.3.1' 'tqdm==4.69.0' 'msgpack==1.2.1' \\
            'pooch==1.9.0' 'lazy_loader==0.5' \\
            cffi pycparser typing_extensions click packaging platformdirs \\
            requests urllib3 idna certifi charset-normalizer \\
            > /pip-install.log 2>&1; then
            tail -8 /pip-install.log
        else
            echo '    !! pip install FAILED — full log follows'
            cat /pip-install.log
            exit 1
        fi

        # The two that must be compiled, one at a time so the log names the
        # package that failed. S250 dumped only the last 60 lines of a combined
        # log, which is why webrtcvad's error was never visible at all — the
        # tail was entirely soxr's CMake output.
        echo '==> Compiling soxr (no musl/aarch64 wheel exists)'
        if pip install --no-cache-dir --break-system-packages \\
            --find-links=/pip_wheels --no-deps 'soxr==1.1.0' \\
            > /pip-soxr.log 2>&1; then
            tail -3 /pip-soxr.log
        else
            echo '    first attempt failed; retrying at -O1 for C++ only'
            # Last resort if a future nanobind gets heavier again: -O1 cuts the
            # frontend's stack depth and memory hard. -DNDEBUG is carried over
            # because overriding the Release flags drops CMake's own copy.
            export SKBUILD_CMAKE_ARGS='-DCMAKE_CXX_FLAGS_RELEASE=-O1 -DNDEBUG'
            export CMAKE_ARGS='-DCMAKE_CXX_FLAGS_RELEASE=-O1'
            if pip install --no-cache-dir --break-system-packages \\
                --find-links=/pip_wheels --no-deps 'soxr==1.1.0' \\
                > /pip-soxr2.log 2>&1; then
                tail -3 /pip-soxr2.log
            else
                echo '    !! soxr FAILED both attempts — full logs follow'
                echo '    ---- attempt 1 ----'; cat /pip-soxr.log
                echo '    ---- attempt 2 (-O1) ----'; cat /pip-soxr2.log
                exit 1
            fi
            unset SKBUILD_CMAKE_ARGS CMAKE_ARGS
        fi

        echo '==> Compiling webrtcvad (no musl/aarch64 wheel exists)'
        if pip install --no-cache-dir --break-system-packages \\
            --find-links=/pip_wheels --no-deps 'webrtcvad==2.0.10' \\
            > /pip-vad.log 2>&1; then
            tail -3 /pip-vad.log
        else
            echo '    !! webrtcvad FAILED — full log follows'
            cat /pip-vad.log
            exit 1
        fi

        echo '==> Verifying every package imports (build fails if not)'
        python3 - <<'PYEOF'
import importlib, sys
mods = ['nara_wpe', 'noisereduce', 'pystoi', 'pyloudnorm', 'webrtcvad',
        'soundfile', 'soxr', 'audioread', 'joblib', 'decorator', 'tqdm',
        'msgpack', 'pooch', 'lazy_loader']
bad = []
for m in mods:
    try:
        mod = importlib.import_module(m)
        print('  OK   %-12s %s' % (m, getattr(mod, '__version__', '')))
    except Exception as e:
        print('  FAIL %-12s %s: %s' % (m, type(e).__name__, e))
        bad.append(m)
# the two that need a working C extension AND real data
import numpy as np
from nara_wpe.wpe import wpe_v8
from nara_wpe.utils import stft
Y = stft(np.random.randn(2, 16000) * 0.05, size=512, shift=128).transpose(2, 0, 1)
assert wpe_v8(Y, taps=8, delay=2, iterations=1).shape == Y.shape
import webrtcvad
assert webrtcvad.Vad(2).is_speech(b'\\x00\\x00' * 480, 16000) in (True, False)
import soxr
assert len(soxr.resample(np.zeros(1000, dtype='float32'), 16000, 8000)) == 500
import soundfile as sf
assert 'PCM_24' in sf.available_subtypes('WAV')
print('  smoke tests passed (nara_wpe, webrtcvad, soxr, soundfile)')
if bad:
    sys.exit('MISSING PACKAGES: %s' % ', '.join(bad))
PYEOF

        # Shrink the shipped rootfs: the toolchain was only needed to build the
        # C extensions above and is dead weight on the device (~180 MB).
        echo '==> Removing build toolchain from the shipped rootfs'
        apk del --no-progress build-base python3-dev libsndfile-dev 2>&1 | tail -3 || true
        apk del --no-progress cmake samurai 2>&1 | tail -1 || true
        rm -rf /var/cache/apk/* /root/.cache /tmp/* /pip-*.log 2>/dev/null || true
        find / -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true

        echo '==> Re-verifying after toolchain removal'
        python3 -c \"
import importlib
for m in ['nara_wpe','noisereduce','pystoi','pyloudnorm','webrtcvad','soundfile','soxr','audioread','joblib','decorator','tqdm','msgpack','pooch','lazy_loader','numpy','scipy']:
    importlib.import_module(m)
print('  all 14 packages + numpy/scipy still import after apk del')\"

        echo 'Python: '\$(python3 --version)
        ffmpeg -version 2>&1 | head -1 || echo 'ffmpeg MISSING'
        tar -czf /out/python-env.tar.gz \
            --exclude=./proc --exclude=./sys --exclude=./dev \
            --exclude=./out \
            -C / .

        # ── S250e: VERIFY THE TARBALL, NOT THE CONTAINER ────────────────────
        # Everything above proves the packages work *in this container*. The
        # device runs whatever came out of `tar`, and those are not the same
        # thing: the python-env.tar.gz committed before S250e passed every
        # in-container check and was still unusable on-device --
        #   * /usr/lib/libopenblas.so.3 was a DANGLING SYMLINK (its target,
        #     libopenblas_armv8p-r0.3.30.so, was simply not in the archive), so
        #     import numpy died with: Error loading shared library
        #     libopenblas.so.3 -- and every numpy engine with it;
        #   * ffmpeg could not start either -- libavdevice needs libdrm.so.2,
        #     libxcb.so.1 and libxcb-shm.so.0, none of which were archived.
        # Both were confirmed by extracting that committed tarball and running
        # it under qemu-aarch64. So: unpack what we just produced into a clean
        # prefix and exercise it there. A check that never runs the shipped
        # artifact cannot catch this class of failure.
        echo '==> Verifying the produced tarball (not just the container)'
        rm -rf /verify && mkdir -p /verify
        tar xzf /out/python-env.tar.gz -C /verify
        BAD=\$(find /verify -type l ! -exec test -e {} \; -print 2>/dev/null | head -20)
        if [ -n \"\$BAD\" ]; then
            echo '    !! dangling symlinks in the archive:'
            echo \"\$BAD\"
            exit 1
        fi
        echo '    no dangling symlinks'
        # S250k: the STRONGEST check — resolve the shared-library closure. Walk
        # every ELF in the archive, read its DT_NEEDED entries and confirm each
        # named library is present, exactly as the dynamic linker will at
        # startup. The tarball committed before S250k fails this with 63 missing
        # libraries: libgcc_s/libstdc++ (numpy's _multiarray_umath links both,
        # so numpy could not import), libbz2/libffi/liblzma/libsqlite3/libexpat
        # (Python's own stdlib extensions), and ~45 codec libs including
        # libmp3lame and libsoxr (so libavcodec could not load and ffmpeg was
        # dead). That single check explains every 'nothing works' symptom, and
        # no exists()-based test could ever have caught it.
        cp /closure_check.py /verify_closure.py 2>/dev/null || true
        if [ -f /closure_check.py ]; then
            python3 /closure_check.py /verify || {
                echo '    !! the archive cannot load its own binaries'; exit 1; }
        else
            echo '    (closure checker not mounted — skipped)'
        fi
        export LD_LIBRARY_PATH=/verify/usr/lib:/verify/lib
        /verify/usr/bin/python3 - <<'VEOF' || { echo '    !! numpy/scipy unusable from the archive'; exit 1; }
import numpy, scipy, numpy as np
from scipy import signal
b, a = signal.butter(4, 0.2)
assert np.isfinite(signal.lfilter(b, a, np.random.randn(4096))).all()
print('    extracted numpy %s + scipy %s work' % (numpy.__version__, scipy.__version__))
VEOF
        /verify/usr/bin/ffmpeg -hide_banner -f lavfi \
            -i anullsrc=r=44100:cl=stereo -t 1 -f wav /verify/t.wav -y \
            >/dev/null 2>&1 \
            || { echo '    !! ffmpeg from the archive cannot encode'; exit 1; }
        echo '    extracted ffmpeg encodes'
        /verify/usr/bin/python3 - <<'VEOF2' || exit 1
import importlib.util, sys
mods = ['nara_wpe','noisereduce','pystoi','pyloudnorm','webrtcvad','soundfile',
        'soxr','audioread','joblib','decorator','tqdm','msgpack','pooch','lazy_loader']
bad = [m for m in mods if importlib.util.find_spec(m) is None]
print('    extracted audio packages: %d/%d' % (len(mods) - len(bad), len(mods)))
if bad:
    sys.exit('    !! missing from archive: %s' % ', '.join(bad))
VEOF2
        unset LD_LIBRARY_PATH
        rm -rf /verify
        echo 'python-env.tar.gz done (verified)'
    "
echo "    python-env.tar.gz: $(du -sh $ASSETS/python-env.tar.gz | cut -f1)"
echo "    pip_wheels cache: $(du -sh pip_wheels 2>/dev/null | cut -f1) (14 packages, S250-verified)"

# ── 3. DeepFilter — use the committed binary; download only if missing ────────
# S240 FIX (v2): the original `cargo install deep_filter` inside QEMU arm64
# Docker compiled a large Rust ML project under CPU emulation — multiple hours,
# and it killed the S239 CI runs twice. It was also pointless: a working 39 MB
# aarch64 deep-filter binary is ALREADY COMMITTED at assets/alpine/deep-filter
# (the same one every previous release shipped) and the cargo build just
# overwrote it. Use it. If it's ever missing, fall back to upstream's release
# binary — NOTE: v0.5.6 publishes NO aarch64-musl asset (the old
# deep-filter-0_5_6-aarch64-unknown-linux-musl URL 404s and always has); the
# real asset is dot-versioned aarch64-unknown-linux-gnu, which matches the
# interpreter of the committed binary.
echo "==> DeepFilter binary"
if [ -f "$ASSETS/deep-filter" ] && [ "$(stat -c%s "$ASSETS/deep-filter")" -gt 1000000 ]; then
    echo "    using committed deep-filter"
else
    DF_URL="https://github.com/Rikorose/DeepFilterNet/releases/download/v${DF_VERSION}/deep-filter-${DF_VERSION}-aarch64-unknown-linux-gnu"
    echo "    committed binary missing — downloading $DF_URL"
    curl -fsSL --retry 3 "$DF_URL" -o "$ASSETS/deep-filter"
fi
chmod +x "$ASSETS/deep-filter"
# Same ELF-arch guard the app applies on-device (bytes 18-19: aarch64 = b7 00).
# od (coreutils) instead of xxd — always present.
ARCH_BYTES=$(od -An -tx1 -j18 -N2 "$ASSETS/deep-filter" | tr -d ' \n')
if [ "$ARCH_BYTES" != "b700" ]; then
    echo "ERROR: deep-filter is not aarch64 (e_machine=$ARCH_BYTES)"; exit 1
fi
echo "    deep-filter: $(du -sh $ASSETS/deep-filter | cut -f1) (aarch64 ✓)"

# ── 4. Reference audio ────────────────────────────────────────────────────────
echo "==> Downloading reference audio"
for f in ref_araf_1425h.mp3 ref_fath_1425h.mp3 ref_fatir_1425h.mp3; do
    if curl -fsSL --retry 3 \
        "https://carm5333-tilawa-server.hf.space/reference_audio/$f" \
        -o "$REF_ASSETS/$f"; then
        echo "    $f: $(du -sh $REF_ASSETS/$f | cut -f1)"
    else
        echo "    WARNING: $f download failed (non-fatal)"
    fi
done

# ── Summary ────────────────────────────────────────────────────────────────────
echo ""
echo "=== Asset summary ==="
du -sh "$ASSETS"/* "$REF_ASSETS"/* 2>/dev/null || true
echo "=== build_assets.sh DONE ==="
