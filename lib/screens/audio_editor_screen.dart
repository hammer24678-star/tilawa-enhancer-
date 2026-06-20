// audio_editor_screen.dart — S160: Full AudioLab-style editor
// File pick → Waveform → Trim → EQ → Effects → Export via ffmpeg

import 'dart:math' show pi, sin, cos, Random;
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';

// ── Theme ─────────────────────────────────────────────────────────────────────
const _bg      = Color(0xFF070F0B);
const _surface = Color(0xFF0C1E14);
const _card    = Color(0xFF0F2418);
const _gold    = Color(0xFFD4AF37);
const _goldDim = Color(0xFF8B6914);
const _teal    = Color(0xFF1DB898);
const _tealDk  = Color(0xFF0A3D2A);
const _red     = Color(0xFFE05252);
const _textA   = Color(0xFFCDD9CF);
const _textB   = Color(0xFF7A9E8A);
const _textDim = Color(0xFF3A5040);
const _border  = Color(0xFF1A2E20);

enum _Tab { trim, eq, effects, export_ }

// ─────────────────────────────────────────────────────────────────────────────
class AudioEditorScreen extends StatefulWidget {
  const AudioEditorScreen({super.key});
  @override State<AudioEditorScreen> createState() => _AudioEditorScreenState();
}

