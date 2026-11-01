import 'package:flutter/material.dart';
import '../design/nur.dart';
import 'package:flutter/services.dart'; // S30-P8
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

    HapticFeedback.lightImpact(); // S30-P8
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


  Future<void> _clearAll() async {
    final s = LangProvider.strings(context);
    final p = NurPalette.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: p.surface,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
          side: BorderSide(color: p.border)),
        title: Text(s.clearAll,
          style: TextStyle(color: p.gold, fontWeight: FontWeight.w800)),
        content: Text(s.clearAllConfirm,
          style: TextStyle(color: p.textSub, height: 1.4)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: Text(s.ar ? 'إلغاء' : 'Cancel',
              style: TextStyle(color: p.textSub))),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: Text(s.clearAll,
              style: TextStyle(color: p.err, fontWeight: FontWeight.w800))),
        ]));
    if (ok == true && mounted) {
      await ApiService.clearAllJobRecords();
      if (!mounted) return; // S189
      setState(() => _jobs.clear());
    }
  }

  @override
  Widget build(BuildContext context) {
    final s = LangProvider.strings(context);
    final p = NurPalette.of(context);
    return NurScaffold(
      title: s.historyTitle,
      icon: Icons.history_rounded,
      actions: [
        if (_jobs.isNotEmpty)
          NurIconButton(
            icon: Icons.delete_sweep_outlined,
            color: p.err,
            tooltip: s.clearAll,
            onTap: _clearAll),
      ],
      body: _loading
        ? Center(child: CircularProgressIndicator(color: p.gold))
        : _jobs.isEmpty
          ? _empty(s, p)
          : RefreshIndicator(
              onRefresh: _load,
              color: p.gold,
              backgroundColor: p.surface,
              child: ListView.builder(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
                itemCount: _jobs.length,
                itemBuilder: (_, i) => EntranceFade(
                  key: ValueKey(_jobs[i]['job_id']),
                  index: i < 8 ? i : 8,
                  child: _jobCard(_jobs[i], s, p)))));
  }

  Widget _empty(S s, NurPalette p) => Center(
    child: EntranceFade(
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Container(
          width: 96, height: 96,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            gradient: RadialGradient(colors: [
              p.gold.withValues(alpha: 0.22), p.gold.withValues(alpha: 0.0)]),
            border: Border.all(color: p.border)),
          child: Icon(Icons.history_rounded, color: p.gold, size: 44)),
        const SizedBox(height: 18),
        Text(s.noHistory,
          style: TextStyle(
            color: p.text, fontSize: 17, fontWeight: FontWeight.w700)),
        const SizedBox(height: 6),
        Text(
          s.ar ? 'الملفات المعالجة ستظهر هنا' : 'Processed files will appear here',
          style: TextStyle(color: p.textDim, fontSize: 13)),
      ])));

  Widget _jobCard(Map<String, dynamic> job, S s, NurPalette p) {
    final jobId  = job['job_id'] as String;
    final score  = double.tryParse(job['score']?.toString() ?? '0') ?? 0.0;
    final engine = job['engine'] as String? ?? 'v8.0';
    final ts     = job['timestamp'] as String? ?? '';
    final isExpired = _expired.contains(jobId);
    final isLoading = _downloading.contains(jobId);

    String displayTs = ts;
    try {
      final dt = DateTime.parse(ts);
      displayTs =
        '${dt.day.toString().padLeft(2,'0')}/${dt.month.toString().padLeft(2,'0')} '
        '${dt.hour.toString().padLeft(2,'0')}:${dt.minute.toString().padLeft(2,'0')}';
    } catch (_) {}

    final label = score >= 96 ? s.excellent
        : score >= 90 ? s.great
        : score >= 85 ? s.good
        : score >= 78 ? s.decent
        : s.fair;

    final scoreColor = score >= 90 ? p.ok : score >= 80 ? p.gold : p.err;

    final metrics = [
      if (job['lufs']  != null) 'LUFS ${job['lufs']}',
      if (job['crest'] != null) 'Crest ${job['crest']}',
      if (job['lra']   != null) 'LRA ${job['lra']}',
    ].join('  ·  ');

    return Dismissible(
      key: Key(jobId),
      direction: DismissDirection.horizontal,
      background: _swipeBg(p, Alignment.centerLeft),
      secondaryBackground: _swipeBg(p, Alignment.centerRight),
      onDismissed: (_) => _removeJob(jobId),
      child: NurCard(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(14),
        radius: 20,
        accent: isExpired ? p.err : scoreColor,
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            // Score ring
            Container(
              width: 56, height: 56,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: p.bg,
                border: Border.all(
                  color: isExpired ? p.textDim : scoreColor, width: 2.2),
                boxShadow: [BoxShadow(
                  color: scoreColor.withValues(alpha: isExpired ? 0 : 0.28),
                  blurRadius: 14)]),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(score.toStringAsFixed(0),
                    style: TextStyle(
                      color: isExpired ? p.textDim : scoreColor,
                      fontWeight: FontWeight.w800, fontSize: 16, height: 1.0)),
                  Text(label,
                    maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: isExpired ? p.textDim : scoreColor, fontSize: 8)),
                ])),
            const SizedBox(width: 14),
            Expanded(child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  job['original_name'] as String?
                    ?? ApiService.buildFilename(engine),
                  maxLines: 1, overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    color: p.text, fontSize: 13, fontWeight: FontWeight.w700)),
                const SizedBox(height: 6),
                Row(children: [
                  NurChip(label: engine, color: p.gold, fontSize: 10),
                  const SizedBox(width: 8),
                  Flexible(child: Text(displayTs,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: p.textSub, fontSize: 11))),
                ]),
                if (metrics.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 5),
                    child: Text(metrics,
                      style: TextStyle(color: p.textDim, fontSize: 11))),
              ])),
          ]),
          const SizedBox(height: 12),
          if (isExpired)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
              decoration: BoxDecoration(
                color: p.err.withValues(alpha: 0.10),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: p.err.withValues(alpha: 0.35))),
              child: Row(children: [
                Icon(Icons.warning_amber_rounded, color: p.err, size: 16),
                const SizedBox(width: 8),
                Expanded(child: Text(s.jobExpired,
                  style: TextStyle(color: p.err, fontSize: 12))),
                const SizedBox(width: 8),
                GestureDetector(
                  onTap: () => _removeJob(jobId),
                  child: NurChip(
                    label: s.ar ? 'حذف' : 'Remove', color: p.err, fontSize: 10)),
              ]))
          else
            NurButton(
              label: isLoading
                ? (s.ar ? 'جارٍ التحميل...' : 'Downloading...')
                : s.reDownload,
              icon: Icons.download_rounded,
              loading: isLoading,
              filled: false,
              accent: p.ok,
              height: 44,
              onTap: isLoading ? null : () => _reDownload(job)),
        ]),
      ),
    );
  }

  Widget _swipeBg(NurPalette p, Alignment al) => Container(
    alignment: al,
    padding: const EdgeInsets.symmetric(horizontal: 24),
    margin: const EdgeInsets.only(bottom: 12),
    decoration: BoxDecoration(
      color: p.err.withValues(alpha: 0.14),
      borderRadius: BorderRadius.circular(20)),
    child: Icon(Icons.delete_outline_rounded, color: p.err));
}
