import 'dart:io';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:path_provider/path_provider.dart';
import '../services/api_service.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen>
    with SingleTickerProviderStateMixin {
  File? _file;
  String _engine = 'v7.6';
  String _status = '';
  double _prog = 0;
  bool _busy = false, _up = false;
  String? _jobId;
  File? _out;
  Map<String, dynamic>? _res;
  Timer? _poll, _srv;
  late AnimationController _glow;

  static const _eng = [
    {'id': 'v7.6',  'n': 'v7.6',  's': 'MDS - تشخيص ذكي',          't': 'NEW',    'c': 'blue'},
    {'id': 'v7.55', 'n': 'v7.55', 's': 'Forensic Fix - Crest دقيق', 't': 'BEST',   'c': 'green'},
    {'id': 'v7.5',  'n': 'v7.5',  's': 'Disciplined - Do-No-Harm',  't': '',        'c': ''},
    {'id': 'v7.0',  'n': 'v7.0',  's': 'Classic - الاساس المثبت',   't': 'STABLE', 'c': 'gold'},
  ];

  @override
  void initState() {
    super.initState();
    _glow = AnimationController(vsync: this, duration: const Duration(seconds: 2))
      ..repeat(reverse: true);
    _srv = Timer.periodic(const Duration(seconds: 4), (_) => _check());
    _check();
  }

  @override
  void dispose() {
    _poll?.cancel();
    _srv?.cancel();
    _glow.dispose();
    super.dispose();
  }

  Future<void> _check() async {
    final up = await ApiService.isServerRunning();
    if (mounted) setState(() => _up = up);
  }

  Future<void> _pick() async {
    try {
      final r = await FilePicker.platform.pickFiles(
        type: FileType.custom,
        allowedExtensions: ['mp3', 'wav', 'm4a', 'flac'],
      );
      if (r?.files.single.path != null && mounted) {
        setState(() {
          _file = File(r!.files.single.path!);
          _out = null; _res = null; _status = ''; _prog = 0;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _status = 'خطأ في اختيار الملف');
    }
  }

  Future<void> _go() async {
    if (_file == null || !_up || _busy) return;
    setState(() { _busy = true; _prog = 0.05; _status = 'جارٍ الرفع...'; _out = null; _res = null; });
    try {
      final r = await ApiService.uploadFile(_file!, _engine);
      _jobId = r['job_id'] as String?;
      if (_jobId != null) {
        _poll = Timer.periodic(const Duration(seconds: 1), (_) => _tick());
      }
    } catch (_) {
      if (mounted) setState(() { _busy = false; _status = 'خطأ في الرفع'; });
    }
  }

  Future<void> _tick() async {
    if (_jobId == null || !mounted) return;
    try {
      final s = await ApiService.getStatus(_jobId!);
      if (!mounted) return;
      setState(() {
        _prog = ((s['progress'] as num?)?.toDouble() ?? 5) / 100;
        _status = (s['label'] as String?) ?? '';
      });
      if (s['status'] == 'done') { _poll?.cancel(); await _dl(s); }
      else if (s['status'] == 'error') {
        _poll?.cancel();
        if (mounted) setState(() { _busy = false; _status = 'فشل: ${s['error']}'; });
      }
    } catch (_) {}
  }

  Future<void> _dl(Map<String, dynamic> s) async {
    if (!mounted) return;
    setState(() => _status = 'جارٍ التحميل...');
    try {
      Directory? dir;
      try {
        if (Platform.isAndroid) {
          dir = Directory('/storage/emulated/0/Download');
          if (!dir.existsSync()) dir = null;
        }
      } catch (_) {}
      dir ??= await getApplicationDocumentsDirectory();
      final nm = (s['filename'] as String?) ?? 'enhanced.mp3';
      final f = await ApiService.downloadFile(_jobId!, '${dir.path}/$nm');
      if (mounted) setState(() { _busy = false; _prog = 1; _out = f; _res = s; _status = f != null ? 'اكتمل' : 'فشل'; });
    } catch (_) {
      if (mounted) setState(() { _busy = false; _status = 'خطأ في التحميل'; });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          children: [
            const SizedBox(height: 28),
            AnimatedBuilder(
              animation: _glow,
              builder: (_, __) => Text('محسِّن التلاوة',
                textDirection: TextDirection.rtl,
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 34, fontWeight: FontWeight.bold,
                  color: Color.lerp(const Color(0xFFD4AF37), const Color(0xFFFFF0A0), _glow.value))),
            ),
            const Text('YASSER AL-DOSSARI - 1425H',
              textAlign: TextAlign.center,
              style: TextStyle(color: Color(0xFF8B949E), fontSize: 11, letterSpacing: 3)),
            const SizedBox(height: 12),
            _badge(),
            const SizedBox(height: 12),
            _engCard(),
            const SizedBox(height: 10),
            _fileCard(),
            if (_busy || _prog > 0) ...[const SizedBox(height: 10), _progCard()],
            if (_out != null) ...[const SizedBox(height: 10), _resCard()],
            const SizedBox(height: 10),
            _donateCard(),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }

  Widget _badge() => Container(
    padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 14),
    decoration: BoxDecoration(
      color: _up ? const Color(0xFF0D2010) : const Color(0xFF200D0D),
      borderRadius: BorderRadius.circular(10),
      border: Border.all(color: _up ? const Color(0xFF3FB950) : const Color(0xFFF85149), width: 0.8),
    ),
    child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
      Icon(Icons.circle, size: 8, color: _up ? const Color(0xFF3FB950) : const Color(0xFFF85149)),
      const SizedBox(width: 8),
      Text(_up ? 'الخادم متصل - 127.0.0.1:5000' : 'غير متصل - شغل: python app.py',
        style: TextStyle(fontSize: 11, color: _up ? const Color(0xFF3FB950) : const Color(0xFFF85149))),
    ]),
  );

  Widget _engCard() => Container(
    decoration: BoxDecoration(
      color: const Color(0xFF161B22),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: const Color(0xFF21262D)),
    ),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Padding(padding: EdgeInsets.fromLTRB(16, 12, 16, 6),
        child: Text('اختر المحرك', style: TextStyle(color: Color(0xFF8B949E), fontSize: 11, letterSpacing: 1))),
      ..._eng.map((e) => _engRow(e)),
      const SizedBox(height: 6),
    ]),
  );

  Widget _engRow(Map<String, String> e) {
    final sel = _engine == e['id'];
    final tc = e['c'] == 'blue' ? const Color(0xFF58A6FF)
        : e['c'] == 'green' ? const Color(0xFF3FB950) : const Color(0xFFD4AF37);
    final bg = e['c'] == 'blue' ? const Color(0xFF1F3A5F)
        : e['c'] == 'green' ? const Color(0xFF1A3020) : const Color(0xFF2A1500);
    return GestureDetector(
      onTap: () => setState(() => _engine = e['id']!),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        margin: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        padding: const EdgeInsets.all(11),
        decoration: BoxDecoration(
          color: sel ? const Color(0xFF1A1500) : Colors.transparent,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: sel ? const Color(0xFFD4AF37) : Colors.transparent),
        ),
        child: Row(children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 180), width: 18, height: 18,
            decoration: BoxDecoration(shape: BoxShape.circle,
              border: Border.all(color: sel ? const Color(0xFFD4AF37) : const Color(0xFF30363D), width: 2),
              color: sel ? const Color(0xFFD4AF37) : Colors.transparent),
            child: sel ? const Icon(Icons.check, size: 11, color: Color(0xFF0A0C10)) : null),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Row(children: [
              Text(e['n']!, style: TextStyle(
                color: sel ? const Color(0xFFD4AF37) : const Color(0xFFC9D1D9),
                fontWeight: FontWeight.bold, fontSize: 13)),
              if (e['t']!.isNotEmpty) ...[
                const SizedBox(width: 6),
                Container(padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                  decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(4)),
                  child: Text(e['t']!, style: TextStyle(color: tc, fontSize: 9, fontWeight: FontWeight.bold))),
              ],
            ]),
            Text(e['s']!, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
          ])),
        ]),
      ),
    );
  }

  Widget _fileCard() => GestureDetector(
    onTap: _busy ? null : _pick,
    child: Container(
      padding: const EdgeInsets.all(22),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: _file != null ? const Color(0xFFD4AF37) : const Color(0xFF30363D),
          width: 1.5),
      ),
      child: Column(children: [
        Icon(_file != null ? Icons.audio_file_rounded : Icons.add_circle_outline_rounded,
          color: const Color(0xFFD4AF37), size: 44),
        const SizedBox(height: 10),
        Text(_file != null ? _file!.path.split('/').last : 'اختر الملف الصوتي',
          textDirection: TextDirection.rtl, textAlign: TextAlign.center,
          style: TextStyle(
            color: _file != null ? const Color(0xFFC9D1D9) : const Color(0xFF8B949E),
            fontSize: _file != null ? 12 : 15,
            fontWeight: _file != null ? FontWeight.normal : FontWeight.bold)),
        if (_file != null) ...[
          const SizedBox(height: 3),
          Text('${(_file!.lengthSync() / 1024 / 1024).toStringAsFixed(1)} MB',
            style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
          const SizedBox(height: 16),
          SizedBox(width: double.infinity,
            child: ElevatedButton(
              onPressed: (_busy || !_up) ? null : _go,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFD4AF37),
                foregroundColor: const Color(0xFF0A0C10),
                disabledBackgroundColor: const Color(0xFF333000),
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              ),
              child: Text(_busy ? 'جارٍ المعالجة...' : 'معالجة بـ $_engine',
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
            )),
        ] else
          const Padding(padding: EdgeInsets.only(top: 4),
            child: Text('MP3 - WAV - M4A - MAX 300MB',
              style: TextStyle(color: Color(0xFF484F58), fontSize: 11))),
      ]),
    ),
  );

  Widget _progCard() => Container(
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: const Color(0xFF161B22),
      borderRadius: BorderRadius.circular(14),
      border: Border.all(color: const Color(0xFF21262D)),
    ),
    child: Column(children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Expanded(child: Text(_status.isEmpty ? 'جارٍ المعالجة...' : _status,
          style: const TextStyle(color: Color(0xFFC9D1D9), fontSize: 12))),
        Text('${(_prog * 100).toInt()}%',
          style: const TextStyle(color: Color(0xFFD4AF37), fontWeight: FontWeight.bold, fontSize: 12)),
      ]),
      const SizedBox(height: 10),
      ClipRRect(borderRadius: BorderRadius.circular(6),
        child: LinearProgressIndicator(value: _prog, minHeight: 7,
          backgroundColor: const Color(0xFF21262D),
          valueColor: const AlwaysStoppedAnimation(Color(0xFFD4AF37)))),
    ]),
  );

  Widget _resCard() {
    final sc = double.tryParse(_res?['score']?.toString() ?? '0') ?? 0;
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: const Color(0xFF0D2010),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF3FB950), width: 1.2),
      ),
      child: Column(children: [
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          Text(sc >= 96 ? 'ممتاز' : sc >= 92 ? 'رائع' : 'جيد',
            style: const TextStyle(color: Color(0xFF3FB950), fontWeight: FontWeight.bold, fontSize: 15)),
          const SizedBox(width: 10),
          Text('${sc.toStringAsFixed(1)}/100',
            style: const TextStyle(color: Color(0xFFD4AF37), fontWeight: FontWeight.w900, fontSize: 28)),
        ]),
        const SizedBox(height: 12),
        Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
          if (_res?['crest'] != null) _chip('Crest', _res!['crest'].toString()),
          if (_res?['lra']   != null) _chip('LRA',   _res!['lra'].toString()),
          if (_res?['rms']   != null) _chip('RMS',   _res!['rms'].toString()),
        ]),
        const SizedBox(height: 14),
        Container(width: double.infinity, padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(10),
            border: Border.all(color: const Color(0xFF3FB950))),
          child: Column(children: [
            const Icon(Icons.download_done_rounded, color: Color(0xFF3FB950), size: 22),
            const SizedBox(height: 4),
            const Text('محفوظ في Downloads', style: TextStyle(color: Color(0xFF3FB950), fontSize: 11)),
            if (_out != null) Text(_out!.path.split('/').last,
              style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10),
              textAlign: TextAlign.center),
          ])),
      ]),
    );
  }

  Widget _chip(String l, String v) => Column(children: [
    Text(l, style: const TextStyle(color: Color(0xFF8B949E), fontSize: 10)),
    const SizedBox(height: 2),
    Text(v, style: const TextStyle(color: Color(0xFFD4AF37), fontWeight: FontWeight.bold, fontSize: 13)),
  ]);

  Widget _donateCard() => GestureDetector(
    onTap: () async {
      final u = Uri.parse('https://ipay.instapay.eg/EG/AR/tilawa');
      if (await canLaunchUrl(u)) await launchUrl(u, mode: LaunchMode.externalApplication);
    },
    child: Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF1A1000), Color(0xFF2A1F00)],
          begin: Alignment.topLeft, end: Alignment.bottomRight),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFD4AF37), width: 0.8)),
      child: Row(children: [
        const Text('🤲', style: TextStyle(fontSize: 26)),
        const SizedBox(width: 12),
        const Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('صدقة جارية', style: TextStyle(color: Color(0xFFD4AF37), fontWeight: FontWeight.bold, fontSize: 14)),
          SizedBox(height: 2),
          Text('ساهم في مشروع تحسين التلاوة', style: TextStyle(color: Color(0xFF8B949E), fontSize: 11)),
        ])),
        const Icon(Icons.arrow_forward_ios_rounded, color: Color(0xFFD4AF37), size: 13),
      ]),
    ),
  );
}
