#!/bin/bash
# build_assets.sh — runs in GitHub Actions BEFORE flutter build apk
# Builds Alpine + Python env tarballs and places them in assets/
# CI runner is x86_64 Ubuntu; phone is aarch64 → use QEMU for aarch64 chroot

set -e
ARCH="aarch64"
ALPINE_VER="3.18.9"
ASSETS="assets/alpine"
REF_ASSETS="assets/reference_audio"
DF_VERSION="0.5.6"
DF_VER_UNDERSCORE="0_5.6"

mkdir -p "$ASSETS" "$REF_ASSETS"

echo "::group::Setup QEMU + dependencies"
sudo apt-get install -y qemu-user-static binfmt-support tar gzip curl 2>/dev/null
sudo update-binfmts --enable qemu-aarch64 2>/dev/null || true
echo "::endgroup::"

# ── 1. Alpine minirootfs ──────────────────────────────────────────────────────
echo "::group::Download Alpine $ALPINE_VER aarch64"
ALPINE_URL="https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/$ARCH/alpine-minirootfs-$ALPINE_VER-$ARCH.tar.gz"
curl -L -o "$ASSETS/alpine-rootfs.tar.gz" "$ALPINE_URL"
echo "Alpine rootfs: $(du -sh $ASSETS/alpine-rootfs.tar.gz | cut -f1)"
echo "::endgroup::"

# ── 2. Python + scipy + ffmpeg env ───────────────────────────────────────────
echo "::group::Build Python env (aarch64 chroot)"
ROOTFS=$(mktemp -d)
tar -xzf "$ASSETS/alpine-rootfs.tar.gz" -C "$ROOTFS"

# Copy qemu binary into rootfs for binfmt
cp /usr/bin/qemu-aarch64-static "$ROOTFS/usr/bin/" 2>/dev/null || true

# DNS
echo "nameserver 8.8.8.8" > "$ROOTFS/etc/resolv.conf"

# Install packages
sudo chroot "$ROOTFS" /bin/sh -c "
  apk update --no-progress 2>&1
  apk add --no-progress python3 py3-numpy py3-scipy ffmpeg 2>&1
  rm -rf /var/cache/apk/*
"

# Pack only the overlay (exclude base dirs that are in alpine-rootfs already)
# We pack the whole rootfs as python-env — on device we extract over alpine-rootfs
echo "Packing python-env.tar.gz…"
tar -czf "$ASSETS/python-env.tar.gz" \
    --exclude="./proc" --exclude="./sys" --exclude="./dev" \
    --exclude="./usr/bin/qemu-aarch64-static" \
    -C "$ROOTFS" .

sudo rm -rf "$ROOTFS"
echo "Python env: $(du -sh $ASSETS/python-env.tar.gz | cut -f1)"
echo "::endgroup::"

# ── 3. DeepFilter aarch64 binary ─────────────────────────────────────────────
echo "::group::Download DeepFilter $DF_VERSION aarch64"
DF_URL="https://github.com/Rikorose/DeepFilterNet/releases/download/v$DF_VERSION/deep-filter-$DF_VER_UNDERSCORE-$ARCH-unknown-linux-musl"
curl -L -o "$ASSETS/deep-filter" "$DF_URL"
chmod +x "$ASSETS/deep-filter"
echo "DeepFilter: $(du -sh $ASSETS/deep-filter | cut -f1)"
echo "::endgroup::"

# ── 4. Reference audio from HF server ────────────────────────────────────────
echo "::group::Download reference audio"
BASE="https://carm5333-tilawa-server.hf.space/reference_audio"
for f in ref_araf_1425h.mp3 ref_fath_1425h.mp3 ref_fatir_1425h.mp3; do
    curl -L -o "$REF_ASSETS/$f" "$BASE/$f" && echo "  OK $f" || echo "  SKIP $f"
done
echo "::endgroup::"

echo ""
echo "Assets ready:"
du -sh assets/alpine/* assets/reference_audio/* 2>/dev/null
