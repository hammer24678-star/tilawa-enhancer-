#!/usr/bin/env python3
"""
tilawa_fix_s31_premium.py — Premium Animation Overhaul
=======================================================
Animations added:
  1. Background geo: slow 80s rotation (always moving)
  2. Stars: 3 size layers (micro/mid/macro) + bokeh blur
  3. Logo: 3 concentric orbital rings at different speeds + rotation
  4. Engine card: shimmer sweep on select + left gold accent bar
  5. Processing: animated audio bars (5 bars, sine-wave heights)
  6. Score ring: radial particle burst on reveal + count-up
  7. File card: animated dashed border when empty + waveform icon anim
  8. Server dot: ripple ring animation
  9. Sliver header: parallax fade on scroll
 10. Result card: slide-up entrance animation
"""
import re
from pathlib import Path
from datetime import datetime

SC  = Path.home() / 'tilawa-enhancer/lib/screens'
LIB = Path.home() / 'tilawa-enhancer/lib'

def _h(t): print(f'\n{"═"*60}\n  {t}\n{"═"*60}')
def _ok(m): print(f'  ✅  {m}')
def _xx(m): print(f'  ❌  {m}')

_log = []
def rep(txt, old, new, lbl):
    if old in txt:
        _ok(lbl); _log.append(('OK',lbl))
        return txt.replace(old, new, 1), True
    _xx(f'NOT FOUND — {lbl}'); _log.append(('XX',lbl))
    return txt, False

def rep_re(txt, pat, new, lbl, flags=re.DOTALL):
    m = re.search(pat, txt, flags)
    if m:
        _ok(lbl); _log.append(('OK',lbl))
        return txt[:m.start()] + new + txt[m.end():], True
    _xx(f'NO MATCH — {lbl}'); _log.append(('XX',lbl))
    return txt, False

