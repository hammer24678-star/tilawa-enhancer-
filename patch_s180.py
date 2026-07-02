#!/usr/bin/env python3
"""
patch_s180.py — S180: fix reversed trim/EQ/effect sliders + add an
                       explanation dialog to the audio editor

  BUG (sliders feel reversed)
    audio_editor_screen.dart wraps the whole screen in
    Directionality(textDirection: TextDirection.rtl, ...) (always-Arabic
    UI, by design — not changed here). Flutter's Material Slider IS
    direction-aware: under ltr it fills/increases left→right, but under
    rtl it fills/increases right→left. Every Slider in this screen (trim
    start, trim end, the 5 EQ bands, and all the effect knobs — fade,
    pitch, tempo, echo, reverb, volume) inherits that ambient rtl and so
    drags the "wrong" way: dragging right *decreases* the value. That's
    what shows up as "reversed" sliders/animations.
      E1  _slider() helper (trim handles + effect knobs) — wrap in a
          nested ltr Directionality so magnitude/time controls behave
          intuitively (drag right = increase) regardless of the
          surrounding Arabic UI.
      E2  same fix for the inline EQ-band Slider in _eqTab().
      E3  same fix for the _knob() helper's Slider.

  ADD: explanation dialog
    No in-app explanation of what the editor's tabs/controls do.
      E4  _appBar() — add an info button that opens a short dialog
          explaining Trim / EQ / Effects / Export.

Run from repo root: python3 patch_s180.py
"""

import sys
from pathlib import Path

REPO = Path(__file__).parent

def fail(msg):
    print(f'  FAIL  {msg}'); sys.exit(1)

def patch(path, old, new, tag, required=True):
    p = Path(path)
    if not p.exists():
        if required: fail(f'{path} not found')
        print(f'  SKIP  {tag} ({path} not found)'); return
    src = p.read_text(encoding='utf-8')
    if new.strip() in src:
        print(f'  SKIP  {tag} (already applied)'); return
    if old not in src:
        if required: fail(f'{tag}: anchor not found in {path}')
        print(f'  WARN  {tag}: anchor not found in {path} — skipped (non-fatal)'); return
    p.write_text(src.replace(old, new, 1), encoding='utf-8')
    print(f'  OK    {tag}')

STAMP = Path('.patch_s180_done')
if STAMP.exists():
    print('patch_s180: already applied — delete .patch_s180_done to re-run'); sys.exit(0)

print('\n── S180: fix reversed sliders + add audio-editor explanation dialog ──')

F = 'lib/screens/audio_editor_screen.dart'

# ════════════════════════════════════════════════════════════════════════════
# E1 — _slider() helper: used for trim start/end + every effect knob's track.
# ════════════════════════════════════════════════════════════════════════════
patch(F,
    '''  Widget _slider(double v, double min, double max, Color c,
      ValueChanged<double> fn) =>
    SliderTheme(
      data: SliderThemeData(
        trackHeight: 4,
        thumbSize: WidgetStateProperty.all(const Size(18, 18)),
        thumbColor: c, activeTrackColor: c.withValues(alpha: 0.8),
        inactiveTrackColor: _border,
        overlayColor: c.withValues(alpha: 0.12)),
      child: Slider(value: v, min: min, max: max, onChanged: fn));''',
    '''  // S180: nested ltr Directionality — Slider is direction-aware and under
  // the screen's ambient rtl it fills/drags backwards (right = decrease).
  // Time/magnitude controls (trim, EQ, effects) should always drag
  // left→right = increase, regardless of the surrounding Arabic UI.
  Widget _slider(double v, double min, double max, Color c,
      ValueChanged<double> fn) =>
    Directionality(
      textDirection: TextDirection.ltr,
      child: SliderTheme(
        data: SliderThemeData(
          trackHeight: 4,
          thumbSize: WidgetStateProperty.all(const Size(18, 18)),
          thumbColor: c, activeTrackColor: c.withValues(alpha: 0.8),
          inactiveTrackColor: _border,
          overlayColor: c.withValues(alpha: 0.12)),
        child: Slider(value: v, min: min, max: max, onChanged: fn)));''',
    'E1: _slider() (trim handles + effect knobs) forced to ltr')

# ════════════════════════════════════════════════════════════════════════════
# E2 — inline EQ-band Slider in _eqTab()'s _card_('أحزمة التعديل', ...) list.
# ════════════════════════════════════════════════════════════════════════════
patch(F,
    '''                Expanded(child: SliderTheme(
                  data: SliderThemeData(
                    trackHeight: 3,
                    thumbSize: WidgetStateProperty.all(const Size(14, 14)),
                    thumbColor: c,
                    activeTrackColor: c.withValues(alpha: 0.75),
                    inactiveTrackColor: _border,
                    overlayColor: c.withValues(alpha: 0.12)),
                  child: Slider(value: v, min: -12, max: 12, divisions: 24,
                      onChanged: (val) => setState(() => _eq[i] = val)))),''',
    '''                Expanded(child: Directionality(  // S180: keep EQ bands ltr (see _slider)
                  textDirection: TextDirection.ltr,
                  child: SliderTheme(
                    data: SliderThemeData(
                      trackHeight: 3,
                      thumbSize: WidgetStateProperty.all(const Size(14, 14)),
                      thumbColor: c,
                      activeTrackColor: c.withValues(alpha: 0.75),
                      inactiveTrackColor: _border,
                      overlayColor: c.withValues(alpha: 0.12)),
                    child: Slider(value: v, min: -12, max: 12, divisions: 24,
                        onChanged: (val) => setState(() => _eq[i] = val))))),''',
    'E2: EQ-band Slider in _eqTab() forced to ltr')

