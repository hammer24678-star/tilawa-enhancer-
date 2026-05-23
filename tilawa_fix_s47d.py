#!/usr/bin/env python3
"""
tilawa_fix_s47d.py — engine card logo header (exact 10sp indent from diag)
Run:
  cp /sdcard/Download/tilawa_fix_s47d.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s47d.py 2>&1 | tee /sdcard/Download/fix_s47d.txt
  # if all OK:
  cp "/sdcard/Download/image-63.jpg"       ~/tilawa-enhancer/assets/images/engines/tajalli.jpg
  cp "/sdcard/Download/image-162.jpg"      ~/tilawa-enhancer/assets/images/engines/itiqan.jpg
  cp "/sdcard/Download/1779536210369.png"  ~/tilawa-enhancer/assets/images/engines/isteidad.jpg
  git add -A && git commit -m "S47: 3 new engines + logo image cards" && git push
"""
from pathlib import Path
from datetime import datetime

SC = Path.home() / 'tilawa-enhancer/lib/screens'

def _h(t): print(f'\n{"="*56}\n  {t}\n{"="*56}')
def _ok(m): print(f'  OK  {m}')
def _xx(m): print(f'  XX  {m}')
def _sk(m): print(f'  --  {m}')

_h(f'tilawa_fix_s47d.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

hf = SC / 'home_screen.dart'
ht = hf.read_text(encoding='utf-8')

_h('Engine card → logo image header (10sp indent)')

if '// S47-ENGINE-CARD' in ht:
    _sk('Already applied')
else:
    # Exact text from diag lines 1055-1103 (10sp base indent)
    OLD = (
        '          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [\n'
        '          // ── Collapsed header (always visible) ───────────────────────\n'
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
        '                  ? const Icon(Icons.check, size: 10, color: Color(0xFF0A0C10))\n'
        '                  : null),\n'
        '              const SizedBox(width: 11),\n'
        '              Expanded(child: Column(\n'
        '                crossAxisAlignment: CrossAxisAlignment.start,\n'
        '                children: [\n'
        '                Row(children: [\n'
        '                  Text(e.id, style: TextStyle(\n'
        '                    color: sel ? col : col.withOpacity(0.55), // S31-F5: per-engine colour\n'
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

    NEW = (
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
        '            Positioned(top: 8, right: 10,\n'
        '              child: Container(\n'
        '                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),\n'
        '                decoration: BoxDecoration(\n'
        '                  color: Colors.black.withOpacity(0.55),\n'
        '                  borderRadius: BorderRadius.circular(20),\n'
        '                  border: Border.all(color: col.withOpacity(0.6))),\n'
        "                child: Text('≥${e.score.toInt()}',\n"
        '                  style: TextStyle(color: col, fontSize: 11,\n'
        '                    fontWeight: FontWeight.w800)))),\n'
        '            Positioned(top: 8, left: 10,\n'
        '              child: Row(mainAxisSize: MainAxisSize.min, children: [\n'
        '                AnimatedContainer(\n'
        '                  duration: const Duration(milliseconds: 200),\n'
        '                  width: 20, height: 20,\n'
        '                  decoration: BoxDecoration(\n'
        '                    shape: BoxShape.circle,\n'
        '                    color: sel ? col : Colors.black.withOpacity(0.40),\n'
        '                    border: Border.all(\n'
        '                      color: sel ? col : col.withOpacity(0.4), width: 1.5)),\n'
        '                  child: sel\n'
        '                    ? const Icon(Icons.check, size: 12,\n'
        '                        color: Color(0xFF0A0C10))\n'
        '                    : null),\n'
        '                if (e.badge.isNotEmpty) ...[const SizedBox(width: 6),\n'
        '                  Container(\n'
        '                    padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 2),\n'
        '                    decoration: BoxDecoration(\n'
        '                      color: Colors.black.withOpacity(0.55),\n'
        '                      borderRadius: BorderRadius.circular(4),\n'
        '                      border: Border.all(color: col.withOpacity(0.6))),\n'
        '                    child: Text(e.badge, style: TextStyle(\n'
        '                      color: col, fontSize: 8,\n'
        '                      fontWeight: FontWeight.bold)))],\n'
        '              ])),\n'
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
        '                      color: Colors.black, blurRadius: 8)])))),\n'
        '          ]),\n'
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
        '                  ? const Icon(Icons.check, size: 10, color: Color(0xFF0A0C10))\n'
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

    if OLD in ht:
        ht = ht.replace(OLD, NEW, 1)
        _ok('engine card → logo image header applied')
    else:
        _xx('anchor not found — dumping lines 1055-1105 for diagnosis')
        for i, l in enumerate(ht.splitlines()[1052:1106], start=1053):
            print(f'  {i:5}  {repr(l[:110])}')

hf.write_text(ht, encoding='utf-8')
_ok('home_screen.dart saved')

print("""
  Next:
    cp "/sdcard/Download/image-63.jpg"       ~/tilawa-enhancer/assets/images/engines/tajalli.jpg
    cp "/sdcard/Download/image-162.jpg"      ~/tilawa-enhancer/assets/images/engines/itiqan.jpg
    cp "/sdcard/Download/1779536210369.png"  ~/tilawa-enhancer/assets/images/engines/isteidad.jpg
    git add -A && git commit -m "S47: 3 new engines + logo image cards" && git push
""")
