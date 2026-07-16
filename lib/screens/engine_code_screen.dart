// engine_code_screen.dart — S234
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
