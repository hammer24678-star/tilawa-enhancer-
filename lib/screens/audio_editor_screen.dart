// audio_editor_screen.dart — S203b: AudioLab features, Sacred Cosmos theme
// Trim · Split · 10-band EQ · Effects (Noise Reduce/Compress/Normalize/Reverse)
// Merge · Set as Ringtone · Export via ffmpeg (proot local engine)

import 'dart:async';
import 'dart:math' show pi, sin, pow, Random;
import 'dart:ui' as ui;
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';
import '../state/lang_provider.dart';
import 'setup_screen.dart';  // S206: lets the setup-required snackbar launch setup directly

// ── Sacred Cosmos palette (unchanged) ────────────────────────────────────────
const _bg      = Color(0xFF020D17);
const _surface = Color(0xFF0C1E28);
const _card    = Color(0xFF0F2420);
const _gold    = Color(0xFFD4AF37);
const _goldDim = Color(0xFF3A2B08);
const _teal    = Color(0xFF1DB898);
const _tealDk  = Color(0xFF0A3D2A);
const _red     = Color(0xFFD94040);
const _textA   = Color(0xFFE2CFA0);
const _textB   = Color(0xFF8AACBA);
const _textDim = Color(0xFF3D5A65);
const _border  = Color(0xFF1A2E20);

enum _Tab { trim, eq, effects, merge, export_ }

class AudioEditorScreen extends StatefulWidget {
  const AudioEditorScreen({super.key});
  @override State<AudioEditorScreen> createState() => _AudioEditorScreenState();
}

