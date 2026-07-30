import 'dart:async';
import 'package:flutter/services.dart';

/// S65 — Dart bridge to LocalEngineRunner.kt (proot offline engine).
/// Channel: com.tilawa.tilawa_enhancer/local_engine
///
/// Kotlin auto-generates outputPath in context.cacheDir.
/// runEngine() streams:
///   progress  → {pct: -1, msg: String}
///   done      → {done: true, path: String, json: String?}
///   error     → {error: true, msg: String}
class LocalEngineService {
  static const _ch =
      MethodChannel('com.tilawa.tilawa_enhancer/local_engine');

  /// S250 — engine ids that can actually run offline, i.e. whose Python script
  /// is present in the on-device engines dir.
  ///
  /// This exists because the app offered all nine engines in local mode while
  /// five of them (v10.0, v9.0, v8.5, v8.0, v7.0) had no bundled script at all:
  /// extractEngines() asked the APK for filenames that were never in
  /// assets/engines/, the failure was swallowed, setup still reported success,
  /// and choosing one of them died inside proot with "can't open file".
  /// v10.0/v8.5/v7.0 are bundled as of S250; v9.0 and v8.0 have no script
  /// anywhere in the project, so they remain server-only and the UI now says so
  /// instead of letting the user pick a guaranteed failure.
  ///
  /// Returns an empty list if the channel is unavailable (e.g. setup not run),
  /// which callers treat as "unknown — don't restrict anything yet".
  static Future<List<String>> availableLocalEngines() async {
    try {
      final r = await _ch.invokeMethod<List<Object?>>('availableLocalEngines');
      return (r ?? const []).whereType<String>().toList();
    } catch (_) {
      return const [];
    }
  }

  // ── Setup check ──────────────────────────────────────────────────────────

  // S157: active controllers — handler routes to whichever is open
  static StreamController<Map<String, dynamic>>? _setupCtrl;
  static StreamController<Map<String, dynamic>>? _engineCtrl;

  static void _installHandler() {
    _ch.setMethodCallHandler((call) async {
      switch (call.method) {
        // Setup events
        case 'setupProgress':
          if (_setupCtrl != null && !_setupCtrl!.isClosed) {
            _setupCtrl!.add(Map<String, dynamic>.from(call.arguments as Map));
          }
          break;  // S176
        case 'setupDone':
          _setupCtrl?.close(); _setupCtrl = null;
          break;  // S176
        case 'setupError':
          if (_setupCtrl != null && !_setupCtrl!.isClosed) {
            _setupCtrl!.addError(Exception(
              ((call.arguments as Map?)?['msg'] as String?) ?? 'Setup failed'));
            _setupCtrl!.close(); _setupCtrl = null;
          }
          break;  // S176
        // Engine events
        case 'engineProgress':
          if (_engineCtrl != null && !_engineCtrl!.isClosed) {
            _engineCtrl!.add({'pct': -1,
              ...Map<String, dynamic>.from(call.arguments as Map)});
          }
          break;  // S176
        case 'engineDone':
          if (_engineCtrl != null && !_engineCtrl!.isClosed) {
            _engineCtrl!.add({'done': true,
              ...Map<String, dynamic>.from(call.arguments as Map)});
            _engineCtrl!.close(); _engineCtrl = null;
          }
          break;  // S176
        case 'engineError':
          if (_engineCtrl != null && !_engineCtrl!.isClosed) {
            _engineCtrl!.add({'error': true,
              ...Map<String, dynamic>.from(call.arguments as Map)});
            _engineCtrl!.close(); _engineCtrl = null;
          }
          break;  // S176
      }
    });
  }

  static bool _handlerInstalled = false;  // S157: install once, routes per-call

  static Future<bool> isSetupComplete() async {
    try {
      return await _ch.invokeMethod<bool>('isSetupComplete') ?? false;
    } catch (_) { return false; }
  }

  // ── One-time setup ────────────────────────────────────────────────────────
  /// Emits {pct: int, phase: String}. Throws Exception on failure.
  static Stream<Map<String, dynamic>> runSetup() {  // S157
    final ctrl = StreamController<Map<String, dynamic>>();
    _setupCtrl = ctrl;
    if (!_handlerInstalled) { _handlerInstalled = true; _installHandler(); }
    _ch.invokeMethod('startSetup').catchError((e) {
      if (!ctrl.isClosed) { ctrl.addError(e); ctrl.close(); }
    });
    return ctrl.stream;
  }

  // ── S256: unpack-on-launch ────────────────────────────────────────────────
  // Everything the offline engine needs is inside the APK — Python, numpy,
  // scipy, the fourteen audio packages, ffmpeg, DeepFilter, the engine scripts
  // and the reference recordings. Nothing is fetched. But proot cannot execute
  // a Python that lives inside an archive, so the bundle is unpacked onto the
  // filesystem exactly once, and that unpack is the only thing standing between
  // a fresh install and a working offline engine.
  //
  // So it starts the moment the app does, rather than when the home screen
  // mounts or (worse) when someone finds a "Tap to set up" link. On a fresh
  // install that means it runs underneath the welcome tour, which is dead time
  // otherwise.
  static Stream<Map<String, dynamic>>? _prepStream;
  static bool _prepDone = false;
  static Map<String, dynamic> _prepLast = const {'pct': 0, 'phase': ''};

