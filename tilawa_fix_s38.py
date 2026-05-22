#!/usr/bin/env python3
"""
tilawa_fix_s38.py  —  close _progressCard Container + design upgrades
====================================================================
FIX   home_screen.dart line ~1530: _progressCard's arrow function
      Container was never closed. After the Column closes with `]),`
      the Container needs `  );` to end the arrow function.
      Depth trace at line 1529: (+1 [+1) — Container open, Column.children open.
      Line 1530 `]),` closes Column.children `]` and Column `)`.
      Still need `  );` for Container.

DESIGN-1  Progress % text → ShaderMask gold-to-white gradient, larger font
DESIGN-2  Cancel button  → teal-bordered container, Sacred Cosmos palette
DESIGN-3  Status text    → slightly brighter colour, tracking letter-spacing

Run:
  cp /sdcard/Download/tilawa_fix_s38.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s38.py 2>&1 | tee /sdcard/Download/fix_s38.txt
  git add -A && git commit -m "S38: close Container in _progressCard; sacred-cosmos progress card polish" && git push
"""

from pathlib import Path
from datetime import datetime

SC   = Path.home() / 'tilawa-enhancer/lib/screens'
_log = []

def _h(t):  print(f'\n{"="*62}\n  {t}\n{"="*62}')
def _ok(m): print(f'  OK  {m}'); _log.append(('OK', m))
def _xx(m): print(f'  XX  {m}'); _log.append(('XX', m))
def _sk(m): print(f'  --  {m}'); _log.append(('SK', m))

def rep(txt, old, new, lbl):
    if old not in txt:
        _xx(f'NOT FOUND — {lbl}')
        return txt, False
    _ok(lbl)
    return txt.replace(old, new, 1), True

