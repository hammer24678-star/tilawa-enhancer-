#!/usr/bin/env python3
"""
patch_qol_s28.py — Session 28: Tier 1 Quality of Life Features

Run from ~/tilawa-enhancer/ then git push.

Features:
  1. Cancel button during processing
  2. "Process Another File" button in result card
  3. Tap metrics row to copy to clipboard
  4. Haptic feedback on Process button (+ Cancel)
  5. Estimated wait time in file card
  6. History: "Clear All" button with confirmation dialog
  7. Privacy policy link in Settings > About
  8. Fix engineNames map (v9.0, v8.9, v8.5 were missing labels)

Modified files:
  lib/services/api_service.dart      — clearAllJobRecords()
  lib/state/lang_provider.dart       — 7 new strings
  lib/screens/home_screen.dart       — features 1-5, 8
  lib/screens/history_screen.dart    — feature 6
  lib/screens/settings_screen.dart   — feature 7
"""

from pathlib import Path
import sys

REPO = Path(".")

# ── Colours for terminal output ───────────────────────────────────────────────
OK   = "\033[92m OK  \033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"

def patch(path: Path, old: str, new: str, label: str = "") -> bool:
    if not path.exists():
        print(f"{ERR} [{path}] file not found")
        return False
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label or old[:55]!r}")
        return False
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"{OK}  [{path.name}] {label or old[:50].strip()!r}")
    return True

errors = 0

# ═══════════════════════════════════════════════════════════════════════════════
# 1. api_service.dart — add clearAllJobRecords()
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[1/5] api_service.dart")

API = REPO / "lib/services/api_service.dart"

ok = patch(API,
    '  // ── Build proper download filename ─────────────────────────────────────',
    '''  /// Remove ALL saved job records (used by History "Clear All").
  static Future<void> clearAllJobRecords() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.remove(_jobsKey);
    } catch (_) {}
  }

  // ── Build proper download filename ─────────────────────────────────────''',
    "clearAllJobRecords()")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# 2. lang_provider.dart — add S28 strings
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[2/5] lang_provider.dart")

LANG = REPO / "lib/state/lang_provider.dart"

ok = patch(LANG,
    '  // Welcome',
    '''  // S28: QoL strings
  String get cancelBtn      => ar ? '\u0625\u0644\u063a\u0627\u0621'                          : 'Cancel';
  String get processAnother => ar ? '\u0645\u0639\u0627\u0644\u062c\u0629 \u0645\u0644\u0641 \u0622\u062e\u0631'               : 'Process Another File';
  String get clearAll       => ar ? '\u0645\u0633\u062d \u0627\u0644\u0643\u0644'                     : 'Clear All';
  String get clearAllConfirm=> ar ? '\u062d\u0630\u0641 \u0633\u062c\u0644 \u0627\u0644\u0645\u0644\u0641\u0627\u062a \u0643\u0627\u0645\u0644\u0627\u064b\u061f'        : 'Delete all history?';
  String get copiedMetrics  => ar ? '\u062a\u0645 \u0646\u0633\u062e \u0627\u0644\u0642\u064a\u0627\u0633\u0627\u062a'              : 'Metrics copied';
  String get estTime        => ar ? '\u0648\u0642\u062a \u0645\u0642\u062f\u0631'                     : 'Est.';
  String get privacyPolicy  => ar ? '\u0633\u064a\u0627\u0633\u0629 \u0627\u0644\u062e\u0635\u0648\u0635\u064a\u0629'               : 'Privacy Policy';

  // Welcome''',
    "7 S28 QoL strings")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# 3. home_screen.dart — 6 patches
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[3/5] home_screen.dart")

HOME = REPO / "lib/screens/home_screen.dart"

# 3a. Add flutter/services import (needed for HapticFeedback + Clipboard)
ok = patch(HOME,
    "import 'dart:async';\nimport 'package:flutter/material.dart';",
    "import 'dart:async';\nimport 'package:flutter/material.dart';\nimport 'package:flutter/services.dart';",
    "add flutter/services.dart import")
if not ok: errors += 1

# 3b. Add _fileBytes state variable
ok = patch(HOME,
    "  int     _pollErrors = 0;     // S22: consecutive poll error counter",
    "  int     _pollErrors = 0;     // S22: consecutive poll error counter\n  int     _fileBytes  = 0;     // S28: file size in bytes for estimated time",
    "add _fileBytes state var")
