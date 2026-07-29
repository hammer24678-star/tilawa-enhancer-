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
//
// S250 — UI rebuild + the bugs behind it:
//  · Tab strip is now scrollable. Ten fixed-width tabs in one Row meant the
//    later labels ("Compliance", "Quality", "Export") were clipped to ~41 px
//    each and unreadable on any normal phone.
//  · Auditioning no longer corrupts the edit. Loading a preview into the
//    shared AudioPlayer fired onDurationChanged, which overwrote _durationSec
//    with the 8-second preview's length — after one Preview tap every trim
//    handle, every time readout and the whole waveform mapped to the wrong
//    duration. The real duration is now held separately and preview playback
//    is an explicit, exitable mode.
//  · Trim handles are draggable directly on the waveform, which also gained a
//    time ruler and dB grid.
//  · Undo/redo across every control, a persistent transport/action bar, real
//    per-stage progress from the engine, and an "Engine Libraries" panel that
//    shows which of the 14 embedded audio packages are live on-device.
//  · New DSP exposed: WPE dereverb, pause squeezing, harmonic focus,
//    non-stationary denoise, plus content insights (pitch, brightness, pace,
//    speech ratio) with one-tap fixes.

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
import '../widgets/anim.dart';   // S250g: shared PressScale / EntranceFade / ChangePulse
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

enum _Tab { trim, eq, effects, fx2, cleanup, studio, loudness, quality, compare, merge, export_ }

/// S250 — one row of the scrollable tab strip.
class _TabSpec {
  final _Tab tab;
  final IconData icon;
  final String en, ar;
  const _TabSpec(this.tab, this.icon, this.en, this.ar);
}

const List<_TabSpec> _kTabs = [
  _TabSpec(_Tab.trim,     Icons.content_cut_rounded,   'Trim',       'قص'),
  _TabSpec(_Tab.eq,       Icons.equalizer_rounded,     'EQ',         'الموازن'),
  _TabSpec(_Tab.effects,  Icons.auto_fix_high_rounded, 'Effects',    'تأثيرات'),
  _TabSpec(_Tab.fx2,      Icons.graphic_eq_rounded,    'FX+',        'FX+'),
  _TabSpec(_Tab.cleanup,  Icons.blur_on_rounded,       'Cleanup',    'تنظيف'),
  _TabSpec(_Tab.studio,   Icons.science_rounded,       'Studio',     'استوديو'),
  _TabSpec(_Tab.loudness, Icons.rule_rounded,          'Compliance', 'التوافق'),
  _TabSpec(_Tab.quality,  Icons.fact_check_rounded,    'Quality',    'الجودة'),
  _TabSpec(_Tab.compare,  Icons.compare_arrows_rounded,'Compare',    'مقارنة'),
  _TabSpec(_Tab.merge,    Icons.merge_type_rounded,    'Merge',      'دمج'),
  _TabSpec(_Tab.export_,  Icons.ios_share_rounded,     'Export',     'تصدير'),
];

class AudioEditorScreen extends StatefulWidget {
  /// S250 — open straight onto a file instead of the picker. The home screen
  /// uses it to hand a just-restored recitation to the editor ("Open in
  /// Editor"), which previously meant finding the output again by hand in the
  /// file picker.
  final String? initialPath;
  const AudioEditorScreen({super.key, this.initialPath});
  @override State<AudioEditorScreen> createState() => _AudioEditorScreenState();
}

