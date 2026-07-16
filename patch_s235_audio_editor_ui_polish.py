#!/usr/bin/env python3
"""
patch_s235_audio_editor_ui_polish.py — S235

Full UI polish pass on lib/screens/audio_editor_screen.dart. Rather than
touching each of the 7 tabs individually, this targets the SHARED helper
widgets every tab is built from (_card_, _slider, _knob, _toggle, _chip_,
_preset, _rackRow) plus the top-level chrome (_appBar, _fileBar,
_waveformSection, _transport, _tabBar, _tabBody) — so the polish cascades
to Trim/EQ/Effects/FX+/Studio/Merge/Export automatically.

Changes:
  • _appBar        — drop shadow for depth, bolder title
  • _fileBar       — circular icon badge, duration in its own pill
  • _waveformSection — sits on a proper elevated card instead of flush bg
  • _transport     — play button breathes (AnimatedScale) + haptic
  • _tabBar        — animated sliding gold/teal indicator instead of a
                     static per-tab border, active icon bumps in size
  • _tabBody       — cross-fades + slides between tabs (AnimatedSwitcher)
  • _card_         — shadow, circular icon badge, header divider
  • _slider        — bigger thumb, wider touch overlay, haptic tick on
                     drag-start (every knob/slider in every tab gets this
                     for free since they all route through here)
  • _knob          — value now shown in a pill/chip instead of plain text
  • _toggle        — row tints gold when the switch is on + haptic
  • _chip_         — soft shadow + haptic
  • _preset        — highlights the active EQ preset + haptic
  • _rackRow (FX+) — chevron rotates instead of swapping icons, and the
                     expand/collapse body animates in/out (AnimatedSize)
                     instead of popping instantly

No behavior/logic changes — every onChanged/onTap callback still fires
exactly the same way; this is purely visual + haptic polish.

Usage: python3 patch_s235_audio_editor_ui_polish.py /path/to/tilawa-enhancer
"""
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
STAMP = REPO / '.patch_s235_audio_editor_ui_polish_done'

if STAMP.exists():
    print('patch_s235 already applied — delete .patch_s235_audio_editor_ui_polish_done to re-run')
    sys.exit(0)

APPLIED = []
SKIPPED = []
FAILED = []


def apply_fix(rel_path: str, label: str, old: str, new: str):
    fp = REPO / rel_path
    if not fp.exists():
        msg = f'{rel_path}: FILE NOT FOUND — skipping [{label}]'
        print('  --  ' + msg)
        FAILED.append(msg)
        return
    src = fp.read_text(encoding='utf-8')
    count = src.count(old)
    if count == 0:
        if new in src:
            print(f'  --  {rel_path}: SKIP [{label}] — already applied')
            SKIPPED.append(f'{rel_path}: {label}')
        else:
            msg = f'{rel_path}: anchor text not found for [{label}] — file may have changed, skipping'
            print('  --  ' + msg)
            FAILED.append(msg)
        return
    if count > 1:
        msg = f'{rel_path}: anchor text for [{label}] appears {count} times (expected 1) — skipping to be safe'
        print('  --  ' + msg)
        FAILED.append(msg)
        return
    fp.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK  {rel_path}: applied [{label}]')
    APPLIED.append(f'{rel_path}: {label}')


F = 'lib/screens/audio_editor_screen.dart'

