import 'dart:io';
import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

class ApiService {
  static const String _base = 'https://carm5333-tilawa-server.hf.space';
  static const int _chunkSize = 8 * 1024 * 1024; // 8 MB

  // ── Media channel — calls MainActivity.kt MediaScannerConnection ───────────
  static const _mediaChannel =
      MethodChannel('com.tilawa.tilawa_enhancer/media');

  // ── Health check ──────────────────────────────────────────────────────────
  static Future<bool> isServerRunning() async {
    try {
      final res = await http
          .get(Uri.parse('$_base/'))
          .timeout(const Duration(seconds: 8));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ── Upload — auto-selects direct or chunked ────────────────────────────────
  static Future<Map<String, dynamic>> uploadFile(
    File file,
    String engine, {
    void Function(double progress, String label)? onProgress,
  }) async {
    final size = await file.length();
    if (size <= _chunkSize) {
      onProgress?.call(0.05, 'رفع الملف...');
      return _uploadDirect(file, engine);
    }
    return _uploadChunked(file, engine, size, onProgress: onProgress);
  }

  static Future<Map<String, dynamic>> _uploadDirect(
      File file, String engine) async {
    final req = http.MultipartRequest('POST', Uri.parse('$_base/upload'));
    req.files.add(await http.MultipartFile.fromPath('file', file.path));
    req.fields['engine'] = engine;
    final res = await req.send().timeout(const Duration(seconds: 60));
    return jsonDecode(await res.stream.bytesToString());
  }

  static Future<Map<String, dynamic>> _uploadChunked(
    File file,
    String engine,
    int fileSize, {
    void Function(double progress, String label)? onProgress,
  }) async {
    final totalChunks = (fileSize / _chunkSize).ceil();
    final filename = file.path.split('/').last;

    onProgress?.call(0.02, 'بدء الجلسة...');
    final startRes = await http
        .post(
          Uri.parse('$_base/upload_start'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'filename': filename,
            'total_size': fileSize,
            'total_chunks': totalChunks,
          }),
        )
        .timeout(const Duration(seconds: 15));
    final jobId =
        (jsonDecode(startRes.body) as Map)['job_id'] as String;

    final raf = await file.open(mode: FileMode.read);
    try {
      for (int i = 0; i < totalChunks; i++) {
        final offset = i * _chunkSize;
        final size =
            ((fileSize - offset) < _chunkSize) ? (fileSize - offset) : _chunkSize;
        await raf.setPosition(offset);
        final bytes = await raf.read(size);

        onProgress?.call(
          0.05 + (i / totalChunks) * 0.60,
          'رفع ${i + 1}/$totalChunks...',
        );

        for (int attempt = 0; attempt < 3; attempt++) {
          try {
            final req = http.MultipartRequest(
                'POST', Uri.parse('$_base/upload_chunk'));
            req.fields['job_id'] = jobId;
            req.fields['index'] = i.toString();
            req.files.add(http.MultipartFile.fromBytes(
              'chunk', bytes,
              filename: 'chunk_$i',
            ));
            final res = await req
                .send()
                .timeout(const Duration(seconds: 60));
            if (res.statusCode == 200) break;
          } catch (e) {
            if (attempt == 2) rethrow;
            await Future.delayed(const Duration(seconds: 2));
          }
        }
      }
    } finally {
      await raf.close();
    }

    onProgress?.call(0.68, 'دمج الأجزاء...');
    final finalRes = await http
        .post(
          Uri.parse('$_base/upload_finalize'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({'job_id': jobId, 'engine': engine}),
        )
        .timeout(const Duration(seconds: 30));
    return jsonDecode(finalRes.body);
  }

  // ── Poll status ────────────────────────────────────────────────────────────
  static Future<Map<String, dynamic>> getStatus(String jobId) async {
    final res = await http
        .get(Uri.parse('$_base/status/$jobId'))
        .timeout(const Duration(seconds: 10));
    return jsonDecode(res.body);
  }

  // ── Download ───────────────────────────────────────────────────────────────
  // STEP 1-1: Returns (File?, String?) — real error on failure, not just null
  // STEP 1-2: Streams to temp file first (always writable, no permission needed)
  // STEP 1-3: True chunk streaming — no RAM buffering, safe for 300MB files
  // STEP 1-4: Size guard — rejects empty/truncated responses early
  // STEP 1-5: Moves temp → app-external dir (visible path, no permission on API 29+)
  // STEP 1-6: Calls MediaScanner via MethodChannel → file appears in stock file managers
  // STEP 1-7: Cleans temp file after successful copy
  // STEP 1-8: catch block returns string error — UI shows real reason, not generic failure
  static Future<(File?, String?)> downloadFile(
      String jobId, String filename) async {
    final client = http.Client();
    try {
      // 1-1: Build request
      final req = http.Request('GET', Uri.parse('$_base/download/$jobId'));
      final res =
          await client.send(req).timeout(const Duration(minutes: 15));
      if (res.statusCode != 200) {
        return (null, 'خطأ HTTP ${res.statusCode}');
      }

      // 1-2 + 1-3: Stream to temp — never loads entire file into RAM
      final tempDir = await getTemporaryDirectory();
      final tempFile = File('${tempDir.path}/$filename');
      final sink = tempFile.openWrite();
      try {
        await for (final chunk in res.stream) {
          sink.add(chunk);
        }
        await sink.flush();
      } finally {
        await sink.close();
      }

      // 1-4: Size guard
      final written = await tempFile.length();
      if (written < 500) {
        await tempFile.delete();
        return (null, 'ملف فارغ: $written bytes');
      }

      // 1-5: Move to visible save directory
      final saveDir = await _getSaveDir();
      await saveDir.create(recursive: true);
      final dest = File('${saveDir.path}/$filename');
      await tempFile.copy(dest.path);

      // 1-7: Cleanup temp
      try { await tempFile.delete(); } catch (_) {}

      // 1-6: Notify Android MediaStore — makes file appear in Downloads / file managers
      await _scanFile(dest.path);

      return (dest, null);
    } catch (e) {
      // 1-8: Real error string to surface in UI
      return (null, e.toString());
    } finally {
      client.close();
    }
  }

  /// Returns the best writable directory for saving files.
  /// getExternalStorageDirectory() → /Android/data/<pkg>/files/
  /// Writable with ZERO permission on Android 10+ (app-scoped storage exemption).
  /// Visible on all Androids — Samsung My Files can reach it; also MediaStore-indexed.
  static Future<Directory> _getSaveDir() async {
    final ext = await getExternalStorageDirectory();
    if (ext != null) return ext;
    // Last-resort fallback — file exists but less discoverable
    return await getApplicationDocumentsDirectory();
  }

  /// Calls MediaScannerConnection.scanFile() on the Kotlin side.
  /// Without this, a file written via File API is INVISIBLE to all stock file
  /// managers and the Downloads section until device reboot or app reinstall.
  static Future<void> _scanFile(String path) async {
    try {
      await _mediaChannel.invokeMethod('scanFile', {'path': path});
    } catch (_) {
      // Non-fatal — file still exists on disk, just won't appear in Downloads
      // until Android indexes it on its own (reboot / app reinstall).
    }
  }

  // ── History ────────────────────────────────────────────────────────────────
  static Future<List<Map<String, dynamic>>> getHistory() async {
    try {
      final res = await http
          .get(Uri.parse('$_base/history'))
          .timeout(const Duration(seconds: 5));
      return List<Map<String, dynamic>>.from(
          jsonDecode(res.body)['jobs'] ?? []);
    } catch (_) {
      return [];
    }
  }

  // ── Build proper download filename ────────────────────────────────────────
  static String buildFilename(String engine) {
    const engineNames = {
      'v8.0': 'Calibrated_Precision',
      'v7.6': 'Intelligent_Assessment',
      'v7.5': 'Disciplined_Precision',
      'v7.0': 'Classic',
    };
    final name = engineNames[engine] ?? engine.replaceAll('.', '_');
    return 'Tilawa_${engine}_${name}_1425H.mp3';
  }
}
