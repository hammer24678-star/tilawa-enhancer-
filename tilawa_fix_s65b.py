#!/usr/bin/env python3
"""tilawa_fix_s65b — correct anchors for remaining 10 failing fixes"""
from pathlib import Path
from datetime import datetime

API = Path.home() / 'tilawa-enhancer/lib/services/api_service.dart'
_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX',l))
def rep(old, new, lbl):
    txt = API.read_text(encoding='utf-8')
    if old in txt: API.write_text(txt.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else: xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s65b  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# Fix-3: checkServer
rep(
    "  static Future<int?> checkServer() async {\n"
    "    try {\n"
    "      final t0 = DateTime.now().millisecondsSinceEpoch;\n"
    "      final res = await http\n"
    "          .get(Uri.parse('$_base/'))\n"
    "          .timeout(const Duration(seconds: 8));\n"
    "      if (res.statusCode == 200) {\n"
    "        return DateTime.now().millisecondsSinceEpoch - t0;\n"
    "      }\n"
    "      return null;\n"
    "    } catch (_) {\n"
    "      return null;\n"
    "    }\n"
    "  }",

    "  static Future<int?> checkServer() async {\n"
    "    // S65: refresh both servers, return best latency\n"
    "    await Future.wait(_servers.map(_refreshHealth));\n"
    "    int? best;\n"
    "    for (final h in _health.values) {\n"
    "      final lat = h['latency'] as int?;\n"
    "      if (lat != null && lat < 9000 && (best == null || lat < best)) best = lat;\n"
    "    }\n"
    "    return best;\n"
    "  }",
    'Fix-3 checkServer')

# Fix pingServer
rep(
    "  static Future<void> pingServer() async {\n"
    "    try {\n"
    "      await http.get(Uri.parse('$_base/')).timeout(const Duration(seconds: 8));\n"
    "    } catch (_) {}\n"
    "  }",

    "  static Future<void> pingServer() async {\n"
    "    try {\n"
    "      final url = await _bestServer();\n"
    "      await http.get(Uri.parse('$url/ping')).timeout(const Duration(seconds: 8));\n"
    "    } catch (_) {}\n"
    "  }",
    'Fix-3b pingServer uses best server')

# Fix-4: uploadFile
rep(
    "  static Future<Map<String, dynamic>> uploadFile(\n"
    "    File file,\n"
    "    String engine, {\n"
    "    void Function(double, String)? onProgress,\n"
    "  }) async {\n"
    "    final size = await file.length();\n"
    "    if (size <= _chunkSize) {\n"
    "      onProgress?.call(0.05, 'رفع الملف...');\n"
    "      return _uploadDirect(file, engine);\n"
    "    }\n"
    "    return _uploadChunked(file, engine, size, onProgress: onProgress);\n"
    "  }",

    "  static Future<Map<String, dynamic>> uploadFile(\n"
    "    File file,\n"
    "    String engine, {\n"
    "    void Function(double, String)? onProgress,\n"
    "  }) async {\n"
    "    final size = await file.length();\n"
    "    await Future.wait(_servers.map(_refreshHealth));\n"
    "    final server = await _bestServer();\n"
    "    onProgress?.call(0.01, 'اختيار الخادم الأمثل...');\n"
    "    // S65: small files (<5MB) get priority direct upload\n"
    "    if (size <= 5 * 1024 * 1024) {\n"
    "      return _uploadDirectTo(file, engine, server);\n"
    "    }\n"
    "    try {\n"
    "      return await _uploadChunkedTo(file, engine, size, server, onProgress: onProgress);\n"
    "    } catch (_) {\n"
    "      // S65: auto-retry on alternate server\n"
    "      final alt = _servers.firstWhere((s) => s != server, orElse: () => server);\n"
    "      if (alt == server) rethrow;\n"
    "      onProgress?.call(0, 'تحويل إلى خادم احتياطي...');\n"
    "      return await _uploadChunkedTo(file, engine, size, alt, onProgress: onProgress);\n"
    "    }\n"
    "  }",
    'Fix-4 uploadFile')

# Fix-5: _uploadDirect
rep(
    "  static Future<Map<String, dynamic>> _uploadDirect(\n"
    "      File file, String engine) async {\n"
    "    // S25-DART5: retry wrapper (was fire-and-forget)\n"
    "    for (int attempt = 0; attempt < 3; attempt++) {\n"
    "      try {\n"
    "        final req = http.MultipartRequest('POST', Uri.parse('$_base/upload'));",

    "  static Future<Map<String, dynamic>> _uploadDirectTo(\n"
    "      File file, String engine, String server) async {\n"
    "    // S25-DART5: retry wrapper (was fire-and-forget)\n"
    "    for (int attempt = 0; attempt < 3; attempt++) {\n"
    "      try {\n"
    "        final req = http.MultipartRequest('POST', Uri.parse('$server/upload'));",
    'Fix-5 _uploadDirectTo with server param')

# Fix-6: _uploadChunked
rep(
    "  static Future<Map<String, dynamic>> _uploadChunked(\n"
    "    File file,\n"
    "    String engine,\n"
    "    int fileSize, {\n"
    "    void Function(double, String)? onProgress,\n"
    "  }) async {",

    "  static Future<Map<String, dynamic>> _uploadChunkedTo(\n"
    "    File file,\n"
    "    String engine,\n"
    "    int fileSize,\n"
    "    String server, {\n"
    "    void Function(double, String)? onProgress,\n"
    "  }) async {",
    'Fix-6 _uploadChunkedTo with server param')

rep(
    "    final startRes = await http\n"
    "        .post(\n"
    "          Uri.parse('$_base/upload_start'),",
    "    final startRes = await http\n"
    "        .post(\n"
    "          Uri.parse('$server/upload_start'),",
    'Fix-6b upload_start')

rep(
    "          Uri.parse('$_base/upload_chunk'),",
    "          Uri.parse('$server/upload_chunk'),",
    'Fix-6c upload_chunk')

rep(
    "    final finRes = await http.post(\n"
    "        Uri.parse('$_base/upload_finalize'),",
    "    final finRes = await http.post(\n"
    "        Uri.parse('$server/upload_finalize'),",
    'Fix-6d upload_finalize')

# Fix status endpoint — uses _servers[0] as stable base for job polling
rep(
    "      final res = await http\n"
    "          .get(Uri.parse('$_base/status/$jobId'))",
    "      final res = await http\n"
    "          .get(Uri.parse('${_servers[0]}/status/$jobId'))",
    'Fix-6e status endpoint')

rep(
    "      'download_url': '$_base/download/$jobId',",
    "      'download_url': '${_servers[0]}/download/$jobId',",
    'Fix-6f download_url')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S65: complete multi-server LB -- health scoring, auto-retry, priority upload" && git push\n')
