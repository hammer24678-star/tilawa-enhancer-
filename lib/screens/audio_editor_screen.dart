// audio_editor_screen.dart — S152: Audio Editor
// EQ (5-band) · Echo · Reverb · Revert — matches app UI theme

import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

// ── Theme constants (mirrored from home_screen) ──────────────────────────────
const _bgMain    = Color(0xFF070F0B);
const _bgSurface = Color(0xFF0C1E28);
const _bgCard    = Color(0xFF0F2420);
const _gold      = Color(0xFFD4AF37);
const _goldDim   = Color(0xFFA07820);
const _teal      = Color(0xFF1DB898);
const _tealDark  = Color(0xFF0A4A3A);
const _textA     = Color(0xFFC9D1D9);
const _textB     = Color(0xFF8AACBA);
const _textDim   = Color(0xFF484F58);
const _border    = Color(0xFF21262D);

// ── Default preset values ────────────────────────────────────────────────────
const _eqBands = ['60Hz', '250Hz', '1kHz', '4kHz', '16kHz'];
const List<double> _eqDefault   = [0, 0, 0, 0, 0];   // dB  range ±12
const double _echoDelayDef      = 0.0;  // 0–1000 ms
const double _echoFeedbackDef   = 0.0;  // 0–90 %
const double _echoWetDef        = 0.0;  // 0–100 %
const double _reverbSizeDef     = 0.0;  // 0–100 %
const double _reverbWetDef      = 0.0;  // 0–100 %

class AudioEditorScreen extends StatefulWidget {
  const AudioEditorScreen({super.key});

  @override
  State<AudioEditorScreen> createState() => _AudioEditorScreenState();
}