if not ok: errors += 1

# 3c. Store _fileBytes when file is picked
ok = patch(HOME,
    "        _isLarge = bytes > 8 * 1024 * 1024;",
    "        _isLarge = bytes > 8 * 1024 * 1024;\n        _fileBytes = bytes;",
    "store _fileBytes in _pickFile")
if not ok: errors += 1

# 3d. Add haptic feedback at start of _process()
ok = patch(HOME,
    "    if (_file == null || !_serverUp) return;\n    setState(() {\n      _busy = true; _progress = 0.02;",
    "    if (_file == null || !_serverUp) return;\n    HapticFeedback.mediumImpact();\n    setState(() {\n      _busy = true; _progress = 0.02;",
    "haptic feedback in _process()")
if not ok: errors += 1

# 3e. Add _cancelProcessing() + _resetForNewFile() after _wakeServer()
ok = patch(HOME,
    "  // ── File picker ────────────────────────────────────────────────────────────\n  Future<void> _pickFile() async {",
    '''  // ── S28: Cancel processing ────────────────────────────────────────────────
  void _cancelProcessing() {
    _pollTimer?.cancel();
    HapticFeedback.mediumImpact();
    setState(() {
      _busy = false; _progress = 0;
      _status = ''; _isMerging = false;
      _jobId = null;
    });
  }

  // ── S28: Reset for new file ────────────────────────────────────────────────
  void _resetForNewFile() {
    setState(() {
      _file = null; _result = null; _output = null;
      _progress = 0; _status = '';
      _jobId = null; _busy = false;
      _isMerging = false; _sizeLabel = '';
      _isLarge = false; _fileBytes = 0;
    });
  }

  // ── File picker ────────────────────────────────────────────────────────────
  Future<void> _pickFile() async {''',
    "_cancelProcessing() + _resetForNewFile()")
if not ok: errors += 1

# 3f. Add _copyMetrics() + _estimatedTime() before BUILD
ok = patch(HOME,
    "  // ── BUILD ──────────────────────────────────────────────────────────────────\n  @override\n  Widget build",
    '''  // ── S28: Copy metrics to clipboard ───────────────────────────────────────
  Future<void> _copyMetrics() async {
    if (_result == null) return;
    HapticFeedback.lightImpact();
    final parts = <String>[];
    if (_result!['score'] != null) parts.add('Score: ${_result!['score']}/100');
    if (_result!['lufs']  != null) parts.add('LUFS: ${_result!['lufs']}');
    if (_result!['rms']   != null) parts.add('RMS: ${_result!['rms']}');
    if (_result!['crest'] != null) parts.add('Crest: ${_result!['crest']}');
    if (_result!['lra']   != null) parts.add('LRA: ${_result!['lra']}');
    parts.add('Engine: $_engine');
    await Clipboard.setData(ClipboardData(text: parts.join('  |  ')));
    if (mounted) {
      final s = LangProvider.strings(context);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(s.copiedMetrics),
        backgroundColor: const Color(0xFF1A1500),
        duration: const Duration(seconds: 2),
      ));
    }
  }

  // ── S28: Estimated processing time ────────────────────────────────────────
  String _estimatedTime() {
    final mb = _fileBytes / 1024 / 1024;
    if (mb < 5)  return '~1 min';
    if (mb < 15) return '~2-3 min';
    if (mb < 30) return '~4-6 min';
    if (mb < 50) return '~7-10 min';
    return '~10-20 min';
  }

  // ── BUILD ──────────────────────────────────────────────────────────────────
  @override
  Widget build''',
    "_copyMetrics() + _estimatedTime()")
if not ok: errors += 1

# 3g. Fix engineNames map — v9.0, v8.9, v8.5 were missing proper labels
ok = patch(HOME,
    """    const engineNames = {
      'v8.4': 'Source Tier Intelligence',
      'v8.0': 'Calibrated Precision',
      'v7.0': 'Classic',
    };""",
    """    const engineNames = {
      'v9.0': 'The Evolution',
      'v8.9': 'Soft Tiers + LPC',
      'v8.5': 'Honest Ceiling',
      'v8.4': 'Source Tier Intelligence',
      'v8.0': 'Calibrated Precision',
      'v7.0': 'Classic',
    };""",
    "fix engineNames (add v9.0, v8.9, v8.5)")
if not ok: errors += 1

