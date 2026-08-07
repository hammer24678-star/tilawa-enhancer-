// mobile_screens_test.dart — a render gate for every screen except the editor.
//
// widget_test.dart already pumps the audio editor at four widths and two text
// scales, because overflow had shipped from that screen twice. Every other
// screen in the app had no render test at all — including home_screen.dart,
// which is 4,200 lines, is the first thing anyone sees after the welcome tour,
// and carries the whole local-mode flow.
//
// That is the same exposure the editor had before S250: a RenderFlex overflow
// makes controls invisible AND untappable in a release build, and nothing in
// CI would have caught one. flutter_test reports an overflow as a test
// exception, so pumping each screen and asserting `takeException() == null` is
// a genuine gate rather than an inspection.
//
// Sizes are the real ones this app ships to: 320 dp is the narrowest Android
// phone still in the wild, 360 dp is the median, 412 dp a Pixel, 480 dp a
// large phone. Text scale 1.3 is Android's "Large" accessibility setting,
// which is where fixed-height rows break first. Both languages are pumped
// because Arabic is the default and RTL lays out differently.
//
// No DSP, no network: every platform channel the screens touch is stubbed.

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:tilawa_enhancer/main.dart' show ThemeProvider;
import 'package:tilawa_enhancer/state/lang_provider.dart';

import 'package:tilawa_enhancer/screens/home_screen.dart';
import 'package:tilawa_enhancer/screens/welcome_screen.dart';
import 'package:tilawa_enhancer/screens/settings_screen.dart';
import 'package:tilawa_enhancer/screens/setup_screen.dart';
import 'package:tilawa_enhancer/screens/history_screen.dart';
import 'package:tilawa_enhancer/screens/ai_tools_screen.dart';
import 'package:tilawa_enhancer/screens/engine_code_screen.dart';
import 'package:tilawa_enhancer/screens/local_mode_info_screen.dart';

late Directory _tmpDir;

/// Load the fonts the app actually ships with.
///
/// This matters for a layout gate: flutter_tester's default font draws every
/// glyph as a square of the font size, so Arabic strings measure far wider
/// than they ever do on a device and would report overflows that do not
/// exist. Measuring against Tajawal — the bundled typeface — is the only way
/// a failure here means something real.
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
  // flutter_tester ships no icon font, so without this every Icon() measures
  // as tofu and the rows it sits in are the wrong width.
  final sdk = Platform.environment['FLUTTER_ROOT'] ?? '/opt/flutter';
  await _loadFontFile('MaterialIcons',
      '$sdk/bin/cache/artifacts/material_fonts/MaterialIcons-Regular.otf');
  for (final m in const ['RobotoMono-Regular', 'RobotoMono-Bold',
                         'Roboto-Regular']) {
    await _loadFontFile('monospace',
        '$sdk/bin/cache/artifacts/material_fonts/$m.ttf');
  }
}

/// Every screen size this app is expected to lay out at, narrowest first.
const _sizes = <Size>[
  Size(320, 640),   // narrowest Android phone still shipping
  Size(360, 740),   // median Android
  Size(412, 892),   // Pixel
  Size(480, 960),   // large phone
];

void _stubChannels(WidgetTester tester) {
  final messenger = tester.binding.defaultBinaryMessenger;

  void handle(String name, Future<Object?>? Function(MethodCall) fn) =>
      messenger.setMockMethodCallHandler(MethodChannel(name), fn);

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

  // Local engine: report "prepared" so the home screen renders its normal
  // local-mode surface rather than only the setup placeholder. The individual
  // getters return shapes matching LocalEngineRunner.kt's real return types.
  handle('com.tilawa.tilawa_enhancer/local_engine', (call) async {
    switch (call.method) {
      case 'isSetupComplete':
      case 'isBasicSetupComplete':
      case 'ffmpegWorks':
      case 'numpyImports':
        return true;
      case 'availableLocalEngines':
        return <String>['v11.3', 'v10.0', 'v8.5', 'v7.0'];
      case 'getSetupStatus':
        return <String, Object>{
          'proot': true, 'python': true, 'libpython': true, 'ffmpeg': true,
          'numpy': true, 'scipy': true, 'deepFilter': true,
          'engines': 8, 'refAudio': 3, 'cacheFiles': 0,
          'cacheBytes': 0, 'runtimeBytes': 0, 'freeBytes': 1 << 30,
          'setupDone': true, 'buildId': 'test',
        };
      case 'clearEngineCache':
        return <String, Object>{'freedBytes': 0, 'deletedFiles': 0};
      case 'runProotCmd':
        return <String, Object>{'rc': 1, 'out': 'stub'};
      case 'diagnose':
        return <String, Object>{};
    }
    return null;
  });
  handle('com.tilawa.tilawa_enhancer/media', (call) async => null);
  handle('com.tilawa.tilawa_enhancer/wake', (call) async => null);

  handle('xyz.luan/audioplayers', (call) async {
    if (call.method == 'getDuration') return 3000;
    if (call.method == 'getCurrentPosition') return 0;
    return 1;
  });
  handle('xyz.luan/audioplayers.global', (call) async => 1);
  handle('plugins.flutter.io/file_picker', (call) async => null);
  handle('plugins.flutter.io/url_launcher', (call) async => true);
  // initialize() is typed Future<bool>; a null reply throws a TypeError that
  // would be reported as a screen failure rather than a stub gap.
  handle('dexterous.com/flutter/local_notifications', (call) async {
    switch (call.method) {
      case 'initialize':
      case 'requestNotificationsPermission':
      case 'requestPermissions':
        return true;
      case 'pendingNotificationRequests':
      case 'getActiveNotifications':
        return <Object?>[];
    }
    return null;
  });
}

