#!/usr/bin/env python3
"""
patch_s28_t3.py — S28 Tier-3: Apply the 7 remaining failing patches

Root-cause analysis of T2 failures
────────────────────────────────────────────────────────────────────────
T1 (patch_qol2_s28.py) succeeded on:
  api_service  : checkServer/shareAudio/saveLastEngine/loadLastEngine
  lang_provider: shareBtn
  home_screen  : _latencyMs var, loadLastEngine in initState,
                 _shareFile(), share button in result card

T1 failed on 9 patches → T2 (patch_qol2_fix_s28.py) fixed 2:
  patch_android.py  : shareFile ✓
  api_service.dart  : originalName param ✓

7 still broken. This script fixes them. Run from ~/tilawa-enhancer/.

Strategy:
  • skip_if=   → idempotent: skip silently if new text already present
  • debug dump → on anchor miss, print repr() of nearest 120 chars
                 so future debugging is instant
"""

from pathlib import Path
import sys, re

REPO = Path(".")

OK   = "\033[92m OK  \033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"
SKIP = "\033[94m SKIP\033[0m"

errors = 0

# ── helpers ─────────────────────────────────────────────────────────────────

def _debug(text: str, hint: str) -> None:
    """Print repr of the first ~120 chars around hint for diagnosis."""
    idx = text.find(hint)
    if idx == -1:
        idx = text.find(hint.split('\n')[0])  # try first line only
    if idx == -1:
        print(f"         [debug] hint phrase not found in file at all")
        return
    snippet = text[max(0, idx-20):idx+120]
    print(f"         [debug] file content around hint ({idx}):")
    print(f"         {repr(snippet)}")

def patch(path: Path, old: str, new: str, label: str = "",
          skip_if: str = "", debug_hint: str = "") -> bool:
    global errors
    if not path.exists():
        print(f"{ERR} [{path}] file not found")
        errors += 1
        return False
    text = path.read_text(encoding="utf-8")

    # Idempotency: if new content already present, skip
    if skip_if and skip_if in text:
        print(f"{SKIP} [{path.name}] already applied — {label}")
        return True

    if old not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label}")
        _debug(text, debug_hint or old.split('\n')[0])
        errors += 1
        return False

    count = text.count(old)
    if count > 1:
        print(f"{WARN} [{path.name}] anchor not unique ({count}×) — {label}")
        errors += 1
        return False

    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"{OK}  [{path.name}] {label}")
    return True


# ═══════════════════════════════════════════════════════════════════════════
# P1 — api_service.dart
#      B2: store 'original_name' in saveJobRecord record body
# ═══════════════════════════════════════════════════════════════════════════
print("\n[P1] api_service.dart — original_name in record body")

API = REPO / "lib/services/api_service.dart"

patch(API,
    # OLD: exact text confirmed from dump at lines 27851-27852
    "        'timestamp': DateTime.now().toIso8601String(),\n"
    "        if (metrics?['lufs']",
    # NEW: insert original_name line between timestamp and metrics
    "        'timestamp': DateTime.now().toIso8601String(),\n"
    "        if (originalName != null) 'original_name': originalName,\n"
    "        if (metrics?['lufs']",
    label="B2: original_name stored in record",
    skip_if="if (originalName != null) 'original_name': originalName,",
    debug_hint="'timestamp': DateTime.now().toIso8601String()",
)


# ═══════════════════════════════════════════════════════════════════════════
# P2-P6 — home_screen.dart  (5 patches)
# ═══════════════════════════════════════════════════════════════════════════
print("\n[P2-P6] home_screen.dart")

HOME = REPO / "lib/screens/home_screen.dart"

