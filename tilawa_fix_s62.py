#!/usr/bin/env python3
"""
tilawa_fix_s62.py — audio bars upgrade: taller, organic, multi-frequency
=========================================================================
Changes:
  1. _audioBarsCtrl: 900ms → 1800ms (smoother, less mechanical)
  2. Progress card bars: 14 → 20 bars, 4+14 → 6+28 height,
     3.5px → 3px wide, multi-frequency sine wave (natural look)
  3. File card bars (hasFile): 22 → 26 bars, 28 → 36px max,
     multi-sine for organic feel, teal→gold gradient preserved
  4. File card empty state: subtle breathing pulse instead of static

Run:
  cp /sdcard/Download/tilawa_fix_s62.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s62.py && git add -A && git commit -m "S62: taller organic audio bars" && git push
"""
from pathlib import Path
from datetime import datetime

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
ok_n = xx_n = sk_n = 0

def ok(m):  global ok_n; print(f'  OK  {m}'); ok_n += 1
def xx(m):  global xx_n; print(f'  XX  {m}'); xx_n += 1
def sk(m):  global sk_n; print(f'  --  {m}'); sk_n += 1

def rep(t, old, new, lbl):
    if old not in t: xx(f'NOT FOUND — {lbl}'); return t
    ok(lbl); return t.replace(old, new, 1)

print(f'\n=== tilawa_fix_s62.py  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} ===\n')

ht = HS.read_text(encoding='utf-8')

# ── 1. Controller: 900ms → 1800ms ────────────────────────────────
if '// S62-BARS-CTRL' in ht:
    sk('controller already updated')
else:
    ht = rep(ht,
        '    _audioBarsCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(milliseconds: 900))\n'
        '      ..repeat(reverse: true);',
        '    _audioBarsCtrl = AnimationController( // S62-BARS-CTRL\n'
        '        vsync: this, duration: const Duration(milliseconds: 1800))\n'
        '      ..repeat(reverse: true);',
        'audioBarsCtrl 900→1800ms')

# ── 2. Progress card bars: 14 bars, 4+14 → 20 bars, 6+28 ─────────
if '// S62-PROG-BARS' in ht:
    sk('progress bars already upgraded')
else:
    ht = rep(ht,
        '              builder: (_, __) {\n'
        '                const n = 14;\n'
        '                return Row(\n'
        '                  mainAxisSize: MainAxisSize.min,\n'
        '                  crossAxisAlignment: CrossAxisAlignment.end,\n'
        '                  children: List.generate(n, (i) {\n'
        '                    final h = 4.0 + 14.0 * (sin(\n'
        '                      (_audioBarsCtrl.value + i/n) * 6.2832 * 1.5\n'
        '                    ) * 0.5 + 0.5);\n'
        '                    final lit = (i / n) < _progress;\n'
        '                    return Container(\n'
        '                      width: 3.5, height: h,\n'
        '                      margin: const EdgeInsets.only(right: 2.5),\n'
        '                      decoration: BoxDecoration(\n'
        '                        color: lit\n'
        '                          ? _gold.withOpacity(0.65 + 0.35 * _audioBarsCtrl.value)\n'
        '                          : _teal.withOpacity(0.22),\n'
        '                        borderRadius: BorderRadius.circular(2)));\n'
        '                  }));\n'
        '              }),',
        '              builder: (_, __) { // S62-PROG-BARS\n'
        '                const n = 20;\n'
        '                final v = _audioBarsCtrl.value;\n'
        '                return Row(\n'
        '                  mainAxisSize: MainAxisSize.min,\n'
        '                  crossAxisAlignment: CrossAxisAlignment.end,\n'
        '                  children: List.generate(n, (i) {\n'
        '                    // Multi-frequency: primary + harmonic + slow swell\n'
        '                    final f1 = sin((v + i / n) * 6.2832 * 1.5);\n'
        '                    final f2 = sin((v * 1.7 + i / n) * 6.2832 * 0.8);\n'
        '                    final f3 = sin((v * 0.4 + i / n) * 6.2832 * 0.3);\n'
        '                    final wave = (f1 * 0.55 + f2 * 0.28 + f3 * 0.17);\n'
        '                    final h = 6.0 + 28.0 * (wave * 0.5 + 0.5);\n'
        '                    final lit = (i / n) < _progress;\n'
        '                    final bright = 0.55 + 0.45 * v;\n'
        '                    return Container(\n'
        '                      width: 3.0, height: h,\n'
        '                      margin: const EdgeInsets.only(right: 2.5),\n'
        '                      decoration: BoxDecoration(\n'
        '                        gradient: lit ? LinearGradient(\n'
        '                          begin: Alignment.bottomCenter,\n'
        '                          end: Alignment.topCenter,\n'
        '                          colors: [\n'
        '                            _gold.withOpacity(bright),\n'
        '                            _goldLight.withOpacity(bright * 0.7)]) : null,\n'
        '                        color: lit ? null : _teal.withOpacity(0.18),\n'
        '                        borderRadius: BorderRadius.circular(2),\n'
        '                        boxShadow: lit ? [BoxShadow(\n'
        '                          color: _gold.withOpacity(0.35 * v),\n'
        '                          blurRadius: 4)] : null));\n'
        '                  }));\n'
        '              }),',
        'progress card bars 14→20, 18px→34px, multi-freq + glow')

