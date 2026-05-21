#!/usr/bin/env python3
"""
tilawa_fix_s29_v5.py — compile error fixes after v4
=====================================================
Errors from GitHub Actions build log:

  1. lang_provider.dart   — duplicate getters (historyTitle, cancelBtn,
                            processAnother, clearAll, clearAllConfirm,
                            copiedMetrics, estTime)
  2. welcome_screen.dart  — unclosed ShaderMask '('
  3. home_screen.dart     — _fileBytes declared twice (int + int?)
  4. home_screen.dart     — Random / sin / cos not in scope
                            (dart:math imported as 'math' alias, need show)
  5. history_screen.dart  — duplicate _clearAll method
"""
from pathlib import Path
from datetime import datetime

def _h1(t): print(f'\n{"="*60}\n  {t}\n{"="*60}')
def _ok(m):  print(f'     OK  {m}')
def _err(m): print(f'     XX  {m}')
def _skip(m):print(f'     --  {m}')
_log = []
def _rec(s,l,r): _log.append((s,l,r))

def _replace_once(txt, old, new, label):
    c = txt.count(old)
    if c == 0: _err(f'NOT FOUND — {label}'); return txt, False
    if c > 1:  print(f'     !!  {c}x — first — {label}')
    else:      _ok(f'Replaced — {label}')
    return txt.replace(old, new, 1), True

def _read(p):     return Path(p).read_text(encoding='utf-8')
def _write(p, t): Path(p).write_text(t, encoding='utf-8'); _ok(f'Wrote {Path(p).name}')

REPO = Path.home() / 'tilawa-enhancer'
LIB  = REPO / 'lib'
SC   = LIB / 'screens'
ST   = LIB / 'state'

_h1(f'tilawa_fix_s29_v5  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')


# ─────────────────────────────────────────────────────────────
# 1. lang_provider.dart — remove the duplicate S28 block
#    The file has two blocks. The SECOND block (added by v3/v4) is
#    the dupe. It starts right after `String get target =>` closes.
# ─────────────────────────────────────────────────────────────
_h1('1 — lang_provider.dart  remove duplicate getters')
txt = _read(ST / 'lang_provider.dart')

# The duplicate block to kill (v3 added this at the bottom of class S,
# but the correct S28 strings are already at lines 63-70 of the dump).
DUPE_BLOCK = (
    "  String get historyTitle   => ar ? 'سجل الملفات المعالجة'          : 'Processing History';\n"
    "  // S28\n"
    "  String get cancelBtn      => ar ? 'إلغاء'                  : 'Cancel';\n"
    "  String get processAnother => ar ? 'معالجة ملف آخر'          : 'Process Another File';\n"
    "  String get clearAll       => ar ? 'مسح الكل'               : 'Clear All';\n"
    "  String get clearAllConfirm=> ar ? 'هل تريد مسح كل السجل؟'  : 'Clear all history?';\n"
    "  String get copiedMetrics  => ar ? 'تم نسخ المقاييس'         : 'Metrics copied';\n"
    "  String get estTime        => ar ? 'الوقت المتوقع'            : 'Est. time';\n"
    "  String get target       =>\n"
    "    ar ? 'الهدف: LUFS=-6.29 · RMS=-10.01 · Crest=10.25 · LRA=4.19'\n"
    "       : 'Target: LUFS=-6.29 · RMS=-10.01 · Crest=10.25 · LRA=4.19';\n"
    "}\n"
)
if DUPE_BLOCK in txt:
    txt = txt.replace(DUPE_BLOCK,
        "  String get version        => ar ? 'الإصدار 2.9'  : 'Version 2.9';\n"
        "  String get target         =>\n"
        "    ar ? 'الهدف: LUFS=-6.29 · RMS=-10.01 · Crest=10.25 · LRA=4.19'\n"
        "       : 'Target: LUFS=-6.29 · RMS=-10.01 · Crest=10.25 · LRA=4.19';\n"
        "}\n"
    , 1)
    _ok('Duplicate S28 block removed, version + target kept')
    _rec('1a', 'lang_provider dupe block removed', '[OK] PASS')