  /// The most recent progress event, for a screen that attaches mid-flight.
  static Map<String, dynamic> get preparationProgress => _prepLast;
  static bool get preparationFinished => _prepDone;

  /// True while the first-launch unpack is in flight. Screens that need the
  /// engine use this to tell "not set up" apart from "being set up right now",
  /// which are very different things to show someone — and to avoid offering a
  /// button that would kick off a second, competing extraction.
  static bool get preparationRunning => _prepStream != null && !_prepDone;

  /// Start the unpack if it is not already running or finished, and return a
  /// broadcast stream of its progress.
  ///
  /// Safe to call from anywhere, any number of times: the underlying
  /// `startSetup` is invoked at most once per process, because invoking it
  /// twice would run two extractions over the same directory.
  static Stream<Map<String, dynamic>> ensurePrepared() {
    if (_prepStream != null) return _prepStream!;
    final out = StreamController<Map<String, dynamic>>.broadcast();
    _prepStream = out.stream;
    () async {
      try {
        if (await isSetupComplete()) {
          _prepDone = true;
          await out.close();
          return;
        }
        runSetup().listen(
          (ev) { _prepLast = ev; if (!out.isClosed) out.add(ev); },
          onError: (e) {
            // Let the next caller retry rather than latching the failure.
            _prepStream = null;
            if (!out.isClosed) { out.addError(e); out.close(); }
          },
          onDone: () async {
            _prepDone = await isSetupComplete();
            if (!_prepDone) _prepStream = null;
            if (!out.isClosed) await out.close();
          },
        );
      } catch (e) {
        _prepStream = null;
        if (!out.isClosed) { out.addError(e); await out.close(); }
      }
    }();
    return _prepStream!;
  }

  // ── Engine run ────────────────────────────────────────────────────────────
  /// Kotlin auto-generates the output path (app cacheDir).
  static Stream<Map<String, dynamic>> runEngine({  // S157
    required String engineId,
    required String inputPath,
    bool aggressive = false,  // S173: standard / aggressive mode
  }) {
    final ctrl = StreamController<Map<String, dynamic>>();
    _engineCtrl = ctrl;  // S157: register before invokeMethod
    if (!_handlerInstalled) { _handlerInstalled = true; _installHandler(); }
    _ch.invokeMethod('runEngine', {
      'engineId':   engineId,
      'inputPath':  inputPath,
      'aggressive': aggressive,  // S173
    }).catchError((e) {
      if (!ctrl.isClosed) { ctrl.add({'error': true, 'msg': e.toString()}); ctrl.close(); }
    });
    return ctrl.stream;
  }

  static Future<void> cancelEngine() async {
    try { await _ch.invokeMethod('cancelEngine'); } catch (_) {}
    _engineCtrl?.close(); _engineCtrl = null;  // S162-B17: unblock await-for in _processLocal()
  }

  // ── S237: local-engine health + cache management ─────────────────────────

  /// Component-level status map from Kotlin computeSetupStatus():
  /// proot/python/libpython/ffmpeg/numpy/scipy/deepFilter (bool),
  /// engines/refAudio/cacheFiles (int), cacheBytes/runtimeBytes/freeBytes
  /// (int, bytes), setupDone (bool), buildId (String).
  static Future<Map<String, dynamic>> getSetupStatus() async {
    try {
      final r = await _ch.invokeMethod<Map>('getSetupStatus');
      return Map<String, dynamic>.from(r ?? {});
    } catch (_) { return {}; }
  }

  /// Deletes all tilawa_* work files from the engine cache.
  /// Returns {freedBytes: int, deletedFiles: int}.
  static Future<Map<String, dynamic>> clearEngineCache() async {
    try {
      final r = await _ch.invokeMethod<Map>('clearEngineCache');
      return Map<String, dynamic>.from(r ?? {});
    } catch (_) { return {'freedBytes': 0, 'deletedFiles': 0}; }
  }

  // S161: run an arbitrary shell command via proot (for AudioLab editor)
  // S174-B3: inputPath/outputPath trigger extra proot bind mounts so
  //          user audio files outside cacheDir are accessible inside proot.
  static Future<Map<String, dynamic>> runProotCmd(
    String cmd, {
    String inputPath  = '',  // S174-B3: adds -b bind for file's parent dir
    String outputPath = '',  // S174-B3
    int timeoutMin = 10,
  }) async {
    try {
      final r = await _ch.invokeMethod<Map>('runProotCmd', {
        'cmd':        cmd,
        'inputPath':  inputPath,
        'outputPath': outputPath,
        'timeoutMin': timeoutMin,
      });
      return Map<String, dynamic>.from(r ?? {'rc': 0, 'out': ''});
    } catch (e) {
      return {'rc': -1, 'out': e.toString()};
    }
  }
}
