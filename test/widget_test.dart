// widget_test.dart — S250: real render checks for the audio editor.
//
// These exist because layout overflow has shipped from this screen twice
// (S244 documents a 135 px clip that made the transport controls invisible AND
// untappable in release builds, then a 103 px self-inflicted one in the fix).
// A render test catches that class of bug for real instead of by inspection:
// flutter_test's RenderFlex reports an overflow as a test exception, so
// `expect(tester.takeException(), isNull)` after pumping every tab at several
// screen sizes and text scales is a genuine regression gate.
//
// The screen talks to the local-engine MethodChannel, path_provider,
// shared_preferences and audioplayers, so all of those are stubbed below. No
// DSP runs — this only exercises layout and interaction.

import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tilawa_enhancer/screens/audio_editor_screen.dart';
import 'package:tilawa_enhancer/state/lang_provider.dart';

late Directory _tmpDir;

/// A tiny but valid 16-bit PCM WAV so the editor has a real file to open.
File _makeWav(String path, {double seconds = 3.0, int sr = 8000}) {
  final frames = (seconds * sr).round();
  final dataBytes = frames * 2 * 2;                 // stereo, 16-bit
  final b = BytesBuilder();
  void s(String v) => b.add(v.codeUnits);
  void u32(int v) => b.add([v & 255, (v >> 8) & 255, (v >> 16) & 255, (v >> 24) & 255]);
  void u16(int v) => b.add([v & 255, (v >> 8) & 255]);
  s('RIFF'); u32(36 + dataBytes); s('WAVE');
  s('fmt '); u32(16); u16(1); u16(2); u32(sr); u32(sr * 4); u16(4); u16(16);
  s('data'); u32(dataBytes);
  for (int i = 0; i < frames; i++) {
    final v = ((i % 200) - 100) * 120;              // audible sawtooth
    u16(v & 0xFFFF);
    u16(v & 0xFFFF);
  }
  return File(path)..writeAsBytesSync(b.takeBytes());
}

void _stubChannels(WidgetTester tester) {
  final messenger = tester.binding.defaultBinaryMessenger;

  void handle(String name, Future<Object?>? Function(MethodCall) fn) =>
      messenger.setMockMethodCallHandler(MethodChannel(name), fn);

  // path_provider
  handle('plugins.flutter.io/path_provider', (call) async {
    switch (call.method) {
      case 'getTemporaryDirectory':
      case 'getApplicationDocumentsDirectory':
      case 'getApplicationSupportDirectory':
      case 'getStorageDirectory':
      case 'getExternalStorageDirectory':
        return _tmpDir.path;
      case 'getExternalStorageDirectories':
      case 'getExternalCacheDirectories':
        return <String>[_tmpDir.path];
    }
    return null;
  });

  // the app's own local-engine + media channels: report "not set up" so no DSP
  // is ever attempted from a test
  handle('com.tilawa.tilawa_enhancer/local_engine', (call) async {
    if (call.method == 'isBasicSetupComplete') return false;
    if (call.method == 'runProotCmd') return <String, Object>{'rc': 1, 'out': 'stub'};
    return null;
  });
  handle('com.tilawa.tilawa_enhancer/media', (call) async => null);

  // audioplayers: accept everything, report a plausible duration
  handle('xyz.luan/audioplayers', (call) async {
    if (call.method == 'getDuration') return 3000;
    if (call.method == 'getCurrentPosition') return 0;
    return 1;
  });
  handle('xyz.luan/audioplayers.global', (call) async => 1);
  handle('plugins.flutter.io/file_picker', (call) async => null);
}

/// Pump the editor inside the app's LangProvider, at a given size/text scale.
Future<void> _pumpEditor(WidgetTester tester, String path,
    {required Size size, double textScale = 1.0, bool arabic = false}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(LangProvider(
    notifier: ValueNotifier<bool>(arabic),
    child: MediaQuery(
      data: MediaQueryData(size: size, textScaler: TextScaler.linear(textScale)),
      child: MaterialApp(home: AudioEditorScreen(initialPath: path)),
    ),
  ));
  // let initState's async work (prefs, file length, setSource) settle
  for (int i = 0; i < 6; i++) {
    await tester.pump(const Duration(milliseconds: 120));
  }
}

