// home_screens_shot.dart — S255: render the welcome and home screens headlessly.
//
// screenshot_test.dart does this for the audio editor. These two screens are
// the first and second thing anyone sees, and nothing rendered them, so any
// change to them was being judged by reading the source. flutter_tester draws
// the real widget tree through the real Skia pipeline, so these are the pixels
// a device would draw.
//
// Output: test/.screenshots/*.png  (git-ignored; regenerate any time)
// Run:    flutter test test/home_screens_shot.dart
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tilawa_enhancer/screens/welcome_screen.dart';
import 'package:tilawa_enhancer/screens/home_screen.dart';
import 'package:tilawa_enhancer/state/lang_provider.dart';
import 'package:tilawa_enhancer/main.dart' show ThemeProvider;

late Directory _outDir;

void _mockPlugins() {
  final m = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  void h(String name, Future<Object?> Function(MethodCall) fn) =>
      m.setMockMethodCallHandler(MethodChannel(name), fn);
  h('plugins.flutter.io/path_provider', (c) async => _outDir.path);
  h('plugins.flutter.io/file_picker', (c) async => null);
  // initialize() is typed Future<bool?>, so a null reply is a TypeError
  // rather than a no-op.
  h('dexterous.com/flutter/local_notifications',
      (c) async => c.method == 'initialize' ? true : null);
  h('xyz.luan/audioplayers.global', (c) async => null);
  h('xyz.luan/audioplayers', (c) async => null);
  // audioplayers opens a per-player event channel whose name carries a UUID,
  // so it cannot be pre-registered; its MissingPluginException is tolerated
  // below instead.
  m.setMockStreamHandler(
      const EventChannel('xyz.luan/audioplayers.global/events'),
      MockStreamHandler.inline(onListen: (a, sink) {}));
  h('com.tilawa.tilawa_enhancer/local_engine', (c) async {
    switch (c.method) {
      case 'availableLocalEngines': return <String>['v11.0', 'v11.1'];
      case 'isSetupComplete':
      case 'isBasicSetupComplete': return true;
      case 'diagnose': return <String, Object>{};
      default: return null;
    }
  });
}

Future<void> _shot(WidgetTester tester, String name) async {
  final boundary = tester.binding.rootElement!.findRenderObject()!;
  RenderRepaintBoundary? rb;
  void walk(RenderObject o) {
    if (rb != null) return;
    if (o is RenderRepaintBoundary) { rb = o; return; }
    o.visitChildren(walk);
  }
  walk(boundary);
  await tester.runAsync(() async {
    final img = await rb!.toImage(pixelRatio: 1.0);
    final data = await img.toByteData(format: ui.ImageByteFormat.png);
    File('${_outDir.path}/$name.png')
        .writeAsBytesSync(data!.buffer.asUint8List());
    img.dispose();
  });
}

/// Swallow the plugin exceptions the capture path provokes.
///
/// audioplayers subscribes to an event channel whose name carries a per-player
/// UUID, so it cannot be pre-registered, and the subscription resolves inside
/// tester.runAsync() — i.e. after the test body returns, where takeException()
/// can no longer reach it. Silencing the reporter for the duration of a capture
/// is the only place left to handle it; the sized tests below keep the real
/// expectations.
Future<void> _captureQuietly(WidgetTester tester, String name) async {
  final prevError = FlutterError.onError;
  final prevReport = reportTestException;
  reportTestException = (details, testDescription) {
    if (!details.toString().contains('MissingPluginException')) {
      prevReport(details, testDescription);
    }
  };
  FlutterError.onError = (d) {
    if (!d.toString().contains('MissingPluginException')) prevError?.call(d);
  };
  try {
    await _shot(tester, name);
    // Let anything the capture kicked off resolve INSIDE the body, so its
    // exception is drainable here rather than arriving after the test ends.
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(milliseconds: 250));
      while (tester.takeException() != null) {}
    }
  } finally {
    // Must be restored inside the body: the binding asserts that
    // reportTestException is unchanged when the test returns, so putting this
    // in a tearDown fails the test it is meant to keep quiet.
    FlutterError.onError = prevError;
    reportTestException = prevReport;
  }
}