class _AudioEditorScreenState extends State<AudioEditorScreen>
    with TickerProviderStateMixin {

  String? _filePath;
  String  _fileName = '';
  double  _durationSec = 0;

  final _player = AudioPlayer();
  StreamSubscription<PlayerState>? _stateSub;
  StreamSubscription<Duration>?    _posSub;
  StreamSubscription<Duration>?    _durSub;
  bool   _playing = false;
  double _positionSec = 0;

  double _trimStart = 0;
  double _trimEnd   = 1;

  // 10-band EQ  31/63/125/250/500/1k/2k/4k/8k/16k Hz
  final List<double> _eq = List.filled(10, 0);
  static const _bands = ['31','63','125','250','500','1k','2k','4k','8k','16k'];
  static const _freqs = [31,63,125,250,500,1000,2000,4000,8000,16000];

  double _fadeIn    = 0;
  double _fadeOut   = 0;
  double _pitch     = 0;
  double _tempo     = 1.0;
  double _echo      = 0;
  double _reverb    = 0;
  double _vol       = 1.0;
  double _stereoW   = 1.0;
  bool   _normalize = false;
  bool   _reverse   = false;
  double _noiseReduc = 0;   // 0-100
  bool   _compress  = false;
  double _compThresh = -18.0;
  double _compRatio  = 4.0;

  // Merge
  String? _mergePath;
  String  _mergeName = '';
  bool    _mergeAppend = true;

  // Export
  String _fmt      = 'MP3';
  int    _kbps     = 192;
  bool   _asRingtone = false;
  bool   _busy     = false;
  double _pct      = 0;
  String? _outPath;
  String  _busyLabel = '';

  _Tab _tab = _Tab.trim;
  late AnimationController _waveCtrl;
  late AnimationController _glowCtrl;
  late List<double> _bars;

  static const _ch    = MethodChannel('com.tilawa.tilawa_enhancer/local_engine');
  static const _media = MethodChannel('com.tilawa.tilawa_enhancer/media');

  @override
  void initState() {
    super.initState();
    final rng = Random(42);
    _bars = List.generate(80, (_) => 0.1 + rng.nextDouble() * 0.9);
    _waveCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 3))..repeat();
    _glowCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 2))..repeat(reverse: true);
    _stateSub = _player.onPlayerStateChanged.listen((s) {
      if (mounted) setState(() => _playing = s == PlayerState.playing);
    });
    _posSub = _player.onPositionChanged.listen((d) {
      if (mounted) setState(() => _positionSec = d.inMilliseconds / 1000.0);
    });
    _durSub = _player.onDurationChanged.listen((d) {
      if (mounted) setState(() => _durationSec = d.inMilliseconds / 1000.0);
    });
  }

  @override
  void dispose() {
    _stateSub?.cancel(); _posSub?.cancel(); _durSub?.cancel();
    _player.dispose(); _waveCtrl.dispose(); _glowCtrl.dispose();
    super.dispose();
  }

  String _fmtTime(double s) {
    final m = s ~/ 60; final ss = (s % 60).toStringAsFixed(1);
    return '${m.toString().padLeft(2,'0')}:${ss.padLeft(4,'0')}';
  }

  Future<bool> _checkSetup() async {
    final ok = await _ch.invokeMethod<bool>('isBasicSetupComplete') ?? false;
    // S206: old message sent users to "Settings" to finish setup, but
    // settings_screen.dart has no local-engine setup code at all — the only
    // real entry point was buried in home_screen.dart's local-mode toggle.
    // Launch SetupScreen directly instead of pointing at a dead end.
    if (!ok && mounted) {
      final ar = LangProvider.strings(context).ar;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        backgroundColor: _card, behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10),
            side: const BorderSide(color: _red, width: 0.7)),
        content: Text(ar ? 'يلزم إعداد المحرك المحلي أولًا' : 'Local engine setup is required first.',
            style: const TextStyle(color: _red, fontSize: 11)),
        action: SnackBarAction(label: ar ? 'إعداد الآن' : 'Set Up Now', textColor: _gold,
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => SetupScreen(
                    onDone: () { if (mounted) Navigator.of(context).pop(); },
                    onSkip: () { if (mounted) Navigator.of(context).pop(); })))),
        duration: const Duration(seconds: 6)));
    }
    return ok;
  }

  Future<String> _safeInput(String path) async {
    final tmp = await getTemporaryDirectory();
    final ext = path.split('.').last;
    final safe = File('${tmp.path}/tl_${DateTime.now().millisecondsSinceEpoch}.$ext');
    await File(path).copy(safe.path); return safe.path;
  }

  Future<String> _outFile(String suffix, String ext) async {
    final dir = await getExternalStorageDirectory() ?? await getApplicationDocumentsDirectory();
    final base = _fileName.replaceAll(RegExp(r'\.[^.]+$'), '');
    return '${dir.path}/tilawa_${base}_$suffix.$ext';
  }

  Future<Map?> _proot(String cmd, String inp, String out, {int timeout = 10}) =>
    _ch.invokeMethod<Map>('runProotCmd', {
      'cmd': cmd, 'inputPath': inp, 'outputPath': out, 'timeoutMin': timeout,
    });

  void _snack(String msg, {Color color = _gold}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      backgroundColor: _card, behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10),
          side: BorderSide(color: color, width: 0.7)),
      content: Text(msg, style: TextStyle(color: color, fontSize: 11)),
      duration: const Duration(seconds: 4)));
  }

  void _warnBusy() => _snack('Processing… please wait', color: _gold);

  Future<void> _pick() async {
    if (_playing) await _player.stop();
    final r = await FilePicker.platform.pickFiles(type: FileType.audio, allowMultiple: false);
    if (r == null || r.files.isEmpty || r.files.first.path == null) return;
    final f = r.files.first;
    if (!mounted) return;
    setState(() {
      _filePath = f.path; _fileName = f.name;
      _durationSec = 0; _positionSec = 0; _trimStart = 0; _trimEnd = 1; _outPath = null;
    });
    await _player.setSource(DeviceFileSource(f.path!));
  }

  Future<void> _pickMerge() async {
    final r = await FilePicker.platform.pickFiles(type: FileType.audio, allowMultiple: false);
    if (r == null || r.files.isEmpty || r.files.first.path == null) return;
    if (!mounted) return;
    setState(() { _mergePath = r.files.first.path; _mergeName = r.files.first.name; });
  }

  Future<void> _togglePlay() async {
    if (_filePath == null) return;
    HapticFeedback.lightImpact();
    if (_playing) { await _player.pause(); return; }
    await _player.seek(Duration(milliseconds: (_trimStart * _durationSec * 1000).round()));
    await _player.resume();
  }

  Future<void> _stop() async {
    await _player.stop();
    if (mounted) setState(() => _positionSec = _trimStart * _durationSec);
  }

  // ── SPLIT ─────────────────────────────────────────────────────────────────
  Future<void> _split() async {
    if (_filePath == null) return;
    if (!await _checkSetup()) return;
    HapticFeedback.mediumImpact();
    setState(() { _busy = true; _busyLabel = 'Splitting…'; _pct = 0.1; });
    try {
      final inp = await _safeInput(_filePath!);
      final ext = _fmt.toLowerCase();
      final outA = await _outFile('part1', ext);
      final outB = await _outFile('part2', ext);
      final sp   = _positionSec.toStringAsFixed(3);
      final r1 = await _proot('ffmpeg -y -i "$inp" -t $sp -acodec ${_codec()} ${_br()} "$outA"', inp, outA);
      if ((r1?['rc'] as int? ?? 1) != 0) throw Exception('Split part1 failed');
      setState(() => _pct = 0.6);
      final r2 = await _proot('ffmpeg -y -ss $sp -i "$inp" -acodec ${_codec()} ${_br()} "$outB"', inp, outB);
      if ((r2?['rc'] as int? ?? 1) != 0) throw Exception('Split part2 failed');
      setState(() { _pct = 1.0; _busy = false; });
      _snack('✓ Split: part1.$ext + part2.$ext');
    } catch (e) {
      setState(() => _busy = false); _snack('Error: $e', color: _red);
    }
  }

  // ── MERGE ─────────────────────────────────────────────────────────────────
  Future<void> _merge() async {
    if (_filePath == null || _mergePath == null) return;
    if (!await _checkSetup()) return;
    HapticFeedback.mediumImpact();
    setState(() { _busy = true; _busyLabel = 'Merging…'; _pct = 0.1; });
    try {
      final tmp  = await getTemporaryDirectory();
      final inpA = await _safeInput(_filePath!);
      final inpB = await _safeInput(_mergePath!);
      final wavA = '${tmp.path}/tl_mA.wav'; final wavB = '${tmp.path}/tl_mB.wav';
      final list = '${tmp.path}/tl_list.txt';
      final ext  = _fmt.toLowerCase();
      final out  = await _outFile('merged', ext);
      await _proot('ffmpeg -y -i "$inpA" -ar 48000 -ac 2 "$wavA"', inpA, wavA);
      setState(() => _pct = 0.3);
      await _proot('ffmpeg -y -i "$inpB" -ar 48000 -ac 2 "$wavB"', inpB, wavB);
      setState(() => _pct = 0.5);
      final fa = _mergeAppend ? wavA : wavB; final fb = _mergeAppend ? wavB : wavA;
      File(list).writeAsStringSync("file '$fa'\nfile '$fb'\n");
      final r = await _proot(
          'ffmpeg -y -f concat -safe 0 -i "$list" -acodec ${_codec()} ${_br()} "$out"',
          list, out, timeout: 15);
      if ((r?['rc'] as int? ?? 1) != 0) throw Exception('Merge failed: ${r?['out']}');
      setState(() { _pct = 1.0; _busy = false; _outPath = out; });
      _snack('✓ Merged → $out');
    } catch (e) {
      setState(() => _busy = false); _snack('Error: $e', color: _red);
    }
  }

  // ── EXPORT ────────────────────────────────────────────────────────────────
  String _codec() => _fmt == 'WAV' ? 'pcm_s16le' : _fmt == 'M4A' ? 'aac' : 'libmp3lame';
  String _br()    => _fmt == 'WAV' ? '' : '-b:a ${_kbps}k';

  List<String> _buildAf() {
    final af = <String>[];
    if (_reverse) af.add('areverse');
    if (_noiseReduc > 0)
      af.add('afftdn=nr=${(_noiseReduc * 0.97).toStringAsFixed(1)}:nf=-25');
    if (_fadeIn  > 0) af.add('afade=t=in:d=${_fadeIn.toStringAsFixed(1)}');
    if (_fadeOut > 0) {
      final st = ((_trimEnd - _trimStart) * _durationSec - _fadeOut)
          .clamp(0.0, double.infinity).toStringAsFixed(2);
      af.add('afade=t=out:st=$st:d=${_fadeOut.toStringAsFixed(1)}');
    }
    for (int i = 0; i < 10; i++) {
      if (_eq[i].abs() > 0.5)
        af.add('equalizer=f=${_freqs[i]}:g=${_eq[i].toStringAsFixed(1)}');
    }
    if (_echo   > 0) af.add('aecho=0.8:${(_echo/100).toStringAsFixed(2)}:500:0.5');
    if (_reverb > 0) af.add('aecho=0.8:${(_reverb/100).toStringAsFixed(2)}:80:0.3');
    if (_pitch  != 0) {
      final r = (pow(2.0, _pitch / 12.0) as double);
      final co = (1.0 / r).clamp(0.5, 2.0).toStringAsFixed(6);
      af.add('asetrate=44100*${r.toStringAsFixed(6)},aresample=44100,atempo=$co');
    }
    if (_tempo != 1.0) af.add('atempo=${_tempo.clamp(0.5,2.0).toStringAsFixed(2)}');
    if (_stereoW != 1.0) af.add('stereotools=mlev=${_stereoW.toStringAsFixed(2)}');
    if (_compress)
      af.add('acompressor=threshold=${_compThresh.toStringAsFixed(1)}dB'
          ':ratio=${_compRatio.toStringAsFixed(1)}:attack=20:release=200');
    if (_normalize) af.add('loudnorm');
    if (_vol != 1.0) af.add('volume=${_vol.toStringAsFixed(2)}');
    return af;
  }

  Future<void> _export() async {
    if (_filePath == null) return;
    if (!await _checkSetup()) return;
    HapticFeedback.mediumImpact();
    setState(() { _busy = true; _pct = 0.05; _outPath = null; _busyLabel = 'Exporting…'; });
    try {
      final inp = await _safeInput(_filePath!);
      final ext = _fmt.toLowerCase();
      final out = await _outFile('edited', ext);
      final ss  = (_trimStart * _durationSec).toStringAsFixed(3);
      final dur = ((_trimEnd - _trimStart) * _durationSec).toStringAsFixed(3);
      final af  = _buildAf();
      final cmd = 'ffmpeg -y -ss $ss -i "$inp" -t $dur '
          '-af ${af.isEmpty ? "anull" : af.join(",")} -acodec ${_codec()} ${_br()} "$out"';
      setState(() => _pct = 0.2);
      final r = await _proot(cmd, inp, out, timeout: 15);
      final rc = (r?['rc'] as int?) ?? 1;
      if (rc != 0) throw Exception('ffmpeg rc=$rc: ${r?['out'] ?? ''}');
      if (!mounted) return;
      setState(() { _pct = 1.0; _outPath = out; _busy = false; });
      if (_asRingtone) {
        try { await _media.invokeMethod('saveToDownloads',
            {'path': out, 'filename': out.split('/').last}); }
        catch (_) {}
      }
      _snack('✓ Saved: $out');
    } catch (e) {
      setState(() => _busy = false); _snack('Error: $e', color: _red);
    }
  }

  // ── BUILD ─────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext ctx) => Directionality(
    textDirection: LangProvider.strings(ctx).ar ? TextDirection.rtl : TextDirection.ltr,
    child: PopScope(
      canPop: !_busy,
      onPopInvokedWithResult: (didPop, _) { if (!didPop) _warnBusy(); },
      child: Scaffold(
        backgroundColor: _bg,
        body: SafeArea(child: Stack(children: [
          Column(children: [
            _appBar(),
            Expanded(child: _filePath == null ? _pickerView() : _editorView()),
          ]),
          if (_busy) _processingOverlay(),
        ])),
      )));

  Widget _processingOverlay() => AbsorbPointer(
    child: AnimatedBuilder(animation: _glowCtrl,
      builder: (_, __) => Container(
        color: Colors.black.withValues(alpha: 0.72),
        alignment: Alignment.center,
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          SizedBox(width: 92, height: 92,
            child: Stack(alignment: Alignment.center, children: [
              Container(width: 92, height: 92, decoration: BoxDecoration(
                shape: BoxShape.circle,
                border: Border.all(
                  color: _gold.withValues(alpha: 0.18 + 0.30 * _glowCtrl.value), width: 1.4),
                boxShadow: [BoxShadow(
                  color: _gold.withValues(alpha: 0.06 + 0.14 * _glowCtrl.value), blurRadius: 28)])),
              SizedBox(width: 68, height: 68,
                child: CircularProgressIndicator(value: _pct > 0.05 ? _pct : null,
                  strokeWidth: 3, backgroundColor: _border,
                  valueColor: AlwaysStoppedAnimation(Color.lerp(_teal, _gold, _glowCtrl.value)!),
                  strokeCap: StrokeCap.round)),
              const Icon(Icons.audio_file_rounded, color: _gold, size: 26),
            ])),
          const SizedBox(height: 18),
          Text(_busyLabel, style: const TextStyle(color: _gold, fontSize: 18, fontWeight: FontWeight.w800)),
          const SizedBox(height: 5),
          const Text("Please wait — don't close the screen", style: TextStyle(color: _textB, fontSize: 12)),
          const SizedBox(height: 18),
          SizedBox(width: 220, child: ClipRRect(borderRadius: BorderRadius.circular(6),
            child: LinearProgressIndicator(value: _pct > 0.05 ? _pct : null,
              backgroundColor: _border, valueColor: const AlwaysStoppedAnimation(_gold), minHeight: 5))),
          if (_pct > 0.05) ...[const SizedBox(height: 8),
            Text('${(_pct * 100).round()}%', style: const TextStyle(color: _textB, fontSize: 12))],
        ]))));

  Widget _appBar() {
    final ar = LangProvider.strings(context).ar;
    return Container(
      decoration: BoxDecoration(color: _surface,
        border: Border(bottom: BorderSide(color: _gold.withValues(alpha: 0.25), width: 1))),
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child: Row(children: [
        IconButton(icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: _textB),
          onPressed: () => _busy ? _warnBusy() : Navigator.pop(context)),
        Expanded(child: ShaderMask(
          shaderCallback: (b) => const LinearGradient(colors: [_gold, Color(0xFFF0CF60)]).createShader(b),
          child: Text(ar ? 'محرر الصوت' : 'Audio Editor',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w700)))),
        IconButton(icon: const Icon(Icons.info_outline_rounded, size: 18, color: _textB),
          onPressed: _showHelp),
        if (_filePath != null)
          TextButton(onPressed: _pick,
            child: Text(ar ? 'تغيير' : 'Change',
                style: const TextStyle(color: _teal, fontSize: 12, fontWeight: FontWeight.w600)))
        else const SizedBox(width: 8),
      ]));
  }

  void _showHelp() {
    final ar = LangProvider.strings(context).ar;
    showDialog(context: context, builder: (_) => Directionality(
      textDirection: ar ? TextDirection.rtl : TextDirection.ltr,
      child: AlertDialog(
        backgroundColor: _card,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14),
            side: const BorderSide(color: _gold, width: 0.7)),
        title: Text(ar ? 'عن محرر الصوت' : 'Audio Editor',
            style: const TextStyle(color: _gold, fontWeight: FontWeight.w700)),
        content: Text(ar
            ? '• قص: حدد نطاق البداية والنهاية.\n'
              '• تقسيم: اضغط ✂️ في التشغيل لتقسيم الملف عند الموضع الحالي.\n'
              '• موازن 10 أحزمة: 31Hz إلى 16kHz مع إعدادات مسبقة.\n'
              '• تأثيرات: تلاشي، طبقة صوت، سرعة، صدى، إرجاع، عكس، تقليص ضوضاء، ضغط، تطبيع، عرض ستيريو.\n'
              '• دمج: جمع ملفين صوتيين.\n'
              '• تصدير: MP3/WAV/M4A + حفظ كنغمة رنين.\n'
              '⚙️ محلي بالكامل عبر ffmpeg — بدون إنترنت.'
            : '• Trim: set start/end range.\n'
              '• Split: tap ✂️ in transport to split at playhead into two files.\n'
              '• 10-band EQ: 31Hz–16kHz with presets.\n'
              '• Effects: fade, pitch, speed, echo, reverb, reverse, noise reduction, compressor, normalize, stereo width.\n'
              '• Merge: join two audio files.\n'
              '• Export: MP3/WAV/M4A + Set as Ringtone.\n'
              '⚙️ Fully local via ffmpeg — no internet needed.',
          style: const TextStyle(color: _textA, fontSize: 13, height: 1.5)),
        actions: [TextButton(onPressed: () => Navigator.pop(context),
          child: Text(ar ? 'حسنًا' : 'OK', style: const TextStyle(color: _teal)))],
      )));
  }

  Widget _pickerView() {
    final ar = LangProvider.strings(context).ar;
    return Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      AnimatedBuilder(animation: _glowCtrl,
        builder: (_, __) => Container(width: 130, height: 130,
          decoration: BoxDecoration(shape: BoxShape.circle, color: _card,
            border: Border.all(color: _gold.withValues(alpha: 0.18 + 0.28 * _glowCtrl.value), width: 1.5),
            boxShadow: [BoxShadow(color: _gold.withValues(alpha: 0.04 + 0.08 * _glowCtrl.value), blurRadius: 36)]),
          child: const Icon(Icons.audio_file_rounded, color: _gold, size: 52))),
      const SizedBox(height: 24),
      Text(ar ? 'اختر ملف صوتي' : 'Choose an audio file',
          style: const TextStyle(color: _textA, fontSize: 20, fontWeight: FontWeight.w700)),
      const SizedBox(height: 8),
      const Text('MP3 · WAV · M4A · AAC · OGG · FLAC',
          style: TextStyle(color: _textB, fontSize: 13)),
      const SizedBox(height: 32),
      GestureDetector(onTap: _pick,
        child: AnimatedBuilder(animation: _glowCtrl,
          builder: (_, __) => Container(
            padding: const EdgeInsets.symmetric(horizontal: 44, vertical: 17),
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [Color(0xFF6B4F10), _gold],
                  begin: Alignment.centerRight, end: Alignment.centerLeft),
              borderRadius: BorderRadius.circular(14),
              boxShadow: [BoxShadow(
                  color: _gold.withValues(alpha: 0.2 + 0.15 * _glowCtrl.value),
                  blurRadius: 18, offset: const Offset(0, 4))]),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.folder_open_rounded, color: Color(0xFF0A0A00), size: 22),
              const SizedBox(width: 10),
              Text(ar ? 'فتح ملف' : 'Open File',
                  style: const TextStyle(color: Color(0xFF0A0A00), fontSize: 16, fontWeight: FontWeight.w800)),
            ])))),
    ]));
  }

  Widget _editorView() => Column(children: [
    _fileBar(), _waveformSection(), _transport(), _tabBar(),
    Expanded(child: _tabBody()),
  ]);

  Widget _fileBar() => Container(
    color: _surface,
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
    child: Row(children: [
      const Icon(Icons.music_note_rounded, color: _teal, size: 16),
      const SizedBox(width: 8),
      Expanded(child: Text(_fileName, overflow: TextOverflow.ellipsis,
          style: const TextStyle(color: _textA, fontSize: 13, fontWeight: FontWeight.w500))),
      const SizedBox(width: 10),
      Text(_fmtTime(_durationSec),
          style: const TextStyle(color: _textB, fontSize: 12, fontFamily: 'monospace')),
    ]));

  Widget _waveformSection() {
    final pos = _durationSec > 0 ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0.0;
    return GestureDetector(
      onTapDown: (d) {
        final box = context.findRenderObject() as RenderBox?;
        if (box == null) return;
        final frac = (d.localPosition.dx / box.size.width).clamp(0.0, 1.0);
        _player.seek(Duration(milliseconds: (frac * _durationSec * 1000).round()));
        setState(() => _positionSec = frac * _durationSec);
      },
      child: AnimatedBuilder(animation: _waveCtrl,
        builder: (_, __) => SizedBox(height: 96,
          child: CustomPaint(
            painter: _WavePainter(bars: _bars, playPos: pos,
              trimStart: _trimStart, trimEnd: _trimEnd,
              animT: _waveCtrl.value, playing: _playing),
            size: const Size(double.infinity, 96)))));
  }

  Widget _transport() => Container(
    color: _surface,
    padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
    child: Row(children: [
      _tBtn(Icons.skip_previous_rounded, () async {
        await _player.seek(Duration(milliseconds: (_trimStart * _durationSec * 1000).round()));
        if (mounted) setState(() => _positionSec = _trimStart * _durationSec);
      }),
      const SizedBox(width: 10),
      AnimatedBuilder(animation: _glowCtrl,
        builder: (_, __) => GestureDetector(onTap: _togglePlay,
          child: Container(width: 52, height: 52,
            decoration: BoxDecoration(shape: BoxShape.circle,
              gradient: const RadialGradient(colors: [Color(0xFFB8921E), _goldDim]),
              boxShadow: [BoxShadow(
                  color: _gold.withValues(alpha: _playing ? 0.15 + 0.2 * _glowCtrl.value : 0.05),
                  blurRadius: 18)]),
            child: Icon(_playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
              color: const Color(0xFF050A06), size: 28)))),
      const SizedBox(width: 10),
      _tBtn(Icons.stop_rounded, _stop),
      const SizedBox(width: 6),
      Tooltip(message: 'Split at playhead',
        child: _tBtn(Icons.content_cut_rounded, _split, color: _teal)),
      const SizedBox(width: 12),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min, children: [
        Row(children: [
          Text(_fmtTime(_positionSec), style: const TextStyle(color: _gold, fontSize: 11,
              fontWeight: FontWeight.w600, fontFamily: 'monospace')),
          const Text(' / ', style: TextStyle(color: _textDim, fontSize: 11)),
          Text(_fmtTime(_durationSec), style: const TextStyle(color: _textB, fontSize: 11, fontFamily: 'monospace')),
        ]),
        const SizedBox(height: 4),
        ClipRRect(borderRadius: BorderRadius.circular(3),
          child: LinearProgressIndicator(
            value: _durationSec > 0 ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0,
            backgroundColor: _border, valueColor: const AlwaysStoppedAnimation(_gold), minHeight: 3)),
      ])),
      const SizedBox(width: 10),
      _tBtn(Icons.loop_rounded, () async { await _player.setReleaseMode(ReleaseMode.loop); }, color: _teal),
    ]));

  Widget _tBtn(IconData icon, VoidCallback onTap, {Color? color}) =>
    GestureDetector(onTap: onTap,
      child: Container(width: 38, height: 38,
        decoration: BoxDecoration(shape: BoxShape.circle, color: _card,
            border: Border.all(color: _border)),
        child: Icon(icon, color: color ?? _textB, size: 19)));

  Widget _tabBar() {
    final ar = LangProvider.strings(context).ar;
    final labels = ar ? ['قص','EQ','تأثيرات','دمج','تصدير']
                      : ['Trim','EQ','Effects','Merge','Export'];
    final icons = [Icons.content_cut_rounded, Icons.equalizer_rounded,
                   Icons.auto_fix_high_rounded, Icons.merge_type_rounded, Icons.ios_share_rounded];
    return Container(
      decoration: BoxDecoration(color: _surface, border: Border(bottom: BorderSide(color: _border))),
      child: Row(children: _Tab.values.map((t) {
        final active = t == _tab;
        return Expanded(child: GestureDetector(
          onTap: () { HapticFeedback.selectionClick(); setState(() => _tab = t); },
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(border: Border(bottom: BorderSide(
                color: active ? _gold : Colors.transparent, width: 2))),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(icons[t.index], color: active ? _gold : _textDim, size: 19),
              const SizedBox(height: 3),
              Text(labels[t.index], style: TextStyle(
                  color: active ? _gold : _textDim,
                  fontSize: 10, fontWeight: FontWeight.w600)),
            ]))));
      }).toList()));
  }

  Widget _tabBody() {
    switch (_tab) {
      case _Tab.trim:    return _trimTab();
      case _Tab.eq:      return _eqTab();
      case _Tab.effects: return _effectsTab();
      case _Tab.merge:   return _mergeTab();
      case _Tab.export_: return _exportTab();
    }
  }

  // ── TRIM TAB ──────────────────────────────────────────────────────────────
  Widget _trimTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _card_(ar ? 'نقطة البداية' : 'Start Point', Icons.align_horizontal_left_rounded, [
        Row(children: [
          Text(_fmtTime(_trimStart * _durationSec),
              style: const TextStyle(color: _teal, fontSize: 15, fontWeight: FontWeight.w800, fontFamily: 'monospace')),
          const Spacer(),
          _chip_(ar ? 'بداية' : 'Start', () => setState(() => _trimStart = 0)),
        ]),
        _slider(_trimStart, 0, _trimEnd - 0.005, _teal, (v) => setState(() => _trimStart = v)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'نقطة النهاية' : 'End Point', Icons.align_horizontal_right_rounded, [
        Row(children: [
          Text(_fmtTime(_trimEnd * _durationSec),
              style: const TextStyle(color: _gold, fontSize: 15, fontWeight: FontWeight.w800, fontFamily: 'monospace')),
          const Spacer(),
          _chip_(ar ? 'نهاية' : 'End', () => setState(() => _trimEnd = 1)),
        ]),
        _slider(_trimEnd, _trimStart + 0.005, 1.0, _gold, (v) => setState(() => _trimEnd = v)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'مدة التحديد' : 'Selection Duration', Icons.timer_outlined, [
        Center(child: Text(_fmtTime((_trimEnd - _trimStart) * _durationSec),
          style: const TextStyle(color: _gold, fontSize: 30, fontWeight: FontWeight.w800,
              letterSpacing: 1.5, fontFamily: 'monospace'))),
        const SizedBox(height: 12),
        Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
          _chip_(ar ? 'الكل' : 'All', () => setState(() { _trimStart = 0; _trimEnd = 1; })),
          _chip_(ar ? 'النصف الأول' : 'First Half', () => setState(() { _trimStart = 0; _trimEnd = 0.5; })),
          _chip_(ar ? 'النصف الثاني' : 'Second Half', () => setState(() { _trimStart = 0.5; _trimEnd = 1; })),
        ]),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'تقسيم عند موضع التشغيل' : 'Split at Playhead', Icons.call_split_rounded, [
        Text(ar
            ? 'اضغط ✂️ في شريط التشغيل لتقسيم الملف إلى جزأين عند الموضع الحالي.'
            : 'Tap ✂️ in the transport bar to split the file at the current playhead into two files.',
            style: const TextStyle(color: _textB, fontSize: 12, height: 1.5)),
        const SizedBox(height: 8),
        Text('${ar ? "الموضع: " : "Position: "}${_fmtTime(_positionSec)}',
            style: const TextStyle(color: _teal, fontSize: 13, fontWeight: FontWeight.w700, fontFamily: 'monospace')),
      ]),
    ]);
  }

  // ── EQ TAB — 10 bands ─────────────────────────────────────────────────────
  Widget _eqTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _card_(ar ? 'منحنى التعديل' : 'EQ Curve', Icons.show_chart_rounded, [
        SizedBox(height: 72, child: CustomPaint(painter: _EqPainter(values: _eq),
            size: const Size(double.infinity, 72))),
        const SizedBox(height: 10),
        SingleChildScrollView(scrollDirection: Axis.horizontal, child: Row(children: [
          _preset(ar ? 'مسطح'   : 'Flat',       List.filled(10, 0.0)),
          _preset(ar ? 'باس'    : 'Bass',        [6,5,4,1,0,0,-1,-1,-2,-2]),
          _preset(ar ? 'صوت'    : 'Voice',       [-2,-1,0,1,3,5,4,2,1,0]),
          _preset(ar ? 'وضوح'   : 'Clarity',     [-1,0,0,0,1,2,4,5,4,3]),
          _preset(ar ? 'تلاوة'  : 'Recitation',  [3,2,1,1,2,3,3,2,1,1]),
          _preset(ar ? 'ليلة'   : 'Night',       [4,3,2,2,0,0,-1,-2,-2,-3]),
          _preset(ar ? 'مسجد'   : 'Mosque',      [2,2,1,0,0,1,2,2,1,0]),
        ])),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'أحزمة التعديل (10)' : 'EQ Bands (10)', Icons.tune_rounded,
          List.generate(10, (i) {
            final v = _eq[i];
            final c = v > 0 ? _gold : v < 0 ? _teal : _textDim;
            return Padding(padding: const EdgeInsets.only(bottom: 8),
              child: Row(children: [
                SizedBox(width: 38, child: Text(_bands[i], style: const TextStyle(color: _textB, fontSize: 11))),
                Expanded(child: Directionality(textDirection: TextDirection.ltr,
                  child: SliderTheme(data: SliderThemeData(trackHeight: 3,
                    thumbSize: WidgetStateProperty.all(const Size(13, 13)),
                    thumbColor: c, activeTrackColor: c.withValues(alpha: 0.75),
                    inactiveTrackColor: _border, overlayColor: c.withValues(alpha: 0.12)),
                    child: Slider(value: v, min: -12, max: 12, divisions: 24,
                        onChanged: (val) => setState(() => _eq[i] = val))))),
                SizedBox(width: 52, child: Text('${v >= 0 ? "+" : ""}${v.toStringAsFixed(1)}',
                    textAlign: TextAlign.end,
                    style: TextStyle(color: c, fontSize: 11, fontWeight: FontWeight.w600))),
              ]));
          })),
    ]);
  }

  // ── EFFECTS TAB ───────────────────────────────────────────────────────────
  Widget _effectsTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _card_(ar ? 'الصوت' : 'Audio', Icons.volume_up_rounded, [
        _knob(ar ? 'مستوى الصوت' : 'Volume', '${(_vol*100).round()}%', _vol, 0.5, 2.0, (v) => setState(() => _vol = v)),
        _knob(ar ? 'درجة الصوت'  : 'Pitch',  '${_pitch>=0?"+":""}${_pitch.toStringAsFixed(1)} st', _pitch, -12, 12, (v) => setState(() => _pitch = v)),
        _knob(ar ? 'السرعة'       : 'Speed',  '${_tempo.toStringAsFixed(2)}×', _tempo, 0.5, 2.0, (v) => setState(() => _tempo = v)),
        _knob(ar ? 'عرض الستيريو' : 'Stereo Width', '${(_stereoW*100).round()}%', _stereoW, 0.5, 2.0, (v) => setState(() => _stereoW = v)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'تلاشي' : 'Fade', Icons.trending_flat_rounded, [
        _knob(ar ? 'دخول (Fade In)'  : 'Fade In',  '${_fadeIn.toStringAsFixed(1)}s',  _fadeIn,  0, 10, (v) => setState(() => _fadeIn = v)),
        _knob(ar ? 'خروج (Fade Out)' : 'Fade Out', '${_fadeOut.toStringAsFixed(1)}s', _fadeOut, 0, 10, (v) => setState(() => _fadeOut = v)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'فضاء صوتي' : 'Space', Icons.surround_sound_rounded, [
        _knob(ar ? 'صدى (Echo)'      : 'Echo',   '${_echo.round()}%',   _echo,   0, 100, (v) => setState(() => _echo = v)),
        _knob(ar ? 'إرجاع (Reverb)' : 'Reverb', '${_reverb.round()}%', _reverb, 0, 100, (v) => setState(() => _reverb = v)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'تقليص الضوضاء' : 'Noise Reduction', Icons.noise_aware_rounded, [
        Text(ar ? 'مرشح afftdn — 0 = معطل' : 'afftdn filter — 0 = disabled',
            style: const TextStyle(color: _textDim, fontSize: 11)),
        const SizedBox(height: 8),
        _knob(ar ? 'قوة التقليص' : 'Strength',
            _noiseReduc == 0 ? (ar ? 'معطل' : 'Off') : '${_noiseReduc.round()}%',
            _noiseReduc, 0, 100, (v) => setState(() => _noiseReduc = v)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'ضاغط ديناميكي' : 'Compressor', Icons.compress_rounded, [
        _toggle(ar ? 'تفعيل الضاغط' : 'Enable Compressor',
            Icons.compress_rounded, _compress, (v) => setState(() => _compress = v)),
        if (_compress) ...[const SizedBox(height: 10),
          _knob(ar ? 'عتبة' : 'Threshold', '${_compThresh.toStringAsFixed(0)} dB',
              _compThresh, -40, 0, (v) => setState(() => _compThresh = v)),
          _knob(ar ? 'نسبة' : 'Ratio', '${_compRatio.toStringAsFixed(1)}:1',
              _compRatio, 1, 20, (v) => setState(() => _compRatio = v)),
        ],
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'تأثيرات إضافية' : 'Extra', Icons.auto_awesome_rounded, [
        _toggle(ar ? 'تطبيع (Normalize)' : 'Normalize', Icons.graphic_eq_rounded, _normalize, (v) => setState(() => _normalize = v)),
        const SizedBox(height: 6),
        _toggle(ar ? 'عكس (Reverse)'    : 'Reverse',   Icons.swap_horiz_rounded,  _reverse,   (v) => setState(() => _reverse = v)),
      ]),
      const SizedBox(height: 10),
      GestureDetector(
        onTap: () {
          HapticFeedback.mediumImpact();
          setState(() {
            _vol=1.0; _pitch=0; _tempo=1.0; _stereoW=1.0;
            _fadeIn=0; _fadeOut=0; _echo=0; _reverb=0;
            _noiseReduc=0; _compress=false; _compThresh=-18; _compRatio=4.0;
            _normalize=false; _reverse=false;
          });
        },
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 13),
          decoration: BoxDecoration(color: _tealDk, borderRadius: BorderRadius.circular(10),
              border: Border.all(color: _teal.withValues(alpha: 0.3))),
          child: Center(child: Row(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.restart_alt_rounded, color: _teal, size: 17),
            const SizedBox(width: 6),
            Text(ar ? 'إعادة ضبط التأثيرات' : 'Reset All Effects',
                style: const TextStyle(color: _teal, fontSize: 13, fontWeight: FontWeight.w600)),
          ])))),
    ]);
  }

  // ── MERGE TAB ─────────────────────────────────────────────────────────────
  Widget _mergeTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _card_(ar ? 'الملف الرئيسي' : 'Main File', Icons.audio_file_rounded, [
        Row(children: [
          const Icon(Icons.check_circle_rounded, color: _teal, size: 16),
          const SizedBox(width: 8),
          Expanded(child: Text(_fileName, overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: _textA, fontSize: 13))),
        ]),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'الملف الثاني' : 'Second File', Icons.audio_file_outlined, [
        if (_mergePath == null)
          GestureDetector(onTap: _pickMerge,
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 14),
              decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: _teal.withValues(alpha: 0.4))),
              child: Center(child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.add_rounded, color: _teal, size: 20),
                const SizedBox(width: 8),
                Text(ar ? 'اختر الملف الثاني' : 'Pick second file',
                    style: const TextStyle(color: _teal, fontSize: 14, fontWeight: FontWeight.w600)),
              ]))))
        else
          Row(children: [
            const Icon(Icons.audio_file_rounded, color: _gold, size: 16),
            const SizedBox(width: 8),
            Expanded(child: Text(_mergeName, overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: _textA, fontSize: 13))),
            IconButton(icon: const Icon(Icons.close_rounded, color: _red, size: 18),
              onPressed: () => setState(() { _mergePath = null; _mergeName = ''; })),
          ]),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'الترتيب' : 'Order', Icons.sort_rounded, [
        GestureDetector(onTap: () => setState(() => _mergeAppend = true),
          child: _orderRow(ar ? 'الرئيسي ثم الثاني' : 'Main → Second', _mergeAppend)),
        const SizedBox(height: 8),
        GestureDetector(onTap: () => setState(() => _mergeAppend = false),
          child: _orderRow(ar ? 'الثاني ثم الرئيسي' : 'Second → Main', !_mergeAppend)),
      ]),
      const SizedBox(height: 14),
      if (_mergePath != null)
        GestureDetector(onTap: _busy ? null : _merge,
          child: AnimatedBuilder(animation: _glowCtrl,
            builder: (_, __) => Container(
              padding: const EdgeInsets.symmetric(vertical: 16),
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [Color(0xFF6B4F10), _gold],
                    begin: Alignment.centerRight, end: Alignment.centerLeft),
                borderRadius: BorderRadius.circular(12),
                boxShadow: [BoxShadow(color: _gold.withValues(alpha: 0.12 + 0.12 * _glowCtrl.value),
                    blurRadius: 18, offset: const Offset(0, 4))]),
              child: Center(child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.merge_type_rounded, color: Color(0xFF0A0A00), size: 20),
                const SizedBox(width: 10),
                Text(ar ? 'دمج الملفين' : 'Merge Files',
                    style: const TextStyle(color: Color(0xFF0A0A00), fontSize: 15, fontWeight: FontWeight.w800)),
              ]))))),
    ]);
  }

  Widget _orderRow(String label, bool sel) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
    decoration: BoxDecoration(
      color: sel ? _goldDim.withValues(alpha: 0.4) : _card,
      borderRadius: BorderRadius.circular(10),
      border: Border.all(color: sel ? _gold : _border, width: sel ? 1.5 : 1)),
    child: Row(children: [
      Icon(sel ? Icons.radio_button_checked_rounded : Icons.radio_button_unchecked_rounded,
          color: sel ? _gold : _textDim, size: 18),
      const SizedBox(width: 10),
      Text(label, style: TextStyle(color: sel ? _gold : _textB, fontSize: 13,
          fontWeight: sel ? FontWeight.w700 : FontWeight.w400)),
    ]));

  // ── EXPORT TAB ────────────────────────────────────────────────────────────
  Widget _exportTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _card_(ar ? 'الصيغة' : 'Format', Icons.file_download_rounded, [
        Row(children: ['MP3','WAV','M4A'].map((f) {
          final sel = f == _fmt;
          return Expanded(child: GestureDetector(
            onTap: () => setState(() => _fmt = f),
            child: AnimatedContainer(duration: const Duration(milliseconds: 180),
              margin: const EdgeInsets.symmetric(horizontal: 4),
              padding: const EdgeInsets.symmetric(vertical: 13),
              decoration: BoxDecoration(
                color: sel ? _goldDim.withValues(alpha: 0.35) : _card,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: sel ? _gold : _border, width: sel ? 1.5 : 1)),
              child: Center(child: Text(f, style: TextStyle(
                  color: sel ? _gold : _textB, fontSize: 14,
                  fontWeight: sel ? FontWeight.w800 : FontWeight.w500))))));
        }).toList()),
        if (_fmt != 'WAV') ...[const SizedBox(height: 16),
          _knob(ar ? 'جودة البث' : 'Bitrate', '$_kbps kbps', _kbps.toDouble(), 64, 320,
              (v) => setState(() => _kbps = v.round()))],
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'خيارات' : 'Options', Icons.settings_rounded, [
        _toggle(ar ? 'حفظ كنغمة رنين (التنزيلات)' : 'Set as Ringtone (saves to Downloads)',
            Icons.ring_volume_rounded, _asRingtone, (v) => setState(() => _asRingtone = v)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'ملخص' : 'Summary', Icons.summarize_rounded, [
        _row(ar ? 'النطاق' : 'Range',
            '${_fmtTime(_trimStart * _durationSec)} → ${_fmtTime(_trimEnd * _durationSec)}'),
        _row(ar ? 'المدة' : 'Duration', _fmtTime((_trimEnd - _trimStart) * _durationSec)),
        _row(ar ? 'الصيغة' : 'Format', '$_fmt${_fmt == "WAV" ? "" : " @ $_kbps kbps"}'),
        if (_noiseReduc > 0) _row('Noise Reduction', '${_noiseReduc.round()}%'),
        if (_compress) _row('Compressor', '${_compThresh.round()}dB / ${_compRatio.round()}:1'),
        if (_normalize) _row('Normalize', '✓'),
        if (_reverse)   _row('Reverse',   '✓'),
      ]),
      if (_outPath != null) ...[const SizedBox(height: 10),
        Container(padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: _tealDk.withValues(alpha: 0.5),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _teal.withValues(alpha: 0.4))),
          child: Row(children: [
            const Icon(Icons.check_circle_rounded, color: _teal, size: 20),
            const SizedBox(width: 10),
            Expanded(child: Text('${ar ? "تم الحفظ: " : "Saved: "}$_outPath',
                style: const TextStyle(color: _textA, fontSize: 11),
                overflow: TextOverflow.ellipsis, maxLines: 2)),
          ]))],
      const SizedBox(height: 14),
      GestureDetector(onTap: _busy ? null : _export,
        child: AnimatedBuilder(animation: _glowCtrl,
          builder: (_, __) => Container(
            padding: const EdgeInsets.symmetric(vertical: 18),
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [Color(0xFF6B4F10), _gold],
                  begin: Alignment.centerRight, end: Alignment.centerLeft),
              borderRadius: BorderRadius.circular(14),
              boxShadow: [BoxShadow(
                  color: _gold.withValues(alpha: _busy ? 0.04 : 0.18 + 0.12 * _glowCtrl.value),
                  blurRadius: 22, offset: const Offset(0, 5))]),
            child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              const Icon(Icons.audio_file_rounded, color: Color(0xFF0A0A00), size: 22),
              const SizedBox(width: 10),
              Text(ar ? 'معالجة وتصدير' : 'Process & Export',
                  style: const TextStyle(color: Color(0xFF0A0A00), fontSize: 16, fontWeight: FontWeight.w800)),
            ])))),
    ]);
  }

  // ── Shared helpers ────────────────────────────────────────────────────────
  Widget _card_(String title, IconData icon, List<Widget> body) =>
    Container(padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _border, width: 1)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, color: _teal, size: 15), const SizedBox(width: 7),
          Text(title, style: const TextStyle(color: _textB, fontSize: 12,
              fontWeight: FontWeight.w700, letterSpacing: 0.3)),
        ]),
        const SizedBox(height: 12),
        ...body,
      ]));

  Widget _slider(double val, double min, double max, Color color, ValueChanged<double> onChanged) =>
    Directionality(textDirection: TextDirection.ltr,
      child: SliderTheme(data: SliderThemeData(trackHeight: 4,
        thumbSize: WidgetStateProperty.all(const Size(16, 16)),
        thumbColor: color, activeTrackColor: color.withValues(alpha: 0.85),
        inactiveTrackColor: _border, overlayColor: color.withValues(alpha: 0.12)),
        child: Slider(value: val, min: min, max: max, onChanged: onChanged)));

  Widget _knob(String label, String valueStr, double val, double min, double max,
      ValueChanged<double> onChanged) =>
    Padding(padding: const EdgeInsets.only(bottom: 10),
      child: Row(children: [
        SizedBox(width: 90, child: Text(label, style: const TextStyle(color: _textB, fontSize: 12))),
        Expanded(child: _slider(val, min, max, _gold, onChanged)),
        SizedBox(width: 68, child: Text(valueStr, textAlign: TextAlign.end,
            style: const TextStyle(color: _gold, fontSize: 12, fontWeight: FontWeight.w700))),
      ]));

  Widget _chip_(String label, VoidCallback onTap) =>
    GestureDetector(onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(color: _tealDk, borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _teal.withValues(alpha: 0.4))),
        child: Text(label, style: const TextStyle(color: _teal, fontSize: 11, fontWeight: FontWeight.w700))));

  Widget _preset(String label, List<double> vals) =>
    GestureDetector(onTap: () => setState(() { for (int i = 0; i < 10; i++) _eq[i] = vals[i]; }),
      child: Container(
        margin: const EdgeInsets.only(right: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _border)),
        child: Text(label, style: const TextStyle(color: _textB, fontSize: 11, fontWeight: FontWeight.w600))));

  Widget _toggle(String label, IconData icon, bool val, ValueChanged<bool> onChanged) =>
    Row(children: [
      Icon(icon, color: _textDim, size: 17), const SizedBox(width: 8),
      Expanded(child: Text(label, style: const TextStyle(color: _textB, fontSize: 13))),
      Switch(value: val, activeColor: _gold, inactiveThumbColor: _textDim,
        activeTrackColor: _goldDim, inactiveTrackColor: _border, onChanged: onChanged),
    ]);

  Widget _row(String label, String value) =>
    Padding(padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Text(label, style: const TextStyle(color: _textB, fontSize: 12)),
        const Spacer(),
        Text(value, style: const TextStyle(color: _gold, fontSize: 12, fontWeight: FontWeight.w600)),
      ]));
}

