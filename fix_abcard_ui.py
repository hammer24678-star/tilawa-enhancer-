#!/usr/bin/env python3
"""fix_abcard_ui.py — improved AB comparison card with animations"""
import re
from pathlib import Path

HS = Path('lib/screens/home_screen.dart')
t = HS.read_text(encoding='utf-8')

OLD = '''  Widget _abCard(S s) {
    if (_file == null || _output == null) return const SizedBox.shrink();
    final progress = (_abPos / _abDur).clamp(0.0, 1.0);
    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFF0A1A14),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1DB898).withValues(alpha: 0.35))),
      child: Column(children: [
        Row(children: [
          const Icon(Icons.compare_arrows_rounded,
            color: Color(0xFF1DB898), size: 14),
          const SizedBox(width: 6),
          Text(s.ar ? 'مقارنة قبل / بعد' : 'Before / After',
            style: const TextStyle(
              color: Color(0xFF1DB898), fontSize: 11,
              fontWeight: FontWeight.w600, letterSpacing: 1.2)),
        ]),
        const SizedBox(height: 10),
        Row(children: [
          // A button
          Expanded(child: GestureDetector(
            onTap: () async {
              if (_abIsB) await _abToggleTrack();
              else await _abTogglePlay();
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(vertical: 8),
              decoration: BoxDecoration(
                color: !_abIsB
                  ? const Color(0xFF1DB898).withValues(alpha: 0.18)
                  : const Color(0xFF0D2B22),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: !_abIsB
                    ? const Color(0xFF1DB898)
                    : const Color(0xFF1DB898).withValues(alpha: 0.25))),
              child: Column(children: [
                Icon(!_abIsB && _abPlaying
                  ? Icons.pause_rounded : Icons.play_arrow_rounded,
                  color: const Color(0xFF1DB898), size: 18),
                const SizedBox(height: 2),
                Text(s.ar ? 'الأصلي' : 'Original',
                  style: const TextStyle(
                    color: Color(0xFF1DB898), fontSize: 10)),
              ]),
            ))),
          const SizedBox(width: 8),
          // B button
          Expanded(child: GestureDetector(
            onTap: () async {
              if (!_abIsB) await _abToggleTrack();
              else await _abTogglePlay();
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              padding: const EdgeInsets.symmetric(vertical: 8),
              decoration: BoxDecoration(
                color: _abIsB
                  ? const Color(0xFFD4AF37).withValues(alpha: 0.18)
                  : const Color(0xFF1A1200),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: _abIsB
                    ? const Color(0xFFD4AF37)
                    : const Color(0xFFD4AF37).withValues(alpha: 0.25))),
              child: Column(children: [
                Icon(_abIsB && _abPlaying
                  ? Icons.pause_rounded : Icons.play_arrow_rounded,
                  color: const Color(0xFFD4AF37), size: 18),
                const SizedBox(height: 2),
                Text(s.ar ? 'المُحسَّن' : 'Enhanced',
                  style: const TextStyle(
                    color: Color(0xFFD4AF37), fontSize: 10)),
              ]),
            ))),
        ]),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: progress, minHeight: 4,
            backgroundColor: const Color(0xFF1A2733),
            valueColor: AlwaysStoppedAnimation<Color>(
              _abIsB ? const Color(0xFFD4AF37) : const Color(0xFF1DB898)))),
        const SizedBox(height: 4),
        Text('''

