#!/usr/bin/env python3
"""
tilawa_fix_s43 — Full HTML-design UI overhaul
==============================================
Fixes:
  1. _IncensePainter wrapped in AnimatedBuilder (was drawing 1 static frame)
  2. Welcome screen: remove duplicate static 130px logo (only animated 180px stays)
  3. _fileCard → Mihrab portal with animated waveform bars + Elevate button
  4. Stars and GeoPainter made more vivid
  5. _GeoPainter teal → gold tones to match HTML --gold palette
"""
import re
from pathlib import Path

HS = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
WS = Path.home() / 'tilawa-enhancer/lib/screens/welcome_screen.dart'
_log = []

def rep(txt, old, new, lbl):
    if old in txt:
        print(f'  OK  {lbl}')
        _log.append(('OK', lbl))
        return txt.replace(old, new, 1)
    print(f'  XX  NOT FOUND — {lbl}')
    _log.append(('XX', lbl))
    return txt

# ═══════════════════════════════════════════════════════════════════════════════
# home_screen.dart
# ═══════════════════════════════════════════════════════════════════════════════
htxt = HS.read_text(encoding='utf-8')

# ── Fix 1: Animate _IncensePainter ──────────────────────────────────────────
htxt = rep(htxt,
    "            child: IgnorePointer(\n"
    "              child: CustomPaint(painter: _IncensePainter(_geoRotCtrl.value)))),",
    "            child: IgnorePointer(\n"
    "              child: AnimatedBuilder(\n"
    "                animation: _geoRotCtrl,\n"
    "                builder: (_, __) => CustomPaint(\n"
    "                  painter: _IncensePainter(_geoRotCtrl.value))))),",
    'IncensePainter → AnimatedBuilder (was static)')

# ── Fix 2: Stars more vivid ──────────────────────────────────────────────────
htxt = rep(htxt,
    "          size = 0.8 + r.nextDouble() * 2.6,",
    "          size = 1.4 + r.nextDouble() * 2.8,",
    'Stars min size 0.8 → 1.4')

htxt = rep(htxt,
    "      final op = 0.25 + 0.60 * (sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5);",
    "      final op = 0.40 + 0.60 * (sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5);",
    'Stars opacity floor 0.25 → 0.40')

# ── Fix 3: GeoPainter — teal → gold tone, slightly more vivid ────────────────
htxt = rep(htxt,
    "      ..color = _teal.withOpacity(0.10)\n"
    "      ..style = PaintingStyle.stroke\n"
    "      ..strokeWidth = 0.7;",
    "      ..color = const Color(0xFFC8A048).withOpacity(0.07)\n"
    "      ..style = PaintingStyle.stroke\n"
    "      ..strokeWidth = 0.8;",
    'GeoPainter teal→gold, more vivid')

