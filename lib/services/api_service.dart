import 'dart:io';
import 'dart:convert';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  // S66: dynamic server pool — loaded from assets/servers.json
  // Add new servers by updating servers.json — no APK rebuild needed
  static List<String> _servers = [
    'https://carm5333-tilawa-server.hf.space',
    'https://carm5333-background.hf.space',
    'https://carm5333-background2.hf.space',  // S150
  ];
  static bool _serversLoaded = false;

  static Future<void> loadServers() async {
    if (_serversLoaded) return;
    try {
      // Load from bundled asset
      final txt = await rootBundle.loadString('assets/servers.json');
      final data = jsonDecode(txt) as Map<String, dynamic>;
      final local = (data['servers'] as List).cast<String>();
      if (local.isNotEmpty) _servers = local;
      // Optionally fetch fresh list from GitHub (non-blocking)
      final remoteUrl = data['remote_url'] as String?;
      if (remoteUrl != null) {
        http.get(Uri.parse(remoteUrl))
            .timeout(const Duration(seconds: 5))
            .then((res) {
          if (res.statusCode == 200) {
            final rd = jsonDecode(res.body) as Map<String, dynamic>;
            final remote = (rd['servers'] as List).cast<String>();
            if (remote.isNotEmpty) _servers = remote;
          }
        }).catchError((_) {});
      }
    } catch (_) {} // keep defaults on any error
    _serversLoaded = true;
  }

  // Server health cache: {url: {latency, queue, ts}}
  static final Map<String, Map<String, dynamic>> _health = {};

  // Adaptive chunk size — updated based on upload speed
  static int _chunkSize = 4 * 1024 * 1024; // S65: adaptive, starts at 4MB
  static String _activeServer = '';  // S120: track which server owns current job

  // Pick best server: lowest score = latency * (1 + queue_depth)
  static Future<String> _bestServer() async {
    String best = _servers.first; double bestScore = double.infinity;
    for (final url in _servers) {
      final h = _health[url];
      if (h == null) { best = url; break; } // untested = try it
      final age = DateTime.now().millisecondsSinceEpoch - (h['ts'] as int);
      if (age > 30000) { best = url; break; } // stale = refresh
      final latency = (h['latency'] as int? ?? 9999).toDouble();
      final queue   = (h['queue']   as int? ?? 0).toDouble();
      final score   = latency * (1.0 + queue * 0.5);
      if (score < bestScore) { bestScore = score; best = url; }
    }
    return best;
  }

  // Refresh health for one server
  static Future<void> _refreshHealth(String url) async {
    try {
      final t0 = DateTime.now().millisecondsSinceEpoch;
      final res = await http
          .get(Uri.parse('$url/queue'))
          .timeout(const Duration(seconds: 6));
      final ms = DateTime.now().millisecondsSinceEpoch - t0;
      if (res.statusCode == 200) {
        final d = jsonDecode(res.body) as Map<String, dynamic>;
        _health[url] = {
          'latency': ms,
          'queue':   (d['queued'] as int? ?? 0) + (d['running'] as int? ?? 0),
          'ts':      DateTime.now().millisecondsSinceEpoch,
        };
      }
    } catch (_) {
      _health[url] = {'latency': 9999, 'queue': 99,
                      'ts': DateTime.now().millisecondsSinceEpoch};
    }
  }

  // Pre-warm all servers (call on app init + file picker open)
  static Future<void> preWarm() async {
    await loadServers(); // S66: ensure server list is current
    await Future.wait(_servers.map(_refreshHealth));
  }

  // Estimated wait time in seconds based on queue depth + file size
  static int estimateWaitSeconds(String serverUrl, int fileSizeBytes) {
    final h = _health[serverUrl];
    final queue = h != null ? (h['queue'] as int? ?? 0) : 0;
    final fileMb = fileSizeBytes / (1024 * 1024);
    final processSec = (fileMb * 8).clamp(30, 480).toInt(); // ~8s/MB
    return queue * 120 + processSec; // 2min per queued job + own job
  }

  static const int _chunkSizeConst = 4 * 1024 * 1024;
  static const _mediaChannel = MethodChannel('com.tilawa.tilawa_enhancer/media');

  // SharedPreferences key for locally persisted job records
  static const _jobsKey = 'saved_job_records_v1';

  // ── Health check ───────────────────────────────────────────────────────────
  static Future<bool> isServerRunning() async {
    try {
      final url = await _bestServer();
      final res = await http
          .get(Uri.parse('$url/'))
          .timeout(const Duration(seconds: 8));
      return res.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  // ── S28-T2: Server latency check ──────────────────────────────────────────
  /// Returns latency in ms if server is up, null if unreachable.
  static Future<int?> checkServer() async {
    // S65: refresh both servers, return best latency
    await Future.wait(_servers.map(_refreshHealth));
    int? best;
    for (final h in _health.values) {
      final lat = h['latency'] as int?;
      if (lat != null && lat < 9000 && (best == null || lat < best)) best = lat;
    }
    return best;
  }

  // ── S32: Silent keep-alive ping ─────────────────────────────────────────────
  static Future<void> pingServer() async {
    try {
      final url = await _bestServer();
      await http.get(Uri.parse('$url/ping')).timeout(const Duration(seconds: 8));
    } catch (_) {}
  }

  // ── S28-T2: Share audio file via Android share sheet ──────────────────────
  static Future<void> shareAudio(String uri) async {
    await _mediaChannel.invokeMethod<void>('shareFile', {'uri': uri});
  }

  // ── S28-T2: Persist last used engine ──────────────────────────────────────
  static const _lastEngineKey = 'last_engine_v1';

  static Future<void> saveLastEngine(String engine) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_lastEngineKey, engine);
    } catch (_) {}
  }

  static Future<String> loadLastEngine() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      return prefs.getString(_lastEngineKey) ?? 'v10.0'; // S31
    } catch (_) {
      return 'v10.0'; // S32-BUG5-FIX: was 'v9.0', inconsistent with normal path
    }
  }

  // S57: persist active job_id so app-kill never loses in-progress jobs
  static const _activeJobKey    = 'active_job_id_v1';
  static const _activeEngineKey = 'active_job_engine_v1';

  static Future<void> saveJobId(String jobId, String engine) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(_activeJobKey,    jobId);
      await prefs.setString(_activeEngineKey, engine);
    } catch (_) {}
  }

  static Future<void> clearJobId() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_activeJobKey);
      await prefs.remove(_activeEngineKey);
    } catch (_) {}
  }

  static Future<Map<String, String>?> loadJobId() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final jobId  = prefs.getString(_activeJobKey);
      final engine = prefs.getString(_activeEngineKey) ?? 'v10.0';
      if (jobId != null && jobId.isNotEmpty) return {'job_id': jobId, 'engine': engine};
    } catch (_) {}
    return null;
  }

  // ── Upload — auto-selects direct or chunked ────────────────────────────────

  static Future<Map<String, dynamic>> uploadFile(
    File file,
    String engine, {
    void Function(double, String)? onProgress,
  }) async {
    final size = await file.length();
    await Future.wait(_servers.map(_refreshHealth));
    final server = await _bestServer();
    _activeServer = server;  // S120
    onProgress?.call(0.01, 'اختيار الخادم الأمثل...');
    // S65: small files (<5MB) get priority direct upload
    if (size <= 5 * 1024 * 1024) {
      onProgress?.call(0.02, 'جار الرفع...');
      return _uploadDirectTo(file, engine, server, onProgress: onProgress);
    }
    try {
      return await _uploadChunkedTo(file, engine, size, server, onProgress: onProgress);
    } catch (_) {
      // S65: auto-retry on alternate server
      final alt = _servers.firstWhere((s) => s != server, orElse: () => server);
      if (alt == server) rethrow;
      onProgress?.call(0, 'تحويل إلى خادم احتياطي...');
      return await _uploadChunkedTo(file, engine, size, alt, onProgress: onProgress);
    }
  }

  static Future<Map<String, dynamic>> _uploadDirectTo(
      File file, String engine, String server, {
      void Function(double, String)? onProgress}) async {
    // S25-DART5: retry wrapper (was fire-and-forget)
    for (int attempt = 0; attempt < 3; attempt++) {
      try {
        if (attempt > 0) onProgress?.call(0.02, 'إعادة محاولة الرفع أثناء الشبكة...');
        final req = http.MultipartRequest('POST', Uri.parse('$server/upload'));
        req.files.add(await http.MultipartFile.fromPath('file', file.path));
        req.fields['engine'] = engine;
        final res = await req.send().timeout(const Duration(seconds: 60));
        onProgress?.call(0.65, 'جار المعالجة...');
        final body = await res.stream
            .bytesToString()
            .timeout(const Duration(seconds: 30)); // FIX: was no timeout
        if (res.statusCode == 200) return Map<String, dynamic>.from(jsonDecode(body) as Map);
        throw Exception('direct upload HTTP ${res.statusCode}');
      } catch (e) {
        if (attempt == 2) rethrow;
        await Future.delayed(Duration(seconds: 2 << attempt));
      }
    }
    throw Exception('unreachable');
  }

  static Future<Map<String, dynamic>> _uploadChunkedTo(
    File file,
    String engine,
    int fileSize,
    String server, {
    void Function(double, String)? onProgress,
  }) async {
    final filename = file.path.split('/').last;
    onProgress?.call(0.02, 'بدء الجلسة...');

    // S25-DART2: use server-negotiated chunk size (server may differ)
    final startRes = await http
        .post(
          Uri.parse('$server/upload_start'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'filename': filename,
            'total_size': fileSize,
            'fcm_token': '',
          }),
        )
        .timeout(const Duration(seconds: 15));
    final startData = jsonDecode(startRes.body) as Map;
    final jobId = startData['job_id'] as String;
    // Respect server chunk size; fall back to our default
    final serverChunkSize = (startData['chunk_size'] as int?) ?? _chunkSize;
    final totalChunks = (fileSize / serverChunkSize).ceil();

    final raf = await file.open(mode: FileMode.read);
    try {
      for (int i = 0; i < totalChunks; i++) {
        final offset = i * serverChunkSize;
        final size = ((fileSize - offset) < serverChunkSize)
            ? (fileSize - offset)
            : serverChunkSize;
        await raf.setPosition(offset);
        final bytes = await raf.read(size);

        // S25-DART4: exponential backoff 2s → 4s → 8s
        for (int attempt = 0; attempt < 3; attempt++) {
          try {
            final req =
                http.MultipartRequest('POST', Uri.parse('$server/upload_chunk'));
            req.fields['job_id'] = jobId;
            req.fields['index'] = i.toString();
            req.files.add(http.MultipartFile.fromBytes('chunk', bytes,
                filename: 'chunk_$i'));
            final res = await req.send().timeout(const Duration(seconds: 60));
            await res.stream.drain<void>(); // S20-D: drain to avoid CLOSE_WAIT
            if (res.statusCode == 200) break;
            throw Exception('chunk_$i HTTP ${res.statusCode}');
          } catch (e) {
            if (attempt == 2) rethrow;
            // S25-DART4: 2s → 4s → 8s
            await Future.delayed(Duration(seconds: 2 << attempt));
          }
        }
        // S25-DART3: progress fires AFTER chunk confirmed (was before send)
        onProgress?.call(0.05 + ((i + 1) / totalChunks) * 0.60,
            'رفع ${i + 1}/$totalChunks...');
      }
    } finally {
      await raf.close();
    }

    // S25-DART6: finalize — server now validates all chunks received
    onProgress?.call(0.67, 'دمج الأجزاء...');
    final finalRes = await http
        .post(
          Uri.parse('$server/upload_finalize'),
          headers: {'Content-Type': 'application/json'},
          body: jsonEncode({
            'job_id': jobId,
            'engine': engine,
            'total_chunks': totalChunks, // server cross-checks this
          }),
        )
        .timeout(const Duration(minutes: 3));
    final finalData = jsonDecode(finalRes.body) as Map;
    // Surface missing-chunks error clearly
    if (finalData['error'] != null) {
      throw Exception('finalize: ${finalData['error']}');
    }
    return Map<String, dynamic>.from(finalData);
  }

  // ── Poll status ────────────────────────────────────────────────────────────
  static Future<Map<String, dynamic>> getStatus(String jobId) async {
    final res = await http
        .get(Uri.parse('${_activeServer.isNotEmpty ? _activeServer : _servers.first}/status/\$jobId'))
        .timeout(const Duration(seconds: 10));
    // S22 BUG2: 404 = job gone (server restarted).
    // Without this check, Flutter parses the error JSON as a normal
    // response, no exception is thrown, _pollErrors never increments,
    // and the 79% freeze survives even after the S22 catch fix.
    if (res.statusCode == 404) {
      return {'status': 'error', 'error': 'JOB_EXPIRED'};
    }
    if (res.statusCode != 200) {
      throw Exception('HTTP ${res.statusCode}');
    }
    return jsonDecode(res.body);
  }

  // ── Download — true streaming, no RAM overflow ─────────────────────────────
  static Future<(File?, String?)> downloadFile(
      String jobId, String filename) async {
    final client = http.Client();
    File? tempFile;
    try {
      final req =
          http.Request('GET', Uri.parse('${_activeServer.isNotEmpty ? _activeServer : _servers.first}/download/\$jobId'));
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
          .get(Uri.parse('${await _bestServer()}/history'))
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
    String? originalName,        // S28: original source file name
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
        if (originalName != null) 'original_name': originalName,
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

  /// Remove ALL saved job records (used by History "Clear All").
  static Future<void> clearAllJobRecords() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_jobsKey);
    } catch (_) {}
  }

  // ── Build proper download filename ─────────────────────────────────────────
  // S21 BUG2 FIX: optional originalPath — preserves original filename prefix.
  // With originalPath:  {basename}__Tilawa_{engine}_{name}_1425H.mp3
  // Without:            Tilawa_{engine}_{name}_1425H.mp3  (history fallback)
  static String buildFilename(String engine, {String? originalPath}) {
    const engineNames = {
      'v10.0': 'Aetherion_Foundation',   // S32-BUG4-FIX
      'v9.0':  'The_Evolution',
      'v8.5':  'Honest_Ceiling',
      'v8.0':  'Calibrated_Precision',
      'v7.6':  'Intelligent_Assessment',
      'v7.5':  'Disciplined_Precision',
      'v7.0':  'Classic',
    };
    final name = engineNames[engine] ?? engine.replaceAll('.', '_');
    final suffix = 'Tilawa_${engine}_${name}_1425H.mp3';
    if (originalPath != null && originalPath.isNotEmpty) {
      final orig = originalPath.split('/').last;
      final noExt = orig.contains('.')
          ? orig.substring(0, orig.lastIndexOf('.'))
          : orig;
      return '${noExt}__${suffix}';
    }
    return suffix;
  }
}
