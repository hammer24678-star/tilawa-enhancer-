import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../design/nur.dart';
import '../services/local_engine_service.dart';
import '../state/lang_provider.dart';

/// S65 — First-run screen: downloads Alpine + Python + ffmpeg + DeepFilter.
/// ~200MB one-time download. Shows progress with retry and skip-to-server.
class SetupScreen extends StatefulWidget {
  final VoidCallback onDone;
  final VoidCallback onSkip;
  const SetupScreen({super.key, required this.onDone, required this.onSkip});

  @override
  State<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends State<SetupScreen>
    with TickerProviderStateMixin {

  int    _pct     = 0;
  String _phase   = 'Preparing…';
  bool   _error   = false;
  String _errMsg  = '';
  bool   _running = false;
  StreamSubscription<Map<String, dynamic>>? _sub;

  late final AnimationController _waveCtrl;

  @override
  void initState() {
    super.initState();
    _waveCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 6))
      ..repeat();
    _startSetup();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _waveCtrl.dispose();
    super.dispose();
  }

  Future<void> _startSetup() async {
    if (_running) return;
    setState(() { _running = true; _error = false; _pct = 0; _phase = 'Starting…'; });
    _sub?.cancel();
    _sub = LocalEngineService.runSetup().listen(
      (ev) {
        if (!mounted) return;
        setState(() {
          _pct   = (ev['pct'] as int? ?? _pct).clamp(0, 100);
          _phase = (ev['phase'] as String?) ?? _phase;
        });
        if (_pct >= 100) {
          Future.delayed(const Duration(milliseconds: 600), () {
            if (mounted) widget.onDone();
          });
        }
      },
      onError: (e) {
        if (!mounted) return;
        setState(() {
          _error   = true;
          _errMsg  = e.toString().replaceFirst('Exception: ', '');
          _running = false;
        });
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    final ar = LangProvider.of(context).value;
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: p.dark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark,
      child: Directionality(
        textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
        child: Scaffold(
          backgroundColor: p.bg,
          body: NurBackdrop(
            accent: _error ? p.err : p.teal,
            child: SafeArea(
              child: Center(
                child: SingleChildScrollView(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 480),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        EntranceFade(child: _orb(p)),
                        const SizedBox(height: 20),
                        EntranceFade(index: 1, child: _title(p)),
                        const SizedBox(height: 28),
                        EntranceFade(
                          index: 2,
                          child: AnimatedSwitcher(
                            duration: const Duration(milliseconds: 350),
                            switchInCurve: Curves.easeOutCubic,
                            transitionBuilder: (c, a) => FadeTransition(
                              opacity: a,
                              child: ScaleTransition(
                                scale: Tween<double>(begin: 0.96, end: 1.0)
                                    .animate(a),
                                child: c)),
                            child: _error
                                ? KeyedSubtree(
                                    key: const ValueKey('err'),
                                    child: _errorCard(p, ar))
                                : KeyedSubtree(
                                    key: const ValueKey('prog'),
                                    child: _progressCard(p)),
                          ),
                        ),
                        const SizedBox(height: 24),
                        EntranceFade(index: 3, child: _infoCard(p, ar)),
                        const SizedBox(height: 12),
                        EntranceFade(
                          index: 4,
                          child: NurButton(
                            label: ar
                                ? 'استخدم وضع الخادم بدلاً من ذلك'
                                : 'Use server mode instead',
                            icon: Icons.cloud_outlined,
                            filled: false,
                            accent: p.textSub,
                            onTap: widget.onSkip,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _orb(NurPalette p) {
    final w = MediaQuery.of(context).size.width;
    final size = (w * 0.58).clamp(150.0, 230.0).toDouble();
    final logo = size * 0.4;
    return NurOrb(
      animation: _waveCtrl,
      size: size,
      energy: _error ? 0.1 : (_running ? 0.8 : 0.4),
      progress: _error ? -1 : _pct / 100.0,
      a: _error ? p.err : p.teal,
      b: _error ? p.warn : p.goldLight,
      child: ClipOval(
        child: SizedBox(
          width: logo,
          height: logo,
          child: Image.asset('assets/images/logo.png',
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) =>
              Icon(Icons.menu_book_rounded, color: p.gold, size: logo * 0.7)),
        ),
      ),
    );
  }

  Widget _title(NurPalette p) => Column(children: [
    GradientText('محسِّن التلاوة',
      gradient: p.goldGradient,
      textAlign: TextAlign.center,
      style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900)),
    const SizedBox(height: 6),
    Text('Local Engine Setup',
      textAlign: TextAlign.center,
      style: TextStyle(
        color: p.textSub, fontSize: 13, letterSpacing: 0.6)),
  ]);

  Widget _progressCard(NurPalette p) => NurCard(
    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 22),
    accent: p.teal,
    glow: _running,
    child: Column(children: [
      Directionality(
        textDirection: TextDirection.ltr,
        child: FittedBox(
          fit: BoxFit.scaleDown,
          child: GradientText('$_pct%',
            gradient: p.goldGradient,
            style: const TextStyle(
              fontSize: 52, fontWeight: FontWeight.w900,
              height: 1.0, letterSpacing: -2)))),
      const SizedBox(height: 16),
      NurProgressBar(
        value: _pct / 100.0,
        height: 10,
        a: p.teal,
        b: p.goldLight),
      const SizedBox(height: 14),
      AnimatedSwitcher(
        duration: const Duration(milliseconds: 250),
        child: Text(_phase,
          key: ValueKey(_phase),
          textAlign: TextAlign.center,
          style: TextStyle(
            color: p.textSub, fontSize: 12, letterSpacing: 0.3))),
    ]));

  Widget _errorCard(NurPalette p, bool ar) => NurCard(
    padding: const EdgeInsets.all(20),
    accent: p.err,
    selected: true,
    child: Column(children: [
      Icon(Icons.error_outline_rounded, color: p.err, size: 40),
      const SizedBox(height: 12),
      Text(ar ? 'فشل الإعداد' : 'Setup Failed',
        textAlign: TextAlign.center,
        style: TextStyle(
          color: p.err, fontSize: 16, fontWeight: FontWeight.bold)),
      const SizedBox(height: 8),
      Text(_errMsg,
        textAlign: TextAlign.center,
        style: TextStyle(color: p.textSub, fontSize: 11, height: 1.5)),
      const SizedBox(height: 20),
      NurButton(
        label: ar ? 'إعادة المحاولة' : 'Retry',
        icon: Icons.refresh_rounded,
        onTap: () { setState(() { _running = false; }); _startSetup(); }),
    ]));

  Widget _infoCard(NurPalette p, bool ar) {
    final rows = <(IconData, String)>[
      (Icons.wifi_off_rounded,
        ar ? 'يعمل بالكامل دون إنترنت بعد الإعداد' : 'Works fully offline after setup'),
      (Icons.lock_outline_rounded,
        ar ? 'صوتك لا يغادر هاتفك أبداً' : 'Your audio never leaves your phone'),
      (Icons.download_rounded,
        ar ? 'تنزيل لمرة واحدة  ~200 م.ب' : 'One-time download  ~200 MB'),
      (Icons.storage_rounded,
        ar ? 'يستخدم ~300 م.ب من التخزين' : 'Uses ~300 MB of storage'),
      // S237: download() now retries with HTTP-Range resume
      (Icons.sync_rounded,
        ar ? 'يُستأنف التنزيل المقطوع تلقائياً' : 'Interrupted downloads resume automatically'),
    ];
    return NurCard(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      radius: 18,
      child: Column(children: [
        for (var i = 0; i < rows.length; i++) ...[
          if (i > 0) const SizedBox(height: 10),
          EntranceFade(
            index: i + 4,
            offsetY: 8,
            child: _row(p, rows[i].$1, rows[i].$2)),
        ],
      ]));
  }

  Widget _row(NurPalette p, IconData ic, String txt) => Row(children: [
    Container(
      width: 30, height: 30,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: p.teal.withValues(alpha: 0.12)),
      child: Icon(ic, color: p.teal, size: 16)),
    const SizedBox(width: 12),
    Expanded(child: Text(txt,
      style: TextStyle(color: p.textSub, fontSize: 12, height: 1.4))),
  ]);
}
