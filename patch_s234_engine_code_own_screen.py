#!/usr/bin/env python3
"""
patch_s234_engine_code_own_screen.py — S234

Undoes S233 (which added a "Code" tab *inside* audio_editor_screen.dart's tab
bar) and instead gives the Studio Engine source viewer its own standalone
screen — lib/screens/engine_code_screen.dart — reachable from a new card on
the Home screen, next to the "محرر الصوت" / "أدوات الذكاء الاصطناعي" cards.

Changes:
  1. lib/screens/audio_editor_screen.dart
     - remove `code` from the _Tab enum
     - remove 'Code'/'كود' from tab bar labels/icons
     - remove the _Tab.code switch case
     - remove _engineFuture field + _engineTab()/_copyEngineSrc()/
       _downloadEngineSrc()/_enginePill() (all S233 additions)
  2. lib/screens/engine_code_screen.dart  (NEW FILE)
     - standalone screen: AppBar + Copy/Download buttons + scrollable
       monospace source viewer, same asset (assets/dsp/tilawa_dsp_studio.py)
  3. lib/screens/home_screen.dart
     - import the new screen
     - add `_engineCodeCard(s)` under the AI Tools card
     - wire it into the build() Sliver list

Usage: python3 patch_s234_engine_code_own_screen.py /path/to/tilawa-enhancer
"""
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
STAMP = REPO / '.patch_s234_engine_code_own_screen_done'

if STAMP.exists():
    print('patch_s234 already applied — delete .patch_s234_engine_code_own_screen_done to re-run')
    sys.exit(0)

APPLIED = []
SKIPPED = []
FAILED = []


def apply_fix(rel_path: str, label: str, old: str, new: str, required: bool = True):
    fp = REPO / rel_path
    if not fp.exists():
        msg = f'{rel_path}: FILE NOT FOUND — skipping [{label}]'
        print('  --  ' + msg)
        FAILED.append(msg)
        return
    src = fp.read_text(encoding='utf-8')
    count = src.count(old)
    if count == 0:
        if new in src:
            print(f'  --  {rel_path}: SKIP [{label}] — already applied')
            SKIPPED.append(f'{rel_path}: {label}')
        else:
            msg = f'{rel_path}: anchor text not found for [{label}] — file may have changed, skipping'
            print('  --  ' + msg)
            FAILED.append(msg)
        return
    if count > 1:
        msg = f'{rel_path}: anchor text for [{label}] appears {count} times (expected 1) — skipping to be safe'
        print('  --  ' + msg)
        FAILED.append(msg)
        return
    fp.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK  {rel_path}: applied [{label}]')
    APPLIED.append(f'{rel_path}: {label}')


AE = 'lib/screens/audio_editor_screen.dart'
HS = 'lib/screens/home_screen.dart'
NEW_SCREEN = 'lib/screens/engine_code_screen.dart'

# ═══════════════════════════════════════════════════════════════════════════
# 1. audio_editor_screen.dart — remove the S233 Code tab entirely
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(AE, 'remove _Tab.code enum value',
    old='''enum _Tab { trim, eq, effects, fx2, studio, merge, export_, code }''',
    new='''enum _Tab { trim, eq, effects, fx2, studio, merge, export_ }''',
)

apply_fix(AE, 'remove _engineFuture state field',
    old='''  Future<String>? _engineFuture;     // S233 — cached load of the Studio Engine source, for the Code tab
''',
    new='',
)

apply_fix(AE, 'remove Code from tab bar labels/icons',
    old='''    final labels = ar ? ['قص','EQ','تأثيرات','FX+','استوديو','دمج','تصدير','كود']
                      : ['Trim','EQ','Effects','FX+','Studio','Merge','Export','Code'];
    final icons = [Icons.content_cut_rounded, Icons.equalizer_rounded,
                   Icons.auto_fix_high_rounded, Icons.graphic_eq_rounded, Icons.science_rounded,
                   Icons.merge_type_rounded, Icons.ios_share_rounded, Icons.code_rounded];''',
    new='''    final labels = ar ? ['قص','EQ','تأثيرات','FX+','استوديو','دمج','تصدير']
                      : ['Trim','EQ','Effects','FX+','Studio','Merge','Export'];
    final icons = [Icons.content_cut_rounded, Icons.equalizer_rounded,
                   Icons.auto_fix_high_rounded, Icons.graphic_eq_rounded, Icons.science_rounded,
                   Icons.merge_type_rounded, Icons.ios_share_rounded];''',
)

