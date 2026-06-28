#!/usr/bin/env python3
"""
الصفاء v5  —  Dedicated Dereverberation Engine
إزالة الصدى والريفيرب

FIXES vs v4 (v5):
  B6  DF3 blending: replaced hard zone assignment + boundary-only crossfades
      with continuous soft-weight blend (Gaussian-smoothed across ~300ms).
      Root cause of "يروح ويجي" (comes-and-goes effect) was that attenuation
      was constant inside each LOUD/MID/QUIET zone — only the boundary had a
      crossfade. Now every sample gets its own uniquely blended attenuation
      level that tracks signal RMS continuously. Zero zone steps.

FIXES vs v2:
  B1  _jalaa() late window: 150ms → 450ms (was reading 50-200ms; §3.3 says 50-500ms)
  B2  _decode() now uses pcm_f32le → float32; soundfile when available (no 16-bit truncation)
  B3  _band_energy() samples across full file (was FFT of first 1024 samples only)
  B4  G4 Ra-trill: scans full audio in overlapping 1s windows (was first 1s only)
  B5  _rt60() fallback slope condition was malformed (med-4 guard logic fixed)

IMPROVEMENTS vs v2:
  I1  DF3 three passes now run in parallel (ThreadPoolExecutor) — 3× faster
  I2  _enc() intermediates are mono; only final output is stereo
  I3  _tailnr() reduces nr by 1 when JALAA already ran (avoid double-attenuation)
  I4  DF3 speech-pass attenuation capped to §79 per-style limits:
        Murattal ≤ 18 dB  /  Mujawwad ≤ 6 dB
  I5  WPE LRA check uses 50% overlapping frames (was non-overlapping → noisy)
  I6  SafaaState gains guard_pass/guard_warn lists (structured; JSON report improved)
  I7  LF EQ: LF band RT60 scaled by 1.3× per §3.4 (LF decays slower than broadband)
  I8  process() tracks all temp paths; single cleanup on exit (no leaks)
  I9  _decode() try/finally ensures temp file removed on exception
  I10 DRR-weighted JALAA: skip when DRR already > 6 dB (room is already reasonably dry)

PIPELINE  (unchanged order)
  S1  RT60 estimation (Schroeder backward integration)
  S2  Sub-band LF room mode removal (3 bands, LF-scaled depth) [B5/I7]
  S3  WPE dereverberation RT60 > 1.0s
  S4  DF3 reverb-adapted (4 passes parallel, continuous soft-weight blend) [I1/I4/B6]
  S5  JALAA per-frame DRR gate [B1/I10]
  S6  Tail floor NR (afftdn calibrated) [I3]
  S7  Arabic phoneme guards [B3/B4]
  S8a dynaudnorm level evenness (f=500ms, m=10, p=0.92) — kills DF3 adaptation bumps
  S8b Volume boost: standard=1.85, aggressive=7.40 (4x)

USAGE
  python3 engine_safaa_v3.py input.wav output.wav [--tier X] [--mujawwad 0.0] [--rt60 0.0]

KB REFS: §3 §28 §35 §36 §52 §79 §109 §138 §140 §143 §145 §151 §152 §154
"""
from __future__ import annotations

__version__ = 'v5'

import os, shutil, subprocess, tempfile, warnings, multiprocessing as _mp
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple
warnings.filterwarnings('ignore')

_TMP = tempfile.gettempdir()

try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

try:
    import soundfile as SF
    SF_OK = True
except ImportError:
    SF_OK = False

try:
    from scipy.io import wavfile as _scipy_wavfile
    SCIPY_WAV_OK = True
except ImportError:
    SCIPY_WAV_OK = False

# DF3 binary — search order: HF Space path first, then local dev paths
_DF3_CLI_BIN = ''
for _c in [
    # '/app/deep-filter' — HF-Space Docker path; removed for local proot mode (S203)
    '/home/claude/deep-filter',  # local Termux/Claude dev
    'deep-filter',               # in PATH
    'deepfilter',
    'deep_filter',
]:
    # shutil.which handles both absolute paths (existence+exec check) and PATH search
    if shutil.which(_c) or (os.path.isfile(_c) and os.access(_c, os.X_OK)):
        _DF3_CLI_BIN = _c; break
DF3_OK = bool(_DF3_CLI_BIN)

# nara_wpe
WPE_OK = False
try:
    from nara_wpe.wpe import wpe_v8
    from nara_wpe.utils import stft as _wpe_stft, istft as _wpe_istft
    WPE_OK = True
except ImportError:
    pass

# ─── Constants ────────────────────────────────────────────────────────────────
SR             = 48000
WAV_CODEC      = 'pcm_s24le'
RT60_MIN       = 0.15    # below: nothing to do
RT60_WPE_MIN   = 1.00    # §109.6
RT60_TAILNR    = 0.30
RT60_AGGR      = 1.50
MUJ_RT60_FLOOR = 1.20    # §145.3

# §79 per-style DF attenuation hard limits — v4: raised for deeper cleaning
_DF3_LIM_MURATTAL  = 24   # dB maximum (was 18)
_DF3_LIM_MUJAWWAD  =  8   # dB maximum (was 6)
_DF3_SPEECH        = 15   # was 12
_DF3_TRANS         = 24   # was 20
_DF3_TAIL          = 32   # was 28

_CHUNK_S       = 0.100
_XFADE_N       = 960

_RMS_MAX_DELTA = 1.0
_LRA_MAX_DELTA = 0.5     # §109.4

DRR_ALREADY_DRY = 3.0   # v4: lower threshold → JALAA runs on more material (was 6.0)


# ─── State ────────────────────────────────────────────────────────────────────
@dataclass
class SafaaState:
    input_path:    str   = ''
    source_tier:   str   = 'TIER_UNKNOWN'
    mujawwad_conf: float = 0.0
    rt60_initial:  float = 0.0
    drr_before:    float = 0.0
    drr_after:     float = 0.0
    lf_eq:         bool  = False
    wpe:           bool  = False
    df3:           bool  = False
    jalaa:         bool  = False
    tail_nr:       bool  = False
    guard_reverts: int   = 0
    guard_pass:    List[str] = field(default_factory=list)   # [I6]
    guard_warn:    List[str] = field(default_factory=list)   # [I6]
    log:           List[str] = field(default_factory=list)
    _tmps:         List[str] = field(default_factory=list, repr=False)

def _L(st, msg):
    st.log.append(msg); print(msg)

def _track(st, path):
    """Register a temp path for cleanup. Returns path."""
    if path and path not in (st.input_path,):
        st._tmps.append(path)
    return path

def _cleanup_all(st):
    for p in st._tmps:
        try:
            if p and os.path.exists(p): os.unlink(p)
        except Exception:
            pass
    st._tmps.clear()


