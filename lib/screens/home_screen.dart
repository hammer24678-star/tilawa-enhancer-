import 'dart:io';
import 'dart:async';
import 'package:flutter/material.dart';
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
  String  _engine    = 'v8.0';
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

  // S19: Wake server state
  bool _waking       = false;
  int  _wakeAttempts = 0;

  late final AnimationController _glowCtrl;

  // ── Engines ────────────────────────────────────────────────────────────────
  static const _engines = [
    _Engine('v8.0', 'v8.0 — Calibrated Precision',
        '5 أخطاء مُصلَحة · ≥96/100 | 5 bugs fixed · ≥96/100',
        'NEW', 'gold'),
    _Engine('v7.6', 'v7.6 — Intelligent Assessment',
        'MDS تشخيص ذكي | Smart multi-metric diagnosis · ~94/100',
        'MDS', 'blue'),
    _Engine('v7.5', 'v7.5 — Disciplined Precision',
        'Do-No-Harm · 94/100',
        'BEST', 'green'),
    _Engine('v7.0', 'v7.0 — Classic',
        'البنية الأصلية | Original architecture · 91/100',
        'STABLE', ''),
  ];

  @override
  void initState() {
    super.initState();
    _glowCtrl = AnimationController(
        vsync: this, duration: const Duration(seconds: 2))
      ..repeat(reverse: true);
    _checkServer();
    _serverTimer = Timer.periodic(
        const Duration(seconds: 6), (_) => _checkServer());
  }

  @override
  void dispose() {
    _serverTimer?.cancel();
    _pollTimer?.cancel();
    _wakeTimer?.cancel();
    _glowCtrl.dispose();
    super.dispose();
  }

  // ── Server check ───────────────────────────────────────────────────────────
  Future<void> _checkServer() async {
    final up = await ApiService.isServerRunning();
    if (mounted) setState(() => _serverUp = up);
  }

  // S19: Wake server — polls every 5s for up to 35s
  void _wakeServer() {
    if (_waking) return;
    _wakeTimer?.cancel();
    _wakeAttempts = 0;
    setState(() { _waking = true; _serverUp = false; });

    _wakeTimer = Timer.periodic(const Duration(seconds: 5), (_) async {
      _wakeAttempts++;
      final up = await ApiService.isServerRunning();
      if (!mounted) {
        _wakeTimer?.cancel();
        return;
      }
      if (up || _wakeAttempts >= 7) { // max 35s
        _wakeTimer?.cancel();
        setState(() { _serverUp = up; _waking = false; _wakeAttempts = 0; });
      }
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
      });
    }
  }

  // ── Process ────────────────────────────────────────────────────────────────
  Future<void> _process() async {
    if (_file == null || !_serverUp) return;
    setState(() {
      _busy = true; _progress = 0.02;
      _status = LangProvider.strings(context).uploading;
      _output = null; _result = null;
    });
    try {
      final resp = await ApiService.uploadFile(_file!, _engine,
          onProgress: (p, label) {
        if (mounted) setState(() { _progress = p; _status = label; });
      });
      _jobId = resp['job_id'];
      _startPolling();
    } catch (e) {
      setState(() { _busy = false; _status = 'خطأ: $e'; });
    }
  }

  // ── Polling — RC2 + RC3 fixes ──────────────────────────────────────────────
  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      if (_jobId == null) return;
      try {
        final st = await ApiService.getStatus(_jobId!);
        if (!mounted) return;

        final srv = (st['progress'] ?? 0) / 100.0;
        final status = st['status'] as String? ?? '';
        final display = (status == 'uploading' || status == 'merging')
            ? _progress
            : (0.68 + srv * 0.32).clamp(0.0, 1.0);
        setState(() { _progress = display; _status = st['label'] ?? ''; });

        if (status == 'error') {
          _pollTimer?.cancel();
          setState(() { _busy = false; _status = 'فشل: ${st['error']}'; });
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
      } catch (_) {} // only poll errors silently ignored
    });
  }

  // ── Auto download after processing ────────────────────────────────────────
  Future<void> _downloadAndSave(Map<String, dynamic> sd) async {
    final s = LangProvider.strings(context);
    setState(() { _status = s.downloading; _progress = 0.95; });

    final filename = ApiService.buildFilename(_engine);
    final (file, error) = await ApiService.downloadFile(_jobId!, filename);

    if (!mounted) return;

    final score = double.tryParse(sd['score']?.toString() ?? '0') ?? 0.0;

    setState(() {
      _busy = false; _progress = 1.0;
      _output = file; _result = sd;
      _status = file != null ? s.done : 'فشل: $error';
    });

    // S19: Save job record locally for persistent re-download
    if (file != null && _jobId != null) {
      await ApiService.saveJobRecord(
        jobId: _jobId!,
        engine: _engine,
        score: score,
        filename: filename,
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

    final filename = ApiService.buildFilename(_engine);
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

  // ── BUILD ──────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    return Scaffold(
      body: SafeArea(
        child: CustomScrollView(slivers: [
          SliverToBoxAdapter(child: _header(s)),
          SliverToBoxAdapter(child: _serverBanner(s)),
          SliverToBoxAdapter(child: _engineSelector(s)),
          SliverToBoxAdapter(child: _fileCard(s)),
          if (_busy || _progress > 0)
            SliverToBoxAdapter(child: _progressCard(s)),
          if (_result != null)
            SliverToBoxAdapter(child: _resultCard(s)),
          SliverToBoxAdapter(child: _bottomRow(s)),
          SliverToBoxAdapter(child: _donationCard(s)),
          const SliverToBoxAdapter(child: SizedBox(height: 40)),
        ]),
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
      _iconBtn(Icons.settings_outlined, () => Navigator.push(
        context, MaterialPageRoute(builder: (_) => const SettingsScreen()))),
    ]),
  );

  Widget _iconBtn(IconData icon, VoidCallback onTap) => GestureDetector(
    onTap: onTap,
    child: Container(
      padding: const EdgeInsets.all(9),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22), shape: BoxShape.circle,
        border: Border.all(color: const Color(0xFF21262D))),
      child: Icon(icon, color: const Color(0xFF8B949E), size: 20)));

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
                  : (_serverUp ? s.serverOnline : s.serverOffline),
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
      border: Border.all(color: const Color(0xFF21262D))),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16,14,16,6),
        child: Text(s.chooseEngine,
          style: const TextStyle(
            color: Color(0xFF8B949E), fontSize: 11, letterSpacing: 1.5))),
      ..._engines.map((e) => _engineTile(e)),
      const SizedBox(height: 8),
    ]),
  );

  Widget _engineTile(_Engine e) {
    final sel = _engine == e.id;
    final bc = _badgeColor(e.bc);
    final bg = _badgeBg(e.bc);
    return GestureDetector(
      onTap: () => setState(() => _engine = e.id),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        margin: const EdgeInsets.fromLTRB(8,2,8,2),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: sel ? const Color(0xFF1A1500) : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: sel ? const Color(0xFFD4AF37) : Colors.transparent,
            width: 1.2)),
        child: Row(children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            width: 20, height: 20,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: sel ? const Color(0xFFD4AF37) : const Color(0xFF30363D),
                width: 2),
              color: sel ? const Color(0xFFD4AF37) : Colors.transparent),
            child: sel
              ? const Icon(Icons.check, size: 12, color: Color(0xFF0A0C10))
              : null),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start,
            children: [
            Row(children: [
              Flexible(child: Text(e.label,
                style: TextStyle(
                  color: sel ? const Color(0xFFD4AF37) : const Color(0xFFC9D1D9),
                  fontWeight: FontWeight.bold, fontSize: 13))),
              if (e.badge.isNotEmpty) ...[
                const SizedBox(width: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                  decoration: BoxDecoration(
                    color: bg, borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: bc.withOpacity(0.4))),
                  child: Text(e.badge,
                    style: TextStyle(
                      color: bc, fontSize: 9, fontWeight: FontWeight.bold))),
              ],
            ]),
            const SizedBox(height: 3),
            Text(e.desc,
              style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),
          ])),
        ]),
      ),
    );
  }

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
          width: 1.5)),
      child: Column(children: [
        Icon(_file != null ? Icons.audio_file : Icons.add_circle_outline,
          color: const Color(0xFFD4AF37), size: 52),
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
              child: Text(
                _busy ? s.processing : '${s.process} — $_engine',
                style: const TextStyle(
                  fontWeight: FontWeight.bold, fontSize: 15)))),
        ],
      ]),
    ),
  );

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
      border: Border.all(color: const Color(0xFF21262D))),
    child: Column(children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Flexible(child: Text(_status.isEmpty ? s.processing : _status,
          style: const TextStyle(color: Color(0xFFC9D1D9), fontSize: 13))),
        Text('${(_progress * 100).toInt()}%',
          style: const TextStyle(
            color: Color(0xFFD4AF37),
            fontWeight: FontWeight.bold, fontSize: 14)),
      ]),
      const SizedBox(height: 12),
      ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: LinearProgressIndicator(
          value: _progress, minHeight: 8,
          backgroundColor: const Color(0xFF21262D),
          valueColor: const AlwaysStoppedAnimation(Color(0xFFD4AF37)))),
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
      'v8.0': 'Calibrated Precision',
      'v7.6': 'Intelligent Assessment',
      'v7.5': 'Disciplined Precision',
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
          width: 1.2)),
      child: Column(children: [
        // Score
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(label, style: TextStyle(
              color: scoreColor,
              fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(width: 10),
            Text('${score.toStringAsFixed(1)}/100',
              style: TextStyle(
                color: scoreColor,
                fontWeight: FontWeight.w900, fontSize: 34)),
          ]),
        const SizedBox(height: 12),

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

        // Metrics (with target deltas)
        _metricsRow(),
        const SizedBox(height: 6),

        // Target reference line
        Text(
          s.ar
            ? 'الهدف: LUFS=-6.29 · RMS=-10.01 · Crest=10.25 · LRA=4.19'
            : 'Target: LUFS=-6.29 · RMS=-10.01 · Crest=10.25 · LRA=4.19',
          style: const TextStyle(color: Color(0xFF484F58), fontSize: 9)),
        const SizedBox(height: 16),

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

        // S19: Open in player button (only when content:// URI available)
        if (hasContentUri) ...[
          const SizedBox(height: 8),
          SizedBox(width: double.infinity,
            child: OutlinedButton.icon(
              onPressed: _openInPlayer,
              style: OutlinedButton.styleFrom(
                foregroundColor: const Color(0xFF58A6FF),
                side: const BorderSide(color: Color(0xFF58A6FF), width: 0.8),
                padding: const EdgeInsets.symmetric(vertical: 10),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12))),
              icon: const Icon(Icons.play_circle_outline_rounded, size: 18),
              label: Text(s.openInPlayer,
                style: const TextStyle(fontSize: 13)),
            )),
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
      ]),
    );
  }

  Widget _metricsRow() => Row(
    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
    children: [
      if (_result?['lufs']  != null) _metric('LUFS',  _result!['lufs'].toString()),
      if (_result?['rms']   != null) _metric('RMS',   _result!['rms'].toString()),
      if (_result?['crest'] != null) _metric('Crest', _result!['crest'].toString()),
      if (_result?['lra']   != null) _metric('LRA',   _result!['lra'].toString()),
    ],
  );

  Widget _metric(String label, String value) => Column(children: [
    Text(label,
      style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),
    const SizedBox(height: 2),
    Text(value, style: const TextStyle(
      color: Color(0xFFD4AF37), fontWeight: FontWeight.bold, fontSize: 13)),
  ]);

  // ── BOTTOM ROW ─────────────────────────────────────────────────────────────
  Widget _bottomRow(S s) => Padding(
    padding: const EdgeInsets.fromLTRB(16,10,16,4),
    child: GestureDetector(
      onTap: () => Navigator.push(context,
        MaterialPageRoute(builder: (_) => const HistoryScreen())),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 14),
        decoration: BoxDecoration(
          color: const Color(0xFF161B22),
          borderRadius: BorderRadius.circular(12),
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
  );

  // ── DONATION CARD ──────────────────────────────────────────────────────────
  Widget _donationCard(S s) => Padding(
    padding: const EdgeInsets.fromLTRB(16,4,16,4),
    child: GestureDetector(
      onTap: () => launchUrl(
        Uri.parse('https://buymeacoffee.com/tilawa'),
        mode: LaunchMode.externalApplication),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: const Color(0xFF1A1500),
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
  );
}

// ── Engine data class ──────────────────────────────────────────────────────────
class _Engine {
  final String id, label, desc, badge, bc;
  const _Engine(this.id, this.label, this.desc, this.badge, this.bc);
}
