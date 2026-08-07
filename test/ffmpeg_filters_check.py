#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ffmpeg_filters_check.py — validate the audio editor's ffmpeg fallback chain.

The editor has two processing paths. The Studio Engine (numpy/scipy) is the
one that normally runs, and test/dsp_studio_smoke.py exercises it end to end.
The second path is `_buildAf()`: a plain ffmpeg `-af` chain that export falls
back to whenever the Studio Engine is unavailable or returns non-zero — which
on a real device means exactly the situation where the user is already having
trouble.

Nothing has ever checked that chain. Every filter in it is a string built by
interpolating slider values into ffmpeg syntax, so a wrong option name, an
option that does not accept the unit being passed, or a value outside the
filter's documented range produces a command that fails at export time on the
phone and nowhere else. `flutter analyze` cannot see inside a string, and the
Studio Engine smoke test never touches this path.

This extracts every filter `_buildAf()` can emit, substitutes real values taken
from the sliders' own min/max in the UI (so the ranges cannot drift from what
the user can actually dial in), and runs each one through ffmpeg against a
real WAV. A filter has to accept the value AND produce audible output: a
chain that "succeeds" into silence is a failure here.

Run: python3 test/ffmpeg_filters_check.py     (needs ffmpeg on PATH)
"""
import os
import re
import subprocess
import sys
import tempfile
import wave
import struct
import math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EDITOR = os.path.join(ROOT, 'lib', 'screens', 'audio_editor_screen.dart')
SR = 44100

_fails = []


def check(label, ok, detail=''):
    print(('  PASS  ' if ok else '  FAIL  ') + label + (f'  [{detail}]' if detail else ''))
    if not ok:
        _fails.append(label)
    return ok


# ── the Dart source ─────────────────────────────────────────────────────────

def build_af_body(src):
    i = src.index('List<String> _buildAf()')
    return src[i:src.index('return af;', i)]


def slider_ranges(src):
    """Every control's (min, max), read from its own call site.

    Two helpers declare them: _slider(value, min, max, ...) and
    _knob(label, readout, value, min, max, ...). Parsing both means this test
    tracks the UI — widen a slider and the filter gets re-checked at the new
    extreme automatically.
    """
    out = {}
    for m in re.finditer(r'_slider\(\s*(_\w+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)', src):
        out[m.group(1)] = (float(m.group(2)), float(m.group(3)))
    for m in re.finditer(
            r'_knob\([^;]*?,\s*(_\w+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,', src):
        out.setdefault(m.group(1), (float(m.group(2)), float(m.group(3))))
    return out


def af_templates(body):
    """Each af.add(...) argument, with adjacent Dart string literals joined.

    `silenceremove` is written as two concatenated literals across a line
    break, so a naive single-literal regex silently skips it — which would
    leave the one filter with the most options unchecked.
    """
    out = []
    for m in re.finditer(r'af\.add\(', body):
        depth, k = 1, m.end()
        while depth and k < len(body):
            if body[k] == '(':
                depth += 1
            elif body[k] == ')':
                depth -= 1
            k += 1
        arg = body[m.end():k - 1]
        parts = re.findall(r"'((?:[^'\\]|\\.)*)'", arg)
        if parts:
            out.append(''.join(parts))
    return out


# ── Dart expression → value ─────────────────────────────────────────────────

def dart_eval(expr, env):
    """Evaluate one `${...}` interpolation.

    Only the arithmetic actually present in _buildAf() is supported: the four
    operators, parentheses, numeric literals, field names, list indexing, and
    the three methods used (toStringAsFixed / round / clamp). Anything else
    raises, so a new expression shape fails loudly here rather than being
    quietly mis-evaluated into a value that happens to pass.
    """
    e = expr.strip()

    # Methods chain off whatever operand sits to their left, and that operand
    # may itself be a parenthesised expression containing more parens
    # (`(16 - (_crusher/100*11)).round()`). Matching it with a regex is what
    # made the first version of this silently mis-parse, so the operand is
    # found by walking backwards over balanced parens instead.
    while True:
        m = re.search(r'\.(toStringAsFixed\((\d+)\)|round\(\)|'
                      r'clamp\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\))', e)
        if not m:
            break
        start = _operand_start(e, m.start())
        val = _num(e[start:m.start()], env)
        if m.group(1).startswith('toStringAsFixed'):
            rep = repr('%.*f' % (int(m.group(2)), val))
        elif m.group(1) == 'round()':
            rep = str(int(round(val)))
        else:
            rep = repr(min(max(val, float(m.group(3))), float(m.group(4))))
        e = e[:start] + rep + e[m.end():]

    if e.startswith("'") and e.endswith("'"):
        return e[1:-1]
    v = _num(e, env)
    return str(int(v)) if float(v).is_integer() else str(v)


def _operand_start(e, dot):
    """Index where the operand ending at `dot` begins (parens balanced)."""
    j = dot - 1
    while j >= 0 and e[j] == ' ':
        j -= 1
    if j >= 0 and e[j] == ')':
        depth = 0
        while j >= 0:
            if e[j] == ')':
                depth += 1
            elif e[j] == '(':
                depth -= 1
                if depth == 0:
                    return j
            j -= 1
        raise ValueError('unbalanced parentheses in %r' % e)
    while j >= 0 and (e[j].isalnum() or e[j] in '_.[]'):
        j -= 1
    return j + 1


def _num(expr, env):
    """Evaluate a purely arithmetic Dart sub-expression to a float."""
    e = expr.strip()
    if e.startswith("'") and e.endswith("'"):
        return float(e[1:-1])
    # list indexing: _freqs[i], _eq[i]
    e = re.sub(r'(_\w+)\[(\w+)\]',
               lambda m: repr(env[m.group(1)][int(env[m.group(2)])]), e)
    for name in sorted(env, key=len, reverse=True):
        if isinstance(env[name], (int, float)):
            e = re.sub(r'(?<![\w.])' + re.escape(name) + r'(?![\w])',
                       repr(env[name]), e)
    if not re.fullmatch(r'[-+*/(). \d]+', e):
        raise ValueError('unsupported Dart expression: %r' % expr)
    return float(eval(e, {'__builtins__': {}}, {}))  # noqa: S307 — arithmetic only


def render(template, env):
    """Substitute every ${...} and $name in one af.add template."""
    out, i = [], 0
    while i < len(template):
        c = template[i]
        if c == '$' and i + 1 < len(template):
            if template[i + 1] == '{':
                depth, j = 1, i + 2
                while depth and j < len(template):
                    if template[j] == '{':
                        depth += 1
                    elif template[j] == '}':
                        depth -= 1
                    j += 1
                out.append(dart_eval(template[i + 2:j - 1], env))
                i = j
                continue
            m = re.match(r'\$(\w+)', template[i:])
            if m:
                v = env[m.group(1)]
                out.append(v if isinstance(v, str) else str(v))
                i += m.end()
                continue
        out.append(c)
        i += 1
    return ''.join(out)


# ── test signal ─────────────────────────────────────────────────────────────

def make_wav(path, seconds=4.0):
    """A stereo tone with harmonics and a little noise — enough for every
    filter here to have something real to act on."""
    n = int(seconds * SR)
    frames = bytearray()
    for i in range(n):
        t = i / SR
        v = (0.45 * math.sin(2 * math.pi * 220 * t)
             + 0.20 * math.sin(2 * math.pi * 440 * t)
             + 0.10 * math.sin(2 * math.pi * 1800 * t)
             + 0.02 * math.sin(2 * math.pi * 50 * t))       # a little mains hum
        env = min(1.0, t * 4, (seconds - t) * 4)
        li = int(max(-1.0, min(1.0, v * env)) * 26000)
        ri = int(max(-1.0, min(1.0, v * env * 0.85)) * 26000)
        frames += struct.pack('<hh', li, ri)
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(bytes(frames))


def peak_of(path):
    """Peak amplitude of a rendered file, via ffmpeg's own volumedetect."""
    r = subprocess.run(
        ['ffmpeg', '-v', 'info', '-i', path, '-af', 'volumedetect',
         '-f', 'null', '-'],
        capture_output=True, text=True)
    m = re.search(r'max_volume:\s*(-?[\d.]+) dB', r.stderr)
    return float(m.group(1)) if m else None