class _AudioEditorScreenState extends State<AudioEditorScreen>
    with TickerProviderStateMixin {

  // EQ
  final List<double> _eq = List.from(_eqDefault);

  // Echo
  double _echoDelay    = _echoDelayDef;
  double _echoFeedback = _echoFeedbackDef;
  double _echoWet      = _echoWetDef;

  // Reverb
  double _reverbSize   = _reverbSizeDef;
  double _reverbWet    = _reverbWetDef;

  // Section expand state
  bool _eqOpen     = true;
  bool _echoOpen   = true;
  bool _reverbOpen = true;

  late AnimationController _revertCtrl;
  late Animation<double>   _revertScale;

  bool get _isDirty =>
      _eq.any((v) => v != 0) ||
      _echoDelay != 0 || _echoFeedback != 0 || _echoWet != 0 ||
      _reverbSize != 0 || _reverbWet != 0;

  @override
  void initState() {
    super.initState();
    _revertCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 180));
    _revertScale = Tween(begin: 1.0, end: 0.88)
        .chain(CurveTween(curve: Curves.easeOut))
        .animate(_revertCtrl);
  }

  @override
  void dispose() { _revertCtrl.dispose(); super.dispose(); }

  void _revert() {
    HapticFeedback.mediumImpact();
    _revertCtrl.forward().then((_) => _revertCtrl.reverse());
    setState(() {
      for (int i = 0; i < _eq.length; i++) _eq[i] = 0;
      _echoDelay = _echoFeedback = _echoWet = 0;
      _reverbSize = _reverbWet = 0;
    });
  }

  void _applyChanges() {
    HapticFeedback.lightImpact();
    // TODO S152: pass values to engine or local DSP
    // Map: eq[0..4] in dB, echoDelay ms, echoFeedback %, echoWet %, reverbSize %, reverbWet %
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        backgroundColor: _bgCard,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: const BorderSide(color: _gold, width: 0.7)),
        content: const Text('تم تطبيق الإعدادات ✓',
            style: TextStyle(color: _gold, fontSize: 13)),
        duration: const Duration(seconds: 2),
      ),
    );
  }

  // ── Build ─────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    return Directionality(
      textDirection: TextDirection.rtl,
      child: Scaffold(
        backgroundColor: _bgMain,
        body: CustomScrollView(
          physics: const BouncingScrollPhysics(),
          slivers: [
            _buildAppBar(),
            SliverPadding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
              sliver: SliverList(delegate: SliverChildListDelegate([
                const SizedBox(height: 12),
                _buildEqCard(),
                const SizedBox(height: 12),
                _buildEchoCard(),
                const SizedBox(height: 12),
                _buildReverbCard(),
                const SizedBox(height: 24),
                _buildActionRow(),
                const SizedBox(height: 16),
              ])),
            ),
          ],
        ),
      ),
    );
  }

  // ── App bar ───────────────────────────────────────────────────────────────
  SliverAppBar _buildAppBar() => SliverAppBar(
    backgroundColor: _bgSurface,
    surfaceTintColor: Colors.transparent,
    elevation: 0,
    pinned: true,
    leading: IconButton(
      icon: const Icon(Icons.arrow_back_ios_new_rounded, color: _textB, size: 18),
      onPressed: () => Navigator.pop(context),
    ),
    title: const Text('محرر الصوت',
        style: TextStyle(
            color: _gold, fontSize: 17,
            fontWeight: FontWeight.w700, letterSpacing: 0.3)),
    centerTitle: true,
    bottom: PreferredSize(
      preferredSize: const Size.fromHeight(1),
      child: Container(height: 1,
          decoration: const BoxDecoration(
            gradient: LinearGradient(colors: [
              Colors.transparent, _gold, Colors.transparent])))),
  );

  // ── EQ Card ───────────────────────────────────────────────────────────────
  Widget _buildEqCard() => _Section(
    title: 'المعادِل الصوتي (EQ)',
    icon: Icons.equalizer_rounded,
    open: _eqOpen,
    onToggle: () => setState(() => _eqOpen = !_eqOpen),
    child: Column(children: [
      // Visual bar display
      _EqVisualizer(values: _eq),
      const SizedBox(height: 20),
      // 5-band sliders
      ...List.generate(_eqBands.length, (i) => _EqBandRow(
        label: _eqBands[i],
        value: _eq[i],
        onChanged: (v) => setState(() => _eq[i] = v),
      )),
    ]),
  );

  // ── Echo Card ─────────────────────────────────────────────────────────────
  Widget _buildEchoCard() => _Section(
    title: 'الصدى (Echo)',
    icon: Icons.surround_sound_rounded,
    open: _echoOpen,
    onToggle: () => setState(() => _echoOpen = !_echoOpen),
    child: Column(children: [
      _KnobRow(
        label: 'زمن التأخير',
        subLabel: '${_echoDelay.round()} ms',
        value: _echoDelay,
        min: 0, max: 1000,
        onChanged: (v) => setState(() => _echoDelay = v),
      ),
      _KnobRow(
        label: 'التغذية الراجعة',
        subLabel: '${_echoFeedback.round()}%',
        value: _echoFeedback,
        min: 0, max: 90,
        onChanged: (v) => setState(() => _echoFeedback = v),
      ),
      _KnobRow(
        label: 'مزج الصدى',
        subLabel: '${_echoWet.round()}%',
        value: _echoWet,
        min: 0, max: 100,
        onChanged: (v) => setState(() => _echoWet = v),
      ),
    ]),
  );

  // ── Reverb Card ───────────────────────────────────────────────────────────
  Widget _buildReverbCard() => _Section(
    title: 'الإرجاع (Reverb)',
    icon: Icons.spatial_audio_off_rounded,
    open: _reverbOpen,
    onToggle: () => setState(() => _reverbOpen = !_reverbOpen),
    child: Column(children: [
      _KnobRow(
        label: 'حجم الغرفة',
        subLabel: '${_reverbSize.round()}%',
        value: _reverbSize,
        min: 0, max: 100,
        onChanged: (v) => setState(() => _reverbSize = v),
      ),
      _KnobRow(
        label: 'مزج الإرجاع',
        subLabel: '${_reverbWet.round()}%',
        value: _reverbWet,
        min: 0, max: 100,
        onChanged: (v) => setState(() => _reverbWet = v),
      ),
    ]),
  );

  // ── Action row ────────────────────────────────────────────────────────────
  Widget _buildActionRow() => Row(children: [
    // Revert button
    ScaleTransition(
      scale: _revertScale,
      child: GestureDetector(
        onTap: _isDirty ? _revert : null,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          decoration: BoxDecoration(
            color: _isDirty ? _tealDark : _border.withValues(alpha: 0.4),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: _isDirty ? _teal.withValues(alpha: 0.5) : _border,
              width: 1)),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.restart_alt_rounded,
                color: _isDirty ? _teal : _textDim, size: 18),
            const SizedBox(width: 6),
            Text('استرداد',
                style: TextStyle(
                    color: _isDirty ? _teal : _textDim,
                    fontSize: 13, fontWeight: FontWeight.w600)),
          ]),
        ),
      ),
    ),
    const SizedBox(width: 12),
    // Apply button
    Expanded(
      child: GestureDetector(
        onTap: _isDirty ? _applyChanges : null,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: BoxDecoration(
            gradient: _isDirty
                ? const LinearGradient(
                    colors: [Color(0xFF8B6914), _gold],
                    begin: Alignment.centerRight,
                    end: Alignment.centerLeft)
                : null,
            color: _isDirty ? null : _border.withValues(alpha: 0.4),
            borderRadius: BorderRadius.circular(12),
            boxShadow: _isDirty ? [
              BoxShadow(color: _gold.withValues(alpha: 0.25),
                  blurRadius: 12, offset: const Offset(0, 4))
            ] : null),
          child: Center(
            child: Text('تطبيق التعديلات',
                style: TextStyle(
                    color: _isDirty ? const Color(0xFF0A0A00) : _textDim,
                    fontSize: 14, fontWeight: FontWeight.w800,
                    letterSpacing: 0.3)),
          ),
        ),
      ),
    ),
  ]);
}

