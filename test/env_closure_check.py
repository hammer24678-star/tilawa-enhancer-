#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""env_closure_check.py — S250k: is the shipped Python/ffmpeg environment complete?

"Make sure they have all they need to work." This answers that question
mechanically rather than by hope: it walks every ELF binary and shared object
in the environment, reads each one's DT_NEEDED entries, and checks that every
library named is actually present. A dynamic linker does exactly this at
startup, so anything missing here is a guaranteed runtime failure on-device.

Run against the python-env.tar.gz committed before S250k, it reports 63
missing libraries, which is the complete explanation for "the audio editor
isn't working":

  libgcc_s.so.1, libstdc++.so.6   numpy's _multiarray_umath links both —
                                  numpy cannot import, so every restoration
                                  engine and the whole Studio Engine die
  libopenblas.so.3                present only as a DANGLING SYMLINK
  libbz2, libexpat, libffi,       Python's own stdlib extension modules:
  liblzma, libsqlite3, libmpdec,  ctypes, sqlite3, lzma, bz2, decimal, expat
  libreadline, libncursesw        are all unloadable
  ~45 codec/system libs           libavcodec/libavformat/libavdevice cannot
  (libmp3lame, libsoxr, libvpx,   load at all, so ffmpeg is dead — including
   libx264, libdrm, libxcb, …)    MP3 export and every ffmpeg fallback path

Both halves of the pipeline — the numpy Studio Engine and the plain-ffmpeg
chain it degrades to — were therefore non-functional, while every readiness
check in the app reported success because they only ever asked whether files
existed.

Usage:
    python3 test/env_closure_check.py <extracted-root> [<extracted-root> ...]
    python3 test/env_closure_check.py --tar assets/alpine/python-env.tar.gz \\
                                      [--tar assets/alpine/alpine-rootfs.tar.gz]

Multiple roots/tars are treated as ONE layered filesystem, which is how the
device assembles them (alpine rootfs first, python env overlaid).

