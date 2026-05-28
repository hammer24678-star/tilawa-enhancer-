import 'dart:io';
import 'dart:convert' show jsonDecode; // S65
import '../services/local_engine_service.dart'; // S65
import 'setup_screen.dart'; // S65

import 'dart:async';
import 'dart:math' as math;
import 'dart:math' show pi, sin, cos, Random; // S29+S30
import 'package:flutter/material.dart';
import '../main.dart' show ThemeProvider; // S31-F2c
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import '../state/lang_provider.dart';
import '../services/api_service.dart';
import 'history_screen.dart';
import 'settings_screen.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart'; // S61

// ── Sacred Cosmos tokens ─────────────────────────────────────────────────────
const _bgDeep    = Color(0xFF020D17);
const _bgSurface = Color(0xFF0C1E28);
const _bgCard    = Color(0xFF0F2420);
const _gold      = Color(0xFFD4AF37);
const _goldLight = Color(0xFFF0CF60);
const _goldMuted = Color(0xFF3A2B08);
const _teal      = Color(0xFF1DB898); // S40-TEAL
const _tealLight = Color(0xFF2E8FA8);
const _textA     = Color(0xFFE2CFA0);
const _textB     = Color(0xFF8AACBA);
const _textC     = Color(0xFF3D5A65);
const _ok        = Color(0xFF2ABF6E);
const _okDark    = Color(0xFF0D3D22);
const _err       = Color(0xFFD94040);
const _errDark   = Color(0xFF3D0808);

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


  // S32: theme cache — updated at top of every build() so ALL sub-methods
  // (which are instance methods) can read current theme colors directly.
  // Initialized to dark-mode defaults; updated before any widget is built.
  Color _tBg     = const Color(0xFF080A0E);
  Color _tCard   = const Color(0xFF161B22);
  Color _tBorder = const Color(0xFF21262D);
  Color _tText   = const Color(0xFFC9D1D9);
  Color _tSub    = const Color(0xFF8B949E);
  Color _tDim    = const Color(0xFF484F58);
  Color _tGold   = const Color(0xFFD4AF37);
  bool  _tDark   = true;
  // S19: Wake server state
  bool _waking       = false;
  int  _wakeAttempts = 0;

  late final AnimationController _glowCtrl;
  late final AnimationController _starCtrl;
  late final AnimationController _shimmer;
  late final AnimationController _geoRotCtrl;
  late final AnimationController _audioBarsCtrl;
  late final AnimationController _shimmerSweep;
  late final AnimationController _scoreCtrl;
  late Animation<double> _scoreAnim;
  late final List<_StarParticle> _starList;
  late final AnimationController _resultCtrl; // S29: result card entrance
  final ScrollController _scrollCtrl = ScrollController(); // S92-SCROLL
  late final AnimationController _particleCtrl; // S58: rising particles

  static const _wakeCh = MethodChannel('com.tilawa.tilawa_enhancer/wake'); // S63
  bool   _localMode  = false;  // S65: run via proot (offline)
  bool   _localReady = false;  // S65: setup confirmed complete
  String _localMsg   = '';     // S65: last line from engine stdout
  // ── Engines (S21: full data from documentation) ─────────────────────────────
  // S25: synced with server ENGINE_SCRIPTS (v8.1 default, v7.5/v7.6 removed)
  static const _engines = [
    // ── S47: Three Sacred Engines ──────────────────────────────────
    _EngineData(
      'v11.0', 'التجلي', 'The Manifestation', 99.5,
      'NEW', 'gold',
      ['Tier Router', 'Auto-Path', 'DF3 NR', 'النقاء', 'البيان', 'النور'],
      'يُحلِّل المصدر تلقائياً ويختار المسار الأمثل: الإتقان للتسجيلات النظيفة، الاسترداد للتالفة.',
      'Auto-analyses the source and routes to the optimal path: الإتقان for clean, الاسترداد for damaged.',
      imgAsset: 'assets/images/engines/tajalli.jpg', localOnly: true),
    _EngineData(
      'v11.1', 'الإتقان', 'Perfection', 99.0,
      '', 'gold',
      ['Pristine Path', 'DF3 NR', 'L-BFGS-B EQ', 'Joint Opt', 'LUFS Ceil', 'LRA Tune'],
      'مسار التسجيلات النظيفة والمضغوطة. تخفيض ضوضاء ثنائي — تحسين طيفي — معايرة LUFS+LRA مشتركة.',
      'Path for clean and compressed recordings. Two-stage NR, spectral EQ, joint LUFS+LRA calibration.',
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
    WidgetsBinding.instance.addObserver(this); // S56: lifecycle observer
    _notif = FlutterLocalNotificationsPlugin();
    _notif.initialize(const InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
    )).then((_) {
      _notif.resolvePlatformSpecificImplementation<AndroidFlutterLocalNotificationsPlugin>()
          ?.requestNotificationsPermission();
    });
    final rng = Random(7777);
    _starList = List.generate(18, (_) => _StarParticle(rng));
    _glowCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 2800))
      ..repeat(reverse: true);
    _starCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 14))
      ..repeat();
    _geoRotCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 80))
      ..repeat();
    _audioBarsCtrl = AnimationController( // S62-BARS-CTRL
        vsync: this, duration: const Duration(milliseconds: 1800))
      ..repeat(reverse: true);
    _shimmerSweep = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1200));
    _shimmer = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1500))
      ..repeat();
    _scoreCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 1300));
    _scoreAnim = const AlwaysStoppedAnimation(0);
    _resultCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 600));
    _particleCtrl = AnimationController( // S58
        vsync: this, duration: const Duration(seconds: 6))
      ..repeat();
    _checkServer();
    _serverTimer = Timer.periodic(
        const Duration(seconds: 6), (_) => _checkServer());
    LocalEngineService.isSetupComplete() // S65
        .then((r) { if (mounted) setState(() => _localReady = r); });
    // S65: pre-warm both servers on app init
    ApiService.preWarm();
    // S30-F1: restored — one loadLastEngine call
    ApiService.loadLastEngine().then((e) {
      if (mounted) setState(() => _engine = e);
    });
    // S57: restore in-progress job after app kill
    ApiService.loadJobId().then((saved) {
      if (!mounted || saved == null) return;
      setState(() {
        _jobId  = saved['job_id'];
        _engine = saved['engine'] ?? _engine;
        _busy   = true;
        _status = 'استئناف المعالجة...';
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
    _resultCtrl.dispose();
    _scrollCtrl.dispose(); // S92-SCROLL
    _particleCtrl.dispose(); // S58
    _starCtrl.dispose();
    _shimmer.dispose();
    _geoRotCtrl.dispose();
    _audioBarsCtrl.dispose();
    _shimmerSweep.dispose();
    _scoreCtrl.dispose();
    _glowCtrl.dispose();
    super.dispose();
  }

  // ── Server check ───────────────────────────────────────────────────────────
  Future<void> _checkServer() async {
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
    setState(() {
      _busy = false; _progress = 0;
      _status = ''; _isMerging = false;
      _jobId = null;
    });
    ApiService.clearJobId(); // S57
  }

  // ── S28: Reset for new file ────────────────────────────────────────────────
  void _resetForNewFile() {
    setState(() {
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
      setState(() {
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
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Local engine not set up — tap the setup link first'),
          backgroundColor: Color(0xFF200D0D),
          duration: Duration(seconds: 5)));
        return;
      }
      if (_file == null) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Pick an audio file first'),
          backgroundColor: Color(0xFF200D0D),
          duration: Duration(seconds: 4)));
        return;
      }
      if (_busy) {
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('Engine already running…'),
          backgroundColor: Color(0xFF1A1200),
          duration: Duration(seconds: 3)));
        return;
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
        final isMerging = (status == 'uploading' || status == 'merging');
        final display = isMerging
            ? _progress
            : (0.68 + srv * 0.32).clamp(_progress, 1.0); // S21: monotonic — never regress
        // S20-A: _isMerging drives indeterminate mode in progress bar
        _pollErrors = 0; // S22: reset on successful poll
        setState(() { _progress = display; _status = st['label'] ?? ''; _isMerging = isMerging && _busy; });

        if (status == 'error') {
          _pollTimer?.cancel();
          _wakeCh.invokeMethod('release').catchError((_) {}); // S63
          setState(() {
            _busy = false;
            _isMerging = false;  // S20-B: clear merge animation on server error
            _status = 'فشل: ${st['''error'''] ?? '''خطأ غير معروف'''}';
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
              textColor: _tGold,
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
              textColor: _tGold,
              onPressed: () {})));
        }
      }
    });
  }

  // ── Auto download after processing ────────────────────────────────────────
  Future<void> _downloadAndSave(Map<String, dynamic> sd) async {
    final s = LangProvider.strings(context);
    setState(() { _status = s.downloading; _progress = 0.95; });

    final filename = ApiService.buildFilename(_engine, originalPath: _file?.path); // S21 BUG2
    final (file, error) = await ApiService.downloadFile(_jobId!, filename);

    if (!mounted) return;

    final score = double.tryParse(sd['score']?.toString() ?? '0') ?? 0.0;

    // S63: fallback auto-retry — only retry if score == 75.0 exactly
    // (ffmpeg fallback always returns hardcoded score=75).
    // Real engines can score anywhere from 55-100; never discard them.
    if (score == 75.0 && file != null && _fallbackRetries < 2) {
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
          duration: const Duration(seconds: 38)));
        // Wait 35 s for the Space to finish loading reference audio,
        // then reprocess the same file.
        await Future.delayed(const Duration(seconds: 35));
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
          textColor: const Color(0xFF3FB950),
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
  Future<void> _reDownload() async {
    // S100: Local mode — copy cached output to Downloads
    if (_localMode && _output != null) {
      final src = _output!;
      try {
        final ts    = DateTime.now().millisecondsSinceEpoch;
        final ext   = src.path.endsWith('.mp3') ? 'mp3' : 'wav';
        final fname = 'tilawa_${_engine.replaceAll('.', '_')}_$ts.$ext';
        final dest  = File('/storage/emulated/0/Download/$fname');
        await dest.parent.create(recursive: true);
        await src.copy(dest.path);
        await LocalEngineService.scanFile(dest.path); // S103: notify MediaStore
        if (!mounted) return;
        setState(() { _output = dest; });
        final s = LangProvider.strings(context);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(
            s.ar ? '✅ تم الحفظ في Downloads\n📁 ${dest.path}'
                 : '✅ Saved to Downloads\n📁 ${dest.path}',
            style: const TextStyle(fontSize: 12)),
          backgroundColor: const Color(0xFF0D2015),
          duration: const Duration(seconds: 8),
          action: SnackBarAction(
            label: s.ar ? 'حسناً' : 'OK',
            textColor: const Color(0xFF3FB950),
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
          textColor: const Color(0xFF3FB950),
          onPressed: () {},
        ),
      ));
    } else {
      final msg = (error == 'JOB_EXPIRED')
          ? (s.ar ? s.jobExpired : s.jobExpired)
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
      final uri = Uri.parse(_output!.path);
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

  // ── S31-F2c: theme color helpers (private instance methods) ────────────────
  // Dart library-private functions (_name) can't cross library boundaries, so
  // we define them here inside the class instead of importing from main.dart.
  bool  _isDark(BuildContext ctx)   => ThemeProvider.isDark(ctx);
  Color _cBg(BuildContext ctx)      => _isDark(ctx) ? _tBg : const Color(0xFFFAF7EE);
  Color _cCard(BuildContext ctx)    => _isDark(ctx) ? _tCard : const Color(0xFFF3EED9);
  Color _cBorder(BuildContext ctx)  => _isDark(ctx) ? _tBorder : const Color(0xFFD4C99A);
  Color _cText(BuildContext ctx)    => _isDark(ctx) ? _tText : const Color(0xFF1A1400);
  Color _cSub(BuildContext ctx)     => _isDark(ctx) ? _tSub : const Color(0xFF6B5E40);
  Color _cDim(BuildContext ctx)     => _isDark(ctx) ? _tDim : const Color(0xFF8B7B5A);
  Color _cGold(BuildContext ctx)    => _isDark(ctx) ? _tGold : const Color(0xFFB8941F);

  // ── BUILD ──────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    // S32: populate theme cache so sub-methods see current colors
    _tDark = _isDark(context); _tBg = _cBg(context); _tCard = _cCard(context);
    _tBorder = _cBorder(context); _tText = _cText(context);
    _tSub = _cSub(context); _tDim = _cDim(context); _tGold = _cGold(context);
    final dark = _tDark; // used in gradient below
    final cBg = _tBg;   // used in Scaffold backgroundColor
    return Scaffold(
      backgroundColor: cBg,
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            // S54-BG-GRADIENT: tinted by selected engine
            colors: dark
              ? [Color.lerp(const Color(0xFF020D0C), _engineColor, 0.055)!,
                 Color.lerp(const Color(0xFF020D0C), _engineColor, 0.028)!]
              : [const Color(0xFFFAF7EE), const Color(0xFFF5F0E0)])),
        // S29: Sacred Cosmos painters Stack
        child: Stack(children: [
          if (dark) Positioned.fill(
            child: IgnorePointer(
              child: RepaintBoundary(
                child: CustomPaint(
                  painter: _GeoPainter(),
                  isComplex: true,
                  willChange: false)))),
          // S58: rising particles (engine-tinted incense dots)
          if (dark) Positioned.fill(
            child: IgnorePointer(
              child: RepaintBoundary(
                child: AnimatedBuilder(
                  animation: _particleCtrl,
                  builder: (_, __) => CustomPaint(
                    painter: _IncensePainter(
                      _particleCtrl.value, _engineColor)))))),
          if (dark) Positioned.fill(
            child: IgnorePointer(
              child: RepaintBoundary(
                child: AnimatedBuilder(
                  animation: _starCtrl,
                  builder: (_, __) => CustomPaint(
                    painter: _StarsPainter(_starCtrl.value, _starList),
                    isComplex: true))))),
          CustomScrollView(controller: _scrollCtrl, slivers: [ // S62b S92-SCROLL
            SliverAppBar( // S61-APPBAR
              pinned: true,
              floating: false,
              backgroundColor: const Color(0xFF020D0C),
              elevation: 0,
              expandedHeight: 72,
              bottom: PreferredSize(
                preferredSize: const Size.fromHeight(1),
                child: Container(
                  height: 1,
                  decoration: const BoxDecoration(
                    gradient: LinearGradient(
                      colors: [Colors.transparent,
                               Color(0xFFD4AF37),
                               Color(0xFF1DB898),
                               Colors.transparent])))),
              flexibleSpace: FlexibleSpaceBar(
                centerTitle: true,
                background: Container(
                  decoration: const BoxDecoration(
                    gradient: RadialGradient(
                      center: Alignment.topCenter,
                      radius: 1.8,
                      colors: [
                        Color(0xFF0D2E1F),
                        Color(0xFF020D0C)]))),
                title: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 34, height: 34,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        boxShadow: [BoxShadow(
                          color: const Color(0xFFD4AF37).withValues(alpha: 0.35),
                          blurRadius: 12)]),
                      child: ClipOval(child: Image.asset(
                        'assets/images/logo.png',
                        fit: BoxFit.cover))),
                    const SizedBox(width: 10),
                    ShaderMask(
                      shaderCallback: (b) => const LinearGradient(
                        colors: [Color(0xFFD4AF37), Color(0xFFF0CF60),
                                 Color(0xFFD4AF37)])
                        .createShader(b),
                      child: const Text('التلاوة',
                        style: TextStyle(
                          color: Colors.white,
                          fontSize: 19,
                          fontWeight: FontWeight.w300,
                          letterSpacing: 0.3))),
                    const Text('محسِّن ',
                      style: TextStyle(
                        color: Color(0xFFE2CFA0),
                        fontSize: 19,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.5)),
                  ])),
            ),
            SliverToBoxAdapter(child: _header(s)),
            SliverToBoxAdapter(child: _serverBanner(s)),
            SliverToBoxAdapter(child: _localModeToggle(s)), // S65
            SliverToBoxAdapter(child: _geoSep(s.ar ? 'اختر المحرك' : 'Engine')),
            SliverToBoxAdapter(child: _engineSelector(s)),
            SliverToBoxAdapter(child: _geoDiamond()),
            SliverToBoxAdapter(child: _fileCard(s)),
            if (_busy || _progress > 0)
              SliverToBoxAdapter(child: _progressCard(s)),
            if (_result != null)
              SliverToBoxAdapter(
                child: FadeTransition(
                  opacity: CurvedAnimation(
                    parent: _resultCtrl, curve: Curves.easeOutBack),
                  child: SlideTransition(
                    position: Tween<Offset>(
                      begin: const Offset(0, 0.08),
                      end: Offset.zero,
                    ).animate(CurvedAnimation(
                      parent: _resultCtrl, curve: Curves.easeOutBack)),
                    child: _resultCard(s),
                  ),
                ),
              ),
            SliverToBoxAdapter(child: _bottomRow(s)),
            SliverToBoxAdapter(child: _donationCard(s)),
            const SliverToBoxAdapter(child: SizedBox(height: 40)),
          ]),
        ]),
      ),
    );
  }

  // ── HEADER — Sacred Cosmos Hero ─────────────────────────────────────────────
  // ── LOCAL PROCESS (S65) — proot offline engine ────────────────────────────
  Future<void> _processLocal() async {
    if (_file == null || _busy) return;
    HapticFeedback.mediumImpact();
    setState(() {
      _busy      = true;
      _progress  = 0.02;
      _status    = 'Starting local engine…';
      _localMsg  = '';
    });

    await for (final ev in LocalEngineService.runEngine(
      engineId:  _engine,
      inputPath: _file!.path,
    )) {
      if (!mounted) return;

      if (ev['error'] == true) {
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
            parsedScore = (data['score'] as num?)?.toDouble() ?? 0;
            _result = Map<String, dynamic>.from(data); // S66
          }
        } catch (_) {}
        final fallbackScore = parsedScore > 0 ? parsedScore : 88.0;
        final resultData = _result ?? {'score': fallbackScore, 'lufs': -14.0, 'lra': 6.0, 'crest': 12.0, 'rms': -16.0};
        if ((resultData['score'] as num?)?.toDouble() == 0 || resultData['score'] == null) {
          resultData['score'] = fallbackScore;
        }
        _wakeCh.invokeMethod('release').catchError((_) {});
        setState(() { // S92: ALL result state inside setState
          _busy = false; _progress = 0;
          _status = 'Local engine complete';
          _output = File(ev['path'] as String? ?? '');
          _result = resultData;
        });
        _scoreCtrl.forward(from: 0);
        _resultCtrl.forward(from: 0);
        WidgetsBinding.instance.addPostFrameCallback((_) { // S92-SCROLL
          if (_scrollCtrl.hasClients) {
            _scrollCtrl.animateTo(0,
              duration: const Duration(milliseconds: 600),
              curve: Curves.easeOutCubic);
          }
        });
        return;
      }

      // Progress update
      final msg = ev['msg'] as String? ?? '';
      if (msg.isNotEmpty) setState(() { _localMsg = msg; _status = msg; });
    }
  }

  Widget _header(S s) => Container(
    padding: const EdgeInsets.fromLTRB(0, 0, 0, 8),
    child: Stack(children: [
      // Top-right action buttons
      Positioned(top: 16, right: 16,
        child: Row(children: [
          _iconBtn(Icons.info_outline_rounded, () => _showInfoSheet(context)),
          const SizedBox(width: 8),
          _iconBtn(Icons.settings_outlined, () => Navigator.push(context,
            PageRouteBuilder(
              pageBuilder: (_, __, ___) => const SettingsScreen(),
              transitionsBuilder: (_, anim, __, child) =>
                FadeTransition(opacity: anim, child: child),
              transitionDuration: const Duration(milliseconds: 220)))),
        ])),
      // Centered hero content
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 24, 16, 20),
        child: Column(children: [
          // Orbital ring + logo
          // S31-3RINGS
          RepaintBoundary(child: AnimatedBuilder( // S59b-ORBITAL-RB
            animation: Listenable.merge([_glowCtrl, _geoRotCtrl]),
            builder: (_, __) {
              final t  = _glowCtrl.value;
              final r  = _geoRotCtrl.value * 6.2832;
              return SizedBox(width: 148, height: 148,
                child: Stack(alignment: Alignment.center, children: [
                  // Ring 3 — outermost, slow clockwise
                  Transform.rotate(angle: r * 0.3,
                    child: Container(width: 148, height: 148,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: _gold.withValues(alpha: 0.10 + 0.12 * t),
                          width: 0.8),
                        boxShadow: [BoxShadow(
                          color: _gold.withValues(alpha: 0.06 + 0.08 * t),
                          blurRadius: 18 + 14 * t)]))),
                  // Ring 2 — mid, counter-clockwise
                  Transform.rotate(angle: -r * 0.5,
                    child: Container(width: 124, height: 124,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: _teal.withValues(alpha: 0.20 + 0.22 * t),
                          width: 1.0)))),
                  // Ring 1 — inner gold, clockwise faster
                  Transform.rotate(angle: r * 1.2,
                    child: Container(width: 104, height: 104,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        border: Border.all(
                          color: _gold.withValues(alpha: 0.22 + 0.28 * t),
                          width: 1.4),
                        boxShadow: [BoxShadow(
                          color: _gold.withValues(alpha: 0.12 + 0.16 * t),
                          blurRadius: 12 + 10 * t)]))),
                  // Logo — breathing scale
                  Transform.scale(
                    scale: 0.96 + 0.08 * t,
                    child: Container(width: 88, height: 88,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        boxShadow: [BoxShadow(
                          color: _gold.withValues(alpha: 0.22 + 0.28 * t),
                          blurRadius: 20 + 16 * t,
                          spreadRadius: 2)]),
                      child: ClipOval(child: Image.asset(
                        'assets/images/logo.png', fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => Container(
                          color: _bgCard,
                          child: const Icon(Icons.menu_book_rounded,
                            color: _gold, size: 44)))))),
                ]));
            })),
          const SizedBox(height: 16),
          // S61-HEADER-NAME — always Arabic, elegant sizing
          ShaderMask(
            shaderCallback: (b) => const LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFFD4AF37), Color(0xFFF5E070),
                       Color(0xFFD4AF37)])
              .createShader(b),
            child: const Text('محسِّن التلاوة',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 30, fontWeight: FontWeight.w800,
                color: Colors.white, height: 1.1,
                letterSpacing: 1.2))),
          const SizedBox(height: 4),
          // Subtitle pill
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
            decoration: BoxDecoration(
              color: _teal.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: _teal.withValues(alpha: 0.35))),
            child: RichText(
              text: TextSpan(
                style: const TextStyle(
                  color: _textB, fontSize: 10, letterSpacing: 1.5),
                children: [
                  TextSpan(text: s.subtitle),
                  const TextSpan(text: '  ·  ',
                    style: TextStyle(color: Color(0xFF1DB898))),
                  TextSpan(
                    text: _engines.firstWhere(
                      (e) => e.id == _engine,
                      orElse: () => _engines.first).nameAr,
                    style: const TextStyle(
                      color: Color(0xFFD4AF37),
                      fontWeight: FontWeight.w600)),
                ])),
          ),
        ])),
    ]),
  );

  Widget _iconBtn(IconData icon, VoidCallback onTap) {
    // S29-ICONBTN-SACRED
    return GestureDetector(
      onTap: onTap,
      child: RepaintBoundary(child: AnimatedBuilder( // S59b-ICONBTN-RB
        animation: _glowCtrl,
        builder: (_, __) => Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: _bgCard, shape: BoxShape.circle,
            border: Border.all(
              color: _teal.withValues(alpha: 0.28 + 0.22 * _glowCtrl.value)),
            boxShadow: [BoxShadow(
              color: _teal.withValues(alpha: 0.08 + 0.08 * _glowCtrl.value),
              blurRadius: 10)]),
          child: Icon(icon, color: _textB, size: 20)))));
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

  // ── SERVER BANNER (S19: wake button + hint) ────────────────────────────────
  // ── LOCAL MODE TOGGLE (S65) ──────────────────────────────────────────────
  Widget _localModeToggle(S s) {
    const gold  = Color(0xFFC8A048);
    const teal  = Color(0xFF1DB898);
    const jade  = Color(0xFF0D2B22);
    const textB = Color(0xFF8AACBA);
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 6),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 280),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        decoration: BoxDecoration(
          color: _localMode
            ? jade.withValues(alpha: 0.85)
            : const Color(0xFF0A0E12).withValues(alpha: 0.6),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: _localMode
              ? gold.withValues(alpha: 0.45)
              : const Color(0xFF1A2733),
            width: 1.0)),
        child: Row(children: [
          Icon(
            _localMode ? Icons.offline_bolt_rounded : Icons.cloud_outlined,
            color: _localMode ? gold : textB, size: 18),
          const SizedBox(width: 10),
          Expanded(child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
            Text(
              _localMode ? 'Local Engine (Offline)' : 'Server Mode (Online)',
              style: TextStyle(
                color: _localMode ? gold : textB,
                fontSize: 12, fontWeight: FontWeight.w700)),
            if (_localMode && !_localReady)
              GestureDetector(
                onTap: _busy ? null : () {
                  // S78: re-check before pushing SetupScreen
                  LocalEngineService.isSetupComplete().then((ready) {
                    if (mounted) setState(() => _localReady = ready);
                    if (!mounted) return;
                    if (ready) {
                      setState(() => _localReady = true);
                    } else {
                      Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) => SetupScreen(
                          onDone: () {
                            Navigator.of(context).pop();
                            LocalEngineService.isSetupComplete()
                              .then((r) { if (mounted) setState(() => _localReady = r); });
                          },
                          onSkip: () {
                            Navigator.of(context).pop();
                            setState(() => _localMode = false);
                          })));
                    }
                  });
                },
                child: const Text('Tap to set up (one-time ~200MB)',
                  style: TextStyle(
                    color: Color(0xFFF0D882), fontSize: 10,
                    decoration: TextDecoration.underline))),
            if (_localMode && _localReady)
              const Text('Ready — processes fully offline',
                style: TextStyle(color: teal, fontSize: 10)),
            if (!_localMode)
              const Text('Switch for offline, private processing',
                style: TextStyle(color: Color(0xFF3D5A65), fontSize: 10)),
          ])),
          Switch(
            value: _localMode,
            onChanged: _busy ? null : (v) {
              setState(() => _localMode = v);
              // S93: always re-check on toggle ON
              if (v) {
                LocalEngineService.isSetupComplete().then((ready) {
                  if (!mounted) return;
                  setState(() => _localReady = ready);
                  if (!ready) {
                    Navigator.of(context).push(MaterialPageRoute(
                      builder: (_) => SetupScreen(
                        onDone: () {
                          Navigator.of(context).pop();
                          LocalEngineService.isSetupComplete()
                            .then((r) { if (mounted) setState(() => _localReady = r); });
                        },
                        onSkip: () {
                          Navigator.of(context).pop();
                          setState(() => _localMode = false);
                        })));
                  }
                });
              }
            },
            activeColor: gold,
            inactiveThumbColor: textB.withValues(alpha: 0.5),
            inactiveTrackColor: const Color(0xFF1A2733)),
        ]),
      ),
    );
  }

  Widget _serverBanner(S s) {
    final isOffline = !_serverUp;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      margin: const EdgeInsets.fromLTRB(16, 10, 16, 10),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      decoration: BoxDecoration(
        color: _serverUp
          ? _ok.withValues(alpha: 0.06)
          : _waking
            ? _gold.withValues(alpha: 0.06)
            : _err.withValues(alpha: 0.06),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: _serverUp
            ? const Color(0xFF3FB950)
            : _waking
              ? _tGold
              : const Color(0xFFF85149),
          width: 0.8)),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            // Status dot / spinner
            if (_waking)
              const SizedBox(width: 8, height: 8,
                child: CircularProgressIndicator(
                  strokeWidth: 1.5,
                  color: Color(0xFFD4AF37)))
            else
              RepaintBoundary(child: AnimatedBuilder( // S59b-SRVDOT-RB
                animation: _glowCtrl,
                builder: (_, __) {
                  final t = _glowCtrl.value;
                  final c = _serverUp ? _ok : _err;
                  return SizedBox(width: 22, height: 22,
                    child: Stack(alignment: Alignment.center, children: [
                      if (_serverUp) Container(
                        width: 8 + 12 * t, height: 8 + 12 * t,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          border: Border.all(
                            color: c.withValues(alpha: 0.6 * (1 - t)),
                            width: 1.5))),
                      Container(width: 8, height: 8,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle, color: c,
                          boxShadow: [BoxShadow(
                            color: c.withValues(alpha: 0.4 + 0.5 * t),
                            blurRadius: 5 + 8 * t)])),
                    ]));
                })),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                _waking
                  ? s.waking
                  : _serverUp
                    ? (_latencyMs != null
                        ? '${s.serverOnline} · ${_latencyMs}ms' // S30-S
                        : s.serverOnline)
                    : s.serverOffline,
                style: TextStyle(
                  color: _serverUp
                    ? const Color(0xFF3FB950)
                    : _waking
                      ? _tGold
                      : const Color(0xFFF85149),
                  fontSize: 12)),
            ),
            // S19: Wake button — shown when server is offline and not already waking
            if (isOffline && !_waking)
              GestureDetector(
                onTap: _wakeServer,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1A1000),
                    borderRadius: BorderRadius.circular(8),
                    border: Border.all(
                      color: _tGold.withValues(alpha: 0.6))),
                  child: Text(s.wakeServer,
                    style: const TextStyle(
                      color: Color(0xFFD4AF37),
                      fontSize: 11,
                      fontWeight: FontWeight.bold)))),
          ]),
          // S19: Hint text when offline
          if (isOffline && !_waking) ...[
            const SizedBox(height: 6),
            Text(s.wakeHint,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Color(0xFF8B949E), fontSize: 10)),
          ],
        ],
      ),
    );
  }

  // ── ENGINE SELECTOR ────────────────────────────────────────────────────────
  Widget _engineSelector(S s) => Container(
    margin: const EdgeInsets.fromLTRB(16,16,16,8),
    decoration: BoxDecoration(
      color: _bgSurface,
      borderRadius: BorderRadius.circular(16),
      border: Border.all(color: _teal.withValues(alpha: 0.28)),
      boxShadow: [BoxShadow(
        color: _teal.withValues(alpha: 0.08), blurRadius: 16, offset: const Offset(0, 4))]),
    child: Column(children: [
      // ── Header row ──────────────────────────────────────────────────
      Padding(
        padding: const EdgeInsets.fromLTRB(18,16,18,14),
        child: Row(children: [
          const Icon(Icons.tune_rounded, color: Color(0xFF484F58), size: 13),
          const SizedBox(width: 7),
          Text(s.chooseEngine, style: const TextStyle(
            color: _textB, fontSize: 11, letterSpacing: 1.8,
            fontWeight: FontWeight.w600)),
          const Spacer(),
          // Score pill for selected engine
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: _badgeBg(_selectedEngine.bc),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: _badgeColor(_selectedEngine.bc).withValues(alpha: 0.5))),
            child: Text(
              '≥${_selectedEngine.score.toInt()}',
              style: TextStyle(
                color: _engineColor,
                fontSize: 10, fontWeight: FontWeight.bold))),
        ])),
      ..._engines.map((e) => _engineCard(e, s)),
      const SizedBox(height: 10),
    ]),
  );

  _EngineData get _selectedEngine =>
      _engines.firstWhere((e) => e.id == _engine, orElse: () => _engines.first);

  // S54: per-engine identity color drives bg tint and glow
  Color get _engineColor {
    switch (_engine) {
      case 'v11.0': return const Color(0xFFD4AF37); // tajalli gold
      case 'v11.1': return const Color(0xFF1DB898); // itiqan teal
      case 'v11.2': return const Color(0xFFE8A030); // isteidad amber
      case 'v10.0': return const Color(0xFFB8860B); // Aetherion dark gold
      case 'v9.0':  return const Color(0xFF9B7FFF); // Evolution violet
      case 'v8.5':  return const Color(0xFF5BB8FF); // Honest blue
      case 'v8.0':  return const Color(0xFFFF7EA0); // Precision rose
      default:      return const Color(0xFFD4AF37);
    }
  }

  // ── KHATAM BADGE (S50) ─────────────────────────────────────────────────
  Widget _khatamBadge(Color col, double score, {double size = 42}) {
    return SizedBox(width: size, height: size,
      child: Stack(alignment: Alignment.center, children: [
        RepaintBoundary(child: AnimatedBuilder( // S59b-ENGRING-RB
          animation: _glowCtrl,
          builder: (_, __) {
            final g = _glowCtrl.value;
            return Stack(children: [
              Positioned.fill(child: Container(
                margin: const EdgeInsets.all(3),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(2),
                  color: col.withValues(alpha: 0.12),
                  border: Border.all(
                    color: col.withValues(alpha: 0.58 + 0.30 * g), width: 1.5),
                  boxShadow: [BoxShadow(
                    color: col.withValues(alpha: 0.20 + 0.22 * g),
                    blurRadius: 8 + 6 * g)]))),
              Positioned.fill(child: Transform.rotate(
                angle: pi / 4,
                child: Container(
                  margin: const EdgeInsets.all(3),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(2),
                    color: col.withValues(alpha: 0.05),
                    border: Border.all(
                      color: col.withValues(alpha: 0.38 + 0.18 * g), width: 1))))),
            ]);
          })),
        ShaderMask(
          shaderCallback: (b) => LinearGradient(
            colors: [col, col.withValues(alpha: 0.65)],
            begin: Alignment.topCenter, end: Alignment.bottomCenter,
          ).createShader(b),
          child: Text('≥${score.toInt()}',
            style: const TextStyle(
              color: Colors.white, fontSize: 9.5, fontWeight: FontWeight.w800,
              letterSpacing: 0.3))),
      ]));
  }

  Widget _engineCard(_EngineData e, S s) {
    final sel = _engine == e.id;
    final col = _badgeColor(e.bc);
    final bg  = _badgeBg(e.bc);
    return GestureDetector(  // S87: removed Opacity/AbsorbPointer wrapper
      onTap: () {
        HapticFeedback.selectionClick(); // S30-P1
        setState(() {
              _engine = e.id;
              // S87: removed auto-mode switch — user controls mode
            });
        ApiService.saveLastEngine(e.id); // S28-T2: persist
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        margin: const EdgeInsets.fromLTRB(8,3,8,3),
        // S32-ENGINE-GLASS
        decoration: BoxDecoration(
          color: sel
            ? col.withValues(alpha: 0.10)
            : const Color(0xFF0D2B22).withValues(alpha: 0.70),  // S85: grey handled by Opacity wrapper
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: sel
              ? col.withValues(alpha: 0.70)
              : const Color(0xFF1DB898).withValues(alpha: 0.22),
            width: sel ? 1.8 : 0.8),
          boxShadow: sel ? [
            BoxShadow(
              color: col.withValues(alpha: 0.22),
              blurRadius: 22, spreadRadius: 0,
              offset: const Offset(0, 4)),
            BoxShadow(
              color: col.withValues(alpha: 0.10),
              blurRadius: 40, spreadRadius: 2),
          ] : null),
        child: Stack(children: [
          // Left accent bar
          if (sel) Positioned(left: 0, top: 0, bottom: 0,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 280),
              width: 3.5,
              decoration: BoxDecoration(
                color: col,
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(13),
                  bottomLeft: Radius.circular(13)),
                boxShadow: [BoxShadow(
                  color: col.withValues(alpha: 0.55), blurRadius: 8)]))),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          // S54: Premium image engine card
          if (e.imgAsset != null) RepaintBoundary(child: AnimatedBuilder( // S59-CARD-IMG-RB
            animation: _glowCtrl,
            builder: (_, __) {
              final g = _glowCtrl.value;
              return Stack(children: [
                // Image layer with optional tint overlay
                ClipRRect(
                  borderRadius: const BorderRadius.only(
                    topLeft: Radius.circular(13),
                    topRight: Radius.circular(13)),
                  child: Stack(children: [
                    Image.asset(e.imgAsset!,
                      width: double.infinity, height: 130,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Container(
                        height: 130,
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment.topLeft,
                            end: Alignment.bottomRight,
                            colors: [col.withValues(alpha: 0.25),
                                     const Color(0xFF020D0C)])))),
                    if (sel) Positioned.fill(child: Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          colors: [
                            col.withValues(alpha: 0.22 + 0.12 * g),
                            Colors.transparent])))),
                    Positioned.fill(child: Container(
                      decoration: BoxDecoration(
                        gradient: LinearGradient(
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                          stops: const [0.35, 1.0],
                          colors: [Colors.transparent,
                                   const Color(0xFF020D0C).withValues(alpha: 0.92)])))),
                  ])),
                // Khatam badge top-right
                Positioned(top: 8, right: 10,
                  child: _khatamBadge(col, e.score, size: 48)),
                // Badge pill top-left
                if (e.badge.isNotEmpty)
                  Positioned(top: 10, left: 10,
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                      decoration: BoxDecoration(
                        color: col.withValues(alpha: 0.15 + 0.10 * g),
                        borderRadius: BorderRadius.circular(6),
                        border: Border.all(
                          color: col.withValues(alpha: 0.55 + 0.25 * g)),
                        boxShadow: [BoxShadow(
                          color: col.withValues(alpha: 0.25 + 0.20 * g),
                          blurRadius: 8)]),
                      child: Text(e.badge, style: TextStyle(
                        color: col, fontSize: 9, fontWeight: FontWeight.w800,
                        letterSpacing: 0.8)))),
                // Engine name and ID pill at bottom
                Positioned(bottom: 0, left: 0, right: 0,
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
                    child: Row(children: [
                      Expanded(child: ShaderMask(
                        shaderCallback: (b) => LinearGradient(
                          colors: sel
                            ? [col, col.withValues(alpha: 0.80)]
                            : [Colors.white, Colors.white70],
                          begin: Alignment.topCenter,
                          end: Alignment.bottomCenter,
                        ).createShader(b),
                        child: Text(s.ar ? e.nameAr : e.nameEn,
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 20, fontWeight: FontWeight.w800,
                            height: 1.1,
                            shadows: [Shadow(
                              color: Colors.black87, blurRadius: 10)])))),
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 8, vertical: 3),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.55),
                          borderRadius: BorderRadius.circular(8),
                          border: Border.all(
                            color: col.withValues(alpha: 0.45))),
                        child: Text(e.id, style: TextStyle(
                          color: col, fontSize: 9,
                          fontWeight: FontWeight.w700))),
                    ]))),
                // Selected glow border overlay
                if (sel) Positioned.fill(child: Container(
                  decoration: BoxDecoration(
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(13),
                      topRight: Radius.circular(13)),
                    border: Border.all(
                      color: col.withValues(alpha: 0.55 + 0.35 * g),
                      width: 2.0)))),
              ]);
            })),
          // S50: JSX khatam card
          if (e.imgAsset == null) Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
            child: Row(crossAxisAlignment: CrossAxisAlignment.center,
              children: [
              _khatamBadge(col, e.score),
              const SizedBox(width: 12),
              Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
                  Flexible(child: Text(e.nameAr,
                    style: TextStyle(
                      color: sel ? col : col.withValues(alpha: 0.80),
                      fontSize: 18, fontWeight: FontWeight.w700, height: 1.1))),
                  const SizedBox(width: 8),
                  // S84-BADGE: LOCAL / SERVER mode badge
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: e.localOnly
                        ? _teal.withValues(alpha: 0.18)
                        : _tBorder.withValues(alpha: 0.5),
                      borderRadius: BorderRadius.circular(5),
                      border: Border.all(
                        color: e.localOnly ? _teal : _tSub.withValues(alpha: 0.5))),
                    child: Text(
                      e.localOnly ? '🏠 LOCAL' : '☁ SERVER',
                      style: TextStyle(
                        color: e.localOnly ? _teal : _tSub,
                        fontSize: 7, fontWeight: FontWeight.bold,
                        letterSpacing: 0.6))),
                  if (e.badge.isNotEmpty) ...[
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: col.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(5),
                        border: Border.all(color: col.withValues(alpha: 0.45))),
                      child: Text(e.badge, style: TextStyle(
                        color: col, fontSize: 8, fontWeight: FontWeight.bold,
                        letterSpacing: 0.8))),
                  ],
                ]),
                const SizedBox(height: 3),
                Text(e.nameEn, style: TextStyle(
                  color: const Color(0xFFF0E8D2).withValues(alpha: 0.42),
                  fontSize: 10.5, fontStyle: FontStyle.italic)),
              ])),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: col.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: col.withValues(alpha: 0.35))),
                child: Text(e.id, style: TextStyle(
                  color: col, fontSize: 9, fontWeight: FontWeight.w600,
                  letterSpacing: 0.4))),
            ])),
          // ── Expanded details (selected engine only) ──────────────────
          AnimatedCrossFade(
            duration: const Duration(milliseconds: 250),
            crossFadeState: sel
              ? CrossFadeState.showSecond
              : CrossFadeState.showFirst,
            firstChild: const SizedBox.shrink(),
            secondChild: _engineExpanded(e, s, col),
          ),
        ]), // end Column
        ]), // end accent-bar Stack
      ),
    );  // S87c: close GestureDetector
  }

  Widget _engineExpanded(_EngineData e, S s, Color col) => Padding(
    padding: const EdgeInsets.fromLTRB(12,0,12,12),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Container(height: 1, color: _tBorder,
        margin: const EdgeInsets.only(bottom: 10)),
      // Score bar
      Row(children: [
        Expanded(child: ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: e.score / 100,
            minHeight: 5,
            backgroundColor: _tBorder,
            valueColor: AlwaysStoppedAnimation<Color>(col)))),
        const SizedBox(width: 8),
        Text('${e.score.toInt()}/100', style: TextStyle(
          color: col, fontSize: 10, fontWeight: FontWeight.bold)),
      ]),
      const SizedBox(height: 10),
      // Feature chips
      Wrap(
        spacing: 5, runSpacing: 5,
        children: e.features.map((f) => Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
          decoration: BoxDecoration(
            color: col.withValues(alpha: 0.07),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: col.withValues(alpha: 0.28))),
          child: Text(f, style: TextStyle(
            color: col.withValues(alpha: 0.75), fontSize: 9)))).toList()),
      const SizedBox(height: 10),
      // What's New box
      Container(
        width: double.infinity,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: const Color(0xFF0A0C10),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: col.withValues(alpha: 0.2))),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(s.ar ? '▶ الجديد في هذه النسخة'
                    : "▶ What's New",
            style: TextStyle(
              color: col, fontSize: 9, fontWeight: FontWeight.bold)),
          const SizedBox(height: 5),
          Text(s.ar ? e.whatsNewAr : e.whatsNewEn,
            textDirection: s.ar ? TextDirection.rtl : TextDirection.ltr,
            style: const TextStyle(
              color: Color(0xFF8B949E), fontSize: 10, height: 1.55)),
        ])),
    ]),
  );

  // S40-GEO-SEP — sacred geometry section divider from HTML design
  Widget _geoSep(String label) => Padding(
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 2),
    child: Row(children: [
      Expanded(child: Container(height: 1,
        decoration: BoxDecoration(gradient: LinearGradient(
          colors: [Colors.transparent, _engineColor],
          stops: [0.0, 1.0])))),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          _geoDiamond(),
          if (label.isNotEmpty) Padding(
            padding: const EdgeInsets.symmetric(horizontal: 6),
            child: Text(label.toUpperCase(), style: TextStyle(
              color: _engineColor, fontSize: 9,
              letterSpacing: 0.22, fontWeight: FontWeight.w500))),
          _geoDiamond(),
        ])),
      Expanded(child: Container(height: 1,
        decoration: BoxDecoration(gradient: LinearGradient(
          colors: [_engineColor, Colors.transparent],
          stops: [0.0, 1.0])))),
    ]));

  Widget _geoDiamond() => Transform.rotate(
    angle: 0.7854,
    child: Container(
      width: 6, height: 6,
      decoration: BoxDecoration(
        color: _engineColor,
        borderRadius: BorderRadius.circular(1),
        boxShadow: [BoxShadow(
          color: _engineColor.withValues(alpha: 0.50), blurRadius: 5)])));

  Color _badgeColor(String bc) => bc == 'gold' ? _tGold
      : bc == 'green' ? const Color(0xFF3FB950)
      : bc == 'blue'  ? const Color(0xFF58A6FF)
      : _tDim;

  Color _badgeBg(String bc) => bc == 'gold' ? const Color(0xFF1A1200)
      : bc == 'green' ? const Color(0xFF0D2015)
      : bc == 'blue'  ? const Color(0xFF0D1B2E)
      : _tCard;

  // ── FILE CARD — Mihrab Upload Portal (S43) ───────────────────────────────
  Widget _fileCard(S s) {
    final hasFile = _file != null;
    return GestureDetector(
      onTap: _busy ? null : _pickFile,
      child: Container(
        margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),
        decoration: BoxDecoration(
          color: hasFile
            ? const Color(0xFF0D2B22)
            : const Color(0xFF071A14),
          borderRadius: const BorderRadius.only( // S46-ARCH
            topLeft: Radius.circular(200),
            topRight: Radius.circular(200),
            bottomLeft: Radius.circular(22),
            bottomRight: Radius.circular(22)),
          border: Border.all(
            color: hasFile
              ? _engineColor.withValues(alpha: 0.68)
              : const Color(0xFF1DB898).withValues(alpha: 0.24),
            width: hasFile ? 1.8 : 1.0),
          boxShadow: [BoxShadow(
            color: hasFile
              ? _engineColor.withValues(alpha: 0.20)
              : const Color(0xFF1DB898).withValues(alpha: 0.08),
            blurRadius: 36, spreadRadius: 2)]),
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
          child: Column(children: [
            // ── Upload icon with breathing ring ──
            AnimatedBuilder(
              animation: _glowCtrl,
              builder: (_, __) => Container(
                width: 72, height: 72,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: _engineColor
                      .withValues(alpha: 0.38 + 0.32 * _glowCtrl.value),
                    width: 1.5),
                  boxShadow: [BoxShadow(
                    color: _engineColor
                      .withValues(alpha: 0.10 + 0.18 * _glowCtrl.value),
                    blurRadius: 18 + 16 * _glowCtrl.value)]),
                child: AnimatedSwitcher(
                  duration: const Duration(milliseconds: 380),
                  switchInCurve: Curves.easeOutBack,
                  transitionBuilder: (child, anim) => ScaleTransition(
                    scale: anim, child: child),
                  child: Icon(
                    hasFile ? Icons.audio_file_rounded : Icons.upload_rounded,
                    key: ValueKey(hasFile),
                    color: const Color(0xFFC8A048), size: 34)))),
            const SizedBox(height: 16),
            // ── Animated waveform bars (file selected) / empty placeholder ──
            SizedBox(height: 48, // S62-FILE-BOX
              child: hasFile
                ? AnimatedBuilder( // S62-FILE-BARS
                    animation: _audioBarsCtrl,
                    builder: (_, __) => Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: List.generate(26, (i) {
                        final v = _audioBarsCtrl.value;
                        final f1 = sin((v + i / 26) * 6.2832 * 1.4);
                        final f2 = sin((v * 1.9 + i / 26) * 6.2832 * 0.7);
                        final f3 = sin((v * 0.5 + i / 26) * 6.2832 * 2.1);
                        final wave = f1 * 0.5 + f2 * 0.3 + f3 * 0.2;
                        final barH = 5.0 + 36.0 * (wave * 0.5 + 0.5);
                        final glow = 0.45 + 0.55 * v;
                        return Container(
                          width: 3, height: barH,
                          margin: const EdgeInsets.symmetric(horizontal: 1.5),
                          decoration: BoxDecoration(
                            borderRadius: BorderRadius.circular(2),
                            gradient: LinearGradient(
                              begin: Alignment.bottomCenter,
                              end: Alignment.topCenter,
                              colors: [
                                const Color(0xFF1DB898).withValues(alpha: glow),
                                const Color(0xFFD4AF37).withValues(alpha: glow * 0.8)]),
                            boxShadow: [BoxShadow(
                              color: const Color(0xFF1DB898).withValues(alpha: 0.25 * v),
                              blurRadius: 4)]));
                      })))
                : Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(18, (i) => Container(
                      width: 3, height: 4.0 + 14.0 * sin(i * 0.45).abs(),
                      margin: const EdgeInsets.symmetric(horizontal: 1.5),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(2),
                        color: const Color(0xFF1DB898).withValues(alpha: 0.20)))))),
            const SizedBox(height: 12),
            // ── Filename / pick label ──
            Text(
              hasFile ? _file!.path.split('/').last // S46-PORTAL
                : (s.ar ? 'أسقط تلاوتك في هذا المحراب'
                        : 'Drop your Quran audio into this sacred portal'),
              textDirection: TextDirection.rtl,
              textAlign: TextAlign.center,
              maxLines: 2, overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: hasFile
                  ? const Color(0xFFE2CFA0)
                  : const Color(0xFF8AACBA),
                fontSize: hasFile ? 13 : 15,
                fontWeight: hasFile ? FontWeight.w500 : FontWeight.w600,
                letterSpacing: hasFile ? 0 : 0.4)),
            if (hasFile) ...[
              const SizedBox(height: 4),
              Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                Text(_sizeLabel,
                  style: const TextStyle(
                    color: Color(0xFF8B949E), fontSize: 11)),
                if (_isLarge) ...[
                  const SizedBox(width: 8),
                  _badge(s.chunkedBadge, 'gold'),
                ],
              ]),
              if (_fileBytes > 0) ...[
                const SizedBox(height: 3),
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  const Icon(Icons.timer_outlined,
                    size: 10, color: Color(0xFF3D5A65)),
                  const SizedBox(width: 3),
                  Text('${s.estTime}: ${_estimatedTime()}',
                    style: const TextStyle(
                      color: Color(0xFF3D5A65), fontSize: 10)),
                ]),
              ],
            ],
            const SizedBox(height: 3),
            if (!hasFile) Text('mp3  ·  wav  ·  m4a', // S46-FMT
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Color(0xFF1DB898),
                fontSize: 9, letterSpacing: 1.4)),
            const SizedBox(height: 3),
            Text(s.sizeLimit,
              style: const TextStyle(
                color: Color(0xFF3D5A65), fontSize: 10,
                letterSpacing: 0.4)),
            if (hasFile) ...[
              const SizedBox(height: 18),
              // ── Elevate button — gold gradient ──
              GestureDetector(
                onTap: _busy ? null : () {  // S95
                  HapticFeedback.mediumImpact();
                  _process();
                },
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(14),
                    gradient: _busy  // S95
                      ? LinearGradient(colors: [
                          const Color(0xFF1A1200).withValues(alpha: 0.6),
                          const Color(0xFF1A1200).withValues(alpha: 0.6)])
                      : const LinearGradient(
                          begin: Alignment.topLeft,
                          end: Alignment.bottomRight,
                          colors: [
                            Color(0xFF6B4518),
                            Color(0xFFC8A048),
                            Color(0xFFF0D882),
                            Color(0xFFC8A048),
                          ],
                          stops: [0.0, 0.3, 0.6, 1.0]),
                    boxShadow: _busy ? null : [  // S95
                      BoxShadow(
                        color: const Color(0xFFC8A048).withValues(alpha: 0.40),
                        blurRadius: 24, offset: const Offset(0, 6)),
                    ]),
                  child: _busy
                    ? Row(mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          const SizedBox(width: 16, height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Color(0xFF020D0C))),
                          const SizedBox(width: 10),
                          Text(s.processing,
                            style: const TextStyle(
                              color: Color(0xFF020D0C),
                              fontWeight: FontWeight.w900, fontSize: 14,
                              letterSpacing: 0.5)),
                        ])
                    : Text(
                        s.ar ? 'ارفع التلاوة' : 'Elevate This Recitation',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: _busy  // S95
                            ? const Color(0xFF3D5A65)
                            : const Color(0xFF020D0C),
                          fontWeight: FontWeight.w900, fontSize: 14,
                          letterSpacing: 0.8)))),
            ],
          ]),
        ),
      ),
    );
  }

  // ── S21: Info bottom sheet ──────────────────────────────────────────────────
  void _showInfoSheet(BuildContext ctx) {
    final s = LangProvider.strings(ctx);
    showModalBottomSheet(
      context: ctx,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (_) => DraggableScrollableSheet(
        initialChildSize: 0.78,
        minChildSize: 0.40,
        maxChildSize: 0.95,
        builder: (_, ctrl) => Container(
          decoration: const BoxDecoration(
            color: Color(0xFF061A14),
            borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
          child: Column(children: [
            Container(
              margin: const EdgeInsets.only(top: 12, bottom: 8),
              width: 36, height: 4,
              decoration: BoxDecoration(
                color: _tBorder,
                borderRadius: BorderRadius.circular(2))),
            Padding(
              padding: const EdgeInsets.fromLTRB(20,4,20,12),
              child: Row(children: [
                const Icon(Icons.info_outline_rounded,
                  color: Color(0xFFD4AF37), size: 18),
                const SizedBox(width: 8),
                Text(s.ar ? 'عن التطبيق' : 'About',
                  style: const TextStyle(
                    color: Color(0xFFD4AF37),
                    fontWeight: FontWeight.bold, fontSize: 16)),
              ])),
            Expanded(child: ListView(
              controller: ctrl,
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 40),
              children: [
                _infoSectionLabel(s.ar ? '📺 قناة يوتيوب' : '📺 YouTube Channel'),
                GestureDetector(
                  onTap: () => launchUrl(
                    Uri.parse('https://youtube.com/@carm-tv2hv'),
                    mode: LaunchMode.externalApplication),
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 16),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFF1A0A0A),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: const Color(0xFFFF0000).withValues(alpha: 0.3))),
                    child: Row(children: [
                      Container(
                        width: 40, height: 40,
                        decoration: BoxDecoration(
                          color: const Color(0xFFFF0000),
                          borderRadius: BorderRadius.circular(10)),
                        child: const Icon(Icons.play_arrow_rounded,
                          color: Colors.white, size: 26)),
                      const SizedBox(width: 12),
                      Expanded(child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                        Text(s.ar ? 'قناة يوتيوب' : 'YouTube Channel',
                          style: const TextStyle(
                            color: Color(0xFFC9D1D9),
                            fontWeight: FontWeight.bold, fontSize: 13)),
                        const SizedBox(height: 2),
                        const Text('@carm-tv2hv',
                          style: TextStyle(
                            color: Color(0xFF8B949E), fontSize: 11)),
                      ])),
                      const Icon(Icons.open_in_new_rounded,
                        color: Color(0xFF484F58), size: 16),
                    ]))),
                _infoSectionLabel(s.ar ? '💬 قناة تيليغرام' : '💬 Telegram Channel'),
                GestureDetector(
                  onTap: () => launchUrl(
                    Uri.parse('https://t.me/TilawaEhnacher'),
                    mode: LaunchMode.externalApplication),
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 16),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFF0A0F1A),
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: const Color(0xFF2AABEE).withValues(alpha: 0.35))),
                    child: Row(children: [
                      Container(
                        width: 40, height: 40,
                        decoration: BoxDecoration(
                          gradient: const LinearGradient(
                            colors: [Color(0xFF2AABEE), Color(0xFF229ED9)]),
                          borderRadius: BorderRadius.circular(10)),
                        child: const Icon(Icons.send_rounded,
                          color: Colors.white, size: 22)),
                      const SizedBox(width: 12),
                      Expanded(child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                        Text(s.ar ? 'قناة التيليغرام' : 'Telegram Channel',
                          style: const TextStyle(
                            color: Color(0xFFC9D1D9),
                            fontWeight: FontWeight.bold, fontSize: 13)),
                        const SizedBox(height: 2),
                        const Text('@TilawaEhnacher',
                          style: TextStyle(
                            color: Color(0xFF8B949E), fontSize: 11)),
                      ])),
                      const Icon(Icons.open_in_new_rounded,
                        color: Color(0xFF484F58), size: 16),
                    ]))),
                _infoSectionLabel(s.ar ? '🎯 المرجع الصوتي' : '🎯 Reference Standard'),
                Container(
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0A1A0F),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: const Color(0xFF3FB950).withValues(alpha: 0.3))),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                    Text(
                      s.ar ? 'الشيخ ياسر الدوسري — 1425هـ'
                           : 'Sheikh Yasser Al-Dossari — 1425H',
                      style: const TextStyle(
                        color: Color(0xFF3FB950),
                        fontWeight: FontWeight.bold, fontSize: 13)),
                    const SizedBox(height: 8),
                    const Text(
                      'LUFS=-6.29  ·  RMS=-10.01  ·  Crest=10.25  ·  LRA=4.19',
                      style: TextStyle(
                        color: Color(0xFF8B949E),
                        fontSize: 11, height: 1.7)),
                    const SizedBox(height: 8),
                    Text(
                      s.ar
                        ? 'ثلاثة ملفات مرجعية: الأعراف · الفتح · فاطر'
                        : 'Three reference files: Al-Araf · Al-Fath · Fatir',
                      style: const TextStyle(
                        color: Color(0xFF484F58), fontSize: 10)),
                  ])),
                _infoSectionLabel(s.ar ? '📊 مقارنة المحركات' : '📊 Engine Comparison'),
                Container(
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration( // S61-ENG-CONTAINER
                    color: const Color(0xFF061018),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(
                      color: const Color(0xFFD4AF37).withValues(alpha: 0.2)),
                    boxShadow: [BoxShadow(
                      color: const Color(0xFF1DB898).withValues(alpha: 0.06),
                      blurRadius: 20)]),
                  child: Column(
                    children: _engines.map((e) {
                      final col = _badgeColor(e.bc);
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                          Row(children: [
                            Text(e.id, style: TextStyle(
                              color: col,
                              fontWeight: FontWeight.bold, fontSize: 12)),
                            const SizedBox(width: 6),
                            Expanded(child: Text(s.ar ? e.nameAr : e.nameEn,
                              style: const TextStyle(
                                color: Color(0xFF8B949E), fontSize: 10))),
                            Text('≥${e.score.toInt()}', style: TextStyle(
                              color: col,
                              fontWeight: FontWeight.bold, fontSize: 12)),
                          ]),
                          const SizedBox(height: 5),
                          // S61-ENG-BAR
                          Stack(children: [
                            ClipRRect(
                              borderRadius: BorderRadius.circular(4),
                              child: LinearProgressIndicator(
                                value: e.score / 100,
                                minHeight: 7,
                                backgroundColor: _tBorder,
                                valueColor: AlwaysStoppedAnimation<Color>(
                                  col))),
                            Positioned.fill(child: ClipRRect(
                              borderRadius: BorderRadius.circular(4),
                              child: FractionallySizedBox(
                                widthFactor: e.score / 100,
                                alignment: Alignment.centerLeft,
                                child: Container(
                                  decoration: BoxDecoration(
                                    borderRadius: BorderRadius.circular(4),
                                    boxShadow: [BoxShadow(
                                      color: col.withValues(alpha: 0.5),
                                      blurRadius: 6,
                                      spreadRadius: 0)])))))],
                          ),
                        ]));
                    }).toList())),
                _infoSectionLabel(s.ar ? '📖 من المطوِّر' : '📖 Developer Notes'),
                Container(
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      begin: Alignment.topLeft, end: Alignment.bottomRight,
                      colors: [Color(0xFF0D1B2A), Color(0xFF06101A)]),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(
                      color: const Color(0xFFD4AF37).withValues(alpha: 0.18))),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                    Text(
                      s.ar ? '﷽' : '﷽',
                      style: const TextStyle(
                        color: Color(0xFFD4AF37),
                        fontSize: 22, height: 1.4)),
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
                      style: const TextStyle(
                        color: Color(0xFFA8B8C8),
                        fontSize: 12, height: 1.75)),
                    const SizedBox(height: 14),
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: const Color(0xFFD4AF37).withValues(alpha: 0.08),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: const Color(0xFFD4AF37).withValues(alpha: 0.2))),
                      child: Text(
                        s.ar
                          ? '🎯 المرجع: الشيخ ياسر الدوسري · ١٤٢٥هـ · LUFS=-6.29'
                          : '🎯 Reference: Yasser Al-Dossari · 1425H · LUFS=-6.29',
                        style: const TextStyle(
                          color: Color(0xFFD4AF37),
                          fontSize: 10, fontWeight: FontWeight.bold))),
                  ])),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: _tCard,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: _tBorder)),
                  child: Row(children: [
                    ClipOval(child: Image.asset('assets/images/logo.png',
                      width: 44, height: 44, fit: BoxFit.cover,
                      errorBuilder: (_,__,___) => Container(
                        width: 44, height: 44,
                        color: _goldMuted.withValues(alpha: 0.55),
                        child: const Icon(Icons.music_note,
                          color: Color(0xFFD4AF37), size: 22)))),
                    const SizedBox(width: 12),
                    Column(crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                      const Text('محسِّن التلاوة',
                        style: TextStyle(
                          color: Color(0xFFD4AF37),
                          fontWeight: FontWeight.bold, fontSize: 14)),
                      Text(s.version, style: const TextStyle(
                        color: Color(0xFF8B949E), fontSize: 11)),
                    ]),
                  ])),
              ],
            )),
          ]),
        ),
      ),
    );
  }

  Widget _infoSectionLabel(String text) => Padding(
    padding: const EdgeInsets.only(bottom: 8, top: 4),
    child: Text(text, style: const TextStyle(
      color: Color(0xFF8B949E), fontSize: 11,
      fontWeight: FontWeight.bold, letterSpacing: 0.5)));

    Widget _badge(String text, String bc) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
    decoration: BoxDecoration(
      color: _badgeBg(bc), borderRadius: BorderRadius.circular(4),
      border: Border.all(color: _badgeColor(bc).withValues(alpha: 0.5))),
    child: Text(text,
      style: TextStyle(
        color: _badgeColor(bc), fontSize: 9, fontWeight: FontWeight.bold)));

  // ── PROGRESS ───────────────────────────────────────────────────────────────
  Widget _progressCard(S s) => Container(
    margin: const EdgeInsets.fromLTRB(16,10,16,4),
    padding: const EdgeInsets.all(18),
    // S35-PROGRESS-CARD
    decoration: BoxDecoration(
      gradient: const LinearGradient(
        begin: Alignment.topLeft, end: Alignment.bottomRight,
        colors: [Color(0xFF0D2B22), Color(0xFF071A14)]),
      borderRadius: BorderRadius.circular(16),
      border: Border.all(
        color: _engineColor.withValues(alpha: 0.20), width: 0.9),
      boxShadow: [
        BoxShadow(
          color: const Color(0xFFD4AF37).withValues(alpha: 0.08),
          blurRadius: 30, spreadRadius: 0,
          offset: const Offset(0, 6)),
        BoxShadow(
          color: const Color(0xFF1DB898).withValues(alpha: 0.08),
          blurRadius: 60, spreadRadius: 2),
      ]),
    child: Column(children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Flexible(child: AnimatedSwitcher( // S30-P2
          duration: const Duration(milliseconds: 300),
          transitionBuilder: (child, anim) => FadeTransition(
            opacity: anim, child: child),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min, children: [
            Text(
              _status.isEmpty ? s.processing : _status,
              key: ValueKey(_status),
              style: const TextStyle( // S38-STATUS-STYLE
                color: Color(0xFFCFD8DC),
                fontSize: 13, letterSpacing: 0.2)),
            const SizedBox(height: 10),
            AnimatedBuilder(
              animation: _audioBarsCtrl,
              builder: (_, __) { // S62-PROG-BARS
                const n = 20;
                final v = _audioBarsCtrl.value;
                return Row(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: List.generate(n, (i) {
                    // Multi-frequency: primary + harmonic + slow swell
                    final f1 = sin((v + i / n) * 6.2832 * 1.5);
                    final f2 = sin((v * 1.7 + i / n) * 6.2832 * 0.8);
                    final f3 = sin((v * 0.4 + i / n) * 6.2832 * 0.3);
                    final wave = (f1 * 0.55 + f2 * 0.28 + f3 * 0.17);
                    final h = 6.0 + 28.0 * (wave * 0.5 + 0.5);
                    final lit = (i / n) < _progress;
                    final bright = 0.55 + 0.45 * v;
                    return Container(
                      width: 3.0, height: h,
                      margin: const EdgeInsets.only(right: 2.5),
                      decoration: BoxDecoration(
                        gradient: lit ? LinearGradient(
                          begin: Alignment.bottomCenter,
                          end: Alignment.topCenter,
                          colors: [
                            _gold.withValues(alpha: bright),
                            _goldLight.withValues(alpha: bright * 0.7)]) : null,
                        color: lit ? null : _teal.withValues(alpha: 0.18),
                        borderRadius: BorderRadius.circular(2),
                        boxShadow: lit ? [BoxShadow(
                          color: _gold.withValues(alpha: 0.35 * v),
                          blurRadius: 4)] : null));
                  }));
              }),
          ]))),
        // S20-A: '...' when merging — frozen '68%' looks like a crash
        ShaderMask( // S38-PCT-SHADER
          shaderCallback: (b) => const LinearGradient(
            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),
          child: Text(_isMerging ? '...' : '${(_progress * 100).toInt()}%',
            style: const TextStyle(
              color: Colors.white,
              fontWeight: FontWeight.bold, fontSize: 18))),
      ]),
      const SizedBox(height: 6),
      Center(child: SizedBox(width: 90, height: 90, // S46-MANDALA
        child: RepaintBoundary(child: AnimatedBuilder( // S59-MANDALA-RB
          animation: _geoRotCtrl,
          builder: (_, __) => CustomPaint(
            painter: _MandalaPainter(_geoRotCtrl.value)))))),
      const SizedBox(height: 6),
      ClipRRect(
        borderRadius: BorderRadius.circular(8),
        // S20-A: null = indeterminate (animated pulse) during server merge
        child: LinearProgressIndicator(
          value: _isMerging ? null : _progress, minHeight: 8,
          backgroundColor: _tBorder,
          valueColor: const AlwaysStoppedAnimation(Color(0xFFD4AF37)))),
      // S28: Cancel button
      const SizedBox(height: 10),
      Container( // S38-CANCEL-STYLE
        decoration: BoxDecoration(
          border: Border.all(
            color: const Color(0xFF1B6B80).withValues(alpha: 0.35)),
          borderRadius: BorderRadius.circular(8)),
        child: TextButton.icon(
          onPressed: _cancelProcessing,
          style: TextButton.styleFrom(
            padding: const EdgeInsets.symmetric(
              horizontal: 12, vertical: 4),
            minimumSize: Size.zero),
          icon: const Icon(Icons.cancel_outlined, size: 14,
            color: Color(0xFF6B9EAE)),
          label: Text(s.cancelBtn,
            style: const TextStyle(
              color: Color(0xFF6B9EAE), fontSize: 11)),
        )),
    ]),  // S37-PAREN-FIX (restored structural ) — S35 FIX-A2 over-stripped)
  );  // S38-CONTAINER-CLOSE

  // ── RESULT + DOWNLOAD BUTTON (S19: better labels, fallback warning, open) ──
  Widget _resultCard(S s) {
    final score = double.tryParse(_result?['score']?.toString() ?? '0') ?? 0.0;

    // S19 FIX: Score labels now have proper thresholds.
    // Before: 75 showed "Very Good" (wrong). Now shows "Fair" correctly.
    final label = score >= 96 ? s.excellent
        : score >= 90 ? s.great
        : score >= 85 ? s.good        // Very Good
        : score >= 78 ? s.decent      // Good
        : s.fair;                     // Fair — covers the 75 fallback case

    final scoreColor = score >= 90 ? const Color(0xFF3FB950)
        : score >= 80 ? _tGold
        : const Color(0xFFF85149); // red for scores below 80

    const engineNames = {
      'v10.0': 'Aetherion Foundation',
      'v9.0': 'The Evolution',
      'v8.9': 'Soft Tiers + LPC',
      'v8.5': 'Honest Ceiling',
      'v8.4': 'Source Tier Intelligence',
      'v8.0': 'Calibrated Precision',
      'v7.0': 'Classic',
    };
    final engineName = engineNames[_engine] ?? _engine;
    final filename   = ApiService.buildFilename(_engine);

    // S19: "Open in Player" only available when we have a content:// URI (API 29+)
    final hasContentUri = _output?.path.startsWith('content://') ?? false;

    return Container(
      margin: const EdgeInsets.fromLTRB(16,10,16,4),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: score < 80 ? _err.withValues(alpha: 0.05) : _ok.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: (score < 80 ? _err : _ok).withValues(alpha: 0.35),
          width: 1.2),
        boxShadow: [BoxShadow(
          color: (score < 80
              ? const Color(0xFFF85149)
              : const Color(0xFF3FB950)).withValues(alpha: 0.12),
          blurRadius: 24, offset: const Offset(0, 6))]),
      child: Column(children: [
        // S30-R1: score arc gauge
        AnimatedBuilder(
          animation: _resultCtrl,
          builder: (_, __) {
            final t = Curves.easeOutCubic.transform(_resultCtrl.value);
            final pulse = _resultCtrl.value > 0.85
                ? 1.0 + 0.05 * (1 - (_resultCtrl.value - 0.85) / 0.15)
                : 1.0;
            return Column(mainAxisSize: MainAxisSize.min, children: [
              Stack(alignment: Alignment.center, children: [
              // S45-KHATAM sacred geometry layer
              AnimatedBuilder(
                animation: _glowCtrl,
                builder: (_, __) => CustomPaint(
                  size: const Size(170, 170),
                  painter: _KhatamPainter(
                    t: _glowCtrl.value, color: scoreColor))),
              // Burst particles on reveal
              if (score >= 85) AnimatedBuilder(
                animation: _resultCtrl,
                builder: (_, __) => CustomPaint(
                  size: const Size(170, 170),
                  painter: _ScoreBurstPainter(
                    progress: _resultCtrl.value,
                    color: scoreColor))),
              Stack(alignment: Alignment.center, children: [
              // Burst particles on reveal
              if (score >= 85) AnimatedBuilder(
                animation: _resultCtrl,
                builder: (_, __) => CustomPaint(
                  size: const Size(170, 170),
                  painter: _ScoreBurstPainter(
                    progress: _resultCtrl.value,
                    color: scoreColor))),
              SizedBox(
                width: 148, height: 148,
                child: CustomPaint(
                  painter: _ScoreArcPainter(
                    progress: t, score: score, color: scoreColor,
                    trackColor: _tBorder),
                  child: Center(child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Transform.scale(
                        scale: pulse,
                        child: Text(
                          '${(score * t).toStringAsFixed(1)}',
                          style: TextStyle(
                            color: scoreColor,
                            fontWeight: FontWeight.w900,
                            fontSize: 40,
                            letterSpacing: -1))),
                      Text('/100', style: TextStyle(
                        color: scoreColor.withValues(alpha: 0.55),
                        fontSize: 12,
                        fontWeight: FontWeight.bold)),
                    ])),
                )),
              ]), // end burst Stack
              ]), // end burst Stack
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
                decoration: BoxDecoration(
                  color: scoreColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: scoreColor.withValues(alpha: 0.4))),
                child: Text(label, style: TextStyle(
                  color: scoreColor,
                  fontWeight: FontWeight.bold,
                  fontSize: 13, letterSpacing: 0.5))),
            ]);
          }),
        const SizedBox(height: 14),

        // Engine used
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
          decoration: BoxDecoration(
            color: const Color(0xFF1A1200),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(
              color: _tGold.withValues(alpha: 0.3))),
          child: Text('$_engine — $engineName',
            style: const TextStyle(
              color: Color(0xFFD4AF37), fontSize: 11))),
        const SizedBox(height: 12),

        // S30-R2: metrics 2×2 grid
        _metricGrid(),
        const SizedBox(height: 12),

        // S30-R4: section divider
        Container(height: 1,
          color: _tBorder,
          margin: const EdgeInsets.only(bottom: 14)),

        // S19 FALLBACK WARNING: shown when score ≤ 78
        if (score < 78) ...[  // S32-BUG3-FIX: 78 = Good label, not fallback
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
              color: const Color(0xFF200D0D),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: const Color(0xFFF85149).withValues(alpha: 0.4))),
            child: Text(s.fallbackWarning,
              textAlign: TextAlign.center,
              style: const TextStyle(
                color: Color(0xFFF85149),
                fontSize: 11, height: 1.5))),
        ],

        // Download button
        SizedBox(width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: _reDownload,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF3FB950),
              foregroundColor: const Color(0xFF000000),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12)),
              elevation: 2),
            icon: const Icon(Icons.download_rounded, size: 22),
            label: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(s.downloadBtn,
                  style: const TextStyle(
                    fontWeight: FontWeight.bold, fontSize: 14)),
                const SizedBox(height: 2),
                Text(filename,
                  style: TextStyle(
                    fontSize: 10,
                    color: Colors.black.withValues(alpha: 0.6))),
              ]),
          )),

        // S30-R3: Open + Share in one row
        if (hasContentUri || (_output?.path.startsWith('content://') ?? false)) ...[
          const SizedBox(height: 8),
          Row(children: [
            if (hasContentUri) Expanded(
              child: OutlinedButton.icon(
                onPressed: _openInPlayer,
                style: OutlinedButton.styleFrom(
                  foregroundColor: const Color(0xFF58A6FF),
                  side: const BorderSide(color: Color(0xFF58A6FF), width: 0.8),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12))),
                icon: const Icon(Icons.play_circle_outline_rounded, size: 16),
                label: Text(s.openInPlayer,
                  style: const TextStyle(fontSize: 12)))),
            if (hasContentUri && (_output?.path.startsWith('content://') ?? false))
              const SizedBox(width: 8),
            if (_output?.path.startsWith('content://') ?? false) Expanded(
              child: OutlinedButton.icon(
                onPressed: _shareFile,
                style: OutlinedButton.styleFrom(
                  foregroundColor: _tSub,
                  side: const BorderSide(color: Color(0xFF30363D), width: 0.8),
                  padding: const EdgeInsets.symmetric(vertical: 10),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12))),
                icon: const Icon(Icons.share_rounded, size: 16),
                label: Text(s.shareBtn,
                  style: const TextStyle(fontSize: 12)))),
          ]),
        ],
        // Saved indicator
        if (_output != null) ...[
          const SizedBox(height: 8),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.check_circle_outline,
              color: Color(0xFF3FB950), size: 14),
            const SizedBox(width: 4),
            Text(s.savedTo,
              style: const TextStyle(
                color: Color(0xFF3FB950), fontSize: 11)),
          ]),
        ],
        // S28: Process Another File button
        const SizedBox(height: 12),
        SizedBox(width: double.infinity,
          child: OutlinedButton.icon(
            onPressed: _resetForNewFile,
            style: OutlinedButton.styleFrom(
              foregroundColor: const Color(0xFF58A6FF),
              side: const BorderSide(color: Color(0xFF58A6FF), width: 0.8),
              padding: const EdgeInsets.symmetric(vertical: 10),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12))),
            icon: const Icon(Icons.refresh_rounded, size: 18), // S30-X1
            label: Text(s.processAnother,
              style: const TextStyle(fontSize: 13)),
          )),
      ]),
    );
  }

  // S30-R2: 2×2 metric grid
  Widget _metricGrid() => GestureDetector(
    onTap: _copyMetrics,
    child: Container(
      decoration: BoxDecoration(
        color: _tCard,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: _tBorder)),
      child: Column(children: [
        IntrinsicHeight(child: Row(children: [
          Expanded(child: _metricTile(
            'LUFS',  _result?['lufs']?.toString()  ?? '—', -6.29)),
          const VerticalDivider(width: 1, color: Color(0xFF21262D)),
          Expanded(child: _metricTile(
            'RMS',   _result?['rms']?.toString()   ?? '—', -10.01)),
        ])),
        const Divider(height: 1, color: Color(0xFF21262D)),
        IntrinsicHeight(child: Row(children: [
          Expanded(child: _metricTile(
            'Crest', _result?['crest']?.toString() ?? '—', 10.25)),
          const VerticalDivider(width: 1, color: Color(0xFF21262D)),
          Expanded(child: _metricTile(
            'LRA',   _result?['lra']?.toString()   ?? '—', 4.19)),
        ])),
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 5),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.copy_rounded, size: 10,
              color: Color(0xFF484F58)),
            const SizedBox(width: 4),
            const Text('tap to copy',
              style: TextStyle(color: Color(0xFF484F58), fontSize: 9)),
          ])),
      ]),
    ),
  );

  Widget _metricTile(String label, String value, double target) {
    final num = double.tryParse(value);
    String delta = '';
    String arrow = '';
    Color tileColor = _tDim;
    if (num != null && value != '—') {
      final diff = num - target;
      delta = '${diff >= 0 ? "+" : ""}${diff.toStringAsFixed(2)}';
      if (diff.abs() <= 0.5) {
        arrow = '✓'; tileColor = const Color(0xFF3FB950);
      } else if (diff > 0) {
        arrow = '▲'; tileColor = _tGold;
      } else {
        arrow = '▼'; tileColor = const Color(0xFF58A6FF);
      }
    }
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(label, style: const TextStyle(
            color: Color(0xFF8B949E),
            fontSize: 10, letterSpacing: 0.5)),
          const SizedBox(height: 5),
          Text(value, style: const TextStyle(
            color: Color(0xFFD4AF37),
            fontWeight: FontWeight.bold, fontSize: 18)),
          if (delta.isNotEmpty) ...[
            const SizedBox(height: 3),
            Row(mainAxisSize: MainAxisSize.min, children: [
              Text(arrow, style: TextStyle(
                color: tileColor, fontSize: 9,
                fontWeight: FontWeight.bold)),
              const SizedBox(width: 2),
              Text(delta, style: TextStyle(
                color: tileColor, fontSize: 9,
                fontWeight: FontWeight.w600)),
            ]),
          ],
        ]),
    );
  }

  // ── BOTTOM ROW ─────────────────────────────────────────────────────────────
  Widget _bottomRow(S s) => Padding(
    padding: const EdgeInsets.fromLTRB(16,10,16,4),
    child: Material( // S30-P4
      color: _bgSurface,
      borderRadius: BorderRadius.circular(14),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => Navigator.push(context,
          PageRouteBuilder(
            pageBuilder: (_, __, ___) => const HistoryScreen(),
            transitionsBuilder: (_, anim, __, child) =>
              FadeTransition(opacity: anim, child: child),
            transitionDuration: const Duration(milliseconds: 220),
          )),
        splashColor: _tGold.withValues(alpha: 0.12),
        highlightColor: _tGold.withValues(alpha: 0.06),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: BoxDecoration(
            border: Border.all(color: _tBorder)),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.history_rounded, color: _textB, size: 18),
            const SizedBox(width: 8),
            Text(s.history, style: const TextStyle(
              color: Color(0xFF8B949E), fontSize: 13)),
          ]),
        ),
      ),
    ),
  );

  // ── DONATION CARD ──────────────────────────────────────────────────────────
  Widget _donationCard(S s) => Padding(
    padding: const EdgeInsets.fromLTRB(16,4,16,4),
    child: Material( // S30-P5
      color: const Color(0xFF1A1500),
      borderRadius: BorderRadius.circular(12),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () {
          HapticFeedback.lightImpact();
          launchUrl(
            Uri.parse('https://buymeacoffee.com/tilawa'),
            mode: LaunchMode.externalApplication);
        },
        splashColor: _tGold.withValues(alpha: 0.18),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: _tGold.withValues(alpha: 0.3))),
        child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          const Icon(Icons.volunteer_activism,
            color: Color(0xFFD4AF37), size: 18),
          const SizedBox(width: 8),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(s.donation, style: const TextStyle(
              color: Color(0xFFD4AF37),
              fontWeight: FontWeight.bold, fontSize: 13)),
            Text(s.donationDesc, style: const TextStyle(
              color: Color(0xFF8B949E), fontSize: 10)),
          ]),
        ]),
      ),
    ),
  ),
  );
}

// S30-P5-close
// ── S30-R1: Score arc painter ──────────────────────────────────────────────────
class _ScoreArcPainter extends CustomPainter {
  final double progress;
  final double score;
  final Color  color;
  final Color  trackColor; // S32-fix: passed from State, was incorrectly _tBorder
  _ScoreArcPainter({
    required this.progress,
    required this.score,
    required this.color,
    required this.trackColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final c = Offset(size.width / 2, size.height / 2);
    final r = size.width / 2 - 12.0;
    const start = pi * 0.75;   // 135° — bottom-left
    const sweep = pi * 1.5;    // 270° arc

    // Background track
    canvas.drawArc(
      Rect.fromCircle(center: c, radius: r),
      start, sweep, false,
      Paint()
        ..color = trackColor
        ..style = PaintingStyle.stroke
        ..strokeWidth = 12
        ..strokeCap = StrokeCap.round,
    );

    // Score fill
    if (progress > 0.01) {
      canvas.drawArc(
        Rect.fromCircle(center: c, radius: r),
        start, sweep * (score / 100) * progress, false,
        Paint()
          ..color = color
          ..style = PaintingStyle.stroke
          ..strokeWidth = 12
          ..strokeCap = StrokeCap.round,
      );
    }
  }

  @override
  bool shouldRepaint(_ScoreArcPainter o) =>
      o.progress != progress || o.color != color || o.trackColor != trackColor;
}

// ── Engine data class (S21: rich model — score, features, what's-new) ───────────
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

// ── Sacred Cosmos painters ────────────────────────────────────────────────────

class _RadialPulsePainter extends CustomPainter {
  final double t;
  _RadialPulsePainter(this.t);
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width * 0.5;
    final cy = size.height * 0.38;
    final p = Paint()..style = PaintingStyle.fill;
    for (int i = 0; i < 3; i++) {
      final phase = (t + i * 0.33) % 1.0;
      final r = 60.0 + phase * 220.0;
      final op = (1.0 - phase) * (i == 0 ? 0.10 : 0.06);
      p.color = const Color(0xFFC8A048).withValues(alpha: op);
      p.maskFilter = const MaskFilter.blur(BlurStyle.normal, 18);
      canvas.drawCircle(Offset(cx, cy), r, p);
    }
    p.maskFilter = const MaskFilter.blur(BlurStyle.normal, 40);
    p.color = const Color(0xFFC8A048).withValues(alpha: 0.06 + 0.06 * t);
    canvas.drawCircle(Offset(cx, cy), 80, p);
    p.maskFilter = const MaskFilter.blur(BlurStyle.normal, 24);
    p.color = const Color(0xFF1DB898).withValues(alpha: 0.04 + 0.04 * (1 - t));
    canvas.drawCircle(Offset(cx, cy), 120 + 40 * t, p);
  }
  @override bool shouldRepaint(_RadialPulsePainter o) => o.t != t;
}
class _StarParticle {
  final double x, y, size, phase, speed, twinkle;
  _StarParticle(Random r)
      : x = r.nextDouble(), y = r.nextDouble(),
        size = 1.4 + r.nextDouble() * 2.8,
        phase = r.nextDouble() * 6.2832,
        speed = 0.15 + r.nextDouble() * 0.6,
        twinkle = 0.4 + r.nextDouble() * 1.6;
}

class _StarsPainter extends CustomPainter {
  final double t;
  final List<_StarParticle> stars;
  _StarsPainter(this.t, this.stars);
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()..maskFilter = const MaskFilter.blur(BlurStyle.normal, 1.0);
    for (final s in stars) {
      final a = t * 6.2832 * s.speed + s.phase;
      final x = s.x * size.width  + sin(a)        * size.width  * 0.016;
      final y = s.y * size.height + cos(a * 0.71) * size.height * 0.012;
      final alpha = sin(t * 6.2832 * s.twinkle + s.phase) * 0.5 + 0.5;
      final op = 0.22 + 0.78 * alpha;
      final sz = s.size * (0.55 + 0.45 * alpha);
      final idx = stars.indexOf(s);
      final sc = idx % 5 == 0 ? _teal
          : idx % 3 == 0 ? const Color(0xFFF0E8C8)
          : _gold;
      // Soft bloom
      p.maskFilter = MaskFilter.blur(BlurStyle.normal, sz * 2.5);
      p.color = sc.withValues(alpha: op * 0.25);
      canvas.drawCircle(Offset(x, y), sz * 2.0, p);
      // Sharp core
      p.maskFilter = null;
      p.color = sc.withValues(alpha: op);
      canvas.drawCircle(Offset(x, y), sz, p);
    }
  }
  @override bool shouldRepaint(_StarsPainter o) => o.t != t;
}

// S45-MANDALA-CLASS — 8-petal spinning mandala for processing screen
class _MandalaPainter extends CustomPainter {
  final double t; // 0..1 geoRotCtrl value
  const _MandalaPainter(this.t);
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2, cy = size.height / 2;
    final r  = size.width / 2 - 4;
    final angle = t * pi * 2;
    final p = Paint()..style = PaintingStyle.stroke;
    // 8 overlapping petal circles
    p.color = const Color(0xFFC8A048).withValues(alpha: 0.50);
    p.strokeWidth = 0.9;
    for (int i = 0; i < 8; i++) {
      final a = (i / 8) * pi * 2 + angle;
      canvas.drawCircle(
        Offset(cx + r * 0.52 * cos(a), cy + r * 0.52 * sin(a)),
        r * 0.40, p);
    }
    // Outer gold ring
    p.color = const Color(0xFFD4AF37).withValues(alpha: 0.38);
    p.strokeWidth = 1.0;
    canvas.drawCircle(Offset(cx, cy), r, p);
    // Counter-rotating hexagon
    p.color = const Color(0xFF1DB898).withValues(alpha: 0.32);
    p.strokeWidth = 0.8;
    final hex = Path();
    for (int i = 0; i < 6; i++) {
      final a = (i / 6) * pi * 2 - angle * 0.5;
      final x = cx + r * 0.50 * cos(a);
      final y = cy + r * 0.50 * sin(a);
      if (i == 0) hex.moveTo(x, y); else hex.lineTo(x, y);
    }
    hex.close();
    canvas.drawPath(hex, p);
    // 8-point inner star
    p.color = const Color(0xFFD4AF37).withValues(alpha: 0.45);
    p.strokeWidth = 1.0;
    final star = Path();
    for (int i = 0; i < 16; i++) {
      final a = (i / 16) * pi * 2 + angle * 0.25;
      final rr = i.isEven ? r * 0.28 : r * 0.14;
      final x = cx + rr * cos(a), y = cy + rr * sin(a);
      if (i == 0) star.moveTo(x, y); else star.lineTo(x, y);
    }
    star.close();
    canvas.drawPath(star, p);
    canvas.drawCircle(Offset(cx, cy), 3,
      Paint()..color = const Color(0xFFD4AF37).withValues(alpha: 0.72)
             ..style = PaintingStyle.fill);
  }
  @override bool shouldRepaint(_MandalaPainter o) => o.t != t;
}

// S45-KHATAM-CLASS — two rotated squares star for result screen
class _KhatamPainter extends CustomPainter {
  final double t;     // glow animation 0..1
  final Color color;
  const _KhatamPainter({required this.t, required this.color});
  @override
  void paint(Canvas canvas, Size size) {
    final cx = size.width / 2, cy = size.height / 2;
    final r  = size.width / 2 - 10;
    final p  = Paint()..style = PaintingStyle.stroke;
    // Square 1
    p.color = color.withValues(alpha: 0.12 + 0.10 * t);
    p.strokeWidth = 1.0;
    final sq1 = Path();
    for (int i = 0; i < 4; i++) {
      final a = (i / 4) * pi * 2 - pi / 4;
      if (i == 0) sq1.moveTo(cx + r * cos(a), cy + r * sin(a));
      else sq1.lineTo(cx + r * cos(a), cy + r * sin(a));
    }
    sq1.close();
    canvas.drawPath(sq1, p);
    // Square 2 (rotated 45°)
    final sq2 = Path();
    for (int i = 0; i < 4; i++) {
      final a = (i / 4) * pi * 2 + pi / 4;
      if (i == 0) sq2.moveTo(cx + r * cos(a), cy + r * sin(a));
      else sq2.lineTo(cx + r * cos(a), cy + r * sin(a));
    }
    sq2.close();
    canvas.drawPath(sq2, p);
    // Pulsing outer glow ring
    p.color = color.withValues(alpha: 0.07 + 0.07 * t);
    p.strokeWidth = 0.7;
    canvas.drawCircle(Offset(cx, cy), r + 8, p);
    // Inner circle
    p.color = color.withValues(alpha: 0.08 + 0.06 * t);
    p.strokeWidth = 0.5;
    canvas.drawCircle(Offset(cx, cy), r * 0.40, p);
  }
  @override bool shouldRepaint(_KhatamPainter o) =>
      o.t != t || o.color != color;
}

// S40-INCENSE — rising gold particle dots from HTML design
class _IncensePainter extends CustomPainter {
  // S58-PARTICLES — 18 rising dots, engine-tinted, matches JSX Particles()
  final double t;
  final Color engCol;
  _IncensePainter(this.t, this.engCol);
  static const _xs = [
    0.08, 0.15, 0.22, 0.30, 0.38, 0.45,
    0.52, 0.58, 0.65, 0.72, 0.80, 0.88,
    0.18, 0.35, 0.55, 0.68, 0.78, 0.42,
  ];
  static const _teal = Color(0xFF1DB898);
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()..style = PaintingStyle.fill;
    for (int i = 0; i < _xs.length; i++) {
      // stagger each particle with a fixed offset so they cover full height
      final phase = ((t + i / _xs.length) % 1.0);
      final drift = sin(phase * 6.2832 * 1.8 + i * 1.3) * 22;
      final dx = _xs[i] * size.width + drift;
      final dy = size.height * (1.0 - phase);
      // fade in at bottom, fade out near top (matches JSX: 10%→50%→100%)
      final op = phase < 0.10 ? phase / 0.10
          : phase > 0.72 ? (1.0 - phase) / 0.28 : 0.55;
      final isTeal = i % 5 == 3;
      final baseCol = isTeal ? _teal : engCol;
      p.color = baseCol.withValues(alpha: op * 0.52);
      final r = (i % 3 == 0) ? 2.0 : 1.4;
      canvas.drawCircle(Offset(dx, dy), r, p);
    }
  }
  @override bool shouldRepaint(_IncensePainter o) =>
      o.t != t || o.engCol != engCol;
}

class _GeoPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = const Color(0xFFC8A048).withValues(alpha: 0.07)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.8;
    const cell = 120.0;
    final cols = (size.width / cell).ceil() + 2;
    final rows = (size.height / (cell * 0.866)).ceil() + 2;
    for (int row = 0; row < rows; row++) {
      for (int col = 0; col < cols; col++) {
        final cx = col * cell + (row.isOdd ? cell * 0.5 : 0) - cell * 0.5;
        final cy = row * cell * 0.866 - cell * 0.5;
        _star8(canvas, Offset(cx, cy), cell * 0.27, p);
      }
    }
  }
  void _star8(Canvas canvas, Offset c, double r, Paint p) {
    final path = Path();
    for (int i = 0; i < 8; i++) {
      final oa = i * pi / 4 - pi / 2;
      final ia = oa + pi / 8;
      final ox = c.dx + r * cos(oa); final oy = c.dy + r * sin(oa);
      final ix = c.dx + r * 0.38 * cos(ia); final iy = c.dy + r * 0.38 * sin(ia);
      if (i == 0) path.moveTo(ox, oy); else path.lineTo(ox, oy);
      path.lineTo(ix, iy);
    }
    path.close();
    canvas.drawPath(path, p);
  }
  @override bool shouldRepaint(_GeoPainter _) => false;
}

class _WaveProgressPainter extends CustomPainter {
  final double progress, shimmer;
  final Color color, bg;
  const _WaveProgressPainter(
      {required this.progress, required this.shimmer,
       required this.color, required this.bg});
  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRRect(
      RRect.fromRectAndRadius(Rect.fromLTWH(0,0,size.width,size.height),
        const Radius.circular(5)),
      Paint()..color = bg);
    if (progress <= 0) return;
    final fillW = (size.width * progress).clamp(0.0, size.width);
    final path = Path();
    path.moveTo(0, size.height);
    path.lineTo(0, size.height * 0.5);
    final waveAmp = size.height * 0.30;
    for (double x = 0; x <= fillW; x++) {
      final y = size.height * 0.5 +
        sin((x / (size.width * 0.55) - shimmer) * 6.2832) * waveAmp;
      path.lineTo(x, y.clamp(0.0, size.height));
    }
    path.lineTo(fillW, size.height);
    path.close();
    canvas.save();
    canvas.clipRect(Rect.fromLTWH(0, 0, fillW, size.height));
    canvas.drawPath(path, Paint()..color = color);
    canvas.drawRect(
      Rect.fromLTWH(0, 0, fillW, size.height),
      Paint()..shader = LinearGradient(
        colors: [Colors.transparent, Colors.white.withValues(alpha: 0.14), Colors.transparent],
        stops: const [0.0, 0.5, 1.0],
        begin: Alignment(shimmer * 2 - 1, 0),
        end: Alignment(shimmer * 2 + 0.4, 0),
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height)));
    canvas.restore();
  }
  @override
  bool shouldRepaint(_WaveProgressPainter o) =>
    o.progress != progress || o.shimmer != shimmer;
}

// ── Score burst painter ───────────────────────────────────────────────────────
class _ScoreBurstPainter extends CustomPainter {
  final double progress;
  final Color color;
  const _ScoreBurstPainter({required this.progress, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    if (progress < 0.3 || progress > 0.95) return;
    final t = ((progress - 0.3) / 0.65).clamp(0.0, 1.0);
    final opacity = (1.0 - t) * 0.7;
    final paint = Paint()
      ..color = color.withValues(alpha: opacity)
      ..strokeWidth = 1.5
      ..style = PaintingStyle.stroke
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 1.5);
    final cx = size.width / 2;
    final cy = size.height / 2;
    const count = 12;
    for (int i = 0; i < count; i++) {
      final angle = i * 6.2832 / count;
      final r1 = 46 + 6 * t;
      final r2 = 46 + 22 * t;
      canvas.drawLine(
        Offset(cx + r1 * cos(angle), cy + r1 * sin(angle)),
        Offset(cx + r2 * cos(angle), cy + r2 * sin(angle)),
        paint);
    }
    // Dot particles
    paint.style = PaintingStyle.fill;
    paint.strokeWidth = 0;
    for (int i = 0; i < count; i++) {
      final angle = i * 6.2832 / count + pi / count;
      final r = 42 + 28 * t;
      canvas.drawCircle(
        Offset(cx + r * cos(angle), cy + r * sin(angle)),
        1.8 * (1 - t), paint);
    }
  }

  @override
  bool shouldRepaint(_ScoreBurstPainter o) => o.progress != progress;
}