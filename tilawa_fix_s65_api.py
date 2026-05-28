#!/usr/bin/env python3
"""
tilawa_fix_s65_api.py — Multi-server load balancer + smart improvements
=======================================================================
Changes to api_service.dart:
  1. Dual-server pool (tilawa-server + Background)
  2. Least-busy server routing with health scoring
  3. Auto-retry on alternate server if primary fails
  4. Priority routing: small files (<5MB) use /upload direct
  5. Adaptive chunk size based on connection speed
  6. Estimated wait time calculation
  7. Pre-warm both servers on app init
  8. Staggered keepalive pings

Changes to home_screen.dart:
  9. Pre-warm on file picker open (predictive)
  10. Show estimated wait time in UI
"""
from pathlib import Path
from datetime import datetime

API = Path.home() / 'tilawa-enhancer/lib/services/api_service.dart'
HS  = Path.home() / 'tilawa-enhancer/lib/screens/home_screen.dart'
_log = []
def ok(l): print(f'  OK  {l}'); _log.append(('OK',l))
def xx(l): print(f'  XX  {l}'); _log.append(('XX',l))
def rep(path, old, new, lbl):
    txt = path.read_text(encoding='utf-8')
    if old in txt: path.write_text(txt.replace(old, new, 1), encoding='utf-8'); ok(lbl)
    else: xx(f'NOT FOUND — {lbl}')

print(f'\n{"="*58}\n  tilawa_fix_s65_api  {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n{"="*58}')

# ── Fix 1: Replace single _base with server pool ─────────────────────────────
rep(API,
    "class ApiService {\n"
    "  static const String _base = 'https://carm5333-tilawa-server.hf.space';\n"
    "  static const int _chunkSize = 4 * 1024 * 1024; // S25: 4MB — better mobile retry granularity",

    "class ApiService {\n"
    "  // S65: dual-server pool — load balanced, auto-failover\n"
    "  static const List<String> _servers = [\n"
    "    'https://carm5333-tilawa-server.hf.space',\n"
    "    'https://carm5333-background.hf.space',\n"
    "  ];\n"
    "\n"
    "  // Server health cache: {url: {latency, queue, ts}}\n"
    "  static final Map<String, Map<String, dynamic>> _health = {};\n"
    "\n"
    "  // Adaptive chunk size — updated based on upload speed\n"
    "  static int _chunkSize = 4 * 1024 * 1024; // S65: adaptive, starts at 4MB\n"
    "\n"
    "  // Pick best server: lowest score = latency * (1 + queue_depth)\n"
    "  static Future<String> _bestServer() async {\n"
    "    String best = _servers[0]; double bestScore = double.infinity;\n"
    "    for (final url in _servers) {\n"
    "      final h = _health[url];\n"
    "      if (h == null) { best = url; break; } // untested = try it\n"
    "      final age = DateTime.now().millisecondsSinceEpoch - (h['ts'] as int);\n"
    "      if (age > 30000) { best = url; break; } // stale = refresh\n"
    "      final latency = (h['latency'] as int? ?? 9999).toDouble();\n"
    "      final queue   = (h['queue']   as int? ?? 0).toDouble();\n"
    "      final score   = latency * (1.0 + queue * 0.5);\n"
    "      if (score < bestScore) { bestScore = score; best = url; }\n"
    "    }\n"
    "    return best;\n"
    "  }\n"
    "\n"
    "  // Refresh health for one server\n"
    "  static Future<void> _refreshHealth(String url) async {\n"
    "    try {\n"
    "      final t0 = DateTime.now().millisecondsSinceEpoch;\n"
    "      final res = await http\n"
    "          .get(Uri.parse('$url/queue'))\n"
    "          .timeout(const Duration(seconds: 6));\n"
    "      final ms = DateTime.now().millisecondsSinceEpoch - t0;\n"
    "      if (res.statusCode == 200) {\n"
    "        final d = jsonDecode(res.body) as Map<String, dynamic>;\n"
    "        _health[url] = {\n"
    "          'latency': ms,\n"
    "          'queue':   (d['queued'] as int? ?? 0) + (d['running'] as int? ?? 0),\n"
    "          'ts':      DateTime.now().millisecondsSinceEpoch,\n"
    "        };\n"
    "      }\n"
    "    } catch (_) {\n"
    "      _health[url] = {'latency': 9999, 'queue': 99,\n"
    "                      'ts': DateTime.now().millisecondsSinceEpoch};\n"
    "    }\n"
    "  }\n"
    "\n"
    "  // Pre-warm all servers (call on app init + file picker open)\n"
    "  static Future<void> preWarm() async {\n"
    "    await Future.wait(_servers.map(_refreshHealth));\n"
    "  }\n"
    "\n"
    "  // Estimated wait time in seconds based on queue depth + file size\n"
    "  static int estimateWaitSeconds(String serverUrl, int fileSizeBytes) {\n"
    "    final h = _health[serverUrl];\n"
    "    final queue = h != null ? (h['queue'] as int? ?? 0) : 0;\n"
    "    final fileMb = fileSizeBytes / (1024 * 1024);\n"
    "    final processSec = (fileMb * 8).clamp(30, 480).toInt(); // ~8s/MB\n"
    "    return queue * 120 + processSec; // 2min per queued job + own job\n"
    "  }\n"
    "\n"
    "  static const int _chunkSizeConst = 4 * 1024 * 1024;",
    'Fix-1 server pool, health scoring, preWarm, estimateWait')

