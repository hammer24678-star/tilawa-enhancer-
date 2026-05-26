#!/bin/bash
# build_assets.sh — runs in GitHub Actions BEFORE flutter build apk
set -eo pipefail

ARCH="aarch64"
ALPINE_VER="3.18.9"
ASSETS="assets/alpine"
REF_ASSETS="assets/reference_audio"
DF_VERSION="0.5.6"
DF_VER_UNDERSCORE="0_5.6"

mkdir -p "$ASSETS" "$REF_ASSETS"

echo "::group::Setup QEMU + dependencies"
sudo apt-get update -qq
sudo apt-get install -y qemu-user-static binfmt-support tar gzip curl
sudo update-binfmts --enable qemu-aarch64 2>/dev/null || true
echo "::endgroup::"

# ── 1. Alpine minirootfs ──────────────────────────────────────────────────────
echo "::group::Download Alpine $ALPINE_VER aarch64"
ALPINE_URL="https://dl-cdn.alpinelinux.org/alpine/v3.18/releases/$ARCH/alpine-minirootfs-$ALPINE_VER-$ARCH.tar.gz"
curl -fL --retry 3 --retry-delay 5 -o "$ASSETS/alpine-rootfs.tar.gz" "$ALPINE_URL"
ACTUAL=$(du -sb "$ASSETS/alpine-rootfs.tar.gz" | cut -f1)
echo "Alpine rootfs: $(du -sh $ASSETS/alpine-rootfs.tar.gz | cut -f1) ($ACTUAL bytes)"
[ "$ACTUAL" -gt 2000000 ] || { echo "ERROR: Alpine rootfs too small ($ACTUAL bytes)"; exit 1; }
echo "::endgroup::"

# ── 2. Python + scipy + ffmpeg env ───────────────────────────────────────────
echo "::group::Build Python env (aarch64 chroot)"
ROOTFS=$(mktemp -d)
tar -xzf "$ASSETS/alpine-rootfs.tar.gz" -C "$ROOTFS"

# Copy qemu binary for aarch64 emulation
sudo cp /usr/bin/qemu-aarch64-static "$ROOTFS/usr/bin/" 2>/dev/null || true

# DNS
echo "nameserver 8.8.8.8" | sudo tee "$ROOTFS/etc/resolv.conf" > /dev/null

# Mount proc/sys/dev
sudo mount --bind /proc "$ROOTFS/proc" 2>/dev/null || true
sudo mount --bind /sys  "$ROOTFS/sys"  2>/dev/null || true
sudo mount --bind /dev  "$ROOTFS/dev"  2>/dev/null || true

# Install packages
sudo chroot "$ROOTFS" /bin/sh -c "
  apk update --no-progress 2>&1 && \
  apk add --no-progress python3 py3-numpy py3-scipy ffmpeg 2>&1 && \
  rm -rf /var/cache/apk/*
" || { echo "ERROR: apk install failed"; sudo umount "$ROOTFS/proc" "$ROOTFS/sys" "$ROOTFS/dev" 2>/dev/null; exit 1; }

# Verify Python installed
sudo chroot "$ROOTFS" /usr/bin/python3 --version || { echo "ERROR: python3 not found after install"; exit 1; }

# Unmount
sudo umount "$ROOTFS/proc" "$ROOTFS/sys" "$ROOTFS/dev" 2>/dev/null || true

# Remove qemu binary from rootfs before packing
sudo rm -f "$ROOTFS/usr/bin/qemu-aarch64-static"

echo "Packing python-env.tar.gz…"
sudo tar -czf "$ASSETS/python-env.tar.gz" \
    --exclude="./proc" --exclude="./sys" --exclude="./dev" \
    -C "$ROOTFS" .

sudo rm -rf "$ROOTFS"
ACTUAL=$(du -sb "$ASSETS/python-env.tar.gz" | cut -f1)
echo "Python env: $(du -sh $ASSETS/python-env.tar.gz | cut -f1) ($ACTUAL bytes)"
[ "$ACTUAL" -gt 50000000 ] || { echo "ERROR: python-env too small ($ACTUAL bytes) — install likely failed"; exit 1; }
echo "::endgroup::"

# ── 3. DeepFilter aarch64 binary ─────────────────────────────────────────────
echo "::group::Download DeepFilter $DF_VERSION aarch64"
DF_URL="https://github.com/Rikorose/DeepFilterNet/releases/download/v$DF_VERSION/deep-filter-$DF_VER_UNDERSCORE-$ARCH-unknown-linux-gnu"
curl -fL --retry 3 --retry-delay 5 -o "$ASSETS/deep-filter" "$DF_URL"
chmod +x "$ASSETS/deep-filter"
ACTUAL=$(du -sb "$ASSETS/deep-filter" | cut -f1)
echo "DeepFilter: $(du -sh $ASSETS/deep-filter | cut -f1) ($ACTUAL bytes)"
[ "$ACTUAL" -gt 1000000 ] || { echo "ERROR: DeepFilter binary too small ($ACTUAL bytes)"; exit 1; }
echo "::endgroup::"

# ── 4. Reference audio from HF server ────────────────────────────────────────
echo "::group::Download reference audio"
BASE="https://carm5333-tilawa-server.hf.space/reference_audio"
for f in ref_araf_1425h.mp3 ref_fath_1425h.mp3 ref_fatir_1425h.mp3; do
    curl -fL --retry 3 --retry-delay 5 -o "$REF_ASSETS/$f" "$BASE/$f"
    ACTUAL=$(du -sb "$REF_ASSETS/$f" | cut -f1)
    echo "  $f: $(du -sh $REF_ASSETS/$f | cut -f1) ($ACTUAL bytes)"
    [ "$ACTUAL" -gt 100000 ] || echo "  WARNING: $f may be too small"
done
echo "::endgroup::"

echo ""
echo "=== Final asset sizes ==="
du -sh "$ASSETS"/* "$REF_ASSETS"/* 2>/dev/null