# ── Fix 4: _fileCard → Mihrab portal ─────────────────────────────────────────
NEW_FILE_CARD = r"""  // ── FILE CARD — Mihrab Upload Portal (S43) ───────────────────────────────
  Widget _fileCard(S s) {
    final hasFile = _file != null;
    return GestureDetector(
      onTap: _busy ? null : _pickFile,
      child: Container(
        margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),
        decoration: BoxDecoration(
          color: hasFile
            ? const Color(0xFF0D2B22)
            : const Color(0xFF071A14),
          borderRadius: BorderRadius.circular(22),
          border: Border.all(
            color: hasFile
              ? const Color(0xFFC8A048).withOpacity(0.68)
              : const Color(0xFF1DB898).withOpacity(0.24),
            width: hasFile ? 1.8 : 1.0),
          boxShadow: [BoxShadow(
            color: hasFile
              ? const Color(0xFFC8A048).withOpacity(0.20)
              : const Color(0xFF1DB898).withOpacity(0.08),
            blurRadius: 36, spreadRadius: 2)]),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
          child: Column(children: [
            // ── Upload icon with breathing ring ──
            AnimatedBuilder(
              animation: _glowCtrl,
              builder: (_, __) => Container(
                width: 72, height: 72,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: const Color(0xFFC8A048)
                      .withOpacity(0.38 + 0.32 * _glowCtrl.value),
                    width: 1.5),
                  boxShadow: [BoxShadow(
                    color: const Color(0xFFC8A048)
                      .withOpacity(0.10 + 0.18 * _glowCtrl.value),
                    blurRadius: 18 + 16 * _glowCtrl.value)]),
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 380),
                  switchInCurve: Curves.easeOutBack,
                  transitionBuilder: (child, anim) => ScaleTransition(
                    scale: anim, child: child),
                  child: Icon(
                    hasFile ? Icons.audio_file_rounded : Icons.upload_rounded,
                    key: ValueKey(hasFile),
                    color: const Color(0xFFC8A048), size: 34)))),
            const SizedBox(height: 16),
            // ── Animated waveform bars (file selected) / empty placeholder ──
            SizedBox(height: 32,
              child: hasFile
                ? AnimatedBuilder(
                    animation: _audioBarsCtrl,
                    builder: (_, __) => Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: List.generate(22, (i) {
                        final phase = (_audioBarsCtrl.value + i * 0.13) % 1.0;
                        final ht = 4.0 + 24.0 *
                          sin(phase * pi).abs() *
                          (0.4 + 0.6 * sin(i * 0.95).abs());
                        return Container(
                          width: 3, height: ht,
                          margin: const EdgeInsets.symmetric(horizontal: 1.5),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(2),
                            gradient: const LinearGradient(
                              begin: Alignment.bottomCenter,
                              end: Alignment.topCenter,
                              colors: [Color(0xFF1DB898), Color(0xFFC8A048)])));
                      })))
                : Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(18, (i) => Container(
                      width: 3, height: 4.0 + 14.0 * sin(i * 0.45).abs(),
                      margin: const EdgeInsets.symmetric(horizontal: 1.5),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(2),
                        color: const Color(0xFF1DB898).withOpacity(0.20)))))),
            const SizedBox(height: 12),
            // ── Filename / pick label ──
            Text(
              hasFile ? _file!.path.split('/').last : s.pickFile,
              textDirection: TextDirection.rtl,
              textAlign: TextAlign.center,
              maxLines: 2, overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: hasFile
                  ? const Color(0xFFE2CFA0)
                  : const Color(0xFF8AACBA),
                fontSize: hasFile ? 13 : 15,
                fontWeight: hasFile ? FontWeight.w500 : FontWeight.w600,
                letterSpacing: hasFile ? 0 : 0.4)),
            if (hasFile) ...[
              const SizedBox(height: 4),
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                Text(_sizeLabel,
                  style: const TextStyle(
                    color: Color(0xFF8B949E), fontSize: 11)),
                if (_isLarge) ...[
                  const SizedBox(width: 8),
                  _badge(s.chunkedBadge, 'gold'),
                ],
              ]),
              if (_fileBytes > 0) ...[
                const SizedBox(height: 3),
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  const Icon(Icons.timer_outlined,
                    size: 10, color: Color(0xFF3D5A65)),
                  const SizedBox(width: 3),
                  Text('${s.estTime}: ${_estimatedTime()}',
                    style: const TextStyle(
                      color: Color(0xFF3D5A65), fontSize: 10)),
                ]),
              ],
            ],
            const SizedBox(height: 6),
            Text(s.sizeLimit,
              style: const TextStyle(
                color: Color(0xFF3D5A65), fontSize: 10,
                letterSpacing: 0.4)),
            if (hasFile) ...[
              const SizedBox(height: 18),
              // ── Elevate button — gold gradient ──
              GestureDetector(
                onTap: (_busy || !_serverUp) ? null : () {
                  HapticFeedback.mediumImpact();
                  _process();
                },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(14),
                    gradient: (_busy || !_serverUp)
                      ? LinearGradient(colors: [
                          const Color(0xFF1A1200).withOpacity(0.6),
                          const Color(0xFF1A1200).withOpacity(0.6)])
                      : const LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [
                            Color(0xFF6B4518),
                            Color(0xFFC8A048),
                            Color(0xFFF0D882),
                            Color(0xFFC8A048),
                          ],
                          stops: [0.0, 0.3, 0.6, 1.0]),
                    boxShadow: (_busy || !_serverUp) ? null : [
                      BoxShadow(
                        color: const Color(0xFFC8A048).withOpacity(0.40),
                        blurRadius: 24, offset: const Offset(0, 6)),
                    ]),
                  child: _busy
                    ? Row(mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const SizedBox(width: 16, height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Color(0xFF020D0C))),
                          const SizedBox(width: 10),
                          Text(s.processing,
                            style: const TextStyle(
                              color: Color(0xFF020D0C),
                              fontWeight: FontWeight.w900, fontSize: 14,
                              letterSpacing: 0.5)),
                        ])
                    : Text(
                        s.ar ? 'ارفع التلاوة' : 'Elevate This Recitation',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: (_busy || !_serverUp)
                            ? const Color(0xFF3D5A65)
                            : const Color(0xFF020D0C),
                          fontWeight: FontWeight.w900, fontSize: 14,
                          letterSpacing: 0.8)))),
            ],
          ]),
        ),
      ),
    );
  }"""