apply_fix(AE, 'remove _Tab.code switch case',
    old='''      case _Tab.export_: return _exportTab();
      case _Tab.code:    return _engineTab();
    }
  }''',
    new='''      case _Tab.export_: return _exportTab();
    }
  }''',
)

apply_fix(AE, 'remove _engineTab()/_enginePill()/copy+download helpers (S233 block)',
    old='''

  // ── S233: Engine tab — view/download the bundled Studio Engine source ──────
  Future<String> _loadEngineSrc() =>
      _engineFuture ??= rootBundle.loadString('assets/dsp/tilawa_dsp_studio.py');

  Future<void> _copyEngineSrc() async {
    final ar = LangProvider.strings(context).ar;
    final src = await _loadEngineSrc();
    await Clipboard.setData(ClipboardData(text: src));
    if (!mounted) return;
    _snack(ar ? '✓ تم نسخ الكود' : '✓ Code copied to clipboard');
  }

  Future<void> _downloadEngineSrc() async {
    final ar = LangProvider.strings(context).ar;
    try {
      final src = await _loadEngineSrc();
      final dir = await getTemporaryDirectory();
      final f = File('${dir.path}/tilawa_dsp_studio.py');
      await f.writeAsString(src, flush: true);
      try {
        await _media.invokeMethod('saveToDownloads',
            {'path': f.path, 'filename': 'tilawa_dsp_studio.py'});
      } catch (_) {}
      if (!mounted) return;
      _snack(ar ? '✓ تم الحفظ في التنزيلات' : '✓ Saved to Downloads');
    } catch (e) {
      if (!mounted) return;
      _snack('Error: $e', color: _red);
    }
  }

  Widget _enginePill(String label, IconData icon, VoidCallback onTap, {bool gold = false}) =>
    GestureDetector(onTap: onTap,
      child: Container(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(color: gold ? _goldDim.withValues(alpha: 0.35) : _surface,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: gold ? _gold.withValues(alpha: 0.6) : _border)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, color: gold ? _gold : _textB, size: 14),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(color: gold ? _gold : _textB, fontSize: 11.5,
              fontWeight: FontWeight.w700)),
        ])));

  Widget _engineTab() {
    final ar = LangProvider.strings(context).ar;
    return Column(children: [
      Padding(padding: const EdgeInsets.fromLTRB(14, 12, 14, 10),
        child: Row(children: [
          Expanded(child: Text(ar ? 'كود محرك المعالجة' : 'Studio Engine source',
              style: const TextStyle(color: _textA, fontSize: 13.5, fontWeight: FontWeight.w700))),
          _enginePill(ar ? 'نسخ' : 'Copy', Icons.copy_rounded, _copyEngineSrc),
          const SizedBox(width: 8),
          _enginePill(ar ? 'تنزيل' : 'Download', Icons.download_rounded, _downloadEngineSrc, gold: true),
        ])),
      Padding(padding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
        child: Text(
          ar ? 'assets/dsp/tilawa_dsp_studio.py — نفس السكربت الذي يعالج تبويب "استوديو"'
             : 'assets/dsp/tilawa_dsp_studio.py — the exact script behind the Studio tab',
          style: const TextStyle(color: _textDim, fontSize: 11))),
      Expanded(child: FutureBuilder<String>(
        future: _loadEngineSrc(),
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) {
            return const Center(child: CircularProgressIndicator(color: _gold, strokeWidth: 2.4));
          }
          if (snap.hasError) {
            return Center(child: Text(ar ? 'تعذر تحميل الكود' : 'Could not load source',
                style: const TextStyle(color: _red)));
          }
          final src = snap.data ?? '';
          return Container(
            margin: const EdgeInsets.fromLTRB(14, 0, 14, 14),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(12),
                border: Border.all(color: _border)),
            child: Scrollbar(thumbVisibility: true,
              child: SingleChildScrollView(
                child: SingleChildScrollView(scrollDirection: Axis.horizontal,
                  child: SelectableText(src, style: const TextStyle(color: _textB, fontSize: 11.5,
                      fontFamily: 'monospace', height: 1.5))))));
        })),
    ]);
  }
''',
    new='',
)

# ═══════════════════════════════════════════════════════════════════════════
# 2. NEW FILE — lib/screens/engine_code_screen.dart
# ═══════════════════════════════════════════════════════════════════════════

