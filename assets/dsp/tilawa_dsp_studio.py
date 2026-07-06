#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tilawa_dsp_studio.py — S228 — "Studio Engine"

General-purpose numpy/scipy audio DSP engine for the Tilawa Audio Editor.

IMPORTANT: this is deliberately NOT one of the Quran-restoration engines
(الصفاء / الإتقان / الاسترداد / إحياء ...). Those stay untouched, mono-focused,
and tuned to Sheikh-specific acoustic profiles. This script is a general
stereo audio tool — trim/EQ/effects/export — that happens to live in the
same app. Keep it that way: no restoration-engine imports, no shared state.

Runs entirely inside the existing proot Alpine environment (same python3 +
numpy + scipy already verified by LocalEngineRunner.numpyWorks() for the
main engines) via the audio editor's generic `runProotCmd` shell channel —
no new native/Kotlin code needed. Decodes/encodes through ffmpeg pipes
(f32le), exactly like the restoration engines do, to avoid any soundfile
dependency.

USAGE:
    python3 tilawa_dsp_studio.py <in_path> <out_path> <params_json_path>

<params_json_path> is a JSON file (see audio_editor_screen.dart
_buildDspParams()) describing the trim window, EQ bands, and every effect.
Prints {"ok": true} / {"ok": false, "error": "..."} to stdout and exits
0/1 accordingly — the Dart side treats a non-zero exit as "fall back to
the plain ffmpeg filter chain", so it's safe for this script to fail loud
rather than produce silently-wrong audio.

Pipeline order (fixed, applied only where the relevant param is non-default):
  reverse → declick → parametric EQ → spectral noise reduction → echo →
  convolution reverb → compressor → pitch shift → time stretch →
  stereo width → volume → loudness (LUFS-ish) normalize + true-peak limit →
  fades → clip → encode
