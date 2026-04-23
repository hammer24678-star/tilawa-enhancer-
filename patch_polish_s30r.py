#!/usr/bin/env python3
"""
patch_polish_s30r.py — S30 Result + UI Polish

Fixes:
  S.  Server banner: literal \${} text → proper Dart interpolation

Result card changes:
  R1. Score arc gauge (CustomPaint 270°) replaces flat badge+number row
  R2. Metric 2×2 grid replaces flat row + dangling target-text line
  R3. Open/Share buttons → single side-by-side row
  R4. Thin divider between score section and action buttons

Extra:
  X1. "Process Another" icon: add_circle_outline → refresh_rounded
"""

from pathlib import Path
import sys

REPO = Path(".")
HOME = REPO / "lib/screens/home_screen.dart"

OK   = "\033[92m OK  \033[0m"
SKIP = "\033[94m SKIP\033[0m"
WARN = "\033[93m WARN\033[0m"
ERR  = "\033[91m ERR \033[0m"
errors = 0

def patch(path: Path, old: str, new: str, label: str) -> bool:
    global errors
    if not path.exists():
        print(f"{ERR} [{path.name}] file not found — {label}"); errors += 1; return False
    text = path.read_text(encoding="utf-8")
    if old not in text:
        print(f"{WARN} [{path.name}] anchor not found — {label}"); return False
    n = text.count(old)
    if n > 1:
        print(f"{WARN} [{path.name}] anchor not unique ({n}×) — {label}"); errors += 1; return False
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{OK}  [{path.name}] {label}")
    return True

