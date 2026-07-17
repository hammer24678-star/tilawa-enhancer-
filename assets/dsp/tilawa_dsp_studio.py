#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tilawa_dsp_studio.py — S228 "Studio Engine" · S236 v2 "full FX suite + analysis"

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

USAGE (process):
    python3 tilawa_dsp_studio.py <in_path> <out_path> <params_json_path>

USAGE (analysis — S236):
    python3 tilawa_dsp_studio.py --analyze <in_path> <out_json_path>

Analysis writes JSON to <out_json_path> (NOT stdout — the proot channel
truncates stdout to its last 800 chars): real waveform peak/RMS buckets,
a log-spaced average spectrum, duration, peak/RMS dBFS, LUFS-ish loudness
and clipping percentage. The Flutter side uses it to draw the *actual*
waveform instead of placeholder bars.

<params_json_path> is a JSON file (see audio_editor_screen.dart
_buildDspParams()) describing the trim window, EQ bands, and every effect —
including, since S236, the entire `fx2` block (tone shaping, character FX,
stereo/space, cleanup & dynamics), which previously only existed in the
ffmpeg fallback chain and was silently dropped whenever this engine
succeeded. Prints {"ok": true} / {"ok": false, "error": "..."} to stdout
and exits 0/1 accordingly — the Dart side treats a non-zero exit as "fall
back to the plain ffmpeg filter chain", so it's safe for this script to
fail loud rather than produce silently-wrong audio.

Pipeline order (fixed, applied only where the relevant param is non-default):
  reverse → auto-trim silence → declip → declick → noise gate → de-hum →
  parametric EQ → spectral noise reduction → high/low-pass →
  bass/treble shelves → sub-bass → presence → vocal isolate →
  echo → convolution reverb →
  compressor → pitch shift → time stretch →
  tremolo → vibrato → chorus → flanger → phaser → bitcrush →
  stereo width → Haas widen → stereo enhance → swap/channel mode →
  de-esser → adaptive normalize → limiter →
  volume → loudness (LUFS-ish) normalize + true-peak limit →
  fades → pad start/end → clip → encode
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


def _encode(x: 'np.ndarray', sr: int, out_path: str, out_cfg: dict) -> bool:
    """S236: honors the Export-tab details that v1 ignored — output sample
    rate, mono/stereo channel count, WAV bit depth and metadata tags."""
    fmt = str(out_cfg.get('format', 'WAV')).upper()
    kbps = int(out_cfg.get('kbps', 192))
    out_sr = int(out_cfg.get('sample_rate', sr) or sr)
    out_ch = 1 if str(out_cfg.get('channels', 'Stereo')) == 'Mono' else 2
    depth = int(out_cfg.get('wav_bit_depth', 16) or 16)
    meta = out_cfg.get('metadata', {}) or {}

    raw = np.clip(x, -1.0, 1.0).astype(np.float32).tobytes()
    cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
           '-f', 'f32le', '-ar', str(sr), '-ac', '2', '-i', '-']
    for tag in ('title', 'artist', 'album'):
        v = str(meta.get(tag, '') or '').strip()
        if v:
            cmd += ['-metadata', f'{tag}={v}']
    cmd += ['-ar', str(out_sr), '-ac', str(out_ch)]
    if fmt == 'WAV':
        pcm = {16: 'pcm_s16le', 24: 'pcm_s24le', 32: 'pcm_s32le'}.get(depth, 'pcm_s16le')
        cmd += ['-c:a', pcm, out_path]
    else:
        codec = {'MP3': 'libmp3lame', 'M4A': 'aac'}.get(fmt, 'libmp3lame')
        cmd += ['-c:a', codec, '-b:a', f'{kbps}k', out_path]
    try:
        r = subprocess.run(cmd, input=raw, capture_output=True, timeout=180)
    except Exception:
        return False
    return r.returncode == 0 and os.path.exists(out_path) and os.path.getsize(out_path) > 44


# ─── Biquad designers — RBJ audio-cookbook ──────────────────────────────────

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


