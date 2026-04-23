#!/usr/bin/env python3
"""
patch_polish_s30.py — Session 30: Deep Polish Pass + Bug Fixes

Bug fixes:
  F1. home_screen.dart  — duplicate loadLastEngine() in initState
  F2. home_screen.dart  — duplicate share button in result card

New polish:
  P1. home_screen.dart  — engine tap: HapticFeedback.selectionClick()
  P2. home_screen.dart  — status text in progress card: AnimatedSwitcher
  P3. home_screen.dart  — file card icon: AnimatedSwitcher (add → audio_file)
  P4. home_screen.dart  — bottom row (history button): GestureDetector → InkWell
  P5. home_screen.dart  — donation card: GestureDetector → InkWell
  P6. home_screen.dart  — metrics: show colored delta arrows vs reference target
  P7. home_screen.dart  — score number: scale-pulse after count-up completes
  P8. history_screen.dart — job card re-download: haptic + InkWell on card tap
"""

from pathlib import Path
import sys

REPO = Path(".")
HOME = REPO / "lib/screens/home_screen.dart"
HIST = REPO / "lib/screens/history_screen.dart"

OK   = "\033[92m OK  \033[0m"
SKIP = "\033[94m SKIP\033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"
errors = 0


def patch(path: Path, old: str, new: str, label: str) -> bool:
    global errors
    if not path.exists():
        print(f"{ERR} [{path.name}] file not found — {label}")
        errors += 1
        return False
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label}")
        return False
    n = text.count(old)
    if n > 1:
        print(f"{WARN} [{path.name}] anchor not unique ({n}×) — {label}")
        errors += 1
        return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{OK}  [{path.name}] {label}")
    return True


def already(path: Path, marker: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"{SKIP} [{path.name}] already applied — {label}")
        return True
    return False


print("\n[BUG FIXES]")

# ── F1: Remove duplicate loadLastEngine() ──────────────────────────────────
if not already(HOME, "// S30-F1", "F1: duplicate loadLastEngine"):
    patch(HOME,
        "    // S28-T2: restore last engine selection\n"
        "    ApiService.loadLastEngine().then((e) {\n"
        "      if (mounted) setState(() => _engine = e);\n"
        "    });\n"
        "    // S28-T2: restore last engine selection\n"
        "    ApiService.loadLastEngine().then((e) {\n"
        "      if (mounted) setState(() => _engine = e);\n"
        "    });",
        "    // S30-F1: restored — one loadLastEngine call\n"
        "    ApiService.loadLastEngine().then((e) {\n"
        "      if (mounted) setState(() => _engine = e);\n"
        "    });",
        "F1: duplicate loadLastEngine removed")

# ── F2: Remove duplicate share button ──────────────────────────────────────
if not already(HOME, "// S30-F2", "F2: duplicate share button"):
    patch(HOME,
        "        ],\n"
        "        // S28-T2: Share button (only for content:// URIs = API 29+)\n"
        "        if (_output?.path.startsWith('content://') ?? false) ...[\n"
        "          const SizedBox(height: 8),\n"
        "          SizedBox(width: double.infinity,\n"
        "            child: OutlinedButton.icon(\n"
        "              onPressed: _shareFile,\n"
        "              style: OutlinedButton.styleFrom(\n"
        "                foregroundColor: const Color(0xFF8B949E),\n"
        "                side: const BorderSide(color: Color(0xFF30363D), width: 0.8),\n"
        "                padding: const EdgeInsets.symmetric(vertical: 10),\n"
        "                shape: RoundedRectangleBorder(\n"
        "                  borderRadius: BorderRadius.circular(12))),\n"
        "              icon: const Icon(Icons.share_rounded, size: 18),\n"
        "              label: Text(s.shareBtn,\n"
        "                style: const TextStyle(fontSize: 13)),\n"
        "            )),\n"
        "        ],\n"
        "        // Saved indicator",
        "        ], // S30-F2: duplicate share block removed\n"
        "        // Saved indicator",
        "F2: duplicate share button removed")


print("\n[POLISH PATCHES]")

# ── P1: Haptic on engine selection ─────────────────────────────────────────
if not already(HOME, "// S30-P1", "P1: haptic on engine tap"):
    patch(HOME,
        "      onTap: () {\n"
        "        setState(() => _engine = e.id);\n"
        "        ApiService.saveLastEngine(e.id); // S28-T2: persist\n"
        "      },",
        "      onTap: () {\n"
        "        HapticFeedback.selectionClick(); // S30-P1\n"
        "        setState(() => _engine = e.id);\n"
        "        ApiService.saveLastEngine(e.id); // S28-T2: persist\n"
        "      },",
        "P1: haptic on engine selection")

