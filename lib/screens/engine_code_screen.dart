// engine_code_screen.dart — S234 · S239 v2 "full engine source browser"
// Standalone screen (own Home-screen card, own route) that shows/copies/
// downloads the bundled engine sources. S234 only exposed the Studio Engine
// DSP script; S239 adds every bundled restoration/analysis engine
// (assets/engines/*.py — الصفاء، الإتقان، الاسترداد، إحياء …) behind a chip
// selector, with per-file stats, in-code search, and chunked rendering so
// even the 15,000-line الاسترداد source scrolls smoothly.

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'dart:io';
import 'package:path_provider/path_provider.dart';
import '../design/nur.dart';
import '../state/lang_provider.dart';

class _EngineFile {
  final String asset;   // full rootBundle path
  final String nameAr;  // display name (Arabic)
  final String nameEn;  // display name (English)
  final String tag;     // small category label shown on the chip
  const _EngineFile(this.asset, this.nameAr, this.nameEn, this.tag);

  String get fileName => asset.split('/').last;
}

class EngineCodeScreen extends StatefulWidget {
  const EngineCodeScreen({super.key});
  @override
  State<EngineCodeScreen> createState() => _EngineCodeScreenState();
}

class _EngineCodeScreenState extends State<EngineCodeScreen> {
  static const _media = MethodChannel('com.tilawa.tilawa_enhancer/media');

  // S239 — every bundled Python engine, not just the Studio DSP script.
  // Names follow the engine roster in settings_screen.dart / home_screen.dart.
  static const _files = <_EngineFile>[
    _EngineFile('assets/dsp/tilawa_dsp_studio.py',
        'محرك الاستوديو', 'Studio Engine', 'DSP'),
    _EngineFile('assets/engines/engine_safaa_v4.py',
        'الصفاء v4', 'Safaa v4 — Purity', 'v11.0'),
    _EngineFile('assets/engines/engine_itiqan_v6_official.py',
        'الإتقان v6', 'Itqan v6 — Perfection', 'v11.1'),
    _EngineFile('assets/engines/engine_isteidad_v21.py',
        'الاسترداد v21', 'Isteidad v21 — Recovery', 'v11.2'),
    _EngineFile('assets/engines/ihyaa_ve.py',
        'إحياء', 'Ihyaa — Revival', 'v11.3'),
    _EngineFile('assets/engines/naqaa_v1_tested.py',
        'نقاء', 'Naqaa — Clarity', 'DSP'),
    _EngineFile('assets/engines/bayan_ve_v2fix.py',
        'بيان', 'Bayan', 'VE'),
    _EngineFile('assets/engines/noor_v5.py',
        'نور v5', 'Noor v5', 'NR'),
    _EngineFile('assets/engines/idrak_text_v2.py',
        'إدراك', 'Idrak — Text', 'TEXT'),
    _EngineFile('assets/engines/miraat_ref_v2.py',
        'مرآة', 'Miraat — Reference', 'REF'),
    _EngineFile('assets/engines/hakim_gen_v2.py',
        'حكيم', 'Hakim — Generator', 'GEN'),
    _EngineFile('assets/engines/engine_safaa_v3_fixed.py',
        'الصفاء v3', 'Safaa v3 (legacy)', 'OLD'),
  ];

  // ~200 lines per SelectableText keeps selection usable while ListView
  // virtualization carries the 15k-line files.
  static const _chunkLines = 200;

  final Map<String, String> _cache = {};
  _EngineFile _sel = _files.first;
  String _query = '';

  Future<String> _load(_EngineFile f) async =>
      _cache[f.asset] ??= await rootBundle.loadString(f.asset);

