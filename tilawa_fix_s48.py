#!/usr/bin/env python3
"""
tilawa_fix_s48.py — Full JSX design implementation across all screens
=====================================================================
Implements tilawa_ultimate_jsx.txt design in Flutter:
  A  _khatamBadge() widget — two rotated squares + score (Khatam component)
  B  Engine card non-image: replace radio+id row with Khatam+AR name+EN+version
  C  Engine expanded chips: per-engine color border + bg (not grey)
  D  Header subtitle pill: show selected engine AR name
  E  Result card: replace ScoreArcPainter with large khatam + gradient score text

Anchors verified from tilawa_dart_dump.txt (updated post-S47, 2510+ lines):
  B: exact 12-sp string match  dart 1126-1171
  C: exact 8-sp string match   dart 1207-1216
  D: exact s.subtitle match    dart 839
  E: regex  dart 1631-1696     S30-R1 → SizedBox(height:14)
"""
import re
from pathlib import Path

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
_log = []

def ok(lbl): print(f'  OK  {lbl}'); _log.append(('OK', lbl))
def xx(lbl): print(f'  XX  NOT FOUND — {lbl}'); _log.append(('XX', lbl))

def rep(txt, old, new, lbl):
    if old in txt: ok(lbl); return txt.replace(old, new, 1)
    xx(lbl); return txt

htxt = HS.read_text(encoding='utf-8')

# ═══════════════════════════════════════════════════════════════════════════════
# A — Add _khatamBadge widget (before _engineCard)
# ═══════════════════════════════════════════════════════════════════════════════

KHATAM_BADGE = (
'    // ── KHATAM BADGE (S48) — two rotated gold squares with score ─────────────\n'
'    Widget _khatamBadge(Color col, double score, {double size = 42}) {\n'
'      return SizedBox(width: size, height: size,\n'
'        child: Stack(alignment: Alignment.center, children: [\n'
'          AnimatedBuilder(\n'
'            animation: _glowCtrl,\n'
'            builder: (_, __) {\n'
'              final g = _glowCtrl.value;\n'
'              return Stack(children: [\n'
'                Positioned.fill(child: Container(\n'
'                  margin: const EdgeInsets.all(3),\n'
'                  decoration: BoxDecoration(\n'
'                    borderRadius: BorderRadius.circular(2),\n'
'                    color: col.withOpacity(0.12),\n'
'                    border: Border.all(\n'
'                      color: col.withOpacity(0.58 + 0.30 * g), width: 1.5),\n'
'                    boxShadow: [BoxShadow(\n'
'                      color: col.withOpacity(0.20 + 0.22 * g),\n'
'                      blurRadius: 8 + 6 * g)]))),\n'
'                Positioned.fill(child: Transform.rotate(\n'
'                  angle: pi / 4,\n'
'                  child: Container(\n'
'                    margin: const EdgeInsets.all(3),\n'
'                    decoration: BoxDecoration(\n'
'                      borderRadius: BorderRadius.circular(2),\n'
'                      color: col.withOpacity(0.05),\n'
'                      border: Border.all(\n'
'                        color: col.withOpacity(0.38 + 0.18 * g), width: 1))))),\n'
'              ]);\n'
'            }),\n'
'          ShaderMask(\n'
'            shaderCallback: (b) => LinearGradient(\n'
'              colors: [col, col.withOpacity(0.65)],\n'
'              begin: Alignment.topCenter, end: Alignment.bottomCenter,\n'
'            ).createShader(b),\n'
'            child: Text(\'\\u2265${score.toInt()}\',\n'
'              style: const TextStyle(\n'
'                color: Colors.white, fontSize: 9.5, fontWeight: FontWeight.w800,\n'
'                letterSpacing: 0.3))),\n'
'        ]));\n'
'    }\n'
'\n'
)

htxt = rep(htxt,
    '    Widget _engineCard(_EngineData e, S s) {',
    KHATAM_BADGE + '    Widget _engineCard(_EngineData e, S s) {',
    'Add _khatamBadge widget method')

# ═══════════════════════════════════════════════════════════════════════════════
# B — Replace non-image engine card collapsed row with JSX-style khatam card
#     Anchor: exact text from dart lines 1126-1171 (dump verified)
# ═══════════════════════════════════════════════════════════════════════════════

