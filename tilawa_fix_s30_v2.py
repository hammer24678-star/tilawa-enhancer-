#!/usr/bin/env python3
"""
tilawa_fix_s30_v2.py — fix failed anchors + deeper design polish
"""
import re
from pathlib import Path
from datetime import datetime

REPO = Path.home() / 'tilawa-enhancer'
SC   = REPO / 'lib/screens'

def _h(t): print(f'\n{"═"*58}\n  {t}\n{"═"*58}')
def _ok(m): print(f'  ✅  {m}')
def _xx(m): print(f'  ❌  {m}')

def rep(txt, old, new, lbl):
    if old in txt:
        _ok(lbl); return txt.replace(old, new, 1), True
    _xx(f'NOT FOUND — {lbl}'); return txt, False

def rep_re(txt, pat, new, lbl, flags=re.DOTALL):
    m = re.search(pat, txt, flags)
    if m:
        _ok(lbl); return txt[:m.start()] + new + txt[m.end():], True
    _xx(f'NO MATCH — {lbl}'); return txt, False

_h(f'tilawa_fix_s30_v2  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ═══════════════════════════════════════════════════════════
# home_screen.dart
# ═══════════════════════════════════════════════════════════
_h('home_screen.dart')
txt = (SC/'home_screen.dart').read_text(encoding='utf-8')

# A — _iconBtn (regex — handles any whitespace/color variations)
MARKER_A = '// S29-ICONBTN-SACRED'
if MARKER_A not in txt:
    txt, ok = rep_re(txt,
        r'Widget _iconBtn\(IconData icon, VoidCallback onTap\) => \w+\([^\)]*\)[^;]+;',
        '''Widget _iconBtn(IconData icon, VoidCallback onTap) {
    // S29-ICONBTN-SACRED
    return GestureDetector(
      onTap: onTap,
      child: AnimatedBuilder(
        animation: _glowCtrl,
        builder: (_, __) => Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: _bgCard, shape: BoxShape.circle,
            border: Border.all(
              color: _teal.withOpacity(0.28 + 0.22 * _glowCtrl.value)),
            boxShadow: [BoxShadow(
              color: _teal.withOpacity(0.08 + 0.08 * _glowCtrl.value),
              blurRadius: 10)]),
          child: Icon(icon, color: _textB, size: 20))));
  }''',
        '_iconBtn → glowing teal circle')
else:
    _ok('_iconBtn already Sacred Cosmos')

# B — Engine card decoration (regex)
MARKER_B = '// S29-ENGCARD-DECO'
if MARKER_B not in txt:
    txt, ok = rep_re(txt,
        r'(child: AnimatedContainer\(\s*duration[^,]+,\s*margin[^,]+,\s*decoration: BoxDecoration\()\s*color: sel \? _tCard : Colors\.transparent,\s*borderRadius: BorderRadius\.circular\(11\),\s*border: Border\.all\(\s*color: sel \? col : _tBorder,\s*width: sel \? 1\.4 : 0\.8\)\),',
        r'''\1
            // S29-ENGCARD-DECO
            color: sel ? col.withOpacity(0.07) : Colors.transparent,
            borderRadius: BorderRadius.circular(13),
            border: Border.all(color: sel ? col : _teal.withOpacity(0.18),
              width: sel ? 1.8 : 0.7),
            boxShadow: sel ? [BoxShadow(
              color: col.withOpacity(0.15), blurRadius: 16)] : null),''',
        'Engine card: gold glow + tint when selected')
else:
    _ok('Engine card already Sacred Cosmos')

# C — File card decoration (regex — matches color: _tCard + border)
MARKER_C = '// S29-FILECARD-DECO'
if MARKER_C not in txt:
    txt, ok = rep_re(txt,
        r'(margin: const EdgeInsets\.fromLTRB\(16,10,16,4\),\s*padding: const EdgeInsets\.all\(24\),\s*decoration: BoxDecoration\()(\s*color: _tCard,\s*borderRadius: BorderRadius\.circular\(14\),\s*border: Border\.all\(\s*color: _file != null \? _tGold : _tBorder,\s*width: 1\.5\),\s*boxShadow: const \[BoxShadow\([^)]+\)\]\),)',
        r'''\1 // S29-FILECARD-DECO
          color: _file != null ? _bgSurface : _bgDeep,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: _file != null
              ? _gold
              : _teal.withOpacity(0.28),
            width: _file != null ? 1.8 : 0.8),
          boxShadow: _file != null ? [BoxShadow(
            color: _gold.withOpacity(0.14), blurRadius: 22)] : null),''',
        'File card: Sacred Cosmos teal/gold border')
else:
    _ok('File card already Sacred Cosmos')

# D — Process ElevatedButton → gradient container
MARKER_D = '// S29-PROCBTN'
if MARKER_D not in txt:
    OLD_PROC = (
        '            SizedBox(width: double.infinity,\n'
        '              child: ElevatedButton(\n'
        '                onPressed: (_busy || !_serverUp) ? null : _process,'
    )
    NEW_PROC = (
        '            // S29-PROCBTN\n'
        '            SizedBox(width: double.infinity,\n'
        '              child: Container(\n'
        '                decoration: BoxDecoration(\n'
        '                  borderRadius: BorderRadius.circular(13),\n'
        '                  gradient: (_busy || !_serverUp) ? null\n'
        '                    : const LinearGradient(\n'
        '                        colors: [Color(0xFF7A5C08), _gold,\n'
        '                                 _goldLight, _gold],\n'
        '                        stops: [0.0, 0.3, 0.6, 1.0]),\n'
        '                  color: (_busy || !_serverUp)\n'
        '                    ? _gold.withOpacity(0.22) : null,\n'
        '                  boxShadow: (_busy || !_serverUp) ? null : [BoxShadow(\n'
        '                    color: _gold.withOpacity(0.30),\n'
        '                    blurRadius: 16, offset: const Offset(0, 5))]),\n'
        '                child: Material(color: Colors.transparent,\n'
        '                  child: InkWell(\n'
        '                    borderRadius: BorderRadius.circular(13),\n'
        '                    onPressed: (_busy || !_serverUp) ? null : () {\n'
        '                      HapticFeedback.mediumImpact(); _process();\n'
        '                    },'
    )
    txt, ok = rep(txt, OLD_PROC, NEW_PROC, 'Process btn → gold gradient')
    if ok:
        # Fix the closing — ElevatedButton had specific closing, wrap with extra )
        OLD_CLOSE_BTN = (
            "                  : Text('${s.process} — $_engine',\n"
            "                      style: const TextStyle(\n"
            "                        fontWeight: FontWeight.bold, fontSize: 15)))),\n"
        )
        NEW_CLOSE_BTN = (
            "                    child: _busy\n"
            "                      ? const Padding(\n"
            "                          padding: EdgeInsets.symmetric(vertical: 15),\n"
            "                          child: SizedBox(width: 18, height: 18,\n"
            "                            child: CircularProgressIndicator(\n"
            "                              strokeWidth: 2.2,\n"
            "                              color: Color(0xFF061218))))\n"
            "                      : Padding(\n"
            "                          padding: const EdgeInsets.symmetric(vertical: 15),\n"
            "                          child: Text('${s.process} — $_engine',\n"
            "                            textAlign: TextAlign.center,\n"
            "                            style: TextStyle(\n"
            "                              color: (_busy||!_serverUp)\n"
            "                                ? _textC : const Color(0xFF061218),\n"
            "                              fontWeight: FontWeight.w900,\n"
            "                              fontSize: 15)))))),\n"
        )
        # Use regex to replace the child of ElevatedButton
        txt, _ = rep_re(txt,
            r'child: _busy\s*\?.*?Text\(.*?fontSize: 15\)\)\)\),\s*\],',
            NEW_CLOSE_BTN + '          ],',
            'Process btn child content')
else:
    _ok('Process btn already gradient')

# E — Engine selector header row: bigger label
OLD_ENGSEL_HDR = (
    '          Text(s.chooseEngine, style: const TextStyle(\n'
    '            color: Color(0xFF8B949E), fontSize: 11, letterSpacing: 1.5)),'
)
NEW_ENGSEL_HDR = (
    '          Text(s.chooseEngine, style: const TextStyle(\n'
    '            color: _textB, fontSize: 11, letterSpacing: 1.8,\n'
    '            fontWeight: FontWeight.w600)),'
)
txt, _ = rep(txt, OLD_ENGSEL_HDR, NEW_ENGSEL_HDR, 'Engine selector label bolder')

# F — Server banner: use Sacred Cosmos tokens for text colors
OLD_BAN_TXT = (
    '              color: _serverUp\n'
    '                ? const Color(0xFF3FB950)\n'
    '                : _waking\n'
    '                  ? _tGold\n'
    '                  : const Color(0xFFF85149),'
)
NEW_BAN_TXT = (
    '              color: _serverUp ? _ok\n'
    '                : _waking ? _gold : _err,'
)
txt, _ = rep(txt, OLD_BAN_TXT, NEW_BAN_TXT, 'Server banner text color tokens')

# G — Wake button: sacred cosmos style
OLD_WAKE = (
    '                      color: const Color(0xFF1A1000),\n'
    '                      borderRadius: BorderRadius.circular(8),\n'
    '                      border: Border.all(\n'
    '                        color: _tGold.withOpacity(0.6))),'
)
NEW_WAKE = (
    '                      color: _goldMuted,\n'
    '                      borderRadius: BorderRadius.circular(10),\n'
    '                      border: Border.all(\n'
    '                        color: _gold.withOpacity(0.55))),'
)
txt, _ = rep(txt, OLD_WAKE, NEW_WAKE, 'Wake button Sacred Cosmos style')

# H — Bottom history row border
OLD_BTM_BRD = (
    '            decoration: BoxDecoration(\n'
    '              border: Border.all(color: _tBorder)),'
)
NEW_BTM_BRD = (
    '            decoration: BoxDecoration(\n'
    '              border: Border.all(color: _teal.withOpacity(0.22))),'
)
txt, _ = rep(txt, OLD_BTM_BRD, NEW_BTM_BRD, 'History btn border teal')

# I — History icon color
txt, _ = rep(txt,
    "            const Icon(Icons.history_rounded,\n              color: Color(0xFF8B949E), size: 18),",
    "            const Icon(Icons.history_rounded, color: _textB, size: 18),",
    'History icon color _textB')

(SC/'home_screen.dart').write_text(txt, encoding='utf-8')
_ok('home_screen.dart ✓')


# ═══════════════════════════════════════════════════════════
# Logo instructions
# ═══════════════════════════════════════════════════════════
_h('LOGO — Manual step required')
print("""
  The new logo must be placed manually:

    cp ~/downloads/1000044971.jpg ~/tilawa-enhancer/assets/images/logo.png

  or if saved as .jpg:
    cp /sdcard/Download/1000044971.jpg ~/tilawa-enhancer/assets/images/logo.png

  Then commit + push.
""")

_h('Push')
print('  git add -A && git commit -m "S30v2: design polish + logo" && git push')