def _shelf_biquad(freq: float, gain_db: float, sr: int, kind: str = 'low',
                  slope: float = 0.9):
    """RBJ low-shelf / high-shelf biquad — real tone-shaping filters for the
    FX+ Bass/Treble Boost rows (v1 delegated these to ffmpeg `bass=`/`treble=`
    and then dropped them whenever the engine succeeded)."""
    a_amp = 10 ** (gain_db / 40.0)
    w0 = 2 * np.pi * freq / sr
    cosw0, sinw0 = np.cos(w0), np.sin(w0)
    alpha = sinw0 / 2.0 * np.sqrt((a_amp + 1 / a_amp) * (1 / slope - 1) + 2)
    two_sq = 2 * np.sqrt(a_amp) * alpha
    if kind == 'low':
        b0 = a_amp * ((a_amp + 1) - (a_amp - 1) * cosw0 + two_sq)
        b1 = 2 * a_amp * ((a_amp - 1) - (a_amp + 1) * cosw0)
        b2 = a_amp * ((a_amp + 1) - (a_amp - 1) * cosw0 - two_sq)
        a0 = (a_amp + 1) + (a_amp - 1) * cosw0 + two_sq
        a1 = -2 * ((a_amp - 1) + (a_amp + 1) * cosw0)
        a2 = (a_amp + 1) + (a_amp - 1) * cosw0 - two_sq
    else:
        b0 = a_amp * ((a_amp + 1) + (a_amp - 1) * cosw0 + two_sq)
        b1 = -2 * a_amp * ((a_amp - 1) + (a_amp + 1) * cosw0)
        b2 = a_amp * ((a_amp + 1) + (a_amp - 1) * cosw0 - two_sq)
        a0 = (a_amp + 1) - (a_amp - 1) * cosw0 + two_sq
        a1 = 2 * ((a_amp - 1) - (a_amp + 1) * cosw0)
        a2 = (a_amp + 1) - (a_amp - 1) * cosw0 - two_sq
    b = np.array([b0, b1, b2]) / a0
    a = np.array([1.0, a1 / a0, a2 / a0])
    return b, a


def _allpass_biquad(freq: float, q: float, sr: int):
    """RBJ allpass biquad — phaser stages."""
    w0 = 2 * np.pi * freq / sr
    alpha = np.sin(w0) / (2.0 * q)
    cosw0 = np.cos(w0)
    a0 = 1 + alpha
    b = np.array([1 - alpha, -2 * cosw0, 1 + alpha]) / a0
    a = np.array([1.0, -2 * cosw0 / a0, (1 - alpha) / a0])
    return b, a


# ─── Parametric EQ — real RBJ-cookbook peaking biquads, cascaded ────────────

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


# ─── Block envelope helper (compressor / gate / limiter share this) ─────────

def _block_env(x, sr, block_s=0.001, attack_ms=5.0, release_ms=150.0):
    """Per-block peak envelope with one-pole attack/release smoothing.
    Returns (env_per_block, block_len)."""
    block = max(16, int(sr * block_s))
    n = x.shape[0]
    nb = int(np.ceil(n / block))
    xa = np.abs(x).max(axis=1)
    pad = nb * block - n
    if pad:
        xa = np.concatenate([xa, np.zeros(pad)])
    lvl = xa.reshape(nb, block).max(axis=1)
    atk = np.exp(-block / (sr * max(attack_ms, 0.1) / 1000.0))
    rel = np.exp(-block / (sr * max(release_ms, 1.0) / 1000.0))
    env = np.zeros(nb, dtype=np.float64)
    e_prev = 0.0
    for i in range(nb):
        coeff = atk if lvl[i] > e_prev else rel
        e_prev = coeff * e_prev + (1.0 - coeff) * lvl[i]
        env[i] = e_prev
    return env, block


def _expand_gain(gain_b, block, n):
    return np.repeat(gain_b, block)[:n]


# ─── Compressor — block-envelope follower (fast, not sample-by-sample) ─────

def _compressor(x, sr, threshold_db, ratio, attack_ms, release_ms, makeup_db):
    if ratio <= 1.0:
        return x
    env, block = _block_env(x, sr, 0.001, attack_ms, release_ms)
    thr = 10 ** (threshold_db / 20.0)
    gain_b = np.ones_like(env)
    over = env > thr
    gain_b[over] = (thr + (env[over] - thr) / ratio) / (env[over] + 1e-12)
    gain = _expand_gain(gain_b, block, x.shape[0])
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


# ─── S236: FX+ — tone shaping ───────────────────────────────────────────────

def _apply_biquad(x, b, a):
    return signal.lfilter(b, a, x.astype(np.float64), axis=0)


def _tone_shelves(x, sr, bass_db, treble_db):
    if not SCIPY_OK:
        return x
    y = x.astype(np.float64)
    if abs(bass_db) >= 0.05:
        b, a = _shelf_biquad(100.0, float(np.clip(bass_db, -12, 12)), sr, 'low')
        y = _apply_biquad(y, b, a)
    if abs(treble_db) >= 0.05:
        b, a = _shelf_biquad(6500.0, float(np.clip(treble_db, -12, 12)), sr, 'high')
        y = _apply_biquad(y, b, a)
    return y.astype(np.float32)


