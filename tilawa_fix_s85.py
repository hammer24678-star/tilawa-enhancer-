#!/usr/bin/env python3
"""
tilawa_fix_s85.py  —  S85: fix local mode stuck after 100% + engine greying
============================================================================
Bug 1: After _processLocal() completes, _progress=1.0 so the progress card
       stays visible forever (_busy || _progress > 0 is still true).
       User can't pick a new file or process again.
Fix:   Reset _progress=0 when _processLocal() completes successfully.

Bug 2: Wrong-mode engines (server engines in local mode, local engines in
       server mode) only get a slightly dimmer background. No AbsorbPointer,
       no Opacity — they're still fully tappable and look almost normal.
Fix:   Wrap engine card in Opacity(0.35) + AbsorbPointer when wrong mode.

Run:
  cp /sdcard/Download/tilawa_fix_s85.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s85.py 2>&1 | tee /sdcard/Download/fix_s85.txt
  git add lib/screens/home_screen.dart
  git commit -m "S85: fix local stuck after 100% + grey wrong-mode engines"
  git push
"""
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
_log = []
def _h(t):  print(f'\n{"="*62}\n  {t}\n{"="*62}')
def ok(m):  print(f'  OK  {m}'); _log.append(('OK', m))
def xx(m):  print(f'  XX  {m}'); _log.append(('XX', m))

_h(f'tilawa_fix_s85.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

txt = HS.read_text(encoding='utf-8')

if '// S85' in txt:
    print('  -- S85 already applied'); exit(0)

# ── FIX 1: reset _progress=0 when local engine completes ─────────────────
# Line ~880: setState({ _busy=false, _status='Local engine complete' })
OLD1 = "        setState(() { _busy = false; _status = 'Local engine complete'; });"
NEW1 = "        setState(() { _busy = false; _progress = 0; _status = 'Local engine complete'; });  // S85: reset progress so UI unlocks"

if OLD1 in txt:
    txt = txt.replace(OLD1, NEW1, 1)
    ok('Reset _progress=0 on local engine complete')
else:
    xx("'Local engine complete' setState anchor not found")

# ── FIX 2: wrap wrong-mode engine card in Opacity+AbsorbPointer ──────────
# The GestureDetector wraps AnimatedContainer. We wrap the whole
# GestureDetector with Opacity+AbsorbPointer when engine is wrong mode.
# The existing onTap already auto-switches mode on tap — we keep that but
# visually grey out non-matching engines properly.
OLD2 = '''\
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick(); // S30-P1
        setState(() {
              _engine = e.id;
              // S84: auto-switch mode to match engine requirement
              if (e.localOnly && !_localMode) {
                _localMode = true;
              } else if (!e.localOnly && _localMode) {
                _localMode = false;
              }
            });
        ApiService.saveLastEngine(e.id); // S28-T2: persist
      },'''

NEW2 = '''\
    final _wrongMode = (_localMode && !e.localOnly) || (!_localMode && e.localOnly);  // S85
    return Opacity(
      opacity: _wrongMode ? 0.38 : 1.0,  // S85: grey wrong-mode engines
      child: AbsorbPointer(
        absorbing: false,  // S85: still tappable to auto-switch mode
        child: GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick(); // S30-P1
        setState(() {
              _engine = e.id;
              // S84: auto-switch mode to match engine requirement
              if (e.localOnly && !_localMode) {
                _localMode = true;
              } else if (!e.localOnly && _localMode) {
                _localMode = false;
              }
            });
        ApiService.saveLastEngine(e.id); // S28-T2: persist
      },'''

if OLD2 in txt:
    txt = txt.replace(OLD2, NEW2, 1)
    # Now close the extra Opacity+AbsorbPointer+child wrappers at end of _engineCard
    # The method ends with: ]);  }  — add closing ));
    # Find the closing of GestureDetector child and add )); after it
    # The last line of _engineCard is the closing of GestureDetector
    # We look for the specific end pattern
    OLD2_END = '''      child: AnimatedContainer('''
    # We only need to close the extra child: wrapping
    # The GestureDetector closes at method end — add )); before final }
    # Find the _engineCard closing brace
    import re
    # Add closing )); just before the final } of _engineCard
    # Pattern: the last }; before next Widget method
    txt = re.sub(
        r'(  Widget _engineCard\(_EngineData e, S s\) \{.*?)(^\s*\}\s*\n\s*Widget )',
        lambda m: m.group(1).rstrip() + '\n      )));  // S85: close Opacity+AbsorbPointer+child\n  }\n\n  Widget ',
        txt, count=1, flags=re.DOTALL | re.MULTILINE
    )
    ok('Wrapped engine card in Opacity(0.38) for wrong-mode engines')
else:
    xx('GestureDetector onTap anchor not found')

# ── Also fix the redundant _wrongMode check in AnimatedContainer decoration
# Remove the existing color logic that tried to dim (it's now handled by Opacity)
OLD3 = '''          color: sel
            ? col.withValues(alpha: 0.10)
            : (_localMode && !e.localOnly) || (!_localMode && e.localOnly)
              ? const Color(0xFF0D2B22).withValues(alpha: 0.28)
              : const Color(0xFF0D2B22).withValues(alpha: 0.70),'''

NEW3 = '''          color: sel
            ? col.withValues(alpha: 0.10)
            : const Color(0xFF0D2B22).withValues(alpha: 0.70),  // S85: grey handled by Opacity wrapper'''

if OLD3 in txt:
    txt = txt.replace(OLD3, NEW3, 1)
    ok('Removed redundant inline alpha dim from AnimatedContainer')
else:
    xx('AnimatedContainer color anchor not found')

# ── Save ──────────────────────────────────────────────────────────────────
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
_h('SUMMARY')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
_h(f'{ok_n} OK   {xx_n} FAIL')

if xx_n == 0:
    HS.write_text(txt, encoding='utf-8')
    ok('home_screen.dart saved')
    print("""
  git add lib/screens/home_screen.dart
  git commit -m "S85: fix local stuck after 100% + grey wrong-mode engines"
  git push
""")
else:
    print('\n  NOT saved — paste output to Claude.\n')