class _AudioEditorScreenState extends State<AudioEditorScreen>
    with TickerProviderStateMixin {

  // File
  String? _filePath;
  String  _fileName = '';
  double  _durationSec = 0;

  // Player
  final _player = AudioPlayer();
  bool   _playing = false;
  double _positionSec = 0;

  // Trim (normalized 0-1)
  double _trimStart = 0;
  double _trimEnd   = 1;

  // EQ (5 bands ±12 dB)
  final List<double> _eq = [0, 0, 0, 0, 0];
  static const _bands = ['60Hz', '250Hz', '1kHz', '4kHz', '16kHz'];
  static const _freqs = [60, 250, 1000, 4000, 16000];

  // Effects
  double _fadeIn  = 0;
  double _fadeOut = 0;
  double _pitch   = 0;
  double _tempo   = 1.0;
  double _echo    = 0;
  double _reverb  = 0;
  double _vol     = 1.0;

  // Export
  String _fmt      = 'MP3';
  int    _kbps     = 192;
  bool   _busy     = false;
  double _pct      = 0;
  String? _outPath;

  // UI
  _Tab _tab = _Tab.trim;
  late AnimationController _waveCtrl;
  late AnimationController _glowCtrl;
  late List<double> _bars;

  static const _ch =
      MethodChannel('com.tilawa.tilawa_enhancer/local_engine');

  @override
  void initState() {
    super.initState();
    final rng = Random(42);
    _bars = List.generate(80, (_) => 0.1 + rng.nextDouble() * 0.9);
    _waveCtrl = AnimationController(vsync: this,
        duration: const Duration(seconds: 3))..repeat();
    _glowCtrl = AnimationController(vsync: this,
        duration: const Duration(seconds: 2))..repeat(reverse: true);
    _player.onPlayerStateChanged.listen((s) {
      if (mounted) setState(() => _playing = s == PlayerState.playing);
    });
    _player.onPositionChanged.listen((d) {
      if (mounted) setState(() => _positionSec = d.inMilliseconds / 1000.0);
    });
  }

  @override
  void dispose() {
    _player.dispose();
    _waveCtrl.dispose();
    _glowCtrl.dispose();
    super.dispose();
  }

  // ── Helpers ──────────────────────────────────────────────────────────────────
  String _fmtTime(double s) {
    final m = s ~/ 60;
    final ss = (s % 60).toStringAsFixed(1);
    return '${m.toString().padLeft(2, '0')}:${ss.padLeft(4, '0')}';
  }

  bool get _isDirty =>
      _trimStart > 0 || _trimEnd < 1 ||
      _eq.any((v) => v.abs() > 0.1) ||
      _fadeIn > 0 || _fadeOut > 0 || _pitch != 0 ||
      _tempo != 1.0 || _echo > 0 || _reverb > 0 || _vol != 1.0;

  // ── File pick ────────────────────────────────────────────────────────────────
  Future<void> _pick() async {
    final r = await FilePicker.platform
        .pickFiles(type: FileType.audio, allowMultiple: false);
    if (r == null || r.files.isEmpty || r.files.first.path == null) return;
    final f = r.files.first;
    setState(() {
      _filePath = f.path; _fileName = f.name;
      _durationSec = 0; _positionSec = 0;
      _trimStart = 0; _trimEnd = 1; _outPath = null;
    });
    await _player.setSource(DeviceFileSource(f.path!));
    final dur = await _player.getDuration() ?? Duration.zero;
    if (mounted && dur != null)
      setState(() => _durationSec = dur.inMilliseconds / 1000.0);
  }

  // ── Playback ─────────────────────────────────────────────────────────────────
  Future<void> _togglePlay() async {
    if (_filePath == null) return;
    HapticFeedback.lightImpact();
    if (_playing) {
      await _player.pause();
    } else {
      await _player.seek(Duration(
          milliseconds: (_trimStart * _durationSec * 1000).round()));
      await _player.resume();
    }
  }

  Future<void> _stop() async {
    await _player.stop();
    setState(() => _positionSec = _trimStart * _durationSec);
  }

  // ── Export ───────────────────────────────────────────────────────────────────
  Future<void> _export() async {
    if (_filePath == null) return;
    HapticFeedback.mediumImpact();
    setState(() { _busy = true; _pct = 0.05; _outPath = null; });
    try {
      final dir = await getExternalStorageDirectory() ??
                  await getApplicationDocumentsDirectory();
      final base = _fileName.replaceAll(RegExp(r'\.[^.]+$'), '');
      final ext  = _fmt.toLowerCase();
      final out  = '${dir.path}/tilawa_${base}_edited.$ext';

      // S179: copy the picked file into a temp dir before handing it to
      // ffmpeg/proot — file_picker paths often resolve through
      // /data/user/0/... symlinks that proot's bind-mount can't follow
      // (same root cause runEngine() already works around for engine runs,
      // S128). Without this, ffmpeg can't see the source file inside the
      // chroot even with S178's bind-mount fix.
      final tmpDir = await getTemporaryDirectory();
      final safeInput = File(
          '${tmpDir.path}/tilawa_edit_input_${DateTime.now().millisecondsSinceEpoch}.${_filePath!.split('.').last}');
      await File(_filePath!).copy(safeInput.path);
      final realInput = safeInput.path;

      final ss  = (_trimStart * _durationSec).toStringAsFixed(3);
      final dur = ((_trimEnd - _trimStart) * _durationSec).toStringAsFixed(3);

      // Build -af filter chain
      final af = <String>[];
      if (_fadeIn  > 0) af.add('afade=t=in:d=${_fadeIn.toStringAsFixed(1)}');
      if (_fadeOut > 0) {
        final st = ((_trimEnd - _trimStart) * _durationSec - _fadeOut)
            .clamp(0.0, double.infinity).toStringAsFixed(2);
        af.add('afade=t=out:st=$st:d=${_fadeOut.toStringAsFixed(1)}');
      }
      for (int i = 0; i < 5; i++) {
        if (_eq[i].abs() > 0.5)
          af.add('equalizer=f=${_freqs[i]}:g=${_eq[i].toStringAsFixed(1)}');
      }
      if (_echo   > 0) af.add('aecho=0.8:${(_echo/100).toStringAsFixed(2)}:500:0.5');
      if (_reverb > 0) af.add('aecho=0.8:${(_reverb/100).toStringAsFixed(2)}:80:0.3');
      if (_tempo  != 1.0)
        af.add('atempo=${_tempo.clamp(0.5, 2.0).toStringAsFixed(2)}');
      if (_vol    != 1.0) af.add('volume=${_vol.toStringAsFixed(2)}');

      final afStr = af.isEmpty ? 'anull' : af.join(',');

      final codec = _fmt == 'WAV' ? 'pcm_s16le'
                  : _fmt == 'M4A' ? 'aac'
                  : 'libmp3lame';
      final bitrateFlag = _fmt == 'WAV' ? '' : '-b:a ${_kbps}k';

      final cmd = 'ffmpeg -y -ss $ss -i "$realInput" -t $dur '
          '-af $afStr -acodec $codec $bitrateFlag "$out"';

      setState(() => _pct = 0.2);
      // S178: pass inputPath/outputPath so Kotlin's runProotCmd bind-mounts
      // their real directories into the proot chroot — without these the
      // picked file and the output folder are invisible inside proot and
      // ffmpeg fails to read/write them. Also check rc instead of assuming
      // success regardless of what ffmpeg actually did.
      final r = await _ch.invokeMethod<Map>('runProotCmd', {
        'cmd':        cmd,
        'inputPath':  realInput,
        'outputPath': out,
        'timeoutMin': 10,
      });  // S161/S178/S179
      final rc = (r?['rc'] as int?) ?? 0;
      if (rc != 0) {
        throw Exception('ffmpeg failed (rc=$rc): ${(r?['out'] as String? ?? '').trim()}');
      }
      setState(() { _pct = 1.0; _outPath = out; _busy = false; });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          backgroundColor: _card,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
              side: const BorderSide(color: _gold, width: 0.7)),
          content: Text('✓ حُفظ: $out',
              style: const TextStyle(color: _gold, fontSize: 11)),
          duration: const Duration(seconds: 4),
        ));
      }
    } catch (e) {
      setState(() => _busy = false);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          backgroundColor: _card,
          content: Text('خطأ: $e',
              style: const TextStyle(color: _red, fontSize: 12))));
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // BUILD
  // ─────────────────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext ctx) => Directionality(
    textDirection: TextDirection.rtl,
    child: Scaffold(
      backgroundColor: _bg,
      body: SafeArea(
        child: Column(children: [
          _appBar(),
          Expanded(child: _filePath == null ? _pickerView() : _editorView()),
        ]),
      ),
    ),
  );

  // ── App bar ───────────────────────────────────────────────────────────────────
  Widget _appBar() => Container(
    decoration: BoxDecoration(
      color: _surface,
      border: Border(bottom: BorderSide(
          color: _gold.withValues(alpha: 0.25), width: 1))),
    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
    child: Row(children: [
      IconButton(
        icon: const Icon(Icons.arrow_back_ios_new_rounded,
            size: 18, color: _textB),
        onPressed: () => Navigator.pop(context)),
      const Expanded(child: Text('محرر الصوت',
          textAlign: TextAlign.center,
          style: TextStyle(color: _gold, fontSize: 17,
              fontWeight: FontWeight.w700, letterSpacing: 0.3))),
      if (_filePath != null)
        TextButton(
          onPressed: _pick,
          child: const Text('تغيير',
              style: TextStyle(color: _teal, fontSize: 12,
                  fontWeight: FontWeight.w600)))
      else
        const SizedBox(width: 48),
    ]),
  );

  // ── Picker view ───────────────────────────────────────────────────────────────
  Widget _pickerView() => Center(
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      AnimatedBuilder(
        animation: _glowCtrl,
        builder: (_, __) => Container(
          width: 130, height: 130,
          decoration: BoxDecoration(
            shape: BoxShape.circle, color: _card,
            border: Border.all(
                color: _gold.withValues(alpha: 0.18 + 0.28 * _glowCtrl.value),
                width: 1.5),
            boxShadow: [BoxShadow(
                color: _gold.withValues(alpha: 0.04 + 0.08 * _glowCtrl.value),
                blurRadius: 36)]),
          child: const Icon(Icons.audio_file_rounded, color: _gold, size: 52))),
      const SizedBox(height: 28),
      const Text('اختر ملف صوتي',
          style: TextStyle(color: _textA, fontSize: 20,
              fontWeight: FontWeight.w700)),
      const SizedBox(height: 8),
      const Text('MP3 · WAV · M4A · AAC · OGG · FLAC',
          style: TextStyle(color: _textB, fontSize: 13)),
      const SizedBox(height: 36),
      GestureDetector(
        onTap: _pick,
        child: AnimatedBuilder(
          animation: _glowCtrl,
          builder: (_, __) => Container(
            padding: const EdgeInsets.symmetric(horizontal: 44, vertical: 17),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                  colors: [Color(0xFF6B4F10), _gold],
                  begin: Alignment.centerRight, end: Alignment.centerLeft),
              borderRadius: BorderRadius.circular(14),
              boxShadow: [BoxShadow(
                  color: _gold.withValues(alpha: 0.2 + 0.15 * _glowCtrl.value),
                  blurRadius: 18, offset: const Offset(0, 4))]),
            child: const Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(Icons.folder_open_rounded,
                  color: Color(0xFF0A0A00), size: 22),
              SizedBox(width: 10),
              Text('فتح ملف', style: TextStyle(
                  color: Color(0xFF0A0A00), fontSize: 16,
                  fontWeight: FontWeight.w800)),
            ]),
          ))),
    ]),
  );

  // ── Editor view ───────────────────────────────────────────────────────────────
  Widget _editorView() => Column(children: [
    _fileBar(),
    _waveformSection(),
    _transport(),
    _tabBar(),
    Expanded(child: _tabBody()),
  ]);

  // ── File bar ──────────────────────────────────────────────────────────────────
  Widget _fileBar() => Container(
    color: _surface,
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
    child: Row(children: [
      const Icon(Icons.music_note_rounded, color: _teal, size: 16),
      const SizedBox(width: 8),
      Expanded(child: Text(_fileName,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(color: _textA, fontSize: 13,
              fontWeight: FontWeight.w500))),
      const SizedBox(width: 10),
      Text(_fmtTime(_durationSec),
          style: const TextStyle(color: _textB, fontSize: 12,
              fontFamily: 'monospace')),
    ]),
  );

  // ── Waveform ──────────────────────────────────────────────────────────────────
  Widget _waveformSection() {
    final pos = _durationSec > 0
        ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0.0;
    return GestureDetector(
      onTapDown: (d) {
        final box = context.findRenderObject() as RenderBox?;
        if (box == null) return;
        final frac = (d.localPosition.dx / box.size.width).clamp(0.0, 1.0);
        _player.seek(Duration(
            milliseconds: (frac * _durationSec * 1000).round()));
        setState(() => _positionSec = frac * _durationSec);
      },
      child: AnimatedBuilder(
        animation: _waveCtrl,
        builder: (_, __) => SizedBox(
          height: 96,
          child: CustomPaint(
            painter: _WavePainter(
              bars: _bars, playPos: pos,
              trimStart: _trimStart, trimEnd: _trimEnd,
              animT: _waveCtrl.value, playing: _playing),
            size: const Size(double.infinity, 96),
          )),
      ),
    );
  }

  // ── Transport ─────────────────────────────────────────────────────────────────
  Widget _transport() => Container(
    color: _surface,
    padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
    child: Row(children: [
      _tBtn(Icons.skip_previous_rounded, () async {
        await _player.seek(Duration(
            milliseconds: (_trimStart * _durationSec * 1000).round()));
        setState(() => _positionSec = _trimStart * _durationSec);
      }),
      const SizedBox(width: 12),
      AnimatedBuilder(
        animation: _glowCtrl,
        builder: (_, __) => GestureDetector(
          onTap: _togglePlay,
          child: Container(
            width: 52, height: 52,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const RadialGradient(
                  colors: [Color(0xFFB8921E), _goldDim]),
              boxShadow: [BoxShadow(
                  color: _gold.withValues(
                      alpha: _playing ? 0.15 + 0.2 * _glowCtrl.value : 0.05),
                  blurRadius: 18)]),
            child: Icon(
              _playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
              color: const Color(0xFF050A06), size: 28)))),
      const SizedBox(width: 12),
      _tBtn(Icons.stop_rounded, _stop),
      const SizedBox(width: 16),
      // Waveform mini-pos indicator
      Expanded(child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(children: [
            Text(_fmtTime(_positionSec),
                style: const TextStyle(color: _gold, fontSize: 11,
                    fontWeight: FontWeight.w600, fontFamily: 'monospace')),
            const Text(' / ',
                style: TextStyle(color: _textDim, fontSize: 11)),
            Text(_fmtTime(_durationSec),
                style: const TextStyle(color: _textB, fontSize: 11,
                    fontFamily: 'monospace')),
          ]),
          const SizedBox(height: 4),
          ClipRRect(
            borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: _durationSec > 0
                  ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0,
              backgroundColor: _border,
              valueColor: const AlwaysStoppedAnimation(_gold),
              minHeight: 3)),
        ])),
      const SizedBox(width: 12),
      _tBtn(Icons.loop_rounded, () async {
        // loop trim region
        await _player.setReleaseMode(ReleaseMode.loop);
      }, color: _teal),
    ]),
  );

  Widget _tBtn(IconData icon, VoidCallback onTap, {Color? color}) =>
      GestureDetector(
        onTap: onTap,
        child: Container(
          width: 38, height: 38,
          decoration: BoxDecoration(
            shape: BoxShape.circle, color: _card,
            border: Border.all(color: _border)),
          child: Icon(icon, color: color ?? _textB, size: 19)));

  // ── Tab bar ───────────────────────────────────────────────────────────────────
  Widget _tabBar() {
    final labels = ['قطع', 'EQ', 'تأثيرات', 'تصدير'];
    final icons  = [
      Icons.content_cut_rounded,
      Icons.equalizer_rounded,
      Icons.auto_fix_high_rounded,
      Icons.ios_share_rounded,
    ];
    return Container(
      decoration: BoxDecoration(
        color: _surface,
        border: Border(bottom: BorderSide(color: _border))),
      child: Row(
        children: _Tab.values.map((t) {
          final active = t == _tab;
          return Expanded(child: GestureDetector(
            onTap: () {
              HapticFeedback.selectionClick();
              setState(() => _tab = t);
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: BoxDecoration(
                border: Border(bottom: BorderSide(
                    color: active ? _gold : Colors.transparent,
                    width: 2))),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Icon(icons[t.index],
                    color: active ? _gold : _textDim, size: 19),
                const SizedBox(height: 3),
                Text(labels[t.index],
                    style: TextStyle(
                        color: active ? _gold : _textDim,
                        fontSize: 10, fontWeight: FontWeight.w600)),
              ]),
            ),
          ));
        }).toList()),
    );
  }

  Widget _tabBody() {
    switch (_tab) {
      case _Tab.trim:    return _trimTab();
      case _Tab.eq:      return _eqTab();
      case _Tab.effects: return _effectsTab();
      case _Tab.export_: return _exportTab();
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // TRIM TAB
  // ═══════════════════════════════════════════════════════════════════════════
  Widget _trimTab() => ListView(
    padding: const EdgeInsets.all(14),
    children: [
      _card_('نقطة البداية', Icons.align_horizontal_left_rounded, [
        Row(children: [
          Text(_fmtTime(_trimStart * _durationSec),
              style: const TextStyle(color: _teal, fontSize: 15,
                  fontWeight: FontWeight.w800, fontFamily: 'monospace')),
          const Spacer(),
          _chip_('بداية', () => setState(() => _trimStart = 0)),
        ]),
        _slider(_trimStart, 0, _trimEnd - 0.005, _teal,
            (v) => setState(() => _trimStart = v)),
      ]),
      const SizedBox(height: 10),
      _card_('نقطة النهاية', Icons.align_horizontal_right_rounded, [
        Row(children: [
          Text(_fmtTime(_trimEnd * _durationSec),
              style: const TextStyle(color: _gold, fontSize: 15,
                  fontWeight: FontWeight.w800, fontFamily: 'monospace')),
          const Spacer(),
          _chip_('نهاية', () => setState(() => _trimEnd = 1)),
        ]),
        _slider(_trimEnd, _trimStart + 0.005, 1.0, _gold,
            (v) => setState(() => _trimEnd = v)),
      ]),
      const SizedBox(height: 10),
      _card_('مدة التحديد', Icons.timer_outlined, [
        Center(child: Text(
          _fmtTime((_trimEnd - _trimStart) * _durationSec),
          style: const TextStyle(color: _gold, fontSize: 30,
              fontWeight: FontWeight.w800, letterSpacing: 1.5,
              fontFamily: 'monospace'))),
        const SizedBox(height: 12),
        Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
          _chip_('اختيار الكل',
              () => setState(() { _trimStart = 0; _trimEnd = 1; })),
          _chip_('النصف الأول',
              () => setState(() { _trimStart = 0; _trimEnd = 0.5; })),
          _chip_('النصف الثاني',
              () => setState(() { _trimStart = 0.5; _trimEnd = 1; })),
        ]),
      ]),
    ],
  );

  // ═══════════════════════════════════════════════════════════════════════════
  // EQ TAB
  // ═══════════════════════════════════════════════════════════════════════════
  Widget _eqTab() => ListView(
    padding: const EdgeInsets.all(14),
    children: [
      _card_('منحنى التعديل', Icons.show_chart_rounded, [
        SizedBox(height: 72,
          child: CustomPaint(
            painter: _EqPainter(values: _eq),
            size: const Size(double.infinity, 72))),
        const SizedBox(height: 10),
        // Presets
        SingleChildScrollView(
          scrollDirection: Axis.horizontal,
          child: Row(children: [
            _preset('مسطح', [0,0,0,0,0]),
            _preset('باس',  [7,4,0,-1,-2]),
            _preset('صوت',  [-2,0,5,4,2]),
            _preset('وضوح', [-1,0,2,5,4]),
            _preset('تلاوة',[3,1,3,2,1]),
            _preset('ليلة', [4,2,0,-2,-3]),
          ])),
      ]),
      const SizedBox(height: 10),
      _card_('أحزمة التعديل', Icons.tune_rounded,
          List.generate(5, (i) {
            final v = _eq[i];
            final c = v > 0 ? _gold : v < 0 ? _teal : _textDim;
            return Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(children: [
                SizedBox(width: 44, child: Text(_bands[i],
                    style: const TextStyle(color: _textB, fontSize: 11))),
                Expanded(child: SliderTheme(
                  data: SliderThemeData(
                    trackHeight: 3,
                    thumbSize: WidgetStateProperty.all(const Size(14, 14)),
                    thumbColor: c,
                    activeTrackColor: c.withValues(alpha: 0.75),
                    inactiveTrackColor: _border,
                    overlayColor: c.withValues(alpha: 0.12)),
                  child: Slider(value: v, min: -12, max: 12, divisions: 24,
                      onChanged: (val) => setState(() => _eq[i] = val)))),
                SizedBox(width: 54,
                  child: Text(
                    '${v >= 0 ? "+" : ""}${v.toStringAsFixed(1)} dB',
                    textAlign: TextAlign.end,
                    style: TextStyle(color: c, fontSize: 11,
                        fontWeight: FontWeight.w600))),
              ]),
            );
          })),
    ],
  );

  // ═══════════════════════════════════════════════════════════════════════════
  // EFFECTS TAB
  // ═══════════════════════════════════════════════════════════════════════════
  Widget _effectsTab() => ListView(
    padding: const EdgeInsets.all(14),
    children: [
      _card_('الصوت', Icons.volume_up_rounded, [
        _knob('مستوى الصوت', '${(_vol*100).round()}%',  _vol,  0.5, 2.0,
            (v)=>setState(()=>_vol=v)),
        _knob('درجة الصوت', '${_pitch>=0?"+":""}${_pitch.toStringAsFixed(1)} st',
            _pitch, -12, 12, (v)=>setState(()=>_pitch=v)),
        _knob('السرعة', '${_tempo.toStringAsFixed(2)}×',
            _tempo, 0.5, 2.0, (v)=>setState(()=>_tempo=v)),
      ]),
      const SizedBox(height: 10),
      _card_('تلاشي', Icons.trending_flat_rounded, [
        _knob('دخول (Fade In)',  '${_fadeIn.toStringAsFixed(1)}s',
            _fadeIn,  0, 10, (v)=>setState(()=>_fadeIn=v)),
        _knob('خروج (Fade Out)', '${_fadeOut.toStringAsFixed(1)}s',
            _fadeOut, 0, 10, (v)=>setState(()=>_fadeOut=v)),
      ]),
      const SizedBox(height: 10),
      _card_('فضاء صوتي', Icons.surround_sound_rounded, [
        _knob('صدى (Echo)',    '${_echo.round()}%',   _echo,   0, 100,
            (v)=>setState(()=>_echo=v)),
        _knob('إرجاع (Reverb)','${_reverb.round()}%', _reverb, 0, 100,
            (v)=>setState(()=>_reverb=v)),
      ]),
      const SizedBox(height: 10),
      GestureDetector(
        onTap: () {
          HapticFeedback.mediumImpact();
          setState(() {
            _vol=1.0; _pitch=0; _tempo=1.0;
            _fadeIn=0; _fadeOut=0; _echo=0; _reverb=0;
          });
        },
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 13),
          decoration: BoxDecoration(
            color: _tealDk, borderRadius: BorderRadius.circular(10),
            border: Border.all(color: _teal.withValues(alpha: 0.3))),
          child: const Center(child: Row(mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.restart_alt_rounded, color: _teal, size: 17),
              SizedBox(width: 6),
              Text('إعادة الضبط',
                  style: TextStyle(color: _teal, fontSize: 13,
                      fontWeight: FontWeight.w600)),
            ])))),
    ],
  );

  // ═══════════════════════════════════════════════════════════════════════════
  // EXPORT TAB
  // ═══════════════════════════════════════════════════════════════════════════
  Widget _exportTab() => ListView(
    padding: const EdgeInsets.all(14),
    children: [
      _card_('الصيغة', Icons.file_download_rounded, [
        Row(children: ['MP3','WAV','M4A'].map((f) {
          final sel = f == _fmt;
          return Expanded(child: GestureDetector(
            onTap: () => setState(() => _fmt = f),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              margin: const EdgeInsets.symmetric(horizontal: 4),
              padding: const EdgeInsets.symmetric(vertical: 13),
              decoration: BoxDecoration(
                color: sel ? _goldDim.withValues(alpha: 0.35) : _card,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                    color: sel ? _gold : _border,
                    width: sel ? 1.5 : 1)),
              child: Center(child: Text(f, style: TextStyle(
                  color: sel ? _gold : _textB, fontSize: 14,
                  fontWeight: sel ? FontWeight.w800 : FontWeight.w500))))));
        }).toList()),
        if (_fmt != 'WAV') ...[
          const SizedBox(height: 16),
          _knob('جودة البث', '$_kbps kbps', _kbps.toDouble(), 64, 320,
              (v) => setState(() => _kbps = v.round())),
        ],
      ]),
      const SizedBox(height: 10),
      // Summary
      _card_('ملخص', Icons.summarize_rounded, [
        _row('المقطع المحدد',
          '${_fmtTime(_trimStart * _durationSec)} ← '
          '${_fmtTime(_trimEnd * _durationSec)}'),
        _row('المدة',
          _fmtTime((_trimEnd - _trimStart) * _durationSec)),
        _row('التأثيرات المفعّلة', () {
          final a = <String>[];
          if (_fadeIn>0)  a.add('Fade In');
          if (_fadeOut>0) a.add('Fade Out');
          if (_echo>0)    a.add('Echo');
          if (_reverb>0)  a.add('Reverb');
          if (_pitch!=0)  a.add('Pitch');
          if (_tempo!=1)  a.add('Tempo');
          if (_vol!=1)    a.add('Volume');
          if (_eq.any((v)=>v.abs()>0.5)) a.add('EQ');
          return a.isEmpty ? '—' : a.join(' · ');
        }()),
        _row('الصيغة',
          '$_fmt${_fmt!="WAV" ? " · $_kbps kbps" : ""}'),
      ]),
      const SizedBox(height: 14),
      if (_busy)
        Column(children: [
          AnimatedBuilder(
            animation: _waveCtrl,
            builder: (_, __) => ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: LinearProgressIndicator(
                value: _pct > 0.1 ? _pct : null,
                backgroundColor: _border,
                valueColor: const AlwaysStoppedAnimation(_gold),
                minHeight: 6))),
          const SizedBox(height: 8),
          const Text('جارٍ المعالجة...',
              style: TextStyle(color: _textB, fontSize: 12)),
        ])
      else
        AnimatedBuilder(
          animation: _glowCtrl,
          builder: (_, __) => GestureDetector(
            onTap: _export,
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 17),
              decoration: BoxDecoration(
                gradient: const LinearGradient(
                    colors: [Color(0xFF5A420D), _gold],
                    begin: Alignment.centerRight,
                    end: Alignment.centerLeft),
                borderRadius: BorderRadius.circular(14),
                boxShadow: [BoxShadow(
                    color: _gold.withValues(
                        alpha: 0.15 + 0.18 * _glowCtrl.value),
                    blurRadius: 22, offset: const Offset(0,4))]),
              child: const Center(child: Row(mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.ios_share_rounded,
                      color: Color(0xFF050A06), size: 21),
                  SizedBox(width: 10),
                  Text('تصدير الملف', style: TextStyle(
                      color: Color(0xFF050A06), fontSize: 16,
                      fontWeight: FontWeight.w800)),
                ])),
            ))),
      if (_outPath != null) ...[
        const SizedBox(height: 12),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: _tealDk, borderRadius: BorderRadius.circular(10),
            border: Border.all(color: _teal.withValues(alpha: 0.35))),
          child: Row(children: [
            const Icon(Icons.check_circle_rounded, color: _teal, size: 18),
            const SizedBox(width: 8),
            Expanded(child: Text(_outPath!, overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: _teal, fontSize: 11))),
          ])),
      ],
    ],
  );

  // ── Shared widgets ────────────────────────────────────────────────────────────
  Widget _card_(String title, IconData icon, List<Widget> body) =>
    Container(
      decoration: BoxDecoration(
        color: _card, borderRadius: BorderRadius.circular(14),
        border: Border.all(color: _border)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(padding: const EdgeInsets.fromLTRB(14,12,14,10),
          child: Row(children: [
            Icon(icon, color: _gold, size: 16),
            const SizedBox(width: 8),
            Text(title, style: const TextStyle(color: _gold, fontSize: 13,
                fontWeight: FontWeight.w700)),
          ])),
        Divider(color: _border, height: 1),
        Padding(padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start,
              children: body)),
      ]));

  Widget _slider(double v, double min, double max, Color c,
      ValueChanged<double> fn) =>
    SliderTheme(
      data: SliderThemeData(
        trackHeight: 4,
        thumbSize: WidgetStateProperty.all(const Size(18, 18)),
        thumbColor: c, activeTrackColor: c.withValues(alpha: 0.8),
        inactiveTrackColor: _border,
        overlayColor: c.withValues(alpha: 0.12)),
      child: Slider(value: v, min: min, max: max, onChanged: fn));

  Widget _knob(String label, String val, double v, double min, double max,
      ValueChanged<double> fn) =>
    Padding(padding: const EdgeInsets.only(bottom: 10),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Text(label,
              style: const TextStyle(color: _textA, fontSize: 12)),
          const Spacer(),
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 120),
            child: Text(val, key: ValueKey(val),
                style: const TextStyle(color: _teal, fontSize: 12,
                    fontWeight: FontWeight.w700))),
        ]),
        const SizedBox(height: 2),
        SliderTheme(
          data: SliderThemeData(
            trackHeight: 3,
            thumbSize: WidgetStateProperty.all(const Size(14, 14)),
            thumbColor: _teal,
            activeTrackColor: _teal.withValues(alpha: 0.7),
            inactiveTrackColor: _border,
            overlayColor: _teal.withValues(alpha: 0.1)),
          child: Slider(value: v, min: min, max: max, onChanged: fn)),
      ]));

  Widget _chip_(String label, VoidCallback fn) =>
    GestureDetector(
      onTap: fn,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: _tealDk, borderRadius: BorderRadius.circular(8),
          border: Border.all(color: _teal.withValues(alpha: 0.3))),
        child: Text(label, style: const TextStyle(
            color: _teal, fontSize: 11, fontWeight: FontWeight.w600))));

  Widget _preset(String label, List<double> vals) =>
    GestureDetector(
      onTap: () => setState(() { for(int i=0;i<5;i++) _eq[i]=vals[i].toDouble(); }),
      child: Container(
        margin: const EdgeInsets.only(left: 6),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: _card, borderRadius: BorderRadius.circular(8),
          border: Border.all(color: _goldDim.withValues(alpha: 0.4))),
        child: Text(label,
            style: const TextStyle(color: _textB, fontSize: 11))));

  Widget _row(String k, String v) =>
    Padding(padding: const EdgeInsets.only(bottom: 6),
      child: Row(children: [
        Text(k, style: const TextStyle(color: _textB, fontSize: 12)),
        const Spacer(),
        Flexible(child: Text(v, textAlign: TextAlign.left,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(color: _textA, fontSize: 12,
                fontWeight: FontWeight.w600))),
      ]));
}