else:
    # Try removing only individual dupes that exist
    # Remove the second historyTitle getter (the one with extra spaces)
    for old_g, label in [
        ("  String get historyTitle   => ar ? 'سجل الملفات المعالجة'          : 'Processing History';\n",
         'dupe historyTitle'),
        ("  String get cancelBtn      => ar ? 'إلغاء'                  : 'Cancel';\n",
         'dupe cancelBtn'),
        ("  String get processAnother => ar ? 'معالجة ملف آخر'          : 'Process Another File';\n",
         'dupe processAnother'),
        ("  String get clearAll       => ar ? 'مسح الكل'               : 'Clear All';\n",
         'dupe clearAll'),
        ("  String get clearAllConfirm=> ar ? 'هل تريد مسح كل السجل؟'  : 'Clear all history?';\n",
         'dupe clearAllConfirm'),
        ("  String get copiedMetrics  => ar ? 'تم نسخ المقاييس'         : 'Metrics copied';\n",
         'dupe copiedMetrics'),
        ("  String get estTime        => ar ? 'الوقت المتوقع'            : 'Est. time';\n",
         'dupe estTime'),
    ]:
        if txt.count(old_g) > 1:
            # Remove only the second occurrence
            idx = txt.index(old_g, txt.index(old_g) + 1)
            txt = txt[:idx] + txt[idx + len(old_g):]
            _ok(f'Removed second occurrence of {label}')
        elif txt.count(old_g) == 0:
            _skip(f'{label} not found')
    _rec('1a', 'lang_provider dupes fixed individually', '[OK] PASS')

# Also ensure `version` getter exists
if 'String get version' not in txt:
    OLD_TARGET = "  String get target"
    NEW_TARGET = "  String get version => ar ? 'الإصدار 2.9' : 'Version 2.9';\n  String get target"
    txt, ok = _replace_once(txt, OLD_TARGET, NEW_TARGET, 'add version getter')
    _rec('1b', 'version getter added', '[OK] PASS' if ok else '[XX] FAIL')
else:
    _skip('version getter already present')
    _rec('1b', 'version getter', '[--] SKIP')

_write(ST / 'lang_provider.dart', txt)


# ─────────────────────────────────────────────────────────────
# 2. welcome_screen.dart — fix unclosed ShaderMask
#    The v3 patch did:
#      ShaderMask(
#        shaderCallback: ...,
#        child: Text(s.appName, ...)),   ← closes Text and ShaderMask
#          const SizedBox(height: 8),    ← BUT this is INSIDE the Column
#    The original file's indentation shows the ShaderMask was missing
#    its closing '),' before const SizedBox. Fix: rewrite the block.
# ─────────────────────────────────────────────────────────────
_h1('2 — welcome_screen.dart  fix ShaderMask closing paren')
txt = _read(SC / 'welcome_screen.dart')

# The broken block from the dump (lines 132-142):
OLD_BROKEN = (
    "        ShaderMask(\n"
    "      shaderCallback: (b) => const LinearGradient(\n"
    "        colors: [Color(0xFFD4AF37), Color(0xFFF0CF60), Color(0xFFD4AF37)],\n"
    "        stops: [0.0, 0.5, 1.0]).createShader(b),\n"
    "      child: Text(s.appName,\n"
    "          textAlign: TextAlign.center,\n"
    "          style: const TextStyle(\n"
    "            fontSize: 36, fontWeight: FontWeight.bold,\n"
    "            color: Color(0xFFD4AF37), height: 1.2,\n"
    "            letterSpacing: -0.5)),\n"
    "          const SizedBox(height: 8),\n"
    "          Text(s.subtitle,\n"
)
NEW_FIXED = (
    "        ShaderMask(\n"
    "          shaderCallback: (b) => const LinearGradient(\n"
    "            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60), Color(0xFFD4AF37)],\n"
    "            stops: [0.0, 0.5, 1.0]).createShader(b),\n"
    "          child: Text(s.appName,\n"
    "            textAlign: TextAlign.center,\n"
    "            style: const TextStyle(\n"
    "              fontSize: 36, fontWeight: FontWeight.bold,\n"
    "              color: Colors.white, height: 1.2,\n"
    "              letterSpacing: -0.5))),\n"
    "          const SizedBox(height: 8),\n"
    "          Text(s.subtitle,\n"
)
txt, ok = _replace_once(txt, OLD_BROKEN, NEW_FIXED, 'fix ShaderMask closing paren')
_rec('2', 'welcome_screen ShaderMask fixed', '[OK] PASS' if ok else '[XX] FAIL')

