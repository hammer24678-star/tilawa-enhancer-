// audio_editor_screen.dart — S203b: AudioLab features, Sacred Cosmos theme
// S228: Studio Engine — numpy/scipy general-purpose DSP (separate from the
// الصفاء/الإتقان restoration engines) with real parametric EQ, spectral noise
// reduction, declick, convolution reverb, phase-vocoder pitch/tempo, and
// LUFS-ish loudness normalize + true-peak limiting. Falls back to the plain
// ffmpeg filter chain below if the Studio Engine is unavailable/fails.
// S236: Studio Engine v2 — ALL 24 FX+ effects now run natively in numpy/scipy
// (previously they only existed in the ffmpeg fallback and were silently
// dropped whenever the engine succeeded), plus a numpy `--analyze` mode that
// powers a REAL waveform (peak + RMS layers, morph-animated in), loudness
// stats (peak/RMS dBFS, LUFS, clipping) and a 30-band spectrum analyzer.
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
import 'package:shared_preferences/shared_preferences.dart';  // S237: persist editor prefs
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

enum _Tab { trim, eq, effects, fx2, studio, loudness, merge, export_ }

class AudioEditorScreen extends StatefulWidget {
  const AudioEditorScreen({super.key});
  @override State<AudioEditorScreen> createState() => _AudioEditorScreenState();
}