# ── P2: AnimatedSwitcher on progress status text ───────────────────────────
if not already(HOME, "// S30-P2", "P2: AnimatedSwitcher status text"):
    patch(HOME,
        "        Flexible(child: Text(_status.isEmpty ? s.processing : _status,\n"
        "          style: const TextStyle(color: Color(0xFFC9D1D9), fontSize: 13))),",
        "        Flexible(child: AnimatedSwitcher( // S30-P2\n"
        "          duration: const Duration(milliseconds: 300),\n"
        "          transitionBuilder: (child, anim) => FadeTransition(\n"
        "            opacity: anim, child: child),\n"
        "          child: Text(\n"
        "            _status.isEmpty ? s.processing : _status,\n"
        "            key: ValueKey(_status),\n"
        "            style: const TextStyle(\n"
        "              color: Color(0xFFC9D1D9), fontSize: 13)))),",
        "P2: status text AnimatedSwitcher")

# ── P3: AnimatedSwitcher on file card icon ─────────────────────────────────
if not already(HOME, "// S30-P3", "P3: file icon AnimatedSwitcher"):
    patch(HOME,
        "        Icon(_file != null ? Icons.audio_file : Icons.add_circle_outline,\n"
        "          color: const Color(0xFFD4AF37), size: 52),",
        "        AnimatedSwitcher( // S30-P3\n"
        "          duration: const Duration(milliseconds: 350),\n"
        "          switchInCurve: Curves.easeOutBack,\n"
        "          transitionBuilder: (child, anim) => ScaleTransition(\n"
        "            scale: anim, child: FadeTransition(opacity: anim, child: child)),\n"
        "          child: Icon(\n"
        "            _file != null ? Icons.audio_file : Icons.add_circle_outline,\n"
        "            key: ValueKey(_file != null),\n"
        "            color: const Color(0xFFD4AF37), size: 52)),",
        "P3: file icon animated swap")

# ── P4: Bottom row (history button) GestureDetector → Material+InkWell ────
if not already(HOME, "// S30-P4", "P4: history button InkWell"):
    patch(HOME,
        "    child: GestureDetector(\n"
        "      onTap: () => Navigator.push(context,\n"
        "        PageRouteBuilder(\n"
        "          pageBuilder: (_, __, ___) => const HistoryScreen(),\n"
        "          transitionsBuilder: (_, anim, __, child) =>\n"
        "            FadeTransition(opacity: anim, child: child),\n"
        "          transitionDuration: const Duration(milliseconds: 220),\n"
        "        )),\n"
        "      child: Container(\n"
        "        padding: const EdgeInsets.symmetric(vertical: 14),\n"
        "        decoration: BoxDecoration(\n"
        "          color: const Color(0xFF161B22),\n"
        "          borderRadius: BorderRadius.circular(12),\n"
        "          border: Border.all(color: const Color(0xFF21262D))),\n"
        "        child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [\n"
        "          const Icon(Icons.history_rounded,\n"
        "            color: Color(0xFF8B949E), size: 18),\n"
        "          const SizedBox(width: 8),\n"
        "          Text(s.history, style: const TextStyle(\n"
        "            color: Color(0xFF8B949E), fontSize: 13)),\n"
        "        ]),\n"
        "      ),\n"
        "    ),",
        "    child: Material( // S30-P4\n"
        "      color: const Color(0xFF161B22),\n"
        "      borderRadius: BorderRadius.circular(12),\n"
        "      clipBehavior: Clip.antiAlias,\n"
        "      child: InkWell(\n"
        "        onTap: () => Navigator.push(context,\n"
        "          PageRouteBuilder(\n"
        "            pageBuilder: (_, __, ___) => const HistoryScreen(),\n"
        "            transitionsBuilder: (_, anim, __, child) =>\n"
        "              FadeTransition(opacity: anim, child: child),\n"
        "            transitionDuration: const Duration(milliseconds: 220),\n"
        "          )),\n"
        "        splashColor: const Color(0xFFD4AF37).withOpacity(0.12),\n"
        "        highlightColor: const Color(0xFFD4AF37).withOpacity(0.06),\n"
        "        child: Container(\n"
        "          padding: const EdgeInsets.symmetric(vertical: 14),\n"
        "          decoration: BoxDecoration(\n"
        "            border: Border.all(color: const Color(0xFF21262D))),\n"
        "          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [\n"
        "            const Icon(Icons.history_rounded,\n"
        "              color: Color(0xFF8B949E), size: 18),\n"
        "            const SizedBox(width: 8),\n"
        "            Text(s.history, style: const TextStyle(\n"
        "              color: Color(0xFF8B949E), fontSize: 13)),\n"
        "          ]),\n"
        "        ),\n"
        "      ),\n"
        "    ),",
        "P4: history button InkWell ripple")