class _AudioEditorScreenState extends State<AudioEditorScreen>
    with TickerProviderStateMixin {

  String? _filePath;
  String  _fileName = '';
  double  _durationSec = 0;
  int     _fileBytes = 0;        // S250 — shown in the file bar
  bool    _loopEnabled = false;  // S244 — moved off the transport row's fixed-width chain

  final _player = AudioPlayer();
  StreamSubscription<PlayerState>? _stateSub;
  StreamSubscription<Duration>?    _posSub;
  StreamSubscription<Duration>?    _durSub;
  bool   _playing = false;
  double _positionSec = 0;

  // S250 BUG FIX — auditioning used to destroy the edit state.
  // _previewDsp()/_playOriginalSlice() point the shared AudioPlayer at a
  // different file; audioplayers then emits onDurationChanged for THAT file and
  // the listener wrote it straight into _durationSec. An 8-second preview of a
  // 40-minute recitation therefore left the editor believing the file was 8
  // seconds long: trim handles, the selection duration, the waveform playhead
  // and every exported time offset were all computed from the wrong total.
  // Position updates were equally wrong (preview-relative, drawn as absolute).
  // Now: preview playback is an explicit mode. While it is active the source
  // duration is preserved, position updates are tracked separately, and the UI
  // shows an exit affordance instead of silently lying about the file.
  bool   _previewMode    = false;   // player is on a rendered preview, not the file
  double _previewLenSec  = 0;       // that preview's own length
  double _previewPosSec  = 0;       // playhead inside the preview
  bool   _previewIsOriginalAb = false;  // A/B: raw file from the preview offset

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

  // S248 — Cleanup tab: real noisereduce + webrtcvad (bundled via S247)
  bool   _aiDenoiseOn       = false;
  double _aiDenoiseStrength = 60;    // 0-100
  bool   _aiDenoiseNonStat  = false; // S250 — moving noise estimate
  bool   _vadTrimOn         = false;
  double _vadAggr           = 2;     // 0-3 (webrtcvad aggressiveness)

  // S250 — Cleanup tab: nara_wpe dereverb + webrtcvad pause squeezing
  double _dereverb      = 0;      // 0-100 (0 = off)
  bool   _squeezeOn     = false;
  double _squeezeMax    = 1.2;    // pauses longer than this get shortened (s)
  double _squeezeKeep   = 0.35;   // …down to this (s)
  double _harmonicFocus = 0;      // 0-100 — HPSS transient-noise removal

  // S248 — Quality tab: pystoi intelligibility score (bundled via S247)
  bool    _qualityChecking = false;
  double? _statStoi;                 // 0..1, higher = more intelligible
  double? _statEstoi;                // S250 — modulation-sensitive variant
  double? _statLufsDelta;            // S250 — loudness change of the render
  double? _statDriftSec;             // S250 — length mismatch (invalidates STOI)

  // S255 — Compare tab: an A/B report against a reference recording. Distinct
  // from Quality, which renders the CURRENT file with the CURRENT settings and
  // scores that against itself. Here the reference is a second file the user
  // picks, and nothing is rendered.
  String? _cmpRefPath, _cmpRefName;
  bool _cmpRunning = false;
  String? _cmpError;
  Map<String, dynamic>? _cmpResult;
  String? _qualityError;

  // S250h — real environment diagnosis (probes, not file checks)
  Map<String, dynamic>? _diag;

  // S250 — Studio tab: which embedded packages are live on this device
  List<Map<String, dynamic>>? _libs;
  int     _libsOk = 0, _libsTotal = 0;
  bool    _libsLoading = false;
  String? _libsError;

  // S250 — content insights from --analyze (drive the one-tap fixes)
  double? _insF0, _insBrightness, _insOnsets, _insSpeechPct, _insStereoCorr, _insDc;
  int?    _insLongPauses;
  String? _insNote;

  // S250 — live progress + per-stage timings reported by the engine
  String  _stageLabel = '';
  Timer?  _progressTimer;
  String? _progressPath;
  List<Map<String, dynamic>> _lastStages = const [];
  double? _lastRunMs;

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
  // S250 — the metadata fields had no controllers, so S237 deliberately refused
  // to persist them ("restored text would be invisible in the UI") and undo
  // couldn't touch them either. With controllers they persist and restore.
  final _metaTitleCtrl  = TextEditingController();
  final _metaArtistCtrl = TextEditingController();
  final _metaAlbumCtrl  = TextEditingController();
  final _fx2SearchCtrl  = TextEditingController();
  bool   _busy     = false;
  double _pct      = 0;
  String? _outPath;
  String  _busyLabel = '';
  DateTime? _busyStart;  // S237: elapsed time shown in the processing overlay

  _Tab _tab = _Tab.trim;
  final _tabScroll = ScrollController();   // S250 — scrollable tab strip

  // S250 — undo/redo over every editable setting. Snapshots are taken lazily:
  // _pushUndo() is called on the *first* change of a gesture (slider drag
  // start, chip tap, switch flip) so a 200-event drag is one undo step.
  final List<Map<String, dynamic>> _undo = [];
  final List<Map<String, dynamic>> _redo = [];
  static const int _kUndoDepth = 40;

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
  // S250d — trim-handle grab emphasis (swell + glow while dragging)
  late AnimationController _grabCtrl;
  late Animation<double> _grabAnim;
  List<double>  _barsFrom = const [], _barsTo = const [];
  List<double>? _rmsTo;
  static const int _kBars = 96;        // must match _WAVE_BUCKETS in the py engine

  static const _ch    = MethodChannel('com.tilawa.tilawa_enhancer/local_engine');
  static const _media = MethodChannel('com.tilawa.tilawa_enhancer/media');

  /// S256: a placeholder waveform that looks like recitation, not like static.
  ///
  /// This used to be `0.1 + rng.nextDouble() * 0.9` per bar — independent
  /// uniform noise, which draws as a barcode: no phrases, no breaths, every
  /// bar unrelated to the one beside it. It is also the first thing you see
  /// for every file, and on anything the analyzer cannot read it is the ONLY
  /// thing you see.
  ///
  /// Recitation is breath groups separated by short pauses, each group with a
  /// quick onset and a longer decay. That is what this draws, seeded from the
  /// file name so a given file always shows the same shape rather than
  /// reshuffling on every rebuild.
  static List<double> _placeholderBars(int seed, int n) {
    final rng = Random(seed);
    final out = List<double>.filled(n, 0.0);
    var i = 0;
    while (i < n) {
      final len = 6 + rng.nextInt(16);          // one breath group
      final gap = 1 + rng.nextInt(3);           // the pause after it
      final peak = 0.42 + rng.nextDouble() * 0.5;
      for (var k = 0; k < len && i < n; k++, i++) {
        final u = len > 1 ? k / (len - 1) : 0.0;
        // quick onset, long decay — the envelope of a spoken phrase
        final env = u < 0.18
            ? u / 0.18
            : pow(1.0 - (u - 0.18) / 0.82, 0.75).toDouble();
        final grain = 0.70 + 0.30 * rng.nextDouble();
        out[i] = (peak * env * grain).clamp(0.05, 1.0);
      }
      for (var k = 0; k < gap && i < n; k++, i++) {
        out[i] = 0.03 + rng.nextDouble() * 0.04;
      }
    }
    return out;
  }

  @override
  void initState() {
    super.initState();
    _bars = _placeholderBars(42, _kBars);
    _waveCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 3))..repeat();
    _glowCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 2))..repeat(reverse: true);
    // S236 — morphs the placeholder bars into the real analyzed waveform
    _grabCtrl = AnimationController(vsync: this,
        duration: const Duration(milliseconds: 160));
    _grabAnim = CurvedAnimation(parent: _grabCtrl, curve: Curves.easeOutBack);
    _barMorphCtrl = AnimationController(vsync: this, duration: const Duration(milliseconds: 800))
      ..addListener(() {
        if (_barsTo.isEmpty) return;
        // S256: the real waveform sweeps in from the left instead of every bar
        // crossfading in lockstep. All 96 changing at once read as "the picture
        // was swapped"; staggered, it reads as the file being read — which is
        // exactly what just happened. Each bar gets its own window inside the
        // run, offset by its position.
        const spread = 0.45;                 // share of the run spent staggering
        final raw = _barMorphCtrl.value;
        final nb = _barsTo.length;
        double progressFor(int i) {
          final start = (nb > 1 ? i / (nb - 1) : 0.0) * spread;
          final local = ((raw - start) / (1.0 - spread)).clamp(0.0, 1.0);
          return Curves.easeOutCubic.transform(local);
        }
        setState(() {
          _bars = List.generate(nb, (i) {
            final f = i < _barsFrom.length ? _barsFrom[i] : 0.0;
            return f + (_barsTo[i] - f) * progressFor(i);
          });
          final rt = _rmsTo;
          if (rt != null) {
            _rmsBars = List.generate(rt.length, (i) => rt[i] * progressFor(i));
          }
        });
      });
    _stateSub = _player.onPlayerStateChanged.listen((s) {
      if (mounted) setState(() => _playing = s == PlayerState.playing);
    });
    // S250 — route position/duration by mode. While a preview is loaded these
    // describe the PREVIEW, not the edited file, so they must not touch
    // _positionSec/_durationSec (see the _previewMode comment above).
    _posSub = _player.onPositionChanged.listen((d) {
      if (!mounted) return;
      final t = d.inMilliseconds / 1000.0;
      setState(() {
        if (_previewMode) {
          _previewPosSec = t;
          // A/B plays the raw file from the preview offset, so its position IS
          // a real position in the source — keep the playhead in sync for it.
          if (_previewIsOriginalAb) _positionSec = t;
        } else {
          _positionSec = t;
        }
      });
    });
    _durSub = _player.onDurationChanged.listen((d) {
      if (!mounted) return;
      final t = d.inMilliseconds / 1000.0;
      if (t <= 0) return;
      setState(() {
        if (_previewMode && !_previewIsOriginalAb) {
          _previewLenSec = t;
        } else if (!_previewMode) {
          _durationSec = t;
        }
      });
    });
    _loadEditorPrefs();  // S237 QoL — restore last-used export/studio settings
    unawaited(_cleanTempFiles());  // S250 — reclaim earlier sessions' scratch
    final initial = widget.initialPath;
    if (initial != null && initial.isNotEmpty) {
      unawaited(_openPath(initial));  // S250 — deep-linked file
    }
  }

  /// S250 — load a known path (no picker). Shared by [widget.initialPath] and
  /// anything else that wants to hand the editor a file.
  Future<void> _openPath(String path) async {
    int bytes = 0;
    try { bytes = File(path).lengthSync(); } catch (_) { return; }
    if (!mounted) return;
    setState(() {
      _filePath = path;
      _fileName = path.split('/').last;
      _fileBytes = bytes;
      _durationSec = 0; _positionSec = 0; _trimStart = 0; _trimEnd = 1;
      _outPath = null;
      _previewMode = false; _previewIsOriginalAb = false;
      _undo.clear(); _redo.clear();
      _bars = _placeholderBars(_fileName.hashCode, _kBars);
    });
    try {
      await _player.setSource(DeviceFileSource(path));
    } catch (_) {
      // duration still arrives from the analysis pass below
    }
    unawaited(_analyzeAudio());
  }

  @override
  void dispose() {
    _stateSub?.cancel(); _posSub?.cancel(); _durSub?.cancel();
    _progressTimer?.cancel();
    _player.dispose(); _waveCtrl.dispose(); _glowCtrl.dispose();
    _barMorphCtrl.dispose();
    _grabCtrl.dispose();
    _tabScroll.dispose();
    _metaTitleCtrl.dispose(); _metaArtistCtrl.dispose(); _metaAlbumCtrl.dispose();
    _fx2SearchCtrl.dispose();
    super.dispose();
  }

  void _syncMetaControllers() {
    if (_metaTitleCtrl.text != _metaTitle) _metaTitleCtrl.text = _metaTitle;
    if (_metaArtistCtrl.text != _metaArtist) _metaArtistCtrl.text = _metaArtist;
    if (_metaAlbumCtrl.text != _metaAlbum) _metaAlbumCtrl.text = _metaAlbum;
  }

  // S250 — _safeInput() copies every input into the temp dir on every
  // operation (analyse, preview, quality check, each export, each batch file)
  // and nothing ever deleted them, so the cache dir grew without bound —
  // gigabytes after a few long recitations. Sweep anything of ours older than
  // an hour at startup, and delete the per-run copies inline (see _dropTemp).
  Future<void> _cleanTempFiles() async {
    try {
      final dir = await getTemporaryDirectory();
      final cutoff = DateTime.now().subtract(const Duration(hours: 1));
      for (final e in dir.listSync()) {
        if (e is! File) continue;
        final name = e.path.split('/').last;
        if (!name.startsWith('tl_')) continue;
        try {
          if (e.statSync().modified.isBefore(cutoff)) e.deleteSync();
        } catch (_) {}
      }
    } catch (_) {}
  }

  void _dropTemp(String? path) {
    if (path == null) return;
    try {
      final f = File(path);
      if (f.existsSync()) f.deleteSync();
    } catch (_) {}
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

  // S250 — engine failures come back as long multi-line ffmpeg/python output.
  // A 4-second snackbar truncated them into uselessness; now the message is
  // trimmed for display and the full text is one tap from the clipboard.
  void _snackError(Object e) {
    if (!mounted) return;
    final ar = LangProvider.strings(context).ar;
    final full = e.toString();
    final short = full.length > 160 ? '${full.substring(0, 160)}…' : full;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      backgroundColor: _card, behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10),
          side: const BorderSide(color: _red, width: 0.7)),
      content: Text(short, style: const TextStyle(color: _red, fontSize: 11), maxLines: 4),
      duration: const Duration(seconds: 8),
      action: SnackBarAction(
        label: ar ? 'نسخ' : 'Copy', textColor: _gold,
        onPressed: () => Clipboard.setData(ClipboardData(text: full))),
    ));
  }

  void _warnBusy() {
    final ar = LangProvider.strings(context).ar;
    _snack(ar ? 'جارٍ المعالجة… انتظر قليلًا' : 'Processing… please wait', color: _gold);
  }

  Future<void> _pick() async {
    if (_busy) { _warnBusy(); return; }
    if (_playing) await _player.stop();
    final r = await FilePicker.platform.pickFiles(type: FileType.audio, allowMultiple: false);
    if (r == null || r.files.isEmpty || r.files.first.path == null) return;
    final f = r.files.first;
    final path = f.path!;
    int bytes = 0;
    try { bytes = File(path).lengthSync(); } catch (_) {}
    if (!mounted) return;
    setState(() {
      _filePath = path; _fileName = f.name; _fileBytes = bytes;
      _durationSec = 0; _positionSec = 0; _trimStart = 0; _trimEnd = 1; _outPath = null;
      _previewMode = false; _previewIsOriginalAb = false;  // S250
      _previewLenSec = 0; _previewPosSec = 0;
      _undo.clear(); _redo.clear();                        // S250 — new file, new history
      // S236 — invalidate any previous file's analysis
      _analyzed = false; _analyzing = false; _rmsBars = null; _spectrum = const [];
      _statPeakDb = null; _statRmsDb = null; _statLufs = null; _statClipPct = null;
      _statLra = null; _statTruePeakDb = null;
      _statStoi = null; _statEstoi = null; _statLufsDelta = null;
      _statDriftSec = null; _qualityError = null;          // S248/S250
      _insF0 = null; _insNote = null; _insBrightness = null; _insOnsets = null;
      _insSpeechPct = null; _insLongPauses = null; _insStereoCorr = null; _insDc = null;
      _lastStages = const []; _lastRunMs = null;
      _bars = _placeholderBars(f.name.hashCode, _kBars);
    });
    try {
      await _player.setSource(DeviceFileSource(path));
    } catch (e) {
      // S250: this was unguarded — an unsupported/corrupt file threw straight
      // out of _pick() and the screen just stopped responding to the tap.
      _snack('Could not open this file: $e', color: _red);
    }
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
    String? inp;
    String? outJson;
    try {
      final ok = await _ch.invokeMethod<bool>('isBasicSetupComplete') ?? false;
      if (!ok || !mounted) return;
      setState(() => _analyzing = true);
      inp = await _safeInput(path);
      final tmp = await getTemporaryDirectory();
      outJson = '${tmp.path}/tl_analysis_${DateTime.now().millisecondsSinceEpoch}.json';
      final script = await _ensureDspScript();
      final r = await _proot('python3 "$script" --analyze "$inp" "$outJson"',
          inp, outJson, timeout: 5);
      if (token != _analyzeToken || !mounted) return;
      if ((r?['rc'] as int? ?? 1) != 0 || !File(outJson).existsSync()) return;
      final m = Map<String, dynamic>.from(jsonDecode(await File(outJson).readAsString()));
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
        // S250 — content insights that power the one-tap fixes
        _insF0         = (m['f0_hz']         as num?)?.toDouble();
        _insNote       =  m['note']          as String?;
        _insBrightness = (m['brightness_hz'] as num?)?.toDouble();
        _insOnsets     = (m['onsets_per_min'] as num?)?.toDouble();
        _insSpeechPct  = (m['speech_pct']    as num?)?.toDouble();
        _insLongPauses = (m['long_pauses']   as num?)?.toInt();
        _insStereoCorr = (m['stereo_corr']   as num?)?.toDouble();
        _insDc         = (m['dc_offset']     as num?)?.toDouble();
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
      _dropTemp(outJson);
      _dropTemp(inp);            // S250 — was leaked on every file open
      if (mounted && token == _analyzeToken) setState(() => _analyzing = false);
    }
  }

  // ── S250: ENGINE LIBRARIES — which embedded packages are live on-device ────
  // Renders in the Studio tab. This is the answer to "are the bundled audio
  // packages actually there?", which until S250 was unanswerable from the app
  // (and the honest answer was "no" — see build_assets.sh).
  Future<void> _loadLibs() async {
    if (_libsLoading) return;
    setState(() { _libsLoading = true; _libsError = null; });
    String? outJson;
    try {
      // S250h — ask what actually WORKS first. This is the difference between
      // "not set up" and "set up but the environment is broken", which is the
      // state that made the editor silently fail every operation.
      try {
        final d = await _ch.invokeMethod<Map>('diagnose');
        if (d != null && mounted) {
          setState(() => _diag = Map<String, dynamic>.from(d));
        }
      } catch (_) {}
      final ok = await _ch.invokeMethod<bool>('isBasicSetupComplete') ?? false;
      if (!ok) {
        final d = _diag;
        if (d != null && d['ffmpeg_file'] == true && d['ffmpeg_runs'] != true) {
          throw Exception('ffmpeg is installed but cannot start — the local '
              'environment needs re-installing (Settings → local mode). '
              '${d['ffmpeg_error'] ?? ''}');
        }
        throw Exception('local engine not set up yet');
      }
      final tmp = await getTemporaryDirectory();
      outJson = '${tmp.path}/tl_libs_${DateTime.now().millisecondsSinceEpoch}.json';
      final script = await _ensureDspScript();
      final r = await _proot('python3 "$script" --libs "$outJson"', outJson, outJson,
          timeout: 3);
      if ((r?['rc'] as int? ?? 1) != 0 || !File(outJson).existsSync()) {
        throw Exception(r?['out'] ?? 'engine did not report');
      }
      final m = Map<String, dynamic>.from(jsonDecode(await File(outJson).readAsString()));
      final pkgs = ((m['packages'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map)).toList();
      if (!mounted) return;
      setState(() {
        _libs = pkgs;
        _libsOk = (m['count_ok'] as num?)?.toInt() ?? pkgs.where((p) => p['ok'] == true).length;
        _libsTotal = (m['count_total'] as num?)?.toInt() ?? pkgs.length;
      });
    } catch (e) {
      if (mounted) setState(() => _libsError = '$e');
    } finally {
      _dropTemp(outJson);
      if (mounted) setState(() => _libsLoading = false);
    }
  }

  // ── S250: LIVE PROGRESS — poll the sidecar file tqdm writes in the engine ──
  // The proot channel is one blocking call, so the only way to show real
  // progress (instead of an indeterminate spinner for minutes) is to watch the
  // file the engine updates as each stage completes.
  void _startProgressPolling(String path) {
    _progressTimer?.cancel();
    _progressPath = path;
    _dropTemp(path);
    _progressTimer = Timer.periodic(const Duration(milliseconds: 600), (_) {
      if (!mounted || !_busy) return;
      try {
        final f = File(path);
        if (!f.existsSync()) return;
        final line = f.readAsStringSync().trim();      // "3/9|dereverb"
        if (line.isEmpty) return;
        final parts = line.split('|');
        final frac = parts[0].split('/');
        if (frac.length == 2) {
          final n = double.tryParse(frac[0].trim());
          final total = double.tryParse(frac[1].trim());
          if (n != null && total != null && total > 0) {
            // hold the bar inside 0.15..0.95 — the Dart side owns the ends
            final p = (0.15 + 0.80 * (n / total)).clamp(0.15, 0.95);
            final label = parts.length > 1 ? parts[1].trim() : '';
            setState(() { _pct = p; _stageLabel = label; });
          }
        }
      } catch (_) {}
    });
  }

  void _stopProgressPolling() {
    _progressTimer?.cancel();
    _progressTimer = null;
    _dropTemp(_progressPath);
    _progressPath = null;
    if (mounted && _stageLabel.isNotEmpty) setState(() => _stageLabel = '');
  }

  /// Reads the per-stage timing report the engine leaves next to its output.
  Future<void> _readRunReport(String outPath) async {
    try {
      final f = File('$outPath.report.json');
      if (!f.existsSync()) return;
      final m = Map<String, dynamic>.from(jsonDecode(await f.readAsString()));
      final stages = ((m['stages'] as List?) ?? const [])
          .map((e) => Map<String, dynamic>.from(e as Map)).toList();
      if (mounted) {
        setState(() {
          _lastStages = stages;
          _lastRunMs = (m['total_ms'] as num?)?.toDouble();
        });
      }
      f.deleteSync();
    } catch (_) {}
  }

  // ── S248: QUALITY CHECK — renders current settings, scores vs. original
  // with pystoi (real speech-intelligibility metric, not just loudness) ──
  Future<void> _runQualityCheck() async {
    if (_filePath == null) return;
    if (!await _checkSetup()) return;
    if (_qualityChecking || _busy) return;
    HapticFeedback.selectionClick();
    setState(() {
      _qualityChecking = true;
      _qualityError = null;
      _statStoi = null; _statEstoi = null; _statLufsDelta = null; _statDriftSec = null;
    });
    String? processedOut;
    String? outJson;
    String? refSlice;
    String? inp;
    try {
      inp = await _safeInput(_filePath!);
      final tmp = await getTemporaryDirectory();
      final stamp = DateTime.now().millisecondsSinceEpoch;
      // S250 — score the SELECTION, not the whole file. Rendering a 40-minute
      // recitation just to get one number was a multi-minute wait, and scoring
      // a full render against a full original also mixes in the trim itself.
      // Both sides are now cut to the same window: like against like.
      final ss  = _trimStart * _durationSec;
      final dur = (_trimEnd - _trimStart) * _durationSec;
      const q = {'format': 'WAV', 'sample_rate': 16000, 'channels': 'Mono',
                 'wav_bit_depth': 16, 'metadata': <String, String>{}};

      processedOut = '${tmp.path}/tl_quality_proc_$stamp.wav';
      final params = _buildDspParams();
      params['output'] = Map<String, dynamic>.from(q);
      final r = await _runDspEngine(inp, processedOut, params);
      if (((r['rc'] as int?) ?? -1) != 0 || !File(processedOut).existsSync()) {
        throw Exception(r['out'] ?? 'Studio Engine render failed');
      }

      // untouched reference cut to the same window (no FX at all)
      refSlice = '${tmp.path}/tl_quality_ref_$stamp.wav';
      final refParams = _neutralDspParams(trimStart: ss, trimDur: dur)
        ..['output'] = Map<String, dynamic>.from(q);
      final rRef = await _runDspEngine(inp, refSlice, refParams);
      final ref = (((rRef['rc'] as int?) ?? -1) == 0 && File(refSlice).existsSync())
          ? refSlice : inp;   // fall back to the full original if that failed

      outJson = '${tmp.path}/tl_quality_$stamp.json';
      final script = await _ensureDspScript();
      final r2 = await _proot(
          'python3 "$script" --quality "$ref" "$processedOut" "$outJson"',
          ref, outJson, timeout: 5);
      if (!File(outJson).existsSync()) {
        throw Exception(r2?['out'] ?? 'Quality check did not run');
      }
      final m = Map<String, dynamic>.from(jsonDecode(await File(outJson).readAsString()));
      if (m['ok'] != true) {
        throw Exception(m['error'] ?? 'pystoi unavailable');
      }
      if (!mounted) return;
      setState(() {
        _statStoi      = (m['stoi']             as num?)?.toDouble();
        _statEstoi     = (m['estoi']            as num?)?.toDouble();
        _statLufsDelta = (m['lufs_delta']       as num?)?.toDouble();
        _statDriftSec  = (m['length_drift_sec'] as num?)?.toDouble();
      });
    } catch (e) {
      if (mounted) setState(() => _qualityError = '$e');
    } finally {
      _dropTemp(processedOut);
      _dropTemp(outJson);
      _dropTemp(refSlice);
      _dropTemp(inp);
      if (mounted) setState(() => _qualityChecking = false);
    }
  }

  /// S250 — an all-defaults param set: decode + trim only, no processing.
  /// Used to cut the untouched reference slice the STOI score compares against.
  Map<String, dynamic> _neutralDspParams({required double trimStart,
      required double trimDur}) => {
    'sr': 48000, 'trim_start': trimStart, 'trim_dur': trimDur, 'reverse': false,
    'eq_freqs': _freqs, 'eq_gains': List.filled(10, 0.0), 'eq_q': 1.4,
    'declick': {'enabled': false, 'sensitivity': 50},
    'noise_reduction': {'strength': 0.0},
    'fade_in': 0.0, 'fade_out': 0.0, 'fade_curve': 'Equal Power',
    'pitch_semitones': 0.0, 'tempo': 1.0,
    'echo': {'mix': 0.0}, 'reverb': {'mix': 0.0, 'type': 'Room'},
    'compressor': {'enabled': false, 'threshold_db': -18.0, 'ratio': 1.0,
                   'attack_ms': 20.0, 'release_ms': 200.0, 'makeup_db': 0.0},
    'stereo_width': 1.0, 'volume': 1.0,
    'loudness': {'target_lufs': null, 'true_peak_limit_db': -1.0, 'limiter': false},
    'fx2': const <String, dynamic>{},
  };

  // ── S255 COMPARE ──────────────────────────────────────────────────────────
  Future<void> _pickCompareRef() async {
    final r = await FilePicker.platform.pickFiles(type: FileType.audio, allowMultiple: false);
    if (r == null || r.files.isEmpty || r.files.first.path == null) return;
    if (!mounted) return;
    setState(() {
      _cmpRefPath = r.files.first.path;
      _cmpRefName = r.files.first.name;
      _cmpResult = null;
      _cmpError = null;
    });
  }

  Future<void> _runCompare() async {
    if (_filePath == null || _cmpRefPath == null) return;
    setState(() { _cmpRunning = true; _cmpError = null; _cmpResult = null; });
    String? outJson;
    try {
      final tmp = await getTemporaryDirectory();
      final stamp = DateTime.now().millisecondsSinceEpoch;
      outJson = '${tmp.path}/tl_compare_$stamp.json';
      final script = await _ensureDspScript();
      // The reference is the FIRST argument: every delta reads "subject
      // relative to reference", which is the direction the wording assumes.
      final r = await _proot(
          'python3 "$script" --compare "$_cmpRefPath" "$_filePath" "$outJson"',
          _cmpRefPath!, outJson, timeout: 10);
      if (!File(outJson).existsSync()) {
        throw Exception(r?['out'] ?? 'Comparison did not run');
      }
      final m = Map<String, dynamic>.from(
          jsonDecode(await File(outJson).readAsString()));
      if (m['ok'] != true) throw Exception(m['error'] ?? 'comparison failed');
      if (!mounted) return;
      setState(() => _cmpResult = m);
    } catch (e) {
      if (mounted) setState(() => _cmpError = '$e');
    } finally {
      _dropTemp(outJson);
      if (mounted) setState(() => _cmpRunning = false);
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
    if (_previewMode) { await _player.resume(); return; }   // S250
    await _player.seek(Duration(milliseconds: (_trimStart * _durationSec * 1000).round()));
    await _player.resume();
  }

  Future<void> _stop() async {
    await _player.stop();
    if (!mounted) return;
    setState(() {
      if (_previewMode) {
        _previewPosSec = 0;
      } else {
        _positionSec = _trimStart * _durationSec;
      }
    });
  }

  /// S250 — leave preview playback and put the player back on the real file so
  /// the transport, waveform and trim controls describe the edit again.
  Future<void> _exitPreview({bool silent = false}) async {
    if (!_previewMode) return;
    final path = _filePath;
    try {
      await _player.stop();
      if (path != null) await _player.setSource(DeviceFileSource(path));
    } catch (_) {}
    if (!mounted) return;
    setState(() {
      _previewMode = false;
      _previewIsOriginalAb = false;
      _previewLenSec = 0;
      _previewPosSec = 0;
    });
    if (!silent) {
      final ar = LangProvider.strings(context).ar;
      _snack(ar ? '↩ عودة إلى الملف الأصلي' : '↩ Back to the source file', color: _textB);
    }
  }

  // S237 QoL — export & studio settings persist across sessions.
  // S250: the metadata tags are persisted too now that the fields are
  // controller-backed (S237 skipped them because restored text would have been
  // invisible), and so are the Cleanup-tab settings, which are per-recording-
  // setup choices you'd otherwise re-dial on every file.
  static const _prefsKey = 'audio_editor_prefs_v2';

  Future<void> _loadEditorPrefs() async {
    try {
      final p = await SharedPreferences.getInstance();
      final raw = p.getString(_prefsKey) ?? p.getString('audio_editor_prefs_v1');
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
        // S250
        _metaArtist        = (m['metaArtist'] as String?) ?? _metaArtist;
        _metaAlbum         = (m['metaAlbum'] as String?) ?? _metaAlbum;
        _aiDenoiseOn       = (m['aiDenoiseOn'] as bool?) ?? _aiDenoiseOn;
        _aiDenoiseStrength = (m['aiDenoiseStrength'] as num?)?.toDouble() ?? _aiDenoiseStrength;
        _aiDenoiseNonStat  = (m['aiDenoiseNonStat'] as bool?) ?? _aiDenoiseNonStat;
        _vadTrimOn         = (m['vadTrimOn'] as bool?) ?? _vadTrimOn;
        _vadAggr           = (m['vadAggr'] as num?)?.toDouble() ?? _vadAggr;
        _dereverb          = (m['dereverb'] as num?)?.toDouble() ?? _dereverb;
        _squeezeOn         = (m['squeezeOn'] as bool?) ?? _squeezeOn;
        _squeezeMax        = (m['squeezeMax'] as num?)?.toDouble() ?? _squeezeMax;
        _squeezeKeep       = (m['squeezeKeep'] as num?)?.toDouble() ?? _squeezeKeep;
        _harmonicFocus     = (m['harmonicFocus'] as num?)?.toDouble() ?? _harmonicFocus;
      });
      _syncMetaControllers();
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
        // S250 — title is per-file, so only artist/album carry over
        'metaArtist': _metaArtist, 'metaAlbum': _metaAlbum,
        'aiDenoiseOn': _aiDenoiseOn, 'aiDenoiseStrength': _aiDenoiseStrength,
        'aiDenoiseNonStat': _aiDenoiseNonStat,
        'vadTrimOn': _vadTrimOn, 'vadAggr': _vadAggr,
        'dereverb': _dereverb, 'squeezeOn': _squeezeOn,
        'squeezeMax': _squeezeMax, 'squeezeKeep': _squeezeKeep,
        'harmonicFocus': _harmonicFocus,
      }));
    } catch (_) {}
  }

  // ── S250: UNDO / REDO ─────────────────────────────────────────────────────
  // Every control funnels through _pushUndo() before it mutates state. Slider
  // drags snapshot once on onChangeStart, so a drag is a single undo step
  // rather than one per pixel.

  Map<String, dynamic> _snapshotAll() => {
    'trimStart': _trimStart, 'trimEnd': _trimEnd,
    'eq': List<double>.of(_eq), 'eqQ': _eqQ,
    'fadeIn': _fadeIn, 'fadeOut': _fadeOut, 'fadeCurve': _fadeCurve,
    'pitch': _pitch, 'tempo': _tempo, 'echo': _echo, 'reverb': _reverb,
    'vol': _vol, 'stereoW': _stereoW, 'reverse': _reverse,
    'noiseReduc': _noiseReduc, 'compress': _compress,
    'compThresh': _compThresh, 'compRatio': _compRatio,
    'compAttack': _compAttack, 'compRelease': _compRelease, 'compMakeup': _compMakeup,
    'declick': _declick, 'declickSens': _declickSens, 'reverbType': _reverbType,
    'loudnessTarget': _loudnessTarget, 'truePeakLimiter': _truePeakLimiter,
    'bassBoost': _bassBoost, 'trebleBoost': _trebleBoost, 'subBass': _subBass,
    'presence': _presence, 'hpFreq': _hpFreq, 'lpFreq': _lpFreq,
    'tremolo': _tremolo, 'vibrato': _vibrato, 'chorus': _chorus,
    'flanger': _flanger, 'phaser': _phaser, 'crusher': _crusher,
    'haasWiden': _haasWiden, 'stereoFx': _stereoFx,
    'channelMode': _channelMode, 'swapLR': _swapLR,
    'dehumOn': _dehumOn, 'dehumBase': _dehumBase, 'dehumStrength': _dehumStrength,
    'vocalIso': _vocalIso, 'noiseGate': _noiseGate, 'gateThresh': _gateThresh,
    'deEsser': _deEsser, 'declip': _declip, 'autoNormalize': _autoNormalize,
    'limiter': _limiter, 'limiterCeil': _limiterCeil,
    'autoTrimSilence': _autoTrimSilence, 'padStart': _padStart, 'padEnd': _padEnd,
    'harmonicFocus': _harmonicFocus,
    'aiDenoiseOn': _aiDenoiseOn, 'aiDenoiseStrength': _aiDenoiseStrength,
    'aiDenoiseNonStat': _aiDenoiseNonStat,
    'vadTrimOn': _vadTrimOn, 'vadAggr': _vadAggr,
    'dereverb': _dereverb, 'squeezeOn': _squeezeOn,
    'squeezeMax': _squeezeMax, 'squeezeKeep': _squeezeKeep,
    'silThresh': _silThresh, 'silMin': _silMin,
    'fmt': _fmt, 'kbps': _kbps, 'sampleRate': _sampleRate, 'channels': _channels,
    'wavBitDepth': _wavBitDepth, 'asRingtone': _asRingtone,
    'metaTitle': _metaTitle, 'metaArtist': _metaArtist, 'metaAlbum': _metaAlbum,
  };

  double _d(Map<String, dynamic> m, String k, double dflt) =>
      (m[k] as num?)?.toDouble() ?? dflt;
  bool _b(Map<String, dynamic> m, String k, bool dflt) => (m[k] as bool?) ?? dflt;

  void _restoreAll(Map<String, dynamic> m) {
    setState(() {
      _trimStart = _d(m, 'trimStart', _trimStart);
      _trimEnd   = _d(m, 'trimEnd', _trimEnd);
      final eq = (m['eq'] as List?)?.cast<double>();
      if (eq != null && eq.length == _eq.length) {
        for (int i = 0; i < _eq.length; i++) { _eq[i] = eq[i]; }
      }
      _eqQ = _d(m, 'eqQ', _eqQ);
      _fadeIn = _d(m, 'fadeIn', _fadeIn);
      _fadeOut = _d(m, 'fadeOut', _fadeOut);
      _fadeCurve = (m['fadeCurve'] as String?) ?? _fadeCurve;
      _pitch = _d(m, 'pitch', _pitch);
      _tempo = _d(m, 'tempo', _tempo);
      _echo = _d(m, 'echo', _echo);
      _reverb = _d(m, 'reverb', _reverb);
      _vol = _d(m, 'vol', _vol);
      _stereoW = _d(m, 'stereoW', _stereoW);
      _reverse = _b(m, 'reverse', _reverse);
      _noiseReduc = _d(m, 'noiseReduc', _noiseReduc);
      _compress = _b(m, 'compress', _compress);
      _compThresh = _d(m, 'compThresh', _compThresh);
      _compRatio = _d(m, 'compRatio', _compRatio);
      _compAttack = _d(m, 'compAttack', _compAttack);
      _compRelease = _d(m, 'compRelease', _compRelease);
      _compMakeup = _d(m, 'compMakeup', _compMakeup);
      _declick = _b(m, 'declick', _declick);
      _declickSens = _d(m, 'declickSens', _declickSens);
      _reverbType = (m['reverbType'] as String?) ?? _reverbType;
      _loudnessTarget = (m['loudnessTarget'] as String?) ?? _loudnessTarget;
      _truePeakLimiter = _b(m, 'truePeakLimiter', _truePeakLimiter);
      _bassBoost = _d(m, 'bassBoost', _bassBoost);
      _trebleBoost = _d(m, 'trebleBoost', _trebleBoost);
      _subBass = _d(m, 'subBass', _subBass);
      _presence = _d(m, 'presence', _presence);
      _hpFreq = _d(m, 'hpFreq', _hpFreq);
      _lpFreq = _d(m, 'lpFreq', _lpFreq);
      _tremolo = _d(m, 'tremolo', _tremolo);
      _vibrato = _d(m, 'vibrato', _vibrato);
      _chorus = _b(m, 'chorus', _chorus);
      _flanger = _b(m, 'flanger', _flanger);
      _phaser = _b(m, 'phaser', _phaser);
      _crusher = _d(m, 'crusher', _crusher);
      _haasWiden = _b(m, 'haasWiden', _haasWiden);
      _stereoFx = _d(m, 'stereoFx', _stereoFx);
      _channelMode = (m['channelMode'] as String?) ?? _channelMode;
      _swapLR = _b(m, 'swapLR', _swapLR);
      _dehumOn = _b(m, 'dehumOn', _dehumOn);
      _dehumBase = (m['dehumBase'] as num?)?.toInt() ?? _dehumBase;
      _dehumStrength = _d(m, 'dehumStrength', _dehumStrength);
      _vocalIso = _d(m, 'vocalIso', _vocalIso);
      _noiseGate = _b(m, 'noiseGate', _noiseGate);
      _gateThresh = _d(m, 'gateThresh', _gateThresh);
      _deEsser = _d(m, 'deEsser', _deEsser);
      _declip = _b(m, 'declip', _declip);
      _autoNormalize = _b(m, 'autoNormalize', _autoNormalize);
      _limiter = _b(m, 'limiter', _limiter);
      _limiterCeil = _d(m, 'limiterCeil', _limiterCeil);
      _autoTrimSilence = _b(m, 'autoTrimSilence', _autoTrimSilence);
      _padStart = _d(m, 'padStart', _padStart);
      _padEnd = _d(m, 'padEnd', _padEnd);
      _harmonicFocus = _d(m, 'harmonicFocus', _harmonicFocus);
      _aiDenoiseOn = _b(m, 'aiDenoiseOn', _aiDenoiseOn);
      _aiDenoiseStrength = _d(m, 'aiDenoiseStrength', _aiDenoiseStrength);
      _aiDenoiseNonStat = _b(m, 'aiDenoiseNonStat', _aiDenoiseNonStat);
      _vadTrimOn = _b(m, 'vadTrimOn', _vadTrimOn);
      _vadAggr = _d(m, 'vadAggr', _vadAggr);
      _dereverb = _d(m, 'dereverb', _dereverb);
      _squeezeOn = _b(m, 'squeezeOn', _squeezeOn);
      _squeezeMax = _d(m, 'squeezeMax', _squeezeMax);
      _squeezeKeep = _d(m, 'squeezeKeep', _squeezeKeep);
      _silThresh = _d(m, 'silThresh', _silThresh);
      _silMin = _d(m, 'silMin', _silMin);
      _fmt = (m['fmt'] as String?) ?? _fmt;
      _kbps = (m['kbps'] as num?)?.toInt() ?? _kbps;
      _sampleRate = (m['sampleRate'] as num?)?.toInt() ?? _sampleRate;
      _channels = (m['channels'] as String?) ?? _channels;
      _wavBitDepth = (m['wavBitDepth'] as num?)?.toInt() ?? _wavBitDepth;
      _asRingtone = _b(m, 'asRingtone', _asRingtone);
      _metaTitle = (m['metaTitle'] as String?) ?? _metaTitle;
      _metaArtist = (m['metaArtist'] as String?) ?? _metaArtist;
      _metaAlbum = (m['metaAlbum'] as String?) ?? _metaAlbum;
    });
    _syncMetaControllers();
  }

  void _pushUndo() {
    _undo.add(_snapshotAll());
    if (_undo.length > _kUndoDepth) _undo.removeAt(0);
    if (_redo.isNotEmpty) _redo.clear();
  }

  /// Snapshot-then-mutate. Use for anything that isn't a slider drag.
  void _edit(VoidCallback fn) {
    _pushUndo();
    setState(fn);
  }

  void _undoOnce() {
    if (_undo.isEmpty) return;
    HapticFeedback.selectionClick();
    _redo.add(_snapshotAll());
    _restoreAll(_undo.removeLast());
  }

  void _redoOnce() {
    if (_redo.isEmpty) return;
    HapticFeedback.selectionClick();
    _undo.add(_snapshotAll());
    _restoreAll(_redo.removeLast());
  }

  // S237 QoL — jump the playhead by ±N seconds from the transport bar
  Future<void> _seekBy(double deltaSec) async {
    if (_filePath == null) return;
    HapticFeedback.selectionClick();
    // S250 — seek within whichever timeline is actually loaded
    final total = _previewMode && !_previewIsOriginalAb ? _previewLenSec : _durationSec;
    if (total <= 0) return;
    final cur = _previewMode && !_previewIsOriginalAb ? _previewPosSec : _positionSec;
    final target = (cur + deltaSec).clamp(0.0, total);
    await _player.seek(Duration(milliseconds: (target * 1000).round()));
    if (!mounted) return;
    setState(() {
      if (_previewMode && !_previewIsOriginalAb) {
        _previewPosSec = target;
      } else {
        _positionSec = target;
      }
    });
  }

  // ── SPLIT ─────────────────────────────────────────────────────────────────
  Future<void> _split() async {
    if (_filePath == null) return;
    if (_busy) { _warnBusy(); return; }
    final ar = LangProvider.strings(context).ar;
    // S250 — splitting at 0:00 (or past the end) produced one empty file and
    // one copy, reported as success. Require a real cut point.
    if (_previewMode) {
      _snack(ar ? 'اخرج من المعاينة أولًا' : 'Exit preview first', color: _gold);
      return;
    }
    if (_durationSec <= 0 || _positionSec < 0.25 || _positionSec > _durationSec - 0.25) {
      _snack(ar ? 'حرّك مؤشر التشغيل إلى موضع القص أولًا'
                : 'Move the playhead to where you want the cut first', color: _gold);
      return;
    }
    if (!await _checkSetup()) return;
    HapticFeedback.mediumImpact();
    setState(() { _busy = true; _busyStart = DateTime.now();
      _busyLabel = ar ? 'جارٍ التقسيم…' : 'Splitting…'; _pct = 0.1; });
    String? inp;
    try {
      inp = await _safeInput(_filePath!);
      final ext = _fmt.toLowerCase();
      final outA = await _outFile('part1', ext);
      final outB = await _outFile('part2', ext);
      final sp   = _positionSec.toStringAsFixed(3);
      final r1 = await _proot('ffmpeg -y -i "$inp" -t $sp -acodec ${_codec()} ${_br()} "$outA"', inp, outA);
      if ((r1?['rc'] as int? ?? 1) != 0) throw Exception('Split part1 failed: ${r1?['out'] ?? ''}');
      if (!mounted) return;
      setState(() => _pct = 0.6);
      final r2 = await _proot('ffmpeg -y -ss $sp -i "$inp" -acodec ${_codec()} ${_br()} "$outB"', inp, outB);
      if ((r2?['rc'] as int? ?? 1) != 0) throw Exception('Split part2 failed: ${r2?['out'] ?? ''}');
      if (!mounted) return;
      setState(() { _pct = 1.0; _busy = false; });
      _snack('✓ ${ar ? "تم التقسيم" : "Split"}: part1.$ext + part2.$ext');
    } catch (e) {
      if (mounted) setState(() => _busy = false);
      _snackError(e);
    } finally {
      _dropTemp(inp);
      if (mounted && _busy) setState(() => _busy = false);
    }
  }

  // ── S238: SPLIT BY SILENCE — cut a recitation into pieces at the pauses ──
  // Runs the Studio Engine's --split mode: detects pauses longer than
  // _silMin below _silThresh dB and writes one file per spoken segment —
  // made for cutting a long recitation into ayah-sized files.
  Future<void> _splitBySilence() async {
    if (_filePath == null) return;
    if (_busy) { _warnBusy(); return; }
    if (!await _checkSetup()) return;
    if (!mounted) return;
    HapticFeedback.mediumImpact();
    final ar = LangProvider.strings(context).ar;
    setState(() { _busy = true; _busyStart = DateTime.now();
      _busyLabel = ar ? 'تقسيم عند السكتات…' : 'Splitting at pauses…'; _pct = 0.1; });
    String? inp;
    try {
      inp    = await _safeInput(_filePath!);
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
      _snackError(e);
    } finally {
      _dropTemp(inp);
      if (mounted && _busy) setState(() => _busy = false);
    }
  }

  // ── MERGE ─────────────────────────────────────────────────────────────────
  Future<void> _merge() async {
    if (_filePath == null || _mergePath == null) return;
    if (_busy) { _warnBusy(); return; }
    if (!await _checkSetup()) return;
    if (!mounted) return;
    HapticFeedback.mediumImpact();
    final ar = LangProvider.strings(context).ar;
    setState(() { _busy = true; _busyStart = DateTime.now();
      _busyLabel = ar ? 'جارٍ الدمج…' : 'Merging…'; _pct = 0.1; });
    final scratch = <String>[];
    try {
      final tmp  = await getTemporaryDirectory();
      final stamp = DateTime.now().millisecondsSinceEpoch;
      final inpA = await _safeInput(_filePath!);
      final inpB = await _safeInput(_mergePath!);
      // S250: these were fixed names (tl_mA/tl_mB/tl_list), so a second merge
      // reused stale intermediates, and none of them were ever deleted.
      final wavA = '${tmp.path}/tl_mA_$stamp.wav';
      final wavB = '${tmp.path}/tl_mB_$stamp.wav';
      final list = '${tmp.path}/tl_list_$stamp.txt';
      scratch.addAll([inpA, inpB, wavA, wavB, list]);
      final ext  = _fmt.toLowerCase();
      final out  = await _outFile('merged', ext);
      // S250: both decodes ignored their exit codes, so a bad second file
      // surfaced as an opaque concat error about a file that was never written.
      final rA = await _proot('ffmpeg -y -i "$inpA" -ar 48000 -ac 2 "$wavA"', inpA, wavA);
      if ((rA?['rc'] as int? ?? 1) != 0 || !File(wavA).existsSync()) {
        throw Exception('Could not decode "$_fileName": ${rA?['out'] ?? ''}');
      }
      if (!mounted) return;
      setState(() => _pct = 0.3);
      final rB = await _proot('ffmpeg -y -i "$inpB" -ar 48000 -ac 2 "$wavB"', inpB, wavB);
      if ((rB?['rc'] as int? ?? 1) != 0 || !File(wavB).existsSync()) {
        throw Exception('Could not decode "$_mergeName": ${rB?['out'] ?? ''}');
      }
      if (!mounted) return;
      setState(() => _pct = 0.5);
      final fa = _mergeAppend ? wavA : wavB; final fb = _mergeAppend ? wavB : wavA;
      File(list).writeAsStringSync("file '$fa'\nfile '$fb'\n");
      // S250: merge now honours the Export tab's rate/channels/metadata too —
      // it used to emit whatever the 48k stereo intermediates happened to be.
      final r = await _proot(
          'ffmpeg -y -f concat -safe 0 -i "$list" ${_metaArgs()} '
          '-ar $_sampleRate -ac ${_channels == "Mono" ? 1 : 2} '
          '-acodec ${_codec()} ${_br()} "$out"',
          list, out, timeout: 15);
      if ((r?['rc'] as int? ?? 1) != 0 || !File(out).existsSync()) {
        throw Exception('Merge failed: ${r?['out'] ?? ''}');
      }
      if (!mounted) return;
      setState(() { _pct = 1.0; _busy = false; _outPath = out; });
      _snack('✓ ${ar ? "تم الدمج" : "Merged"} → $out');
    } catch (e) {
      if (mounted) setState(() => _busy = false);
      _snackError(e);
    } finally {
      for (final p in scratch) {
        _dropTemp(p);
      }
      if (mounted && _busy) setState(() => _busy = false);
    }
  }

  // ── EXPORT ────────────────────────────────────────────────────────────────
  String _codec() => _fmt == 'WAV'
      ? (_wavBitDepth == 24 ? 'pcm_s24le' : _wavBitDepth == 32 ? 'pcm_s32le' : 'pcm_s16le')
      : _fmt == 'M4A' ? 'aac' : 'libmp3lame';
  String _br()    => _fmt == 'WAV' ? '' : '-b:a ${_kbps}k';

  // S229 — shared -metadata flags for both single export and batch export.
  // S250: these are interpolated into a shell command line, and the old
  // escaping only swapped double quotes for single ones — so a title
  // containing $, `, \ or a newline was expanded by the shell (at best
  // mangling the tag, at worst running the substitution). Single-quote the
  // value instead and escape embedded single quotes the POSIX way, which
  // leaves nothing for the shell to interpret.
  static String _shQuote(String v) {
    final clean = v.replaceAll(RegExp(r'[\r\n]'), ' ').trim();
    return "'${clean.replaceAll("'", r"'\''")}'";
  }

  String _metaArgs() {
    final parts = <String>[];
    if (_metaTitle.isNotEmpty)  parts.add('-metadata title=${_shQuote(_metaTitle)}');
    if (_metaArtist.isNotEmpty) parts.add('-metadata artist=${_shQuote(_metaArtist)}');
    if (_metaAlbum.isNotEmpty)  parts.add('-metadata album=${_shQuote(_metaAlbum)}');
    return parts.join(' ');
  }

  List<String> _buildAf() {
    final af = <String>[];
    if (_reverse) af.add('areverse');
    // S229 — auto-trim leading/trailing silence, before any other shaping
    if (_autoTrimSilence) {
      af.add('silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.08:'
          'stop_periods=-1:stop_threshold=-45dB:stop_silence=0.08');
    }
    if (_noiseReduc > 0) {
      af.add('afftdn=nr=${(_noiseReduc * 0.97).toStringAsFixed(1)}:nf=-25');
    }
    if (_declip) af.add('adeclip');
    if (_noiseGate) {
      af.add('agate=threshold=${_gateThresh.toStringAsFixed(0)}dB:ratio=6:attack=5:release=150');
    }
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
      if (_eq[i].abs() > 0.5) {
        af.add('equalizer=f=${_freqs[i]}:g=${_eq[i].toStringAsFixed(1)}');
      }
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
    if (_crusher > 0) {
      af.add('acrusher=bits=${(16 - (_crusher/100*11)).round()}:mode=log:aa=1');
    }
    if (_stereoW != 1.0) af.add('stereotools=mlev=${_stereoW.toStringAsFixed(2)}');
    // S229 — stereo & space
    if (_haasWiden) af.add('haas');
    if (_stereoFx != 0) {
      af.add('extrastereo=m=${(1 + _stereoFx/100).toStringAsFixed(2)}:c=0');
    }
    if (_swapLR) af.add('pan=stereo|c0=c1|c1=c0');
    if (_channelMode == 'Mono')  af.add('pan=mono|c0=0.5*c0+0.5*c1');
    if (_channelMode == 'Left')  af.add('pan=stereo|c0=c0|c1=c0');
    if (_channelMode == 'Right') af.add('pan=stereo|c0=c1|c1=c1');
    if (_compress) {
      af.add('acompressor=threshold=${_compThresh.toStringAsFixed(1)}dB'
          ':ratio=${_compRatio.toStringAsFixed(1)}:attack=20:release=200');
    }
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
    // S255: v5 — bumped for --compare. MUST change whenever the bundled
    // script changes, because the
    // cached copy is reused as-is when it exists. A stale v3 copy would keep
    // running the old engine (no --libs mode, no dereverb/squeeze/harmonic
    // focus, no progress sidecar) even after the app updated, and the new
    // params would be silently ignored.
    final dst  = File('${dir.path}/tilawa_dsp_studio_v5.py');
    final data = await rootBundle.load('assets/dsp/tilawa_dsp_studio.py');
    await dst.writeAsBytes(data.buffer.asUint8List(data.offsetInBytes, data.lengthInBytes), flush: true);
    _dspScriptPath = dst.path;
    return dst.path;
  }

  Map<String, dynamic> _buildDspParams({double? previewStart, double? previewDur,
      bool fullFile = false, String? progressPath}) {
    final isPreview = previewStart != null;
    // S236: batch export processes each picked file in full — the trim window
    // belongs to the currently loaded file only.
    final ss  = fullFile ? 0.0 : isPreview ? previewStart : (_trimStart * _durationSec);
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
        // S248 — Cleanup tab
        'ai_denoise': {'enabled': _aiDenoiseOn, 'strength': _aiDenoiseStrength,
                       'non_stationary': _aiDenoiseNonStat},
        'vad_trim': {'enabled': _vadTrimOn, 'aggressiveness': _vadAggr.round()},
        // S250 — Cleanup tab: nara_wpe dereverb, pause squeeze, HPSS focus
        'dereverb': {'strength': _dereverb, 'taps': 10, 'delay': 3},
        'pause_squeeze': {'enabled': _squeezeOn, 'max_pause_s': _squeezeMax,
                          'keep_s': _squeezeKeep},
        'harmonic_focus': _harmonicFocus,
        'pad_start_sec': _padStart, 'pad_end_sec': _padEnd,
      },
      if (progressPath != null) 'progress_path': progressPath,
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

  /// S250 — temp path for the engine's progress sidecar (polled by the UI).
  Future<String> _progressFilePath() async {
    final tmp = await getTemporaryDirectory();
    return '${tmp.path}/tl_progress_${DateTime.now().millisecondsSinceEpoch}.txt';
  }

  // S238 QoL — A/B: hear the untouched original from the same spot the last
  // Studio preview started, so processed vs. original is a two-tap compare.
  Future<void> _playOriginalSlice() async {
    if (_filePath == null) return;
    HapticFeedback.selectionClick();
    final ar = LangProvider.strings(context).ar;
    try {
      if (_playing) await _player.stop();
      await _player.setSource(DeviceFileSource(_filePath!));
      await _player.seek(Duration(milliseconds: (_lastPreviewStart * 1000).round()));
      await _player.resume();
      if (!mounted) return;
      // S250 — A/B plays the real file, so leave preview mode: positions are
      // genuine source positions again and the waveform playhead is correct.
      setState(() {
        _previewMode = false;
        _previewIsOriginalAb = false;
        _positionSec = _lastPreviewStart;
      });
      _snack(ar ? '▶ الأصلي (بدون معالجة)' : '▶ Original (unprocessed)', color: _gold);
    } catch (e) {
      _snack('A/B error: $e', color: _red);
    }
  }

  /// Renders a short slice (current playhead, or trim start) through the
  /// Studio Engine with the live settings, so the user can audition before
  /// committing to a full export. "Preview" = quick audition, not a visual.
  Future<void> _previewDsp() async {
    if (_filePath == null) return;
    if (!await _checkSetup()) return;
    if (_dspBusy || _busy) return;
    if (!mounted) return;
    HapticFeedback.selectionClick();
    final ar = LangProvider.strings(context).ar;
    setState(() => _dspBusy = true);
    String? inp;
    try {
      if (_playing) await _player.stop();
      inp = await _safeInput(_filePath!);
      final tmp = await getTemporaryDirectory();
      final out = '${tmp.path}/tl_preview_${DateTime.now().millisecondsSinceEpoch}.wav';
      final rangeEnd   = _trimEnd * _durationSec;
      final rangeStart = _trimStart * _durationSec;
      // S250 — with preview mode fixed, _positionSec is always a real source
      // position here, so "audition from the playhead" finally works as meant.
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
      await _readRunReport(out);
      if (!mounted) return;
      setState(() {
        _previewMode = true;              // S250 — explicit, exitable mode
        _previewIsOriginalAb = false;
        _previewLenSec = dur;
        _previewPosSec = 0;
      });
      await _player.setSource(DeviceFileSource(out));
      await _player.resume();
      _snack(ar
          ? '▶ معاينة ${dur.toStringAsFixed(1)} ثانية بالإعدادات الحالية'
          : '▶ Previewing ${dur.toStringAsFixed(1)}s with current settings', color: _teal);
    } catch (e) {
      _snack('Preview error: $e', color: _red);
    } finally {
      _dropTemp(inp);
      if (mounted) setState(() => _dspBusy = false);
    }
  }

  Future<void> _export() async {
    if (_filePath == null) return;
    if (_busy) { _warnBusy(); return; }
    if (_durationSec <= 0) {
      final ar = LangProvider.strings(context).ar;
      _snack(ar ? 'لم تُقرأ مدة الملف بعد' : 'File duration not read yet', color: _red);
      return;
    }
    if (!await _checkSetup()) return;
    if (!mounted) return;
    HapticFeedback.mediumImpact();
    final ar = LangProvider.strings(context).ar;
    setState(() { _busy = true; _busyStart = DateTime.now(); _pct = 0.05;
      _outPath = null; _busyLabel = ar ? 'جارٍ التصدير…' : 'Exporting…'; });
    String? inp;
    try {
      inp = await _safeInput(_filePath!);
      final ext = _fmt.toLowerCase();
      final out = await _outFile('edited', ext);
      if (!mounted) return;
      setState(() => _pct = 0.15);
      final progress = await _progressFilePath();
      _startProgressPolling(progress);              // S250 — real stage progress
      final params = _buildDspParams(progressPath: progress);
      final r = await _runDspEngine(inp, out, params);
      _stopProgressPolling();
      await _readRunReport(out);
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
        try {
          await _media.invokeMethod('saveToDownloads',
              {'path': out, 'filename': out.split('/').last});
        } catch (e) {
          // S250: this was swallowed silently — the user ticked "Set as
          // Ringtone", nothing landed in Downloads, and nothing said why.
          _snack(ar ? 'تم التصدير، لكن النسخ إلى التنزيلات فشل: $e'
                    : 'Exported, but copying to Downloads failed: $e', color: _gold);
        }
      }
      _snack('✓ ${ar ? "تم الحفظ" : "Saved"}: $out');
    } catch (e) {
      if (mounted) setState(() => _busy = false);
      _snackError(e);
    } finally {
      _stopProgressPolling();
      _dropTemp(inp);
      if (mounted && _busy) setState(() => _busy = false);
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
    child: AnimatedBuilder(animation: Listenable.merge([_glowCtrl, _waveCtrl]),
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
              // S250d — a counter-rotating sweep on top of the progress ring,
              // so a long DSP stage still looks like it is doing something even
              // while the determinate value sits still between stage ticks.
              SizedBox(width: 84, height: 84,
                child: Transform.rotate(
                  angle: -_waveCtrl.value * 2 * pi,
                  child: CustomPaint(
                      painter: _SweepPainter(t: _waveCtrl.value)))),
              AnimatedScale(
                duration: const Duration(milliseconds: 400),
                scale: 0.94 + 0.06 * _glowCtrl.value,
                child: const Icon(Icons.audio_file_rounded, color: _gold, size: 26)),
            ])),
          const SizedBox(height: 18),
          Padding(padding: const EdgeInsets.symmetric(horizontal: 24),
            child: Text(_busyLabel, textAlign: TextAlign.center,
                maxLines: 2, overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: _gold, fontSize: 18, fontWeight: FontWeight.w800))),
          const SizedBox(height: 5),
          // S250 — the current DSP stage, straight from the engine's tqdm
          // sidecar. Previously a long export showed one static label and an
          // indeterminate bar, with no way to tell progress from a hang.
          if (_stageLabel.isNotEmpty)
            Padding(padding: const EdgeInsets.only(bottom: 4),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                const Icon(Icons.memory_rounded, color: _teal, size: 12),
                const SizedBox(width: 5),
                Text(_stageLabel, style: const TextStyle(color: _teal, fontSize: 12,
                    fontWeight: FontWeight.w700, fontFamily: 'monospace')),
              ])),
          Text(
              LangProvider.strings(context).ar
                  ? 'انتظر قليلًا — لا تُغلق الشاشة'
                  : "Please wait — don't close the screen",
              style: const TextStyle(color: _textB, fontSize: 12)),
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
              '• تنظيف: إزالة صدى القاعة (WPE)، إزالة ضوضاء (noisereduce)، تنقية العابرات، '
              'قص بكشف الصوت (VAD)، وتقصير السكتات الطويلة داخل التسجيل.\n'
              '• قراءة الملف: طبقة الصوت والسطوع والإيقاع ونسبة الكلام وعدد السكتات، '
              'مع زر إصلاح لكل ملاحظة.\n'
              '• تراجع/إعادة: كل تغيير قابل للتراجع من الشريط السفلي.\n'
              '• مكتبات المحرك: تبويب استوديو يعرض أي حزم الصوت الـ١٤ متوفرة على جهازك.\n'
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
              '• Cleanup: room dereverb (WPE), noise reduction (noisereduce), transient '
              'cleanup, voice-activity trim (VAD), and squeezing of over-long pauses inside '
              'the recording.\n'
              '• What\'s in this file: voice pitch, brightness, pace, speech ratio and pause '
              'count — each with a one-tap fix.\n'
              '• Undo/redo: every change is reversible from the bottom bar.\n'
              '• Engine Libraries: the Studio tab shows which of the 14 embedded audio '
              'packages are live on your device.\n'
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
      AnimatedBuilder(
        animation: Listenable.merge([_glowCtrl, _waveCtrl]),
        builder: (_, __) => SizedBox(width: 168, height: 168,
          child: Stack(alignment: Alignment.center, children: [
            // S250g — a ring that slowly traces the disc, so the empty state
            // reads as ready rather than as a frozen screenshot
            SizedBox(width: 156, height: 156,
              child: Transform.rotate(
                angle: _waveCtrl.value * 2 * pi,
                child: CustomPaint(painter: _SweepPainter(t: _waveCtrl.value)))),
            Container(width: 130, height: 130,
              decoration: BoxDecoration(shape: BoxShape.circle, color: _card,
                border: Border.all(color: _gold.withValues(alpha: 0.18 + 0.28 * _glowCtrl.value), width: 1.5),
                boxShadow: [BoxShadow(color: _gold.withValues(alpha: 0.04 + 0.08 * _glowCtrl.value), blurRadius: 36)]),
              child: Transform.scale(
                scale: 0.96 + 0.05 * _glowCtrl.value,
                child: const Icon(Icons.audio_file_rounded, color: _gold, size: 52))),
          ]))),
      const SizedBox(height: 24),
      Text(ar ? 'اختر ملف صوتي' : 'Choose an audio file',
          style: const TextStyle(color: _textA, fontSize: 20, fontWeight: FontWeight.w700)),
      const SizedBox(height: 8),
      const Text('MP3 · WAV · M4A · AAC · OGG · FLAC',
          style: TextStyle(color: _textB, fontSize: 13)),
      const SizedBox(height: 32),
      PressScale(onTap: _pick,
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
    _actionBar(),
  ]);

  // S250 — the audition controls used to live in a bar shown on only four of
  // the ten tabs (`_tab == eq || effects || fx2 || studio`), so from Trim,
  // Cleanup, Compliance, Quality, Merge or Export there was no way to hear
  // your settings or start an export without first navigating elsewhere — even
  // though Cleanup's controls feed the very same pipeline. It is now a
  // persistent bottom bar, and carries undo/redo plus a live count of engaged
  // processing so the state of the edit is always visible.
  // Layout note (S250): this bar carries five controls plus a status readout —
  // exactly the shape that overflowed twice in S244. Two guarantees, both
  // verified by the render test in test/widget_test.dart (which caught an 81 px
  // overflow in the first draft of this bar, and then a 29 px one in the
  // second — a FittedBox placed in a Row's *inflexible* slot receives unbounded
  // main-axis constraints and therefore never scales at all):
  //   1. below ~340 dp of usable width the chips drop their text labels and
  //      become icon-only, so the fixed cost shrinks with the screen;
  //   2. everything except the undo/redo pair lives inside ONE
  //      Expanded → FittedBox(scaleDown). Expanded bounds the width, which is
  //      what lets FittedBox measure and scale, so no font metric, locale or
  //      system text scale can push content off-screen.
  // Exactly one flexible child, so there is no flex-vs-flex competition (the
  // other mistake S244 documents).
  Widget _actionBar() {
    final ar = LangProvider.strings(context).ar;
    final on = _dspOnCount();
    final canPreview = _filePath != null && !_dspBusy && !_busy;
    final canExport = _filePath != null && !_busy;
    return Container(
      decoration: BoxDecoration(
        color: _surface,
        border: Border(top: BorderSide(color: _gold.withValues(alpha: 0.18))),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.3),
            blurRadius: 12, offset: const Offset(0, -3))]),
      padding: const EdgeInsets.fromLTRB(10, 7, 10, 7),
      child: LayoutBuilder(builder: (ctx, cons) {
        final compact = cons.maxWidth < 340;
        return Row(children: [
          _barIconBtn(Icons.undo_rounded, _undo.isNotEmpty ? _undoOnce : null,
              ar ? 'تراجع' : 'Undo'),
          const SizedBox(width: 4),
          _barIconBtn(Icons.redo_rounded, _redo.isNotEmpty ? _redoOnce : null,
              ar ? 'إعادة' : 'Redo'),
          const SizedBox(width: 8),
          Expanded(child: FittedBox(
            fit: BoxFit.scaleDown,
            alignment: AlignmentDirectional.centerEnd,
            child: Row(mainAxisSize: MainAxisSize.min, children: [
              Column(crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min, children: [
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(on > 0 ? Icons.tune_rounded : Icons.horizontal_rule_rounded,
                      color: on > 0 ? _teal : _textDim, size: 12),
                  const SizedBox(width: 4),
                  Text(
                      on == 0
                          ? (ar ? 'بدون معالجة' : 'No processing')
                          : (ar ? '$on إعداد مفعّل' : '$on setting${on == 1 ? "" : "s"} on'),
                      maxLines: 1,
                      style: TextStyle(color: on > 0 ? _teal : _textDim,
                          fontSize: 10.5, fontWeight: FontWeight.w700)),
                ]),
                if (!compact)
                  Text(ar ? 'محرك الاستوديو (numpy/scipy)' : 'Studio Engine · numpy/scipy',
                      maxLines: 1,
                      style: const TextStyle(color: _textDim, fontSize: 9)),
              ]),
              const SizedBox(width: 12),
              _barChip(
                  icon: Icons.compare_arrows_rounded,
                  label: compact ? null : (ar ? 'أصلي' : 'A/B'),
                  color: _gold, bg: _goldDim.withValues(alpha: 0.35),
                  tip: ar ? 'الأصلي' : 'A/B — hear the original',
                  onTap: canPreview ? _playOriginalSlice : null),
              const SizedBox(width: 6),
              _barChip(
                  icon: Icons.headphones_rounded,
                  label: compact ? null : (ar ? 'معاينة' : 'Preview'),
                  color: _teal, bg: _tealDk, busy: _dspBusy,
                  tip: ar ? 'معاينة ٨ ثوان' : 'Preview 8s',
                  onTap: canPreview ? _previewDsp : null),
              const SizedBox(width: 6),
              Tooltip(message: ar ? 'معالجة وتصدير' : 'Process & Export',
                child: _pressable(
                  onTap: canExport ? _export : null,
                  child: Opacity(opacity: canExport ? 1 : 0.4,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 9),
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(colors: [Color(0xFF6B4F10), _gold],
                            begin: Alignment.centerRight, end: Alignment.centerLeft),
                        borderRadius: BorderRadius.circular(20)),
                      child: Row(mainAxisSize: MainAxisSize.min, children: [
                        const Icon(Icons.ios_share_rounded, color: Color(0xFF0A0A00), size: 14),
                        const SizedBox(width: 5),
                        Text(ar ? 'تصدير' : 'Export',
                            style: const TextStyle(color: Color(0xFF0A0A00), fontSize: 12,
                                fontWeight: FontWeight.w800)),
                      ]))),
                )),
            ])),
          ),
        ]);
      }));
  }

  /// S250d — press feedback. A tap on a flat container gave no acknowledgement
  /// at all before the (often slow) action started, which reads as a dropped
  /// tap. Scales down while held, springs back on release.
  Widget _pressable({required Widget child, VoidCallback? onTap}) =>
      PressScale(onTap: onTap, child: child);

  Widget _barIconBtn(IconData icon, VoidCallback? onTap, String tip) => Tooltip(
    message: tip,
    child: GestureDetector(
      onTap: onTap,
      child: Container(width: 32, height: 32,
        decoration: BoxDecoration(shape: BoxShape.circle, color: _card,
            border: Border.all(color: onTap == null ? _border : _teal.withValues(alpha: 0.4))),
        child: Icon(icon, size: 16, color: onTap == null ? _textDim : _teal))));

  Widget _barChip({required IconData icon, String? label,
      required Color color, required Color bg, VoidCallback? onTap,
      bool busy = false, String? tip}) {
    final chip = _pressable(
      onTap: onTap,
      child: Opacity(opacity: onTap == null ? 0.4 : 1,
        child: Container(
          padding: EdgeInsets.symmetric(horizontal: label == null ? 9 : 11, vertical: 9),
          decoration: BoxDecoration(color: bg,
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: color.withValues(alpha: 0.5))),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            if (busy)
              SizedBox(width: 14, height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2, color: color))
            else
              Icon(icon, color: color, size: 15),
            if (label != null) ...[
              const SizedBox(width: 5),
              Text(label, style: TextStyle(color: color, fontSize: 12,
                  fontWeight: FontWeight.w700)),
            ],
          ]))));
    return tip == null ? chip : Tooltip(message: tip, child: chip);
  }

  static String _fmtBytes(int b) {
    if (b <= 0) return '';
    if (b < 1024) return '$b B';
    if (b < 1024 * 1024) return '${(b / 1024).toStringAsFixed(0)} KB';
    return '${(b / 1048576).toStringAsFixed(1)} MB';
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
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min, children: [
        Text(_fileName, overflow: TextOverflow.ellipsis, maxLines: 1,
            style: const TextStyle(color: _textA, fontSize: 13, fontWeight: FontWeight.w600)),
        // S250 — size + format at a glance
        if (_fileBytes > 0)
          Text('${_fmtBytes(_fileBytes)}'
              '${_fileName.contains('.') ? ' · ${_fileName.split('.').last.toUpperCase()}' : ''}',
              style: const TextStyle(color: _textDim, fontSize: 9.5)),
      ])),
      const SizedBox(width: 10),
      Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(8),
            border: Border.all(color: _border)),
        child: Text(_fmtTime(_durationSec),
            style: const TextStyle(color: _textB, fontSize: 11.5, fontFamily: 'monospace'))),
    ]));

  // S250 — which waveform element a drag grabbed
  static const double _kHandleGrabPx = 26.0;
  int _dragTarget = 0;   // 0 = none/seek, 1 = trim start, 2 = trim end

  void _onWaveDown(double dx, double w) {
    if (w <= 0) return;
    final sx = _trimStart * w;
    final ex = _trimEnd * w;
    // grab whichever handle is nearest, if the touch is close enough to one
    final dStart = (dx - sx).abs();
    final dEnd = (dx - ex).abs();
    if (dStart <= _kHandleGrabPx && dStart <= dEnd) {
      _dragTarget = 1;
      _pushUndo();
    } else if (dEnd <= _kHandleGrabPx) {
      _dragTarget = 2;
      _pushUndo();
    } else {
      _dragTarget = 0;
    }
    if (_dragTarget != 0) _grabCtrl.forward();   // S250d
  }

  void _onWaveDrag(double dx, double w) {
    if (w <= 0 || _dragTarget == 0) return;
    final frac = (dx / w).clamp(0.0, 1.0);
    setState(() {
      if (_dragTarget == 1) {
        _trimStart = frac.clamp(0.0, (_trimEnd - 0.005).clamp(0.0, 1.0));
      } else {
        _trimEnd = frac.clamp((_trimStart + 0.005).clamp(0.0, 1.0), 1.0);
      }
    });
  }

  Future<void> _seekFrac(double frac) async {
    if (_durationSec <= 0) return;
    if (_previewMode) await _exitPreview(silent: true);
    final target = frac.clamp(0.0, 1.0) * _durationSec;
    await _player.seek(Duration(milliseconds: (target * 1000).round()));
    if (mounted) setState(() => _positionSec = target);
  }

  /// S250i — the real audio level at the playhead, 0..1.
  ///
  /// This is what makes the waveform animation actually respond to the audio:
  /// the numpy `--analyze` pass already produced per-bucket peak and RMS for
  /// the whole file, so the level under the playhead is a lookup rather than
  /// anything that needs live PCM taps (audioplayers exposes no PCM or FFT
  /// stream, so a visualiser would otherwise need a second native plugin).
  /// RMS is weighted higher than peak because it tracks perceived loudness;
  /// the value is smoothed toward its target so the motion doesn't strobe on
  /// bucket boundaries.
  double _levelAtPlayhead() {
    if (!_analyzed || _durationSec <= 0) return 0.0;
    final bars = _barsTo.isNotEmpty ? _barsTo : _bars;
    if (bars.isEmpty) return 0.0;
    final frac = (_positionSec / _durationSec).clamp(0.0, 1.0);
    final i = (frac * bars.length).floor().clamp(0, bars.length - 1);
    final peak = bars[i];
    final rms = (_rmsBars != null && i < _rmsBars!.length) ? _rmsBars![i] : peak * 0.6;
    return (0.35 * peak + 0.65 * rms).clamp(0.0, 1.0);
  }

  double _levelSmoothed = 0;

  Widget _waveformSection() {
    final ar = LangProvider.strings(context).ar;
    final pos = _durationSec > 0 ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0.0;
    // one-pole smoothing: fast attack so a transient still reads, slower
    // release so it decays instead of flickering off
    final target = _playing && !_previewMode ? _levelAtPlayhead() : 0.0;
    _levelSmoothed = target > _levelSmoothed
        ? _levelSmoothed + (target - _levelSmoothed) * 0.55
        : _levelSmoothed + (target - _levelSmoothed) * 0.18;
    return Container(
      margin: const EdgeInsets.fromLTRB(10, 8, 10, 4),
      padding: const EdgeInsets.symmetric(vertical: 6),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _border),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.22),
              blurRadius: 12, offset: const Offset(0, 5))]),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        // S250 — preview banner. Without this, hearing a preview and then
        // looking at the transport was simply confusing: different length,
        // different playhead, no clue why.
        if (_previewMode)
          Padding(padding: const EdgeInsets.fromLTRB(10, 0, 10, 6),
            child: Row(children: [
              const Icon(Icons.headphones_rounded, color: _teal, size: 13),
              const SizedBox(width: 6),
              Expanded(child: Text(
                  ar ? 'تشغيل معاينة (${_previewLenSec.toStringAsFixed(1)} ث) — الملف لم يتغير'
                     : 'Playing a preview (${_previewLenSec.toStringAsFixed(1)}s) — the file is unchanged',
                  style: const TextStyle(color: _teal, fontSize: 10.5, fontWeight: FontWeight.w600))),
              GestureDetector(
                onTap: _exitPreview,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
                  decoration: BoxDecoration(color: _surface,
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(color: _teal.withValues(alpha: 0.5))),
                  child: Text(ar ? 'خروج' : 'Exit',
                      style: const TextStyle(color: _teal, fontSize: 10, fontWeight: FontWeight.w700))),
              ),
            ])),
        ClipRRect(borderRadius: BorderRadius.circular(10),
          // S243: seek used context.findRenderObject() — that's the WHOLE
          // screen's box, not the waveform's, so the tap fraction was scaled by
          // screen width and offset by the card margins (seek landed off). Use
          // the waveform's own width via LayoutBuilder. The wave is drawn
          // left→right in raw canvas coords (not mirrored), so this stays
          // correct in RTL too.
          // S250: the same gesture area now also drags the trim handles — the
          // only way to set a range before this was two sliders on another tab,
          // while looking at the waveform that shows you where to put them.
          child: LayoutBuilder(builder: (ctx, cons) => GestureDetector(
            onTapDown: (d) {
              final w = cons.maxWidth;
              if (w <= 0 || _durationSec <= 0) return;
              _onWaveDown(d.localPosition.dx, w);
              if (_dragTarget == 0) {
                unawaited(_seekFrac(d.localPosition.dx / w));
              }
            },
            onHorizontalDragStart: (d) {
              final w = cons.maxWidth;
              if (w <= 0 || _durationSec <= 0) return;
              _onWaveDown(d.localPosition.dx, w);
              if (_dragTarget != 0) HapticFeedback.selectionClick();
            },
            onHorizontalDragUpdate: (d) => _onWaveDrag(d.localPosition.dx, cons.maxWidth),
            onHorizontalDragEnd: (_) { _dragTarget = 0; _grabCtrl.reverse(); },
            onHorizontalDragCancel: () { _dragTarget = 0; _grabCtrl.reverse(); },
            child: AnimatedBuilder(
              animation: Listenable.merge([_waveCtrl, _grabCtrl]),
              builder: (_, __) => SizedBox(height: 118,
                child: CustomPaint(
                  key: const ValueKey('waveform'),   // S250d: targetable in tests
                  painter: _WavePainter(bars: _bars, rms: _rmsBars, playPos: pos,
                    trimStart: _trimStart, trimEnd: _trimEnd,
                    animT: _waveCtrl.value, playing: _playing && !_previewMode,
                    analyzed: _analyzed, durationSec: _durationSec,
                    dimmed: _previewMode, grab: _grabAnim.value,
                    level: _levelSmoothed),
                  size: const Size(double.infinity, 118))))))),
        // S250 — selection readout right under the wave, where you're looking
        if (_durationSec > 0)
          Padding(padding: const EdgeInsets.fromLTRB(12, 6, 12, 0),
            child: Row(children: [
              const Icon(Icons.content_cut_rounded, color: _teal, size: 11),
              const SizedBox(width: 5),
              Text(
                  '${_fmtTime(_trimStart * _durationSec)} → ${_fmtTime(_trimEnd * _durationSec)}',
                  style: const TextStyle(color: _textB, fontSize: 10,
                      fontFamily: 'monospace')),
              const Spacer(),
              Text(ar ? 'المحدد ' : 'selected ',
                  style: const TextStyle(color: _textDim, fontSize: 9.5)),
              Text(_fmtTime((_trimEnd - _trimStart) * _durationSec),
                  style: const TextStyle(color: _gold, fontSize: 10.5,
                      fontWeight: FontWeight.w800, fontFamily: 'monospace')),
            ])),
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
              // S250i — live level bar while playing, from the analysed buckets
              if (_playing && !_previewMode && _analyzed) ...[
                Container(width: 34, height: 4,
                  decoration: BoxDecoration(
                      color: _border, borderRadius: BorderRadius.circular(2)),
                  alignment: AlignmentDirectional.centerStart,
                  child: FractionallySizedBox(
                    widthFactor: _levelSmoothed.clamp(0.02, 1.0),
                    child: Container(decoration: BoxDecoration(
                        color: Color.lerp(_teal, _gold, _levelSmoothed),
                        borderRadius: BorderRadius.circular(2))))),
                const SizedBox(width: 8),
              ],
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
              if (_previewMode) { await _exitPreview(silent: true); }
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
        // S250 — while a preview plays, the transport describes the PREVIEW
        // (its own position and length), not the source file, and says so.
        FittedBox(fit: BoxFit.scaleDown, alignment: AlignmentDirectional.centerStart,
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            if (_previewMode) ...[
              const Icon(Icons.headphones_rounded, color: _teal, size: 11),
              const SizedBox(width: 3),
            ],
            Text(_fmtTime(_previewMode ? _previewPosSec : _positionSec),
                style: TextStyle(color: _previewMode ? _teal : _gold, fontSize: 11,
                    fontWeight: FontWeight.w600, fontFamily: 'monospace')),
            const Text(' / ', style: TextStyle(color: _textDim, fontSize: 11)),
            Text(_fmtTime(_previewMode ? _previewLenSec : _durationSec),
                style: const TextStyle(color: _textB, fontSize: 11, fontFamily: 'monospace')),
          ])),
        const SizedBox(height: 4),
        ClipRRect(borderRadius: BorderRadius.circular(3),
          child: LinearProgressIndicator(
            value: _previewMode
                ? (_previewLenSec > 0 ? (_previewPosSec / _previewLenSec).clamp(0.0, 1.0) : 0)
                : (_durationSec > 0 ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0),
            backgroundColor: _border,
            valueColor: AlwaysStoppedAnimation(_previewMode ? _teal : _gold),
            minHeight: 3)),
      ])),
    ]));

  Widget _tBtn(IconData icon, VoidCallback onTap, {Color? color}) =>
    GestureDetector(onTap: onTap,
      child: Container(width: 34, height: 34,
        decoration: BoxDecoration(shape: BoxShape.circle, color: _card,
            border: Border.all(color: _border)),
        child: Icon(icon, color: color ?? _textB, size: 17)));

  // S250 REBUILD — the tab strip scrolls.
  // It used to be `Row(children: 10 × Expanded(...))`, which on a 412 dp phone
  // gave each tab ~41 dp: "Compliance" at fontSize 10 needs roughly 55 dp, so
  // the longer labels were clipped mid-word with no way to see the full name
  // and no indication that they even were tabs. A fixed Row also meant adding
  // an eleventh section would squeeze every existing one further.
  // Now each tab sizes to its own content, the strip scrolls horizontally, the
  // selected tab is scrolled into view (so tapping through them never leaves
  // the active one off-screen), and the indicator is drawn inside each tab —
  // no Stack alignment maths that can drift out of sync with the Row, and it
  // follows the Row in RTL for free.
  int _dspOnCount() => [
    _noiseReduc > 0, _compress, _reverse, _pitch != 0, _tempo != 1.0,
    _echo > 0, _reverb > 0, _vol != 1.0, _stereoW != 1.0,
    _fadeIn > 0, _fadeOut > 0, _eq.any((v) => v.abs() > 0.5),
    _bassBoost != 0, _trebleBoost != 0, _subBass > 0, _presence > 0,
    _hpFreq > 0, _lpFreq < 20000, _tremolo > 0, _vibrato > 0,
    _chorus, _flanger, _phaser, _crusher > 0,
    _haasWiden, _stereoFx != 0, _channelMode != 'Stereo', _swapLR,
    _noiseGate, _deEsser > 0, _declip, _autoNormalize, _limiter,
    _autoTrimSilence, _padStart > 0, _padEnd > 0,
    _dehumOn, _vocalIso > 0, _declick,
    _aiDenoiseOn, _vadTrimOn, _dereverb > 0, _squeezeOn, _harmonicFocus > 0,
    _loudnessTarget != 'Off',
  ].where((b) => b).length;

  /// Per-tab count of engaged settings, shown as a small badge so you can see
  /// at a glance which sections are doing something.
  int _tabBadge(_Tab t) {
    switch (t) {
      case _Tab.trim:
        return (_trimStart > 0 || _trimEnd < 1) ? 1 : 0;
      case _Tab.eq:
        return _eq.where((v) => v.abs() > 0.5).length;
      case _Tab.effects:
        return [_vol != 1.0, _pitch != 0, _tempo != 1.0, _stereoW != 1.0,
                _fadeIn > 0, _fadeOut > 0, _echo > 0, _reverb > 0,
                _noiseReduc > 0, _compress, _reverse].where((b) => b).length;
      case _Tab.fx2:
        return [_bassBoost != 0, _trebleBoost != 0, _subBass > 0, _presence > 0,
                _hpFreq > 0, _lpFreq < 20000, _tremolo > 0, _vibrato > 0,
                _chorus, _flanger, _phaser, _crusher > 0, _haasWiden,
                _stereoFx != 0, _channelMode != 'Stereo', _swapLR, _noiseGate,
                _deEsser > 0, _declip, _autoNormalize, _limiter,
                _autoTrimSilence, _padStart > 0, _padEnd > 0, _dehumOn,
                _vocalIso > 0, _harmonicFocus > 0].where((b) => b).length;
      case _Tab.cleanup:
        return [_aiDenoiseOn, _vadTrimOn, _dereverb > 0, _squeezeOn]
            .where((b) => b).length;
      case _Tab.studio:
        return [_declick, _loudnessTarget != 'Off', _eqQ != 1.4,
                _reverbType != 'Room', _fadeCurve != 'Equal Power']
            .where((b) => b).length;
      case _Tab.loudness:
      case _Tab.quality:
        return 0;
      case _Tab.compare:
        // S255: badge when a reference is loaded, the same way Merge badges a
        // picked file — it is the one setting this tab carries.
        return _cmpRefPath != null ? 1 : 0;
      case _Tab.merge:
        return _mergePath != null ? 1 : 0;
      case _Tab.export_:
        return _asRingtone ? 1 : 0;
    }
  }

  void _selectTab(_Tab t) {
    HapticFeedback.selectionClick();
    setState(() { _prevTabIndex = _tab.index; _tab = t; });
    // keep the chosen tab visible (approximate width per tab is fine — the
    // clamp keeps it inside the scroll extent either way)
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_tabScroll.hasClients) return;
      final max = _tabScroll.position.maxScrollExtent;
      if (max <= 0) return;
      final frac = _kTabs.length > 1 ? t.index / (_kTabs.length - 1) : 0.0;
      _tabScroll.animateTo((frac * max).clamp(0.0, max),
          duration: const Duration(milliseconds: 260), curve: Curves.easeOutCubic);
    });
  }

  Widget _tabBar() {
    final ar = LangProvider.strings(context).ar;
    return Container(
      decoration: BoxDecoration(color: _surface,
          border: const Border(bottom: BorderSide(color: _border)),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.15),
              blurRadius: 6, offset: const Offset(0, 3))]),
      child: SingleChildScrollView(
        controller: _tabScroll,
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 6),
        child: Row(children: _kTabs.map((spec) {
          final active = spec.tab == _tab;
          final badge = _tabBadge(spec.tab);
          return GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: () => _selectTab(spec.tab),
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 9),
              margin: const EdgeInsets.symmetric(horizontal: 2, vertical: 5),
              decoration: BoxDecoration(
                color: active ? _goldDim.withValues(alpha: 0.30) : Colors.transparent,
                borderRadius: BorderRadius.circular(11),
                border: Border.all(
                    color: active ? _gold.withValues(alpha: 0.55) : Colors.transparent),
              ),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                Row(mainAxisSize: MainAxisSize.min, children: [
                  Icon(spec.icon, color: active ? _gold : _textDim, size: 17),
                  const SizedBox(width: 6),
                  Text(ar ? spec.ar : spec.en, style: TextStyle(
                      color: active ? _gold : _textB,
                      fontSize: 11.5,
                      fontWeight: active ? FontWeight.w800 : FontWeight.w600)),
                  if (badge > 0) ...[
                    const SizedBox(width: 5),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                      decoration: BoxDecoration(
                          color: _tealDk, borderRadius: BorderRadius.circular(7),
                          border: Border.all(color: _teal.withValues(alpha: 0.5))),
                      child: Text('$badge', style: const TextStyle(
                          color: _teal, fontSize: 9, fontWeight: FontWeight.w800,
                          fontFamily: 'monospace')),
                    ),
                  ],
                ]),
                const SizedBox(height: 5),
                AnimatedContainer(
                  duration: const Duration(milliseconds: 220),
                  curve: Curves.easeOutCubic,
                  height: 2.4,
                  width: active ? 26 : 0,
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [_teal, _gold]),
                    borderRadius: BorderRadius.circular(2)),
                ),
              ]),
            ));
        }).toList()),
      ));
  }

  int _prevTabIndex = 0;   // S250d — direction of travel for the transition

  Widget _tabBody() {
    _cardSeq = 0;                       // S250g — restart the stagger per tab
    late final Widget child;
    switch (_tab) {
      case _Tab.trim:    child = _trimTab(); break;
      case _Tab.eq:      child = _eqTab(); break;
      case _Tab.effects: child = _effectsTab(); break;
      case _Tab.fx2:     child = _fx2Tab(); break;
      case _Tab.cleanup: child = _cleanupTab(); break;
      case _Tab.studio:  child = _studioTab(); break;
      case _Tab.loudness: child = _loudnessTab(); break;
      case _Tab.quality: child = _qualityTab(); break;
      case _Tab.compare: child = _compareTab(); break;
      case _Tab.merge:   child = _mergeTab(); break;
      case _Tab.export_: child = _exportTab(); break;
    }
    // S250d — the transition now carries DIRECTION: move right through the
    // tabs and content enters from the right, move left and it enters from the
    // left. The old version always slid a flat 2% upward regardless, which read
    // as a twitch rather than as navigation.
    final forward = _tab.index >= _prevTabIndex;
    final dx = forward ? 0.18 : -0.18;
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 260),
      switchInCurve: Curves.easeOutCubic,
      switchOutCurve: Curves.easeInCubic,
      transitionBuilder: (c, anim) => FadeTransition(opacity: anim,
          child: SlideTransition(
              position: Tween<Offset>(begin: Offset(dx, 0.015), end: Offset.zero)
                  .animate(anim),
              child: c)),
      // keep the outgoing child under the incoming one so the slide reads
      layoutBuilder: (current, previous) => Stack(
          alignment: Alignment.topCenter,
          children: [...previous, if (current != null) current]),
      child: KeyedSubtree(key: ValueKey(_tab), child: child),
    );
  }

  // ── TRIM TAB ──────────────────────────────────────────────────────────────
  /// S250 — nudge a trim edge by whole seconds. Dragging alone can't hit an
  /// exact boundary on a long file: one pixel is several seconds of a
  /// 40-minute recitation.
  void _nudgeTrim({required bool start, required double deltaSec}) {
    if (_durationSec <= 0) return;
    HapticFeedback.selectionClick();
    final d = deltaSec / _durationSec;
    _edit(() {
      if (start) {
        _trimStart = (_trimStart + d).clamp(0.0, (_trimEnd - 0.005).clamp(0.0, 1.0));
      } else {
        _trimEnd = (_trimEnd + d).clamp((_trimStart + 0.005).clamp(0.0, 1.0), 1.0);
      }
    });
  }

  Widget _nudgeRow(String label, Color color, bool isStart, double valueSec) =>
    Row(children: [
      SizedBox(width: 44, child: Text(label,
          style: const TextStyle(color: _textDim, fontSize: 10.5))),
      _miniBtn(Icons.remove_rounded, () => _nudgeTrim(start: isStart, deltaSec: -1)),
      const SizedBox(width: 5),
      Expanded(child: Center(child: Text(_fmtTime(valueSec),
          style: TextStyle(color: color, fontSize: 16, fontWeight: FontWeight.w800,
              fontFamily: 'monospace')))),
      _miniBtn(Icons.add_rounded, () => _nudgeTrim(start: isStart, deltaSec: 1)),
      const SizedBox(width: 8),
      // set this edge to wherever the playhead is
      GestureDetector(
        onTap: _durationSec <= 0 ? null : () {
          HapticFeedback.selectionClick();
          final f = (_positionSec / _durationSec).clamp(0.0, 1.0);
          _edit(() {
            if (isStart) {
              _trimStart = f.clamp(0.0, (_trimEnd - 0.005).clamp(0.0, 1.0));
            } else {
              _trimEnd = f.clamp((_trimStart + 0.005).clamp(0.0, 1.0), 1.0);
            }
          });
        },
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 5),
          decoration: BoxDecoration(color: _surface,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: color.withValues(alpha: 0.45))),
          child: Icon(Icons.my_location_rounded, color: color, size: 13)),
      ),
    ]);

  /// S250 — set the trim range to the audible span, read straight off the
  /// waveform buckets the analysis already produced. No processing run, no
  /// export needed: instant, and reversible with Undo.
  void _trimToAudio() {
    final bars = _barsTo.isNotEmpty ? _barsTo : _bars;
    if (bars.isEmpty || _durationSec <= 0) return;
    const thr = 0.08;                       // ~-22 dB of the file's own peak
    int first = -1, last = -1;
    for (int i = 0; i < bars.length; i++) {
      if (bars[i] > thr) {
        if (first < 0) first = i;
        last = i;
      }
    }
    final ar = LangProvider.strings(context).ar;
    if (first < 0 || last <= first) {
      _snack(ar ? 'لم يُعثَر على مقطع مسموع واضح' : 'No clearly audible span found',
          color: _gold);
      return;
    }
    final pad = 1 / bars.length;            // one bucket of breathing room
    _edit(() {
      _trimStart = (first / bars.length - pad).clamp(0.0, 1.0);
      _trimEnd = ((last + 1) / bars.length + pad).clamp(0.0, 1.0);
    });
    _snack(ar ? '✓ تم التحديد حول الصوت' : '✓ Selected around the audio', color: _teal);
  }

  Widget _miniBtn(IconData icon, VoidCallback onTap) => GestureDetector(
    onTap: onTap,
    child: Container(width: 26, height: 26,
      decoration: BoxDecoration(shape: BoxShape.circle, color: _surface,
          border: Border.all(color: _border)),
      child: Icon(icon, color: _textB, size: 14)));

  Widget _trimTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.fromLTRB(14, 14, 14, 24), children: [
      // S250 — what the analysis found, with one-tap fixes
      _insightsCard(),
      if (_insF0 != null || _insSpeechPct != null) const SizedBox(height: 10),
      _card_(ar ? 'نطاق القص' : 'Trim Range', Icons.content_cut_rounded, [
        Text(ar ? 'اسحب المقبضين على الموجة أعلاه، أو اضبط بدقة هنا'
                : 'Drag the two handles on the waveform above, or fine-tune here',
            style: const TextStyle(color: _textDim, fontSize: 10.5)),
        const SizedBox(height: 10),
        // S250 — ±1 s nudges and "set to playhead", because dragging can't be
        // frame-accurate on a long file.
        _nudgeRow(ar ? 'البداية' : 'Start', _teal, true, _trimStart * _durationSec),
        const SizedBox(height: 6),
        _nudgeRow(ar ? 'النهاية' : 'End', _gold, false, _trimEnd * _durationSec),
        const SizedBox(height: 6),
        // Single RangeSlider replaces the old two separate full-width Sliders —
        // both handles visible on one track instead of two stacked bars.
        Directionality(textDirection: TextDirection.ltr,
          child: SliderTheme(data: SliderThemeData(
              trackHeight: 5,
              rangeThumbShape: const RoundRangeSliderThumbShape(enabledThumbRadius: 9),
              overlayShape: const RoundSliderOverlayShape(overlayRadius: 18),
              activeTrackColor: _gold,
              inactiveTrackColor: _border,
              thumbColor: _teal,
              overlayColor: _teal.withValues(alpha: 0.15)),
            child: RangeSlider(
              values: RangeValues(_trimStart.clamp(0.0, 1.0), _trimEnd.clamp(0.0, 1.0)),
              onChanged: (r) => setState(() {
                _trimStart = r.start.clamp(0.0, _trimEnd - 0.005);
                _trimEnd = r.end.clamp(_trimStart + 0.005, 1.0);
              }),
              // S250 — one undo step per drag
              onChangeStart: (_) { HapticFeedback.selectionClick(); _pushUndo(); },
            ))),
        const SizedBox(height: 8),
        Divider(height: 1, color: _border.withValues(alpha: 0.6)),
        const SizedBox(height: 12),
        Center(child: Column(children: [
          Text(_fmtTime((_trimEnd - _trimStart) * _durationSec),
              style: const TextStyle(color: _gold, fontSize: 28, fontWeight: FontWeight.w800,
                  letterSpacing: 1.2, fontFamily: 'monospace')),
          const SizedBox(height: 2),
          Text(ar ? 'مدة التحديد' : 'Selection Duration', style: const TextStyle(color: _textDim, fontSize: 10.5)),
        ])),
        const SizedBox(height: 12),
        Wrap(spacing: 8, runSpacing: 8, alignment: WrapAlignment.center, children: [
          _chip_(ar ? 'الكل' : 'All', () => setState(() { _trimStart = 0; _trimEnd = 1; })),
          _chip_(ar ? 'النصف الأول' : 'First Half', () => setState(() { _trimStart = 0; _trimEnd = 0.5; })),
          _chip_(ar ? 'النصف الثاني' : 'Second Half', () => setState(() { _trimStart = 0.5; _trimEnd = 1; })),
          // S250 — trim to the audible part using the analysed waveform, with
          // no processing run at all
          if (_analyzed)
            _chip_(ar ? 'حول الصوت' : 'Around Audio', _trimToAudio),
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
          // S250d — staggered rise so the analyser reads as filling up
          SizedBox(height: 64, child: TweenAnimationBuilder<double>(
              key: ValueKey(_spectrum.length),
              tween: Tween(begin: 0, end: 1),
              duration: const Duration(milliseconds: 650),
              curve: Curves.easeOutCubic,
              builder: (_, t, __) => CustomPaint(
                  painter: _SpectrumPainter(bands: _spectrum, reveal: t),
                  size: const Size(double.infinity, 64)))),
          const SizedBox(height: 6),
          const Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
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
          _edit(() {
            _vol=1.0; _pitch=0; _tempo=1.0; _stereoW=1.0;
            _fadeIn=0; _fadeOut=0; _echo=0; _reverb=0;
            _noiseReduc=0; _compress=false; _compThresh=-18; _compRatio=4.0;
            _reverse=false;
            // S228 — Studio Engine settings
            _eqQ=1.4; _declick=false; _declickSens=50; _reverbType='Room';
            _compAttack=20; _compRelease=200; _compMakeup=0;
            _loudnessTarget='Off'; _truePeakLimiter=true; _fadeCurve='Equal Power';
            _aiDenoiseOn=false; _aiDenoiseStrength=60; _vadTrimOn=false; _vadAggr=2;  // S248
            // S250 — the new Cleanup-tab processing was missing from this reset,
            // so "Reset All Effects" left dereverb/squeeze/harmonic focus on.
            _aiDenoiseNonStat=false; _dereverb=0; _squeezeOn=false;
            _squeezeMax=1.2; _squeezeKeep=0.35; _harmonicFocus=0;
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

  // ── CLEANUP TAB — S248 noisereduce + webrtcvad, S250 nara_wpe + HPSS ─────
  Widget _cleanupTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.fromLTRB(14, 14, 14, 24), children: [
      if (_insSpeechPct != null || _insLongPauses != null) ...[
        _insightsCard(),
        const SizedBox(height: 10),
      ],
      _card_(ar ? 'إزالة الضوضاء (AI)' : 'AI Noise Reduction', Icons.blur_on_rounded, [
        Text(ar
            ? 'إزالة ضوضاء طيفية (noisereduce) — أدق من المُقلّص اليدوي في تبويب التأثيرات، ويمكن تشغيلها معه.'
            : 'Spectral-gating noise reduction (noisereduce) — more accurate than the manual '
              'reducer in the Effects tab, and can run alongside it.',
            style: const TextStyle(color: _textDim, fontSize: 11, height: 1.4)),
        const SizedBox(height: 10),
        _toggle(ar ? 'تفعيل' : 'Enable', Icons.blur_on_rounded,
            _aiDenoiseOn, (v) => setState(() => _aiDenoiseOn = v)),
        if (_aiDenoiseOn) ...[const SizedBox(height: 10),
          _knob(ar ? 'قوة الإزالة' : 'Strength', '${_aiDenoiseStrength.round()}%',
              _aiDenoiseStrength, 0, 100, (v) => setState(() => _aiDenoiseStrength = v)),
          // S250 — noisereduce's non-stationary mode
          _toggle(ar ? 'ضوضاء متغيّرة' : 'Changing noise', Icons.waves_rounded,
              _aiDenoiseNonStat, (v) => setState(() => _aiDenoiseNonStat = v)),
          Text(ar
              ? 'فعّلها إذا كانت الضوضاء تتغير أثناء التسجيل (مرور سيارات، مروحة، ضجيج قاعة) — '
                'يتابع المحرك تقديرًا متحركًا للضوضاء بدل تقدير ثابت واحد.'
              : 'Turn on when the noise changes during the recording (passing traffic, a fan, '
                'hall murmur) — the engine tracks a moving noise estimate instead of one fixed profile.',
              style: const TextStyle(color: _textDim, fontSize: 10.5, height: 1.4)),
        ],
      ]),
      const SizedBox(height: 10),
      // ── S250: nara_wpe dereverberation ──
      _card_(ar ? 'إزالة صدى القاعة (Dereverb)' : 'Room Dereverb (WPE)',
          Icons.surround_sound_rounded, [
        Text(ar
            ? 'يقصّر ذيل صدى الغرفة/المسجد فعليًا (خوارزمية WPE من nara_wpe) بدل تغطيته — '
              'يقدّر الصدى المتأخر من إشارة التسجيل نفسها ويطرحه لكل ترددٍ على حدة. '
              'الأفضل للتلاوات المسجّلة في مكان مُصلِت.'
            : 'Actually shortens a room/mosque reverb tail (nara_wpe\'s WPE algorithm) instead '
              'of masking it — it estimates the late reverberation from the signal\'s own past '
              'and subtracts it per frequency band. Best on recitations recorded in a live room.',
            style: const TextStyle(color: _textDim, fontSize: 11, height: 1.4)),
        const SizedBox(height: 10),
        _knob(ar ? 'قوة الإزالة' : 'Strength',
            _dereverb == 0 ? (ar ? 'معطل' : 'Off') : '${_dereverb.round()}%',
            _dereverb, 0, 100, (v) => setState(() => _dereverb = v)),
        Text(ar ? 'ابدأ من ٤٠٪ — القيم العالية تجعل الصوت جافًا وقريبًا جدًا'
                : 'Start around 40% — high values make the voice dry and very close',
            style: const TextStyle(color: _textDim, fontSize: 10.5)),
      ]),
      const SizedBox(height: 10),
      // ── S250: HPSS transient removal ──
      _card_(ar ? 'تنقية العابرات (تركيز نغمي)' : 'Transient Cleanup (Harmonic Focus)',
          Icons.auto_awesome_motion_rounded, [
        Text(ar
            ? 'يفصل الصوت الممتد (صوت القارئ) عن الأصوات اللحظية — قلب الصفحات، طرق الميكروفون، '
              'صرير الكرسي، نقرات الفم — ويخفض هذه الأخيرة. تلتقط ما تعجز عنه بوابة الضوضاء '
              '(لأنه أعلى من العتبة) وما يُشوّهه تقليل الضوضاء الطيفي (لأنه عريض النطاق).'
            : 'Separates sustained sound (the reciter\'s voice) from momentary ones — page turns, '
              'mic bumps, chair creaks, mouth clicks — and pulls the latter down. Catches what a '
              'noise gate can\'t (it\'s above the threshold) and what spectral denoise only smears '
              '(it\'s broadband).',
            style: const TextStyle(color: _textDim, fontSize: 11, height: 1.4)),
        const SizedBox(height: 10),
        _knob(ar ? 'قوة التنقية' : 'Amount',
            _harmonicFocus == 0 ? (ar ? 'معطل' : 'Off') : '${_harmonicFocus.round()}%',
            _harmonicFocus, 0, 100, (v) => setState(() => _harmonicFocus = v)),
      ]),
      const SizedBox(height: 10),
      _card_(ar ? 'قص السكوت بكشف الصوت (VAD)' : 'Voice-Activity Trim', Icons.record_voice_over_rounded, [
        Text(ar
            ? 'يكتشف الكلام فعليًا (webrtcvad) بدل عتبة صوت بسيطة — يقص الصمت وغير الكلام من '
              'البداية والنهاية بدقة أعلى من "قص السكوت التلقائي" في تبويب FX+.'
            : 'Real speech detection (webrtcvad) instead of a plain volume threshold — trims '
              'leading/trailing silence and non-speech more precisely than "Auto-Trim Silence" '
              'in the FX+ tab.',
            style: const TextStyle(color: _textDim, fontSize: 11, height: 1.4)),
        const SizedBox(height: 10),
        _toggle(ar ? 'تفعيل (يُلغي القص التلقائي البسيط)' : 'Enable (overrides plain auto-trim)',
            Icons.record_voice_over_rounded, _vadTrimOn, (v) => setState(() => _vadTrimOn = v)),
        if (_vadTrimOn) ...[const SizedBox(height: 10),
          _knob(ar ? 'حساسية الكشف' : 'Detection Aggressiveness',
              _vadAggr.round().toString(),
              _vadAggr, 0, 3, (v) => setState(() => _vadAggr = v)),
          const SizedBox(height: 4),
          Text(ar ? '٠ = متساهل (أقل قصًا) — ٣ = صارم (أكثر قصًا)'
                  : '0 = lenient (trims less) — 3 = strict (trims more)',
              style: const TextStyle(color: _textDim, fontSize: 10.5)),
        ],
      ]),
      const SizedBox(height: 10),
      // ── S250: internal pause squeezing ──
      _card_(ar ? 'تقصير السكتات الطويلة' : 'Squeeze Long Pauses',
          Icons.compress_rounded, [
        Text(ar
            ? 'يقصّر السكتات *داخل* التسجيل لا في طرفيه فقط: كل سكتة أطول من الحد يتم تقصيرها '
              'مع تلاشٍ متقاطع قصير حتى لا تُسمع نقرة. يحافظ على أنفاس القارئ (يعدّها webrtcvad '
              'صوتًا) بخلاف مرشحات إزالة الصمت العامة.'
            : 'Shortens the pauses *inside* the recording, not just at its ends: any pause longer '
              'than the limit is cut down, with a short crossfade so no click appears. Unlike a '
              'generic silence-removal filter it keeps the reciter\'s breath (webrtcvad still '
              'hears voice there).',
            style: const TextStyle(color: _textDim, fontSize: 11, height: 1.4)),
        const SizedBox(height: 10),
        _toggle(ar ? 'تفعيل' : 'Enable', Icons.compress_rounded,
            _squeezeOn, (v) => setState(() => _squeezeOn = v)),
        if (_squeezeOn) ...[const SizedBox(height: 10),
          _knob(ar ? 'أطول سكتة مسموحة' : 'Longer than',
              '${_squeezeMax.toStringAsFixed(1)}s', _squeezeMax, 0.4, 5.0,
              (v) => setState(() {
                _squeezeMax = v;
                if (_squeezeKeep > _squeezeMax) _squeezeKeep = _squeezeMax;
              })),
          _knob(ar ? 'تُقصّر إلى' : 'Shorten to',
              '${_squeezeKeep.toStringAsFixed(2)}s', _squeezeKeep, 0.1,
              _squeezeMax.clamp(0.2, 5.0),
              (v) => setState(() => _squeezeKeep = v)),
          if (_insLongPauses != null)
            Text(ar
                ? 'التحليل وجد ${_insLongPauses!} سكتة طويلة في هذا الملف'
                : 'Analysis found ${_insLongPauses!} long pause${_insLongPauses == 1 ? "" : "s"} in this file',
                style: const TextStyle(color: _teal, fontSize: 10.5)),
        ],
      ]),
    ]);
  }

  // ── S250: CONTENT INSIGHTS — measurements with one-tap fixes ──────────────
  // The analyse pass already reads pitch, brightness, pace, speech ratio and
  // pause structure; before S250 none of it reached the UI. Each row that
  // indicates a problem offers the setting that addresses it, so the numbers
  // are actionable instead of trivia.
  Widget _insightsCard() {
    final ar = LangProvider.strings(context).ar;
    final rows = <Widget>[];

    void row(IconData icon, String label, String value, {String? hint,
        String? fixLabel, VoidCallback? onFix, Color color = _textB}) {
      rows.add(Padding(padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(children: [
          Icon(icon, color: color, size: 15),
          const SizedBox(width: 9),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Expanded(child: Text(label,
                  style: const TextStyle(color: _textA, fontSize: 12))),
              Text(value, style: TextStyle(color: color, fontSize: 12,
                  fontWeight: FontWeight.w700, fontFamily: 'monospace')),
            ]),
            if (hint != null)
              Text(hint, style: const TextStyle(color: _textDim, fontSize: 10, height: 1.3)),
          ])),
          if (onFix != null) ...[
            const SizedBox(width: 8),
            GestureDetector(
              onTap: () { _edit(onFix); HapticFeedback.selectionClick(); },
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
                decoration: BoxDecoration(color: _goldDim.withValues(alpha: 0.4),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: _gold.withValues(alpha: 0.5))),
                child: Text(fixLabel ?? (ar ? 'إصلاح' : 'Fix'),
                    style: const TextStyle(color: _gold, fontSize: 10,
                        fontWeight: FontWeight.w700))),
            ),
          ],
        ])));
    }

    if (_insF0 != null) {
      row(Icons.music_note_rounded, ar ? 'طبقة الصوت' : 'Voice pitch',
          '${_insF0!.toStringAsFixed(0)} Hz${_insNote != null ? " · $_insNote" : ""}',
          color: _teal);
    }
    if (_insBrightness != null) {
      final dull = _insBrightness! < 900;
      row(Icons.light_mode_rounded, ar ? 'السطوع' : 'Brightness',
          '${_insBrightness!.toStringAsFixed(0)} Hz',
          color: dull ? _gold : _teal,
          hint: dull
              ? (ar ? 'الصوت مكتوم نسبيًا' : 'Sounds fairly dull')
              : null,
          fixLabel: ar ? 'وضوح' : 'Brighten',
          onFix: dull ? () { _presence = 30; _trebleBoost = 2; } : null);
    }
    if (_insOnsets != null) {
      row(Icons.speed_rounded, ar ? 'الإيقاع' : 'Pace',
          '${_insOnsets!.toStringAsFixed(0)}/min');
    }
    if (_insSpeechPct != null) {
      final sparse = _insSpeechPct! < 65;
      row(Icons.record_voice_over_rounded, ar ? 'نسبة الكلام' : 'Speech',
          '${_insSpeechPct!.toStringAsFixed(0)}%',
          color: sparse ? _gold : _teal,
          hint: sparse
              ? (ar ? 'جزء كبير من الملف ليس كلامًا' : 'A lot of this file isn\'t speech')
              : null,
          fixLabel: ar ? 'قص' : 'Trim',
          onFix: sparse ? () { _vadTrimOn = true; } : null);
    }
    if ((_insLongPauses ?? 0) > 0) {
      row(Icons.pause_circle_outline_rounded, ar ? 'سكتات طويلة' : 'Long pauses',
          '$_insLongPauses',
          color: _gold,
          hint: ar ? 'يمكن تقصيرها تلقائيًا' : 'These can be shortened automatically',
          fixLabel: ar ? 'تقصير' : 'Squeeze',
          onFix: () { _squeezeOn = true; });
    }
    if (_insStereoCorr != null) {
      final fakeStereo = _insStereoCorr! > 0.98;
      row(Icons.hearing_rounded, ar ? 'ترابط القناتين' : 'L/R correlation',
          _insStereoCorr!.toStringAsFixed(2),
          color: fakeStereo ? _gold : _textB,
          hint: fakeStereo
              ? (ar ? 'القناتان متطابقتان — التصدير أحاديًا يوفّر نصف الحجم'
                    : 'Both channels are identical — exporting mono halves the size')
              : null,
          fixLabel: ar ? 'أحادي' : 'Mono',
          onFix: fakeStereo ? () { _channels = 'Mono'; } : null);
    }
    if (_insDc != null && _insDc!.abs() > 0.002) {
      row(Icons.trending_flat_rounded, 'DC offset', _insDc!.toStringAsFixed(4),
          color: _red,
          hint: ar ? 'إزاحة تيار مستمر تُهدر مجال الذروة' : 'A DC offset wastes headroom',
          fixLabel: ar ? 'مرشح' : 'Filter',
          onFix: () { if (_hpFreq < 20) _hpFreq = 30; });
    }

    if (rows.isEmpty) return const SizedBox.shrink();
    return _card_(ar ? 'قراءة الملف' : 'What\'s in this file',
        Icons.insights_rounded, rows);
  }

  // ── S250: ENGINE LIBRARIES PANEL ─────────────────────────────────────────
  // Shows which of the 14 embedded audio packages are actually present in the
  // on-device python environment, and what each one powers. This exists
  // because the answer used to be "none of them" without any way to find out:
  // the CI step that was supposed to install them failed silently on every
  // build (see build_assets.sh), so the features that depend on them were
  // quietly inert. Now it's one tap to verify.
  Widget _libsCard() {
    final ar = LangProvider.strings(context).ar;
    final libs = _libs;
    final all = libs != null && _libsTotal > 0 && _libsOk == _libsTotal;
    final d = _diag;
    return _card_(ar ? 'مكتبات المحرك' : 'Engine Libraries', Icons.extension_rounded, [
      // S250h — the environment's real state, probed by running things. A
      // broken rootfs used to present as "everything fine" here while every
      // operation failed, because every check was a File.exists().
      if (d != null) ...[
        _diagRow(ar ? 'ffmpeg يعمل' : 'ffmpeg runs', d['ffmpeg_runs'] == true,
            d['ffmpeg_file'] == true
                ? (ar ? 'الملف موجود' : 'file present')
                : (ar ? 'الملف مفقود' : 'file missing')),
        _diagRow(ar ? 'numpy يُحمَّل' : 'numpy imports', d['numpy_imports'] == true,
            d['numpy_imports'] == true ? '' : '${d['numpy_error'] ?? ''}'),
        _diagRow(ar ? 'إصدار البيئة' : 'environment version',
            d['env_stamp_ok'] == true,
            d['env_stamp_ok'] == true
                ? (ar ? 'محدَّث' : 'current')
                : (ar ? 'قديم — أعد التثبيت' : 'stale — re-install local mode')),
        if (d['ffmpeg_runs'] != true || d['numpy_imports'] != true) ...[
          const SizedBox(height: 8),
          Text(ar
              ? 'المعالجة لن تعمل حتى يعمل ffmpeg و numpy. أعد تثبيت الوضع المحلي '
                'من الشاشة الرئيسية — سيُستبدل الإصدار المعطوب.'
              : 'Processing cannot work until ffmpeg and numpy both run. Re-install '
                'local mode from the home screen — that replaces the broken copy.',
              style: const TextStyle(color: _red, fontSize: 11.5, height: 1.45)),
        ],
        const SizedBox(height: 10),
        Divider(height: 1, color: _border.withValues(alpha: 0.6)),
        const SizedBox(height: 10),
      ],
      Text(ar
          ? 'حزم الصوت المُضمّنة في بيئة بايثون على جهازك. كل واحدة منها تُشغّل ميزة '
            'محددة في المحرر — والميزات التي تعتمد عليها تعمل فقط إذا كانت موجودة.'
          : 'The audio packages embedded in the on-device Python environment. Each one powers a '
            'specific editor feature — and the features that depend on it only work if it\'s there.',
          style: const TextStyle(color: _textB, fontSize: 12, height: 1.5)),
      const SizedBox(height: 12),
      if (libs == null)
        GestureDetector(
          onTap: _libsLoading ? null : _loadLibs,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 13),
            decoration: BoxDecoration(color: _tealDk, borderRadius: BorderRadius.circular(10),
                border: Border.all(color: _teal.withValues(alpha: 0.4))),
            child: Center(child: Row(mainAxisSize: MainAxisSize.min, children: [
              if (_libsLoading)
                const SizedBox(width: 14, height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2, color: _teal))
              else
                const Icon(Icons.fact_check_outlined, color: _teal, size: 17),
              const SizedBox(width: 8),
              Text(_libsLoading
                      ? (ar ? 'جارٍ الفحص…' : 'Checking…')
                      : (ar ? 'فحص المكتبات' : 'Check Libraries'),
                  style: const TextStyle(color: _teal, fontSize: 13, fontWeight: FontWeight.w700)),
            ])))),
      if (libs != null) ...[
        Row(children: [
          Icon(all ? Icons.verified_rounded : Icons.warning_amber_rounded,
              color: all ? _teal : _gold, size: 17),
          const SizedBox(width: 8),
          Expanded(child: Text(
              ar ? '$_libsOk من $_libsTotal حزمة متوفرة'
                 : '$_libsOk of $_libsTotal packages available',
              style: TextStyle(color: all ? _teal : _gold, fontSize: 12.5,
                  fontWeight: FontWeight.w700))),
          GestureDetector(
            onTap: _libsLoading ? null : _loadLibs,
            child: const Icon(Icons.refresh_rounded, color: _textB, size: 17)),
        ]),
        const SizedBox(height: 4),
        Text(ar
            ? all ? 'كل الميزات المعتمدة على هذه الحزم تعمل.'
                  : 'الميزات المعتمدة على الحزم الناقصة ترجع تلقائيًا إلى بديل numpy/scipy.'
            : all ? 'Every feature that depends on these is live.'
                  : 'Features needing a missing package fall back to numpy/scipy automatically.',
            style: const TextStyle(color: _textDim, fontSize: 10.5, height: 1.4)),
        const SizedBox(height: 10),
        ...libs.map((p) {
          final ok = p['ok'] == true;
          final ver = (p['version'] as String?) ?? '';
          return Padding(padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(children: [
              _rackLamp(ok),
              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Row(children: [
                  Text('${p['name']}', style: TextStyle(
                      color: ok ? _textA : _textDim, fontSize: 11.5,
                      fontWeight: FontWeight.w700, fontFamily: 'monospace')),
                  if (ver.isNotEmpty) ...[
                    const SizedBox(width: 6),
                    Text(ver, style: const TextStyle(color: _textDim, fontSize: 9.5,
                        fontFamily: 'monospace')),
                  ],
                ]),
                Text('${p['role']}',
                    style: TextStyle(color: ok ? _textB : _textDim, fontSize: 10, height: 1.3)),
              ])),
              Icon(ok ? Icons.check_rounded : Icons.close_rounded,
                  color: ok ? _teal : _red, size: 14),
            ]));
        }),
      ],
      if (_libsError != null) ...[
        const SizedBox(height: 10),
        Text(_libsError!, style: const TextStyle(color: _red, fontSize: 11, height: 1.4)),
      ],
    ]);
  }

  Widget _diagRow(String label, bool ok, String detail) =>
    Padding(padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Icon(ok ? Icons.check_circle_rounded : Icons.cancel_rounded,
            color: ok ? _teal : _red, size: 15),
        const SizedBox(width: 8),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(label, style: TextStyle(
              color: ok ? _textA : _red, fontSize: 12,
              fontWeight: ok ? FontWeight.w500 : FontWeight.w700)),
          if (detail.trim().isNotEmpty)
            Text(detail.trim(), maxLines: 3, overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: _textDim, fontSize: 9.5, height: 1.3)),
        ])),
      ]));

  // ── S250: last run's per-stage timings, straight from the engine report ────
  Widget _stageTimingCard() {
    final ar = LangProvider.strings(context).ar;
    final total = _lastRunMs;
    return _card_(ar ? 'زمن آخر معالجة' : 'Last Run Timing', Icons.timer_outlined, [
      if (total != null)
        Row(children: [
          Text(ar ? 'الإجمالي' : 'Total',
              style: const TextStyle(color: _textB, fontSize: 12)),
          const Spacer(),
          Text('${(total / 1000).toStringAsFixed(2)} s',
              style: const TextStyle(color: _gold, fontSize: 13,
                  fontWeight: FontWeight.w800, fontFamily: 'monospace')),
        ]),
      const SizedBox(height: 6),
      ..._lastStages.map((s) {
        final ms = (s['ms'] as num?)?.toDouble() ?? 0;
        final frac = (total != null && total > 0) ? (ms / total).clamp(0.0, 1.0) : 0.0;
        return Padding(padding: const EdgeInsets.symmetric(vertical: 3),
          child: Row(children: [
            SizedBox(width: 96, child: Text('${s['name']}',
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(color: _textB, fontSize: 10.5))),
            Expanded(child: ClipRRect(borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(value: frac, minHeight: 4,
                  backgroundColor: _border,
                  valueColor: const AlwaysStoppedAnimation(_teal)))),
            const SizedBox(width: 8),
            SizedBox(width: 58, child: Text('${ms.toStringAsFixed(0)} ms',
                textAlign: TextAlign.end,
                style: const TextStyle(color: _textDim, fontSize: 10,
                    fontFamily: 'monospace'))),
          ]));
      }),
      const SizedBox(height: 4),
      Text(ar ? 'يقيس المحرك كل مرحلة على حدة — يوضح أي إعداد يستهلك الوقت'
              : 'The engine times each stage — shows which setting costs the time',
          style: const TextStyle(color: _textDim, fontSize: 10.5)),
    ]);
  }

  // ── STUDIO TAB — S228 advanced Studio Engine settings ───────────────────
  Widget _studioTab() {
    final ar = LangProvider.strings(context).ar;
    return ListView(padding: const EdgeInsets.fromLTRB(14, 14, 14, 24), children: [
      _libsCard(),                                        // S250
      const SizedBox(height: 10),
      if (_lastStages.isNotEmpty) ...[
        _stageTimingCard(),                               // S250
        const SizedBox(height: 10),
      ],
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
              lufs != null ? lufs.toStringAsFixed(1) : '—', 'LUFS',
              animateTo: lufs)),
          Expanded(child: _loudnessStatBlock(ar ? 'نطاق الجهارة' : 'Loudness Range',
              lra != null ? lra.toStringAsFixed(1) : '—', 'LU', animateTo: lra)),
          Expanded(child: _loudnessStatBlock(ar ? 'الذروة الحقيقية' : 'True Peak',
              tp != null ? '${tp >= 0 ? "+" : ""}${tp.toStringAsFixed(1)}' : '—', 'dBTP',
              warn: tp != null && tp > -1.0, animateTo: tp)),
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
                      setState(() { _loudnessTarget = preset; _truePeakLimiter = true;
                        _prevTabIndex = _tab.index; _tab = _Tab.studio; });
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

  // S250d — measured values count up from zero when a fresh analysis lands, so
  // the numbers read as "just measured" rather than as static labels that may
  // or may not belong to the current file.
  Widget _loudnessStatBlock(String label, String value, String unit,
      {bool warn = false, double? animateTo, int decimals = 1}) => Column(children: [
    Text(label, style: const TextStyle(color: _textDim, fontSize: 10), textAlign: TextAlign.center),
    const SizedBox(height: 4),
    if (animateTo == null)
      Text(value, style: TextStyle(color: warn ? _red : _gold, fontSize: 20,
          fontWeight: FontWeight.w800, fontFamily: 'monospace'))
    else
      TweenAnimationBuilder<double>(
        key: ValueKey('$label$animateTo'),
        tween: Tween(begin: 0, end: animateTo),
        duration: const Duration(milliseconds: 700),
        curve: Curves.easeOutCubic,
        builder: (_, v, __) => Text(
            '${v > 0 && animateTo > 0 ? "+" : ""}${v.toStringAsFixed(decimals)}',
            style: TextStyle(color: warn ? _red : _gold, fontSize: 20,
                fontWeight: FontWeight.w800, fontFamily: 'monospace'))),
    Text(unit, style: const TextStyle(color: _textDim, fontSize: 10)),
  ]);

  // ── QUALITY TAB — S248: pystoi intelligibility score (bundled via S247) ──
  Widget _qualityTab() {
    final ar = LangProvider.strings(context).ar;
    if (_filePath == null) {
      return Center(child: Text(ar ? 'افتح ملفًا أولًا' : 'Open a file first',
          style: const TextStyle(color: _textDim)));
    }
    final stoi = _statStoi;
    return ListView(padding: const EdgeInsets.all(14), children: [
      _card_(ar ? 'فحص وضوح الكلام' : 'Speech Intelligibility Check', Icons.fact_check_rounded, [
        Text(ar
            ? 'يقارن هذا التبويب الملف الأصلي بمعالجة الإعدادات الحالية باستخدام مقياس STOI '
              '(pystoi) — تقييم موضوعي لوضوح الكلام، وليس مجرد الجهارة. مفيد للتأكد أن '
              'التعديلات (تقليل الضوضاء، الموازن، إلخ) لم تُضِرّ بوضوح التلاوة.'
            : 'This tab compares the original file against a render of your current settings '
              'using the STOI metric (pystoi) — an objective measure of speech intelligibility, '
              'not just loudness. Useful for confirming edits (noise reduction, EQ, etc.) '
              'haven\'t hurt the clarity of the recitation.',
            style: const TextStyle(color: _textB, fontSize: 12, height: 1.5)),
        const SizedBox(height: 12),
        GestureDetector(
          onTap: _qualityChecking ? null : _runQualityCheck,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 13),
            decoration: BoxDecoration(color: _tealDk, borderRadius: BorderRadius.circular(10),
                border: Border.all(color: _teal.withValues(alpha: 0.4))),
            child: Center(child: Row(mainAxisSize: MainAxisSize.min, children: [
              if (_qualityChecking)
                const SizedBox(width: 14, height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2, color: _teal))
              else
                const Icon(Icons.fact_check_rounded, color: _teal, size: 17),
              const SizedBox(width: 8),
              Text(_qualityChecking ? (ar ? 'جارٍ الفحص…' : 'Checking…') : (ar ? 'فحص الآن' : 'Check Now'),
                  style: const TextStyle(color: _teal, fontSize: 13, fontWeight: FontWeight.w700)),
            ])))),
      ]),
      if (_qualityError != null) ...[const SizedBox(height: 10),
        _card_(ar ? 'تعذّر الفحص' : 'Check Unavailable', Icons.warning_amber_rounded, [
          Text(_qualityError!, style: const TextStyle(color: _red, fontSize: 11.5, height: 1.4)),
        ])],
      if (stoi != null) ...[const SizedBox(height: 10),
        _card_(ar ? 'نتيجة STOI' : 'STOI Score', Icons.graphic_eq_rounded, [
          Center(child: Column(children: [
            Text((stoi * 100).toStringAsFixed(1),
                style: TextStyle(
                    color: stoi >= 0.85 ? _teal : (stoi >= 0.7 ? _gold : _red),
                    fontSize: 34, fontWeight: FontWeight.w800, fontFamily: 'monospace')),
            Text(ar ? '٪ وضوح' : '% intelligibility', style: const TextStyle(color: _textDim, fontSize: 11)),
          ])),
          const SizedBox(height: 10),
          // S250 — ESTOI reacts to the modulation-domain damage that aggressive
          // denoising leaves behind, which plain STOI can miss entirely.
          if (_statEstoi != null)
            _row('ESTOI', '${(_statEstoi! * 100).toStringAsFixed(1)}%'),
          if (_statLufsDelta != null)
            _row(ar ? 'فرق الجهارة' : 'Loudness change',
                '${_statLufsDelta! >= 0 ? "+" : ""}${_statLufsDelta!.toStringAsFixed(1)} LU'),
          if (_statDriftSec != null)
            _row(ar ? 'فرق الطول' : 'Length difference',
                '${_statDriftSec!.toStringAsFixed(2)}s'),
          const SizedBox(height: 8),
          Text(
              stoi >= 0.85
                  ? (ar ? 'ممتاز — لا يوجد فقدان وضوح ملحوظ.' : 'Excellent — no noticeable intelligibility loss.')
                  : stoi >= 0.7
                      ? (ar ? 'جيد — فقدان طفيف، راجع إعدادات تقليل الضوضاء/الموازن.'
                            : 'Good — minor loss, worth reviewing noise-reduction/EQ settings.')
                      : (ar ? 'تحذير — فقدان وضوح واضح، جرّب تخفيف الإعدادات الحالية.'
                            : 'Warning — noticeable intelligibility loss, try easing back current settings.'),
              style: const TextStyle(color: _textB, fontSize: 12, height: 1.5)),
        ]),
        // S250 — STOI aligns the two signals sample-for-sample, so anything
        // that changes duration (pitch, speed, VAD trim, pause squeezing)
        // makes a low score meaningless rather than bad. Say so instead of
        // letting the user "fix" a problem that isn't there.
        if ((_statDriftSec ?? 0) > 0.25 || _pitch != 0 || _tempo != 1.0) ...[
          const SizedBox(height: 10),
          _card_(ar ? 'اقرأ النتيجة بحذر' : 'Read this score with care',
              Icons.info_outline_rounded, [
            Text(ar
                ? 'هذا القياس يقارن الإشارتين عيّنةً بعيّنة، لذا أي إعداد يغيّر الطول أو الطبقة '
                  '(السرعة، الطبقة، قص السكوت بالـVAD، تقصير السكتات) يجعل النتيجة منخفضة '
                  'بلا معنى — وليست دليلًا على سوء الجودة. أوقف تلك الإعدادات مؤقتًا لقياس '
                  'أثر تقليل الضوضاء والموازن وحدهما.'
                : 'This metric compares the two signals sample-for-sample, so any setting that '
                  'changes length or pitch (speed, pitch, VAD trim, pause squeezing) makes a low '
                  'score meaningless rather than bad. Turn those off temporarily to measure the '
                  'effect of noise reduction and EQ on their own.',
                style: const TextStyle(color: _gold, fontSize: 11.5, height: 1.5)),
          ]),
        ],
      ],
    ]);
  }

  // ── S255 COMPARE TAB ──────────────────────────────────────────────────────
  /// Side-by-side against a reference recording.
  ///
  /// The engine aligns the two by envelope cross-correlation before measuring
  /// (two takes of the same passage rarely start on the same sample) and
  /// matches loudness before reading the bands (otherwise a quiet copy differs
  /// everywhere by the same amount, which says nothing about tone). Both are
  /// surfaced here rather than hidden, so the numbers can be trusted.
  Widget _compareTab() {
    final ar = LangProvider.strings(context).ar;
    if (_filePath == null) {
      return Center(child: Text(ar ? 'افتح ملفًا أولًا' : 'Open a file first',
          style: const TextStyle(color: _textDim)));
    }
    final res = _cmpResult;
    final ready = _cmpRefPath != null;

    Widget pair(String label, Object? refV, Object? subV, {String unit = ''}) {
      String f(Object? v) => v == null ? '—'
          : (v is num ? '${v.toStringAsFixed(v is int ? 0 : 1)}$unit' : '$v');
      return Padding(padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(children: [
          Expanded(flex: 4, child: Text(label,
              style: const TextStyle(color: _textDim, fontSize: 11.5))),
          Expanded(flex: 3, child: Text(f(refV), textAlign: TextAlign.end,
              style: const TextStyle(color: _textB, fontSize: 11.5,
                  fontFamily: 'monospace'))),
          Expanded(flex: 3, child: Text(f(subV), textAlign: TextAlign.end,
              style: const TextStyle(color: _teal, fontSize: 11.5,
                  fontWeight: FontWeight.w700, fontFamily: 'monospace'))),
        ]));
    }

    return ListView(padding: const EdgeInsets.all(14), children: [
      _card_(ar ? 'قارن بمرجع' : 'Compare with a Reference',
          Icons.compare_arrows_rounded, [
        Text(ar
            ? 'اختر تسجيلًا مرجعيًا وقارن ملفك الحالي به: الجهارة، المدى الديناميكي، '
              'الذروة الحقيقية، وتوازن النطاقات الترددية. يُحاذي المحرّك الملفين زمنيًا '
              'أولًا ثم يوحّد الجهارة قبل قراءة النطاقات، حتى تعكس الأرقام الفرق في '
              'النبرة لا في المستوى أو التوقيت.'
            : 'Pick a reference recording and measure your current file against it: '
              'loudness, dynamic range, true peak and the balance across frequency '
              'bands. The engine time-aligns the two first and matches loudness before '
              'reading the bands, so the numbers reflect a difference in tone rather '
              'than in level or timing.',
            style: const TextStyle(color: _textB, fontSize: 12, height: 1.5)),
        const SizedBox(height: 12),
        GestureDetector(
          onTap: _cmpRunning ? null : _pickCompareRef,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 12),
            decoration: BoxDecoration(color: _surface,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: _textDim.withValues(alpha: 0.35))),
            child: Row(children: [
              const Icon(Icons.library_music_rounded, color: _gold, size: 17),
              const SizedBox(width: 9),
              Expanded(child: Text(
                  _cmpRefName ?? (ar ? 'اختر ملف المرجع…' : 'Choose reference file…'),
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                      color: _cmpRefName == null ? _textDim : _textB, fontSize: 12))),
            ]))),
        const SizedBox(height: 10),
        GestureDetector(
          onTap: (_cmpRunning || !ready) ? null : _runCompare,
          child: Opacity(opacity: ready ? 1 : 0.45, child: Container(
            padding: const EdgeInsets.symmetric(vertical: 13),
            decoration: BoxDecoration(color: _tealDk,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: _teal.withValues(alpha: 0.4))),
            child: Center(child: Row(mainAxisSize: MainAxisSize.min, children: [
              if (_cmpRunning)
                const SizedBox(width: 14, height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2, color: _teal))
              else
                const Icon(Icons.compare_arrows_rounded, color: _teal, size: 17),
              const SizedBox(width: 8),
              Text(_cmpRunning
                      ? (ar ? 'جارٍ المقارنة…' : 'Comparing…')
                      : (ar ? 'قارن الآن' : 'Compare Now'),
                  style: const TextStyle(color: _teal, fontSize: 13,
                      fontWeight: FontWeight.w700)),
            ]))))),
      ]),

      if (_cmpError != null) ...[const SizedBox(height: 10),
        _card_(ar ? 'تعذّرت المقارنة' : 'Comparison Unavailable',
            Icons.warning_amber_rounded, [
          Text(_cmpError!, style: const TextStyle(color: _red, fontSize: 11.5, height: 1.4)),
        ])],

      if (res != null) ...[
        const SizedBox(height: 10),
        _card_(ar ? 'القياسات' : 'Measurements', Icons.straighten_rounded, [
          Row(children: [
            const Expanded(flex: 4, child: SizedBox()),
            Expanded(flex: 3, child: Text(ar ? 'المرجع' : 'Reference',
                textAlign: TextAlign.end,
                style: const TextStyle(color: _textDim, fontSize: 10,
                    fontWeight: FontWeight.w700))),
            Expanded(flex: 3, child: Text(ar ? 'ملفك' : 'Yours',
                textAlign: TextAlign.end,
                style: const TextStyle(color: _teal, fontSize: 10,
                    fontWeight: FontWeight.w700))),
          ]),
          const Divider(color: _textDim, height: 14),
          for (final e in [
            [ar ? 'الجهارة' : 'Loudness', 'lufs', ' LUFS'],
            [ar ? 'المدى الديناميكي' : 'Dynamic range', 'lra', ' LU'],
            [ar ? 'الذروة الحقيقية' : 'True peak', 'true_peak_db', ' dBTP'],
            [ar ? 'الذروة' : 'Peak', 'peak_db', ' dBFS'],
            [ar ? 'المدة' : 'Duration', 'duration_sec', ' s'],
          ])
            pair(e[0],
                 (res['reference'] as Map?)?[e[1]],
                 (res['subject'] as Map?)?[e[1]], unit: e[2]),
        ]),

        if ((res['bands'] as List?)?.isNotEmpty ?? false) ...[
          const SizedBox(height: 10),
          _card_(ar ? 'توازن النطاقات (بعد توحيد الجهارة)'
                    : 'Band Balance (loudness-matched)',
              Icons.equalizer_rounded, [
            for (final b in (res['bands'] as List).cast<Map>())
              _bandBar(b['band'] as String,
                       ((b['delta_db'] as num?) ?? 0).toDouble()),
            const SizedBox(height: 6),
            Text(ar
                ? 'الأشرطة إلى اليمين تعني أن ملفك أعلى في ذلك النطاق من المرجع.'
                : 'Bars to the right mean your file has more energy in that band '
                  'than the reference.',
                style: const TextStyle(color: _textDim, fontSize: 10.5, height: 1.4)),
          ])],

        const SizedBox(height: 10),
        _card_(ar ? 'الخلاصة' : 'What This Means', Icons.lightbulb_outline_rounded, [
          if (((res['notes'] as List?) ?? const []).isEmpty)
            Text(ar
                ? 'لا فروق ذات دلالة — الملفان متطابقان عمليًا في كل ما قيس.'
                : 'No meaningful differences — the two files match on everything measured.',
                style: const TextStyle(color: _teal, fontSize: 12, height: 1.5))
          else
            for (final n in (res['notes'] as List).cast<String>())
              Padding(padding: const EdgeInsets.only(bottom: 6),
                child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Padding(padding: EdgeInsets.only(top: 5, right: 7),
                      child: Icon(Icons.circle, size: 5, color: _gold)),
                  Expanded(child: Text(n,
                      style: const TextStyle(color: _textB, fontSize: 12, height: 1.45))),
                ])),
          if (res['stoi'] != null) ...[
            const Divider(color: _textDim, height: 20),
            _row(ar ? 'تشابه الوضوح (STOI)' : 'Intelligibility match (STOI)',
                '${(((res['stoi'] as num).toDouble()) * 100).toStringAsFixed(1)}%'),
          ],
          if ((res['alignment'] as Map?)?['correlation'] != null)
            _row(ar ? 'الارتباط' : 'Correlation',
                ((res['alignment'] as Map)['correlation'] as num)
                    .toDouble().toStringAsFixed(2)),
        ]),
      ],
    ]);
  }

  /// A signed dB bar for one frequency band, centred on zero.
  Widget _bandBar(String name, double deltaDb) {
    const maxDb = 12.0;
    final t = (deltaDb.abs() / maxDb).clamp(0.0, 1.0);
    final over = deltaDb.abs() >= 3.0;
    return Padding(padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(children: [
        SizedBox(width: 74, child: Text(name,
            style: const TextStyle(color: _textDim, fontSize: 10.5))),
        Expanded(child: LayoutBuilder(builder: (_, c) {
          final half = c.maxWidth / 2;
          return SizedBox(height: 12, child: Stack(children: [
            Positioned(left: half - 0.5, top: 0, bottom: 0,
                child: Container(width: 1, color: _textDim.withValues(alpha: 0.5))),
            Positioned(
              left: deltaDb >= 0 ? half : half - half * t,
              width: (half * t).clamp(1.0, half),
              top: 2, bottom: 2,
              child: Container(decoration: BoxDecoration(
                  color: (over ? _gold : _teal).withValues(alpha: 0.75),
                  borderRadius: BorderRadius.circular(2)))),
          ]));
        })),
        SizedBox(width: 52, child: Text(
            '${deltaDb >= 0 ? '+' : ''}${deltaDb.toStringAsFixed(1)}',
            textAlign: TextAlign.end,
            style: TextStyle(color: over ? _gold : _textB, fontSize: 10.5,
                fontFamily: 'monospace'))),
      ]));
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
      // S250 — controller-backed so the tags survive a rebuild, persist across
      // sessions, and participate in undo/redo (S237 had to skip all three).
      _card_(ar ? 'بيانات وصفية' : 'Metadata Tags', Icons.label_rounded, [
        TextField(controller: _metaTitleCtrl,
          style: const TextStyle(color: _textA, fontSize: 13),
          decoration: InputDecoration(labelText: ar ? 'العنوان' : 'Title',
              labelStyle: const TextStyle(color: _textDim, fontSize: 12)),
          onChanged: (v) => _metaTitle = v),
        TextField(controller: _metaArtistCtrl,
          style: const TextStyle(color: _textA, fontSize: 13),
          decoration: InputDecoration(labelText: ar ? 'الفنان' : 'Artist',
              labelStyle: const TextStyle(color: _textDim, fontSize: 12)),
          onChanged: (v) => _metaArtist = v),
        TextField(controller: _metaAlbumCtrl,
          style: const TextStyle(color: _textA, fontSize: 13),
          decoration: InputDecoration(labelText: ar ? 'الألبوم' : 'Album',
              labelStyle: const TextStyle(color: _textDim, fontSize: 12)),
          onChanged: (v) => _metaAlbum = v),
        const SizedBox(height: 6),
        GestureDetector(
          onTap: _fileName.isEmpty ? null : () {
            _edit(() => _metaTitle = _fileName.replaceAll(RegExp(r'\.[^.]+$'), ''));
            _syncMetaControllers();
          },
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.auto_awesome_rounded, color: _teal, size: 13),
            const SizedBox(width: 5),
            Text(ar ? 'استخدم اسم الملف كعنوان' : 'Use the file name as the title',
                style: const TextStyle(color: _teal, fontSize: 11, fontWeight: FontWeight.w600)),
          ])),
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
        _row(ar ? 'الإخراج' : 'Output',
            '$_sampleRate Hz · ${_channels == "Mono" ? (ar ? "أحادي" : "Mono") : (ar ? "ستيريو" : "Stereo")}'
            '${_fmt == "WAV" ? " · $_wavBitDepth-bit" : ""}'),
        if (_noiseReduc > 0) _row('Noise Reduction', '${_noiseReduc.round()}%'),
        if (_compress) _row('Compressor', '${_compThresh.round()}dB / ${_compRatio.round()}:1'),
        if (_loudnessTarget != 'Off') _row('Loudness', _loudnessTarget),
        if (_declick)   _row('Declick', '${_declickSens.round()}%'),
        if (_reverse)   _row('Reverse', '✓'),
        // S250 — the Cleanup-tab processing was invisible here, so an export
        // could quietly include dereverb/squeeze/denoise with no mention.
        if (_aiDenoiseOn) _row('AI Denoise',
            '${_aiDenoiseStrength.round()}%${_aiDenoiseNonStat ? " · non-stationary" : ""}'),
        if (_dereverb > 0) _row('Dereverb (WPE)', '${_dereverb.round()}%'),
        if (_harmonicFocus > 0) _row('Transient Cleanup', '${_harmonicFocus.round()}%'),
        if (_vadTrimOn) _row('VAD Trim', 'aggr ${_vadAggr.round()}'),
        if (_squeezeOn) _row('Pause Squeeze',
            '>${_squeezeMax.toStringAsFixed(1)}s → ${_squeezeKeep.toStringAsFixed(2)}s'),
        if (_pitch != 0) _row('Pitch', '${_pitch >= 0 ? "+" : ""}${_pitch.toStringAsFixed(1)} st'),
        if (_tempo != 1.0) _row('Speed', '${_tempo.toStringAsFixed(2)}×'),
        const SizedBox(height: 4),
        Divider(height: 1, color: _border.withValues(alpha: 0.6)),
        const SizedBox(height: 6),
        _row(ar ? 'إعدادات مفعّلة' : 'Settings engaged', '${_dspOnCount()}'),
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
  // S250g — cards cascade in when a tab appears instead of the whole page
  // snapping into place. The counter resets per tab build (see _tabBody), so
  // the stagger follows reading order rather than drifting upward forever.
  int _cardSeq = 0;

  Widget _card_(String title, IconData icon, List<Widget> body) =>
    EntranceFade(
      key: ValueKey('${_tab.name}-$title'),
      index: _cardSeq++,
      child: _cardInner(title, icon, body));

  Widget _cardInner(String title, IconData icon, List<Widget> body) =>
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

  // S250 — every slider snapshots ONCE per drag (onChangeStart) so undo steps
  // are gestures, not individual pixel movements.
  Widget _slider(double val, double min, double max, Color color, ValueChanged<double> onChanged) =>
    Directionality(textDirection: TextDirection.ltr,
      child: SliderTheme(data: SliderThemeData(trackHeight: 5,
        thumbSize: WidgetStateProperty.all(const Size(18, 18)),
        thumbColor: color, activeTrackColor: color.withValues(alpha: 0.9),
        inactiveTrackColor: _border, overlayColor: color.withValues(alpha: 0.15),
        overlayShape: const RoundSliderOverlayShape(overlayRadius: 18)),
        child: Slider(value: val.clamp(min, max), min: min, max: max,
            onChanged: onChanged,
            onChangeStart: (_) { HapticFeedback.selectionClick(); _pushUndo(); })));

  Widget _knob(String label, String valueStr, double val, double min, double max,
      ValueChanged<double> onChanged) =>
    Padding(padding: const EdgeInsets.only(bottom: 12),
      child: Row(children: [
        SizedBox(width: 90, child: Text(label, style: const TextStyle(color: _textB, fontSize: 12))),
        Expanded(child: _slider(val, min, max, _gold, onChanged)),
        const SizedBox(width: 8),
        // S250g — the readout ticks when it changes, so the number you are
        // dragging visibly reacts instead of silently updating.
        ChangePulse(value: valueStr, color: _gold,
          child: Container(
            constraints: const BoxConstraints(minWidth: 60),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
            decoration: BoxDecoration(color: _goldDim.withValues(alpha: 0.4),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: _gold.withValues(alpha: 0.3))),
            child: Text(valueStr, textAlign: TextAlign.end,
                style: const TextStyle(color: _gold, fontSize: 11.5, fontWeight: FontWeight.w700,
                    fontFamily: 'monospace')),
          )),
      ]));

  Widget _chip_(String label, VoidCallback onTap) =>
    GestureDetector(onTap: () { HapticFeedback.selectionClick(); _pushUndo(); onTap(); },
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
        _edit(() { for (int i = 0; i < 10; i++) { _eq[i] = vals[i]; } }); },
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
        // S250: activeColor is deprecated (→ activeThumbColor after 3.31)
        Switch(value: val, activeThumbColor: _gold, inactiveThumbColor: _textDim,
          activeTrackColor: _goldDim, inactiveTrackColor: _border,
          onChanged: (v) { HapticFeedback.selectionClick(); _pushUndo(); onChanged(v); }),
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
  // S250d — a lit lamp now breathes with the shared glow controller, the way a
  // real rack's indicators do. Unlit lamps stay perfectly static (no animation
  // cost for the common case) and the widget is otherwise unchanged.
  Widget _rackLamp(bool on) {
    if (!on) {
      return Container(width: 8, height: 8,
        margin: const EdgeInsetsDirectional.only(end: 10),
        decoration: BoxDecoration(shape: BoxShape.circle,
          color: Colors.transparent,
          border: Border.all(color: _textDim, width: 1.4)));
    }
    return AnimatedBuilder(
      animation: _glowCtrl,
      builder: (_, __) {
        final g = _glowCtrl.value;
        return Container(width: 8, height: 8,
          margin: const EdgeInsetsDirectional.only(end: 10),
          decoration: BoxDecoration(shape: BoxShape.circle,
            color: Color.lerp(_gold, const Color(0xFFFFF1C4), g * 0.5),
            border: Border.all(color: _gold, width: 1.4),
            boxShadow: [BoxShadow(
                color: _gold.withValues(alpha: 0.35 + 0.45 * g),
                blurRadius: 5 + 6 * g, spreadRadius: 0.5 + g)]));
      });
  }

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
    Switch(value: val, activeThumbColor: _gold, inactiveThumbColor: _textDim,
      activeTrackColor: _goldDim, inactiveTrackColor: _border,
      onChanged: (v) { _pushUndo(); onChanged(v); });

  Widget _rackSection(String title, int onCount, List<Widget> rows) {
    if (rows.isEmpty) return const SizedBox.shrink();
    final ar = LangProvider.strings(context).ar;
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
          // S250: was `'$onCount ${onCount == 1 ? "on" : "on"}'` — a ternary
          // with identical branches, and untranslated. Also hide the "0 on"
          // noise on sections that aren't doing anything.
          if (onCount > 0)
            Text(ar ? '$onCount مفعّل' : '$onCount on',
                style: const TextStyle(color: _teal, fontSize: 10, fontFamily: 'monospace')),
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
    _edit(() {
      _bassBoost=0; _trebleBoost=0; _subBass=0; _presence=0; _hpFreq=0; _lpFreq=20000;
      _tremolo=0; _vibrato=0; _chorus=false; _flanger=false; _phaser=false; _crusher=0;
      _haasWiden=false; _stereoFx=0; _channelMode='Stereo'; _swapLR=false;
      _noiseGate=false; _gateThresh=-50; _deEsser=0; _declip=false;
      _autoNormalize=false; _limiter=false; _limiterCeil=-1.0;
      _autoTrimSilence=false; _padStart=0; _padEnd=0;
      _dehumOn=false; _dehumBase=50; _dehumStrength=60; _vocalIso=0;  // S238
      _harmonicFocus=0;                                               // S250
      _fx2OpenId=null;
    });
  }

  /// S250 — total rows in the FX rack, kept next to the rack itself.
  static const int _kFx2Count = 27;

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
    final onHarmFocus = _harmonicFocus != 0;  // S250

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
      // S250 — HPSS transient cleanup, also reachable from the Cleanup tab
      if (vis('Transient Cleanup', 'تنقية العابرات'))
        _rackRow(id: 'harmfocus',
          label: ar ? 'تنقية العابرات' : 'Transient Cleanup', on: onHarmFocus,
          valueStr: _harmonicFocus==0 ? (ar?'معطل':'Off') : '${_harmonicFocus.round()}%',
          body: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            _slider(_harmonicFocus, 0, 100, _gold, (v) => setState(() => _harmonicFocus = v)),
            Text(ar ? 'يخفض قلب الصفحات وطرق الميكروفون ونقرات الفم'
                    : 'Pulls down page turns, mic bumps and mouth clicks',
                style: const TextStyle(color: _textDim, fontSize: 10)),
          ])),
    ];

    final totalOn = [_dehumOn,onVocalIso,  // S238
        onBass,onTreble,onSub,onPresence,onHp,onLp,
        onTrem,onVib,_chorus,_flanger,_phaser,onCrush,
        _haasWiden,onStereoFx,onChanMode,_swapLR,
        _noiseGate,onDeEsser,_declip,_autoNormalize,_limiter,_autoTrimSilence,
        onPadStart,onPadEnd,onHarmFocus]
        .where((b) => b).length;

    return Column(children: [
      Padding(padding: const EdgeInsets.fromLTRB(14, 12, 14, 0),
        child: TextField(
          controller: _fx2SearchCtrl,
          onChanged: (v) => setState(() => _fx2Search = v),
          style: const TextStyle(color: _textA, fontSize: 13),
          decoration: InputDecoration(
            // S250 — the count is derived, not a hardcoded "26" that goes stale
            // every time a row is added (it already had).
            hintText: ar ? 'ابحث في $_kFx2Count تأثيرًا…' : 'Search $_kFx2Count effects…',
            hintStyle: const TextStyle(color: _textDim, fontSize: 12),
            prefixIcon: const Icon(Icons.search_rounded, color: _textDim, size: 19),
            suffixIcon: _fx2Search.isEmpty ? null : IconButton(
                icon: const Icon(Icons.close_rounded, color: _textDim, size: 17),
                onPressed: () {
                  _fx2SearchCtrl.clear();
                  setState(() => _fx2Search = '');
                }),
            filled: true, fillColor: _card, isDense: true,
            contentPadding: const EdgeInsets.symmetric(vertical: 12),
            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(11),
                borderSide: const BorderSide(color: _border)),
            focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(11),
                borderSide: const BorderSide(color: _gold)),
          ))),
      // S250 — searching used to silently show nothing on no match
      if (_fx2Search.trim().isNotEmpty && voiceRows.isEmpty && toneRows.isEmpty &&
          charRows.isEmpty && spaceRows.isEmpty && dynRows.isEmpty)
        Padding(padding: const EdgeInsets.fromLTRB(14, 18, 14, 0),
          child: Row(children: [
            const Icon(Icons.search_off_rounded, color: _textDim, size: 16),
            const SizedBox(width: 8),
            Expanded(child: Text(
                ar ? 'لا تأثير يطابق "${_fx2Search.trim()}"'
                   : 'No effect matches "${_fx2Search.trim()}"',
                style: const TextStyle(color: _textDim, fontSize: 12))),
          ])),
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
            [_noiseGate,onDeEsser,_declip,_autoNormalize,_limiter,_autoTrimSilence,
             onPadStart,onPadEnd,onHarmFocus]
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
    if (_busy) { _warnBusy(); return; }
    if (!await _checkSetup()) return;
    final picked = await FilePicker.platform.pickFiles(
        type: FileType.audio, allowMultiple: true);
    if (picked == null || picked.files.isEmpty) return;
    final paths = picked.files.where((f) => f.path != null).map((f) => f.path!).toList();
    if (paths.isEmpty) return;
    if (!mounted) return;
    setState(() { _busy = true; _busyStart = DateTime.now();
      _busyLabel = ar ? 'تصدير دفعي…' : 'Batch exporting…'; _pct = 0; });
    int done = 0, failed = 0;
    final errors = <String>[];
    try {
      for (int i = 0; i < paths.length; i++) {
        final p = paths[i];
        final name = p.split('/').last;
        if (!mounted) return;
        // S250 — say which file, and how far along, instead of a bare spinner
        setState(() => _busyLabel = ar
            ? 'تصدير ${i + 1}/${paths.length}: $name'
            : 'Exporting ${i + 1}/${paths.length}: $name');
        String? inp;
        try {
          inp = await _safeInput(p);
          final ext = _fmt.toLowerCase();
          final base = name.replaceAll(RegExp(r'\.[^.]+$'), '');
          final dir = await getExternalStorageDirectory()
              ?? await getApplicationDocumentsDirectory();
          final out = '${dir.path}/tilawa_${base}_batch.$ext';
          // S236: batch runs the full Studio Engine (numpy/scipy) per file —
          // same quality as single export — with the ffmpeg chain as fallback.
          final params = _buildDspParams(fullFile: true);
          final res = await _runDspEngine(inp, out, params);
          var okFile = ((res['rc'] as int?) ?? -1) == 0 && File(out).existsSync();
          if (!okFile) {
            final af = _buildAf();
            final cmd = 'ffmpeg -y -i "$inp" '
                '-af ${af.isEmpty ? "anull" : af.join(",")} ${_metaArgs()} '
                '-ar $_sampleRate -ac ${_channels == "Mono" ? 1 : 2} '
                '-acodec ${_codec()} ${_br()} "$out"';
            final res2 = await _proot(cmd, inp, out, timeout: 15);
            okFile = (res2?['rc'] as int? ?? 1) == 0 && File(out).existsSync();
            if (!okFile) errors.add('$name: ${res2?['out'] ?? res['out'] ?? 'failed'}');
          }
          try { File('$out.report.json').deleteSync(); } catch (_) {}
          if (okFile) { done++; } else { failed++; }
        } catch (e) {
          failed++;
          errors.add('$name: $e');
        } finally {
          _dropTemp(inp);
        }
        if (!mounted) return;
        setState(() => _pct = (done + failed) / paths.length);
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
    unawaited(_saveEditorPrefs());  // S237 QoL
    if (!mounted) return;
    if (failed > 0) {
      // S250: failures used to be a bare count with no way to find out why.
      _snackError(Exception(
          '${ar ? "تم" : "Done"}: $done · ${ar ? "فشل" : "failed"}: $failed\n'
          '${errors.take(5).join("\n")}'));
    } else {
      _snack('✓ ${ar ? "تم" : "Done"}: $done');
    }
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
  final double durationSec;   // S250 — for the time ruler
  final bool dimmed;          // S250 — a preview is playing, this isn't it
  final double grab;          // S250d — 0..1 trim-handle grab emphasis
  final double level;         // S250i — real audio level at the playhead, 0..1
  _WavePainter({required this.bars, this.rms, required this.playPos,
      required this.trimStart, required this.trimEnd,
      required this.animT, required this.playing, this.analyzed = false,
      this.durationSec = 0, this.dimmed = false, this.grab = 0,
      this.level = 0});

  // S250 — the strip along the bottom that carries the time ruler
  static const double _rulerH = 16.0;

  static String _tick(double s) {
    final m = s ~/ 60;
    final ss = (s % 60).floor().toString().padLeft(2, '0');
    return '$m:$ss';
  }

  /// Time ruler with a sensible tick step for the file's length.
  void _paintRuler(Canvas c, Size sz) {
    final y = sz.height - _rulerH;
    c.drawLine(Offset(0, y), Offset(sz.width, y),
        Paint()..color = const Color(0xFF1A3A30)..strokeWidth = 0.8);
    if (durationSec <= 0) return;
    const steps = [1.0, 2.0, 5.0, 10.0, 15.0, 30.0, 60.0, 120.0, 300.0,
                   600.0, 900.0, 1800.0, 3600.0];
    double step = steps.last;
    for (final s in steps) {
      if (durationSec / s <= 8) { step = s; break; }
    }
    const label = TextStyle(color: Color(0xFF3D5A65), fontSize: 8.5,
        fontFamily: 'monospace', fontWeight: FontWeight.w600);
    for (double t = 0; t <= durationSec + 1e-6; t += step) {
      final x = (t / durationSec) * sz.width;
      if (x > sz.width - 1) break;
      c.drawLine(Offset(x, y), Offset(x, y + 4),
          Paint()..color = const Color(0xFF24463C)..strokeWidth = 0.8);
      if (t == 0) continue;
      final tp = TextPainter(
          text: TextSpan(text: _tick(t), style: label),
          textDirection: ui.TextDirection.ltr)
        ..layout();
      final tx = (x - tp.width / 2).clamp(0.0, sz.width - tp.width);
      tp.paint(c, Offset(tx, y + 4.5));
    }
  }

  @override
  void paint(Canvas c, Size szFull) {
    // S250 — reserve the bottom strip for the ruler; everything else draws
    // into the remaining box exactly as before.
    final sz = Size(szFull.width, (szFull.height - _rulerH).clamp(10.0, szFull.height));
    final n = bars.length; final bw = sz.width / n; final mid = sz.height / 2;
    final barW = (bw - 2).clamp(1.0, bw);

    // faint dB reference lines at -6 and -12 dBFS of the drawn height
    final gridPaint = Paint()..color = const Color(0xFF163229)..strokeWidth = 0.6;
    for (final f in const [0.5, 0.25]) {
      c.drawLine(Offset(0, mid - mid * 0.9 * f), Offset(sz.width, mid - mid * 0.9 * f), gridPaint);
      c.drawLine(Offset(0, mid + mid * 0.9 * f), Offset(sz.width, mid + mid * 0.9 * f), gridPaint);
    }

    // S242: SoundCloud-style progress waveform. Bars the playhead has already
    // passed light up GOLD; bars still ahead stay TEAL — so the sweep visibly
    // "intersects" the wave as it plays. A tight energy bump + scan glow marks
    // the exact play point. (Old code left every bar the same teal with only a
    // faint flat wash, plus a jumpy global sine that read as broken.)
    Paint vgrad(Color a, Color b) => Paint()
      ..shader = ui.Gradient.linear(const Offset(0, 0), Offset(0, sz.height), [a, b]);
    final playedCore   = vgrad(const Color(0xFFF3D170), const Color(0xFF8A6A12));
    final playedGhost  = Paint()..color = const Color(0xFFD4AF37).withValues(alpha: 0.30);
    final aheadCore    = vgrad(const Color(0xFF37E0B8), const Color(0xFF0C5B3C));
    final aheadGhost   = Paint()..color = const Color(0xFF1DB898).withValues(alpha: 0.26);
    final inactive     = Paint()..color = const Color(0xFF24463C).withValues(alpha: 0.55);
    final inactiveGhost= Paint()..color = const Color(0xFF1A3A30).withValues(alpha: 0.22);
    final hotCore      = vgrad(const Color(0xFFFFF6D0), const Color(0xFFE7BE3F));
    final rTrim        = Paint()..color = Colors.black.withValues(alpha: 0.35);

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
      // S250i — AUDIO-REACTIVE. The bump used to be a fixed 0.16 regardless of
      // what was playing, so a whisper and a peak looked identical. It is now
      // scaled by `level`: the real analysed amplitude at the playhead (peak
      // and RMS of that bucket, from the numpy --analyze pass). Quiet passages
      // barely ripple, loud ones visibly kick, and the reaction spreads a
      // little wider when the audio is louder.
      if (playing) {
        final dist = (i - headF).abs();
        // Wider than before, and a smooth flat-topped falloff rather than a
        // linear ramp to a hard cutoff — the old 2-4 bar window with a sharp
        // edge looked like a cursor artefact rather than the wave responding.
        final reach = 3.0 + 4.5 * level;                 // louder = wider
        if (dist < reach) {
          final u = dist / reach;
          final falloff = (1 - u * u) * (1 - u * u);
          final wob = 0.72 + 0.28 * sin(animT * 2 * pi * 3 + i * 0.42);
          final bump = (0.05 + 0.30 * level) * falloff * wob;
          amp += bump;
          rmsAmp += bump * 0.8;
        } else if (!analyzed) {
          // Placeholder-only extra liveliness while waiting on the analyser.
          amp += 0.14 * amp * sin(animT * 2 * pi + i * 0.28);
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
    // S250 BUG FIX: this gradient passes three colors, and ui.Gradient.linear
    // REQUIRES colorStops whenever colors.length != 2 — it threw
    // ArgumentError('"colors" must have length 2 if "colorStops" is omitted')
    // on every single paint since S242. Because the throw happened here,
    // paint() aborted at this line, so everything after it never drew:
    // the playhead line, its cap dots, the trim shading edges and BOTH TRIM
    // HANDLES were invisible on the waveform in every build. Caught by the new
    // render test in test/widget_test.dart.
    final px = playPos * sz.width;
    // S250i — the scan glow widens and brightens with the actual level, so the
    // playhead reads as a meter rather than a fixed marker.
    final glowW = 20.0 + 34.0 * level;
    c.drawRect(Rect.fromLTWH(px - glowW / 2, 0, glowW, sz.height),
        Paint()..shader = ui.Gradient.linear(
            Offset(px - glowW / 2, 0), Offset(px + glowW / 2, 0), [
          Colors.transparent,
          const Color(0xFFF3D170).withValues(
              alpha: playing
                  ? (0.14 + 0.26 * level) + 0.08 * sin(animT * 2 * pi * 2)
                  : 0.14),
          Colors.transparent,
        ], const [0.0, 0.5, 1.0]));
    c.drawLine(Offset(px, 0), Offset(px, sz.height),
        Paint()..color = const Color(0xFFFFF1C4)..strokeWidth = 1.6);
    final capPaint = Paint()..color = const Color(0xFFFFF1C4);
    c.drawCircle(Offset(px, 3), 2.6, capPaint);
    c.drawCircle(Offset(px, sz.height - 3), 2.6, capPaint);

    // S250 — handles now look grabbable: a full-height rail plus a wide grip
    // pill with grip lines, matching the ±26 px drag hit-box in the widget.
    void handle(double x, Color col, bool start) {
      // S250d — the grabbed handle swells and casts a glow, so a drag has
      // physical feedback instead of the bar simply teleporting.
      final g = grab.clamp(0.0, 1.0);
      if (g > 0) {
        c.drawRect(Rect.fromLTWH(x - 16, 0, 32, sz.height),
            Paint()..shader = ui.Gradient.linear(
                Offset(x - 16, 0), Offset(x + 16, 0),
                [Colors.transparent, col.withValues(alpha: 0.22 * g), Colors.transparent],
                const [0.0, 0.5, 1.0]));
      }
      c.drawLine(Offset(x, 0), Offset(x, sz.height),
          Paint()..color = col..strokeWidth = 2.0 + 1.4 * g);
      final gw = 13.0 + 4.0 * g, gh = 30.0 + 10.0 * g;
      final gx = start ? x : x - gw;
      final rect = RRect.fromRectAndCorners(
          Rect.fromLTWH(gx, mid - gh / 2, gw, gh),
          topLeft: Radius.circular(start ? 3 : 7),
          bottomLeft: Radius.circular(start ? 3 : 7),
          topRight: Radius.circular(start ? 7 : 3),
          bottomRight: Radius.circular(start ? 7 : 3));
      c.drawRRect(rect, Paint()..color = col.withValues(alpha: 0.92));
      final grip = Paint()..color = const Color(0xFF02100C)..strokeWidth = 1.2;
      for (final dy in const [-5.0, 0.0, 5.0]) {
        c.drawLine(Offset(gx + 4, mid + dy), Offset(gx + gw - 4, mid + dy), grip);
      }
      // small flag at the top so the exact edge stays readable
      final p = Path();
      if (start) {
        p.moveTo(x, 0); p.lineTo(x + 9, 0); p.lineTo(x, 10);
      } else {
        p.moveTo(x, 0); p.lineTo(x - 9, 0); p.lineTo(x, 10);
      }
      p.close();
      c.drawPath(p, Paint()..color = col);
    }
    handle(x0, const Color(0xFF1DB898), true);
    handle(x1, const Color(0xFFD4AF37), false);

    // S250d — IDLE SHIMMER. Verified by the animation gate in
    // test/screenshot_test.dart, which measured a 0.00% frame-to-frame diff on
    // the idle editor: with playback paused nothing on the screen moved at all,
    // because the only motion was gated behind `playing`. A soft highlight now
    // sweeps the selected region so the waveform reads as live rather than as a
    // frozen screenshot. It is deliberately confined to the trim window — that
    // is the part the user is working on — and skipped entirely while playing,
    // where the playhead already carries the motion.
    if (!playing && !dimmed && x1 > x0) {
      final sweep = (animT * 1.6) % 1.6 - 0.3;      // travels, with a pause
      final cx = x0 + (x1 - x0) * sweep.clamp(0.0, 1.0);
      const w = 64.0;
      if (sweep >= 0 && sweep <= 1) {
        c.save();
        c.clipRect(Rect.fromLTWH(x0, 0, x1 - x0, sz.height));
        c.drawRect(Rect.fromLTWH(cx - w / 2, 0, w, sz.height),
            Paint()..shader = ui.Gradient.linear(
                Offset(cx - w / 2, 0), Offset(cx + w / 2, 0),
                [Colors.transparent,
                 const Color(0xFF37E0B8).withValues(alpha: 0.10),
                 Colors.transparent],
                const [0.0, 0.5, 1.0]));
        c.restore();
      }
    }

    _paintRuler(c, szFull);

    // S250 — a preview is playing something else; grey the source wave so the
    // playhead position isn't read as "where the preview is".
    if (dimmed) {
      c.drawRect(Rect.fromLTWH(0, 0, szFull.width, szFull.height),
          Paint()..color = const Color(0xFF020D17).withValues(alpha: 0.45));
    }
  }

  @override bool shouldRepaint(_WavePainter o) =>
      o.playing != playing ||
      o.playPos != playPos ||
      o.trimStart != trimStart ||
      o.trimEnd != trimEnd ||
      o.dimmed != dimmed ||
      o.analyzed != analyzed ||
      o.durationSec != durationSec ||
      o.grab != grab ||
      o.level != level ||
      o.bars.length != bars.length ||
      // S250d: animT now matters whether or not playback is running — the
      // idle shimmer needs it. (The earlier `playing && ...` guard is exactly
      // why the animation gate measured a 0.00% idle diff.) Still far cheaper
      // than the original unconditional `=> true`, which repainted on every
      // rebuild including ones with no visual change at all.
      o.animT != animT ||
      !identical(o.bars, bars) ||
      !identical(o.rms, rms);
}

/// S250i — test hook. `_WavePainter` is private (correctly: nothing outside
/// this file should build one), but the audio-reactivity gate in
/// test/screenshot_test.dart has to construct one with a chosen `level` to
/// prove the value reaches the drawing. This is the smallest possible seam.
class WavePainterProbe {
  const WavePainterProbe._();
  static CustomPainter make({
    required List<double> bars,
    required List<double> rms,
    required double playPos,
    required double level,
  }) => _WavePainter(bars: bars, rms: rms, playPos: playPos,
      trimStart: 0, trimEnd: 1, animT: 0.5, playing: true,
      analyzed: true, durationSec: 12, level: level);
}

// ── S250d: PROCESSING SWEEP ─────────────────────────────────────────────────
// A short, fading arc that chases the progress ring. Deliberately tiny: one
// arc, no shader allocation per frame beyond the sweep gradient.
class _SweepPainter extends CustomPainter {
  final double t;
  const _SweepPainter({required this.t});

  @override
  void paint(Canvas c, Size sz) {
    final r = sz.shortestSide / 2 - 2;
    final rect = Rect.fromCircle(center: Offset(sz.width / 2, sz.height / 2), radius: r);
    c.drawArc(rect, -pi / 2, pi * 0.55, false,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.2
          ..strokeCap = StrokeCap.round
          ..shader = ui.Gradient.sweep(
              rect.center,
              [const Color(0x001DB898), const Color(0xFF37E0B8), const Color(0x00D4AF37)],
              const [0.0, 0.14, 0.28]));
  }

  @override bool shouldRepaint(_SweepPainter o) => o.t != t;
}

// ── SPECTRUM PAINTER — S236: 30-band average spectrum from numpy analysis ────
class _SpectrumPainter extends CustomPainter {
  final List<double> bands;
  final double reveal;   // S250d — 0..1 staggered entrance
  _SpectrumPainter({required this.bands, this.reveal = 1});

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
      // each band starts slightly after the one before it
      final lead = (i / n) * 0.35;
      final t = ((reveal - lead) / (1 - 0.35)).clamp(0.0, 1.0);
      final v = bands[i].clamp(0.0, 1.0) * t;
      final h = v * (sz.height - 2);
      final x = i * bw + 1.0;
      c.drawRRect(RRect.fromRectAndRadius(
          Rect.fromLTWH(x, sz.height - h, bw - 2, h), const Radius.circular(2)),
          Paint()..shader = ui.Gradient.linear(
              Offset(0, sz.height), const Offset(0, 0),
              const [Color(0xFF0A5A3A), Color(0xFF1DB898), Color(0xFFD4AF37)],
              const [0.0, 0.55, 1.0]));
    }
  }

  @override bool shouldRepaint(_SpectrumPainter o) {
    if (o.reveal != reveal) return true;
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
      if (i == 0) { path.moveTo(x, y); } else { path.lineTo(x, y); }
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
      const Color(0xFF1DB898).withValues(alpha: 0.18),
      const Color(0xFF1DB898).withValues(alpha: 0.0)]));
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