_write(SC / 'welcome_screen.dart', txt)


# ─────────────────────────────────────────────────────────────
# 3. home_screen.dart — fix _fileBytes duplicate + math imports
# ─────────────────────────────────────────────────────────────
_h1('3 — home_screen.dart  fixes')
txt = _read(SC / 'home_screen.dart')

# 3a — remove the extra `int? _fileBytes;` (line 85 in dump)
#      The original `int _fileBytes = 0;` at line 58 is correct.
OLD_DUPE_FB = "  int? _fileBytes;\n"
if txt.count(OLD_DUPE_FB) >= 1:
    # Remove only if the original int _fileBytes  = 0 also exists
    if '  int     _fileBytes  = 0;' in txt or '  int _fileBytes' in txt:
        txt = txt.replace(OLD_DUPE_FB, '', 1)
        _ok('Removed duplicate int? _fileBytes')
        _rec('3a', '_fileBytes dupe removed', '[OK] PASS')
    else:
        _skip('only one _fileBytes, skipping')
        _rec('3a', '_fileBytes dupe', '[--] SKIP')
else:
    _skip('int? _fileBytes already gone')
    _rec('3a', '_fileBytes dupe', '[--] SKIP')

# 3b — fix math imports so Random / sin / cos are in scope
# Current: `import 'dart:math' as math;` + `import 'dart:math' show pi;`
# Need:    `import 'dart:math' as math;` + `import 'dart:math' show pi, sin, cos, Random;`
OLD_MATH = "import 'dart:math' show pi; // S30-R1\n"
NEW_MATH = "import 'dart:math' show pi, sin, cos, Random; // S29+S30\n"
if OLD_MATH in txt:
    txt, ok = _replace_once(txt, OLD_MATH, NEW_MATH, 'expand dart:math show clause')
    _rec('3b', 'dart:math show pi,sin,cos,Random', '[OK] PASS' if ok else '[XX] FAIL')
elif 'show pi, sin, cos, Random' in txt:
    _skip('dart:math show already expanded')
    _rec('3b', 'dart:math imports', '[--] SKIP')
else:
    # Fallback: replace the math alias import
    OLD_MATH2 = "import 'dart:math' as math;\n"
    NEW_MATH2 = "import 'dart:math' as math;\nimport 'dart:math' show pi, sin, cos, Random;\n"
    txt, ok = _replace_once(txt, OLD_MATH2, NEW_MATH2, 'add dart:math show clause')
    _rec('3b', 'dart:math show added', '[OK] PASS' if ok else '[XX] FAIL')

# 3c — fix _StarParticle to use math.Random (in case Random isn't in show)
# Actually since we added `show Random` above this should work, but let's
# also fix the _rng variable name used in initState (dump line 132 uses _rng)
OLD_RNG = "    final _rng = math.Random(7777);\n"
if OLD_RNG in txt:
    txt = txt.replace(OLD_RNG, "    final rng = Random(7777);\n", 1)
    _ok('Fixed _rng → rng (non-underscore local)')
    _rec('3c', 'initState _rng → rng', '[OK] PASS')
else:
    _skip('_rng already fixed or not present')
    _rec('3c', 'initState _rng', '[--] SKIP')

_write(SC / 'home_screen.dart', txt)


# ─────────────────────────────────────────────────────────────
# 4. history_screen.dart — remove duplicate _clearAll method
#    The FIRST one (lines 112-138) is the OLD version.
#    The SECOND one (lines 151-178) is our S29 version. Keep second.
# ─────────────────────────────────────────────────────────────
_h1('4 — history_screen.dart  remove duplicate _clearAll')
txt = _read(SC / 'history_screen.dart')

