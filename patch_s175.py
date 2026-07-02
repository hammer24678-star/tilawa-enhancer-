#!/usr/bin/env python3
"""
patch_s175.py — Add missing _aggressiveModeToggle widget (auto-locating version)

Root cause:  Same as S174-hotfix. S173 added the call site and the
             _aggressive field, but never defined Widget _aggressiveModeToggle(S s).

Why S175 instead of just re-running the .patch file:
             The unified diff (patch_s174_hotfix.patch) needs to be run from
             the repo root with the right -p level, which broke when the file
             was patched standalone from ~/downloads. This script instead
             *finds* lib/screens/home_screen.dart itself — you can run it
             from anywhere (repo root, ~/downloads with the repo as a sibling
             folder, etc.) and it will locate the right file.

Usage:
    python3 patch_s175.py                  # auto-search from cwd upward/downward
    python3 patch_s175.py /path/to/repo     # search starting at this folder
    python3 patch_s175.py /path/to/home_screen.dart   # patch this exact file

Safe to re-run: it's idempotent (SKIPs if already applied).
"""

import sys
from pathlib import Path

def fail(msg):
    print(f'  FAIL  {msg}')
    sys.exit(1)

def find_home_screen(start: Path) -> Path:
    # 1) exact file given
    if start.is_file() and start.name == 'home_screen.dart':
        return start

    # 2) obvious relative path from a repo root
    candidate = start / 'lib' / 'screens' / 'home_screen.dart'
    if candidate.exists():
        return candidate

    # 3) search downward from start (repo root passed, or cwd)
    if start.is_dir():
        matches = list(start.rglob('home_screen.dart'))
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            print('  Multiple home_screen.dart files found:')
            for m in matches:
                print(f'    - {m}')
            fail('ambiguous — pass the exact path as an argument')

    # 4) search upward from start (in case we're run from deep inside repo, e.g. lib/screens/)
    for parent in [start] + list(start.parents):
        candidate = parent / 'lib' / 'screens' / 'home_screen.dart'
        if candidate.exists():
            return candidate

    fail(f'could not find home_screen.dart starting from {start}')

# ── Resolve target file ──────────────────────────────────────────────────────

arg = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
HOME = find_home_screen(arg)
print(f'  Target: {HOME}')

STAMP = HOME.parent / '.patch_s175_done'
if STAMP.exists():
    print('patch_s175: already applied — delete .patch_s175_done next to home_screen.dart to re-run')
    sys.exit(0)

src = HOME.read_text(encoding='utf-8')

OLD_ANCHOR = '  Widget _serverBanner(S s) {'

NEW_METHOD = (
    '  // S173/S174-hotfix/S175: aggressive dereverberation toggle (الصفاء v11.0 only)\n'
    '  Widget _aggressiveModeToggle(S s) {\n'
    '    const amber  = Color(0xFFE8943A);\n'
    '    const textB  = Color(0xFF8AACBA);\n'
    '    const darkBg = Color(0xFF1A0E05);\n'
    '    return Padding(\n'
    '      padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),\n'
    '      child: AnimatedContainer(\n'
    '        duration: const Duration(milliseconds: 280),\n'
    '        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),\n'
    '        decoration: BoxDecoration(\n'
    '          color: _aggressive\n'
    '            ? darkBg.withValues(alpha: 0.85)\n'
    '            : const Color(0xFF0A0E12).withValues(alpha: 0.6),\n'
    '          borderRadius: BorderRadius.circular(12),\n'
    '          border: Border.all(\n'
    '            color: _aggressive\n'
    '              ? amber.withValues(alpha: 0.45)\n'
    '              : const Color(0xFF1A2733),\n'
    '            width: 1.0)),\n'
    '        child: Row(children: [\n'
    '          Icon(\n'
    '            _aggressive ? Icons.waves_rounded : Icons.water_drop_outlined,\n'
    '            color: _aggressive ? amber : textB, size: 18),\n'
    '          const SizedBox(width: 10),\n'
    '          Expanded(child: Column(\n'
    '            crossAxisAlignment: CrossAxisAlignment.start,\n'
    '            children: [\n'
    '            Text(\n'
    '              _aggressive\n'
    "                ? (s.ar ? 'وضع صارم (إزالة صدى عميقة)' : 'Aggressive (deep dereverberation)')\n"
    "                : (s.ar ? 'وضع قياسي (محافظ على الصوت)' : 'Standard (voice-preserving)'),\n"
    '              style: TextStyle(\n'
    '                color: _aggressive ? amber : textB,\n'
    '                fontSize: 12, fontWeight: FontWeight.w700)),\n'
    '            Text(\n'
    '              _aggressive\n'
    "                ? (s.ar ? 'لتسجيلات شديدة الصدى' : 'Best for heavily reverberant recordings')\n"
    "                : (s.ar ? 'موصى به للتسجيلات العادية' : 'Recommended for most recordings'),\n"
    '              style: const TextStyle(\n'
    '                color: Color(0xFF3D5A65), fontSize: 10)),\n'
    '          ])),\n'
    '          Switch(\n'
    '            value: _aggressive,\n'
    '            onChanged: _busy ? null : (v) {\n'
    '              setState(() => _aggressive = v);\n'
    '              SharedPreferences.getInstance().then(\n'
    "                (p) => p.setBool('aggressive_mode', v));  // S174-B4\n"
    '            },\n'
    '            activeColor: amber,\n'
    '            inactiveThumbColor: textB.withValues(alpha: 0.5),\n'
    '            inactiveTrackColor: const Color(0xFF1A2733)),\n'
    '        ]),\n'
    '      ),\n'
    '    );\n'
    '  }\n'
    '\n'
    + OLD_ANCHOR
)

if 'Widget _aggressiveModeToggle(S s) {' in src:
    print('  SKIP  _aggressiveModeToggle already defined (already applied)')
    STAMP.write_text('S175\n')
    sys.exit(0)

if OLD_ANCHOR not in src:
    fail(f'anchor "{OLD_ANCHOR.strip()}" not found in {HOME}')

HOME.write_text(src.replace(OLD_ANCHOR, NEW_METHOD, 1), encoding='utf-8')
STAMP.write_text('S175\n')

print('  OK    inserted _aggressiveModeToggle widget body')
print('\n✅  patch_s175 done')
print(f'   git add {HOME}')
print('   git commit -m "S175: add missing _aggressiveModeToggle widget body"')
print('   git push')