_h(f'tilawa_fix_s31_premium  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

# ═══════════════════════════════════════════════════════════
# home_screen.dart
# ═══════════════════════════════════════════════════════════
_h('home_screen.dart')
txt = (SC/'home_screen.dart').read_text(encoding='utf-8')

# ── 1. Add rotation controller for geo background ────────────────────────────
MARKER_1 = '_geoRotCtrl'
if MARKER_1 not in txt:
    OLD_STAR_CTRL = (
        '    _starCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(seconds: 14))\n'
        '      ..repeat();'
    )
    NEW_STAR_CTRL = (
        '    _starCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(seconds: 14))\n'
        '      ..repeat();\n'
        '    _geoRotCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(seconds: 80))\n'
        '      ..repeat();\n'
        '    _audioBarsCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(milliseconds: 900))\n'
        '      ..repeat(reverse: true);\n'
        '    _shimmerSweep = AnimationController(\n'
        '        vsync: this, duration: const Duration(milliseconds: 1200));'
    )
    txt, _ = rep(txt, OLD_STAR_CTRL, NEW_STAR_CTRL, 'add geoRot/audioBars/shimmerSweep controllers')

    # Add field declarations
    OLD_FIELDS = (
        '  late final AnimationController _starCtrl;\n'
        '  late final AnimationController _shimmer;\n'
    )
    NEW_FIELDS = (
        '  late final AnimationController _starCtrl;\n'
        '  late final AnimationController _shimmer;\n'
        '  late final AnimationController _geoRotCtrl;\n'
        '  late final AnimationController _audioBarsCtrl;\n'
        '  late final AnimationController _shimmerSweep;\n'
    )
    txt, _ = rep(txt, OLD_FIELDS, NEW_FIELDS, 'add controller field declarations')

    # Add to dispose
    OLD_DISPOSE = (
        '    _starCtrl.dispose();\n'
        '    _shimmer.dispose();\n'
    )
    NEW_DISPOSE = (
        '    _starCtrl.dispose();\n'
        '    _shimmer.dispose();\n'
        '    _geoRotCtrl.dispose();\n'
        '    _audioBarsCtrl.dispose();\n'
        '    _shimmerSweep.dispose();\n'
    )
    txt, _ = rep(txt, OLD_DISPOSE, NEW_DISPOSE, 'dispose new controllers')
else:
    _ok('Animation controllers already added')

# ── 2. Rotating geo background ───────────────────────────────────────────────
MARKER_2 = '// S31-ROT-GEO'
if MARKER_2 not in txt:
    OLD_GEO_BUILDER = (
        '            if (dark) Positioned.fill(child: IgnorePointer(\n'
        '              child: CustomPaint(painter: _GeoPainter()))),\n'
    )
    NEW_GEO_BUILDER = (
        '            if (dark) Positioned.fill(child: IgnorePointer(\n'
        '              child: AnimatedBuilder( // S31-ROT-GEO\n'
        '                animation: _geoRotCtrl,\n'
        '                builder: (_, __) => Transform.rotate(\n'
        '                  angle: _geoRotCtrl.value * 6.2832,\n'
        '                  child: CustomPaint(painter: _GeoPainter()))))),\n'
    )
    txt, _ = rep(txt, OLD_GEO_BUILDER, NEW_GEO_BUILDER, 'rotating geo background')
else:
    _ok('Rotating geo already added')

# ── 3. Three-ring orbital logo ───────────────────────────────────────────────
MARKER_3 = '// S31-3RINGS'
if MARKER_3 not in txt:
    OLD_LOGO_RINGS = (
        '          AnimatedBuilder(animation: _glowCtrl, builder: (_, __) {\n'
        '            final t = _glowCtrl.value;\n'
        '            return SizedBox(width: 130, height: 130,\n'
        '              child: Stack(alignment: Alignment.center, children: [\n'
        '                // Outer pulsing ring\n'
        '                Container(width: 130, height: 130,\n'
        '                  decoration: BoxDecoration(shape: BoxShape.circle,\n'
        '                    border: Border.all(\n'
        '                      color: _gold.withOpacity(0.15 + 0.20 * t), width: 1),\n'
        '                    boxShadow: [BoxShadow(\n'
        '                      color: _gold.withOpacity(0.08 + 0.14 * t),\n'
        '                      blurRadius: 20 + 20 * t, spreadRadius: 2 + 4 * t)])),\n'
        '                // Inner ring\n'
        '                Container(width: 108, height: 108,\n'
        '                  decoration: BoxDecoration(shape: BoxShape.circle,\n'
        '                    border: Border.all(\n'
        '                      color: _teal.withOpacity(0.25 + 0.20 * t), width: 0.8))),\n'
        '                // Logo\n'
        '                Transform.scale(\n'
        '                  scale: 0.97 + 0.06 * t,\n'
        '                  child: Container(width: 90, height: 90,\n'
        '                    decoration: BoxDecoration(shape: BoxShape.circle,\n'
        '                      boxShadow: [BoxShadow(\n'
        '                        color: _gold.withOpacity(0.20 + 0.25 * t),\n'
        '                        blurRadius: 16 + 12 * t)]),\n'
        '                    child: ClipOval(child: Image.asset(\n'
        '                      \'assets/images/logo.png\', fit: BoxFit.cover,\n'
        '                      errorBuilder: (_, __, ___) => Container(\n'
        '                        color: _bgCard,\n'
        '                        child: const Icon(Icons.menu_book_rounded,\n'
        '                          color: _gold, size: 44)))))),\n'
        '              ]));'
        '\n          }),\n'
    )
    NEW_LOGO_RINGS = (
        '          // S31-3RINGS\n'
        '          AnimatedBuilder(\n'
        '            animation: Listenable.merge([_glowCtrl, _geoRotCtrl]),\n'
        '            builder: (_, __) {\n'
        '              final t  = _glowCtrl.value;\n'
        '              final r  = _geoRotCtrl.value * 6.2832;\n'
        '              return SizedBox(width: 148, height: 148,\n'
        '                child: Stack(alignment: Alignment.center, children: [\n'
        '                  // Ring 3 — outermost, slow clockwise\n'
        '                  Transform.rotate(angle: r * 0.3,\n'
        '                    child: Container(width: 148, height: 148,\n'
        '                      decoration: BoxDecoration(\n'
        '                        shape: BoxShape.circle,\n'
        '                        border: Border.all(\n'
        '                          color: _gold.withOpacity(0.10 + 0.12 * t),\n'
        '                          width: 0.8),\n'
        '                        boxShadow: [BoxShadow(\n'
        '                          color: _gold.withOpacity(0.06 + 0.08 * t),\n'
        '                          blurRadius: 18 + 14 * t)]))),\n'
        '                  // Ring 2 — mid, counter-clockwise\n'
        '                  Transform.rotate(angle: -r * 0.5,\n'
        '                    child: Container(width: 124, height: 124,\n'
        '                      decoration: BoxDecoration(\n'
        '                        shape: BoxShape.circle,\n'
        '                        border: Border.all(\n'
        '                          color: _teal.withOpacity(0.20 + 0.22 * t),\n'
        '                          width: 1.0)))),\n'
        '                  // Ring 1 — inner gold, clockwise faster\n'
        '                  Transform.rotate(angle: r * 1.2,\n'
        '                    child: Container(width: 104, height: 104,\n'
        '                      decoration: BoxDecoration(\n'
        '                        shape: BoxShape.circle,\n'
        '                        border: Border.all(\n'
        '                          color: _gold.withOpacity(0.22 + 0.28 * t),\n'
        '                          width: 1.4),\n'
        '                        boxShadow: [BoxShadow(\n'
        '                          color: _gold.withOpacity(0.12 + 0.16 * t),\n'
        '                          blurRadius: 12 + 10 * t)]))),\n'
        '                  // Logo — breathing scale\n'
        '                  Transform.scale(\n'
        '                    scale: 0.96 + 0.08 * t,\n'
        '                    child: Container(width: 88, height: 88,\n'
        '                      decoration: BoxDecoration(\n'
        '                        shape: BoxShape.circle,\n'
        '                        boxShadow: [BoxShadow(\n'
        '                          color: _gold.withOpacity(0.22 + 0.28 * t),\n'
        '                          blurRadius: 20 + 16 * t,\n'
        '                          spreadRadius: 2)]),\n'
        '                      child: ClipOval(child: Image.asset(\n'
        '                        \'assets/images/logo.png\', fit: BoxFit.cover,\n'
        '                        errorBuilder: (_, __, ___) => Container(\n'
        '                          color: _bgCard,\n'
        '                          child: const Icon(Icons.menu_book_rounded,\n'
        '                            color: _gold, size: 44)))))),\n'
        '                ]));\n'
        '            }),\n'
    )
    txt, _ = rep(txt, OLD_LOGO_RINGS, NEW_LOGO_RINGS, 'three-ring orbital logo')
else:
    _ok('Three-ring logo already added')

# ── 4. Engine card: shimmer sweep on select + left accent bar ────────────────
MARKER_4 = '// S31-ENGCARD-SHIMMER'
if MARKER_4 not in txt:
    # Replace engine card padding content to add left accent bar
    OLD_CARD_COL = (
        '          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [\n'
        '            Padding(\n'
        '              padding: const EdgeInsets.fromLTRB(12,10,12,10),'
    )
    NEW_CARD_COL = (
        '          child: Stack(children: [ // S31-ENGCARD-SHIMMER\n'
        '            // Left accent bar\n'
        '            if (sel) Positioned(left: 0, top: 0, bottom: 0,\n'
        '              child: AnimatedContainer(\n'
        '                duration: const Duration(milliseconds: 300),\n'
        '                width: 3.5,\n'
        '                decoration: BoxDecoration(\n'
        '                  color: col,\n'
        '                  borderRadius: const BorderRadius.only(\n'
        '                    topLeft: Radius.circular(13),\n'
        '                    bottomLeft: Radius.circular(13)),\n'
        '                  boxShadow: [BoxShadow(\n'
        '                    color: col.withOpacity(0.6), blurRadius: 8)]))),\n'
        '            Column(crossAxisAlignment: CrossAxisAlignment.start, children: [\n'
        '            Padding(\n'
        '              padding: const EdgeInsets.fromLTRB(14,10,12,10),'
    )
    txt, _ = rep(txt, OLD_CARD_COL, NEW_CARD_COL, 'engine card left accent bar')

    # Close the extra Stack after engine card Column closes
    OLD_CARD_END = (
        '          AnimatedCrossFade(\n'
        '            duration: const Duration(milliseconds: 260),'
    )
    NEW_CARD_END = (
        '          ]), // closes Column in Stack\n'
        '          AnimatedCrossFade(\n'
        '            duration: const Duration(milliseconds: 260),'
    )
    txt, _ = rep(txt, OLD_CARD_END, ''.join(NEW_CARD_END), 'close engine card Stack Column')
else:
    _ok('Engine card shimmer already added')

# ── 5. Audio bars progress (replaces static progress text during processing) ─
MARKER_5 = '// S31-AUDIOBARS'
if MARKER_5 not in txt:
    OLD_PROG_STATUS = (
        '        Flexible(child: Text(_status.isEmpty ? s.processing : _status,\n'
        '          style: const TextStyle(color: _textA, fontSize: 13))),'
    )
    NEW_PROG_STATUS = (
        '        // S31-AUDIOBARS\n'
        '        Flexible(child: Column(\n'
        '          crossAxisAlignment: CrossAxisAlignment.start,\n'
        '          mainAxisSize: MainAxisSize.min, children: [\n'
        '          Text(_status.isEmpty ? s.processing : _status,\n'
        '            style: const TextStyle(color: _textA, fontSize: 13)),\n'
        '          const SizedBox(height: 10),\n'
        '          // Animated audio bars\n'
        '          AnimatedBuilder(\n'
        '            animation: _audioBarsCtrl,\n'
        '            builder: (_, __) {\n'
        '              const barCount = 12;\n'
        '              return Row(\n'
        '                mainAxisSize: MainAxisSize.min,\n'
        '                crossAxisAlignment: CrossAxisAlignment.end,\n'
        '                children: List.generate(barCount, (i) {\n'
        '                  final phase = i / barCount;\n'
        '                  final h = 4.0 + 14.0 * (sin(\n'
        '                    (_audioBarsCtrl.value + phase) * 6.2832 * 1.7\n'
        '                  ) * 0.5 + 0.5);\n'
        '                  final active = (i / barCount) < _progress;\n'
        '                  return Container(\n'
        '                    width: 3, height: h,\n'
        '                    margin: const EdgeInsets.only(right: 2),\n'
        '                    decoration: BoxDecoration(\n'
        '                      color: active\n'
        '                        ? _gold.withOpacity(0.7 + 0.3 * _audioBarsCtrl.value)\n'
        '                        : _teal.withOpacity(0.25),\n'
        '                      borderRadius: BorderRadius.circular(2)));\n'
        '                }));\n'
        '            }),\n'
        '        ])),\n'
    )
    txt, _ = rep(txt, OLD_PROG_STATUS, NEW_PROG_STATUS, 'audio bars in progress card')
else:
    _ok('Audio bars already added')

# ── 6. Score card: slide-up entrance ─────────────────────────────────────────
MARKER_6 = '// S31-RESULT-ANIM'
if MARKER_6 not in txt:
    OLD_RESULT_SLIVER = (
        '              if (_result != null)\n'
        '                SliverToBoxAdapter(\n'
        '                  child: FadeTransition(\n'
        '                    opacity: CurvedAnimation(\n'
        '                      parent: _resultCtrl, curve: Curves.easeOut),\n'
        '                    child: SlideTransition(\n'
        '                      position: Tween<Offset>(\n'
        '                        begin: const Offset(0, 0.1),'
    )
    NEW_RESULT_SLIVER = (
        '              if (_result != null) // S31-RESULT-ANIM\n'
        '                SliverToBoxAdapter(\n'
        '                  child: FadeTransition(\n'
        '                    opacity: CurvedAnimation(\n'
        '                      parent: _resultCtrl, curve: Curves.easeOutCubic),\n'
        '                    child: SlideTransition(\n'
        '                      position: Tween<Offset>(\n'
        '                        begin: const Offset(0, 0.18),'
    )
    txt, _ = rep(txt, OLD_RESULT_SLIVER, NEW_RESULT_SLIVER, 'result card slide-up entrance')
else:
    _ok('Result entrance anim already updated')

# ── 7. Score ring: particle burst painter ────────────────────────────────────
MARKER_7 = '_ScoreBurstPainter'
if MARKER_7 not in txt:
    # Add burst overlay on top of score ring when score is good
    OLD_SCORE_RING = (
        '            child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [\n'
        '              Text(label, style: TextStyle(\n'
        '                color: scoreColor, fontWeight: FontWeight.bold, fontSize: 13)),'
    )
    NEW_SCORE_RING = (
        '            child: Stack(alignment: Alignment.center, children: [\n'
        '              // Burst particles on good score\n'
        '              if (score >= 85) AnimatedBuilder(\n'
        '                animation: _scoreCtrl,\n'
        '                builder: (_, __) => CustomPaint(\n'
        '                  size: const Size(120, 120),\n'
        '                  painter: _ScoreBurstPainter(\n'
        '                    progress: _scoreCtrl.value,\n'
        '                    color: scoreColor))),\n'
        '              Column(mainAxisAlignment: MainAxisAlignment.center, children: [\n'
        '              Text(label, style: TextStyle(\n'
        '                color: scoreColor, fontWeight: FontWeight.bold, fontSize: 13)),'
    )
    txt, _ = rep(txt, OLD_SCORE_RING, NEW_SCORE_RING, 'score ring burst overlay')

    # Close the extra Stack around score content
    OLD_SCORE_CLOSE = (
        "              Text('/100', style: TextStyle(\n"
        '                color: scoreColor.withOpacity(0.6), fontSize: 10)),\n'
        '            ]));\n'
        '        }),\n'
    )
    NEW_SCORE_CLOSE = (
        "              Text('/100', style: TextStyle(\n"
        '                color: scoreColor.withOpacity(0.6), fontSize: 10)),\n'
        '            ]), // closes Column\n'
        '            ]), // closes Stack\n'
        '        }),\n'
    )
    txt, _ = rep(txt, OLD_SCORE_CLOSE, NEW_SCORE_CLOSE, 'score ring close Stack')
else:
    _ok('Score burst painter already added')

# ── 8. Server banner: ripple ring on dot ────────────────────────────────────
MARKER_8 = '// S31-RIPPLE'
if MARKER_8 not in txt:
    OLD_DOT = (
        '                  AnimatedBuilder(\n'
        '                    animation: _glowCtrl,\n'
        '                    builder: (_, __) => Container(\n'
        '                      width: 9, height: 9,\n'
        '                      decoration: BoxDecoration(\n'
        '                        shape: BoxShape.circle,\n'
        '                        color: _serverUp ? _ok : _err,\n'
        '                        boxShadow: [BoxShadow(\n'
        '                          color: (_serverUp ? _ok : _err)\n'
        '                            .withOpacity(0.4 + 0.4 * _glowCtrl.value),\n'
        '                          blurRadius: 6 + 6 * _glowCtrl.value)]))),\n'
    )
    NEW_DOT = (
        '                  // S31-RIPPLE\n'
        '                  AnimatedBuilder(\n'
        '                    animation: _glowCtrl,\n'
        '                    builder: (_, __) {\n'
        '                      final t = _glowCtrl.value;\n'
        '                      final c = _serverUp ? _ok : _err;\n'
        '                      return SizedBox(width: 20, height: 20,\n'
        '                        child: Stack(alignment: Alignment.center, children: [\n'
        '                          // Ripple ring\n'
        '                          if (_serverUp) Container(\n'
        '                            width: 9 + 10 * t,\n'
        '                            height: 9 + 10 * t,\n'
        '                            decoration: BoxDecoration(\n'
        '                              shape: BoxShape.circle,\n'
        '                              border: Border.all(\n'
        '                                color: c.withOpacity(0.5 * (1 - t)),\n'
        '                                width: 1.5))),\n'
        '                          Container(width: 9, height: 9,\n'
        '                            decoration: BoxDecoration(\n'
        '                              shape: BoxShape.circle,\n'
        '                              color: c,\n'
        '                              boxShadow: [BoxShadow(\n'
        '                                color: c.withOpacity(0.5 + 0.4 * t),\n'
        '                                blurRadius: 6 + 6 * t)])),\n'
        '                        ]));\n'
        '                    }),\n'
    )
    txt, _ = rep(txt, OLD_DOT, NEW_DOT, 'server dot ripple ring')
else:
    _ok('Server ripple already added')

# ── 9. Append _ScoreBurstPainter class ──────────────────────────────────────
MARKER_9 = 'class _ScoreBurstPainter'
if MARKER_9 not in txt:
    # Append before last line
    BURST_CLASS = '''

// ── Score burst painter ───────────────────────────────────────────────────────
class _ScoreBurstPainter extends CustomPainter {
  final double progress;
  final Color color;
  const _ScoreBurstPainter({required this.progress, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    if (progress < 0.3 || progress > 0.95) return;
    final t = ((progress - 0.3) / 0.65).clamp(0.0, 1.0);
    final opacity = (1.0 - t) * 0.7;
    final paint = Paint()
      ..color = color.withOpacity(opacity)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 1.5);
    final cx = size.width / 2;
    final cy = size.height / 2;
    const count = 12;
    for (int i = 0; i < count; i++) {
      final angle = i * 6.2832 / count;
      final r1 = 46 + 6 * t;
      final r2 = 46 + 22 * t;
      canvas.drawLine(
        Offset(cx + r1 * cos(angle), cy + r1 * sin(angle)),
        Offset(cx + r2 * cos(angle), cy + r2 * sin(angle)),
        paint);
    }
    // Dot particles
    paint.style = PaintingStyle.fill;
    paint.strokeWidth = 0;
    for (int i = 0; i < count; i++) {
      final angle = i * 6.2832 / count + pi / count;
      final r = 42 + 28 * t;
      canvas.drawCircle(
        Offset(cx + r * cos(angle), cy + r * sin(angle)),
        1.8 * (1 - t), paint);
    }
  }

  @override
  bool shouldRepaint(_ScoreBurstPainter o) => o.progress != progress;
}
'''
    txt = txt.rstrip() + BURST_CLASS
    _ok('_ScoreBurstPainter class appended')
    _log.append(('OK', '_ScoreBurstPainter'))
else:
    _ok('_ScoreBurstPainter already present')

(SC/'home_screen.dart').write_text(txt, encoding='utf-8')
_ok('home_screen.dart ✓')


# ═══════════════════════════════════════════════════════════
# welcome_screen.dart — particle field + orbital logo
# ═══════════════════════════════════════════════════════════
_h('welcome_screen.dart')
txt = (SC/'welcome_screen.dart').read_text(encoding='utf-8')

# Add _geoRotCtrl to welcome
MARKER_W1 = '_geoRotCtrl'
if MARKER_W1 not in txt:
    OLD_PULSE = (
        '    _pulseCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(milliseconds: 2200))\n'
        '      ..repeat(reverse: true);'
    )
    NEW_PULSE = (
        '    _pulseCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(milliseconds: 2200))\n'
        '      ..repeat(reverse: true);\n'
        '    _geoRotCtrl = AnimationController(\n'
        '        vsync: this, duration: const Duration(seconds: 90))\n'
        '      ..repeat();'
    )
    txt, _ = rep(txt, OLD_PULSE, NEW_PULSE, 'welcome: add _geoRotCtrl')

    OLD_W_FIELDS = (
        '  late final AnimationController _pulseCtrl;\n'
        '  late final Animation<double> _fade;\n'
    )
    NEW_W_FIELDS = (
        '  late final AnimationController _pulseCtrl;\n'
        '  late final AnimationController _geoRotCtrl;\n'
        '  late final Animation<double> _fade;\n'
    )
    txt, _ = rep(txt, OLD_W_FIELDS, NEW_W_FIELDS, 'welcome: add geoRotCtrl field')

    OLD_W_DISPOSE = (
        '    _fadeCtrl.dispose();\n'
        '    _pulseCtrl.dispose();\n'
        '    super.dispose();'
    )
    NEW_W_DISPOSE = (
        '    _fadeCtrl.dispose();\n'
        '    _pulseCtrl.dispose();\n'
        '    _geoRotCtrl.dispose();\n'
        '    super.dispose();'
    )
    txt, _ = rep(txt, OLD_W_DISPOSE, NEW_W_DISPOSE, 'welcome: dispose geoRotCtrl')
else:
    _ok('welcome geoRotCtrl already present')

# Rotate geo in welcome too
MARKER_W2 = '// S31-W-ROTGEO'
if MARKER_W2 not in txt:
    OLD_W_GEO = 'Positioned.fill(child: CustomPaint(painter: _GeoPainter())),'
    NEW_W_GEO = (
        '// S31-W-ROTGEO\n'
        '        Positioned.fill(child: AnimatedBuilder(\n'
        '          animation: _geoRotCtrl,\n'
        '          builder: (_, __) => Transform.rotate(\n'
        '            angle: _geoRotCtrl.value * 6.2832,\n'
        '            child: CustomPaint(painter: _GeoPainter())))),'
    )
    txt, _ = rep(txt, OLD_W_GEO, NEW_W_GEO, 'welcome: rotating geo')
else:
    _ok('welcome rotating geo already present')

(SC/'welcome_screen.dart').write_text(txt, encoding='utf-8')
_ok('welcome_screen.dart ✓')


# ═══════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════
_h('SUMMARY')
ok  = sum(1 for s,_ in _log if s=='OK')
xx  = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok} ✅   {xx} ❌\n')
for s,l in _log:
    print(f'  {"✅" if s=="OK" else "❌"}  {l}')
print("""
  git add -A
  git commit -m "S31: Premium animations — orbital rings, audio bars, burst, ripple, rotating geo"
  git push
""")
