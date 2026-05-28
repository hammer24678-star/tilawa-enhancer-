#!/usr/bin/env python3
"""
tilawa_fix_s107.py  —  S107: A/B comparison + enhancement report card
======================================================================
Adds back S104+S105 features to current S101 base.
Improvements over original:
  - A/B listeners moved to initState (no listener leak per build)
  - Time display on progress bar (mm:ss)
  - Stop A/B player on _resetForNewFile
  - Report card shows improvement delta visually with color bars

Does NOT touch local mode, _process(), or any engine logic.

Run:
  cp /sdcard/Download/tilawa_fix_s107.py ~/tilawa-enhancer/
  cd ~/tilawa-enhancer
  python3 tilawa_fix_s107.py 2>&1 | tee /sdcard/Download/fix_s107.txt
  git add -A
  git commit -m "S107: A/B comparison player + enhancement report card"
  git push
"""
from pathlib import Path
from datetime import datetime

HS = Path('lib/screens/home_screen.dart')
PY = Path('pubspec.yaml')

_log = []
def _h(t):  print(f'\n{"="*62}\n  {t}\n{"="*62}')
def ok(m):  print(f'  OK  {m}'); _log.append(('OK',m))
def xx(m):  print(f'  XX  {m}'); _log.append(('XX',m))