OLD_CARD_ROW = (
'            if (e.imgAsset == null) Padding(\n'
'              padding: const EdgeInsets.fromLTRB(12,11,12,11),\n'
'              child: Row(children: [\n'
'                AnimatedContainer(\n'
'                  duration: const Duration(milliseconds: 200),\n'
'                  width: 18, height: 18,\n'
'                  decoration: BoxDecoration(\n'
'                    shape: BoxShape.circle,\n'
'                    border: Border.all(\n'
'                      color: sel ? col : _tBorder, width: 2),\n'
'                    color: sel ? col : Colors.transparent),\n'
'                  child: sel\n'
'                    ? const Icon(Icons.check, size: 10, color: Color(0xFF0A0C10))\n'
'                    : null),\n'
'                const SizedBox(width: 11),\n'
'                Expanded(child: Column(\n'
'                  crossAxisAlignment: CrossAxisAlignment.start,\n'
'                  children: [\n'
'                  Row(children: [\n'
'                    Text(e.id, style: TextStyle(\n'
'                      color: sel ? col : col.withOpacity(0.55),\n'
'                      fontWeight: FontWeight.bold, fontSize: 13)),\n'
'                    if (e.badge.isNotEmpty) ...[\n'
'                      const SizedBox(width: 6),\n'
'                      Container(\n'
'                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),\n'
'                        decoration: BoxDecoration(\n'
'                          color: bg, borderRadius: BorderRadius.circular(4),\n'
'                          border: Border.all(color: col.withOpacity(0.45))),\n'
'                        child: Text(e.badge, style: TextStyle(\n'
'                          color: col, fontSize: 8, fontWeight: FontWeight.bold))),\n'
'                    ],\n'
'                  ]),\n'
'                  const SizedBox(height: 2),\n'
'                  Text(s.ar ? e.nameAr : e.nameEn,\n'
'                    style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),\n'
'                ])),\n'
'                Column(crossAxisAlignment: CrossAxisAlignment.end, children: [\n'
"                  Text('\\u2265${e.score.toInt()}', style: TextStyle(\n"
'                    color: sel ? col : col.withOpacity(0.40),\n'
'                    fontWeight: FontWeight.w800, fontSize: 15)),\n'
"                  Text('/100', style: TextStyle(\n"
'                    color: col.withOpacity(sel ? 0.45 : 0.25),\n'
'                    fontSize: 8)),\n'
'                ]),\n'
'              ])),\n'
)

NEW_CARD_ROW = (
'            // S48: JSX-style khatam card (non-image engines)\n'
'            if (e.imgAsset == null) Padding(\n'
'              padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),\n'
'              child: Row(crossAxisAlignment: CrossAxisAlignment.start,\n'
'                children: [\n'
'                _khatamBadge(col, e.score),\n'
'                const SizedBox(width: 12),\n'
'                Expanded(child: Column(\n'
'                  crossAxisAlignment: CrossAxisAlignment.start,\n'
'                  children: [\n'
'                  Row(crossAxisAlignment: CrossAxisAlignment.center, children: [\n'
'                    Flexible(child: Text(e.nameAr,\n'
'                      style: TextStyle(\n'
'                        color: sel ? col : col.withOpacity(0.80),\n'
'                        fontSize: 18, fontWeight: FontWeight.w700, height: 1.1))),\n'
'                    if (e.badge.isNotEmpty) ...[\n'
'                      const SizedBox(width: 8),\n'
'                      Container(\n'
'                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),\n'
'                        decoration: BoxDecoration(\n'
'                          color: col.withOpacity(0.12),\n'
'                          borderRadius: BorderRadius.circular(5),\n'
'                          border: Border.all(color: col.withOpacity(0.45))),\n'
'                        child: Text(e.badge, style: TextStyle(\n'
'                          color: col, fontSize: 8, fontWeight: FontWeight.bold,\n'
'                          letterSpacing: 0.8))),\n'
'                    ],\n'
'                  ]),\n'
'                  const SizedBox(height: 3),\n'
'                  Text(e.nameEn, style: TextStyle(\n'
'                    color: const Color(0xFFF0E8D2).withOpacity(0.42),\n'
'                    fontSize: 10.5, fontStyle: FontStyle.italic)),\n'
'                ])),\n'
'                const SizedBox(width: 8),\n'
'                Container(\n'
'                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),\n'
'                  decoration: BoxDecoration(\n'
'                    color: col.withOpacity(0.12),\n'
'                    borderRadius: BorderRadius.circular(8),\n'
'                    border: Border.all(color: col.withOpacity(0.35))),\n'
'                  child: Text(e.id, style: TextStyle(\n'
'                    color: col, fontSize: 9, fontWeight: FontWeight.w600,\n'
'                    letterSpacing: 0.4))),\n'
'              ])),\n'
)

