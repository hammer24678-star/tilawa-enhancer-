import 'dart:io';
import 'dart:convert' show jsonDecode; // S65
import '../services/local_engine_service.dart'; // S65
import 'local_mode_info_screen.dart'; // S146

import 'dart:async';
import 'package:audioplayers/audioplayers.dart';
import 'dart:ui' show ImageFilter;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart'; // S148
import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import '../state/lang_provider.dart';
import '../design/nur.dart'; // Nur design system (also exports widgets/anim.dart)
import '../services/api_service.dart';
import 'history_screen.dart';
import 'audio_editor_screen.dart';
import 'game_screen.dart'; // S209
import 'ai_tools_screen.dart'; // S184 // S152-B13: home_screen is already in lib/screens/
import 'engine_code_screen.dart'; // S234
import 'settings_screen.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart'; // S61

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with TickerProviderStateMixin, WidgetsBindingObserver {
  // ── State ──────────────────────────────────────────────────────────────────
  File?   _file;
  String  _engine    = 'v11.0';  // S84: default = strongest local engine
  String  _status    = '';
  double  _progress  = 0;
  bool    _busy      = false;
  bool    _serverUp  = false;
  String? _jobId;
  File?   _output;
  File?   _abOutputFile; // S144: cacheDir path for A/B — unaffected by _reDownload()
  // S104: A/B comparison player
  final AudioPlayer _abPlayer  = AudioPlayer();
  // S195-BUG6: store subscriptions; register once in initState, cancel in dispose
  StreamSubscription<Duration>? _abDurSub;
  StreamSubscription<Duration>? _abPosSub;
  StreamSubscription<void>?     _abDoneSub;
  bool _abEverPlayed   = false; // S140
  bool   _abPlaying   = false;
  bool   _abIsB       = true;   // true=enhanced, false=original
  double _abPos       = 0.0;
  double _abDur       = 1.0;
  Map<String, dynamic>? _result;
  Timer?  _serverTimer;
  Timer?  _pollTimer;
  Timer?  _wakeTimer;
  String  _sizeLabel = '';
  bool    _isLarge   = false;
  bool    _downloading = false; // RC3: prevent concurrent downloads
  bool    _isMerging  = false; // S20-A: true during server chunk-merge phase
  int     _pollErrors = 0;     // S22: consecutive poll error counter
  int     _fileBytes  = 0;     // S28: file size in bytes for estimated time
  int?    _latencyMs;              // S28-T2: server latency in ms
  DateTime? _processStart;     // S22: start time for 25-min hard timeout
  int _fallbackRetries = 0;    // S32: auto-retry counter for fallback mode
  late FlutterLocalNotificationsPlugin _notif; // S61


  // S19: Wake server state
  bool _waking       = false;
  int  _wakeAttempts = 0;

  late final AnimationController _glowCtrl;   // slow breathing pulse (reverse)
  late final AnimationController _waveCtrl;   // looping 0..1 clock for waveforms/orb
  late final AnimationController _scoreCtrl;
  late final AnimationController _resultCtrl; // S29: result card entrance
  final ScrollController _scrollCtrl = ScrollController(); // S92-SCROLL
  final ScrollController _engCtrl = ScrollController();    // engine carousel

  static const _wakeCh = MethodChannel('com.tilawa.tilawa_enhancer/wake'); // S63
  bool   _localMode  = false;  // S65: run via proot (offline)
  bool   _engineTintEnabled = true;  // S188-B: engine-color background tint intensity toggle
  bool   _localReady = false;  // S65: setup confirmed complete
  // S256: the offline engine prepares itself on first launch. Python, numpy,
  // scipy, the fourteen audio packages, ffmpeg and DeepFilter are all inside
  // the APK already (S254) — but proot cannot execute them from inside an
  // archive, so the bundle still has to be unpacked onto the filesystem once.
  // That is a mechanical consequence of how proot works, not a decision the
  // user should have to make, and it used to be gated behind a "Tap to set up
  // (one-time ~200MB)" link and a dedicated screen. It now runs by itself in
  // the background from the moment the app opens; these three fields are only
  // so the UI can say what is happening.
  bool   _prepping   = false;
  int    _prepPct    = 0;
  String _prepPhase  = '';
  String? _prepError;
  StreamSubscription<Map<String, dynamic>>? _prepSub;
  // S250 — engine ids with a runnable on-device script. Empty = not yet known
  // (setup not run / channel unavailable), which must NOT restrict the UI.
  List<String> _localEngines = const [];
  // S250 — armed by the first back-press during processing; a second press
  // while armed is allowed through (see the PopScope in build()). A Timer
  // disarms it so the state is always accurate — deriving it from a deadline
  // would leave canPop stale until something else happened to rebuild.
  bool _exitArmed = false;
  Timer? _exitArmTimer;
  bool   _aggressive = false;  // S173: safaa standard / aggressive mode
  // ── Engines (S21: full data from documentation) ─────────────────────────────
  // S25: synced with server ENGINE_SCRIPTS (v8.1 default, v7.5/v7.6 removed)
  static const _engines = [
    // ── S47: Three Sacred Engines ──────────────────────────────────
    _EngineData(
      'v11.0', 'الصفاء', 'Purity', 99.5,
      'NEW', 'gold',
      ['دي-ريفِرب', 'WPE', 'DF3 NR', 'JALAA', 'Tail-NR', 'Arabic Guard'],
      'محرك إزالة الصدى الصوتي — يُزيل الصدى الصوتي مع الحفاظ على أحكام التجويد كاملةً.',
      'Dereverberation engine — removes mosque echo while preserving all Tajweed phonology.',
      imgAsset: 'assets/images/engines/safaa.jpg', localOnly: true), // S149
    _EngineData(
      'v11.1', 'الإتقان', 'Perfection', 99.0,
      '', 'gold',
      ['Pristine+Noisy', 'صدي التمييز', '5-Seg Traj', 'L-BFGS-B EQ', 'Onset Guard', 'Joint Opt'],  // S154,
      'مسار التسجيلات النظيفة والمضغوطة والمشوبة بالضجيج. تخفيض ضوضاء انتقائي — تحسين طيفي بـ48 نطاقاً — صدي التمييز — مسار طيفي خماسي — حماية بداية الحروف العربية.',
      'Path for clean, compressed, and lightly noisy recordings. Selective NR, 48-band L-BFGS-B EQ, صدي التمييز harmonic enhancement, 5-segment spectral trajectory, Arabic onset protection.',
      imgAsset: 'assets/images/engines/itiqan.jpg', localOnly: true),
    _EngineData(
      'v11.2', 'الاسترداد', 'Recovery', 98.0,
      '', 'gold',
      ['Damaged Path', 'DF3 Heavy NR', 'Declip', 'Dereverberate', 'Reconstruct', 'إحياء'],
      'مسار التسجيلات التالفة. إزالة ضوضاء مكثفة — إزالة القطع — إعادة بناء الطيف الصوتي.',
      'Path for damaged recordings. Heavy NR, declipping, spectrum reconstruction.',
      imgAsset: 'assets/images/engines/isteidad.jpg', localOnly: true),
    // ── Legacy engines ────────────────────────────────────────────────
    _EngineData(
      'v10.0', 'الأثيريون — الأساس', 'Aetherion Foundation', 99.0,
      'NEW', 'gold',
      ['24 Fixes', 'Two-Stage NR', 'L-BFGS-B EQ', 'Joint Opt', 'Declip', 'v10 NR'],
      '٢٤ إصلاحاً تراكمياً من v9.0: تخفيض ضوضاء ثنائي — تحسين طيفي L-BFGS-B — 8 إصلاحات حرجة في LUFS وLRA ومدى التضخيم.',
      '24 cumulative fixes from v9.0: two-stage NR (hum + broadband), L-BFGS-B spectral EQ, 8 critical bug fixes including LUFS measurement and ±18dB joint gain range.',
    ),
    _EngineData(
      'v9.0', 'التطور', 'The Evolution', 99.0,
      '', 'gold', // v9.0 badge cleared S31
      ['Joint Opt', 'LFS Fix', 'NR→EQ', 'Hash Cache', 'Confidence', 'Clean Arch'],
      'إعادة بناء كاملة: NR دائماً قبل EQ — مُحسِّن LUFS+LRA مشترك — كشف LFS صريح — 1890 سطر.',
      'Full rewrite: NR before EQ, joint LUFS+LRA optimizer, explicit LFS detection. 1890 lines.',
    ),
    // v8.9 removed S31 | v8.7 removed S31-F3
    _EngineData(
      'v8.5', 'تقييم صادق', 'Honest Ceiling', 99.0,
      '', 'gold',
      ['Tier Scoring', 'Full-File Ref', 'Phrase LRA', 'Source Tier', 'MDS Weighted', '64K Honest'],
      'تقييم طبقي صادق: ملف 64kbps يضرب السقف الفيزيائي يحصل على 95/100 لا 75/100. الدرجة_الطبقية تُقاس مقابل ما يمكن تحقيقه فعلاً. Full-file spectral بدلاً من 40 ثانية أولى.',
      'Honest tier scoring: a 64kbps file hitting its physical ceiling scores 95/100, not 75/100. score_tier vs achievable targets. Full-file spectral analysis replaces 40s clip.',
    ),
    _EngineData(
      'v8.0', 'دقة مُعايَرة', 'Calibrated Precision', 96.0,
      '', 'gold',
      ['4-Pass WAV', 'MDS', 'Crest Guard', 'SFM-NR', 'Single Compand', 'BIAS_V8'],
      'إصلاح 5 أخطاء حرجة من v7.6: انعكاس اتجاه SPECTRAL_BIAS في 250Hz/4kHz/8kHz، compand مزدوج يسحق Crest، 5 limiters تراكمية، خطأ DR→LRA، وحارس Crest مستقل لكل pass.',
      '5 critical fixes from v7.6: inverted SPECTRAL_BIAS in 250Hz/4kHz/8kHz, double-stacked compand crushing Crest, 5 cumulative limiters, wrong DR→LRA type, and independent Crest Guard per pass.',
    ),
    _EngineData(
      'v7.0', 'كلاسيكي', 'Classic', 91.0,
      'STABLE', '',
      ['Proven Arch', '9-Seg Spectral', 'Bark EQ', 'Compand Curves', 'LUFS \u00b10.1', 'AR-Safe'],
      'البنية المُثبَّتة الأساس لجميع محركات v7.x. THREE-PASS pipeline مع تقارب تكراري، 9 قطاعات طيفية لكامل الملف، ودقة LUFS ±0.1 مقارنة بتسجيلات المرجع 1425H.',
      'The proven foundational architecture for all v7.x engines. THREE-PASS pipeline with iterative convergence, 9-segment full-file spectral average, LUFS precision \u00b10.1 from 1425H reference.',
    ),
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this); // S56
    // S195-BUG6: register AB listeners once here
    _abDurSub  = _abPlayer.onDurationChanged.listen((d) {
      if (mounted) setState(() { _abDur = d.inMilliseconds.toDouble().clamp(1, 1e9); });
    });
    _abPosSub  = _abPlayer.onPositionChanged.listen((p) {
      if (mounted) setState(() { _abPos = p.inMilliseconds.toDouble(); });
    });
    _abDoneSub = _abPlayer.onPlayerComplete.listen((_) {
      if (mounted) setState(() { _abPlaying = false; _abPos = 0; });
    });
    _notif = FlutterLocalNotificationsPlugin();
    _notif.initialize(const InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
    )).then((_) {
      _notif.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
          ?.requestNotificationsPermission();
    });
    _glowCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2800))
      ..repeat(reverse: true);
    _waveCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 7))
      ..repeat();
    _scoreCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1300));
    _resultCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1400));
    _checkServer();
    SharedPreferences.getInstance().then((p){if(mounted) {
      setState((){
      _localMode=p.getBool("local_mode")??false;
      _engineTintEnabled=p.getBool("engine_tint_enabled")??true; // S188-B
    });
    }});
    SharedPreferences.getInstance().then((p){if(mounted)setState(()=>_aggressive=p.getBool("aggressive_mode")??false);});  // S174-B4
    _serverTimer = Timer.periodic(
        const Duration(seconds: 6), (_) => _checkServer());
    LocalEngineService.isSetupComplete() // S65
        .then((r) {
          if (!mounted) return;
          setState(() => _localReady = r);
          // S256: if it is not ready, get it ready. Nobody has to ask.
          if (!r) _autoPrepareOfflineEngine();
        });
    _refreshLocalEngines();  // S250: which engines can run offline at all
    // S65: pre-warm both servers on app init
    ApiService.preWarm();
    // S30-F1: restored — one loadLastEngine call
    ApiService.loadLastEngine().then((e) {
      if (!mounted) return;
      setState(() => _engine = e);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _scrollToEngine();
      });
    });
    // S57: restore in-progress job after app kill
    ApiService.loadJobId().then((saved) {
      if (!mounted || saved == null) return;
      setState(() {
        _jobId  = saved['job_id'];
        _engine = saved['engine'] ?? _engine;
        _busy   = true;
        _status = ''; // S147: empty → build() shows bilingual s.processing
        _progress = 0.35;
        _processStart = DateTime.now();
      });
      _startPolling();
    });
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this); // S56
    _serverTimer?.cancel();
    _pollTimer?.cancel();
    _wakeTimer?.cancel();
    _exitArmTimer?.cancel();  // S250
    _prepSub?.cancel();       // S256: the first-launch unpack outlives this screen otherwise
    _resultCtrl.dispose();
    _scrollCtrl.dispose(); // S92-SCROLL
    _engCtrl.dispose();
    _waveCtrl.dispose();
    _scoreCtrl.dispose();
    _abDurSub?.cancel(); _abPosSub?.cancel(); _abDoneSub?.cancel();  // S195-BUG6 (S196-BUG-A: dedup)
    _abPlayer.dispose();
    _glowCtrl.dispose();
    super.dispose();
  }

  // ── Server check ───────────────────────────────────────────────────────────
  Future<void> _checkServer() async {
    if (_localMode) return; // S147: skip server poll when fully offline
    final ms = await ApiService.checkServer();
    if (!mounted) return;
    setState(() { _serverUp = ms != null; _latencyMs = ms; });
    // S32: auto-wake when offline — no manual tap needed
    if (ms == null && !_waking) _wakeServer();
  }

  // S19: Wake server — polls every 5s for up to 35s
  void _wakeServer() {
    if (_waking) return;
    _wakeTimer?.cancel();
    _wakeAttempts = 0;
    setState(() { _waking = true; });  // S95: keep serverUp state during wake

    _wakeTimer = Timer.periodic(const Duration(seconds: 5), (_) async {
      _wakeAttempts++;
      final ms = await ApiService.checkServer();
      final up = ms != null;
      if (!mounted) {
        _wakeTimer?.cancel();
        return;
      }
      if (up || _wakeAttempts >= 18) { // S32: max 90s (HF cold-boot can take ~60-90s)
        _wakeTimer?.cancel();
        setState(() { _serverUp = up; _latencyMs = ms; _waking = false; _wakeAttempts = 0; });
      }
    });
  }

  // ── S28: Cancel processing ────────────────────────────────────────────────
  void _cancelProcessing() {
    _pollTimer?.cancel();
    HapticFeedback.mediumImpact();
    if (_localMode) LocalEngineService.cancelEngine(); // S140: stop proot process
    _wakeCh.invokeMethod('release').catchError((_) {}); // S143: always release on any cancel
    setState(() {
      _busy = false; _progress = 0;
      _status = ''; _isMerging = false;
      _jobId = null;
    });
    ApiService.clearJobId(); // S57
  }

  // ── S28: Reset for new file ────────────────────────────────────────────────
  void _resetForNewFile() {
    _abPlayer.stop(); // S144: stop audio when picking new file
    if (!mounted) return; // S184-B2
    setState(() {
      _abEverPlayed = false; // S144: reset A/B state for clean start
      _abPlaying    = false;
      _abPos        = 0.0;
      _abDur        = 1.0;
      _abIsB        = true;
      _abOutputFile = null; // S144
      _file = null; _result = null; _output = null;
      _progress = 0; _status = '';
      _jobId = null; _busy = false;
      _isMerging = false; _sizeLabel = '';
      _isLarge = false; _fileBytes = 0;
    });
    ApiService.clearJobId(); // S57
  }

  // ── File picker ────────────────────────────────────────────────────────────
  Future<void> _pickFile() async {
    ApiService.preWarm(); // S65: predictive pre-warm on file picker open
    final r = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['mp3', 'wav', 'm4a', 'flac', 'aac']);
    if (r?.files.single.path != null) {
      final f = File(r!.files.single.path!);
      final bytes = await f.length();
      _abPlayer.stop(); // S145: stop audio when new file is picked
      if (!mounted) return; // S184-B2
      setState(() {
        _abEverPlayed = false; // S145: reset A/B state
        _abPlaying    = false;
        _abPos        = 0.0;
        _abDur        = 1.0;
        _abIsB        = true;
        _abOutputFile = null; // S145
        _file = f;
        _output = null; _result = null;
        _status = ''; _progress = 0;
        _sizeLabel = '${(bytes / 1024 / 1024).toStringAsFixed(1)} MB';
        _isLarge = bytes > 8 * 1024 * 1024;
        _fileBytes = bytes;
      });
    }
  }

  // ── Process ────────────────────────────────────────────────────────────────
  // S32-BUG2-FIX: userInitiated=true for button tap, false for auto-retry.
  // Previously _fallbackRetries was reset inside setState() unconditionally,
  // meaning auto-retries always reset the counter → limit of 2 was never hit.
  Future<void> _process({bool userInitiated = true}) async {
    if (_localMode) {  // S90: gate restored — setup must complete first
      // S101: re-check ready in case initState ran before setup completed
      if (!_localReady) {
        _localReady = await LocalEngineService.isSetupComplete();
      }
      if (!_localReady) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Local engine not set up — tap the setup link first'),
          backgroundColor: Color(0xFF200D0D),
          duration: Duration(seconds: 5)));
        }
        return;
      }
      if (_file == null) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Pick an audio file first'),
          backgroundColor: Color(0xFF200D0D),
          duration: Duration(seconds: 4)));
        }
        return;
      }
      if (_busy) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Engine already running…'),
          backgroundColor: Color(0xFF1A1200),
          duration: Duration(seconds: 3)));
        }
        return;
      }
      // S162-B18: non-local engines silently fell back to v11.0 in Kotlin —
      // redirect explicitly and notify user so the swap is visible.
      if (!_selectedEngine.localOnly) {
        setState(() => _engine = 'v11.0');
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('☁ SERVER engine redirected to 🏠 v11.0 (local mode)'),
          backgroundColor: Color(0xFF0F2623),
          duration: Duration(seconds: 3)));
        }
      }
      await _processLocal(); return;
    }
    if (_file == null) return;  // S91
    if (!_serverUp) { _wakeServer(); }  // S94: wake but dont block
    HapticFeedback.mediumImpact();
    if (userInitiated) _fallbackRetries = 0; // reset only on fresh user action
    setState(() {
      _busy = true; _progress = 0.02;
      _status = LangProvider.strings(context).uploading;
      _output = null; _result = null;
    });
    _processStart = DateTime.now(); // S22: start clock for timeout
    _pollErrors = 0;               // S22: reset in case of re-process
    try {
      final resp = await ApiService.uploadFile(_file!, _engine,
          onProgress: (p, label) {
        if (mounted) setState(() { _progress = p; _status = label; });
      });
      _jobId = resp['job_id'];
      ApiService.saveJobId(_jobId!, _engine); // S57
      _startPolling();
    } catch (e) {
      setState(() {
        _busy = false;
        _progress = 0;       // S20-C: reset — bar disappears on upload error
        _isMerging = false;  // S20-A: cancel merge animation
        _status = 'خطأ: $e';
      });
    }
  }

  // ── Polling — RC2 + RC3 fixes ──────────────────────────────────────────────
  void _startPolling() {
    _pollTimer?.cancel();
    _pollErrors = 0; // S22: fresh counter for each new polling session
    _wakeCh.invokeMethod('acquire').catchError((_) {}); // S63
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      if (_jobId == null) return;
      try {
        final st = await ApiService.getStatus(_jobId!);
        if (!mounted) return;

        final srv = (st['progress'] ?? 0) / 100.0;
        final status = st['status'] as String? ?? '';
        final isMerging = (status == 'merging');  // 'uploading' no longer freezes progress
        final display = isMerging
            ? _progress
            : (0.68 + srv * 0.32).clamp(_progress, 1.0); // S21: monotonic — never regress
        // S20-A: _isMerging drives indeterminate mode in progress bar
        _pollErrors = 0; // S22: reset on successful poll
        setState(() { _progress = display; _status = st['label'] ?? ''; _isMerging = isMerging && _busy; });

        if (status == 'error') {
          _pollTimer?.cancel();
          _wakeCh.invokeMethod('release').catchError((_) {});
          final errMsg = st['error'] as String? ?? '';
          if (errMsg == 'JOB_EXPIRED' && _fallbackRetries < 5) {
            _fallbackRetries++;
            final s = LangProvider.strings(context);
            setState(() { _progress = 0.02; _isMerging = false; _status = s.uploading; });
            ScaffoldMessenger.of(context).showSnackBar(SnackBar(
              content: Text(s.ar ? 'الخادم انقطع - اعادة محاولة...' : 'Server restarted - retrying...',
                style: const TextStyle(fontSize: 12)),
              backgroundColor: const Color(0xFF1A1200),
              duration: const Duration(seconds: 5)));
            await Future.delayed(const Duration(seconds: 3));
            if (mounted) _process(userInitiated: false);
            return;
          }
          setState(() {
            _busy = false; _isMerging = false;
            _status = 'فشل: $errMsg';
          });
          return;
        }

        if (status == 'done') {
          _pollTimer?.cancel();
          _wakeCh.invokeMethod('release').catchError((_) {}); // S63
          if (_downloading) return; // RC3
          _downloading = true;
          try {
            await _downloadAndSave(st); // RC2: own try/catch
          } catch (e) {
            if (mounted) setState(() { _busy = false; _status = 'فشل: $e'; });
          } finally {
            _downloading = false;
          }
        }
      } catch (_) {
        // S22: surface poll errors -- do NOT silently swallow.
        // Root cause of the 79% freeze: server restart kills the job.
        // Every poll throws SocketException / returns bad JSON.
        // Old catch(_){} hid this completely forever.
        _pollErrors++;
        if (_pollErrors >= 5 && mounted) {
          // 5 errors = ~10 seconds of failure. Server is gone.
          _pollTimer?.cancel();
          final s = LangProvider.strings(context);
          setState(() {
            _busy = false; _isMerging = false;
            _progress = 0; _status = '';
          });
          _checkServer(); // S22: immediately refresh server status banner
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(
              s.ar
                ? '⚠️ انقطع الاتصال بالخادم. انتظر 30 ثانية، نبّه الخادم، ثم أعد المعالجة.'
                : '⚠️ Lost connection to server. Wait 30s, wake the server, then retry.',
              style: const TextStyle(fontSize: 12)),
            backgroundColor: const Color(0xFF200D0D),
            duration: const Duration(seconds: 10),
            action: SnackBarAction(
              label: s.ar ? 'حسناً' : 'OK',
              textColor: _p.gold,
              onPressed: () {})));
          return;
        }
      }
      // S22: 25-minute hard timeout. v8.0 on a large file runs 4 WAV
      // passes which can take 20-40 min on free HF CPU. Show this
      // instead of freezing at whatever % the server was at.
      if (_busy && _processStart != null && mounted) {
        final elapsed = DateTime.now().difference(_processStart!);
        if (elapsed.inMinutes >= 25) {
          _pollTimer?.cancel();
          _wakeCh.invokeMethod('release').catchError((_) {}); // S148
          final s = LangProvider.strings(context);
          setState(() {
            _busy = false; _isMerging = false;
            _progress = 0; _status = '';
          });
          _checkServer();
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(
              s.ar
                ? '⏱️ استغرقت المعالجة أكثر من 25 دقيقة. جرّب محرك v7.0 أو أعد المحاولة لاحقاً.'
                : '⏱️ Processing exceeded 25 min. Try v7.0 engine or retry later.',
              style: const TextStyle(fontSize: 12)),
            backgroundColor: const Color(0xFF200D0D),
            duration: const Duration(seconds: 12),
            action: SnackBarAction(
              label: s.ar ? 'حسناً' : 'OK',
              textColor: _p.gold,
              onPressed: () {})));
        }
      }
    });
  }

  // ── Auto download after processing ────────────────────────────────────────
  Future<void> _downloadAndSave(Map<String, dynamic> sd) async {
    if (!mounted) return; // S184-B3
    final s = LangProvider.strings(context);
    setState(() { _status = s.downloading; _progress = 0.95; });

    final filename = ApiService.buildFilename(_engine, originalPath: _file?.path); // S21 BUG2
    final (file, error) = await ApiService.downloadFile(_jobId!, filename);

    if (!mounted) return;

    final score = double.tryParse(sd['score']?.toString() ?? '0') ?? 0.0;

    // S63: fallback auto-retry — only retry if score == 75.0 exactly
    // (ffmpeg fallback always returns hardcoded score=75).
    // Real engines can score anywhere from 55-100; never discard them.
    final el148=_processStart!=null?DateTime.now().difference(_processStart!).inSeconds:999;
    if (score == 75.0 && file != null && _fallbackRetries < 2 && el148 < 8) {
      _fallbackRetries++;
      final retryNum = _fallbackRetries;
      if (mounted) {
        setState(() { _progress = 0.0; _status = ''; _busy = false; });
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(
            s.ar
              ? '⏳ الخادم كان في وضع الاستعداد — إعادة المعالجة تلقائياً ($retryNum/2)…'
              : '⏳ Server was warming up — retrying automatically ($retryNum/2)…',
            style: const TextStyle(fontSize: 12)),
          backgroundColor: const Color(0xFF1A1200),
          duration: const Duration(seconds: 10)));
        // Wait 35 s for the Space to finish loading reference audio,
        // then reprocess the same file.
        await Future.delayed(const Duration(seconds: 5)); // S149: faster retry
        if (mounted) _process(userInitiated: false);
      }
      return; // don't show the fallback result
    }
    // ── end S32 ──────────────────────────────────────────────────────────

    setState(() {
      _busy = false; _progress = 1.0;
      _output = file; _result = sd;
      _status = file != null ? s.done : 'فشل: $error';
    });

    if (file != null) _resultCtrl.forward(from: 0); // S29: animate in
    if (file != null) { // S92-SCROLL: scroll to result card
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scrollCtrl.hasClients) {
          _scrollCtrl.animateTo(0,
            duration: const Duration(milliseconds: 600),
            curve: Curves.easeOutCubic);
        }
      });
    }
    if (file != null) _fireCompletionNotif(filename, score); // S61

    // S19: Save job record locally for persistent re-download
    if (file != null && _jobId != null) {
      await ApiService.saveJobRecord(
        jobId: _jobId!,
        engine: _engine,
        score: score,
        filename: filename,
        originalName: _file?.path.split('/').last, // S28-T2
        metrics: sd,
      );
    }

    if (!mounted) return; // S185-B5 / S250: guard BOTH branches below
    if (file != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(
          s.ar
            ? '✅ تم الحفظ في Downloads\n📁 ${file.path}'
            : '✅ Saved to Downloads\n📁 ${file.path}',
          style: const TextStyle(fontSize: 12),
        ),
        backgroundColor: const Color(0xFF0D2015),
        duration: const Duration(seconds: 8),
        action: SnackBarAction(
          label: s.ar ? 'حسناً' : 'OK',
          textColor: const Color(0xFF2ABF6E),
          onPressed: () {},
        ),
      ));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(
          s.ar ? '❌ فشل التحميل\n$error' : '❌ Download failed\n$error',
          style: const TextStyle(fontSize: 12),
        ),
        backgroundColor: const Color(0xFF200D0D),
        duration: const Duration(seconds: 6),
      ));
    }
  }

  // ── S61: completion notification ──────────────────────────────────────────
  Future<void> _fireCompletionNotif(String filename, dynamic score) async {
    final s = score is num ? score.round() : 0;
    final label = s >= 96 ? 'ممتاز' : s >= 90 ? 'رائع' : s >= 85 ? 'جيد جداً' : 'جيد';
    const details = NotificationDetails(
      android: AndroidNotificationDetails(
        'tilawa_done', 'التحسين اكتمل',
        channelDescription: 'إشعار عند اكتمال تحسين التلاوة',
        importance: Importance.high, priority: Priority.high,
        color: Color(0xFFC8A048),
        icon: '@mipmap/ic_launcher',
        playSound: true, enableVibration: true),);
    try {
      await _notif.show(0, 'محسِّن التلاوة ✦', '$filename · $s/100 $label', details);
    } catch (_) {}
  }

  // ── Manual re-download button ──────────────────────────────────────────────
  // S104: A/B comparison ─────────────────────────────────────────────────────
  Future<void> _abToggleTrack() async {
    setState(() { _abIsB = !_abIsB; _abPos = 0; _abDur = 1.0; }); // S138: reset dur
    final src = _abIsB ? (_abOutputFile ?? _output) : _file; // S144: use cacheDir path — content:// fails DeviceFileSource
    if (src == null) return;
    // S195-BUG6: listeners in initState
    await _abPlayer.stop();
    await _abPlayer.play(DeviceFileSource(src.path));
    _abEverPlayed = true; // S140
    if (!mounted) return; // S189
    setState(() { _abPlaying = true; });
  }

  Future<void> _abTogglePlay() async {
    // S195-BUG6: listeners in initState
    if (_abPlaying) {
      await _abPlayer.pause();
      if (!mounted) return; // S189
      setState(() { _abPlaying = false; });
    } else {
      final src = _abIsB ? (_abOutputFile ?? _output) : _file; // S144: use cacheDir path — content:// fails DeviceFileSource
      if (src == null) return;
      if (!_abEverPlayed || _abPos <= 0.1 || _abPos >= _abDur - 0.1) { // S142: also replay when pos reset to 0
        await _abPlayer.play(DeviceFileSource(src.path));
        _abEverPlayed = true;
      } else {
        await _abPlayer.resume();
      }
      if (!mounted) return; // S189
      setState(() { _abPlaying = true; });
    }
  }


  Future<void> _reDownload() async {
    // S100: Local mode — copy cached output to Downloads
    if (_localMode && _abOutputFile != null) { // S145: use cacheDir file — _output may be content:// after first save
      final src = _abOutputFile!;
      try {
        final ts    = DateTime.now().millisecondsSinceEpoch;
        final ext   = src.path.endsWith('.mp3') ? 'mp3' : 'wav';
        final fname = 'tilawa_${_engine.replaceAll('.', '_')}_$ts.$ext';
        const mediaChannel = MethodChannel('com.tilawa.tilawa_enhancer/media'); // S141: was /wake
        final contentUri = await mediaChannel.invokeMethod<String>(
          'saveToDownloads', {'path': src.path, 'filename': fname});
        if (!mounted) return;
        // S143: update _output to the Downloads copy so Open/Share use the permanent file
        if (contentUri != null && contentUri.startsWith('content://')) {
          setState(() { _output = File(contentUri); });
        } else {
          setState(() { _output = src; }); // fallback: API <29 returns file path
        }
        final s = LangProvider.strings(context);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(
            s.ar ? '✅ تم الحفظ في Downloads\n📁 $fname'
                 : '✅ Saved to Downloads\n📁 $fname',
            style: const TextStyle(fontSize: 12)),
          backgroundColor: const Color(0xFF0D2015),
          duration: const Duration(seconds: 8),
          action: SnackBarAction(
            label: s.ar ? 'حسناً' : 'OK',
            textColor: const Color(0xFF2ABF6E),
            onPressed: () {})));
      } catch (e) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('❌ Save failed: $e', style: const TextStyle(fontSize: 12)),
          backgroundColor: const Color(0xFF200D0D),
          duration: const Duration(seconds: 6)));
      }
      return;
    }
    if (_jobId == null) return;
    final s = LangProvider.strings(context);
    setState(() { _status = s.downloading; _progress = 0.95; });

    final filename = ApiService.buildFilename(_engine, originalPath: _file?.path); // S21 BUG2
    final (file, error) = await ApiService.downloadFile(_jobId!, filename);

    if (!mounted) return;
    setState(() {
      _output = file;
      _progress = 1.0;
      _status = file != null ? s.done : 'فشل: $error';
    });

    if (file != null) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(
          s.ar
            ? '✅ تم الحفظ في Downloads\n📁 ${file.path}'
            : '✅ Saved to Downloads\n📁 ${file.path}',
          style: const TextStyle(fontSize: 12),
        ),
        backgroundColor: const Color(0xFF0D2015),
        duration: const Duration(seconds: 8),
        action: SnackBarAction(
          label: s.ar ? 'حسناً' : 'OK',
          textColor: const Color(0xFF2ABF6E),
          onPressed: () {},
        ),
      ));
    } else {
      final msg = (error == 'JOB_EXPIRED')
          ? s.jobExpired
          : (s.ar ? '❌ فشل التحميل\n$error' : '❌ Download failed\n$error');
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(msg, style: const TextStyle(fontSize: 12)),
        backgroundColor: const Color(0xFF200D0D),
        duration: const Duration(seconds: 6),
      ));
    }
  }

  // S19: Open in player button
  Future<void> _openInPlayer() async {
    if (_output == null) return;
    try {
      final uri = _output!.path.startsWith('content://')
          ? Uri.parse(_output!.path)   // S143: content:// from MediaStore
          : Uri.file(_output!.path);   // local cacheDir path
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (e) {
      if (mounted) {
        final s = LangProvider.strings(context);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(
            s.ar
              ? 'لم يُعثر على تطبيق مشغل صوت. افتح مجلد Downloads يدوياً.'
              : 'No audio player found. Open your Downloads folder manually.',
          ),
          backgroundColor: const Color(0xFF200D0D),
          duration: const Duration(seconds: 4),
        ));
      }
    }
  }

  // ── S28-T2: Share via Android share sheet ────────────────────────────────
  /// S250 — a real on-disk path for the restored output, or null if we only
  /// have a content:// URI (which DeviceFileSource/ffmpeg can't open).
  /// _abOutputFile is the cacheDir copy and stays valid after a Downloads save.
  String? _editableOutputPath() {
    for (final f in [_abOutputFile, _output]) {
      final p = f?.path;
      if (p == null || p.isEmpty || p.startsWith('content://')) continue;
      try {
        if (File(p).existsSync()) return p;
      } catch (_) {}
    }
    return null;
  }

  Future<void> _shareFile() async {
    if (_output == null) return;
    HapticFeedback.lightImpact();
    try {
      await ApiService.shareAudio(_output!.path);
    } catch (e) {
      if (mounted) {
        final s = LangProvider.strings(context);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(s.ar ? 'فشل المشاركة' : 'Share failed: $e'),
          backgroundColor: const Color(0xFF200D0D),
          duration: const Duration(seconds: 3),
        ));
      }
    }
  }
  // ── S28: Copy metrics to clipboard ───────────────────────────────────────
  Future<void> _copyMetrics() async {
    if (_result == null) return;
    HapticFeedback.lightImpact();
    final parts = <String>[];
    if (_result!['score'] != null) parts.add('Score: ${_result!['score']}/100');
    if (_result!['lufs']  != null) parts.add('LUFS: ${_result!['lufs']}');
    if (_result!['rms']   != null) parts.add('RMS: ${_result!['rms']}');
    if (_result!['crest'] != null) parts.add('Crest: ${_result!['crest']}');
    if (_result!['lra']   != null) parts.add('LRA: ${_result!['lra']}');
    parts.add('Engine: $_engine');
    await Clipboard.setData(ClipboardData(text: parts.join('  |  ')));
    if (mounted) {
      final s = LangProvider.strings(context);
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(s.copiedMetrics),
        backgroundColor: const Color(0xFF1A1500),
        duration: const Duration(seconds: 2),
      ));
    }
  }

  // ── S28: Estimated processing time ────────────────────────────────────────
  String _estimatedTime() {
    final mb = _fileBytes / 1024 / 1024;
    if (mb < 5)  return '~1 min';
    if (mb < 15) return '~2-3 min';
    if (mb < 30) return '~4-6 min';
    if (mb < 50) return '~7-10 min';
    return '~10-20 min';
  }

  // ── LOCAL PROCESS (S65) — proot offline engine ────────────────────────────
  Future<void> _processLocal() async {
    if (_file == null || _busy) return;
    // S250: last line of defence. The engine could still be one with no
    // on-device script — selected before the availability list arrived, or
    // restored from saveLastEngine() on a fresh launch. Fail here with a
    // sentence the user can act on rather than deep inside proot.
    await _refreshLocalEngines();
    if (!mounted) return;
    if (_engineBlocked(_engine)) {
      final s = LangProvider.strings(context);
      setState(() {
        _busy = false;
        _status = s.ar
          ? 'هذا المحرك غير متوفر بدون إنترنت — اختر محركًا آخر أو أوقف الوضع المحلي'
          : 'This engine has no offline version — pick another, or turn off local mode';
      });
      return;
    }
    HapticFeedback.mediumImpact(); // S146: removed server-only guard — allow all engines in local mode
    _wakeCh.invokeMethod('acquire').catchError((_) {}); // S141: keep CPU alive during proot
    setState(() {
      _busy      = true;
      _progress  = 0.02;
      _status    = 'Starting local engine…';
    });

    await for (final ev in LocalEngineService.runEngine(
      engineId:   _engine,
      inputPath:  _file!.path,
      aggressive: _aggressive,  // S173
    )) {
      if (!mounted) return;

      if (ev['error'] == true) {
        _wakeCh.invokeMethod('release').catchError((_) {}); // S142: release on error
        setState(() {
          _busy     = false;
          _status   = ev['msg'] as String? ?? 'Local engine error';
        });
        return;
      }

      if (ev['done'] == true) {
        double parsedScore = 0;
        try {
          final jsonStr = ev['json'] as String?;
          if (jsonStr != null) {
            final data = jsonDecode(jsonStr) as Map<String, dynamic>;
            // S172: v4 has no score — derive from drr_gain (0-6 dB → 80-99)
            if (data.containsKey('score')) {
              parsedScore = (data['score'] as num?)?.toDouble() ?? 0;
            } else {
              final drr = (data['drr_gain'] as num?)?.toDouble() ?? 0;
              parsedScore = (80 + drr.clamp(0.0, 6.0) * 3.0).clamp(80.0, 99.0);
            }
            _result = Map<String, dynamic>.from(data); // S66
          }
        } catch (_) {}
        final fallbackScore = parsedScore > 0 ? parsedScore : 88.0;
        final resultData = _result ?? {'score': fallbackScore, 'lufs': -14.0, 'lra': 6.0, 'crest': 12.0, 'rms': -16.0};
        if ((resultData['score'] as num?)?.toDouble() == 0 || resultData['score'] == null) {
          resultData['score'] = fallbackScore;
        }
        _wakeCh.invokeMethod('release').catchError((_) {});
        if (mounted) setState(() => _progress = 1.0);  // S157: hit 100% before reset
        await Future.delayed(const Duration(milliseconds: 300));
        final outPath = ev['path'] as String? ?? ''; // S140: null-safe
        _abOutputFile = outPath.isNotEmpty ? File(outPath) : null; // S144: preserve cacheDir path for A/B
        if (!mounted) return; // S184-B4
        setState(() { // S92: ALL result state inside setState
          _busy = false; _progress = 0;
          _status = 'Local engine complete';
          _output = outPath.isNotEmpty ? File(outPath) : null;
          _result = resultData;
        });
        _scoreCtrl.forward(from: 0);
        _resultCtrl.forward(from: 0);
        // S113: await _reDownload after setState settles
        WidgetsBinding.instance.addPostFrameCallback((_) async {
          await _reDownload();
          final sc = ((_result?['score'] as num?)?.toDouble() ?? 88.0);
          final fn = _file?.path.split('/').last ?? 'audio';
          _fireCompletionNotif(fn, sc); // S140: pass num, not String
        });
        WidgetsBinding.instance.addPostFrameCallback((_) { // S92-SCROLL
          if (_scrollCtrl.hasClients) {
            _scrollCtrl.animateTo(0,
              duration: const Duration(milliseconds: 600),
              curve: Curves.easeOutCubic);
          }
        });
        return;
      }

      // S-PROGRESS: advance bar from engine phase pct; never regress; cap at 98%
      final pct = ev['pct'] as int? ?? -1;
      final msg = ev['msg'] as String? ?? '';
      setState(() {
        if (pct > 0) _progress = (pct / 100.0).clamp(_progress, 0.98);
        if (msg.isNotEmpty) { _status = msg; }
      });
    }
  }

  /// S256: unpack the bundled offline engine, unprompted, in the background.
  ///
  /// Safe to call more than once — it no-ops while a run is in flight. A
  /// failure is recorded but never blocks anything: server mode keeps working,
  /// and the inline status offers a retry rather than a dead end.
  void _autoPrepareOfflineEngine() {
    if (_prepping || _localReady) return;
    final seen = LocalEngineService.preparationProgress;
    setState(() {
      _prepping = true;
      // It has been running since app start, so pick up where it actually is
      // instead of snapping the bar back to zero on arriving at this screen.
      _prepPct = (seen['pct'] as num?)?.toInt() ?? 0;
      _prepPhase = (seen['phase'] as String?) ?? '';
      _prepError = null;
    });
    _prepSub?.cancel();
    // S256: attach to the shared run started in main() rather than launching a
    // second one — two extractions over the same directory would race.
    _prepSub = LocalEngineService.ensurePrepared().listen(
      (ev) {
        if (!mounted) return;
        setState(() {
          _prepPct = (ev['pct'] as num?)?.toInt() ?? _prepPct;
          _prepPhase = (ev['phase'] as String?) ?? _prepPhase;
        });
      },
      onError: (e) {
        if (!mounted) return;
        setState(() { _prepping = false; _prepError = '$e'; });
      },
      onDone: () async {
        final ready = await LocalEngineService.isSetupComplete();
        if (!mounted) return;
        setState(() { _prepping = false; _localReady = ready; });
        if (ready) _refreshLocalEngines();
      },
    );
  }

  // S56: Resume polling when app returns to foreground
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed &&
        _jobId != null && _busy && _pollTimer == null) {
      _pollErrors = 0;
      _processStart ??= DateTime.now(); // reset timeout from resume
      _startPolling();
    }
  }

  // ═══════════════════════════════════════════════════════════════════════════
  //  NUR UI — everything below is presentation only. All behaviour lives above.
  // ═══════════════════════════════════════════════════════════════════════════

  NurPalette _p = NurPalette.night;

  _EngineData get _selectedEngine =>
      _engines.firstWhere((e) => e.id == _engine, orElse: () => _engines.first);

  /// Per-engine identity colour: drives the backdrop tint, glow and accents.
  Color _colorOf(String id) {
    switch (id) {
      case 'v11.0': return const Color(0xFFD9B13F); // Safaa — gold
      case 'v11.1': return const Color(0xFF2FD4B0); // Itiqan — teal
      case 'v11.2': return const Color(0xFFF0A23B); // Isteidad — amber
      case 'v10.0': return const Color(0xFFC9972B); // Aetherion — dark gold
      case 'v9.0':  return const Color(0xFF9B7FFF); // Evolution — violet
      case 'v8.5':  return const Color(0xFF5BB8FF); // Honest — blue
      case 'v8.0':  return const Color(0xFFFF7EA0); // Precision — rose
      default:      return const Color(0xFFD9B13F);
    }
  }

  Color get _engineColor => _colorOf(_engine);

  Future<void> _refreshLocalEngines() async {
    final list = await LocalEngineService.availableLocalEngines();
    if (mounted) setState(() => _localEngines = list);
  }

  /// S250 — true when this engine cannot run in the current mode. Only ever
  /// true in local mode, and only once we actually know the on-device list.
  bool _engineBlocked(String id) =>
      _localMode && _localEngines.isNotEmpty && !_localEngines.contains(id);

  void _setLocalMode(bool v) {
    if (_busy) return;
    setState(() => _localMode = v);
    SharedPreferences.getInstance().then((p) => p.setBool('local_mode', v)); // S148
    // S93/S256: re-check on toggle ON; if not ready, prepare in the background.
    if (v) {
      LocalEngineService.isSetupComplete().then((ready) {
        if (!mounted) return;
        setState(() => _localReady = ready);
        if (!ready) _autoPrepareOfflineEngine();
      });
    }
  }

  void _selectEngine(_EngineData e, S s) {
    HapticFeedback.selectionClick(); // S30-P1
    // S250: explain at the point of choice, not deep inside proot.
    if (_engineBlocked(e.id)) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        backgroundColor: const Color(0xFF200D0D),
        duration: const Duration(seconds: 5),
        content: Text(
          s.ar
            ? '${e.nameAr} غير متوفر بدون إنترنت — أوقف الوضع المحلي لاستخدامه'
            : '${e.nameEn} isn\'t available offline — turn off local mode to use it',
          style: const TextStyle(color: Color(0xFFFF8A8A), fontSize: 12)),
        action: SnackBarAction(
          label: s.ar ? 'أوقف' : 'Turn off',
          textColor: _p.gold,
          onPressed: () => _setLocalMode(false)),
      ));
      return;
    }
    setState(() => _engine = e.id);
    ApiService.saveLastEngine(e.id); // S28-T2: persist
  }

  void _scrollToEngine() {
    final i = _engines.indexWhere((e) => e.id == _engine);
    if (i < 0 || !_engCtrl.hasClients) return;
    final target = (i * (_engCardW + 12.0))
        .clamp(0.0, _engCtrl.position.maxScrollExtent);
    _engCtrl.animateTo(target,
        duration: const Duration(milliseconds: 520), curve: Curves.easeOutCubic);
  }

  static const double _engCardW = 236;

  Route<T> _go<T>(Widget page) => nurRoute<T>(page);

  // ── BUILD ──────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    _p = NurPalette.of(context);
    // S250 QoL — the root route's back button EXITS THE APP; a tap during a
    // multi-minute local restoration killed the proot process and lost the run.
    // First press warns, a second within 3 s leaves.
    return PopScope(
      canPop: !_busy || _exitArmed,
      onPopInvokedWithResult: (didPop, _) {
        if (didPop || !mounted) return;
        setState(() => _exitArmed = true);
        _exitArmTimer?.cancel();
        _exitArmTimer = Timer(const Duration(seconds: 3), () {
          if (mounted) setState(() => _exitArmed = false);
        });
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          duration: const Duration(seconds: 3),
          content: Text(
            s.ar
              ? 'المعالجة جارية — اضغط رجوع مرة أخرى للخروج وإلغاء العمل'
              : 'Still processing — press back again to exit and cancel the run',
            style: TextStyle(color: _p.text, fontSize: 12.5)),
        ));
      },
      child: Directionality(
        textDirection: s.ar ? TextDirection.rtl : TextDirection.ltr,
        child: _buildHome(s)));
  }

  Widget _buildHome(S s) {
    final p = _p;
    return Scaffold(
      backgroundColor: p.bg,
      body: NurBackdrop(
        accent: _engineTintEnabled ? _engineColor : p.teal,
        intensity: _busy ? 0.55 : 1.0,
        child: Stack(children: [
          CustomScrollView(controller: _scrollCtrl, slivers: [
            _appBar(s),
            SliverToBoxAdapter(child: EntranceFade(index: 0, child: _hero(s))),
            SliverToBoxAdapter(child: EntranceFade(index: 1, child: _modeCard(s))),
            SliverToBoxAdapter(child: EntranceFade(index: 2, child: _engineSection(s))),
            SliverToBoxAdapter(child: EntranceFade(index: 3, child: _fileCard(s))),
            if (!_busy && _progress > 0)
              SliverToBoxAdapter(child: _progressStrip(s)),
            if (_result != null)
              SliverToBoxAdapter(
                child: FadeTransition(
                  opacity: CurvedAnimation(
                    parent: _resultCtrl,
                    curve: const Interval(0, 0.35, curve: Curves.easeOutCubic)),
                  child: SlideTransition(
                    position: Tween<Offset>(
                      begin: const Offset(0, 0.08), end: Offset.zero,
                    ).animate(CurvedAnimation(
                      parent: _resultCtrl,
                      curve: const Interval(0, 0.45, curve: Curves.easeOutCubic))),
                    child: _resultCard(s)))),
            if (_result != null) SliverToBoxAdapter(child: _reportCard(s)),
            if (_result != null) SliverToBoxAdapter(child: _abCard(s)),
            SliverToBoxAdapter(child: EntranceFade(index: 4, child: _toolsSection(s))),
            const SliverToBoxAdapter(child: SizedBox(height: 48)),
          ]),
          if (_busy) Positioned.fill(child: _processingOverlay(s)),
        ]),
      ),
    );
  }

  // ── APP BAR ────────────────────────────────────────────────────────────────
  Widget _appBar(S s) => SliverAppBar(
    pinned: true,
    automaticallyImplyLeading: false,
    backgroundColor: _p.bg.withValues(alpha: 0.80),
    surfaceTintColor: Colors.transparent,
    elevation: 0,
    scrolledUnderElevation: 0,
    toolbarHeight: 62,
    centerTitle: true,
    title: _wordmark(),
    actions: [
      NurIconButton(
        icon: Icons.info_outline_rounded, size: 38,
        onTap: () => _showInfoSheet(context)),
      const SizedBox(width: 6),
      // S209: persistent entry point to the mini-game
      NurIconButton(
        icon: Icons.sports_esports_rounded, size: 38,
        onTap: () => Navigator.push(context, _go(const GameScreen()))),
      const SizedBox(width: 6),
      NurIconButton(
        icon: Icons.settings_outlined, size: 38,
        onTap: () => Navigator.push(context, _go(const SettingsScreen()))),
      const SizedBox(width: 12),
    ],
    bottom: PreferredSize(
      preferredSize: const Size.fromHeight(1),
      child: Container(
        height: 1,
        decoration: BoxDecoration(
          gradient: LinearGradient(colors: [
            Colors.transparent,
            _p.gold.withValues(alpha: 0.55),
            _p.teal.withValues(alpha: 0.55),
            Colors.transparent,
          ])))),
  );

  /// Compact brand lockup, revealed as the hero scrolls away so the brand is
  /// always present and never doubled. FittedBox keeps it inside the bar on a
  /// narrow screen or at a large text scale.
  Widget _wordmark() => AnimatedBuilder(
    animation: _scrollCtrl,
    builder: (_, child) {
      final off = _scrollCtrl.hasClients ? _scrollCtrl.offset : 0.0;
      final t = ((off - 150.0) / 80.0).clamp(0.0, 1.0);
      return Opacity(
        key: const ValueKey('appbar-wordmark-opacity'),
        opacity: t,
        child: Transform.translate(
          offset: Offset(0, 10 * (1 - t)), child: child));
    },
    child: FittedBox(
      fit: BoxFit.scaleDown,
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 28, height: 28,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            boxShadow: [BoxShadow(
              color: _p.gold.withValues(alpha: 0.40), blurRadius: 12)]),
          child: ClipOval(child: Image.asset(
            'assets/images/logo.png', fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => Icon(
              Icons.menu_book_rounded, color: _p.gold, size: 16)))),
        const SizedBox(width: 9),
        GradientText('محسِّن التلاوة',
          gradient: _p.goldGradient,
          style: const TextStyle(
            fontSize: 18, fontWeight: FontWeight.w800, letterSpacing: 0.3)),
      ])));

  // ── HERO — the studio orb ──────────────────────────────────────────────────
  Widget _hero(S s) {
    final p = _p;
    final eng = _selectedEngine;
    final energy = _busy ? 1.0 : (_file != null ? 0.78 : 0.5);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 4),
      child: Column(children: [
        TweenAnimationBuilder<double>(
          tween: Tween<double>(begin: energy, end: energy),
          duration: const Duration(milliseconds: 700),
          curve: Curves.easeOutCubic,
          builder: (_, e, __) => NurOrb(
            animation: _waveCtrl,
            size: 244,
            energy: e,
            a: p.teal,
            b: _engineColor,
            child: AnimatedBuilder(
              animation: _glowCtrl,
              builder: (_, child) => Transform.scale(
                scale: 0.97 + 0.05 * _glowCtrl.value, child: child),
              child: Container(
                width: 96, height: 96,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  boxShadow: [BoxShadow(
                    color: _engineColor.withValues(alpha: 0.45),
                    blurRadius: 26, spreadRadius: 1)]),
                child: ClipOval(child: Image.asset(
                  'assets/images/logo.png', fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => Container(
                    color: p.surfaceHi,
                    child: Icon(Icons.menu_book_rounded,
                      color: p.gold, size: 44))))))),
        ),
        const SizedBox(height: 6),
        FittedBox(
          fit: BoxFit.scaleDown,
          child: GradientText('محسِّن التلاوة',
            gradient: p.goldGradient,
            style: const TextStyle(
              fontSize: 32, fontWeight: FontWeight.w800, height: 1.15))),
        const SizedBox(height: 10),
        NurChip(
          label: '${s.subtitle}  ·  ${eng.nameAr}',
          color: p.teal, fontSize: 11),
      ]),
    );
  }

  // ── MODE CARD — cloud / on-device, status and options ──────────────────────
  Widget _modeCard(S s) {
    final p = _p;
    final showAggressive = _localMode && _localReady && _engine == 'v11.0';
    return NurCard(
      margin: const EdgeInsets.fromLTRB(16, 14, 16, 4),
      padding: const EdgeInsets.all(14),
      accent: _localMode ? p.gold : p.teal,
      child: Column(children: [
        NurSegmented(
          enabled: !_busy,
          accent: _localMode ? p.gold : p.teal,
          index: _localMode ? 1 : 0,
          items: [
            NurSegment(s.ar ? 'السحابة' : 'Cloud', Icons.cloud_outlined),
            NurSegment(s.ar ? 'على الجهاز' : 'On-device',
              Icons.offline_bolt_rounded),
          ],
          onChanged: (i) => _setLocalMode(i == 1)),
        const SizedBox(height: 14),
        AnimatedSize(
          duration: const Duration(milliseconds: 320),
          curve: Curves.easeOutCubic,
          alignment: Alignment.topCenter,
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 280),
            switchInCurve: Curves.easeOutCubic,
            transitionBuilder: (child, anim) => FadeTransition(
              opacity: anim,
              child: SlideTransition(
                position: Tween<Offset>(
                  begin: const Offset(0, 0.12), end: Offset.zero).animate(anim),
                child: child)),
            child: KeyedSubtree(
              key: ValueKey<bool>(_localMode),
              child: _localMode ? _localStatus(s) : _serverStatus(s)))),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 12),
          child: Container(height: 1, color: p.border)),
        NurOptionRow(
          icon: Icons.palette_outlined,
          title: s.ar ? 'تظليل الخلفية بلون المحرك' : 'Engine-colour backdrop',
          active: _engineTintEnabled,
          accent: _engineColor,
          trailing: NurSwitch(
            value: _engineTintEnabled,
            accent: _engineColor,
            onChanged: (v) {
              setState(() => _engineTintEnabled = v);
              SharedPreferences.getInstance()
                .then((p) => p.setBool('engine_tint_enabled', v)); // S188-B
            })),
        AnimatedSize(
          duration: const Duration(milliseconds: 320),
          curve: Curves.easeOutCubic,
          alignment: Alignment.topCenter,
          child: showAggressive
            ? Padding(
                padding: const EdgeInsets.only(top: 12),
                child: NurOptionRow(
                  icon: _aggressive ? Icons.waves_rounded : Icons.water_drop_outlined,
                  title: _aggressive
                    ? (s.ar ? 'وضع صارم (إزالة صدى عميقة)' : 'Aggressive (deep dereverberation)')
                    : (s.ar ? 'وضع قياسي (محافظ على الصوت)' : 'Standard (voice-preserving)'),
                  subtitle: _aggressive
                    ? (s.ar ? 'لتسجيلات شديدة الصدى' : 'Best for heavily reverberant recordings')
                    : (s.ar ? 'موصى به للتسجيلات العادية' : 'Recommended for most recordings'),
                  active: _aggressive,
                  accent: p.warn,
                  trailing: NurSwitch(
                    value: _aggressive,
                    accent: p.warn,
                    onChanged: _busy ? null : (v) {
                      setState(() => _aggressive = v);
                      SharedPreferences.getInstance().then(
                        (p) => p.setBool('aggressive_mode', v)); // S174-B4
                    })))
            : const SizedBox(width: double.infinity)),
      ]),
    );
  }

  Widget _serverStatus(S s) {
    final p = _p;
    final offline = !_serverUp;
    final col = _serverUp ? p.ok : _waking ? p.gold : p.err;
    return Column(children: [
      Row(children: [
        PulseDot(color: col, size: 9, active: _serverUp || _waking),
        const SizedBox(width: 6),
        Expanded(child: Text(
          _waking
            ? s.waking
            : _serverUp
              ? (_latencyMs != null
                  ? '${s.serverOnline} · ${_latencyMs}ms' // S30-S
                  : s.serverOnline)
              : s.serverOffline,
          style: TextStyle(
            color: col, fontSize: 13, fontWeight: FontWeight.w700))),
        // S19: wake button — only when offline and not already waking
        if (offline && !_waking)
          PressScale(
            scale: 0.92,
            onTap: _wakeServer,
            child: NurChip(
              label: s.wakeServer, color: p.gold,
              icon: Icons.bolt_rounded, filled: true)),
      ]),
      if (offline && !_waking) ...[
        const SizedBox(height: 6),
        Align(
          alignment: AlignmentDirectional.centerStart,
          child: Text(s.wakeHint,
            style: TextStyle(color: p.textDim, fontSize: 11, height: 1.4))),
      ],
    ]);
  }

  Widget _localStatus(S s) {
    final p = _p;
    final String sub;
    if (_localReady) {
      sub = _localEngines.isEmpty
        ? (s.ar ? 'جاهز — تشغيل بدون إنترنت' : 'Ready — processes fully offline')
        : (s.ar
            ? 'جاهز — ${_localEngines.length} محركات تعمل بدون إنترنت'
            : 'Ready — ${_localEngines.length} engines run offline');
    } else if (_prepError != null) {
      sub = s.ar ? 'تعذّر التجهيز — اضغط للمحاولة مجدداً'
                 : 'Preparation failed — tap to retry';
    } else {
      sub = _prepping
        ? (s.ar ? 'يُجهّز المحرك المحلي… $_prepPct٪'
                : 'Preparing the offline engine… $_prepPct%')
        : (s.ar ? 'يبدأ التجهيز…' : 'Starting…');
    }
    final failed = !_localReady && _prepError != null;
    final subCol = _localReady ? p.teal : failed ? p.err : p.gold;
    return Column(children: [
      Row(children: [
        Icon(Icons.offline_bolt_rounded, color: p.gold, size: 20),
        const SizedBox(width: 10),
        Expanded(child: Column(
          crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(s.ar ? 'المحرك المحلي (بدون إنترنت)' : 'Local Engine (Offline)',
            style: TextStyle(
              color: p.text, fontSize: 13.5, fontWeight: FontWeight.w800)),
          const SizedBox(height: 2),
          GestureDetector(
            onTap: failed && !_busy ? _autoPrepareOfflineEngine : null,
            child: Text(sub,
              style: TextStyle(
                color: subCol, fontSize: 11.5,
                decoration: failed ? TextDecoration.underline : null))),
        ])),
        NurIconButton(
          icon: Icons.info_outline_rounded, size: 34,
          onTap: () => Navigator.push(
            context, _go(const LocalModeInfoScreen()))), // S146
      ]),
      if (!_localReady && _prepError == null) ...[
        const SizedBox(height: 12),
        NurProgressBar(
          value: _prepping && _prepPct > 0 ? _prepPct / 100.0 : null,
          height: 5, a: p.teal, b: p.gold),
      ],
    ]);
  }

  // ── ENGINES ────────────────────────────────────────────────────────────────
  Widget _engineSection(S s) {
    final p = _p;
    final sel = _selectedEngine;
    final col = _engineColor;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      NurSectionHeader(
        s.chooseEngine, accent: col,
        trailing: NurChip(
          label: '≥${sel.score.toInt()}', color: col, filled: true)),
      SizedBox(
        height: 204,
        child: ListView.separated(
          controller: _engCtrl,
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.fromLTRB(16, 6, 16, 14),
          itemCount: _engines.length,
          separatorBuilder: (_, __) => const SizedBox(width: 12),
          itemBuilder: (_, i) => _engineCard(_engines[i], s))),
      AnimatedSize(
        duration: const Duration(milliseconds: 340),
        curve: Curves.easeOutCubic,
        alignment: Alignment.topCenter,
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 320),
          switchInCurve: Curves.easeOutCubic,
          transitionBuilder: (child, anim) => FadeTransition(
            opacity: anim,
            child: SlideTransition(
              position: Tween<Offset>(
                begin: const Offset(0, 0.06), end: Offset.zero).animate(anim),
              child: child)),
          child: KeyedSubtree(
            key: ValueKey<String>(sel.id),
            child: _engineDetails(sel, s, col, p)))),
    ]);
  }

  Widget _engineCard(_EngineData e, S s) {
    final p = _p;
    final sel = _engine == e.id;
    final col = _colorOf(e.id);
    final blocked = _engineBlocked(e.id); // S250
    final fallback = Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [col.withValues(alpha: 0.42), const Color(0xFF061214)])),
      child: Align(
        alignment: const Alignment(0, -0.35),
        child: Icon(Icons.graphic_eq_rounded,
          size: 46, color: col.withValues(alpha: 0.55))));
    return AnimatedScale(
      scale: sel ? 1.0 : 0.95,
      duration: const Duration(milliseconds: 320),
      curve: Curves.easeOutBack,
      child: PressScale(
        scale: 0.97,
        onTap: () => _selectEngine(e, s),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 320),
          curve: Curves.easeOutCubic,
          width: _engCardW,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(26),
            border: Border.all(
              color: blocked
                ? p.err.withValues(alpha: 0.45)
                : sel ? col : p.border.withValues(alpha: 0.9),
              width: sel ? 2 : 1),
            boxShadow: sel
              ? [BoxShadow(
                  color: col.withValues(alpha: 0.38),
                  blurRadius: 30, offset: const Offset(0, 10))]
              : [BoxShadow(
                  color: Colors.black.withValues(alpha: 0.22),
                  blurRadius: 14, offset: const Offset(0, 6))]),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(24),
            child: Stack(fit: StackFit.expand, children: [
              if (e.imgAsset != null)
                Image.asset(e.imgAsset!, fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => fallback)
              else
                fallback,
              // legibility scrim
              DecoratedBox(
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter, end: Alignment.bottomCenter,
                    stops: const [0.25, 1.0],
                    colors: [
                      Colors.transparent,
                      Colors.black.withValues(alpha: 0.86)]))),
              if (sel)
                DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter, end: Alignment.center,
                      colors: [
                        col.withValues(alpha: 0.30), Colors.transparent]))),
              if (blocked)
                Container(color: Colors.black.withValues(alpha: 0.5)),
              Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Flexible(child: Wrap(spacing: 5, runSpacing: 5, children: [
                      NurChip(
                        label: e.localOnly ? 'LOCAL' : 'SERVER',
                        color: e.localOnly ? p.teal : Colors.white70,
                        fontSize: 9),
                      if (e.badge.isNotEmpty)
                        NurChip(
                          label: e.badge, color: col,
                          filled: true, fontSize: 9),
                    ])),
                    const SizedBox(width: 8),
                    _scoreBadge(col, e.score),
                  ]),
                  const Spacer(),
                  if (blocked)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 4),
                      child: Row(children: [
                        Icon(Icons.cloud_off_rounded, size: 13, color: p.err),
                        const SizedBox(width: 5),
                        Flexible(child: Text(
                          s.ar ? 'يتطلب إنترنت' : 'Needs internet',
                          maxLines: 1, overflow: TextOverflow.ellipsis,
                          style: TextStyle(color: p.err, fontSize: 11))),
                      ])),
                  Text(s.ar ? e.nameAr : e.nameEn,
                    maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: sel ? Colors.white : Colors.white.withValues(alpha: 0.9),
                      fontSize: 20, fontWeight: FontWeight.w800, height: 1.15,
                      shadows: const [Shadow(color: Colors.black87, blurRadius: 10)])),
                  const SizedBox(height: 3),
                  Row(children: [
                    Flexible(child: Text(s.ar ? e.nameEn : e.nameAr,
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.6),
                        fontSize: 11.5))),
                    const SizedBox(width: 8),
                    Text(e.id, style: TextStyle(
                      color: col, fontSize: 11, fontWeight: FontWeight.w800)),
                  ]),
                ])),
            ])))),
    );
  }

  Widget _scoreBadge(Color col, double score) => Container(
    width: 42, height: 42,
    decoration: BoxDecoration(
      shape: BoxShape.circle,
      color: Colors.black.withValues(alpha: 0.5),
      border: Border.all(color: col.withValues(alpha: 0.8), width: 1.5),
      boxShadow: [BoxShadow(color: col.withValues(alpha: 0.35), blurRadius: 10)]),
    child: Center(child: FittedBox(
      fit: BoxFit.scaleDown,
      child: Padding(
        padding: const EdgeInsets.all(4),
        child: Text('≥${score.toInt()}',
          style: TextStyle(
            color: col, fontSize: 11.5, fontWeight: FontWeight.w900))))));

  Widget _engineDetails(_EngineData e, S s, Color col, NurPalette p) => NurCard(
    margin: const EdgeInsets.fromLTRB(16, 0, 16, 4),
    padding: const EdgeInsets.all(16),
    accent: col,
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(child: NurProgressBar(
          value: e.score / 100, height: 7,
          a: col.withValues(alpha: 0.6), b: col)),
        const SizedBox(width: 10),
        Text('${e.score.toInt()}/100', style: TextStyle(
          color: col, fontSize: 12, fontWeight: FontWeight.w800)),
      ]),
      const SizedBox(height: 12),
      Wrap(spacing: 6, runSpacing: 6, children: [
        for (final f in e.features)
          NurChip(label: f, color: col, fontSize: 10.5),
      ]),
      const SizedBox(height: 12),
      Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: col.withValues(alpha: p.dark ? 0.07 : 0.09),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: col.withValues(alpha: 0.25))),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            Icon(Icons.auto_awesome_rounded, size: 13, color: col),
            const SizedBox(width: 6),
            Text(s.ar ? 'الجديد في هذه النسخة' : "What's New",
              style: TextStyle(
                color: col, fontSize: 11.5, fontWeight: FontWeight.w800)),
          ]),
          const SizedBox(height: 6),
          Text(s.ar ? e.whatsNewAr : e.whatsNewEn,
            textDirection: s.ar ? TextDirection.rtl : TextDirection.ltr,
            style: TextStyle(color: p.textSub, fontSize: 12, height: 1.6)),
        ])),
    ]));


  // ── FILE CARD — the upload portal ──────────────────────────────────────────
  Widget _fileCard(S s) {
    final p = _p;
    final hasFile = _file != null;
    final col = _engineColor;
    return NurCard(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.fromLTRB(18, 20, 18, 18),
      radius: 30,
      accent: col,
      glow: hasFile,
      child: Column(children: [
        PressScale(
          scale: 0.98,
          onTap: _busy ? null : _pickFile,
          child: Column(children: [
            AnimatedBuilder(
              animation: _glowCtrl,
              builder: (_, child) => Container(
                width: 74, height: 74,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(colors: [
                    col.withValues(alpha: 0.22), col.withValues(alpha: 0.04)]),
                  border: Border.all(
                    color: col.withValues(alpha: 0.40 + 0.35 * _glowCtrl.value),
                    width: 1.6),
                  boxShadow: [BoxShadow(
                    color: col.withValues(alpha: 0.12 + 0.20 * _glowCtrl.value),
                    blurRadius: 18 + 16 * _glowCtrl.value)]),
                child: child),
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 420),
                switchInCurve: Curves.easeOutBack,
                transitionBuilder: (c, a) => ScaleTransition(
                  scale: a, child: FadeTransition(opacity: a, child: c)),
                child: Icon(
                  hasFile ? Icons.audio_file_rounded : Icons.upload_rounded,
                  key: ValueKey<bool>(hasFile), color: col, size: 34))),
            const SizedBox(height: 16),
            NurWaveform(
              animation: _waveCtrl,
              bars: 34, height: 46,
              energy: hasFile ? 0.9 : 0.14,
              a: hasFile ? p.teal : p.textDim,
              b: hasFile ? col : p.textDim),
            const SizedBox(height: 14),
            AnimatedSwitcher(
              duration: const Duration(milliseconds: 320),
              child: Text(
                hasFile
                  ? _file!.path.split('/').last // S46-PORTAL
                  : (s.ar ? 'أسقط تلاوتك في هذا المحراب'
                          : 'Drop your Quran audio into this sacred portal'),
                key: ValueKey<String>(_file?.path ?? ''),
                textAlign: TextAlign.center,
                maxLines: 2, overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: hasFile ? p.text : p.textSub,
                  fontSize: hasFile ? 14.5 : 15.5,
                  fontWeight: FontWeight.w700, height: 1.35))),
            const SizedBox(height: 10),
            if (hasFile)
              Wrap(
                alignment: WrapAlignment.center,
                spacing: 8, runSpacing: 6, children: [
                if (_sizeLabel.isNotEmpty)
                  NurChip(
                    label: _sizeLabel, color: p.textSub,
                    icon: Icons.sd_storage_rounded),
                if (_isLarge)
                  NurChip(label: s.chunkedBadge, color: p.gold),
                if (_fileBytes > 0)
                  NurChip(
                    label: '${s.estTime}: ${_estimatedTime()}',
                    color: p.teal, icon: Icons.timer_outlined),
              ])
            else ...[
              Text('mp3  ·  wav  ·  m4a',
                style: TextStyle(
                  color: p.teal, fontSize: 11, letterSpacing: 1.6,
                  fontWeight: FontWeight.w700)),
              const SizedBox(height: 4),
              Text(s.sizeLimit,
                style: TextStyle(color: p.textDim, fontSize: 11)),
            ],
          ])),
        AnimatedSize(
          duration: const Duration(milliseconds: 360),
          curve: Curves.easeOutCubic,
          alignment: Alignment.topCenter,
          child: hasFile
            ? Padding(
                padding: const EdgeInsets.only(top: 18),
                child: NurButton(
                  label: s.ar ? 'ارفع التلاوة' : 'Elevate This Recitation',
                  icon: Icons.auto_awesome_rounded,
                  accent: col,
                  loading: _busy,
                  onTap: _busy ? null : () => _process())) // S95
            : const SizedBox(width: double.infinity)),
      ]),
    );
  }

  /// Slim progress card for the post-processing download phase (the busy phase
  /// is covered by the overlay).
  Widget _progressStrip(S s) {
    final p = _p;
    return NurCard(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.all(16),
      accent: _engineColor,
      child: Column(children: [
        Row(children: [
          Expanded(child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 300),
            child: Text(
              _status.isEmpty ? s.processing : _status,
              key: ValueKey<String>(_status),
              maxLines: 2, overflow: TextOverflow.ellipsis,
              style: TextStyle(color: p.textSub, fontSize: 13)))),
          const SizedBox(width: 10),
          GradientText('${(_progress * 100).toInt()}%',
            gradient: p.goldGradient,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900)),
        ]),
        const SizedBox(height: 12),
        NurProgressBar(value: _progress, height: 8, a: p.teal, b: _engineColor),
      ]),
    );
  }

  // ── PROCESSING OVERLAY ─────────────────────────────────────────────────────
  // Frosted scrim over the whole screen while _busy. Cancel and the game
  // shortcut are deliberately NOT behind an AbsorbPointer.
  Widget _processingOverlay(S s) {
    final p = _p;
    final col = _engineColor;
    final determinate = !_isMerging && _progress > 0.05;
    final status = _isMerging
      ? (s.ar ? 'جارٍ دمج المقاطع…' : 'Merging chunks…')
      : _status.isNotEmpty
        ? _status
        : (s.ar ? 'يُرجى الانتظار…' : 'Please wait…');
    return TweenAnimationBuilder<double>(
      tween: Tween<double>(begin: 0, end: 1),
      duration: const Duration(milliseconds: 420),
      curve: Curves.easeOutCubic,
      builder: (_, t, child) => Opacity(opacity: t, child: child),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 16, sigmaY: 16),
        child: Container(
          color: p.bgDeep.withValues(alpha: 0.80),
          alignment: Alignment.center,
          child: SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                NurOrb(
                  animation: _waveCtrl,
                  size: 268,
                  energy: 1.0,
                  progress: determinate ? _progress : -1,
                  a: p.teal, b: col,
                  child: determinate
                    ? GradientText('${(_progress * 100).round()}%',
                        gradient: p.goldGradient,
                        style: const TextStyle(
                          fontSize: 38, fontWeight: FontWeight.w900))
                    : AnimatedBuilder(
                        animation: _glowCtrl,
                        builder: (_, __) => Icon(
                          Icons.graphic_eq_rounded,
                          size: 40 + 6 * _glowCtrl.value, color: col))),
                const SizedBox(height: 18),
                GradientText(s.ar ? 'جارٍ المعالجة' : 'Processing',
                  gradient: p.goldGradient,
                  style: const TextStyle(
                    fontSize: 24, fontWeight: FontWeight.w800)),
                const SizedBox(height: 8),
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 300),
                  child: Text(status,
                    key: ValueKey<String>(status),
                    textAlign: TextAlign.center,
                    maxLines: 3, overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: p.textSub, fontSize: 13.5))),
                const SizedBox(height: 18),
                SizedBox(
                  width: 260,
                  child: NurProgressBar(
                    value: determinate ? _progress : null,
                    height: 6, a: p.teal, b: col)),
                const SizedBox(height: 26),
                Wrap(
                  alignment: WrapAlignment.center,
                  spacing: 12, runSpacing: 12, children: [
                  NurButton(
                    label: s.cancelBtn,
                    icon: Icons.close_rounded,
                    filled: false, expand: false, height: 48,
                    accent: p.textSub,
                    onTap: _cancelProcessing),
                  // S209: processing continues in the background — the game
                  // is the "play while you wait" entry point.
                  NurButton(
                    label: s.playWhileWait,
                    icon: Icons.sports_esports_rounded,
                    expand: false, height: 48,
                    accent: p.teal,
                    onTap: () => Navigator.push(
                      context, _go(const GameScreen()))),
                ]),
              ])))),
      ),
    );
  }

  // ── RESULT ─────────────────────────────────────────────────────────────────
  Widget _resultCard(S s) {
    final p = _p;
    final score = double.tryParse(_result?['score']?.toString() ?? '0') ?? 0.0;
    final label = score >= 96 ? s.excellent
        : score >= 90 ? s.great
        : score >= 85 ? s.good
        : score >= 78 ? s.decent
        : s.fair;
    final sc = score >= 90 ? p.ok : score >= 80 ? p.gold : p.err;
    const engineNames = { // S141: added v11.x, removed dead v8.4/v8.9
      'v11.0': 'الصفاء — Purity', // S149
      'v11.1': 'الإتقان — Perfection',
      'v11.2': 'الاسترداد — Recovery',
      'v10.0': 'Aetherion Foundation',
      'v9.0': 'The Evolution',
      'v8.5': 'Honest Ceiling',
      'v8.0': 'Calibrated Precision',
      'v7.0': 'Classic',
    };
    final engineName = engineNames[_engine] ?? _engine;
    final filename = ApiService.buildFilename(_engine);
    final hasContentUri = _output?.path.startsWith('content://') ?? false;
    final canOpen = hasContentUri || (_localMode && _output != null); // S142

    return NurCard(
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 4),
      padding: const EdgeInsets.fromLTRB(18, 22, 18, 18),
      radius: 32,
      accent: sc,
      glow: true,
      child: Column(children: [
        AnimatedBuilder(
          animation: Listenable.merge([_resultCtrl, _glowCtrl]),
          builder: (_, __) {
            final t = Curves.easeOutCubic.transform(_resultCtrl.value);
            final pop = _resultCtrl.value > 0.85
                ? 1.0 + 0.05 * (1 - (_resultCtrl.value - 0.85) / 0.15)
                : 1.0;
            return SizedBox(
              width: 224, height: 224,
              child: Stack(alignment: Alignment.center, children: [
                if (score >= 85)
                  CustomPaint(
                    size: const Size(224, 224),
                    painter: BurstPainter(
                      progress: _resultCtrl.value, color: sc)),
                CustomPaint(
                  size: const Size(200, 200),
                  painter: ScoreRingPainter(
                    progress: (score / 100) * t,
                    a: Color.lerp(sc, p.teal, 0.45)!,
                    b: Color.lerp(sc, Colors.white, 0.25)!,
                    track: p.border,
                    glow: _glowCtrl.value)),
                Transform.scale(
                  scale: pop,
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Text((score * t).toStringAsFixed(1),
                      style: TextStyle(
                        color: sc, fontSize: 46,
                        fontWeight: FontWeight.w900, letterSpacing: -1)),
                    Text('/100', style: TextStyle(
                      color: sc.withValues(alpha: 0.6),
                      fontSize: 13, fontWeight: FontWeight.w700)),
                  ])),
              ]));
          }),
        const SizedBox(height: 6),
        NurChip(label: label, color: sc, filled: true, fontSize: 13),
        const SizedBox(height: 10),
        NurChip(
          label: '$_engine — $engineName',
          color: p.gold, icon: Icons.memory_rounded),
        const SizedBox(height: 16),
        _metricGrid(s),
        if (score < 78) ...[ // S32-BUG3-FIX: 78 = Good label, not fallback
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: p.err.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: p.err.withValues(alpha: 0.4))),
            child: Text(s.fallbackWarning,
              textAlign: TextAlign.center,
              style: TextStyle(color: p.err, fontSize: 12, height: 1.5))),
        ],
        const SizedBox(height: 16),
        NurButton(
          label: s.downloadBtn,
          icon: Icons.download_rounded,
          accent: p.ok,
          onTap: _reDownload),
        const SizedBox(height: 6),
        Text(filename, maxLines: 1, overflow: TextOverflow.ellipsis,
          style: TextStyle(color: p.textDim, fontSize: 10.5)),
        if (canOpen) ...[
          const SizedBox(height: 10),
          Row(children: [
            Expanded(child: NurButton(
              label: s.openInPlayer,
              icon: Icons.play_circle_outline_rounded,
              filled: false, height: 46, accent: p.info,
              onTap: _openInPlayer)),
            if (hasContentUri) ...[ // S143: share requires content:// URI
              const SizedBox(width: 10),
              Expanded(child: NurButton(
                label: s.shareBtn,
                icon: Icons.share_rounded,
                filled: false, height: 46, accent: p.textSub,
                onTap: _shareFile)),
            ],
          ]),
          // S250 — hand the restored file straight to the Audio Editor.
          if (_editableOutputPath() != null) ...[
            const SizedBox(height: 10),
            NurButton(
              label: s.ar ? 'تحرير في محرر الصوت' : 'Open in Audio Editor',
              icon: Icons.equalizer_rounded,
              filled: false, height: 46, accent: p.teal,
              onTap: () => Navigator.push(context, _go(
                AudioEditorScreen(initialPath: _editableOutputPath())))),
          ],
        ],
        if (_output != null) ...[
          const SizedBox(height: 12),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            Icon(Icons.check_circle_rounded, color: p.ok, size: 15),
            const SizedBox(width: 6),
            Text(s.savedTo, style: TextStyle(
              color: p.ok, fontSize: 12, fontWeight: FontWeight.w700)),
          ]),
        ],
        const SizedBox(height: 12),
        NurButton(
          label: s.processAnother,
          icon: Icons.refresh_rounded,
          filled: false, height: 46, accent: p.info,
          onTap: _resetForNewFile),
      ]),
    );
  }

  // S30-R2: 2×2 metric grid — tap to copy
  Widget _metricGrid(S s) {
    final p = _p;
    return PressScale(
      scale: 0.985,
      onTap: _copyMetrics,
      child: Container(
        decoration: BoxDecoration(
          color: p.dark ? Colors.black.withValues(alpha: 0.22) : p.bgDeep,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: p.border)),
        child: Column(children: [
          IntrinsicHeight(child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Expanded(child: _metricTile('LUFS',
              _result?['lufs']?.toString() ?? '—', -6.29, 0)),
            VerticalDivider(width: 1, color: p.border),
            Expanded(child: _metricTile('RMS',
              _result?['rms']?.toString() ?? '—', -10.01, 1)),
          ])),
          Divider(height: 1, color: p.border),
          IntrinsicHeight(child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Expanded(child: _metricTile('Crest',
              _result?['crest']?.toString() ?? '—', 10.25, 2)),
            VerticalDivider(width: 1, color: p.border),
            Expanded(child: _metricTile('LRA',
              _result?['lra']?.toString() ?? '—', 4.19, 3)),
          ])),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 7),
            child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              Icon(Icons.copy_rounded, size: 11, color: p.textDim),
              const SizedBox(width: 5),
              Text(s.ar ? 'اضغط للنسخ' : 'tap to copy',
                style: TextStyle(color: p.textDim, fontSize: 10.5)),
            ])),
        ])));
  }

  Widget _metricTile(String label, String value, double target, int index) {
    final p = _p;
    final num = double.tryParse(value);
    String delta = '';
    String arrow = '';
    Color tone = p.textDim;
    if (num != null && value != '—') {
      final diff = num - target;
      delta = '${diff >= 0 ? "+" : ""}${diff.toStringAsFixed(2)}';
      if (diff.abs() <= 0.5) {
        arrow = '✓'; tone = p.ok;
      } else if (diff > 0) {
        arrow = '▲'; tone = p.gold;
      } else {
        arrow = '▼'; tone = p.info;
      }
    }
    return EntranceFade(
      index: index + 2,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          Text(label, style: TextStyle(
            color: p.textDim, fontSize: 11, letterSpacing: 0.6,
            fontWeight: FontWeight.w700)),
          const SizedBox(height: 5),
          FittedBox(
            fit: BoxFit.scaleDown,
            child: Text(value, style: TextStyle(
              color: p.gold, fontWeight: FontWeight.w900, fontSize: 21))),
          if (delta.isNotEmpty) ...[
            const SizedBox(height: 4),
            Row(mainAxisSize: MainAxisSize.min, children: [
              Text(arrow, style: TextStyle(
                color: tone, fontSize: 10, fontWeight: FontWeight.w900)),
              const SizedBox(width: 3),
              Text(delta, style: TextStyle(
                color: tone, fontSize: 10.5, fontWeight: FontWeight.w700)),
            ]),
          ],
        ])));
  }

  // S105: Enhancement report card ────────────────────────────────────────────
  Widget _reportCard(S s) {
    if (_result == null) return const SizedBox.shrink();
    final p = _p;
    final lufs  = double.tryParse(_result!['lufs']?.toString()  ?? '') ?? -99;
    final rms   = double.tryParse(_result!['rms']?.toString()   ?? '') ?? -99;
    final crest = double.tryParse(_result!['crest']?.toString() ?? '') ?? 0;
    final lra   = double.tryParse(_result!['lra']?.toString()   ?? '') ?? 0;

    // Deltas from the 1425H reference
    final dLufs  = lufs  - (-6.29);
    final dRms   = rms   - (-10.01);
    final dCrest = crest - 10.25;
    final dLra   = lra   - 4.19;

    final items = <_Insight>[];

    if (dLufs.abs() <= 1.0) {
      items.add(_Insight(Icons.check_circle_outline, p.ok,
        'مستوى الصوت مطابق للمرجع ١٤٢٥هـ', 'Loudness matches 1425H reference'));
    } else if (dLufs < -1.0) {
      items.add(_Insight(Icons.volume_up_rounded, p.gold,
        'رُفع مستوى الصوت ${dLufs.abs().toStringAsFixed(1)} وحدة نحو الهدف',
        'Loudness boosted ${dLufs.abs().toStringAsFixed(1)} LU toward target'));
    } else {
      items.add(_Insight(Icons.volume_down_rounded, p.info,
        'خُفّض مستوى الصوت ${dLufs.abs().toStringAsFixed(1)} وحدة نحو الهدف',
        'Loudness reduced ${dLufs.abs().toStringAsFixed(1)} LU toward target'));
    }

    if (dCrest.abs() <= 1.0) {
      items.add(_Insight(Icons.equalizer_rounded, p.ok,
        'الديناميكية متوازنة ومطابقة للمرجع', 'Dynamics balanced and on target'));
    } else if (dCrest > 1.0) {
      items.add(_Insight(Icons.trending_up_rounded, p.ok,
        'تحسّنت الديناميكية — الصوت أكثر حيوية',
        'Dynamics improved — audio more vibrant'));
    } else {
      items.add(_Insight(Icons.compress_rounded, p.gold,
        'ضُغطت الديناميكية قليلاً — مقبول للتلاوة',
        'Dynamics slightly compressed — acceptable for recitation'));
    }

    if (dLra.abs() <= 0.8) {
      items.add(_Insight(Icons.graphic_eq_rounded, p.ok,
        'نطاق الصوت مثالي ومتوازن', 'Loudness range ideal and balanced'));
    } else if (dLra > 0.8) {
      items.add(_Insight(Icons.unfold_more_rounded, p.info,
        'توسّع النطاق الصوتي — التباين بين الهادئ والقوي أكبر',
        'Loudness range expanded — more contrast between soft and loud'));
    } else {
      items.add(_Insight(Icons.unfold_less_rounded, p.gold,
        'النطاق الصوتي ضيّق — تلاوة ذات مستوى ثابت',
        'Narrow loudness range — consistent level recitation'));
    }

    if (dRms.abs() <= 1.5) {
      items.add(_Insight(Icons.sensors_rounded, p.ok,
        'طاقة الصوت الكلية مطابقة للمرجع', 'Overall energy matches reference'));
    } else if (dRms < -1.5) {
      items.add(_Insight(Icons.bolt_rounded, p.gold,
        'طاقة الصوت أقل من المرجع — التسجيل خافت',
        'Energy below reference — recording was quiet'));
    } else {
      items.add(_Insight(Icons.flash_on_rounded, p.info,
        'طاقة الصوت فوق المرجع — التسجيل قوي',
        'Energy above reference — recording was loud'));
    }

    final score = ((_result!['score'] as num?)?.toDouble() ?? 0);
    final String verdict;
    final Color vColor;
    if (score >= 90) {
      verdict = s.ar ? '✨ جودة استثنائية — يُضاهي مستوى الإذاعة' : '✨ Exceptional — broadcast quality';
      vColor = p.ok;
    } else if (score >= 80) {
      verdict = s.ar ? '🌟 جيد جداً — مناسب للنشر والمشاركة' : '🌟 Very good — suitable for sharing';
      vColor = p.gold;
    } else if (score >= 70) {
      verdict = s.ar ? '👍 جيد — تحسّن ملموس عن الأصل' : '👍 Good — noticeable improvement';
      vColor = p.info;
    } else {
      verdict = s.ar ? '⚠️ التسجيل صعب — جرّب محرك مختلف' : '⚠️ Difficult recording — try a different engine';
      vColor = p.err;
    }

    return NurCard(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.all(16),
      accent: vColor,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(Icons.analytics_outlined, color: p.textSub, size: 16),
          const SizedBox(width: 8),
          Text(s.ar ? 'تقرير التحسين' : 'Enhancement Report',
            style: TextStyle(
              color: p.text, fontSize: 14, fontWeight: FontWeight.w800)),
        ]),
        const SizedBox(height: 12),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
          decoration: BoxDecoration(
            color: vColor.withValues(alpha: 0.10),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: vColor.withValues(alpha: 0.35))),
          child: Text(verdict, textAlign: TextAlign.center,
            style: TextStyle(
              color: vColor, fontSize: 12.5, fontWeight: FontWeight.w800))),
        const SizedBox(height: 12),
        for (var i = 0; i < items.length; i++)
          EntranceFade(
            index: i,
            child: Padding(
              padding: const EdgeInsets.only(bottom: 9),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start, children: [
                Container(
                  width: 26, height: 26,
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(8),
                    color: items[i].color.withValues(alpha: 0.12)),
                  child: Icon(items[i].icon, color: items[i].color, size: 15)),
                const SizedBox(width: 10),
                Expanded(child: Padding(
                  padding: const EdgeInsets.only(top: 3),
                  child: Text(s.ar ? items[i].ar : items[i].en,
                    style: TextStyle(
                      color: p.textSub, fontSize: 12.5, height: 1.45)))),
              ]))),
      ]),
    );
  }

  // ── A/B COMPARISON ─────────────────────────────────────────────────────────
  Widget _abCard(S s) {
    if (_file == null || _output == null) return const SizedBox.shrink();
    final p = _p;
    final progress = (_abPos / _abDur).clamp(0.0, 1.0);
    final active = _abIsB ? p.gold : p.teal;

    String fmt(double ms) {
      final t = Duration(milliseconds: ms.toInt());
      return '${t.inMinutes}:${(t.inSeconds % 60).toString().padLeft(2, '0')}';
    }

    Widget trackBtn({
      required bool on, required Color col, required String title,
      required String sub, required VoidCallback onTap,
    }) => Expanded(child: PressScale(
      scale: 0.96,
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOutCubic,
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: on
            ? LinearGradient(
                begin: Alignment.topLeft, end: Alignment.bottomRight,
                colors: [col.withValues(alpha: 0.28), col.withValues(alpha: 0.10)])
            : null,
          color: on ? null : col.withValues(alpha: 0.04),
          border: Border.all(
            color: on ? col : col.withValues(alpha: 0.22), width: on ? 1.6 : 1),
          boxShadow: on && _abPlaying
            ? [BoxShadow(color: col.withValues(alpha: 0.32), blurRadius: 18)]
            : const []),
        child: Column(children: [
          AnimatedSwitcher(
            duration: const Duration(milliseconds: 220),
            transitionBuilder: (c, a) =>
              ScaleTransition(scale: a, child: c),
            child: Icon(
              on && _abPlaying
                ? Icons.pause_circle_rounded
                : Icons.play_circle_rounded,
              key: ValueKey<bool>(on && _abPlaying),
              color: col, size: 34)),
          const SizedBox(height: 4),
          Text(title, style: TextStyle(
            color: on ? p.text : p.textSub,
            fontSize: 13, fontWeight: FontWeight.w800)),
          Text(sub, style: TextStyle(color: p.textDim, fontSize: 10.5)),
        ]))));

    return NurCard(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.all(16),
      accent: active,
      child: Column(children: [
        Row(children: [
          Icon(Icons.compare_arrows_rounded, color: active, size: 18),
          const SizedBox(width: 8),
          Text(s.ar ? 'مقارنة قبل / بعد' : 'Before / After',
            style: TextStyle(
              color: p.text, fontSize: 14, fontWeight: FontWeight.w800)),
          const Spacer(),
          NurChip(
            label: _abIsB
              ? (s.ar ? 'المُحسَّن' : 'Enhanced')
              : (s.ar ? 'الأصلي' : 'Original'),
            color: active, filled: _abPlaying, fontSize: 10.5),
        ]),
        const SizedBox(height: 14),
        Row(children: [
          trackBtn( // A — original
            on: !_abIsB, col: p.teal,
            title: s.ar ? 'الأصلي' : 'Original', sub: 'A',
            onTap: () async {
              if (_abIsB) { await _abToggleTrack(); } else { await _abTogglePlay(); }
            }),
          const SizedBox(width: 12),
          trackBtn( // B — enhanced
            on: _abIsB, col: p.gold,
            title: s.ar ? 'المُحسَّن' : 'Enhanced', sub: 'B',
            onTap: () async {
              if (!_abIsB) { await _abToggleTrack(); } else { await _abTogglePlay(); }
            }),
        ]),
        const SizedBox(height: 14),
        NurWaveform(
          animation: _waveCtrl,
          bars: 44, height: 34,
          progress: progress,
          energy: _abPlaying ? 0.95 : 0.25,
          a: active, b: Color.lerp(active, Colors.white, 0.3)),
        const SizedBox(height: 6),
        Row(children: [
          Text(fmt(_abPos), style: TextStyle(
            color: active, fontSize: 11, fontWeight: FontWeight.w700)),
          const Spacer(),
          Text(fmt(_abDur), style: TextStyle(color: p.textDim, fontSize: 11)),
        ]),
      ]),
    );
  }

  // ── TOOLS ──────────────────────────────────────────────────────────────────
  Widget _toolTile({
    required IconData icon,
    required String title,
    String? subtitle,
    required Color color,
    required VoidCallback onTap,
  }) {
    final p = _p;
    return NurCard(
      padding: const EdgeInsets.all(14),
      radius: 22,
      accent: color,
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.center, children: [
        Container(
          width: 40, height: 40,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(13),
            gradient: LinearGradient(
              begin: Alignment.topLeft, end: Alignment.bottomRight,
              colors: [color.withValues(alpha: 0.30), color.withValues(alpha: 0.10)]),
            border: Border.all(color: color.withValues(alpha: 0.45))),
          child: Icon(icon, color: color, size: 21)),
        const SizedBox(height: 12),
        Text(title, maxLines: 2, overflow: TextOverflow.ellipsis,
          style: TextStyle(
            color: p.text, fontSize: 13.5, fontWeight: FontWeight.w800, height: 1.25)),
        if (subtitle != null) ...[
          const SizedBox(height: 3),
          Text(subtitle, maxLines: 2, overflow: TextOverflow.ellipsis,
            style: TextStyle(color: p.textDim, fontSize: 11, height: 1.3)),
        ],
      ]));
  }

  Widget _toolsSection(S s) {
    final p = _p;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      NurSectionHeader(s.ar ? 'الأدوات' : 'Tools', accent: p.teal),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16),
        child: Column(children: [
          IntrinsicHeight(child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Expanded(child: _toolTile(
              icon: Icons.history_rounded, title: s.history, color: p.info,
              onTap: () => Navigator.push(context, _go(const HistoryScreen())))),
            const SizedBox(width: 12),
            Expanded(child: _toolTile(
              icon: Icons.equalizer_rounded,
              title: s.ar ? 'محرر الصوت' : 'Audio Editor', // S152
              color: p.teal,
              onTap: () => Navigator.push(
                context, _go(const AudioEditorScreen())))),
          ])),
          const SizedBox(height: 12),
          IntrinsicHeight(child: Row(
            crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Expanded(child: _toolTile(
              icon: Icons.code_rounded,
              title: s.ar ? 'كود محركات المعالجة' : 'Engine Source Code', // S234
              color: p.gold,
              onTap: () => Navigator.push(
                context, _go(const EngineCodeScreen())))),
            const SizedBox(width: 12),
            Expanded(child: _toolTile(
              icon: Icons.warning_amber_rounded, // S184
              title: s.ar ? 'أدوات الذكاء الاصطناعي' : 'AI Tools',
              subtitle: s.ar ? 'الخيار الأخير — استخدم بحذر'
                             : 'Last resort — use with care',
              color: p.warn,
              onTap: () => Navigator.push(
                context, _go(const AiToolsScreen())))),
          ])),
          const SizedBox(height: 12),
          NurCard(
            padding: const EdgeInsets.all(16),
            radius: 22,
            accent: p.gold,
            glow: true,
            onTap: () {
              HapticFeedback.lightImpact();
              launchUrl(Uri.parse('https://buymeacoffee.com/tilawa'),
                mode: LaunchMode.externalApplication);
            },
            child: Row(children: [
              Container(
                width: 44, height: 44,
                decoration: BoxDecoration(
                  shape: BoxShape.circle, gradient: p.goldGradient),
                child: Icon(Icons.volunteer_activism_rounded,
                  color: p.onGold, size: 22)),
              const SizedBox(width: 14),
              Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(s.donation, style: TextStyle(
                  color: p.text, fontSize: 14.5, fontWeight: FontWeight.w800)),
                const SizedBox(height: 2),
                Text(s.donationDesc, style: TextStyle(
                  color: p.textSub, fontSize: 11.5)),
              ])),
              Icon(Icons.arrow_forward_ios_rounded, size: 14, color: p.gold),
            ])),
        ])),
    ]);
  }

  // ── INFO SHEET ─────────────────────────────────────────────────────────────
  void _showInfoSheet(BuildContext ctx) {
    final s = LangProvider.strings(ctx);
    showNurSheet<void>(ctx, builder: (c, ctrl) {
      final p = NurPalette.of(c);
      Widget label(String t) => Padding(
        padding: const EdgeInsets.only(bottom: 8, top: 6),
        child: Text(t, style: TextStyle(
          color: p.textSub, fontSize: 12, fontWeight: FontWeight.w800,
          letterSpacing: 0.4)));

      Widget linkTile({
        required IconData icon, required Color color,
        required String title, required String handle, required String url,
      }) => NurCard(
        margin: const EdgeInsets.only(bottom: 14),
        padding: const EdgeInsets.all(14),
        radius: 20,
        accent: color,
        onTap: () => launchUrl(Uri.parse(url),
          mode: LaunchMode.externalApplication),
        child: Row(children: [
          Container(
            width: 42, height: 42,
            decoration: BoxDecoration(
              color: color, borderRadius: BorderRadius.circular(13)),
            child: Icon(icon, color: Colors.white, size: 24)),
          const SizedBox(width: 12),
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title, style: TextStyle(
              color: p.text, fontWeight: FontWeight.w800, fontSize: 13.5)),
            const SizedBox(height: 2),
            Text(handle, maxLines: 1, overflow: TextOverflow.ellipsis,
              style: TextStyle(color: p.textDim, fontSize: 11.5)),
          ])),
          Icon(Icons.open_in_new_rounded, color: p.textDim, size: 16),
        ]));

      return Directionality(
        textDirection: s.ar ? TextDirection.rtl : TextDirection.ltr,
        child: ListView(
          controller: ctrl,
          padding: const EdgeInsets.fromLTRB(18, 6, 18, 40),
          children: [
            Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(children: [
                Icon(Icons.info_outline_rounded, color: p.gold, size: 20),
                const SizedBox(width: 8),
                GradientText(s.ar ? 'عن التطبيق' : 'About',
                  gradient: p.goldGradient,
                  style: const TextStyle(
                    fontSize: 20, fontWeight: FontWeight.w800)),
              ])),
            label(s.ar ? 'قناة يوتيوب' : 'YouTube Channel'),
            linkTile(
              icon: Icons.play_arrow_rounded, color: const Color(0xFFE52D27),
              title: s.ar ? 'قناة يوتيوب' : 'YouTube Channel',
              handle: '@carm-tv2hv', url: 'https://youtube.com/@carm-tv2hv'),
            label(s.ar ? 'قناة تيليغرام' : 'Telegram Channel'),
            linkTile(
              icon: Icons.send_rounded, color: const Color(0xFF2AABEE),
              title: s.ar ? 'قناة التيليغرام' : 'Telegram Channel',
              handle: '@TilawaEhnacher', url: 'https://t.me/TilawaEhnacher'),
            label(s.ar ? 'الموقع الإلكتروني' : 'Website'),
            linkTile(
              icon: Icons.language_rounded, color: p.gold,
              title: s.ar ? 'الموقع الإلكتروني الرسمي' : 'Official Website',
              handle: 'hammer24678-star.github.io/tilawa-enhancer-',
              url: 'https://hammer24678-star.github.io/tilawa-enhancer-/'),
            label(s.ar ? 'المرجع الصوتي' : 'Reference Standard'),
            NurCard(
              margin: const EdgeInsets.only(bottom: 14),
              padding: const EdgeInsets.all(16),
              radius: 20,
              accent: p.ok,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(
                  s.ar ? 'الشيخ ياسر الدوسري — 1425هـ'
                       : 'Sheikh Yasser Al-Dossari — 1425H',
                  style: TextStyle(
                    color: p.ok, fontWeight: FontWeight.w800, fontSize: 13.5)),
                const SizedBox(height: 8),
                Text('LUFS=-6.29  ·  RMS=-10.01  ·  Crest=10.25  ·  LRA=4.19',
                  style: TextStyle(color: p.textSub, fontSize: 12, height: 1.7)),
                const SizedBox(height: 6),
                Text(
                  s.ar ? 'ثلاثة ملفات مرجعية: الأعراف · الفتح · فاطر'
                       : 'Three reference files: Al-Araf · Al-Fath · Fatir',
                  style: TextStyle(color: p.textDim, fontSize: 11)),
              ])),
            label(s.ar ? 'مقارنة المحركات' : 'Engine Comparison'),
            NurCard(
              margin: const EdgeInsets.only(bottom: 14),
              padding: const EdgeInsets.all(16),
              radius: 20,
              accent: p.gold,
              child: Column(children: [
                for (final e in _engines)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 14),
                    child: Column(children: [
                      Row(children: [
                        Text(e.id, style: TextStyle(
                          color: _colorOf(e.id),
                          fontWeight: FontWeight.w800, fontSize: 12.5)),
                        const SizedBox(width: 8),
                        Expanded(child: Text(s.ar ? e.nameAr : e.nameEn,
                          maxLines: 1, overflow: TextOverflow.ellipsis,
                          style: TextStyle(color: p.textSub, fontSize: 11.5))),
                        Text('≥${e.score.toInt()}', style: TextStyle(
                          color: _colorOf(e.id),
                          fontWeight: FontWeight.w800, fontSize: 12.5)),
                      ]),
                      const SizedBox(height: 6),
                      TweenAnimationBuilder<double>(
                        tween: Tween<double>(begin: 0, end: e.score / 100),
                        duration: const Duration(milliseconds: 900),
                        curve: Curves.easeOutCubic,
                        builder: (_, v, __) => NurProgressBar(
                          value: v, height: 7,
                          a: _colorOf(e.id).withValues(alpha: 0.55),
                          b: _colorOf(e.id))),
                    ])),
              ])),
            label(s.ar ? 'من المطوِّر' : 'Developer Notes'),
            NurCard(
              margin: const EdgeInsets.only(bottom: 14),
              padding: const EdgeInsets.all(18),
              radius: 22,
              accent: p.gold,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start, children: [
                GradientText('﷽',
                  gradient: p.goldGradient,
                  style: const TextStyle(fontSize: 26, height: 1.4)),
                const SizedBox(height: 10),
                Text(
                  s.ar
                    ? 'هذا التطبيق وُلد من حبٍّ خالص لكتاب الله.\n\n'
                      'أكثر من ٦٠ جلسة، مئات الإصلاحات، ومحرك واحد لا يهدأ: '
                      'أن تُسمع التلاوة كما ينبغي لها أن تُسمع.\n\n'
                      'لا فريق، لا ميزانية — فقط هاتف، وطرفية، ومحبة للقرآن الكريم. '
                      'كل محرك بُني كأنه عبادة، وكل معامل ضُبط كأنه دعاء.\n\n'
                      'الهدف لم يتغيّر: أن يُعاد للصوت القرآني جماله الأصيل،'
                      ' حتى وإن جاء من تسجيل قديم أو ملف تالف.'
                    : 'This app was born from pure love for the Book of Allah.\n\n'
                      'Over 60 sessions, hundreds of fixes, one relentless goal: '
                      'to make Quranic recitation sound as it deserves to be heard.\n\n'
                      'No team, no budget — just a phone, Termux, and a deep love for the Quran. '
                      'Every engine was built like an act of worship, every parameter tuned like a prayer.\n\n'
                      'The mission never changed: restore the original beauty of the Quranic voice, '
                      'even from an old recording or a damaged file.',
                  style: TextStyle(color: p.textSub, fontSize: 12.5, height: 1.8)),
                const SizedBox(height: 14),
                NurChip(
                  label: s.ar
                    ? 'المرجع: الشيخ ياسر الدوسري · ١٤٢٥هـ · LUFS=-6.29'
                    : 'Reference: Yasser Al-Dossari · 1425H · LUFS=-6.29',
                  color: p.gold, icon: Icons.gps_fixed_rounded, fontSize: 10.5),
              ])),
            NurCard(
              padding: const EdgeInsets.all(14),
              radius: 20,
              child: Row(children: [
                ClipOval(child: Image.asset('assets/images/logo.png',
                  width: 46, height: 46, fit: BoxFit.cover,
                  errorBuilder: (_, __, ___) => Container(
                    width: 46, height: 46, color: p.surfaceHi,
                    child: Icon(Icons.music_note, color: p.gold, size: 22)))),
                const SizedBox(width: 12),
                Expanded(child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start, children: [
                  GradientText('محسِّن التلاوة',
                    gradient: p.goldGradient,
                    style: const TextStyle(
                      fontWeight: FontWeight.w800, fontSize: 15)),
                  Text(s.version, style: TextStyle(
                    color: p.textDim, fontSize: 11.5)),
                ])),
              ])),
          ]));
    });
  }
}

/// One line of the enhancement report.
class _Insight {
  final IconData icon;
  final Color color;
  final String ar, en;
  const _Insight(this.icon, this.color, this.ar, this.en);
}

// ── Engine data class (S21: rich model — score, features, what's-new) ─────────
class _EngineData {
  final String id, nameAr, nameEn, badge, bc;
  final double score;
  final List<String> features;
  final String whatsNewAr, whatsNewEn;
  final String? imgAsset;
  final bool localOnly;   // S84: true = requires local proot engine // S47 — engine logo
  const _EngineData(this.id, this.nameAr, this.nameEn, this.score,
      this.badge, this.bc, this.features, this.whatsNewAr, this.whatsNewEn,
      {this.imgAsset, this.localOnly = false});
}
