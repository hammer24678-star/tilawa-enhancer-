#!/usr/bin/env python3
"""
patch_s203_local_engines_and_audiolab_editor.py — S203

THREE CHANGES:

  1. ENGINE ITIQAN LOCAL (engine_itiqan_v6_local.py)
     The server version (engine_itiqan_v6_sever.py) has two server-specific
     hacks that are wrong inside the proot Alpine environment:

     BUG-A  Line with `env={**os.environ, 'HOME': '/tmp'}` — on HuggingFace
            Spaces the container user is root with no home dir, so HOME must be
            forced to /tmp. Inside proot however, Kotlin's runEngine() /
            runProotWithBinds() already injects HOME=/root into the process
            environment. Keeping '/tmp' overwrites that and breaks any tool
            (e.g. deep-filter) that expects a writable home.
            Fix: use os.environ.get('HOME', '/root') so the value injected
            by Kotlin wins and /tmp is only the fallback.

     BUG-B  Comment `# SRV: always 0 on success` on the main() return path.
            The behaviour (return 0 on success) is correct for both modes, but
            the comment is misleading in the local engine file.  Updated.

  2. ENGINE SAFAA LOCAL (engine_safaa_v5_local.py)
     The server version (engine_safaa_v5_server.py) lists '/app/deep-filter'
     first in the DF3 binary search order — that path is the HuggingFace
     Docker WORKDIR and never exists inside Alpine proot.  The local engine
     already falls back to the PATH-based searches ('deep-filter', etc.) which
     will find the binary wherever setup installs it, but the dead /app/ entry
     causes a stat() call + log noise on every invocation.
     Fix: comment out the /app/ entry.

  3. AUDIO EDITOR REDESIGN (lib/screens/audio_editor_screen.dart)
     Complete visual overhaul to AudioLab aesthetics:
     — Deep-red "lab" palette (crimson background, coral/red accents)
     — Lab flask hero icon on picker view + title bar
     — Red gradient waveform bars with sharper trim handles
     — Circular gradient play button with red glow
     — Active tab indicator: red underline + subtle red bg tint
     — Export button: wide red gradient "Process & Export" CTA
     All audio logic (trim/EQ/effects/ffmpeg export) is preserved verbatim.

Usage:
  python3 patch_s203_local_engines_and_audiolab_editor.py /path/to/tilawa-enhancer

Requirements (run before this patch):
  The two local engine files must already exist in the repo root:
    engine_itiqan_v6_local.py  (copied from engine_itiqan_v6_sever.py)
    engine_safaa_v5_local.py            (copied from engine_safaa_v5_server.py)
  This patch applies str.replace edits on top of those files.
"""
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
if not (REPO / 'lib').exists():
    print(f'ERROR: lib/ not found in {REPO}'); sys.exit(1)

STAMP = REPO / '.patch_s203_done'
if STAMP.exists():
    print('patch_s203 already applied — delete .patch_s203_done to re-run'); sys.exit(0)


def rep(old, new, tag, src, required=True):
    p = REPO / src
    if not p.exists():
        if required: print(f'  FAIL  {tag}: file missing: {src}'); sys.exit(1)
        print(f'  SKIP  {tag} (file missing — non-fatal)'); return
    text = p.read_text(encoding='utf-8')
    if old not in text:
        if new in text:
            print(f'  SKIP  {tag} (already applied)'); return
        if required: print(f'  FAIL  {tag}: anchor not found in {src}'); sys.exit(1)
        print(f'  WARN  {tag}: anchor not found — skipped'); return
    p.write_text(text.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')


def overwrite(src, content, tag):
    p = REPO / src
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding='utf-8')
    print(f'  OK    {tag}  ({len(content.splitlines())} lines)')


print(f'\n── S203  [repo: {REPO}] ──\n')

# ── 1. ENGINE ITIQAN: BUG-A — fix HOME env for proot ─────────────────────────
rep(
    "env={**os.environ, 'HOME': '/tmp'},  # SRV: HF runs as root, HOME may be unset",
    "env={**os.environ, 'HOME': os.environ.get('HOME', '/root')},  # LOCAL: proot already sets HOME=/root",
    'ITIQAN-LOCAL-A: fix HOME env — /tmp → os.environ.get(HOME, /root)',
    'engine_itiqan_v6_local.py',
    required=False,
)

# ── 2. ENGINE ITIQAN: BUG-B — update stale SRV comment on return 0 ───────────
rep(
    'return 0  # SRV: always 0 on success — server treats any rc!=0 as failure/fallback',
    'return 0  # LOCAL: 0 = success; Kotlin runEngine checks rc != 0 for failure',
    'ITIQAN-LOCAL-B: update return 0 comment',
    'engine_itiqan_v6_local.py',
    required=False,
)

# ── 3. ENGINE SAFAA: BUG-A — remove HF Docker /app/ path ─────────────────────
rep(
    "    '/app/deep-filter',          # HuggingFace Space (Docker WORKDIR /app)\n",
    "    # '/app/deep-filter' — HF-Space Docker path; not present in proot Alpine (S203)\n",
    'SAFAA-LOCAL-A: comment out /app/deep-filter from DF3 search paths',
    'engine_safaa_v5_local.py',
    required=False,
)

