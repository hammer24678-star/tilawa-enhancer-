#!/usr/bin/env python3
"""
tilawa_fix_s53.py — Engine color propagation (run AFTER s52)
=============================================================
Requires: _engineColor getter added by s52.
Fails gracefully if anchors not found (s52 not yet run).

Patches:
  A  _geoSep  left  gradient line  → _engineColor
  B  _geoSep  label text color     → _engineColor
  C  _geoSep  right gradient line  → _engineColor
  D  _geoDiamond color + glow      → _engineColor
  E  _fileCard breathing ring      → _engineColor
  F  _fileCard border/shadow       → _engineColor (hasFile state)
  G  _progressCard border          → _engineColor

Rule 45: comment strings contain NO raw brackets or parens.
Verify every anchor against dart dump before running.
"""
from pathlib import Path
from datetime import datetime

HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
txt = HS.read_text(encoding='utf-8')
_log = []

def ok(l): print(f'  OK  {l}'); _log.append(('OK', l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX', l))
def rep(old, new, lbl):
    global txt
    if old in txt:
        txt = txt.replace(old, new, 1); ok(lbl)
    else:
        xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s53  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# ═══════════════════════════════════════════════════════════
# Pre-check: ensure _engineColor exists (s52 has run)
# ═══════════════════════════════════════════════════════════
if '_engineColor' not in txt:
    print('\n  !! ABORT: _engineColor not found — run s52 first\n')
    exit(1)
ok('Pre-check: _engineColor present')

# ═══════════════════════════════════════════════════════════
# A — _geoSep left gradient: transparent → _engineColor
# Dart lines 1341-1344 (verified from 2026-05-23 dump)
# ═══════════════════════════════════════════════════════════
rep(
    "        Expanded(child: Container(height: 1,\n"
    "          decoration: const BoxDecoration(gradient: LinearGradient(\n"
    "            colors: [Colors.transparent, Color(0xFFC8A048)],\n"
    "            stops: [0.0, 1.0])))),",

    "        Expanded(child: Container(height: 1,\n"
    "          decoration: BoxDecoration(gradient: LinearGradient(\n"
    "            colors: [Colors.transparent, _engineColor],\n"
    "            stops: [0.0, 1.0])))),",
    'A _geoSep left gradient uses _engineColor')

# ═══════════════════════════════════════════════════════════
# B — _geoSep label text: static gold → _engineColor
# Dart lines 1351-1353
# ═══════════════════════════════════════════════════════════
rep(
    "              child: Text(label.toUpperCase(), style: const TextStyle(\n"
    "                color: Color(0xFFC8A048), fontSize: 9,\n"
    "                letterSpacing: 0.22, fontWeight: FontWeight.w500))),",

    "              child: Text(label.toUpperCase(), style: TextStyle(\n"
    "                color: _engineColor, fontSize: 9,\n"
    "                letterSpacing: 0.22, fontWeight: FontWeight.w500))),",
    'B _geoSep label text uses _engineColor')

# ═══════════════════════════════════════════════════════════
# C — _geoSep right gradient: _engineColor → transparent
# Dart lines 1356-1359
# ═══════════════════════════════════════════════════════════
rep(
    "        Expanded(child: Container(height: 1,\n"
    "          decoration: const BoxDecoration(gradient: LinearGradient(\n"
    "            colors: [Color(0xFFC8A048), Colors.transparent],\n"
    "            stops: [0.0, 1.0])))),",

    "        Expanded(child: Container(height: 1,\n"
    "          decoration: BoxDecoration(gradient: LinearGradient(\n"
    "            colors: [_engineColor, Colors.transparent],\n"
    "            stops: [0.0, 1.0])))),",
    'C _geoSep right gradient uses _engineColor')

# ═══════════════════════════════════════════════════════════
# D — _geoDiamond: static gold fill + glow → _engineColor
# Dart lines 1362-1371 (exact from dump)
# ═══════════════════════════════════════════════════════════
rep(
    "    Widget _geoDiamond() => Transform.rotate(\n"
    "      angle: 0.7854, // 45 degrees\n"
    "      child: Container(\n"
    "        width: 6, height: 6,\n"
    "        decoration: BoxDecoration(\n"
    "          color: const Color(0xFFC8A048),\n"
    "          borderRadius: BorderRadius.circular(1),\n"
    "          boxShadow: [const BoxShadow(\n"
    "            color: Color(0x80C8A048), blurRadius: 5)])));",

    "    Widget _geoDiamond() => Transform.rotate(\n"
    "      angle: 0.7854,\n"
    "      child: Container(\n"
    "        width: 6, height: 6,\n"
    "        decoration: BoxDecoration(\n"
    "          color: _engineColor,\n"
    "          borderRadius: BorderRadius.circular(1),\n"
    "          boxShadow: [BoxShadow(\n"
    "            color: _engineColor.withOpacity(0.50), blurRadius: 5)])));",
    'D _geoDiamond fill and glow use _engineColor')

# ═══════════════════════════════════════════════════════════
# E — _fileCard upload ring: breathing border + shadow glow
# Dart lines 1418-1424 (exact from dump)
# ═══════════════════════════════════════════════════════════
rep(
    "                    color: const Color(0xFFC8A048)\n"
    "                        .withOpacity(0.38 + 0.32 * _glowCtrl.value),\n"
    "                      width: 1.5),\n"
    "                    boxShadow: [BoxShadow(\n"
    "                      color: const Color(0xFFC8A048)\n"
    "                        .withOpacity(0.10 + 0.18 * _glowCtrl.value),\n"
    "                      blurRadius: 18 + 16 * _glowCtrl.value)]),",

    "                    color: _engineColor\n"
    "                        .withOpacity(0.38 + 0.32 * _glowCtrl.value),\n"
    "                      width: 1.5),\n"
    "                    boxShadow: [BoxShadow(\n"
    "                      color: _engineColor\n"
    "                        .withOpacity(0.10 + 0.18 * _glowCtrl.value),\n"
    "                      blurRadius: 18 + 16 * _glowCtrl.value)]),",
    'E _fileCard upload ring uses _engineColor')

# ═══════════════════════════════════════════════════════════
# F — _fileCard container border/shadow (hasFile state only)
# Dart lines 1398-1407 (exact from dump)
# ═══════════════════════════════════════════════════════════
rep(
    "            border: Border.all(\n"
    "              color: hasFile\n"
    "                ? const Color(0xFFC8A048).withOpacity(0.68)\n"
    "                : const Color(0xFF1DB898).withOpacity(0.24),\n"
    "              width: hasFile ? 1.8 : 1.0),\n"
    "            boxShadow: [BoxShadow(\n"
    "              color: hasFile\n"
    "                ? const Color(0xFFC8A048).withOpacity(0.20)\n"
    "                : const Color(0xFF1DB898).withOpacity(0.08),\n"
    "              blurRadius: 36, spreadRadius: 2)]),",

    "            border: Border.all(\n"
    "              color: hasFile\n"
    "                ? _engineColor.withOpacity(0.68)\n"
    "                : const Color(0xFF1DB898).withOpacity(0.24),\n"
    "              width: hasFile ? 1.8 : 1.0),\n"
    "            boxShadow: [BoxShadow(\n"
    "              color: hasFile\n"
    "                ? _engineColor.withOpacity(0.20)\n"
    "                : const Color(0xFF1DB898).withOpacity(0.08),\n"
    "              blurRadius: 36, spreadRadius: 2)]),",
    'F _fileCard hasFile border and glow use _engineColor')

# ═══════════════════════════════════════════════════════════
# G — _progressCard border tint: static gold → _engineColor
# Dart line 1783 (exact from dump)
# ═══════════════════════════════════════════════════════════
rep(
    "          color: const Color(0xFFD4AF37).withOpacity(0.18), width: 0.9),",

    "          color: _engineColor.withOpacity(0.20), width: 0.9),",
    'G _progressCard border uses _engineColor')

# ═══════════════════════════════════════════════════════════
# Write + report
# ═══════════════════════════════════════════════════════════
HS.write_text(txt, encoding='utf-8')
ok('home_screen.dart saved')

print(f'\n{"="*58}')
for s, l in _log:
    print(f'  {"OK" if s == "OK" else "XX"}  {l}')
ok_n = sum(1 for s, _ in _log if s == 'OK')
xx_n = sum(1 for s, _ in _log if s == 'XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S53: engine color → geoSep, geoDiamond, fileCard ring, progressCard" && git push\n')
else:
    print('  Fix XX items above. Re-run diag to get exact anchors.\n')
