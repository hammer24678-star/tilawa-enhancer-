import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart'; // S30-P8
import '../design/nur.dart';
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
    final p = NurPalette.of(context);

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
          style: TextStyle(fontSize: 12, color: p.text),
        ),
        backgroundColor: p.surface,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 8),
        action: SnackBarAction(
          label: s.ar ? 'حسناً' : 'OK',
          textColor: p.ok,
          onPressed: () {},
        ),
      ));
    } else if (error == 'JOB_EXPIRED') {
      setState(() => _expired.add(jobId));
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(s.jobExpired,
          style: TextStyle(fontSize: 12, color: p.text)),
        backgroundColor: p.surface,
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 5),
        action: SnackBarAction(
          label: s.ar ? 'حذف' : 'Remove',
          textColor: p.err,
          onPressed: () => _removeJob(jobId),
        ),
      ));
    } else {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(
          s.ar ? '❌ فشل التحميل\n$error' : '❌ Download failed\n$error',
          style: TextStyle(fontSize: 12, color: p.text),
        ),
        backgroundColor: p.surface,
        behavior: SnackBarBehavior.floating,
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
    final ok = await showDialog<bool>(
      context: context,
      builder: (dCtx) {
        final p = NurPalette.of(dCtx);
        return Directionality(
          textDirection: s.ar ? TextDirection.rtl : TextDirection.ltr,
          child: AlertDialog(
            title: Row(children: [
              Icon(Icons.delete_sweep_rounded, color: p.err, size: 22),
              const SizedBox(width: 10),
              Expanded(child: Text(s.clearAll,
                style: TextStyle(color: p.gold, fontWeight: FontWeight.w800))),
            ]),
            content: Text(s.clearAllConfirm,
              style: TextStyle(color: p.textSub, height: 1.5)),
            backgroundColor: p.surface,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(24),
              side: BorderSide(color: p.border)),
            actions: [
              TextButton(onPressed: () => Navigator.pop(dCtx, false),
                child: Text(s.ar ? 'إلغاء' : 'Cancel',
                  style: TextStyle(color: p.textSub))),
              ElevatedButton(
                onPressed: () => Navigator.pop(dCtx, true),
                style: ElevatedButton.styleFrom(
                  backgroundColor: p.err,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12))),
                child: Text(s.clearAll,
                  style: const TextStyle(
                    color: Colors.white, fontWeight: FontWeight.bold))),
            ]));
      });
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
        AnimatedSwitcher(
          duration: const Duration(milliseconds: 300),
          transitionBuilder: (child, anim) =>
              ScaleTransition(scale: anim, child: child),
          child: _jobs.isNotEmpty
            ? Padding(
                key: const ValueKey<String>('clear'),
                padding: const EdgeInsetsDirectional.only(start: 8),
                child: NurIconButton(
                  icon: Icons.delete_sweep_rounded,
                  color: p.err,
                  tooltip: s.clearAll,
                  onTap: _clearAll))
            : const SizedBox(key: ValueKey<String>('none'), width: 0, height: 0)),
      ],
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 350),
        child: _loading
          ? Center(
              key: const ValueKey<String>('loading'),
              child: CircularProgressIndicator(color: p.gold))
          : _jobs.isEmpty
            ? _EmptyState(
                key: const ValueKey<String>('empty'),
                title: s.noHistory,
                subtitle: s.ar
                  ? 'الملفات المعالجة ستظهر هنا'
                  : 'Processed files will appear here')
            : RefreshIndicator(
                key: const ValueKey<String>('list'),
                onRefresh: _load,
                color: p.gold,
                child: ListView.builder(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(16, 0, 16, 32),
                  itemCount: _jobs.length + 1,
                  itemBuilder: (_, i) {
                    if (i == 0) {
                      return NurSectionHeader(
                        s.historyTitle,
                        padding: const EdgeInsets.fromLTRB(4, 14, 4, 12),
                        trailing: NurChip(
                          label: '${_jobs.length}',
                          color: p.gold,
                          icon: Icons.audio_file_rounded,
                          filled: true));
                    }
                    final job = _jobs[i - 1];
                    return EntranceFade(
                      key: ValueKey<Object?>(job['job_id']),
                      index: i - 1,
                      child: _jobCard(job, s, p));
                  }))),
    );
  }

  Widget _jobCard(Map<String, dynamic> job, S s, NurPalette p) {
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

    final scoreColor = score >= 90 ? p.ok
        : score >= 80 ? p.gold
        : p.err;

    final metrics = [
      if (job['lufs']  != null) 'LUFS ${job['lufs']}',
      if (job['crest'] != null) 'Crest ${job['crest']}',
      if (job['lra']   != null) 'LRA ${job['lra']}',
    ];

    return Dismissible(
      key: Key(jobId),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: AlignmentDirectional.centerEnd,
        padding: const EdgeInsetsDirectional.only(end: 22),
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: p.err.withValues(alpha: 0.16),
          borderRadius: BorderRadius.circular(22)),
        child: Icon(Icons.delete_outline_rounded, color: p.err)),
      onDismissed: (_) => _removeJob(jobId),
      child: Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: NurCard(
          accent: isExpired ? p.err : scoreColor,
          glow: !isExpired && score >= 90,
          padding: const EdgeInsets.all(14),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Row(children: [
              _ScoreRing(score: score, color: scoreColor, track: p.border),
              const SizedBox(width: 14),
              Expanded(child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // S28-T2: show original source name if stored, else fall back
                  Text(
                    job['original_name'] as String?
                      ?? ApiService.buildFilename(engine),
                    maxLines: 1, overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      color: p.text, fontSize: 13.5,
                      fontWeight: FontWeight.w800)),
                  const SizedBox(height: 8),
                  Wrap(spacing: 6, runSpacing: 6, children: [
                    NurChip(label: engine, color: p.gold, fontSize: 10),
                    NurChip(
                      label: displayTs,
                      color: p.textSub,
                      icon: Icons.schedule_rounded,
                      fontSize: 10),
                    NurChip(label: label, color: scoreColor, fontSize: 10),
                  ]),
                  if (metrics.isNotEmpty)
                    Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Text(metrics.join('  ·  '),
                        style: TextStyle(color: p.textDim, fontSize: 10.5))),
                ])),
            ]),
            const SizedBox(height: 12),
            AnimatedSize(
              duration: const Duration(milliseconds: 320),
              curve: Curves.easeOutCubic,
              alignment: Alignment.topCenter,
              child: AnimatedSwitcher(
                duration: const Duration(milliseconds: 280),
                child: isExpired
                  ? _expiredPanel(jobId, s, p)
                  : NurButton(
                      key: const ValueKey<String>('dl'),
                      label: isLoading
                        ? (s.ar ? 'جارٍ التحميل...' : 'Downloading...')
                        : s.reDownload,
                      icon: Icons.download_rounded,
                      filled: false,
                      accent: p.ok,
                      height: 44,
                      loading: isLoading,
                      onTap: isLoading ? null : () => _reDownload(job)))),
          ])),
      ),
    );
  }

  // Expired indicator
  Widget _expiredPanel(String jobId, S s, NurPalette p) {
    return Container(
      key: const ValueKey<String>('expired'),
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: p.err.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: p.err.withValues(alpha: 0.35))),
      child: Row(children: [
        Icon(Icons.warning_amber_rounded, color: p.err, size: 18),
        const SizedBox(width: 8),
        Expanded(child: Text(s.jobExpired,
          style: TextStyle(color: p.err, fontSize: 11.5, height: 1.3))),
        const SizedBox(width: 8),
        PressScale(
          onTap: () => _removeJob(jobId),
          child: NurChip(
            label: s.ar ? 'حذف' : 'Remove',
            color: p.err,
            icon: Icons.delete_outline_rounded,
            filled: true)),
      ]));
  }
}

