// nur_widgets.dart — reusable widgets of the Nur design system.
//
// One vocabulary for every screen: a living backdrop, glass-like cards, a
// shimmering primary button, a sliding segmented control, an animated switch,
// gradient text, the radial "studio orb" and a scaffold that ties them
// together (including right-to-left mirroring for Arabic).

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../state/lang_provider.dart';
import '../widgets/anim.dart';
import 'nur_paint.dart';
import 'nur_theme.dart';

// ─────────────────────────────────────────────────────────────────────────────
// Backdrop
// ─────────────────────────────────────────────────────────────────────────────

/// The living background: a vertical night gradient, a slow aurora tinted by
/// [accent] (cross-fades when the accent changes), a faint rotating eight-
/// pointed star and twinkling stars. Everything below is cheap and sits behind
/// a RepaintBoundary, so scrolling content never repaints it.
class NurBackdrop extends StatefulWidget {
  final Widget child;
  final Color? accent;
  final double intensity;

  const NurBackdrop({
    super.key,
    required this.child,
    this.accent,
    this.intensity = 1.0,
  });

  @override
  State<NurBackdrop> createState() => _NurBackdropState();
}

class _NurBackdropState extends State<NurBackdrop>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c =
      AnimationController(vsync: this, duration: const Duration(seconds: 48))
        ..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final accent = widget.accent ?? p.teal;
    final second = p.dark ? const Color(0xFF1C7F8A) : p.goldLight;
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [p.bg, p.bgDeep],
        ),
      ),
      child: Stack(
        children: [
          Positioned.fill(
            child: IgnorePointer(
              child: RepaintBoundary(
                child: TweenAnimationBuilder<Color?>(
                  tween: ColorTween(begin: accent, end: accent),
                  duration: const Duration(milliseconds: 800),
                  builder: (context, col, _) => TweenAnimationBuilder<double>(
                    tween: Tween<double>(
                        begin: widget.intensity, end: widget.intensity),
                    duration: const Duration(milliseconds: 600),
                    builder: (context, inten, __) => AnimatedBuilder(
                      animation: _c,
                      builder: (_, ___) => CustomPaint(
                        painter: AuroraPainter(
                          t: _c.value,
                          accent: col ?? accent,
                          second: second,
                          dark: p.dark,
                          intensity: inten,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
          widget.child,
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Text
// ─────────────────────────────────────────────────────────────────────────────

/// Text filled with a gradient.
class GradientText extends StatelessWidget {
  final String text;
  final TextStyle? style;
  final Gradient gradient;
  final TextAlign? textAlign;
  final int? maxLines;
  final TextOverflow? overflow;

  const GradientText(
    this.text, {
    super.key,
    required this.gradient,
    this.style,
    this.textAlign,
    this.maxLines,
    this.overflow,
  });

  @override
  Widget build(BuildContext context) => ShaderMask(
        blendMode: BlendMode.srcIn,
        shaderCallback: (bounds) => gradient.createShader(
            Rect.fromLTWH(0, 0, bounds.width, bounds.height)),
        child: Text(
          text,
          textAlign: textAlign,
          maxLines: maxLines,
          overflow: overflow,
          style: (style ?? const TextStyle()).copyWith(color: Colors.white),
        ),
      );
}

/// A number that counts up (or down) to [value] whenever it changes.
class AnimatedCount extends StatelessWidget {
  final double value;
  final int decimals;
  final TextStyle? style;
  final String suffix;
  final Duration duration;

  const AnimatedCount({
    super.key,
    required this.value,
    this.decimals = 0,
    this.style,
    this.suffix = '',
    this.duration = const Duration(milliseconds: 900),
  });

  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
        tween: Tween<double>(begin: 0, end: value),
        duration: duration,
        curve: Curves.easeOutCubic,
        builder: (_, v, __) =>
            Text('${v.toStringAsFixed(decimals)}$suffix', style: style),
      );
}

// ─────────────────────────────────────────────────────────────────────────────
// Surfaces
// ─────────────────────────────────────────────────────────────────────────────

/// The standard surface: soft gradient fill, hairline border, a coloured glow
/// when [selected] or [glow], and press feedback when [onTap] is given.
class NurCard extends StatelessWidget {
  final Widget child;
  final EdgeInsetsGeometry padding;
  final EdgeInsetsGeometry? margin;
  final double radius;
  final Color? accent;
  final VoidCallback? onTap;
  final bool glow;
  final bool selected;
  final Gradient? gradient;

  const NurCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(16),
    this.margin,
    this.radius = 22,
    this.accent,
    this.onTap,
    this.glow = false,
    this.selected = false,
    this.gradient,
  });

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final acc = accent ?? p.teal;
    final lit = glow || selected;
    Widget card = AnimatedContainer(
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
      padding: padding,
      decoration: BoxDecoration(
        gradient: gradient ??
            LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [p.surfaceHi, p.surface],
            ),
        borderRadius: BorderRadius.circular(radius),
        border: Border.all(
          color: selected ? acc.withValues(alpha: 0.80) : p.border,
          width: selected ? 1.5 : 1,
        ),
        boxShadow: [
          BoxShadow(
            color: lit
                ? acc.withValues(alpha: p.dark ? 0.24 : 0.18)
                : Colors.black.withValues(alpha: p.dark ? 0.30 : 0.06),
            blurRadius: lit ? 30 : 18,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: child,
    );
    if (onTap != null) {
      card = PressScale(scale: 0.975, onTap: onTap, child: card);
    }
    return margin == null ? card : Padding(padding: margin!, child: card);
  }
}

/// Small rounded label.
class NurChip extends StatelessWidget {
  final String label;
  final Color color;
  final IconData? icon;
  final bool filled;
  final double fontSize;

  const NurChip({
    super.key,
    required this.label,
    required this.color,
    this.icon,
    this.filled = false,
    this.fontSize = 11,
  });

  @override
  Widget build(BuildContext context) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
        decoration: BoxDecoration(
          color: color.withValues(alpha: filled ? 0.22 : 0.10),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: color.withValues(alpha: 0.42)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (icon != null) ...[
              Icon(icon, size: fontSize + 3, color: color),
              const SizedBox(width: 5),
            ],
            Flexible(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: color,
                  fontSize: fontSize,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ],
        ),
      );
}

/// Section title with an accent bar and a fading rule.
class NurSectionHeader extends StatelessWidget {
  final String title;
  final Widget? trailing;
  final Color? accent;
  final EdgeInsetsGeometry padding;

  const NurSectionHeader(
    this.title, {
    super.key,
    this.trailing,
    this.accent,
    this.padding = const EdgeInsets.fromLTRB(20, 22, 20, 12),
  });

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final acc = accent ?? p.gold;
    return Padding(
      padding: padding,
      child: Row(
        children: [
          Container(
            width: 4,
            height: 18,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(2),
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [acc, acc.withValues(alpha: 0.35)],
              ),
            ),
          ),
          const SizedBox(width: 10),
          Text(
            title,
            style: TextStyle(
              color: p.text,
              fontSize: 15,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.2,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Container(
              height: 1,
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  begin: AlignmentDirectional.centerStart,
                  end: AlignmentDirectional.centerEnd,
                  colors: [
                    acc.withValues(alpha: 0.45),
                    acc.withValues(alpha: 0),
                  ],
                ),
              ),
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: 10),
            trailing!,
          ],
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Controls
// ─────────────────────────────────────────────────────────────────────────────

/// Primary / secondary action button. The filled variant carries a slow gold
/// shimmer sweep while it is tappable; both give springy press feedback.
class NurButton extends StatefulWidget {
  final String label;
  final IconData? icon;
  final VoidCallback? onTap;
  final bool loading;
  final bool filled;
  final Color? accent;
  final bool expand;
  final double height;

  const NurButton({
    super.key,
    required this.label,
    this.icon,
    this.onTap,
    this.loading = false,
    this.filled = true,
    this.accent,
    this.expand = true,
    this.height = 54,
  });

  @override
  State<NurButton> createState() => _NurButtonState();
}

class _NurButtonState extends State<NurButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 3200));

  bool get _shimmer =>
      widget.filled && widget.onTap != null && !widget.loading;

  @override
  void initState() {
    super.initState();
    _sync();
  }

  @override
  void didUpdateWidget(covariant NurButton oldWidget) {
    super.didUpdateWidget(oldWidget);
    _sync();
  }

  void _sync() {
    if (_shimmer) {
      if (!_c.isAnimating) _c.repeat();
    } else {
      if (_c.isAnimating) _c.stop();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final acc = widget.accent ?? p.gold;
    final active = widget.onTap != null || widget.loading;
    final tappable = widget.onTap != null && !widget.loading;
    final radius = BorderRadius.circular(widget.height / 2.6);
    final Color fg = !active
        ? p.textDim
        : (widget.filled ? p.onGold : acc);

    final content = Row(
      mainAxisSize: MainAxisSize.min,
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        if (widget.loading)
          SizedBox(
            width: 18,
            height: 18,
            child: CircularProgressIndicator(strokeWidth: 2.2, color: fg),
          )
        else if (widget.icon != null)
          Icon(widget.icon, size: 20, color: fg),
        if (widget.loading || widget.icon != null) const SizedBox(width: 10),
        Flexible(
          child: Text(
            widget.label,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(
              color: fg,
              fontSize: 15,
              fontWeight: FontWeight.w800,
              letterSpacing: 0.3,
            ),
          ),
        ),
      ],
    );

    final Gradient? fill = widget.filled
        ? (active
            ? LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color.lerp(acc, Colors.white, 0.28)!, acc],
              )
            : LinearGradient(colors: [p.border, p.border]))
        : null;

    final btn = Container(
      height: widget.height,
      width: widget.expand ? double.infinity : null,
      decoration: BoxDecoration(
        borderRadius: radius,
        gradient: fill,
        color: widget.filled ? null : acc.withValues(alpha: active ? 0.08 : 0.03),
        border: widget.filled
            ? null
            : Border.all(
                color: acc.withValues(alpha: active ? 0.55 : 0.22),
                width: 1.2,
              ),
        boxShadow: widget.filled && active
            ? [
                BoxShadow(
                  color: acc.withValues(alpha: 0.38),
                  blurRadius: 26,
                  offset: const Offset(0, 8),
                ),
              ]
            : null,
      ),
      child: ClipRRect(
        borderRadius: radius,
        child: Stack(
          children: [
            if (_shimmer)
              Positioned.fill(
                child: IgnorePointer(
                  child: AnimatedBuilder(
                    animation: _c,
                    builder: (_, __) {
                      final tt = (_c.value / 0.45).clamp(0.0, 1.0);
                      final t = Curves.easeInOutSine.transform(tt);
                      return FractionallySizedBox(
                        alignment: Alignment(-1.8 + 3.6 * t, 0),
                        widthFactor: 0.32,
                        child: Transform(
                          transform: Matrix4.skewX(-0.35),
                          child: DecoratedBox(
                            decoration: BoxDecoration(
                              gradient: LinearGradient(
                                colors: [
                                  Colors.white.withValues(alpha: 0),
                                  Colors.white.withValues(alpha: 0.34),
                                  Colors.white.withValues(alpha: 0),
                                ],
                              ),
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 22),
              child: Center(child: content),
            ),
          ],
        ),
      ),
    );

    return PressScale(
      scale: 0.97,
      onTap: tappable
          ? () {
              HapticFeedback.lightImpact();
              widget.onTap!();
            }
          : null,
      child: btn,
    );
  }
}

/// Round glass icon button.
class NurIconButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback? onTap;
  final Color? color;
  final double size;
  final String? tooltip;

  const NurIconButton({
    super.key,
    required this.icon,
    this.onTap,
    this.color,
    this.size = 42,
    this.tooltip,
  });

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    Widget b = PressScale(
      scale: 0.86,
      onTap: onTap == null
          ? null
          : () {
              HapticFeedback.selectionClick();
              onTap!();
            },
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          gradient: LinearGradient(
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
            colors: [p.surfaceHi, p.surface],
          ),
          border: Border.all(color: p.border),
        ),
        child: Icon(icon, size: size * 0.48, color: color ?? p.textSub),
      ),
    );
    if (tooltip != null) b = Tooltip(message: tooltip!, child: b);
    return b;
  }
}

/// One option of a [NurSegmented].
class NurSegment {
  final String label;
  final IconData icon;
  const NurSegment(this.label, this.icon);
}

/// A segmented control whose highlight glides between options.
class NurSegmented extends StatelessWidget {
  final List<NurSegment> items;
  final int index;
  final ValueChanged<int> onChanged;
  final Color? accent;
  final bool enabled;

  const NurSegmented({
    super.key,
    required this.items,
    required this.index,
    required this.onChanged,
    this.accent,
    this.enabled = true,
  });

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final acc = accent ?? p.gold;
    final n = items.length;
    final x = n <= 1 ? 0.0 : -1.0 + 2.0 * index / (n - 1);
    return Opacity(
      opacity: enabled ? 1 : 0.5,
      child: Container(
        height: 48,
        padding: const EdgeInsets.all(4),
        decoration: BoxDecoration(
          color: p.dark ? Colors.black.withValues(alpha: 0.28) : p.bgDeep,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: p.border),
        ),
        child: Stack(
          children: [
            AnimatedAlign(
              duration: const Duration(milliseconds: 380),
              curve: Curves.easeOutBack,
              alignment: AlignmentDirectional(x, 0),
              child: FractionallySizedBox(
                widthFactor: 1 / n,
                heightFactor: 1,
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(12),
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: [acc.withValues(alpha: 0.34), acc.withValues(alpha: 0.16)],
                    ),
                    border: Border.all(color: acc.withValues(alpha: 0.65)),
                    boxShadow: [
                      BoxShadow(
                        color: acc.withValues(alpha: 0.22),
                        blurRadius: 14,
                      ),
                    ],
                  ),
                ),
              ),
            ),
            Row(
              children: [
                for (var i = 0; i < n; i++)
                  Expanded(
                    child: GestureDetector(
                      behavior: HitTestBehavior.opaque,
                      onTap: !enabled || i == index
                          ? null
                          : () {
                              HapticFeedback.selectionClick();
                              onChanged(i);
                            },
                      child: Center(
                        child: AnimatedDefaultTextStyle(
                          duration: const Duration(milliseconds: 250),
                          style: TextStyle(
                            color: i == index ? p.text : p.textDim,
                            fontSize: 13,
                            fontWeight:
                                i == index ? FontWeight.w800 : FontWeight.w600,
                            fontFamily: 'Tajawal',
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                items[i].icon,
                                size: 17,
                                color: i == index ? acc : p.textDim,
                              ),
                              const SizedBox(width: 7),
                              Flexible(
                                child: Text(
                                  items[i].label,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Animated switch (springy knob, glowing track).
class NurSwitch extends StatelessWidget {
  final bool value;
  final ValueChanged<bool>? onChanged;
  final Color? accent;

  const NurSwitch({
    super.key,
    required this.value,
    required this.onChanged,
    this.accent,
  });

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final acc = accent ?? p.gold;
    return Opacity(
      opacity: onChanged == null ? 0.45 : 1,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: onChanged == null
            ? null
            : () {
                HapticFeedback.selectionClick();
                onChanged!(!value);
              },
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 260),
          curve: Curves.easeOutCubic,
          width: 48,
          height: 28,
          padding: const EdgeInsets.all(3),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            color: value ? acc.withValues(alpha: 0.85) : p.border,
            boxShadow: value
                ? [BoxShadow(color: acc.withValues(alpha: 0.35), blurRadius: 12)]
                : null,
          ),
          child: AnimatedAlign(
            duration: const Duration(milliseconds: 260),
            curve: Curves.easeOutBack,
            alignment: value
                ? AlignmentDirectional.centerEnd
                : AlignmentDirectional.centerStart,
            child: Container(
              width: 22,
              height: 22,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: value ? Colors.white : p.textDim,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// A settings-style row: icon, title, optional subtitle and a trailing widget.
class NurOptionRow extends StatelessWidget {
  final IconData icon;
  final String title;
  final String? subtitle;
  final Widget trailing;
  final Color? accent;
  final bool active;

  const NurOptionRow({
    super.key,
    required this.icon,
    required this.title,
    required this.trailing,
    this.subtitle,
    this.accent,
    this.active = false,
  });

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final acc = accent ?? p.gold;
    return Row(
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 260),
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            color: acc.withValues(alpha: active ? 0.18 : 0.08),
            border: Border.all(color: acc.withValues(alpha: active ? 0.55 : 0.22)),
          ),
          child: Icon(icon, size: 19, color: active ? acc : p.textSub),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                title,
                style: TextStyle(
                  color: active ? p.text : p.textSub,
                  fontSize: 13.5,
                  fontWeight: FontWeight.w700,
                ),
              ),
              if (subtitle != null)
                Padding(
                  padding: const EdgeInsets.only(top: 2),
                  child: Text(
                    subtitle!,
                    style: TextStyle(color: p.textDim, fontSize: 11, height: 1.3),
                  ),
                ),
            ],
          ),
        ),
        const SizedBox(width: 10),
        trailing,
      ],
    );
  }
}

/// A status dot with an expanding ring while [active].
class PulseDot extends StatefulWidget {
  final Color color;
  final double size;
  final bool active;

  const PulseDot({
    super.key,
    required this.color,
    this.size = 10,
    this.active = true,
  });

  @override
  State<PulseDot> createState() => _PulseDotState();
}

class _PulseDotState extends State<PulseDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
      vsync: this, duration: const Duration(milliseconds: 1800));

  @override
  void initState() {
    super.initState();
    if (widget.active) _c.repeat();
  }

  @override
  void didUpdateWidget(covariant PulseDot old) {
    super.didUpdateWidget(old);
    if (widget.active && !_c.isAnimating) _c.repeat();
    if (!widget.active && _c.isAnimating) _c.stop();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final s = widget.size;
    return SizedBox(
      width: s * 2.4,
      height: s * 2.4,
      child: AnimatedBuilder(
        animation: _c,
        builder: (_, __) {
          final t = widget.active ? _c.value : 0.0;
          return Stack(
            alignment: Alignment.center,
            children: [
              if (widget.active)
                Container(
                  width: s + s * 1.4 * t,
                  height: s + s * 1.4 * t,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    border: Border.all(
                      color: widget.color.withValues(alpha: 0.65 * (1 - t)),
                      width: 1.5,
                    ),
                  ),
                ),
              Container(
                width: s,
                height: s,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: widget.color,
                  boxShadow: [
                    BoxShadow(
                      color: widget.color.withValues(alpha: 0.55),
                      blurRadius: 8,
                    ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Audio-flavoured visuals
// ─────────────────────────────────────────────────────────────────────────────

/// Compact horizontal waveform. Drive it with a repeating controller
/// ([animation]); [progress] < 0 lights every bar.
class NurWaveform extends StatelessWidget {
  final Animation<double> animation;
  final int bars;
  final double height;
  final double progress;
  final double energy;
  final Color? a;
  final Color? b;

  const NurWaveform({
    super.key,
    required this.animation,
    this.bars = 30,
    this.height = 44,
    this.progress = -1,
    this.energy = 1,
    this.a,
    this.b,
  });

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    return SizedBox(
      height: height,
      width: double.infinity,
      child: RepaintBoundary(
        child: AnimatedBuilder(
          animation: animation,
          builder: (_, __) => CustomPaint(
            painter: BarsPainter(
              t: animation.value,
              energy: energy,
              progress: progress,
              a: a ?? p.teal,
              b: b ?? p.goldLight,
              track: p.textDim,
              bars: bars,
            ),
          ),
        ),
      ),
    );
  }
}

/// The studio orb: a ring of radial audio bars around a glowing disc that
/// hosts [child]. Idle it breathes; with [energy] raised it dances; with
/// [progress] it doubles as a progress meter.
class NurOrb extends StatelessWidget {
  final Animation<double> animation;
  final double size;
  final double energy;
  final double progress;
  final Color? a;
  final Color? b;
  final Widget child;

  const NurOrb({
    super.key,
    required this.animation,
    required this.child,
    this.size = 260,
    this.energy = 0.55,
    this.progress = -1,
    this.a,
    this.b,
  });

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final ca = a ?? p.teal;
    final cb = b ?? p.goldLight;
    return SizedBox(
      width: size,
      height: size,
      child: Stack(
        alignment: Alignment.center,
        children: [
          Positioned.fill(
            child: DecoratedBox(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: RadialGradient(
                  colors: [
                    cb.withValues(alpha: p.dark ? 0.20 : 0.16),
                    cb.withValues(alpha: 0),
                  ],
                ),
              ),
            ),
          ),
          RepaintBoundary(
            child: AnimatedBuilder(
              animation: animation,
              builder: (_, __) => CustomPaint(
                size: Size.square(size),
                painter: RadialWavePainter(
                  t: animation.value,
                  energy: energy,
                  progress: progress,
                  a: ca,
                  b: cb,
                  track: p.textDim,
                ),
              ),
            ),
          ),
          Container(
            width: size * 0.62,
            height: size * 0.62,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: RadialGradient(
                colors: [p.surfaceHi, p.surface],
              ),
              border: Border.all(color: cb.withValues(alpha: 0.38)),
              boxShadow: [
                BoxShadow(
                  color: cb.withValues(alpha: p.dark ? 0.22 : 0.18),
                  blurRadius: 34,
                ),
              ],
            ),
          ),
          SizedBox(
            width: size * 0.54,
            height: size * 0.54,
            child: Center(child: child),
          ),
        ],
      ),
    );
  }
}

/// Rounded linear progress with a gradient fill that eases to each new value.
class NurProgressBar extends StatelessWidget {
  final double? value;
  final double height;
  final Color? a;
  final Color? b;

  const NurProgressBar({
    super.key,
    required this.value,
    this.height = 8,
    this.a,
    this.b,
  });

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final ca = a ?? p.teal;
    final cb = b ?? p.goldLight;
    final v = value;
    if (v == null) {
      return ClipRRect(
        borderRadius: BorderRadius.circular(height),
        child: SizedBox(
          height: height,
          child: LinearProgressIndicator(
            minHeight: height,
            backgroundColor: p.border,
            valueColor: AlwaysStoppedAnimation<Color>(cb),
          ),
        ),
      );
    }
    return Container(
      height: height,
      decoration: BoxDecoration(
        color: p.border.withValues(alpha: 0.7),
        borderRadius: BorderRadius.circular(height),
      ),
      child: TweenAnimationBuilder<double>(
        tween: Tween<double>(begin: v, end: v),
        duration: const Duration(milliseconds: 450),
        curve: Curves.easeOutCubic,
        builder: (_, val, __) => Align(
          alignment: AlignmentDirectional.centerStart,
          child: FractionallySizedBox(
            widthFactor: val.clamp(0.0, 1.0),
            child: DecoratedBox(
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(height),
                gradient: LinearGradient(
                  begin: AlignmentDirectional.centerStart,
                  end: AlignmentDirectional.centerEnd,
                  colors: [ca, cb],
                ),
                boxShadow: [
                  BoxShadow(color: cb.withValues(alpha: 0.45), blurRadius: 10),
                ],
              ),
              child: SizedBox(height: height),
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Structure
// ─────────────────────────────────────────────────────────────────────────────

/// Standard secondary-screen frame: backdrop, a glassy header (back button,
/// icon, gradient title, actions) and a body. Mirrors itself for Arabic, so
/// screens that adopt it must NOT also flip their own rows and alignments.
class NurScaffold extends StatelessWidget {
  final String title;
  final IconData? icon;
  final Widget body;
  final List<Widget> actions;
  final Color? accent;
  final bool showBack;
  final Widget? floatingActionButton;
  final double intensity;

  const NurScaffold({
    super.key,
    required this.title,
    required this.body,
    this.icon,
    this.actions = const [],
    this.accent,
    this.showBack = true,
    this.floatingActionButton,
    this.intensity = 0.85,
  });

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final ar = LangProvider.of(context).value;
    final acc = accent ?? p.gold;
    return Directionality(
      textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
      child: Scaffold(
        backgroundColor: p.bg,
        floatingActionButton: floatingActionButton,
        body: NurBackdrop(
          accent: acc,
          intensity: intensity,
          child: SafeArea(
            bottom: false,
            child: Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 8, 16, 6),
                  child: Row(
                    children: [
                      if (showBack) ...[
                        NurIconButton(
                          icon: Icons.arrow_back_ios_new_rounded,
                          onTap: () => Navigator.maybePop(context),
                        ),
                        const SizedBox(width: 12),
                      ],
                      if (icon != null) ...[
                        Container(
                          width: 38,
                          height: 38,
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(12),
                            gradient: LinearGradient(
                              begin: Alignment.topLeft,
                              end: Alignment.bottomRight,
                              colors: [
                                acc.withValues(alpha: 0.30),
                                acc.withValues(alpha: 0.10),
                              ],
                            ),
                            border: Border.all(color: acc.withValues(alpha: 0.5)),
                          ),
                          child: Icon(icon, size: 20, color: acc),
                        ),
                        const SizedBox(width: 12),
                      ],
                      Expanded(
                        child: GradientText(
                          title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          gradient: p.goldGradient,
                          style: const TextStyle(
                            fontSize: 21,
                            fontWeight: FontWeight.w800,
                            letterSpacing: 0.2,
                          ),
                        ),
                      ),
                      ...actions,
                    ],
                  ),
                ),
                Expanded(child: body),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Rounded draggable bottom sheet with a grab handle.
Future<T?> showNurSheet<T>(
  BuildContext context, {
  required Widget Function(BuildContext context, ScrollController controller)
      builder,
  double initialSize = 0.78,
  double minSize = 0.4,
  double maxSize = 0.95,
}) {
  return showModalBottomSheet<T>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    barrierColor: Colors.black.withValues(alpha: 0.55),
    builder: (ctx) {
      final p = NurPalette.of(ctx);
      return DraggableScrollableSheet(
        initialChildSize: initialSize,
        minChildSize: minSize,
        maxChildSize: maxSize,
        expand: false,
        builder: (c, ctrl) => DecoratedBox(
          decoration: BoxDecoration(
            color: p.surface,
            borderRadius: const BorderRadius.vertical(top: Radius.circular(30)),
            border: Border(top: BorderSide(color: p.border)),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.4),
                blurRadius: 30,
              ),
            ],
          ),
          child: Column(
            children: [
              Container(
                margin: const EdgeInsets.only(top: 12, bottom: 6),
                width: 44,
                height: 5,
                decoration: BoxDecoration(
                  color: p.border,
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
              Expanded(child: builder(c, ctrl)),
            ],
          ),
        ),
      );
    },
  );
}