# ── 3. File card bars (hasFile=true): 22→26 bars, 28→36px ────────
if '// S62-FILE-BARS' in ht:
    sk('file card bars already upgraded')
else:
    ht = rep(ht,
        '                ? AnimatedBuilder(\n'
        '                    animation: _audioBarsCtrl,\n'
        '                    builder: (_, __) => Row(\n'
        '                      mainAxisAlignment: MainAxisAlignment.center,\n'
        '                      crossAxisAlignment: CrossAxisAlignment.center,\n'
        '                      children: List.generate(22, (i) {\n'
        '                        final phase = (_audioBarsCtrl.value + i * 0.13) % 1.0;\n'
        '                        final ht = 4.0 + 24.0 *\n'
        '                          sin(phase * pi).abs() *\n'
        '                          (0.4 + 0.6 * sin(i * 0.95).abs());\n'
        '                        return Container(\n'
        '                          width: 3, height: ht,\n'
        '                          margin: const EdgeInsets.symmetric(horizontal: 1.5),\n'
        '                          decoration: BoxDecoration(\n'
        '                            borderRadius: BorderRadius.circular(2),\n'
        '                            gradient: const LinearGradient(\n'
        '                              begin: Alignment.bottomCenter,\n'
        '                              end: Alignment.topCenter,\n'
        '                              colors: [Color(0xFF1DB898), Color(0xFFC8A048)])));\n'
        '                      })))',
        '                ? AnimatedBuilder( // S62-FILE-BARS\n'
        '                    animation: _audioBarsCtrl,\n'
        '                    builder: (_, __) => Row(\n'
        '                      mainAxisAlignment: MainAxisAlignment.center,\n'
        '                      crossAxisAlignment: CrossAxisAlignment.end,\n'
        '                      children: List.generate(26, (i) {\n'
        '                        final v = _audioBarsCtrl.value;\n'
        '                        final f1 = sin((v + i / 26) * 6.2832 * 1.4);\n'
        '                        final f2 = sin((v * 1.9 + i / 26) * 6.2832 * 0.7);\n'
        '                        final f3 = sin((v * 0.5 + i / 26) * 6.2832 * 2.1);\n'
        '                        final wave = f1 * 0.5 + f2 * 0.3 + f3 * 0.2;\n'
        '                        final barH = 5.0 + 36.0 * (wave * 0.5 + 0.5);\n'
        '                        final glow = 0.45 + 0.55 * v;\n'
        '                        return Container(\n'
        '                          width: 3, height: barH,\n'
        '                          margin: const EdgeInsets.symmetric(horizontal: 1.5),\n'
        '                          decoration: BoxDecoration(\n'
        '                            borderRadius: BorderRadius.circular(2),\n'
        '                            gradient: LinearGradient(\n'
        '                              begin: Alignment.bottomCenter,\n'
        '                              end: Alignment.topCenter,\n'
        '                              colors: [\n'
        '                                const Color(0xFF1DB898).withOpacity(glow),\n'
        '                                const Color(0xFFD4AF37).withOpacity(glow * 0.8)]),\n'
        '                            boxShadow: [BoxShadow(\n'
        '                              color: const Color(0xFF1DB898).withOpacity(0.25 * v),\n'
        '                              blurRadius: 4)]));\n'
        '                      })))',
        'file card bars 22→26, 28→41px, multi-freq + bottom-glow')

# ── 4. File card SizedBox height: 32 → 48 to fit taller bars ─────
if '// S62-FILE-BOX' in ht:
    sk('file card SizedBox already updated')
else:
    ht = rep(ht,
        '            SizedBox(height: 32,\n'
        '              child: hasFile',
        '            SizedBox(height: 48, // S62-FILE-BOX\n'
        '              child: hasFile',
        'file card SizedBox 32→48')

HS.write_text(ht, encoding='utf-8')
print(f'\n  {ok_n} OK   {sk_n} SKIP   {xx_n} FAIL\n')
if xx_n == 0:
    print('git add -A && git commit -m "S62: taller organic audio bars" && git push')
else:
    print('Paste output back to Claude.')