def run_filter(src_wav, work, idx, chain):
    out = os.path.join(work, 'o%d.wav' % idx)
    r = subprocess.run(
        ['ffmpeg', '-y', '-v', 'error', '-i', src_wav, '-af', chain,
         '-ar', '44100', '-ac', '2', out],
        capture_output=True, text=True)
    if r.returncode != 0:
        return False, (r.stderr.strip().splitlines() or [''])[-1][:160], None
    if not os.path.exists(out) or os.path.getsize(out) < 1000:
        return False, 'produced no output', None
    return True, '', peak_of(out)


def main():
    if not shutil_which('ffmpeg'):
        print('ffmpeg is required to run this test')
        return 2

    src = open(EDITOR, encoding='utf-8').read()
    body = build_af_body(src)
    ranges = slider_ranges(src)
    templates = af_templates(body)

    check('found the filter chain builder', len(templates) >= 35,
          '%d filters' % len(templates))
    check('slider ranges parsed from the UI', len(ranges) >= 18,
          '%d controls' % len(ranges))

    # Locals defined inside _buildAf(), plus the constants it closes over.
    # Values are recomputed per variant below from the same expressions the
    # Dart uses, so they cannot drift from the source.
    freqs = [int(x) for x in re.search(
        r'_freqs\s*=\s*\[([^\]]*)\]', src).group(1).split(',')]

    work = tempfile.mkdtemp(prefix='tilawa_ffmpeg_check_')
    src_wav = os.path.join(work, 'in.wav')
    make_wav(src_wav)

    # Three variants per control: the two extremes a user can actually reach,
    # plus the midpoint. Extremes are where filter option ranges get violated.
    # Controls whose filter is only emitted when the value is non-zero. At the
    # slider's literal minimum those filters never run at all, so testing them
    # at 0 would exercise a command the app cannot produce (and flag a silent
    # `wet=0.00` as a defect). The real minimum is the smallest non-zero value
    # the slider can reach.
    zero_guarded = set(re.findall(r'if\s*\(\s*(_\w+)\s*[!>]=?\s*0[.0]*\s*\)', body))

    def env_for(pos):
        env = {'_freqs': freqs, 'i': 0, 'k': 1}
        for name, (lo, hi) in ranges.items():
            if pos == 'min':
                env[name] = (hi * 0.01 if (name in zero_guarded and lo == 0)
                             else lo)
            elif pos == 'max':
                env[name] = hi
            else:
                env[name] = (lo + hi) / 2
        # fields with no slider of their own
        env.setdefault('_noiseReduc', 100.0 if pos != 'min' else 1.0)
        env['_noiseReduc'] = {'min': 1.0, 'mid': 50.0, 'max': 100.0}[pos]
        env['_dehumBase'] = 50 if pos == 'min' else 60
        env['_fadeIn'] = {'min': 0.1, 'mid': 5.0, 'max': 10.0}[pos]
        env['_fadeOut'] = {'min': 0.1, 'mid': 5.0, 'max': 10.0}[pos]
        env['_echo'] = {'min': 1.0, 'mid': 50.0, 'max': 100.0}[pos]
        env['_reverb'] = {'min': 1.0, 'mid': 50.0, 'max': 100.0}[pos]
        env['_pitch'] = {'min': -12.0, 'mid': 3.0, 'max': 12.0}[pos]
        env['_tempo'] = {'min': 0.5, 'mid': 1.5, 'max': 2.0}[pos]
        env['_stereoW'] = {'min': 0.5, 'mid': 1.5, 'max': 2.0}[pos]
        env['_vol'] = {'min': 0.5, 'mid': 1.5, 'max': 2.0}[pos]
        env['_eq'] = [{'min': -12.0, 'mid': 6.0, 'max': 12.0}[pos]] * len(freqs)
        # locals computed by _buildAf itself
        env['w'] = '%.1f' % (2 + env['_dehumStrength'] / 100 * 6)
        env['slev'] = '%.2f' % (1 - 0.85 * env['_vocalIso'] / 100)
        env['st'] = '%.2f' % max(0.0, 4.0 - env['_fadeOut'])
        r = 2.0 ** (env['_pitch'] / 12.0)
        env['r'] = r
        env['co'] = '%.6f' % min(max(1.0 / r, 0.5), 2.0)
        return env

    idx = 0
    for pos in ('min', 'mid', 'max'):
        print('\n── %s of every range ──────────────────────────────' % pos)
        env = env_for(pos)
        for tmpl in templates:
            # the EQ filter is emitted once per band; check every band
            spread = range(len(freqs)) if '_freqs[i]' in tmpl else [0]
            for band in spread:
                env['i'] = band
                # the de-hum notch is emitted for 5 harmonics
                harmonics = range(1, 6) if '_dehumBase * k' in tmpl else [1]
                for k in harmonics:
                    env['k'] = k
                    try:
                        chain = render(tmpl, env)
                    except Exception as ex:      # noqa: BLE001 — reported below
                        check('render %s' % tmpl[:46], False, str(ex)[:90])
                        continue
                    idx += 1
                    ok, err, peak = run_filter(src_wav, work, idx, chain)
                    name = chain.split('=')[0].split(',')[0]
                    if not ok:
                        check('%s accepts %s' % (name, pos), False,
                              '%s → %s' % (chain[:70], err))
                    elif peak is not None and peak < -60:
                        check('%s leaves audible output at %s' % (name, pos),
                              False, '%s → peak %.1f dB' % (chain[:60], peak))
                    else:
                        label = '%s @%s' % (chain[:58], pos)
                        print('  PASS  %s  [peak %s]' % (
                            label, ('%.1f dB' % peak) if peak is not None else 'n/a'))

    # The real export joins every active filter with commas — a chain that is
    # valid one filter at a time can still fail as a whole (a filter that
    # changes the channel count feeding one that requires stereo, say). This
    # is the command the fallback actually runs.
    print('\n── the whole chain at once ────────────────────────────')
    env = env_for('mid')
    whole = []
    for tmpl in templates:
        if '_freqs[i]' in tmpl or '_dehumBase * k' in tmpl:
            continue
        if tmpl.startswith('pan=') and whole and any(
                x.startswith('pan=') for x in whole):
            continue          # the four pan modes are mutually exclusive
        try:
            whole.append(render(tmpl, env))
        except Exception:     # noqa: BLE001 — already reported per-filter
            pass
    idx += 1
    ok, err, peak = run_filter(src_wav, work, idx, ','.join(whole))
    check('every filter combined into one chain runs', ok,
          err or ('%d filters, peak %.1f dB' % (len(whole), peak or 0)))

    print('\n' + '=' * 60)
    if _fails:
        print('%d CHECK(S) FAILED:' % len(_fails))
        for f in _fails:
            print('  · ' + f)
        return 1
    print('every ffmpeg filter the editor can emit runs and produces audio')
    return 0


def shutil_which(x):
    from shutil import which
    return which(x)


if __name__ == '__main__':
    sys.exit(main())
