import 'package:flutter/material.dart';
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
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final jobs = await ApiService.getHistory();
    if (mounted) setState(() { _jobs = jobs; _loading = false; });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('السجل', textDirection: TextDirection.rtl),
        centerTitle: true,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFFD4AF37)))
          : _jobs.isEmpty
              ? const Center(child: Text('لا توجد ملفات بعد',
                  style: TextStyle(color: Color(0xFF8B949E)),
                  textDirection: TextDirection.rtl))
              : RefreshIndicator(
                  onRefresh: _load,
                  color: const Color(0xFFD4AF37),
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _jobs.length,
                    itemBuilder: (_, i) {
                      final j = _jobs[i];
                      final sc = double.tryParse(j['score']?.toString() ?? '0') ?? 0;
                      final color = sc >= 96 ? const Color(0xFF3FB950)
                          : sc >= 90 ? const Color(0xFFD4AF37)
                          : const Color(0xFFF85149);
                      return Container(
                        margin: const EdgeInsets.only(bottom: 10),
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: const Color(0xFF161B22),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(color: const Color(0xFF21262D)),
                        ),
                        child: Row(children: [
                          Container(
                            width: 48, height: 48,
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              border: Border.all(color: color, width: 2)),
                            child: Center(child: Text(sc.toStringAsFixed(0),
                              style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 14))),
                          ),
                          const SizedBox(width: 12),
                          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                            Text(j['filename']?.toString() ?? 'ملف',
                              maxLines: 1, overflow: TextOverflow.ellipsis,
                              style: const TextStyle(color: Color(0xFFC9D1D9), fontSize: 13, fontWeight: FontWeight.bold)),
                            const SizedBox(height: 4),
                            Row(children: [
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                                decoration: BoxDecoration(
                                  color: const Color(0xFF1A1500),
                                  borderRadius: BorderRadius.circular(4)),
                                child: Text(j['engine']?.toString() ?? '',
                                  style: const TextStyle(color: Color(0xFFD4AF37), fontSize: 10, fontWeight: FontWeight.bold))),
                              const SizedBox(width: 8),
                              Flexible(child: Text(j['timestamp']?.toString() ?? '',
                                style: const TextStyle(color: Color(0xFF8B949E), fontSize: 11))),
                            ]),
                          ])),
                        ]),
                      );
                    },
                  )),
    );
  }
}
