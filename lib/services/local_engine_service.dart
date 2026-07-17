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

  // ── Setup check ──────────────────────────────────────────────────────────

  // S157: active controllers — handler routes to whichever is open
  static StreamController<Map<String, dynamic>>? _setupCtrl;
  static StreamController<Map<String, dynamic>>? _engineCtrl;

  static void _installHandler() {
    _ch.setMethodCallHandler((call) async {
      switch (call.method) {
        // Setup events
        case 'setupProgress':
          if (_setupCtrl != null && !_setupCtrl!.isClosed)
            _setupCtrl!.add(Map<String, dynamic>.from(call.arguments as Map));
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
          if (_engineCtrl != null && !_engineCtrl!.isClosed)
            _engineCtrl!.add({'pct': -1,
              ...Map<String, dynamic>.from(call.arguments as Map)});
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