// ── WAVEFORM PAINTER ──────────────────────────────────────────────────────────
class _WavePainter extends CustomPainter {
  final List<double> bars;
  final double playPos, trimStart, trimEnd, animT;
  final bool playing;
  _WavePainter({required this.bars, required this.playPos,
      required this.trimStart, required this.trimEnd,
      required this.animT, required this.playing});

  @override
  void paint(Canvas c, Size sz) {
    final n = bars.length; final bw = sz.width / n; final mid = sz.height / 2;
    final rActive   = Paint()..shader = ui.Gradient.linear(Offset(0,0), Offset(0,sz.height),
        [const Color(0xFF1DB898), const Color(0xFF0A5A3A)]);
    final rInactive = Paint()..color = const Color(0xFF1A3A30).withOpacity(0.5);
    final rTrim     = Paint()..color = Colors.black.withOpacity(0.35);

    final x0 = trimStart * sz.width; final x1 = trimEnd * sz.width;
    if (trimStart > 0) c.drawRect(Rect.fromLTWH(0, 0, x0, sz.height), rTrim);
    if (trimEnd   < 1) c.drawRect(Rect.fromLTWH(x1, 0, sz.width - x1, sz.height), rTrim);

    for (int i = 0; i < n; i++) {
      final x = i * bw + 1.0; final frac = i / n;
      final inTrim = frac >= trimStart && frac < trimEnd;
      final pulse = playing ? 0.08 * sin(animT * 2 * pi + i * 0.25) : 0.0;
      final h = (bars[i] + pulse).clamp(0.05, 1.0) * mid * 0.88;
      c.drawRRect(RRect.fromRectAndRadius(
          Rect.fromLTWH(x, mid - h, bw - 2, h * 2), const Radius.circular(2.5)),
          inTrim ? rActive : rInactive);
    }

    final px = playPos * sz.width;
    c.drawRect(Rect.fromLTWH(0, 0, px, sz.height),
        Paint()..color = const Color(0xFFD4AF37).withOpacity(0.16));
    c.drawLine(Offset(px, 0), Offset(px, sz.height),
        Paint()..color = const Color(0xFFD4AF37)..strokeWidth = 1.5);

    void handle(double x, Color col, bool start) {
      c.drawLine(Offset(x,0), Offset(x,sz.height), Paint()..color=col..strokeWidth=1.8);
      final p = Path();
      if (start) { p.moveTo(x,0); p.lineTo(x+9,0); p.lineTo(x,10); p.close(); }
      else        { p.moveTo(x,0); p.lineTo(x-9,0); p.lineTo(x,10); p.close(); }
      c.drawPath(p, Paint()..color=col);
    }
    handle(x0, const Color(0xFF1DB898), true);
    handle(x1, const Color(0xFFD4AF37), false);
  }