// ═══════════════════════════════════════════════════════════════════════════
// WAVEFORM PAINTER
// ═══════════════════════════════════════════════════════════════════════════
class _WavePainter extends CustomPainter {
  final List<double> bars;
  final double playPos, trimStart, trimEnd, animT;
  final bool playing;
  _WavePainter({
    required this.bars, required this.playPos,
    required this.trimStart, required this.trimEnd,
    required this.animT, required this.playing,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width; final h = size.height; final mid = h / 2;
    final bw = w / bars.length;

    // Dim outside trim
    final dim = Paint()..color = const Color(0xAA070F0B);
    if (trimStart > 0)
      canvas.drawRect(Rect.fromLTWH(0, 0, w * trimStart, h), dim);
    if (trimEnd < 1)
      canvas.drawRect(Rect.fromLTWH(w * trimEnd, 0, w*(1-trimEnd), h), dim);

    for (int i = 0; i < bars.length; i++) {
      final x    = i * bw + bw / 2;
      final frac = i / bars.length;
      final inT  = frac >= trimStart && frac <= trimEnd;
      final past = frac < playPos;

      double amp = bars[i];
      if (playing && inT)
        amp *= 1.0 + 0.18 * sin(animT * 6.2832 * 2.5 + i * 0.4);

      final bh = (amp * mid * 0.85).clamp(2.0, mid * 0.95);
      final c  = !inT ? const Color(0xFF162A1E)
               : past ? const Color(0xFFD4AF37)
               :         const Color(0xFF1DB898);

      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset(x, mid),
              width: bw * 0.55, height: bh * 2),
          const Radius.circular(2)),
        Paint()..color = c);
    }

    // Trim markers
    _vline(canvas, w * trimStart, h, const Color(0xFF1DB898));
    _vline(canvas, w * trimEnd,   h, const Color(0xFFD4AF37));

    // Playhead
    if (playPos > 0.001)
      _vline(canvas, w * playPos, h,
          Colors.white.withValues(alpha: 0.75), width: 1.5);
  }

  void _vline(Canvas c, double x, double h, Color col, {double width = 1.8}) =>
      c.drawLine(Offset(x, 0), Offset(x, h),
          Paint()..color = col..strokeWidth = width);

  @override
  bool shouldRepaint(_WavePainter o) =>
      o.playPos != playPos || o.animT != animT || o.playing != playing ||
      o.trimStart != trimStart || o.trimEnd != trimEnd;
}