"""
import sys
import os
import json
import subprocess

import numpy as np

try:
    from scipy import signal
    SCIPY_OK = True
except Exception:
    SCIPY_OK = False


# ─── I/O via ffmpeg pipes (same convention as the restoration engines) ──────

def _decode(path: str, sr: int, start: float, dur: float):
    """Decode (and trim) input to interleaved stereo float32 via ffmpeg pipe."""
    cmd = ['ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error']
    if start > 0:
        cmd += ['-ss', f'{start:.3f}']
    cmd += ['-i', path]
    if dur > 0:
        cmd += ['-t', f'{dur:.3f}']
    cmd += ['-ar', str(sr), '-ac', '2', '-f', 'f32le', '-']
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=180)
    except Exception:
        return None
    if r.returncode != 0 or len(r.stdout) < 8:
        return None
    data = np.frombuffer(r.stdout, dtype=np.float32)
    if len(data) % 2 == 1:
        data = data[:-1]
    return data.reshape(-1, 2).copy()


def _encode(x: 'np.ndarray', sr: int, out_path: str, fmt: str, kbps: int) -> bool:
    raw = np.clip(x, -1.0, 1.0).astype(np.float32).tobytes()
    if fmt == 'WAV':
        cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
               '-f', 'f32le', '-ar', str(sr), '-ac', '2', '-i', '-',
               '-c:a', 'pcm_s16le', out_path]
    else:
        codec = {'MP3': 'libmp3lame', 'M4A': 'aac'}.get(fmt, 'libmp3lame')
        cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
               '-f', 'f32le', '-ar', str(sr), '-ac', '2', '-i', '-',
               '-c:a', codec, '-b:a', f'{kbps}k', out_path]
    try:
        r = subprocess.run(cmd, input=raw, capture_output=True, timeout=180)
    except Exception:
        return False
    return r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 44


# ─── Parametric EQ — real RBJ-cookbook peaking biquads, cascaded ────────────

def _peaking_biquad(freq: float, gain_db: float, q: float, sr: int):
    """RBJ audio-cookbook peaking-EQ biquad coefficients."""
    a_amp = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * freq / sr
    alpha = np.sin(w0) / (2.0 * q)
    cosw0 = np.cos(w0)
    b0 = 1 + alpha * a_amp
    b1 = -2 * cosw0
    b2 = 1 - alpha * a_amp
    a0 = 1 + alpha / a_amp
    a1 = -2 * cosw0
    a2 = 1 - alpha / a_amp
    b = np.array([b0, b1, b2]) / a0
    a = np.array([1.0, a1 / a0, a2 / a0])
    return b, a


def _apply_eq(x, sr, freqs, gains, q):
    """Cascade one zero-phase peaking biquad per non-zero band (real filters,
    not ffmpeg's blunt `equalizer=` chain)."""
    if not SCIPY_OK or not freqs or not gains:
        return x
    nyq = sr / 2.0
    sos_list = []
    for f, g in zip(freqs, gains):
        if abs(g) < 0.1:
            continue
        f = min(max(f, 20.0), nyq * 0.98)
        b, a = _peaking_biquad(f, g, max(q, 0.1), sr)
        sos_list.append(signal.tf2sos(b, a))
    if not sos_list:
        return x
    sos = np.vstack(sos_list)
    return signal.sosfiltfilt(sos, x, axis=0).astype(np.float32)


# ─── Declick — median-filter outlier detection + interpolation ─────────────

def _declick(x, sr, sensitivity):
    if not SCIPY_OK or x.shape[0] < 32:
        return x
    thresh_z = float(np.interp(sensitivity, [0, 100], [8.0, 2.0]))
    y = x.copy()
    idx = np.arange(x.shape[0])
    for ch in range(x.shape[1]):
        sig_ = x[:, ch].astype(np.float64)
        med = signal.medfilt(sig_, kernel_size=7)
        resid = sig_ - med
        mad = np.median(np.abs(resid - np.median(resid))) + 1e-9
        z = np.abs(resid) / (1.4826 * mad)
        bad = z > thresh_z
        good = ~bad
        if np.any(bad) and np.sum(good) > 2:
            sig_[bad] = np.interp(idx[bad], idx[good], sig_[good])
        y[:, ch] = sig_.astype(np.float32)
    return y


# ─── Spectral noise reduction — STFT noise-floor gating ─────────────────────

def _spectral_denoise(x, sr, strength):
    if not SCIPY_OK or strength <= 0:
        return x
    strength = min(max(strength, 0.0), 100.0) / 100.0
    n_fft = 2048
    hop = n_fft // 4
    out = np.zeros_like(x)
    for ch in range(x.shape[1]):
        f, t, z = signal.stft(x[:, ch], fs=sr, nperseg=n_fft,
                               noverlap=n_fft - hop, boundary='zeros')
        mag = np.abs(z)
        phase = np.angle(z)
        noise_floor = np.percentile(mag, 10, axis=1, keepdims=True)
        over_sub = 1.0 + 2.0 * strength
        clean_mag = mag - over_sub * noise_floor
        floor = 0.05 * mag  # spectral floor — avoids "musical noise" artifacts
        clean_mag = np.maximum(clean_mag, floor)
        blended = strength * clean_mag + (1.0 - strength) * mag
        zc = blended * np.exp(1j * phase)
        _, xr = signal.istft(zc, fs=sr, nperseg=n_fft, noverlap=n_fft - hop, boundary=True)
        n = min(len(xr), x.shape[0])
        out[:n, ch] = xr[:n]
    return out.astype(np.float32)


# ─── Echo — true feedback delay line (IIR, not ffmpeg aecho) ────────────────

def _echo(x, sr, mix, delay_s=0.35, feedback=0.35):
    if not SCIPY_OK or mix <= 0:
        return x
    mix = min(max(mix, 0.0), 100.0) / 100.0
    d = max(1, int(delay_s * sr))
    a = np.zeros(d + 1, dtype=np.float64)
    a[0] = 1.0
    a[d] = -feedback
    wet = signal.lfilter([1.0], a, x.astype(np.float64), axis=0)
    peak = np.max(np.abs(wet)) + 1e-9
    if peak > 1.5:
        wet = wet / peak * 1.2
    return ((1.0 - mix) * x + mix * wet).astype(np.float32)


# ─── Convolution reverb — procedurally synthesized impulse response ────────

_REVERB_PRESETS = {
    'Room':      (0.35, 0.007),
    'Hall':      (1.80, 0.018),
    'Plate':     (1.10, 0.010),
    'Cathedral': (3.40, 0.030),
}


def _make_ir(sr, rtype):
    decay_s, predelay_s = _REVERB_PRESETS.get(rtype, _REVERB_PRESETS['Room'])
    n = max(8, int(sr * decay_s))
    t = np.arange(n) / sr
    rng = np.random.default_rng(1234)
    noise = rng.standard_normal(n).astype(np.float64)
    ir = np.zeros(n, dtype=np.float64)
    for tap_t, tap_g in [(0.007, 0.50), (0.013, 0.35), (0.021, 0.25), (0.034, 0.18)]:
        i = int(tap_t * sr)
        if i < n:
            ir[i] += tap_g
    env = np.exp(-t / (decay_s / 5.0))
    ir = ir + 0.6 * noise * env
    predelay_n = int(predelay_s * sr)
    if predelay_n > 0 and predelay_n < n:
        ir[:predelay_n] *= 0.2
    peak = np.max(np.abs(ir)) + 1e-9
    return (ir / peak).astype(np.float32)


def _reverb(x, sr, mix, rtype):
    if not SCIPY_OK or mix <= 0:
        return x
    mix = min(max(mix, 0.0), 100.0) / 100.0
    ir = _make_ir(sr, rtype)
    wet = np.zeros_like(x)
    dry_peak = np.max(np.abs(x)) + 1e-9
    for ch in range(x.shape[1]):
        w = signal.fftconvolve(x[:, ch], ir, mode='full')[:x.shape[0]]
        wet[:, ch] = w
    wet_peak = np.max(np.abs(wet)) + 1e-9
    wet = wet / wet_peak * dry_peak
    return ((1.0 - mix) * x + mix * wet).astype(np.float32)


# ─── Compressor — block-envelope follower (fast, not sample-by-sample) ─────

def _compressor(x, sr, threshold_db, ratio, attack_ms, release_ms, makeup_db):
    if ratio <= 1.0:
        return x
    block = max(16, int(sr * 0.001))  # ~1ms blocks — plenty for audible dynamics
    n = x.shape[0]
    nb = int(np.ceil(n / block))
    xa = np.abs(x).max(axis=1)
    lvl = np.zeros(nb, dtype=np.float64)
    for i in range(nb):
        s = i * block
        e = min(n, s + block)
        lvl[i] = xa[s:e].max() if e > s else 0.0
    atk = np.exp(-block / (sr * max(attack_ms, 0.1) / 1000.0))
    rel = np.exp(-block / (sr * max(release_ms, 1.0) / 1000.0))
    env = np.zeros(nb, dtype=np.float64)
    e_prev = 0.0
    for i in range(nb):
        coeff = atk if lvl[i] > e_prev else rel
        e_prev = coeff * e_prev + (1.0 - coeff) * lvl[i]
        env[i] = e_prev
    thr = 10 ** (threshold_db / 20.0)
    gain_b = np.ones(nb, dtype=np.float64)
    over = env > thr
    gain_b[over] = (thr + (env[over] - thr) / ratio) / (env[over] + 1e-12)
    gain = np.repeat(gain_b, block)[:n]
    makeup = 10 ** (makeup_db / 20.0)
    return (x * gain[:, None] * makeup).astype(np.float32)


# ─── Pitch shift / time stretch — real phase vocoder (STFT), decoupled ─────
# Old ffmpeg pipeline hacked pitch via asetrate+atempo (chipmunk artifacts and
# tempo/pitch coupled together). This is a genuine phase vocoder: pitch and
# tempo are independent controls, each backed by the same stretch primitive.

def _phase_vocoder_stretch(x, stretch, n_fft=2048, hop=512):
    """Time-stretch a mono float64 signal by `stretch` (out_len / in_len),
    preserving pitch, via STFT phase-accumulation (classic phase vocoder)."""
    if not SCIPY_OK or abs(stretch - 1.0) < 1e-3:
        return x.copy()
    n = len(x)
    if n <= n_fft:
        return x.copy()
    window = signal.windows.hann(n_fft, sym=False)
    out_hop = max(1, int(round(hop * stretch)))
    num_frames = 1 + (n - n_fft) // hop
    if num_frames < 1:
        return x.copy()
    n_bins = n_fft // 2 + 1
    omega = 2 * np.pi * hop * np.arange(n_bins) / n_fft
    prev_phase = np.zeros(n_bins)
    phase_acc = np.zeros(n_bins)
    out_len = out_hop * num_frames + n_fft
    y = np.zeros(out_len, dtype=np.float64)
    win_sum = np.zeros(out_len, dtype=np.float64)
    for i in range(num_frames):
        s = i * hop
        frame = x[s:s + n_fft]
        if len(frame) < n_fft:
            frame = np.pad(frame, (0, n_fft - len(frame)))
        spec = np.fft.rfft(frame * window)
        mag = np.abs(spec)
        phase = np.angle(spec)
        dphi = phase - prev_phase - omega
        dphi = dphi - 2 * np.pi * np.round(dphi / (2 * np.pi))
        true_freq = omega + dphi
        prev_phase = phase
        phase_acc = phase_acc + true_freq * stretch
        new_spec = mag * np.exp(1j * phase_acc)
        new_frame = np.fft.irfft(new_spec, n_fft) * window
        os_ = i * out_hop
        y[os_:os_ + n_fft] += new_frame
        win_sum[os_:os_ + n_fft] += window ** 2
    valid = win_sum > 1e-8
    y[valid] /= win_sum[valid]
    return y[:out_len]


def _pitch_shift(x, sr, semitones):
    if not SCIPY_OK or abs(semitones) < 1e-3:
        return x
    ratio = 2.0 ** (semitones / 12.0)
    chans = []
    for ch in range(x.shape[1]):
        stretched = _phase_vocoder_stretch(x[:, ch].astype(np.float64), ratio)
        resampled = signal.resample(stretched, x.shape[0])
        chans.append(resampled.astype(np.float32))
    n = min(len(c) for c in chans)
    return np.stack([c[:n] for c in chans], axis=1)


def _time_stretch(x, sr, tempo):
    if not SCIPY_OK or abs(tempo - 1.0) < 1e-3:
        return x
    chans = []
    for ch in range(x.shape[1]):
        stretched = _phase_vocoder_stretch(x[:, ch].astype(np.float64), 1.0 / tempo)
        chans.append(stretched.astype(np.float32))
    n = min(len(c) for c in chans)
    return np.stack([c[:n] for c in chans], axis=1)


# ─── Stereo width — mid/side matrix ─────────────────────────────────────────

def _stereo_width(x, width):
    if x.shape[1] < 2 or abs(width - 1.0) < 1e-3:
        return x
    mid = (x[:, 0] + x[:, 1]) * 0.5
    side = (x[:, 0] - x[:, 1]) * 0.5 * width
    left = mid + side
    right = mid - side
    return np.stack([left, right], axis=1).astype(np.float32)


# ─── Loudness — simplified BS.1770-style K-weighting + gating + true peak ──
# NOTE: this is a lightweight approximation (high-pass + shelf pre-filter,
# gated RMS), not a certified loudness meter. Good enough to bring levels
# into a consistent, sane ballpark; not a mastering-grade LUFS meter.

def _k_weight(x, sr):
    sos_hp = signal.butter(2, 60 / (sr / 2.0), btype='highpass', output='sos')
    b_shelf, a_shelf = _peaking_biquad(4000, 4.0, 0.7, sr)
    y = signal.sosfilt(sos_hp, x, axis=0)
    y = signal.lfilter(b_shelf, a_shelf, y, axis=0)
    return y


def _measure_lufs_ish(x, sr):
    kw = _k_weight(x, sr)
    block = max(1, int(0.4 * sr))
    hop = max(1, int(0.1 * sr))
    n = kw.shape[0]
    powers = []
    for s in range(0, max(n - block, 1), hop):
        seg = kw[s:s + block]
        p = float(np.mean(seg ** 2))
        if p > 0:
            powers.append(p)
    if not powers:
        powers = [float(np.mean(kw ** 2)) + 1e-12]
    powers = np.array(powers)
    gate = np.mean(powers) * 10 ** (-10 / 10.0)
    gated = powers[powers > gate] if np.any(powers > gate) else powers
    mean_p = np.mean(gated) + 1e-12
    return float(-0.691 + 10 * np.log10(mean_p))


def _true_peak_limit(x, sr, ceiling_db):
    ceiling = 10 ** (ceiling_db / 20.0)
    up = signal.resample_poly(x, 4, 1, axis=0)
    peak = np.max(np.abs(up)) + 1e-9
    y = x
    if peak > ceiling:
        y = x * (ceiling / peak)
    # soft-clip safety net for any residual overs
    return np.tanh(y / ceiling) * ceiling


def _loudness_normalize(x, sr, target_lufs, true_peak_db, limiter):
    if not SCIPY_OK or target_lufs is None:
        return x
    cur = _measure_lufs_ish(x, sr)
    gain_db = float(np.clip(target_lufs - cur, -24.0, 24.0))
    y = x * (10 ** (gain_db / 20.0))
    if limiter:
        y = _true_peak_limit(y, sr, true_peak_db)
    return y.astype(np.float32)


# ─── Fades — proper envelope curves (equal-power by default) ───────────────

def _fade_env(t, curve):
    if curve == 'Linear':
        return t
    if curve == 'Exponential':
        return t ** 2
    return np.sin(t * np.pi / 2.0)  # Equal Power (default) — perceptually smoother


def _apply_fades(x, sr, fade_in_s, fade_out_s, curve):
    n = x.shape[0]
    y = x.copy()
    if fade_in_s > 0:
        ni = min(n, int(fade_in_s * sr))
        if ni > 1:
            t = np.linspace(0.0, 1.0, ni)
            y[:ni] *= _fade_env(t, curve)[:, None]
    if fade_out_s > 0:
        no_ = min(n, int(fade_out_s * sr))
        if no_ > 1:
            t = np.linspace(1.0, 0.0, no_)
            y[n - no_:] *= _fade_env(t, curve)[:, None]
    return y


# ─── Main pipeline ───────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 4:
        print(json.dumps({'ok': False, 'error': 'usage: tilawa_dsp_studio.py <in> <out> <params.json>'}))
        return 1

    in_path, out_path, params_path = sys.argv[1], sys.argv[2], sys.argv[3]
    try:
        with open(params_path, 'r', encoding='utf-8') as fh:
            p = json.load(fh)
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'bad params json: {e}'}))
        return 1

    sr = int(p.get('sr', 48000))
    start = float(p.get('trim_start', 0.0))
    dur = float(p.get('trim_dur', 0.0))

    x = _decode(in_path, sr, start, dur)
    if x is None or x.shape[0] == 0:
        print(json.dumps({'ok': False, 'error': 'ffmpeg decode failed'}))
        return 1

    try:
        if p.get('reverse'):
            x = x[::-1].copy()

        dc = p.get('declick', {}) or {}
        if dc.get('enabled'):
            x = _declick(x, sr, float(dc.get('sensitivity', 50)))

        x = _apply_eq(x, sr, p.get('eq_freqs', []), p.get('eq_gains', []),
                      float(p.get('eq_q', 1.4)))

        nr = float((p.get('noise_reduction', {}) or {}).get('strength', 0))
        if nr > 0:
            x = _spectral_denoise(x, sr, nr)

        echo_mix = float((p.get('echo', {}) or {}).get('mix', 0))
        if echo_mix > 0:
            x = _echo(x, sr, echo_mix)

        rv = p.get('reverb', {}) or {}
        if float(rv.get('mix', 0)) > 0:
            x = _reverb(x, sr, float(rv.get('mix', 0)), rv.get('type', 'Room'))

        comp = p.get('compressor', {}) or {}
        if comp.get('enabled'):
            x = _compressor(x, sr, float(comp.get('threshold_db', -18)),
                             float(comp.get('ratio', 4)),
                             float(comp.get('attack_ms', 20)),
                             float(comp.get('release_ms', 200)),
                             float(comp.get('makeup_db', 0)))

        pitch = float(p.get('pitch_semitones', 0))
        if abs(pitch) > 1e-3:
            x = _pitch_shift(x, sr, pitch)

        tempo = float(p.get('tempo', 1.0))
        if abs(tempo - 1.0) > 1e-3:
            x = _time_stretch(x, sr, tempo)

        x = _stereo_width(x, float(p.get('stereo_width', 1.0)))

        vol = float(p.get('volume', 1.0))
        if abs(vol - 1.0) > 1e-3:
            x = x * vol

        loud = p.get('loudness', {}) or {}
        target = loud.get('target_lufs')
        if target is not None:
            x = _loudness_normalize(x, sr, float(target),
                                     float(loud.get('true_peak_limit_db', -1.0)),
                                     bool(loud.get('limiter', True)))

        x = _apply_fades(x, sr, float(p.get('fade_in', 0)), float(p.get('fade_out', 0)),
                          p.get('fade_curve', 'Equal Power'))

        x = np.clip(x, -1.0, 1.0).astype(np.float32)
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'dsp stage failed: {e}'}))
        return 1

    out_cfg = p.get('output', {}) or {}
    fmt = str(out_cfg.get('format', 'WAV')).upper()
    kbps = int(out_cfg.get('kbps', 192))
    ok = _encode(x, sr, out_path, fmt, kbps)
    print(json.dumps({'ok': ok, 'scipy': SCIPY_OK}))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
