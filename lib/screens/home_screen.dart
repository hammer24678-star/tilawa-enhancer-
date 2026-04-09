import 'dart:io';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:path_provider/path_provider.dart';
import '../services/api_service.dart';
import '../l10n/strings.dart';
import 'history_screen.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  final S s;
  final VoidCallback onLangToggle;
  const HomeScreen({super.key, required this.s, required this.onLangToggle});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  File? _selectedFile;
  String _selectedEngine = 'v8.0';
  String _status = '';
  double _progress = 0;
  bool _isProcessing = false;
  bool _isServerUp = false;
  String? _jobId;
  File? _outputFile;
  Map<String, dynamic>? _result;
  Timer? _serverTimer;
  Timer? _pollTimer;
  late AnimationController _glowCtrl;
  String _fileSizeLabel = '';
  bool _isLargeFile = false;

  // ── 4 engines: v8.0 at top ──────────────────────────────────────────────────
  final List<Map<String, String>> _engines = [
    {'id':'v8.0','name':'v8.0 - Calibrated Precision','desc':'5 أخطاء مُصلَحة — الأدق | 5 bugs fixed — Most accurate','badge':'NEW','bc':'gold'},
    {'id':'v7.6','name':'v7.6 - Intelligent Assessment','desc':'MDS تشخيص ذكي | Smart diagnosis','badge':'MDS','bc':'blue'},
    {'id':'v7.5','name':'v7.5 - Disciplined Precision','desc':'Do-No-Harm — 94/100','badge':'BEST','bc':'green'},
    {'id':'v7.0','name':'v7.0 - Classic','desc':'البنية الأصلية | Original — 91/100','badge':'STABLE','bc':''},
  ];

  S get s => widget.s;

  @override
  void initState() {
    super.initState();
    _glowCtrl = AnimationController(vsync: this, duration: const Duration(seconds: 2))
        ..repeat(reverse: true);
    _checkServer();
    _serverTimer = Timer.periodic(const Duration(seconds: 6), (_) => _checkServer());
  }

  @override
  void dispose() {
    _serverTimer?.cancel();
    _pollTimer?.cancel();
    _glowCtrl.dispose();
    super.dispose();
  }

  Future<void> _checkServer() async {
    final up = await ApiService.isServerRunning();
    if (mounted) setState(() => _isServerUp = up);
  }

  Future<void> _pickFile() async {
    final r = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['mp3','wav','m4a','flac','aac']);
    if (r != null && r.files.single.path != null) {
      final file = File(r.files.single.path!);
      final bytes = await file.length();
      setState(() {
        _selectedFile = file;
        _outputFile = null; _result = null;
        _status = ''; _progress = 0;
        _fileSizeLabel = '${(bytes/1024/1024).toStringAsFixed(1)} MB';
        _isLargeFile = bytes > 8 * 1024 * 1024;
      });
    }
  }

  Future<void> _process() async {
    if (_selectedFile == null || !_isServerUp) return;
    setState(() {
      _isProcessing = true; _progress = 0.02;
      _status = s.processing;
      _outputFile = null; _result = null;
    });
    try {
      final resp = await ApiService.uploadFile(_selectedFile!, _selectedEngine,
        onProgress: (p, label) {
          if (mounted) setState(() { _progress = p; _status = label; });
        });
      _jobId = resp['job_id'];
      _startPolling();
    } catch (e) {
      setState(() { _isProcessing = false; _status = 'خطأ: $e'; });
    }
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      if (_jobId == null) return;
      try {
        final st = await ApiService.getStatus(_jobId!);
        if (!mounted) return;
        final srvProgress = (st['progress'] ?? 0) / 100.0;
        final status = st['status'] as String? ?? '';
        double displayP;
        if (status == 'uploading' || status == 'merging') {
          displayP = _progress;
        } else {
          displayP = 0.68 + srvProgress * 0.32;
        }
        setState(() { _progress = displayP.clamp(0.0, 1.0); _status = st['label'] ?? ''; });
        if (status == 'done') {
          _pollTimer?.cancel();
          await _download(st);
        } else if (status == 'error') {
          _pollTimer?.cancel();
          setState(() { _isProcessing = false; _status = 'فشل: ${st['error']}'; });
        }
      } catch (_) {}
    });
  }

  Future<void> _download(Map<String, dynamic> sd) async {
    setState(() { _status = 'جارٍ التحميل...'; _progress = 0.95; });
    try {
      final dir = await getDownloadsDirectory() ?? await getApplicationDocumentsDirectory();
      final name = sd['filename'] ?? 'enhanced_1425h.mp3';
      final path = '${dir.path}/$name';
      final f = await ApiService.downloadFile(_jobId!, path);
      if (mounted) {
        setState(() {
          _isProcessing = false; _progress = 1.0;
          _outputFile = f; _result = sd;
          _status = f != null ? s.done : 'فشل التحميل';
        });
      }
    } catch (e) {
      if (mounted) setState(() { _isProcessing = false; _status = 'خطأ: $e'; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: CustomScrollView(slivers: [
          SliverToBoxAdapter(child: _header()),
          SliverToBoxAdapter(child: _serverBanner()),
          SliverToBoxAdapter(child: _engineSelector()),
          SliverToBoxAdapter(child: _fileCard()),
          if (_isProcessing || _progress > 0)
            SliverToBoxAdapter(child: _progressCard()),
          if (_outputFile != null)
            SliverToBoxAdapter(child: _resultCard()),
          SliverToBoxAdapter(child: _bottomRow()),
          SliverToBoxAdapter(child: _donationCard()),
          const SliverToBoxAdapter(child: SizedBox(height: 40)),
        ]),
      ),
    );
  }

  Widget _header() => Padding(
    padding: const EdgeInsets.fromLTRB(20, 28, 20, 8),
    child: Row(children: [
      // Logo
      Container(
        width: 52, height: 52,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          boxShadow: [BoxShadow(
            color: const Color(0xFFD4AF37).withOpacity(0.2),
            blurRadius: 12)]),
        child: ClipOval(child: Image.asset(
          'assets/images/logo.png', fit: BoxFit.cover,
          errorBuilder: (_,__,___) => Container(
            color: const Color(0xFF1A1500),
            child: const Icon(Icons.music_note, color: Color(0xFFD4AF37), size: 28))))),
      const SizedBox(width: 14),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        AnimatedBuilder(
          animation: _glowCtrl,
          builder: (_, __) => Text(s.appName,
            textDirection: TextDirection.rtl,
            style: TextStyle(
              fontSize: 26, fontWeight: FontWeight.bold,
              color: Color.lerp(const Color(0xFFD4AF37), const Color(0xFFFFF4B0), _glowCtrl.value)))),
        Text(s.subtitle,
          style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10, letterSpacing: 1.5)),
      ])),
      // Settings button
      GestureDetector(
        onTap: () => Navigator.push(context, MaterialPageRoute(
          builder: (_) => SettingsScreen(s: s, onLangToggle: widget.onLangToggle))),
        child: Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: const Color(0xFF161B22),
            shape: BoxShape.circle,
            border: Border.all(color: const Color(0xFF21262D))),
          child: const Icon(Icons.settings_outlined,
            color: Color(0xFF8B949E), size: 20))),
    ]),
  );

  Widget _serverBanner() => Container(
    margin: const EdgeInsets.fromLTRB(16,4,16,4),
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
    decoration: BoxDecoration(
      color: _isServerUp ? const Color(0xFF0D2015) : const Color(0xFF200D0D),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(
        color: _isServerUp ? const Color(0xFF3FB950) : const Color(0xFFF85149),
        width: 0.8)),
    child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
      Container(width: 8, height: 8, decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: _isServerUp ? const Color(0xFF3FB950) : const Color(0xFFF85149))),
      const SizedBox(width: 8),
      Text(_isServerUp ? s.serverOnline : s.serverOffline,
        style: TextStyle(
          color: _isServerUp ? const Color(0xFF3FB950) : const Color(0xFFF85149),
          fontSize: 12)),
    ]),
  );

  Widget _engineSelector() => Container(
    margin: const EdgeInsets.fromLTRB(16,10,16,4),
    decoration: BoxDecoration(
      color: const Color(0xFF161B22),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: const Color(0xFF21262D))),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16,14,16,4),
        child: Text(s.chooseEngine,
          style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11, letterSpacing: 1.5))),
      ..._engines.map(_engineTile),
      const SizedBox(height: 8),
    ]),
  );

  Widget _engineTile(Map<String, String> e) {
    final sel = _selectedEngine == e['id'];
    final bc = e['bc']!;
    final badgeColor = bc == 'gold' ? const Color(0xFFD4AF37)
        : bc == 'green' ? const Color(0xFF3FB950)
        : bc == 'blue' ? const Color(0xFF58A6FF)
        : const Color(0xFF484F58);
    final badgeBg = bc == 'gold' ? const Color(0xFF1A1200)
        : bc == 'green' ? const Color(0xFF0D2015)
        : bc == 'blue' ? const Color(0xFF0D1B2E)
        : const Color(0xFF1C1C1C);

    return GestureDetector(
      onTap: () => setState(() => _selectedEngine = e['id']!),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        margin: const EdgeInsets.fromLTRB(8,3,8,3),
        padding: const EdgeInsets.all(13),
        decoration: BoxDecoration(
          color: sel ? const Color(0xFF1A1500) : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(
            color: sel ? const Color(0xFFD4AF37) : Colors.transparent, width: 1.2)),
        child: Row(children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            width: 20, height: 20,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              border: Border.all(
                color: sel ? const Color(0xFFD4AF37) : const Color(0xFF30363D), width: 2),
              color: sel ? const Color(0xFFD4AF37) : Colors.transparent),
            child: sel ? const Icon(Icons.check, size: 12, color: Color(0xFF0A0C10)) : null),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Flexible(child: Text(e['name']!,
                style: TextStyle(
                  color: sel ? const Color(0xFFD4AF37) : const Color(0xFFC9D1D9),
                  fontWeight: FontWeight.bold, fontSize: 13))),
              const SizedBox(width: 6),
              if (e['badge']!.isNotEmpty)
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                  decoration: BoxDecoration(
                    color: badgeBg, borderRadius: BorderRadius.circular(4),
                    border: Border.all(color: badgeColor.withOpacity(0.4), width: 0.6)),
                  child: Text(e['badge']!,
                    style: TextStyle(color: badgeColor, fontSize: 9, fontWeight: FontWeight.bold))),
            ]),
            const SizedBox(height: 3),
            Text(e['desc']!,
              style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),
          ])),
        ]),
      ),
    );
  }

  Widget _fileCard() => GestureDetector(
    onTap: _isProcessing ? null : _pickFile,
    child: Container(
      margin: const EdgeInsets.fromLTRB(16,10,16,4),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: _selectedFile != null ? const Color(0xFFD4AF37) : const Color(0xFF30363D),
          width: 1.5)),
      child: Column(children: [
        Icon(_selectedFile != null ? Icons.audio_file : Icons.add_circle_outline,
          color: const Color(0xFFD4AF37), size: 52),
        const SizedBox(height: 12),
        Text(_selectedFile != null ? _selectedFile!.path.split('/').last : s.pickFile,
          textDirection: TextDirection.rtl,
          textAlign: TextAlign.center,
          style: TextStyle(
            color: _selectedFile != null ? const Color(0xFFC9D1D9) : const Color(0xFF8B949E),
            fontSize: _selectedFile != null ? 13 : 16,
            fontWeight: _selectedFile != null ? FontWeight.normal : FontWeight.bold)),
        if (_selectedFile != null) ...[
          const SizedBox(height: 4),
          Row(mainAxisAlignment: MainAxisAlignment.center, children: [
            Text(_fileSizeLabel,
              style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
            if (_isLargeFile) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                decoration: BoxDecoration(
                  color: const Color(0xFF1A1500), borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: const Color(0xFFD4AF37).withOpacity(0.5))),
                child: Text(s.chunkedBadge,
                  style: const TextStyle(color: Color(0xFFD4AF37), fontSize: 9))),
            ],
          ]),
        ],
        const SizedBox(height: 4),
        Text(s.fileSizeLimit,
          style: const TextStyle(color: Color(0xFF484F58), fontSize: 11)),
        if (_selectedFile != null) ...[
          const SizedBox(height: 18),
          SizedBox(width: double.infinity,
            child: ElevatedButton(
              onPressed: (_isProcessing || !_isServerUp) ? null : _process,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFD4AF37),
                foregroundColor: const Color(0xFF0A0C10),
                padding: const EdgeInsets.symmetric(vertical: 15),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                disabledBackgroundColor: const Color(0xFFD4AF37).withOpacity(0.3)),
              child: Text(
                _isProcessing ? s.processing : '${s.process} — $_selectedEngine',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)))),
        ],
      ]),
    ),
  );

  Widget _progressCard() => Container(
    margin: const EdgeInsets.fromLTRB(16,10,16,4),
    padding: const EdgeInsets.all(20),
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
            color: Color(0xFFD4AF37), fontWeight: FontWeight.bold, fontSize: 14)),
      ]),
      const SizedBox(height: 12),
      ClipRRect(
        borderRadius: BorderRadius.circular(8),
        child: LinearProgressIndicator(
          value: _progress, minHeight: 8,
          backgroundColor: const Color(0xFF21262D),
          valueColor: const AlwaysStoppedAnimation(Color(0xFFD4AF37)))),
      if (_isLargeFile && _progress < 0.68) ...[
        const SizedBox(height: 8),
        Text(s.chunkedBadge,
          style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),
      ],
    ]),
  );

  Widget _resultCard() {
    final score = double.tryParse(_result?['score']?.toString() ?? '0') ?? 0.0;
    final label = score >= 96 ? s.excellent : score >= 92 ? s.great : s.good;
    return Container(
      margin: const EdgeInsets.fromLTRB(16,10,16,4),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFF0D2015),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF3FB950), width: 1.2)),
      child: Column(children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Text(label, style: const TextStyle(
              color: Color(0xFF3FB950), fontWeight: FontWeight.bold, fontSize: 16)),
            const SizedBox(width: 10),
            Text('${score.toStringAsFixed(1)}/100',
              style: const TextStyle(
                color: Color(0xFFD4AF37), fontWeight: FontWeight.w900, fontSize: 32)),
          ]),
        const SizedBox(height: 14),
        Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
          if (_result?['lufs']  != null) _chip('LUFS',  _result!['lufs'].toString()),
          if (_result?['rms']   != null) _chip('RMS',   _result!['rms'].toString()),
          if (_result?['crest'] != null) _chip('Crest', _result!['crest'].toString()),
          if (_result?['lra']   != null) _chip('LRA',   _result!['lra'].toString()),
        ]),
        const SizedBox(height: 16),
        SizedBox(width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: () {
              if (_outputFile == null) return;
              ScaffoldMessenger.of(context).showSnackBar(SnackBar(
                content: Text('${s.savedTo}: ${_outputFile!.path.split('/').last}'),
                backgroundColor: const Color(0xFF0D2015)));
            },
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF0D2015),
              foregroundColor: const Color(0xFF3FB950),
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(10),
                side: const BorderSide(color: Color(0xFF3FB950)))),
            icon: const Icon(Icons.download),
            label: Text(s.savedTo,
              style: const TextStyle(fontWeight: FontWeight.bold)))),
      ]),
    );
  }

  Widget _chip(String label, String value) => Column(children: [
    Text(label, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),
    const SizedBox(height: 2),
    Text(value, style: const TextStyle(
      color: Color(0xFFD4AF37), fontWeight: FontWeight.bold, fontSize: 13)),
  ]);

  Widget _bottomRow() => Padding(
    padding: const EdgeInsets.fromLTRB(16,10,16,4),
    child: Row(children: [
      Expanded(child: GestureDetector(
        onTap: () => Navigator.push(context,
          MaterialPageRoute(builder: (_) => const HistoryScreen())),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
          decoration: BoxDecoration(
            color: const Color(0xFF161B22),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFF21262D))),
          child: Row(children: [
            const Icon(Icons.history, color: Color(0xFF8B949E), size: 20),
            const SizedBox(width: 10),
            Expanded(child: Text(s.history,
              style: const TextStyle(color: Color(0xFFC9D1D9), fontSize: 13))),
            const Icon(Icons.arrow_forward_ios, color: Color(0xFF8B949E), size: 13),
          ])))),
    ]),
  );

  Widget _donationCard() => GestureDetector(
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
        const Text('🤲', style: TextStyle(fontSize: 30)),
        const SizedBox(width: 14),
        Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(s.donation, style: const TextStyle(
            color: Color(0xFFD4AF37), fontWeight: FontWeight.bold, fontSize: 15)),
          const SizedBox(height: 3),
          Text(s.donationDesc, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
        ])),
        const Icon(Icons.arrow_forward_ios, color: Color(0xFFD4AF37), size: 14),
      ]),
    ),
  );
}
