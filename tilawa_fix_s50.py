#!/usr/bin/env python3
"""tilawa_fix_s50 — exact anchors from sed output"""
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = HS.read_text(encoding='utf-8')
_log = []

def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX',l))
def rep(old, new, lbl):
    global txt
    if old in txt: txt = txt.replace(old, new, 1); ok(lbl)
    else: xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*54}\n  tilawa_fix_s50  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*54}')

# ── A: Header subtitle (exact lines 836-841) ──────────────────────────────────
rep(
    "            child: Text(s.subtitle,\n"
    "              style: const TextStyle(\n"
    "                color: _textB, fontSize: 10, letterSpacing: 2.0))),",
    "            child: RichText(\n"
    "              text: TextSpan(\n"
    "                style: const TextStyle(\n"
    "                  color: _textB, fontSize: 10, letterSpacing: 1.5),\n"
    "                children: [\n"
    "                  TextSpan(text: s.subtitle),\n"
    "                  const TextSpan(text: '  \u00b7  ',\n"
    "                    style: TextStyle(color: Color(0xFF1DB898))),\n"
    "                  TextSpan(\n"
    "                    text: _engines.firstWhere(\n"
    "                      (e) => e.id == _engine,\n"
    "                      orElse: () => _engines.first).nameAr,\n"
    "                    style: const TextStyle(\n"
    "                      color: Color(0xFFD4AF37),\n"
    "                      fontWeight: FontWeight.w600)),\n"
    "                ])),",
    'Header subtitle + engine name')

# ── B: Engine card non-image row (exact from lines 1126-1171) ─────────────────
OLD_ROW = (
    "          if (e.imgAsset == null) Padding(\n"
    "            padding: const EdgeInsets.fromLTRB(12,11,12,11),\n"
    "            child: Row(children: [\n"
    "              AnimatedContainer(\n"
    "                duration: const Duration(milliseconds: 200),\n"
)
NEW_ROW = (
    "          // S50: JSX khatam card\n"
    "          if (e.imgAsset == null) Padding(\n"
    "            padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),\n"
    "            child: Row(crossAxisAlignment: CrossAxisAlignment.center,\n"
    "              children: [\n"
    "              _khatamBadge(col, e.score),\n"
    "              const SizedBox(width: 12),\n"
    "              Expanded(child: Column(\n"
    "                crossAxisAlignment: CrossAxisAlignment.start,\n"
    "                children: [\n"
    "                Row(crossAxisAlignment: CrossAxisAlignment.center, children: [\n"
    "                  Flexible(child: Text(e.nameAr,\n"
    "                    style: TextStyle(\n"
    "                      color: sel ? col : col.withOpacity(0.80),\n"
    "                      fontSize: 18, fontWeight: FontWeight.w700, height: 1.1))),\n"
    "                  if (e.badge.isNotEmpty) ...[\n"
    "                    const SizedBox(width: 8),\n"
    "                    Container(\n"
    "                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),\n"
    "                      decoration: BoxDecoration(\n"
    "                        color: col.withOpacity(0.12),\n"
    "                        borderRadius: BorderRadius.circular(5),\n"
    "                        border: Border.all(color: col.withOpacity(0.45))),\n"
    "                      child: Text(e.badge, style: TextStyle(\n"
    "                        color: col, fontSize: 8, fontWeight: FontWeight.bold,\n"
    "                        letterSpacing: 0.8))),\n"
    "                  ],\n"
    "                ]),\n"
    "                const SizedBox(height: 3),\n"
    "                Text(e.nameEn, style: TextStyle(\n"
    "                  color: const Color(0xFFF0E8D2).withOpacity(0.42),\n"
    "                  fontSize: 10.5, fontStyle: FontStyle.italic)),\n"
    "              ])),\n"
    "              const SizedBox(width: 8),\n"
    "              Container(\n"
    "                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),\n"
    "                decoration: BoxDecoration(\n"
    "                  color: col.withOpacity(0.12),\n"
    "                  borderRadius: BorderRadius.circular(8),\n"
    "                  border: Border.all(color: col.withOpacity(0.35))),\n"
    "                child: Text(e.id, style: TextStyle(\n"
    "                  color: col, fontSize: 9, fontWeight: FontWeight.w600,\n"
    "                  letterSpacing: 0.4))),\n"
    "            ])),\n"
    "          // S50-placeholder (old AnimatedContainer removed)\n"
    "          if (false) AnimatedContainer(\n"
    "                duration: const Duration(milliseconds: 200),\n"
)
rep(OLD_ROW, NEW_ROW, 'Engine card non-image → khatam JSX')

