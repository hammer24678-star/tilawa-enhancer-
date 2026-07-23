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
docker run --rm \
    --platform linux/arm64 \
    --volume "$PWD/$ASSETS:/out" \
    --volume "$PWD/pip_wheels:/pip_wheels:ro" \
    alpine:3.21 \
    sh -c "
        apk update --no-progress 2>&1 | tail -2
        apk add --no-progress python3 py3-pip py3-numpy py3-scipy ffmpeg \
            build-base python3-dev libsndfile 2>&1 | tail -5
        echo '==> Installing embedded audio-editor packages (offline, S247)'
        pip install --quiet --no-cache-dir --break-system-packages \
            --no-index --find-links=/pip_wheels \
            noisereduce nara_wpe pystoi pyloudnorm webrtcvad soundfile soxr audioread decorator joblib lazy_loader pooch tqdm msgpack librosa 2>&1 | tail -30
        rm -rf /var/cache/apk/*
        echo 'Python: '$(python3 --version)
        echo 'ffmpeg: '$(which ffmpeg 2>/dev/null && ffmpeg -version 2>&1 | head -1 || echo 'checking inside tar...')
        tar -czf /out/python-env.tar.gz \
            --exclude=./proc --exclude=./sys --exclude=./dev \
            --exclude=./out \
            -C / .
        echo 'python-env.tar.gz done'
    "
echo "    python-env.tar.gz: $(du -sh $ASSETS/python-env.tar.gz | cut -f1)"
echo "    embedded pip_wheels: $(du -sh pip_wheels 2>/dev/null | cut -f1) (S247: noisereduce, nara_wpe, pystoi, pyloudnorm, webrtcvad + deps)"

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