# ─── FFmpeg helpers ───────────────────────────────────────────────────────────
def _run(cmd, timeout=600):
    r = subprocess.run(cmd, capture_output=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr

def _tmp(tag, st=None):
    p = os.path.join(_TMP, f'safaa3_{tag}_{os.getpid()}.wav')
    if st is not None:
        st._tmps.append(p)
    return p

def _cleanup(*paths):
    for p in paths:
        try:
            if p and os.path.exists(p): os.unlink(p)
        except Exception:
            pass

def _decode(path, st=None):
    """
    Float32 mono at SR. [B2/I9]
    Uses soundfile when available (faster, native float32).
    Falls back to ffmpeg pcm_f32le + wave read.
    try/finally ensures temp file removed on exception.
    """
    if not NUMPY_OK:
        return None
    t = None
    try:
        if SF_OK:
            # ffmpeg → pcm_f32le temp, then soundfile reads it natively
            t = os.path.join(_TMP, f'safaa3_dec_{os.getpid()}.wav')
            rc, _, _ = _run(['ffmpeg', '-y', '-i', path,
                             '-acodec', 'pcm_f32le',
                             '-ar', str(SR), '-ac', '1',
                             '-loglevel', 'error', t])
            if rc or not os.path.exists(t):
                return None
            data, _ = SF.read(t, dtype='float32', always_2d=False)
            return data
        elif SCIPY_WAV_OK:
            # scipy.io.wavfile can read pcm_f32le natively
            t = os.path.join(_TMP, f'safaa3_dec_{os.getpid()}.wav')
            rc, _, _ = _run(['ffmpeg', '-y', '-i', path,
                             '-acodec', 'pcm_f32le',
                             '-ar', str(SR), '-ac', '1',
                             '-loglevel', 'error', t])
            if rc or not os.path.exists(t):
                return None
            _, data = _scipy_wavfile.read(t)
            if data.dtype != np.float32:
                data = data.astype(np.float32) / np.iinfo(data.dtype).max
            return data.copy()
        else:
            # Final fallback: pcm_s16le → int16 → float32 normalised
            t = os.path.join(_TMP, f'safaa3_dec_{os.getpid()}.wav')
            rc, _, _ = _run(['ffmpeg', '-y', '-i', path,
                             '-acodec', 'pcm_s16le',
                             '-ar', str(SR), '-ac', '1',
                             '-loglevel', 'error', t])
            if rc or not os.path.exists(t):
                return None
            import wave as _w
            with _w.open(t, 'rb') as f:
                raw = f.readframes(f.getnframes())
            return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    except Exception:
        return None
    finally:
        if t and os.path.exists(t):
            try: os.unlink(t)
            except Exception: pass

def _enc_mono(src, dst):
    """Intermediate encode: mono 24-bit. [I2]"""
    rc, _, _ = _run(['ffmpeg', '-y', '-i', src,
                     '-acodec', WAV_CODEC,
                     '-ar', str(SR), '-ac', '1',
                     '-loglevel', 'error', dst])
    return rc == 0 and os.path.exists(dst)

def _enc_stereo(src, dst):
    """Final output encode: stereo 24-bit. [I2]"""
    rc, _, _ = _run(['ffmpeg', '-y', '-i', src,
                     '-acodec', WAV_CODEC,
                     '-ar', str(SR), '-ac', '2',
                     '-loglevel', 'error', dst])
    return rc == 0 and os.path.exists(dst)

def _rmsdb(s):
    return float(20 * np.log10(np.sqrt(np.mean(s ** 2)) + 1e-10))

def _band_energy(s, flo, fhi, n_fft=2048, n_samples=8):
    """
    Band energy estimate sampled across the full signal. [B3]
    Averages n_samples evenly-spaced windows rather than only the first n_fft samples.
    """
    if len(s) < n_fft:
        return 0.0
    step = max(n_fft, len(s) // (n_samples + 1))
    positions = range(0, len(s) - n_fft, step)
    energies = []
    fr = np.fft.rfftfreq(n_fft, 1.0 / SR)
    mask = (fr >= flo) & (fr <= fhi)
    for pos in positions:
        sp = np.abs(np.fft.rfft(s[pos:pos + n_fft], n=n_fft))
        energies.append(float(np.mean(sp[mask] ** 2) + 1e-20))
    return float(np.mean(energies)) if energies else 0.0


# ─── Stage 1: RT60 (Schroeder backward integration) ──────────────────────────
def _rt60(samples, sr=SR):
    """
    Schroeder backward integration (§3.1).
    Find -5 dB and -25 dB crossings of backward energy → T20 × 3 = T60.
    Fallback: linear regression on the decay region. [B5]
    """
    if not NUMPY_OK or samples is None or len(samples) < sr * 3:
        return 0.0
    fn = int(0.020 * sr)
    n = len(samples) // fn
    if n < 30:
        return 0.0

    energy = np.array([float(np.mean(samples[i * fn:(i + 1) * fn] ** 2)) for i in range(n)])
    energy = np.maximum(energy, 1e-20)
    sch = np.cumsum(energy[::-1])[::-1]
    sch_db = 10 * np.log10(sch / (sch[0] + 1e-20))

    t5 = t25 = None
    for i, v in enumerate(sch_db):
        if t5  is None and v <= -5.0:  t5  = i * 0.020
        if t25 is None and v <= -25.0: t25 = i * 0.020; break
    if t5 is not None and t25 is not None and t25 > t5:
        return float(np.clip((t25 - t5) * 3.0, 0.0, 6.0))

    # Fallback: slope estimation on the decay tail [B5]
    edb = 10 * np.log10(energy)
    med = float(np.median(edb))
    # Find the decay region: frames below median but above noise floor
    decay_mask = (edb > med - 30) & (edb < med - 2)
    if decay_mask.sum() < 6:
        return 0.0
    t_arr = np.where(decay_mask)[0] * 0.020
    e_arr = edb[decay_mask]
    slope = float(np.polyfit(t_arr, e_arr, 1)[0])
    if slope >= -1.0:
        return 0.0
    return float(np.clip(60.0 / abs(slope), 0.0, 4.0))


def _drr(samples, sr=SR):
    """
    DRR: energy ratio early(0-50ms) vs late(50-500ms) (§3.3/§28.6).
    """
    if not NUMPY_OK or samples is None:
        return 0.0
    en = int(0.050 * sr)
    ln = int(0.450 * sr)           # late window: 50-500ms
    step = int(0.200 * sr)
    vals = []
    for s in range(0, len(samples) - en - ln, step):
        er = float(np.sqrt(np.mean(samples[s:s + en] ** 2)) + 1e-10)
        lr = float(np.sqrt(np.mean(samples[s + en:s + en + ln] ** 2)) + 1e-10)
        if er > 1e-5 and lr > 1e-5:
            vals.append(20.0 * np.log10(er / lr))
    return float(np.median(vals)) if vals else 0.0


# ─── Stage 2: Sub-band LF EQ (§3.4) ─────────────────────────────────────────
def _lf_eq(wav, samples, rt60, st):
    """
    Three EQ bands with LF-scaled depth. [I7]
    §3.4: LF bands have longer RT60 (empirically ~1.3× broadband).
    Apply the LF multiplier before computing per-band depth.
    Mujawwad: reduce depth and enforce RT60 floor (§145.3).
    """
    if rt60 < RT60_MIN:
        return wav
    lf_rt60  = rt60 * 1.30        # §3.4: LF decays ~30% slower [I7]
    scale    = float(np.clip(lf_rt60 / 0.5, 1.0, 6.0))
    d_sub    = float(np.clip(scale * 1.0, 1.0, 6.0))
    d_lo     = float(np.clip(scale * 0.7, 0.7, 4.2))
    d_room   = float(np.clip(scale * 0.4, 0.4, 2.4))

    if st.mujawwad_conf > 0.6:
        d_sub *= 0.5; d_lo *= 0.5; d_room *= 0.5
        if rt60 < MUJ_RT60_FLOOR * 1.5:
            r = float(np.clip((rt60 - MUJ_RT60_FLOOR) / (MUJ_RT60_FLOOR * 0.5 + 0.001), 0, 1))
            d_sub *= r; d_lo *= r; d_room *= r
            _L(st, f'  [S2-LF] Mujawwad floor limiter ratio={r:.2f}')

    flt = []
    if d_sub  > 0.2: flt.append(f'equalizer=f=150:width_type=o:width=1.4:g=-{d_sub:.1f}')
    if d_lo   > 0.2: flt.append(f'equalizer=f=300:width_type=o:width=1.2:g=-{d_lo:.1f}')
    if d_room > 0.2: flt.append(f'equalizer=f=500:width_type=o:width=1.0:g=-{d_room:.1f}')
    if not flt:
        return wav

    out = _tmp('s2', st)
    rc, _, _ = _run(['ffmpeg', '-y', '-i', wav, '-af', ','.join(flt),
                     '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '1',  # mono [I2]
                     '-loglevel', 'error', out])
    if rc or not os.path.exists(out):
        return wav

    post = _decode(out)
    if post is not None and samples is not None:
        d = _rmsdb(post) - _rmsdb(samples)
        if abs(d) > 3.0:   # relaxed: LF EQ at high RT60 can legitimately remove >1dB
            _cleanup(out); st.guard_reverts += 1
            _L(st, f'  [S2-LF] RMS Δ={d:+.2f}dB — REVERT'); return wav

    st.lf_eq = True
    _L(st, f'  [S2-LF] ✓ lf_rt60={lf_rt60:.2f}s sub={d_sub:.1f} lo={d_lo:.1f} room={d_room:.1f} dB')
    return out


# ─── Stage 3: WPE (threshold 1.0s, §109.6) ───────────────────────────────────
def _lra_overlapping(s, frame_s=0.4, hop_s=0.2, sr=SR):
    """LRA estimate using 50% overlapping frames. [I5]"""
    fn = int(frame_s * sr)
    hn = int(hop_s * sr)
    if len(s) < fn:
        return 0.0
    db = [float(20 * np.log10(np.sqrt(np.mean(s[i:i + fn] ** 2)) + 1e-10))
          for i in range(0, len(s) - fn, hn)]
    return float(np.percentile(db, 95) - np.percentile(db, 10)) if len(db) >= 4 else 0.0

# S190: hard cap — wall-clock cap on WPE so a slow/atypical file (e.g. RT60=6s,
# taps=12) can't eat the entire 600s job budget and get SIGKILL'd.
# WPE runs in a forked child; if it exceeds WPE_TIMEOUT_S we kill just
# that worker and continue to S4-DF3 with the un-dereverbed audio.
WPE_TIMEOUT_S = 240

def _wpe_compute_worker(mi, mo, rt60, mujawwad_conf, sr, lra_max, q):
    """Forked worker: runs wpe_v8 + writes result wav; sends small dict back via queue."""
    try:
        if SF_OK:
            y, _ = SF.read(mi, dtype='float32', always_2d=False)
        else:
            import wave as _w
            with _w.open(mi, 'rb') as f: raw = f.readframes(f.getnframes())
            y = np.frombuffer(raw, dtype=np.float32).copy()

        if   mujawwad_conf > 0.6: taps, iters = 5, 2
        elif rt60 > 4.0:           taps, iters = 12, 3
        elif rt60 > 2.0:           taps, iters = 10, 3
        else:                      taps, iters = 8, 3
        delay = 3

        Y = _wpe_stft(y, size=512, shift=128)
        Z = wpe_v8(Y[..., np.newaxis], taps=taps, delay=delay, iterations=iters)
        z = _wpe_istft(Z[..., 0], size=512, shift=128)
        z = z[:len(y)] if len(z) > len(y) else np.pad(z, (0, len(y) - len(z)))

        ld = abs(_lra_overlapping(y) - _lra_overlapping(z))
        if ld > lra_max:
            Z2 = wpe_v8(Y[..., np.newaxis], taps=taps, delay=delay, iterations=max(1, iters-1))
            z2 = _wpe_istft(Z2[..., 0], size=512, shift=128)
            z2 = z2[:len(y)] if len(z2) > len(y) else np.pad(z2, (0, len(y)-len(z2)))
            ld2 = abs(_lra_overlapping(y) - _lra_overlapping(z2))
            if ld2 > lra_max:
                q.put({'ok': False, 'reason': f'LRA {ld2:.2f}LU after retry — REVERT'})
                return
            z = z2; ld = ld2

        if SF_OK:
            SF.write(mo, z.astype(np.float32), sr, subtype='FLOAT')
        else:
            import wave as _w
            b16 = (np.clip(z, -1, 1) * 32767).astype(np.int16)
            with _w.open(mo, 'wb') as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(sr)
                f.writeframes(b16.tobytes())
        q.put({'ok': True, 'taps': taps, 'delay': delay, 'iters': iters, 'ld': float(ld)})
    except Exception as e:
        q.put({'ok': False, 'reason': f'exception: {e}'})


def _wpe(wav, rt60, st):
    if not WPE_OK:
        _L(st, '  [S3-WPE] nara_wpe not installed → pip install nara_wpe soundfile')
        return wav
    if rt60 < RT60_WPE_MIN:
        _L(st, f'  [S3-WPE] RT60={rt60:.2f}s < {RT60_WPE_MIN}s — skip (§109.6)')
        return wav

    _L(st, f'  [S3-WPE] RT60={rt60:.2f}s — running WPE (cap={WPE_TIMEOUT_S}s) [S190]')
    d = tempfile.mkdtemp(prefix='safaa3_wpe_')
    try:
        mi = os.path.join(d, 'in.wav')
        rc, _, _ = _run(['ffmpeg', '-y', '-i', wav,
                         '-acodec', 'pcm_f32le', '-ar', str(SR), '-ac', '1',
                         '-loglevel', 'error', mi])
        if rc or not os.path.exists(mi):
            return wav

        mo = os.path.join(d, 'out.wav')
        ctx = _mp.get_context('fork')
        q   = ctx.Queue()
        proc = ctx.Process(
            target=_wpe_compute_worker,
            args=(mi, mo, rt60, st.mujawwad_conf, SR, _LRA_MAX_DELTA, q))
        proc.start()
        proc.join(WPE_TIMEOUT_S)
        if proc.is_alive():
            proc.terminate(); proc.join(5)
            if proc.is_alive(): proc.kill(); proc.join(5)
            st.guard_reverts += 1
            _L(st, f'  [S3-WPE] ⏱ TIMED OUT after {WPE_TIMEOUT_S}s — '
                   f'skipping WPE, continuing to S4-DF3 [S190]')
            return wav

        result = q.get() if not q.empty() else {'ok': False, 'reason': 'worker died silently'}
        if not result.get('ok'):
            st.guard_reverts += 1
            _L(st, f"  [S3-WPE] {result.get('reason','failed')} — REVERT")
            return wav

        out = _tmp('s3', st)
        if not _enc_mono(mo, out):
            return wav
        st.wpe = True
        _L(st, f"  [S3-WPE] ✓ taps={result['taps']} delay={result['delay']} "
               f"iters={result['iters']} LRA Δ={result['ld']:.2f}LU")
        return out
    except Exception as e:
        _L(st, f'  [S3-WPE] exception: {e}'); return wav
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ─── Stage 4: DF3 smooth adaptive VAD (§22.5 / §106 / RL-01 / RL-16) ─────────
_ADF_LOUD_T   = -15.0         # dBFS — projecting voice → protect
_ADF_QUIET_T  = -25.0         # dBFS — soft/breath → clean hard
_ADF_SNR_GATE = 10.0          # v4: lower gate → more chunks get cleaned (was 12)
_ADF_CHUNK_S  = 0.050         # 50ms chunks — finer granularity than isteidad 100ms
# v5: continuous blend — no hard zones, no boundary-only crossfades
_ADF_SIGMA_DB  = 4.0          # dBFS half-width of loud↔quiet soft transition
_ADF_SMOOTH_C  = 6            # Gaussian temporal smoothing width in chunks (~300ms @ 50ms/chunk)
_ADF_GATE_MAX  = 0.70         # max SNR-gate fraction; always retain ≥30% DF3 on clean chunks
# RL-16: guard bands — restore these from original after blend
_RL16_BANDS   = [(220, 290), (950, 1100)]   # Hz: Ghunnah nasal pole + formant zone

def _df3_pipe_decode(path, sr):
    """Decode WAV to float32 mono via ffmpeg pipe — avoids wave/soundfile dep."""
    r = subprocess.run(
        ['ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
         '-i', path, '-ar', str(sr), '-ac', '1', '-f', 'f32le', '-'],
        capture_output=True, timeout=120)
    if r.returncode or len(r.stdout) < 4:
        return None
    return np.frombuffer(r.stdout, dtype=np.float32).copy()

def _stft_restore_bands(processed, original, sr, bands):
    """
    RL-16: after DF3 blend, restore specified Hz bands from original.
    Uses STFT with 50% overlap Hann window — preserves phase coherence.
    """
    from numpy.fft import rfft, irfft
    N = 2048; HOP = N // 2
    freqs = np.fft.rfftfreq(N, d=1.0/sr)  # Hz per bin
    restore_mask = np.zeros(len(freqs), dtype=bool)
    for lo, hi in bands:
        restore_mask |= (freqs >= lo) & (freqs <= hi)

    win = np.hanning(N).astype(np.float32)
    min_n = min(len(processed), len(original))
    p = processed[:min_n].astype(np.float64)
    o = original[:min_n].astype(np.float64)
    out = np.zeros(min_n, dtype=np.float64)
    norm = np.zeros(min_n, dtype=np.float64)

    for s in range(0, min_n - N, HOP):
        Pf = rfft(p[s:s+N] * win)
        Of = rfft(o[s:s+N] * win)
        # S167: soft blend instead of hard copy — avoids tonal whistle when DF3
        # removes reverb masking context around nasal/formant poles.
        # 220-290Hz (nasal pole): 60% original (safe, low-freq, well-masked)
        # 950-1100Hz (formant zone): 15% original — high-risk for unmasked whistle;
        #   just enough to prevent total nasalization kill without audible tones.
        for lo, hi in bands:
            band_mask = (freqs >= lo) & (freqs <= hi)
            alpha = 0.60 if hi <= 300 else 0.15
            Pf[band_mask] = alpha * Of[band_mask] + (1.0 - alpha) * Pf[band_mask]
        frame = irfft(Pf) * win
        out[s:s+N] += frame; norm[s:s+N] += win**2

    valid = norm > 1e-8
    out[valid] /= norm[valid]
    out[~valid] = p[~valid]
    return out.astype(np.float32)

def _df3(wav, samples, rt60, st, aggressive=False):
    if not DF3_OK:
        _L(st, '  [S4-DF3] deep-filter not found — skip'); return wav

    # §106.3 + §79 atten limits — v4: stronger per-class
    lim = _DF3_LIM_MUJAWWAD if st.mujawwad_conf > 0.6 else _DF3_LIM_MURATTAL
    if aggressive:
        # Raise the numeric caps, but they still pass through min(x, lim) —
        # for Mujawwad sources lim=8 so this changes nothing for them; the
        # ornamentation protection is preserved by construction, not by a
        # separate check. Only Murattal-style sources (lim=24) get headroom.
        a_loud  = min(16, lim)
        a_mid   = min(22, lim)
        a_quiet = min(28, lim + 14)
        a_trans = min(20, lim)
    else:
        a_loud  = min(10, lim)       # was 8
        a_mid   = min(18, lim)       # was 15
        a_quiet = min(24, lim + 10)  # was 20
        a_trans = min(14, lim)       # v4: new transition class between loud/mid
    if st.mujawwad_conf > 0.6:
        a_loud  = min(a_loud,  8)
        a_mid   = min(a_mid,  10)
        a_quiet = min(a_quiet, 14)
        a_trans = min(a_trans,  9)

    d = tempfile.mkdtemp(prefix='safaa3_df3_')
    try:
        # ── Prepare pcm_s16le mono input ──────────────────────────────────
        fi = os.path.join(d, 'in.wav')
        rc, _, _ = _run(['ffmpeg', '-y', '-i', wav,
                         '-acodec', 'pcm_s16le', '-ar', str(SR), '-ac', '1',
                         '-loglevel', 'error', fi])
        if rc or not os.path.exists(fi):
            return wav
        mono = _df3_pipe_decode(fi, SR)
        if mono is None:
            return wav
        total = len(mono)

        # ── VAD — 50ms chunks with SNR gate (§22.5) ──────────────────────
        CHUNK = int(_ADF_CHUNK_S * SR)
        nc = max(1, total // CHUNK)
        # Estimate noise floor from quietest 10% of chunks
        rms_db = np.array([
            20.0 * np.log10(np.sqrt(np.mean(mono[i*CHUNK:(i+1)*CHUNK]**2)) + 1e-12)
            for i in range(nc)])
        noise_floor = float(np.percentile(rms_db, 10))

        # §22.5 SNR gate value (used later in continuous blend)
        chunk_snr = rms_db - noise_floor
        snr_gate  = (_ADF_SNR_GATE + 3.0) if aggressive else _ADF_SNR_GATE

        # Stats for logging only — no longer used for hard assignment
        n_loud  = int((rms_db >  _ADF_LOUD_T).sum())
        n_quiet = int((rms_db <= _ADF_QUIET_T).sum())
        n_mid   = nc - n_loud - n_quiet
        n_clean = int((chunk_snr >= snr_gate).sum())
        _L(st, f'  [S4-ADF] 50ms chunks: LOUD={n_loud} MID={n_mid} '
               f'QUIET={n_quiet} CLEAN(snr-gate)={n_clean}  nf={noise_floor:.1f}dBFS')

        # ── 3 parallel DF passes with per-class flags ─────────────────────
        df_out = {}
        def _run_pass(cls, atten, pf=False, pf_beta=0.02):
            od = os.path.join(d, cls); os.makedirs(od, exist_ok=True)
            cmd = [_DF3_CLI_BIN, '--atten-lim-db', str(atten)]
            if pf:
                cmd += ['--pf', '--pf-beta', str(pf_beta)]
            cmd += ['-o', od, fi]
            r2 = subprocess.run(cmd, capture_output=True, timeout=600)
            wp = os.path.join(od, 'in.wav')
            if r2.returncode or not os.path.exists(wp):
                _L(st, f'  [S4-ADF] {cls} pass failed — using source')
                return cls, mono.copy()
            arr = _df3_pipe_decode(wp, SR)
            if arr is None:
                _L(st, f'  [S4-ADF] {cls} decode failed — using source')
                return cls, mono.copy()
            pf_tag = ' +PF' if pf else ''
            _L(st, f'  [S4-ADF] {cls:6s} {atten:2d}dB{pf_tag} ✓  '
                   f'max={np.max(np.abs(arr)):.4f}')
            return cls, arr

        with ThreadPoolExecutor(max_workers=4) as ex:
            futs = [
                ex.submit(_run_pass, 'loud',  a_loud,  aggressive, 0.02),
                ex.submit(_run_pass, 'mid',   a_mid,   aggressive, 0.02),
                ex.submit(_run_pass, 'quiet', a_quiet, True, 0.04),   # PF quiet always
                ex.submit(_run_pass, 'trans', a_trans, aggressive, 0.02),
            ]
            for fut in as_completed(futs):
                cls, arr = fut.result()
                df_out[cls] = arr

        # ── Continuous soft-weight blend (v5) ────────────────────────────
        # Root cause of "يروح ويجي": hard zone assignment kept attenuation
        # constant inside each zone; crossfade only fired AT boundaries.
        # Fix: compute soft sigmoid weights from RMS per chunk, Gaussian-smooth
        # them temporally (~300ms window), interpolate to sample level.
        # Every individual sample now has a uniquely blended attenuation that
        # tracks the signal continuously — no zones, no boundaries, no jumps.

        def _sig(x):
            return 1.0 / (1.0 + np.exp(-np.clip(x.astype(np.float64), -20, 20)))

        def _gauss1d(arr, sig):
            """Gaussian kernel smoothing — pure numpy, no scipy dependency."""
            sig = max(0.5, float(sig))
            r = max(1, int(3.5 * sig))
            t = np.arange(-r, r + 1, dtype=np.float64)
            k = np.exp(-0.5 * (t / sig) ** 2); k /= k.sum()
            return np.convolve(arr.astype(np.float64), k, mode='same')

        SIGMA = _ADF_SIGMA_DB    # dBFS half-width of transition (4 dB)
        SC    = _ADF_SMOOTH_C    # Gaussian temporal smoothing in chunks (~300ms)

        # Raw soft weights per chunk (sum not forced to 1 yet)
        wL = _sig((rms_db - _ADF_LOUD_T)  / SIGMA)   # 1 = very loud
        wQ = _sig((_ADF_QUIET_T - rms_db) / SIGMA)   # 1 = very quiet
        wM = np.clip(1.0 - wL - wQ, 0.0, 1.0)        # mid fills the gap

        # Normalize to sum = 1 per chunk
        wS = wL + wM + wQ + 1e-8
        wL /= wS; wM /= wS; wQ /= wS

        # Gaussian temporal smoothing across chunks — this is what eliminates
        # the step-function zones; after smoothing the weights transition over
        # ~300ms even when the signal level changes abruptly.
        wL = _gauss1d(wL, SC); wM = _gauss1d(wM, SC); wQ = _gauss1d(wQ, SC)
        wS2 = wL + wM + wQ + 1e-8
        wL /= wS2; wM /= wS2; wQ /= wS2

        # Interpolate chunk-level weights → sample level (linear, smooth)
        # Anchored at chunk centres so edges don't overshoot
        t_c = (np.arange(nc, dtype=np.float64) + 0.5) * CHUNK
        t_s = np.arange(total, dtype=np.float64)
        wL_s = np.interp(t_s, t_c, wL)
        wM_s = np.interp(t_s, t_c, wM)
        wQ_s = np.interp(t_s, t_c, wQ)

        # Three-way blend at sample level
        min_n = min(total, *(len(df_out[c]) for c in ('loud', 'mid', 'quiet', 'trans')))
        blended = (
            wL_s[:min_n] * df_out['loud'][:min_n].astype(np.float64) +
            wM_s[:min_n] * df_out['mid'][:min_n].astype(np.float64)  +
            wQ_s[:min_n] * df_out['quiet'][:min_n].astype(np.float64)
        )

        # SNR gate: for already-clean regions, blend toward 'trans' (light-touch
        # pass) rather than raw mono — avoids re-introducing un-processed noise.
        # Gate weight is also Gaussian-smoothed so it ramps gradually.
        w_gate = np.clip((chunk_snr - snr_gate) / 8.0, 0.0, 1.0)
        w_gate = _gauss1d(w_gate, SC * 2)                 # wider smooth for gate
        w_gate_s = np.clip(np.interp(t_s, t_c, w_gate), 0.0, _ADF_GATE_MAX)
        blended[:min_n] = (
            (1.0 - w_gate_s[:min_n]) * blended[:min_n] +
            w_gate_s[:min_n] * df_out['trans'][:min_n].astype(np.float64)
        )

        _L(st, f'  [S4-ADF] v5 continuous blend: σ_db={SIGMA:.1f}dB '
               f'smooth={SC}×{int(_ADF_CHUNK_S*1000)}ms={int(SC*_ADF_CHUNK_S*1000)}ms '
               f'gate≤{int(_ADF_GATE_MAX*100)}%')

        # ── RL-16: restore Ghunnah guard bands from original ──────────────
        blended_f32 = np.where(np.isfinite(blended), blended, 0.0).astype(np.float32)
        blended_f32 = _stft_restore_bands(blended_f32, mono[:min_n], SR, _RL16_BANDS)
        _L(st, f'  [S4-ADF] RL-16 bands restored: '
               f'{", ".join(f"{lo}-{hi}Hz" for lo,hi in _RL16_BANDS)}')

        # ── Silence guard ─────────────────────────────────────────────────
        if float(np.max(np.abs(blended_f32))) < 1e-4:
            _L(st, '  [S4-ADF] ⚠ silent result — fallback to mid pass')
            blended_f32 = df_out['mid'][:min_n].astype(np.float32)

        # ── Encode to pcm_s24le stereo ────────────────────────────────────
        out = _tmp('s4', st)
        r3 = subprocess.run(
            ['ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
             '-f', 'f32le', '-ar', str(SR), '-ac', '1', '-i', '-',
             '-ar', str(SR), '-ac', '2', '-acodec', 'pcm_s24le', out],
            input=blended_f32.tobytes(), capture_output=True, timeout=120)
        if r3.returncode or not os.path.exists(out):
            return wav

        delta = _rmsdb(blended_f32) - _rmsdb(mono)
        st.df3 = True
        _L(st, f'  [S4-ADF] ✓  loud={a_loud}dB mid={a_mid}dB quiet={a_quiet}dB '
               f'RMS Δ={delta:+.2f}dB')
        return out
    except Exception as e:
        _L(st, f'  [S4-DF3] exception: {e}'); return wav
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ─── Stage 5: JALAA per-frame DRR gate (§28.6) ───────────────────────────────
def _jalaa(wav, samples, rt60, drr_before, st):
    """
    Per-frame DRR classification → calibrated afftdn on reverb-dominated frames.
    [B1] Late window corrected to 450ms (50-500ms per §3.3).
    [I10] Skip entirely if DRR already > DRR_ALREADY_DRY (room is dry enough).
    """
    if not NUMPY_OK or samples is None or rt60 < 0.30:
        _L(st, f'  [S5-JALAA] RT60={rt60:.2f}s < 0.30 — skip'); return wav
    if drr_before > DRR_ALREADY_DRY:
        _L(st, f'  [S5-JALAA] DRR={drr_before:.1f}dB already dry — skip [I10]'); return wav

    fn = int(0.200 * SR)
    en = int(0.050 * SR)
    ln = int(0.450 * SR)          # [B1] was 0.150 → 450ms (50-500ms window)
    n  = len(samples) // fn
    if n < 5:
        return wav

    nf_vals = []
    for i in range(n):
        s = i * fn; chunk = samples[s:s + fn]
        if len(chunk) < en + ln:
            continue
        er = float(np.sqrt(np.mean(chunk[:en] ** 2)) + 1e-10)
        lr = float(np.sqrt(np.mean(chunk[en:en + ln] ** 2)) + 1e-10)
        if er < 1e-5: continue
        if 20.0 * np.log10(er / lr) < 3.0:   # reverb-dominated
            nf_vals.append(float(20 * np.log10(lr + 1e-10)))

    if not nf_vals:
        _L(st, '  [S5-JALAA] no reverb frames — skip'); return wav

    nf = float(np.clip(float(np.median(nf_vals)) + 3, -72, -20))  # v4: floor raised -25→-20
    nr = 3 if rt60 > RT60_AGGR else 2   # v4: base raised (was 2/1)
    if st.mujawwad_conf > 0.6: nr = max(1, nr - 1)

    # v4: two-pass JALAA — first pass stationary, second adaptive tracking
    out = _tmp('s5a', st)
    rc, _, _ = _run(['ffmpeg', '-y', '-i', wav,
                     '-af', f'afftdn=nr={nr}:nf={nf:.0f}:nt=w:tn=1',
                     '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '1',
                     '-loglevel', 'error', out])
    if rc or not os.path.exists(out):
        return wav

    out2 = _tmp('s5b', st)
    rc2, _, _ = _run(['ffmpeg', '-y', '-i', out,
                      '-af', f'afftdn=nr={max(1,nr-1)}:nf={nf+3:.0f}:nt=w:tn=1',
                      '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '1',
                      '-loglevel', 'error', out2])
    if rc2 or not os.path.exists(out2):
        pass  # keep single-pass result
    else:
        _cleanup(out); out = out2

    post = _decode(out)
    if post is not None:
        d = _rmsdb(post) - _rmsdb(samples)
        if abs(d) > _RMS_MAX_DELTA:
            _cleanup(out); st.guard_reverts += 1
            _L(st, f'  [S5-JALAA] RMS Δ={d:+.2f}dB — REVERT'); return wav

    st.jalaa = True
    _L(st, f'  [S5-JALAA] ✓ reverb_frames={len(nf_vals)}/{n} nf={nf:.0f}dB nr={nr}')
    return out


# ─── Stage 6: Tail floor NR — 2-stage (afftdn + anlmdn) ─────────────────────
def _tailnr(wav, samples, rt60, st):
    """
    2-stage NR pipeline (§83.3 order: stationary → non-stationary):
      Stage A: afftdn with nt=w (adaptive tracking) for stationary noise floor.
      Stage B: anlmdn (s=7:p=3:r=15) for transient/non-stationary residuals.
    RT60-scaled nr: base=2, +1 per 1.5s RT60 above threshold, cap=5 (§5.3: 20dB/nr max).
    [I3] If JALAA already ran, reduce nr by 1 to avoid double-attenuation.
    RL-16: sibilant SNR guard — revert if Safir/Tafasshi band drops > 2dB.
    """
    if rt60 < RT60_TAILNR or samples is None or not NUMPY_OK:
        return wav
    fn = int(0.200 * SR)
    overall = _rmsdb(samples)
    fdb = np.array([float(20 * np.log10(np.sqrt(np.mean(samples[i:i+fn]**2)) + 1e-10))
                    for i in range(0, len(samples) - fn, fn)])
    quiet = fdb[fdb < overall - 10]
    if len(quiet) == 0:
        return wav

    nf = float(np.clip(float(np.median(quiet)) + 4, -72, -25))
    # v4: RT60-scaled nr — higher cap (8 was 5), stronger base
    nr = min(8, 3 + int((rt60 - RT60_TAILNR) / 1.2))   # was cap=5, base=2, step=1.5
    if st.mujawwad_conf > 0.6: nr = max(1, nr - 1)
    if st.jalaa:               nr = max(1, nr - 1)   # [I3]

    # ── Stage A: afftdn with adaptive noise tracking ──────────────────────
    out_a = _tmp('s6a', st)
    rc, _, _ = _run(['ffmpeg', '-y', '-i', wav,
                     '-af', f'afftdn=nr={nr}:nf={nf:.0f}:nt=w:om=o',
                     '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '2',
                     '-loglevel', 'error', out_a])
    if rc or not os.path.exists(out_a):
        return wav

    # ── Stage B: anlmdn for non-stationary residuals ──────────────────────
    # anlmdn: s=patch size, p=context, r=search radius (§95 KB)
    # Scale strength with nr: gentle (s=5) at nr<=2, standard (s=7) at nr>2
    patch = 7 if nr > 2 else 5
    out_b = _tmp('s6b', st)
    rc2, _, _ = _run(['ffmpeg', '-y', '-i', out_a,
                      '-af', f'anlmdn=s={patch}:p=3:r=15:m=1',
                      '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '2',
                      '-loglevel', 'error', out_b])
    if rc2 or not os.path.exists(out_b):
        # Stage B failed — commit Stage A only
        st.tail_nr = True
        jalaa_note = ' (JALAA-adj)' if st.jalaa else ''
        _L(st, f'  [S6-tailNR] ✓ 1-stage nr={nr}{jalaa_note} nf={nf:.0f}dB  '
               f'[anlmdn failed — Stage A only]')
        return out_a

    # ── Sibilant SNR guard (RL-16 spirit) ─────────────────────────────────
    post_s = _decode(out_b)
    if post_s is not None:
        sib_orig = _band_energy(samples, 3500, 8000)
        sib_post = _band_energy(post_s,  3500, 8000)
        sib_drop = sib_post - sib_orig
        if sib_drop < -2.0:
            _L(st, f'  [S6-tailNR] sibilant drop {sib_drop:+.1f}dB — '
                   f'revert Stage B, keep Stage A')
            _cleanup(out_b)
            st.tail_nr = True
            _L(st, f'  [S6-tailNR] ✓ nr={nr} nf={nf:.0f}dB [Stage A only]')
            return out_a

    # ── Stage C: v4 — gentle anlmdn second pass for reverb tail residual ────
    out_c = _tmp('s6c', st)
    rc3, _, _ = _run(['ffmpeg', '-y', '-i', out_b,
                      '-af', f'anlmdn=s=5:p=3:r=10:m=1',
                      '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '2',
                      '-loglevel', 'error', out_c])
    if rc3 or not os.path.exists(out_c):
        pass  # keep Stage B
    else:
        post_c = _decode(out_c)
        if post_c is not None:
            sib_c = _band_energy(post_c, 3500, 8000)
            sib_drop_c = sib_c - _band_energy(samples, 3500, 8000)
            if sib_drop_c >= -2.5:
                _cleanup(out_b); out_b = out_c
            else:
                _cleanup(out_c)

    _cleanup(out_a)
    st.tail_nr = True
    jalaa_note = ' (JALAA-adj)' if st.jalaa else ''
    _L(st, f'  [S6-tailNR] ✓ 3-stage nr={nr}{jalaa_note} nf={nf:.0f}dB '
           f'patch={patch} rt60={rt60:.1f}s')
    return out_b


# ─── Stage 6.5: Wind noise removal (v4) ─────────────────────────────────────
def _windnr(wav, samples, rt60, st):
    """
    Targets wind noise: broadband low-frequency energy (30–400Hz)
    that DF3 doesn't clean because it looks like speech sub-harmonics.

    Strategy:
      A) Hard HPF at 60Hz to kill sub-rumble
      B) Spectral gate on 60–300Hz band: estimate wind energy from
         speech-inactive frames, subtract with 6dB headroom
      C) Gentle de-essing inversion below 400Hz (anlmdn lightweight)
      D) Guard: if low-band energy drops > 8dB → revert (protect bass vowels)
    """
    if samples is None or not NUMPY_OK:
        _L(st, '  [S6.5-WIND] no samples — skip'); return wav

    # Measure wind energy spectrally — find steady LF floor even during speech
    # Wind = energy in 60-300Hz that doesn't modulate with speech (stays constant)
    fn  = int(0.100 * SR)
    n   = len(samples) // fn
    overall_db = _rmsdb(samples)

    # Low-band energy per frame (60–300Hz via FFT)
    lo_energy_db = []
    for i in range(n):
        frame = samples[i*fn:(i+1)*fn]
        spec  = np.abs(np.fft.rfft(frame, n=fn)) / fn   # normalize by N
        freqs = np.fft.rfftfreq(fn, d=1.0/SR)
        lo_mask = (freqs >= 60) & (freqs <= 300)
        lo_rms  = float(np.sqrt(np.mean(spec[lo_mask]**2) + 1e-20))
        lo_energy_db.append(20 * np.log10(lo_rms + 1e-10))

    lo_energy_db = np.array(lo_energy_db)
    # Wind floor = the bottom 20th percentile of LF energy across all frames
    # Wind is the *minimum* steady LF that persists regardless of speech activity
    wind_floor_db = float(np.percentile(lo_energy_db, 20))

    # Only apply if wind floor is detectable (above -62dBFS in LF band)
    if wind_floor_db < -62.0:
        _L(st, f'  [S6.5-WIND] LF floor={wind_floor_db:.1f}dBFS — inaudible, skip'); return wav

    # Baseline for guards must be the wav INPUT (already DF3/tailNR processed),
    # NOT s_orig — comparing against original would fire on DF3's own changes.
    wav_pre = _decode(wav)
    if wav_pre is None:
        _L(st, '  [S6.5-WIND] decode failed — skip'); return wav

    lo_before  = _band_energy(wav_pre, 60,  200)   # wind zone: 60-200Hz
    mid_before = _band_energy(wav_pre, 250, 900)   # vowel zone: protect formants

    # Wind noise in mosque/outdoor recordings sits below 200Hz.
    # afftdn nt=w is too broad (hits vowel formants) — use HPF + low-shelf instead.
    # Stage A: HPF at 80Hz (2-pole) — kills sub-rumble below speech
    tmp_a = _tmp('s65a', st)
    rc, _, _ = _run(['ffmpeg', '-y', '-i', wav,
                     '-af', 'highpass=f=80:poles=2',
                     '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '2',
                     '-loglevel', 'error', tmp_a])
    if rc or not os.path.exists(tmp_a):
        _L(st, '  [S6.5-WIND] HPF failed — skip'); return wav

    # Stage B: low-shelf EQ targeting 80-200Hz wind band.
    # Depth scales with severity: heavy wind → up to -8dB shelf; faint → -3dB.
    # shelf at 200Hz, so everything above is unaffected.
    shelf_db = -8.0 if wind_floor_db > -35 else (-5.0 if wind_floor_db > -45 else -3.0)
    tmp_b = _tmp('s65b', st)
    rc2, _, _ = _run(['ffmpeg', '-y', '-i', tmp_a,
                      '-af', (f'equalizer=f=100:width_type=o:width=1.0:g={shelf_db:.0f},'
                              f'equalizer=f=180:width_type=o:width=0.8:g={shelf_db*0.5:.0f}'),
                      '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '2',
                      '-loglevel', 'error', tmp_b])
    if rc2 or not os.path.exists(tmp_b):
        _L(st, '  [S6.5-WIND] shelf EQ failed — keep HPF only')
        result = tmp_a
    else:
        # Stage C: very gentle anlmdn for residual wind texture (s=2, conservative)
        tmp_c = _tmp('s65c', st)
        rc3, _, _ = _run(['ffmpeg', '-y', '-i', tmp_b,
                          '-af', 'anlmdn=s=2:p=2:r=6:m=1',
                          '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '2',
                          '-loglevel', 'error', tmp_c])
        result = tmp_c if (rc3 == 0 and os.path.exists(tmp_c)) else tmp_b

    # Dual guard:
    #   Wind zone (60-200Hz): allow up to -15dB — this IS the wind band
    #   Vowel zone (250-900Hz): max -2dB — protect speech formants tightly
    post_s = _decode(result)
    if post_s is not None:
        lo_after  = _band_energy(post_s,  60,  200)
        mid_after = _band_energy(post_s, 250,  900)
        if lo_before > 1e-15:
            lo_drop  = 10 * np.log10(lo_after  / (lo_before  + 1e-20) + 1e-20)
            if lo_drop < -15.0:
                for t in [tmp_a, tmp_b, tmp_c if 'tmp_c' in dir() else None]:
                    if t: _cleanup(t)
                st.guard_reverts += 1
                _L(st, f'  [S6.5-WIND] wind-zone over-removal {lo_drop:+.1f}dB — REVERT')
                return wav
        if mid_before > 1e-15:
            mid_drop = 10 * np.log10(mid_after / (mid_before + 1e-20) + 1e-20)
            if mid_drop < -2.0:
                for t in [tmp_a, tmp_b, tmp_c if 'tmp_c' in dir() else None]:
                    if t: _cleanup(t)
                st.guard_reverts += 1
                _L(st, f'  [S6.5-WIND] vowel band drop {mid_drop:+.1f}dB — REVERT')
                return wav
            _L(st, f'  [S6.5-WIND] guards ✓  wind={lo_drop:+.1f}dB  vowel={mid_drop:+.1f}dB')

    if result not in (tmp_a,):
        _cleanup(tmp_a)
    if 'tmp_b' in dir() and result not in (tmp_b,):
        _cleanup(tmp_b)
    _L(st, f'  [S6.5-WIND] ✓ floor={wind_floor_db:.1f}dBFS  shelf={shelf_db:.0f}dB @100-180Hz')
    return result


# ─── Stage 7: Arabic phoneme guards (§35/§52/§143/§152) ──────────────────────
def _arabic_guards(orig_s, proc_wav, st):
    """
    Seven guards verifying Tajweed-critical features survived processing.
    WARN-only by design — reverb is worse than mild phoneme loss.
    Results stored in st.guard_pass / st.guard_warn (structured). [I6]
    [B3] _band_energy() now samples across full file.
    [B4] G4 Ra-trill scans full audio in overlapping 1s windows.
    """
    if not NUMPY_OK or orig_s is None:
        return proc_wav
    proc_s = _decode(proc_wav)
    if proc_s is None:
        return proc_wav
    n = min(len(orig_s), len(proc_s))
    o = orig_s[:n]; p = proc_s[:n]

    def chk(name, cond, detail):
        entry = f'{name}: {detail}'
        if cond:
            st.guard_pass.append(entry); _L(st, f'  [S7-PASS] {entry}')
        else:
            st.guard_warn.append(entry); _L(st, f'  [S7-WARN] ⚠ {entry}')

    # G1 Ghunnah 250-300 Hz (§152.3)
    go = _band_energy(o, 250, 300); gp = _band_energy(p, 250, 300)
    if go > 1e-15:
        d = 10 * np.log10(gp / go + 1e-20)
        chk('G1-Ghunnah', d >= -3.0, f'{d:+.1f}dB {"✓" if d>=-3 else "⚠ nasal murmur lost"}')

    # G2 Ikhfa 250-400 Hz (§52.5)
    io = _band_energy(o, 250, 400); ip = _band_energy(p, 250, 400)
    if io > 1e-15:
        d = 10 * np.log10(ip / io + 1e-20)
        chk('G2-Ikhfa', d >= -4.0, f'{d:+.1f}dB {"✓" if d>=-4 else "⚠ ikhfa nasalisation lost"}')

    # G3 Qalqalah burst (§52.7, §143 Class 2)
    sil_n = int(0.020 * SR); bst_n = int(0.030 * SR)
    total = viol = 0
    for i in range(0, n - sil_n - bst_n, sil_n):
        sr_ = float(np.sqrt(np.mean(o[i:i + sil_n] ** 2)) + 1e-10)
        br_ = float(np.sqrt(np.mean(o[i + sil_n:i + sil_n + bst_n] ** 2)) + 1e-10)
        if sr_ < 0.005 and br_ > sr_ * 5:
            total += 1
            bp = float(np.sqrt(np.mean(p[i + sil_n:i + sil_n + bst_n] ** 2)) + 1e-10)
            if 20 * np.log10(bp / br_ + 1e-10) < -6.0: viol += 1
    if total > 0:
        pct = viol / total * 100
        chk('G3-Qalqalah', pct <= 20,
            f'{total} bursts {pct:.0f}% violated {"✓" if pct<=20 else "⚠ echo burst attenuated"}')

    # G4 Ra trill AM 25-35 Hz — FULL AUDIO scan in overlapping 1s windows [B4]
    win = SR; hop = SR // 2
    am_ratios = []
    for pos in range(0, n - win, hop):
        ef_o = np.abs(np.fft.rfft(np.abs(o[pos:pos + win]), n=win))
        ef_p = np.abs(np.fft.rfft(np.abs(p[pos:pos + win]), n=win))
        am_o = float(np.mean(ef_o[25:36])); am_p = float(np.mean(ef_p[25:36]))
        if am_o > 1e-8:
            am_ratios.append(am_p / am_o)
    if am_ratios:
        r = float(np.median(am_ratios))
        chk('G4-Ra-trill', r >= 0.70,
            f'AM ratio={r:.2f} (median over {len(am_ratios)} windows) '
            f'{"✓" if r>=0.70 else "⚠ ر trill may be smeared"}')

    # G5 Safir 5.5-12 kHz — ص س ز (§152.3)
    so = _band_energy(o, 5500, 12000); sp = _band_energy(p, 5500, 12000)
    if so > 1e-15:
        d = 10 * np.log10(sp / so + 1e-20)
        chk('G5-Safir', d >= -5.0,
            f'{d:+.1f}dB {"✓" if d>=-5 else "⚠ ص س ز may be dull"}')

    # G6 Tafasshi 3-8 kHz — ش (§152.3)
    to = _band_energy(o, 3000, 8000); tp = _band_energy(p, 3000, 8000)
    if to > 1e-15:
        d = 10 * np.log10(tp / to + 1e-20)
        chk('G6-Tafasshi', d >= -4.0,
            f'{d:+.1f}dB {"✓" if d>=-4 else "⚠ ش may lose spread"}')

    # G7 Izhar silence count (§52.5.1)
    def _sil_count(s):
        fn_ = int(0.010 * SR)
        db = np.array([float(20 * np.log10(np.sqrt(np.mean(s[i:i + fn_] ** 2)) + 1e-10))
                       for i in range(0, len(s) - fn_, fn_)])
        med = float(np.median(db)); c = 0; in_s = False; sl = 0
        for v in db:
            if v < med - 18: in_s = True; sl += 1
            else:
                if in_s and 2 <= sl <= 8: c += 1
                in_s = False; sl = 0
        return c
    sc_o = _sil_count(o); sc_p = _sil_count(p)
    if sc_o > 0:
        r = sc_p / sc_o
        chk('G7-Izhar', r >= 0.70,
            f'silences {sc_o}→{sc_p} ({r:.0%}) {"✓" if r>=0.70 else "⚠ words may run together"}')

    total_g = len(st.guard_pass) + len(st.guard_warn)
    if st.guard_warn:
        _L(st, f'  [S7] {len(st.guard_warn)}/{total_g} warnings — check output for Tajweed artifacts')
    else:
        _L(st, f'  [S7] All {total_g} guards passed ✓')
    return proc_wav


# ─── Main ─────────────────────────────────────────────────────────────────────
def process(input_path, output_path, source_tier='TIER_UNKNOWN',
            mujawwad_conf=0.0, force_rt60=0.0, verbose=True, aggressive=False):
    """
    الصفاء v3 — main entry point.
    Returns SafaaState with full diagnostics.
    All temp files are tracked and cleaned up on exit. [I8]
    """
    st = SafaaState(input_path=input_path, source_tier=source_tier,
                    mujawwad_conf=mujawwad_conf)
    _L(st, f'\n{"═"*60}')
    _L(st, f'  الصفاء {__version__} — إزالة الصدى والريفيرب')
    _L(st, f'  Input   : {Path(input_path).name}')
    _L(st, f'  Tier    : {source_tier}   Mujawwad: {mujawwad_conf:.2f}')
    _L(st, f'{"═"*60}')
    if aggressive:
        _L(st, '  [AGGRESSIVE] DF3 attenuation caps + post-filter coverage widened '
                '(Mujawwad ceiling unchanged — protected by design)')

    s_orig = _decode(input_path)
    if s_orig is None:
        _L(st, '  ERROR: decode failed'); return st

    try:
        cur = input_path

        # S1: RT60 + DRR
        rt60 = force_rt60 if force_rt60 > 0 else _rt60(s_orig)
        st.rt60_initial = rt60; st.drr_before = _drr(s_orig)
        _L(st, f'  [S1] RT60={rt60:.2f}s  DRR={st.drr_before:.1f}dB')

        if rt60 < RT60_MIN:
            _L(st, f'  [S1] RT60 < {RT60_MIN}s — no processing needed')
            _enc_stereo(input_path, output_path); return st

        # S2 Sub-band LF EQ
        cur = _lf_eq(cur, s_orig, rt60, st)
        # S3 WPE
        cur = _wpe(cur, rt60, st)
        # S4 DF3 (parallel)
        _s4 = _decode(cur); s4 = _s4 if _s4 is not None else s_orig
        cur = _df3(cur, s4, rt60, st, aggressive=aggressive)
        # S5 JALAA (DRR-weighted, corrected late window)
        _s5 = _decode(cur); s5 = _s5 if _s5 is not None else s_orig
        cur = _jalaa(cur, s5, rt60, st.drr_before, st)
        # S6 Tail NR (JALAA-aware)
        _s6 = _decode(cur); s6 = _s6 if _s6 is not None else s_orig
        cur = _tailnr(cur, s6, rt60, st)
        # S6.5 Wind noise removal — v4 addition
        cur = _windnr(cur, s_orig, rt60, st)
        # S7 Arabic guards
        cur = _arabic_guards(s_orig, cur, st)

        # Final stereo encode + S8a dynamic normalizer + S8b volume boost
        # S8a: dynaudnorm final level evenness (v5: DF3 now self-smooth; dynaudnorm is a safety net)
        #   f=500ms window (long=smooth), m=10 max gain cap (20dB safety),
        #   p=0.92 peak target, r=0.0 (peak mode, not RMS — preserves Tajweed transients)
        # S8b: Aggressive mode = 4x boost (7.40) vs standard (1.85); limiter tightened
        _s8_vol = 7.40 if aggressive else 1.85
        _s8_lim = 0.94 if aggressive else 0.89
        _s8_norm = 'dynaudnorm=f=500:g=31:p=0.92:m=10:r=0.0:b=1,'
        _s8_af  = (_s8_norm +
                   f'volume={_s8_vol},'
                   'equalizer=f=2000:width_type=o:width=1.0:g=1.5,'
                   'equalizer=f=300:width_type=o:width=1.0:g=-1.0,'
                   f'alimiter=level_in=1:level_out=1:limit={_s8_lim}:attack=5:release=50')
        _s8_mode = 'AGGRESSIVE 4x' if aggressive else 'standard'
        _L(st, f'  [S8a] dynaudnorm f=500ms m=10 p=0.92 — level evenness pass')
        _L(st, f'  [S8b] volume boost={_s8_vol:.2f} ({_s8_mode})')
        rc, _, err = _run(['ffmpeg', '-y', '-i', cur,
                           '-af', _s8_af,
                           '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '2',
                           '-loglevel', 'error', output_path])
        if rc:
            _L(st, f'  ERROR: final encode: {err[:80]}'); return st

        sf_ = _decode(output_path)
        if sf_ is not None: st.drr_after = _drr(sf_)

        _L(st, f'\n{"═"*60}')
        _L(st, f'  الصفاء {__version__} ✓')
        _L(st, f'  RT60  : {st.rt60_initial:.2f}s')
        _L(st, f'  DRR   : {st.drr_before:.1f} → {st.drr_after:.1f} dB  '
              f'(Δ{st.drr_after - st.drr_before:+.1f})')
        _L(st, f'  LF={st.lf_eq} WPE={st.wpe} DF3={st.df3} JALAA={st.jalaa} tailNR={st.tail_nr}')
        _L(st, f'  Reverts:{st.guard_reverts}  Warns:{len(st.guard_warn)}/{len(st.guard_pass)+len(st.guard_warn)}')
        _L(st, f'{"═"*60}\n')
        return st

    finally:
        _cleanup_all(st)   # [I8] always runs


# ─── CLI ──────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    import argparse, json
    ap = argparse.ArgumentParser(description=f'الصفاء {__version__} — Dereverberation Engine')
    ap.add_argument('input')
    ap.add_argument('output')
    ap.add_argument('--tier',     default='TIER_UNKNOWN')
    ap.add_argument('--mujawwad', type=float, default=0.0)
    ap.add_argument('--rt60',       type=float, default=0.0, help='Force RT60 (0=auto)')
    ap.add_argument('--aggressive', action='store_true',
                    help='4x volume boost (7.40) + wider DF3 caps vs standard (1.85)')
    a = ap.parse_args()
    st = process(a.input, a.output,
                 source_tier=a.tier, mujawwad_conf=a.mujawwad, force_rt60=a.rt60,
                 aggressive=a.aggressive)
    print('\n[REPORT]')
    print(json.dumps({
        'version':      __version__,
        'rt60':         st.rt60_initial,
        'drr_before':   round(st.drr_before, 2),
        'drr_after':    round(st.drr_after,  2),
        'drr_gain':     round(st.drr_after - st.drr_before, 2),
        'stages': {
            'lf_eq':    st.lf_eq,
            'wpe':      st.wpe,
            'df3':      st.df3,
            'jalaa':    st.jalaa,
            'tail_nr':  st.tail_nr,
        },
        'guard_reverts': st.guard_reverts,
        'guard_pass':    st.guard_pass,
        'guard_warn':    st.guard_warn,
    }, indent=2, ensure_ascii=False))
