import 'dart:io';
import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

class ApiService {
  static const String _base = 'https://carm5333-tilawa-server.hf.space';
  static const int _chunkSize = 8 * 1024 * 1024;
  static const _mediaChannel = MethodChannel('com.tilawa.tilawa_enhancer/media');

  static Future<bool> isServerRunning() async {
    try {
      final res = await http.get(Uri.parse('$_base/')).timeout(const Duration(seconds: 8));
      return res.statusCode == 200;
    } catch (_) { return false; }
  }

  static Future<Map<String, dynamic>> uploadFile(File file, String engine,
      {void Function(double, String)? onProgress}) async {
    final size = await file.length();
    if (size <= _chunkSize) {
      onProgress?.call(0.05, '\u0631\u0641\u0639 \u0627\u0644\u0645\u0644\u0641...');
      return _uploadDirect(file, engine);
    }
    return _uploadChunked(file, engine, size, onProgress: onProgress);
  }

  static Future<Map<String, dynamic>> _uploadDirect(File file, String engine) async {
    final req = http.MultipartRequest('POST', Uri.parse('$_base/upload'));
    req.files.add(await http.MultipartFile.fromPath('file', file.path));
    req.fields['engine'] = engine;
    final res = await req.send().timeout(const Duration(seconds: 60));
    return jsonDecode(await res.stream.bytesToString());
  }

  static Future<Map<String, dynamic>> _uploadChunked(File file, String engine, int fileSize,
      {void Function(double, String)? onProgress}) async {
    final totalChunks = (fileSize / _chunkSize).ceil();
    final filename = file.path.split('/').last;
    onProgress?.call(0.02, '\u0628\u062f\u0621 \u0627\u0644\u062c\u0644\u0633\u0629...');
    final startRes = await http.post(Uri.parse('$_base/upload_start'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'filename': filename, 'total_size': fileSize, 'total_chunks': totalChunks}))
        .timeout(const Duration(seconds: 15));
    final jobId = (jsonDecode(startRes.body) as Map)['job_id'] as String;
    final raf = await file.open(mode: FileMode.read);
    try {
      for (int i = 0; i < totalChunks; i++) {
        final offset = i * _chunkSize;
        final size = ((fileSize - offset) < _chunkSize) ? (fileSize - offset) : _chunkSize;
        await raf.setPosition(offset);
        final bytes = await raf.read(size);
        onProgress?.call(0.05 + (i / totalChunks) * 0.60, '\u0631\u0641\u0639 ${i+1}/$totalChunks...');
        for (int attempt = 0; attempt < 3; attempt++) {
          try {
            final req = http.MultipartRequest('POST', Uri.parse('$_base/upload_chunk'));
            req.fields['job_id'] = jobId;
            req.fields['index'] = i.toString();
            req.files.add(http.MultipartFile.fromBytes('chunk', bytes, filename: 'chunk_$i'));
            final res = await req.send().timeout(const Duration(seconds: 60));
            if (res.statusCode == 200) break;
          } catch (e) {
            if (attempt == 2) rethrow;
            await Future.delayed(const Duration(seconds: 2));
          }
        }
      }
    } finally { await raf.close(); }
    onProgress?.call(0.68, '\u062f\u0645\u062c \u0627\u0644\u0623\u062c\u0632\u0627\u0621...');
    final finalRes = await http.post(Uri.parse('$_base/upload_finalize'),
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({'job_id': jobId, 'engine': engine}))
        .timeout(const Duration(seconds: 30));
    return jsonDecode(finalRes.body);
  }

  static Future<Map<String, dynamic>> getStatus(String jobId) async {
    final res = await http.get(Uri.parse('$_base/status/$jobId')).timeout(const Duration(seconds: 10));
    return jsonDecode(res.body);
  }

  static Future<(File?, String?)> downloadFile(String jobId, String filename) async {
    final client = http.Client();
    File? tempFile;
    try {
      final req = http.Request('GET', Uri.parse('$_base/download/$jobId'));
      final res = await client.send(req).timeout(const Duration(minutes: 15));
      if (res.statusCode != 200) return (null, '\u062e\u0637\u0623 HTTP ${res.statusCode}');
      final tempDir = await getTemporaryDirectory();
      tempFile = File('${tempDir.path}/$filename');
      final sink = tempFile.openWrite();
      try {
        await res.stream.timeout(const Duration(minutes: 10)).forEach((chunk) => sink.add(chunk));
        await sink.flush();
      } finally { await sink.close(); }
      final written = await tempFile.length();
      if (written < 500) {
        try { await tempFile.delete(); } catch (_) {}
        return (null, '\u0645\u0644\u0641 \u0641\u0627\u0631\u063a: $written bytes');
      }
      final String? savedUri;
      try {
        savedUri = await _mediaChannel.invokeMethod<String>(
            'saveToDownloads', {'path': tempFile.path, 'filename': filename});
      } on PlatformException catch (e) {
        return (tempFile, '\u062a\u062d\u0630\u064a\u0631: \u062d\u064f\u0641\u0638 \u0641\u064a temp (${e.message})');
      }
      if (savedUri == null) return (null, 'saveToDownloads \u0623\u0631\u062c\u0639 null');
      try { await tempFile.delete(); } catch (_) {}
      tempFile = null;
      return (File(savedUri), null);
    } catch (e) {
      if (tempFile != null) { try { await tempFile.delete(); } catch (_) {} }
      return (null, e.toString());
    } finally { client.close(); }
  }

  static Future<List<Map<String, dynamic>>> getHistory() async {
    try {
      final res = await http.get(Uri.parse('$_base/history')).timeout(const Duration(seconds: 5));
      return List<Map<String, dynamic>>.from(jsonDecode(res.body)['jobs'] ?? []);
    } catch (_) { return []; }
  }

  static String buildFilename(String engine) {
    const engineNames = {
      'v8.0': 'Calibrated_Precision', 'v7.6': 'Intelligent_Assessment',
      'v7.5': 'Disciplined_Precision', 'v7.0': 'Classic',
    };
    final name = engineNames[engine] ?? engine.replaceAll('.', '_');
    return 'Tilawa_${engine}_${name}_1425H.mp3';
  }
}