# 3h. Add estimated time in _fileCard (after size/chunked badge row)
ok = patch(HOME,
    """            if (_isLarge) ...[
              const SizedBox(width: 8),
              _badge(s.chunkedBadge, 'gold'),
            ],
          ]),
        ],
        const SizedBox(height: 4),
        Text(s.sizeLimit,""",
    """            if (_isLarge) ...[
              const SizedBox(width: 8),
              _badge(s.chunkedBadge, 'gold'),
            ],
          ]),
          // S28: Estimated processing time
          if (_fileBytes > 0) ...[
            const SizedBox(height: 4),
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              const Icon(Icons.timer_outlined, size: 11,
                color: Color(0xFF484F58)),
              const SizedBox(width: 4),
              Text('${s.estTime}: ${_estimatedTime()}',
                style: const TextStyle(
                  color: Color(0xFF484F58), fontSize: 10)),
            ]),
          ],
        ],
        const SizedBox(height: 4),
        Text(s.sizeLimit,""",
    "estimated time in _fileCard")
if not ok: errors += 1

# 3i. Add cancel button in _progressCard (inside Column, after progress bar)
ok = patch(HOME,
    "          valueColor: const AlwaysStoppedAnimation(Color(0xFFD4AF37)))),\n    ]),\n  );",
    """          valueColor: const AlwaysStoppedAnimation(Color(0xFFD4AF37)))),
      // S28: Cancel button
      const SizedBox(height: 10),
      TextButton.icon(
        onPressed: _cancelProcessing,
        style: TextButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 4)),
        icon: const Icon(Icons.cancel_outlined, size: 16,
          color: Color(0xFF8B949E)),
        label: Text(s.cancelBtn,
          style: const TextStyle(color: Color(0xFF8B949E), fontSize: 12)),
      ),
    ]),
  );""",
    "cancel button in _progressCard")
if not ok: errors += 1

# 3j. Add "Process Another" button + replace _metricsRow() with tappable version
ok = patch(HOME,
    """        // Saved indicator
        if (_output != null) ...[
          const SizedBox(height: 8),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.check_circle_outline,
              color: Color(0xFF3FB950), size: 14),
            const SizedBox(width: 4),
            Text(s.savedTo,
              style: const TextStyle(
                color: Color(0xFF3FB950), fontSize: 11)),
          ]),
        ],
      ]),
    );
  }

  Widget _metricsRow() => Row(
    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
    children: [
      if (_result?['lufs']  != null) _metric('LUFS',  _result!['lufs'].toString()),
      if (_result?['rms']   != null) _metric('RMS',   _result!['rms'].toString()),
      if (_result?['crest'] != null) _metric('Crest', _result!['crest'].toString()),
      if (_result?['lra']   != null) _metric('LRA',   _result!['lra'].toString()),
    ],
  );""",
    """        // Saved indicator
        if (_output != null) ...[
          const SizedBox(height: 8),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.check_circle_outline,
              color: Color(0xFF3FB950), size: 14),
            const SizedBox(width: 4),
            Text(s.savedTo,
              style: const TextStyle(
                color: Color(0xFF3FB950), fontSize: 11)),
          ]),
        ],
        // S28: Process Another File button
        const SizedBox(height: 12),
        SizedBox(width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: _resetForNewFile,
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFF58A6FF),
              side: const BorderSide(color: Color(0xFF58A6FF), width: 0.8),
              padding: const EdgeInsets.symmetric(vertical: 10),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12))),
            icon: const Icon(Icons.add_circle_outline_rounded, size: 18),
            label: Text(s.processAnother,
              style: const TextStyle(fontSize: 13)),
          )),
      ]),
    );
  }

  // S28: Tappable metrics row — tap to copy all values to clipboard
  Widget _metricsRow() => InkWell(
    onTap: _copyMetrics,
    borderRadius: BorderRadius.circular(8),
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          if (_result?['lufs']  != null) _metric('LUFS',  _result!['lufs'].toString()),
          if (_result?['rms']   != null) _metric('RMS',   _result!['rms'].toString()),
          if (_result?['crest'] != null) _metric('Crest', _result!['crest'].toString()),
          if (_result?['lra']   != null) _metric('LRA',   _result!['lra'].toString()),
          const Icon(Icons.copy_rounded, size: 12, color: Color(0xFF484F58)),
        ],
      ),
    ),
  );""",
    '"Process Another" button + tappable _metricsRow()')
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# 4. history_screen.dart — Clear All button
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[4/5] history_screen.dart")

