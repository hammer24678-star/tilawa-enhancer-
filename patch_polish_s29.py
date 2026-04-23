#!/usr/bin/env python3
"""
patch_polish_s29.py — Session 29: Visual Polish & Animation Pass

Run after patch_qol2_s28.py, from ~/tilawa-enhancer/ then git push.

Changes:
  home_screen.dart  (14 patches)
    1.  _resultCtrl late field
    2.  _resultCtrl init in initState
    3.  _resultCtrl dispose
    4.  Trigger result animation in _downloadAndSave
    5.  build(): gradient bg + animated result card entry
    6.  _resultCard: score counts up + label badge
    7.  Process button: spinner instead of disabled text when busy
    8.  _iconBtn: GestureDetector → Material + InkWell (ripple)
    9.  Settings push: fade transition
    10. History push: fade transition
    11. Engine selector card: subtle drop shadow
    12. File card: subtle drop shadow
    13. Progress card: subtle drop shadow
    14. Result card: colored glow shadow

  history_screen.dart  (1 patch)
    15. ListView itemBuilder: stagger fade-in + slide per card
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
    if text.count(old) > 1:
        print(f"{WARN} [{path.name}] anchor is NOT unique — {label}")
        return False
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
    print(f"{OK}  [{path.name}] {label}")
    return True

errors = 0
HOME  = REPO / "lib/screens/home_screen.dart"
HIST  = REPO / "lib/screens/history_screen.dart"

print("\n[home_screen.dart — 14 patches]")

# ── 1. _resultCtrl late field ──────────────────────────────────────────────
errors += 0 if patch(HOME,
    "  late final AnimationController _glowCtrl;",
    "  late final AnimationController _glowCtrl;\n"
    "  late final AnimationController _resultCtrl; // S29: result card entrance",
    "1. _resultCtrl field") else 1

# ── 2. _resultCtrl init in initState ──────────────────────────────────────
errors += 0 if patch(HOME,
    "      ..repeat(reverse: true);",
    "      ..repeat(reverse: true);\n"
    "    _resultCtrl = AnimationController(\n"
    "        vsync: this, duration: const Duration(milliseconds: 600));",
    "2. _resultCtrl init") else 1

# ── 3. _resultCtrl dispose ────────────────────────────────────────────────
errors += 0 if patch(HOME,
    "    _glowCtrl.dispose();",
    "    _resultCtrl.dispose();\n"
    "    _glowCtrl.dispose();",
    "3. _resultCtrl dispose") else 1

# ── 4. Trigger result animation ───────────────────────────────────────────
errors += 0 if patch(HOME,
    "    setState(() {\n"
    "      _busy = false; _progress = 1.0;\n"
    "      _output = file; _result = sd;\n"
    "      _status = file != null ? s.done : '\u0641\u0634\u0644: $error';\n"
    "    });\n"
    "\n"
    "    // S19: Save job record locally for persistent re-download",
    "    setState(() {\n"
    "      _busy = false; _progress = 1.0;\n"
    "      _output = file; _result = sd;\n"
    "      _status = file != null ? s.done : '\u0641\u0634\u0644: $error';\n"
    "    });\n"
    "\n"
    "    if (file != null) _resultCtrl.forward(from: 0); // S29: animate in\n"
    "\n"
    "    // S19: Save job record locally for persistent re-download",
    "4. trigger animation on result") else 1

# ── 5. build(): gradient background + animated result card entry ───────────
errors += 0 if patch(HOME,
    "    return Scaffold(\n"
    "      body: SafeArea(\n"
    "        child: CustomScrollView(slivers: [\n"
    "          SliverToBoxAdapter(child: _header(s)),\n"
    "          SliverToBoxAdapter(child: _serverBanner(s)),\n"
    "          SliverToBoxAdapter(child: _engineSelector(s)),\n"
    "          SliverToBoxAdapter(child: _fileCard(s)),\n"
    "          if (_busy || _progress > 0)\n"
    "            SliverToBoxAdapter(child: _progressCard(s)),\n"
    "          if (_result != null)\n"
    "            SliverToBoxAdapter(child: _resultCard(s)),\n"
    "          SliverToBoxAdapter(child: _bottomRow(s)),\n"
    "          SliverToBoxAdapter(child: _donationCard(s)),\n"
    "          const SliverToBoxAdapter(child: SizedBox(height: 40)),\n"
    "        ]),\n"
    "      ),\n"
    "    );\n"
    "  }",
    "    return Scaffold(\n"
    "      backgroundColor: const Color(0xFF080A0E),\n"
    "      body: Container(\n"
    "        decoration: const BoxDecoration(\n"
    "          gradient: LinearGradient(\n"
    "            begin: Alignment.topCenter,\n"
    "            end: Alignment.bottomCenter,\n"
    "            colors: [Color(0xFF080A0E), Color(0xFF0C1018)])),\n"
    "        child: SafeArea(\n"
    "          child: CustomScrollView(slivers: [\n"
    "            SliverToBoxAdapter(child: _header(s)),\n"
    "            SliverToBoxAdapter(child: _serverBanner(s)),\n"
    "            SliverToBoxAdapter(child: _engineSelector(s)),\n"
    "            SliverToBoxAdapter(child: _fileCard(s)),\n"
    "            if (_busy || _progress > 0)\n"
    "              SliverToBoxAdapter(child: _progressCard(s)),\n"
    "            if (_result != null)\n"
    "              SliverToBoxAdapter(\n"
    "                child: FadeTransition(\n"
    "                  opacity: CurvedAnimation(\n"
    "                    parent: _resultCtrl, curve: Curves.easeOut),\n"
    "                  child: SlideTransition(\n"
    "                    position: Tween<Offset>(\n"
    "                      begin: const Offset(0, 0.1),\n"
    "                      end: Offset.zero,\n"
    "                    ).animate(CurvedAnimation(\n"
    "                      parent: _resultCtrl, curve: Curves.easeOutCubic)),\n"
    "                    child: _resultCard(s),\n"
    "                  ),\n"
    "                ),\n"
    "              ),\n"
    "            SliverToBoxAdapter(child: _bottomRow(s)),\n"
    "            SliverToBoxAdapter(child: _donationCard(s)),\n"
    "            const SliverToBoxAdapter(child: SizedBox(height: 40)),\n"
    "          ]),\n"
    "        ),\n"
    "      ),\n"
    "    );\n"
    "  }",
    "5. gradient bg + animated result card") else 1

# ── 6. Score row: label → badge + number → count-up ──────────────────────
errors += 0 if patch(HOME,
    "        Row(\n"
    "          mainAxisAlignment: MainAxisAlignment.center,\n"
    "          crossAxisAlignment: CrossAxisAlignment.baseline,\n"
    "          textBaseline: TextBaseline.alphabetic,\n"
    "          children: [\n"
    "            Text(label, style: TextStyle(\n"
    "              color: scoreColor,\n"
    "              fontWeight: FontWeight.bold, fontSize: 16)),\n"
    "            const SizedBox(width: 10),\n"
    "            Text('${score.toStringAsFixed(1)}/100',\n"
    "              style: TextStyle(\n"
    "                color: scoreColor,\n"
    "                fontWeight: FontWeight.w900, fontSize: 34)),\n"
    "          ]),",
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
    "            AnimatedBuilder(\n"
    "              animation: _resultCtrl,\n"
    "              builder: (_, __) {\n"
    "                final t = Curves.easeOutCubic.transform(_resultCtrl.value);\n"
    "                return Text(\n"
    "                  '${(score * t).toStringAsFixed(1)}/100',\n"
    "                  style: TextStyle(\n"
    "                    color: scoreColor,\n"
    "                    fontWeight: FontWeight.w900, fontSize: 34));\n"
    "              }),\n"
    "          ]),",
    "6. score label badge + count-up animation") else 1

# ── 7. Process button: spinner when _busy ──────────────────────────────────
errors += 0 if patch(HOME,
    "              child: Text(\n"
    "                _busy ? s.processing : '${s.process} \u2014 $_engine',\n"
    "                style: const TextStyle(\n"
    "                  fontWeight: FontWeight.bold, fontSize: 15)))),",
    "              child: _busy\n"
    "                ? Row(mainAxisSize: MainAxisSize.min, children: [\n"
    "                    const SizedBox(width: 16, height: 16,\n"
    "                      child: CircularProgressIndicator(\n"
    "                        strokeWidth: 2,\n"
    "                        color: Color(0xFF0A0C10))),\n"
    "                    const SizedBox(width: 10),\n"
    "                    Text(s.processing,\n"
    "                      style: const TextStyle(\n"
    "                        fontWeight: FontWeight.bold, fontSize: 15)),\n"
    "                  ])\n"
    "                : Text('${s.process} \u2014 $_engine',\n"
    "                    style: const TextStyle(\n"
    "                      fontWeight: FontWeight.bold, fontSize: 15)))),",
    "7. process button spinner") else 1

# ── 8. _iconBtn: GestureDetector → Material + InkWell ──────────────────────
errors += 0 if patch(HOME,
    "  Widget _iconBtn(IconData icon, VoidCallback onTap) => GestureDetector(\n"
    "    onTap: onTap,\n"
    "    child: Container(\n"
    "      padding: const EdgeInsets.all(9),\n"
    "      decoration: BoxDecoration(\n"
    "        color: const Color(0xFF161B22), shape: BoxShape.circle,\n"
    "        border: Border.all(color: const Color(0xFF21262D))),\n"
    "      child: Icon(icon, color: const Color(0xFF8B949E), size: 20)));",
    "  Widget _iconBtn(IconData icon, VoidCallback onTap) => Material(\n"
    "    color: const Color(0xFF161B22),\n"
    "    shape: const CircleBorder(\n"
    "      side: BorderSide(color: Color(0xFF21262D))),\n"
    "    clipBehavior: Clip.antiAlias,\n"
    "    child: InkWell(\n"
    "      onTap: onTap,\n"
    "      splashColor: const Color(0xFFD4AF37).withOpacity(0.18),\n"
    "      highlightColor: const Color(0xFFD4AF37).withOpacity(0.08),\n"
    "      child: Padding(\n"
    "        padding: const EdgeInsets.all(9),\n"
    "        child: Icon(icon, color: const Color(0xFF8B949E), size: 20))));",
    "8. _iconBtn Material+InkWell") else 1

# ── 9. Settings: fade page transition ─────────────────────────────────────
errors += 0 if patch(HOME,
    "        _iconBtn(Icons.settings_outlined, () => Navigator.push(\n"
    "          context, MaterialPageRoute(builder: (_) => const SettingsScreen()))),",
    "        _iconBtn(Icons.settings_outlined, () => Navigator.push(context,\n"
    "          PageRouteBuilder(\n"
    "            pageBuilder: (_, __, ___) => const SettingsScreen(),\n"
    "            transitionsBuilder: (_, anim, __, child) =>\n"
    "              FadeTransition(opacity: anim, child: child),\n"
    "            transitionDuration: const Duration(milliseconds: 220),\n"
    "          ))),",
    "9. settings fade transition") else 1

# ── 10. History: fade page transition ─────────────────────────────────────
errors += 0 if patch(HOME,
    "      onTap: () => Navigator.push(context,\n"
    "        MaterialPageRoute(builder: (_) => const HistoryScreen())),",
    "      onTap: () => Navigator.push(context,\n"
    "        PageRouteBuilder(\n"
    "          pageBuilder: (_, __, ___) => const HistoryScreen(),\n"
    "          transitionsBuilder: (_, anim, __, child) =>\n"
    "            FadeTransition(opacity: anim, child: child),\n"
    "          transitionDuration: const Duration(milliseconds: 220),\n"
    "        )),",
    "10. history fade transition") else 1

# ── 11. Engine selector: drop shadow ──────────────────────────────────────
errors += 0 if patch(HOME,
    "    decoration: BoxDecoration(\n"
    "      color: const Color(0xFF161B22),\n"
    "      borderRadius: BorderRadius.circular(14),\n"
    "      border: Border.all(color: const Color(0xFF21262D))),\n"
    "    child: Column(children: [\n"
    "      // \u2500\u2500 Header row \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
    "    decoration: BoxDecoration(\n"
    "      color: const Color(0xFF161B22),\n"
    "      borderRadius: BorderRadius.circular(14),\n"
    "      border: Border.all(color: const Color(0xFF21262D)),\n"
    "      boxShadow: const [BoxShadow(\n"
    "        color: Color(0x26000000),\n"
    "        blurRadius: 12, offset: Offset(0, 3))]),\n"
    "    child: Column(children: [\n"
    "      // \u2500\u2500 Header row \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500",
    "11. engine selector drop shadow") else 1

# ── 12. File card: drop shadow ─────────────────────────────────────────────
errors += 0 if patch(HOME,
    "          color: _file != null ? const Color(0xFFD4AF37) : const Color(0xFF30363D),\n"
    "          width: 1.5)),\n"
    "      child: Column(children: [",
    "          color: _file != null ? const Color(0xFFD4AF37) : const Color(0xFF30363D),\n"
    "          width: 1.5),\n"
    "        boxShadow: const [BoxShadow(\n"
    "          color: Color(0x26000000),\n"
    "          blurRadius: 12, offset: Offset(0, 3))]),\n"
    "      child: Column(children: [",
    "12. file card drop shadow") else 1

# ── 13. Progress card: drop shadow ────────────────────────────────────────
errors += 0 if patch(HOME,
    "    decoration: BoxDecoration(\n"
    "      color: const Color(0xFF161B22),\n"
    "      borderRadius: BorderRadius.circular(14),\n"
    "      border: Border.all(color: const Color(0xFF21262D))),\n"
    "    child: Column(children: [\n"
    "      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [",
    "    decoration: BoxDecoration(\n"
    "      color: const Color(0xFF161B22),\n"
    "      borderRadius: BorderRadius.circular(14),\n"
    "      border: Border.all(color: const Color(0xFF21262D)),\n"
    "      boxShadow: const [BoxShadow(\n"
    "        color: Color(0x26000000),\n"
    "        blurRadius: 12, offset: Offset(0, 3))]),\n"
    "    child: Column(children: [\n"
    "      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [",
    "13. progress card drop shadow") else 1

# ── 14. Result card: colored glow shadow ──────────────────────────────────
errors += 0 if patch(HOME,
    "        border: Border.all(\n"
    "          color: score < 80 ? const Color(0xFFF85149) : const Color(0xFF3FB950),\n"
    "          width: 1.2)),\n"
    "      child: Column(children: [\n"
    "        // Score",
    "        border: Border.all(\n"
    "          color: score < 80 ? const Color(0xFFF85149) : const Color(0xFF3FB950),\n"
    "          width: 1.2),\n"
    "        boxShadow: [BoxShadow(\n"
    "          color: (score < 80\n"
    "              ? const Color(0xFFF85149)\n"
    "              : const Color(0xFF3FB950)).withOpacity(0.12),\n"
    "          blurRadius: 24, offset: const Offset(0, 6))]),\n"
    "      child: Column(children: [\n"
    "        // Score",
    "14. result card glow shadow") else 1

# ═══════════════════════════════════════════════════════════════════════════════
print("\n[history_screen.dart — 1 patch]")

# ── 15. Stagger fade+slide per card ──────────────────────────────────────
errors += 0 if patch(HIST,
    "                itemBuilder: (_, i) => _jobCard(_jobs[i], s))));",
    "                itemBuilder: (_, i) {\n"
    "                  return TweenAnimationBuilder<double>(\n"
    "                    key: ValueKey(_jobs[i]['job_id']),\n"
    "                    tween: Tween(begin: 0.0, end: 1.0),\n"
    "                    duration: Duration(\n"
    "                      milliseconds: 280 + 55 * (i < 8 ? i : 8)),\n"
    "                    curve: Curves.easeOutCubic,\n"
    "                    builder: (_, val, child) => Opacity(\n"
    "                      opacity: val,\n"
    "                      child: Transform.translate(\n"
    "                        offset: Offset(0, 16 * (1 - val)),\n"
    "                        child: child)),\n"
    "                    child: _jobCard(_jobs[i], s),\n"
    "                  );\n"
    "                })));",
    "15. history stagger animation") else 1

# ═══════════════════════════════════════════════════════════════════════════════
print()
print("=" * 60)
if errors == 0:
    print("\033[92m ALL 15 PATCHES APPLIED \033[0m")
    print()
    print("Next:")
    print("  cd ~/tilawa-enhancer")
    print("  git add lib/screens/home_screen.dart \\")
    print("          lib/screens/history_screen.dart")
    print("  git commit -m 'S29: Visual polish — animations, shadows, transitions'")
    print("  git push origin master")
    print()
    print("What changed visually:")
    print("  - Result card slides up + fades in on completion")
    print("  - Score number counts from 0 to final value (600ms easeOutCubic)")
    print("  - Score label is now a rounded badge (e.g. [Excellent])")
    print("  - Process button shows spinner + 'Processing...' while busy")
    print("  - Info/Settings buttons have gold ripple on tap")
    print("  - Settings and History open with 220ms fade (not slide)")
    print("  - Subtle drop shadow on engine, file, and progress cards")
    print("  - Result card glows green (good score) or red (low score)")
    print("  - App background has a very subtle top-to-bottom gradient")
    print("  - History list items stagger in with fade + upward slide")
else:
    print(f"\033[91m {errors} PATCH(ES) FAILED \033[0m")
    print("Check WARN lines. Fix anchors then re-run.")
    sys.exit(1)