ENGINE_CODE_SCREEN = r'''// engine_code_screen.dart — S234
// Standalone screen (own Home-screen card, own route) that shows/copies/
// downloads the bundled Studio Engine source (assets/dsp/tilawa_dsp_studio.py
// — the same numpy/scipy script the Audio Editor's "Studio" tab runs).
// Split out of audio_editor_screen.dart's tab bar (was S233's "Code" tab) so
// it lives on its own, not nested inside the editor.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import '../state/lang_provider.dart';

const _bg      = Color(0xFF020D17);
const _surface = Color(0xFF0C1E28);
const _card    = Color(0xFF0F2420);
const _gold    = Color(0xFFD4AF37);
const _goldDim = Color(0xFF3A2B08);
const _red     = Color(0xFFD94040);
const _textA   = Color(0xFFE2CFA0);
const _textB   = Color(0xFF8AACBA);
const _textDim = Color(0xFF3D5A65);
const _border  = Color(0xFF1A2E20);

class EngineCodeScreen extends StatefulWidget {
  const EngineCodeScreen({super.key});
  @override
  State<EngineCodeScreen> createState() => _EngineCodeScreenState();
}

class _EngineCodeScreenState extends State<EngineCodeScreen> {
  static const _media = MethodChannel('com.tilawa.tilawa_enhancer/media');
  Future<String>? _engineFuture;

  Future<String> _loadEngineSrc() =>
      _engineFuture ??= rootBundle.loadString('assets/dsp/tilawa_dsp_studio.py');

  void _snack(String msg, {Color color = _gold}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg, style: TextStyle(color: color == _gold ? _bg : Colors.white)),
      backgroundColor: color == _gold ? _gold : color,
      behavior: SnackBarBehavior.floating,
      duration: const Duration(seconds: 2)));
  }

  Future<void> _copyEngineSrc() async {
    final ar = LangProvider.strings(context).ar;
    final src = await _loadEngineSrc();
    await Clipboard.setData(ClipboardData(text: src));
    if (!mounted) return;
    _snack(ar ? '✓ تم نسخ الكود' : '✓ Code copied to clipboard');
  }

  Future<void> _downloadEngineSrc() async {
    final ar = LangProvider.strings(context).ar;
    try {
      final src = await _loadEngineSrc();
      final dir = await getTemporaryDirectory();
      final f = File('${dir.path}/tilawa_dsp_studio.py');
      await f.writeAsString(src, flush: true);
      try {
        await _media.invokeMethod('saveToDownloads',
            {'path': f.path, 'filename': 'tilawa_dsp_studio.py'});
      } catch (_) {}
      if (!mounted) return;
      _snack(ar ? '✓ تم الحفظ في التنزيلات' : '✓ Saved to Downloads');
    } catch (e) {
      if (!mounted) return;
      _snack('Error: $e', color: _red);
    }
  }

  Widget _pill(String label, IconData icon, VoidCallback onTap, {bool gold = false}) =>
    GestureDetector(onTap: onTap,
      child: Container(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(color: gold ? _goldDim.withValues(alpha: 0.35) : _surface,
            borderRadius: BorderRadius.circular(18),
            border: Border.all(color: gold ? _gold.withValues(alpha: 0.6) : _border)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(icon, color: gold ? _gold : _textB, size: 14),
          const SizedBox(width: 6),
          Text(label, style: TextStyle(color: gold ? _gold : _textB, fontSize: 11.5,
              fontWeight: FontWeight.w700)),
        ])));

  @override
  Widget build(BuildContext context) {
    final ar = LangProvider.strings(context).ar;
    return Scaffold(
      backgroundColor: _bg,
      appBar: AppBar(
        backgroundColor: _bg,
        foregroundColor: _textA,
        elevation: 0,
        title: Text(ar ? 'كود محرك المعالجة' : 'Studio Engine source',
            style: const TextStyle(color: _textA, fontSize: 15, fontWeight: FontWeight.w700)),
      ),
      body: Column(children: [
        Padding(padding: const EdgeInsets.fromLTRB(14, 10, 14, 10),
          child: Row(children: [
            Expanded(child: Text(
              ar ? 'assets/dsp/tilawa_dsp_studio.py — نفس السكربت الذي يعالج تبويب "استوديو"'
                 : 'assets/dsp/tilawa_dsp_studio.py — the exact script behind the Studio tab',
              style: const TextStyle(color: _textDim, fontSize: 11))),
          ])),
        Padding(padding: const EdgeInsets.fromLTRB(14, 0, 14, 10),
          child: Row(children: [
            _pill(ar ? 'نسخ' : 'Copy', Icons.copy_rounded, _copyEngineSrc),
            const SizedBox(width: 8),
            _pill(ar ? 'تنزيل' : 'Download', Icons.download_rounded, _downloadEngineSrc, gold: true),
          ])),
        Expanded(child: FutureBuilder<String>(
          future: _loadEngineSrc(),
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator(color: _gold, strokeWidth: 2.4));
            }
            if (snap.hasError) {
              return Center(child: Text(ar ? 'تعذر تحميل الكود' : 'Could not load source',
                  style: const TextStyle(color: _red)));
            }
            final src = snap.data ?? '';
            return Container(
              margin: const EdgeInsets.fromLTRB(14, 0, 14, 14),
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(12),
                  border: Border.all(color: _border)),
              child: Scrollbar(thumbVisibility: true,
                child: SingleChildScrollView(
                  child: SingleChildScrollView(scrollDirection: Axis.horizontal,
                    child: SelectableText(src, style: const TextStyle(color: _textB, fontSize: 11.5,
                        fontFamily: 'monospace', height: 1.5))))));
          })),
      ]),
    );
  }
}
'''

