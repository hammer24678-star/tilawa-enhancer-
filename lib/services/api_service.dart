import 'dart:io';
import 'dart:convert';
import 'dart:typed_data';
import 'package:http/http.dart' as http;

class ApiService {
  static const String _base = 'https://carm5333-tilawa-server.hf.space';

  // ── Chunk size: 8MB (safe under HF 12MB limit) ─────────────────────────────
  static const int _chunkSize = 8 * 1024 * 1024;

  // ── Server health check ─────────────────────────────────────────────────────
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

  // ── Upload file — auto-detects size and uses chunked if >8MB ───────────────
  static Future<Map<String, dynamic>> uploadFile(
    File file,
    String engine, {
    void Function(double progress, String label)? onProgress,
  }) async {
    final fileSize = await file.length();

    if (fileSize <= _chunkSize) {
      // Small file — direct upload
      onProgress?.call(0.05, 'جارٍ الرفع...');
      return _uploadDirect(file, engine);
    } else {
      // Large file — chunked upload
      return _uploadChunked(file, engine, fileSize, onProgress: onProgress);
    }
  }

  // ── Direct upload (files ≤ 8MB) ─────────────────────────────────────────────
  static Future<Map<String, dynamic>> _uploadDirect(
      File file, String engine) async {
    final uri = Uri.parse('$_base/upload');
    final req = http.MultipartRequest('POST', uri);
    req.files.add(await http.MultipartFile.fromPath('file', file.path));
    req.fields['engine'] = engine;
    final res = await req.send().timeout(const Duration(seconds: 60));
    return jsonDecode(await res.stream.bytesToString());
  }

  // ── Chunked upload (files > 8MB, up to 300MB) ───────────────────────────────
  static Future<Map<String, dynamic>> _uploadChunked(
    File file,
    String engine,
    int fileSize, {
    void Function(double progress, String label)? onProgress,
  }) async {
    final totalChunks = (fileSize / _chunkSize).ceil();
    final filename = file.path.split('/').last;

    // Step 1: Start session
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

    final startData = jsonDecode(startRes.body);
    final jobId = startData['job_id'] as String;

    // Step 2: Upload chunks
    final raf = await file.open(mode: FileMode.read);
    try {
      for (int i = 0; i < totalChunks; i++) {
        final offset = i * _chunkSize;
        final remaining = fileSize - offset;
        final size = remaining < _chunkSize ? remaining : _chunkSize;

        await raf.setPosition(offset);
        final bytes = await raf.read(size);

        final chunkProgress = 0.05 + (i / totalChunks) * 0.60;
        onProgress?.call(
          chunkProgress,
          'رفع الجزء ${i + 1}/$totalChunks...',
        );

        // Retry up to 3 times per chunk
        bool sent = false;
        for (int attempt = 0; attempt < 3 && !sent; attempt++) {
          try {
            final req = http.MultipartRequest(
                'POST', Uri.parse('$_base/upload_chunk'));
            req.fields['job_id'] = jobId;
            req.fields['index'] = i.toString();
            req.files.add(http.MultipartFile.fromBytes(
              'chunk',
              bytes,
              filename: 'chunk_$i',
            ));
            final res = await req
                .send()
                .timeout(const Duration(seconds: 60));
            if (res.statusCode == 200) {
              sent = true;
            }
          } catch (e) {
            if (attempt == 2) rethrow;
            await Future.delayed(const Duration(seconds: 2));
          }
        }
      }
    } finally {
      await raf.close();
    }

    // Step 3: Finalize
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

  // ── Poll status ──────────────────────────────────────────────────────────────
  static Future<Map<String, dynamic>> getStatus(String jobId) async {
    final res = await http
        .get(Uri.parse('$_base/status/$jobId'))
        .timeout(const Duration(seconds: 10));
    return jsonDecode(res.body);
  }

  // ── Download output — streaming for large files ──────────────────────────────
  static Future<File?> downloadFile(String jobId, String savePath) async {
    final uri = Uri.parse('$_base/download/$jobId');
    final client = http.Client();
    try {
      final req = http.Request('GET', uri);
      final streamedRes =
          await client.send(req).timeout(const Duration(minutes: 10));

      if (streamedRes.statusCode == 200) {
        final file = File(savePath);
        final sink = file.openWrite();
        await streamedRes.stream.pipe(sink);
        await sink.close();
        return file;
      }
      return null;
    } finally {
      client.close();
    }
  }

  // ── History ──────────────────────────────────────────────────────────────────
  static Future<List<Map<String, dynamic>>> getHistory() async {
    try {
      final res = await http
          .get(Uri.parse('$_base/history'))
          .timeout(const Duration(seconds: 5));
      final data = jsonDecode(res.body);
      return List<Map<String, dynamic>>.from(data['jobs'] ?? []);
    } catch (_) {
      return [];
    }
  }
}