# ═══════════════════════════════════════════════════════════════════════════
# 1. _appBar — drop shadow + bolder title
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_appBar: shadow + bolder title',
    old='''    return Container(
      decoration: BoxDecoration(color: _surface,
        border: Border(bottom: BorderSide(color: _gold.withValues(alpha: 0.25), width: 1))),
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child: Row(children: [
        IconButton(icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: _textB),
          onPressed: () => _busy ? _warnBusy() : Navigator.pop(context)),
        Expanded(child: ShaderMask(
          shaderCallback: (b) => const LinearGradient(colors: [_gold, Color(0xFFF0CF60)]).createShader(b),
          child: Text(ar ? 'محرر الصوت' : 'Audio Editor',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w700)))),''',
    new='''    return Container(
      decoration: BoxDecoration(color: _surface,
        border: Border(bottom: BorderSide(color: _gold.withValues(alpha: 0.25), width: 1)),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.25),
            blurRadius: 10, offset: const Offset(0, 3))]),
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 8),
      child: Row(children: [
        IconButton(icon: const Icon(Icons.arrow_back_ios_new_rounded, size: 18, color: _textB),
          onPressed: () => _busy ? _warnBusy() : Navigator.pop(context)),
        Expanded(child: ShaderMask(
          shaderCallback: (b) => const LinearGradient(colors: [_gold, Color(0xFFF0CF60)]).createShader(b),
          child: Text(ar ? 'محرر الصوت' : 'Audio Editor',
              textAlign: TextAlign.center,
              style: const TextStyle(color: Colors.white, fontSize: 17, fontWeight: FontWeight.w800)))),''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 2. _fileBar — icon badge + duration pill
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_fileBar: icon badge + duration pill',
    old='''  Widget _fileBar() => Container(
    color: _surface,
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
    child: Row(children: [
      const Icon(Icons.music_note_rounded, color: _teal, size: 16),
      const SizedBox(width: 8),
      Expanded(child: Text(_fileName, overflow: TextOverflow.ellipsis,
          style: const TextStyle(color: _textA, fontSize: 13, fontWeight: FontWeight.w500))),
      const SizedBox(width: 10),
      Text(_fmtTime(_durationSec),
          style: const TextStyle(color: _textB, fontSize: 12, fontFamily: 'monospace')),
    ]));''',
    new='''  Widget _fileBar() => Container(
    decoration: BoxDecoration(color: _surface,
        border: Border(bottom: BorderSide(color: _border.withValues(alpha: 0.6)))),
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 9),
    child: Row(children: [
      Container(width: 26, height: 26, alignment: Alignment.center,
        decoration: BoxDecoration(shape: BoxShape.circle,
            color: _teal.withValues(alpha: 0.14),
            border: Border.all(color: _teal.withValues(alpha: 0.4))),
        child: const Icon(Icons.music_note_rounded, color: _teal, size: 14)),
      const SizedBox(width: 10),
      Expanded(child: Text(_fileName, overflow: TextOverflow.ellipsis,
          style: const TextStyle(color: _textA, fontSize: 13, fontWeight: FontWeight.w600))),
      const SizedBox(width: 10),
      Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(8),
            border: Border.all(color: _border)),
        child: Text(_fmtTime(_durationSec),
            style: const TextStyle(color: _textB, fontSize: 11.5, fontFamily: 'monospace'))),
    ]));''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 3. _waveformSection — elevated card instead of flush background
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_waveformSection: elevated card wrapper',
    old='''  Widget _waveformSection() {
    final pos = _durationSec > 0 ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0.0;
    return GestureDetector(
      onTapDown: (d) {
        final box = context.findRenderObject() as RenderBox?;
        if (box == null) return;
        final frac = (d.localPosition.dx / box.size.width).clamp(0.0, 1.0);
        _player.seek(Duration(milliseconds: (frac * _durationSec * 1000).round()));
        setState(() => _positionSec = frac * _durationSec);
      },
      child: AnimatedBuilder(animation: _waveCtrl,
        builder: (_, __) => SizedBox(height: 96,
          child: CustomPaint(
            painter: _WavePainter(bars: _bars, playPos: pos,
              trimStart: _trimStart, trimEnd: _trimEnd,
              animT: _waveCtrl.value, playing: _playing),
            size: const Size(double.infinity, 96)))));
  }''',
    new='''  Widget _waveformSection() {
    final pos = _durationSec > 0 ? (_positionSec / _durationSec).clamp(0.0, 1.0) : 0.0;
    return Container(
      margin: const EdgeInsets.fromLTRB(10, 8, 10, 4),
      padding: const EdgeInsets.symmetric(vertical: 6),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _border),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.22),
              blurRadius: 12, offset: const Offset(0, 5))]),
      child: ClipRRect(borderRadius: BorderRadius.circular(10),
        child: GestureDetector(
          onTapDown: (d) {
            final box = context.findRenderObject() as RenderBox?;
            if (box == null) return;
            final frac = (d.localPosition.dx / box.size.width).clamp(0.0, 1.0);
            _player.seek(Duration(milliseconds: (frac * _durationSec * 1000).round()));
            setState(() => _positionSec = frac * _durationSec);
          },
          child: AnimatedBuilder(animation: _waveCtrl,
            builder: (_, __) => SizedBox(height: 92,
              child: CustomPaint(
                painter: _WavePainter(bars: _bars, playPos: pos,
                  trimStart: _trimStart, trimEnd: _trimEnd,
                  animT: _waveCtrl.value, playing: _playing),
                size: const Size(double.infinity, 92)))))));
  }''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 4. _transport — play button breathes + haptic
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_transport: play button AnimatedScale + haptic',
    old='''      AnimatedBuilder(animation: _glowCtrl,
        builder: (_, __) => GestureDetector(onTap: _togglePlay,
          child: Container(width: 52, height: 52,
            decoration: BoxDecoration(shape: BoxShape.circle,
              gradient: const RadialGradient(colors: [Color(0xFFB8921E), _goldDim]),
              boxShadow: [BoxShadow(
                  color: _gold.withValues(alpha: _playing ? 0.15 + 0.2 * _glowCtrl.value : 0.05),
                  blurRadius: 18)]),
            child: Icon(_playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
              color: const Color(0xFF050A06), size: 28)))),''',
    new='''      AnimatedBuilder(animation: _glowCtrl,
        builder: (_, __) => GestureDetector(
          onTap: () { HapticFeedback.mediumImpact(); _togglePlay(); },
          child: AnimatedScale(duration: const Duration(milliseconds: 200),
            scale: _playing ? 1.06 : 1.0,
            child: Container(width: 54, height: 54,
              decoration: BoxDecoration(shape: BoxShape.circle,
                gradient: const RadialGradient(colors: [Color(0xFFB8921E), _goldDim]),
                boxShadow: [BoxShadow(
                    color: _gold.withValues(alpha: _playing ? 0.2 + 0.22 * _glowCtrl.value : 0.08),
                    blurRadius: 20)]),
              child: Icon(_playing ? Icons.pause_rounded : Icons.play_arrow_rounded,
                color: const Color(0xFF050A06), size: 28))))),''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 5. _tabBar — animated sliding indicator + icon bump
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_tabBar: sliding indicator + icon bump',
    old='''  Widget _tabBar() {
    final ar = LangProvider.strings(context).ar;
    final labels = ar ? ['قص','EQ','تأثيرات','FX+','استوديو','دمج','تصدير']
                      : ['Trim','EQ','Effects','FX+','Studio','Merge','Export'];
    final icons = [Icons.content_cut_rounded, Icons.equalizer_rounded,
                   Icons.auto_fix_high_rounded, Icons.graphic_eq_rounded, Icons.science_rounded,
                   Icons.merge_type_rounded, Icons.ios_share_rounded];
    return Container(
      decoration: BoxDecoration(color: _surface, border: Border(bottom: BorderSide(color: _border))),
      child: Row(children: _Tab.values.map((t) {
        final active = t == _tab;
        return Expanded(child: GestureDetector(
          onTap: () { HapticFeedback.selectionClick(); setState(() => _tab = t); },
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(border: Border(bottom: BorderSide(
                color: active ? _gold : Colors.transparent, width: 2))),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(icons[t.index], color: active ? _gold : _textDim, size: 19),
              const SizedBox(height: 3),
              Text(labels[t.index], style: TextStyle(
                  color: active ? _gold : _textDim,
                  fontSize: 10, fontWeight: FontWeight.w600)),
            ]))));
      }).toList()));
  }''',
    new='''  Widget _tabBar() {
    final ar = LangProvider.strings(context).ar;
    final labels = ar ? ['قص','EQ','تأثيرات','FX+','استوديو','دمج','تصدير']
                      : ['Trim','EQ','Effects','FX+','Studio','Merge','Export'];
    final icons = [Icons.content_cut_rounded, Icons.equalizer_rounded,
                   Icons.auto_fix_high_rounded, Icons.graphic_eq_rounded, Icons.science_rounded,
                   Icons.merge_type_rounded, Icons.ios_share_rounded];
    final n = _Tab.values.length;
    return Container(
      decoration: BoxDecoration(color: _surface, border: Border(bottom: BorderSide(color: _border)),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.15),
              blurRadius: 6, offset: const Offset(0, 3))]),
      child: Stack(children: [
        AnimatedAlign(
          duration: const Duration(milliseconds: 220), curve: Curves.easeOutCubic,
          alignment: Alignment(-1 + 2 * _tab.index / (n - 1), 1),
          child: FractionallySizedBox(widthFactor: 1 / n,
            child: Container(height: 2.4, margin: const EdgeInsets.symmetric(horizontal: 2),
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [_teal, _gold]),
                borderRadius: BorderRadius.circular(2)))),
        ),
        Row(children: _Tab.values.map((t) {
          final active = t == _tab;
          return Expanded(child: GestureDetector(
            onTap: () { HapticFeedback.selectionClick(); setState(() => _tab = t); },
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 10),
              child: Column(mainAxisSize: MainAxisSize.min, children: [
                AnimatedScale(duration: const Duration(milliseconds: 180),
                  scale: active ? 1.12 : 1.0,
                  child: Icon(icons[t.index], color: active ? _gold : _textDim, size: 19)),
                const SizedBox(height: 3),
                Text(labels[t.index], style: TextStyle(
                    color: active ? _gold : _textDim,
                    fontSize: 10, fontWeight: active ? FontWeight.w800 : FontWeight.w600)),
              ]))));
        }).toList()),
      ]));
  }''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 6. _tabBody — cross-fade + slide between tabs
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_tabBody: AnimatedSwitcher cross-fade',
    old='''  Widget _tabBody() {
    switch (_tab) {
      case _Tab.trim:    return _trimTab();
      case _Tab.eq:      return _eqTab();
      case _Tab.effects: return _effectsTab();
      case _Tab.fx2:     return _fx2Tab();
      case _Tab.studio:  return _studioTab();
      case _Tab.merge:   return _mergeTab();
      case _Tab.export_: return _exportTab();
    }
  }''',
    new='''  Widget _tabBody() {
    late final Widget child;
    switch (_tab) {
      case _Tab.trim:    child = _trimTab(); break;
      case _Tab.eq:      child = _eqTab(); break;
      case _Tab.effects: child = _effectsTab(); break;
      case _Tab.fx2:     child = _fx2Tab(); break;
      case _Tab.studio:  child = _studioTab(); break;
      case _Tab.merge:   child = _mergeTab(); break;
      case _Tab.export_: child = _exportTab(); break;
    }
    return AnimatedSwitcher(
      duration: const Duration(milliseconds: 220),
      transitionBuilder: (c, anim) => FadeTransition(opacity: anim,
          child: SlideTransition(
              position: Tween<Offset>(begin: const Offset(0, 0.02), end: Offset.zero).animate(anim),
              child: c)),
      child: KeyedSubtree(key: ValueKey(_tab), child: child),
    );
  }''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 7. _card_ — shadow + icon badge + header divider
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_card_: shadow + icon badge + divider',
    old='''  Widget _card_(String title, IconData icon, List<Widget> body) =>
    Container(padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(14),
          border: Border.all(color: _border, width: 1)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(icon, color: _teal, size: 15), const SizedBox(width: 7),
          Text(title, style: const TextStyle(color: _textB, fontSize: 12,
              fontWeight: FontWeight.w700, letterSpacing: 0.3)),
        ]),
        const SizedBox(height: 12),
        ...body,
      ]));''',
    new='''  Widget _card_(String title, IconData icon, List<Widget> body) =>
    Container(padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _border, width: 1),
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.18),
              blurRadius: 14, offset: const Offset(0, 6))]),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(width: 26, height: 26, alignment: Alignment.center,
            decoration: BoxDecoration(shape: BoxShape.circle,
                color: _teal.withValues(alpha: 0.12),
                border: Border.all(color: _teal.withValues(alpha: 0.35))),
            child: Icon(icon, color: _teal, size: 14)),
          const SizedBox(width: 9),
          Expanded(child: Text(title, style: const TextStyle(color: _textA, fontSize: 12.5,
              fontWeight: FontWeight.w700, letterSpacing: 0.3))),
        ]),
        const SizedBox(height: 10),
        Divider(height: 1, color: _border.withValues(alpha: 0.7)),
        const SizedBox(height: 12),
        ...body,
      ]));''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 8. _slider — bigger thumb, wider overlay, haptic on drag start
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_slider: bigger thumb + haptic',
    old='''  Widget _slider(double val, double min, double max, Color color, ValueChanged<double> onChanged) =>
    Directionality(textDirection: TextDirection.ltr,
      child: SliderTheme(data: SliderThemeData(trackHeight: 4,
        thumbSize: WidgetStateProperty.all(const Size(16, 16)),
        thumbColor: color, activeTrackColor: color.withValues(alpha: 0.85),
        inactiveTrackColor: _border, overlayColor: color.withValues(alpha: 0.12)),
        child: Slider(value: val, min: min, max: max, onChanged: onChanged)));''',
    new='''  Widget _slider(double val, double min, double max, Color color, ValueChanged<double> onChanged) =>
    Directionality(textDirection: TextDirection.ltr,
      child: SliderTheme(data: SliderThemeData(trackHeight: 5,
        thumbSize: WidgetStateProperty.all(const Size(18, 18)),
        thumbColor: color, activeTrackColor: color.withValues(alpha: 0.9),
        inactiveTrackColor: _border, overlayColor: color.withValues(alpha: 0.15),
        overlayShape: const RoundSliderOverlayShape(overlayRadius: 18)),
        child: Slider(value: val, min: min, max: max, onChanged: onChanged,
            onChangeStart: (_) => HapticFeedback.selectionClick())));''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 9. _knob — value pill instead of plain text
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_knob: value pill',
    old='''  Widget _knob(String label, String valueStr, double val, double min, double max,
      ValueChanged<double> onChanged) =>
    Padding(padding: const EdgeInsets.only(bottom: 10),
      child: Row(children: [
        SizedBox(width: 90, child: Text(label, style: const TextStyle(color: _textB, fontSize: 12))),
        Expanded(child: _slider(val, min, max, _gold, onChanged)),
        SizedBox(width: 68, child: Text(valueStr, textAlign: TextAlign.end,
            style: const TextStyle(color: _gold, fontSize: 12, fontWeight: FontWeight.w700))),
      ]));''',
    new='''  Widget _knob(String label, String valueStr, double val, double min, double max,
      ValueChanged<double> onChanged) =>
    Padding(padding: const EdgeInsets.only(bottom: 12),
      child: Row(children: [
        SizedBox(width: 90, child: Text(label, style: const TextStyle(color: _textB, fontSize: 12))),
        Expanded(child: _slider(val, min, max, _gold, onChanged)),
        const SizedBox(width: 8),
        Container(
          constraints: const BoxConstraints(minWidth: 60),
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(color: _goldDim.withValues(alpha: 0.4),
              borderRadius: BorderRadius.circular(8),
              border: Border.all(color: _gold.withValues(alpha: 0.3))),
          child: Text(valueStr, textAlign: TextAlign.end,
              style: const TextStyle(color: _gold, fontSize: 11.5, fontWeight: FontWeight.w700,
                  fontFamily: 'monospace')),
        ),
      ]));''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 10. _chip_ — soft shadow + haptic
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_chip_: shadow + haptic',
    old='''  Widget _chip_(String label, VoidCallback onTap) =>
    GestureDetector(onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(color: _tealDk, borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _teal.withValues(alpha: 0.4))),
        child: Text(label, style: const TextStyle(color: _teal, fontSize: 11, fontWeight: FontWeight.w700))));''',
    new='''  Widget _chip_(String label, VoidCallback onTap) =>
    GestureDetector(onTap: () { HapticFeedback.selectionClick(); onTap(); },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(color: _tealDk, borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _teal.withValues(alpha: 0.45)),
            boxShadow: [BoxShadow(color: _teal.withValues(alpha: 0.12),
                blurRadius: 8, offset: const Offset(0, 3))]),
        child: Text(label, style: const TextStyle(color: _teal, fontSize: 11, fontWeight: FontWeight.w700))));''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 11. _preset — highlight active EQ preset + haptic
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_preset: active-state highlight + haptic',
    old='''  Widget _preset(String label, List<double> vals) =>
    GestureDetector(onTap: () => setState(() { for (int i = 0; i < 10; i++) _eq[i] = vals[i]; }),
      child: Container(
        margin: const EdgeInsets.only(right: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(color: _card, borderRadius: BorderRadius.circular(20),
            border: Border.all(color: _border)),
        child: Text(label, style: const TextStyle(color: _textB, fontSize: 11, fontWeight: FontWeight.w600))));''',
    new='''  Widget _preset(String label, List<double> vals) {
    final active = List.generate(10, (i) => (_eq[i] - vals[i]).abs() < 0.01).every((x) => x);
    return GestureDetector(
      onTap: () { HapticFeedback.selectionClick();
        setState(() { for (int i = 0; i < 10; i++) _eq[i] = vals[i]; }); },
      child: AnimatedContainer(duration: const Duration(milliseconds: 200),
        margin: const EdgeInsets.only(right: 8),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
            color: active ? _goldDim.withValues(alpha: 0.55) : _card,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: active ? _gold.withValues(alpha: 0.7) : _border)),
        child: Text(label, style: TextStyle(color: active ? _gold : _textB, fontSize: 11,
            fontWeight: FontWeight.w600))));
  }''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 12. _toggle — gold tint when on + haptic
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_toggle: on-state tint + haptic',
    old='''  Widget _toggle(String label, IconData icon, bool val, ValueChanged<bool> onChanged) =>
    Row(children: [
      Icon(icon, color: _textDim, size: 17), const SizedBox(width: 8),
      Expanded(child: Text(label, style: const TextStyle(color: _textB, fontSize: 13))),
      Switch(value: val, activeColor: _gold, inactiveThumbColor: _textDim,
        activeTrackColor: _goldDim, inactiveTrackColor: _border, onChanged: onChanged),
    ]);''',
    new='''  Widget _toggle(String label, IconData icon, bool val, ValueChanged<bool> onChanged) =>
    AnimatedContainer(duration: const Duration(milliseconds: 200),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: val ? _gold.withValues(alpha: 0.08) : Colors.transparent,
        borderRadius: BorderRadius.circular(10)),
      child: Row(children: [
        Icon(icon, color: val ? _gold : _textDim, size: 17), const SizedBox(width: 8),
        Expanded(child: Text(label, style: TextStyle(color: val ? _textA : _textB, fontSize: 13))),
        Switch(value: val, activeColor: _gold, inactiveThumbColor: _textDim,
          activeTrackColor: _goldDim, inactiveTrackColor: _border,
          onChanged: (v) { HapticFeedback.selectionClick(); onChanged(v); }),
      ]));''',
)

# ═══════════════════════════════════════════════════════════════════════════
# 13. _rackRow (FX+ tab) — rotating chevron + animated expand/collapse
# ═══════════════════════════════════════════════════════════════════════════

apply_fix(F, '_rackRow: animated expand/collapse + rotating chevron',
    old='''  Widget _rackRow({required String id, required String label, required String valueStr,
      required bool on, Widget? rightControl, Widget? body}) {
    final open = _fx2OpenId == id;
    final expandable = body != null;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: expandable ? () => setState(() => _fx2OpenId = open ? null : id) : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(padding: const EdgeInsets.symmetric(vertical: 12),
          child: Row(children: [
            _rackLamp(on),
            Expanded(child: Text(label, style: const TextStyle(color: _textA, fontSize: 13, fontWeight: FontWeight.w600))),
            Text(valueStr, style: TextStyle(color: on ? _gold : _textDim, fontSize: 11,
                fontFamily: 'monospace', fontWeight: FontWeight.w600)),
            const SizedBox(width: 10),
            rightControl ?? Icon(open ? Icons.keyboard_arrow_down_rounded : Icons.chevron_right_rounded,
                color: _textDim, size: 18),
          ])),
        if (open && body != null)
          Padding(padding: const EdgeInsets.only(bottom: 12), child: body),
      ]));
  }''',
    new='''  Widget _rackRow({required String id, required String label, required String valueStr,
      required bool on, Widget? rightControl, Widget? body}) {
    final open = _fx2OpenId == id;
    final expandable = body != null;
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTap: expandable ? () { HapticFeedback.selectionClick();
          setState(() => _fx2OpenId = open ? null : id); } : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Padding(padding: const EdgeInsets.symmetric(vertical: 12),
          child: Row(children: [
            _rackLamp(on),
            Expanded(child: Text(label, style: const TextStyle(color: _textA, fontSize: 13, fontWeight: FontWeight.w600))),
            Text(valueStr, style: TextStyle(color: on ? _gold : _textDim, fontSize: 11,
                fontFamily: 'monospace', fontWeight: FontWeight.w600)),
            const SizedBox(width: 10),
            rightControl ?? AnimatedRotation(duration: const Duration(milliseconds: 200),
                turns: open ? 0.25 : 0,
                child: const Icon(Icons.chevron_right_rounded, color: _textDim, size: 18)),
          ])),
        AnimatedSize(duration: const Duration(milliseconds: 220), curve: Curves.easeOutCubic,
          child: (open && body != null)
              ? Padding(padding: const EdgeInsets.only(bottom: 12), child: body)
              : const SizedBox(width: double.infinity, height: 0)),
      ]));
  }''',
)

# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════

print()
print(f'Applied: {len(APPLIED)}   Skipped: {len(SKIPPED)}   Failed: {len(FAILED)}')
if FAILED:
    print('\nSome fixes could not be applied — review the file manually:')
    for f in FAILED:
        print('  - ' + f)
    sys.exit(1)
else:
    STAMP.write_text('done\n')
    print('\nAll good — S235: Audio Editor UI polish applied across every tab.')
