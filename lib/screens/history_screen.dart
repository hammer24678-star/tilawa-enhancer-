import 'package:flutter/material.dart';
import '../state/lang_provider.dart';
import '../services/api_service.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});
  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Map<String, dynamic>> _jobs = [];
  bool _loading = true;

  @override
  void initState() { super.initState(); _load(); }

  Future<void> _load() async {
    final jobs = await ApiService.getHistory();
    if (mounted) setState(() { _jobs = jobs; _loading = false; });
  }

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    return Scaffold(
      backgroundColor: const Color(0xFF0A0C10),
      appBar: AppBar(
        title: Text(s.history, style: const TextStyle(
          color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF0A0C10),
        iconTheme: const IconThemeData(color: Color(0xFFD4AF37)),
        elevation: 0),
      body: _loading
        ? const Center(child: CircularProgressIndicator(
            color: Color(0xFFD4AF37)))
        : _jobs.isEmpty
          ? Center(child: Text(s.ar ? 'لا يوجد سجل بعد' : 'No history yet',
              style: const TextStyle(color: Color(0xFF8B949E), fontSize: 16)))
          : RefreshIndicator(
              onRefresh: _load,
              color: const Color(0xFFD4AF37),
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: _jobs.length,
                itemBuilder: (_, i) => _jobCard(_jobs[i]))));
  }

  Widget _jobCard(Map<String, dynamic> job) {
    final score = double.tryParse(job['score']?.toString() ?? '0') ?? 0.0;
    final engine = job['engine'] ?? 'v8.0';
    final ts = job['timestamp'] ?? '';
    final c = score >= 94 ? const Color(0xFF3FB950)
        : score >= 90 ? const Color(0xFFD4AF37)
        : const Color(0xFFF85149);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF161B22),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF21262D))),
      child: Row(children: [
        Container(
          width: 50, height: 50,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: const Color(0xFF0A0C10),
            border: Border.all(color: c, width: 2)),
          child: Center(child: Text(score.toStringAsFixed(0),
            style: TextStyle(
              color: c, fontWeight: FontWeight.bold, fontSize: 15)))),
        const SizedBox(width: 12),
        Expanded(child: Column(
          crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(ApiService.buildFilename(engine),
            maxLines: 1, overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              color: Color(0xFFC9D1D9), fontSize: 12,
              fontWeight: FontWeight.bold)),
          const SizedBox(height: 3),
          Row(children: [
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
              decoration: BoxDecoration(
                color: const Color(0xFF1A1500),
                borderRadius: BorderRadius.circular(4),
                border: Border.all(
                  color: const Color(0xFFD4AF37).withOpacity(0.4))),
              child: Text(engine, style: const TextStyle(
                color: Color(0xFFD4AF37), fontSize: 9,
                fontWeight: FontWeight.bold))),
            const SizedBox(width: 8),
            Text(ts, style: const TextStyle(
              color: Color(0xFF8B949E), fontSize: 10)),
          ]),
          if (job['lufs'] != null)
            Padding(
              padding: const EdgeInsets.only(top: 3),
              child: Text(
                [
                  if (job['lufs']  != null) 'LUFS ${job['lufs']}',
                  if (job['crest'] != null) 'Crest ${job['crest']}',
                  if (job['lra']   != null) 'LRA ${job['lra']}',
                ].join('  ·  '),
                style: const TextStyle(
                  color: Color(0xFF484F58), fontSize: 10))),
        ])),
      ]));
  }
}