# ── P2 — C1: _checkServer() uses checkServer() + stores latency ─────────
patch(HOME,
    # OLD: exact from dump line 25838-25841
    "  Future<void> _checkServer() async {\n"
    "    final up = await ApiService.isServerRunning();\n"
    "    if (mounted) setState(() => _serverUp = up);\n"
    "  }",
    # NEW
    "  Future<void> _checkServer() async {\n"
    "    final ms = await ApiService.checkServer();\n"
    "    if (mounted) setState(() { _serverUp = ms != null; _latencyMs = ms; });\n"
    "  }",
    label="C1: _checkServer uses checkServer()",
    skip_if="final ms = await ApiService.checkServer();",
    debug_hint="Future<void> _checkServer() async {",
)

# ── P3 — C2: _wakeServer timer uses checkServer() ───────────────────────
patch(HOME,
    # OLD: exact from dump lines 25852-25859 (6-space indent inside timer)
    "      final up = await ApiService.isServerRunning();\n"
    "      if (!mounted) {\n"
    "        _wakeTimer?.cancel();\n"
    "        return;\n"
    "      }\n"
    "      if (up || _wakeAttempts >= 7) { // max 35s\n"
    "        _wakeTimer?.cancel();\n"
    "        setState(() { _serverUp = up; _waking = false; _wakeAttempts = 0; });",
    # NEW
    "      final ms = await ApiService.checkServer();\n"
    "      final up = ms != null;\n"
    "      if (!mounted) {\n"
    "        _wakeTimer?.cancel();\n"
    "        return;\n"
    "      }\n"
    "      if (up || _wakeAttempts >= 7) { // max 35s\n"
    "        _wakeTimer?.cancel();\n"
    "        setState(() { _serverUp = up; _latencyMs = ms; _waking = false; _wakeAttempts = 0; });",
    label="C2: _wakeServer uses checkServer()",
    skip_if="_latencyMs = ms; _waking = false;",
    debug_hint="final up = await ApiService.isServerRunning();",
)

# ── P4 — C3: engine onTap saves last engine ─────────────────────────────
patch(HOME,
    # OLD: exact from dump lines 26391-26392 (4-space + 6-space indent)
    "    return GestureDetector(\n"
    "      onTap: () => setState(() => _engine = e.id),",
    # NEW: expand to block-body + persist
    "    return GestureDetector(\n"
    "      onTap: () {\n"
    "        setState(() => _engine = e.id);\n"
    "        ApiService.saveLastEngine(e.id); // S28-T2: persist\n"
    "      },",
    label="C3: save engine on tap",
    skip_if="ApiService.saveLastEngine(e.id); // S28-T2: persist",
    debug_hint="return GestureDetector(",
)

# ── P5 — C4: pass originalName to saveJobRecord ─────────────────────────
patch(HOME,
    # OLD: exact from dump lines 26055-26061
    "      await ApiService.saveJobRecord(\n"
    "        jobId: _jobId!,\n"
    "        engine: _engine,\n"
    "        score: score,\n"
    "        filename: filename,\n"
    "        metrics: sd,\n"
    "      );",
    # NEW
    "      await ApiService.saveJobRecord(\n"
    "        jobId: _jobId!,\n"
    "        engine: _engine,\n"
    "        score: score,\n"
    "        filename: filename,\n"
    "        originalName: _file?.path.split('/').last, // S28-T2\n"
    "        metrics: sd,\n"
    "      );",
    label="C4: pass originalName to saveJobRecord",
    skip_if="originalName: _file?.path.split('/').last, // S28-T2",
    debug_hint="await ApiService.saveJobRecord(",
)

# ── P6 — C5: server banner shows latency ────────────────────────────────
patch(HOME,
    # OLD: exact from dump lines 26307-26309 (16-space + 18-space + 18-space)
    "                _waking\n"
    "                  ? s.waking\n"
    "                  : (_serverUp ? s.serverOnline : s.serverOffline),",
    # NEW: ternary tree — online shows latency if available
    "                _waking\n"
    "                  ? s.waking\n"
    "                  : _serverUp\n"
    "                    ? (_latencyMs != null\n"
    "                        ? '${s.serverOnline} \u00b7 ${_latencyMs}ms'\n"
    "                        : s.serverOnline)\n"
    "                    : s.serverOffline,",
    label="C5: latency shown in server banner",
    skip_if="${_latencyMs}ms",
    debug_hint="? s.waking",
)