# ════════════════════════════════════════════════════════════════════════════
# E3 — _knob() helper's Slider (used by fade/pitch/tempo/echo/reverb/volume).
# ════════════════════════════════════════════════════════════════════════════
patch(F,
    '''        const SizedBox(height: 2),
        SliderTheme(
          data: SliderThemeData(
            trackHeight: 3,
            thumbSize: WidgetStateProperty.all(const Size(14, 14)),
            thumbColor: _teal,
            activeTrackColor: _teal.withValues(alpha: 0.7),
            inactiveTrackColor: _border,
            overlayColor: _teal.withValues(alpha: 0.1)),
          child: Slider(value: v, min: min, max: max, onChanged: fn)),
      ]));''',
    '''        const SizedBox(height: 2),
        Directionality(  // S180: keep effect-knob sliders ltr (see _slider)
          textDirection: TextDirection.ltr,
          child: SliderTheme(
            data: SliderThemeData(
              trackHeight: 3,
              thumbSize: WidgetStateProperty.all(const Size(14, 14)),
              thumbColor: _teal,
              activeTrackColor: _teal.withValues(alpha: 0.7),
              inactiveTrackColor: _border,
              overlayColor: _teal.withValues(alpha: 0.1)),
            child: Slider(value: v, min: min, max: max, onChanged: fn))),
      ]));''',
    'E3: _knob() Slider forced to ltr')

# ════════════════════════════════════════════════════════════════════════════
# E4 — _appBar(): add an info button that explains the editor.
# ════════════════════════════════════════════════════════════════════════════
patch(F,
    '''    child: Row(children: [
      IconButton(
        icon: const Icon(Icons.arrow_back_ios_new_rounded,
            size: 18, color: _textB),
        onPressed: () => Navigator.pop(context)),
      const Expanded(child: Text('محرر الصوت',
          textAlign: TextAlign.center,
          style: TextStyle(color: _gold, fontSize: 17,
              fontWeight: FontWeight.w700, letterSpacing: 0.3))),
      if (_filePath != null)
        TextButton(
          onPressed: _pick,
          child: const Text('تغيير',
              style: TextStyle(color: _teal, fontSize: 12,
                  fontWeight: FontWeight.w600)))
      else
        const SizedBox(width: 48),
    ]),
  );''',
    '''    child: Row(children: [
      IconButton(
        icon: const Icon(Icons.arrow_back_ios_new_rounded,
            size: 18, color: _textB),
        onPressed: () => Navigator.pop(context)),
      const Expanded(child: Text('محرر الصوت',
          textAlign: TextAlign.center,
          style: TextStyle(color: _gold, fontSize: 17,
              fontWeight: FontWeight.w700, letterSpacing: 0.3))),
      IconButton(  // S180: explain what the editor's tabs/controls do
        icon: const Icon(Icons.info_outline_rounded,
            size: 18, color: _textB),
        onPressed: _showHelp),
      if (_filePath != null)
        TextButton(
          onPressed: _pick,
          child: const Text('تغيير',
              style: TextStyle(color: _teal, fontSize: 12,
                  fontWeight: FontWeight.w600)))
      else
        const SizedBox(width: 8),
    ]),
  );

  // S180: quick explanation of the editor — trim/EQ/effects/export.
  void _showHelp() => showDialog(
    context: context,
    builder: (_) => Directionality(
      textDirection: TextDirection.rtl,
      child: AlertDialog(
        backgroundColor: _card,
        shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(14),
            side: const BorderSide(color: _gold, width: 0.7)),
        title: const Text('عن محرر الصوت',
            style: TextStyle(color: _gold, fontWeight: FontWeight.w700)),
        content: const Text(
          '• القص: اسحب البداية والنهاية لاختيار الجزء المطلوب من التسجيل.\\n'
          '• الموازن (EQ): تحكم بمستوى كل نطاق تردد لتغيير طابع الصوت.\\n'
          '• المؤثرات: تلاشي الدخول/الخروج، طبقة الصوت، السرعة، الصدى، والحجم.\\n'
          '• التصدير: يحفظ نسخة جديدة بصيغة MP3 أو WAV أو M4A بكل التعديلات.\\n\\n'
          'يعمل التحرير محليًا على جهازك عبر ffmpeg — لا يحتاج اتصالًا بالإنترنت.',
          style: TextStyle(color: _textA, fontSize: 13, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('حسنًا', style: TextStyle(color: _teal))),
        ],
      ),
    ),
  );''',
    'E4: added info button + explanation dialog to _appBar()')

STAMP.write_text('S180\n')
print('\n✅  patch_s180 done')
print('   git add lib/screens/audio_editor_screen.dart')
print('   git commit -m "S180: E1-E3 fix reversed trim/EQ/effect sliders under rtl,')
print('   E4 add audio editor explanation dialog"')
print('   git push')
print()
print('NOTE: the screen itself stays rtl (Arabic-only UI by design) — only the')
print('Slider widgets are forced ltr internally, since Slider is the one widget')
print('here whose drag direction Flutter actually mirrors under rtl. Labels,')
print('icons, and layout around the sliders are untouched.')