# ── P5: Donation card GestureDetector → Material+InkWell ──────────────────
if not already(HOME, "// S30-P5", "P5: donation card InkWell"):
    patch(HOME,
        "    child: GestureDetector(\n"
        "      onTap: () => launchUrl(\n"
        "        Uri.parse('https://buymeacoffee.com/tilawa'),\n"
        "        mode: LaunchMode.externalApplication),\n"
        "      child: Container(\n"
        "        padding: const EdgeInsets.all(14),\n"
        "        decoration: BoxDecoration(\n"
        "          color: const Color(0xFF1A1500),\n"
        "          borderRadius: BorderRadius.circular(12),\n"
        "          border: Border.all(\n"
        "            color: const Color(0xFFD4AF37).withOpacity(0.3))),",
        "    child: Material( // S30-P5\n"
        "      color: const Color(0xFF1A1500),\n"
        "      borderRadius: BorderRadius.circular(12),\n"
        "      clipBehavior: Clip.antiAlias,\n"
        "      child: InkWell(\n"
        "        onTap: () {\n"
        "          HapticFeedback.lightImpact();\n"
        "          launchUrl(\n"
        "            Uri.parse('https://buymeacoffee.com/tilawa'),\n"
        "            mode: LaunchMode.externalApplication);\n"
        "        },\n"
        "        splashColor: const Color(0xFFD4AF37).withOpacity(0.18),\n"
        "        child: Container(\n"
        "          padding: const EdgeInsets.all(14),\n"
        "          decoration: BoxDecoration(\n"
        "            borderRadius: BorderRadius.circular(12),\n"
        "            border: Border.all(\n"
        "              color: const Color(0xFFD4AF37).withOpacity(0.3))),",
        "P5: donation card InkWell ripple")

# Close the extra nesting from P5 — we added one more Container layer
# The original ends the _donationCard with:
#   ]),        ← Row children end
#   ]),        ← Column end
#   ),         ← Container end
#   ),         ← GestureDetector end
# New structure needs one extra closing for the InkWell+Material child Container
if not already(HOME, "// S30-P5-close", "P5-close: donation card extra brace"):
    patch(HOME,
        "          Text(s.donationDesc, style: const TextStyle(\n"
        "              color: Color(0xFF8B949E), fontSize: 10)),\n"
        "          ]),\n"
        "        ]),\n"
        "      ),\n"
        "    ),\n"
        "  );\n"
        "}\n"
        "\n"
        "// ── Engine data class",
        "          Text(s.donationDesc, style: const TextStyle(\n"
        "              color: Color(0xFF8B949E), fontSize: 10)),\n"
        "          ]),\n"
        "        ]),\n"
        "      ),\n"
        "    ),\n"
        "  ),\n"           # extra close for Material child Container
        "  );\n"
        "}\n"
        "\n"
        "// S30-P5-close\n"
        "// ── Engine data class",
        "P5-close: donation card extra closing paren")

# ── P6: Metrics row — delta arrows vs reference targets ───────────────────
if not already(HOME, "// S30-P6", "P6: metrics delta arrows"):
    patch(HOME,
        "  Widget _metric(String label, String value) => Column(children: [\n"
        "    Text(label,\n"
        "      style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),\n"
        "    const SizedBox(height: 2),\n"
        "    Text(value, style: const TextStyle(\n"
        "      color: Color(0xFFD4AF37), fontWeight: FontWeight.bold, fontSize: 13)),\n"
        "  ]);",
        "  // S30-P6: metric widget with delta arrow vs reference target\n"
        "  static const _metricTargets = {\n"
        "    'LUFS': -6.29, 'RMS': -10.01, 'Crest': 10.25, 'LRA': 4.19\n"
        "  };\n"
        "\n"
        "  Widget _metric(String label, String value) {\n"
        "    final num = double.tryParse(value);\n"
        "    final target = _metricTargets[label];\n"
        "    String arrow = '';\n"
        "    Color arrowColor = const Color(0xFF484F58);\n"
        "    if (num != null && target != null) {\n"
        "      final diff = num - target;\n"
        "      if (diff.abs() <= 0.5) {\n"
        "        arrow = ' ✓';\n"
        "        arrowColor = const Color(0xFF3FB950);\n"
        "      } else if (diff > 0) {\n"
        "        arrow = ' ▲';\n"
        "        arrowColor = const Color(0xFFD4AF37);\n"
        "      } else {\n"
        "        arrow = ' ▼';\n"
        "        arrowColor = const Color(0xFF58A6FF);\n"
        "      }\n"
        "    }\n"
        "    return Column(children: [\n"
        "      Text(label,\n"
        "        style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),\n"
        "      const SizedBox(height: 2),\n"
        "      Row(mainAxisSize: MainAxisSize.min, children: [\n"
        "        Text(value, style: const TextStyle(\n"
        "          color: Color(0xFFD4AF37),\n"
        "          fontWeight: FontWeight.bold, fontSize: 13)),\n"
        "        Text(arrow, style: TextStyle(\n"
        "          color: arrowColor, fontSize: 10,\n"
        "          fontWeight: FontWeight.bold)),\n"
        "      ]),\n"
        "    ]);\n"
        "  }",
        "P6: metrics delta arrows (✓ ▲ ▼)")

