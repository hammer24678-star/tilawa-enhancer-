import 'dart:io';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:path_provider/path_provider.dart';
import '../services/api_service.dart';
import 'history_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with TickerProviderStateMixin {
  File? _selectedFile;
  String _selectedEngine = 'v7.6';
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

  // File size display
  String _fileSizeLabel = '';
  bool _isLargeFile = false; // > 8MB → shows chunk info

  final List<Map<String, String>> _engines = [
    {
      'id': 'v7.6',
      'name': 'v7.6 - Intelligent Assessment',
      'desc': 'MDS تشخيص ذكي - الاحدث',
      'badge': 'NEW',
      'bc': 'blue',
    },
    {
      'id': 'v7.5',
      'name': 'v7.5 - Disciplined Precision',
      'desc': 'Do-No-Harm - 94/100 مثبت',
      'badge': 'BEST',
      'bc': 'green',
    },
    {
      'id': 'v7.0',
      'name': 'v7.0 - Classic',
      'desc': 'البنية الاصلية - 91/100',
      'badge': 'STABLE',
      'bc': 'gold',
    },
  ];

  @override
  void initState() {
    super.initState();
    _glowCtrl = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..repeat(reverse: true);
    _checkServerOnce();
    _serverTimer = Timer.periodic(
      const Duration(seconds: 6),
      (_) => _checkServerOnce(),
    );
  }

  @override
  void dispose() {
    _serverTimer?.cancel();
    _pollTimer?.cancel();
    _glowCtrl.dispose();
    super.dispose();
  }

  Future<void> _checkServerOnce() async {
    final up = await ApiService.isServerRunning();
    if (mounted) setState(() => _isServerUp = up);
  }

  Future<void> _pickFile() async {
    final r = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['mp3', 'wav', 'm4a', 'flac', 'aac'],
    );
    if (r != null && r.files.single.path != null) {
      final file = File(r.files.single.path!);
      final bytes = await file.length();
      final mb = bytes / 1024 / 1024;
      final isLarge = bytes > 8 * 1024 * 1024;

      setState(() {
        _selectedFile = file;
        _outputFile = null;
        _result = null;
        _status = '';
        _progress = 0;
        _fileSizeLabel = '${mb.toStringAsFixed(1)} MB';
        _isLargeFile = isLarge;
      });
    }
  }

  Future<void> _process() async {
    if (_selectedFile == null || !_isServerUp) return;
    setState(() {
      _isProcessing = true;
      _progress = 0.02;
      _status = 'جارٍ الرفع...';
      _outputFile = null;
      _result = null;
    });

    try {
      final resp = await ApiService.uploadFile(
        _selectedFile!,
        _selectedEngine,
        onProgress: (progress, label) {
          if (mounted) setState(() {
            _progress = progress;
            _status = label;
          });
        },
      );
      _jobId = resp['job_id'];
      _startPolling();
    } catch (e) {
      setState(() {
        _isProcessing = false;
        _status = 'خطا في الرفع: $e';
      });
    }
  }

  void _startPolling() {
    _pollTimer?.cancel();
    _pollTimer = Timer.periodic(const Duration(seconds: 2), (_) async {
      if (_jobId == null) return;
      try {
        final s = await ApiService.getStatus(_jobId!);
        if (!mounted) return;

        final serverProgress = (s['progress'] ?? 0) / 100.0;
        // Blend: upload progress was 0-68%, server is 0-100%
        // After finalize, use server progress mapped to 68-100%
        final status = s['status'] as String? ?? '';
        double displayProgress;
        if (status == 'uploading' || status == 'merging') {
          displayProgress = _progress; // keep upload progress
        } else {
          displayProgress = 0.68 + serverProgress * 0.32;
        }

        setState(() {
          _progress = displayProgress.clamp(0.0, 1.0);
          _status = s['label'] ?? '';
        });

        if (status == 'done') {
          _pollTimer?.cancel();
          await _downloadOutput(s);
        } else if (status == 'error') {
          _pollTimer?.cancel();
          setState(() {
            _isProcessing = false;
            _status = 'فشل: ${s['error']}';
          });
        }
      } catch (_) {}
    });
  }

  Future<void> _downloadOutput(Map<String, dynamic> sd) async {
    setState(() { _status = 'جارٍ التحميل...'; _progress = 0.95; });
    try {
      final dir = await getDownloadsDirectory() ??
          await getApplicationDocumentsDirectory();
      final name = sd['filename'] ?? 'enhanced_1425h.mp3';
      final f = await ApiService.downloadFile(_jobId!, '${dir.path}/$name');
      if (mounted) {
        setState(() {
          _isProcessing = false;
          _progress = 1.0;
          _outputFile = f;
          _result = sd;
          _status = f != null ? 'اكتملت' : 'فشل التحميل';
        });
      }
    } catch (e) {
      if (mounted) setState(() { _isProcessing = false; _status = 'خطا: $e'; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: CustomScrollView(
          slivers: [
            SliverToBoxAdapter(child: _header()),
            SliverToBoxAdapter(child: _serverBanner()),
            SliverToBoxAdapter(child: _engineSelector()),
            SliverToBoxAdapter(child: _fileCard()),
            if (_isProcessing || _progress > 0)
              SliverToBoxAdapter(child: _progressCard()),
            if (_outputFile != null)
              SliverToBoxAdapter(child: _resultCard()),
            SliverToBoxAdapter(child: _historyButton()),
            SliverToBoxAdapter(child: _donationCard()),
            const SliverToBoxAdapter(child: SizedBox(height: 40)),
          ],
        ),
      ),
    );
  }

  Widget _header() => Padding(
    padding: const EdgeInsets.fromLTRB(24, 36, 24, 8),
    child: Column(children: [
      AnimatedBuilder(
        animation: _glowCtrl,
        builder: (_, __) => Text(
          'محسِّن التلاوة',
          textDirection: TextDirection.rtl,
          style: TextStyle(
            fontSize: 38, fontWeight: FontWeight.bold,
            color: Color.lerp(
              const Color(0xFFD4AF37),
              const Color(0xFFFFF4B0),
              _glowCtrl.value,
            ),
          ),
        ),
      ),
      const SizedBox(height: 4),
      const Text('YASSER AL-DOSSARI - 1425H',
        style: TextStyle(color: Color(0xFF8B949E), fontSize: 11, letterSpacing: 3)),
    ]),
  );

  Widget _serverBanner() => Container(
    margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
    decoration: BoxDecoration(
      color: _isServerUp ? const Color(0xFF0D2015) : const Color(0xFF200D0D),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(
        color: _isServerUp ? const Color(0xFF3FB950) : const Color(0xFFF85149),
        width: 0.8),
    ),
    child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
      Container(width: 8, height: 8,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: _isServerUp ? const Color(0xFF3FB950) : const Color(0xFFF85149))),
      const SizedBox(width: 8),
      Flexible(child: Text(
        _isServerUp
            ? 'الخادم السحابي يعمل'
            : 'الخادم غير متصل - تحقق من الانترنت',
        style: TextStyle(
          color: _isServerUp ? const Color(0xFF3FB950) : const Color(0xFFF85149),
          fontSize: 12))),
    ]),
  );

  Widget _engineSelector() => Container(
    margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),
    decoration: BoxDecoration(
      color: const Color(0xFF161B22),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: const Color(0xFF21262D)),
    ),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Padding(
        padding: EdgeInsets.fromLTRB(16, 14, 16, 4),
        child: Text('اختر المحرك',
          style: TextStyle(color: Color(0xFF8B949E), fontSize: 11, letterSpacing: 1.5)),
      ),
      ..._engines.map(_engineTile),
      const SizedBox(height: 8),
    ]),
  );

  Widget _engineTile(Map<String, String> e) {
    final sel = _selectedEngine == e['id'];
    final bc = e['bc'];
    final badgeColor = bc == 'blue' ? const Color(0xFF58A6FF)
        : bc == 'green' ? const Color(0xFF3FB950)
        : const Color(0xFFD4AF37);
    final badgeBg = bc == 'blue' ? const Color(0xFF0D1B2E)
        : bc == 'green' ? const Color(0xFF0D2015)
        : const Color(0xFF1A1200);

    return GestureDetector(
      onTap: () => setState(() => _selectedEngine = e['id']!),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        margin: const EdgeInsets.fromLTRB(8, 3, 8, 3),
        padding: const EdgeInsets.all(13),
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
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Flexible(child: Text(e['name']!,
                style: TextStyle(
                  color: sel ? const Color(0xFFD4AF37) : const Color(0xFFC9D1D9),
                  fontWeight: FontWeight.bold, fontSize: 13))),
              const SizedBox(width: 6),
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
              style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
          ])),
        ]),
      ),
    );
  }

  Widget _fileCard() => GestureDetector(
    onTap: _isProcessing ? null : _pickFile,
    child: Container(
      margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: _selectedFile != null ? const Color(0xFFD4AF37) : const Color(0xFF30363D),
          width: 1.5)),
      child: Column(children: [
        Icon(
          _selectedFile != null ? Icons.audio_file : Icons.add_circle_outline,
          color: const Color(0xFFD4AF37), size: 52),
        const SizedBox(height: 12),
        Text(
          _selectedFile != null
              ? _selectedFile!.path.split('/').last
              : 'اختر الملف الصوتي',
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
                  color: const Color(0xFF1A1500),
                  borderRadius: BorderRadius.circular(4),
                  border: Border.all(color: const Color(0xFFD4AF37).withOpacity(0.5))),
                child: const Text('رفع مجزأ',
                  style: TextStyle(color: Color(0xFFD4AF37), fontSize: 9))),
            ],
          ]),
        ],
        const SizedBox(height: 4),
        const Text('MP3 - WAV - M4A - FLAC - حتى 300MB',
          style: TextStyle(color: Color(0xFF484F58), fontSize: 11)),
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
                _isProcessing ? 'جارٍ المعالجة...' : 'معالجة بالمحرك $_selectedEngine',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)))),
        ],
      ]),
    ),
  );

  Widget _progressCard() => Container(
    margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),
    padding: const EdgeInsets.all(20),
    decoration: BoxDecoration(
      color: const Color(0xFF161B22),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: const Color(0xFF21262D))),
    child: Column(children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Flexible(child: Text(
          _status.isEmpty ? 'جارٍ المعالجة...' : _status,
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
        Text(
          'ملف كبير — رفع مجزأ (قد يستغرق دقيقة)',
          style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),
      ],
    ]),
  );

  Widget _resultCard() {
    final score = double.tryParse(_result?['score']?.toString() ?? '0') ?? 0.0;
    final label = score >= 96 ? 'ممتاز' : score >= 92 ? 'رائع' : 'جيد جداً';
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),
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
                content: Text('محفوظ: ${_outputFile!.path.split('/').last}'),
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
            label: const Text('محفوظ في Downloads',
              style: TextStyle(fontWeight: FontWeight.bold)))),
      ]),
    );
  }

  Widget _chip(String label, String value) => Column(children: [
    Text(label, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),
    const SizedBox(height: 2),
    Text(value, style: const TextStyle(
      color: Color(0xFFD4AF37), fontWeight: FontWeight.bold, fontSize: 13)),
  ]);

  Widget _historyButton() => GestureDetector(
    onTap: () => Navigator.push(
      context, MaterialPageRoute(builder: (_) => const HistoryScreen())),
    child: Container(
      margin: const EdgeInsets.fromLTRB(16, 10, 16, 4),
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF21262D))),
      child: Row(children: [
        const Icon(Icons.history, color: Color(0xFF8B949E), size: 20),
        const SizedBox(width: 12),
        const Expanded(child: Text('سجل الملفات المعالجة',
          style: TextStyle(color: Color(0xFFC9D1D9), fontSize: 14))),
        const Icon(Icons.arrow_forward_ios, color: Color(0xFF8B949E), size: 14),
      ]),
    ),
  );

  Widget _donationCard() => GestureDetector(
    onTap: () async {
      final uri = Uri.parse('https://ipay.instapay.eg/EG/AR/tilawa');
      if (await canLaunchUrl(uri)) await launchUrl(uri);
    },
    child: Container(
      margin: const EdgeInsets.fromLTRB(16, 10, 16, 8),
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
        const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('صدقة جارية',
            style: TextStyle(color: Color(0xFFD4AF37), fontWeight: FontWeight.bold, fontSize: 15)),
          SizedBox(height: 3),
          Text('ساهم في مشروع تحسين التلاوة - InstaPay',
            style: TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
        ])),
        const Icon(Icons.arrow_forward_ios, color: Color(0xFFD4AF37), size: 14),
      ]),
    ),
  );
}
