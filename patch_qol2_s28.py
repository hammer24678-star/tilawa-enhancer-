#!/usr/bin/env python3
"""
patch_qol2_s28.py — Session 28: Tier 2 Quality of Life Features

Run AFTER patch_qol_s28.py, from ~/tilawa-enhancer/ then git push.

Features:
  10. Share button in result card (Android share sheet, API 29+ content:// URI)
  11. Original source filename stored in history records
  13. Last-used engine persisted across app restarts (SharedPreferences)
  14. Server latency shown in banner  "🟢 Online · 84ms"

Modified files:
  patch_android.py              — shareFile case in MainActivity.kt
  lib/services/api_service.dart — checkServer(), shareAudio(),
                                  saveLastEngine(), loadLastEngine(),
                                  original_name in saveJobRecord()
  lib/state/lang_provider.dart  — shareBtn string
  lib/screens/home_screen.dart  — _latencyMs state, updated _checkServer,
                                  _wakeServer, engine onTap, initState,
                                  _shareFile(), share button in result card,
                                  latency in _serverBanner
  lib/screens/history_screen.dart — show original_name in job cards
"""

from pathlib import Path
import sys

REPO = Path(".")

OK   = "\033[92m OK  \033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"

def patch(path: Path, old: str, new: str, label: str = "") -> bool:
    if not path.exists():
        print(f"{ERR} [{path}] file not found")
        return False
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label or old[:60]!r}")
        return False
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"{OK}  [{path.name}] {label}")
    return True

errors = 0

# ═══════════════════════════════════════════════════════════════════════════════
# 1. patch_android.py — add shareFile case to MainActivity.kt
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[1/5] patch_android.py — shareFile in MainActivity.kt")

PATCH_ANDROID = REPO / "patch_android.py"

ok = patch(PATCH_ANDROID,
    "'                else -> result.notImplemented()\n'",
    # Insert shareFile BEFORE else -> notImplemented
    """'                "shareFile" -> {\\n'
'                    val uriString = call.argument<String>("uri")\\n'
'                    if (uriString != null) {\\n'
'                        try {\\n'
'                            val shareUri = android.net.Uri.parse(uriString)\\n'
'                            val intent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {\\n'
'                                type = "audio/mpeg"\\n'
'                                putExtra(android.content.Intent.EXTRA_STREAM, shareUri)\\n'
'                                addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)\\n'
'                            }\\n'
'                            startActivity(android.content.Intent.createChooser(intent, "Share"))\\n'
'                            result.success(null)\\n'
'                        } catch (e: Exception) {\\n'
'                            result.error("SHARE_FAILED", e.message, null)\\n'
'                        }\\n'
'                    } else {\\n'
'                        result.error("INVALID_ARGS", "uri is null", null)\\n'
'                    }\\n'
'                }\\n'
'                else -> result.notImplemented()\\n'""",
    "shareFile MethodChannel case")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# 2. api_service.dart — 5 additions
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[2/5] api_service.dart")

API = REPO / "lib/services/api_service.dart"

# 2a. Add checkServer() + shareAudio() + saveLastEngine() + loadLastEngine()
#     right after isServerRunning(), before the upload section
ok = patch(API,
    "  // ── Upload — auto-selects direct or chunked ────────────────────────────────\n\n  /// Get FCM token",
    """  // ── S28-T2: Server latency check ──────────────────────────────────────────
  /// Returns latency in ms if server is up, null if unreachable.
  static Future<int?> checkServer() async {
    try {
      final t0 = DateTime.now().millisecondsSinceEpoch;
      final res = await http
          .get(Uri.parse('$_base/'))
          .timeout(const Duration(seconds: 8));
      if (res.statusCode == 200) {
        return DateTime.now().millisecondsSinceEpoch - t0;
      }
      return null;
    } catch (_) {
      return null;
    }
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
      return prefs.getString(_lastEngineKey) ?? 'v9.0';
    } catch (_) {
      return 'v9.0';
    }
  }

  // ── Upload — auto-selects direct or chunked ────────────────────────────────

  /// Get FCM token""",
    "checkServer() + shareAudio() + saveLastEngine() + loadLastEngine()")
if not ok: errors += 1

