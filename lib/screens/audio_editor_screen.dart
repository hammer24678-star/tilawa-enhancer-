// audio_editor_screen.dart — S203b: AudioLab features, Sacred Cosmos theme
// S228: Studio Engine — numpy/scipy general-purpose DSP (separate from the
// الصفاء/الإتقان restoration engines) with real parametric EQ, spectral noise
// reduction, declick, convolution reverb, phase-vocoder pitch/tempo, and
// LUFS-ish loudness normalize + true-peak limiting. Falls back to the plain
// ffmpeg filter chain below if the Studio Engine is unavailable/fails.
// Trim · Split · 10-band EQ · Effects (Noise Reduce/Compress/Normalize/Reverse)
// Merge · Set as Ringtone · Export via ffmpeg (proot local engine)

import 'dart:async';
import 'dart:convert';
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

enum _Tab { trim, eq, effects, fx2, studio, merge, export_ }

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
  bool   _reverse   = false;
  double _noiseReduc = 0;   // 0-100
  bool   _compress  = false;
  double _compThresh = -18.0;
  double _compRatio  = 4.0;

  // S228 — Studio Engine (numpy/scipy) advanced settings
  double _eqQ            = 1.4;      // parametric EQ per-band Q (bandwidth)
  bool   _declick         = false;
  double _declickSens     = 50;      // 0-100
  String _reverbType      = 'Room';  // Room / Hall / Plate / Cathedral
  double _compAttack      = 20;      // ms
  double _compRelease     = 200;     // ms
  double _compMakeup      = 0;       // dB
  String _loudnessTarget  = 'Off';   // Off / -14 LUFS (Streaming) / -16 LUFS (Mobile) / -23 LUFS (Broadcast)
  bool   _truePeakLimiter = true;
  String _fadeCurve       = 'Equal Power'; // Linear / Equal Power / Exponential
  bool   _dspBusy         = false;   // preview-only busy flag (separate from export _busy)
  String? _dspScriptPath;           // cached copy of the bundled Studio Engine script

  // S232 — FX rack: which row is expanded (single-open, like a hardware rack) + search
  String? _fx2OpenId;
  String  _fx2Search = '';

  // S229 — FX+ tab: tone shaping
  double _bassBoost   = 0;      // dB, -12..12
  double _trebleBoost = 0;      // dB, -12..12
  double _subBass     = 0;      // 0-100
  double _presence    = 0;      // 0-100 (clarity/crystalizer)
  double _hpFreq      = 0;      // Hz, 0 = off
  double _lpFreq      = 20000;  // Hz, 20000 = off

  // S229 — FX+ tab: character effects
  double _tremolo = 0;   // 0-100
  double _vibrato = 0;   // 0-100
  bool   _chorus  = false;
  bool   _flanger = false;
  bool   _phaser  = false;
  double _crusher = 0;   // 0-100 (bitcrush amount)

  // S229 — FX+ tab: stereo & space
  bool   _haasWiden   = false;
  double _stereoFx    = 0;         // -100..100 (extrastereo)
  String _channelMode = 'Stereo';  // Stereo / Mono / Left / Right
  bool   _swapLR      = false;

  // S229 — FX+ tab: cleanup & dynamics
  bool   _noiseGate       = false;
  double _gateThresh      = -50;   // dB
  double _deEsser         = 0;     // 0-100
  bool   _declip          = false;
  bool   _autoNormalize   = false;
  bool   _limiter         = false;
  double _limiterCeil     = -1.0;  // dB
  bool   _autoTrimSilence = false;
  double _padStart        = 0;     // sec
  double _padEnd          = 0;     // sec

  // Merge
  String? _mergePath;
  String  _mergeName = '';
  bool    _mergeAppend = true;

  // Export
  String _fmt      = 'MP3';
  int    _kbps     = 192;
  bool   _asRingtone = false;

  // S229 — export details
  int    _sampleRate  = 48000;   // 16000 / 22050 / 44100 / 48000
  String _channels    = 'Stereo';
  int    _wavBitDepth = 16;      // 16 / 24 / 32
  String _metaTitle   = '';
  String _metaArtist  = '';
  String _metaAlbum   = '';
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
  String _codec() => _fmt == 'WAV'
      ? (_wavBitDepth == 24 ? 'pcm_s24le' : _wavBitDepth == 32 ? 'pcm_s32le' : 'pcm_s16le')
      : _fmt == 'M4A' ? 'aac' : 'libmp3lame';
  String _br()    => _fmt == 'WAV' ? '' : '-b:a ${_kbps}k';

  // S229 — shared -metadata flags for both single export and batch export
  String _metaArgs() {
    final parts = <String>[];
    if (_metaTitle.isNotEmpty)  parts.add('-metadata title="${_metaTitle.replaceAll('"', "'")}"');
    if (_metaArtist.isNotEmpty) parts.add('-metadata artist="${_metaArtist.replaceAll('"', "'")}"');
    if (_metaAlbum.isNotEmpty)  parts.add('-metadata album="${_metaAlbum.replaceAll('"', "'")}"');
    return parts.join(' ');
  }

  List<String> _buildAf() {
    final af = <String>[];
    if (_reverse) af.add('areverse');
    // S229 — auto-trim leading/trailing silence, before any other shaping
    if (_autoTrimSilence)
      af.add('silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08:'
          'stop_periods=-1:stop_threshold=-45dB:stop_silence=0.08');
    if (_noiseReduc > 0)
      af.add('afftdn=nr=${(_noiseReduc * 0.97).toStringAsFixed(1)}:nf=-25');
    if (_declip) af.add('adeclip');
    if (_noiseGate)
      af.add('agate=threshold=${_gateThresh.toStringAsFixed(0)}dB:ratio=6:attack=5:release=150');
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
    // S229 — tone shaping
    if (_bassBoost   != 0) af.add('bass=g=${_bassBoost.toStringAsFixed(1)}:f=100:w=0.8');
    if (_trebleBoost != 0) af.add('treble=g=${_trebleBoost.toStringAsFixed(1)}:f=6500:w=0.8');
    if (_subBass  > 0) af.add('asubboost=dry=1:wet=${(_subBass/100).toStringAsFixed(2)}');
    if (_presence > 0) af.add('crystalizer=i=${(_presence/100*8).toStringAsFixed(2)}:c=0');
    if (_hpFreq > 0) af.add('highpass=f=${_hpFreq.round()}:poles=2');
    if (_lpFreq < 20000) af.add('lowpass=f=${_lpFreq.round()}:poles=2');
    if (_echo   > 0) af.add('aecho=0.8:${(_echo/100).toStringAsFixed(2)}:500:0.5');
    if (_reverb > 0) af.add('aecho=0.8:${(_reverb/100).toStringAsFixed(2)}:80:0.3');
    if (_pitch  != 0) {
      final r = (pow(2.0, _pitch / 12.0) as double);
      final co = (1.0 / r).clamp(0.5, 2.0).toStringAsFixed(6);
      af.add('asetrate=44100*${r.toStringAsFixed(6)},aresample=44100,atempo=$co');
    }
    if (_tempo != 1.0) af.add('atempo=${_tempo.clamp(0.5,2.0).toStringAsFixed(2)}');
    // S229 — character FX
    if (_tremolo > 0) af.add('tremolo=f=5:d=${(_tremolo/100).toStringAsFixed(2)}');
    if (_vibrato > 0) af.add('vibrato=f=5:d=${(_vibrato/100).toStringAsFixed(2)}');
    if (_chorus)  af.add('chorus=0.6:0.9:55|60|40:0.4|0.32|0.3:0.25|0.4|0.3:2|2.3|1.3');
    if (_flanger) af.add('flanger');
    if (_phaser)  af.add('aphaser=in_gain=0.5');
    if (_crusher > 0)
      af.add('acrusher=bits=${(16 - (_crusher/100*11)).round()}:mode=log:aa=1');
    if (_stereoW != 1.0) af.add('stereotools=mlev=${_stereoW.toStringAsFixed(2)}');
    // S229 — stereo & space
    if (_haasWiden) af.add('haas');
    if (_stereoFx != 0)
      af.add('extrastereo=m=${(1 + _stereoFx/100).toStringAsFixed(2)}:c=0');
    if (_swapLR) af.add('pan=stereo|c0=c1|c1=c0');
    if (_channelMode == 'Mono')  af.add('pan=mono|c0=0.5*c0+0.5*c1');
    if (_channelMode == 'Left')  af.add('pan=stereo|c0=c0|c1=c0');
    if (_channelMode == 'Right') af.add('pan=stereo|c0=c1|c1=c1');
    if (_compress)
      af.add('acompressor=threshold=${_compThresh.toStringAsFixed(1)}dB'
          ':ratio=${_compRatio.toStringAsFixed(1)}:attack=20:release=200');
    // S229 — de-esser / adaptive normalize / limiter
    if (_deEsser > 0) af.add('deesser=i=${(_deEsser/100).toStringAsFixed(2)}');
    if (_autoNormalize) af.add('dynaudnorm=f=150:g=15');
    if (_limiter) af.add('alimiter=limit=${_limiterCeil.toStringAsFixed(1)}dB:attack=5:release=50');
    if (_loudnessTarget != 'Off') af.add('loudnorm');  // S228: legacy fallback — blunt vs the Studio Engine's real LUFS normalize
    if (_vol != 1.0) af.add('volume=${_vol.toStringAsFixed(2)}');
    // S229 — start/end padding, always last
    if (_padStart > 0) af.add('adelay=${(_padStart*1000).round()}:all=1');
    if (_padEnd   > 0) af.add('apad=pad_dur=${_padEnd.toStringAsFixed(1)}');
    return af;
  }

  // ── S228: STUDIO ENGINE (numpy/scipy) ───────────────────────────────────
  // Bundled as a Flutter asset (assets/dsp/tilawa_dsp_studio.py), copied once
  // to the same temp/cache dir _safeInput() already uses (bind-mounted into
  // proot by runProotCmd for every call), then invoked as a plain `python3`
  // command through the existing generic proot shell channel. No new native/
  // Kotlin code needed — and nothing here touches the restoration engines.
  Future<String> _ensureDspScript() async {
    if (_dspScriptPath != null && File(_dspScriptPath!).existsSync()) return _dspScriptPath!;
    final dir  = await getTemporaryDirectory();
    final dst  = File('${dir.path}/tilawa_dsp_studio_v1.py');
    final data = await rootBundle.load('assets/dsp/tilawa_dsp_studio.py');
    await dst.writeAsBytes(data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes), flush: true);
    _dspScriptPath = dst.path;
    return dst.path;
  }

  Map<String, dynamic> _buildDspParams({double? previewStart, double? previewDur}) {
    final isPreview = previewStart != null;
    final ss  = isPreview ? previewStart! : (_trimStart * _durationSec);
    final dur = isPreview ? (previewDur ?? 0) : ((_trimEnd - _trimStart) * _durationSec);
    double? lufs;
    switch (_loudnessTarget) {
      case '-14 LUFS (Streaming)': lufs = -14; break;
      case '-16 LUFS (Mobile)':    lufs = -16; break;
      case '-23 LUFS (Broadcast)': lufs = -23; break;
      default: lufs = null;
    }
    return {
      'sr': 48000,
      'trim_start': ss,
      'trim_dur': dur,
      'reverse': isPreview ? false : _reverse,
      'eq_freqs': _freqs,
      'eq_gains': _eq,
      'eq_q': _eqQ,
      'declick': {'enabled': _declick, 'sensitivity': _declickSens},
      'noise_reduction': {'strength': _noiseReduc},
      'fade_in': isPreview ? 0.0 : _fadeIn,
      'fade_out': isPreview ? 0.0 : _fadeOut,
      'fade_curve': _fadeCurve,
      'pitch_semitones': _pitch,
      'tempo': _tempo,
      'echo': {'mix': _echo},
      'reverb': {'mix': _reverb, 'type': _reverbType},
      'compressor': {
        'enabled': _compress, 'threshold_db': _compThresh, 'ratio': _compRatio,
        'attack_ms': _compAttack, 'release_ms': _compRelease, 'makeup_db': _compMakeup,
      },
      'stereo_width': _stereoW,
      'volume': _vol,
      'loudness': {'target_lufs': lufs, 'true_peak_limit_db': -1.0, 'limiter': _truePeakLimiter},
      // S229 — forwarded for a future Studio Engine build; the ffmpeg fallback
      // in _buildAf() already implements every one of these today.
      'fx2': {
        'bass_db': _bassBoost, 'treble_db': _trebleBoost, 'sub_bass': _subBass,
        'presence': _presence, 'highpass_hz': _hpFreq, 'lowpass_hz': _lpFreq,
        'tremolo': _tremolo, 'vibrato': _vibrato, 'chorus': _chorus,
        'flanger': _flanger, 'phaser': _phaser, 'bitcrush': _crusher,
        'haas_widen': _haasWiden, 'stereo_fx': _stereoFx,
        'channel_mode': _channelMode, 'swap_lr': _swapLR,
        'noise_gate': {'enabled': _noiseGate, 'threshold_db': _gateThresh},
        'deesser': _deEsser, 'declip': _declip, 'adaptive_normalize': _autoNormalize,
        'limiter': {'enabled': _limiter, 'ceiling_db': _limiterCeil},
        'auto_trim_silence': _autoTrimSilence,
        'pad_start_sec': _padStart, 'pad_end_sec': _padEnd,
      },
      'output': {
        'format': isPreview ? 'WAV' : _fmt, 'kbps': _kbps,
        'sample_rate': _sampleRate, 'channels': _channels, 'wav_bit_depth': _wavBitDepth,
        'metadata': {'title': _metaTitle, 'artist': _metaArtist, 'album': _metaAlbum},
      },
    };
  }

  Future<Map<String, dynamic>> _runDspEngine(
      String inp, String out, Map<String, dynamic> params) async {
    final script = await _ensureDspScript();
    final tmp = await getTemporaryDirectory();
    final paramsFile = File('${tmp.path}/tl_dsp_params_${DateTime.now().millisecondsSinceEpoch}.json');
    await paramsFile.writeAsString(jsonEncode(params));
    final cmd = 'python3 "$script" "$inp" "$out" "${paramsFile.path}"';
    final r = await _proot(cmd, inp, out, timeout: 20);
    try { await paramsFile.delete(); } catch (_) {}
    return Map<String, dynamic>.from(r ?? {'rc': -1, 'out': 'no result'});
  }

  /// Renders a short slice (current playhead, or trim start) through the
  /// Studio Engine with the live settings, so the user can audition before
  /// committing to a full export. "Preview" = quick audition, not a visual.
  Future<void> _previewDsp() async {
    if (_filePath == null) return;
    if (!await _checkSetup()) return;
    if (_dspBusy) return;
    HapticFeedback.selectionClick();
    setState(() => _dspBusy = true);
    try {
      if (_playing) await _player.stop();
      final inp = await _safeInput(_filePath!);
      final tmp = await getTemporaryDirectory();
      final out = '${tmp.path}/tl_preview_${DateTime.now().millisecondsSinceEpoch}.wav';
      final rangeEnd   = _trimEnd * _durationSec;
      final rangeStart = _trimStart * _durationSec;
      final start = (_positionSec >= rangeStart && _positionSec < rangeEnd)
          ? _positionSec : rangeStart;
      final remain = (rangeEnd - start).clamp(0.2, double.infinity);
      final dur = remain > 8.0 ? 8.0 : remain;
      final params = _buildDspParams(previewStart: start, previewDur: dur);
      final r = await _runDspEngine(inp, out, params);
      final rc = (r['rc'] as int?) ?? -1;
      if (rc != 0 || !File(out).existsSync()) {
        throw Exception(r['out'] ?? 'Studio Engine preview failed');
      }
      await _player.setSource(DeviceFileSource(out));
      await _player.resume();
      _snack('▶ Previewing ${dur.toStringAsFixed(1)}s with current settings', color: _teal);
    } catch (e) {
      _snack('Preview error: $e', color: _red);
    } finally {
      if (mounted) setState(() => _dspBusy = false);
    }
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
      setState(() => _pct = 0.15);
      final params = _buildDspParams();
      final r = await _runDspEngine(inp, out, params);
      final rc = (r['rc'] as int?) ?? -1;
      if (rc != 0 || !File(out).existsSync()) {
        // S228: Studio Engine unavailable/failed (e.g. numpy/scipy missing
        // inside proot) — fall back to the plain ffmpeg filter chain so
        // export still works, just without the advanced DSP.
        final ss  = (_trimStart * _durationSec).toStringAsFixed(3);
        final dur = ((_trimEnd - _trimStart) * _durationSec).toStringAsFixed(3);
        final af  = _buildAf();
        final cmd = 'ffmpeg -y -ss $ss -i "$inp" -t $dur '
            '-af ${af.isEmpty ? "anull" : af.join(",")} ${_metaArgs()} '
            '-ar $_sampleRate -ac ${_channels == "Mono" ? 1 : 2} '
            '-acodec ${_codec()} ${_br()} "$out"';
        final r2 = await _proot(cmd, inp, out, timeout: 15);
        final rc2 = (r2?['rc'] as int?) ?? 1;
        if (rc2 != 0) {
          throw Exception('Export failed — studio: ${r['out']} · ffmpeg: ${r2?['out'] ?? ''}');
        }
      }
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
        border: Border(bottom: BorderSide(color: _gold.withValues(alpha: 0.25), width: 1)),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.25),
            blurRadius: 10, offset: const Offset(0, 3))]),
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child: Row(children: [
        IconButton(icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: _textB),
          onPressed: () => _busy ? _warnBusy() : Navigator.pop(context)),
        Expanded(child: ShaderMask(
          shaderCallback: (b) => const LinearGradient(colors: [_gold, Color(0xFFF0CF60)]).createShader(b),
          child: Text(ar ? 'محرر الصوت' : 'Audio Editor',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w800)))),
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
              '• موازن 10 أحزمة: موازن معلمي حقيقي (numpy/scipy) بدقة Q قابلة للضبط.\n'
              '• تأثيرات: تلاشي، طبقة صوت، سرعة، صدى، إرجاع، عكس، تقليص ضوضاء طيفي، ضغط.\n'
              '• استوديو: إزالة طقطقة، نوع الصدى، ديناميكية الضاغط، تطبيع الصوت LUFS.\n'
              '• معاينة: استمع لـ٨ ثوانٍ بالإعدادات الحالية قبل التصدير الكامل.\n'
              '• دمج: جمع ملفين صوتيين.\n'
              '• تصدير: MP3/WAV/M4A + حفظ كنغمة رنين.\n'
              '⚙️ محلي بالكامل — محرك الاستوديو (numpy/scipy) مع رجوع تلقائي لـ ffmpeg — بدون إنترنت.'
            : '• Trim: set start/end range.\n'
              '• Split: tap ✂️ in transport to split at playhead into two files.\n'
              '• 10-band EQ: real parametric EQ (numpy/scipy) with adjustable Q.\n'
              '• Effects: fade, pitch, speed, echo, reverb, reverse, spectral noise reduction, compressor.\n'
              '• Studio: declick, reverb type, compressor dynamics, LUFS loudness normalize.\n'
              '• Preview: audition 8s with your current settings before a full export.\n'
              '• Merge: join two audio files.\n'
              '• Export: MP3/WAV/M4A + Set as Ringtone.\n'
              '⚙️ Fully local — Studio Engine (numpy/scipy) with automatic ffmpeg fallback, no internet needed.',
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
    if (_tab == _Tab.eq || _tab == _Tab.effects || _tab == _Tab.fx2 || _tab == _Tab.studio) _previewBar(),
    Expanded(child: _tabBody()),
  ]);

  // S228: quick-audition bar for the Studio Engine — shown on the tabs whose
  // settings actually feed the DSP pipeline (EQ / Effects / Studio).
  Widget _previewBar() {
    final ar = LangProvider.strings(context).ar;
    return Container(
      color: _surface,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(children: [
        const Icon(Icons.science_rounded, color: _teal, size: 15),
        const SizedBox(width: 6),
        Expanded(
          child: Text(
            ar ? 'محرك الاستوديو (numpy/scipy)' : 'Studio Engine (numpy/scipy)',
            style: const TextStyle(color: _textB, fontSize: 11, fontWeight: FontWeight.w600),
          ),
        ),
        GestureDetector(
          onTap: _dspBusy ? null : _previewDsp,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
            decoration: BoxDecoration(
              color: _tealDk,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _teal.withValues(alpha: 0.5)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (_dspBusy)
                  const SizedBox(
                    width: 12, height: 12,
                    child: CircularProgressIndicator(strokeWidth: 2, color: _teal),
                  )
                else
                  const Icon(Icons.headphones_rounded, color: _teal, size: 14),
                const SizedBox(width: 6),
                Text(
                  ar ? 'معاينة (٨ث)' : 'Preview (8s)',
                  style: const TextStyle(color: _teal, fontSize: 12, fontWeight: FontWeight.w700),
                ),
              ],
            ),
          ),
        ),
      ]),
    );
  }

  Widget _fileBar() => Container(
    decoration: BoxDecoration(color: _surface,
        border: Border(bottom: BorderSide(color: _border.withValues(alpha: 0.6)))),
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
    child: Row(children: [
      Container(width: 26, height: 26, alignment: Alignment.center,
        decoration: BoxDecoration(shape: BoxShape.circle,
            color: _teal.withValues(alpha: 0.14),
            border: Border.all(color: _teal.withValues(alpha: 0.4))),
        child: const Icon(Icons.music_note_rounded, color: _teal, size: 14)),
      const SizedBox(width: 10),
      Expanded(child: Text(_fileName, overflow: TextOverflow.ellipsis,
          style: const TextStyle(color: _textA, fontSize: 13, fontWeight: FontWeight.w600))),
      const SizedBox(width: 10),
      Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(8),
            border: Border.all(color: _border)),
        child: Text(_fmtTime(_durationSec),
            style: const TextStyle(color: _textB, fontSize: 11.5, fontFamily: 'monospace'))),
    ]));

  Widget _waveformSection() {
    final pos = _durationSec > 0 ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0.0;
    return Container(
      margin: const EdgeInsets.fromLTRB(10, 8, 10, 4),
      padding: const EdgeInsets.symmetric(vertical: 6),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _border),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.22),
              blurRadius: 12, offset: const Offset(0, 5))]),
      child: ClipRRect(borderRadius: BorderRadius.circular(10),
        child: GestureDetector(
          onTapDown: (d) {
            final box = context.findRenderObject() as RenderBox?;
            if (box == null) return;
            final frac = (d.localPosition.dx / box.size.width).clamp(0.0, 1.0);
            _player.seek(Duration(milliseconds: (frac * _durationSec * 1000).round()));
            setState(() => _positionSec = frac * _durationSec);
          },
          child: AnimatedBuilder(animation: _waveCtrl,
            builder: (_, __) => SizedBox(height: 92,
              child: CustomPaint(
                painter: _WavePainter(bars: _bars, playPos: pos,
                  trimStart: _trimStart, trimEnd: _trimEnd,
                  animT: _waveCtrl.value, playing: _playing),
                size: const Size(double.infinity, 92)))))));
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
        builder: (_, __) => GestureDetector(
          onTap: () { HapticFeedback.mediumImpact(); _togglePlay(); },
          child: AnimatedScale(duration: const Duration(milliseconds: 200),
            scale: _playing ? 1.06 : 1.0,
            child: Container(width: 54, height: 54,
              decoration: BoxDecoration(shape: BoxShape.circle,
                gradient: const RadialGradient(colors: [Color(0xFFB8921E), _goldDim]),
                boxShadow: [BoxShadow(
                    color: _gold.withValues(alpha: _playing ? 0.2 + 0.22 * _glowCtrl.value : 0.08),
                    blurRadius: 20)]),
              child: Icon(_playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
                color: const Color(0xFF050A06), size: 28))))),
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
    final labels = ar ? ['قص','EQ','تأثيرات','FX+','استوديو','دمج','تصدير']
                      : ['Trim','EQ','Effects','FX+','Studio','Merge','Export'];
    final icons = [Icons.content_cut_rounded, Icons.equalizer_rounded,
                   Icons.auto_fix_high_rounded, Icons.graphic_eq_rounded, Icons.science_rounded,
                   Icons.merge_type_rounded, Icons.ios_share_rounded];
    final n = _Tab.values.length;
    return Container(
      decoration: BoxDecoration(color: _surface, border: Border(bottom: BorderSide(color: _border)),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.15),
              blurRadius: 6, offset: const Offset(0, 3))]),
      child: Stack(children: [
        AnimatedAlign(
          duration: const Duration(milliseconds: 220), curve: Curves.easeOutCubic,
          alignment: Alignment(-1 + 2 * _tab.index / (n - 1), 1),
          child: FractionallySizedBox(widthFactor: 1 / n,
            child: Container(height: 2.4, margin: const EdgeInsets.symmetric(horizontal: 2),
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [_teal, _gold]),
                borderRadius: BorderRadius.circular(2)))),
        ),
        Row(children: _Tab.values.map((t) {
          final active = t == _tab;
          return Expanded(child: GestureDetector(
            onTap: () { HapticFeedback.selectionClick(); setState(() => _tab = t); },
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                AnimatedScale(duration: const Duration(milliseconds: 180),
                  scale: active ? 1.12 : 1.0,
                  child: Icon(icons[t.index], color: active ? _gold : _textDim, size: 19)),
                const SizedBox(height: 3),
                Text(labels[t.index], style: TextStyle(
                    color: active ? _gold : _textDim,
                    fontSize: 10, fontWeight: active ? FontWeight.w800 : FontWeight.w600)),
              ]))));
        }).toList()),
      ]));
  }

  Widget _tabBody() {
    late final Widget child;
    switch (_tab) {
      case _Tab.trim:    child = _trimTab(); break;
      case _Tab.eq:      child = _eqTab(); break;
      case _Tab.effects: child = _effectsTab(); break;
      case _Tab.fx2:     child = _fx2Tab(); break;
      case _Tab.studio:  child = _studioTab(); break;
      case _Tab.merge:   child = _mergeTab(); break;
      case _Tab.export_: child = _exportTab(); break;
    }
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 220),
      transitionBuilder: (c, anim) => FadeTransition(opacity: anim,
          child: SlideTransition(
              position: Tween<Offset>(begin: const Offset(0, 0.02), end: Offset.zero).animate(anim),
              child: c)),
      child: KeyedSubtree(key: ValueKey(_tab), child: child),
    );
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
        Text(ar ? 'تقليل ضوضاء طيفي (STFT) — 0 = معطل' : 'Spectral (STFT) noise reduction — 0 = disabled',
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
        _toggle(ar ? 'عكس (Reverse)'    : 'Reverse',   Icons.swap_horiz_rounded,  _reverse,   (v) => setState(() => _reverse = v)),
        const SizedBox(height: 8),
        Text(ar ? 'تطبيع الصوت (LUFS) انتقل الآن لتبويب ‘استوديو’ ←'
                : 'Loudness Normalize (LUFS) moved to the Studio tab →',
            style: const TextStyle(color: _textDim, fontSize: 11)),
      ]),
      const SizedBox(height: 10),
      GestureDetector(
        onTap: () {
          HapticFeedback.mediumImpact();
          setState(() {
            _vol=1.0; _pitch=0; _tempo=1.0; _stereoW=1.0;
            _fadeIn=0; _fadeOut=0; _echo=0; _reverb=0;
            _noiseReduc=0; _compress=false; _compThresh=-18; _compRatio=4.0;
            _reverse=false;
            // S228 — Studio Engine settings
            _eqQ=1.4; _declick=false; _declickSens=50; _reverbType='Room';
            _compAttack=20; _compRelease=200; _compMakeup=0;
            _loudnessTarget='Off'; _truePeakLimiter=true; _fadeCurve='Equal Power';
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

  // ── STUDIO TAB — S228 advanced Studio Engine settings ───────────────────
  Widget _studioTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _card_(ar ? 'محرك الاستوديو' : 'Studio Engine', Icons.science_rounded, [
        Text(ar
            ? 'معالجة حقيقية بواسطة numpy/scipy تعمل بالكامل على الجهاز: موازن معلمي حقيقي، تقليل ضوضاء طيفي، إزالة الطقطقة، صدى تلافيفي، وتطبيع صوت (LUFS) مع محدد ذروة حقيقية. عند فشل المحرك يتم الرجوع تلقائيًا لسلسلة مرشحات ffmpeg.'
            : 'Real numpy/scipy DSP running fully on-device: true parametric EQ, spectral noise reduction, declicking, convolution reverb, and LUFS-ish loudness normalize with a true-peak limiter. Falls back automatically to the plain ffmpeg filter chain if unavailable.',
            style: const TextStyle(color: _textB, fontSize: 12, height: 1.5)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'دقة الموازن (Q)' : 'EQ Sharpness (Q)', Icons.tune_rounded, [
        _knob(ar ? 'حدة النطاق' : 'Band Q', _eqQ.toStringAsFixed(2), _eqQ, 0.4, 4.0,
            (v) => setState(() => _eqQ = v)),
        Text(ar ? 'قيم أعلى = نطاقات أضيق وأكثر دقة' : 'Higher = narrower, more surgical bands',
            style: const TextStyle(color: _textDim, fontSize: 11)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'إزالة الطقطقة' : 'Declick', Icons.grain_rounded, [
        _toggle(ar ? 'تفعيل إزالة الطقطقة' : 'Enable Declick', Icons.grain_rounded,
            _declick, (v) => setState(() => _declick = v)),
        if (_declick) ...[const SizedBox(height: 8),
          _knob(ar ? 'الحساسية' : 'Sensitivity', '${_declickSens.round()}%',
              _declickSens, 10, 100, (v) => setState(() => _declickSens = v))],
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'نوع الصدى (Reverb)' : 'Reverb Type', Icons.surround_sound_rounded, [
        Wrap(spacing: 8, runSpacing: 8, children: ['Room','Hall','Plate','Cathedral'].map((t) {
          final sel = t == _reverbType;
          return GestureDetector(onTap: () => setState(() => _reverbType = t),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: sel ? _goldDim.withValues(alpha: 0.4) : _card,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: sel ? _gold : _border, width: sel ? 1.5 : 1)),
              child: Text(t, style: TextStyle(color: sel ? _gold : _textB, fontSize: 12,
                  fontWeight: sel ? FontWeight.w700 : FontWeight.w400))));
        }).toList()),
        const SizedBox(height: 8),
        Text(ar ? 'استخدم شريط ‘إرجاع’ في تبويب التأثيرات لضبط نسبة المزج'
                : 'Use the Reverb slider in the Effects tab to set the wet/dry mix',
            style: const TextStyle(color: _textDim, fontSize: 11)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'ديناميكية الضاغط' : 'Compressor Dynamics', Icons.speed_rounded, [
        _knob(ar ? 'هجوم (Attack)' : 'Attack', '${_compAttack.round()} ms',
            _compAttack, 1, 200, (v) => setState(() => _compAttack = v)),
        _knob(ar ? 'تحرير (Release)' : 'Release', '${_compRelease.round()} ms',
            _compRelease, 20, 1000, (v) => setState(() => _compRelease = v)),
        _knob(ar ? 'تعويض (Makeup)' : 'Makeup Gain',
            '${_compMakeup >= 0 ? "+" : ""}${_compMakeup.toStringAsFixed(1)} dB',
            _compMakeup, 0, 24, (v) => setState(() => _compMakeup = v)),
        Text(ar ? 'تُطبَّق فقط عند تفعيل الضاغط في تبويب التأثيرات' : 'Only applied when Compressor is enabled in the Effects tab',
            style: const TextStyle(color: _textDim, fontSize: 11)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'تطبيع الصوت (LUFS)' : 'Loudness Normalize (LUFS)', Icons.graphic_eq_rounded, [
        Wrap(spacing: 8, runSpacing: 8,
          children: ['Off','-14 LUFS (Streaming)','-16 LUFS (Mobile)','-23 LUFS (Broadcast)'].map((t) {
          final sel = t == _loudnessTarget;
          return GestureDetector(onTap: () => setState(() => _loudnessTarget = t),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: sel ? _goldDim.withValues(alpha: 0.4) : _card,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: sel ? _gold : _border, width: sel ? 1.5 : 1)),
              child: Text(t, style: TextStyle(color: sel ? _gold : _textB, fontSize: 11,
                  fontWeight: sel ? FontWeight.w700 : FontWeight.w400))));
        }).toList()),
        if (_loudnessTarget != 'Off') ...[const SizedBox(height: 10),
          _toggle(ar ? 'محدد الذروة الحقيقية (True Peak Limiter)' : 'True Peak Limiter',
              Icons.security_rounded, _truePeakLimiter, (v) => setState(() => _truePeakLimiter = v))],
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'منحنى التلاشي' : 'Fade Curve', Icons.trending_flat_rounded, [
        Wrap(spacing: 8, runSpacing: 8, children: ['Linear','Equal Power','Exponential'].map((t) {
          final sel = t == _fadeCurve;
          return GestureDetector(onTap: () => setState(() => _fadeCurve = t),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: sel ? _goldDim.withValues(alpha: 0.4) : _card,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: sel ? _gold : _border, width: sel ? 1.5 : 1)),
              child: Text(t, style: TextStyle(color: sel ? _gold : _textB, fontSize: 11,
                  fontWeight: sel ? FontWeight.w700 : FontWeight.w400))));
        }).toList()),
      ]),
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
      _card_(ar ? 'تفاصيل التصدير' : 'Export Details', Icons.settings_input_component_rounded, [
        Text(ar ? 'معدل العينة' : 'Sample Rate', style: const TextStyle(color: _textB, fontSize: 12)),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: [16000,22050,44100,48000].map((sr) {
          final sel = sr == _sampleRate;
          return GestureDetector(onTap: () => setState(() => _sampleRate = sr),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              decoration: BoxDecoration(
                color: sel ? _goldDim.withValues(alpha: 0.4) : _card,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: sel ? _gold : _border, width: sel ? 1.5 : 1)),
              child: Text('$sr Hz', style: TextStyle(color: sel ? _gold : _textB, fontSize: 11,
                  fontWeight: sel ? FontWeight.w700 : FontWeight.w400))));
        }).toList()),
        const SizedBox(height: 14),
        Text(ar ? 'القنوات' : 'Channels', style: const TextStyle(color: _textB, fontSize: 12)),
        const SizedBox(height: 8),
        Row(children: ['Stereo','Mono'].map((c) {
          final sel = c == _channels;
          return Expanded(child: GestureDetector(onTap: () => setState(() => _channels = c),
            child: Container(margin: const EdgeInsets.only(right: 6),
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: BoxDecoration(
                color: sel ? _goldDim.withValues(alpha: 0.35) : _card,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: sel ? _gold : _border, width: sel ? 1.5 : 1)),
              child: Center(child: Text(c, style: TextStyle(color: sel ? _gold : _textB, fontSize: 12,
                  fontWeight: sel ? FontWeight.w700 : FontWeight.w500))))));
        }).toList()),
        if (_fmt == 'WAV') ...[const SizedBox(height: 14),
          Text(ar ? 'عمق البت' : 'Bit Depth', style: const TextStyle(color: _textB, fontSize: 12)),
          const SizedBox(height: 8),
          Row(children: [16,24,32].map((b) {
            final sel = b == _wavBitDepth;
            return Expanded(child: GestureDetector(onTap: () => setState(() => _wavBitDepth = b),
              child: Container(margin: const EdgeInsets.only(right: 6),
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: BoxDecoration(
                  color: sel ? _goldDim.withValues(alpha: 0.35) : _card,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: sel ? _gold : _border, width: sel ? 1.5 : 1)),
                child: Center(child: Text('$b-bit', style: TextStyle(color: sel ? _gold : _textB, fontSize: 12,
                    fontWeight: sel ? FontWeight.w700 : FontWeight.w500))))));
          }).toList())],
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'بيانات وصفية' : 'Metadata Tags', Icons.label_rounded, [
        TextField(style: const TextStyle(color: _textA, fontSize: 13),
          decoration: InputDecoration(labelText: ar ? 'العنوان' : 'Title',
              labelStyle: const TextStyle(color: _textDim, fontSize: 12)),
          onChanged: (v) => _metaTitle = v),
        TextField(style: const TextStyle(color: _textA, fontSize: 13),
          decoration: InputDecoration(labelText: ar ? 'الفنان' : 'Artist',
              labelStyle: const TextStyle(color: _textDim, fontSize: 12)),
          onChanged: (v) => _metaArtist = v),
        TextField(style: const TextStyle(color: _textA, fontSize: 13),
          decoration: InputDecoration(labelText: ar ? 'الألبوم' : 'Album',
              labelStyle: const TextStyle(color: _textDim, fontSize: 12)),
          onChanged: (v) => _metaAlbum = v),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'إعدادات مسبقة سريعة' : 'Quick Presets', Icons.flash_on_rounded, [
        Wrap(spacing: 8, runSpacing: 8, children: [
          _chip_(ar ? 'رسالة واتساب صوتية' : 'WhatsApp Voice Note', () => setState(() {
            _fmt='M4A'; _kbps=64; _sampleRate=16000; _channels='Mono'; _loudnessTarget='-16 LUFS (Mobile)';
          })),
          _chip_(ar ? 'بودكاست' : 'Podcast', () => setState(() {
            _fmt='MP3'; _kbps=128; _sampleRate=44100; _channels='Stereo'; _loudnessTarget='-16 LUFS (Mobile)';
          })),
          _chip_(ar ? 'نغمة رنين HD' : 'Ringtone HD', () => setState(() {
            _fmt='M4A'; _kbps=256; _sampleRate=48000; _channels='Stereo'; _loudnessTarget='Off';
          })),
          _chip_(ar ? 'بث آمن' : 'Broadcast Safe', () => setState(() {
            _fmt='WAV'; _sampleRate=48000; _wavBitDepth=24; _channels='Stereo';
            _loudnessTarget='-23 LUFS (Broadcast)'; _truePeakLimiter=true;
          })),
        ]),
      ]),
      const SizedBox(height: 10),
      GestureDetector(onTap: _busy ? null : _batchExport,
        child: Container(padding: const EdgeInsets.symmetric(vertical: 13),
          decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(10),
              border: Border.all(color: _border)),
          child: Center(child: Row(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.playlist_add_check_rounded, color: _textB, size: 17),
            const SizedBox(width: 6),
            Text(ar ? 'تصدير دفعي (ملفات متعددة)' : 'Batch Export (multiple files)',
                style: const TextStyle(color: _textB, fontSize: 13, fontWeight: FontWeight.w600)),
          ])))),
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
        if (_loudnessTarget != 'Off') _row('Loudness', _loudnessTarget),
        if (_declick)   _row('Declick', '${_declickSens.round()}%'),
        if (_reverse)   _row('Reverse', '✓'),
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
    Container(padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _border, width: 1),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.18),
              blurRadius: 14, offset: const Offset(0, 6))]),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(width: 26, height: 26, alignment: Alignment.center,
            decoration: BoxDecoration(shape: BoxShape.circle,
                color: _teal.withValues(alpha: 0.12),
                border: Border.all(color: _teal.withValues(alpha: 0.35))),
            child: Icon(icon, color: _teal, size: 14)),
          const SizedBox(width: 9),
          Expanded(child: Text(title, style: const TextStyle(color: _textA, fontSize: 12.5,
              fontWeight: FontWeight.w700, letterSpacing: 0.3))),
        ]),
        const SizedBox(height: 10),
        Divider(height: 1, color: _border.withValues(alpha: 0.7)),
        const SizedBox(height: 12),
        ...body,
      ]));

  Widget _slider(double val, double min, double max, Color color, ValueChanged<double> onChanged) =>
    Directionality(textDirection: TextDirection.ltr,
      child: SliderTheme(data: SliderThemeData(trackHeight: 5,
        thumbSize: WidgetStateProperty.all(const Size(18, 18)),
        thumbColor: color, activeTrackColor: color.withValues(alpha: 0.9),
        inactiveTrackColor: _border, overlayColor: color.withValues(alpha: 0.15),
        overlayShape: const RoundSliderOverlayShape(overlayRadius: 18)),
        child: Slider(value: val, min: min, max: max, onChanged: onChanged,
            onChangeStart: (_) => HapticFeedback.selectionClick())));

  Widget _knob(String label, String valueStr, double val, double min, double max,
      ValueChanged<double> onChanged) =>
    Padding(padding: const EdgeInsets.only(bottom: 12),
      child: Row(children: [
        SizedBox(width: 90, child: Text(label, style: const TextStyle(color: _textB, fontSize: 12))),
        Expanded(child: _slider(val, min, max, _gold, onChanged)),
        const SizedBox(width: 8),
        Container(
          constraints: const BoxConstraints(minWidth: 60),
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(color: _goldDim.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: _gold.withValues(alpha: 0.3))),
          child: Text(valueStr, textAlign: TextAlign.end,
              style: const TextStyle(color: _gold, fontSize: 11.5, fontWeight: FontWeight.w700,
                  fontFamily: 'monospace')),
        ),
      ]));

  Widget _chip_(String label, VoidCallback onTap) =>
    GestureDetector(onTap: () { HapticFeedback.selectionClick(); onTap(); },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(color: _tealDk, borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _teal.withValues(alpha: 0.45)),
            boxShadow: [BoxShadow(color: _teal.withValues(alpha: 0.12),
                blurRadius: 8, offset: const Offset(0, 3))]),
        child: Text(label, style: const TextStyle(color: _teal, fontSize: 11, fontWeight: FontWeight.w700))));

  Widget _preset(String label, List<double> vals) {
    final active = List.generate(10, (i) => (_eq[i] - vals[i]).abs() < 0.01).every((x) => x);
    return GestureDetector(
      onTap: () { HapticFeedback.selectionClick();
        setState(() { for (int i = 0; i < 10; i++) _eq[i] = vals[i]; }); },
      child: AnimatedContainer(duration: const Duration(milliseconds: 200),
        margin: const EdgeInsets.only(right: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
            color: active ? _goldDim.withValues(alpha: 0.55) : _card,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: active ? _gold.withValues(alpha: 0.7) : _border)),
        child: Text(label, style: TextStyle(color: active ? _gold : _textB, fontSize: 11,
            fontWeight: FontWeight.w600))));
  }

  Widget _toggle(String label, IconData icon, bool val, ValueChanged<bool> onChanged) =>
    AnimatedContainer(duration: const Duration(milliseconds: 200),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: val ? _gold.withValues(alpha: 0.08) : Colors.transparent,
        borderRadius: BorderRadius.circular(10)),
      child: Row(children: [
        Icon(icon, color: val ? _gold : _textDim, size: 17), const SizedBox(width: 8),
        Expanded(child: Text(label, style: TextStyle(color: val ? _textA : _textB, fontSize: 13))),
        Switch(value: val, activeColor: _gold, inactiveThumbColor: _textDim,
          activeTrackColor: _goldDim, inactiveTrackColor: _border,
          onChanged: (v) { HapticFeedback.selectionClick(); onChanged(v); }),
      ]));

  Widget _row(String label, String value) =>
    Padding(padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        Text(label, style: const TextStyle(color: _textB, fontSize: 12)),
        const Spacer(),
        Text(value, style: const TextStyle(color: _gold, fontSize: 12, fontWeight: FontWeight.w600)),
      ]));

  // ── FX+ TAB — S229: tone shaping, character FX, stereo/space, cleanup ────

  // ── S232: FX rack redesign — collapsible rows, lamp indicators, search ──────
  Widget _rackLamp(bool on) => Container(width: 8, height: 8,
    margin: const EdgeInsets.only(right: 10),
    decoration: BoxDecoration(shape: BoxShape.circle,
      color: on ? _gold : Colors.transparent,
      border: Border.all(color: on ? _gold : _textDim, width: 1.4),
      boxShadow: on ? [BoxShadow(color: _gold.withValues(alpha: 0.6), blurRadius: 7, spreadRadius: 1)] : null));

  Widget _rackRow({required String id, required String label, required String valueStr,
      required bool on, Widget? rightControl, Widget? body}) {
    final open = _fx2OpenId == id;
    final expandable = body != null;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: expandable ? () { HapticFeedback.selectionClick();
          setState(() => _fx2OpenId = open ? null : id); } : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(padding: const EdgeInsets.symmetric(vertical: 12),
          child: Row(children: [
            _rackLamp(on),
            Expanded(child: Text(label, style: const TextStyle(color: _textA, fontSize: 13, fontWeight: FontWeight.w600))),
            Text(valueStr, style: TextStyle(color: on ? _gold : _textDim, fontSize: 11,
                fontFamily: 'monospace', fontWeight: FontWeight.w600)),
            const SizedBox(width: 10),
            rightControl ?? AnimatedRotation(duration: const Duration(milliseconds: 200),
                turns: open ? 0.25 : 0,
                child: const Icon(Icons.chevron_right_rounded, color: _textDim, size: 18)),
          ])),
        AnimatedSize(duration: const Duration(milliseconds: 220), curve: Curves.easeOutCubic,
          child: (open && body != null)
              ? Padding(padding: const EdgeInsets.only(bottom: 12), child: body)
              : const SizedBox(width: double.infinity, height: 0)),
      ]));
  }

  Widget _rackSwitch(bool val, ValueChanged<bool> onChanged) =>
    Switch(value: val, activeColor: _gold, inactiveThumbColor: _textDim,
      activeTrackColor: _goldDim, inactiveTrackColor: _border, onChanged: onChanged);

  Widget _rackSection(String title, int onCount, List<Widget> rows) {
    if (rows.isEmpty) return const SizedBox.shrink();
    final children = <Widget>[];
    for (int i = 0; i < rows.length; i++) {
      children.add(rows[i]);
      if (i != rows.length - 1) children.add(const Divider(height: 1, color: _border));
    }
    return Padding(padding: const EdgeInsets.only(bottom: 16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Expanded(child: Text(title, style: const TextStyle(color: _textA, fontSize: 15,
              fontWeight: FontWeight.w700, fontFamily: 'serif'))),
          Text('$onCount ${onCount == 1 ? "on" : "on"}', style: const TextStyle(color: _teal, fontSize: 10, fontFamily: 'monospace')),
        ]),
        const SizedBox(height: 8),
        Container(padding: const EdgeInsets.symmetric(horizontal: 13),
          decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(14),
              border: Border.all(color: _border)),
          child: Column(children: children)),
      ]));
  }

  void _resetFx2() {
    HapticFeedback.mediumImpact();
    setState(() {
      _bassBoost=0; _trebleBoost=0; _subBass=0; _presence=0; _hpFreq=0; _lpFreq=20000;
      _tremolo=0; _vibrato=0; _chorus=false; _flanger=false; _phaser=false; _crusher=0;
      _haasWiden=false; _stereoFx=0; _channelMode='Stereo'; _swapLR=false;
      _noiseGate=false; _gateThresh=-50; _deEsser=0; _declip=false;
      _autoNormalize=false; _limiter=false; _limiterCeil=-1.0;
      _autoTrimSilence=false; _padStart=0; _padEnd=0;
      _fx2OpenId=null;
    });
  }

  Widget _fx2Tab() {
    final ar = LangProvider.strings(context).ar;
    final q = _fx2Search.trim().toLowerCase();
    bool vis(String en, String arLbl) => q.isEmpty || en.toLowerCase().contains(q) || arLbl.toLowerCase().contains(q);

    final onBass = _bassBoost != 0, onTreble = _trebleBoost != 0, onSub = _subBass != 0,
        onPresence = _presence != 0, onHp = _hpFreq != 0, onLp = _lpFreq < 20000;
    final onTrem = _tremolo != 0, onVib = _vibrato != 0, onCrush = _crusher != 0;
    final onStereoFx = _stereoFx != 0, onChanMode = _channelMode != 'Stereo';
    final onDeEsser = _deEsser != 0, onPadStart = _padStart != 0, onPadEnd = _padEnd != 0;

    final toneRows = <Widget>[
      if (vis('Bass Boost', 'تعزيز الجهير'))
        _rackRow(id: 'bass', label: ar ? 'تعزيز الجهير' : 'Bass Boost', on: onBass,
          valueStr: '${_bassBoost>=0?"+":""}${_bassBoost.toStringAsFixed(1)} dB',
          body: _slider(_bassBoost, -12, 12, _gold, (v) => setState(() => _bassBoost = v))),
      if (vis('Treble Boost', 'تعزيز الحدة'))
        _rackRow(id: 'treble', label: ar ? 'تعزيز الحدة' : 'Treble Boost', on: onTreble,
          valueStr: '${_trebleBoost>=0?"+":""}${_trebleBoost.toStringAsFixed(1)} dB',
          body: _slider(_trebleBoost, -12, 12, _gold, (v) => setState(() => _trebleBoost = v))),
      if (vis('Sub Bass', 'جهير فرعي'))
        _rackRow(id: 'subbass', label: ar ? 'جهير فرعي' : 'Sub Bass', on: onSub,
          valueStr: _subBass==0 ? (ar?'معطل':'Off') : '${_subBass.round()}%',
          body: _slider(_subBass, 0, 100, _gold, (v) => setState(() => _subBass = v))),
      if (vis('Presence/Clarity', 'الوضوح'))
        _rackRow(id: 'presence', label: ar ? 'الوضوح' : 'Presence/Clarity', on: onPresence,
          valueStr: _presence==0 ? (ar?'معطل':'Off') : '${_presence.round()}%',
          body: _slider(_presence, 0, 100, _gold, (v) => setState(() => _presence = v))),
      if (vis('High-Pass', 'مرشح تمرير عالي'))
        _rackRow(id: 'hp', label: ar ? 'مرشح تمرير عالي' : 'High-Pass', on: onHp,
          valueStr: _hpFreq==0 ? (ar?'معطل':'Off') : '${_hpFreq.round()} Hz',
          body: _slider(_hpFreq, 0, 500, _gold, (v) => setState(() => _hpFreq = v))),
      if (vis('Low-Pass', 'مرشح تمرير منخفض'))
        _rackRow(id: 'lp', label: ar ? 'مرشح تمرير منخفض' : 'Low-Pass', on: onLp,
          valueStr: _lpFreq>=20000 ? (ar?'معطل':'Off') : '${_lpFreq.round()} Hz',
          body: _slider(_lpFreq, 2000, 20000, _gold, (v) => setState(() => _lpFreq = v))),
    ];

    final charRows = <Widget>[
      if (vis('Tremolo', 'ترعيد'))
        _rackRow(id: 'tremolo', label: ar ? 'ترعيد (Tremolo)' : 'Tremolo', on: onTrem,
          valueStr: _tremolo==0 ? (ar?'معطل':'Off') : '${_tremolo.round()}%',
          body: _slider(_tremolo, 0, 100, _gold, (v) => setState(() => _tremolo = v))),
      if (vis('Vibrato', 'اهتزاز'))
        _rackRow(id: 'vibrato', label: ar ? 'اهتزاز (Vibrato)' : 'Vibrato', on: onVib,
          valueStr: _vibrato==0 ? (ar?'معطل':'Off') : '${_vibrato.round()}%',
          body: _slider(_vibrato, 0, 100, _gold, (v) => setState(() => _vibrato = v))),
      if (vis('Chorus', 'جوقة'))
        _rackRow(id: 'chorus', label: ar ? 'جوقة (Chorus)' : 'Chorus', on: _chorus,
          valueStr: _chorus ? (ar?'مفعّل':'On') : (ar?'معطل':'Off'),
          rightControl: _rackSwitch(_chorus, (v) => setState(() => _chorus = v))),
      if (vis('Flanger', 'فلانجر'))
        _rackRow(id: 'flanger', label: ar ? 'فلانجر (Flanger)' : 'Flanger', on: _flanger,
          valueStr: _flanger ? (ar?'مفعّل':'On') : (ar?'معطل':'Off'),
          rightControl: _rackSwitch(_flanger, (v) => setState(() => _flanger = v))),
      if (vis('Phaser', 'فايزر'))
        _rackRow(id: 'phaser', label: ar ? 'فايزر (Phaser)' : 'Phaser', on: _phaser,
          valueStr: _phaser ? (ar?'مفعّل':'On') : (ar?'معطل':'Off'),
          rightControl: _rackSwitch(_phaser, (v) => setState(() => _phaser = v))),
      if (vis('Bitcrusher', 'بت-كراشر'))
        _rackRow(id: 'crusher', label: ar ? 'بت-كراشر' : 'Bitcrusher', on: onCrush,
          valueStr: _crusher==0 ? (ar?'معطل':'Off') : '${_crusher.round()}%',
          body: _slider(_crusher, 0, 100, _gold, (v) => setState(() => _crusher = v))),
    ];

    final spaceRows = <Widget>[
      if (vis('Haas Widener', 'توسيع هاس'))
        _rackRow(id: 'haas', label: ar ? 'توسيع هاس (Haas)' : 'Haas Widener', on: _haasWiden,
          valueStr: _haasWiden ? (ar?'مفعّل':'On') : (ar?'معطل':'Off'),
          rightControl: _rackSwitch(_haasWiden, (v) => setState(() => _haasWiden = v))),
      if (vis('Stereo Enhancer', 'محسن الستيريو'))
        _rackRow(id: 'stereofx', label: ar ? 'محسّن الستيريو' : 'Stereo Enhancer', on: onStereoFx,
          valueStr: '${_stereoFx.round()}',
          body: _slider(_stereoFx, -100, 100, _gold, (v) => setState(() => _stereoFx = v))),
      if (vis('Channel Mode', 'وضع القنوات'))
        _rackRow(id: 'channelmode', label: ar ? 'وضع القنوات' : 'Channel Mode', on: onChanMode,
          valueStr: _channelMode,
          body: Wrap(spacing: 8, runSpacing: 8, children: ['Stereo','Mono','Left','Right'].map((m) {
            final sel = m == _channelMode;
            return GestureDetector(onTap: () => setState(() => _channelMode = m),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                decoration: BoxDecoration(
                  color: sel ? _goldDim.withValues(alpha: 0.4) : _surface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: sel ? _gold : _border, width: sel ? 1.5 : 1)),
                child: Text(m, style: TextStyle(color: sel ? _gold : _textB, fontSize: 11,
                    fontWeight: sel ? FontWeight.w700 : FontWeight.w400))));
          }).toList())),
      if (vis('Swap L/R', 'تبديل يمين يسار'))
        _rackRow(id: 'swaplr', label: ar ? 'تبديل يمين/يسار' : 'Swap L/R', on: _swapLR,
          valueStr: _swapLR ? (ar?'مفعّل':'On') : (ar?'معطل':'Off'),
          rightControl: _rackSwitch(_swapLR, (v) => setState(() => _swapLR = v))),
    ];

    final dynRows = <Widget>[
      if (vis('Noise Gate', 'بوابة ضوضاء'))
        _rackRow(id: 'gate', label: ar ? 'بوابة ضوضاء (Noise Gate)' : 'Noise Gate', on: _noiseGate,
          valueStr: _noiseGate ? '${_gateThresh.round()} dB' : (ar?'معطل':'Off'),
          rightControl: _rackSwitch(_noiseGate, (v) => setState(() { _noiseGate = v; if (!v) _fx2OpenId = null; })),
          body: _noiseGate ? _slider(_gateThresh, -80, -20, _gold, (v) => setState(() => _gateThresh = v)) : null),
      if (vis('De-esser', 'مزيل الصفير'))
        _rackRow(id: 'deesser', label: ar ? 'مزيل الصفير (De-esser)' : 'De-esser', on: onDeEsser,
          valueStr: _deEsser==0 ? (ar?'معطل':'Off') : '${_deEsser.round()}%',
          body: _slider(_deEsser, 0, 100, _gold, (v) => setState(() => _deEsser = v))),
      if (vis('Declip', 'إزالة التقطيع'))
        _rackRow(id: 'declip', label: ar ? 'إزالة التقطيع (Declip)' : 'Declip', on: _declip,
          valueStr: _declip ? (ar?'مفعّل':'On') : (ar?'معطل':'Off'),
          rightControl: _rackSwitch(_declip, (v) => setState(() => _declip = v))),
      if (vis('Adaptive Normalize', 'تطبيع تكيفي'))
        _rackRow(id: 'autonorm', label: ar ? 'تطبيع تكيّفي' : 'Adaptive Normalize', on: _autoNormalize,
          valueStr: _autoNormalize ? (ar?'مفعّل':'On') : (ar?'معطل':'Off'),
          rightControl: _rackSwitch(_autoNormalize, (v) => setState(() => _autoNormalize = v))),
      if (vis('Limiter', 'محدد ذروة'))
        _rackRow(id: 'limiter', label: ar ? 'محدد ذروة (Limiter)' : 'Limiter', on: _limiter,
          valueStr: _limiter ? '${_limiterCeil.toStringAsFixed(1)} dB' : (ar?'معطل':'Off'),
          rightControl: _rackSwitch(_limiter, (v) => setState(() { _limiter = v; if (!v) _fx2OpenId = null; })),
          body: _limiter ? _slider(_limiterCeil, -6, 0, _gold, (v) => setState(() => _limiterCeil = v)) : null),
      if (vis('Auto-Trim Silence', 'قص الصمت تلقائيا'))
        _rackRow(id: 'autotrim', label: ar ? 'قص الصمت تلقائيًا' : 'Auto-Trim Silence', on: _autoTrimSilence,
          valueStr: _autoTrimSilence ? (ar?'مفعّل':'On') : (ar?'معطل':'Off'),
          rightControl: _rackSwitch(_autoTrimSilence, (v) => setState(() => _autoTrimSilence = v))),
      if (vis('Pad Start', 'حشو البداية'))
        _rackRow(id: 'padstart', label: ar ? 'حشو البداية' : 'Pad Start', on: onPadStart,
          valueStr: _padStart==0 ? (ar?'معطل':'Off') : '${_padStart.toStringAsFixed(1)}s',
          body: _slider(_padStart, 0, 5, _gold, (v) => setState(() => _padStart = v))),
      if (vis('Pad End', 'حشو النهاية'))
        _rackRow(id: 'padend', label: ar ? 'حشو النهاية' : 'Pad End', on: onPadEnd,
          valueStr: _padEnd==0 ? (ar?'معطل':'Off') : '${_padEnd.toStringAsFixed(1)}s',
          body: _slider(_padEnd, 0, 5, _gold, (v) => setState(() => _padEnd = v))),
    ];

    final totalOn = [onBass,onTreble,onSub,onPresence,onHp,onLp,
        onTrem,onVib,_chorus,_flanger,_phaser,onCrush,
        _haasWiden,onStereoFx,onChanMode,_swapLR,
        _noiseGate,onDeEsser,_declip,_autoNormalize,_limiter,_autoTrimSilence,onPadStart,onPadEnd]
        .where((b) => b).length;

    return Column(children: [
      Padding(padding: const EdgeInsets.fromLTRB(14, 12, 14, 0),
        child: TextField(
          onChanged: (v) => setState(() => _fx2Search = v),
          style: const TextStyle(color: _textA, fontSize: 13),
          decoration: InputDecoration(
            hintText: ar ? 'ابحث في 24 تأثيرًا…' : 'Search 24 effects…',
            hintStyle: const TextStyle(color: _textDim, fontSize: 12),
            prefixIcon: const Icon(Icons.search_rounded, color: _textDim, size: 19),
            filled: true, fillColor: _card, isDense: true,
            contentPadding: const EdgeInsets.symmetric(vertical: 12),
            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(11),
                borderSide: const BorderSide(color: _border)),
            focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(11),
                borderSide: const BorderSide(color: _gold)),
          ))),
      Padding(padding: const EdgeInsets.fromLTRB(14, 10, 14, 0),
        child: Row(children: [
          Expanded(child: Text(
            ar ? '$totalOn تأثير مفعّل' : '$totalOn effect${totalOn == 1 ? "" : "s"} engaged',
            style: const TextStyle(color: _textB, fontSize: 11.5, fontWeight: FontWeight.w700))),
          GestureDetector(onTap: _resetFx2,
            child: Container(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(color: _surface, borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: _red.withValues(alpha: 0.4))),
              child: Text(ar ? 'إعادة ضبط' : 'Reset',
                  style: const TextStyle(color: _red, fontSize: 10.5, fontWeight: FontWeight.w700)))),
        ])),
      const SizedBox(height: 6),
      Expanded(child: ListView(padding: const EdgeInsets.fromLTRB(14, 6, 14, 20), children: [
        _rackSection(ar ? 'تشكيل النغمة' : 'Tone Shaping',
            [onBass,onTreble,onSub,onPresence,onHp,onLp].where((b) => b).length, toneRows),
        _rackSection(ar ? 'تأثيرات مميزة' : 'Character FX',
            [onTrem,onVib,_chorus,_flanger,_phaser,onCrush].where((b) => b).length, charRows),
        _rackSection(ar ? 'الستيريو والفضاء' : 'Stereo & Space',
            [_haasWiden,onStereoFx,onChanMode,_swapLR].where((b) => b).length, spaceRows),
        _rackSection(ar ? 'تنظيف وديناميكية' : 'Cleanup & Dynamics',
            [_noiseGate,onDeEsser,_declip,_autoNormalize,_limiter,_autoTrimSilence,onPadStart,onPadEnd]
                .where((b) => b).length, dynRows),
        _card_(ar ? 'الإعدادات المسبقة' : 'Presets', Icons.bookmark_rounded, [
          Row(children: [
            Expanded(child: GestureDetector(onTap: _saveFxPreset,
              child: Container(padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(color: _tealDk, borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: _teal.withValues(alpha: 0.4))),
                child: Center(child: Text(ar ? 'حفظ' : 'Save', style: const TextStyle(
                    color: _teal, fontSize: 13, fontWeight: FontWeight.w700)))))),
            const SizedBox(width: 10),
            Expanded(child: GestureDetector(onTap: _loadFxPresetSheet,
              child: Container(padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: _border)),
                child: Center(child: Text(ar ? 'تحميل' : 'Load', style: const TextStyle(
                    color: _textA, fontSize: 13, fontWeight: FontWeight.w700)))))),
          ]),
        ]),
      ])),
    ]);
  }

  // ── S229: FX+ presets — saved as JSON in the app documents dir ───────────
  Future<File> _presetsFile() async {
    final dir = await getApplicationDocumentsDirectory();
    return File('${dir.path}/tilawa_fx_presets.json');
  }

  Map<String, dynamic> _currentFxSnapshot() => {
    'bassBoost': _bassBoost, 'trebleBoost': _trebleBoost, 'subBass': _subBass,
    'presence': _presence, 'hpFreq': _hpFreq, 'lpFreq': _lpFreq,
    'tremolo': _tremolo, 'vibrato': _vibrato, 'chorus': _chorus, 'flanger': _flanger,
    'phaser': _phaser, 'crusher': _crusher, 'haasWiden': _haasWiden, 'stereoFx': _stereoFx,
    'channelMode': _channelMode, 'swapLR': _swapLR, 'noiseGate': _noiseGate,
    'gateThresh': _gateThresh, 'deEsser': _deEsser, 'declip': _declip,
    'autoNormalize': _autoNormalize, 'limiter': _limiter, 'limiterCeil': _limiterCeil,
    'autoTrimSilence': _autoTrimSilence, 'padStart': _padStart, 'padEnd': _padEnd,
  };

  void _applyFxSnapshot(Map<String, dynamic> m) {
    setState(() {
      _bassBoost = (m['bassBoost'] ?? 0).toDouble();
      _trebleBoost = (m['trebleBoost'] ?? 0).toDouble();
      _subBass = (m['subBass'] ?? 0).toDouble();
      _presence = (m['presence'] ?? 0).toDouble();
      _hpFreq = (m['hpFreq'] ?? 0).toDouble();
      _lpFreq = (m['lpFreq'] ?? 20000).toDouble();
      _tremolo = (m['tremolo'] ?? 0).toDouble();
      _vibrato = (m['vibrato'] ?? 0).toDouble();
      _chorus = m['chorus'] ?? false;
      _flanger = m['flanger'] ?? false;
      _phaser = m['phaser'] ?? false;
      _crusher = (m['crusher'] ?? 0).toDouble();
      _haasWiden = m['haasWiden'] ?? false;
      _stereoFx = (m['stereoFx'] ?? 0).toDouble();
      _channelMode = m['channelMode'] ?? 'Stereo';
      _swapLR = m['swapLR'] ?? false;
      _noiseGate = m['noiseGate'] ?? false;
      _gateThresh = (m['gateThresh'] ?? -50).toDouble();
      _deEsser = (m['deEsser'] ?? 0).toDouble();
      _declip = m['declip'] ?? false;
      _autoNormalize = m['autoNormalize'] ?? false;
      _limiter = m['limiter'] ?? false;
      _limiterCeil = (m['limiterCeil'] ?? -1.0).toDouble();
      _autoTrimSilence = m['autoTrimSilence'] ?? false;
      _padStart = (m['padStart'] ?? 0).toDouble();
      _padEnd = (m['padEnd'] ?? 0).toDouble();
    });
  }

  Future<void> _saveFxPreset() async {
    final ar = LangProvider.strings(context).ar;
    final ctrl = TextEditingController();
    final name = await showDialog<String>(context: context, builder: (_) => AlertDialog(
      backgroundColor: _card,
      title: Text(ar ? 'اسم الإعداد' : 'Preset Name', style: const TextStyle(color: _textA)),
      content: TextField(controller: ctrl, autofocus: true,
          style: const TextStyle(color: _textA),
          decoration: const InputDecoration(hintText: 'My Preset', hintStyle: TextStyle(color: _textDim))),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(ar ? 'إلغاء' : 'Cancel')),
        TextButton(onPressed: () => Navigator.pop(context, ctrl.text.trim()), child: Text(ar ? 'حفظ' : 'Save')),
      ]));
    if (name == null || name.isEmpty) return;
    try {
      final f = await _presetsFile();
      Map<String, dynamic> all = {};
      if (await f.exists()) {
        try { all = Map<String, dynamic>.from(jsonDecode(await f.readAsString())); } catch (_) {}
      }
      all[name] = _currentFxSnapshot();
      await f.writeAsString(jsonEncode(all));
      _snack('✓ ${ar ? "تم حفظ" : "Saved"} "$name"');
    } catch (e) { _snack('Error: $e', color: _red); }
  }

  Future<void> _loadFxPresetSheet() async {
    final ar = LangProvider.strings(context).ar;
    try {
      final f = await _presetsFile();
      if (!await f.exists()) { _snack(ar ? 'لا توجد إعدادات محفوظة' : 'No saved presets yet'); return; }
      final all = Map<String, dynamic>.from(jsonDecode(await f.readAsString()));
      if (all.isEmpty) { _snack(ar ? 'لا توجد إعدادات محفوظة' : 'No saved presets yet'); return; }
      if (!mounted) return;
      await showModalBottomSheet(context: context, backgroundColor: _surface,
        builder: (_) => SafeArea(child: ListView(shrinkWrap: true,
          children: all.keys.map((k) => ListTile(
            title: Text(k, style: const TextStyle(color: _textA)),
            leading: const Icon(Icons.bookmark_rounded, color: _gold),
            trailing: IconButton(icon: const Icon(Icons.delete_outline_rounded, color: _red),
              onPressed: () async {
                all.remove(k); await f.writeAsString(jsonEncode(all));
                if (mounted) Navigator.pop(context);
              }),
            onTap: () {
              _applyFxSnapshot(Map<String, dynamic>.from(all[k]));
              Navigator.pop(context);
              _snack('✓ ${ar ? "تم تطبيق" : "Applied"} "$k"');
            })).toList())));
    } catch (e) { _snack('Error: $e', color: _red); }
  }

  // ── S229: BATCH EXPORT — apply current FX/format settings to N more files ─
  Future<void> _batchExport() async {
    final ar = LangProvider.strings(context).ar;
    if (!await _checkSetup()) return;
    final r = await FilePicker.platform.pickFiles(type: FileType.audio, allowMultiple: true);
    if (r == null || r.files.isEmpty) return;
    final paths = r.files.where((f) => f.path != null).map((f) => f.path!).toList();
    if (paths.isEmpty) return;
    setState(() { _busy = true; _busyLabel = ar ? 'تصدير دفعي…' : 'Batch exporting…'; _pct = 0; });
    int done = 0, failed = 0;
    for (final p in paths) {
      try {
        final inp = await _safeInput(p);
        final ext = _fmt.toLowerCase();
        final base = p.split('/').last.replaceAll(RegExp(r'\.[^.]+$'), '');
        final dir = await getExternalStorageDirectory() ?? await getApplicationDocumentsDirectory();
        final out = '${dir.path}/tilawa_${base}_batch.$ext';
        final af = _buildAf();
        final cmd = 'ffmpeg -y -i "$inp" '
            '-af ${af.isEmpty ? "anull" : af.join(",")} ${_metaArgs()} '
            '-ar $_sampleRate -ac ${_channels == "Mono" ? 1 : 2} '
            '-acodec ${_codec()} ${_br()} "$out"';
        final res = await _proot(cmd, inp, out, timeout: 15);
        if ((res?['rc'] as int? ?? 1) != 0) { failed++; } else { done++; }
      } catch (_) { failed++; }
      setState(() => _pct = (done + failed) / paths.length);
    }
    setState(() => _busy = false);
    _snack('✓ ${ar ? "تم" : "Done"}: $done${failed > 0 ? "  ·  ${ar ? "فشل" : "failed"}: $failed" : ""}');
  }
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

  // S227 BUG FIX: this used to be `values != o.values`. _eq is a `final`
  // List<double> that every slider/preset mutates IN PLACE, so the old and
  // new _EqPainter always pointed at the exact same list object — List has
  // no `==` override, so `!=` fell back to reference identity, which is
  // never true for the same object. shouldRepaint() therefore always
  // returned false and the EQ curve graph never redrew when a slider moved
  // or a preset was tapped. Compare contents instead of identity.
  @override bool shouldRepaint(_EqPainter o) {
    if (o.values.length != values.length) return true;
    for (int i = 0; i < values.length; i++) {
      if (o.values[i] != values[i]) return true;
    }
    return false;
  }
}
