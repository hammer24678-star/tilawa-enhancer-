// anim.dart — S250g: small reusable animation primitives.
//
// These started life private to audio_editor_screen.dart. The home screen has
// the same needs — its engine cards and its primary "process" button are plain
// GestureDetectors with no press feedback at all — so they live here now
// rather than being copy-pasted, which is how the two engine-script tables in
// LocalEngineRunner.kt drifted apart in the first place.
//
// Everything here is deliberately cheap: no controllers left running when
// nothing is happening, and no per-frame allocation.

import 'dart:async';

import 'package:flutter/material.dart';

/// Scales its child down while held and springs it back on release.
///
/// Stateful on purpose: screens in this app rebuild on every animation tick
/// (glow/wave controllers), so a pressed-flag held by the parent would be
/// reset constantly and the feedback would never be seen.
class PressScale extends StatefulWidget {
  final Widget child;
  final VoidCallback? onTap;
  final double scale;
  final HitTestBehavior behavior;

  const PressScale({
    super.key,
    required this.child,
    this.onTap,
    this.scale = 0.93,
    this.behavior = HitTestBehavior.opaque,
  });

  @override
  State<PressScale> createState() => _PressScaleState();
}

class _PressScaleState extends State<PressScale> {
  bool _down = false;

  void _set(bool v) {
    if (mounted && _down != v) setState(() => _down = v);
  }

  @override
  Widget build(BuildContext context) => GestureDetector(
        behavior: widget.behavior,
        onTap: widget.onTap,
        onTapDown: widget.onTap == null ? null : (_) => _set(true),
        onTapUp: (_) => _set(false),
        onTapCancel: () => _set(false),
        child: AnimatedScale(
          scale: _down ? widget.scale : 1.0,
          duration: Duration(milliseconds: _down ? 90 : 220),
          curve: _down ? Curves.easeOut : Curves.elasticOut,
          child: widget.child,
        ),
      );
}

/// Fades and lifts its child in once, on first build.
///
/// [index] staggers a list: each successive item starts slightly later, so a
/// tab's cards cascade instead of appearing as one solid block. Runs exactly
/// once per widget identity — give it a ValueKey tied to the content if you
/// want it to replay.
class EntranceFade extends StatefulWidget {
  final Widget child;
  final int index;
  final double offsetY;
  final Duration duration;

  const EntranceFade({
    super.key,
    required this.child,
    this.index = 0,
    this.offsetY = 14,
    this.duration = const Duration(milliseconds: 320),
  });

  @override
  State<EntranceFade> createState() => _EntranceFadeState();
}

class _EntranceFadeState extends State<EntranceFade>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: widget.duration);
  late final Animation<double> _a =
      CurvedAnimation(parent: _c, curve: Curves.easeOutCubic);

  Timer? _delay;

  @override
  void initState() {
    super.initState();
    // cap the stagger so a long list's last card is not left waiting
    final delay = Duration(milliseconds: (widget.index.clamp(0, 8)) * 45);
    if (delay == Duration.zero) {
      _c.forward();
    } else {
      // A real Timer, not Future.delayed: the stagger fires after the widget
      // may already be gone (switch tabs quickly and every pending card is
      // disposed mid-delay). Future.delayed cannot be cancelled, so it stayed
      // pending past dispose — caught by the widget test's pending-timer
      // invariant, and a genuine if small leak on device.
      _delay = Timer(delay, () { if (mounted) _c.forward(); });
    }
  }

  @override
  void dispose() {
    _delay?.cancel();
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _a,
        builder: (_, child) => Opacity(
          opacity: _a.value,
          child: Transform.translate(
            offset: Offset(0, widget.offsetY * (1 - _a.value)),
            child: child,
          ),
        ),
        child: widget.child,
      );
}

/// Briefly highlights its child whenever [value] changes — used on the readout
/// chips beside sliders, so the number you are dragging visibly reacts instead
/// of silently updating.
class ChangePulse extends StatefulWidget {
  final Object? value;
  final Widget child;
  final Color color;

  const ChangePulse({
    super.key,
    required this.value,
    required this.child,
    required this.color,
  });

  @override
  State<ChangePulse> createState() => _ChangePulseState();
}

class _ChangePulseState extends State<ChangePulse>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 260));

  @override
  void didUpdateWidget(covariant ChangePulse old) {
    super.didUpdateWidget(old);
    if (old.value != widget.value) _c.forward(from: 0);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _c,
        builder: (_, child) {
          // one quick up-down, so it reads as a tick rather than a throb
          final t = _c.value == 0 ? 0.0 : (1 - (_c.value * 2 - 1).abs());
          return DecoratedBox(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(8),
              boxShadow: t <= 0
                  ? null
                  : [BoxShadow(
                      color: widget.color.withValues(alpha: 0.45 * t),
                      blurRadius: 10 * t,
                      spreadRadius: 1.5 * t)],
            ),
            child: child,
          );
        },
        child: widget.child,
      );
}