def _sub_bass(x, sr, amount):
    """Adds a filtered low band back in (asubboost-style) — amount 0..100."""
    if not SCIPY_OK or amount <= 0:
        return x
    a = min(max(amount, 0.0), 100.0) / 100.0
    sos = signal.butter(4, 90.0 / (sr / 2.0), btype='low', output='sos')
    low = signal.sosfilt(sos, x.astype(np.float64), axis=0)
    return (x + a * 1.2 * low).astype(np.float32)


def _presence(x, sr, amount):
    """Clarity/crystalizer: soft-saturated high band mixed back in."""
    if not SCIPY_OK or amount <= 0:
        return x
    a = min(max(amount, 0.0), 100.0) / 100.0
    sos = signal.butter(2, 3500.0 / (sr / 2.0), btype='high', output='sos')
    hi = signal.sosfilt(sos, x.astype(np.float64), axis=0)
    excited = np.tanh(hi * 3.0) / 3.0
    return (x + a * 0.9 * excited).astype(np.float32)


def _hp_lp(x, sr, hp_hz, lp_hz):
    if not SCIPY_OK:
        return x
    y = x.astype(np.float64)
    nyq = sr / 2.0
    if hp_hz and hp_hz > 0:
        f = min(max(float(hp_hz), 10.0), nyq * 0.95)
        sos = signal.butter(2, f / nyq, btype='high', output='sos')
        y = signal.sosfilt(sos, y, axis=0)
    if lp_hz and 0 < lp_hz < 20000:
        f = min(max(float(lp_hz), 100.0), nyq * 0.98)
        sos = signal.butter(2, f / nyq, btype='low', output='sos')
        y = signal.sosfilt(sos, y, axis=0)
    return y.astype(np.float32)


# ─── S236: FX+ — character effects ──────────────────────────────────────────

def _tremolo(x, sr, amount, rate_hz=5.0):
    if amount <= 0:
        return x
    d = min(max(amount, 0.0), 100.0) / 100.0
    t = np.arange(x.shape[0]) / sr
    lfo = 1.0 - d * 0.5 * (1.0 + np.sin(2 * np.pi * rate_hz * t))
    return (x * lfo[:, None]).astype(np.float32)


def _mod_delay_read(x_ch, delay_samps):
    """Fractional modulated-delay read via linear interpolation (vectorized)."""
    n = len(x_ch)
    pos = np.arange(n) - delay_samps
    pos = np.clip(pos, 0.0, n - 1.0)
    return np.interp(pos, np.arange(n), x_ch)


def _vibrato(x, sr, amount, rate_hz=5.0):
    if amount <= 0:
        return x
    d = min(max(amount, 0.0), 100.0) / 100.0
    depth = d * 0.004 * sr          # up to ±4 ms pitch wobble
    base = depth + 8
    t = np.arange(x.shape[0])
    delay = base + depth * np.sin(2 * np.pi * rate_hz * t / sr)
    y = np.zeros_like(x, dtype=np.float64)
    for ch in range(x.shape[1]):
        y[:, ch] = _mod_delay_read(x[:, ch].astype(np.float64), delay)
    return y.astype(np.float32)


def _chorus(x, sr):
    """Three modulated delay taps (~20 ms base) blended with the dry path."""
    n = x.shape[0]
    t = np.arange(n)
    y = x.astype(np.float64).copy()
    for base_ms, depth_ms, rate, gain in [(18, 2.5, 0.8, 0.30),
                                          (24, 3.0, 1.1, 0.25),
                                          (30, 2.0, 0.6, 0.20)]:
        base = base_ms * sr / 1000.0
        depth = depth_ms * sr / 1000.0
        for ch in range(x.shape[1]):
            ph = ch * np.pi / 3  # slight L/R phase offset — wider image
            d2 = base + depth * np.sin(2 * np.pi * rate * t / sr + ph)
            y[:, ch] += gain * _mod_delay_read(x[:, ch].astype(np.float64), d2)
    peak = np.max(np.abs(y)) + 1e-9
    if peak > 1.0:
        y /= peak
    return y.astype(np.float32)


def _flanger(x, sr):
    """Classic swept short delay (0.5–5 ms, 0.25 Hz) mixed 50/50."""
    n = x.shape[0]
    t = np.arange(n)
    base = 0.003 * sr
    depth = 0.0025 * sr
    delay = base + depth * np.sin(2 * np.pi * 0.25 * t / sr)
    y = np.zeros_like(x, dtype=np.float64)
    for ch in range(x.shape[1]):
        wet = _mod_delay_read(x[:, ch].astype(np.float64), delay)
        y[:, ch] = 0.6 * x[:, ch] + 0.6 * wet
    peak = np.max(np.abs(y)) + 1e-9
    if peak > 1.0:
        y /= peak
    return y.astype(np.float32)