// ═══════════════════════════════════════════════════════════════════════════
// EQ CURVE PAINTER
// ═══════════════════════════════════════════════════════════════════════════
class _EqPainter extends CustomPainter {
  final List<double> values;
  _EqPainter({required this.values});

  @override
  void paint(Canvas canvas, Size size) {
    final w = size.width; final h = size.height; final mid = h / 2;
    canvas.drawLine(Offset(0, mid), Offset(w, mid),
        Paint()..color = const Color(0xFF1A2E20)..strokeWidth = 1);
    if (values.isEmpty) return;

    final step = w / (values.length + 1);
    final pts  = [for (int i = 0; i < values.length; i++)
      Offset(step * (i+1), mid - (values[i] / 12.0) * mid * 0.85)];

    final path = Path()..moveTo(0, mid)..lineTo(pts.first.dx, pts.first.dy);
    for (int i = 0; i < pts.length - 1; i++) {
      final m = (pts[i].dx + pts[i+1].dx) / 2;
      path.cubicTo(m, pts[i].dy, m, pts[i+1].dy, pts[i+1].dx, pts[i+1].dy);
    }
    path.lineTo(w, mid);

    canvas.drawPath(Path.from(path)..close(), Paint()
      ..shader = LinearGradient(
          begin: Alignment.topCenter, end: Alignment.bottomCenter,
          colors: [const Color(0xFFD4AF37).withValues(alpha: 0.22),
                   Colors.transparent])
          .createShader(Rect.fromLTWH(0,0,w,h)));
    canvas.drawPath(path, Paint()
      ..color = const Color(0xFFD4AF37)..strokeWidth = 2
      ..style = PaintingStyle.stroke..strokeCap = StrokeCap.round);
    for (final p in pts) {
      canvas.drawCircle(p, 4, Paint()..color = const Color(0xFF0F2418));
      canvas.drawCircle(p, 4, Paint()
        ..color = const Color(0xFFD4AF37)
        ..style = PaintingStyle.stroke..strokeWidth = 2);
    }
  }

  @override
  bool shouldRepaint(_EqPainter o) => o.values != values;
}
