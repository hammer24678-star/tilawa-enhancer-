#!/usr/bin/env python3
"""
tilawa_fix_s47.py — Add التجلي / الإتقان / الاسترداد engines + logo images
============================================================================
Changes:
  1. _EngineData gets a new `imgAsset` field (nullable String?)
  2. Three new engines prepended to _engines list:
       v11.0  التجلي       engine_tajalli_v1.py      — Tier Router
       v11.1  الإتقان      true_engine_itiqan_v2_fixed.py  — Pristine/Compressed
       v11.2  الاسترداد    engine_isteidad_v12.py    — Damaged/Critical
  3. _engineCard redesigned:
       - Full-width logo image at top (rounded corners, 110px tall)
       - Name in large Arabic text (20sp) — NO version number shown
       - Score pill repositioned to bottom-right overlay on image
       - Wider selected border glow
  4. pubspec.yaml — adds assets/images/engines/ path
  5. settings_screen.dart version map updated with new engine names

Run:
  cp /sdcard/Download/tilawa_fix_s47.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s47.py 2>&1 | tee /sdcard/Download/fix_s47.txt
  git add -A && git commit -m "S47: Add التجلي/الإتقان/الاسترداد engines + logo image cards" && git push
"""

from pathlib import Path
from datetime import datetime

BASE    = Path.home() / 'tilawa-enhancer'
LIB     = BASE / 'lib'
SCREENS = LIB / 'screens'
ASSETS  = BASE / 'assets' / 'images' / 'engines'

_log = []
def _h(t):  print(f'\n{"="*60}\n  {t}\n{"="*60}')
def _ok(m): print(f'  OK  {m}'); _log.append(('OK', m))
def _xx(m): print(f'  XX  {m}'); _log.append(('XX', m))
def _sk(m): print(f'  --  {m}'); _log.append(('SK', m))

def rep(txt, old, new, lbl):
    if old not in txt:
        _xx(f'NOT FOUND — {lbl}')
        return txt, False
    _ok(lbl)
    return txt.replace(old, new, 1), True

