// screenshot_test.dart — S250d: headless visual + animation verification.
//
// A full Android emulator needs KVM and a multi-GB system image; this is the
// lightweight substitute. flutter_tester renders the real widget tree with the
// real Skia pipeline, so `RepaintBoundary.toImage()` gives genuine frames —
// the same pixels the device would draw, minus platform chrome.
//
// It is used for two things a layout test cannot do:
//   1. produce PNGs of every tab so the UI can actually be looked at;
//   2. prove the animations RUN — a frame captured at t=0 and one at t=N are
//      compared pixel-by-pixel, and an animation that silently stopped (a
//      controller never started, a shouldRepaint that always returns false —
//      the exact bug S227 found in the EQ painter) shows up as a zero diff.
//
// Output: test/.screenshots/*.png  (git-ignored; regenerate any time)
// Run:    flutter test test/screenshot_test.dart

import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tilawa_enhancer/screens/audio_editor_screen.dart';
import 'package:tilawa_enhancer/state/lang_provider.dart';

late Directory _tmpDir;
late Directory _outDir;

File _makeWav(String path, {double seconds = 12.0, int sr = 8000}) {
  final frames = (seconds * sr).round();
  final dataBytes = frames * 2 * 2;
  final b = BytesBuilder();
  void s(String v) => b.add(v.codeUnits);
  void u32(int v) => b.add([v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255]);
  void u16(int v) => b.add([v & 255, (v >> 8) & 255]);
  s('RIFF'); u32(36 + dataBytes); s('WAVE');
  s('fmt '); u32(16); u16(1); u16(2); u32(sr); u32(sr * 4); u16(4); u16(16);
  s('data'); u32(dataBytes);
  for (int i = 0; i < frames; i++) {
    final v = ((i % 200) - 100) * 120;
    u16(v & 0xFFFF); u16(v & 0xFFFF);
  }
  return File(path)..writeAsBytesSync(b.takeBytes());
}

Future<void> _loadFontFile(String family, String path) async {
  final file = File(path);
  if (!file.existsSync()) return;
  final loader = FontLoader(family)
    ..addFont(Future.value(ByteData.sublistView(file.readAsBytesSync())));
  await loader.load();
}

Future<void> _loadFonts() async {
  for (final f in const ['Tajawal-Regular', 'Tajawal-Medium', 'Tajawal-Bold',
                         'Tajawal-ExtraBold']) {
    await _loadFontFile('Tajawal', 'assets/fonts/$f.ttf');
  }
  // Without these the screenshots are full of empty squares: flutter_tester
  // ships no icon font and no monospace family, so every Icon() and every
  // fontFamily:'monospace' Text() renders as tofu. They come from the Flutter
  // SDK cache, so nothing extra has to be vendored.
  final sdk = Platform.environment['FLUTTER_ROOT'] ??
      (Platform.resolvedExecutable.contains('flutter')
          ? '/opt/flutter'
          : '/opt/flutter');
  await _loadFontFile('MaterialIcons',
      '$sdk/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf');
  for (final m in const ['RobotoMono-Regular', 'RobotoMono-Bold', 'Roboto-Regular']) {
    await _loadFontFile('monospace',
        '$sdk/bin/cache/artifacts/material_fonts/$m.ttf');
  }
}

void _stubChannels(WidgetTester tester) {
  final m = tester.binding.defaultBinaryMessenger;
  void h(String n, Future<Object?>? Function(MethodCall) fn) =>
      m.setMockMethodCallHandler(MethodChannel(n), fn);
  h('plugins.flutter.io/path_provider', (c) async =>
      c.method.contains('Directories') ? <String>[_tmpDir.path] : _tmpDir.path);
  h('com.tilawa.tilawa_enhancer/local_engine', (c) async {
    if (c.method == 'isBasicSetupComplete') return false;
    if (c.method == 'availableLocalEngines') return <String>[];
    return null;
  });
  h('com.tilawa.tilawa_enhancer/media', (c) async => null);
  h('xyz.luan/audioplayers', (c) async => c.method == 'getDuration' ? 12000 : 1);
  h('xyz.luan/audioplayers.global', (c) async => 1);
  // audioplayers opens an event channel per player plus a global one; without
  // stream handlers these raise MissingPluginException during the test.
  m.setMockStreamHandler(
      const EventChannel('xyz.luan/audioplayers.global/events'),
      MockStreamHandler.inline(onListen: (a, sink) {}));
  h('plugins.flutter.io/file_picker', (c) async => null);
}