  void _snack(String msg, {bool error = false}) {
    if (!mounted) return;
    final p = NurPalette.of(context);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg, style: TextStyle(
          color: error ? p.err : p.text, fontWeight: FontWeight.w600)),
      backgroundColor: p.surfaceHi,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: error ? p.err : p.gold, width: 0.8)),
      duration: const Duration(seconds: 2)));
  }

  Future<void> _copySrc() async {
    final ar = LangProvider.strings(context).ar;
    try {
      final src = await _load(_sel);
      await Clipboard.setData(ClipboardData(text: src));
      if (!mounted) return;
      _snack(ar ? '✓ تم نسخ ${_sel.fileName}' : '✓ ${_sel.fileName} copied');
    } catch (e) {
      _snack('Error: $e', error: true);
    }
  }

  Future<void> _downloadSrc() async {
    final ar = LangProvider.strings(context).ar;
    try {
      final src = await _load(_sel);
      final dir = await getTemporaryDirectory();
      final f = File('${dir.path}/${_sel.fileName}');
      await f.writeAsString(src, flush: true);
      try {
        await _media.invokeMethod('saveToDownloads',
            {'path': f.path, 'filename': _sel.fileName});
      } catch (_) {}
      if (!mounted) return;
      _snack(ar ? '✓ تم الحفظ في التنزيلات' : '✓ Saved to Downloads');
    } catch (e) {
      if (!mounted) return;
      _snack('Error: $e', error: true);
    }
  }

  Widget _fileChip(_EngineFile f, bool ar, NurPalette p) {
    final sel = f.asset == _sel.asset;
    return GestureDetector(
      onTap: () {
        if (sel) return;
        HapticFeedback.selectionClick();
        setState(() { _sel = f; _query = ''; });
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOutCubic,
        margin: const EdgeInsetsDirectional.only(end: 8),
        padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 8),
        decoration: BoxDecoration(
          color: sel ? p.gold.withValues(alpha: 0.16) : p.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
              color: sel ? p.gold : p.border, width: sel ? 1.4 : 1),
          boxShadow: sel
              ? [BoxShadow(color: p.gold.withValues(alpha: 0.22), blurRadius: 14)]
              : null),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Text(ar ? f.nameAr : f.nameEn,
              style: TextStyle(color: sel ? p.gold : p.textSub, fontSize: 12,
                  fontWeight: sel ? FontWeight.w800 : FontWeight.w500)),
          const SizedBox(width: 7),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
            decoration: BoxDecoration(
              color: sel ? p.gold.withValues(alpha: 0.18) : p.surfaceHi,
              borderRadius: BorderRadius.circular(6)),
            child: Text(f.tag, style: TextStyle(
                color: sel ? p.gold : p.textDim, fontSize: 9,
                fontWeight: FontWeight.w700, fontFamily: 'monospace'))),
        ])));
  }

  // Search results — matched lines with their 1-based line numbers.
  List<MapEntry<int, String>> _matches(List<String> lines) {
    final q = _query.trim().toLowerCase();
    final out = <MapEntry<int, String>>[];
    for (int i = 0; i < lines.length; i++) {
      if (lines[i].toLowerCase().contains(q)) {
        out.add(MapEntry(i + 1, lines[i]));
        if (out.length >= 500) break;  // sanity cap for 1-char queries
      }
    }
    return out;
  }

  @override
  Widget build(BuildContext context) {
    final ar = LangProvider.strings(context).ar;
    final p = NurPalette.of(context);
    return NurScaffold(
      title: ar ? 'كود محركات المعالجة' : 'Engine Source Code',
      icon: Icons.code_rounded,
      accent: p.teal,
      intensity: 0.6,
      body: Column(children: [
        // ── engine picker ──────────────────────────────────────────────────
        SizedBox(height: 44,
          child: ListView(
            scrollDirection: Axis.horizontal,
            physics: const BouncingScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 16),
            children: _files.map((f) => Center(child: _fileChip(f, ar, p))).toList())),
        const SizedBox(height: 10),
        // ── actions + search ───────────────────────────────────────────────
        Padding(padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
          child: Row(children: [
            NurIconButton(
                icon: Icons.copy_rounded, size: 40,
                tooltip: ar ? 'نسخ' : 'Copy', onTap: _copySrc),
            const SizedBox(width: 8),
            NurIconButton(
                icon: Icons.download_rounded, size: 40, color: p.gold,
                tooltip: ar ? 'تنزيل' : 'Download', onTap: _downloadSrc),
            const SizedBox(width: 10),
            Expanded(child: SizedBox(height: 40,
              child: TextField(
                onChanged: (v) => setState(() => _query = v),
                style: TextStyle(color: p.text, fontSize: 12.5),
                cursorColor: p.gold,
                decoration: InputDecoration(
                  hintText: ar ? 'ابحث في الكود…' : 'Search in code…',
                  hintStyle: TextStyle(color: p.textDim, fontSize: 12),
                  prefixIcon: Icon(Icons.search_rounded, color: p.textDim, size: 18),
                  filled: true, fillColor: p.surface, isDense: true,
                  contentPadding: EdgeInsets.zero,
                  enabledBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(20),
                      borderSide: BorderSide(color: p.border)),
                  focusedBorder: OutlineInputBorder(
                      borderRadius: BorderRadius.circular(20),
                      borderSide: BorderSide(color: p.gold)),
                )))),
          ])),
        // ── code view ──────────────────────────────────────────────────────
        Expanded(child: FutureBuilder<String>(
          future: _load(_sel),
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return Center(
                  child: CircularProgressIndicator(color: p.gold, strokeWidth: 2.4));
            }
            if (snap.hasError) {
              return Center(child: Text(
                  ar ? 'تعذر تحميل الكود' : 'Could not load source',
                  style: TextStyle(color: p.err)));
            }
            final src = snap.data ?? '';
            final lines = src.split('\n');
            final kb = (src.length / 1024).toStringAsFixed(0);
            final searching = _query.trim().isNotEmpty;
            final matches = searching ? _matches(lines) : const <MapEntry<int, String>>[];
            return Column(children: [
              // stats strip
              Padding(
                padding: const EdgeInsets.fromLTRB(18, 0, 18, 8),
                child: Row(children: [
                  Expanded(child: Text(_sel.fileName,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: p.textDim, fontSize: 11,
                          fontFamily: 'monospace'))),
                  NurChip(
                      label: searching
                          ? (ar ? '${matches.length} نتيجة' : '${matches.length} matches')
                          : '${lines.length} ${ar ? "سطر" : "lines"} · $kb KB',
                      color: p.teal, fontSize: 10.5),
                ])),
              Expanded(child: Container(
                margin: const EdgeInsets.fromLTRB(14, 0, 14, 14),
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                    color: p.dark ? p.bgDeep.withValues(alpha: 0.85) : p.surface,
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(color: p.border)),
                // Code is always LTR regardless of app language.
                child: Directionality(
                  textDirection: TextDirection.ltr,
                  child: searching
                      ? _searchResultsView(matches, ar, p)
                      : _chunkedCodeView(lines, p)))),
            ]);
          })),
      ]),
    );
  }

  // Chunked virtualized rendering — one SelectableText per ~200 lines keeps
  // even the 15k-line الاسترداد source smooth on mid-range phones.
  Widget _chunkedCodeView(List<String> lines, NurPalette p) {
    final chunks = (lines.length / _chunkLines).ceil().clamp(1, 1 << 20);
    return Scrollbar(thumbVisibility: true,
      child: ListView.builder(
        itemCount: chunks,
        itemBuilder: (_, i) {
          final start = i * _chunkLines;
          final end = (start + _chunkLines).clamp(0, lines.length);
          return SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SelectableText(
              lines.sublist(start, end).join('\n'),
              style: TextStyle(color: p.textSub, fontSize: 11.5,
                  fontFamily: 'monospace', height: 1.5)));
        }));
  }

  Widget _searchResultsView(List<MapEntry<int, String>> matches, bool ar, NurPalette p) {
    if (matches.isEmpty) {
      return Center(child: Text(ar ? 'لا نتائج' : 'No matches',
          style: TextStyle(color: p.textDim, fontSize: 12)));
    }
    return ListView.builder(
      itemCount: matches.length,
      itemBuilder: (_, i) {
        final m = matches[i];
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 3),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              SizedBox(width: 48, child: Text('${m.key}',
                  style: TextStyle(color: p.gold, fontSize: 10.5,
                      fontFamily: 'monospace'))),
              SelectableText(m.value,
                  style: TextStyle(color: p.textSub, fontSize: 11.5,
                      fontFamily: 'monospace', height: 1.4)),
            ])));
      });
  }
}