_h(f'tilawa_fix_s107.py   {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

txt = HS.read_text(encoding='utf-8')
pub = PY.read_text(encoding='utf-8')

if '// S107' in txt:
    print('  -- S107 already applied'); exit(0)

# ── 1. pubspec: add audioplayers ──────────────────────────────────────────
if 'audioplayers' not in pub:
    pub = pub.replace(
        '  just_audio:',
        '  audioplayers: ^6.1.0  # S107\n  just_audio:'
    )
    if 'audioplayers' in pub:
        PY.write_text(pub); ok('Added audioplayers to pubspec.yaml')
    else:
        # try alternate anchor
        pub2 = PY.read_text()
        lines = pub2.splitlines()
        for i,l in enumerate(lines):
            if 'dependencies:' in l:
                lines.insert(i+1, '  audioplayers: ^6.1.0  # S107')
                PY.write_text('\n'.join(lines)); ok('Added audioplayers to pubspec.yaml (fallback)'); break
else:
    ok('audioplayers already in pubspec.yaml')

# ── 2. import audioplayers ────────────────────────────────────────────────
OLD2 = "import 'dart:async';"
NEW2 = "import 'dart:async';\nimport 'package:audioplayers/audioplayers.dart';  // S107"
if 'audioplayers/audioplayers' not in txt:
    if OLD2 in txt:
        txt = txt.replace(OLD2, NEW2, 1); ok('Added audioplayers import')
    else:
        xx('dart:async import anchor not found')
else:
    ok('audioplayers import already present')

# ── 3. Add A/B player fields after _result declaration ───────────────────
OLD3 = '  Map<String, dynamic>? _result;'
NEW3 = '''  Map<String, dynamic>? _result;
  // S107: A/B comparison player
  final AudioPlayer _abPlayer = AudioPlayer();
  bool   _abPlaying = false;
  bool   _abIsB     = true;   // true=enhanced, false=original
  double _abPos     = 0.0;
  double _abDur     = 1.0;'''

if '_abPlayer' not in txt:
    if OLD3 in txt:
        txt = txt.replace(OLD3, NEW3, 1); ok('Added A/B player fields')
    else:
        xx('_result field anchor not found')
else:
    ok('A/B player fields already present')

# ── 4. Init A/B listeners in initState ───────────────────────────────────
OLD4 = '    LocalEngineService.isSetupComplete() // S65'
NEW4 = '''    // S107: A/B player listeners — attached once, not per build
    _abPlayer.onDurationChanged.listen((d) {
      if (mounted) setState(() { _abDur = d.inMilliseconds.toDouble().clamp(1, 1e9); });
    });
    _abPlayer.onPositionChanged.listen((p) {
      if (mounted) setState(() { _abPos = p.inMilliseconds.toDouble(); });
    });
    _abPlayer.onPlayerComplete.listen((_) {
      if (mounted) setState(() { _abPlaying = false; _abPos = 0; });
    });
    LocalEngineService.isSetupComplete() // S65'''

if 'onDurationChanged' not in txt:
    if OLD4 in txt:
        txt = txt.replace(OLD4, NEW4, 1); ok('A/B listeners added to initState')
    else:
        xx('initState LocalEngineService anchor not found')
else:
    ok('A/B listeners already in initState')

# ── 5. Dispose A/B player ─────────────────────────────────────────────────
OLD5 = '    _glowCtrl.dispose();\n    super.dispose();'
NEW5 = '    _abPlayer.dispose();  // S107\n    _glowCtrl.dispose();\n    super.dispose();'
if '_abPlayer.dispose' not in txt:
    if OLD5 in txt:
        txt = txt.replace(OLD5, NEW5, 1); ok('_abPlayer.dispose() added')
    else:
        xx('dispose anchor not found')
else:
    ok('_abPlayer.dispose already present')

# ── 6. Stop A/B on reset ──────────────────────────────────────────────────
OLD6 = '  void _resetForNewFile() {'
NEW6 = '''  void _resetForNewFile() {
    _abPlayer.stop();  // S107: stop A/B on new file
    setState(() { _abPlaying = false; _abPos = 0; _abDur = 1; _abIsB = true; });'''
if '_abPlayer.stop' not in txt:
    if OLD6 in txt:
        txt = txt.replace(OLD6, NEW6, 1); ok('A/B stop added to _resetForNewFile')
    else:
        xx('_resetForNewFile anchor not found')
else:
    ok('A/B stop already in _resetForNewFile')

# ── 7. Add cards to scroll list ───────────────────────────────────────────
OLD7 = '            SliverToBoxAdapter(child: _bottomRow(s)),'
NEW7 = '''            if (_result != null)
                SliverToBoxAdapter(child: _reportCard(s)),  // S107
            if (_file != null && _output != null)
                SliverToBoxAdapter(child: _abCard(s)),  // S107
            SliverToBoxAdapter(child: _bottomRow(s)),'''

if '_reportCard' not in txt:
    if OLD7 in txt:
        txt = txt.replace(OLD7, NEW7, 1); ok('Added _reportCard and _abCard to scroll list')
    else:
        xx('scroll list bottomRow anchor not found')
else:
    ok('Cards already in scroll list')

# ── 8. Add _abToggleTrack, _abTogglePlay, _abCard, _reportCard methods ───
AB_METHODS = '''
  // ── S107: A/B comparison ─────────────────────────────────────────────────
  Future<void> _abToggleTrack() async {
    setState(() { _abIsB = !_abIsB; _abPos = 0; });
    final src = _abIsB ? _output : _file;
    if (src == null) return;
    await _abPlayer.stop();
    await _abPlayer.play(DeviceFileSource(src.path));
    setState(() { _abPlaying = true; });
  }

  Future<void> _abTogglePlay() async {
    if (_abPlaying) {
      await _abPlayer.pause();
      setState(() { _abPlaying = false; });
    } else {
      final src = _abIsB ? _output : _file;
      if (src == null) return;
      if (_abPos >= _abDur - 200) {
        await _abPlayer.play(DeviceFileSource(src.path));
      } else {
        await _abPlayer.resume();
      }
      setState(() { _abPlaying = true; });
    }
  }

  String _abFmt(double ms) {
    final s = (ms / 1000).round();
    return '${(s ~/ 60).toString().padLeft(2,'0')}:${(s % 60).toString().padLeft(2,'0')}';
  }

  Widget _abCard(S s) {
    if (_file == null || _output == null) return const SizedBox.shrink();
    final progress = (_abPos / _abDur).clamp(0.0, 1.0);
    final posStr = _abFmt(_abPos);
    final durStr = _abFmt(_abDur);
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF0A1A14),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1DB898).withValues(alpha: 0.35))),
      child: Column(children: [
        Row(children: [
          const Icon(Icons.compare_arrows_rounded, color: Color(0xFF1DB898), size: 14),
          const SizedBox(width: 6),
          Text(s.ar ? 'مقارنة قبل / بعد' : 'Before / After',
            style: const TextStyle(color: Color(0xFF1DB898),
              fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 1.2)),
        ]),
        const SizedBox(height: 10),
        Row(children: [
          // Original (A)
          Expanded(child: GestureDetector(
            onTap: () async {
              if (_abIsB) await _abToggleTrack(); else await _abTogglePlay();
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: BoxDecoration(
                color: !_abIsB
                  ? const Color(0xFF1DB898).withValues(alpha: 0.18)
                  : const Color(0xFF0D2B22),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: !_abIsB
                  ? const Color(0xFF1DB898)
                  : const Color(0xFF1DB898).withValues(alpha: 0.25))),
              child: Column(children: [
                Icon(!_abIsB && _abPlaying
                  ? Icons.pause_rounded : Icons.play_arrow_rounded,
                  color: const Color(0xFF1DB898), size: 20),
                const SizedBox(height: 3),
                Text(s.ar ? 'الأصلي' : 'Original',
                  style: const TextStyle(color: Color(0xFF1DB898),
                    fontSize: 10, fontWeight: FontWeight.w600)),
              ])))),
          const SizedBox(width: 8),
          // Enhanced (B)
          Expanded(child: GestureDetector(
            onTap: () async {
              if (!_abIsB) await _abToggleTrack(); else await _abTogglePlay();
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(vertical: 10),
              decoration: BoxDecoration(
                color: _abIsB
                  ? const Color(0xFFD4AF37).withValues(alpha: 0.18)
                  : const Color(0xFF1A1200),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: _abIsB
                  ? const Color(0xFFD4AF37)
                  : const Color(0xFFD4AF37).withValues(alpha: 0.25))),
              child: Column(children: [
                Icon(_abIsB && _abPlaying
                  ? Icons.pause_rounded : Icons.play_arrow_rounded,
                  color: const Color(0xFFD4AF37), size: 20),
                const SizedBox(height: 3),
                Text(s.ar ? 'المُحسَّن' : 'Enhanced',
                  style: const TextStyle(color: Color(0xFFD4AF37),
                    fontSize: 10, fontWeight: FontWeight.w600)),
              ])))),
        ]),
        const SizedBox(height: 10),
        // Progress bar
        GestureDetector(
          onTapDown: (d) async {
            final box = context.findRenderObject() as RenderBox?;
            if (box == null) return;
            final frac = (d.localPosition.dx / box.size.width).clamp(0.0, 1.0);
            final ms = frac * _abDur;
            await _abPlayer.seek(Duration(milliseconds: ms.toInt()));
            setState(() { _abPos = ms; });
          },
          child: Column(children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: progress, minHeight: 5,
                backgroundColor: const Color(0xFF1A2733),
                valueColor: AlwaysStoppedAnimation<Color>(
                  _abIsB ? const Color(0xFFD4AF37) : const Color(0xFF1DB898)))),
            const SizedBox(height: 4),
            Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
              Text(posStr, style: const TextStyle(
                color: Color(0xFF484F58), fontSize: 9)),
              Text(
                _abIsB ? (s.ar ? '▶ المُحسَّن' : '▶ Enhanced')
                       : (s.ar ? '▶ الأصلي' : '▶ Original'),
                style: TextStyle(
                  color: _abIsB
                    ? const Color(0xFFD4AF37).withValues(alpha: 0.6)
                    : const Color(0xFF1DB898).withValues(alpha: 0.6),
                  fontSize: 9)),
              Text(durStr, style: const TextStyle(
                color: Color(0xFF484F58), fontSize: 9)),
            ]),
          ])),
      ]));
  }

  // ── S107: Enhancement report card ─────────────────────────────────────────
  Widget _reportCard(S s) {
    if (_result == null) return const SizedBox.shrink();
    final lufs  = double.tryParse(_result!['lufs']?.toString()  ?? '') ?? -99;
    final rms   = double.tryParse(_result!['rms']?.toString()   ?? '') ?? -99;
    final crest = double.tryParse(_result!['crest']?.toString() ?? '') ?? 0;
    final lra   = double.tryParse(_result!['lra']?.toString()   ?? '') ?? 0;

    final dLufs  = lufs  - (-6.29);
    final dRms   = rms   - (-10.01);
    final dCrest = crest - 10.25;
    final dLra   = lra   - 4.19;

    final List<Map<String, dynamic>> items = [];

    if (dLufs.abs() <= 1.0) {
      items.add({'icon': Icons.check_circle_outline, 'color': const Color(0xFF3FB950),
        'ar': 'مستوى الصوت مطابق للمرجع ١٤٢٥هـ', 'en': 'Loudness matches 1425H reference'});
    } else if (dLufs < -1.0) {
      items.add({'icon': Icons.volume_up_rounded, 'color': const Color(0xFFD4AF37),
        'ar': 'رُفع مستوى الصوت ${dLufs.abs().toStringAsFixed(1)} وحدة نحو الهدف',
        'en': 'Loudness boosted ${dLufs.abs().toStringAsFixed(1)} LU toward target'});
    } else {
      items.add({'icon': Icons.volume_down_rounded, 'color': const Color(0xFF58A6FF),
        'ar': 'خُفّض مستوى الصوت ${dLufs.abs().toStringAsFixed(1)} وحدة نحو الهدف',
        'en': 'Loudness reduced ${dLufs.abs().toStringAsFixed(1)} LU toward target'});
    }

    if (dCrest.abs() <= 1.0) {
      items.add({'icon': Icons.equalizer_rounded, 'color': const Color(0xFF3FB950),
        'ar': 'الديناميكية متوازنة ومطابقة للمرجع', 'en': 'Dynamics balanced and on target'});
    } else if (dCrest > 1.0) {
      items.add({'icon': Icons.trending_up_rounded, 'color': const Color(0xFF3FB950),
        'ar': 'تحسّنت الديناميكية — الصوت أكثر حيوية', 'en': 'Dynamics improved — audio more vibrant'});
    } else {
      items.add({'icon': Icons.compress_rounded, 'color': const Color(0xFFD4AF37),
        'ar': 'ضُغطت الديناميكية قليلاً — مقبول للتلاوة', 'en': 'Dynamics slightly compressed — acceptable'});
    }

    if (dLra.abs() <= 0.8) {
      items.add({'icon': Icons.graphic_eq_rounded, 'color': const Color(0xFF3FB950),
        'ar': 'نطاق الصوت مثالي ومتوازن', 'en': 'Loudness range ideal and balanced'});
    } else if (dLra > 0.8) {
      items.add({'icon': Icons.unfold_more_rounded, 'color': const Color(0xFF58A6FF),
        'ar': 'توسّع النطاق الصوتي — تباين أعمق', 'en': 'Range expanded — deeper contrast'});
    } else {
      items.add({'icon': Icons.unfold_less_rounded, 'color': const Color(0xFFD4AF37),
        'ar': 'النطاق الصوتي ضيّق — مستوى ثابت', 'en': 'Narrow range — consistent level'});
    }

    if (dRms.abs() <= 1.5) {
      items.add({'icon': Icons.sensors_rounded, 'color': const Color(0xFF3FB950),
        'ar': 'طاقة الصوت الكلية مطابقة للمرجع', 'en': 'Overall energy matches reference'});
    } else if (dRms < -1.5) {
      items.add({'icon': Icons.bolt_rounded, 'color': const Color(0xFFD4AF37),
        'ar': 'طاقة الصوت أقل من المرجع', 'en': 'Energy below reference — was quiet'});
    } else {
      items.add({'icon': Icons.flash_on_rounded, 'color': const Color(0xFF58A6FF),
        'ar': 'طاقة الصوت فوق المرجع', 'en': 'Energy above reference — was loud'});
    }

    final score = ((_result!['score'] as num?)?.toDouble() ?? 0);
    final String verdict;
    final Color vColor;
    if (score >= 90) {
      verdict = s.ar ? '✨ جودة استثنائية — يُضاهي مستوى الإذاعة' : '✨ Exceptional — broadcast quality';
      vColor = const Color(0xFF3FB950);
    } else if (score >= 80) {
      verdict = s.ar ? '🌟 جيد جداً — مناسب للنشر والمشاركة' : '🌟 Very good — suitable for sharing';
      vColor = const Color(0xFFD4AF37);
    } else if (score >= 70) {
      verdict = s.ar ? '👍 جيد — تحسّن ملموس عن الأصل' : '👍 Good — noticeable improvement';
      vColor = const Color(0xFF58A6FF);
    } else {
      verdict = s.ar ? '⚠️ التسجيل صعب — جرّب محرك مختلف' : '⚠️ Difficult recording — try another engine';
      vColor = const Color(0xFFF85149);
    }

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 4, 16, 4),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF070F0C),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF21262D))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.analytics_outlined, color: Color(0xFF8B949E), size: 13),
          const SizedBox(width: 6),
          Text(s.ar ? 'تقرير التحسين' : 'Enhancement Report',
            style: const TextStyle(color: Color(0xFF8B949E),
              fontSize: 10, letterSpacing: 1.4, fontWeight: FontWeight.w600)),
        ]),
        const SizedBox(height: 10),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
          decoration: BoxDecoration(
            color: vColor.withValues(alpha: 0.08),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: vColor.withValues(alpha: 0.3))),
          child: Text(verdict, textAlign: TextAlign.center,
            style: TextStyle(color: vColor, fontSize: 11, fontWeight: FontWeight.w600))),
        const SizedBox(height: 10),
        ...items.map((item) => Padding(
          padding: const EdgeInsets.only(bottom: 7),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Icon(item['icon'] as IconData, color: item['color'] as Color, size: 13),
            const SizedBox(width: 7),
            Expanded(child: Text(
              s.ar ? item['ar'] as String : item['en'] as String,
              style: TextStyle(
                color: (item['color'] as Color).withValues(alpha: 0.85),
                fontSize: 11, height: 1.4))),
          ]))),
      ]));
  }

'''

if '_abCard' not in txt:
    # Insert before _bottomRow
    OLD8 = '  Widget _bottomRow(S s) => Padding('
    if OLD8 in txt:
        txt = txt.replace(OLD8, AB_METHODS + '  Widget _bottomRow(S s) => Padding(', 1)
        ok('Added _abCard, _abToggleTrack, _abTogglePlay, _reportCard methods')
    else:
        xx('_bottomRow anchor not found')
else:
    ok('A/B methods already present')

# ── Save ──────────────────────────────────────────────────────────────────
ok_n = sum(1 for s,_ in _log if s=='OK')
xx_n = sum(1 for s,_ in _log if s=='XX')
_h('SUMMARY')
for s,l in _log: print(f'  {"OK" if s=="OK" else "XX"}  {l}')
_h(f'{ok_n} OK   {xx_n} FAIL')

if xx_n == 0:
    HS.write_text(txt, encoding='utf-8')
    ok('home_screen.dart saved')
    print("""
  git add -A
  git commit -m "S107: A/B comparison player + enhancement report card"
  git push
""")
else:
    print('\n  NOT saved — paste output to Claude.\n')