class _AudioEditorScreenState extends State<AudioEditorScreen>
    with TickerProviderStateMixin {

  String? _filePath;
  String  _fileName = '';
  double  _durationSec = 0;
  bool    _loopEnabled = false;  // S244 — moved off the transport row's fixed-width chain

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

  // S238 — voice/recitation tools (halal-focused: voice only, no music FX)
  bool   _dehumOn       = false;
  int    _dehumBase     = 50;     // 50 Hz (most regions) / 60 Hz (Americas)
  double _dehumStrength = 60;     // 0-100
  double _vocalIso      = 0;      // 0-100 — center/voice-band focus

  // S238 — split-by-silence (Trim tab)
  double _silThresh = -40;        // dB
  double _silMin    = 0.6;        // seconds of pause that counts as a cut point

  // S238 — A/B: remembers where the last Studio preview started
  double _lastPreviewStart = 0;

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
  DateTime? _busyStart;  // S237: elapsed time shown in the processing overlay

  _Tab _tab = _Tab.trim;
  late AnimationController _waveCtrl;
  late AnimationController _glowCtrl;
  late List<double> _bars;

  // S236 — real waveform analysis (numpy --analyze) state
  List<double>? _rmsBars;              // real RMS layer under the peak bars
  List<double> _spectrum = const [];   // 30-band average spectrum, 0..1
  double? _statPeakDb, _statRmsDb, _statLufs, _statClipPct, _statLra, _statTruePeakDb;
  bool _analyzed  = false;             // bars are the real waveform, not placeholder
  bool _analyzing = false;
  int  _analyzeToken = 0;              // discards stale results after file change
  late AnimationController _barMorphCtrl;
  List<double>  _barsFrom = const [], _barsTo = const [];
  List<double>? _rmsTo;
  static const int _kBars = 96;        // must match _WAVE_BUCKETS in the py engine

  static const _ch    = MethodChannel('com.tilawa.tilawa_enhancer/local_engine');
  static const _media = MethodChannel('com.tilawa.tilawa_enhancer/media');

  @override
  void initState() {
    super.initState();
    final rng = Random(42);
    _bars = List.generate(_kBars, (_) => 0.1 + rng.nextDouble() * 0.9);
    _waveCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 3))..repeat();
    _glowCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 2))..repeat(reverse: true);
    // S236 — morphs the placeholder bars into the real analyzed waveform
    _barMorphCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 800))
      ..addListener(() {
        if (_barsTo.isEmpty) return;
        final t = Curves.easeOutCubic.transform(_barMorphCtrl.value);
        setState(() {
          _bars = List.generate(_barsTo.length, (i) {
            final f = i < _barsFrom.length ? _barsFrom[i] : 0.0;
            return f + (_barsTo[i] - f) * t;
          });
          final rt = _rmsTo;
          if (rt != null) _rmsBars = List.generate(rt.length, (i) => rt[i] * t);
        });
      });
    _stateSub = _player.onPlayerStateChanged.listen((s) {
      if (mounted) setState(() => _playing = s == PlayerState.playing);
    });
    _posSub = _player.onPositionChanged.listen((d) {
      if (mounted) setState(() => _positionSec = d.inMilliseconds / 1000.0);
    });
    _durSub = _player.onDurationChanged.listen((d) {
      if (mounted) setState(() => _durationSec = d.inMilliseconds / 1000.0);
    });
    _loadEditorPrefs();  // S237 QoL — restore last-used export/studio settings
  }

  @override
  void dispose() {
    _stateSub?.cancel(); _posSub?.cancel(); _durSub?.cancel();
    _player.dispose(); _waveCtrl.dispose(); _glowCtrl.dispose();
    _barMorphCtrl.dispose();
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
      // S236 — invalidate any previous file's analysis
      _analyzed = false; _analyzing = false; _rmsBars = null; _spectrum = const [];
      _statPeakDb = null; _statRmsDb = null; _statLufs = null; _statClipPct = null;
      _statLra = null; _statTruePeakDb = null;
      final rng = Random(f.name.hashCode);
      _bars = List.generate(_kBars, (_) => 0.1 + rng.nextDouble() * 0.9);
    });
    await _player.setSource(DeviceFileSource(f.path!));
    unawaited(_analyzeAudio());
  }

  // ── S236: REAL WAVEFORM — numpy --analyze ─────────────────────────────────
  // Best-effort: runs right after picking a file, quietly leaves the animated
  // placeholder bars in place if the local engine isn't set up or fails. The
  // engine writes JSON to a file (proot stdout is truncated to 800 chars).
  Future<void> _analyzeAudio() async {
    final token = ++_analyzeToken;
    final path = _filePath;
    if (path == null) return;
    try {
      final ok = await _ch.invokeMethod<bool>('isBasicSetupComplete') ?? false;
      if (!ok || !mounted) return;
      setState(() => _analyzing = true);
      final inp = await _safeInput(path);
      final tmp = await getTemporaryDirectory();
      final outJson = '${tmp.path}/tl_analysis_${DateTime.now().millisecondsSinceEpoch}.json';
      final script = await _ensureDspScript();
      final r = await _proot('python3 "$script" --analyze "$inp" "$outJson"',
          inp, outJson, timeout: 5);
      if (token != _analyzeToken || !mounted) return;
      if ((r?['rc'] as int? ?? 1) != 0 || !File(outJson).existsSync()) return;
      final m = Map<String, dynamic>.from(jsonDecode(await File(outJson).readAsString()));
      try { File(outJson).deleteSync(); } catch (_) {}
      if (m['ok'] != true) return;
      final peaks = ((m['peaks'] as List?) ?? const [])
          .map((e) => ((e as num).toDouble()).clamp(0.04, 1.0)).cast<double>().toList();
      final rms = (m['rms'] as List?)
          ?.map((e) => (e as num).toDouble().clamp(0.0, 1.0)).cast<double>().toList();
      if (peaks.isEmpty || token != _analyzeToken || !mounted) return;
      setState(() {
        _analyzed = true;
        _spectrum = ((m['spectrum'] as List?) ?? const [])
            .map((e) => (e as num).toDouble()).cast<double>().toList();
        _statPeakDb  = (m['peak_db']  as num?)?.toDouble();
        _statRmsDb   = (m['rms_db']   as num?)?.toDouble();
        _statLufs    = (m['lufs']     as num?)?.toDouble();
        _statClipPct = (m['clip_pct'] as num?)?.toDouble();
        _statLra        = (m['lra']          as num?)?.toDouble();  // S245
        _statTruePeakDb = (m['true_peak_db'] as num?)?.toDouble();  // S245
        final d = (m['duration_sec'] as num?)?.toDouble() ?? 0;
        if (_durationSec == 0 && d > 0) _durationSec = d;
        _barsFrom = List.of(_bars);
        _barsTo   = peaks;
        _rmsTo    = rms;
      });
      _barMorphCtrl.forward(from: 0);
    } catch (_) {
      // analysis is a bonus — the editor stays fully usable without it
    } finally {
      if (mounted && token == _analyzeToken) setState(() => _analyzing = false);
    }
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

  // S237 QoL — export & studio settings persist across sessions. Only chip/
  // slider-backed state is saved (metadata TextFields have no controllers, so
  // restored text would be invisible in the UI — deliberately not persisted).
  static const _prefsKey = 'audio_editor_prefs_v1';

  Future<void> _loadEditorPrefs() async {
    try {
      final p = await SharedPreferences.getInstance();
      final raw = p.getString(_prefsKey);
      if (raw == null || !mounted) return;
      final m = Map<String, dynamic>.from(jsonDecode(raw));
      setState(() {
        _fmt            = (m['fmt'] as String?) ?? _fmt;
        _kbps           = (m['kbps'] as num?)?.toInt() ?? _kbps;
        _sampleRate     = (m['sampleRate'] as num?)?.toInt() ?? _sampleRate;
        _channels       = (m['channels'] as String?) ?? _channels;
        _wavBitDepth    = (m['wavBitDepth'] as num?)?.toInt() ?? _wavBitDepth;
        _loudnessTarget = (m['loudnessTarget'] as String?) ?? _loudnessTarget;
        _truePeakLimiter = (m['truePeakLimiter'] as bool?) ?? _truePeakLimiter;
        _fadeCurve      = (m['fadeCurve'] as String?) ?? _fadeCurve;
        _eqQ            = (m['eqQ'] as num?)?.toDouble() ?? _eqQ;
        _reverbType     = (m['reverbType'] as String?) ?? _reverbType;
      });
    } catch (_) {}
  }

  Future<void> _saveEditorPrefs() async {
    try {
      final p = await SharedPreferences.getInstance();
      await p.setString(_prefsKey, jsonEncode({
        'fmt': _fmt, 'kbps': _kbps, 'sampleRate': _sampleRate,
        'channels': _channels, 'wavBitDepth': _wavBitDepth,
        'loudnessTarget': _loudnessTarget, 'truePeakLimiter': _truePeakLimiter,
        'fadeCurve': _fadeCurve, 'eqQ': _eqQ, 'reverbType': _reverbType,
      }));
    } catch (_) {}
  }

  // S237 QoL — jump the playhead by ±N seconds from the transport bar
  Future<void> _seekBy(double deltaSec) async {
    if (_filePath == null || _durationSec <= 0) return;
    HapticFeedback.selectionClick();
    final target = (_positionSec + deltaSec).clamp(0.0, _durationSec);
    await _player.seek(Duration(milliseconds: (target * 1000).round()));
    if (mounted) setState(() => _positionSec = target);
  }

  // ── SPLIT ─────────────────────────────────────────────────────────────────
  Future<void> _split() async {
    if (_filePath == null) return;
    if (!await _checkSetup()) return;
    HapticFeedback.mediumImpact();
    setState(() { _busy = true; _busyStart = DateTime.now(); _busyLabel = 'Splitting…'; _pct = 0.1; });
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

  // ── S238: SPLIT BY SILENCE — cut a recitation into pieces at the pauses ──
  // Runs the Studio Engine's --split mode: detects pauses longer than
  // _silMin below _silThresh dB and writes one file per spoken segment —
  // made for cutting a long recitation into ayah-sized files.
  Future<void> _splitBySilence() async {
    if (_filePath == null || _busy) return;
    if (!await _checkSetup()) return;
    HapticFeedback.mediumImpact();
    final ar = LangProvider.strings(context).ar;
    setState(() { _busy = true; _busyStart = DateTime.now();
      _busyLabel = ar ? 'تقسيم عند السكتات…' : 'Splitting at pauses…'; _pct = 0.1; });
    try {
      final inp    = await _safeInput(_filePath!);
      final script = await _ensureDspScript();
      final tmp    = await getTemporaryDirectory();
      final dir    = await getExternalStorageDirectory() ?? await getApplicationDocumentsDirectory();
      final base   = _fileName.replaceAll(RegExp(r'\.[^.]+$'), '');
      final outBase = '${dir.path}/tilawa_${base}_part';
      final paramsFile = File('${tmp.path}/tl_split_${DateTime.now().millisecondsSinceEpoch}.json');
      await paramsFile.writeAsString(jsonEncode({
        'silence_db': _silThresh, 'min_silence_s': _silMin, 'min_seg_s': 1.0,
        'output': {'format': _fmt, 'kbps': _kbps, 'sample_rate': _sampleRate,
                   'channels': _channels, 'wav_bit_depth': _wavBitDepth,
                   'metadata': {'title': _metaTitle, 'artist': _metaArtist, 'album': _metaAlbum}},
      }));
      final report = '${outBase}_report.json';
      setState(() => _pct = 0.3);
      final r = await _proot(
          'python3 "$script" --split "$inp" "$outBase" "${paramsFile.path}"',
          inp, report, timeout: 20);
      try { await paramsFile.delete(); } catch (_) {}
      final rc = (r?['rc'] as int?) ?? -1;
      if (rc != 0 || !File(report).existsSync()) {
        throw Exception(r?['out'] ?? 'split failed');
      }
      final rep = Map<String, dynamic>.from(jsonDecode(await File(report).readAsString()));
      final count = (rep['count'] as num?)?.toInt() ?? 0;
      if (!mounted) return;
      setState(() { _pct = 1.0; _busy = false; });
      _snack('✓ ${ar ? "تم التقسيم إلى" : "Split into"} $count ${ar ? "مقطعًا في" : "parts in"} ${dir.path}');
    } catch (e) {
      if (mounted) setState(() => _busy = false);
      _snack('Error: $e', color: _red);
    }
  }

  // ── MERGE ─────────────────────────────────────────────────────────────────
  Future<void> _merge() async {
    if (_filePath == null || _mergePath == null) return;
    if (!await _checkSetup()) return;
    HapticFeedback.mediumImpact();
    setState(() { _busy = true; _busyStart = DateTime.now(); _busyLabel = 'Merging…'; _pct = 0.1; });
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
    // S238 — de-hum fallback: notch the mains frequency + 4 harmonics
    if (_dehumOn) {
      final w = (2 + _dehumStrength / 100 * 6).toStringAsFixed(1);
      for (int k = 1; k <= 5; k++) {
        af.add('bandreject=f=${_dehumBase * k}:width_type=h:w=$w');
      }
    }
    // S238 — vocal isolate fallback: pull the side channel down + voice-band lift
    if (_vocalIso > 0) {
      final slev = (1 - 0.85 * _vocalIso / 100).toStringAsFixed(2);
      af.add('stereotools=slev=$slev');
      af.add('equalizer=f=1800:g=${(_vocalIso / 100 * 3).toStringAsFixed(1)}');
    }
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
    final dst  = File('${dir.path}/tilawa_dsp_studio_v3.py');  // S245: v3 — busts any cached v2 copy (real loudness algorithm)
    final data = await rootBundle.load('assets/dsp/tilawa_dsp_studio.py');
    await dst.writeAsBytes(data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes), flush: true);
    _dspScriptPath = dst.path;
    return dst.path;
  }

  Map<String, dynamic> _buildDspParams({double? previewStart, double? previewDur,
      bool fullFile = false}) {
    final isPreview = previewStart != null;
    // S236: batch export processes each picked file in full — the trim window
    // belongs to the currently loaded file only.
    final ss  = fullFile ? 0.0 : isPreview ? previewStart! : (_trimStart * _durationSec);
    final dur = fullFile ? 0.0 : isPreview ? (previewDur ?? 0) : ((_trimEnd - _trimStart) * _durationSec);
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
      // S236 — the Studio Engine now implements ALL of these natively in
      // numpy/scipy (see tilawa_dsp_studio.py fx2 stages); _buildAf() keeps
      // its ffmpeg equivalents purely as the fallback path.
      'fx2': {
        'bass_db': _bassBoost, 'treble_db': _trebleBoost, 'sub_bass': _subBass,
        'presence': _presence, 'highpass_hz': _hpFreq, 'lowpass_hz': _lpFreq,
        'tremolo': _tremolo, 'vibrato': _vibrato, 'chorus': _chorus,
        'flanger': _flanger, 'phaser': _phaser, 'bitcrush': _crusher,
        'haas_widen': _haasWiden, 'stereo_fx': _stereoFx,
        'channel_mode': _channelMode, 'swap_lr': _swapLR,
        'noise_gate': {'enabled': _noiseGate, 'threshold_db': _gateThresh},
        // S238 — voice tools
        'dehum': {'enabled': _dehumOn, 'base_hz': _dehumBase, 'strength': _dehumStrength},
        'vocal_isolate': _vocalIso,
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

  // S238 QoL — A/B: hear the untouched original from the same spot the last
  // Studio preview started, so processed vs. original is a two-tap compare.
  Future<void> _playOriginalSlice() async {
    if (_filePath == null) return;
    HapticFeedback.selectionClick();
    final ar = LangProvider.strings(context).ar;
    if (_playing) await _player.stop();
    await _player.setSource(DeviceFileSource(_filePath!));
    await _player.seek(Duration(milliseconds: (_lastPreviewStart * 1000).round()));
    await _player.resume();
    _snack(ar ? '▶ الأصلي (بدون معالجة)' : '▶ Original (unprocessed)', color: _gold);
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
      _lastPreviewStart = start;  // S238 — A/B jumps back to the same spot
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
    setState(() { _busy = true; _busyStart = DateTime.now(); _pct = 0.05; _outPath = null; _busyLabel = 'Exporting…'; });
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
      unawaited(_saveEditorPrefs());  // S237 QoL — remember these export settings
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
          // S237 QoL — elapsed time (this AnimatedBuilder already ticks with _glowCtrl)
          if (_busyStart != null) ...[const SizedBox(height: 6),
            Builder(builder: (_) {
              final e = DateTime.now().difference(_busyStart!);
              final mm = e.inMinutes.toString().padLeft(2, '0');
              final ss = (e.inSeconds % 60).toString().padLeft(2, '0');
              return Text('$mm:$ss', style: const TextStyle(
                  color: _textDim, fontSize: 11, fontFamily: 'monospace'));
            })],
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
            ? '• موجة حقيقية: يقرأ numpy الملف ويرسم موجته الفعلية (قمة + RMS) مع إحصاءات Peak/RMS/LUFS.\n'
              '• طيف ترددي: محلل ٣٠ نطاقًا في تبويب الموازن يوضح أين تتركز طاقة الملف.\n'
              '• قص: حدد نطاق البداية والنهاية.\n'
              '• تقسيم: اضغط ✂️ في التشغيل لتقسيم الملف عند الموضع الحالي.\n'
              '• تقسيم عند السكتات: يفصل التلاوة تلقائيًا إلى مقاطع (آيات) عند السكتات.\n'
              '• أدوات صوت القارئ: إزالة طنين الكهرباء (50/60 هرتز) وعزل صوت القارئ عن الخلفية.\n'
              '• تحسين صوتي سريع: سلاسل جاهزة بضغطة واحدة (تلاوة نقية، رسالة صوتية، إصلاح تسجيل قديم).\n'
              '• موازن 10 أحزمة: موازن معلمي حقيقي (numpy/scipy) بدقة Q قابلة للضبط.\n'
              '• تأثيرات: تلاشي، طبقة صوت، سرعة، صدى، إرجاع، عكس، تقليص ضوضاء طيفي، ضغط.\n'
              '• FX+‏: ٢٦ تأثيرًا تعمل كلها داخل محرك numpy/scipy مباشرة.\n'
              '• استوديو: إزالة طقطقة، نوع الصدى، ديناميكية الضاغط، تطبيع الصوت LUFS.\n'
              '• التوافق: قياس جهارة حقيقي (LUFS/LRA/Peak) وفق ITU-R BS.1770-4 (pyloudnorm) '
              'مع قائمة توافق لمنصات النشر الشهيرة.\n'
              '• معاينة: استمع لـ٨ ثوانٍ بالإعدادات الحالية قبل التصدير الكامل.\n'
              '• دمج: جمع ملفين صوتيين. تصدير دفعي بمحرك الاستوديو.\n'
              '• تصدير: MP3/WAV/M4A + معدل عينة/قنوات/عمق بت + بيانات وصفية + نغمة رنين.\n'
              '⚙️ محلي بالكامل — محرك الاستوديو (numpy/scipy) مع رجوع تلقائي لـ ffmpeg — بدون إنترنت.'
            : '• Real waveform: numpy reads your file and draws its actual wave (peak + RMS) with Peak/RMS/LUFS stats.\n'
              '• Spectrum: a 30-band analyzer in the EQ tab shows where the file\'s energy lives.\n'
              '• Trim: set start/end range.\n'
              '• Split: tap ✂️ in transport to split at playhead into two files.\n'
              '• Split by Silence: auto-cuts a recitation into ayah-sized parts at the pauses.\n'
              '• Voice tools: mains-hum removal (50/60 Hz) and reciter-voice isolation.\n'
              '• Quick Voice Enhance: one-tap chains (Recitation Clean, Voice Note, Old Tape Repair).\n'
              '• 10-band EQ: real parametric EQ (numpy/scipy) with adjustable Q.\n'
              '• Effects: fade, pitch, speed, echo, reverb, reverse, spectral noise reduction, compressor.\n'
              '• FX+: all 26 effects run natively inside the numpy/scipy engine.\n'
              '• Studio: declick, reverb type, compressor dynamics, LUFS loudness normalize.\n'
              '• Compliance: real ITU-R BS.1770-4 loudness measurement (LUFS/LRA/True Peak, '
              'via a vendored pyloudnorm) checked against major publishing platform targets.\n'
              '• Preview: audition 8s with your current settings before a full export.\n'
              '• Merge: join two audio files. Batch export runs the Studio Engine too.\n'
              '• Export: MP3/WAV/M4A + sample rate/channels/bit depth + metadata + ringtone.\n'
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
        // S238 QoL — A/B: replay the raw original from the same spot
        GestureDetector(
          onTap: _dspBusy ? null : _playOriginalSlice,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 7),
            decoration: BoxDecoration(
              color: _goldDim.withValues(alpha: 0.35),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _gold.withValues(alpha: 0.45)),
            ),
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.compare_arrows_rounded, color: _gold, size: 14),
              const SizedBox(width: 5),
              Text(ar ? 'أصلي' : 'A/B',
                  style: const TextStyle(color: _gold, fontSize: 12, fontWeight: FontWeight.w700)),
            ]),
          ),
        ),
        const SizedBox(width: 8),
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
    final ar = LangProvider.strings(context).ar;
    final pos = _durationSec > 0 ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0.0;
    return Container(
      margin: const EdgeInsets.fromLTRB(10, 8, 10, 4),
      padding: const EdgeInsets.symmetric(vertical: 6),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _border),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.22),
              blurRadius: 12, offset: const Offset(0, 5))]),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        ClipRRect(borderRadius: BorderRadius.circular(10),
          // S243: seek used context.findRenderObject() — that's the WHOLE
          // screen's box, not the waveform's, so the tap fraction was scaled by
          // screen width and offset by the card margins (seek landed off). Use
          // the waveform's own width via LayoutBuilder. The wave is drawn
          // left→right in raw canvas coords (not mirrored), so this stays
          // correct in RTL too.
          child: LayoutBuilder(builder: (ctx, cons) => GestureDetector(
            onTapDown: (d) {
              final w = cons.maxWidth;
              if (w <= 0 || _durationSec <= 0) return;
              final frac = (d.localPosition.dx / w).clamp(0.0, 1.0);
              _player.seek(Duration(milliseconds: (frac * _durationSec * 1000).round()));
              setState(() => _positionSec = frac * _durationSec);
            },
            child: AnimatedBuilder(animation: _waveCtrl,
              builder: (_, __) => SizedBox(height: 92,
                child: CustomPaint(
                  painter: _WavePainter(bars: _bars, rms: _rmsBars, playPos: pos,
                    trimStart: _trimStart, trimEnd: _trimEnd,
                    animT: _waveCtrl.value, playing: _playing, analyzed: _analyzed),
                  size: const Size(double.infinity, 92))))))),
        // S236 — analysis status + real loudness stats under the waveform
        if (_analyzing || _analyzed)
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 5, 12, 1),
            child: Row(children: [
              if (_analyzing) ...[
                const SizedBox(width: 9, height: 9,
                  child: CircularProgressIndicator(strokeWidth: 1.5, color: _teal)),
                const SizedBox(width: 6),
                Text(ar ? 'قراءة الموجة الحقيقية…' : 'Reading real waveform…',
                    style: const TextStyle(color: _textDim, fontSize: 9.5)),
              ] else ...[
                const Icon(Icons.verified_rounded, color: _teal, size: 11),
                const SizedBox(width: 4),
                Text(ar ? 'موجة حقيقية' : 'Real waveform',
                    style: const TextStyle(color: _teal, fontSize: 9.5, fontWeight: FontWeight.w700)),
              ],
              const Spacer(),
              if (_statPeakDb != null)
                _waveStat('Peak', '${_statPeakDb!.toStringAsFixed(1)}dB'),
              if (_statRmsDb != null)
                _waveStat('RMS', '${_statRmsDb!.toStringAsFixed(1)}dB'),
              if (_statLufs != null)
                _waveStat('LUFS', _statLufs!.toStringAsFixed(1)),
              if ((_statClipPct ?? 0) > 0.5)
                _waveStat('Clip', '${_statClipPct!.toStringAsFixed(1)}%', color: _red),
            ])),
      ]));
  }

  Widget _waveStat(String label, String value, {Color color = _textB}) =>
    Padding(padding: const EdgeInsetsDirectional.only(start: 8),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text('$label ', style: const TextStyle(color: _textDim, fontSize: 9)),
        Text(value, style: TextStyle(color: color, fontSize: 9.5,
            fontWeight: FontWeight.w700, fontFamily: 'monospace')),
      ]));

  // S244 FIX: this row previously packed 7 fixed-width circular buttons (prev,
  // -10s, play, +10s, stop, split, loop) plus a flexible time/progress column
  // into one Row. Verified with a real Flutter render (flutter_tester, not a
  // guess): it overflowed by 135px on a common 412-wide phone — "RenderFlex
  // overflowed by 135 pixels on the right." In a release build that overflow
  // is clipped silently (no debug hazard stripes), so the trailing controls
  // rendered completely off-screen: invisible AND untappable.
  // Fix: the loop toggle moved out of the fixed-width chain entirely (see
  // below), and the remaining button cluster is wrapped in
  // Flexible+FittedBox(scaleDown) — this makes overflow structurally
  // impossible: FittedBox measures its child then scales it to fit whatever
  // space is actually available, so no combination of screen width, system
  // font scale, or locale can ever push content off-screen. On any normal
  // phone the buttons render at their natural size; only on a genuinely
  // cramped layout do they shrink slightly as a group — they never clip.
  Widget _transport() => Container(
    color: _surface,
    padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 10),
    child: Row(children: [
      Flexible(
        child: FittedBox(
          fit: BoxFit.scaleDown,
          alignment: AlignmentDirectional.centerStart,
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            _tBtn(Icons.skip_previous_rounded, () async {
              await _player.seek(Duration(milliseconds: (_trimStart * _durationSec * 1000).round()));
              if (mounted) setState(() => _positionSec = _trimStart * _durationSec);
            }),
            const SizedBox(width: 4),
            _tBtn(Icons.replay_10_rounded, () => _seekBy(-10)),  // S237 QoL
            const SizedBox(width: 4),
            AnimatedBuilder(animation: _glowCtrl,
              builder: (_, __) => GestureDetector(
                onTap: () { HapticFeedback.mediumImpact(); _togglePlay(); },
                child: AnimatedScale(duration: const Duration(milliseconds: 200),
                  scale: _playing ? 1.06 : 1.0,
                  child: Container(width: 50, height: 50,
                    decoration: BoxDecoration(shape: BoxShape.circle,
                      gradient: const RadialGradient(colors: [Color(0xFFB8921E), _goldDim]),
                      boxShadow: [BoxShadow(
                          color: _gold.withValues(alpha: _playing ? 0.2 + 0.22 * _glowCtrl.value : 0.08),
                          blurRadius: 20)]),
                    child: Icon(_playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
                      color: const Color(0xFF050A06), size: 26))))),
            const SizedBox(width: 4),
            _tBtn(Icons.forward_10_rounded, () => _seekBy(10)),  // S237 QoL
            const SizedBox(width: 4),
            _tBtn(Icons.stop_rounded, _stop),
            const SizedBox(width: 4),
            Tooltip(message: 'Split at playhead',
              child: _tBtn(Icons.content_cut_rounded, _split, color: _teal)),
            const SizedBox(width: 4),
            // S244 v2: loop back here (in the overflow-proof FittedBox cluster)
            // — round 1 of this fix put it in the "flexible" time column
            // instead, paired with a bare Spacer(); Spacer defaults to flex:1,
            // the SAME as the time text's own Flexible, so they split the
            // column 50/50 and squeezed the position/duration text into a box
            // too narrow for it — a second, self-inflicted overflow (found via
            // a real Flutter render, not guessed: "RenderFlex overflowed by
            // 103 pixels", pointing at that exact Row). No more flex vs. flex
            // competition: everything space-hungry lives in the one
            // FittedBox, and the time row below is free to just fit its text.
            GestureDetector(
              onTap: () async {
                HapticFeedback.selectionClick();
                _loopEnabled = !_loopEnabled;
                await _player.setReleaseMode(_loopEnabled ? ReleaseMode.loop : ReleaseMode.release);
                if (mounted) setState(() {});
              },
              child: Container(width: 34, height: 34,
                decoration: BoxDecoration(shape: BoxShape.circle,
                    color: _card, border: Border.all(color: _border)),
                child: Icon(Icons.loop_rounded, size: 17,
                    color: _loopEnabled ? _teal : _textDim))),
          ]),
        ),
      ),
      const SizedBox(width: 8),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min, children: [
        // S244: also FittedBox-guarded — a long duration ("12:34.5") plus a
        // long position at once is unlikely to overflow a typical remaining
        // width, but this makes it structurally impossible regardless.
        FittedBox(fit: BoxFit.scaleDown, alignment: AlignmentDirectional.centerStart,
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text(_fmtTime(_positionSec), style: const TextStyle(color: _gold, fontSize: 11,
                fontWeight: FontWeight.w600, fontFamily: 'monospace')),
            const Text(' / ', style: TextStyle(color: _textDim, fontSize: 11)),
            Text(_fmtTime(_durationSec), style: const TextStyle(color: _textB, fontSize: 11, fontFamily: 'monospace')),
          ])),
        const SizedBox(height: 4),
        ClipRRect(borderRadius: BorderRadius.circular(3),
          child: LinearProgressIndicator(
            value: _durationSec > 0 ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0,
            backgroundColor: _border, valueColor: const AlwaysStoppedAnimation(_gold), minHeight: 3)),
      ])),
    ]));

  Widget _tBtn(IconData icon, VoidCallback onTap, {Color? color}) =>
    GestureDetector(onTap: onTap,
      child: Container(width: 34, height: 34,
        decoration: BoxDecoration(shape: BoxShape.circle, color: _card,
            border: Border.all(color: _border)),
        child: Icon(icon, color: color ?? _textB, size: 17)));

  Widget _tabBar() {
    final ar = LangProvider.strings(context).ar;
    final labels = ar ? ['قص','EQ','تأثيرات','FX+','استوديو','التوافق','دمج','تصدير']
                      : ['Trim','EQ','Effects','FX+','Studio','Compliance','Merge','Export'];
    final icons = [Icons.content_cut_rounded, Icons.equalizer_rounded,
                   Icons.auto_fix_high_rounded, Icons.graphic_eq_rounded, Icons.science_rounded,
                   Icons.rule_rounded, Icons.merge_type_rounded, Icons.ios_share_rounded];
    final n = _Tab.values.length;
    return Container(
      decoration: BoxDecoration(color: _surface, border: Border(bottom: BorderSide(color: _border)),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.15),
              blurRadius: 6, offset: const Offset(0, 3))]),
      child: Stack(children: [
        AnimatedAlign(
          duration: const Duration(milliseconds: 220), curve: Curves.easeOutCubic,
          // S243 RTL FIX: was plain Alignment (never flips), so in Arabic the
          // tab Row reversed but the underline stayed LTR — it sat under the
          // wrong tab. AlignmentDirectional is start-relative, matching the Row.
          alignment: AlignmentDirectional(-1 + 2 * _tab.index / (n - 1), 1),
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
      case _Tab.loudness: child = _loudnessTab(); break;
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
      const SizedBox(height: 10),
      // S238 — split a long recitation into ayah-sized files at the pauses
      _card_(ar ? 'تقسيم عند السكتات (فواصل الآيات)' : 'Split by Silence (Ayah Cutter)',
          Icons.graphic_eq_rounded, [
        Text(ar
            ? 'يكتشف السكتات في التلاوة ويقسم الملف تلقائيًا إلى مقاطع منفصلة — مثالي لفصل الآيات.'
            : 'Detects the pauses in a recitation and automatically cuts the file into separate parts — perfect for isolating ayat.',
            style: const TextStyle(color: _textB, fontSize: 12, height: 1.5)),
        const SizedBox(height: 10),
        _knob(ar ? 'حساسية الصمت' : 'Silence Level', '${_silThresh.round()} dB',
            _silThresh, -60, -25, (v) => setState(() => _silThresh = v)),
        _knob(ar ? 'أقل مدة سكتة' : 'Min Pause', '${_silMin.toStringAsFixed(1)}s',
            _silMin, 0.2, 2.0, (v) => setState(() => _silMin = v)),
        const SizedBox(height: 4),
        GestureDetector(onTap: _busy ? null : _splitBySilence,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 13),
            decoration: BoxDecoration(color: _tealDk, borderRadius: BorderRadius.circular(10),
                border: Border.all(color: _teal.withValues(alpha: 0.4))),
            child: Center(child: Row(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.splitscreen_rounded, color: _teal, size: 17),
              const SizedBox(width: 8),
              Text(ar ? 'تقسيم تلقائي' : 'Auto-Split Now',
                  style: const TextStyle(color: _teal, fontSize: 13, fontWeight: FontWeight.w700)),
            ])))),
      ]),
    ]);
  }

  // ── EQ TAB — 10 bands ─────────────────────────────────────────────────────
  Widget _eqTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.all(14), children: [
      // S236 — real frequency profile of the loaded file (numpy Welch analysis)
      if (_spectrum.isNotEmpty) ...[
        _card_(ar ? 'الطيف الترددي للملف' : 'Frequency Profile', Icons.bar_chart_rounded, [
          SizedBox(height: 64, child: CustomPaint(
              painter: _SpectrumPainter(bands: _spectrum),
              size: const Size(double.infinity, 64))),
          const SizedBox(height: 6),
          Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: const [
            Text('60Hz', style: TextStyle(color: _textDim, fontSize: 9, fontFamily: 'monospace')),
            Text('1kHz', style: TextStyle(color: _textDim, fontSize: 9, fontFamily: 'monospace')),
            Text('10kHz', style: TextStyle(color: _textDim, fontSize: 9, fontFamily: 'monospace')),
          ]),
          const SizedBox(height: 4),
          Text(ar ? 'متوسط طاقة الملف عبر الترددات — يساعدك على ضبط الموازن بدقة'
                  : 'Average energy across frequencies — helps you target the EQ precisely',
              style: const TextStyle(color: _textDim, fontSize: 10.5)),
        ]),
        const SizedBox(height: 10),
      ],
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
      // S238 — one-tap chains tuned for the human voice (recitation, lectures,
      // voice notes). Sets multiple existing controls at once; export as usual.
      _card_(ar ? 'تحسين صوتي سريع' : 'Quick Voice Enhance', Icons.record_voice_over_rounded, [
        Text(ar ? 'سلاسل جاهزة مضبوطة لصوت القارئ — اضغط، عاين، ثم صدّر'
                : 'Ready-made chains tuned for the reciter\'s voice — tap, preview, export',
            style: const TextStyle(color: _textDim, fontSize: 11)),
        const SizedBox(height: 10),
        Wrap(spacing: 8, runSpacing: 8, children: [
          _chip_(ar ? 'تلاوة نقية' : 'Recitation Clean', () {
            setState(() {
              _hpFreq = 80; _noiseReduc = 45; _presence = 25;
              _compress = true; _compThresh = -18; _compRatio = 3.0;
              _loudnessTarget = '-16 LUFS (Mobile)';
            });
            _snack(ar ? '✓ تلاوة نقية — عاين ثم صدّر' : '✓ Recitation Clean applied — preview, then export');
          }),
          _chip_(ar ? 'رسالة صوتية واضحة' : 'Clear Voice Note', () {
            setState(() {
              _hpFreq = 100; _noiseReduc = 55; _deEsser = 30;
              _autoNormalize = true; _loudnessTarget = '-16 LUFS (Mobile)';
            });
            _snack(ar ? '✓ رسالة صوتية واضحة' : '✓ Clear Voice Note applied');
          }),
          _chip_(ar ? 'إصلاح تسجيل قديم' : 'Old Tape Repair', () {
            setState(() {
              _declip = true; _declick = true; _dehumOn = true;
              _noiseReduc = 60; _trebleBoost = 2;
              _loudnessTarget = '-16 LUFS (Mobile)';
            });
            _snack(ar ? '✓ إصلاح تسجيل قديم' : '✓ Old Tape Repair applied');
          }),
          _chip_(ar ? 'عزل صوت القارئ' : 'Isolate Reciter', () {
            setState(() {
              _vocalIso = 55; _hpFreq = 90; _noiseReduc = 35;
              _loudnessTarget = '-16 LUFS (Mobile)';
            });
            _snack(ar ? '✓ عزل صوت القارئ' : '✓ Isolate Reciter applied');
          }),
        ]),
      ]),
      const SizedBox(height: 10),
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

  // ── S245: COMPLIANCE TAB — real EBU R128 loudness checklist ─────────────
  // Backed by tilawa_dsp_studio.py's vendored pyloudnorm algorithm (real
  // ITU-R BS.1770-4 gated integrated loudness + EBU Tech 3342 Loudness
  // Range), not an approximation. Uses the SAME analysis already run for
  // the waveform — no extra processing needed to show this tab.
  static const _kComplianceTargets = [
    // label(EN), label(AR), target LUFS, tolerance LU, loudnessTarget preset string
    ('Spotify / Apple Podcasts', 'Spotify / آبل بودكاست', -14.0, 1.0, '-14 LUFS (Streaming)'),
    ('YouTube', 'يوتيوب', -14.0, 1.0, '-14 LUFS (Streaming)'),
    ('Apple Music', 'آبل ميوزك', -16.0, 1.0, '-16 LUFS (Mobile)'),
    ('Broadcast (EBU R128)', 'البث الإذاعي (EBU R128)', -23.0, 0.5, '-23 LUFS (Broadcast)'),
  ];

  Widget _loudnessTab() {
    final ar = LangProvider.strings(context).ar;
    if (_filePath == null) {
      return Center(child: Text(ar ? 'افتح ملفًا أولًا' : 'Open a file first',
          style: const TextStyle(color: _textDim)));
    }
    if (!_analyzed) {
      return ListView(padding: const EdgeInsets.all(14), children: [
        _card_(ar ? 'التوافق مع منصات النشر' : 'Publishing Compliance', Icons.rule_rounded, [
          Text(ar
              ? 'يقيس هذا التبويب الجهارة الحقيقية (LUFS) ونطاق الجهارة (LRA) والذروة '
                'الحقيقية (True Peak) باستخدام خوارزمية ITU-R BS.1770-4 الفعلية '
                '(المستمدة من مكتبة pyloudnorm)، ويقارنها بأهداف منصات النشر الشائعة.'
              : 'This tab measures real loudness (LUFS), Loudness Range (LRA), and '
                'True Peak using the actual ITU-R BS.1770-4 algorithm (vendored from '
                'the pyloudnorm library), and checks them against common publishing targets.',
              style: const TextStyle(color: _textB, fontSize: 12, height: 1.5)),
          const SizedBox(height: 12),
          GestureDetector(
            onTap: _analyzing ? null : _analyzeAudio,
            child: Container(
              padding: const EdgeInsets.symmetric(vertical: 13),
              decoration: BoxDecoration(color: _tealDk, borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: _teal.withValues(alpha: 0.4))),
              child: Center(child: Row(mainAxisSize: MainAxisSize.min, children: [
                if (_analyzing)
                  const SizedBox(width: 14, height: 14,
                      child: CircularProgressIndicator(strokeWidth: 2, color: _teal))
                else
                  const Icon(Icons.analytics_rounded, color: _teal, size: 17),
                const SizedBox(width: 8),
                Text(_analyzing ? (ar ? 'جارٍ التحليل…' : 'Analyzing…') : (ar ? 'تحليل الآن' : 'Analyze Now'),
                    style: const TextStyle(color: _teal, fontSize: 13, fontWeight: FontWeight.w700)),
              ])))),
        ]),
      ]);
    }

    final lufs = _statLufs;
    final lra = _statLra;
    final tp = _statTruePeakDb;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _card_(ar ? 'قياسات الجهارة الحقيقية' : 'Real Loudness Measurements', Icons.analytics_rounded, [
        Row(children: [
          Expanded(child: _loudnessStatBlock(ar ? 'الجهارة المتكاملة' : 'Integrated',
              lufs != null ? '${lufs.toStringAsFixed(1)}' : '—', 'LUFS')),
          Expanded(child: _loudnessStatBlock(ar ? 'نطاق الجهارة' : 'Loudness Range',
              lra != null ? lra.toStringAsFixed(1) : '—', 'LU')),
          Expanded(child: _loudnessStatBlock(ar ? 'الذروة الحقيقية' : 'True Peak',
              tp != null ? '${tp >= 0 ? "+" : ""}${tp.toStringAsFixed(1)}' : '—', 'dBTP',
              warn: tp != null && tp > -1.0)),
        ]),
        const SizedBox(height: 4),
        Text(ar ? 'وفق ITU-R BS.1770-4 / EBU Tech 3342 — خوارزمية pyloudnorm الحقيقية'
                : 'Per ITU-R BS.1770-4 / EBU Tech 3342 — the real pyloudnorm algorithm',
            style: const TextStyle(color: _textDim, fontSize: 10.5)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'قائمة التوافق' : 'Compliance Checklist', Icons.checklist_rounded,
          lufs == null ? [
            Text(ar ? 'تعذّر قياس الجهارة لهذا الملف' : 'Could not measure loudness for this file',
                style: const TextStyle(color: _textDim, fontSize: 12)),
          ] : _kComplianceTargets.map((t) {
            final label = ar ? t.$2 : t.$1;
            final target = t.$3;
            final tol = t.$4;
            final preset = t.$5;
            final diff = lufs - target;
            final pass = diff.abs() <= tol;
            final tooLoud = diff > tol;
            final icon = pass ? Icons.check_circle_rounded
                : (tooLoud ? Icons.arrow_upward_rounded : Icons.arrow_downward_rounded);
            final color = pass ? _teal : _gold;
            return Padding(padding: const EdgeInsets.symmetric(vertical: 7),
              child: Row(children: [
                Icon(icon, color: color, size: 18),
                const SizedBox(width: 10),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(label, style: const TextStyle(color: _textA, fontSize: 13, fontWeight: FontWeight.w600)),
                  Text(
                      pass
                          ? (ar ? 'ضمن الهدف (${target.toStringAsFixed(0)} LUFS)' : 'Within target (${target.toStringAsFixed(0)} LUFS)')
                          : (tooLoud
                              ? (ar ? 'أعلى من الهدف بـ ${diff.abs().toStringAsFixed(1)} LU' : '${diff.abs().toStringAsFixed(1)} LU too loud')
                              : (ar ? 'أهدأ من الهدف بـ ${diff.abs().toStringAsFixed(1)} LU' : '${diff.abs().toStringAsFixed(1)} LU too quiet')),
                      style: TextStyle(color: color, fontSize: 11)),
                ])),
                if (!pass)
                  GestureDetector(
                    onTap: () {
                      HapticFeedback.selectionClick();
                      setState(() { _loudnessTarget = preset; _truePeakLimiter = true; _tab = _Tab.studio; });
                      _snack(ar ? '✓ تم ضبط الهدف — راجع تبويب الاستوديو' : '✓ Target set — check the Studio tab');
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(color: _goldDim.withValues(alpha: 0.4),
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: _gold.withValues(alpha: 0.5))),
                      child: Text(ar ? 'إصلاح' : 'Fix',
                          style: const TextStyle(color: _gold, fontSize: 11, fontWeight: FontWeight.w700))),
                  ),
              ]));
          }).toList()),
      const SizedBox(height: 10),
      if (lra != null)
        _card_(ar ? 'نطاق الجهارة (LRA)' : 'Loudness Range (LRA)', Icons.expand_rounded, [
          Text(
              lra < 4
                  ? (ar ? 'نطاق ضيق — ديناميكية مضغوطة، مناسب لرسائل صوتية/بودكاست.'
                        : 'Narrow range — compressed dynamics, good for voice notes/podcasts.')
                  : lra < 9
                      ? (ar ? 'نطاق معتدل — ديناميكية طبيعية.' : 'Moderate range — natural dynamics.')
                      : (ar ? 'نطاق واسع — ديناميكية كبيرة بين الأجزاء الهادئة والصاخبة.'
                            : 'Wide range — large swing between quiet and loud sections.'),
              style: const TextStyle(color: _textB, fontSize: 12, height: 1.5)),
        ]),
      if ((_statClipPct ?? 0) > 0.5) ...[const SizedBox(height: 10),
        _card_(ar ? 'تحذير' : 'Warning', Icons.warning_amber_rounded, [
          Text(ar ? '${_statClipPct!.toStringAsFixed(1)}٪ من العينات مقطوعة (Clipping) — فعّل "إزالة التقطيع" في FX+.'
                  : '${_statClipPct!.toStringAsFixed(1)}% of samples are clipped — enable Declip in FX+.',
              style: const TextStyle(color: _red, fontSize: 12, height: 1.5)),
        ])],
    ]);
  }

  Widget _loudnessStatBlock(String label, String value, String unit, {bool warn = false}) => Column(children: [
    Text(label, style: const TextStyle(color: _textDim, fontSize: 10), textAlign: TextAlign.center),
    const SizedBox(height: 4),
    Text(value, style: TextStyle(color: warn ? _red : _gold, fontSize: 20,
        fontWeight: FontWeight.w800, fontFamily: 'monospace')),
    Text(unit, style: const TextStyle(color: _textDim, fontSize: 10)),
  ]);

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
            child: Container(margin: const EdgeInsetsDirectional.only(end: 6),
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
              child: Container(margin: const EdgeInsetsDirectional.only(end: 6),
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
        // S237 QoL — tap to copy the saved path to the clipboard
        GestureDetector(
          onTap: () {
            Clipboard.setData(ClipboardData(text: _outPath!));
            HapticFeedback.selectionClick();
            _snack(ar ? '✓ تم نسخ المسار' : '✓ Path copied', color: _teal);
          },
          child: Container(padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(color: _tealDk.withValues(alpha: 0.5),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: _teal.withValues(alpha: 0.4))),
            child: Row(children: [
              const Icon(Icons.check_circle_rounded, color: _teal, size: 20),
              const SizedBox(width: 10),
              Expanded(child: Text('${ar ? "تم الحفظ: " : "Saved: "}$_outPath',
                  style: const TextStyle(color: _textA, fontSize: 11),
                  overflow: TextOverflow.ellipsis, maxLines: 2)),
              const Icon(Icons.copy_rounded, color: _teal, size: 14),
            ])))],
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
        margin: const EdgeInsetsDirectional.only(end: 8),
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
    margin: const EdgeInsetsDirectional.only(end: 10),
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
      _dehumOn=false; _dehumBase=50; _dehumStrength=60; _vocalIso=0;  // S238
      _fx2OpenId=null;
    });
  }

  Widget _fx2Tab() {
    final ar = LangProvider.strings(context).ar;
    final q = _fx2Search.trim().toLowerCase();
    bool vis(String en, String arLbl) => q.isEmpty || en.toLowerCase().contains(q) || arLbl.toLowerCase().contains(q);

    final onBass = _bassBoost != 0, onTreble = _trebleBoost != 0, onSub = _subBass != 0,
        onPresence = _presence != 0, onHp = _hpFreq != 0, onLp = _lpFreq < 20000;
    final onVocalIso = _vocalIso != 0;  // S238
    final onTrem = _tremolo != 0, onVib = _vibrato != 0, onCrush = _crusher != 0;
    final onStereoFx = _stereoFx != 0, onChanMode = _channelMode != 'Stereo';
    final onDeEsser = _deEsser != 0, onPadStart = _padStart != 0, onPadEnd = _padEnd != 0;

    // S238 — voice & recitation tools (voice-only processing, no music FX)
    final voiceRows = <Widget>[
      if (vis('De-Hum', 'إزالة طنين الكهرباء'))
        _rackRow(id: 'dehum', label: ar ? 'إزالة طنين الكهرباء' : 'De-Hum', on: _dehumOn,
          valueStr: _dehumOn ? '$_dehumBase Hz · ${_dehumStrength.round()}%' : (ar?'معطل':'Off'),
          rightControl: _rackSwitch(_dehumOn, (v) => setState(() { _dehumOn = v; if (!v) _fx2OpenId = null; })),
          body: _dehumOn ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Wrap(spacing: 8, children: [50, 60].map((hz) {
              final sel = hz == _dehumBase;
              return GestureDetector(onTap: () => setState(() => _dehumBase = hz),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
                  decoration: BoxDecoration(
                    color: sel ? _goldDim.withValues(alpha: 0.4) : _surface,
                    borderRadius: BorderRadius.circular(18),
                    border: Border.all(color: sel ? _gold : _border, width: sel ? 1.5 : 1)),
                  child: Text('$hz Hz', style: TextStyle(color: sel ? _gold : _textB,
                      fontSize: 11, fontWeight: sel ? FontWeight.w700 : FontWeight.w400))));
            }).toList()),
            const SizedBox(height: 6),
            _slider(_dehumStrength, 10, 100, _gold, (v) => setState(() => _dehumStrength = v)),
            Text(ar ? '٥٠ هرتز لمعظم الدول · ٦٠ هرتز للأمريكتين'
                    : '50 Hz for most regions · 60 Hz for the Americas',
                style: const TextStyle(color: _textDim, fontSize: 10)),
          ]) : null),
      if (vis('Vocal Isolate', 'عزل الصوت البشري'))
        _rackRow(id: 'vocaliso', label: ar ? 'عزل الصوت البشري' : 'Vocal Isolate', on: onVocalIso,
          valueStr: _vocalIso==0 ? (ar?'معطل':'Off') : '${_vocalIso.round()}%',
          body: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _slider(_vocalIso, 0, 100, _gold, (v) => setState(() => _vocalIso = v)),
            Text(ar ? 'يركّز على صوت القارئ ويخفض أصوات الخلفية والقاعة'
                    : 'Focuses on the reciter\'s voice, pulls down room ambience',
                style: const TextStyle(color: _textDim, fontSize: 10)),
          ])),
    ];

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

    final totalOn = [_dehumOn,onVocalIso,  // S238
        onBass,onTreble,onSub,onPresence,onHp,onLp,
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
            hintText: ar ? 'ابحث في 26 تأثيرًا…' : 'Search 26 effects…',
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
        _rackSection(ar ? 'صوت القارئ' : 'Voice & Recitation',  // S238
            [_dehumOn,onVocalIso].where((b) => b).length, voiceRows),
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
    // S238 — voice tools
    'dehumOn': _dehumOn, 'dehumBase': _dehumBase, 'dehumStrength': _dehumStrength,
    'vocalIso': _vocalIso,
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
      // S238 — voice tools
      _dehumOn = m['dehumOn'] ?? false;
      _dehumBase = (m['dehumBase'] as num?)?.toInt() ?? 50;
      _dehumStrength = (m['dehumStrength'] ?? 60).toDouble();
      _vocalIso = (m['vocalIso'] ?? 0).toDouble();
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
    setState(() { _busy = true; _busyStart = DateTime.now(); _busyLabel = ar ? 'تصدير دفعي…' : 'Batch exporting…'; _pct = 0; });
    int done = 0, failed = 0;
    for (final p in paths) {
      try {
        final inp = await _safeInput(p);
        final ext = _fmt.toLowerCase();
        final base = p.split('/').last.replaceAll(RegExp(r'\.[^.]+$'), '');
        final dir = await getExternalStorageDirectory() ?? await getApplicationDocumentsDirectory();
        final out = '${dir.path}/tilawa_${base}_batch.$ext';
        // S236: batch now runs the full Studio Engine (numpy/scipy) per file —
        // same quality as single export — with the ffmpeg chain as fallback.
        final params = _buildDspParams(fullFile: true);
        final r = await _runDspEngine(inp, out, params);
        var okFile = ((r['rc'] as int?) ?? -1) == 0 && File(out).existsSync();
        if (!okFile) {
          final af = _buildAf();
          final cmd = 'ffmpeg -y -i "$inp" '
              '-af ${af.isEmpty ? "anull" : af.join(",")} ${_metaArgs()} '
              '-ar $_sampleRate -ac ${_channels == "Mono" ? 1 : 2} '
              '-acodec ${_codec()} ${_br()} "$out"';
          final res = await _proot(cmd, inp, out, timeout: 15);
          okFile = (res?['rc'] as int? ?? 1) == 0;
        }
        if (okFile) { done++; } else { failed++; }
      } catch (_) { failed++; }
      setState(() => _pct = (done + failed) / paths.length);
    }
    setState(() => _busy = false);
    unawaited(_saveEditorPrefs());  // S237 QoL
    _snack('✓ ${ar ? "تم" : "Done"}: $done${failed > 0 ? "  ·  ${ar ? "فشل" : "failed"}: $failed" : ""}');
  }
}

