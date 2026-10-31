// nur_paint.dart — CustomPainters behind the Nur design system.
//
// Every painter here is looping-safe: all time terms use integer multiples of
// the 0..1 controller value, so an AnimationController that simply repeats
// never visibly "jumps" at the seam. None allocate per frame beyond a Paint.

import 'dart:math' as math;

import 'package:flutter/material.dart';

const double _tau = math.pi * 2;

class _Star {
  final double x, y, r, phase;
  final int speed;
  const _Star(this.x, this.y, this.r, this.phase, this.speed);
}

List<_Star> _makeStars() {
  final rng = math.Random(42);
  return List<_Star>.generate(
    46,
    (_) => _Star(
      rng.nextDouble(),
      rng.nextDouble(),
      0.5 + rng.nextDouble() * 1.2,
      rng.nextDouble(),
      1 + rng.nextInt(3),
    ),
  );
}

final List<_Star> _stars = _makeStars();

/// Slow aurora of three tinted light-orbs, a faint rotating eight-pointed star
/// (the Rub el Hizb motif) and — in dark mode — twinkling stars.
class AuroraPainter extends CustomPainter {
  final double t;
  final Color accent;
  final Color second;
  final bool dark;
  final double intensity;

  const AuroraPainter({
    required this.t,
    required this.accent,
    required this.second,
    required this.dark,
    required this.intensity,
  });

  void _orb(Canvas canvas, Offset c, double r, Color col, double alpha) {
    final rect = Rect.fromCircle(center: c, radius: r);
    final paint = Paint()
      ..shader = RadialGradient(
        colors: [col.withValues(alpha: alpha), col.withValues(alpha: 0)],
      ).createShader(rect);
    canvas.drawCircle(c, r, paint);
  }

  void _octagram(Canvas canvas, Offset c, double r, double rot, Paint paint) {
    for (var k = 0; k < 2; k++) {
      final path = Path();
      for (var i = 0; i < 4; i++) {
        final a = rot + k * (math.pi / 4) + i * (math.pi / 2);
        final pt = Offset(c.dx + r * math.cos(a), c.dy + r * math.sin(a));
        if (i == 0) {
          path.moveTo(pt.dx, pt.dy);
        } else {
          path.lineTo(pt.dx, pt.dy);
        }
      }
      path.close();
      canvas.drawPath(path, paint);
    }
  }

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final ang = t * _tau;
    final a = (dark ? 0.30 : 0.17) * intensity;

    _orb(
      canvas,
      Offset(w * (0.18 + 0.10 * math.sin(ang)), h * (0.10 + 0.05 * math.cos(ang))),
      w * 0.95,
      accent,
      a,
    );
    _orb(
      canvas,
      Offset(w * (0.92 + 0.07 * math.cos(ang)), h * (0.46 + 0.07 * math.sin(ang * 2))),
      w * 0.80,
      second,
      a * 0.75,
    );
    _orb(
      canvas,
      Offset(w * (0.25 + 0.12 * math.sin(ang * 3)), h * (0.92 + 0.04 * math.cos(ang))),
      w * 0.85,
      accent,
      a * 0.55,
    );

    // Geometric motif: nested eight-pointed stars, rotating a full octant per
    // loop (the figure repeats every 45°, so the loop is seamless).
    final line = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1
      ..color = accent.withValues(alpha: (dark ? 0.10 : 0.12) * intensity);
    final centre = Offset(w * 0.86, h * 0.13);
    final rot = t * (math.pi / 4);
    _octagram(canvas, centre, w * 0.46, rot, line);
    _octagram(canvas, centre, w * 0.33, -rot, line);
    _octagram(canvas, centre, w * 0.20, rot, line);

    if (dark) {
      final starPaint = Paint();
      final tint = Color.lerp(Colors.white, accent, 0.35)!;
      for (final s in _stars) {
        final tw = 0.5 + 0.5 * math.sin(ang * s.speed + s.phase * _tau);
        starPaint.color = tint.withValues(alpha: (0.10 + 0.50 * tw) * intensity);
        canvas.drawCircle(Offset(s.x * w, s.y * h), s.r, starPaint);
      }
    }
  }

  @override
  bool shouldRepaint(AuroraPainter old) =>
      old.t != t ||
      old.accent != accent ||
      old.second != second ||
      old.dark != dark ||
      old.intensity != intensity;
}

/// A ring of radial audio bars — the studio "orb". [progress] < 0 lights every
/// bar; otherwise only the bars up to that fraction are lit, which turns the
/// ring into a progress meter that still looks like sound.
class RadialWavePainter extends CustomPainter {
  final double t;
  final double energy;
  final double progress;
  final Color a;
  final Color b;
  final Color track;
  final int bars;

