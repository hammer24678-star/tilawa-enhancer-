import 'package:flutter/material.dart';
import '../main.dart' show ThemeProvider; // S31-F2c
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


  // S32: theme cache (see home_screen.dart for rationale)
  Color _tBg     = const Color(0xFF020D0C); // S46-HIST
  Color _tCard   = const Color(0xFF0F2420);
  Color _tBorder = const Color(0xFF1A4035);
  Color _tText   = const Color(0xFFC9D1D9);
  Color _tGold   = const Color(0xFFD4AF37);
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


  // ── S31-F2c / S32: theme color helpers ────────────────────────────────────
  bool  _isDark(BuildContext ctx)  => ThemeProvider.isDark(ctx);
  Color _cBg(BuildContext ctx)     => _isDark(ctx) ? const Color(0xFF020D0C) : const Color(0xFFFAF7EE); // S46-HIST-M
  Color _cCard(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFF0F2420) : const Color(0xFFF3EED9);
  Color _cBorder(BuildContext ctx) => _isDark(ctx) ? const Color(0xFF1A4035) : const Color(0xFFD4C99A);
  Color _cText(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFC9D1D9) : const Color(0xFF1A1400);
  Color _cSub(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF8B949E) : const Color(0xFF6B5E40);
  Color _cDim(BuildContext ctx)    => _isDark(ctx) ? const Color(0xFF484F58) : const Color(0xFF8B7B5A);
  Color _cGold(BuildContext ctx)   => _isDark(ctx) ? const Color(0xFFD4AF37) : const Color(0xFFB8941F);
  // S32-COLORS-APPLIED

  Future<void> _clearAll() async {
    final s = LangProvider.strings(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: Text(s.clearAll,
          style: const TextStyle(color: Color(0xFFD4AF37), fontWeight: FontWeight.bold)),
        content: Text(s.clearAllConfirm,
          style: const TextStyle(color: Color(0xFFE2CFA0))),
        backgroundColor: const Color(0xFF0C1E28),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: const Color(0xFF1B6B80).withOpacity(0.3))),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false),
            child: Text(s.ar ? 'إلغاء' : 'Cancel',
              style: const TextStyle(color: Color(0xFF8AACBA)))),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFD94040)),
            child: Text(s.clearAll,
              style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
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
    // S32: update theme cache
    _tBg = _cBg(context); _tCard = _cCard(context);
    _tBorder = _cBorder(context); _tText = _cText(context);
    _tGold = _cGold(context);
    final cBg = _tBg; final cGold = _tGold;
    return Scaffold(
      backgroundColor: cBg,
      appBar: AppBar(
        title: ShaderMask(
          shaderCallback: (b) => const LinearGradient(
            colors: [Color(0xFFD4AF37), Color(0xFFF0CF60)]).createShader(b),
          child: Text(s.historyTitle, style: const TextStyle(
            color: Colors.white, fontWeight: FontWeight.bold))),
        backgroundColor: cBg,
        iconTheme: IconThemeData(color: cGold),
        elevation: 0,
        actions: [
          if (_jobs.isNotEmpty)
            TextButton.icon(
              onPressed: _clearAll,
              icon: const Icon(Icons.delete_sweep_outlined,
                color: Color(0xFFD94040), size: 16),
              label: Text(s.clearAll,
                style: const TextStyle(
                  color: Color(0xFFD94040), fontSize: 12))),
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
              color: _tGold,
              child: ListView.builder(
                padding: const EdgeInsets.all(16),
                itemCount: _jobs.length,
                itemBuilder: (_, i) {
                  return TweenAnimationBuilder<double>(
                    key: ValueKey(_jobs[i]['job_id']),
                    tween: Tween(begin: 0.0, end: 1.0),
                    duration: Duration(
                      milliseconds: 280 + 55 * (i < 8 ? i : 8)),
                    curve: Curves.easeOutCubic,
                    builder: (_, val, child) => Opacity(
                      opacity: val,
                      child: Transform.translate(
                        offset: Offset(0, 16 * (1 - val)),
                        child: child)),
                    child: _jobCard(_jobs[i], s),
                  );
                })));
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
        : score >= 80 ? _tGold
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
          color: isExpired ? const Color(0xFF1A0808) : _tCard,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: isExpired ? const Color(0xFFF85149).withOpacity(0.3) : _tBorder)),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            // Score circle
            Container(
              width: 50, height: 50,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _tBg,
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
              // S28-T2: show original source name if stored, else fall back
              Text(
                job['original_name'] as String?
                  ?? ApiService.buildFilename(engine),
                maxLines: 1, overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  color: _tText, fontSize: 11, // S32-BUG7-FIX: theme-aware
                  fontWeight: FontWeight.bold)),
              const SizedBox(height: 4),
              Row(children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
                  decoration: BoxDecoration(
                    color: const Color(0xFF1A1500),
                    borderRadius: BorderRadius.circular(4),
                    border: Border.all(
                      color: _tGold.withOpacity(0.4))),
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
                  backgroundColor: _tCard,
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
