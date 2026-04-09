import 'dart:convert';
import 'package:http/http.dart' as http;

class ApiService {
  ApiService._();

  static const String baseUrl = 'http://127.0.0.1:5000';

  static Uri _uri(String path) => Uri.parse('$baseUrl$path');

  static Future<Map<String, dynamic>> getStatus() async {
    final res = await http.get(_uri('/')).timeout(
      const Duration(seconds: 5),
    );
    if (res.statusCode != 200) {
      throw Exception('Server health check failed: ${res.statusCode}');
    }
    return {'ok': true};
  }

  static Future<Map<String, dynamic>> uploadAudio({
    required List<int> bytes,
    required String filename,
    String engine = 'v7.5',
  }) async {
    final request = http.MultipartRequest('POST', _uri('/upload'));
    request.fields['engine'] = engine;
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        bytes,
        filename: filename,
      ),
    );

    final streamed = await request.send().timeout(
      const Duration(seconds: 60),
    );

    final body = await streamed.stream.bytesToString();
    if (streamed.statusCode != 200) {
      throw Exception('Upload failed: ${streamed.statusCode} $body');
    }

    return jsonDecode(body) as Map<String, dynamic>;
  }

  static Future<Map<String, dynamic>> getJobStatus(String jobId) async {
    final res = await http.get(_uri('/status/$jobId')).timeout(
      const Duration(seconds: 10),
    );
    if (res.statusCode != 200) {
      throw Exception('Status failed: ${res.statusCode}');
    }
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  static Future<List<int>> downloadResult(String jobId) async {
    final res = await http.get(_uri('/download/$jobId')).timeout(
      const Duration(seconds: 60),
    );
    if (res.statusCode != 200) {
      throw Exception('Download failed: ${res.statusCode}');
    }
    return res.bodyBytes;
  }

  static Future<List<dynamic>> getHistory() async {
    final res = await http.get(_uri('/history')).timeout(
      const Duration(seconds: 10),
    );
    if (res.statusCode != 200) {
      throw Exception('History failed: ${res.statusCode}');
    }
    final data = jsonDecode(res.body);
    if (data is Map && data['jobs'] is List) {
      return data['jobs'] as List<dynamic>;
    }
    return const [];
  }
}
