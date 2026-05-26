#!/bin/bash
# build_assets.sh — CI asset builder
set -e

ARCH="aarch64"
ALPINE_VER="3.18.9"
ASSETS="assets/alpine"
REF_ASSETS="assets/reference_audio"
DF_VERSION="0.5.6"

mkdir -p "$ASSETS" "$REF_ASSETS"

# ── 1. Dependencies ───────────────────────────────────────────────────────────
echo "==> Installing dependencies"
sudo apt-get install -y --no-install-recommends \
    qemu-user-static binfmt-support 2>&1 | tail -3
sudo update-binfmts --enable qemu-aarch64 2>/dev/null || true

# ── 2. Alpine minirootfs ──────────────────────────────────────────────────────
echo "==> Downloading Alpine $ALPINE_VER $ARCH"
curl -fsSL --retry 3 \
    "https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/$ARCH/alpine-minirootfs-$ALPINE_VER-$ARCH.tar.gz" \
    -o "$ASSETS/alpine-rootfs.tar.gz"
echo "    alpine-rootfs.tar.gz: $(du -sh $ASSETS/alpine-rootfs.tar.gz | cut -f1)"

# ── 3. Python env via chroot ──────────────────────────────────────────────────
echo "==> Building Python env (aarch64 chroot)"
ROOTFS=$(mktemp -d)
sudo tar -xzf "$ASSETS/alpine-rootfs.tar.gz" -C "$ROOTFS"
sudo cp "$(which qemu-aarch64-static)" "$ROOTFS/usr/bin/" 2>/dev/null || \
    sudo cp /usr/bin/qemu-aarch64-static "$ROOTFS/usr/bin/"
echo "nameserver 8.8.8.8" | sudo tee "$ROOTFS/etc/resolv.conf" >/dev/null

sudo chroot "$ROOTFS" /bin/sh << 'CHROOT'
apk update --no-progress
apk add --no-progress python3 py3-numpy py3-scipy ffmpeg
rm -rf /var/cache/apk/*
CHROOT

echo "    Python: $(sudo chroot $ROOTFS /usr/bin/python3 --version)"

sudo rm -f "$ROOTFS/usr/bin/qemu-aarch64-static"
echo "==> Packing python-env.tar.gz"
sudo tar -czf "$ASSETS/python-env.tar.gz" \
    --exclude="./proc" --exclude="./sys" --exclude="./dev" \
    -C "$ROOTFS" .
sudo rm -rf "$ROOTFS"
echo "    python-env.tar.gz: $(du -sh $ASSETS/python-env.tar.gz | cut -f1)"

# ── 4. DeepFilter binary ──────────────────────────────────────────────────────
echo "==> Downloading DeepFilter $DF_VERSION $ARCH"
# Try gnu first, fall back to musl
DF_URL="https://github.com/Rikorose/DeepFilterNet/releases/download/v${DF_VERSION}/deep-filter-${DF_VERSION//./_}-${ARCH}-unknown-linux-gnu"
curl -fsSL --retry 3 "$DF_URL" -o "$ASSETS/deep-filter" || \
    curl -fsSL --retry 3 \
        "https://github.com/Rikorose/DeepFilterNet/releases/download/v${DF_VERSION}/deep-filter-${DF_VERSION//./_}-${ARCH}-unknown-linux-musl" \
        -o "$ASSETS/deep-filter"
chmod +x "$ASSETS/deep-filter"
echo "    deep-filter: $(du -sh $ASSETS/deep-filter | cut -f1)"

# ── 5. Reference audio ────────────────────────────────────────────────────────
echo "==> Downloading reference audio"
for f in ref_araf_1425h.mp3 ref_fath_1425h.mp3 ref_fatir_1425h.mp3; do
    curl -fsSL --retry 3 \
        "https://carm5333-tilawa-server.hf.space/reference_audio/$f" \
        -o "$REF_ASSETS/$f" && \
        echo "    $f: $(du -sh $REF_ASSETS/$f | cut -f1)" || \
        echo "    WARNING: $f download failed"
done

echo ""
echo "=== Asset summary ==="
du -sh "$ASSETS"/* "$REF_ASSETS"/* 2>/dev/null