# ── 4. AUDIO EDITOR: full AudioLab-style redesign ────────────────────────────
AUDIO_EDITOR_DART = r"""// audio_editor_screen.dart — S203: AudioLab-style full redesign
// Trim · EQ · Effects · Export via ffmpeg (proot local engine)
// Aesthetic: deep-red "lab" palette — mirrors AudioLab icon language
//   (gradient flask/experiment vibe, vibrant coral-red accents)

import 'dart:async';
import 'dart:math' show pi, sin, cos, pow, Random;
import 'dart:ui' as ui;
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';
import '../state/lang_provider.dart';

// ── AudioLab palette ──────────────────────────────────────────────────────────
const _bg      = Color(0xFF0D0403);   // near-black, red-tinted
const _surface = Color(0xFF1A0806);   // deep dark red surface
const _card    = Color(0xFF251109);   // card background
const _rim     = Color(0xFF3D160D);   // card border / rim
const _red     = Color(0xFFFF3D1A);   // primary accent — AudioLab orange-red
const _redDk   = Color(0xFF4D1206);   // dark red for fills
const _coral   = Color(0xFFFF6B40);   // secondary coral highlight
const _amber   = Color(0xFFFFAB40);   // warning / bitrate indicator
const _textA   = Color(0xFFFFF0EC);   // primary text — warm white
const _textB   = Color(0xFFBBA8A2);   // secondary text
const _textDim = Color(0xFF5C3328);   // dim / placeholder text
const _border  = Color(0xFF3D1A12);   // dividers

// ─────────────────────────────────────────────────────────────────────────────
enum _Tab { trim, eq, effects, export_ }

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
  StreamSubscription<PlayerState>? _stateSub;
  StreamSubscription<Duration>?    _posSub;
  StreamSubscription<Duration>?    _durSub;
  bool   _playing = false;
  double _positionSec = 0;

  // Trim (normalised 0-1)
  double _trimStart = 0;
  double _trimEnd   = 1;

  // EQ (5 bands +/-12 dB)
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
  late AnimationController _pulseCtrl;
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
    _pulseCtrl = AnimationController(vsync: this,
        duration: const Duration(seconds: 2))..repeat(reverse: true);
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
    _player.dispose();
    _waveCtrl.dispose();
    _pulseCtrl.dispose();
    super.dispose();
  }

  // ── Helpers ───────────────────────────────────────────────────────────────
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

  // ── File pick ─────────────────────────────────────────────────────────────
  Future<void> _pick() async {
    if (_playing) await _player.stop();
    final r = await FilePicker.platform
        .pickFiles(type: FileType.audio, allowMultiple: false);
    if (r == null || r.files.isEmpty || r.files.first.path == null) return;
    final f = r.files.first;
    if (!mounted) return;
    setState(() {
      _filePath = f.path; _fileName = f.name;
      _durationSec = 0; _positionSec = 0;
      _trimStart = 0; _trimEnd = 1; _outPath = null;
    });
    await _player.setSource(DeviceFileSource(f.path!));
  }

  // ── Playback ──────────────────────────────────────────────────────────────
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
    if (mounted) setState(() => _positionSec = _trimStart * _durationSec);
  }

  // ── Export ────────────────────────────────────────────────────────────────
  Future<void> _export() async {
    if (_filePath == null) return;
    HapticFeedback.mediumImpact();
    setState(() { _busy = true; _pct = 0.05; _outPath = null; });
    final ar = LangProvider.strings(context).ar;
    try {
      final setupOk = await _ch.invokeMethod<bool>('isBasicSetupComplete') ?? false;
      if (!setupOk) {
        throw Exception(ar
            ? 'يجب إكمال تجهيز المحرك المحلي أولاً من الإعدادات قبل استخدام محرر الصوت'
            : 'Please finish setting up the local engine in Settings before using the audio editor.');
      }
      final dir = await getExternalStorageDirectory() ??
                  await getApplicationDocumentsDirectory();
      final base = _fileName.replaceAll(RegExp(r'\.[^.]+$'), '');
      final ext  = _fmt.toLowerCase();
      final out  = '${dir.path}/tilawa_${base}_edited.$ext';

      final tmpDir = await getTemporaryDirectory();
      final safeInput = File(
          '${tmpDir.path}/tilawa_edit_input_${DateTime.now().millisecondsSinceEpoch}.${_filePath!.split('.').last}');
      await File(_filePath!).copy(safeInput.path);
      final realInput = safeInput.path;

      final ss  = (_trimStart * _durationSec).toStringAsFixed(3);
      final dur = ((_trimEnd - _trimStart) * _durationSec).toStringAsFixed(3);

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
      if (_pitch != 0) {
        final pitchRate = (pow(2.0, _pitch / 12.0) as double);
        final pitchCompensate = (1.0 / pitchRate).clamp(0.5, 2.0).toStringAsFixed(6);
        af.add('asetrate=44100*${pitchRate.toStringAsFixed(6)},aresample=44100,atempo=$pitchCompensate');
      }
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
      final r = await _ch.invokeMethod<Map>('runProotCmd', {
        'cmd':        cmd,
        'inputPath':  realInput,
        'outputPath': out,
        'timeoutMin': 10,
      });
      final rc = (r?['rc'] as int?) ?? 0;
      if (rc != 0) {
        throw Exception('ffmpeg failed (rc=$rc): ${(r?['out'] as String? ?? '').trim()}');
      }
      if (!mounted) return;
      setState(() { _pct = 1.0; _outPath = out; _busy = false; });
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          backgroundColor: _card,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(10),
              side: const BorderSide(color: _red, width: 0.8)),
          content: Text(ar ? '\u2713 \u062d\u064f\u0641\u0638: $out' : '\u2713 Saved: $out',
              style: const TextStyle(color: _coral, fontSize: 11)),
          duration: const Duration(seconds: 4),
        ));
      }
    } catch (e) {
      setState(() => _busy = false);
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          backgroundColor: _card,
          content: Text(ar ? '\u062e\u0637\u0623: $e' : 'Error: $e',
              style: const TextStyle(color: _amber, fontSize: 12))));
    }
  }

  // ── Busy warning ──────────────────────────────────────────────────────────
  void _warnBusy() {
    if (!mounted) return;
    final ar = LangProvider.strings(context).ar;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      backgroundColor: _card,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(10),
          side: const BorderSide(color: _red, width: 0.8)),
      content: Text(ar ? '\u062c\u0627\u0631\u064d \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629\u2026 \u0627\u0646\u062a\u0638\u0631 \u062d\u062a\u0649 \u062a\u0646\u062a\u0647\u064a \u0627\u0644\u0639\u0645\u0644\u064a\u0629'
          : 'Processing\u2026 please wait until it finishes',
          style: const TextStyle(color: _coral, fontSize: 12)),
      duration: const Duration(seconds: 2),
    ));
  }

  // ─────────────────────────────────────────────────────────────────────────
  // BUILD ROOT
  // ─────────────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext ctx) => Directionality(
    textDirection: LangProvider.strings(ctx).ar ? TextDirection.rtl : TextDirection.ltr,
    child: PopScope(
      canPop: !_busy,
      onPopInvokedWithResult: (didPop, _) { if (!didPop) _warnBusy(); },
      child: Scaffold(
        backgroundColor: _bg,
        body: SafeArea(
          child: Stack(children: [
            Column(children: [
              _appBar(),
              Expanded(child: _filePath == null ? _pickerView() : _editorView()),
            ]),
            if (_busy) _processingOverlay(),
          ]),
        ),
      ),
    ),
  );

  // ── Processing overlay ────────────────────────────────────────────────────
  Widget _processingOverlay() {
    final ar = LangProvider.strings(context).ar;
    return AbsorbPointer(
    child: AnimatedBuilder(
      animation: _pulseCtrl,
      builder: (_, __) => Container(
        color: Colors.black.withValues(alpha: 0.78),
        alignment: Alignment.center,
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          SizedBox(width: 100, height: 100,
            child: Stack(alignment: Alignment.center, children: [
              Container(width: 100, height: 100,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: _red.withValues(alpha: 0.15 + 0.30 * _pulseCtrl.value),
                    width: 1.5),
                  boxShadow: [BoxShadow(
                    color: _red.withValues(alpha: 0.06 + 0.18 * _pulseCtrl.value),
                    blurRadius: 36)])),
              SizedBox(width: 72, height: 72,
                child: CircularProgressIndicator(
                  value: _pct > 0.05 ? _pct : null,
                  strokeWidth: 3.5, backgroundColor: _rim,
                  valueColor: AlwaysStoppedAnimation(
                    Color.lerp(_red, _coral, _pulseCtrl.value)!),
                  strokeCap: StrokeCap.round)),
              ShaderMask(
                shaderCallback: (b) => const LinearGradient(
                  colors: [_coral, _red],
                  begin: Alignment.topCenter, end: Alignment.bottomCenter).createShader(b),
                child: const Icon(Icons.science_rounded, color: Colors.white, size: 30)),
            ])),
          const SizedBox(height: 22),
          ShaderMask(
            shaderCallback: (b) => const LinearGradient(
                colors: [_red, _coral]).createShader(b),
            child: Text(ar ? '\u062c\u0627\u0631\u064d \u0627\u0644\u0645\u0639\u0627\u0644\u062c\u0629' : 'Processing',
              style: const TextStyle(color: Colors.white, fontSize: 21,
                fontWeight: FontWeight.w800, letterSpacing: 0.5))),
          const SizedBox(height: 6),
          Text(ar ? '\u064a\u064f\u0631\u062c\u0649 \u0627\u0644\u0627\u0646\u062a\u0638\u0627\u0631 \u2014 \u0644\u0627 \u062a\u063a\u0644\u0642 \u0627\u0644\u0634\u0627\u0634\u0629'
              : "Please wait \u2014 don't close the screen",
            style: const TextStyle(color: _textB, fontSize: 13)),
          const SizedBox(height: 22),
          SizedBox(width: 220, child: ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: _pct > 0.05 ? _pct : null,
                backgroundColor: _rim,
                valueColor: const AlwaysStoppedAnimation(_red),
                minHeight: 6))),
          if (_pct > 0.05) ...[ const SizedBox(height: 8),
            Text('${(_pct * 100).round()}%',
              style: const TextStyle(color: _textB, fontSize: 12)) ],
        ]),
      )));
  }

  // ── App bar ───────────────────────────────────────────────────────────────
  Widget _appBar() {
    final ar = LangProvider.strings(context).ar;
    return Container(
    decoration: const BoxDecoration(color: _surface,
        border: Border(bottom: BorderSide(color: _rim, width: 1))),
    padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
    child: Row(children: [
      IconButton(
        icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: _textB),
        onPressed: () => _busy ? _warnBusy() : Navigator.pop(context)),
      Expanded(child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
        ShaderMask(
          shaderCallback: (b) => const LinearGradient(
              colors: [_red, _coral]).createShader(b),
          child: const Icon(Icons.science_rounded, color: Colors.white, size: 18)),
        const SizedBox(width: 6),
        ShaderMask(
          shaderCallback: (b) => const LinearGradient(
              colors: [_red, _coral]).createShader(b),
          child: Text(ar ? '\u0645\u062d\u0631\u0631 \u0627\u0644\u0635\u0648\u062a' : 'Audio Lab',
              style: const TextStyle(color: Colors.white, fontSize: 17,
                  fontWeight: FontWeight.w800, letterSpacing: 0.5))),
      ])),
      IconButton(
        icon: const Icon(Icons.info_outline_rounded, size: 18, color: _textB),
        onPressed: _showHelp),
      if (_filePath != null)
        TextButton(onPressed: _pick,
          child: Text(ar ? '\u062a\u063a\u064a\u064a\u0631' : 'Change',
              style: const TextStyle(color: _coral, fontSize: 12,
                  fontWeight: FontWeight.w600)))
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
            side: const BorderSide(color: _red, width: 0.8)),
        title: Row(children: [
          const Icon(Icons.science_rounded, color: _coral, size: 20),
          const SizedBox(width: 8),
          Text(ar ? '\u0639\u0646 \u0645\u062d\u0631\u0631 \u0627\u0644\u0635\u0648\u062a' : 'About Audio Lab',
              style: const TextStyle(color: _coral, fontWeight: FontWeight.w700)),
        ]),
        content: Text(
          ar
            ? '\u2022 \u0627\u0644\u0642\u0635: \u0627\u0633\u062d\u0628 \u0627\u0644\u0628\u062f\u0627\u064a\u0629 \u0648\u0627\u0644\u0646\u0647\u0627\u064a\u0629 \u0644\u0627\u062e\u062a\u064a\u0627\u0631 \u0627\u0644\u062c\u0632\u0621 \u0627\u0644\u0645\u0637\u0644\u0648\u0628.\n'
              '\u2022 \u0627\u0644\u0645\u0648\u0627\u0632\u0646 (EQ): \u062a\u062d\u0643\u0645 \u0628\u0645\u0633\u062a\u0648\u0649 \u0643\u0644 \u0646\u0637\u0627\u0642 \u062a\u0631\u062f\u062f.\n'
              '\u2022 \u0627\u0644\u0645\u0624\u062b\u0631\u0627\u062a: \u062a\u0644\u0627\u0634\u064a \u0648\u062f\u0631\u062c\u0629 \u0635\u0648\u062a \u0648\u0633\u0631\u0639\u0629 \u0648\u0635\u062f\u0649.\n'
              '\u2022 \u0627\u0644\u062a\u0635\u062f\u064a\u0631: MP3 / WAV / M4A \u0645\u0639 \u062c\u0645\u064a\u0639 \u0627\u0644\u062a\u0639\u062f\u064a\u0644\u0627\u062a.\n\n'
              '\u26d4  \u0644\u0627 \u064a\u062d\u062a\u0627\u062c \u0627\u062a\u0635\u0627\u0644\u0627\u064b \u0628\u0627\u0644\u0625\u0646\u062a\u0631\u0646\u062a \u2014 \u064a\u0639\u0645\u0644 \u0639\u0628\u0631 ffmpeg \u0645\u062d\u0644\u064a\u0627\u064b.'
            : '\u2022 Trim: drag start/end handles to select a range.\n'
              '\u2022 EQ: adjust each frequency band.\n'
              '\u2022 Effects: fade, pitch, speed, echo, volume.\n'
              '\u2022 Export: save as MP3, WAV or M4A with all edits.\n\n'
              '\u26d4  No internet needed \u2014 runs locally via ffmpeg.',
          style: const TextStyle(color: _textA, fontSize: 13, height: 1.5),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(context),
          child: Text(ar ? '\u062d\u0633\u0646\u064b\u0627' : 'OK',
              style: const TextStyle(color: _coral)))],
      )));
  }

  // ── Picker view ───────────────────────────────────────────────────────────
  Widget _pickerView() {
    final ar = LangProvider.strings(context).ar;
    return Container(
    decoration: const BoxDecoration(gradient: LinearGradient(
        colors: [_bg, Color(0xFF1A0806)],
        begin: Alignment.topCenter, end: Alignment.bottomCenter)),
    child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
      AnimatedBuilder(
        animation: _pulseCtrl,
        builder: (_, __) => Container(
          width: 140, height: 140,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: const RadialGradient(
              colors: [Color(0xFF4D1206), _bg], radius: 0.9),
            border: Border.all(
                color: _red.withValues(alpha: 0.20 + 0.30 * _pulseCtrl.value),
                width: 1.5),
            boxShadow: [
              BoxShadow(color: _red.withValues(alpha: 0.08 + 0.16 * _pulseCtrl.value), blurRadius: 50),
              BoxShadow(color: _coral.withValues(alpha: 0.04 + 0.08 * _pulseCtrl.value), blurRadius: 80),
            ]),
          child: ShaderMask(
            shaderCallback: (b) => const LinearGradient(
              colors: [_coral, _red],
              begin: Alignment.topLeft, end: Alignment.bottomRight).createShader(b),
            child: const Icon(Icons.science_rounded, color: Colors.white, size: 64)))),
      const SizedBox(height: 28),
      Text(ar ? '\u0627\u0633\u062a\u062f\u064a\u0648 \u0627\u0644\u0635\u0648\u062a' : 'Audio Lab',
          style: const TextStyle(color: _textA, fontSize: 24,
              fontWeight: FontWeight.w900, letterSpacing: 0.3)),
      const SizedBox(height: 6),
      Text(ar ? '\u0627\u062e\u062a\u0631 \u0645\u0644\u0641 \u0635\u0648\u062a\u064a \u0644\u0644\u0628\u062f\u0621' : 'Choose an audio file to start',
          style: const TextStyle(color: _textB, fontSize: 14)),
      const SizedBox(height: 6),
      const Text('MP3 \u00b7 WAV \u00b7 M4A \u00b7 AAC \u00b7 OGG \u00b7 FLAC',
          style: TextStyle(color: _textDim, fontSize: 12)),
      const SizedBox(height: 36),
      GestureDetector(
        onTap: _pick,
        child: AnimatedBuilder(
          animation: _pulseCtrl,
          builder: (_, __) => Container(
            padding: const EdgeInsets.symmetric(horizontal: 44, vertical: 16),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                  colors: [Color(0xFF8C1C0A), _red],
                  begin: Alignment.centerLeft, end: Alignment.centerRight),
              borderRadius: BorderRadius.circular(40),
              boxShadow: [BoxShadow(
                  color: _red.withValues(alpha: 0.22 + 0.18 * _pulseCtrl.value),
                  blurRadius: 24, offset: const Offset(0, 6))]),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.folder_open_rounded, color: Colors.white, size: 22),
              const SizedBox(width: 10),
              Text(ar ? '\u0641\u062a\u062d \u0645\u0644\u0641' : 'Open File',
                  style: const TextStyle(color: Colors.white, fontSize: 16,
                      fontWeight: FontWeight.w800, letterSpacing: 0.3)),
            ])))),
    ])));
  }

  // ── Editor view ───────────────────────────────────────────────────────────
  Widget _editorView() => Column(children: [
    _fileBar(), _waveformSection(), _transport(), _tabBar(),
    Expanded(child: _tabBody()),
  ]);

  Widget _fileBar() => Container(
    color: _surface,
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
    child: Row(children: [
      ShaderMask(
        shaderCallback: (b) => const LinearGradient(colors: [_red, _coral]).createShader(b),
        child: const Icon(Icons.music_note_rounded, color: Colors.white, size: 16)),
      const SizedBox(width: 8),
      Expanded(child: Text(_fileName,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(color: _textA, fontSize: 13, fontWeight: FontWeight.w500))),
      const SizedBox(width: 10),
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(color: _redDk, borderRadius: BorderRadius.circular(6)),
        child: Text(_fmtTime(_durationSec),
            style: const TextStyle(color: _coral, fontSize: 11,
                fontWeight: FontWeight.w600, fontFamily: 'monospace'))),
    ]));

  Widget _waveformSection() {
    final pos = _durationSec > 0
        ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0.0;
    return GestureDetector(
      onTapDown: (d) {
        final box = context.findRenderObject() as RenderBox?;
        if (box == null) return;
        final frac = (d.localPosition.dx / box.size.width).clamp(0.0, 1.0);
        _player.seek(Duration(milliseconds: (frac * _durationSec * 1000).round()));
        setState(() => _positionSec = frac * _durationSec);
      },
      child: AnimatedBuilder(
        animation: _waveCtrl,
        builder: (_, __) => SizedBox(height: 96,
          child: CustomPaint(
            painter: _WavePainter(bars: _bars, playPos: pos,
              trimStart: _trimStart, trimEnd: _trimEnd,
              animT: _waveCtrl.value, playing: _playing),
            size: const Size(double.infinity, 96)))));
  }

  Widget _transport() => Container(
    decoration: const BoxDecoration(color: _surface,
        border: Border(top: BorderSide(color: _rim, width: 0.5))),
    padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
    child: Row(children: [
      _tBtn(Icons.skip_previous_rounded, () async {
        await _player.seek(Duration(
            milliseconds: (_trimStart * _durationSec * 1000).round()));
        if (mounted) setState(() => _positionSec = _trimStart * _durationSec);
      }),
      const SizedBox(width: 12),
      AnimatedBuilder(
        animation: _pulseCtrl,
        builder: (_, __) => GestureDetector(
          onTap: _togglePlay,
          child: Container(
            width: 54, height: 54,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: const LinearGradient(
                  colors: [Color(0xFFCC2C10), _red],
                  begin: Alignment.topLeft, end: Alignment.bottomRight),
              boxShadow: [BoxShadow(
                  color: _red.withValues(
                      alpha: _playing ? 0.20 + 0.22 * _pulseCtrl.value : 0.08),
                  blurRadius: 20)]),
            child: Icon(
              _playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
              color: Colors.white, size: 28)))),
      const SizedBox(width: 12),
      _tBtn(Icons.stop_rounded, _stop),
      const SizedBox(width: 14),
      Expanded(child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min,
        children: [
          Row(children: [
            Text(_fmtTime(_positionSec),
                style: const TextStyle(color: _coral, fontSize: 11,
                    fontWeight: FontWeight.w700, fontFamily: 'monospace')),
            const Text(' / ', style: TextStyle(color: _textDim, fontSize: 11)),
            Text(_fmtTime(_durationSec),
                style: const TextStyle(color: _textB, fontSize: 11, fontFamily: 'monospace')),
          ]),
          const SizedBox(height: 5),
          ClipRRect(borderRadius: BorderRadius.circular(3),
            child: LinearProgressIndicator(
              value: _durationSec > 0
                  ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0,
              backgroundColor: _rim,
              valueColor: const AlwaysStoppedAnimation(_red),
              minHeight: 4)),
        ])),
      const SizedBox(width: 12),
      _tBtn(Icons.loop_rounded, () async {
        await _player.setReleaseMode(ReleaseMode.loop);
      }, color: _coral),
    ]));

  Widget _tBtn(IconData icon, VoidCallback onTap, {Color? color}) =>
      GestureDetector(onTap: onTap,
        child: Container(width: 38, height: 38,
          decoration: BoxDecoration(shape: BoxShape.circle, color: _card,
              border: Border.all(color: _rim)),
          child: Icon(icon, color: color ?? _textB, size: 19)));

  Widget _tabBar() {
    final ar = LangProvider.strings(context).ar;
    final labels = ar ? ['\u0642\u0637\u0639', 'EQ', '\u062a\u0623\u062b\u064a\u0631\u0627\u062a', '\u062a\u0635\u062f\u064a\u0631']
                      : ['Trim', 'EQ', 'Effects', 'Export'];
    final icons  = [Icons.content_cut_rounded, Icons.equalizer_rounded,
                    Icons.auto_fix_high_rounded, Icons.ios_share_rounded];
    return Container(
      decoration: const BoxDecoration(color: _surface,
          border: Border(bottom: BorderSide(color: _rim, width: 1))),
      child: Row(children: _Tab.values.map((t) {
        final active = t == _tab;
        return Expanded(child: GestureDetector(
          onTap: () { HapticFeedback.selectionClick(); setState(() => _tab = t); },
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            padding: const EdgeInsets.symmetric(vertical: 11),
            decoration: BoxDecoration(
              border: Border(bottom: BorderSide(
                  color: active ? _red : Colors.transparent, width: 2.5)),
              color: active ? _redDk.withValues(alpha: 0.4) : Colors.transparent),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(icons[t.index], color: active ? _coral : _textDim, size: 20),
              const SizedBox(height: 3),
              Text(labels[t.index], style: TextStyle(
                  color: active ? _coral : _textDim,
                  fontSize: 10, fontWeight: FontWeight.w700)),
            ]))));
      }).toList()));
  }

  Widget _tabBody() {
    switch (_tab) {
      case _Tab.trim:    return _trimTab();
      case _Tab.eq:      return _eqTab();
      case _Tab.effects: return _effectsTab();
      case _Tab.export_: return _exportTab();
    }
  }

  // ─── TRIM TAB ─────────────────────────────────────────────────────────────
  Widget _trimTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _sectionCard(ar ? '\u0646\u0642\u0637\u0629 \u0627\u0644\u0628\u062f\u0627\u064a\u0629' : 'Start Point',
          Icons.align_horizontal_left_rounded, [
        Row(children: [
          Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(color: _redDk, borderRadius: BorderRadius.circular(8)),
            child: Text(_fmtTime(_trimStart * _durationSec),
                style: const TextStyle(color: _coral, fontSize: 15,
                    fontWeight: FontWeight.w800, fontFamily: 'monospace'))),
          const Spacer(),
          _chip(ar ? '\u0628\u062f\u0627\u064a\u0629' : 'Start', () => setState(() => _trimStart = 0)),
        ]),
        _slider(_trimStart, 0, _trimEnd - 0.005, _red, (v) => setState(() => _trimStart = v)),
      ]),
      const SizedBox(height: 10),
      _sectionCard(ar ? '\u0646\u0642\u0637\u0629 \u0627\u0644\u0646\u0647\u0627\u064a\u0629' : 'End Point',
          Icons.align_horizontal_right_rounded, [
        Row(children: [
          Container(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(color: _redDk, borderRadius: BorderRadius.circular(8)),
            child: Text(_fmtTime(_trimEnd * _durationSec),
                style: const TextStyle(color: _amber, fontSize: 15,
                    fontWeight: FontWeight.w800, fontFamily: 'monospace'))),
          const Spacer(),
          _chip(ar ? '\u0646\u0647\u0627\u064a\u0629' : 'End', () => setState(() => _trimEnd = 1)),
        ]),
        _slider(_trimEnd, _trimStart + 0.005, 1.0, _amber, (v) => setState(() => _trimEnd = v)),
      ]),
      const SizedBox(height: 10),
      _sectionCard(ar ? '\u0645\u062f\u0629 \u0627\u0644\u062a\u062d\u062f\u064a\u062f' : 'Selection Duration',
          Icons.timer_outlined, [
        Center(child: ShaderMask(
          shaderCallback: (b) => const LinearGradient(colors: [_red, _coral]).createShader(b),
          child: Text(_fmtTime((_trimEnd - _trimStart) * _durationSec),
            style: const TextStyle(color: Colors.white, fontSize: 30,
                fontWeight: FontWeight.w900, letterSpacing: 2.0, fontFamily: 'monospace')))),
        const SizedBox(height: 14),
        Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
          _chip(ar ? '\u0627\u062e\u062a\u064a\u0627\u0631 \u0627\u0644\u0643\u0644' : 'Select All',
              () => setState(() { _trimStart = 0; _trimEnd = 1; })),
          _chip(ar ? '\u0627\u0644\u0646\u0635\u0641 \u0627\u0644\u0623\u0648\u0644' : 'First Half',
              () => setState(() { _trimStart = 0; _trimEnd = 0.5; })),
          _chip(ar ? '\u0627\u0644\u0646\u0635\u0641 \u0627\u0644\u062b\u0627\u0646\u064a' : 'Second Half',
              () => setState(() { _trimStart = 0.5; _trimEnd = 1; })),
        ]),
      ]),
    ]);
  }

  // ─── EQ TAB ───────────────────────────────────────────────────────────────
  Widget _eqTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _sectionCard(ar ? '\u0645\u0646\u062d\u0646\u0649 \u0627\u0644\u062a\u0639\u062f\u064a\u0644' : 'EQ Curve',
          Icons.show_chart_rounded, [
        SizedBox(height: 72, child: CustomPaint(painter: _EqPainter(values: _eq),
            size: const Size(double.infinity, 72))),
        const SizedBox(height: 10),
        SingleChildScrollView(scrollDirection: Axis.horizontal, child: Row(children: [
          _preset(ar ? '\u0645\u0633\u0637\u062d' : 'Flat',       [0,0,0,0,0]),
          _preset(ar ? '\u0628\u0627\u0633' : 'Bass',             [7,4,0,-1,-2]),
          _preset(ar ? '\u0635\u0648\u062a' : 'Voice',            [-2,0,5,4,2]),
          _preset(ar ? '\u0648\u0636\u0648\u062d' : 'Clarity',    [-1,0,2,5,4]),
          _preset(ar ? '\u062a\u0644\u0627\u0648\u0629' : 'Recitation', [3,1,3,2,1]),
          _preset(ar ? '\u0644\u064a\u0644\u0629' : 'Night',      [4,2,0,-2,-3]),
        ])),
      ]),
      const SizedBox(height: 10),
      _sectionCard(ar ? '\u0623\u062d\u0632\u0645\u0629 \u0627\u0644\u062a\u0639\u062f\u064a\u0644' : 'EQ Bands',
          Icons.tune_rounded,
          List.generate(5, (i) {
            final v = _eq[i];
            final c = v > 0 ? _red : v < 0 ? _coral : _textDim;
            return Padding(padding: const EdgeInsets.only(bottom: 8),
              child: Row(children: [
                SizedBox(width: 44, child: Text(_bands[i],
                    style: const TextStyle(color: _textB, fontSize: 11))),
                Expanded(child: Directionality(textDirection: TextDirection.ltr,
                  child: SliderTheme(
                    data: SliderThemeData(
                      trackHeight: 3,
                      thumbSize: WidgetStateProperty.all(const Size(14, 14)),
                      thumbColor: c, activeTrackColor: c.withValues(alpha: 0.80),
                      inactiveTrackColor: _rim, overlayColor: c.withValues(alpha: 0.12)),
                    child: Slider(value: v, min: -12, max: 12, divisions: 24,
                        onChanged: (val) => setState(() => _eq[i] = val))))),
                SizedBox(width: 54, child: Text(
                    '${v >= 0 ? "+" : ""}${v.toStringAsFixed(1)} dB',
                    textAlign: TextAlign.end,
                    style: TextStyle(color: c, fontSize: 11, fontWeight: FontWeight.w600))),
              ]));
          })),
    ]);
  }

  // ─── EFFECTS TAB ──────────────────────────────────────────────────────────
  Widget _effectsTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _sectionCard(ar ? '\u0627\u0644\u0635\u0648\u062a' : 'Audio', Icons.volume_up_rounded, [
        _knob(ar ? '\u0645\u0633\u062a\u0648\u0649 \u0627\u0644\u0635\u0648\u062a' : 'Volume',
            '${(_vol*100).round()}%', _vol, 0.5, 2.0, (v)=>setState(()=>_vol=v)),
        _knob(ar ? '\u062f\u0631\u062c\u0629 \u0627\u0644\u0635\u0648\u062a' : 'Pitch',
            '${_pitch>=0?"+":""}${_pitch.toStringAsFixed(1)} st',
            _pitch, -12, 12, (v)=>setState(()=>_pitch=v)),
        _knob(ar ? '\u0627\u0644\u0633\u0631\u0639\u0629' : 'Speed',
            '${_tempo.toStringAsFixed(2)}\u00d7',
            _tempo, 0.5, 2.0, (v)=>setState(()=>_tempo=v)),
      ]),
      const SizedBox(height: 10),
      _sectionCard(ar ? '\u062a\u0644\u0627\u0634\u064a' : 'Fade', Icons.trending_flat_rounded, [
        _knob(ar ? '\u062f\u062e\u0648\u0644 (Fade In)' : 'Fade In',
            '${_fadeIn.toStringAsFixed(1)}s', _fadeIn, 0, 10, (v)=>setState(()=>_fadeIn=v)),
        _knob(ar ? '\u062e\u0631\u0648\u062c (Fade Out)' : 'Fade Out',
            '${_fadeOut.toStringAsFixed(1)}s', _fadeOut, 0, 10, (v)=>setState(()=>_fadeOut=v)),
      ]),
      const SizedBox(height: 10),
      _sectionCard(ar ? '\u0641\u0636\u0627\u0621 \u0635\u0648\u062a\u064a' : 'Space',
          Icons.surround_sound_rounded, [
        _knob(ar ? '\u0635\u062f\u0649 (Echo)' : 'Echo',
            '${_echo.round()}%', _echo, 0, 100, (v)=>setState(()=>_echo=v)),
        _knob(ar ? '\u0625\u0631\u062c\u0627\u0639 (Reverb)' : 'Reverb',
            '${_reverb.round()}%', _reverb, 0, 100, (v)=>setState(()=>_reverb=v)),
      ]),
      const SizedBox(height: 10),
      GestureDetector(
        onTap: () {
          HapticFeedback.mediumImpact();
          setState(() { _vol=1.0; _pitch=0; _tempo=1.0; _fadeIn=0; _fadeOut=0; _echo=0; _reverb=0; });
        },
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: BoxDecoration(color: _redDk, borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _red.withValues(alpha: 0.35))),
          child: Center(child: Row(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.restart_alt_rounded, color: _coral, size: 18),
            const SizedBox(width: 8),
            Text(ar ? '\u0625\u0639\u0627\u062f\u0629 \u0627\u0644\u0636\u0628\u0637' : 'Reset All',
                style: const TextStyle(color: _coral, fontSize: 13, fontWeight: FontWeight.w700)),
          ])))),
    ]);
  }

  // ─── EXPORT TAB ───────────────────────────────────────────────────────────
  Widget _exportTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _sectionCard(ar ? '\u0627\u0644\u0635\u064a\u063a\u0629' : 'Format',
          Icons.file_download_rounded, [
        Row(children: ['MP3','WAV','M4A'].map((f) {
          final sel = f == _fmt;
          return Expanded(child: GestureDetector(
            onTap: () => setState(() => _fmt = f),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              margin: const EdgeInsets.symmetric(horizontal: 4),
              padding: const EdgeInsets.symmetric(vertical: 14),
              decoration: BoxDecoration(
                gradient: sel ? const LinearGradient(
                  colors: [Color(0xFF5C1208), Color(0xFF3D0D06)]) : null,
                color: sel ? null : _card,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: sel ? _red : _rim, width: sel ? 1.5 : 1)),
              child: Center(child: Text(f, style: TextStyle(
                  color: sel ? _coral : _textB, fontSize: 14,
                  fontWeight: sel ? FontWeight.w900 : FontWeight.w500))))));
        }).toList()),
        if (_fmt != 'WAV') ...[ const SizedBox(height: 16),
          _knob(ar ? '\u062c\u0648\u062f\u0629 \u0627\u0644\u0628\u062b' : 'Bitrate',
              '$_kbps kbps', _kbps.toDouble(), 64, 320,
              (v) => setState(() => _kbps = v.round())) ],
      ]),
      const SizedBox(height: 10),
      _sectionCard(ar ? '\u0645\u0644\u062e\u0635' : 'Summary', Icons.summarize_rounded, [
        _row(ar ? '\u0627\u0644\u0645\u0642\u0637\u0639 \u0627\u0644\u0645\u062d\u062f\u062f' : 'Selected Range',
          '${_fmtTime(_trimStart * _durationSec)} ${ar ? "\u2190" : "\u2192"} ${_fmtTime(_trimEnd * _durationSec)}'),
        _row(ar ? '\u0627\u0644\u0645\u062f\u0629' : 'Duration',
            _fmtTime((_trimEnd - _trimStart) * _durationSec)),
        _row(ar ? '\u0627\u0644\u0635\u064a\u063a\u0629' : 'Format',
            '$_fmt${_fmt == "WAV" ? "" : " @ $_kbps kbps"}'),
      ]),
      if (_outPath != null) ...[ const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(color: _redDk.withValues(alpha: 0.6),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: _red.withValues(alpha: 0.4))),
          child: Row(children: [
            const Icon(Icons.check_circle_rounded, color: _coral, size: 20),
            const SizedBox(width: 10),
            Expanded(child: Text('${ar ? "\u062a\u0645 \u0627\u0644\u062d\u0641\u0638: " : "Saved: "}$_outPath',
                style: const TextStyle(color: _textA, fontSize: 11),
                overflow: TextOverflow.ellipsis, maxLines: 2)),
          ])) ],
      const SizedBox(height: 14),
      GestureDetector(
        onTap: _busy ? null : _export,
        child: AnimatedBuilder(
          animation: _pulseCtrl,
          builder: (_, __) => Container(
            padding: const EdgeInsets.symmetric(vertical: 18),
            decoration: BoxDecoration(
              gradient: const LinearGradient(
                colors: [Color(0xFFAA2008), _red, Color(0xFFFF5733)],
                begin: Alignment.centerLeft, end: Alignment.centerRight),
              borderRadius: BorderRadius.circular(14),
              boxShadow: [BoxShadow(
                  color: _red.withValues(alpha: _busy ? 0.05 : 0.18 + 0.14 * _pulseCtrl.value),
                  blurRadius: 24, offset: const Offset(0, 6))]),
            child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              const Icon(Icons.science_rounded, color: Colors.white, size: 22),
              const SizedBox(width: 10),
              Text(ar ? '\u0645\u0639\u0627\u0644\u062c\u0629 \u0648\u062a\u0635\u062f\u064a\u0631' : 'Process & Export',
                  style: const TextStyle(color: Colors.white, fontSize: 16,
                      fontWeight: FontWeight.w900, letterSpacing: 0.3)),
            ])))),
    ]);
  }

  // ── Shared widget helpers ─────────────────────────────────────────────────
  Widget _sectionCard(String title, IconData icon, List<Widget> body) =>
    Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _rim, width: 1)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, color: _coral, size: 16), const SizedBox(width: 7),
          Text(title, style: const TextStyle(color: _textB, fontSize: 12,
              fontWeight: FontWeight.w700, letterSpacing: 0.3)),
        ]),
        const SizedBox(height: 12),
        ...body,
      ]));

  Widget _slider(double val, double min, double max, Color color,
      ValueChanged<double> onChanged) =>
    Directionality(textDirection: TextDirection.ltr,
      child: SliderTheme(
        data: SliderThemeData(trackHeight: 4,
          thumbSize: WidgetStateProperty.all(const Size(16, 16)),
          thumbColor: color, activeTrackColor: color.withValues(alpha: 0.85),
          inactiveTrackColor: _rim, overlayColor: color.withValues(alpha: 0.12)),
        child: Slider(value: val, min: min, max: max, onChanged: onChanged)));

  Widget _knob(String label, String valueStr, double val, double min,
      double max, ValueChanged<double> onChanged) =>
    Padding(padding: const EdgeInsets.only(bottom: 10),
      child: Row(children: [
        SizedBox(width: 90, child: Text(label,
            style: const TextStyle(color: _textB, fontSize: 12))),
        Expanded(child: _slider(val, min, max, _red, onChanged)),
        SizedBox(width: 68, child: Text(valueStr, textAlign: TextAlign.end,
            style: const TextStyle(color: _coral, fontSize: 12, fontWeight: FontWeight.w700))),
      ]));

  Widget _chip(String label, VoidCallback onTap) =>
    GestureDetector(onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(color: _redDk, borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _red.withValues(alpha: 0.4))),
        child: Text(label, style: const TextStyle(
            color: _coral, fontSize: 11, fontWeight: FontWeight.w700))));

  Widget _preset(String label, List<double> vals) =>
    GestureDetector(onTap: () => setState(() { for (int i=0;i<5;i++) _eq[i]=vals[i]; }),
      child: Container(
        margin: const EdgeInsets.only(right: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _rim)),
        child: Text(label, style: const TextStyle(
            color: _textB, fontSize: 11, fontWeight: FontWeight.w600))));

  Widget _row(String label, String value) =>
    Padding(padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Text(label, style: const TextStyle(color: _textB, fontSize: 12)),
        const Spacer(),
        Text(value, style: const TextStyle(color: _coral, fontSize: 12,
            fontWeight: FontWeight.w600)),
      ]));
}

// ─────────────────────────────────────────────────────────────────────────────
// WAVEFORM PAINTER — AudioLab red gradient style
// ─────────────────────────────────────────────────────────────────────────────
class _WavePainter extends CustomPainter {
  final List<double> bars;
  final double playPos, trimStart, trimEnd, animT;
  final bool playing;
  _WavePainter({required this.bars, required this.playPos,
      required this.trimStart, required this.trimEnd,
      required this.animT, required this.playing});

  @override
  void paint(Canvas c, Size sz) {
    final n   = bars.length;
    final bw  = sz.width / n;
    final mid = sz.height / 2;
    final gap = 1.0;
    final rActive   = Paint()..shader = ui.Gradient.linear(
        Offset(0, 0), Offset(0, sz.height),
        [const Color(0xFFFF5733), const Color(0xFF8C1A0A)]);
    final rInactive = Paint()..shader = ui.Gradient.linear(
        Offset(0, 0), Offset(0, sz.height), [
      const Color(0xFF4D1A10).withOpacity(0.6),
      const Color(0xFF200806).withOpacity(0.4)]);
    final rTrim = Paint()..color = const Color(0xFF3D0F08).withOpacity(0.55);
    final rPlay = Paint()..color = const Color(0xFFFF3D1A).withOpacity(0.18);

    final x0 = trimStart * sz.width, x1 = trimEnd * sz.width;
    if (trimStart > 0)
      c.drawRect(Rect.fromLTWH(0, 0, x0, sz.height), rTrim);
    if (trimEnd < 1)
      c.drawRect(Rect.fromLTWH(x1, 0, sz.width - x1, sz.height), rTrim);

    for (int i = 0; i < n; i++) {
      final x    = i * bw + gap;
      final frac = i / n;
      final inTrim = frac >= trimStart && frac < trimEnd;
      final pulse  = playing ? 0.08 * sin(animT * 2 * pi + i * 0.25) : 0.0;
      final h = (bars[i] + pulse).clamp(0.05, 1.0) * mid * 0.88;
      c.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTWH(x, mid - h, bw - gap * 2, h * 2),
          const Radius.circular(2.5)),
        inTrim ? rActive : rInactive);
    }

    final px = playPos * sz.width;
    c.drawRect(Rect.fromLTWH(0, 0, px, sz.height), rPlay);
    c.drawLine(Offset(px, 0), Offset(px, sz.height),
        Paint()..color = const Color(0xFFFF3D1A)..strokeWidth = 1.5);
    _handle(c, x0, sz.height, const Color(0xFFFF5733), true);
    _handle(c, x1, sz.height, const Color(0xFFFFAB40), false);
  }

  void _handle(Canvas c, double x, double h, Color col, bool start) {
    c.drawLine(Offset(x, 0), Offset(x, h),
        Paint()..color = col..strokeWidth = 1.8);
    final p = Path();
    if (start) { p.moveTo(x,0); p.lineTo(x+9,0); p.lineTo(x,10); p.close(); }
    else        { p.moveTo(x,0); p.lineTo(x-9,0); p.lineTo(x,10); p.close(); }
    c.drawPath(p, Paint()..color = col);
  }

  @override bool shouldRepaint(_WavePainter o) => true;
}

// ─────────────────────────────────────────────────────────────────────────────
// EQ CURVE PAINTER
// ─────────────────────────────────────────────────────────────────────────────
class _EqPainter extends CustomPainter {
  final List<double> values;
  _EqPainter({required this.values});

  @override
  void paint(Canvas c, Size sz) {
    if (values.length < 2) return;
    final n = values.length;
    final midY = sz.height / 2;
    final scX  = sz.width / (n - 1);
    final scY  = midY / 14;

    final gridP = Paint()..color = const Color(0xFF3D1A12)..strokeWidth = 0.5;
    c.drawLine(Offset(0, midY), Offset(sz.width, midY), gridP);
    for (final y in [midY - 6 * scY, midY + 6 * scY])
      c.drawLine(Offset(0, y), Offset(sz.width, y),
          Paint()..color = const Color(0xFF2A0E08)..strokeWidth = 0.5);

    final path = Path();
    for (int i = 0; i < n; i++) {
      final x = i * scX;
      final y = midY - values[i] * scY;
      if (i == 0) path.moveTo(x, y); else path.lineTo(x, y);
    }
    c.drawPath(path, Paint()
      ..style = PaintingStyle.stroke..strokeWidth = 2
      ..strokeCap = StrokeCap.round..strokeJoin = StrokeJoin.round
      ..shader = ui.Gradient.linear(const Offset(0, 0), Offset(sz.width, 0),
          [const Color(0xFFFF3D1A), const Color(0xFFFF6B40)]));

    final fill = Path.from(path);
    fill.lineTo((n - 1) * scX, midY); fill.lineTo(0, midY); fill.close();
    c.drawPath(fill, Paint()..shader = ui.Gradient.linear(
        Offset(0, midY - 14 * scY), Offset(0, midY + 14 * scY), [
      const Color(0xFFFF3D1A).withOpacity(0.22),
      const Color(0xFFFF3D1A).withOpacity(0.0)]));
  }

  @override bool shouldRepaint(_EqPainter o) => values != o.values;
}
"""

