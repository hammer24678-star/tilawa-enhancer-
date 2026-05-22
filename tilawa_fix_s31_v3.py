#!/usr/bin/env python3
"""tilawa_fix_s31_v3 — 4 remaining fixes with exact anchors"""
from pathlib import Path
from datetime import datetime

SC = Path.home() / 'tilawa-enhancer/lib/screens'
_log = []

def _h(t): print(f'\n{"═"*56}\n  {t}\n{"═"*56}')
def _ok(m): print(f'  ✅  {m}'); _log.append(('OK',m))
def _xx(m): print(f'  ❌  {m}'); _log.append(('XX',m))
def rep(txt, old, new, lbl):
    if old in txt: _ok(lbl); return txt.replace(old,new,1), True
    _xx(f'NOT FOUND — {lbl}'); return txt, False

_h(f'tilawa_fix_s31_v3  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

txt = (SC/'home_screen.dart').read_text(encoding='utf-8')

# ── 1. Rotating geo  (exact indent from diag line 624-625) ────────────────────
OLD_GEO = (
    "            child: IgnorePointer(\n"
    "              child: CustomPaint(painter: _GeoPainter())))),"
)
NEW_GEO = (
    "            child: IgnorePointer(\n"
    "              child: AnimatedBuilder(\n"
    "                animation: _geoRotCtrl,\n"
    "                builder: (_, __) => Transform.rotate(\n"
    "                  angle: _geoRotCtrl.value * 6.2832,\n"
    "                  child: CustomPaint(painter: _GeoPainter()))))),"
)
txt, _ = rep(txt, OLD_GEO, NEW_GEO, 'rotating geo background')

# ── 2. Engine card close Stack  (exact from diag lines 1006-1007) ────────────
# After AnimatedCrossFade closes, we have `        ]),` closing our injected Column.
# Need to add one more `      ]),` to close the Stack we injected.
OLD_ENG_CLOSE = (
    "            secondChild: _engineExpanded(e, s, col),\n"
    "          ),\n"
    "        ]),\n"
    "      ),\n"
    "    );\n"
    "  }"
)
NEW_ENG_CLOSE = (
    "            secondChild: _engineExpanded(e, s, col),\n"
    "          ),\n"
    "        ]), // end Column\n"
    "        ]), // end accent-bar Stack\n"
    "      ),\n"
    "    );\n"
    "  }"
)
txt, _ = rep(txt, OLD_ENG_CLOSE, NEW_ENG_CLOSE, 'engine card close Stack')

# ── 3. Score burst on existing arc gauge  (exact from diag lines 1489-1512) ──
# The arc gauge is already excellent — wrap SizedBox in Stack to add burst
OLD_SCORE = (
    "              SizedBox(\n"
    "                width: 148, height: 148,\n"
    "                child: CustomPaint(\n"
    "                  painter: _ScoreArcPainter(\n"
    "                    progress: t, score: score, color: scoreColor,\n"
    "                    trackColor: _tBorder),"
)
NEW_SCORE = (
    "              Stack(alignment: Alignment.center, children: [\n"
    "              // Burst particles on reveal\n"
    "              if (score >= 85) AnimatedBuilder(\n"
    "                animation: _resultCtrl,\n"
    "                builder: (_, __) => CustomPaint(\n"
    "                  size: const Size(170, 170),\n"
    "                  painter: _ScoreBurstPainter(\n"
    "                    progress: _resultCtrl.value,\n"
    "                    color: scoreColor))),\n"
    "              SizedBox(\n"
    "                width: 148, height: 148,\n"
    "                child: CustomPaint(\n"
    "                  painter: _ScoreArcPainter(\n"
    "                    progress: t, score: score, color: scoreColor,\n"
    "                    trackColor: _tBorder),"
)
txt, ok = rep(txt, OLD_SCORE, NEW_SCORE, 'score burst overlay on arc gauge')

if ok:
    # Close the extra Stack after the SizedBox closes
    OLD_SCORE_CLOSE = (
        "              const SizedBox(height: 10),\n"
        "              Container("
    )
    NEW_SCORE_CLOSE = (
        "              ]), // end burst Stack\n"
        "              const SizedBox(height: 10),\n"
        "              Container("
    )
    txt, _ = rep(txt, OLD_SCORE_CLOSE, NEW_SCORE_CLOSE, 'score burst Stack close')

# ── 4. Server dot ripple  (exact from diag lines 818-825) ────────────────────
OLD_DOT = (
    "            else\n"
    "              AnimatedContainer(\n"
    "                duration: const Duration(milliseconds: 400),\n"
    "                width: 8, height: 8,\n"
    "                decoration: BoxDecoration(\n"
    "                  shape: BoxShape.circle,\n"
    "                  color: _serverUp\n"
    "                    ? const Color(0xFF3FB950)\n"
    "                    : const Color(0xFFF85149))),"
)
NEW_DOT = (
    "            else\n"
    "              AnimatedBuilder(\n"
    "                animation: _glowCtrl,\n"
    "                builder: (_, __) {\n"
    "                  final t = _glowCtrl.value;\n"
    "                  final c = _serverUp ? _ok : _err;\n"
    "                  return SizedBox(width: 22, height: 22,\n"
    "                    child: Stack(alignment: Alignment.center, children: [\n"
    "                      if (_serverUp) Container(\n"
    "                        width: 8 + 12 * t, height: 8 + 12 * t,\n"
    "                        decoration: BoxDecoration(\n"
    "                          shape: BoxShape.circle,\n"
    "                          border: Border.all(\n"
    "                            color: c.withOpacity(0.6 * (1 - t)),\n"
    "                            width: 1.5))),\n"
    "                      Container(width: 8, height: 8,\n"
    "                        decoration: BoxDecoration(\n"
    "                          shape: BoxShape.circle, color: c,\n"
    "                          boxShadow: [BoxShadow(\n"
    "                            color: c.withOpacity(0.4 + 0.5 * t),\n"
    "                            blurRadius: 5 + 8 * t)])),\n"
    "                    ]));\n"
    "                }),"
)
txt, _ = rep(txt, OLD_DOT, NEW_DOT, 'server dot ripple ring')

(SC/'home_screen.dart').write_text(txt, encoding='utf-8')
_ok('home_screen.dart saved')

_h('SUMMARY')
for s,l in _log: print(f'  {"✅" if s=="OK" else "❌"}  {l}')
ok = sum(1 for s,_ in _log if s=='OK')
xx = sum(1 for s,_ in _log if s=='XX')
_h(f'{ok} ✅   {xx} ❌')
print('\n  git add -A && git commit -m "S31v3: all premium animations complete" && git push\n')
