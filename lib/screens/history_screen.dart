import 'dart:io';
import 'package:flutter/material.dart';
import '../state/lang_provider.dart';
import '../services/api_service.dart';

// S19: HistoryScreen now loads from LOCAL SharedPreferences (persistent across
// app restarts and server restarts) instead of the server's /history endpoint
// (which clears when the HuggingFace container restarts).
//
// Each job record was saved by HomeScreen._downloadAndSave() on successful download.
// Re-download calls ApiService.downloadFile(jobId, filename).
// If download returns 'JOB_EXPIRED', the card shows a dismissible expired state.

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({super.key});
  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  List<Map<String, dynamic>> _jobs = [];
  bool _loading = true;

  // Track which jobs are currently being re-downloaded
  final Set<String> _downloading = {};
  // Track which jobs are confirmed expired (404 from server)
  final Set<String> _expired = {};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final jobs = await ApiService.getSavedJobRecords();
    if (mounted) setState(() { _jobs = jobs; _loading = false; });
  }

  Future<void> _reDownload(Map<String, dynamic> job) async {
    final jobId    = job['job_id'] as String;
    final filename = job['filename'] as String? ?? ApiService.buildFilename(job['engine'] ?? 'v8.0');
    final s = LangProvider.strings(context);

    setState(() => _downloading.add(jobId));
    final (file, error) = await ApiService.downloadFile(jobId, filename);
    if (!mounted) return;
    setState(() => _downloading.remove(jobId));

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
    } else if (error == 'JOB_EXPIRED') {
      setState(() => _expired.add(jobId));
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(s.jobExpired,
          style: const TextStyle(fontSize: 12)),
        backgroundColor: const Color(0xFF200D0D),
        duration: const Duration(seconds: 5),
        action: SnackBarAction(
          label: s.ar ? 'حذف' : 'Remove',
          textColor: const Color(0xFFF85149),
          onPressed: () => _removeJob(jobId),
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

  Future<void> _removeJob(String jobId) async {
    await ApiService.removeJobRecord(jobId);
    if (!mounted) return;
    _jobs.removeWhere((j) => j['job_id'] == jobId);
    setState(() {});
  }

  // S28: Clear All confirmation dialog
  Future<void> _clearAll() async {
    final s = LangProvider.strings(context);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF161B22),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(14)),
        title: Text(s.clearAll,
          style: const TextStyle(color: Color(0xFFD4AF37))),
        content: Text(s.clearAllConfirm,
          style: const TextStyle(color: Color(0xFFC9D1D9))),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(s.ar ? 'لا' : 'No',
              style: const TextStyle(color: Color(0xFF8B949E)))),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(s.ar ? 'احذف' : 'Delete',
              style: const TextStyle(color: Color(0xFFF85149)))),
        ]));
    if (confirmed == true && mounted) {
      await ApiService.clearAllJobRecords();
      setState(() => _jobs = []);
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    return Scaffold(
      backgroundColor: const Color(0xFF0A0C10),
      appBar: AppBar(
        title: Text(s.historyTitle, style: const TextStyle(
          color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),
        backgroundColor: const Color(0xFF0A0C10),
        iconTheme: const IconThemeData(color: Color(0xFFD4AF37)),
        elevation: 0,
        actions: [
          if (_jobs.isNotEmpty)
            TextButton(
              onPressed: _clearAll,
              child: Text(s.clearAll,
                style: const TextStyle(
                  color: Color(0xFFF85149), fontSize: 12))),
        ]),
      body: _loading
        ? const Center(child: CircularProgressIndicator(color: Color(0xFFD4AF37)))
        : _jobs.isEmpty
          ? Center(child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.history_rounded,
                  color: Color(0xFF30363D), size: 56),
                const SizedBox(height: 12),
                Text(s.noHistory,
                  style: const TextStyle(color: Color(0xFF8B949E), fontSize: 16)),
                const SizedBox(height: 6),
                Text(
                  s.ar
                    ? 'الملفات المعالجة ستظهر هنا'
                    : 'Processed files will appear here',
                  style: const TextStyle(color: Color(0xFF484F58), fontSize: 12)),
              ]))
          : RefreshIndicator(
              onRefresh: _load,
              color: const Color(0xFFD4AF37),
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: _jobs.length,
                itemBuilder: (_, i) => _jobCard(_jobs[i], s))));
  }

  Widget _jobCard(Map<String, dynamic> job, S s) {
    final jobId  = job['job_id'] as String;
    final score  = double.tryParse(job['score']?.toString() ?? '0') ?? 0.0;
    final engine = job['engine'] as String? ?? 'v8.0';
    final ts     = job['timestamp'] as String? ?? '';
    final isExpired = _expired.contains(jobId);
    final isLoading = _downloading.contains(jobId);

    // Format timestamp
    String displayTs = ts;
    try {
      final dt = DateTime.parse(ts);
      displayTs =
        '${dt.day.toString().padLeft(2,'0')}/${dt.month.toString().padLeft(2,'0')} '
        '${dt.hour.toString().padLeft(2,'0')}:${dt.minute.toString().padLeft(2,'0')}';
    } catch (_) {}

    // Score label (using same thresholds as home_screen)
    final label = score >= 96 ? s.excellent
        : score >= 90 ? s.great
        : score >= 85 ? s.good
        : score >= 78 ? s.decent
        : s.fair;

    final scoreColor = score >= 90 ? const Color(0xFF3FB950)
        : score >= 80 ? const Color(0xFFD4AF37)
        : const Color(0xFFF85149);

    return Dismissible(
      key: Key(jobId),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        margin: const EdgeInsets.only(bottom: 10),
        decoration: BoxDecoration(
          color: const Color(0xFF200D0D),
          borderRadius: BorderRadius.circular(12)),
        child: const Icon(Icons.delete_outline, color: Color(0xFFF85149))),
      onDismissed: (_) => _removeJob(jobId),
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: isExpired ? const Color(0xFF1A0808) : const Color(0xFF161B22),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isExpired ? const Color(0xFFF85149).withOpacity(0.3) : const Color(0xFF21262D))),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            // Score circle
            Container(
              width: 50, height: 50,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: const Color(0xFF0A0C10),
                border: Border.all(color: scoreColor, width: 2)),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(score.toStringAsFixed(0),
                    style: TextStyle(
                      color: scoreColor,
                      fontWeight: FontWeight.bold, fontSize: 14)),
                  Text(label,
                    style: TextStyle(
                      color: scoreColor, fontSize: 7)),
                ])),
            const SizedBox(width: 12),

            // Job info
            Expanded(child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
              Text(ApiService.buildFilename(engine),
                maxLines: 1, overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  color: Color(0xFFC9D1D9), fontSize: 11,
                  fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Row(children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1A1500),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(
                      color: const Color(0xFFD4AF37).withOpacity(0.4))),
                  child: Text(engine, style: const TextStyle(
                    color: Color(0xFFD4AF37), fontSize: 9,
                    fontWeight: FontWeight.bold))),
                const SizedBox(width: 6),
                Text(displayTs, style: const TextStyle(
                  color: Color(0xFF8B949E), fontSize: 10)),
              ]),

              // Metrics if available
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
          ]),

          const SizedBox(height: 10),

          // Expired indicator OR re-download button
          if (isExpired)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 6),
              decoration: BoxDecoration(
                color: const Color(0xFF200D0D),
                borderRadius: BorderRadius.circular(8)),
              child: Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                const Icon(Icons.warning_amber_rounded,
                  color: Color(0xFFF85149), size: 14),
                const SizedBox(width: 6),
                Flexible(child: Text(s.jobExpired,
                  style: const TextStyle(
                    color: Color(0xFFF85149), fontSize: 11))),
                const SizedBox(width: 8),
                GestureDetector(
                  onTap: () => _removeJob(jobId),
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      border: Border.all(color: const Color(0xFFF85149).withOpacity(0.5)),
                      borderRadius: BorderRadius.circular(6)),
                    child: Text(s.ar ? 'حذف' : 'Remove',
                      style: const TextStyle(
                        color: Color(0xFFF85149), fontSize: 10)))),
              ]))
          else
            SizedBox(width: double.infinity,
              child: ElevatedButton.icon(
                onPressed: isLoading ? null : () => _reDownload(job),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF161B22),
                  foregroundColor: const Color(0xFF3FB950),
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  side: const BorderSide(color: Color(0xFF3FB950), width: 0.8),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(8)),
                  elevation: 0),
                icon: isLoading
                  ? const SizedBox(width: 14, height: 14,
                      child: CircularProgressIndicator(
                        strokeWidth: 1.5,
                        color: Color(0xFF3FB950)))
                  : const Icon(Icons.download_rounded, size: 16),
                label: Text(isLoading
                  ? (s.ar ? 'جارٍ التحميل...' : 'Downloading...')
                  : s.reDownload,
                  style: const TextStyle(fontSize: 12)))),
        ]),
      ),
    );
  }
}