HIST = REPO / "lib/screens/history_screen.dart"

# 4a. Add _clearAll() method before build()
ok = patch(HIST,
    "  @override\n  Widget build(BuildContext context) {\n    final s = LangProvider.strings(context);\n    return Scaffold(\n      backgroundColor: const Color(0xFF0A0C10),\n      appBar: AppBar(",
    """  // S28: Clear All confirmation dialog
  Future<void> _clearAll() async {
    final s = LangProvider.strings(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14)),
        title: Text(s.clearAll,
          style: const TextStyle(color: Color(0xFFD4AF37))),
        content: Text(s.clearAllConfirm,
          style: const TextStyle(color: Color(0xFFC9D1D9))),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(s.ar ? '\u0644\u0627' : 'No',
              style: const TextStyle(color: Color(0xFF8B949E)))),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(s.ar ? '\u0627\u062d\u0630\u0641' : 'Delete',
              style: const TextStyle(color: Color(0xFFF85149)))),
        ]));
    if (confirmed == true && mounted) {
      await ApiService.clearAllJobRecords();
      setState(() => _jobs = []);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    return Scaffold(
      backgroundColor: const Color(0xFF0A0C10),
      appBar: AppBar(""",
    "_clearAll() method")
if not ok: errors += 1

# 4b. Add actions to AppBar in history_screen
ok = patch(HIST,
    "        iconTheme: const IconThemeData(color: Color(0xFFD4AF37)),\n        elevation: 0),",
    """        iconTheme: const IconThemeData(color: Color(0xFFD4AF37)),
        elevation: 0,
        actions: [
          if (_jobs.isNotEmpty)
            TextButton(
              onPressed: _clearAll,
              child: Text(s.clearAll,
                style: const TextStyle(
                  color: Color(0xFFF85149), fontSize: 12))),
        ]),""",
    "Clear All action in AppBar")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# 5. settings_screen.dart — Privacy policy link
# ═══════════════════════════════════════════════════════════════════════════════
print("\n[5/5] settings_screen.dart")

SETTINGS = REPO / "lib/screens/settings_screen.dart"

# 5a. Add url_launcher import
ok = patch(SETTINGS,
    "import 'package:flutter/material.dart';\nimport '../state/lang_provider.dart';",
    "import 'package:flutter/material.dart';\nimport 'package:url_launcher/url_launcher.dart';\nimport '../state/lang_provider.dart';",
    "add url_launcher import")
if not ok: errors += 1

# 5b. Add privacy policy link in About section (before final SizedBox(height:40))
ok = patch(SETTINGS,
    """              const Text('Yasser Al-Dossari \u00b7 1425H',
                style: TextStyle(
                  color: Color(0xFF484F58), fontSize: 11)),
            ])),
          const SizedBox(height: 40),""",
    """              const Text('Yasser Al-Dossari \u00b7 1425H',
                style: TextStyle(
                  color: Color(0xFF484F58), fontSize: 11)),
            ])),
          // S28: Privacy policy link
          const SizedBox(height: 12),
          GestureDetector(
            onTap: () => launchUrl(
              Uri.parse('https://profound-cactus-00498c.netlify.app/privacy_policy.html'),
              mode: LaunchMode.externalApplication),
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 12),
              child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                const Icon(Icons.privacy_tip_outlined,
                  color: Color(0xFF484F58), size: 14),
                const SizedBox(width: 6),
                Text(s.privacyPolicy,
                  style: const TextStyle(
                    color: Color(0xFF484F58),
                    fontSize: 12,
                    decoration: TextDecoration.underline,
                    decorationColor: Color(0xFF484F58))),
              ]))),
          const SizedBox(height: 40),""",
    "privacy policy link in About")
if not ok: errors += 1

# ═══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL PATCHES APPLIED SUCCESSFULLY \033[0m")
    print()
    print("Next steps:")
    print("  cd ~/tilawa-enhancer")
    print("  git add lib/services/api_service.dart \\")
    print("          lib/state/lang_provider.dart \\")
    print("          lib/screens/home_screen.dart \\")
    print("          lib/screens/history_screen.dart \\")
    print("          lib/screens/settings_screen.dart")
    print("  git commit -m 'S28: Tier 1 QoL features'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} PATCH(ES) FAILED — check WARN lines above \033[0m")
    print("Fix anchors for failed patches before pushing.")
    sys.exit(1)