def _phaser(x, sr, stages=4, rate_hz=0.5):
    """Block-based cascade of LFO-swept allpass biquads (state carried across
    blocks so sweeps stay click-free)."""
    if not SCIPY_OK:
        return x
    block = 1024
    n = x.shape[0]
    y = np.zeros_like(x, dtype=np.float64)
    for ch in range(x.shape[1]):
        zi = [np.zeros(2) for _ in range(stages)]
        src = x[:, ch].astype(np.float64)
        dst = np.zeros(n, dtype=np.float64)
        for s in range(0, n, block):
            e = min(n, s + block)
            seg = src[s:e]
            t_mid = (s + e) / 2.0 / sr
            sweep = 0.5 * (1.0 + np.sin(2 * np.pi * rate_hz * t_mid))
            f0 = 300.0 * (2.0 ** (sweep * 3.0))  # 300 Hz .. 2.4 kHz sweep
            for st in range(stages):
                b, a = _allpass_biquad(min(f0 * (1.0 + 0.4 * st), sr * 0.45), 0.7, sr)
                seg, zi[st] = signal.lfilter(b, a, seg, zi=zi[st])
            dst[s:e] = seg
        y[:, ch] = 0.5 * src + 0.5 * dst
    return y.astype(np.float32)


def _bitcrush(x, amount):
    """Bit-depth quantize + sample-hold decimation — amount 0..100."""
    if amount <= 0:
        return x
    a = min(max(amount, 0.0), 100.0) / 100.0
    bits = 16.0 - a * 12.0                    # 16 → 4 bits
    levels = 2.0 ** bits
    y = np.round(x.astype(np.float64) * levels) / levels
    hold = int(1 + round(a * 7))              # 1 → 8× sample-hold
    if hold > 1:
        n = y.shape[0]
        idx = (np.arange(n) // hold) * hold
        y = y[idx]
    return y.astype(np.float32)


# ─── S236: FX+ — stereo & space ─────────────────────────────────────────────

def _stereo_width(x, width):
    if x.shape[1] < 2 or abs(width - 1.0) < 1e-3:
        return x
    mid = (x[:, 0] + x[:, 1]) * 0.5
    side = (x[:, 0] - x[:, 1]) * 0.5 * width
    left = mid + side
    right = mid - side
    return np.stack([left, right], axis=1).astype(np.float32)


def _haas(x, sr, delay_ms=15.0):
    """Haas widener — delays the right channel a few ms."""
    d = int(sr * delay_ms / 1000.0)
    if d <= 0 or d >= x.shape[0] or x.shape[1] < 2:
        return x
    r = np.concatenate([np.zeros(d, dtype=x.dtype), x[:-d, 1]])
    return np.stack([x[:, 0], r], axis=1)


def _stereo_enhance(x, amount):
    """extrastereo-style side gain: amount -100 (mono-ish) .. +100 (wide)."""
    if x.shape[1] < 2 or amount == 0:
        return x
    return _stereo_width(x, 1.0 + min(max(amount, -100.0), 100.0) / 100.0)


def _channel_mode(x, mode, swap_lr):
    y = x
    if swap_lr and y.shape[1] >= 2:
        y = y[:, ::-1].copy()
    if mode == 'Mono' and y.shape[1] >= 2:
        m = y.mean(axis=1)
        y = np.stack([m, m], axis=1)
    elif mode == 'Left' and y.shape[1] >= 2:
        y = np.stack([y[:, 0], y[:, 0]], axis=1)
    elif mode == 'Right' and y.shape[1] >= 2:
        y = np.stack([y[:, 1], y[:, 1]], axis=1)
    return y.astype(np.float32)


# ─── S238: voice/recitation tools ──────────────────────────────────────────

def _dehum(x, sr, base_hz, strength):
    """Mains-hum remover: narrow IIR notches at the base frequency (50 or
    60 Hz) and its first four harmonics. Strength widens the notches."""
    if not SCIPY_OK or strength <= 0:
        return x
    depth = min(max(strength, 0.0), 100.0) / 100.0
    q = float(np.interp(depth, [0, 1], [45.0, 22.0]))  # stronger = wider notch
    y = x.astype(np.float64)
    for k in range(1, 6):
        f = base_hz * k
        if f >= sr * 0.45:
            break
        b, a = signal.iirnotch(f / (sr / 2.0), q)
        y = signal.lfilter(b, a, y, axis=0)
    return y.astype(np.float32)


def _vocal_isolate(x, sr, amount):
    """Recitation/voice focus: the voice sits in the stereo center and the
    150 Hz–5 kHz band — attenuate the side channel (ambience, room) and
    gently emphasize the voice band. amount 0..100."""
    if not SCIPY_OK or amount <= 0:
        return x
    a = min(max(amount, 0.0), 100.0) / 100.0
    y = x.astype(np.float64)
    if y.shape[1] >= 2:
        mid = (y[:, 0] + y[:, 1]) * 0.5
        side = (y[:, 0] - y[:, 1]) * 0.5 * (1.0 - 0.85 * a)
        y = np.stack([mid + side, mid - side], axis=1)
    lo = 150.0 / (sr / 2.0)
    hi = min(5000.0, sr * 0.44) / (sr / 2.0)
    sos = signal.butter(2, [lo, hi], btype='band', output='sos')
    band = signal.sosfilt(sos, y, axis=0)
    y = (1.0 - 0.40 * a) * y + 0.55 * a * band
    return y.astype(np.float32)


# ─── S236: FX+ — cleanup & dynamics ────────────────────────────────────────

def _noise_gate(x, sr, threshold_db):
    """Soft downward expander below threshold (smoothed block envelope)."""
    env, block = _block_env(x, sr, 0.005, attack_ms=2.0, release_ms=120.0)
    thr = 10 ** (min(max(threshold_db, -80.0), -10.0) / 20.0)
    ratio = (env / (thr + 1e-12)) ** 2
    gain_b = np.clip(ratio, 0.0, 1.0)
    gain_b[env >= thr] = 1.0
    gain = _expand_gain(gain_b, block, x.shape[0])
    return (x * gain[:, None]).astype(np.float32)


def _deesser(x, sr, amount):
    """Split-band sibilance tamer: compress only the 4.5–9.5 kHz band."""
    if not SCIPY_OK or amount <= 0:
        return x
    strength = min(max(amount, 0.0), 100.0) / 100.0
    hi_edge = min(9500.0, sr * 0.45)
    sos = signal.butter(4, [4500.0 / (sr / 2.0), hi_edge / (sr / 2.0)],
                        btype='band', output='sos')
    band = signal.sosfilt(sos, x.astype(np.float64), axis=0)
    rest = x.astype(np.float64) - band
    env, block = _block_env(band.astype(np.float32), sr, 0.002,
                            attack_ms=1.0, release_ms=60.0)
    active = env[env > 1e-5]
    thr = np.percentile(active, 60) if active.size else 1.0
    gain_b = np.ones_like(env)
    over = env > thr
    gain_b[over] = (thr / (env[over] + 1e-12)) ** strength
    gain = _expand_gain(gain_b, block, x.shape[0])
    return (rest + band * gain[:, None]).astype(np.float32)


def _declip(x, sr):
    """Reconstructs clipped runs (|x| ≥ ~0.985) by interpolating from the
    surrounding clean samples — same interp strategy as _declick."""
    y = x.copy()
    idx = np.arange(x.shape[0])
    for ch in range(x.shape[1]):
        sig_ = x[:, ch].astype(np.float64)
        bad = np.abs(sig_) >= 0.985
        good = ~bad
        if np.any(bad) and np.sum(good) > 2:
            sig_[bad] = np.interp(idx[bad], idx[good], sig_[good])
            y[:, ch] = sig_.astype(np.float32)
    return y


def _adaptive_normalize(x, sr, target_rms_db=-16.0):
    """dynaudnorm-lite: frame-wise gain ride toward a target RMS, smoothed so
    it breathes instead of pumping."""
    frame = max(256, int(sr * 0.4))
    hop = frame // 2
    n = x.shape[0]
    if n < frame:
        return x
    mono = x.mean(axis=1).astype(np.float64)
    starts = np.arange(0, n - frame + 1, hop)
    rms = np.array([np.sqrt(np.mean(mono[s:s + frame] ** 2)) + 1e-9 for s in starts])
    target = 10 ** (target_rms_db / 20.0)
    gains = np.clip(target / rms, 0.5, 8.0)
    if len(gains) >= 5:  # gaussian-ish smoothing across frames
        kernel = np.array([0.06, 0.24, 0.4, 0.24, 0.06])
        gains = np.convolve(gains, kernel, mode='same')
    centers = starts + frame // 2
    per_sample = np.interp(np.arange(n), centers, gains)
    return np.clip(x * per_sample[:, None], -1.0, 1.0).astype(np.float32)


def _hard_limiter(x, sr, ceiling_db):
    """Look-ahead-ish limiter: smoothed gain reduction + safety clip."""
    ceiling = 10 ** (min(max(ceiling_db, -12.0), 0.0) / 20.0)
    env, block = _block_env(x, sr, 0.001, attack_ms=0.5, release_ms=50.0)
    gain_b = np.ones_like(env)
    over = env > ceiling
    gain_b[over] = ceiling / (env[over] + 1e-12)
    gain = _expand_gain(gain_b, block, x.shape[0])
    y = x * gain[:, None]
    return np.clip(y, -ceiling, ceiling).astype(np.float32)


def _auto_trim_silence(x, sr, thresh_db=-45.0, pad_s=0.08):
    env = np.abs(x).max(axis=1)
    thr = 10 ** (thresh_db / 20.0)
    above = np.flatnonzero(env > thr)
    if above.size == 0:
        return x
    pad = int(pad_s * sr)
    s = max(0, int(above[0]) - pad)
    e = min(x.shape[0], int(above[-1]) + pad)
    if e - s < int(0.05 * sr):
        return x
    return x[s:e].copy()


def _pad(x, sr, start_s, end_s):
    parts = []
    if start_s > 0:
        parts.append(np.zeros((int(start_s * sr), x.shape[1]), dtype=x.dtype))
    parts.append(x)
    if end_s > 0:
        parts.append(np.zeros((int(end_s * sr), x.shape[1]), dtype=x.dtype))
    return np.concatenate(parts, axis=0) if len(parts) > 1 else x


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


# ─── S236: ANALYSIS MODE — real waveform / spectrum / loudness for the UI ──

_ANALYZE_SR = 22050        # plenty for visuals + stats, keeps decode fast
_WAVE_BUCKETS = 96         # bars drawn by the Flutter waveform
_SPEC_BANDS = 30           # log-spaced spectrum bands (60 Hz .. 10 kHz)


def analyze(in_path: str, out_json: str) -> int:
    x = _decode(in_path, _ANALYZE_SR, 0.0, 0.0)
    if x is None or x.shape[0] == 0:
        print(json.dumps({'ok': False, 'error': 'ffmpeg decode failed'}))
        return 1
    try:
        n = x.shape[0]
        duration = n / float(_ANALYZE_SR)
        mono = x.mean(axis=1).astype(np.float64)

        # Waveform buckets — true peak + RMS per bucket, display-normalized.
        nb = _WAVE_BUCKETS
        edges = np.linspace(0, n, nb + 1).astype(int)
        peaks = np.zeros(nb)
        rms = np.zeros(nb)
        for i in range(nb):
            seg = mono[edges[i]:max(edges[i] + 1, edges[i + 1])]
            peaks[i] = np.max(np.abs(seg)) if seg.size else 0.0
            rms[i] = np.sqrt(np.mean(seg ** 2)) if seg.size else 0.0
        norm = max(float(peaks.max()), 1e-6)
        peaks_n = np.clip(peaks / norm, 0.0, 1.0)
        rms_n = np.clip(rms / norm, 0.0, 1.0)

        # Level stats (true dBFS, pre-normalization).
        peak_db = float(20 * np.log10(np.max(np.abs(mono)) + 1e-9))
        rms_db = float(20 * np.log10(np.sqrt(np.mean(mono ** 2)) + 1e-9))
        clip_pct = float(100.0 * np.mean(np.abs(mono) >= 0.985))
        lufs = None
        if SCIPY_OK:
            try:
                lufs = round(_measure_lufs_ish(x.astype(np.float64), _ANALYZE_SR), 1)
            except Exception:
                lufs = None

        # Average spectrum — log-spaced bands, normalized 0..1 over a 60 dB range.
        spectrum = []
        if SCIPY_OK and n > 4096:
            try:
                f, pxx = signal.welch(mono, fs=_ANALYZE_SR, nperseg=4096)
                band_edges = np.geomspace(60.0, min(10000.0, _ANALYZE_SR * 0.45),
                                          _SPEC_BANDS + 1)
                p_db = 10 * np.log10(pxx + 1e-14)
                top = float(p_db.max())
                for i in range(_SPEC_BANDS):
                    m = (f >= band_edges[i]) & (f < band_edges[i + 1])
                    v = float(p_db[m].mean()) if np.any(m) else -120.0
                    spectrum.append(round(float(np.clip((v - top + 60.0) / 60.0, 0.0, 1.0)), 3))
            except Exception:
                spectrum = []

        payload = {
            'ok': True,
            'duration_sec': round(duration, 3),
            'peaks': [round(float(v), 3) for v in peaks_n],
            'rms': [round(float(v), 3) for v in rms_n],
            'spectrum': spectrum,
            'peak_db': round(peak_db, 1),
            'rms_db': round(rms_db, 1),
            'lufs': lufs,
            'clip_pct': round(clip_pct, 2),
            'scipy': SCIPY_OK,
        }
        with open(out_json, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
        print(json.dumps({'ok': True, 'scipy': SCIPY_OK}))
        return 0
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'analysis failed: {e}'}))
        return 1


