#!/usr/bin/env python3
"""
tilawa_fix_s47b.py — fix 4 failing anchors from s47
====================================================
Run:
  cp /sdcard/Download/tilawa_fix_s47b.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s47b.py 2>&1 | tee /sdcard/Download/fix_s47b.txt
  git add -A && git commit -m "S47b: 3 new engines + logo cards" && git push
"""

from pathlib import Path
from datetime import datetime

SC = Path.home() / 'tilawa-enhancer/lib/screens'
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

_h(f'tilawa_fix_s47b.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ══════════════════════════════════════════════════════════════════
# HOME SCREEN
# ══════════════════════════════════════════════════════════════════
hf = SC / 'home_screen.dart'
ht = hf.read_text(encoding='utf-8')

# ── 1. Prepend 3 new engines (exact 2sp/4sp/6sp from diag) ───────
_h('1 — prepend التجلي / الإتقان / الاسترداد')
if "'v11.0'" in ht:
    _sk('v11.x already in _engines')
else:
    OLD = (
        "  static const _engines = [\n"
        "    _EngineData(\n"
        "      'v10.0', 'الأثيريون — الأساس', 'Aetherion Foundation', 99.0,"
    )
    NEW = (
        "  static const _engines = [\n"
        "    // ── S47: Three Sacred Engines ──────────────────────────────────\n"
        "    _EngineData(\n"
        "      'v11.0', 'التجلي', 'The Manifestation', 99.5,\n"
        "      'NEW', 'gold',\n"
        "      ['Tier Router', 'Auto-Path', 'DF3 NR', 'النقاء', 'البيان', 'النور'],\n"
        "      'يُحلِّل المصدر تلقائياً ويختار المسار الأمثل: الإتقان للتسجيلات النظيفة، الاسترداد للتالفة.',\n"
        "      'Auto-analyses the source and routes to the optimal path: الإتقان for clean, الاسترداد for damaged.',\n"
        "      imgAsset: 'assets/images/engines/tajalli.jpg'),\n"
        "    _EngineData(\n"
        "      'v11.1', 'الإتقان', 'Perfection', 99.0,\n"
        "      '', 'gold',\n"
        "      ['Pristine Path', 'DF3 NR', 'L-BFGS-B EQ', 'Joint Opt', 'LUFS Ceil', 'LRA Tune'],\n"
        "      'مسار التسجيلات النظيفة والمضغوطة. تخفيض ضوضاء ثنائي — تحسين طيفي — معايرة LUFS+LRA مشتركة.',\n"
        "      'Path for clean and compressed recordings. Two-stage NR, spectral EQ, joint LUFS+LRA calibration.',\n"
        "      imgAsset: 'assets/images/engines/itiqan.jpg'),\n"
        "    _EngineData(\n"
        "      'v11.2', 'الاسترداد', 'Recovery', 98.0,\n"
        "      '', 'gold',\n"
        "      ['Damaged Path', 'DF3 Heavy NR', 'Declip', 'Dereverberate', 'Reconstruct', 'إحياء'],\n"
        "      'مسار التسجيلات التالفة. إزالة ضوضاء مكثفة — إزالة القطع — إعادة بناء الطيف الصوتي.',\n"
        "      'Path for damaged recordings. Heavy NR, declipping, spectrum reconstruction.',\n"
        "      imgAsset: 'assets/images/engines/isteidad.jpg'),\n"
        "    // ── Legacy engines ────────────────────────────────────────────────\n"
        "    _EngineData(\n"
        "      'v10.0', 'الأثيريون — الأساس', 'Aetherion Foundation', 99.0,"
    )
    ht, _ = rep(ht, OLD, NEW, 'prepend 3 new engines (2sp/4sp/6sp)')

# ── 2. _engineCard — add logo image block before Column ──────────
# Find the exact unique anchor: the accent-bar Stack child Column
_h('2 — _engineCard logo image header')
if '// S47-ENGINE-CARD' in ht:
    _sk('engine card already redesigned')
else:
    # Exact from dump line 1032-1034 (4sp/12sp indent)
    OLD_COL = (
        '          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [\n'
        '          // ── Collapsed header (always visible) ───────────────────\n'
        '          Padding(\n'
        '            padding: const EdgeInsets.fromLTRB(12,11,12,11),\n'
        '            child: Row(children: [\n'
        '              AnimatedContainer(\n'
        '                duration: const Duration(milliseconds: 200),\n'
        '                width: 18, height: 18,\n'
        '                decoration: BoxDecoration(\n'
        '                  shape: BoxShape.circle,\n'
        '                  border: Border.all(\n'
        '                    color: sel ? col : _tBorder, width: 2),\n'
        '                  color: sel ? col : Colors.transparent),\n'
        '                child: sel\n'
        "                  ? const Icon(Icons.check, size: 10, color: Color(0xFF0A0C10))\n"
        '                  : null),\n'
        '              const SizedBox(width: 11),\n'
        '              Expanded(child: Column(\n'
        '                crossAxisAlignment: CrossAxisAlignment.start,\n'
        '                children: [\n'
        '                Row(children: [\n'
        '                  Text(e.id, style: TextStyle(\n'
        "                    color: sel ? col : col.withOpacity(0.55), // S31-F5: per-engine colour\n"
        '                    fontWeight: FontWeight.bold, fontSize: 13)),\n'
        '                  if (e.badge.isNotEmpty) ...[\n'
        '                    const SizedBox(width: 6),\n'
        '                    Container(\n'
        '                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),\n'
        '                      decoration: BoxDecoration(\n'
        '                        color: bg, borderRadius: BorderRadius.circular(4),\n'
        '                        border: Border.all(color: col.withOpacity(0.45))),\n'
        '                      child: Text(e.badge, style: TextStyle(\n'
        '                        color: col, fontSize: 8, fontWeight: FontWeight.bold))),\n'
        '                  ],\n'
        '                ]),\n'
        '                const SizedBox(height: 2),\n'
        '                Text(s.ar ? e.nameAr : e.nameEn,\n'
        '                  style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),\n'
        '              ])),\n'
        '              Column(crossAxisAlignment: CrossAxisAlignment.end, children: [\n'
        "                Text('≥${e.score.toInt()}', style: TextStyle(\n"
        '                  color: sel ? col : col.withOpacity(0.40), // S31-F5\n'
        '                  fontWeight: FontWeight.w800, fontSize: 15)),\n'
        "                Text('/100', style: TextStyle(\n"
        '                  color: col.withOpacity(sel ? 0.45 : 0.25), // S31-F5\n'
        '                  fontSize: 8)),\n'
        '              ]),\n'
        '            ])),\n'
    )
    NEW_COL = (
        '          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [\n'
        '          // S47-ENGINE-CARD — logo image header\n'
        '          if (e.imgAsset != null) Stack(children: [\n'
        '            ClipRRect(\n'
        '              borderRadius: const BorderRadius.only(\n'
        '                topLeft: Radius.circular(13),\n'
        '                topRight: Radius.circular(13)),\n'
        '              child: Image.asset(\n'
        '                e.imgAsset!,\n'
        '                width: double.infinity,\n'
        '                height: 110,\n'
        '                fit: BoxFit.cover,\n'
        '                errorBuilder: (_, __, ___) => Container(\n'
        '                  height: 110,\n'
        '                  decoration: BoxDecoration(\n'
        '                    gradient: LinearGradient(\n'
        '                      begin: Alignment.topLeft,\n'
        '                      end: Alignment.bottomRight,\n'
        '                      colors: [col.withOpacity(0.18),\n'
        '                               Colors.transparent]))))),\n'
        '            // Score pill — top right\n'
        '            Positioned(top: 8, right: 10,\n'
        '              child: Container(\n'
        '                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),\n'
        '                decoration: BoxDecoration(\n'
        '                  color: Colors.black.withOpacity(0.55),\n'
        '                  borderRadius: BorderRadius.circular(20),\n'
        '                  border: Border.all(color: col.withOpacity(0.6))),\n'
        "                child: Text('≥${e.score.toInt()}',\n"
        '                  style: TextStyle(\n'
        '                    color: col, fontSize: 11,\n'
        '                    fontWeight: FontWeight.w800)))),\n'
        '            // Check + badge — top left\n'
        '            Positioned(top: 8, left: 10,\n'
        '              child: Row(mainAxisSize: MainAxisSize.min, children: [\n'
        '                AnimatedContainer(\n'
        '                  duration: const Duration(milliseconds: 200),\n'
        '                  width: 20, height: 20,\n'
        '                  decoration: BoxDecoration(\n'
        '                    shape: BoxShape.circle,\n'
        '                    color: sel\n'
        '                      ? col\n'
        '                      : Colors.black.withOpacity(0.40),\n'
        '                    border: Border.all(\n'
        '                      color: sel ? col : col.withOpacity(0.4),\n'
        '                      width: 1.5)),\n'
        '                  child: sel\n'
        '                    ? const Icon(Icons.check, size: 12,\n'
        '                        color: Color(0xFF0A0C10))\n'
        '                    : null),\n'
        '                if (e.badge.isNotEmpty) ...[const SizedBox(width: 6),\n'
        '                  Container(\n'
        '                    padding: const EdgeInsets.symmetric(\n'
        '                      horizontal: 5, vertical: 2),\n'
        '                    decoration: BoxDecoration(\n'
        '                      color: Colors.black.withOpacity(0.55),\n'
        '                      borderRadius: BorderRadius.circular(4),\n'
        '                      border: Border.all(color: col.withOpacity(0.6))),\n'
        '                    child: Text(e.badge, style: TextStyle(\n'
        '                      color: col, fontSize: 8,\n'
        '                      fontWeight: FontWeight.bold)))],\n'
        '              ])),\n'
        '            // Name gradient overlay — bottom\n'
        '            Positioned(bottom: 0, left: 0, right: 0,\n'
        '              child: Container(\n'
        '                padding: const EdgeInsets.fromLTRB(12, 8, 12, 8),\n'
        '                decoration: BoxDecoration(\n'
        '                  gradient: LinearGradient(\n'
        '                    begin: Alignment.topCenter,\n'
        '                    end: Alignment.bottomCenter,\n'
        '                    colors: [Colors.transparent,\n'
        '                             Colors.black.withOpacity(0.82)])),\n'
        '                child: Text(s.ar ? e.nameAr : e.nameEn,\n'
        '                  style: TextStyle(\n'
        '                    color: sel ? col : Colors.white,\n'
        '                    fontSize: 18, fontWeight: FontWeight.w700,\n'
        '                    shadows: const [Shadow(\n'
        '                      color: Colors.black,\n'
        '                      blurRadius: 8)])))),\n'
        '          ]),\n'
        '          // ── Compact header for engines without logo ──────────────\n'
        '          if (e.imgAsset == null) Padding(\n'
        '            padding: const EdgeInsets.fromLTRB(12,11,12,11),\n'
        '            child: Row(children: [\n'
        '              AnimatedContainer(\n'
        '                duration: const Duration(milliseconds: 200),\n'
        '                width: 18, height: 18,\n'
        '                decoration: BoxDecoration(\n'
        '                  shape: BoxShape.circle,\n'
        '                  border: Border.all(\n'
        '                    color: sel ? col : _tBorder, width: 2),\n'
        '                  color: sel ? col : Colors.transparent),\n'
        '                child: sel\n'
        "                  ? const Icon(Icons.check, size: 10, color: Color(0xFF0A0C10))\n"
        '                  : null),\n'
        '              const SizedBox(width: 11),\n'
        '              Expanded(child: Column(\n'
        '                crossAxisAlignment: CrossAxisAlignment.start,\n'
        '                children: [\n'
        '                Row(children: [\n'
        '                  Text(e.id, style: TextStyle(\n'
        '                    color: sel ? col : col.withOpacity(0.55),\n'
        '                    fontWeight: FontWeight.bold, fontSize: 13)),\n'
        '                  if (e.badge.isNotEmpty) ...[\n'
        '                    const SizedBox(width: 6),\n'
        '                    Container(\n'
        '                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),\n'
        '                      decoration: BoxDecoration(\n'
        '                        color: bg, borderRadius: BorderRadius.circular(4),\n'
        '                        border: Border.all(color: col.withOpacity(0.45))),\n'
        '                      child: Text(e.badge, style: TextStyle(\n'
        '                        color: col, fontSize: 8, fontWeight: FontWeight.bold))),\n'
        '                  ],\n'
        '                ]),\n'
        '                const SizedBox(height: 2),\n'
        '                Text(s.ar ? e.nameAr : e.nameEn,\n'
        '                  style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),\n'
        '              ])),\n'
        '              Column(crossAxisAlignment: CrossAxisAlignment.end, children: [\n'
        "                Text('≥${e.score.toInt()}', style: TextStyle(\n"
        '                  color: sel ? col : col.withOpacity(0.40),\n'
        '                  fontWeight: FontWeight.w800, fontSize: 15)),\n'
        "                Text('/100', style: TextStyle(\n"
        '                  color: col.withOpacity(sel ? 0.45 : 0.25),\n'
        '                  fontSize: 8)),\n'
        '              ]),\n'
        '            ])),\n'
    )
    ht, _ = rep(ht, OLD_COL, NEW_COL, 'engine card → logo image header')

# ── 3. Version name map (exact from diag line 1703-1704) ─────────
_h('3 — version name map')
if "'v11.0'" in ht and 'engineNames' in ht:
    _sk('v11.x already in engineNames map')
else:
    ht, _ = rep(ht,
        "    const engineNames = {\n"
        "      'v10.0': 'Aetherion Foundation',",
        "    const engineNames = {\n"
        "      'v11.0': 'Tajalli',\n"
        "      'v11.1': 'Itiqan',\n"
        "      'v11.2': 'Isteidad',\n"
        "      'v10.0': 'Aetherion Foundation',",
        'v11.x in engineNames map')

hf.write_text(ht, encoding='utf-8')
_ok('home_screen.dart saved')

# ── 4. settings_screen.dart — _EHist prepend v11.x ───────────────
_h('4 — settings_screen.dart _EHist prepend')
sf = SC / 'settings_screen.dart'
st = sf.read_text(encoding='utf-8')

if "'v11.0'" in st:
    _sk('v11.x already in settings _EHist')
else:
    # From diag line 12: _EHist('v9.0',...) is first entry
    OLD_HIST = "_EHist('v9.0','The Evolution','≥ 99/100','LATEST','gold',"
    NEW_HIST = (
        "_EHist('v11.0','التجلي — The Manifestation','≥ 99.5/100','LATEST','gold',\n"
        "      'محرك التوجيه الذكي: يختار مسار الإتقان أو الاسترداد تلقائياً.',\n"
        "      'Smart router: auto-selects Itiqan or Isteidad path based on source tier.'),\n"
        "    _EHist('v11.1','الإتقان — Perfection','≥ 99/100','','gold',\n"
        "      'مسار التسجيلات النظيفة: NR ثنائي + EQ طيفي + معايرة LUFS+LRA.',\n"
        "      'Clean recordings path: two-stage NR, spectral EQ, joint LUFS+LRA.'),\n"
        "    _EHist('v11.2','الاسترداد — Recovery','≥ 98/100','','gold',\n"
        "      'مسار التسجيلات التالفة: NR مكثف + إزالة قطع + إعادة بناء طيفي.',\n"
        "      'Damaged path: heavy NR, declip, spectrum reconstruction.'),\n"
        "    _EHist('v9.0','The Evolution','≥ 99/100','LATEST','gold',"
    )
    st, _ = rep(st, OLD_HIST, NEW_HIST, 'prepend v11.x to _EHist list')
    sf.write_text(st, encoding='utf-8')
    _ok('settings_screen.dart saved')

# ══════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════
_h('SUMMARY')
ok_n = sum(1 for s, _ in _log if s == 'OK')
sk_n = sum(1 for s, _ in _log if s == 'SK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
for s, l in _log:
    print(f'  {"OK" if s=="OK" else "--" if s=="SK" else "XX"}  {l}')
_h(f'{ok_n} OK   {sk_n} SKIP   {xx_n} FAIL')

if xx_n == 0:
    print("""
  Copy images then commit:
    cp "/sdcard/Download/image-63.jpg"       ~/tilawa-enhancer/assets/images/engines/tajalli.jpg
    cp "/sdcard/Download/image-162.jpg"      ~/tilawa-enhancer/assets/images/engines/itiqan.jpg
    cp "/sdcard/Download/1779536210369.png"  ~/tilawa-enhancer/assets/images/engines/isteidad.jpg

    git add -A
    git commit -m "S47b: 3 new engines + logo image cards"
    git push
""")
else:
    print('\n  Paste output back to Claude.\n')