htxt = rep(htxt, OLD_CARD_ROW, NEW_CARD_ROW,
    'Engine card non-image: khatam + AR name + EN name + version badge')

# ═══════════════════════════════════════════════════════════════════════════════
# C — Engine expanded chips: per-engine color (not grey)
#     3 targeted replacements inside _engineExpanded
# ═══════════════════════════════════════════════════════════════════════════════

htxt = rep(htxt,
    '            children: e.features.map((f) => Container(\n'
    '            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),\n'
    '            decoration: BoxDecoration(\n'
    '              color: const Color(0xFF0A0C10),\n'
    '              borderRadius: BorderRadius.circular(6),\n'
    '              border: Border.all(color: _tBorder)),\n'
    '            child: Text(f, style: const TextStyle(\n'
    '              color: Color(0xFF8B949E), fontSize: 9)))).toList()),',
    '            children: e.features.map((f) => Container(\n'
    '            padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),\n'
    '            decoration: BoxDecoration(\n'
    '              color: col.withOpacity(0.07),\n'
    '              borderRadius: BorderRadius.circular(6),\n'
    '              border: Border.all(color: col.withOpacity(0.28))),\n'
    '            child: Text(f, style: TextStyle(\n'
    '              color: col.withOpacity(0.75), fontSize: 9)))).toList()),',
    'Expanded feature chips: per-engine color')

# ═══════════════════════════════════════════════════════════════════════════════
# D — Header subtitle pill: add selected engine AR name
#     Anchor: `child: Text(s.subtitle,` in _header (dart line 839)
# ═══════════════════════════════════════════════════════════════════════════════

htxt = rep(htxt,
    '              child: Text(s.subtitle,\n'
    '                style: const TextStyle(\n'
    '                  color: _textB, fontSize: 10, letterSpacing: 2.0))),',
    '              child: RichText(\n'
    '                text: TextSpan(\n'
    '                  style: const TextStyle(\n'
    '                    color: _textB, fontSize: 10, letterSpacing: 1.5),\n'
    '                  children: [\n'
    '                    TextSpan(text: s.subtitle),\n'
    '                    const TextSpan(text: \'  ·  \',\n'
    '                      style: TextStyle(color: _teal, letterSpacing: 0)),\n'
    '                    TextSpan(text: _selectedEngine.nameAr,\n'
    '                      style: const TextStyle(\n'
    '                        color: _textA, fontWeight: FontWeight.w600,\n'
    '                        letterSpacing: 0.5)),\n'
    '                  ]))),',
    'Header subtitle: show selected engine AR name')

# ═══════════════════════════════════════════════════════════════════════════════
# E — Result card: replace ScoreArcPainter section with large JSX khatam
#     Regex anchored: S30-R1 comment → const SizedBox(height: 14),
#     Dart lines 1631-1697 (verified from dump). Also adds labelAr variable.
# ═══════════════════════════════════════════════════════════════════════════════

