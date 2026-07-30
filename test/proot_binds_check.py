#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""proot_binds_check.py — S258 guard for the audio editor's proot commands.

`runProotCmd` mounts exactly three things into the sandbox: the parent of the
`inputPath` it is handed, the parent of the `outputPath`, and the app cache
dir. Anything else on the device filesystem does not exist inside proot.

Every file the editor hands to the Studio Engine therefore has to be either

  * one of those two declared paths, or
  * a temp-dir path (the cache dir, which is always bound), which in this
    screen means something that came back from _safeInput() or was built from
    getTemporaryDirectory().

The Compare tab shipped passing BOTH picker paths straight through — the
reference as `inputPath`, and the loaded file as a bare third argument. The
loaded file sat in a directory proot never mounted, so the engine could not
open it. Every other operation in the screen copies through _safeInput() for
exactly this reason, which is what made the omission easy to miss.

This parses each `python3 "$script" ...` command out of the Dart and checks
that every interpolated path in it is accounted for.

Run: python3 test/proot_binds_check.py      (stdlib only)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITOR = os.path.join(ROOT, 'lib', 'screens', 'audio_editor_screen.dart')

_fails = []


def check(label, ok, detail=''):
    print(('  PASS  ' if ok else '  FAIL  ') + label + (f'  [{detail}]' if detail else ''))
    if not ok:
        _fails.append(label)


def main():
    src = open(EDITOR, encoding='utf-8').read()

    # Names that are safe to interpolate into a proot command:
    #  - assigned from _safeInput(...)          → copied into the temp dir
    #  - built from a getTemporaryDirectory()   → the temp dir itself
    #  - the extracted engine script            → also in the temp dir
    safe = set(re.findall(r'(\w+)\s*=\s*await\s+_safeInput\(', src))
    safe |= set(re.findall(r'(\w+)\s*=\s*await\s+_ensureDspScript\(', src))
    safe |= set(re.findall(r'(\w+)\s*=\s*await\s+_progressFilePath\(', src))
    safe |= set(re.findall(r'(\w+)\s*=\s*await\s+_outFile\(', src))   # external files dir, bound
    # Anything built from the temp dir, whether as a bare string or wrapped in
    # a File(...): `x = '${tmp.path}/y'` and `x = File('${tmp.path}/y')`.
    safe |= set(re.findall(r"(\w+)\s*=\s*(?:File\()?'\$\{tmp\.path\}/", src))
    safe |= {'script', 'outBase'}
    # A name assigned by a ternary between two already-safe names is safe too —
    # e.g. `final ref = cond ? refSlice : inp;`, the untouched-reference
    # fallback in the quality check.
    for name, a, b in re.findall(
            r'(\w+)\s*=\s*\([^;]*?\)\s*\?\s*(\w+)\s*:\s*(\w+)\s*;', src, re.S):
        if a in safe and b in safe:
            safe.add(name)
    print('  temp-dir-backed names: %s' % ', '.join(sorted(safe)))

    cmds = re.findall(r"'(python3 \"\$script\"[^']*)'", src)
    check('found the Studio Engine invocations', len(cmds) >= 5, '%d commands' % len(cmds))

    for cmd in cmds:
        mode = re.search(r'--(\w+)', cmd)
        label = mode.group(1) if mode else 'process'
        # every "$x" or "${x.path}" interpolation in the command
        names = re.findall(r'\$\{?(\w+)', cmd)
        bad = [n for n in names
               if n != 'script' and n not in safe and not n.startswith('_')]
        # A leading underscore means a state field (_filePath, _cmpRefPath):
        # those are raw picker paths and are never bound.
        raw = [n for n in names if n.startswith('_')]
        check('%s: every path is inside a bound directory' % label,
              not bad and not raw,
              ('unbound: ' + ' '.join(bad + raw)) if (bad or raw) else ' '.join(names))

    print('\n' + '=' * 60)
    if _fails:
        print('%d CHECK(S) FAILED:' % len(_fails))
        for f in _fails:
            print('  · ' + f)
        return 1
    print('all proot commands pass only bound paths')
    return 0


if __name__ == '__main__':
    sys.exit(main())