/// Circular score gauge that sweeps to its value and counts up.
class _ScoreRing extends StatelessWidget {
  final double score;
  final Color color;
  final Color track;
  const _ScoreRing({
    required this.score, required this.color, required this.track});

  @override
  Widget build(BuildContext context) {
    final frac = (score / 100).clamp(0.0, 1.0);
    return SizedBox(
      width: 58, height: 58,
      child: Stack(alignment: Alignment.center, children: [
        TweenAnimationBuilder<double>(
          tween: Tween<double>(begin: 0, end: frac),
          duration: const Duration(milliseconds: 900),
          curve: Curves.easeOutCubic,
          builder: (_, v, __) => SizedBox(
            width: 58, height: 58,
            child: CircularProgressIndicator(
              value: v,
              strokeWidth: 4,
              strokeCap: StrokeCap.round,
              backgroundColor: track,
              color: color))),
        AnimatedCount(
          value: score,
          style: TextStyle(
            color: color, fontWeight: FontWeight.w800, fontSize: 15)),
      ]));
  }
}

/// Empty state: a softly breathing orb of rings around a history glyph.
class _EmptyState extends StatefulWidget {
  final String title;
  final String subtitle;
  const _EmptyState({super.key, required this.title, required this.subtitle});
  @override
  State<_EmptyState> createState() => _EmptyStateState();
}

class _EmptyStateState extends State<_EmptyState>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(
      vsync: this, duration: const Duration(seconds: 4))..repeat();

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final p = NurPalette.of(context);
    return Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          EntranceFade(
            child: SizedBox(
              width: 150, height: 150,
              child: AnimatedBuilder(
                animation: _c,
                builder: (_, __) {
                  final t = _c.value;
                  final breathe = 0.5 + 0.5 * math.sin(t * 2 * math.pi);
                  return Stack(alignment: Alignment.center, children: [
                    for (var k = 0; k < 2; k++)
                      Builder(builder: (_) {
                        final ph = (t + k * 0.5) % 1.0;
                        final d = 84 + 66 * ph;
                        return Container(
                          width: d, height: d,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            border: Border.all(
                              color: p.gold.withValues(alpha: 0.35 * (1 - ph)),
                              width: 1.5)));
                      }),
                    Container(
                      width: 84 + 6 * breathe, height: 84 + 6 * breathe,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: RadialGradient(
                          colors: [p.surfaceHi, p.surface]),
                        border: Border.all(
                          color: p.gold.withValues(alpha: 0.45)),
                        boxShadow: [BoxShadow(
                          color: p.gold.withValues(alpha: 0.12 + 0.12 * breathe),
                          blurRadius: 28)]),
                      child: Icon(Icons.history_rounded,
                        color: p.gold, size: 38)),
                  ]);
                }))),
          const SizedBox(height: 22),
          EntranceFade(
            index: 1,
            child: GradientText(widget.title,
              gradient: p.goldGradient,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 18, fontWeight: FontWeight.w800))),
          const SizedBox(height: 8),
          EntranceFade(
            index: 2,
            child: Text(widget.subtitle,
              textAlign: TextAlign.center,
              style: TextStyle(color: p.textSub, fontSize: 12.5, height: 1.5))),
        ])));
  }
}