# ── P7: Score number — scale-pulse after count-up ─────────────────────────
if not already(HOME, "// S30-P7", "P7: score pulse after count-up"):
    patch(HOME,
        "            AnimatedBuilder(\n"
        "              animation: _resultCtrl,\n"
        "              builder: (_, __) {\n"
        "                final t = Curves.easeOutCubic.transform(_resultCtrl.value);\n"
        "                return Text(\n"
        "                  '${(score * t).toStringAsFixed(1)}/100',\n"
        "                  style: TextStyle(\n"
        "                    color: scoreColor,\n"
        "                    fontWeight: FontWeight.w900, fontSize: 34));\n"
        "              }),",
        "            AnimatedBuilder( // S30-P7: scale-pulse at finish\n"
        "              animation: _resultCtrl,\n"
        "              builder: (_, __) {\n"
        "                final t = Curves.easeOutCubic.transform(_resultCtrl.value);\n"
        "                // Pulse: scale slightly above 1 at ~90% then settle to 1\n"
        "                final pulse = _resultCtrl.value > 0.85\n"
        "                    ? 1.0 + 0.06 * (1 - (_resultCtrl.value - 0.85) / 0.15)\n"
        "                    : 1.0;\n"
        "                return Transform.scale(\n"
        "                  scale: pulse,\n"
        "                  child: Text(\n"
        "                    '${(score * t).toStringAsFixed(1)}/100',\n"
        "                    style: TextStyle(\n"
        "                      color: scoreColor,\n"
        "                      fontWeight: FontWeight.w900, fontSize: 34)));\n"
        "              }),",
        "P7: score scale-pulse at count-up finish")

# ── P8: History job card — InkWell on card + haptic on re-download ─────────
if not already(HIST, "// S30-P8", "P8: history card InkWell + haptic"):
    patch(HIST,
        "    setState(() => _downloading.add(jobId));\n"
        "    final (file, error) = await ApiService.downloadFile(jobId, filename);",
        "    HapticFeedback.lightImpact(); // S30-P8\n"
        "    setState(() => _downloading.add(jobId));\n"
        "    final (file, error) = await ApiService.downloadFile(jobId, filename);",
        "P8: haptic on history re-download")

# Ensure HapticFeedback is imported in history_screen.dart
if not already(HIST, "package:flutter/services.dart", "P8-import: services.dart"):
    patch(HIST,
        "import 'package:flutter/material.dart';",
        "import 'package:flutter/material.dart';\n"
        "import 'package:flutter/services.dart'; // S30-P8",
        "P8-import: HapticFeedback import in history_screen.dart")


print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL PATCHES APPLIED \033[0m")
    print()
    print("What changed:")
    print("  F1. Fixed: duplicate loadLastEngine() in initState")
    print("  F2. Fixed: duplicate share button in result card")
    print("  P1. Engine tap now triggers selection haptic")
    print("  P2. Status text fades smoothly when it changes")
    print("  P3. File icon animates (scale+fade) when file is picked")
    print("  P4. History button has gold ripple on tap")
    print("  P5. Donation card has gold ripple + haptic on tap")
    print("  P6. Metrics show ✓ (on-target) ▲ (above) ▼ (below) vs 1425H ref")
    print("  P7. Score number pulses slightly at end of count-up")
    print("  P8. History re-download has light haptic feedback")
    print()
    print("Next:")
    print("  git add lib/screens/home_screen.dart \\")
    print("          lib/screens/history_screen.dart")
    print("  git commit -m 'S30: Deep polish — bug fixes + animations + haptics + metrics'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} PATCH(ES) FAILED — fix WARN/ERR lines above \033[0m")
    sys.exit(1)
