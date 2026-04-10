import 'dart:io';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:path_provider/path_provider.dart';
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
  String  _engine       = 'v8.0';
  String  _status       = '';
  double  _progress     = 0;
  bool    _busy         = false;
  bool    _serverUp     = false;
  String? _jobId;
  File?   _output;
  Map<String, dynamic>? _result;
  Timer?  _serverTimer;
  Timer?  _pollTimer;
  String  _sizeLabel    = '';
  bool    _isLarge      = false;

  late final AnimationController _glowCtrl;

  // ── Engines ────────────────────────────────────────────────────────────────
  static const _engines = [
    _Engine('v8.0', 'v8.0 — Calibrated Precision',
        '5 أخطاء مُصلَحة · ≥96/100 | 5 bugs fixed · ≥96/100',
        'NEW', 'gold'),
    _Engine('v7.6', 'v7.6 — Intelligent Assessment',
        'MDS تشخيص ذكي | Smart multi-metric diagnosis',
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
    _glowCtrl.dispose();
    super.dispose();
  }

  // ── Actions ────────────────────────────────────────────────────────────────
  Future<void> _checkServer() async {
    final up = await ApiService.isServerRunning();
    if (mounted) setState(() => _serverUp = up);
  }

  Future<void> _pickFile() async {
    final r = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['mp3','wav','m4a','flac','aac']);
    if (r?.files.single.path != null) {
      final f = File(r!.files.single.path!);
      final bytes = await f.length();
      setState(() {
        _file = f;
        _output = null; _result = null;
        _status = ''; _progress = 0;
        _sizeLabel = '${(bytes/1024/1024).toStringAsFixed(1)} MB';
        _isLarge = bytes > 8 * 1024 * 1024;
      });
    }
  }

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
        if (status == 'done') {
          _pollTimer?.cancel();
          await _downloadAndSave(st);
        } else if (status == 'error') {
          _pollTimer?.cancel();
          setState(() { _busy = false; _status = 'فشل: ${st['error']}'; });
        }
      } catch (_) {}
    });
  }

  /// Auto-download and save when processing finishes
  Future<void> _downloadAndSave(Map<String, dynamic> sd) async {
    final s = LangProvider.strings(context);
    setState(() { _status = s.downloading; _progress = 0.95; });
    try {
      final dir = await getDownloadsDirectory()
          ?? await getApplicationDocumentsDirectory();
      // Proper filename: Tilawa_v8.0_Calibrated_Precision_1425H.mp3
      final filename = ApiService.buildFilename(_engine);
      final path = '${dir.path}/$filename';
      final f = await ApiService.downloadFile(_jobId!, path);
      if (mounted) {
        setState(() {
          _busy = false; _progress = 1.0;
          _output = f; _result = sd;
          _status = f != null ? s.done : 'فشل التحميل';
        });
      }
    } catch (e) {
      if (mounted) setState(() { _busy = false; _status = 'خطأ: $e'; });
    }
  }

  /// Re-download button (in case first download failed)
  Future<void> _reDownload() async {
    if (_jobId == null) return;
    final s = LangProvider.strings(context);
    setState(() { _status = s.downloading; });
    try {
      final dir = await getDownloadsDirectory()
          ?? await getApplicationDocumentsDirectory();
      final filename = ApiService.buildFilename(_engine);
      final path = '${dir.path}/$filename';
      final f = await ApiService.downloadFile(_jobId!, path);
      if (mounted) {
        setState(() { _output = f; _status = f != null ? s.done : 'فشل التحميل'; });
        if (f != null) {
          ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text('${s.savedTo}: $filename'),
            backgroundColor: const Color(0xFF0D2015),
            duration: const Duration(seconds: 3)));
        }
      }
    } catch (e) {
      if (mounted) setState(() { _status = 'خطأ: $e'; });
    }
  }

  // ── BUILD ──────────────────────────────────────────────────────────────────
  @override
  Widget build(BuildContext context) {
    // Reading from InheritedWidget — auto-rebuilds when lang changes
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
      // Logo
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
      // Settings icon
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

  // ── SERVER BANNER ──────────────────────────────────────────────────────────
  Widget _serverBanner(S s) => AnimatedContainer(
    duration: const Duration(milliseconds: 400),
    margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
    decoration: BoxDecoration(
      color: _serverUp ? const Color(0xFF0D2015) : const Color(0xFF200D0D),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(
        color: _serverUp ? const Color(0xFF3FB950) : const Color(0xFFF85149),
        width: 0.8)),
    child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
      AnimatedContainer(
        duration: const Duration(milliseconds: 400),
        width: 8, height: 8,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: _serverUp ? const Color(0xFF3FB950) : const Color(0xFFF85149))),
      const SizedBox(width: 8),
      Text(_serverUp ? s.serverOnline : s.serverOffline,
        style: TextStyle(
          color: _serverUp ? const Color(0xFF3FB950) : const Color(0xFFF85149),
          fontSize: 12)),
    ]),
  );

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

  // ── RESULT + DOWNLOAD BUTTON ───────────────────────────────────────────────
  Widget _resultCard(S s) {
    final score = double.tryParse(_result?['score']?.toString() ?? '0') ?? 0.0;
    final label = score >= 96 ? s.excellent : score >= 92 ? s.great : s.good;
    final engineNames = {
      'v8.0': 'Calibrated Precision',
      'v7.6': 'Intelligent Assessment',
      'v7.5': 'Disciplined Precision',
      'v7.0': 'Classic',
    };
    final engineName = engineNames[_engine] ?? _engine;
    final filename   = ApiService.buildFilename(_engine);

    return Container(
      margin: const EdgeInsets.fromLTRB(16,10,16,4),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF0D2015),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF3FB950), width: 1.2)),
      child: Column(children: [
        // Score
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(label, style: const TextStyle(
              color: Color(0xFF3FB950),
              fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(width: 10),
            Text('${score.toStringAsFixed(1)}/100',
              style: const TextStyle(
                color: Color(0xFFD4AF37),
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

        // Metrics
        Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
          if (_result?['lufs']  != null) _metric('LUFS',  _result!['lufs'].toString()),
          if (_result?['rms']   != null) _metric('RMS',   _result!['rms'].toString()),
          if (_result?['crest'] != null) _metric('Crest', _result!['crest'].toString()),
          if (_result?['lra']   != null) _metric('LRA',   _result!['lra'].toString()),
        ]),
        const SizedBox(height: 18),

        // ── DOWNLOAD BUTTON ──────────────────────────────────────────────────
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

        // Show if already saved
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
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
        decoration: BoxDecoration(
          color: const Color(0xFF161B22),
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFF21262D))),
        child: Row(children: [
          const Icon(Icons.history_rounded,
            color: Color(0xFF8B949E), size: 20),
          const SizedBox(width: 10),
          Expanded(child: Text(s.history,
            style: const TextStyle(
              color: Color(0xFFC9D1D9), fontSize: 13))),
          const Icon(Icons.arrow_forward_ios_rounded,
            color: Color(0xFF8B949E), size: 13),
        ]))));

  // ── DONATION ───────────────────────────────────────────────────────────────
  Widget _donationCard(S s) => GestureDetector(
    onTap: () async {
      final uri = Uri.parse('https://ipay.instapay.eg/EG/AR/tilawa');
      if (await canLaunchUrl(uri)) await launchUrl(uri);
    },
    child: Container(
      margin: const EdgeInsets.fromLTRB(16,10,16,8),
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF1A1000), Color(0xFF2A1F00)],
          begin: Alignment.topLeft, end: Alignment.bottomRight),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFD4AF37), width: 0.8)),
      child: Row(children: [
        const Text('🤲', style: TextStyle(fontSize: 28)),
        const SizedBox(width: 14),
        Expanded(child: Column(
          crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(s.donation, style: const TextStyle(
            color: Color(0xFFD4AF37),
            fontWeight: FontWeight.bold, fontSize: 15)),
          const SizedBox(height: 3),
          Text(s.donationDesc, style: const TextStyle(
            color: Color(0xFF8B949E), fontSize: 11)),
        ])),
        const Icon(Icons.arrow_forward_ios_rounded,
          color: Color(0xFFD4AF37), size: 14),
      ]),
    ),
  );
}

// Data class for engines
class _Engine {
  final String id, label, desc, badge, bc;
  const _Engine(this.id, this.label, this.desc, this.badge, this.bc);
}
