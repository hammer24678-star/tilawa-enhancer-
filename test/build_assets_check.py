#!/usr/bin/env python3
"""S252: parse-check build_assets.sh, including the shell it embeds as a string.

build_assets.sh passes a ~215-line script to Alpine as a single double-quoted
`sh -eu -c "..."` argument. Nothing parses that inner script until Docker runs
it, which is forty minutes into a CI job and after QEMU, the Alpine pull and
the whole apk install have already happened. A stray quote or an unbalanced
`if` in there costs a full build to discover.

This is the same idea as test/kotlin_compile_check.sh, which exists because
patch_android.py emits its Kotlin as a string literal that nothing compiled.

It also guards the S252 fix itself: the two packages with no musllinux/aarch64
wheel must keep being installed one at a time with their own logs, because the
combined install is what made a failure impossible to attribute.
"""
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "build_assets.sh")

# Compiled from source inside the emulated container; see the S252 comment.
COMPILED_FROM_SOURCE = ("soxr", "webrtcvad")

failures = []


def fail(msg):
    failures.append(msg)


def unescape_double_quoted(s):
    """Apply bash's double-quote rules, the way the shell hands the string to sh."""
    out, i = [], 0
    while i < len(s):
        if s[i] == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            if nxt == "\n":  # line continuation: both characters vanish
                i += 2
                continue
            if nxt in '\\"$`':
                out.append(nxt)
                i += 2
                continue
        out.append(s[i])
        i += 1
    return "".join(out)


def inner_payloads(src):
    """Every `sh -eu -c "..."` argument in the script, unescaped."""
    payloads, i = [], 0
    while True:
        m = re.search(r'sh -eu -c "', src[i:])
        if not m:
            return payloads
        start = i + m.end()
        j = start
        while j < len(src):
            if src[j] == "\\":
                j += 2
                continue
            if src[j] == '"':
                break
            j += 1
        if j >= len(src):
            fail("unterminated sh -eu -c string")
            return payloads
        payloads.append(unescape_double_quoted(src[start:j]))
        i = j + 1


def main():
    if not os.path.exists(SCRIPT):
        print("MISSING", SCRIPT)
        return 1
    src = open(SCRIPT, encoding="utf-8").read()

    # ---- 1. the outer script parses ------------------------------------
    r = subprocess.run(["bash", "-n", SCRIPT], capture_output=True, text=True)
    if r.returncode:
        fail("build_assets.sh does not parse:\n" + r.stderr.strip())

    # ---- 2. every embedded inner script parses --------------------------
    payloads = inner_payloads(src)
    if not payloads:
        fail("found no `sh -eu -c` payload — has the script been restructured?")
    for n, payload in enumerate(payloads):
        with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as fh:
            fh.write(payload)
            path = fh.name
        try:
            r = subprocess.run(["sh", "-n", path], capture_output=True, text=True)
            if r.returncode:
                fail("embedded payload %d does not parse:\n%s" % (n, r.stderr.strip()))
            else:
                print("embedded payload %d: %d lines, parses" % (n, payload.count("\n") + 1))
        finally:
            os.unlink(path)

    # The inner script keeps its own `\`-newline continuations; fold them so a
    # multi-line pip invocation reads as the single command it becomes.
    joined = re.sub(r"\\\n\s*", " ", "\n".join(payloads))

    # ---- 3. failures stay attributable ----------------------------------
    # `tail -N` on a shared log is how a webrtcvad failure hid behind soxr's
    # CMake output for an entire release cycle.
    installs = re.findall(r"pip install[^\n]*", joined)
    for pkg in COMPILED_FROM_SOURCE:
        owning = [c for c in installs if re.search(r"'%s==" % pkg, c)]
        if not owning:
            fail("%s is never installed" % pkg)
            continue
        # It has to be the ONLY pinned package in its command. Sharing a command
        # means a failure cannot be attributed to it, which is the whole defect.
        if not any(len(re.findall(r"'[\w.\-]+==", c)) == 1 for c in owning):
            fail(
                "%s shares a pip install with other packages — a build failure "
                "could not be attributed to it" % pkg
            )
    if re.search(r"tail -\d+ /pip-install\.log\s*\n\s*exit 1", joined):
        fail("a failing pip install must dump its whole log, not a tail")

    # ---- 4. the QEMU compile mitigations are still in place -------------
    for needle, why in (
        ("CMAKE_BUILD_PARALLEL_LEVEL=1", "serialised CMake build"),
        ("MAKEFLAGS=-j1", "serialised make"),
        ("ulimit -s", "raised stack for the C++ frontend under qemu-user"),
    ):
        if needle not in joined:
            fail("missing %s (%s) — the g++ SIGSEGV under QEMU will return" % (needle, why))

    # ---- 5. every install checks its own exit status --------------------
    # The S247 breakage shipped because `pip install ... | tail` returns tail's
    # status, so a total failure looked like success.
    for m in re.finditer(r"pip install[^\n]*\|\s*tail", joined):
        fail("pip install piped into tail — its exit status would be lost: %s" % m.group(0)[:70])

    if failures:
        print("\nFAILED (%d):" % len(failures))
        for f in failures:
            print("  -", f)
        return 1
    print("build_assets.sh: outer script, embedded shell and S252 guards all OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
