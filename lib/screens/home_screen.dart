import 'dart:io';
import 'dart:async';
import 'dart:math' show pi; // S30-R1
import 'package:flutter/material.dart';
import '../main.dart' show ThemeProvider; // S31-F2c
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import '../state/lang_provider.dart';
import '../services/api_service.dart';
import 'history_screen.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with TickerProviderStateMixin {
  // ── State ──────────────────────────────────────────────────────────────────
  File?   _file;
  String  _engine    = 'v10.0';
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

  // S19: Wake server state
  bool _waking       = false;
  int  _wakeAttempts = 0;

  late final AnimationController _glowCtrl;
  late final AnimationController _resultCtrl; // S29: result card entrance

  // ── Engines (S21: full data from documentation) ─────────────────────────────
  // S25: synced with server ENGINE_SCRIPTS (v8.1 default, v7.5/v7.6 removed)
  static const _engines = [
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
    _glowCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 2))
      ..repeat(reverse: true);
    _resultCtrl = AnimationController(
        vsync: this, duration: const Duration(milliseconds: 600));
    _checkServer();
    _serverTimer = Timer.periodic(
        const Duration(seconds: 6), (_) => _checkServer());
    // S30-F1: restored — one loadLastEngine call
    ApiService.loadLastEngine().then((e) {
      if (mounted) setState(() => _engine = e);
    });
  }

  @override
  void dispose() {
    _serverTimer?.cancel();
    _pollTimer?.cancel();
    _wakeTimer?.cancel();
    _resultCtrl.dispose();
    _glowCtrl.dispose();
    super.dispose();
  }

  // ── Server check ───────────────────────────────────────────────────────────
  Future<void> _checkServer() async {
    final ms = await ApiService.checkServer();
    if (mounted) setState(() { _serverUp = ms != null; _latencyMs = ms; });
  }

  // S19: Wake server — polls every 5s for up to 35s
  void _wakeServer() {
    if (_waking) return;
    _wakeTimer?.cancel();
    _wakeAttempts = 0;
    setState(() { _waking = true; _serverUp = false; });

    _wakeTimer = Timer.periodic(const Duration(seconds: 5), (_) async {
      _wakeAttempts++;
      final ms = await ApiService.checkServer();
      final up = ms != null;
      if (!mounted) {
        _wakeTimer?.cancel();
        return;
      }
      if (up || _wakeAttempts >= 7) { // max 35s
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
  }

  // ── File picker ────────────────────────────────────────────────────────────
  Future<void> _pickFile() async {
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
  Future<void> _process() async {
    if (_file == null || !_serverUp) return;
    HapticFeedback.mediumImpact();
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
          setState(() {
            _busy = false;
            _isMerging = false;  // S20-B: clear merge animation on server error
            _status = 'فشل: ${st['error']}';
          });
          return;
        }

        if (status == 'done') {
          _pollTimer?.cancel();
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
              textColor: const Color(0xFFD4AF37),
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
              textColor: const Color(0xFFD4AF37),
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

    setState(() {
      _busy = false; _progress = 1.0;
      _output = file; _result = sd;
      _status = file != null ? s.done : 'فشل: $error';
    });

    if (file != null) _resultCtrl.forward(from: 0); // S29: animate in

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

  // ── Manual re-download button ──────────────────────────────────────────────
  Future<void> _reDownload() async {
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
  Color _cBg(BuildContext ctx)      => _isDark(ctx) ? const Color(0xFF080A0E) : const Color(0xFFFAF7EE);
  Color _cCard(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF161B22) : const Color(0xFFF3EED9);
  Color _cBorder(BuildContext ctx)  => _isDark(ctx) ? const Color(0xFF21262D) : const Color(0xFFD4C99A);
  Color _cText(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFFC9D1D9) : const Color(0xFF1A1400);
  Color _cSub(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);
  Color _cDim(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF484F58) : const Color(0xFF8B7B5A);
  Color _cGold(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);

  // ── BUILD ──────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    final dark = _isDark(context);
    final cBg     = _cBg(context);
    final cCard   = _cCard(context);
    final cBorder = _cBorder(context);
    final cText   = _cText(context);
    final cSub    = _cSub(context);
    final cDim    = _cDim(context);
    final cGold   = _cGold(context);
    return Scaffold(
      backgroundColor: cBg,
      body: Container(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: dark
              ? [const Color(0xFF080A0E), const Color(0xFF0C1018)]
              : [const Color(0xFFFAF7EE), const Color(0xFFF5F0E0)])),
        child: SafeArea(
          child: CustomScrollView(slivers: [
            SliverToBoxAdapter(child: _header(s)),
            SliverToBoxAdapter(child: _serverBanner(s)),
            SliverToBoxAdapter(child: _engineSelector(s)),
            SliverToBoxAdapter(child: _fileCard(s)),
            if (_busy || _progress > 0)
              SliverToBoxAdapter(child: _progressCard(s)),
            if (_result != null)
              SliverToBoxAdapter(
                child: FadeTransition(
                  opacity: CurvedAnimation(
                    parent: _resultCtrl, curve: Curves.easeOut),
                  child: SlideTransition(
                    position: Tween<Offset>(
                      begin: const Offset(0, 0.1),
                      end: Offset.zero,
                    ).animate(CurvedAnimation(
                      parent: _resultCtrl, curve: Curves.easeOutCubic)),
                    child: _resultCard(s),
                  ),
                ),
              ),
            SliverToBoxAdapter(child: _bottomRow(s)),
            SliverToBoxAdapter(child: _donationCard(s)),
            const SliverToBoxAdapter(child: SizedBox(height: 40)),
          ]),
        ),
      ),
    );
  }

  // ── HEADER ─────────────────────────────────────────────────────────────────
  Widget _header(S s) => Padding(
    padding: const EdgeInsets.fromLTRB(16, 24, 16, 8),
    child: Row(children: [
      Container(
        width: 52, height: 52,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          boxShadow: [BoxShadow(
            color: const Color(0xFFD4AF37).withOpacity(0.25),
            blurRadius: 16)]),
        child: ClipOval(child: Image.asset('assets/images/logo.png',
          fit: BoxFit.cover,
          errorBuilder: (_,__,___) => Container(
            color: const Color(0xFF1A1500),
            child: const Icon(Icons.music_note,
              color: Color(0xFFD4AF37), size: 28))))),
      const SizedBox(width: 12),
      Expanded(child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: [
        AnimatedBuilder(animation: _glowCtrl,
          builder: (_, __) => Text(s.appName,
            style: TextStyle(
              fontSize: 24, fontWeight: FontWeight.bold,
              color: Color.lerp(
                const Color(0xFFD4AF37),
                const Color(0xFFFFF4B0),
                _glowCtrl.value)))),
        Text(s.subtitle,
          style: const TextStyle(
            color: Color(0xFF8B949E), fontSize: 10, letterSpacing: 1.5)),
      ])),
      Row(children: [
        _iconBtn(Icons.info_outline_rounded, () => _showInfoSheet(context)),
        const SizedBox(width: 6),
        _iconBtn(Icons.settings_outlined, () => Navigator.push(context,
          PageRouteBuilder(
            pageBuilder: (_, __, ___) => const SettingsScreen(),
            transitionsBuilder: (_, anim, __, child) =>
              FadeTransition(opacity: anim, child: child),
            transitionDuration: const Duration(milliseconds: 220),
          ))),
      ]),
    ]),
  );

  Widget _iconBtn(IconData icon, VoidCallback onTap) => Material(
    color: const Color(0xFF161B22),
    shape: const CircleBorder(
      side: BorderSide(color: Color(0xFF21262D))),
    clipBehavior: Clip.antiAlias,
    child: InkWell(
      onTap: onTap,
      splashColor: const Color(0xFFD4AF37).withOpacity(0.18),
      highlightColor: const Color(0xFFD4AF37).withOpacity(0.08),
      child: Padding(
        padding: const EdgeInsets.all(9),
        child: Icon(icon, color: const Color(0xFF8B949E), size: 20))));

  // ── SERVER BANNER (S19: wake button + hint) ────────────────────────────────
  Widget _serverBanner(S s) {
    final isOffline = !_serverUp;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 400),
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: _serverUp
          ? const Color(0xFF0D2015)
          : _waking
            ? const Color(0xFF1A1500)
            : const Color(0xFF200D0D),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: _serverUp
            ? const Color(0xFF3FB950)
            : _waking
              ? const Color(0xFFD4AF37)
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
              AnimatedContainer(
                duration: const Duration(milliseconds: 400),
                width: 8, height: 8,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _serverUp
                    ? const Color(0xFF3FB950)
                    : const Color(0xFFF85149))),
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
                      ? const Color(0xFFD4AF37)
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
                      color: const Color(0xFFD4AF37).withOpacity(0.6))),
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
    margin: const EdgeInsets.fromLTRB(16,10,16,4),
    decoration: BoxDecoration(
      color: const Color(0xFF161B22),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: const Color(0xFF21262D)),
      boxShadow: const [BoxShadow(
        color: Color(0x26000000),
        blurRadius: 12, offset: Offset(0, 3))]),
    child: Column(children: [
      // ── Header row ──────────────────────────────────────────────────
      Padding(
        padding: const EdgeInsets.fromLTRB(16,14,16,10),
        child: Row(children: [
          const Icon(Icons.tune_rounded, color: Color(0xFF484F58), size: 13),
          const SizedBox(width: 7),
          Text(s.chooseEngine, style: const TextStyle(
            color: Color(0xFF8B949E), fontSize: 11, letterSpacing: 1.5)),
          const Spacer(),
          // Score pill for selected engine
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              color: _badgeBg(_selectedEngine.bc),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: _badgeColor(_selectedEngine.bc).withOpacity(0.5))),
            child: Text(
              '≥${_selectedEngine.score.toInt()}',
              style: TextStyle(
                color: _badgeColor(_selectedEngine.bc),
                fontSize: 10, fontWeight: FontWeight.bold))),
        ])),
      ..._engines.map((e) => _engineCard(e, s)),
      const SizedBox(height: 10),
    ]),
  );

  _EngineData get _selectedEngine =>
      _engines.firstWhere((e) => e.id == _engine, orElse: () => _engines.first);

  Widget _engineCard(_EngineData e, S s) {
    final sel = _engine == e.id;
    final col = _badgeColor(e.bc);
    final bg  = _badgeBg(e.bc);
    return GestureDetector(
      onTap: () {
        HapticFeedback.selectionClick(); // S30-P1
        setState(() => _engine = e.id);
        ApiService.saveLastEngine(e.id); // S28-T2: persist
      },
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 220),
        margin: const EdgeInsets.fromLTRB(8,3,8,3),
        decoration: BoxDecoration(
          color: sel ? const Color(0xFF0D1117) : Colors.transparent,
          borderRadius: BorderRadius.circular(11),
          border: Border.all(
            color: sel ? col : const Color(0xFF21262D),
            width: sel ? 1.4 : 0.8)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          // ── Collapsed header (always visible) ───────────────────────
          Padding(
            padding: const EdgeInsets.fromLTRB(12,11,12,11),
            child: Row(children: [
              AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                width: 18, height: 18,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: sel ? col : const Color(0xFF30363D), width: 2),
                  color: sel ? col : Colors.transparent),
                child: sel
                  ? const Icon(Icons.check, size: 10, color: Color(0xFF0A0C10))
                  : null),
              const SizedBox(width: 11),
              Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                Row(children: [
                  Text(e.id, style: TextStyle(
                    // S31-F2b
                    color: sel ? col : const Color(0xFFC9D1D9), // S31-F4
                    fontWeight: FontWeight.bold, fontSize: 13)),
                  if (e.badge.isNotEmpty) ...[
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                      decoration: BoxDecoration(
                        color: bg, borderRadius: BorderRadius.circular(4),
                        border: Border.all(color: col.withOpacity(0.45))),
                      child: Text(e.badge, style: TextStyle(
                        color: col, fontSize: 8, fontWeight: FontWeight.bold))),
                  ],
                ]),
                const SizedBox(height: 2),
                Text(s.ar ? e.nameAr : e.nameEn,
                  style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),
              ])),
              Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
                Text('≥${e.score.toInt()}', style: TextStyle(
                  // S31-F2: gold engines → muted gold when unselected
                  color: sel ? col : const Color(0xFF484F58), // S31-F4
                  fontWeight: FontWeight.w800, fontSize: 15)),
                Text('/100', style: TextStyle(
                  color: sel ? col.withOpacity(0.45) : const Color(0xFF484F58),
                  fontSize: 8)),
              ]),
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
        ]),
      ),
    );
  }

  Widget _engineExpanded(_EngineData e, S s, Color col) => Padding(
    padding: const EdgeInsets.fromLTRB(12,0,12,12),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Container(height: 1, color: const Color(0xFF21262D),
        margin: const EdgeInsets.only(bottom: 10)),
      // Score bar
      Row(children: [
        Expanded(child: ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: e.score / 100,
            minHeight: 5,
            backgroundColor: const Color(0xFF21262D),
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
            color: const Color(0xFF0A0C10),
            borderRadius: BorderRadius.circular(6),
            border: Border.all(color: const Color(0xFF30363D))),
          child: Text(f, style: const TextStyle(
            color: Color(0xFF8B949E), fontSize: 9)))).toList()),
      const SizedBox(height: 10),
      // What's New box
      Container(
        width: double.infinity,
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: const Color(0xFF0A0C10),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: col.withOpacity(0.2))),
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

  Color _badgeColor(String bc) => bc == 'gold' ? const Color(0xFFD4AF37)
      : bc == 'green' ? const Color(0xFF3FB950)
      : bc == 'blue'  ? const Color(0xFF58A6FF)
      : const Color(0xFF484F58);

  Color _badgeBg(String bc) => bc == 'gold' ? const Color(0xFF1A1200)
      : bc == 'green' ? const Color(0xFF0D2015)
      : bc == 'blue'  ? const Color(0xFF0D1B2E)
      : const Color(0xFF1C1C1C);

  // ── FILE CARD ──────────────────────────────────────────────────────────────
  Widget _fileCard(S s) => GestureDetector(
    onTap: _busy ? null : _pickFile,
    child: Container(
      margin: const EdgeInsets.fromLTRB(16,10,16,4),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: _file != null ? const Color(0xFFD4AF37) : const Color(0xFF30363D),
          width: 1.5),
        boxShadow: const [BoxShadow(
          color: Color(0x26000000),
          blurRadius: 12, offset: Offset(0, 3))]),
      child: Column(children: [
        AnimatedSwitcher( // S30-P3
          duration: const Duration(milliseconds: 350),
          switchInCurve: Curves.easeOutBack,
          transitionBuilder: (child, anim) => ScaleTransition(
            scale: anim, child: FadeTransition(opacity: anim, child: child)),
          child: Icon(
            _file != null ? Icons.audio_file : Icons.add_circle_outline,
            key: ValueKey(_file != null),
            color: const Color(0xFFD4AF37), size: 52)),
        const SizedBox(height: 12),
        Text(_file != null ? _file!.path.split('/').last : s.pickFile,
          textDirection: TextDirection.rtl,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: _file != null ? const Color(0xFFC9D1D9) : const Color(0xFF8B949E),
            fontSize: _file != null ? 13 : 16,
            fontWeight: _file != null ? FontWeight.normal : FontWeight.bold)),
        if (_file != null) ...[
          const SizedBox(height: 4),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            Text(_sizeLabel,
              style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
            if (_isLarge) ...[
              const SizedBox(width: 8),
              _badge(s.chunkedBadge, 'gold'),
            ],
          ]),
          // S28: Estimated processing time
          if (_fileBytes > 0) ...[
            const SizedBox(height: 4),
            Row(mainAxisAlignment: MainAxisAlignment.center, children: [
              const Icon(Icons.timer_outlined, size: 11,
                color: Color(0xFF484F58)),
              const SizedBox(width: 4),
              Text('${s.estTime}: ${_estimatedTime()}',
                style: const TextStyle(
                  color: Color(0xFF484F58), fontSize: 10)),
            ]),
          ],
        ],
        const SizedBox(height: 4),
        Text(s.sizeLimit,
          style: const TextStyle(color: Color(0xFF484F58), fontSize: 11)),
        if (_file != null) ...[
          const SizedBox(height: 18),
          SizedBox(width: double.infinity,
            child: ElevatedButton(
              onPressed: (_busy || !_serverUp) ? null : _process,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFD4AF37),
                foregroundColor: const Color(0xFF0A0C10),
                padding: const EdgeInsets.symmetric(vertical: 15),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10)),
                disabledBackgroundColor:
                  const Color(0xFFD4AF37).withOpacity(0.3)),
              child: _busy
                ? Row(mainAxisSize: MainAxisSize.min, children: [
                    const SizedBox(width: 16, height: 16,
                      child: CircularProgressIndicator(
                        strokeWidth: 2,
                        color: Color(0xFF0A0C10))),
                    const SizedBox(width: 10),
                    Text(s.processing,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold, fontSize: 15)),
                  ])
                : Text('${s.process} — $_engine',
                    style: const TextStyle(
                      fontWeight: FontWeight.bold, fontSize: 15)))),
        ],
      ]),
    ),
  );

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
            color: Color(0xFF0D1117),
            borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
          child: Column(children: [
            Container(
              margin: const EdgeInsets.only(top: 12, bottom: 8),
              width: 36, height: 4,
              decoration: BoxDecoration(
                color: const Color(0xFF30363D),
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
                        color: const Color(0xFFFF0000).withOpacity(0.3))),
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
                _infoSectionLabel(s.ar ? '🎯 المرجع الصوتي' : '🎯 Reference Standard'),
                Container(
                  margin: const EdgeInsets.only(bottom: 16),
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFF0A1A0F),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(
                      color: const Color(0xFF3FB950).withOpacity(0.3))),
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
                  decoration: BoxDecoration(
                    color: const Color(0xFF161B22),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFF21262D))),
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
                          ClipRRect(
                            borderRadius: BorderRadius.circular(3),
                            child: LinearProgressIndicator(
                              value: e.score / 100,
                              minHeight: 4,
                              backgroundColor: const Color(0xFF21262D),
                              valueColor: AlwaysStoppedAnimation<Color>(col))),
                        ]));
                    }).toList())),
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    color: const Color(0xFF161B22),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: const Color(0xFF21262D))),
                  child: Row(children: [
                    ClipOval(child: Image.asset('assets/images/logo.png',
                      width: 44, height: 44, fit: BoxFit.cover,
                      errorBuilder: (_,__,___) => Container(
                        width: 44, height: 44,
                        color: const Color(0xFF1A1500),
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
      border: Border.all(color: _badgeColor(bc).withOpacity(0.5))),
    child: Text(text,
      style: TextStyle(
        color: _badgeColor(bc), fontSize: 9, fontWeight: FontWeight.bold)));

  // ── PROGRESS ───────────────────────────────────────────────────────────────
  Widget _progressCard(S s) => Container(
    margin: const EdgeInsets.fromLTRB(16,10,16,4),
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: const Color(0xFF161B22),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: const Color(0xFF21262D)),
      boxShadow: const [BoxShadow(
        color: Color(0x26000000),
        blurRadius: 12, offset: Offset(0, 3))]),
    child: Column(children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Flexible(child: AnimatedSwitcher( // S30-P2
          duration: const Duration(milliseconds: 300),
          transitionBuilder: (child, anim) => FadeTransition(
            opacity: anim, child: child),
          child: Text(
            _status.isEmpty ? s.processing : _status,
            key: ValueKey(_status),
            style: const TextStyle(
              color: Color(0xFFC9D1D9), fontSize: 13)))),
        // S20-A: '...' when merging — frozen '68%' looks like a crash
        Text(_isMerging ? '...' : '${(_progress * 100).toInt()}%',
          style: const TextStyle(
            color: Color(0xFFD4AF37),
            fontWeight: FontWeight.bold, fontSize: 14)),
      ]),
      const SizedBox(height: 12),
      ClipRRect(
        borderRadius: BorderRadius.circular(8),
        // S20-A: null = indeterminate (animated pulse) during server merge
        child: LinearProgressIndicator(
          value: _isMerging ? null : _progress, minHeight: 8,
          backgroundColor: const Color(0xFF21262D),
          valueColor: const AlwaysStoppedAnimation(Color(0xFFD4AF37)))),
      // S28: Cancel button
      const SizedBox(height: 10),
      TextButton.icon(
        onPressed: _cancelProcessing,
        style: TextButton.styleFrom(
          padding: const EdgeInsets.symmetric(vertical: 4)),
        icon: const Icon(Icons.cancel_outlined, size: 16,
          color: Color(0xFF8B949E)),
        label: Text(s.cancelBtn,
          style: const TextStyle(color: Color(0xFF8B949E), fontSize: 12)),
      ),
    ]),
  );

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
        : score >= 80 ? const Color(0xFFD4AF37)
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
        color: score < 80 ? const Color(0xFF1A0A00) : const Color(0xFF0D2015),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: score < 80 ? const Color(0xFFF85149) : const Color(0xFF3FB950),
          width: 1.2),
        boxShadow: [BoxShadow(
          color: (score < 80
              ? const Color(0xFFF85149)
              : const Color(0xFF3FB950)).withOpacity(0.12),
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
              SizedBox(
                width: 148, height: 148,
                child: CustomPaint(
                  painter: _ScoreArcPainter(
                    progress: t, score: score, color: scoreColor),
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
                        color: scoreColor.withOpacity(0.55),
                        fontSize: 12,
                        fontWeight: FontWeight.bold)),
                    ])),
                )),
              const SizedBox(height: 10),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 5),
                decoration: BoxDecoration(
                  color: scoreColor.withOpacity(0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: scoreColor.withOpacity(0.4))),
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
              color: const Color(0xFFD4AF37).withOpacity(0.3))),
          child: Text('$_engine — $engineName',
            style: const TextStyle(
              color: Color(0xFFD4AF37), fontSize: 11))),
        const SizedBox(height: 12),

        // S30-R2: metrics 2×2 grid
        _metricGrid(),
        const SizedBox(height: 12),

        // S30-R4: section divider
        Container(height: 1,
          color: const Color(0xFF21262D),
          margin: const EdgeInsets.only(bottom: 14)),

        // S19 FALLBACK WARNING: shown when score ≤ 78
        if (score <= 78) ...[
          Container(
            padding: const EdgeInsets.all(12),
            margin: const EdgeInsets.only(bottom: 12),
            decoration: BoxDecoration(
              color: const Color(0xFF200D0D),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(
                color: const Color(0xFFF85149).withOpacity(0.4))),
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
                    color: Colors.black.withOpacity(0.6))),
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
                  foregroundColor: const Color(0xFF8B949E),
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
        color: const Color(0xFF0D1117),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFF21262D))),
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
    Color tileColor = const Color(0xFF484F58);
    if (num != null && value != '—') {
      final diff = num - target;
      delta = '${diff >= 0 ? "+" : ""}${diff.toStringAsFixed(2)}';
      if (diff.abs() <= 0.5) {
        arrow = '✓'; tileColor = const Color(0xFF3FB950);
      } else if (diff > 0) {
        arrow = '▲'; tileColor = const Color(0xFFD4AF37);
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
      color: const Color(0xFF161B22),
      borderRadius: BorderRadius.circular(12),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () => Navigator.push(context,
          PageRouteBuilder(
            pageBuilder: (_, __, ___) => const HistoryScreen(),
            transitionsBuilder: (_, anim, __, child) =>
              FadeTransition(opacity: anim, child: child),
            transitionDuration: const Duration(milliseconds: 220),
          )),
        splashColor: const Color(0xFFD4AF37).withOpacity(0.12),
        highlightColor: const Color(0xFFD4AF37).withOpacity(0.06),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 14),
          decoration: BoxDecoration(
            border: Border.all(color: const Color(0xFF21262D))),
          child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            const Icon(Icons.history_rounded,
              color: Color(0xFF8B949E), size: 18),
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
        splashColor: const Color(0xFFD4AF37).withOpacity(0.18),
        child: Container(
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: const Color(0xFFD4AF37).withOpacity(0.3))),
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
  const _ScoreArcPainter({
    required this.progress,
    required this.score,
    required this.color,
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
        ..color = const Color(0xFF21262D)
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
      o.progress != progress || o.color != color;
}

// ── Engine data class (S21: rich model — score, features, what's-new) ───────────
class _EngineData {
  final String id, nameAr, nameEn, badge, bc;
  final double score;
  final List<String> features;
  final String whatsNewAr, whatsNewEn;
  const _EngineData(this.id, this.nameAr, this.nameEn, this.score,
      this.badge, this.bc, this.features, this.whatsNewAr, this.whatsNewEn);
}