/// Mount a screen with the two InheritedWidgets every screen reads
/// (LangProvider, ThemeProvider) plus a MaterialApp, at a given size/scale.
Future<void> _pump(
  WidgetTester tester,
  Widget screen, {
  required Size size,
  double textScale = 1.0,
  bool arabic = true,
  bool dark = true,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.reset);

  await tester.pumpWidget(ThemeProvider(
    notifier: ValueNotifier<bool>(dark),
    child: LangProvider(
      notifier: ValueNotifier<bool>(arabic),
      child: MediaQuery(
        data: MediaQueryData(
            size: size, textScaler: TextScaler.linear(textScale)),
        child: MaterialApp(
          theme: ThemeData(useMaterial3: true, fontFamily: 'Tajawal'),
          home: screen,
        ),
      ),
    ),
  ));

  // Let initState's async work (prefs, channel round-trips, file probes)
  // settle. pumpAndSettle is unusable here: several screens run permanent
  // idle animations, so it would time out rather than fail meaningfully.
  for (int i = 0; i < 8; i++) {
    await tester.pump(const Duration(milliseconds: 120));
  }
}

/// The screens under test, by name, each built fresh per pump.
final _screens = <String, Widget Function()>{
  'home':       () => const HomeScreen(),
  'welcome':    () => const WelcomeScreen(),
  'settings':   () => const SettingsScreen(),
  'setup':      () => SetupScreen(onDone: () {}, onSkip: () {}),
  'history':    () => const HistoryScreen(),
  'ai_tools':   () => const AiToolsScreen(),
  'engineCode': () => const EngineCodeScreen(),
  'localInfo':  () => const LocalModeInfoScreen(),
};

void main() {
  setUpAll(() async {
    _tmpDir = Directory.systemTemp.createTempSync('tilawa_mobile_test_');
    await _loadFonts();
  });
  tearDownAll(() {
    try { _tmpDir.deleteSync(recursive: true); } catch (_) {}
  });

  setUp(() {
    SharedPreferences.setMockInitialValues(<String, Object>{
      'lang_ar': true,
      'is_dark': true,
      'seen_welcome_v5': true,
    });
  });

  // ── The core gate: every screen, every phone width, both text scales ──────
  for (final entry in _screens.entries) {
    for (final size in _sizes) {
      for (final scale in <double>[1.0, 1.3]) {
        testWidgets(
            '${entry.key} lays out at ${size.width.toInt()}w scale $scale',
            (tester) async {
          _stubChannels(tester);
          await _pump(tester, entry.value(), size: size, textScale: scale);
          expect(tester.takeException(), isNull,
              reason: '${entry.key} overflowed or threw at '
                  '${size.width.toInt()}x${size.height.toInt()} @$scale');
        });
      }
    }
  }

  // ── Arabic is the default language, but English must lay out too ─────────
  for (final entry in _screens.entries) {
    testWidgets('${entry.key} lays out in English (LTR)', (tester) async {
      _stubChannels(tester);
      await _pump(tester, entry.value(),
          size: const Size(360, 740), arabic: false);
      expect(tester.takeException(), isNull,
          reason: '${entry.key} broke in English');
    });
  }

  // ── Light theme is a first-class setting, not a variant to skip ──────────
  for (final entry in _screens.entries) {
    testWidgets('${entry.key} lays out in light theme', (tester) async {
      _stubChannels(tester);
      await _pump(tester, entry.value(),
          size: const Size(360, 740), dark: false);
      expect(tester.takeException(), isNull,
          reason: '${entry.key} broke in light theme');
    });
  }
}