Exit 0 = every dependency resolves. Exit 1 = something is missing.
Requires only the standard library (ELF parsing is done inline, so this runs
anywhere — no readelf, no host toolchain).
"""
import argparse
import os
import struct
import sys
import tarfile
import tempfile

# Libraries the musl loader provides itself or that are legitimately absent
# from a rootfs; never reported as missing.
_PROVIDED = {
    'ld-musl-aarch64.so.1', 'ld-musl-x86_64.so.1',
    'libc.musl-aarch64.so.1', 'libc.musl-x86_64.so.1',
    'linux-vdso.so.1', 'ld-linux-aarch64.so.1',
}


def _elf_needed(path):
    """DT_NEEDED names from an ELF file, parsed directly (no readelf).

    Returns [] for anything that is not a 64-bit ELF we understand, so
    scripts, data files and foreign objects are skipped silently.
    """
    try:
        with open(path, 'rb') as fh:
            data = fh.read()
    except Exception:
        return []
    if len(data) < 64 or data[:4] != b'\x7fELF':
        return []
    if data[4] != 2:                                  # ELFCLASS64 only
        return []
    little = data[5] == 1
    e = '<' if little else '>'
    try:
        e_phoff = struct.unpack_from(e + 'Q', data, 0x20)[0]
        e_phentsize = struct.unpack_from(e + 'H', data, 0x36)[0]
        e_phnum = struct.unpack_from(e + 'H', data, 0x38)[0]
    except Exception:
        return []

    dyn_off = dyn_size = None
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        if off + 56 > len(data):
            break
        p_type = struct.unpack_from(e + 'I', data, off)[0]
        if p_type == 2:                               # PT_DYNAMIC
            dyn_off = struct.unpack_from(e + 'Q', data, off + 0x08)[0]
            dyn_size = struct.unpack_from(e + 'Q', data, off + 0x20)[0]
            break
    if dyn_off is None:
        return []

    # locate .dynstr via DT_STRTAB, mapping the vaddr back through PT_LOAD
    loads = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        if off + 56 > len(data):
            break
        if struct.unpack_from(e + 'I', data, off)[0] == 1:      # PT_LOAD
            p_offset = struct.unpack_from(e + 'Q', data, off + 0x08)[0]
            p_vaddr = struct.unpack_from(e + 'Q', data, off + 0x10)[0]
            p_filesz = struct.unpack_from(e + 'Q', data, off + 0x20)[0]
            loads.append((p_vaddr, p_offset, p_filesz))

    def v2o(vaddr):
        for p_vaddr, p_offset, p_filesz in loads:
            if p_vaddr <= vaddr < p_vaddr + p_filesz:
                return p_offset + (vaddr - p_vaddr)
        return None

    needed_offsets, strtab = [], None
    pos, end = dyn_off, dyn_off + (dyn_size or 0)
    while pos + 16 <= min(end, len(data)):
        d_tag, d_val = struct.unpack_from(e + 'qQ', data, pos)
        if d_tag == 0:                                 # DT_NULL
            break
        if d_tag == 1:                                 # DT_NEEDED
            needed_offsets.append(d_val)
        elif d_tag == 5:                               # DT_STRTAB
            strtab = v2o(d_val)
        pos += 16
    if strtab is None:
        return []

    out = []
    for o in needed_offsets:
        s = strtab + o
        if s >= len(data):
            continue
        nul = data.find(b'\x00', s)
        if nul > s:
            out.append(data[s:nul].decode('utf-8', 'replace'))
    return out


def scan(roots):
    """-> (present filenames, {needed lib: set(users)}, elf count)"""
    present, needed, count = set(), {}, 0
    for root in roots:
        for d, _, files in os.walk(root):
            for f in files:
                present.add(f)
    for root in roots:
        for d, _, files in os.walk(root):
            for f in files:
                p = os.path.join(d, f)
                if os.path.islink(p):
                    continue
                for n in _elf_needed(p):
                    needed.setdefault(n, set()).add(os.path.relpath(p, root))
                else:
                    pass
                # count only files that really were ELF
                try:
                    with open(p, 'rb') as fh:
                        if fh.read(4) == b'\x7fELF':
                            count += 1
                except Exception:
                    pass
    return present, needed, count


# S252: kernel-provided filesystems. These are mounted on the device at
# runtime and can never exist inside a tarball, so a symlink into one is
# correct rather than broken. /etc/mtab -> /proc/mounts is the standard Linux
# configuration and is exactly what Alpine's minirootfs ships — counting it as
# dangling failed the build on a healthy environment.
_RUNTIME_FS = ('/proc', '/sys', '/dev', '/run')


def _is_runtime_target(target):
    return any(target == m or target.startswith(m + '/') for m in _RUNTIME_FS)


def dangling(roots):
    """Symlinks whose target is absent.

    An ABSOLUTE symlink inside a rootfs (/bin/ls -> /bin/busybox) must be
    resolved against that rootfs, not against the host filesystem — otherwise
    every busybox applet link reads as broken. Relative links resolve normally.
    Links into /proc, /sys, /dev and /run are resolved by the kernel on the
    device and are skipped entirely.
    """
    bad = []
    for root in roots:
        for d, _, files in os.walk(root):
            for f in files:
                p = os.path.join(d, f)
                if not os.path.islink(p):
                    continue
                target = os.readlink(p)
                if os.path.isabs(target) and _is_runtime_target(target):
                    continue
                if os.path.isabs(target):
                    resolved = None
                    for r in roots:                    # layered: try each root
                        cand = os.path.join(r, target.lstrip('/'))
                        if os.path.exists(cand):
                            resolved = cand
                            break
                else:
                    cand = os.path.join(d, target)
                    resolved = cand if os.path.exists(cand) else None
                if resolved is None:
                    bad.append(f'{os.path.relpath(p, root)} -> {target}')
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('roots', nargs='*', help='extracted root directories')
    ap.add_argument('--tar', action='append', default=[],
                    help='tarball to extract and check (layered in order)')
    args = ap.parse_args()

    tmp = None
    roots = list(args.roots)
    if args.tar:
        tmp = tempfile.mkdtemp(prefix='envclosure_')
        for t in args.tar:
            with tarfile.open(t) as tf:
                tf.extractall(tmp, filter='tar')
        roots.append(tmp)
    if not roots:
        ap.error('give a root directory or --tar')

    present, needed, elf_count = scan(roots)
    missing = {n: u for n, u in needed.items()
               if n not in present and n not in _PROVIDED}
    broken_links = dangling(roots)

    print(f'roots: {", ".join(roots)}')
    print(f'ELF files scanned      : {elf_count}')
    print(f'distinct libs required : {len(needed)}')
    print(f'dangling symlinks      : {len(broken_links)}')
    print(f'MISSING libraries      : {len(missing)}')
    for n in sorted(missing):
        users = sorted(missing[n])
        shown = ', '.join(users[:3]) + (' …' if len(users) > 3 else '')
        print(f'    {n:26s} <- {shown}')
    for b in broken_links[:20]:
        print(f'    DANGLING SYMLINK: {b}')

    if tmp:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # S252: these are two different faults and used to share one message. A
    # dangling symlink reported as "cannot load its own binaries" is what sent
    # the S250k diagnosis after a shared-library closure that was already
    # complete (MISSING libraries: 0).
    if missing:
        print('\nFAIL: the environment cannot load its own binaries — '
              f'{len(missing)} shared librar'
              f'{"y is" if len(missing) == 1 else "ies are"} missing.')
        return 1
    if broken_links:
        print(f'\nFAIL: {len(broken_links)} symlink(s) resolve to nothing '
              'inside the environment.')
        return 1
    print('\nPASS: every shared-library dependency resolves.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