// ═══════════════════════════════════════════════════════════════════════════
// SECTION CARD
// ═══════════════════════════════════════════════════════════════════════════
class _Section extends StatelessWidget {
  final String title;
  final IconData icon;
  final bool open;
  final VoidCallback onToggle;
  final Widget child;

  const _Section({
    required this.title, required this.icon,
    required this.open, required this.onToggle, required this.child,
  });

  @override
  Widget build(BuildContext context) => Container(
    decoration: BoxDecoration(
      color: _bgCard,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: _border)),
    child: Column(children: [
      // Header
      InkWell(
        onTap: onToggle,
        borderRadius: BorderRadius.circular(16),
        splashColor: _gold.withValues(alpha: 0.07),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
          child: Row(children: [
            Icon(icon, color: _gold, size: 18),
            const SizedBox(width: 10),
            Text(title,
                style: const TextStyle(
                    color: _gold, fontSize: 14,
                    fontWeight: FontWeight.w700, letterSpacing: 0.2)),
            const Spacer(),
            AnimatedRotation(
              turns: open ? 0.5 : 0,
              duration: const Duration(milliseconds: 200),
              child: const Icon(Icons.keyboard_arrow_down_rounded,
                  color: _textDim, size: 20)),
          ]),
        ),
      ),
      // Divider
      if (open) Container(height: 1,
          margin: const EdgeInsets.symmetric(horizontal: 16),
          color: _border),
      // Body
      AnimatedCrossFade(
        duration: const Duration(milliseconds: 220),
        crossFadeState: open
            ? CrossFadeState.showFirst
            : CrossFadeState.showSecond,
        firstChild: Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
          child: child),
        secondChild: const SizedBox(width: double.infinity),
      ),
    ]),
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// EQ VISUALIZER
// ═══════════════════════════════════════════════════════════════════════════
class _EqVisualizer extends StatelessWidget {
  final List<double> values; // -12 to +12 dB

  const _EqVisualizer({required this.values});

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 72,
    child: CustomPaint(painter: _EqPainter(values: values)),
  );
}

class _EqPainter extends CustomPainter {
  final List<double> values;
  const _EqPainter({required this.values});

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width;
    final h = size.height;
    final mid = h / 2;
    final step = w / (values.length + 1);

    // Zero line
    final zeroPaint = Paint()
      ..color = _border
      ..strokeWidth = 1;
    canvas.drawLine(Offset(0, mid), Offset(w, mid), zeroPaint);

    // Curve
    final path = Path();
    final pts = <Offset>[];
    for (int i = 0; i < values.length; i++) {
      final x = step * (i + 1);
      final y = mid - (values[i] / 12.0) * mid * 0.85;
      pts.add(Offset(x, y));
    }

    if (pts.isEmpty) return;
    path.moveTo(0, mid);
    path.lineTo(pts.first.dx, pts.first.dy);
    for (int i = 0; i < pts.length - 1; i++) {
      final cp1 = Offset((pts[i].dx + pts[i + 1].dx) / 2, pts[i].dy);
      final cp2 = Offset((pts[i].dx + pts[i + 1].dx) / 2, pts[i + 1].dy);
      path.cubicTo(cp1.dx, cp1.dy, cp2.dx, cp2.dy,
                   pts[i + 1].dx, pts[i + 1].dy);
    }
    path.lineTo(w, mid);

