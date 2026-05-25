import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../services/local_engine_service.dart';

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

  static const _void   = Color(0xFF020D0C);
  static const _gold   = Color(0xFFC8A048);
  static const _sunlit = Color(0xFFF0D882);
  static const _teal   = Color(0xFF1DB898);
  static const _textB  = Color(0xFF8AACBA);
  static const _jade   = Color(0xFF0D2B22);
  static const _red    = Color(0xFFD94040);

  late final AnimationController _pulseCtrl;
  late final AnimationController _shimCtrl;

  @override
  void initState() {
    super.initState();
    _pulseCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2000))
      ..repeat(reverse: true);
    _shimCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1400))
      ..repeat();
    _startSetup();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _pulseCtrl.dispose();
    _shimCtrl.dispose();
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
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: SystemUiOverlayStyle.light,
      child: Scaffold(
        backgroundColor: _void,
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 24),
            child: Column(children: [
              const SizedBox(height: 32),
              _logo(),
              const SizedBox(height: 24),
              _title(),
              const SizedBox(height: 44),
              _error ? _errorCard() : _progressCard(),
              const SizedBox(height: 28),
              _infoCard(),
              const SizedBox(height: 20),
              TextButton(
                onPressed: widget.onSkip,
                child: Text('Use server mode instead',
                  style: TextStyle(
                    color: _textB.withValues(alpha: 0.55), fontSize: 12))),
              const SizedBox(height: 16),
            ]),
          ),
        ),
      ),
    );
  }

  Widget _logo() => AnimatedBuilder(
    animation: _pulseCtrl,
    builder: (_, __) {
      final g = _pulseCtrl.value;
      return Container(
        width: 96, height: 96,
        decoration: BoxDecoration(
          shape: BoxShape.circle, color: _jade,
          border: Border.all(
            color: _gold.withValues(alpha: 0.28 + 0.45 * g), width: 2.0),
          boxShadow: [
            BoxShadow(color: _gold.withValues(alpha: 0.08 + 0.16 * g),
              blurRadius: 28 + 20 * g, spreadRadius: 2),
            BoxShadow(color: _teal.withValues(alpha: 0.04 + 0.08 * g),
              blurRadius: 48 + 28 * g),
          ]),
        child: ClipOval(child: Image.asset('assets/images/logo.png',
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) =>
            const Icon(Icons.menu_book_rounded, color: _gold, size: 50))));
    });

  Widget _title() => Column(children: [
    const Text('محسِّن التلاوة',
      style: TextStyle(color: _gold, fontSize: 26, fontWeight: FontWeight.w900)),
    const SizedBox(height: 6),
    const Text('Local Engine Setup',
      style: TextStyle(color: _textB, fontSize: 13, letterSpacing: 0.6)),
  ]);

  Widget _progressCard() => Column(children: [
    AnimatedBuilder(
      animation: _pulseCtrl,
      builder: (_, __) => ShaderMask(
        shaderCallback: (b) => const LinearGradient(
          colors: [_sunlit, _gold],
          begin: Alignment.topCenter, end: Alignment.bottomCenter,
        ).createShader(b),
        child: Text('$_pct%',
          style: const TextStyle(
            color: Colors.white, fontSize: 56, fontWeight: FontWeight.w900,
            height: 1.0, letterSpacing: -2)))),
    const SizedBox(height: 16),
    Container(
      height: 10,
      decoration: BoxDecoration(
        color: _jade, borderRadius: BorderRadius.circular(7),
        border: Border.all(color: _teal.withValues(alpha: 0.18))),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(7),
        child: LinearProgressIndicator(
          value: _pct / 100.0,
          backgroundColor: Colors.transparent,
          valueColor: AlwaysStoppedAnimation<Color>(
            _pct < 36 ? _teal : _pct < 80 ? _gold : _sunlit)))),
    const SizedBox(height: 12),
    AnimatedSwitcher(
      duration: const Duration(milliseconds: 250),
      child: Text(_phase,
        key: ValueKey(_phase),
        textAlign: TextAlign.center,
        style: const TextStyle(color: _textB, fontSize: 12, letterSpacing: 0.3))),
  ]);

  Widget _errorCard() => Container(
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: const Color(0xFF2A0A0A),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: _red.withValues(alpha: 0.45))),
    child: Column(children: [
      const Icon(Icons.error_outline_rounded, color: _red, size: 40),
      const SizedBox(height: 12),
      const Text('Setup Failed',
        style: TextStyle(color: _red, fontSize: 16, fontWeight: FontWeight.bold)),
      const SizedBox(height: 8),
      Text(_errMsg,
        textAlign: TextAlign.center,
        style: const TextStyle(color: _textB, fontSize: 11, height: 1.5)),
      const SizedBox(height: 20),
      SizedBox(width: double.infinity,
        child: ElevatedButton.icon(
          onPressed: () { setState(() { _running = false; }); _startSetup(); },
          style: ElevatedButton.styleFrom(
            backgroundColor: _gold, foregroundColor: _void,
            padding: const EdgeInsets.symmetric(vertical: 13),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10))),
          icon: const Icon(Icons.refresh_rounded, size: 18),
          label: const Text('Retry',
            style: TextStyle(fontWeight: FontWeight.w900, fontSize: 14)))),
    ]));

  Widget _infoCard() => Container(
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
    decoration: BoxDecoration(
      color: _jade.withValues(alpha: 0.6),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: _teal.withValues(alpha: 0.18))),
    child: Column(children: [
      _row(Icons.wifi_off_rounded,        'Works fully offline after setup'),
      const SizedBox(height: 8),
      _row(Icons.lock_outline_rounded,    'Your audio never leaves your phone'),
      const SizedBox(height: 8),
      _row(Icons.download_rounded,        'One-time download  ~200 MB'),
      const SizedBox(height: 8),
      _row(Icons.storage_rounded,         'Uses ~300 MB of storage'),
    ]));

  Widget _row(IconData ic, String txt) => Row(children: [
    Icon(ic, color: _teal, size: 16),
    const SizedBox(width: 10),
    Expanded(child: Text(txt,
      style: const TextStyle(color: _textB, fontSize: 11, height: 1.4))),
  ]);
}
