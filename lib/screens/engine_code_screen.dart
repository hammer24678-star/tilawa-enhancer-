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
import '../state/lang_provider.dart';

const _bg      = Color(0xFF020D17);
const _surface = Color(0xFF0C1E28);
const _card    = Color(0xFF0F2420);
const _gold    = Color(0xFFD4AF37);
const _goldDim = Color(0xFF3A2B08);
const _teal    = Color(0xFF1DB898);
const _red     = Color(0xFFD94040);
const _textA   = Color(0xFFE2CFA0);
const _textB   = Color(0xFF8AACBA);
const _textDim = Color(0xFF3D5A65);
const _border  = Color(0xFF1A2E20);

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

  void _snack(String msg, {Color color = _gold}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(msg, style: TextStyle(color: color == _gold ? _bg : Colors.white)),
      backgroundColor: color == _gold ? _gold : color,
      behavior: SnackBarBehavior.floating,
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
      _snack('Error: $e', color: _red);
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

  Widget _fileChip(_EngineFile f, bool ar) {
    final sel = f.asset == _sel.asset;
    return GestureDetector(
      onTap: () {
        if (sel) return;
        HapticFeedback.selectionClick();
        setState(() { _sel = f; _query = ''; });
      },
      child: Container(
        margin: const EdgeInsetsDirectional.only(end: 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
        decoration: BoxDecoration(
          color: sel ? _goldDim.withValues(alpha: 0.45) : _card,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: sel ? _gold : _border, width: sel ? 1.4 : 1)),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Text(ar ? f.nameAr : f.nameEn,
              style: TextStyle(color: sel ? _gold : _textB, fontSize: 11.5,
                  fontWeight: sel ? FontWeight.w800 : FontWeight.w500)),
          const SizedBox(width: 6),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
            decoration: BoxDecoration(
              color: sel ? _gold.withValues(alpha: 0.14) : _surface,
              borderRadius: BorderRadius.circular(6)),
            child: Text(f.tag, style: TextStyle(
                color: sel ? _gold : _textDim, fontSize: 8.5,
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
    return Directionality(
      textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
      child: Scaffold(
        backgroundColor: _bg,
        appBar: AppBar(
          backgroundColor: _bg,
          foregroundColor: _textA,
          elevation: 0,
          title: Text(ar ? 'كود محركات المعالجة' : 'Engine Source Code',
              style: const TextStyle(color: _textA, fontSize: 15, fontWeight: FontWeight.w700)),
        ),
        body: Column(children: [
          // ── engine picker ────────────────────────────────────────────────
          SizedBox(height: 40,
            child: ListView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 14),
              children: _files.map((f) => Center(child: _fileChip(f, ar))).toList())),
          const SizedBox(height: 8),
          // ── actions + search ─────────────────────────────────────────────
          Padding(padding: const EdgeInsets.fromLTRB(14, 0, 14, 8),
            child: Row(children: [
              _pill(ar ? 'نسخ' : 'Copy', Icons.copy_rounded, _copySrc),
              const SizedBox(width: 8),
              _pill(ar ? 'تنزيل' : 'Download', Icons.download_rounded, _downloadSrc, gold: true),
              const SizedBox(width: 10),
              Expanded(child: SizedBox(height: 34,
                child: TextField(
                  onChanged: (v) => setState(() => _query = v),
                  style: const TextStyle(color: _textA, fontSize: 12),
                  decoration: InputDecoration(
                    hintText: ar ? 'ابحث في الكود…' : 'Search in code…',
                    hintStyle: const TextStyle(color: _textDim, fontSize: 11),
                    prefixIcon: const Icon(Icons.search_rounded, color: _textDim, size: 16),
                    filled: true, fillColor: _card, isDense: true,
                    contentPadding: EdgeInsets.zero,
                    enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(17),
                        borderSide: const BorderSide(color: _border)),
                    focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(17),
                        borderSide: const BorderSide(color: _gold)),
                  )))),
            ])),
          // ── code view ────────────────────────────────────────────────────
          Expanded(child: FutureBuilder<String>(
            future: _load(_sel),
            builder: (context, snap) {
              if (snap.connectionState != ConnectionState.done) {
                return const Center(
                    child: CircularProgressIndicator(color: _gold, strokeWidth: 2.4));
              }
              if (snap.hasError) {
                return Center(child: Text(
                    ar ? 'تعذر تحميل الكود' : 'Could not load source',
                    style: const TextStyle(color: _red)));
              }
              final src = snap.data ?? '';
              final lines = src.split('\n');
              final kb = (src.length / 1024).toStringAsFixed(0);
              final searching = _query.trim().isNotEmpty;
              final matches = searching ? _matches(lines) : const <MapEntry<int, String>>[];
              return Column(children: [
                // stats strip
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
                  child: Row(children: [
                    Expanded(child: Text(_sel.fileName,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(color: _textDim, fontSize: 10.5,
                            fontFamily: 'monospace'))),
                    Text(searching
                        ? (ar ? '${matches.length} نتيجة' : '${matches.length} matches')
                        : '${lines.length} ${ar ? "سطر" : "lines"} · $kb KB',
                        style: const TextStyle(color: _teal, fontSize: 10.5,
                            fontWeight: FontWeight.w700, fontFamily: 'monospace')),
                  ])),
                Expanded(child: Container(
                  margin: const EdgeInsets.fromLTRB(14, 0, 14, 14),
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  decoration: BoxDecoration(color: _card,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(color: _border)),
                  // Code is always LTR regardless of app language.
                  child: Directionality(
                    textDirection: TextDirection.ltr,
                    child: searching
                        ? _searchResultsView(matches, ar)
                        : _chunkedCodeView(lines)))),
              ]);
            })),
        ]),
      ));
  }

  // Chunked virtualized rendering — one SelectableText per ~200 lines keeps
  // even the 15k-line الاسترداد source smooth on mid-range phones.
  Widget _chunkedCodeView(List<String> lines) {
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
              style: const TextStyle(color: _textB, fontSize: 11.5,
                  fontFamily: 'monospace', height: 1.5)));
        }));
  }

  Widget _searchResultsView(List<MapEntry<int, String>> matches, bool ar) {
    if (matches.isEmpty) {
      return Center(child: Text(ar ? 'لا نتائج' : 'No matches',
          style: const TextStyle(color: _textDim, fontSize: 12)));
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
                  style: const TextStyle(color: _gold, fontSize: 10.5,
                      fontFamily: 'monospace'))),
              SelectableText(m.value,
                  style: const TextStyle(color: _textB, fontSize: 11.5,
                      fontFamily: 'monospace', height: 1.4)),
            ])));
      });
  }
}