NEW = '''  Widget _abCard(S s) {
    if (_file == null || _output == null) return const SizedBox.shrink();
    final progress = (_abPos / _abDur).clamp(0.0, 1.0);
    final teal   = const Color(0xFF1DB898);
    final gold   = const Color(0xFFD4AF37);
    final active = _abIsB ? gold : teal;

    String _fmt(double ms) {
      final t = Duration(milliseconds: ms.toInt());
      return '${t.inMinutes}:${(t.inSeconds % 60).toString().padLeft(2,'0')}';
    }

    return Container(
      margin: const EdgeInsets.fromLTRB(16, 8, 16, 4),
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft, end: Alignment.bottomRight,
          colors: [const Color(0xFF061812), const Color(0xFF030E0A)]),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: active.withValues(alpha: 0.3)),
        boxShadow: [BoxShadow(
          color: active.withValues(alpha: 0.08),
          blurRadius: 20, spreadRadius: 0)]),
      child: Column(children: [
        // ── Header ──────────────────────────────────────────────
        Row(children: [
          Icon(Icons.compare_arrows_rounded, color: active, size: 13),
          const SizedBox(width: 6),
          Text(s.ar ? 'مقارنة قبل / بعد' : 'Before / After',
            style: TextStyle(color: active, fontSize: 11,
              fontWeight: FontWeight.w700, letterSpacing: 1.5)),
          const Spacer(),
          // playing indicator dots
          if (_abPlaying) ...[
            for (int i = 0; i < 3; i++)
              AnimatedContainer(
                duration: Duration(milliseconds: 300 + i * 120),
                margin: const EdgeInsets.symmetric(horizontal: 1.5),
                width: 3, height: _abPlaying ? 10.0 : 4.0,
                decoration: BoxDecoration(
                  color: active, borderRadius: BorderRadius.circular(2))),
          ],
        ]),
        const SizedBox(height: 12),
        // ── Buttons ──────────────────────────────────────────────
        Row(children: [
          // A — Original
          Expanded(child: GestureDetector(
            onTap: () async {
              if (_abIsB) await _abToggleTrack();
              else await _abTogglePlay();
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 250),
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: !_abIsB
                  ? teal.withValues(alpha: 0.15)
                  : const Color(0xFF050F0A),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: !_abIsB ? teal : teal.withValues(alpha: 0.2)),
                boxShadow: !_abIsB && _abPlaying ? [BoxShadow(
                  color: teal.withValues(alpha: 0.25),
                  blurRadius: 12)] : []),
              child: Column(children: [
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 200),
                  child: Icon(
                    !_abIsB && _abPlaying
                      ? Icons.pause_circle_rounded
                      : Icons.play_circle_rounded,
                    key: ValueKey(!_abIsB && _abPlaying),
                    color: teal, size: 28)),
                const SizedBox(height: 4),
                Text(s.ar ? 'الأصلي' : 'Original',
                  style: TextStyle(
                    color: !_abIsB ? teal : teal.withValues(alpha: 0.6),
                    fontSize: 10, fontWeight: FontWeight.w600)),
              ])))),
          const SizedBox(width: 10),
          // B — Enhanced
          Expanded(child: GestureDetector(
            onTap: () async {
              if (!_abIsB) await _abToggleTrack();
              else await _abTogglePlay();
            },
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 250),
              padding: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(
                color: _abIsB
                  ? gold.withValues(alpha: 0.12)
                  : const Color(0xFF0D0900),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: _abIsB ? gold : gold.withValues(alpha: 0.2)),
                boxShadow: _abIsB && _abPlaying ? [BoxShadow(
                  color: gold.withValues(alpha: 0.3),
                  blurRadius: 16)] : []),
              child: Column(children: [
                AnimatedSwitcher(
                  duration: const Duration(milliseconds: 200),
                  child: Icon(
                    _abIsB && _abPlaying
                      ? Icons.pause_circle_rounded
                      : Icons.play_circle_rounded,
                    key: ValueKey(_abIsB && _abPlaying),
                    color: gold, size: 28)),
                const SizedBox(height: 4),
                Text(s.ar ? 'المُحسَّن' : 'Enhanced',
                  style: TextStyle(
                    color: _abIsB ? gold : gold.withValues(alpha: 0.6),
                    fontSize: 10, fontWeight: FontWeight.w600)),
              ])))),
        ]),
        const SizedBox(height: 12),
        // ── Progress bar ─────────────────────────────────────────
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: progress),
            duration: const Duration(milliseconds: 100),
            builder: (_, v, __) => LinearProgressIndicator(
              value: v, minHeight: 5,
              backgroundColor: const Color(0xFF0F1F18),
              valueColor: AlwaysStoppedAnimation<Color>(active)))),
        const SizedBox(height: 6),
        Row(children: [
          Text(_fmt(_abPos),
            style: TextStyle(color: active.withValues(alpha: 0.7),
              fontSize: 9, fontWeight: FontWeight.w500)),
          const Spacer(),
          Text(_fmt(_abDur),
            style: const TextStyle(color: Color(0xFF3A5048),
              fontSize: 9)),
        ]),
        const SizedBox(height: 4),
        Text('''

if OLD in t:
    HS.write_text(t.replace(OLD, NEW, 1), encoding='utf-8')
    print('done')
else:
    print('NOT FOUND')
