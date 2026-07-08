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
    alpine:3.21 \
    sh -c "
        apk update --no-progress 2>&1 | tail -2
        apk add --no-progress python3 py3-pip py3-numpy py3-scipy ffmpeg 2>&1 | tail -5
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

# ── 3. DeepFilter — build inside arm64 Alpine Docker (same as Python env) ──
echo "==> Building deep-filter for aarch64 inside arm64 Docker"
docker run --rm --platform linux/arm64 \
    --volume "$PWD/$ASSETS:/out" \
    alpine:3.21 sh -c "
        apk add --no-progress rust cargo musl-dev 2>&1 | tail -3
        cargo install deep_filter --root /tmp/df 2>&1 | tail -3
        cp /tmp/df/bin/deep_filter /out/deep-filter
        chmod +x /out/deep-filter
        echo done
    "
echo "    deep-filter: $(du -sh $ASSETS/deep-filter 2>/dev/null | cut -f1 || echo FAILED)"

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
