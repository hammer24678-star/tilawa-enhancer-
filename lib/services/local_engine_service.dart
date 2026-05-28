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

  static Future<bool> isSetupComplete() async {
    try {
      return await _ch.invokeMethod<bool>('isSetupComplete') ?? false;
    } catch (_) { return false; }
  }

  // ── One-time setup ────────────────────────────────────────────────────────
  /// Emits {pct: int, phase: String}. Throws Exception on failure.
  static Stream<Map<String, dynamic>> runSetup() {
    final ctrl = StreamController<Map<String, dynamic>>();
    _ch.setMethodCallHandler((call) async {
      if (ctrl.isClosed) return;
      switch (call.method) {
        case 'setupProgress':
          ctrl.add(Map<String, dynamic>.from(call.arguments as Map));
        case 'setupDone':
          ctrl.close();
        case 'setupError':
          ctrl.addError(Exception(
            ((call.arguments as Map?)?['msg'] as String?) ?? 'Setup failed'));
          ctrl.close();
      }
    });
    _ch.invokeMethod('startSetup').catchError((e) {
      if (!ctrl.isClosed) { ctrl.addError(e); ctrl.close(); }
    });
    return ctrl.stream;
  }

  // ── Engine run ────────────────────────────────────────────────────────────
  /// Kotlin auto-generates the output path (app cacheDir).
  static Stream<Map<String, dynamic>> runEngine({
    required String engineId,
    required String inputPath,
  }) {
    final ctrl = StreamController<Map<String, dynamic>>();
    _ch.setMethodCallHandler((call) async {
      if (ctrl.isClosed) return;
      switch (call.method) {
        case 'engineProgress':
          ctrl.add({'pct': -1,
            ...Map<String, dynamic>.from(call.arguments as Map)});
        case 'engineDone':
          ctrl.add({'done': true,
            ...Map<String, dynamic>.from(call.arguments as Map)});
          ctrl.close();
        case 'engineError':
          ctrl.add({'error': true,
            ...Map<String, dynamic>.from(call.arguments as Map)});
          ctrl.close();
      }
    });
    _ch.invokeMethod('runEngine', {
      'engineId':  engineId,
      'inputPath': inputPath,
    }).catchError((e) {
      if (!ctrl.isClosed) { ctrl.add({'error': true, 'msg': e.toString()}); ctrl.close(); }
    });
    return ctrl.stream;
  }

  static Future<void> cancelEngine() async {
    try { await _ch.invokeMethod('cancelEngine'); } catch (_) {}
  }

  static Future<void> scanFile(String path) async {
    try { await _ch.invokeMethod('scanFile', {'path': path}); } catch (_) {}
  }
}