# Replace the old _fileCard with regex (robust across whitespace differences)
pattern = r'  // ── FILE CARD ──+\n  Widget _fileCard\(S s\) => GestureDetector\(.*?\n  \);'
new_htxt, n = re.subn(pattern, NEW_FILE_CARD, htxt, count=1, flags=re.DOTALL)
if n == 1:
    htxt = new_htxt
    print('  OK  _fileCard → Mihrab portal with waveform + Elevate button')
    _log.append(('OK', 'Mihrab file card'))
else:
    print('  XX  _fileCard regex did not match — check anchor')
    _log.append(('XX', 'Mihrab file card'))

HS.write_text(htxt, encoding='utf-8')
print('  → home_screen.dart saved')

# ═══════════════════════════════════════════════════════════════════════════════
# welcome_screen.dart — remove duplicate static logo
# ═══════════════════════════════════════════════════════════════════════════════
wtxt = WS.read_text(encoding='utf-8')

# The static 130×130 logo comes first in the Column, remove it entirely
wtxt = rep(wtxt,
    "          // S33-WELCOME-LOGO\n"
    "          Center(\n"
    "            child: Container(\n"
    "              margin: const EdgeInsets.only(bottom: 20, top: 8),\n"
    "              width: 130, height: 130,\n"
    "              decoration: const BoxDecoration(\n"
    "                shape: BoxShape.circle,\n"
    "                boxShadow: [\n"
    "                  BoxShadow(\n"
    "                    color: Color(0x59D4AF37),\n"
    "                    blurRadius: 40, spreadRadius: 4),\n"
    "                  BoxShadow(\n"
    "                    color: Color(0x331C8EA8),\n"
    "                    blurRadius: 70, spreadRadius: 10),\n"
    "                ]),\n"
    "              child: ClipOval(child: Image.asset('assets/images/logo.png',\n"
    "                fit: BoxFit.cover, width: 130, height: 130)))),",
    "          // S43: single animated logo below (static duplicate removed)",
    'Welcome: remove duplicate static 130px logo')

WS.write_text(wtxt, encoding='utf-8')
print('  → welcome_screen.dart saved')

# ═══════════════════════════════════════════════════════════════════════════════
ok = sum(1 for s, _ in _log if s == 'OK')
xx = sum(1 for s, _ in _log if s == 'XX')
print(f'\n  {"✅" if xx == 0 else "⚠ " + str(xx) + " FAILED"}  {ok} OK')
if xx:
    print('  Run the diag script to check exact current anchors.')
print('\n  git add -A && git commit -m "S43: mihrab portal + waveform + animate incense + fix welcome logo" && git push')