  const RadialWavePainter({
    required this.t,
    required this.energy,
    required this.progress,
    required this.a,
    required this.b,
    required this.track,
    this.bars = 72,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    final r = math.min(size.width, size.height) / 2;
    final inner = r * 0.70;
    final maxLen = r * 0.28;
    final paint = Paint()
      ..strokeCap = StrokeCap.round
      ..strokeWidth = math.max(2.0, r * 0.028);

    for (var i = 0; i < bars; i++) {
      final f = i / bars;
      final ang = f * _tau - math.pi / 2;
      final w1 = math.sin((t + f) * _tau * 3);
      final w2 = math.sin((t * 2 + f * 5) * _tau);
      final w3 = math.sin((f * 2 - t) * _tau);
      final amp = 0.5 + 0.5 * (w1 * 0.5 + w2 * 0.3 + w3 * 0.2);
      final len = maxLen * (0.16 + 0.84 * amp * energy);
      final lit = progress < 0 || f <= progress;
      final col = lit ? Color.lerp(a, b, f)! : track;
      paint.color = col.withValues(alpha: lit ? 0.95 : 0.30);
      final dx = math.cos(ang);
      final dy = math.sin(ang);
      canvas.drawLine(
        Offset(c.dx + dx * inner, c.dy + dy * inner),
        Offset(c.dx + dx * (inner + len), c.dy + dy * (inner + len)),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(RadialWavePainter old) =>
      old.t != t ||
      old.energy != energy ||
      old.progress != progress ||
      old.a != a ||
      old.b != b ||
      old.track != track ||
      old.bars != bars;
}

/// Horizontal, vertically-centred bars — a compact waveform.
class BarsPainter extends CustomPainter {
  final double t;
  final double energy;
  final double progress;
  final Color a;
  final Color b;
  final Color track;
  final int bars;

  const BarsPainter({
    required this.t,
    required this.energy,
    required this.progress,
    required this.a,
    required this.b,
    required this.track,
    required this.bars,
  });

  @override
  void paint(Canvas canvas, Size size) {
    if (bars <= 0 || size.width <= 0) return;
    const gap = 3.0;
    final bw = math.max(1.5, (size.width - gap * (bars - 1)) / bars);
    final mid = size.height / 2;
    final paint = Paint();
    for (var i = 0; i < bars; i++) {
      final f = i / bars;
      final w1 = math.sin((t + f) * _tau * 1.0 * 2);
      final w2 = math.sin((t * 2 + f * 3) * _tau);
      final w3 = math.sin((f * 5 - t) * _tau);
      final amp = 0.5 + 0.5 * (w1 * 0.5 + w2 * 0.3 + w3 * 0.2);
      final bh = size.height * (0.14 + 0.86 * amp * energy);
      final lit = progress < 0 || f <= progress;
      final col = lit ? Color.lerp(a, b, f)! : track;
      paint.color = col.withValues(alpha: lit ? 0.95 : 0.28);
      final x = i * (bw + gap);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x, mid - bh / 2, bw, bh),
          Radius.circular(bw / 2),
        ),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(BarsPainter old) =>
      old.t != t ||
      old.energy != energy ||
      old.progress != progress ||
      old.a != a ||
      old.b != b ||
      old.track != track ||
      old.bars != bars;
}

/// A gradient arc ring. [progress] null = indeterminate (a comet that orbits,
/// driven by [t]).
class ArcRingPainter extends CustomPainter {
  final double? progress;
  final double t;
  final Color a;
  final Color b;
  final Color track;
  final double stroke;

  const ArcRingPainter({
    required this.progress,
    required this.t,
    required this.a,
    required this.b,
    required this.track,
    this.stroke = 6,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    final r = math.min(size.width, size.height) / 2 - stroke;
    final rect = Rect.fromCircle(center: c, radius: r);

    canvas.drawCircle(
      c,
      r,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = stroke
        ..color = track,
    );

    final p = progress;
    final double start;
    final double sweep;
    if (p == null) {
      start = t * _tau - math.pi / 2;
      sweep = math.pi * 0.55;
    } else {
      start = -math.pi / 2;
      sweep = _tau * p.clamp(0.0, 1.0);
    }
    if (sweep <= 0.001) return;

    final paint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = stroke
      ..strokeCap = StrokeCap.round
      ..shader = SweepGradient(
        startAngle: 0,
        endAngle: _tau,
        transform: GradientRotation(start),
        colors: [a, b, a],
      ).createShader(rect);
    canvas.drawArc(rect, start, sweep, false, paint);
  }

  @override
  bool shouldRepaint(ArcRingPainter old) =>
      old.progress != progress ||
      old.t != t ||
      old.a != a ||
      old.b != b ||
      old.track != track ||
      old.stroke != stroke;
}

/// 270° gauge with tick marks, gradient fill and a glowing end-cap — the
/// result screen's score ring. [progress] is already scaled by the reveal
/// animation (0..1 of the full 270° sweep).
class ScoreRingPainter extends CustomPainter {
  final double progress;
  final Color a;
  final Color b;
  final Color track;
  final double glow;

  const ScoreRingPainter({
    required this.progress,
    required this.a,
    required this.b,
    required this.track,
    required this.glow,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    final r = size.width / 2 - 16;
    final rect = Rect.fromCircle(center: c, radius: r);
    const start = math.pi * 0.75;
    const sweepAll = math.pi * 1.5;

    // tick marks hugging the outside of the arc
    final tick = Paint()
      ..strokeWidth = 1.2
      ..strokeCap = StrokeCap.round;
    for (var i = 0; i <= 40; i++) {
      final f = i / 40;
      final ang = start + sweepAll * f;
      final major = i % 10 == 0;
      final r1 = r + 12;
      final r2 = r + (major ? 19 : 15);
      tick.color = (f <= progress ? a : track).withValues(
          alpha: major ? 0.85 : 0.40);
      canvas.drawLine(
        Offset(c.dx + math.cos(ang) * r1, c.dy + math.sin(ang) * r1),
        Offset(c.dx + math.cos(ang) * r2, c.dy + math.sin(ang) * r2),
        tick,
      );
    }

    canvas.drawArc(
      rect,
      start,
      sweepAll,
      false,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 11
        ..strokeCap = StrokeCap.round
        ..color = track.withValues(alpha: 0.55),
    );

    final sweep = sweepAll * progress.clamp(0.0, 1.0);
    if (sweep <= 0.002) return;

    // soft glow underneath
    canvas.drawArc(
      rect,
      start,
      sweep,
      false,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 16
        ..strokeCap = StrokeCap.round
        ..color = b.withValues(alpha: 0.18 + 0.20 * glow)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 9),
    );

    canvas.drawArc(
      rect,
      start,
      sweep,
      false,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 11
        ..strokeCap = StrokeCap.round
        ..shader = SweepGradient(
          startAngle: 0,
          endAngle: sweepAll,
          transform: const GradientRotation(start),
          colors: [a, b],
        ).createShader(rect),
    );

    // bright end-cap
    final endAng = start + sweep;
    final endPt = Offset(c.dx + math.cos(endAng) * r, c.dy + math.sin(endAng) * r);
    canvas.drawCircle(
      endPt,
      7 + 2 * glow,
      Paint()
        ..color = b.withValues(alpha: 0.55)
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 5),
    );
    canvas.drawCircle(endPt, 3.6, Paint()..color = Colors.white);
  }

  @override
  bool shouldRepaint(ScoreRingPainter old) =>
      old.progress != progress ||
      old.a != a ||
      old.b != b ||
      old.track != track ||
      old.glow != glow;
}

class _Spark {
  final double angle, speed, size;
  const _Spark(this.angle, this.speed, this.size);
}

List<_Spark> _makeSparks() {
  final rng = math.Random(7);
  return List<_Spark>.generate(
    30,
    (_) => _Spark(
      rng.nextDouble() * _tau,
      0.55 + rng.nextDouble() * 0.45,
      1.4 + rng.nextDouble() * 2.4,
    ),
  );
}

final List<_Spark> _sparks = _makeSparks();

/// One-shot celebratory burst of sparks. [progress] runs 0..1 once.
class BurstPainter extends CustomPainter {
  final double progress;
  final Color color;

  const BurstPainter({required this.progress, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    if (progress <= 0 || progress >= 1) return;
    final c = Offset(size.width / 2, size.height / 2);
    final maxR = math.min(size.width, size.height) / 2;
    final ease = Curves.easeOutCubic.transform(progress);
    final fade = (1 - progress).clamp(0.0, 1.0);
    final paint = Paint();
    for (final s in _sparks) {
      final d = maxR * 0.55 + maxR * 0.45 * s.speed * ease;
      paint.color = color.withValues(alpha: 0.85 * fade);
      canvas.drawCircle(
        Offset(c.dx + math.cos(s.angle) * d, c.dy + math.sin(s.angle) * d),
        s.size * (1 - 0.5 * progress),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(BurstPainter old) =>
      old.progress != progress || old.color != color;
}
