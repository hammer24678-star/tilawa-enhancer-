#!/usr/bin/env python3
"""S251: structural gate for assets/game/nova_drift.html.

The game is one self-contained HTML file with no build step, so nothing else
in the repo can catch a config entry that names a behaviour key which does not
exist, an external dependency sneaking in, or a draw call that bypasses the
performance-tier blur gate. This runs in seconds with no browser and no npm.

The deeper runtime pass (spawning every archetype, deriving every ship's stats,
the WCAG flash ceiling, modal stacking) lives in the headless-Chromium harness;
this is the part that can run anywhere, including CI.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "assets", "game", "nova_drift.html")

EXPECTED = {"enemies": 70, "ships": 45, "achievements": 50, "upgrades": 60}

failures = []


def fail(msg):
    failures.append(msg)


def block(src, start_marker):
    """Returns the text of the array literal that begins at start_marker."""
    i = src.index(start_marker)
    i = src.index("[", i)
    depth, j = 0, i
    while j < len(src):
        if src[j] == "[":
            depth += 1
        elif src[j] == "]":
            depth -= 1
            if depth == 0:
                return src[i : j + 1]
        j += 1
    raise ValueError("unterminated array after " + start_marker)


def keys_of(src, obj_name):
    """Property names declared on a `const NAME = { ... }` behaviour library."""
    i = src.index("const %s = {" % obj_name)
    depth, j, body = 0, src.index("{", i), None
    k = j
    while k < len(src):
        if src[k] == "{":
            depth += 1
        elif src[k] == "}":
            depth -= 1
            if depth == 0:
                body = src[j : k + 1]
                break
        k += 1
    names = set(re.findall(r"^\s{4}(\w+)\s*[({:]", body, re.M))
    # Entries added after the literal, e.g. ATTACKS.devour = function(...)
    names |= set(re.findall(r"\b%s\.(\w+)\s*=" % obj_name, src))
    return names


def main():
    if not os.path.exists(GAME):
        print("MISSING", GAME)
        return 1
    src = open(GAME, encoding="utf-8").read()

    # ---- 1. still one self-contained file -------------------------------
    externals = re.findall(r'(?:src|href)\s*=\s*["\']([^"\']+)["\']', src)
    for url in externals:
        if url.startswith("https://fonts.g"):
            continue  # the one documented exception
        fail("external dependency: %s" % url)
    if re.search(r"<script[^>]+src=", src):
        fail("external script tag")

    # ---- 2. roster sizes -------------------------------------------------
    counts = {
        "enemies": len(re.findall(r"^  \{id:'", block(src, "const ENEMIES ="), re.M)),
        "ships": len(re.findall(r"^  \{id:'", block(src, "const SHIPS ="), re.M)),
        "achievements": len(
            re.findall(r"^  \{id:'", block(src, "const ACHIEVEMENTS ="), re.M)
        ),
        "upgrades": len(re.findall(r"^  \{id:'", block(src, "const UPGRADES ="), re.M)),
    }
    for name, want in EXPECTED.items():
        if counts[name] != want:
            fail("%s: expected %d entries, found %d" % (name, want, counts[name]))

    # ---- 3. every config key resolves to a library entry -----------------
    enemies_src = block(src, "const ENEMIES =")
    movements = keys_of(src, "MOVEMENTS")
    attacks = keys_of(src, "ATTACKS")
    ondeath = keys_of(src, "ONDEATH")
    passives = keys_of(src, "PASSIVES")
    conditions = keys_of(src, "CONDITIONS")

    for field, library, label in (
        ("movement", movements, "MOVEMENTS"),
        ("attack", attacks, "ATTACKS"),
        ("attack2", attacks, "ATTACKS"),
        ("onDeath", ondeath, "ONDEATH"),
    ):
        for key in re.findall(r"%s:'(\w+)'" % field, enemies_src):
            if key not in library:
                fail("enemy %s '%s' is not in %s" % (field, key, label))

    enemy_ids = set(re.findall(r"^  \{id:'(\w+)'", enemies_src, re.M))
    for field in ("spawns", "splitInto"):
        for key in re.findall(r"%s:'(\w+)'" % field, enemies_src):
            if key not in enemy_ids:
                fail("enemy %s '%s' is not an enemy id" % (field, key))

    for key in re.findall(r"passive:'(\w+)'", block(src, "const SHIPS =")):
        if key not in passives:
            fail("ship passive '%s' is not in PASSIVES" % key)
    for key in re.findall(r"cond:'(\w+)'", block(src, "const ACHIEVEMENTS =")):
        if key not in conditions:
            fail("achievement cond '%s' is not in CONDITIONS" % key)

    # ---- 3b. every upgrade's stat is actually consumed somewhere ---------
    # A purchasable upgrade whose stat nothing ever reads is a shard sink that
    # does nothing, which is indistinguishable from a bug to the player.
    upg_src = block(src, "const UPGRADES =")
    outside = src.replace(upg_src, "")
    for stat in sorted(set(re.findall(r"stat:'(\w+)'", upg_src))):
        if not re.search(r"\b%s\b" % stat, outside):
            fail("upgrade stat '%s' is declared but read nowhere" % stat)

    # ---- 4. localisation: both languages for every player-facing entry ---
    for label, arr in (
        ("enemy", enemies_src),
        ("ship", block(src, "const SHIPS =")),
        ("upgrade", block(src, "const UPGRADES =")),
        ("achievement", block(src, "const ACHIEVEMENTS =")),
    ):
        entries = re.split(r"\n  \{id:'", arr)[1:]
        for e in entries:
            eid = e.split("'", 1)[0]
            for field in ("name", "desc"):
                if ("%sAr:" % field) not in e:
                    fail("%s '%s' has no %sAr string" % (label, eid, field))

    # ---- 5. no blur bypasses the performance-tier gate -------------------
    for m in re.finditer(r"shadowBlur\s*=\s*([^;]+);", src):
        expr = m.group(1).strip()
        if expr == "0" or expr.startswith("sb(") or "sb(" in expr:
            continue
        fail("shadowBlur assignment bypasses sb(): %s" % expr)

    # ---- 5b. the WebGL2 renderer -----------------------------------------
    # GLSL is invisible to every other tool here, and a shader that fails to
    # compile only shows up as a black screen on someone's phone.
    shader_srcs = re.findall(r"GLSL\.(\w+)\s*=\s*`([^`]*)`", src)
    if len(shader_srcs) < 5:
        fail("expected the GLSL sources to be present; found %d" % len(shader_srcs))
    for name, body in shader_srcs:
        if not body.startswith("#version 300 es"):
            fail("shader %s must open with '#version 300 es' on the first line" % name)
        if "texture2D(" in body:
            fail("shader %s uses the GLSL ES 1.00 texture2D(); use texture()" % name)

    # The 2D path is the safety net for a driver that rejects a shader, a
    # device with no WebGL2, or a lost context. It must stay reachable.
    if not re.search(r"if\(GL_ON && glDrawFrame\(dt\)\)", src):
        fail("draw() must fall through to the Canvas2D path when GL is off or fails")
    for needle, why in (
        ("webglcontextlost", "context-loss handling"),
        ("NOVA_FORCE_2D", "the forced-2D switch the fallback is tested with"),
        ("fxCanvas.getContext('2d')", "the text overlay above the GL layer"),
    ):
        if needle not in src:
            fail("missing %s (%s)" % (needle, why))

    # No allocation inside the per-frame GL functions (2.8).
    for fn_name in ("glDrawFrame", "glCollect", "glDrawRange", "glPush"):
        m = re.search(r"function %s\([^)]*\)\{" % fn_name, src)
        if not m:
            fail("GL function %s not found" % fn_name)
            continue
        depth, i = 0, m.end() - 1
        while i < len(src):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        body = src[m.start():i]
        for bad in re.finditer(r"new (?:Float32Array|Array|Map)\(", body):
            fail("%s allocates per frame: %s" % (fn_name, bad.group(0)))

    # ---- 6. no music, per the hard constraint in the spec ----------------
    # A loop point or a sustained source is the thing to catch; every voice in
    # the file has to stop at an explicit time.
    for pattern, why in (
        (r"\.loop\s*=\s*true", "a looping audio source"),
        (r"<audio", "an <audio> element"),
        (r"createMediaElementSource", "media element audio"),
        (r"\.start\((?!\s*t0)", "an audio source started without an explicit time"),
    ):
        for m in re.finditer(pattern, src):
            fail("possible music/sustained audio (%s): %r" % (why, m.group(0)))
    starts = len(re.findall(r"\.start\(t0\)", src))
    stops = len(re.findall(r"\.stop\(t0", src))
    if starts != stops:
        fail("every audio voice must stop: %d start() vs %d stop()" % (starts, stops))

    # ---- 7. save compatibility ------------------------------------------
    if "novaDrift:saveV3" not in src:
        fail("the V3 save key is gone — returning players would lose progress")
    if "migrateV3" not in src:
        fail("no V3 -> V4 migration path")

    print(json.dumps(counts))
    print(
        "libraries: %d movements, %d attacks, %d death responses, "
        "%d passives, %d conditions"
        % (len(movements), len(attacks), len(ondeath), len(passives), len(conditions))
    )
    if failures:
        print("\nFAILED (%d):" % len(failures))
        for f in failures:
            print("  -", f)
        return 1
    print("nova_drift.html: all structural checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