_h(f'tilawa_fix_s38.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

htxt = (SC / 'home_screen.dart').read_text(encoding='utf-8')

# ══════════════════════════════════════════════════════════════════
# FIX — close _progressCard's Container
# The arrow function `Widget _progressCard(S s) => Container(` needs
# `  );` after the Column closes with `]),`.
# ══════════════════════════════════════════════════════════════════
_h('FIX — insert Container close after Column ])')

MARK_CLOSED = '  );  // S38-CONTAINER-CLOSE'

if MARK_CLOSED in htxt:
    _sk('Container close already present')
else:
    OLD_COL_CLOSE = (
        '    ]),  // S37-PAREN-FIX (restored structural ) — S35 FIX-A2 over-stripped)\n'
        '\n'
        '  // ── RESULT + DOWNLOAD BUTTON'
    )
    NEW_COL_CLOSE = (
        '    ]),  // S37-PAREN-FIX (restored structural ) — S35 FIX-A2 over-stripped)\n'
        '  );  // S38-CONTAINER-CLOSE\n'
        '\n'
        '  // ── RESULT + DOWNLOAD BUTTON'
    )
    htxt, ok = rep(htxt, OLD_COL_CLOSE, NEW_COL_CLOSE,
                   'Container );  after Column ])')
    if not ok:
        # Fallback: no blank line between ]), and comment
        OLD2 = (
            '    ]),  // S37-PAREN-FIX (restored structural ) — S35 FIX-A2 over-stripped)\n'
            '  // ── RESULT + DOWNLOAD BUTTON'
        )
        NEW2 = (
            '    ]),  // S37-PAREN-FIX (restored structural ) — S35 FIX-A2 over-stripped)\n'
            '  );  // S38-CONTAINER-CLOSE\n'
            '\n'
            '  // ── RESULT + DOWNLOAD BUTTON'
        )
        htxt, ok = rep(htxt, OLD2, NEW2, 'Container );  (no-blank-line fallback)')


# ══════════════════════════════════════════════════════════════════
# DESIGN-1 — Progress percentage: ShaderMask gold gradient + larger font
# Old: plain Text with Color(0xFFD4AF37), fontSize: 14
# New: ShaderMask gold→cream gradient, fontSize: 18, bold
# ══════════════════════════════════════════════════════════════════
_h('DESIGN-1 — Progress % ShaderMask gold gradient')

MARK_D1 = '// S38-PCT-SHADER'

if MARK_D1 in htxt:
    _sk('% ShaderMask already applied')
else:
    OLD_PCT = (
        "        Text(_isMerging ? '...' : '${(_progress * 100).toInt()}%',\n"
        "          style: const TextStyle(\n"
        "            color: Color(0xFFD4AF37),\n"
        "            fontWeight: FontWeight.bold, fontSize: 14)),"
    )
    NEW_PCT = (
        "        ShaderMask( // S38-PCT-SHADER\n"
        "          shaderCallback: (b) => const LinearGradient(\n"
        "            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),\n"
        "          child: Text(_isMerging ? '...' : '${(_progress * 100).toInt()}%',\n"
        "            style: const TextStyle(\n"
        "              color: Colors.white,\n"
        "              fontWeight: FontWeight.bold, fontSize: 18))),"
    )
    htxt, _ = rep(htxt, OLD_PCT, NEW_PCT, '% text → ShaderMask gold gradient')


# ══════════════════════════════════════════════════════════════════
# DESIGN-2 — Cancel button: teal-bordered Sacred Cosmos style
# ══════════════════════════════════════════════════════════════════
_h('DESIGN-2 — Cancel button Sacred Cosmos restyle')

MARK_D2 = '// S38-CANCEL-STYLE'

if MARK_D2 in htxt:
    _sk('Cancel button already restyled')
else:
    OLD_CANCEL = (
        "      TextButton.icon(\n"
        "        onPressed: _cancelProcessing,\n"
        "        style: TextButton.styleFrom(\n"
        "          padding: const EdgeInsets.symmetric(vertical: 4)),\n"
        "        icon: const Icon(Icons.cancel_outlined, size: 16,\n"
        "          color: Color(0xFF8B949E)),\n"
        "        label: Text(s.cancelBtn,\n"
        "          style: const TextStyle(color: Color(0xFF8B949E), fontSize: 12)),\n"
        "      ),"
    )
    NEW_CANCEL = (
        "      Container( // S38-CANCEL-STYLE\n"
        "        decoration: BoxDecoration(\n"
        "          border: Border.all(\n"
        "            color: const Color(0xFF1B6B80).withOpacity(0.35)),\n"
        "          borderRadius: BorderRadius.circular(8)),\n"
        "        child: TextButton.icon(\n"
        "          onPressed: _cancelProcessing,\n"
        "          style: TextButton.styleFrom(\n"
        "            padding: const EdgeInsets.symmetric(\n"
        "              horizontal: 12, vertical: 4),\n"
        "            minimumSize: Size.zero),\n"
        "          icon: const Icon(Icons.cancel_outlined, size: 14,\n"
        "            color: Color(0xFF6B9EAE)),\n"
        "          label: Text(s.cancelBtn,\n"
        "            style: const TextStyle(\n"
        "              color: Color(0xFF6B9EAE), fontSize: 11)),\n"
        "        )),"
    )
    htxt, _ = rep(htxt, OLD_CANCEL, NEW_CANCEL,
                  'Cancel button → teal-bordered Sacred Cosmos')


# ══════════════════════════════════════════════════════════════════
# DESIGN-3 — Status text: brighter + letter-spacing
# ══════════════════════════════════════════════════════════════════
_h('DESIGN-3 — Status text brightness + tracking')

MARK_D3 = '// S38-STATUS-STYLE'

if MARK_D3 in htxt:
    _sk('Status text already restyled')
else:
    OLD_STATUS = (
        "              style: const TextStyle(\n"
        "                color: _textA, fontSize: 13)),"
    )
    NEW_STATUS = (
        "              style: const TextStyle( // S38-STATUS-STYLE\n"
        "                color: Color(0xFFCFD8DC),\n"
        "                fontSize: 13, letterSpacing: 0.2)),"
    )
    htxt, _ = rep(htxt, OLD_STATUS, NEW_STATUS,
                  'Status text → brighter + letter-spacing')


# ══════════════════════════════════════════════════════════════════
# Save + summary
# ══════════════════════════════════════════════════════════════════
_h('Saving home_screen.dart')
(SC / 'home_screen.dart').write_text(htxt, encoding='utf-8')
_ok('Saved')

_h('SUMMARY')
ok_n = sum(1 for s, _ in _log if s == 'OK')
sk_n = sum(1 for s, _ in _log if s == 'SK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
for s, l in _log:
    icon = 'OK' if s == 'OK' else ('--' if s == 'SK' else 'XX')
    print(f'  {icon}  {l}')
_h(f'{ok_n} OK   {sk_n} SKIP   {xx_n} FAIL')

if xx_n == 0:
    print("""
  git add -A && git commit -m "S38: close Container in _progressCard; sacred-cosmos progress card polish" && git push
""")
else:
    print('\n  Some anchors not found — paste output back to Claude.\n')
