#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""local_engines_test.py — S250 guard for the local-mode engine wiring.

The bug this prevents: LocalEngineRunner.kt had TWO independent lists — an
id->script map in runEngine() and a filename list in extractEngines() — and
they had drifted. extractEngines() asked the APK for engine_v90.py and
engine_v80.py, which exist nowhere in the project, while runEngine() pointed
v9.0/v8.0 at them. Three more (engine_v100.py, engine_v85.py, engine_v70.py)
were named by both but had never been copied into assets/engines/. Every
extraction failure was swallowed by an empty `catch (_: Exception) {}`, setup
still reported success, and choosing any of those five engines in local mode
died inside proot with "can't open file" and no explanation.

So: five of the nine engines offered in local mode could not work, and nothing
in the build or the app said so.

This test asserts the invariants that make that state unreachable:
  1. every script ENGINE_SCRIPTS maps to is really in assets/engines/
  2. every script extractEngines() asks for is really in assets/engines/
  3. the two are derived from one table (no second literal map)
  4. engines that CAN run offline accept the CLI runEngine actually invokes
  5. no engine id is silently routed to a different engine's script

Run: python3 test/local_engines_test.py     (stdlib only, no build needed)
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ASSETS = os.path.join(ROOT, 'assets', 'engines')
PATCH = os.path.join(ROOT, 'patch_android.py')

_fails = []


def check(label, ok, detail=''):
    print(('  PASS  ' if ok else '  FAIL  ') + label + (f'  [{detail}]' if detail else ''))
    if not ok:
        _fails.append(label)
    return ok


def kotlin_source():
    src = open(PATCH, encoding='utf-8').read()
    i = src.index('class LocalEngineRunner')
    j = src.index('\n"""', i)
    return src[i:j], src


def engine_scripts(kt):
    """Parse the single ENGINE_SCRIPTS table."""
    m = re.search(r'val ENGINE_SCRIPTS[^(]*\((.*?)\n        \)', kt, re.S)
    if not m:
        return {}
    return dict(re.findall(r'"([^"]+)"\s+to\s+"([^"]+)"', m.group(1)))


def support_scripts(kt):
    m = re.search(r'val SUPPORT_SCRIPTS[^(]*\((.*?)\n        \)', kt, re.S)
    return re.findall(r'"([^"]+\.py)"', m.group(1)) if m else []


def main():
    if not os.path.isdir(ASSETS):
        print(f'assets/engines not found at {ASSETS}')
        return 2
    kt, full = kotlin_source()
    bundled = {f for f in os.listdir(ASSETS) if f.endswith('.py')}
    scripts = engine_scripts(kt)
    support = support_scripts(kt)

    print(f'bundled engine scripts: {len(bundled)}')
    print(f'ENGINE_SCRIPTS entries: {len(scripts)}')

    check('ENGINE_SCRIPTS table is present and non-empty', bool(scripts),
          ', '.join(sorted(scripts)))

    # 1 + 2: nothing may reference a script that is not shipped
    missing = {eid: s for eid, s in scripts.items() if s not in bundled}
    check('every mapped engine script is bundled', not missing,
          '; '.join(f'{k}->{v}' for k, v in missing.items()) or 'all present')

    missing_support = [s for s in support if s not in bundled]
    check('every support script is bundled', not missing_support,
          ', '.join(missing_support) or 'all present')

    # 3: exactly one table — runEngine must read it, not carry a second copy
    check('runEngine reads the shared table',
          'ENGINE_SCRIPTS[engineId]' in kt)
    # There must be exactly ONE mapOf() keyed by engine ids — the ENGINE_SCRIPTS
    # declaration itself. A second one means the drift this test guards against
    # has been reintroduced.
    id_maps = re.findall(r'mapOf\(\s*\n\s*"v\d+\.\d+"\s+to\s+"', kt)
    check('exactly one id->script table exists (no drifting copy)',
          len(id_maps) == 1, f'{len(id_maps)} found')

    # 4: the ids that can run offline must accept runEngine's actual CLI.
    #    Safaa takes positional `input output`; everything else -i/-o/--ref.
    for eid, script in sorted(scripts.items()):
        path = os.path.join(ASSETS, script)
        if not os.path.exists(path):
            continue
        src = open(path, encoding='utf-8', errors='replace').read()
        if script.startswith('engine_safaa'):
            ok = bool(re.search(r"add_argument\(\s*['\"]input", src))
            check(f'{eid} ({script}) takes positional input/output', ok)
        else:
            has_i = bool(re.search(r"add_argument\(\s*['\"]-i['\"]", src))
            has_o = bool(re.search(r"add_argument\(\s*['\"]-o['\"]", src))
            check(f'{eid} ({script}) accepts -i/-o', has_i and has_o,
                  f'-i={has_i} -o={has_o}')

    # 5: no two engine ids may share a script (would silently mis-attribute
    #    output to the engine the user thought they picked)
    dupes = {}
    for eid, s in scripts.items():
        dupes.setdefault(s, []).append(eid)
    shared = {s: ids for s, ids in dupes.items() if len(ids) > 1}
    check('no engine id is routed to another engine\'s script', not shared,
          '; '.join(f'{s}<-{ids}' for s, ids in shared.items()) or 'all distinct')

    # extraction must not be silent any more
    check('extraction failures are logged, not swallowed',
          'could not extract' in kt)
    check('availableLocalEngines() is exposed on the channel',
          'fun availableLocalEngines' in kt and
          '"availableLocalEngines" ->' in full)
    check('runEngine refuses a missing script with a readable message',
          'is not available offline' in kt)

    # the Dart side must actually consult it
    home = open(os.path.join(ROOT, 'lib', 'screens', 'home_screen.dart'),
                encoding='utf-8').read()
    svc = open(os.path.join(ROOT, 'lib', 'services', 'local_engine_service.dart'),
               encoding='utf-8').read()
    check('Dart service wraps availableLocalEngines',
          'availableLocalEngines' in svc)
    check('home screen blocks engines with no offline script',
          '_engineBlocked' in home and '_refreshLocalEngines' in home)

    # a bundled script nothing routes to is dead weight in the APK
    routed = set(scripts.values()) | set(support)
    orphans = sorted(bundled - routed)
    if orphans:
        print(f'  NOTE  bundled but never extracted: {", ".join(orphans)}')

    print('\n' + '=' * 60)
    if _fails:
        print(f'{len(_fails)} CHECK(S) FAILED:')
        for f in _fails:
            print('  · ' + f)
        return 1
    print('all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