# ═══════════════════════════════════════════════════════════════════════════
# P7 — history_screen.dart
#      D: show original_name if available, else fall back to buildFilename
# ═══════════════════════════════════════════════════════════════════════════
print("\n[P7] history_screen.dart — original_name in job card")

HIST = REPO / "lib/screens/history_screen.dart"

patch(HIST,
    # OLD: exact from dump lines 25632-25636 (14-space indent)
    "              Text(ApiService.buildFilename(engine),\n"
    "                maxLines: 1, overflow: TextOverflow.ellipsis,\n"
    "                style: const TextStyle(\n"
    "                  color: Color(0xFFC9D1D9), fontSize: 11,\n"
    "                  fontWeight: FontWeight.bold)),",
    # NEW: show original_name first, fall back
    "              Text(\n"
    "                job['original_name'] as String?\n"
    "                  ?? ApiService.buildFilename(engine),\n"
    "                maxLines: 1, overflow: TextOverflow.ellipsis,\n"
    "                style: const TextStyle(\n"
    "                  color: Color(0xFFC9D1D9), fontSize: 11,\n"
    "                  fontWeight: FontWeight.bold)),",
    label="D: original_name in history job card",
    skip_if="job['original_name'] as String?",
    debug_hint="Text(ApiService.buildFilename(engine)",
)


# ═══════════════════════════════════════════════════════════════════════════
# BONUS: verify T1 successes that future patches depend on
# (print status but don't count as failures if missing — they may not exist
#  in edge-case repo states; the build will simply warn at compile time)
# ═══════════════════════════════════════════════════════════════════════════
print("\n[CHECK] Verifying T1 prerequisites in api_service.dart...")
api_text = API.read_text(encoding="utf-8") if API.exists() else ""
for sym, desc in [
    ("checkServer()", "checkServer() method"),
    ("shareAudio(",   "shareAudio() method"),
    ("saveLastEngine(", "saveLastEngine() method"),
    ("loadLastEngine(", "loadLastEngine() method"),
]:
    if sym in api_text:
        print(f"{OK}  [api_service.dart] {desc} present")
    else:
        print(f"{WARN} [api_service.dart] {desc} MISSING — re-run patch_qol2_s28.py or add manually")

print("\n[CHECK] Verifying T1 prerequisites in home_screen.dart...")
home_text = HOME.read_text(encoding="utf-8") if HOME.exists() else ""
for sym, desc in [
    ("int?    _latencyMs",           "_latencyMs state var"),
    ("ApiService.loadLastEngine()",  "loadLastEngine in initState"),
    ("Future<void> _shareFile()",    "_shareFile() method"),
    ("_output?.path.startsWith('content://')", "share button in result card"),
]:
    if sym in home_text:
        print(f"{OK}  [home_screen.dart] {desc} present")
    else:
        print(f"{WARN} [home_screen.dart] {desc} MISSING — run patch_qol2_s28.py first")

print("\n[CHECK] Verifying shareBtn in lang_provider.dart...")
lang = REPO / "lib/state/lang_provider.dart"
if lang.exists() and "shareBtn" in lang.read_text(encoding="utf-8"):
    print(f"{OK}  [lang_provider.dart] shareBtn present")
else:
    print(f"{WARN} [lang_provider.dart] shareBtn MISSING — run patch_qol2_s28.py first")


# ═══════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL 7 PATCHES APPLIED (or already present) \033[0m")
    print()
    print("Next:")
    print("  git add lib/services/api_service.dart \\")
    print("          lib/screens/home_screen.dart \\")
    print("          lib/screens/history_screen.dart")
    print("  git commit -m 'S28-T3: fix remaining 7 patches'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} PATCH(ES) STILL FAILING — check WARN + debug lines above \033[0m")
    sys.exit(1)