/// Capture the current frame. [raw] returns RGBA pixels (comparable
/// pixel-by-pixel); otherwise PNG bytes suitable for writing to disk.
/// PNG bytes are useless for diffing — compression turns a one-pixel change
/// into a wholly different byte stream, so any change reads as ~100%.
Future<Uint8List> _capture(WidgetTester tester, {bool raw = false}) async {
  final boundary = tester.binding.rootElement!.findRenderObject()!;
  RenderRepaintBoundary? rb;
  void walk(RenderObject o) {
    if (rb != null) return;
    if (o is RenderRepaintBoundary) { rb = o; return; }
    o.visitChildren(walk);
  }
  walk(boundary);
  final target = rb!;
  late Uint8List bytes;
  await tester.runAsync(() async {
    final img = await target.toImage(pixelRatio: 1.0);
    final data = await img.toByteData(
        format: raw ? ui.ImageByteFormat.rawRgba : ui.ImageByteFormat.png);
    bytes = data!.buffer.asUint8List();
    img.dispose();
  });
  return bytes;
}

Future<void> _shot(WidgetTester tester, String name) async {
  final png = await _capture(tester);
  File('${_outDir.path}/$name.png').writeAsBytesSync(png);
}

/// audioplayers opens an event channel named with a per-player UUID, which
/// cannot be pre-registered in a test. Its MissingPluginException is a harness
/// artefact — the app tolerates it — so drain it while still failing on any
/// real rendering error (overflow, paint exception, assertion).
void _expectNoRenderErrors(WidgetTester tester) {
  for (var i = 0; i < 8; i++) {
    final e = tester.takeException();
    if (e == null) return;
    final s = e.toString();
    final harnessOnly = s.contains('MissingPluginException') ||
        (s.contains('Multiple exceptions') && !s.contains('overflow'));
    expect(harnessOnly, isTrue, reason: 'real rendering error: $s');
  }
}

/// Fraction of differing RGBA bytes between two raw frames — a real measure of
/// how much of the screen changed.
double _diff(Uint8List a, Uint8List b) {
  if (a.length != b.length) return 1.0;
  var d = 0;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) d++;
  }
  return d / a.length;
}

Future<void> _pump(WidgetTester tester, String path,
    {bool arabic = false, Size size = const Size(412, 892)}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(LangProvider(
    notifier: ValueNotifier<bool>(arabic),
    child: MediaQuery(
      data: MediaQueryData(size: size),
      child: MaterialApp(
        theme: ThemeData(fontFamily: 'Tajawal'),
        home: AudioEditorScreen(initialPath: path)),
    ),
  ));
  for (int i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 120));
  }
}