overwrite('lib/screens/audio_editor_screen.dart', AUDIO_EDITOR_DART,
          'S203: AudioLab-style audio editor redesign')

# ── Commit ───────────────────────────────────────────────────────────────────
import subprocess
result = subprocess.run(
    ['git', '-C', str(REPO), 'add',
     'lib/screens/audio_editor_screen.dart',
     'engine_itiqan_v6_local.py',
     'engine_safaa_v5_local.py'],
    capture_output=True, text=True)
if result.returncode == 0:
    subprocess.run(
        ['git', '-C', str(REPO), 'commit', '-m',
         'S203: local-mode engines and AudioLab audio editor redesign'],
        capture_output=True, text=True)
    print('\n  git add + commit done')
else:
    print(f'\n  git add warning: {result.stderr.strip()} (manual commit needed)')

STAMP.write_text('ok\n')
print('\nDone — S203 applied.\n')
print('  ITIQAN-LOCAL-A  HOME env fixed for proot')
print('  ITIQAN-LOCAL-B  return-code comment updated')
print('  SAFAA-LOCAL-A   /app/deep-filter HF path removed')
print('  AUDIO EDITOR    Full AudioLab-style redesign (red/coral lab palette)')
print()
print('  Deploy:')
print('    Upload engine_itiqan_v6_local.py + engine_safaa_v5_local.py to HF Space')
print('    OR place them in the repo engines/ dir if bundled in APK')
print('    Rebuild APK to pick up the new audio_editor_screen.dart')