# ── C: Feature chips → per-engine color (exact lines 1209-1216) ───────────────
rep(
    "          decoration: BoxDecoration(\n"
    "            color: const Color(0xFF0A0C10),\n"
    "            borderRadius: BorderRadius.circular(6),\n"
    "            border: Border.all(color: _tBorder)),\n"
    "          child: Text(f, style: const TextStyle(\n"
    "            color: Color(0xFF8B949E), fontSize: 9)))).toList()),",
    "          decoration: BoxDecoration(\n"
    "            color: col.withOpacity(0.07),\n"
    "            borderRadius: BorderRadius.circular(6),\n"
    "            border: Border.all(color: col.withOpacity(0.28))),\n"
    "          child: Text(f, style: TextStyle(\n"
    "            color: col.withOpacity(0.75), fontSize: 9)))).toList()),",
    'Feature chips per-engine color')

# ── D: _khatamBadge widget (before _engineCard) ───────────────────────────────
KHATAM = (
    "  // ── KHATAM BADGE (S50) ─────────────────────────────────────────────────\n"
    "  Widget _khatamBadge(Color col, double score, {double size = 42}) {\n"
    "    return SizedBox(width: size, height: size,\n"
    "      child: Stack(alignment: Alignment.center, children: [\n"
    "        AnimatedBuilder(\n"
    "          animation: _glowCtrl,\n"
    "          builder: (_, __) {\n"
    "            final g = _glowCtrl.value;\n"
    "            return Stack(children: [\n"
    "              Positioned.fill(child: Container(\n"
    "                margin: const EdgeInsets.all(3),\n"
    "                decoration: BoxDecoration(\n"
    "                  borderRadius: BorderRadius.circular(2),\n"
    "                  color: col.withOpacity(0.12),\n"
    "                  border: Border.all(\n"
    "                    color: col.withOpacity(0.58 + 0.30 * g), width: 1.5),\n"
    "                  boxShadow: [BoxShadow(\n"
    "                    color: col.withOpacity(0.20 + 0.22 * g),\n"
    "                    blurRadius: 8 + 6 * g)]))),\n"
    "              Positioned.fill(child: Transform.rotate(\n"
    "                angle: pi / 4,\n"
    "                child: Container(\n"
    "                  margin: const EdgeInsets.all(3),\n"
    "                  decoration: BoxDecoration(\n"
    "                    borderRadius: BorderRadius.circular(2),\n"
    "                    color: col.withOpacity(0.05),\n"
    "                    border: Border.all(\n"
    "                      color: col.withOpacity(0.38 + 0.18 * g), width: 1))))),\n"
    "            ]);\n"
    "          }),\n"
    "        ShaderMask(\n"
    "          shaderCallback: (b) => LinearGradient(\n"
    "            colors: [col, col.withOpacity(0.65)],\n"
    "            begin: Alignment.topCenter, end: Alignment.bottomCenter,\n"
    "          ).createShader(b),\n"
    "          child: Text('\u2265\${score.toInt()}',\n"
    "            style: const TextStyle(\n"
    "              color: Colors.white, fontSize: 9.5, fontWeight: FontWeight.w800,\n"
    "              letterSpacing: 0.3))),\n"
    "      ]));\n"
    "  }\n"
    "\n"
    "  Widget _engineCard(_EngineData e, S s) {\n"
)
rep(
    "  Widget _engineCard(_EngineData e, S s) {\n",
    KHATAM,
    '_khatamBadge widget added')

HS.write_text(txt, encoding='utf-8')
ok('home_screen.dart saved')

print(f'\n{"="*54}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL')
print('\n  git add -A && git commit -m "S50: khatam engine cards + colored chips + engine name header" && git push\n')
