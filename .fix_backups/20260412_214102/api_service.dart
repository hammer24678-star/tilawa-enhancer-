import 'dart:io';
import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  static const String _base = 'https://carm5333-tilawa-server.hf.space';
  static const int _chunkSize = 8 * 1024 * 1024;
  static const _mediaChannel = MethodChannel('com.tilawa.tilawa_enhancer/media');

  // SharedPreferences key for locally persisted job records
  static const _jobsKey = 'saved_job_records_v1';

  // ── Health check ───────────────────────────────────────────────────────────
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
    void Function(double, String)? onProgress,
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
    void Function(double, String)? onProgress,
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
    final jobId = (jsonDecode(startRes.body) as Map)['job_id'] as String;

    final raf = await file.open(mode: FileMode.read);
    try {
      for (int i = 0; i < totalChunks; i++) {
        final offset = i * _chunkSize;
        final size = ((fileSize - offset) < _chunkSize)
            ? (fileSize - offset)
            : _chunkSize;
        await raf.setPosition(offset);
        final bytes = await raf.read(size);
        onProgress?.call(0.05 + (i / totalChunks) * 0.60, 'رفع ${i + 1}/$totalChunks...');
        for (int attempt = 0; attempt < 3; attempt++) {
          try {
            final req =
                http.MultipartRequest('POST', Uri.parse('$_base/upload_chunk'));
            req.fields['job_id'] = jobId;
            req.fields['index'] = i.toString();
            req.files.add(http.MultipartFile.fromBytes('chunk', bytes,
                filename: 'chunk_$i'));
            final res = await req.send().timeout(const Duration(seconds: 60));
            // S20-D: always drain — unread streams leave sockets in CLOSE_WAIT
            await res.stream.drain<void>();
            if (res.statusCode == 200) break;
            // S20-E: non-200 = throw so retry loop or rethrow fires
            throw Exception('chunk_$i upload failed: HTTP ${res.statusCode}');
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
        .timeout(const Duration(minutes: 3)); // S20-F: was 30s — HF cold start can exceed that
    return jsonDecode(finalRes.body);
  }

  // ── Poll status ────────────────────────────────────────────────────────────
  static Future<Map<String, dynamic>> getStatus(String jobId) async {
    final res = await http
        .get(Uri.parse('$_base/status/$jobId'))
        .timeout(const Duration(seconds: 10));
    return jsonDecode(res.body);
  }

  // ── Download — true streaming, no RAM overflow ─────────────────────────────
  static Future<(File?, String?)> downloadFile(
      String jobId, String filename) async {
    final client = http.Client();
    File? tempFile;
    try {
      final req =
          http.Request('GET', Uri.parse('$_base/download/$jobId'));
      final res =
          await client.send(req).timeout(const Duration(minutes: 15));

      // S18 A21: A 404 at this point means job was cleared from the server
      if (res.statusCode == 404) {
        return (null, 'JOB_EXPIRED');
      }
      if (res.statusCode != 200) {
        return (null, 'خطأ HTTP ${res.statusCode}');
      }

      final tempDir = await getTemporaryDirectory();
      tempFile = File('${tempDir.path}/$filename');
      final sink = tempFile.openWrite();
      try {
        // S18 A21 FIX: timeout on stream body, not just headers
        await res.stream
            .timeout(const Duration(minutes: 10))
            .forEach((chunk) => sink.add(chunk));
        await sink.flush();
      } finally {
        await sink.close();
      }

      final written = await tempFile.length();
      if (written < 500) {
        try { await tempFile.delete(); } catch (_) {}
        return (null, 'ملف فارغ: $written bytes');
      }

      // RC1: Save to public Downloads via Kotlin MethodChannel
      final String? savedUri;
      try {
        savedUri = await _mediaChannel.invokeMethod<String>(
            'saveToDownloads', {'path': tempFile.path, 'filename': filename});
      } on PlatformException catch (e) {
        // Graceful fallback: keep temp file (at least user has something)
        return (tempFile, 'تحذير: حُفظ في temp (${e.message})');
      }

      if (savedUri == null) {
        return (null, 'saveToDownloads أرجع null');
      }
      try { await tempFile.delete(); } catch (_) {}
      tempFile = null;
      return (File(savedUri), null);
    } catch (e) {
      if (tempFile != null) { try { await tempFile.delete(); } catch (_) {} }
      return (null, e.toString());
    } finally {
      client.close();
    }
  }

  // ── Server history (from server, session-bound) ────────────────────────────
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

  // ── S19: Persistent local job records ─────────────────────────────────────
  // Stored in SharedPreferences so re-download survives app restarts.
  // Key format: 'saved_job_records_v1' → JSON array of job maps.

  /// Save a completed job locally so it can be re-downloaded later.
  static Future<void> saveJobRecord({
    required String jobId,
    required String engine,
    required double score,
    required String filename,
    Map<String, dynamic>? metrics,
  }) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final existing = await getSavedJobRecords();

      // Deduplicate: remove old entry for this jobId if present
      existing.removeWhere((j) => j['job_id'] == jobId);

      final record = {
        'job_id': jobId,
        'engine': engine,
        'score': score,
        'filename': filename,
        'timestamp': DateTime.now().toIso8601String(),
        if (metrics?['lufs']  != null) 'lufs':  metrics!['lufs'].toString(),
        if (metrics?['rms']   != null) 'rms':   metrics!['rms'].toString(),
        if (metrics?['crest'] != null) 'crest': metrics!['crest'].toString(),
        if (metrics?['lra']   != null) 'lra':   metrics!['lra'].toString(),
      };

      // Insert newest first, cap at 50 entries
      existing.insert(0, record);
      if (existing.length > 50) existing.removeRange(50, existing.length);

      final jsonList = existing.map(jsonEncode).toList();
      await prefs.setStringList(_jobsKey, jsonList);
    } catch (_) {
      // Persistence is best-effort; never crash on a prefs failure
    }
  }

  /// Load all locally saved job records (newest first).
  static Future<List<Map<String, dynamic>>> getSavedJobRecords() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getStringList(_jobsKey) ?? [];
      return raw
          .map((s) => Map<String, dynamic>.from(jsonDecode(s) as Map))
          .toList();
    } catch (_) {
      return [];
    }
  }

  /// Remove a single job record (e.g. after user confirms it's expired).
  static Future<void> removeJobRecord(String jobId) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final existing = await getSavedJobRecords();
      existing.removeWhere((j) => j['job_id'] == jobId);
      final jsonList = existing.map(jsonEncode).toList();
      await prefs.setStringList(_jobsKey, jsonList);
    } catch (_) {}
  }

  // ── Build proper download filename ─────────────────────────────────────────
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
