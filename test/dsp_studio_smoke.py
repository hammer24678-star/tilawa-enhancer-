#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dsp_studio_smoke.py — S250 self-test for assets/dsp/tilawa_dsp_studio.py

Runs the Studio Engine through every mode it exposes (process / --analyze /
--split / --quality / --libs) against a synthesized "recitation" that
deliberately contains the defects the engine is meant to fix: mains hum,
broadband hiss, impulse clicks, a reverb tail, over-long pauses and a stereo
image. Then it repeats the whole run with all 14 embedded packages hidden, to
prove the numpy/scipy fallbacks still produce valid audio.

Usage:
    python3 test/dsp_studio_smoke.py            # needs numpy + scipy + ffmpeg
    python3 test/dsp_studio_smoke.py --keep     # leave the temp files behind

Exit code 0 = every check passed. This is a smoke test, not an audio-quality
judgement: it asserts the engine runs, honours the output settings, and never
emits silence or garbage.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import wave
import struct
import math
import random

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, '..', 'assets', 'dsp', 'tilawa_dsp_studio.py')
SR = 44100

_fails = []


def check(label, ok, detail=''):
    print(('  PASS  ' if ok else '  FAIL  ') + label + (f'  [{detail}]' if detail else ''))
    if not ok:
        _fails.append(label)
    return ok


def make_input(path):
    """Synthesize a stereo 'recitation' with realistic defects — stdlib only,
    so this test can run before numpy is even importable."""
    rnd = random.Random(7)
    samples = []

    def voiced(dur, f0):
        n = int(dur * SR)
        for i in range(n):
            t = i / SR
            vib = 0.6 * math.sin(2 * math.pi * 4.5 * t)
            v = 0.0
            for k, g in ((1, 1.0), (2, 0.5), (3, 0.3), (4, 0.18), (5, 0.1)):
                v += g * math.sin(2 * math.pi * f0 * k * t + vib)
            env = math.sin(math.pi * min(max(i / n, 0.0), 1.0)) ** 0.4
            samples.append(v / 6.0 * env)

    for dur, f0, pause in ((2.2, 132.0, 1.8), (1.9, 148.0, 2.4),
                           (2.5, 120.0, 0.6), (1.4, 160.0, 0.0)):
        voiced(dur, f0)
        samples.extend([0.0] * int(pause * SR))

    # defects: 50 Hz hum + harmonic, hiss, impulse clicks
    for i in range(len(samples)):
        t = i / SR
        samples[i] += 0.02 * math.sin(2 * math.pi * 50 * t)
        samples[i] += 0.012 * math.sin(2 * math.pi * 100 * t)
        samples[i] += rnd.gauss(0.0, 0.004)
    for _ in range(40):
        samples[rnd.randrange(len(samples))] += rnd.choice((-0.7, 0.7))

    # cheap reverb tail: a few decaying delayed taps
    wet = list(samples)
    for delay_ms, gain in ((23, 0.30), (47, 0.22), (79, 0.15), (131, 0.09)):
        d = int(delay_ms * SR / 1000)
        for i in range(d, len(samples)):
            wet[i] += gain * samples[i - d]
    peak = max(abs(v) for v in wet) or 1.0
    scale = 0.85 / peak

    off = int(0.003 * SR)                     # small L/R offset → stereo image
    with wave.open(path, 'wb') as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        frames = bytearray()
        for i, v in enumerate(wet):
            l = int(max(-1.0, min(1.0, v * scale)) * 32000)
            rv = wet[i - off] if i >= off else 0.0
            r = int(max(-1.0, min(1.0, rv * scale * 0.95)) * 32000)
            frames += struct.pack('<hh', l, r)
        w.writeframes(bytes(frames))
    return len(wet) / SR