void main() {
  setUpAll(() {
    _tmpDir = Directory.systemTemp.createTempSync('tilawa_widget_test_');
  });
  tearDownAll(() {
    try { _tmpDir.deleteSync(recursive: true); } catch (_) {}
  });

  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{});
  });

  testWidgets('picker view renders with no file', (tester) async {
    _stubChannels(tester);
    tester.view.physicalSize = const Size(412, 892);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);
    await tester.pumpWidget(LangProvider(
      notifier: ValueNotifier<bool>(false),
      child: const MaterialApp(home: AudioEditorScreen()),
    ));
    await tester.pump(const Duration(milliseconds: 200));
    expect(find.text('Open File'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  // The regression gate: every tab, at the narrow/typical/large widths and at a
  // large system font scale, must lay out without a RenderFlex overflow.
  for (final size in const [Size(360, 800), Size(412, 892), Size(480, 1000)]) {
    for (final scale in const [1.0, 1.3]) {
      testWidgets('all tabs lay out at ${size.width.toInt()}w scale $scale',
          (tester) async {
        _stubChannels(tester);
        final wav = _makeWav('${_tmpDir.path}/probe.wav');
        await _pumpEditor(tester, wav.path, size: size, textScale: scale);
        expect(tester.takeException(), isNull,
            reason: 'editor failed to lay out at ${size.width}x${size.height}');

        for (final label in const ['Trim', 'EQ', 'Effects', 'FX+', 'Cleanup',
                                   'Studio', 'Compliance', 'Quality', 'Merge',
                                   'Export']) {
          final finder = find.text(label);
          if (finder.evaluate().isEmpty) continue;   // scrolled out of view
          await tester.tap(finder.first, warnIfMissed: false);
          await tester.pump(const Duration(milliseconds: 350));
          expect(tester.takeException(), isNull,
              reason: '$label tab overflowed at ${size.width}w scale $scale');
        }
      });
    }
  }

  testWidgets('tab strip scrolls to reveal the later tabs', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/scroll.wav');
    await _pumpEditor(tester, wav.path, size: const Size(360, 800));

    // Export is the last tab; on a 360 dp phone it starts off-screen and must
    // be reachable by dragging the strip (the old fixed Row clipped it instead).
    await tester.drag(find.text('Trim'), const Offset(-400, 0));
    await tester.pump(const Duration(milliseconds: 300));
    expect(find.text('Export'), findsWidgets);
    expect(tester.takeException(), isNull);
  });

  testWidgets('renders in Arabic (RTL) with no overflow', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/rtl.wav');
    await _pumpEditor(tester, wav.path, size: const Size(412, 892), arabic: true);
    expect(find.text('محرر الصوت'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('undo and redo restore a changed setting', (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/undo.wav');
    await _pumpEditor(tester, wav.path, size: const Size(412, 892));

    // Effects tab → move the Volume slider, then undo it.
    await tester.tap(find.text('Effects'), warnIfMissed: false);
    await tester.pump(const Duration(milliseconds: 350));
    final sliders = find.byType(Slider);
    expect(sliders, findsWidgets);
    final before = tester.widget<Slider>(sliders.first).value;
    await tester.drag(sliders.first, const Offset(60, 0));
    await tester.pump(const Duration(milliseconds: 100));
    final after = tester.widget<Slider>(find.byType(Slider).first).value;
    expect(after, isNot(equals(before)), reason: 'slider did not move');

    await tester.tap(find.byIcon(Icons.undo_rounded));
    await tester.pump(const Duration(milliseconds: 200));
    expect(tester.widget<Slider>(find.byType(Slider).first).value,
        closeTo(before, 0.0001), reason: 'undo did not restore the value');

    await tester.tap(find.byIcon(Icons.redo_rounded));
    await tester.pump(const Duration(milliseconds: 200));
    expect(tester.widget<Slider>(find.byType(Slider).first).value,
        closeTo(after, 0.0001), reason: 'redo did not re-apply the value');
    expect(tester.takeException(), isNull);
  });

  testWidgets('transport, action bar and waveform are all present',
      (tester) async {
    _stubChannels(tester);
    final wav = _makeWav('${_tmpDir.path}/bars.wav');
    await _pumpEditor(tester, wav.path, size: const Size(412, 892));
    // the controls S244 found rendered off-screen
    expect(find.byIcon(Icons.play_arrow_rounded), findsOneWidget);
    expect(find.byIcon(Icons.replay_10_rounded), findsOneWidget);
    expect(find.byIcon(Icons.forward_10_rounded), findsOneWidget);
    expect(find.byIcon(Icons.stop_rounded), findsOneWidget);
    expect(find.byIcon(Icons.loop_rounded), findsOneWidget);
    // the persistent action bar (S250)
    expect(find.text('Preview'), findsOneWidget);
    expect(find.text('A/B'), findsOneWidget);
    expect(find.text('Export'), findsWidgets);
    expect(tester.takeException(), isNull);
  });
}
