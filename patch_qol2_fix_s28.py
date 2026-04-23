#!/usr/bin/env python3
"""
patch_qol2_fix_s28.py — Repair for 9 failed patches from patch_qol2_s28.py

Root causes fixed:
  A) patch_android.py Kotlin uses literal \\n (two chars) — anchors need \\\\n
  B) home_screen _checkServer/_wakeServer anchors had Unicode dash comment lines
  C) Dart interpolation needs ${...} not \\${...} in Python strings
  D) engine onTap anchor needed more unique surrounding context
  E) saveJobRecord / history filename anchors — use shorter unique fragments

Run from ~/tilawa-enhancer/ then git push.
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
        print(f"{WARN} [{path.name}] anchor not found — {label}")
        return False
    count = text.count(old)
    if count > 1:
        print(f"{WARN} [{path.name}] anchor not unique ({count}x) — {label}")
        return False
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"{OK}  [{path.name}] {label}")
    return True

errors = 0

# ═══════════════════════════════════════════════════════════════════════════════
# FIX A — patch_android.py shareFile case
# Root cause: Kotlin source uses literal \n (backslash + n as two chars).
# Anchor must use \\n to match the literal two-char sequence in the file.
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[FIX A] patch_android.py — shareFile MethodChannel case")

PATCH_ANDROID = REPO / "patch_android.py"

ok = patch(PATCH_ANDROID,
    # literal \\n in the file = backslash + n
    "'                else -> result.notImplemented()\\n'",
    "'                \"shareFile\" -> {\\n'\n"
    "'                    val uriString = call.argument<String>(\"uri\")\\n'\n"
    "'                    if (uriString != null) {\\n'\n"
    "'                        try {\\n'\n"
    "'                            val shareUri = android.net.Uri.parse(uriString)\\n'\n"
    "'                            val intent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {\\n'\n"
    "'                                type = \"audio/mpeg\"\\n'\n"
    "'                                putExtra(android.content.Intent.EXTRA_STREAM, shareUri)\\n'\n"
    "'                                addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)\\n'\n"
    "'                            }\\n'\n"
    "'                            startActivity(android.content.Intent.createChooser(intent, \"Share\"))\\n'\n"
    "'                            result.success(null)\\n'\n"
    "'                        } catch (e: Exception) {\\n'\n"
    "'                            result.error(\"SHARE_FAILED\", e.message, null)\\n'\n"
    "'                        }\\n'\n"
    "'                    } else {\\n'\n"
    "'                        result.error(\"INVALID_ARGS\", \"uri is null\", null)\\n'\n"
    "'                    }\\n'\n"
    "'                }\\n'\n"
    "'                else -> result.notImplemented()\\n'",
    "shareFile case (\\\\n literal fix)")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# FIX B1+B2 — api_service.dart saveJobRecord
# Root cause: multi-line anchor. Use a short unique line instead.
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[FIX B] api_service.dart — saveJobRecord originalName")

API = REPO / "lib/services/api_service.dart"

# B1: add originalName parameter — anchor on the unique 'Map<String, dynamic>? metrics,' line
ok = patch(API,
    "    Map<String, dynamic>? metrics,\n  }) async {",
    "    String? originalName,\n"
    "    Map<String, dynamic>? metrics,\n  }) async {",
    "originalName param in saveJobRecord")
if not ok: errors += 1

# B2: store it in the record — anchor on the unique timestamp line
ok = patch(API,
    "        'timestamp': DateTime.now().toIso8601String(),\n"
    "        if (metrics?['lufs']",
    "        'timestamp': DateTime.now().toIso8601String(),\n"
    "        if (originalName != null) 'original_name': originalName,\n"
    "        if (metrics?['lufs']",
    "store original_name in record")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# FIX C — home_screen.dart (6 patches)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[FIX C] home_screen.dart")

HOME = REPO / "lib/screens/home_screen.dart"

# C1: _checkServer — skip the ── Unicode comment line, anchor on method body only
ok = patch(HOME,
    "  Future<void> _checkServer() async {\n"
    "    final up = await ApiService.isServerRunning();\n"
    "    if (mounted) setState(() => _serverUp = up);\n"
    "  }",
    "  Future<void> _checkServer() async {\n"
    "    final ms = await ApiService.checkServer();\n"
    "    if (mounted) setState(() { _serverUp = ms != null; _latencyMs = ms; });\n"
    "  }",
    "C1: _checkServer uses checkServer()")
if not ok: errors += 1

# C2: _wakeServer timer — anchor on the isServerRunning call with 6-space indent
#     (distinguishes it from _checkServer which has 4-space indent)
ok = patch(HOME,
    "      final up = await ApiService.isServerRunning();\n"
    "      if (!mounted) {\n"
    "        _wakeTimer?.cancel();\n"
    "        return;\n"
    "      }\n"
    "      if (up || _wakeAttempts >= 7) { // max 35s\n"
    "        _wakeTimer?.cancel();\n"
    "        setState(() { _serverUp = up; _waking = false; _wakeAttempts = 0; });",
    "      final ms = await ApiService.checkServer();\n"
    "      final up = ms != null;\n"
    "      if (!mounted) {\n"
    "        _wakeTimer?.cancel();\n"
    "        return;\n"
    "      }\n"
    "      if (up || _wakeAttempts >= 7) { // max 35s\n"
    "        _wakeTimer?.cancel();\n"
    "        setState(() { _serverUp = up; _latencyMs = ms; _waking = false; _wakeAttempts = 0; });",
    "C2: _wakeServer uses checkServer()")
if not ok: errors += 1

# C3: save engine on tap — anchor includes GestureDetector line for uniqueness
ok = patch(HOME,
    "    return GestureDetector(\n"
    "      onTap: () => setState(() => _engine = e.id),",
    "    return GestureDetector(\n"
    "      onTap: () {\n"
    "        setState(() => _engine = e.id);\n"
    "        ApiService.saveLastEngine(e.id); // S28-T2: persist\n"
    "      },",
    "C3: save engine on tap")
if not ok: errors += 1

# C4: pass originalName to saveJobRecord — anchor on unique score line near the call
ok = patch(HOME,
    "      await ApiService.saveJobRecord(\n"
    "        jobId: _jobId!,\n"
    "        engine: _engine,\n"
    "        score: score,\n"
    "        filename: filename,\n"
    "        metrics: sd,\n"
    "      );",
    "      await ApiService.saveJobRecord(\n"
    "        jobId: _jobId!,\n"
    "        engine: _engine,\n"
    "        score: score,\n"
    "        filename: filename,\n"
    "        originalName: _file?.path.split('/').last, // S28-T2\n"
    "        metrics: sd,\n"
    "      );",
    "C4: pass originalName to saveJobRecord")
if not ok: errors += 1

# C5: latency in server banner — FIX: use ${...} not \${...} for Dart interpolation
# Anchor on the unique ternary structure around s.serverOnline
ok = patch(HOME,
    "                _waking\n"
    "                  ? s.waking\n"
    "                  : (_serverUp ? s.serverOnline : s.serverOffline),",
    "                _waking\n"
    "                  ? s.waking\n"
    "                  : _serverUp\n"
    "                    ? (_latencyMs != null\n"
    "                        ? '${s.serverOnline} \u00b7 ${_latencyMs}ms'\n"
    "                        : s.serverOnline)\n"
    "                    : s.serverOffline,",
    "C5: latency in banner (${...} fix, no backslash)")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# FIX D — history_screen.dart — original_name display
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[FIX D] history_screen.dart — original_name in job card")

HIST = REPO / "lib/screens/history_screen.dart"

ok = patch(HIST,
    "              Text(ApiService.buildFilename(engine),\n"
    "                maxLines: 1, overflow: TextOverflow.ellipsis,\n"
    "                style: const TextStyle(\n"
    "                  color: Color(0xFFC9D1D9), fontSize: 11,\n"
    "                  fontWeight: FontWeight.bold)),",
    "              Text(\n"
    "                job['original_name'] as String?\n"
    "                  ?? ApiService.buildFilename(engine),\n"
    "                maxLines: 1, overflow: TextOverflow.ellipsis,\n"
    "                style: const TextStyle(\n"
    "                  color: Color(0xFFC9D1D9), fontSize: 11,\n"
    "                  fontWeight: FontWeight.bold)),",
    "D: original_name in history card")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL 9 FIXES APPLIED \033[0m")
    print()
    print("Next:")
    print("  cd ~/tilawa-enhancer")
    print("  git add patch_android.py \\")
    print("          lib/services/api_service.dart \\")
    print("          lib/screens/home_screen.dart \\")
    print("          lib/screens/history_screen.dart")
    print("  git commit -m 'S28-T2: fix 9 failed patches (latency, share, engine persist, history name)'")
    print("  git push origin master")
    print()
    print("After this passes, run patch_polish_s29.py for the visual pass.")
else:
    print(f"\033[91m {errors} FIX(ES) STILL FAILING \033[0m")
    print("Check WARN lines above.")
    sys.exit(1)