def already(path: Path, marker: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if marker in text:
        print(f"{SKIP} [{path.name}] already applied — {label}")
        return True
    return False

# ═══════════════════════════════════════════════════════════════════════════
print("\n[S] Server banner — fix literal \\${} strings")
# ═══════════════════════════════════════════════════════════════════════════

if not already(HOME, "// S30-S", "S: server banner interpolation fix"):
    patch(HOME,
        "? '\\${s.serverOnline} · \\${_latencyMs}ms'",
        "'${s.serverOnline} · ${_latencyMs}ms' // S30-S",
        "S: server banner text interpolation fixed")

# ═══════════════════════════════════════════════════════════════════════════
print("\n[R1] Score arc gauge — dart:math import + CustomPaint painter")
# ═══════════════════════════════════════════════════════════════════════════

if not already(HOME, "dart:math", "R1-import: dart:math already present"):
    patch(HOME,
        "import 'dart:async';",
        "import 'dart:async';\n"
        "import 'dart:math' show pi; // S30-R1",
        "R1-import: dart:math show pi")

if not already(HOME, "_ScoreArcPainter", "R1-class: _ScoreArcPainter"):
    patch(HOME,
        "\n// ── Engine data class (S21: rich model — score, features, what's-new) ───────────\n"
        "class _EngineData {",
        "\n"
        "// ── S30-R1: Score arc painter ──────────────────────────────────────────────────\n"
        "class _ScoreArcPainter extends CustomPainter {\n"
        "  final double progress;\n"
        "  final double score;\n"
        "  final Color  color;\n"
        "  const _ScoreArcPainter({\n"
        "    required this.progress,\n"
        "    required this.score,\n"
        "    required this.color,\n"
        "  });\n"
        "\n"
        "  @override\n"
        "  void paint(Canvas canvas, Size size) {\n"
        "    final c = Offset(size.width / 2, size.height / 2);\n"
        "    final r = size.width / 2 - 12.0;\n"
        "    const start = pi * 0.75;   // 135° — bottom-left\n"
        "    const sweep = pi * 1.5;    // 270° arc\n"
        "\n"
        "    // Background track\n"
        "    canvas.drawArc(\n"
        "      Rect.fromCircle(center: c, radius: r),\n"
        "      start, sweep, false,\n"
        "      Paint()\n"
        "        ..color = const Color(0xFF21262D)\n"
        "        ..style = PaintingStyle.stroke\n"
        "        ..strokeWidth = 12\n"
        "        ..strokeCap = StrokeCap.round,\n"
        "    );\n"
        "\n"
        "    // Score fill\n"
        "    if (progress > 0.01) {\n"
        "      canvas.drawArc(\n"
        "        Rect.fromCircle(center: c, radius: r),\n"
        "        start, sweep * (score / 100) * progress, false,\n"
        "        Paint()\n"
        "          ..color = color\n"
        "          ..style = PaintingStyle.stroke\n"
        "          ..strokeWidth = 12\n"
        "          ..strokeCap = StrokeCap.round,\n"
        "      );\n"
        "    }\n"
        "  }\n"
        "\n"
        "  @override\n"
        "  bool shouldRepaint(_ScoreArcPainter o) =>\n"
        "      o.progress != progress || o.color != color;\n"
        "}\n"
        "\n"
        "// ── Engine data class (S21: rich model — score, features, what's-new) ───────────\n"
        "class _EngineData {",
        "R1-class: _ScoreArcPainter added")

# Replace score Row (badge + number) with arc widget
if not already(HOME, "// S30-R1: score arc", "R1-widget: score arc already in result card"):
    patch(HOME,
        "        // Score\n"
        "        Row(\n"
        "          mainAxisAlignment: MainAxisAlignment.center,\n"
        "          crossAxisAlignment: CrossAxisAlignment.baseline,\n"
        "          textBaseline: TextBaseline.alphabetic,\n"
        "          children: [\n"
        "            // S29: label as badge\n"
        "            Container(\n"
        "              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),\n"
        "              decoration: BoxDecoration(\n"
        "                color: scoreColor.withOpacity(0.15),\n"
        "                borderRadius: BorderRadius.circular(20),\n"
        "                border: Border.all(color: scoreColor.withOpacity(0.4))),\n"
        "              child: Text(label, style: TextStyle(\n"
        "                color: scoreColor,\n"
        "                fontWeight: FontWeight.bold, fontSize: 13))),\n"
        "            const SizedBox(width: 12),\n"
        "            // S29: score counts up with result animation\n"
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
        "              }),\n"
        "          ]),\n"
        "        const SizedBox(height: 12),",
        "        // S30-R1: score arc gauge\n"
        "        AnimatedBuilder(\n"
        "          animation: _resultCtrl,\n"
        "          builder: (_, __) {\n"
        "            final t = Curves.easeOutCubic.transform(_resultCtrl.value);\n"
        "            final pulse = _resultCtrl.value > 0.85\n"
        "                ? 1.0 + 0.05 * (1 - (_resultCtrl.value - 0.85) / 0.15)\n"
        "                : 1.0;\n"
        "            return Column(mainAxisSize: MainAxisSize.min, children: [\n"
        "              SizedBox(\n"
        "                width: 148, height: 148,\n"
        "                child: CustomPaint(\n"
        "                  painter: _ScoreArcPainter(\n"
        "                    progress: t, score: score, color: scoreColor),\n"
        "                  child: Center(child: Column(\n"
        "                    mainAxisSize: MainAxisSize.min,\n"
        "                    children: [\n"
        "                      Transform.scale(\n"
        "                        scale: pulse,\n"
        "                        child: Text(\n"
        "                          '${(score * t).toStringAsFixed(1)}',\n"
        "                          style: TextStyle(\n"
        "                            color: scoreColor,\n"
        "                            fontWeight: FontWeight.w900,\n"
        "                            fontSize: 40,\n"
        "                            letterSpacing: -1))),\n"
        "                      Text('/100', style: TextStyle(\n"
        "                        color: scoreColor.withOpacity(0.55),\n"
        "                        fontSize: 12,\n"
        "                        fontWeight: FontWeight.bold)),\n"
        "                    ])),\n"
        "                )),\n"
        "              const SizedBox(height: 10),\n"
        "              Container(\n"
        "                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),\n"
        "                decoration: BoxDecoration(\n"
        "                  color: scoreColor.withOpacity(0.15),\n"
        "                  borderRadius: BorderRadius.circular(20),\n"
        "                  border: Border.all(color: scoreColor.withOpacity(0.4))),\n"
        "                child: Text(label, style: TextStyle(\n"
        "                  color: scoreColor,\n"
        "                  fontWeight: FontWeight.bold,\n"
        "                  fontSize: 13, letterSpacing: 0.5))),\n"
        "            ]);\n"
        "          }),\n"
        "        const SizedBox(height: 14),",
        "R1-widget: score arc in result card")

# ═══════════════════════════════════════════════════════════════════════════
print("\n[R2] Metric 2×2 grid")
# ═══════════════════════════════════════════════════════════════════════════

# Replace the call site: _metricsRow() + target text → _metricGrid()
if not already(HOME, "_metricGrid()", "R2-call: _metricGrid call already present"):
    patch(HOME,
        "        // Metrics (with target deltas)\n"
        "        _metricsRow(),\n"
        "        const SizedBox(height: 6),\n"
        "\n"
        "        // Target reference line\n"
        "        Text(\n"
        "          s.ar\n"
        "            ? '\u0627\u0644\u0647\u062f\u0641: LUFS=-6.29 \xb7 RMS=-10.01 \xb7 Crest=10.25 \xb7 LRA=4.19'\n"
        "            : 'Target: LUFS=-6.29 \xb7 RMS=-10.01 \xb7 Crest=10.25 \xb7 LRA=4.19',\n"
        "          style: const TextStyle(color: Color(0xFF484F58), fontSize: 9)),\n"
        "        const SizedBox(height: 16),",
        "        // S30-R2: metrics 2\xd72 grid\n"
        "        _metricGrid(),\n"
        "        const SizedBox(height: 12),\n"
        "\n"
        "        // S30-R4: section divider\n"
        "        Container(height: 1,\n"
        "          color: const Color(0xFF21262D),\n"
        "          margin: const EdgeInsets.only(bottom: 14)),",
        "R2-call: _metricGrid + R4 divider")

# Replace _metricsRow + _metric methods with _metricGrid + _metricTile
if not already(HOME, "Widget _metricGrid()", "R2-method: _metricGrid method already present"):
    patch(HOME,
        "  // S28: Tappable metrics row — tap to copy all values to clipboard\n"
        "  Widget _metricsRow() => InkWell(\n"
        "    onTap: _copyMetrics,\n"
        "    borderRadius: BorderRadius.circular(8),\n"
        "    child: Padding(\n"
        "      padding: const EdgeInsets.symmetric(vertical: 6),\n"
        "      child: Row(\n"
        "        mainAxisAlignment: MainAxisAlignment.spaceEvenly,\n"
        "        children: [\n"
        "          if (_result?['lufs']  != null) _metric('LUFS',  _result!['lufs'].toString()),\n"
        "          if (_result?['rms']   != null) _metric('RMS',   _result!['rms'].toString()),\n"
        "          if (_result?['crest'] != null) _metric('Crest', _result!['crest'].toString()),\n"
        "          if (_result?['lra']   != null) _metric('LRA',   _result!['lra'].toString()),\n"
        "          const Icon(Icons.copy_rounded, size: 12, color: Color(0xFF484F58)),\n"
        "        ],\n"
        "      ),\n"
        "    ),\n"
        "  );\n"
        "\n"
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
        "        arrow = ' \u2713';\n"
        "        arrowColor = const Color(0xFF3FB950);\n"
        "      } else if (diff > 0) {\n"
        "        arrow = ' \u25b2';\n"
        "        arrowColor = const Color(0xFFD4AF37);\n"
        "      } else {\n"
        "        arrow = ' \u25bc';\n"
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
        "  // S30-R2: 2\xd72 metric grid\n"
        "  Widget _metricGrid() => GestureDetector(\n"
        "    onTap: _copyMetrics,\n"
        "    child: Container(\n"
        "      decoration: BoxDecoration(\n"
        "        color: const Color(0xFF0D1117),\n"
        "        borderRadius: BorderRadius.circular(10),\n"
        "        border: Border.all(color: const Color(0xFF21262D))),\n"
        "      child: Column(children: [\n"
        "        IntrinsicHeight(child: Row(children: [\n"
        "          Expanded(child: _metricTile(\n"
        "            'LUFS',  _result?['lufs']?.toString()  ?? '\u2014', -6.29)),\n"
        "          const VerticalDivider(width: 1, color: Color(0xFF21262D)),\n"
        "          Expanded(child: _metricTile(\n"
        "            'RMS',   _result?['rms']?.toString()   ?? '\u2014', -10.01)),\n"
        "        ])),\n"
        "        const Divider(height: 1, color: Color(0xFF21262D)),\n"
        "        IntrinsicHeight(child: Row(children: [\n"
        "          Expanded(child: _metricTile(\n"
        "            'Crest', _result?['crest']?.toString() ?? '\u2014', 10.25)),\n"
        "          const VerticalDivider(width: 1, color: Color(0xFF21262D)),\n"
        "          Expanded(child: _metricTile(\n"
        "            'LRA',   _result?['lra']?.toString()   ?? '\u2014', 4.19)),\n"
        "        ])),\n"
        "        Padding(\n"
        "          padding: const EdgeInsets.symmetric(vertical: 5),\n"
        "          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [\n"
        "            const Icon(Icons.copy_rounded, size: 10,\n"
        "              color: Color(0xFF484F58)),\n"
        "            const SizedBox(width: 4),\n"
        "            const Text('tap to copy',\n"
        "              style: TextStyle(color: Color(0xFF484F58), fontSize: 9)),\n"
        "          ])),\n"
        "      ]),\n"
        "    ),\n"
        "  );\n"
        "\n"
        "  Widget _metricTile(String label, String value, double target) {\n"
        "    final num = double.tryParse(value);\n"
        "    String delta = '';\n"
        "    String arrow = '';\n"
        "    Color tileColor = const Color(0xFF484F58);\n"
        "    if (num != null && value != '\u2014') {\n"
        "      final diff = num - target;\n"
        "      delta = '${diff >= 0 ? \"+\" : \"\"}${diff.toStringAsFixed(2)}';\n"
        "      if (diff.abs() <= 0.5) {\n"
        "        arrow = '\u2713'; tileColor = const Color(0xFF3FB950);\n"
        "      } else if (diff > 0) {\n"
        "        arrow = '\u25b2'; tileColor = const Color(0xFFD4AF37);\n"
        "      } else {\n"
        "        arrow = '\u25bc'; tileColor = const Color(0xFF58A6FF);\n"
        "      }\n"
        "    }\n"
        "    return Padding(\n"
        "      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),\n"
        "      child: Column(\n"
        "        mainAxisAlignment: MainAxisAlignment.center,\n"
        "        children: [\n"
        "          Text(label, style: const TextStyle(\n"
        "            color: Color(0xFF8B949E),\n"
        "            fontSize: 10, letterSpacing: 0.5)),\n"
        "          const SizedBox(height: 5),\n"
        "          Text(value, style: const TextStyle(\n"
        "            color: Color(0xFFD4AF37),\n"
        "            fontWeight: FontWeight.bold, fontSize: 18)),\n"
        "          if (delta.isNotEmpty) ...[\n"
        "            const SizedBox(height: 3),\n"
        "            Row(mainAxisSize: MainAxisSize.min, children: [\n"
        "              Text(arrow, style: TextStyle(\n"
        "                color: tileColor, fontSize: 9,\n"
        "                fontWeight: FontWeight.bold)),\n"
        "              const SizedBox(width: 2),\n"
        "              Text(delta, style: TextStyle(\n"
        "                color: tileColor, fontSize: 9,\n"
        "                fontWeight: FontWeight.w600)),\n"
        "            ]),\n"
        "          ],\n"
        "        ]),\n"
        "    );\n"
        "  }",
        "R2-method: _metricGrid + _metricTile methods")

# ═══════════════════════════════════════════════════════════════════════════
print("\n[R3] Open/Share buttons → side-by-side row")
# ═══════════════════════════════════════════════════════════════════════════

if not already(HOME, "// S30-R3", "R3: button row already consolidated"):
    patch(HOME,
        "        // S19: Open in player button (only when content:// URI available)\n"
        "        if (hasContentUri) ...[\n"
        "          const SizedBox(height: 8),\n"
        "          SizedBox(width: double.infinity,\n"
        "            child: OutlinedButton.icon(\n"
        "              onPressed: _openInPlayer,\n"
        "              style: OutlinedButton.styleFrom(\n"
        "                foregroundColor: const Color(0xFF58A6FF),\n"
        "                side: const BorderSide(color: Color(0xFF58A6FF), width: 0.8),\n"
        "                padding: const EdgeInsets.symmetric(vertical: 10),\n"
        "                shape: RoundedRectangleBorder(\n"
        "                  borderRadius: BorderRadius.circular(12))),\n"
        "              icon: const Icon(Icons.play_circle_outline_rounded, size: 18),\n"
        "              label: Text(s.openInPlayer,\n"
        "                style: const TextStyle(fontSize: 13)),\n"
        "            )),\n"
        "        ],\n"
        "\n"
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
        "        ], // S30-F2: duplicate share block removed",
        "        // S30-R3: Open + Share in one row\n"
        "        if (hasContentUri || (_output?.path.startsWith('content://') ?? false)) ...[\n"
        "          const SizedBox(height: 8),\n"
        "          Row(children: [\n"
        "            if (hasContentUri) Expanded(\n"
        "              child: OutlinedButton.icon(\n"
        "                onPressed: _openInPlayer,\n"
        "                style: OutlinedButton.styleFrom(\n"
        "                  foregroundColor: const Color(0xFF58A6FF),\n"
        "                  side: const BorderSide(color: Color(0xFF58A6FF), width: 0.8),\n"
        "                  padding: const EdgeInsets.symmetric(vertical: 10),\n"
        "                  shape: RoundedRectangleBorder(\n"
        "                    borderRadius: BorderRadius.circular(12))),\n"
        "                icon: const Icon(Icons.play_circle_outline_rounded, size: 16),\n"
        "                label: Text(s.openInPlayer,\n"
        "                  style: const TextStyle(fontSize: 12)))),\n"
        "            if (hasContentUri && (_output?.path.startsWith('content://') ?? false))\n"
        "              const SizedBox(width: 8),\n"
        "            if (_output?.path.startsWith('content://') ?? false) Expanded(\n"
        "              child: OutlinedButton.icon(\n"
        "                onPressed: _shareFile,\n"
        "                style: OutlinedButton.styleFrom(\n"
        "                  foregroundColor: const Color(0xFF8B949E),\n"
        "                  side: const BorderSide(color: Color(0xFF30363D), width: 0.8),\n"
        "                  padding: const EdgeInsets.symmetric(vertical: 10),\n"
        "                  shape: RoundedRectangleBorder(\n"
        "                    borderRadius: BorderRadius.circular(12))),\n"
        "                icon: const Icon(Icons.share_rounded, size: 16),\n"
        "                label: Text(s.shareBtn,\n"
        "                  style: const TextStyle(fontSize: 12)))),\n"
        "          ]),\n"
        "        ],",
        "R3: Open+Share consolidated to side-by-side row")

# ═══════════════════════════════════════════════════════════════════════════
print("\n[X1] Process Another: icon refresh_rounded")
# ═══════════════════════════════════════════════════════════════════════════

if not already(HOME, "Icons.refresh_rounded", "X1: refresh icon already applied"):
    patch(HOME,
        "            icon: const Icon(Icons.add_circle_outline_rounded, size: 18),",
        "            icon: const Icon(Icons.refresh_rounded, size: 18), // S30-X1",
        "X1: Process Another icon → refresh_rounded")

# ═══════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL PATCHES APPLIED \033[0m")
    print()
    print("Changes:")
    print("  S.  Server banner: fixed \${} literal text bug")
    print("  R1. Score arc: 270\xb0 CustomPaint gauge with count-up inside")
    print("  R2. Metrics: 2\xd72 grid (bigger values, delta, tap-to-copy)")
    print("  R3. Open/Share buttons: now side by side in one row")
    print("  R4. Divider between score/metrics and action buttons")
    print("  X1. Process Another icon is now a refresh symbol")
    print()
    print("Next:")
    print("  git add lib/screens/home_screen.dart")
    print("  git commit -m 'S30-R: result card arc + metric grid + banner fix'")
    print("  git push origin master")
else:
    print(f"\033[91m {errors} PATCH(ES) FAILED \033[0m")
    sys.exit(1)