_h(f'tilawa_fix_s47.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ── 0. Create assets/images/engines/ directory ───────────────────────────────
_h('0 — Create assets/images/engines/')
ASSETS.mkdir(parents=True, exist_ok=True)
_ok(f'Directory ready: {ASSETS}')

# ── 1. pubspec.yaml — add engines asset path ──────────────────────────────────
_h('1 — pubspec.yaml')
pf = BASE / 'pubspec.yaml'
pt = pf.read_text(encoding='utf-8')
if 'assets/images/engines/' in pt:
    _sk('engines/ already in pubspec')
else:
    pt, ok = rep(pt,
        '    - assets/images/',
        '    - assets/images/\n    - assets/images/engines/',
        'add engines asset path')
    if ok:
        pf.write_text(pt, encoding='utf-8')

# ── 2. home_screen.dart ───────────────────────────────────────────────────────
_h('2 — home_screen.dart')
hf = SCREENS / 'home_screen.dart'
ht = hf.read_text(encoding='utf-8')

# 2a. _EngineData — add imgAsset field
_h('2a — _EngineData: add imgAsset field')
if 'imgAsset' in ht:
    _sk('imgAsset already in _EngineData')
else:
    ht, _ = rep(ht,
        'class _EngineData {\n'
        '  final String id, nameAr, nameEn, badge, bc;\n'
        '  final double score;\n'
        '  final List<String> features;\n'
        '  final String whatsNewAr, whatsNewEn;\n'
        '  const _EngineData(this.id, this.nameAr, this.nameEn, this.score,\n'
        '      this.badge, this.bc, this.features, this.whatsNewAr, this.whatsNewEn);',
        'class _EngineData {\n'
        '  final String id, nameAr, nameEn, badge, bc;\n'
        '  final double score;\n'
        '  final List<String> features;\n'
        '  final String whatsNewAr, whatsNewEn;\n'
        '  final String? imgAsset; // S47 — engine logo\n'
        '  const _EngineData(this.id, this.nameAr, this.nameEn, this.score,\n'
        '      this.badge, this.bc, this.features, this.whatsNewAr, this.whatsNewEn,\n'
        '      {this.imgAsset});',
        '_EngineData class + imgAsset')

# 2b. Add 3 new engines at top of _engines list
_h('2b — prepend التجلي / الإتقان / الاسترداد to _engines')
MARKER_NEW = "'v11.0',"
if MARKER_NEW in ht:
    _sk('v11.0 already in _engines')
else:
    OLD_LIST = "    static const _engines = [\n      _EngineData(\n        'v10.0',"
    NEW_LIST = (
        "    static const _engines = [\n"
        "      // ── S47: Three Sacred Engines ───────────────────────────────────\n"
        "      _EngineData(\n"
        "        'v11.0', 'التجلي', 'The Manifestation', 99.5,\n"
        "        'NEW', 'gold',\n"
        "        ['Tier Router', 'Auto-Path', 'DF3 NR', 'النقاء', 'البيان', 'النور'],\n"
        "        'يُحلِّل المصدر تلقائياً ويختار المسار الأمثل: الإتقان للتسجيلات النظيفة، الاسترداد للتسجيلات التالفة.',\n"
        "        'Automatically analyses the source and routes to the optimal path: الإتقان for clean recordings, الاسترداد for damaged ones.',\n"
        "        imgAsset: 'assets/images/engines/tajalli.jpg'),\n"
        "      _EngineData(\n"
        "        'v11.1', 'الإتقان', 'Perfection', 99.0,\n"
        "        '', 'gold',\n"
        "        ['Pristine Path', 'DF3 NR', 'L-BFGS-B EQ', 'Joint Opt', 'LUFS Ceil', 'LRA Tune'],\n"
        "        'مسار التسجيلات النظيفة والمضغوطة. تخفيض ضوضاء ثنائي المرحلة — تحسين طيفي — معايرة LUFS+LRA مشتركة.',\n"
        "        'Path for clean and compressed recordings. Two-stage NR, L-BFGS-B spectral EQ, joint LUFS+LRA calibration.',\n"
        "        imgAsset: 'assets/images/engines/itiqan.png'),\n"
        "      _EngineData(\n"
        "        'v11.2', 'الاسترداد', 'Recovery', 98.0,\n"
        "        '', 'gold',\n"
        "        ['Damaged Path', 'DF3 Heavy NR', 'Declip', 'Dereverberate', 'Reconstruct', 'إحياء'],\n"
        "        'مسار التسجيلات التالفة والحرجة. إزالة ضوضاء مكثفة — إزالة القطع — إعادة بناء الطيف الصوتي.',\n"
        "        'Path for damaged and critical recordings. Heavy NR, declipping, spectrum reconstruction.',\n"
        "        imgAsset: 'assets/images/engines/isteidad.jpg'),\n"
        "      // ── Legacy engines ───────────────────────────────────────────────\n"
        "      _EngineData(\n"
        "        'v10.0',"
    )
    ht, _ = rep(ht, OLD_LIST, NEW_LIST, 'prepend 3 new engines')

# 2c. Redesign _engineCard to show logo image + large Arabic name
_h('2c — _engineCard redesign with logo image')
MARKER_CARD = '// S47-ENGINE-CARD'
if MARKER_CARD in ht:
    _sk('Engine card already redesigned')
else:
    OLD_CARD_HEADER = (
        '            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [\n'
        '            // ── Collapsed header (always visible) ───────────────────\n'
        '            Padding(\n'
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
        '                      color: sel ? col : col.withOpacity(0.55), // S31-F5: per-engine colour\n'
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
        '                  Text(\'≥${e.score.toInt()}\', style: TextStyle(\n'
        '                    color: sel ? col : col.withOpacity(0.40), // S31-F5\n'
        '                    fontWeight: FontWeight.w800, fontSize: 15)),\n'
        '                  Text(\'/100\', style: TextStyle(\n'
        '                    color: col.withOpacity(sel ? 0.45 : 0.25), // S31-F5\n'
        '                    fontSize: 8)),\n'
        '                ]),\n'
        '              ])),\n'
    )
    NEW_CARD_HEADER = (
        '            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [\n'
        '            // ── S47-ENGINE-CARD: Logo image header ──────────────────\n'
        '            if (e.imgAsset != null) Stack(children: [\n'
        '              ClipRRect(\n'
        '                borderRadius: const BorderRadius.only(\n'
        '                  topLeft: Radius.circular(13),\n'
        '                  topRight: Radius.circular(13)),\n'
        '                child: Image.asset(\n'
        '                  e.imgAsset!,\n'
        '                  width: double.infinity,\n'
        '                  height: 110,\n'
        '                  fit: BoxFit.cover,\n'
        '                  errorBuilder: (_, __, ___) => Container(\n'
        '                    height: 110,\n'
        '                    decoration: BoxDecoration(\n'
        '                      gradient: LinearGradient(\n'
        '                        begin: Alignment.topLeft,\n'
        '                        end: Alignment.bottomRight,\n'
        '                        colors: [col.withOpacity(0.15), Colors.transparent])),\n'
        '                  ))),\n'
        '              // Score pill overlay\n'
        '              Positioned(top: 8, right: 10,\n'
        '                child: Container(\n'
        '                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),\n'
        '                  decoration: BoxDecoration(\n'
        '                    color: Colors.black.withOpacity(0.55),\n'
        '                    borderRadius: BorderRadius.circular(20),\n'
        '                    border: Border.all(color: col.withOpacity(0.6))),\n'
        '                  child: Text(\'≥${e.score.toInt()}\',\n'
        '                    style: TextStyle(\n'
        '                      color: col, fontSize: 11,\n'
        '                      fontWeight: FontWeight.w800)))),\n'
        '              // Selected check + badge overlay\n'
        '              Positioned(top: 8, left: 10,\n'
        '                child: Row(mainAxisSize: MainAxisSize.min, children: [\n'
        '                  AnimatedContainer(\n'
        '                    duration: const Duration(milliseconds: 200),\n'
        '                    width: 20, height: 20,\n'
        '                    decoration: BoxDecoration(\n'
        '                      shape: BoxShape.circle,\n'
        '                      color: sel\n'
        '                        ? col\n'
        '                        : Colors.black.withOpacity(0.40),\n'
        '                      border: Border.all(color: sel ? col : col.withOpacity(0.4), width: 1.5)),\n'
        '                    child: sel\n'
        '                      ? const Icon(Icons.check, size: 12, color: Color(0xFF0A0C10))\n'
        '                      : null),\n'
        '                  if (e.badge.isNotEmpty) ...[const SizedBox(width: 6),\n'
        '                    Container(\n'
        '                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),\n'
        '                      decoration: BoxDecoration(\n'
        '                        color: Colors.black.withOpacity(0.55),\n'
        '                        borderRadius: BorderRadius.circular(4),\n'
        '                        border: Border.all(color: col.withOpacity(0.6))),\n'
        '                      child: Text(e.badge, style: TextStyle(\n'
        '                        color: col, fontSize: 8, fontWeight: FontWeight.bold)))],\n'
        '                ])),\n'
        '              // Name overlay at bottom of image\n'
        '              Positioned(bottom: 0, left: 0, right: 0,\n'
        '                child: Container(\n'
        '                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),\n'
        '                  decoration: BoxDecoration(\n'
        '                    gradient: LinearGradient(\n'
        '                      begin: Alignment.topCenter,\n'
        '                      end: Alignment.bottomCenter,\n'
        '                      colors: [Colors.transparent, Colors.black.withOpacity(0.82)])),\n'
        '                  child: Text(s.ar ? e.nameAr : e.nameEn,\n'
        '                    style: TextStyle(\n'
        '                      color: sel ? col : Colors.white,\n'
        '                      fontSize: 18, fontWeight: FontWeight.w700,\n'
        '                      shadows: [Shadow(color: Colors.black, blurRadius: 8)])))),\n'
        '            ]),\n'
        '            // ── Compact header for engines without image ─────────────\n'
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
        '                    if (e.badge.isNotEmpty) ...[const SizedBox(width: 6),\n'
        '                      Container(\n'
        '                        padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),\n'
        '                        decoration: BoxDecoration(\n'
        '                          color: bg, borderRadius: BorderRadius.circular(4),\n'
        '                          border: Border.all(color: col.withOpacity(0.45))),\n'
        '                        child: Text(e.badge, style: TextStyle(\n'
        '                          color: col, fontSize: 8, fontWeight: FontWeight.bold)))],\n'
        '                  ]),\n'
        '                  const SizedBox(height: 2),\n'
        '                  Text(s.ar ? e.nameAr : e.nameEn,\n'
        '                    style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),\n'
        '                ])),\n'
        '                Column(crossAxisAlignment: CrossAxisAlignment.end, children: [\n'
        '                  Text(\'≥${e.score.toInt()}\', style: TextStyle(\n'
        '                    color: sel ? col : col.withOpacity(0.40),\n'
        '                    fontWeight: FontWeight.w800, fontSize: 15)),\n'
        '                  Text(\'/100\', style: TextStyle(\n'
        '                    color: col.withOpacity(sel ? 0.45 : 0.25),\n'
        '                    fontSize: 8)),\n'
        '                ]),\n'
        '              ])),\n'
    )
    ht, _ = rep(ht, OLD_CARD_HEADER, NEW_CARD_HEADER, 'engine card → logo image header')

# 2d. Update ApiService version name map to include new engines
_h('2d — version name map in home_screen')
if "'v11.0': 'التجلي'" in ht or "'v11.0': 'Tajalli'" in ht:
    _sk('v11.x already in version name map')
else:
    ht, _ = rep(ht,
        "'v10.0': 'Aetherion_Foundation',   // S32-BUG4-FIX",
        "'v10.0': 'Aetherion_Foundation',   // S32-BUG4-FIX\n"
        "        'v11.0': 'Tajalli',\n"
        "        'v11.1': 'Itiqan',\n"
        "        'v11.2': 'Isteidad',",
        'v11.x in history filename map')

hf.write_text(ht, encoding='utf-8')
_ok('home_screen.dart saved')

# ── 3. settings_screen.dart — version name map ────────────────────────────────
_h('3 — settings_screen.dart version map')
sf = SCREENS / 'settings_screen.dart'
st = sf.read_text(encoding='utf-8')

if "'v11.0': s.ar ? 'التجلي'" in st:
    _sk('v11.x already in settings version map')
else:
    st, _ = rep(st,
        "        ('v10.0', s.ar ? 'الأثيريون — الأساس' : 'Aetherion Foundation',",
        "        ('v11.0', s.ar ? 'التجلي' : 'The Manifestation',\n"
        "          s.ar ? '≥ 99.5/100' : '≥ 99.5/100', 'v11.0'),\n"
        "        ('v11.1', s.ar ? 'الإتقان' : 'Perfection',\n"
        "          s.ar ? '≥ 99/100' : '≥ 99/100', 'v11.1'),\n"
        "        ('v11.2', s.ar ? 'الاسترداد' : 'Recovery',\n"
        "          s.ar ? '≥ 98/100' : '≥ 98/100', 'v11.2'),\n"
        "        ('v10.0', s.ar ? 'الأثيريون — الأساس' : 'Aetherion Foundation',",
        'v11.x in settings version map')

    sf.write_text(st, encoding='utf-8')
    _ok('settings_screen.dart saved')

# ── SUMMARY ───────────────────────────────────────────────────────────────────
_h('SUMMARY')
ok_n = sum(1 for s, _ in _log if s == 'OK')
sk_n = sum(1 for s, _ in _log if s == 'SK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
for s, l in _log:
    print(f'  {"OK" if s=="OK" else "--" if s=="SK" else "XX"}  {l}')
_h(f'{ok_n} OK   {sk_n} SKIP   {xx_n} FAIL')

if xx_n == 0:
    print("""
  NEXT: Copy engine images to ~/tilawa-enhancer/assets/images/engines/
    tajalli.jpg   — التجلي  (image 2 — the gold star)
    itiqan.png    — الإتقان  (image 3 — the emerald crystal)
    isteidad.jpg  — الاسترداد (image 1 — the broken mandala)

  Then:
    cd ~/tilawa-enhancer
    git add -A
    git commit -m "S47: Add التجلي/الإتقان/الاسترداد engines + logo image cards"
    git push
""")
else:
    print('\n  Paste output back to Claude for anchors fix.\n')