OLD_FIRST_CLEAR = (
    "  // S28: Clear All confirmation dialog\n"
    "  Future<void> _clearAll() async {\n"
    "    final s = LangProvider.strings(context);\n"
    "    final confirmed = await showDialog<bool>(\n"
    "      context: context,\n"
    "      builder: (ctx) => AlertDialog(\n"
    "        backgroundColor: _tCard,\n"
    "        shape: RoundedRectangleBorder(\n"
    "          borderRadius: BorderRadius.circular(14)),\n"
    "        title: Text(s.clearAll,\n"
    "          style: const TextStyle(color: Color(0xFFD4AF37))),\n"
    "        content: Text(s.clearAllConfirm,\n"
    "          style: TextStyle(color: _tText)), // S32-BUG6-FIX: theme-aware\n"
    "        actions: [\n"
    "          TextButton(\n"
    "            onPressed: () => Navigator.pop(ctx, false),\n"
    "            child: Text(s.ar ? 'لا' : 'No',\n"
    "              style: TextStyle(color: _tSub))), // S32-BUG6-FIX\n"
    "          TextButton(\n"
    "            onPressed: () => Navigator.pop(ctx, true),\n"
    "            child: Text(s.ar ? 'احذف' : 'Delete',\n"
    "              style: const TextStyle(color: Color(0xFFF85149)))),\n"
    "        ]));\n"
    "    if (confirmed == true && mounted) {\n"
    "      await ApiService.clearAllJobRecords();\n"
    "      setState(() => _jobs = []);\n"
    "    }\n"
    "  }\n"
)
if OLD_FIRST_CLEAR in txt:
    txt = txt.replace(OLD_FIRST_CLEAR, '', 1)
    _ok('First (old) _clearAll removed')
    _rec('4', 'history duplicate _clearAll removed', '[OK] PASS')
else:
    _skip('old _clearAll already removed or pattern mismatch')
    # Try generic: remove first _clearAll method
    import re
    # Find all _clearAll method positions
    pattern = r'  // S28: Clear All confirmation dialog\n  Future<void> _clearAll\(\) async \{[^}]+?\}(?:\n    \}\n  \})?'
    matches = list(re.finditer(r'  Future<void> _clearAll\(\) async \{', txt))
    if len(matches) >= 2:
        # Remove content from first match to just before second match
        start = matches[0].start()
        # Find the closing of the first method
        depth = 0
        i = matches[0].start()
        found_end = -1
        while i < matches[1].start():
            if txt[i] == '{': depth += 1
            elif txt[i] == '}':
                depth -= 1
                if depth == 0:
                    found_end = i + 1
                    break
            i += 1
        if found_end > 0:
            # Also remove preceding comment line if any
            pre = txt[:start]
            if pre.rstrip().endswith('_clearAll') or '// S28' in pre[-200:]:
                # Find start of comment
                comment_start = pre.rfind('\n  // S28')
                if comment_start > 0:
                    start = comment_start + 1
            txt = txt[:start] + txt[found_end:].lstrip('\n')
            _ok('Removed first _clearAll via regex')
            _rec('4', 'history _clearAll removed (regex)', '[OK] PASS')
        else:
            _err('Could not find end of first _clearAll')
            _rec('4', 'history _clearAll remove', '[XX] FAIL')
    else:
        _skip('Only one _clearAll, nothing to do')
        _rec('4', 'history _clearAll', '[--] SKIP')

_write(SC / 'history_screen.dart', txt)


# ─────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────
_h1('SUMMARY')
print(f"\n  {'Step':<6}  {'Label':<48}  Result")
print(f"  {'----':<6}  {'-----':<48}  ------")
for sid, label, result in _log:
    print(f'  {sid:<6}  {label:<48}  {result}')
passed  = sum(1 for _,_,r in _log if '[OK]' in r)
skipped = sum(1 for _,_,r in _log if '[--]' in r)
failed  = sum(1 for _,_,r in _log if '[XX]' in r)
_h1(f'Done — {passed} PASS  {skipped} SKIP  {failed} FAIL')
print('  flutter pub get && flutter build apk --release --no-tree-shake-icons\n')