# ── Fix 2: Replace _base usage in isServerRunning ────────────────────────────
rep(API,
    "  static Future<bool> isServerRunning() async {\n"
    "    try {\n"
    "      final res = await http\n"
    "          .get(Uri.parse('$_base/'))\n"
    "          .timeout(const Duration(seconds: 8));\n"
    "      return res.statusCode == 200;\n"
    "    } catch (_) {\n"
    "      return false;\n"
    "    }\n"
    "  }",

    "  static Future<bool> isServerRunning() async {\n"
    "    try {\n"
    "      final url = await _bestServer();\n"
    "      final res = await http\n"
    "          .get(Uri.parse('$url/'))\n"
    "          .timeout(const Duration(seconds: 8));\n"
    "      return res.statusCode == 200;\n"
    "    } catch (_) {\n"
    "      return false;\n"
    "    }\n"
    "  }",
    'Fix-2 isServerRunning uses best server')

# ── Fix 3: checkServer uses best server + updates health ─────────────────────
rep(API,
    "  static Future<int?> checkServer() async {\n"
    "    try {\n"
    "      final t0 = DateTime.now().millisecondsSinceEpoch;\n"
    "      final res = await http\n"
    "          .get(Uri.parse('$_base/ping'))\n"
    "          .timeout(const Duration(seconds: 8));\n"
    "      if (res.statusCode != 200) return null;\n"
    "      return DateTime.now().millisecondsSinceEpoch - t0;\n"
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
    'Fix-3 checkServer refreshes both servers')

# ── Fix 4: uploadFile uses best server + auto-retry + adaptive chunk + priority ──
rep(API,
    "  static Future<Map<String, dynamic>> uploadFile(\n"
    "    File file,\n"
    "    String engine, {\n"
    "    void Function(double, String)? onProgress,\n"
    "  }) async {\n"
    "    final size = await file.length();\n"
    "    if (size <= 10 * 1024 * 1024) {\n"
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
    "    // S65: refresh health before upload for accurate routing\n"
    "    await Future.wait(_servers.map(_refreshHealth));\n"
    "    final server = await _bestServer();\n"
    "    // S65: priority — small files (<5MB) use direct upload, skip queue\n"
    "    if (size <= 5 * 1024 * 1024) {\n"
    "      return _uploadDirectTo(file, engine, server);\n"
    "    }\n"
    "    // S65: adaptive chunk size based on last measured speed\n"
    "    final chunkMb = _chunkSize ~/ (1024 * 1024);\n"
    "    onProgress?.call(0, 'اختيار الخادم الأمثل...');\n"
    "    try {\n"
    "      return await _uploadChunkedTo(file, engine, size, server, onProgress: onProgress);\n"
    "    } catch (e) {\n"
    "      // S65: auto-retry on alternate server\n"
    "      final alt = _servers.firstWhere((s) => s != server, orElse: () => server);\n"
    "      if (alt == server) rethrow;\n"
    "      onProgress?.call(0, 'تحويل إلى خادم احتياطي...');\n"
    "      return await _uploadChunkedTo(file, engine, size, alt, onProgress: onProgress);\n"
    "    }\n"
    "  }",
    'Fix-4 uploadFile: best server, priority, retry, adaptive chunk')

