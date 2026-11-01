// lib/screens/game_screen.dart — S209
// "Play while you wait" — hosts the Nova Drift HTML5 game in a WebView.
// Pushed on top of HomeScreen without disposing it, so a running upload or
// local-engine job (owned by HomeScreen's State) keeps going in the
// background exactly as it would if the user just locked their phone.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';
import '../state/lang_provider.dart';

const _gGold = Color(0xFFD4AF37);
const _gCyan = Color(0xFF3DF0FF);
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
    return PopScope(
      canPop: true,
      child: Scaffold(
        backgroundColor: _gBg,
        body: Stack(children: [
          WebViewWidget(controller: _controller),
          if (_loading)
            Container(
              color: _gBg,
              alignment: Alignment.center,
              child: const CircularProgressIndicator(
                color: _gGold, strokeWidth: 2.4)),
          if (_failed)
            Container(
              color: _gBg,
              alignment: Alignment.center,
              padding: const EdgeInsets.all(32),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.satellite_alt_rounded,
                  color: _gCyan, size: 40),
                const SizedBox(height: 16),
                Text(s.gameLoadError,
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: Color(0xFF8B949E), fontSize: 13)),
                const SizedBox(height: 20),
                TextButton.icon(
                  onPressed: () => Navigator.of(context).pop(),
                  icon: const Icon(Icons.arrow_back_rounded, color: _gGold, size: 16),
                  label: Text(s.ar ? 'رجوع' : 'Back',
                    style: const TextStyle(color: _gGold, fontSize: 13))),
              ])),
          // Minimal exit affordance — bottom-left, clear of the game's own
          // UI (settings gear top-left, pause top-right, dash button
          // bottom-right, on-screen joysticks anchored to touch points).
          Positioned(
            left: 10, bottom: 10,
            child: SafeArea(
              child: GestureDetector(
                onTap: () => Navigator.of(context).pop(),
                child: Container(
                  width: 34, height: 34,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.black.withValues(alpha: 0.35),
                    border: Border.all(
                      color: _gGold.withValues(alpha: 0.35), width: 0.8)),
                  child: const Icon(Icons.close_rounded,
                    color: _gGold, size: 16)))),
          ),
        ]),
      ),
    );
  }
}