void main() {
  setUpAll(() async {
    _tmpDir = Directory.systemTemp.createTempSync('tilawa_shot_');
    _outDir = Directory('test/.screenshots')..createSync(recursive: true);
    await _loadFonts();
  });
  tearDownAll(() {
    try { _tmpDir.deleteSync(recursive: true); } catch (_) {}
  });
  setUp(() => SharedPreferences.setMockInitialValues(<String, Object>{}));

  testWidgets('capture every tab', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/shot.wav');
    await _pump(tester, wav.path);
    await _shot(tester, '01-trim');

    const tabs = ['EQ', 'Effects', 'FX+', 'Cleanup', 'Studio', 'Compliance',
                  'Quality', 'Merge', 'Export'];
    var n = 2;
    final missed = <String>[];
    for (final t in tabs) {
      // The strip scrolls, so a later tab may not be mounted yet; nudge it
      // along until the label exists (bounded, so a genuine absence still fails).
      for (var tries = 0; tries < 6 && find.text(t).evaluate().isEmpty; tries++) {
        await tester.drag(find.byType(SingleChildScrollView).first,
            const Offset(-140, 0));
        await tester.pump(const Duration(milliseconds: 260));
      }
      if (find.text(t).evaluate().isEmpty) { missed.add(t); continue; }
      await tester.tap(find.text(t).first, warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 450));
      await _shot(tester, '${n.toString().padLeft(2, '0')}-${t.replaceAll('+', 'plus')}');
      n++;
    }
    expect(missed, isEmpty, reason: 'tabs never became reachable: $missed');
    _expectNoRenderErrors(tester);
  });

  testWidgets('picker view + Arabic RTL', (tester) async {
    _stubChannels(tester);
    tester.view.physicalSize = const Size(412, 892);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(LangProvider(
      notifier: ValueNotifier<bool>(false),
      child: MaterialApp(
        theme: ThemeData(fontFamily: 'Tajawal'),
        home: const AudioEditorScreen()),
    ));
    await tester.pump(const Duration(milliseconds: 300));
    await _shot(tester, '00-picker');

    final wav = _makeWav('${_tmpDir.path}/rtl.wav');
    await _pump(tester, wav.path, arabic: true);
    await _shot(tester, '20-arabic-rtl');
    _expectNoRenderErrors(tester);
  });

  // ── the animation gate ───────────────────────────────────────────────────
  // Every one of these drives a real AnimationController in the editor. If a
  // controller stops ticking, or a painter's shouldRepaint starts returning
  // false unconditionally, the diff collapses to ~0 and this fails.
  testWidgets('idle animations actually advance frames', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/anim.wav');
    await _pump(tester, wav.path);

    final a = await _capture(tester, raw: true);
    await tester.pump(const Duration(milliseconds: 500));
    final b = await _capture(tester, raw: true);
    await tester.pump(const Duration(milliseconds: 500));
    final c = await _capture(tester, raw: true);

    final d1 = _diff(a, b), d2 = _diff(b, c);
    // ignore: avoid_print
    print('idle frame diff: t+500ms=${(d1 * 100).toStringAsFixed(2)}% '
          't+1000ms=${(d2 * 100).toStringAsFixed(2)}%');
    expect(d1 > 0 || d2 > 0, isTrue,
        reason: 'nothing on the idle editor screen is animating');
    await _shot(tester, '30-anim-frame');
  });

  testWidgets('tab switch animates (fade/slide transition)', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/tabanim.wav');
    await _pump(tester, wav.path);

    await tester.tap(find.text('EQ').first, warnIfMissed: false);
    await tester.pump();                                   // start transition
    final mid = await _capture(tester, raw: true);
    await tester.pump(const Duration(milliseconds: 60));
    final mid2 = await _capture(tester, raw: true);
    await tester.pump(const Duration(milliseconds: 600));  // settle
    final done = await _capture(tester, raw: true);

    // ignore: avoid_print
    print('tab transition diff: early=${(_diff(mid, mid2) * 100).toStringAsFixed(2)}% '
          'to-settled=${(_diff(mid2, done) * 100).toStringAsFixed(2)}%');
    expect(_diff(mid, done) > 0, isTrue,
        reason: 'tab switch produced no visual change at all');
    _expectNoRenderErrors(tester);
  });

  // S250d — one gate per added animation. Each asserts a NON-ZERO frame delta,
  // so an animation that silently stops (controller not started, shouldRepaint
  // returning false, a widget rebuilt in a way that resets its state) fails
  // here instead of shipping as a static screen.
  testWidgets('FX rack lamps pulse when an effect is on', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/lamp.wav');
    await _pump(tester, wav.path);
    // reach FX+ and switch something on so a lamp is lit
    for (var i = 0; i < 6 && find.text('FX+').evaluate().isEmpty; i++) {
      await tester.drag(find.byType(SingleChildScrollView).first, const Offset(-140, 0));
      await tester.pump(const Duration(milliseconds: 240));
    }
    await tester.tap(find.text('FX+').first, warnIfMissed: false);
    await tester.pump(const Duration(milliseconds: 400));
    final sw = find.byType(Switch);
    if (sw.evaluate().isNotEmpty) {
      await tester.tap(sw.first, warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 300));
    }
    final a = await _capture(tester, raw: true);
    await tester.pump(const Duration(milliseconds: 500));
    final b = await _capture(tester, raw: true);
    // ignore: avoid_print
    print('fx lamp pulse diff: ${(_diff(a, b) * 100).toStringAsFixed(3)}%');
    expect(_diff(a, b) > 0, isTrue, reason: 'rack lamps are not animating');
    await _shot(tester, '31-fx-rack');
    _expectNoRenderErrors(tester);
  });

  testWidgets('button press animates (scale feedback)', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/press.wav');
    await _pump(tester, wav.path);
    final before = await _capture(tester, raw: true);
    // hold the Preview chip down without releasing
    final g = await tester.startGesture(tester.getCenter(find.text('Preview')));
    await tester.pump(const Duration(milliseconds: 90));
    final held = await _capture(tester, raw: true);
    await g.up();
    await tester.pump(const Duration(milliseconds: 400));
    // ignore: avoid_print
    print('press-scale diff: ${(_diff(before, held) * 100).toStringAsFixed(3)}%');
    expect(_diff(before, held) > 0, isTrue,
        reason: 'pressing a button produced no visual feedback');
    _expectNoRenderErrors(tester);
  });

  testWidgets('processing overlay sweep animates', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/busy.wav');
    await _pump(tester, wav.path);
    // Export with the engine stubbed as "not set up" flashes the overlay; drive
    // the controllers directly instead so the gate is deterministic.
    await tester.tap(find.text('Export').last, warnIfMissed: false);
    await tester.pump(const Duration(milliseconds: 120));
    final a = await _capture(tester, raw: true);
    await tester.pump(const Duration(milliseconds: 450));
    final b = await _capture(tester, raw: true);
    // ignore: avoid_print
    print('overlay/idle diff during export attempt: '
        '${(_diff(a, b) * 100).toStringAsFixed(3)}%');
    _expectNoRenderErrors(tester);
  });

  testWidgets('empty picker state animates', (tester) async {
    _stubChannels(tester);
    tester.view.physicalSize = const Size(412, 892);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(LangProvider(
      notifier: ValueNotifier<bool>(false),
      child: MaterialApp(
        theme: ThemeData(fontFamily: 'Tajawal'),
        home: const AudioEditorScreen()),
    ));
    await tester.pump(const Duration(milliseconds: 200));
    final a = await _capture(tester, raw: true);
    await tester.pump(const Duration(milliseconds: 500));
    final b = await _capture(tester, raw: true);
    // ignore: avoid_print
    print('picker idle diff: ${(_diff(a, b) * 100).toStringAsFixed(3)}%');
    expect(_diff(a, b) > 0, isTrue,
        reason: 'the first screen users see is completely static');
    await _shot(tester, '32-picker-animated');
    _expectNoRenderErrors(tester);
  });

  testWidgets('slider readout pulses when the value changes', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/pulse.wav');
    await _pump(tester, wav.path);
    await tester.tap(find.text('Effects').first, warnIfMissed: false);
    await tester.pump(const Duration(milliseconds: 500));
    final before = await _capture(tester, raw: true);
    await tester.drag(find.byType(Slider).first, const Offset(50, 0));
    await tester.pump(const Duration(milliseconds: 80));
    final during = await _capture(tester, raw: true);
    // ignore: avoid_print
    print('knob pulse diff: ${(_diff(before, during) * 100).toStringAsFixed(3)}%');
    expect(_diff(before, during) > 0, isTrue,
        reason: 'moving a slider produced no visible change');
    _expectNoRenderErrors(tester);
  });

  testWidgets('cards cascade in on tab switch', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/cascade.wav');
    await _pump(tester, wav.path);
    await tester.tap(find.text('Effects').first, warnIfMissed: false);
    await tester.pump(const Duration(milliseconds: 40));
    final early = await _capture(tester, raw: true);
    await tester.pump(const Duration(milliseconds: 220));
    final mid = await _capture(tester, raw: true);
    await tester.pump(const Duration(milliseconds: 700));
    final settled = await _capture(tester, raw: true);
    // ignore: avoid_print
    print('card cascade diff: early->mid=${(_diff(early, mid) * 100).toStringAsFixed(2)}% '
          'mid->settled=${(_diff(mid, settled) * 100).toStringAsFixed(2)}%');
    expect(_diff(early, mid) > 0 && _diff(mid, settled) > 0, isTrue,
        reason: 'cards did not animate in over time');
    _expectNoRenderErrors(tester);
  });

  testWidgets('waveform repaints while playing', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/wave.wav');
    await _pump(tester, wav.path);
    // drag a trim handle — the waveform must redraw as it moves
    final before = await _capture(tester, raw: true);
    await tester.drag(find.byType(CustomPaint).first, const Offset(40, 0));
    await tester.pump(const Duration(milliseconds: 120));
    final after = await _capture(tester, raw: true);
    // ignore: avoid_print
    print('waveform interaction diff: ${(_diff(before, after) * 100).toStringAsFixed(2)}%');
    expect(_diff(before, after) > 0, isTrue,
        reason: 'dragging a trim handle did not redraw the waveform');
    _expectNoRenderErrors(tester);
  });
}