// ── WAVEFORM PAINTER ──────────────────────────────────────────────────────────
// S236: dual-layer (peak outline + solid RMS core) once the numpy analysis
// lands, with an *accurate* play animation — instead of the old fake global
// sine shimmer, a gaussian energy ripple hugs the playhead so motion follows
// what is actually being heard. Placeholder (pre-analysis) bars keep a gentle
// global shimmer so the screen never looks frozen.
class _WavePainter extends CustomPainter {
  final List<double> bars;
  final List<double>? rms;
  final double playPos, trimStart, trimEnd, animT;
  final bool playing, analyzed;
  _WavePainter({required this.bars, this.rms, required this.playPos,
      required this.trimStart, required this.trimEnd,
      required this.animT, required this.playing, this.analyzed = false});

  @override
  void paint(Canvas c, Size sz) {
    final n = bars.length; final bw = sz.width / n; final mid = sz.height / 2;
    final barW = (bw - 2).clamp(1.0, bw);

    // S242: SoundCloud-style progress waveform. Bars the playhead has already
    // passed light up GOLD; bars still ahead stay TEAL — so the sweep visibly
    // "intersects" the wave as it plays. A tight energy bump + scan glow marks
    // the exact play point. (Old code left every bar the same teal with only a
    // faint flat wash, plus a jumpy global sine that read as broken.)
    Paint vgrad(Color a, Color b) => Paint()
      ..shader = ui.Gradient.linear(const Offset(0, 0), Offset(0, sz.height), [a, b]);
    final playedCore   = vgrad(const Color(0xFFF3D170), const Color(0xFF8A6A12));
    final playedGhost  = Paint()..color = const Color(0xFFD4AF37).withOpacity(0.30);
    final aheadCore    = vgrad(const Color(0xFF37E0B8), const Color(0xFF0C5B3C));
    final aheadGhost   = Paint()..color = const Color(0xFF1DB898).withOpacity(0.26);
    final inactive     = Paint()..color = const Color(0xFF24463C).withOpacity(0.55);
    final inactiveGhost= Paint()..color = const Color(0xFF1A3A30).withOpacity(0.22);
    final hotCore      = vgrad(const Color(0xFFFFF6D0), const Color(0xFFE7BE3F));
    final rTrim        = Paint()..color = Colors.black.withOpacity(0.35);

    final x0 = trimStart * sz.width; final x1 = trimEnd * sz.width;

    final hasRms = rms != null && rms!.length == n;
    final headF  = playPos * n;  // fractional bar index of the playhead

    void bar(int i, Paint ghost, Paint core, double amp, double rmsAmp) {
      final x = i * bw + 1.0;
      final h = amp.clamp(0.05, 1.0) * mid * 0.9;
      if (hasRms) {
        c.drawRRect(RRect.fromRectAndRadius(
            Rect.fromLTWH(x, mid - h, barW, h * 2), const Radius.circular(2.5)), ghost);
        final hr = rmsAmp.clamp(0.03, 1.0) * mid * 0.9;
        c.drawRRect(RRect.fromRectAndRadius(
            Rect.fromLTWH(x, mid - hr, barW, hr * 2), const Radius.circular(2.5)), core);
      } else {
        c.drawRRect(RRect.fromRectAndRadius(
            Rect.fromLTWH(x, mid - h, barW, h * 2), const Radius.circular(2.5)), core);
      }
    }

    for (int i = 0; i < n; i++) {
      final frac = i / n;
      final inTrim = frac >= trimStart && frac < trimEnd;
      final played = frac < playPos;

      double amp = bars[i];
      double rmsAmp = hasRms ? rms![i] : 0;
      // tight reactive bump on the ~2 bars at the play point (localized, not global)
      if (playing) {
        final dist = (i - headF).abs();
        if (dist < 2.4) {
          final bump = 0.16 * (1 - dist / 2.4) * (0.72 + 0.28 * sin(animT * 2 * pi * 4));
          amp += bump; rmsAmp += bump * 0.8;
        } else if (!analyzed) {
          amp += 0.06 * sin(animT * 2 * pi + i * 0.28);  // placeholder liveliness
        }
      }

      Paint core, ghost;
      if (!inTrim) { core = inactive; ghost = inactiveGhost; }
      else if (playing && (i - headF).abs() < 0.9) { core = hotCore; ghost = playedGhost; }
      else if (played) { core = playedCore; ghost = playedGhost; }
      else { core = aheadCore; ghost = aheadGhost; }
      bar(i, ghost, core, amp, rmsAmp);
    }

    // trim shading on top of the bars so out-of-range reads as dimmed
    if (trimStart > 0) c.drawRect(Rect.fromLTWH(0, 0, x0, sz.height), rTrim);
    if (trimEnd   < 1) c.drawRect(Rect.fromLTWH(x1, 0, sz.width - x1, sz.height), rTrim);

    // ── playhead: soft scan glow + crisp line + cap dots ──
    final px = playPos * sz.width;
    const glowW = 24.0;
    c.drawRect(Rect.fromLTWH(px - glowW / 2, 0, glowW, sz.height),
        Paint()..shader = ui.Gradient.linear(
            Offset(px - glowW / 2, 0), Offset(px + glowW / 2, 0), [
          Colors.transparent,
          const Color(0xFFF3D170).withOpacity(playing ? 0.22 + 0.10 * sin(animT * 2 * pi * 2) : 0.14),
          Colors.transparent,
        ]));
    c.drawLine(Offset(px, 0), Offset(px, sz.height),
        Paint()..color = const Color(0xFFFFF1C4)..strokeWidth = 1.6);
    final capPaint = Paint()..color = const Color(0xFFFFF1C4);
    c.drawCircle(Offset(px, 3), 2.6, capPaint);
    c.drawCircle(Offset(px, sz.height - 3), 2.6, capPaint);

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

// ── SPECTRUM PAINTER — S236: 30-band average spectrum from numpy analysis ────
class _SpectrumPainter extends CustomPainter {
  final List<double> bands;
  _SpectrumPainter({required this.bands});

  @override
  void paint(Canvas c, Size sz) {
    if (bands.isEmpty) return;
    // faint reference grid at 25/50/75%
    final grid = Paint()..color = const Color(0xFF1A3A30)..strokeWidth = 0.5;
    for (final g in [0.25, 0.5, 0.75]) {
      final y = sz.height * (1 - g);
      c.drawLine(Offset(0, y), Offset(sz.width, y), grid);
    }
    final n = bands.length;
    final bw = sz.width / n;
    for (int i = 0; i < n; i++) {
      final v = bands[i].clamp(0.0, 1.0);
      final h = v * (sz.height - 2);
      final x = i * bw + 1.0;
      c.drawRRect(RRect.fromRectAndRadius(
          Rect.fromLTWH(x, sz.height - h, bw - 2, h), const Radius.circular(2)),
          Paint()..shader = ui.Gradient.linear(
              Offset(0, sz.height), Offset(0, 0),
              [const Color(0xFF0A5A3A), const Color(0xFF1DB898), const Color(0xFFD4AF37)],
              [0.0, 0.55, 1.0]));
    }
  }

  @override bool shouldRepaint(_SpectrumPainter o) {
    if (o.bands.length != bands.length) return true;
    for (int i = 0; i < bands.length; i++) {
      if (o.bands[i] != bands[i]) return true;
    }
    return false;
  }
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