def wav_info(path):
    """Minimal RIFF reader. Python's `wave` module rejects
    WAVE_FORMAT_EXTENSIBLE (0xFFFE), which is exactly what ffmpeg emits for
    24-bit output — so parse the chunks directly instead."""
    with open(path, 'rb') as fh:
        raw = fh.read()
    if raw[:4] != b'RIFF' or raw[8:12] != b'WAVE':
        raise ValueError('not a RIFF/WAVE file: ' + path)
    pos = 12
    fmt = None
    data = b''
    while pos + 8 <= len(raw):
        cid = raw[pos:pos + 4]
        size = struct.unpack('<I', raw[pos + 4:pos + 8])[0]
        body = raw[pos + 8:pos + 8 + size]
        if cid == b'fmt ':
            fmt = struct.unpack('<HHIIHH', body[:16])
        elif cid == b'data':
            data = body
        pos += 8 + size + (size & 1)
    if fmt is None:
        raise ValueError('no fmt chunk: ' + path)
    _tag, ch, rate, _brate, _align, bits = fmt
    width = max(1, bits // 8)
    frames = len(data) // max(1, width * ch)
    peak = 0.0
    if width == 2:
        vals = struct.unpack_from('<%dh' % (len(data) // 2), data)
        peak = (max(abs(v) for v in vals) / 32768.0) if vals else 0.0
    elif width == 3:
        for i in range(0, len(data) - 2, 3):
            v = int.from_bytes(data[i:i + 3], 'little', signed=True)
            peak = max(peak, abs(v))
        peak /= float(1 << 23)
    elif data:
        peak = 1.0 if any(data) else 0.0
    return {'frames': frames, 'channels': ch, 'width': width, 'rate': rate,
            'seconds': frames / float(rate) if rate else 0, 'peak': peak}


def run(args, blocked=False, cwd=None):
    """Invoke the engine. blocked=True hides all 14 embedded packages."""
    if not blocked:
        cmd = [sys.executable, ENGINE] + args
        return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, timeout=900)
    harness = (
        "import sys, importlib.abc\n"
        "BLOCK={'nara_wpe','noisereduce','webrtcvad','pystoi','pyloudnorm',"
        "'soundfile','soxr','audioread','joblib','decorator','tqdm','msgpack',"
        "'pooch','lazy_loader','librosa'}\n"
        "class F(importlib.abc.MetaPathFinder):\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name.split('.')[0] in BLOCK: raise ImportError('blocked '+name)\n"
        "        return None\n"
        "sys.meta_path.insert(0, F())\n"
        f"sys.argv=['tilawa_dsp_studio.py']+{args!r}\n"
        f"exec(compile(open({ENGINE!r}).read(), {ENGINE!r}, 'exec'),"
        " {'__name__':'__main__','__file__':%r})\n" % ENGINE
    )
    return subprocess.run([sys.executable, '-c', harness],
                          capture_output=True, text=True, cwd=cwd, timeout=900)


def params(tmp, **over):
    p = {
        'sr': 48000, 'trim_start': 0.0, 'trim_dur': 0.0, 'reverse': False,
        'eq_freqs': [31, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000],
        'eq_gains': [0, 0, -2, 0, 1, 2, 3, 1, 0, 0], 'eq_q': 1.4,
        'declick': {'enabled': True, 'sensitivity': 60},
        'noise_reduction': {'strength': 20},
        'fade_in': 0.3, 'fade_out': 0.5, 'fade_curve': 'Equal Power',
        'pitch_semitones': 0.0, 'tempo': 1.0,
        'echo': {'mix': 0}, 'reverb': {'mix': 0, 'type': 'Room'},
        'compressor': {'enabled': True, 'threshold_db': -18, 'ratio': 3,
                       'attack_ms': 20, 'release_ms': 200, 'makeup_db': 2},
        'stereo_width': 1.1, 'volume': 1.0,
        'loudness': {'target_lufs': -16, 'true_peak_limit_db': -1.0, 'limiter': True},
        'progress_path': os.path.join(tmp, over.pop('_prog', 'prog.txt')),
        'fx2': {
            'bass_db': 1, 'treble_db': 2, 'sub_bass': 0, 'presence': 20,
            'highpass_hz': 80, 'lowpass_hz': 20000,
            'tremolo': 0, 'vibrato': 0, 'chorus': False, 'flanger': False,
            'phaser': False, 'bitcrush': 0, 'haas_widen': False, 'stereo_fx': 0,
            'channel_mode': 'Stereo', 'swap_lr': False,
            'noise_gate': {'enabled': True, 'threshold_db': -55},
            'dehum': {'enabled': True, 'base_hz': 50, 'strength': 70},
            'vocal_isolate': 20, 'deesser': 15, 'declip': True,
            'adaptive_normalize': False,
            'limiter': {'enabled': True, 'ceiling_db': -1.0},
            'auto_trim_silence': False,
            'ai_denoise': {'enabled': True, 'strength': 55, 'non_stationary': False},
            'vad_trim': {'enabled': True, 'aggressiveness': 2},
            'pause_squeeze': {'enabled': True, 'max_pause_s': 0.8, 'keep_s': 0.3},
            'dereverb': {'strength': 70, 'taps': 10, 'delay': 3},
            'harmonic_focus': 40,
            'pad_start_sec': 0, 'pad_end_sec': 0,
        },
        'output': {'format': 'WAV', 'kbps': 192, 'sample_rate': 44100,
                   'channels': 'Stereo', 'wav_bit_depth': 16,
                   'metadata': {'title': 'Smoke', 'artist': 'Test', 'album': 'S250'}},
    }
    p.update(over)
    path = os.path.join(tmp, over.pop('_name', 'params.json'))
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(p, fh)
    return path, p


def suite(tmp, blocked):
    tag = 'fallback (packages hidden)' if blocked else 'full (packages present)'
    print(f'\n── {tag} ' + '─' * (52 - len(tag)))

    inp = os.path.join(tmp, 'in.wav')
    src_sec = make_input(inp)

    # --libs
    libs_json = os.path.join(tmp, 'libs.json')
    r = run(['--libs', libs_json], blocked)
    ok = r.returncode == 0 and os.path.exists(libs_json)
    if check('--libs writes a report', ok, r.stdout.strip()[:80]):
        d = json.load(open(libs_json))
        check('--libs lists 14 packages', d.get('count_total') == 14,
              f"{d.get('count_ok')}/{d.get('count_total')} available")
        check('--libs roles are described',
              all(p.get('role') for p in d.get('packages', [])))
        if not blocked:
            check('all 14 packages available here', d.get('count_ok') == 14,
                  ', '.join(p['name'] for p in d['packages'] if not p['ok']) or 'none missing')

    # process
    suffix = 'blocked' if blocked else 'full'
    out = os.path.join(tmp, f'out_{suffix}.wav')
    prog_name = f'prog_{suffix}.txt'
    pfile, _ = params(tmp, _name=f'params_{suffix}.json', _prog=prog_name)
    r = run([inp, out, pfile], blocked)
    if check('process run exits 0', r.returncode == 0, (r.stdout or r.stderr).strip()[:120]):
        info = wav_info(out)
        check('output honours sample rate', info['rate'] == 44100, str(info['rate']))
        check('output honours stereo', info['channels'] == 2, str(info['channels']))
        check('output is not silent', info['peak'] > 0.001, f"peak {info['peak']:.3f}")
        check('output is not clipped solid', info['peak'] <= 1.0)
        if blocked:
            # webrtcvad is hidden, so pause squeezing must no-op rather than
            # mangle the length — the file should come back essentially intact.
            check('pause squeeze no-ops without webrtcvad',
                  info['seconds'] > 0.9 * src_sec,
                  f"{info['seconds']:.2f}s from {src_sec:.2f}s")
        else:
            check('pause squeeze shortened the file',
                  0.3 * src_sec < info['seconds'] < src_sec,
                  f"{info['seconds']:.2f}s from {src_sec:.2f}s")
        rep = out + '.report.json'
        if check('run report written', os.path.exists(rep)):
            d = json.load(open(rep))
            check('report has stage timings', isinstance(d.get('stages'), list))
            check('report records lib availability', len(d.get('libs', {})) == 14)
        prog = os.path.join(tmp, prog_name)
        shown = open(prog).read().strip()[:40] if os.path.exists(prog) else 'absent'
        if blocked:
            check('progress degrades quietly without tqdm',
                  not os.path.exists(prog) or shown == '', shown)
        else:
            check('progress file written and complete',
                  os.path.exists(prog) and 'done' in shown, shown)

    # mono / MP3 (exercises the ffmpeg encode branch)
    mp3 = os.path.join(tmp, f'out_{suffix}.mp3')
    pfile2, _ = params(tmp, _name=f'p_mp3_{suffix}.json', output={
        'format': 'MP3', 'kbps': 128, 'sample_rate': 22050, 'channels': 'Mono',
        'wav_bit_depth': 16, 'metadata': {'title': 'M', 'artist': '', 'album': ''}})
    r = run([inp, mp3, pfile2], blocked)
    check('MP3/mono export exits 0', r.returncode == 0, (r.stdout or r.stderr).strip()[:100])
    check('MP3 file has content', os.path.exists(mp3) and os.path.getsize(mp3) > 1000,
          f'{os.path.getsize(mp3) if os.path.exists(mp3) else 0} bytes')

    # 24-bit WAV (soundfile subtype path when available)
    w24 = os.path.join(tmp, f'out24_{suffix}.wav')
    pfile3, _ = params(tmp, _name=f'p24_{suffix}.json', output={
        'format': 'WAV', 'kbps': 192, 'sample_rate': 48000, 'channels': 'Stereo',
        'wav_bit_depth': 24, 'metadata': {}})
    r = run([inp, w24, pfile3], blocked)
    if check('24-bit WAV export exits 0', r.returncode == 0):
        check('24-bit WAV is really 24-bit', wav_info(w24)['width'] == 3,
              f"{wav_info(w24)['width'] * 8}-bit")

    # --analyze (twice: second run should hit the msgpack cache)
    a1 = os.path.join(tmp, f'a1_{suffix}.json')
    r = run(['--analyze', inp, a1], blocked)
    if check('--analyze exits 0', r.returncode == 0, (r.stdout or r.stderr).strip()[:100]):
        d = json.load(open(a1))
        check('waveform has 96 buckets', len(d.get('peaks', [])) == 96, str(len(d.get('peaks', []))))
        check('rms layer present', len(d.get('rms', [])) == 96)
        check('duration is sane', abs(d.get('duration_sec', 0) - src_sec) < 0.5,
              f"{d.get('duration_sec')} vs {src_sec:.2f}")
        check('level stats present', d.get('peak_db') is not None and d.get('rms_db') is not None)
        check('loudness measured', d.get('lufs') is not None, str(d.get('lufs')))
        check('F0 detected near 132 Hz', d.get('f0_hz') and 100 < d['f0_hz'] < 180,
              f"{d.get('f0_hz')} Hz → {d.get('note')}")
        check('brightness reported', d.get('brightness_hz') is not None)
        check('onset rate reported', d.get('onsets_per_min') is not None)
        if not blocked:
            check('speech ratio reported (webrtcvad)', d.get('speech_pct') is not None,
                  f"{d.get('speech_pct')}%")
    a2 = os.path.join(tmp, f'a2_{suffix}.json')
    r = run(['--analyze', inp, a2], blocked)
    cached = '"cached": true' in (r.stdout or '')
    check('second --analyze hits the cache' if not blocked else 'no cache without msgpack',
          cached if not blocked else not cached, r.stdout.strip()[:70])

    # --quality
    q = os.path.join(tmp, f'q_{suffix}.json')
    r = run(['--quality', inp, w24, q], blocked)
    if not blocked:
        if check('--quality exits 0', r.returncode == 0, (r.stdout or r.stderr).strip()[:100]):
            d = json.load(open(q))
            check('STOI reported', d.get('stoi') is not None, str(d.get('stoi')))
            check('ESTOI reported', d.get('estoi') is not None, str(d.get('estoi')))
            check('length drift reported', d.get('length_drift_sec') is not None,
                  f"{d.get('length_drift_sec')}s")
    else:
        d = json.load(open(q)) if os.path.exists(q) else {}
        check('--quality fails gracefully without pystoi',
              d.get('ok') is False and 'pystoi' in str(d.get('error', '')),
              str(d.get('error'))[:60])

    # --split
    base = os.path.join(tmp, f'seg_{suffix}')
    sp = os.path.join(tmp, f'sp_{suffix}.json')
    with open(sp, 'w', encoding='utf-8') as fh:
        json.dump({'silence_db': -34, 'min_silence_s': 0.5, 'min_seg_s': 0.8,
                   'output': {'format': 'WAV', 'sample_rate': 44100,
                              'channels': 'Stereo', 'wav_bit_depth': 16,
                              'metadata': {}}}, fh)
    r = run(['--split', inp, base, sp], blocked)
    if check('--split exits 0', r.returncode == 0, (r.stdout or r.stderr).strip()[:100]):
        rep = base + '_report.json'
        if check('--split writes a report', os.path.exists(rep)):
            d = json.load(open(rep))
            check('--split produced at least one part', (d.get('count') or 0) >= 1,
                  f"{d.get('count')} parts")
            for f in d.get('files', []):
                check(f"part exists: {os.path.basename(f['path'])}",
                      os.path.exists(f['path']) and os.path.getsize(f['path']) > 1000)

    # bad input must fail loudly, not silently produce a file
    r = run([os.path.join(tmp, 'nope.wav'), os.path.join(tmp, 'x.wav'), pfile], blocked)
    check('missing input exits non-zero', r.returncode != 0)
    check('missing input reports an error', '"ok": false' in (r.stdout or ''),
          r.stdout.strip()[:70])


def main():
    keep = '--keep' in sys.argv
    if not os.path.exists(ENGINE):
        print(f'engine not found: {ENGINE}')
        return 2
    try:
        import numpy  # noqa: F401
    except Exception:
        print('numpy is required to run this test')
        return 2
    if not shutil.which('ffmpeg'):
        print('NOTE: ffmpeg not on PATH — the MP3 branch will be skipped by the engine')

    tmp = tempfile.mkdtemp(prefix='tilawa_dsp_smoke_')
    # keep the engine's analysis cache inside the temp dir so runs are isolated
    os.environ['TMPDIR'] = tmp
    print(f'workdir: {tmp}')
    try:
        suite(tmp, blocked=False)
        for f in os.listdir(tmp):                    # fresh cache for round 2
            if f.startswith('tilawa_analysis_cache'):
                os.remove(os.path.join(tmp, f))
        suite(tmp, blocked=True)
    finally:
        if keep:
            print(f'\nkept: {tmp}')
        else:
            shutil.rmtree(tmp, ignore_errors=True)

    print('\n' + '═' * 60)
    if _fails:
        print(f'{len(_fails)} CHECK(S) FAILED:')
        for f in _fails:
            print('  · ' + f)
        return 1
    print('all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