fp = REPO / NEW_SCREEN
if fp.exists():
    print(f'  --  {NEW_SCREEN}: SKIP — file already exists')
    SKIPPED.append(f'{NEW_SCREEN}: create file')
else:
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(ENGINE_CODE_SCREEN, encoding='utf-8')
    print(f'  OK  {NEW_SCREEN}: created')
    APPLIED.append(f'{NEW_SCREEN}: create file')

# ═══════════════════════════════════════════════════════════════════════════
# 3. home_screen.dart — import + new card + wire into build()
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(HS, 'import engine_code_screen.dart',
    old='''import 'ai_tools_screen.dart'; // S184 // S152-B13: home_screen is already in lib/screens/''',
    new='''import 'ai_tools_screen.dart'; // S184 // S152-B13: home_screen is already in lib/screens/
import 'engine_code_screen.dart'; // S234''',
)

apply_fix(HS, 'wire _engineCodeCard into build() Sliver list',
    old='''            SliverToBoxAdapter(child: _aiToolsCard(s)),     // S184''',
    new='''            SliverToBoxAdapter(child: _aiToolsCard(s)),     // S184
            SliverToBoxAdapter(child: _engineCodeCard(s)),   // S234''',
)

NEW_CARD = r'''

  // ── ENGINE CODE CARD — S234 (own screen, split out of Audio Editor tabs) ───
  Widget _engineCodeCard(S s) => Padding(
    padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
    child: Material(
      color: _bgCard,
      borderRadius: BorderRadius.circular(14),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => Navigator.push(context,
          PageRouteBuilder(
            pageBuilder: (_, __, ___) => const EngineCodeScreen(),
            transitionsBuilder: (_, anim, __, child) =>
              FadeTransition(opacity: anim, child: child),
            transitionDuration: const Duration(milliseconds: 220),
          )),
        splashColor: _gold.withValues(alpha: 0.12),
        highlightColor: _gold.withValues(alpha: 0.06),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
          decoration: BoxDecoration(
            border: Border.all(color: _gold.withValues(alpha: 0.25))),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.code_rounded, color: _gold, size: 18),
            const SizedBox(width: 8),
            Text(LangProvider.strings(context).ar ? 'كود محرك المعالجة' : 'Engine Source',
                style: const TextStyle(color: Color(0xFF8AACBA), fontSize: 13)),
            const Spacer(),
            const Icon(Icons.chevron_left_rounded,
                color: Color(0xFF484F58), size: 18),
          ]),
        ),
      ),
    ),
  );
'''

apply_fix(HS, 'add _engineCodeCard() widget after _aiToolsCard()',
    old='''  // ── AI TOOLS CARD — S184 ──────────────────────────────────────────────────''',
    new=NEW_CARD.strip('\n') + '\n\n  // ── AI TOOLS CARD — S184 ──────────────────────────────────────────────────',
)

# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════

print()
print(f'Applied: {len(APPLIED)}   Skipped: {len(SKIPPED)}   Failed: {len(FAILED)}')
if FAILED:
    print('\nSome fixes could not be applied — review the file manually:')
    for f in FAILED:
        print('  - ' + f)
    sys.exit(1)
else:
    STAMP.write_text('done\n')
    print('\nAll good — S234: Engine Source is now its own screen/card, not an Audio Editor tab.')