# ─── S238: SPLIT-BY-SILENCE — cut a recitation into pieces at the pauses ────
# python3 tilawa_dsp_studio.py --split <in> <out_base> <params.json>
# Writes <out_base>_001.<ext>, _002… and a <out_base>_report.json listing them.
# Perfect for splitting a long recitation into ayah-sized files: cuts are
# placed in the middle of each detected pause, and each piece keeps ~120 ms
# of breathing room on both sides.

def split_mode(in_path: str, out_base: str, params_path: str) -> int:
    try:
        with open(params_path, 'r', encoding='utf-8') as fh:
            p = json.load(fh)
    except Exception:
        p = {}
    sr = 32000  # decode rate for detection + output resampled by ffmpeg anyway
    thresh_db = float(p.get('silence_db', -40.0))
    min_sil = float(p.get('min_silence_s', 0.6))
    min_seg = float(p.get('min_seg_s', 1.0))
    out_cfg = p.get('output', {}) or {}
    fmt = str(out_cfg.get('format', 'MP3')).upper()
    ext = {'MP3': 'mp3', 'WAV': 'wav', 'M4A': 'm4a'}.get(fmt, 'mp3')

    x = _decode(in_path, sr, 0.0, 0.0)
    if x is None or x.shape[0] == 0:
        print(json.dumps({'ok': False, 'error': 'ffmpeg decode failed'}))
        return 1
    try:
        n = x.shape[0]
        env = np.abs(x).max(axis=1)
        # ~20 ms smoothing so consonant gaps don't read as pauses
        win = max(1, int(0.02 * sr))
        env = np.convolve(env, np.ones(win) / win, mode='same')
        thr = 10 ** (thresh_db / 20.0)
        silent = env < thr

        # find silent runs long enough to count as a pause; cut at run centers
        cuts = []
        run_start = None
        for i in range(n + 1):
            is_sil = silent[i] if i < n else False
            if is_sil and run_start is None:
                run_start = i
            elif not is_sil and run_start is not None:
                if i - run_start >= int(min_sil * sr):
                    cuts.append((run_start + i) // 2)
                run_start = None

        bounds = [0] + cuts + [n]
        pad = int(0.12 * sr)
        segments = []
        for a, b in zip(bounds[:-1], bounds[1:]):
            aa = max(0, a - (pad if a > 0 else 0))
            bb = min(n, b + (pad if b < n else 0))
            seg = x[aa:bb]
            if bb - aa < int(min_seg * sr):
                continue
            if float(np.max(np.abs(seg))) < thr:  # pure silence — drop
                continue
            segments.append((aa, bb))

        if not segments:
            print(json.dumps({'ok': False, 'error': 'no segments found — lower the silence threshold'}))
            return 1

        files = []
        for i, (a, b) in enumerate(segments, start=1):
            out_path = f'{out_base}_{i:03d}.{ext}'
            if _encode(x[a:b].copy(), sr, out_path, out_cfg):
                files.append({'path': out_path,
                              'start_sec': round(a / sr, 2),
                              'dur_sec': round((b - a) / sr, 2)})
        report = {'ok': len(files) > 0, 'count': len(files), 'files': files}
        with open(f'{out_base}_report.json', 'w', encoding='utf-8') as fh:
            json.dump(report, fh)
        print(json.dumps({'ok': len(files) > 0, 'count': len(files)}))
        return 0 if files else 1
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'split failed: {e}'}))
        return 1


