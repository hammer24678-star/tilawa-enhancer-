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


  late final AnimationController _shimCtrl;

  @override
  void initState() {
    super.initState();
    _shimCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1400))
      ..repeat();
    _startSetup();
  }

  @override
  void dispose() {
    _sub?.cancel();
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
    final p = NurPalette.of(context);
    return AnnotatedRegion<SystemUiOverlayStyle>(
      value: p.dark ? SystemUiOverlayStyle.light : SystemUiOverlayStyle.dark,
      child: Scaffold(
        backgroundColor: p.bg,
        body: NurBackdrop(
          accent: _error ? p.err : p.teal,
          child: SafeArea(
            child: SingleChildScrollView(
              physics: const BouncingScrollPhysics(),
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
              child: Column(children: [
                const SizedBox(height: 12),
                EntranceFade(index: 0, child: _hero(p)),
                const SizedBox(height: 28),
                EntranceFade(index: 1, child: _title(p)),
                const SizedBox(height: 32),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 300),
                  child: _error ? _errorCard(p) : _progressCard(p)),
                const SizedBox(height: 24),
                EntranceFade(index: 2, child: _infoCard(p)),
                const SizedBox(height: 12),
                TextButton(
                  onPressed: widget.onSkip,
                  child: Text('Use server mode instead',
                    style: TextStyle(color: p.textSub, fontSize: 13))),
                const SizedBox(height: 16),
              ]),
            ),
          ),
        ),
      ),
    );
  }

  Widget _hero(NurPalette p) => NurOrb(
    animation: _shimCtrl,
    size: 220,
    energy: _error ? 0.1 : 0.35 + 0.65 * (_pct / 100.0),
    progress: _error ? -1 : _pct / 100.0,
    a: _error ? p.err : null,
    child: Container(
      width: 92, height: 92,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: p.surface,
        border: Border.all(color: p.gold.withValues(alpha: 0.55), width: 1.6)),
      child: ClipOval(child: Image.asset('assets/images/logo.png',
        fit: BoxFit.cover,
        errorBuilder: (_, __, ___) =>
          Icon(Icons.menu_book_rounded, color: p.gold, size: 44)))));

  Widget _title(NurPalette p) => Column(children: [
    GradientText('محسِّن التلاوة',
      gradient: p.goldGradient,
      style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w900)),
    const SizedBox(height: 6),
    Text('Local Engine Setup',
      style: TextStyle(color: p.textSub, fontSize: 13, letterSpacing: 0.8)),
  ]);

  Widget _progressCard(NurPalette p) => NurCard(
    key: const ValueKey('progress'),
    radius: 24,
    glow: true,
    padding: const EdgeInsets.fromLTRB(22, 22, 22, 20),
    child: Column(children: [
      AnimatedCount(
        value: _pct.toDouble(),
        suffix: '%',
        style: TextStyle(
          color: p.gold, fontSize: 52, fontWeight: FontWeight.w900,
          height: 1.0, letterSpacing: -1.5)),
      const SizedBox(height: 18),
      NurProgressBar(value: _pct / 100.0, height: 10),
      const SizedBox(height: 14),
      AnimatedSwitcher(
        duration: const Duration(milliseconds: 250),
        child: Text(_phase,
          key: ValueKey(_phase),
          textAlign: TextAlign.center,
          style: TextStyle(color: p.textSub, fontSize: 12.5, letterSpacing: 0.2))),
    ]));

  Widget _errorCard(NurPalette p) => NurCard(
    key: const ValueKey('error'),
    radius: 24,
    accent: p.err,
    selected: true,
    padding: const EdgeInsets.all(22),
    child: Column(children: [
      Icon(Icons.error_outline_rounded, color: p.err, size: 42),
      const SizedBox(height: 12),
      Text('Setup Failed',
        style: TextStyle(color: p.err, fontSize: 17, fontWeight: FontWeight.w800)),
      const SizedBox(height: 8),
      Text(_errMsg,
        textAlign: TextAlign.center,
        style: TextStyle(color: p.textSub, fontSize: 12, height: 1.5)),
      const SizedBox(height: 20),
      NurButton(
        label: 'Retry',
        icon: Icons.refresh_rounded,
        onTap: () { setState(() { _running = false; }); _startSetup(); }),
    ]));

  Widget _infoCard(NurPalette p) => NurCard(
    radius: 20,
    padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
    child: Column(children: [
      _row(p, Icons.wifi_off_rounded,        'Works fully offline after setup'),
      const SizedBox(height: 10),
      _row(p, Icons.lock_outline_rounded,    'Your audio never leaves your phone'),
      const SizedBox(height: 10),
      _row(p, Icons.download_rounded,        'One-time download  ~200 MB'),
      const SizedBox(height: 10),
      _row(p, Icons.storage_rounded,         'Uses ~300 MB of storage'),
      const SizedBox(height: 10),
      // S237: download() now retries with HTTP-Range resume
      _row(p, Icons.sync_rounded,            'Interrupted downloads resume automatically'),
    ]));

  Widget _row(NurPalette p, IconData ic, String txt) => Row(children: [
    Container(
      width: 30, height: 30,
      decoration: BoxDecoration(
        color: p.teal.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(10)),
      child: Icon(ic, color: p.teal, size: 16)),
    const SizedBox(width: 12),
    Expanded(child: Text(txt,
      style: TextStyle(color: p.textSub, fontSize: 12, height: 1.4))),
  ]);
}
