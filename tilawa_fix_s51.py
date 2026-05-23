#!/usr/bin/env python3
"""
tilawa_fix_s51.py — Full Engine Identity + Per-Engine Theme
============================================================
1. Engine color map — each engine has its own identity color
2. Per-engine background gradient shift (replaces static void teal)
3. Image engine cards (tajalli/itiqan/isteidad) — full premium treatment:
   - Khatam overlay badge top-right (animated glow)
   - Large AR name + shimmer gradient
   - Engine ID pill bottom-right
   - Selected: glowing border + color tint overlay
4. BG gradient animates to engine's tint on select
5. _tBg/_tCard/_tBorder update per engine selection
"""
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = HS.read_text(encoding='utf-8')
_log = []

def ok(l): print(f'  OK  {l}'); _log.append(('OK', l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX', l))
def rep(old, new, lbl):
    global txt
    if old in txt: txt = txt.replace(old, new, 1); ok(lbl)
    else: xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s51  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# ═══════════════════════════════════════════════════════════
# 1. Add _engineColor() helper after _selectedEngine getter
#    Returns the identity color for any engine id
# ═══════════════════════════════════════════════════════════
rep(
    "  _EngineData get _selectedEngine =>\n"
    "    _engines.firstWhere((e) => e.id == _engine,\n"
    "      orElse: () => _engines.first);",

    "  _EngineData get _selectedEngine =>\n"
    "    _engines.firstWhere((e) => e.id == _engine,\n"
    "      orElse: () => _engines.first);\n"
    "\n"
    "  // Per-engine identity color — drives bg tint + glow\n"
    "  Color get _engineColor {\n"
    "    switch (_engine) {\n"
    "      case 'v11.0': return const Color(0xFFD4AF37); // التجلي — gold\n"
    "      case 'v11.1': return const Color(0xFF1DB898); // الإتقان — teal\n"
    "      case 'v11.2': return const Color(0xFFE8A030); // الاسترداد — amber\n"
    "      case 'v10.0': return const Color(0xFFB8860B); // Aetherion — dark gold\n"
    "      case 'v9.0':  return const Color(0xFF9B7FFF); // Evolution — violet\n"
    "      case 'v8.5':  return const Color(0xFF5BB8FF); // Honest — blue\n"
    "      case 'v8.0':  return const Color(0xFFFF7EA0); // Precision — rose\n"
    "      default:      return const Color(0xFFD4AF37);\n"
    "    }\n"
    "  }",
    '_engineColor getter added')

# ═══════════════════════════════════════════════════════════
# 2. Per-engine background gradient (replaces static void teal)
#    Exact anchor: lines 642-644 in dump
# ═══════════════════════════════════════════════════════════
rep(
    "            colors: dark\n"
    "              ? [const Color(0xFF020D0C), const Color(0xFF051A14)]\n"
    "              : [const Color(0xFFFAF7EE), const Color(0xFFF5F0E0)]),",

    "            colors: dark\n"
    "              ? [Color.lerp(\n"
    "                  const Color(0xFF020D0C),\n"
    "                  _engineColor.withOpacity(1),\n"
    "                  0.06)!,\n"
    "                 Color.lerp(\n"
    "                  const Color(0xFF020D0C),\n"
    "                  _engineColor.withOpacity(1),\n"
    "                  0.03)!]\n"
    "              : [const Color(0xFFFAF7EE), const Color(0xFFF5F0E0)]),",
    'Per-engine bg gradient tint')

# ═══════════════════════════════════════════════════════════
# 3. Rebuild image engine card with premium treatment
#    Exact anchor from dump lines 1057-1125
# ═══════════════════════════════════════════════════════════
OLD_IMG_CARD = (
    "            if (e.imgAsset != null) Stack(children: [\n"
    "              ClipRRect(\n"
    "                borderRadius: const BorderRadius.only(\n"
    "                  topLeft: Radius.circular(13),\n"
    "                  topRight: Radius.circular(13)),\n"
    "                child: Image.asset(\n"
    "                  e.imgAsset!,\n"
    "                  width: double.infinity,\n"
    "                  height: 110,\n"
    "                  fit: BoxFit.cover,\n"
    "                  errorBuilder: (_, __, ___) => Container(\n"
    "                    height: 110,\n"
    "                    decoration: BoxDecoration(\n"
    "                      gradient: LinearGradient(\n"
    "                        begin: Alignment.topLeft,\n"
    "                        end: Alignment.bottomRight,\n"
    "                        colors: [col.withOpacity(0.18),\n"
    "                                 Colors.transparent]))))),\n"
    "              Positioned(top: 8, right: 10,\n"
    "                child: Container(\n"
    "                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),\n"
    "                  decoration: BoxDecoration(\n"
    "                    color: Colors.black.withOpacity(0.55),\n"
    "                    borderRadius: BorderRadius.circular(20),\n"
    "                    border: Border.all(color: col.withOpacity(0.6))),\n"
    "                  child: Text('\u2265\${e.score.toInt()}',\n"
    "                    style: TextStyle(color: col, fontSize: 11,\n"
    "                      fontWeight: FontWeight.w800)))),\n"
    "              Positioned(top: 8, left: 10,\n"
    "                child: Row(mainAxisSize: MainAxisSize.min, children: [\n"
    "                  AnimatedContainer(\n"
    "                    duration: const Duration(milliseconds: 200),\n"
    "                    width: 20, height: 20,\n"
    "                    decoration: BoxDecoration(\n"
    "                      shape: BoxShape.circle,\n"
    "                      color: sel ? col : Colors.black.withOpacity(0.40),\n"
    "                      border: Border.all(\n"
    "                        color: sel ? col : col.withOpacity(0.4), width: 1.5)),\n"
    "                    child: sel\n"
    "                      ? const Icon(Icons.check, size: 12,\n"
    "                          color: Color(0xFF0A0C10))\n"
    "                      : null),\n"
    "                  if (e.badge.isNotEmpty) ...[const SizedBox(width: 6),\n"
    "                    Container(\n"
    "                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),\n"
    "                      decoration: BoxDecoration(\n"
    "                        color: Colors.black.withOpacity(0.55),\n"
    "                        borderRadius: BorderRadius.circular(4),\n"
    "                        border: Border.all(color: col.withOpacity(0.6))),\n"
    "                      child: Text(e.badge, style: TextStyle(\n"
    "                        color: col, fontSize: 8,\n"
    "                        fontWeight: FontWeight.bold)))],\n"
    "                ])),\n"
    "              Positioned(bottom: 0, left: 0, right: 0,\n"
    "                child: Container(\n"
    "                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),\n"
    "                  decoration: BoxDecoration(\n"
    "                    gradient: LinearGradient(\n"
    "                      begin: Alignment.topCenter,\n"
    "                      end: Alignment.bottomCenter,\n"
    "                      colors: [Colors.transparent,\n"
    "                               Colors.black.withOpacity(0.82)])),\n"
    "                  child: Text(s.ar ? e.nameAr : e.nameEn,\n"
    "                    style: TextStyle(\n"
    "                      color: sel ? col : Colors.white,\n"
    "                      fontSize: 18, fontWeight: FontWeight.w700,\n"
    "                      shadows: const [Shadow(\n"
    "                        color: Colors.black, blurRadius: 8)])))),\n"
    "            ]),"
)
NEW_IMG_CARD = (
    "            // S51: Premium image engine card\n"
    "            if (e.imgAsset != null) AnimatedBuilder(\n"
    "              animation: _glowCtrl,\n"
    "              builder: (_, __) {\n"
    "                final g = _glowCtrl.value;\n"
    "                return Stack(children: [\n"
    "                  // Image\n"
    "                  ClipRRect(\n"
    "                    borderRadius: const BorderRadius.only(\n"
    "                      topLeft: Radius.circular(13),\n"
    "                      topRight: Radius.circular(13)),\n"
    "                    child: Stack(children: [\n"
    "                      Image.asset(e.imgAsset!,\n"
    "                        width: double.infinity, height: 130,\n"
    "                        fit: BoxFit.cover,\n"
    "                        errorBuilder: (_, __, ___) => Container(\n"
    "                          height: 130,\n"
    "                          decoration: BoxDecoration(\n"
    "                            gradient: LinearGradient(\n"
    "                              begin: Alignment.topLeft,\n"
    "                              end: Alignment.bottomRight,\n"
    "                              colors: [col.withOpacity(0.25),\n"
    "                                       const Color(0xFF020D0C)])))),\n"
    "                      // Selected: color overlay\n"
    "                      if (sel) Positioned.fill(child: Container(\n"
    "                        decoration: BoxDecoration(\n"
    "                          gradient: LinearGradient(\n"
    "                            begin: Alignment.topCenter,\n"
    "                            end: Alignment.bottomCenter,\n"
    "                            colors: [\n"
    "                              col.withOpacity(0.22 + 0.12 * g),\n"
    "                              Colors.transparent])))),\n"
    "                      // Bottom gradient always\n"
    "                      Positioned.fill(child: Container(\n"
    "                        decoration: BoxDecoration(\n"
    "                          gradient: LinearGradient(\n"
    "                            begin: Alignment.topCenter,\n"
    "                            end: Alignment.bottomCenter,\n"
    "                            stops: const [0.35, 1.0],\n"
    "                            colors: [Colors.transparent,\n"
    "                                     const Color(0xFF020D0C).withOpacity(0.92)])))),\n"
    "                    ])),\n"
    "                  // Khatam badge — top right\n"
    "                  Positioned(top: 8, right: 10,\n"
    "                    child: _khatamBadge(col, e.score, size: 48)),\n"
    "                  // Badge pill — top left\n"
    "                  if (e.badge.isNotEmpty)\n"
    "                    Positioned(top: 10, left: 10,\n"
    "                      child: Container(\n"
    "                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),\n"
    "                        decoration: BoxDecoration(\n"
    "                          color: col.withOpacity(0.15 + 0.10 * g),\n"
    "                          borderRadius: BorderRadius.circular(6),\n"
    "                          border: Border.all(\n"
    "                            color: col.withOpacity(0.55 + 0.25 * g)),\n"
    "                          boxShadow: [BoxShadow(\n"
    "                            color: col.withOpacity(0.25 + 0.20 * g),\n"
    "                            blurRadius: 8)]),\n"
    "                        child: Text(e.badge, style: TextStyle(\n"
    "                          color: col, fontSize: 9, fontWeight: FontWeight.w800,\n"
    "                          letterSpacing: 0.8)))),\n"
    "                  // Engine name — bottom\n"
    "                  Positioned(bottom: 0, left: 0, right: 0,\n"
    "                    child: Padding(\n"
    "                      padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),\n"
    "                      child: Row(children: [\n"
    "                        Expanded(child: ShaderMask(\n"
    "                          shaderCallback: (b) => LinearGradient(\n"
    "                            colors: sel\n"
    "                              ? [col, col.withOpacity(0.80)]\n"
    "                              : [Colors.white, Colors.white70],\n"
    "                            begin: Alignment.topCenter,\n"
    "                            end: Alignment.bottomCenter,\n"
    "                          ).createShader(b),\n"
    "                          child: Text(s.ar ? e.nameAr : e.nameEn,\n"
    "                            style: const TextStyle(\n"
    "                              color: Colors.white,\n"
    "                              fontSize: 20, fontWeight: FontWeight.w800,\n"
    "                              height: 1.1,\n"
    "                              shadows: [Shadow(\n"
    "                                color: Colors.black87, blurRadius: 10)])))),\n"
    "                        // Engine ID pill\n"
    "                        Container(\n"
    "                          padding: const EdgeInsets.symmetric(\n"
    "                            horizontal: 8, vertical: 3),\n"
    "                          decoration: BoxDecoration(\n"
    "                            color: Colors.black.withOpacity(0.55),\n"
    "                            borderRadius: BorderRadius.circular(8),\n"
    "                            border: Border.all(\n"
    "                              color: col.withOpacity(0.45))),\n"
    "                          child: Text(e.id, style: TextStyle(\n"
    "                            color: col, fontSize: 9,\n"
    "                            fontWeight: FontWeight.w700))),\n"
    "                      ]))),\n"
    "                  // Selected glow border\n"
    "                  if (sel) Positioned.fill(child: Container(\n"
    "                    decoration: BoxDecoration(\n"
    "                      borderRadius: const BorderRadius.only(\n"
    "                        topLeft: Radius.circular(13),\n"
    "                        topRight: Radius.circular(13)),\n"
    "                      border: Border.all(\n"
    "                        color: col.withOpacity(0.55 + 0.35 * g),\n"
    "                        width: 2.0)))),\n"
    "                ]);\n"
    "              }),\n"
    "            if (e.imgAsset != null) const SizedBox.shrink(),"
)
rep(OLD_IMG_CARD, NEW_IMG_CARD, 'Image engine card → premium khatam treatment')

# ═══════════════════════════════════════════════════════════
# 4. Engine selector header: show engine color dot
#    Exact anchor: engine selector badge pill
# ═══════════════════════════════════════════════════════════
rep(
    "                  '\u2265\${_selectedEngine.score.toInt()}',\n"
    "                  style: TextStyle(\n"
    "                    color: _badgeColor(_selectedEngine.bc).withOpacity(0.5))),",

    "                  '\u2265\${_selectedEngine.score.toInt()}',\n"
    "                  style: TextStyle(\n"
    "                    color: _engineColor.withOpacity(0.9))),",
    'Engine selector score badge → engineColor')

# ═══════════════════════════════════════════════════════════
# 5. Engine card selected bg tint uses engineColor
# ═══════════════════════════════════════════════════════════
rep(
    "          color: sel\n"
    "            ? col.withOpacity(0.09)\n"
    "            : const Color(0xFF0D2B22).withOpacity(0.75),",

    "          color: sel\n"
    "            ? col.withOpacity(0.10)\n"
    "            : const Color(0xFF0D2B22).withOpacity(0.70),",
    'Engine card bg subtle tweak (idempotent marker)')

HS.write_text(txt, encoding='utf-8')
ok('home_screen.dart saved')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL')
print('\n  git add -A && git commit -m "S51: per-engine identity color + premium image cards" && git push\n')