    // Fill
    final fillPath = Path.from(path)..close();
    canvas.drawPath(fillPath, Paint()
      ..shader = LinearGradient(
          begin: Alignment.topCenter, end: Alignment.bottomCenter,
          colors: [_gold.withOpacity(0.18), Colors.transparent])
          .createShader(Rect.fromLTWH(0, 0, w, h)));

    // Line
    canvas.drawPath(path, Paint()
      ..color = _gold
      ..strokeWidth = 2
      ..style = PaintingStyle.stroke
      ..strokeCap = StrokeCap.round);

    // Dots
    for (final pt in pts) {
      canvas.drawCircle(pt, 4, Paint()..color = _bgCard);
      canvas.drawCircle(pt, 4, Paint()
        ..color = _gold
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2);
    }
  }

  @override
  bool shouldRepaint(_EqPainter old) => old.values != values;
}

// ═══════════════════════════════════════════════════════════════════════════
// EQ BAND ROW
// ═══════════════════════════════════════════════════════════════════════════
class _EqBandRow extends StatelessWidget {
  final String label;
  final double value;   // -12 to +12
  final ValueChanged<double> onChanged;

  const _EqBandRow({
    required this.label, required this.value, required this.onChanged});

  @override
  Widget build(BuildContext context) {
    final dB = value.toStringAsFixed(1);
    final color = value > 0 ? _gold
                : value < 0 ? _teal
                : _textDim;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(children: [
        SizedBox(width: 44,
            child: Text(label,
                style: const TextStyle(color: _textB, fontSize: 11,
                    fontWeight: FontWeight.w500))),
        Expanded(
          child: SliderTheme(
            data: SliderThemeData(
              trackHeight: 3,
              thumbSize: WidgetStateProperty.all(const Size(14, 14)),  // S159
              thumbColor: color,
              activeTrackColor: color.withValues(alpha: 0.7),
              inactiveTrackColor: _border,
              overlayColor: color.withValues(alpha: 0.15),
              overlayShape: const RoundSliderOverlayShape(overlayRadius: 16),
            ),
            child: Slider(
              value: value, min: -12, max: 12,
              divisions: 24,
              onChanged: onChanged,
            ),
          ),
        ),
        SizedBox(width: 44,
            child: Text(
              value == 0 ? '0.0 dB' : '${value > 0 ? "+" : ""}$dB dB',
              textAlign: TextAlign.end,
              style: TextStyle(color: color, fontSize: 11,
                  fontWeight: FontWeight.w600),
            )),
      ]),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// KNOB ROW (echo / reverb)
// ═══════════════════════════════════════════════════════════════════════════
class _KnobRow extends StatelessWidget {
  final String label;
  final String subLabel;
  final double value;
  final double min, max;
  final ValueChanged<double> onChanged;

  const _KnobRow({
    required this.label, required this.subLabel,
    required this.value, required this.min, required this.max,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final pct = (value - min) / (max - min);
    final active = pct > 0;
    final color = active ? _teal : _textDim;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(label,
              style: const TextStyle(color: _textA, fontSize: 13,
                  fontWeight: FontWeight.w500)),
          const Spacer(),
          AnimatedDefaultTextStyle(
            duration: const Duration(milliseconds: 150),
            style: TextStyle(
                color: active ? _teal : _textDim,
                fontSize: 12, fontWeight: FontWeight.w700),
            child: Text(subLabel)),
        ]),
        const SizedBox(height: 6),
        SliderTheme(
          data: SliderThemeData(
            trackHeight: 4,
            thumbSize: WidgetStateProperty.all(const Size(16, 16)),  // S159
            thumbColor: active ? _teal : _textDim,
            activeTrackColor: _teal.withValues(alpha: 0.75),
            inactiveTrackColor: _border,
            overlayColor: _teal.withValues(alpha: 0.15),
            overlayShape: const RoundSliderOverlayShape(overlayRadius: 18),
          ),
          child: Slider(
            value: value, min: min, max: max,
            onChanged: onChanged,
          ),
        ),
        // Tick labels
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 2),
          child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(min == 0 ? '0' : min.round().toString(),
                    style: const TextStyle(color: _textDim, fontSize: 9)),
                Text(((min + max) / 2).round().toString(),
                    style: const TextStyle(color: _textDim, fontSize: 9)),
                Text(max.round().toString(),
                    style: const TextStyle(color: _textDim, fontSize: 9)),
              ]),
        ),
      ]),
    );
  }
}