# 2b. Add original_name to saveJobRecord signature + record
ok = patch(API,
    "  static Future<void> saveJobRecord({\n    required String jobId,\n    required String engine,\n    required double score,\n    required String filename,\n    Map<String, dynamic>? metrics,\n  }) async {",
    """  static Future<void> saveJobRecord({
    required String jobId,
    required String engine,
    required double score,
    required String filename,
    String? originalName,        // S28: original source file name
    Map<String, dynamic>? metrics,
  }) async {""",
    "originalName param in saveJobRecord")
if not ok: errors += 1

ok = patch(API,
    "        'timestamp': DateTime.now().toIso8601String(),\n        if (metrics?['lufs']",
    """        'timestamp': DateTime.now().toIso8601String(),
        if (originalName != null) 'original_name': originalName,
        if (metrics?['lufs']""",
    "store original_name in record")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# 3. lang_provider.dart — shareBtn string
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[3/5] lang_provider.dart")

LANG = REPO / "lib/state/lang_provider.dart"

ok = patch(LANG,
    "  // S28: QoL strings",
    """  // S28: QoL strings
  String get shareBtn       => ar ? '\u0645\u0634\u0627\u0631\u0643\u0629'                           : 'Share';""",
    "shareBtn string (note: S28 comment already there from script 1)")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# 4. home_screen.dart — 8 patches
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[4/5] home_screen.dart")

HOME = REPO / "lib/screens/home_screen.dart"

# 4a. Add _latencyMs state variable after _fileBytes (which S28 script 1 added)
ok = patch(HOME,
    "  int     _fileBytes  = 0;     // S28: file size in bytes for estimated time",
    "  int     _fileBytes  = 0;     // S28: file size in bytes for estimated time\n  int?    _latencyMs;              // S28-T2: server latency in ms",
    "_latencyMs state var")
if not ok: errors += 1

# 4b. Update _checkServer() to use checkServer() and store latency
ok = patch(HOME,
    "  // ── Server check ───────────────────────────────────────────────────────────\n  Future<void> _checkServer() async {\n    final up = await ApiService.isServerRunning();\n    if (mounted) setState(() => _serverUp = up);\n  }",
    """  // ── Server check ───────────────────────────────────────────────────────────
  Future<void> _checkServer() async {
    final ms = await ApiService.checkServer();
    if (mounted) setState(() { _serverUp = ms != null; _latencyMs = ms; });
  }""",
    "_checkServer() now stores latency")
if not ok: errors += 1

# 4c. Update _wakeServer() timer to use checkServer()
ok = patch(HOME,
    "      final up = await ApiService.isServerRunning();\n      if (!mounted) {\n        _wakeTimer?.cancel();\n        return;\n      }\n      if (up || _wakeAttempts >= 7) { // max 35s\n        _wakeTimer?.cancel();\n        setState(() { _serverUp = up; _waking = false; _wakeAttempts = 0; });",
    """      final ms = await ApiService.checkServer();
      final up = ms != null;
      if (!mounted) {
        _wakeTimer?.cancel();
        return;
      }
      if (up || _wakeAttempts >= 7) { // max 35s
        _wakeTimer?.cancel();
        setState(() { _serverUp = up; _latencyMs = ms; _waking = false; _wakeAttempts = 0; });""",
    "_wakeServer() timer uses checkServer()")
if not ok: errors += 1

# 4d. Load last engine in initState()
ok = patch(HOME,
    "    _checkServer();\n    _serverTimer = Timer.periodic(\n        const Duration(seconds: 6), (_) => _checkServer());",
    """    _checkServer();
    _serverTimer = Timer.periodic(
        const Duration(seconds: 6), (_) => _checkServer());
    // S28-T2: restore last engine selection
    ApiService.loadLastEngine().then((e) {
      if (mounted) setState(() => _engine = e);
    });""",
    "load last engine in initState")
if not ok: errors += 1

# 4e. Save engine on selection
ok = patch(HOME,
    "      onTap: () => setState(() => _engine = e.id),",
    """      onTap: () {
        setState(() => _engine = e.id);
        ApiService.saveLastEngine(e.id); // S28-T2: persist
      },""",
    "save engine on tap")
if not ok: errors += 1

# 4f. Pass originalName to saveJobRecord in _downloadAndSave()
ok = patch(HOME,
    "      await ApiService.saveJobRecord(\n        jobId: _jobId!,\n        engine: _engine,\n        score: score,\n        filename: filename,\n        metrics: sd,\n      );",
    """      await ApiService.saveJobRecord(
        jobId: _jobId!,
        engine: _engine,
        score: score,
        filename: filename,
        originalName: _file?.path.split('/').last, // S28-T2
        metrics: sd,
      );""",
    "pass originalName to saveJobRecord")
