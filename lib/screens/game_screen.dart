// lib/screens/game_screen.dart — S209
// "Play while you wait" — hosts the Nova Drift HTML5 game in a WebView.
// Pushed on top of HomeScreen without disposing it, so a running upload or
// local-engine job (owned by HomeScreen's State) keeps going in the
// background exactly as it would if the user just locked their phone.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../design/nur.dart';
import '../state/lang_provider.dart';

const _gBg   = Color(0xFF070914); // matches Nova Drift's own --bg

class GameScreen extends StatefulWidget {
  const GameScreen({super.key});
  @override
  State<GameScreen> createState() => _GameScreenState();
}

class _GameScreenState extends State<GameScreen> {
  late final WebViewController _controller;
  bool _loading = true;
  bool _failed  = false;
  bool _pageReady = false;
  bool? _pushedAr;

  @override
  void initState() {
    super.initState();
    // S209: immersive while playing — this is meant to be a full-screen
    // distraction; restored in dispose().
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);

    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(_gBg)
      ..setNavigationDelegate(NavigationDelegate(
        onPageFinished: (_) {
          if (!mounted) return;
          _pageReady = true;
          _pushedAr = null;   // force the first push
          _pushLanguage();
          setState(() => _loading = false);
        },
        onWebResourceError: (err) {
          // S209: only fail the whole screen if the top-level asset itself
          // didn't load — a blocked/offline Google Fonts CDN sub-request
          // (see nova_drift.html's fallback font stack) must not trigger this.
          if (err.isForMainFrame == true && mounted) {
            setState(() { _loading = false; _failed = true; });
          }
        },
      ))
      ..loadFlutterAsset('assets/game/nova_drift.html');
  }

  @override
  void dispose() {
    SystemChrome.setEnabledSystemUIMode(
      SystemUiMode.edgeToEdge); // S209: matches the app's normal mode
    super.dispose();
  }

  /// S251: Nova Drift ships every player-facing string in both languages, but
  /// it has no way to know which one the app is in — the asset is loaded
  /// straight off disk with no query string. Push it across the bridge on load
  /// and again whenever the user flips the app language mid-game.
  void _pushLanguage() {
    if (!_pageReady || !mounted) return;
    final ar = LangProvider.of(context).value;
    if (_pushedAr == ar) return;
    _pushedAr = ar;
    final code = ar ? 'ar' : 'en';
    _controller.runJavaScript(
      "window.NOVA_LANG='$code';"
      "if(window.novaSetLanguage)window.novaSetLanguage('$code');",
    );
  }

  // LangProvider is an InheritedNotifier, so a language flip re-runs this;
  // that is the hook that keeps the WebView in step with the app.
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _pushLanguage();
  }

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    // The game is always dark (it matches Nova Drift's own palette), so the
    // chrome around it is pinned to the night theme regardless of app theme.
    final night = buildNurTheme(dark: true);
    final Widget overlay = _failed
        ? _GameError(
            key: const ValueKey('error'),
            message: s.gameLoadError,
            backLabel: s.ar ? 'رجوع' : 'Back',
            onBack: () => Navigator.of(context).pop())
        : _loading
            ? _GameLoading(
                key: const ValueKey('loading'),
                label: s.ar ? 'جارٍ تحميل اللعبة…' : 'Loading game…')
            : const SizedBox.shrink(key: ValueKey('none'));
    return PopScope(
      canPop: true,
      child: Scaffold(
        backgroundColor: _gBg,
        body: Stack(children: [
          WebViewWidget(controller: _controller),
          Positioned.fill(
            child: IgnorePointer(
              ignoring: !(_loading || _failed),
              child: Theme(
                data: night,
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 420),
                  switchInCurve: Curves.easeOutCubic,
                  switchOutCurve: Curves.easeInCubic,
                  layoutBuilder: (current, previous) => Stack(
                    fit: StackFit.expand,
                    children: [...previous, if (current != null) current]),
                  child: overlay)))),
          // Minimal exit affordance — bottom-left, clear of the game's own
          // UI (settings gear top-left, pause top-right, dash button
          // bottom-right, on-screen joysticks anchored to touch points).
          Positioned(
            left: 10, bottom: 10,
            child: SafeArea(
              child: Theme(
                data: night,
                child: Opacity(
                  opacity: 0.78,
                  child: NurIconButton(
                    icon: Icons.close_rounded,
                    size: 36,
                    color: NurPalette.night.gold,
                    tooltip: s.ar ? 'رجوع' : 'Back',
                    onTap: () => Navigator.of(context).pop()))))),
        ]),
      ),
    );
  }
}

/// Loading overlay: the Nur backdrop, a breathing orb and an indeterminate bar.
class _GameLoading extends StatefulWidget {
  final String label;
  const _GameLoading({super.key, required this.label});

  @override
  State<_GameLoading> createState() => _GameLoadingState();
}

class _GameLoadingState extends State<_GameLoading>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
      vsync: this, duration: const Duration(seconds: 3))
    ..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    return NurBackdrop(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            NurOrb(
              animation: _c,
              size: 170,
              child: Icon(Icons.rocket_launch_rounded, color: p.gold, size: 34)),
            const SizedBox(height: 22),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 220),
              child: const NurProgressBar(value: null, height: 5)),
            const SizedBox(height: 14),
            Text(widget.label,
                textAlign: TextAlign.center,
                style: TextStyle(color: p.textSub, fontSize: 13)),
          ]))));
  }
}

/// Error overlay shown when the game asset itself fails to load.
class _GameError extends StatelessWidget {
  final String message;
  final String backLabel;
  final VoidCallback onBack;
  const _GameError({
    super.key,
    required this.message,
    required this.backLabel,
    required this.onBack,
  });

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    return NurBackdrop(
      accent: p.err,
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(28),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TweenAnimationBuilder<double>(
              tween: Tween<double>(begin: 0.6, end: 1),
              duration: const Duration(milliseconds: 560),
              curve: Curves.easeOutBack,
              builder: (_, v, child) => Transform.scale(scale: v, child: child),
              child: Container(
                width: 76, height: 76,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: p.err.withValues(alpha: 0.12),
                  border: Border.all(color: p.err.withValues(alpha: 0.5)),
                  boxShadow: [BoxShadow(
                      color: p.err.withValues(alpha: 0.28), blurRadius: 26)]),
                child: Icon(Icons.satellite_alt_rounded, color: p.err, size: 34))),
            const SizedBox(height: 18),
            Text(message,
                textAlign: TextAlign.center,
                style: TextStyle(color: p.textSub, fontSize: 13.5, height: 1.6)),
            const SizedBox(height: 22),
            NurButton(
                label: backLabel,
                icon: Icons.arrow_back_rounded,
                filled: false,
                expand: false,
                height: 46,
                onTap: onBack),
          ]))));
  }
}