/// Drain the plugin-channel exceptions the harness itself provokes, while
/// still failing on a real layout overflow or paint assertion.
void _expectNoRenderErrors(WidgetTester tester, String where) {
  for (var i = 0; i < 8; i++) {
    final e = tester.takeException();
    if (e == null) return;
    final s = e.toString();
    // Same rule screenshot_test.dart uses: plugin channels the harness cannot
    // provide are noise, but a layout overflow inside the multi-exception
    // wrapper is exactly what this is here to catch.
    final harnessOnly = s.contains('MissingPluginException') ||
        (s.contains('Multiple exceptions') && !s.contains('overflow'));
    expect(harnessOnly, isTrue, reason: '$where: real rendering error: $s');
  }
}

Future<void> _pump(WidgetTester tester, Widget screen,
    {bool arabic = false,
     bool dark = true,
     Size size = const Size(412, 892),
     double textScale = 1.0}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  // HomeScreen reads ThemeProvider.of(context)!, so the real app's two
  // inherited notifiers both have to be above it or it throws on first build.
  await tester.pumpWidget(ThemeProvider(
    notifier: ValueNotifier<bool>(dark),
    child: LangProvider(
      notifier: ValueNotifier<bool>(arabic),
      child: MediaQuery(
        data: MediaQueryData(size: size, textScaler: TextScaler.linear(textScale)),
        child: MaterialApp(
          theme: ThemeData(fontFamily: 'Tajawal'),
          home: screen),
      ),
    ),
  ));
  for (var i = 0; i < 8; i++) {
    await tester.pump(const Duration(milliseconds: 140));
  }
}

void main() {
  setUpAll(() async {
    TestWidgetsFlutterBinding.ensureInitialized();
    // Load the real bundled faces. Without this flutter_tester substitutes a
    // placeholder that draws every glyph as a box, which makes the captured
    // frames useless for judging typography, wrapping or truncation — the
    // things they exist to show.
    for (final f in const ['Regular', 'Medium', 'Bold', 'ExtraBold']) {
      final file = File('${Directory.current.path}/assets/fonts/Tajawal-$f.ttf');
      if (!file.existsSync()) continue;
      final loader = FontLoader('Tajawal')
        ..addFont(Future.value(
            ByteData.view(file.readAsBytesSync().buffer)));
      await loader.load();
    }
    SharedPreferences.setMockInitialValues({});
    _outDir = Directory('${Directory.current.path}/test/.screenshots');
    if (!_outDir.existsSync()) _outDir.createSync(recursive: true);
    _mockPlugins();
  });

  // These four exist to PRODUCE the PNGs. They deliberately do not assert:
  // capturing a frame runs inside tester.runAsync(), which lets audioplayers'
  // per-player event channel — whose name carries a UUID and so cannot be
  // pre-registered — throw MissingPluginException after the test body has
  // finished, where no drain can reach it. The layout expectations live in the
  // sized tests below, which cover the same two screens at the same widths.
  testWidgets('capture welcome (en)', (tester) async {
    await _pump(tester, const WelcomeScreen());
    await _captureQuietly(tester, 'welcome_en');
  });

  testWidgets('capture welcome (ar)', (tester) async {
    await _pump(tester, const WelcomeScreen(), arabic: true);
    await _captureQuietly(tester, 'welcome_ar');
  });

  testWidgets('capture home (en)', (tester) async {
    await _pump(tester, const HomeScreen());
    await _captureQuietly(tester, 'home_en');
  });

  testWidgets('capture home (ar)', (tester) async {
    await _pump(tester, const HomeScreen(), arabic: true);
    await _captureQuietly(tester, 'home_ar');
  });

  // The two sizes and the large-text setting that actually break layouts.
  for (final size in const [Size(360, 740), Size(412, 892)]) {
    for (final scale in const [1.0, 1.3]) {
      testWidgets('welcome lays out at ${size.width.toInt()}w x$scale',
          (tester) async {
        await _pump(tester, const WelcomeScreen(), size: size, textScale: scale);
        _expectNoRenderErrors(tester, 'welcome ${size.width}@$scale');
      });
      testWidgets('home lays out at ${size.width.toInt()}w x$scale',
          (tester) async {
        await _pump(tester, const HomeScreen(), size: size, textScale: scale);
        _expectNoRenderErrors(tester, 'home ${size.width}@$scale');
      });
    }
  }
}
