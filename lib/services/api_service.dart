import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const String _base = 'https://carm5333-tilawa-server.hf.space';
  static const int _chunkSize = 8 * 1024 * 1024; // 8 MB

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
    final res =
        await req.send().timeout(const Duration(seconds: 60));
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

  // ── Download — true streaming, no memory limit ─────────────────────────────
  static Future<File?> downloadFile(String jobId, String savePath) async {
    final client = http.Client();
    try {
      final req = http.Request('GET', Uri.parse('$_base/download/$jobId'));
      final res =
          await client.send(req).timeout(const Duration(minutes: 15));
      if (res.statusCode != 200) return null;

      final file = File(savePath);
      final sink = file.openWrite();
      try {
        await for (final chunk in res.stream) {
          sink.add(chunk);
        }
        await sink.flush();
      } finally {
        await sink.close();
      }
      final written = await file.length();
      return written > 500 ? file : null; // guard against empty response
    } catch (_) {
      return null;
    } finally {
      client.close();
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
  /// Returns: "محسن_التلاوة_v8.0_Calibrated_Precision_1425H.mp3"
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
