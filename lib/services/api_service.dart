import 'dart:io';
import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  static const _b = 'https://carm5333-tilawa-server.hf.space';

  static Future<bool> isServerRunning() async {
    try {
      final r = await http.get(Uri.parse('$_b/')).timeout(const Duration(seconds: 6));
      return r.statusCode == 200;
    } catch (_) { return false; }
  }

  static Future<Map<String, dynamic>> uploadFile(File f, String engine) async {
    final req = http.MultipartRequest('POST', Uri.parse('$_b/upload'));
    req.files.add(await http.MultipartFile.fromPath('file', f.path));
    req.fields['engine'] = engine;
    final res = await req.send().timeout(const Duration(seconds: 60));
    return jsonDecode(await res.stream.bytesToString());
  }

  static Future<Map<String, dynamic>> getStatus(String id) async {
    final r = await http.get(Uri.parse('$_b/status/$id')).timeout(const Duration(seconds: 10));
    return jsonDecode(r.body);
  }

  static Future<File?> downloadFile(String id, String path) async {
    final r = await http.get(Uri.parse('$_b/download/$id')).timeout(const Duration(minutes: 5));
    if (r.statusCode == 200) { final f = File(path); await f.writeAsBytes(r.bodyBytes); return f; }
    return null;
  }

  static Future<List<Map<String, dynamic>>> getHistory() async {
    try {
      final r = await http.get(Uri.parse('$_b/history')).timeout(const Duration(seconds: 5));
      return List<Map<String, dynamic>>.from(jsonDecode(r.body)['jobs'] ?? []);
    } catch (_) { return []; }
  }
}