if not ok: errors += 1

# 4g. Add _shareFile() method before _copyMetrics
ok = patch(HOME,
    "  // ── S28: Copy metrics to clipboard ───────────────────────────────────────",
    """  // ── S28-T2: Share via Android share sheet ────────────────────────────────
  Future<void> _shareFile() async {
    if (_output == null) return;
    HapticFeedback.lightImpact();
    try {
      await ApiService.shareAudio(_output!.path);
    } catch (e) {
      if (mounted) {
        final s = LangProvider.strings(context);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(s.ar ? '\u0641\u0634\u0644 \u0627\u0644\u0645\u0634\u0627\u0631\u0643\u0629' : 'Share failed: $e'),
          backgroundColor: const Color(0xFF200D0D),
          duration: const Duration(seconds: 3),
        ));
      }
    }
  }

  // ── S28: Copy metrics to clipboard ───────────────────────────────────────""",
    "_shareFile() method")
if not ok: errors += 1

# 4h. Add share button in result card (after Open in Player block, before Saved indicator)
ok = patch(HOME,
    "        // Saved indicator\n        if (_output != null) ...[",
    """        // S28-T2: Share button (only for content:// URIs = API 29+)
        if (_output?.path.startsWith('content://') ?? false) ...[
          const SizedBox(height: 8),
          SizedBox(width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _shareFile,
              style: OutlinedButton.styleFrom(
                foregroundColor: const Color(0xFF8B949E),
                side: const BorderSide(color: Color(0xFF30363D), width: 0.8),
                padding: const EdgeInsets.symmetric(vertical: 10),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12))),
              icon: const Icon(Icons.share_rounded, size: 18),
              label: Text(s.shareBtn,
                style: const TextStyle(fontSize: 13)),
            )),
        ],
        // Saved indicator
        if (_output != null) ...[""",
    "share button in result card")
if not ok: errors += 1

# 4i. Update _serverBanner to show latency
ok = patch(HOME,
    "              _waking\n                  ? s.waking\n                  : (_serverUp ? s.serverOnline : s.serverOffline),",
    """              _waking
                  ? s.waking
                  : _serverUp
                    ? (_latencyMs != null
                        ? '\${s.serverOnline} · \${_latencyMs}ms'
                        : s.serverOnline)
                    : s.serverOffline,""",
    "latency in server banner text")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# 5. history_screen.dart — show original_name if available
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[5/5] history_screen.dart")

HIST = REPO / "lib/screens/history_screen.dart"

ok = patch(HIST,
    "              Text(ApiService.buildFilename(engine),\n                maxLines: 1, overflow: TextOverflow.ellipsis,\n                style: const TextStyle(\n                  color: Color(0xFFC9D1D9), fontSize: 11,\n                  fontWeight: FontWeight.bold)),",
    """              // S28-T2: show original source name if stored, else fall back
              Text(
                job['original_name'] as String?
                  ?? ApiService.buildFilename(engine),
                maxLines: 1, overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: Color(0xFFC9D1D9), fontSize: 11,
                  fontWeight: FontWeight.bold)),""",
    "original_name in history job card")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL PATCHES APPLIED SUCCESSFULLY \033[0m")
    print()
    print("Files changed:")
    print("  patch_android.py")
    print("  lib/services/api_service.dart")
    print("  lib/state/lang_provider.dart")
    print("  lib/screens/home_screen.dart")
    print("  lib/screens/history_screen.dart")
    print()
    print("Next steps:")
    print("  cd ~/tilawa-enhancer")
    print("  git add patch_android.py \\")
    print("          lib/services/api_service.dart \\")
    print("          lib/state/lang_provider.dart \\")
    print("          lib/screens/home_screen.dart \\")
    print("          lib/screens/history_screen.dart")
    print("  git commit -m 'S28: Tier 2 QoL — share, history name, engine persist, latency'")
    print("  git push origin master")
    print()
    print("Notes:")
    print("  - Share button only visible on API 29+ (content:// URI from MediaStore)")
    print("  - Engine persisted to SharedPreferences key 'last_engine_v1'")
    print("  - Latency shown as: 'Cloud server online v · 84ms'")
    print("  - Original filename shown in history for NEW records (old records unchanged)")
else:
    print(f"\033[91m {errors} PATCH(ES) FAILED — check WARN lines above \033[0m")
    sys.exit(1)