  @override bool shouldRepaint(_WavePainter o) => true;
}

// ── EQ CURVE PAINTER ──────────────────────────────────────────────────────────
class _EqPainter extends CustomPainter {
  final List<double> values;
  _EqPainter({required this.values});

  @override
  void paint(Canvas c, Size sz) {
    if (values.length < 2) return;
    final n = values.length; final midY = sz.height / 2;
    final scX = sz.width / (n - 1); final scY = midY / 14;

    c.drawLine(Offset(0,midY), Offset(sz.width,midY),
        Paint()..color=const Color(0xFF1A3A30)..strokeWidth=0.5);

    final path = Path();
    for (int i = 0; i < n; i++) {
      final x = i * scX; final y = midY - values[i] * scY;
      if (i == 0) path.moveTo(x, y); else path.lineTo(x, y);
    }
    c.drawPath(path, Paint()
      ..style = PaintingStyle.stroke..strokeWidth = 2
      ..strokeCap = StrokeCap.round..strokeJoin = StrokeJoin.round
      ..shader = ui.Gradient.linear(const Offset(0,0), Offset(0, sz.height),
          [const Color(0xFF1DB898), const Color(0xFFD4AF37)]));

    final fill = Path.from(path);
    fill.lineTo((n-1)*scX, midY); fill.lineTo(0, midY); fill.close();
    c.drawPath(fill, Paint()..shader = ui.Gradient.linear(
        Offset(0, midY-14*scY), Offset(0, midY+14*scY), [
      const Color(0xFF1DB898).withOpacity(0.18),
      const Color(0xFF1DB898).withOpacity(0.0)]));
  }

  @override bool shouldRepaint(_EqPainter o) => values != o.values;
}