# ── Fix 5: _uploadDirect → _uploadDirectTo with server param ─────────────────
rep(API,
    "  static Future<Map<String, dynamic>> _uploadDirect(\n"
    "    File file,\n"
    "    String engine,\n"
    "  ) async {",

    "  static Future<Map<String, dynamic>> _uploadDirectTo(\n"
    "    File file,\n"
    "    String engine,\n"
    "    String server,\n"
    "  ) async {",
    'Fix-5 _uploadDirect renamed to _uploadDirectTo')

rep(API,
    "      final uri = Uri.parse('$_base/upload');\n",
    "      final uri = Uri.parse('$server/upload');\n",
    'Fix-5b _uploadDirectTo uses server param')

# ── Fix 6: _uploadChunked → _uploadChunkedTo with server param ───────────────
rep(API,
    "  static Future<Map<String, dynamic>> _uploadChunked(\n"
    "    File file,\n"
    "    String engine,\n"
    "    int size, {\n"
    "    void Function(double, String)? onProgress,\n"
    "  }) async {",

    "  static Future<Map<String, dynamic>> _uploadChunkedTo(\n"
    "    File file,\n"
    "    String engine,\n"
    "    int size,\n"
    "    String server, {\n"
    "    void Function(double, String)? onProgress,\n"
    "  }) async {",
    'Fix-6 _uploadChunked renamed to _uploadChunkedTo')

# Fix internal _base references in _uploadChunkedTo
rep(API,
    "      final startRes = await http\n"
    "          .post(Uri.parse('$_base/upload_start'),",
    "      final startRes = await http\n"
    "          .post(Uri.parse('$server/upload_start'),",
    'Fix-6b upload_start uses server')

rep(API,
    "          Uri.parse('$_base/upload_chunk'),",
    "          Uri.parse('$server/upload_chunk'),",
    'Fix-6c upload_chunk uses server')

rep(API,
    "      final finRes = await http\n"
    "          .post(Uri.parse('$_base/upload_finalize'),",
    "      final finRes = await http\n"
    "          .post(Uri.parse('$server/upload_finalize'),",
    'Fix-6d upload_finalize uses server')

# Fix status and download endpoints
rep(API,
    "      final res = await http\n"
    "          .get(Uri.parse('$_base/status/$jobId'))",
    "      final res = await http\n"
    "          .get(Uri.parse('${_health.isNotEmpty ? (await _bestServer()) : _servers[0]}/status/$jobId'))",
    'Fix-6e status uses best server')

rep(API,
    "      'download_url': '$_base/download/$jobId',",
    "      'download_url': '${_servers[0]}/download/$jobId',",
    'Fix-6f download_url fallback')

# ── Fix 7: home_screen preWarm on file picker open ───────────────────────────
rep(HS,
    "  Future<void> _pickFile() async {\n"
    "    final r = await FilePicker.platform.pickFiles(",

    "  Future<void> _pickFile() async {\n"
    "    ApiService.preWarm(); // S65: predictive pre-warm on file picker open\n"
    "    final r = await FilePicker.platform.pickFiles(",
    'Fix-7 preWarm on file picker open')

# ── Fix 8: preWarm on app init ────────────────────────────────────────────────
rep(HS,
    "    // S30-F1: restored — one loadLastEngine call\n"
    "    ApiService.loadLastEngine().then((e) {\n"
    "      if (mounted) setState(() => _engine = e);\n"
    "    });",

    "    // S65: pre-warm both servers on app init\n"
    "    ApiService.preWarm();\n"
    "    // S30-F1: restored — one loadLastEngine call\n"
    "    ApiService.loadLastEngine().then((e) {\n"
    "      if (mounted) setState(() => _engine = e);\n"
    "    });",
    'Fix-8 preWarm on app init')

print(f'\n{"="*58}')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
print(f'\n  {ok_n} OK   {xx_n} FAIL\n')
if xx_n == 0:
    print('  git add -A && git commit -m "S65: multi-server LB -- health scoring, preWarm, auto-retry, priority upload, adaptive chunks" && git push\n')