NEW_RESULT_TOP = (
'          // ── S48: large khatam score display (JSX style) ──────────────────\n'
'          final labelAr = score >= 96 ? \'\\u0645\\u0645\\u062a\\u0627\\u0632\'\n'
'              : score >= 90 ? \'\\u0631\\u0627\\u0626\\u0639\'\n'
'              : score >= 85 ? \'\\u062c\\u064a\\u062f \\u062c\\u062f\\u0627\\u064b\'\n'
'              : score >= 78 ? \'\\u062c\\u064a\\u062f\'\n'
'              : \'\\u0645\\u0642\\u0628\\u0648\\u0644\';\n'
'          AnimatedBuilder(\n'
'            animation: Listenable.merge([_resultCtrl, _glowCtrl]),\n'
'            builder: (_, __) {\n'
'              final t = Curves.easeOutCubic.transform(_resultCtrl.value);\n'
'              final g = _glowCtrl.value;\n'
'              return Transform.scale(\n'
'                scale: 0.55 + 0.45 * t,\n'
'                child: Opacity(\n'
'                  opacity: t.clamp(0.0, 1.0),\n'
'                  child: SizedBox(width: 160, height: 160,\n'
'                    child: Stack(alignment: Alignment.center, children: [\n'
'                      // Outer ambient glow\n'
'                      Positioned.fill(child: Container(\n'
'                        decoration: BoxDecoration(\n'
'                          shape: BoxShape.circle,\n'
'                          boxShadow: [BoxShadow(\n'
'                            color: scoreColor.withOpacity(0.10 + 0.14 * g),\n'
'                            blurRadius: 36 + 22 * g, spreadRadius: 6)]))),\n'
'                      // Burst particles on high score\n'
'                      if (score >= 85) CustomPaint(\n'
'                        size: const Size(160, 160),\n'
'                        painter: _ScoreBurstPainter(\n'
'                          progress: _resultCtrl.value, color: scoreColor)),\n'
'                      // Khatam square 1 (straight)\n'
'                      Positioned.fill(child: Container(\n'
'                        margin: const EdgeInsets.all(12),\n'
'                        decoration: BoxDecoration(\n'
'                          borderRadius: BorderRadius.circular(6),\n'
'                          color: scoreColor.withOpacity(0.10),\n'
'                          border: Border.all(\n'
'                            color: scoreColor.withOpacity(0.62 + 0.22 * g),\n'
'                            width: 2.0),\n'
'                          boxShadow: [BoxShadow(\n'
'                            color: scoreColor.withOpacity(0.28 + 0.24 * g),\n'
'                            blurRadius: 24 + 16 * g)]))),\n'
'                      // Khatam square 2 (rotated 45°)\n'
'                      Positioned.fill(child: Transform.rotate(\n'
'                        angle: pi / 4,\n'
'                        child: Container(\n'
'                          margin: const EdgeInsets.all(12),\n'
'                          decoration: BoxDecoration(\n'
'                            borderRadius: BorderRadius.circular(6),\n'
'                            color: scoreColor.withOpacity(0.04),\n'
'                            border: Border.all(\n'
'                              color: scoreColor.withOpacity(0.38 + 0.16 * g),\n'
'                              width: 1.5))))),\n'
'                      // Score text + bilingual label\n'
'                      Column(mainAxisSize: MainAxisSize.min, children: [\n'
'                        ShaderMask(\n'
'                          shaderCallback: (b) => LinearGradient(\n'
'                            begin: Alignment.topCenter,\n'
'                            end: Alignment.bottomCenter,\n'
'                            colors: [\n'
'                              const Color(0xFFF0D882),\n'
'                              scoreColor,\n'
'                              scoreColor.withOpacity(0.65)]).createShader(b),\n'
'                          child: Text(\n'
'                            \'${(score * t).toStringAsFixed(1)}\',\n'
'                            style: const TextStyle(\n'
'                              color: Colors.white, fontSize: 52,\n'
'                              fontWeight: FontWeight.w900,\n'
'                              height: 1.0, letterSpacing: -2))),\n'
'                        const SizedBox(height: 4),\n'
'                        Text(\n'
'                          s.ar ? labelAr : \'$label \\u00b7 $labelAr\',\n'
'                          style: const TextStyle(\n'
'                            color: Color(0xFF1DB898), fontSize: 13,\n'
'                            fontStyle: FontStyle.italic,\n'
'                            letterSpacing: 0.08)),\n'
'                      ]),\n'
'                    ]))));\n'
'            }),\n'
'          const SizedBox(height: 14),\n'
'\n'
'          // Engine used'
)

pattern_e = (
    r'          // S30-R1: score arc gauge\n'
    r'          AnimatedBuilder\(\n'
    r'            animation: _resultCtrl,\n'
    r'.*?'
    r'          const SizedBox\(height: 14\),\n'
    r'\n'
    r'          // Engine used'
)
new_htxt, n = re.subn(pattern_e, NEW_RESULT_TOP, htxt, count=1, flags=re.DOTALL)
if n == 1:
    htxt = new_htxt
    ok('Result card: large khatam with gradient score text')
else:
    xx('Result card regex — check S30-R1 comment + SizedBox(height:14) anchors')
    # Diag: show lines around score arc gauge
    for i, l in enumerate(htxt.splitlines()):
        if 'S30-R1' in l or 'score arc' in l:
            lo = max(0, i-1); hi = min(len(htxt.splitlines()), i+5)
            for j in range(lo, hi):
                print(f'      {j+1:5}  {repr(htxt.splitlines()[j][:100])}')
            break

# ═══════════════════════════════════════════════════════════════════════════════
HS.write_text(htxt, encoding='utf-8')
print('  → home_screen.dart saved')

ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
print(f'\n  {"✅ All OK" if xx_n == 0 else "⚠  " + str(xx_n) + " FAILED"}  {ok_n} OK')
if xx_n:
    print('  Paste full output back to Claude for anchor repair.')
print(
    '\n  git add -A && git commit -m '
    '"S48: JSX khatam cards + engine name in header + large result khatam" && git push'
)