# ─── Main pipeline ───────────────────────────────────────────────────────────

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == '--split':
        if len(sys.argv) < 5:
            print(json.dumps({'ok': False,
                              'error': 'usage: tilawa_dsp_studio.py --split <in> <out_base> <params.json>'}))
            return 1
        return split_mode(sys.argv[2], sys.argv[3], sys.argv[4])

    if len(sys.argv) >= 2 and sys.argv[1] == '--analyze':
        if len(sys.argv) < 4:
            print(json.dumps({'ok': False,
                              'error': 'usage: tilawa_dsp_studio.py --analyze <in> <out.json>'}))
            return 1
        return analyze(sys.argv[2], sys.argv[3])

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

    fx = p.get('fx2', {}) or {}

    try:
        if p.get('reverse'):
            x = x[::-1].copy()

        # ── cleanup first: silence trim, declip, declick, gate ──
        if fx.get('auto_trim_silence'):
            x = _auto_trim_silence(x, sr)

        if fx.get('declip'):
            x = _declip(x, sr)

        dc = p.get('declick', {}) or {}
        if dc.get('enabled'):
            x = _declick(x, sr, float(dc.get('sensitivity', 50)))

        gate = fx.get('noise_gate', {}) or {}
        if gate.get('enabled'):
            x = _noise_gate(x, sr, float(gate.get('threshold_db', -50)))

        # S238 — mains-hum removal early, before any spectral shaping
        hum = fx.get('dehum', {}) or {}
        if hum.get('enabled'):
            x = _dehum(x, sr, float(hum.get('base_hz', 50)),
                       float(hum.get('strength', 60)))

        # ── spectral shaping ──
        x = _apply_eq(x, sr, p.get('eq_freqs', []), p.get('eq_gains', []),
                      float(p.get('eq_q', 1.4)))

        nr = float((p.get('noise_reduction', {}) or {}).get('strength', 0))
        if nr > 0:
            x = _spectral_denoise(x, sr, nr)

        x = _hp_lp(x, sr, float(fx.get('highpass_hz', 0) or 0),
                   float(fx.get('lowpass_hz', 20000) or 20000))

        x = _tone_shelves(x, sr, float(fx.get('bass_db', 0) or 0),
                          float(fx.get('treble_db', 0) or 0))

        if float(fx.get('sub_bass', 0) or 0) > 0:
            x = _sub_bass(x, sr, float(fx.get('sub_bass', 0)))

        if float(fx.get('presence', 0) or 0) > 0:
            x = _presence(x, sr, float(fx.get('presence', 0)))

        # S238 — voice/recitation focus
        if float(fx.get('vocal_isolate', 0) or 0) > 0:
            x = _vocal_isolate(x, sr, float(fx.get('vocal_isolate', 0)))

        # ── space ──
        echo_mix = float((p.get('echo', {}) or {}).get('mix', 0))
        if echo_mix > 0:
            x = _echo(x, sr, echo_mix)

        rv = p.get('reverb', {}) or {}
        if float(rv.get('mix', 0)) > 0:
            x = _reverb(x, sr, float(rv.get('mix', 0)), rv.get('type', 'Room'))

        # ── dynamics (main compressor) ──
        comp = p.get('compressor', {}) or {}
        if comp.get('enabled'):
            x = _compressor(x, sr, float(comp.get('threshold_db', -18)),
                             float(comp.get('ratio', 4)),
                             float(comp.get('attack_ms', 20)),
                             float(comp.get('release_ms', 200)),
                             float(comp.get('makeup_db', 0)))

        # ── pitch / tempo ──
        pitch = float(p.get('pitch_semitones', 0))
        if abs(pitch) > 1e-3:
            x = _pitch_shift(x, sr, pitch)

        tempo = float(p.get('tempo', 1.0))
        if abs(tempo - 1.0) > 1e-3:
            x = _time_stretch(x, sr, tempo)

        # ── character FX ──
        if float(fx.get('tremolo', 0) or 0) > 0:
            x = _tremolo(x, sr, float(fx.get('tremolo', 0)))
        if float(fx.get('vibrato', 0) or 0) > 0:
            x = _vibrato(x, sr, float(fx.get('vibrato', 0)))
        if fx.get('chorus'):
            x = _chorus(x, sr)
        if fx.get('flanger'):
            x = _flanger(x, sr)
        if fx.get('phaser'):
            x = _phaser(x, sr)
        if float(fx.get('bitcrush', 0) or 0) > 0:
            x = _bitcrush(x, float(fx.get('bitcrush', 0)))

        # ── stereo & space ──
        x = _stereo_width(x, float(p.get('stereo_width', 1.0)))
        if fx.get('haas_widen'):
            x = _haas(x, sr)
        if float(fx.get('stereo_fx', 0) or 0) != 0:
            x = _stereo_enhance(x, float(fx.get('stereo_fx', 0)))
        x = _channel_mode(x, str(fx.get('channel_mode', 'Stereo')),
                          bool(fx.get('swap_lr', False)))

        # ── final cleanup & dynamics ──
        if float(fx.get('deesser', 0) or 0) > 0:
            x = _deesser(x, sr, float(fx.get('deesser', 0)))
        if fx.get('adaptive_normalize'):
            x = _adaptive_normalize(x, sr)
        lim = fx.get('limiter', {}) or {}
        if lim.get('enabled'):
            x = _hard_limiter(x, sr, float(lim.get('ceiling_db', -1.0)))

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

        x = _pad(x, sr, float(fx.get('pad_start_sec', 0) or 0),
                 float(fx.get('pad_end_sec', 0) or 0))

        x = np.clip(x, -1.0, 1.0).astype(np.float32)
    except Exception as e:
        print(json.dumps({'ok': False, 'error': f'dsp stage failed: {e}'}))
        return 1

    ok = _encode(x, sr, out_path, p.get('output', {}) or {})
    print(json.dumps({'ok': ok, 'scipy': SCIPY_OK}))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
