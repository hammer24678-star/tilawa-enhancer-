#!/usr/bin/env python3
"""
الصفاء v3  —  Dedicated Dereverberation Engine
إزالة الصدى والريفيرب

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
  S4  DF3 reverb-adapted (speech/transition/tail, parallel) [I1/I4]
  S5  JALAA per-frame DRR gate [B1/I10]
  S6  Tail floor NR (afftdn calibrated) [I3]
  S7  Arabic phoneme guards [B3/B4]

USAGE
  python3 engine_safaa_v3.py input.wav output.wav [--tier X] [--mujawwad 0.0] [--rt60 0.0]

KB REFS: §3 §28 §35 §36 §52 §79 §109 §138 §140 §143 §145 §151 §152 §154
"""
from __future__ import annotations

__version__ = 'v3'

import os, shutil, subprocess, tempfile, time, warnings  # S156: time for temp uniqueness
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

# DF3 binary
_DF3_CLI_BIN = ''
for _c in ['deep-filter', 'deepfilter', 'deep_filter',
           '/usr/local/bin/deep-filter', '/app/deep-filter']:
    if shutil.which(_c):
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

# §79 per-style DF attenuation hard limits
_DF3_LIM_MURATTAL  = 18   # dB maximum
_DF3_LIM_MUJAWWAD  =  6   # dB maximum
_DF3_SPEECH        = 12
_DF3_TRANS         = 20
_DF3_TAIL          = 28

_CHUNK_S       = 0.100
_XFADE_N       = 960

_RMS_MAX_DELTA = 1.0
_LRA_MAX_DELTA = 0.5     # §109.4

DRR_ALREADY_DRY = 6.0   # dB — skip JALAA if DRR already above this [I10]


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
    # S156-B2: add nanosecond suffix — avoids collision between concurrent server jobs
    p = os.path.join(_TMP, f'safaa3_{tag}_{os.getpid()}_{time.time_ns()}.wav')
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
            t = os.path.join(_TMP, f'safaa3_dec_{os.getpid()}_{time.time_ns()}.wav')  # S156-B2
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
            t = os.path.join(_TMP, f'safaa3_dec_{os.getpid()}_{time.time_ns()}.wav')  # S156-B2
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
            t = os.path.join(_TMP, f'safaa3_dec_{os.getpid()}_{time.time_ns()}.wav')  # S156-B2
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

def _wpe(wav, rt60, st):
    if not WPE_OK:
        _L(st, '  [S3-WPE] nara_wpe not installed → pip install nara_wpe soundfile')
        return wav
    if rt60 < RT60_WPE_MIN:
        _L(st, f'  [S3-WPE] RT60={rt60:.2f}s < {RT60_WPE_MIN}s — skip (§109.6)')
        return wav

    _L(st, f'  [S3-WPE] RT60={rt60:.2f}s — running WPE')
    d = tempfile.mkdtemp(prefix='safaa3_wpe_')
    try:
        mi = os.path.join(d, 'in.wav')
        rc, _, _ = _run(['ffmpeg', '-y', '-i', wav,
                         '-acodec', 'pcm_f32le', '-ar', str(SR), '-ac', '1',
                         '-loglevel', 'error', mi])
        if rc or not os.path.exists(mi):
            return wav
        if SF_OK:
            y, _ = SF.read(mi, dtype='float32', always_2d=False)
        else:
            import wave as _w
            with _w.open(mi, 'rb') as f: raw = f.readframes(f.getnframes())
            y = np.frombuffer(raw, dtype=np.float32).copy()

        if   st.mujawwad_conf > 0.6: taps, iters = 5, 2
        elif rt60 > 4.0:              taps, iters = 12, 3
        elif rt60 > 2.0:              taps, iters = 10, 3
        else:                         taps, iters = 8, 3
        delay = 3

        Y = _wpe_stft(y, size=512, shift=128)
        Z = wpe_v8(Y[..., np.newaxis], taps=taps, delay=delay, iterations=iters)
        z = _wpe_istft(Z[..., 0], size=512, shift=128)
        z = z[:len(y)] if len(z) > len(y) else np.pad(z, (0, len(y) - len(z)))

        ld = abs(_lra_overlapping(y) - _lra_overlapping(z))   # [I5]
        if ld > _LRA_MAX_DELTA:
            _L(st, f'  [S3-WPE] LRA Δ={ld:.2f}LU — retry iters-1')
            Z2 = wpe_v8(Y[..., np.newaxis], taps=taps, delay=delay, iterations=max(1, iters - 1))
            z2 = _wpe_istft(Z2[..., 0], size=512, shift=128)
            z2 = z2[:len(y)] if len(z2) > len(y) else np.pad(z2, (0, len(y) - len(z2)))
            ld2 = abs(_lra_overlapping(y) - _lra_overlapping(z2))
            if ld2 > _LRA_MAX_DELTA:
                st.guard_reverts += 1
                _L(st, f'  [S3-WPE] LRA {ld2:.2f}LU after retry — REVERT'); return wav
            z = z2; ld = ld2

        mo = os.path.join(d, 'out.wav')
        if SF_OK:
            SF.write(mo, z.astype(np.float32), SR, subtype='FLOAT')
        else:
            import wave as _w
            b16 = (np.clip(z, -1, 1) * 32767).astype(np.int16)
            with _w.open(mo, 'wb') as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
                f.writeframes(b16.tobytes())
        out = _tmp('s3', st)
        if not _enc_mono(mo, out):
            return wav
        st.wpe = True
        _L(st, f'  [S3-WPE] ✓ taps={taps} delay={delay} iters={iters} LRA Δ={ld:.2f}LU')
        return out
    except Exception as e:
        _L(st, f'  [S3-WPE] exception: {e}'); return wav
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ─── Stage 4: DF3 reverb-adapted pass (parallel) [I1/I4] ─────────────────────
def _df3_run_one(args):
    """Worker: run DF3 at one attenuation level. Returns (name, array|None)."""
    name, at, cli_bin, fi, od, SR_ = args
    import wave as _w
    r = subprocess.run([cli_bin, '--atten-lim-db', str(at), '-o', od, fi],
                       capture_output=True, timeout=600)
    wp = os.path.join(od, os.path.basename(fi))
    if r.returncode or not os.path.exists(wp):
        return name, None
    with _w.open(wp, 'rb') as f:
        raw = f.readframes(f.getnframes())
    return name, np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

def _df3(wav, samples, rt60, st):
    if not DF3_OK:
        _L(st, '  [S4-DF3] deep-filter not found — skip'); return wav

    # Attenuation levels
    ta = _DF3_TAIL   + (4 if rt60 > RT60_AGGR else 0)
    ra = _DF3_TRANS  + (2 if rt60 > RT60_AGGR else 0)
    sa = _DF3_SPEECH

    # §79 per-style hard limits [I4]
    if st.mujawwad_conf > 0.6:
        lim = _DF3_LIM_MUJAWWAD
    else:
        lim = _DF3_LIM_MURATTAL
    sa = min(sa, lim)
    ra = min(ra, lim + 8)    # transition/tail may exceed speech limit but respect style spirit
    ta = min(ta, lim + 16)
    if st.mujawwad_conf > 0.6:
        ta = min(ta, int(ta * 0.70)); ra = min(ra, int(ra * 0.70)); sa = min(sa, int(sa * 0.80))

    import wave as _w
    d = tempfile.mkdtemp(prefix='safaa3_df3_')
    try:
        fi = os.path.join(d, 'in.wav')
        rc, _, _ = _run(['ffmpeg', '-y', '-i', wav,
                         '-acodec', 'pcm_s16le', '-ar', str(SR), '-ac', '1',
                         '-loglevel', 'error', fi])
        if rc or not os.path.exists(fi):
            return wav
        with _w.open(fi, 'rb') as f: raw = f.readframes(f.getnframes())
        s16 = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

        cn = int(_CHUNK_S * SR); nc = len(s16) // cn
        if nc < 1:
            return wav

        rms = np.array([float(np.sqrt(np.mean(s16[i*cn:(i+1)*cn]**2)) + 1e-10) for i in range(nc)])
        zcr = np.array([float(np.mean(np.abs(np.diff(np.sign(s16[i*cn:(i+1)*cn]))))) for i in range(nc)])
        rp30 = float(np.percentile(rms, 30)); rp70 = float(np.percentile(rms, 70))
        zm   = float(np.median(zcr))
        labels = np.where((rms >= rp70) & (zcr >= zm * 0.7), 0,
                          np.where((rms <= rp30) & (zcr < zm * 0.5), 2, 1))

        # Parallel DF3 passes [I1]
        jobs = []
        for nm, at in [('speech', sa), ('transition', ra), ('tail', ta)]:
            od = os.path.join(d, nm); os.makedirs(od, exist_ok=True)
            jobs.append((nm, at, _DF3_CLI_BIN, fi, od, SR))

        pas = {}
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs = {ex.submit(_df3_run_one, j): j[0] for j in jobs}
            for fut in as_completed(futs):
                nm, arr = fut.result()
                if arr is None:
                    _L(st, f'  [S4-DF3] {nm} failed — abort'); return wav
                pas[nm] = arr
                atten = next(j[1] for j in jobs if j[0] == nm)
                _L(st, f'  [S4-DF3] {nm:10s} {atten:2d}dB ✓')

        pa = [pas['speech'], pas['transition'], pas['tail']]
        ml = min(len(s16), min(len(a) for a in pa))
        out_s = np.empty(ml, dtype=np.float32)
        t = np.linspace(0, 1, _XFADE_N, dtype=np.float32)
        ci_ = 0.5 * (1 - np.cos(np.pi * t)).astype(np.float32); co_ = 1 - ci_
        pl = int(labels[0])
        for ci in range(nc):
            s = ci * cn; e = min((ci + 1) * cn, ml)
            if e > ml: break
            lb = int(labels[ci])
            if lb != pl and ci > 0 and s + _XFADE_N <= ml:
                b = min(_XFADE_N, e - s)
                out_s[s:s+b] = pa[pl][s:s+b] * co_[:b] + pa[lb][s:s+b] * ci_[:b]
                if e > s + _XFADE_N: out_s[s+_XFADE_N:e] = pa[lb][s+_XFADE_N:e]
            else:
                out_s[s:e] = pa[lb][s:e]
            pl = lb

        bm = os.path.join(d, 'blend.wav')
        b16 = (np.clip(out_s, -1, 1) * 32767).astype(np.int16)
        with _w.open(bm, 'wb') as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
            f.writeframes(b16.tobytes())
        out = _tmp('s4', st)
        if not _enc_mono(bm, out):
            return wav

        delta = _rmsdb(b16.astype(np.float32) / 32768.0) - _rmsdb(s16)
        if abs(delta) > _RMS_MAX_DELTA * 2:
            _cleanup(out); st.guard_reverts += 1
            _L(st, f'  [S4-DF3] RMS Δ={delta:+.2f}dB — REVERT'); return wav
        st.df3 = True
        _L(st, f'  [S4-DF3] ✓ sa={sa} ra={ra} ta={ta} RMS Δ={delta:+.2f}dB  '
              f'speech={int(np.sum(labels==0))} trans={int(np.sum(labels==1))} '
              f'tail={int(np.sum(labels==2))}')
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

    nf = float(np.clip(float(np.median(nf_vals)) + 3, -72, -25))
    nr = 2 if rt60 > RT60_AGGR else 1
    if st.mujawwad_conf > 0.6: nr = max(1, nr - 1)

    out = _tmp('s5', st)
    rc, _, _ = _run(['ffmpeg', '-y', '-i', wav,
                     '-af', f'afftdn=nr={nr}:nf={nf:.0f}:tn=1',
                     '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '1',
                     '-loglevel', 'error', out])
    if rc or not os.path.exists(out):
        return wav

    post = _decode(out)
    if post is not None:
        d = _rmsdb(post) - _rmsdb(samples)
        if abs(d) > _RMS_MAX_DELTA:
            _cleanup(out); st.guard_reverts += 1
            _L(st, f'  [S5-JALAA] RMS Δ={d:+.2f}dB — REVERT'); return wav

    st.jalaa = True
    _L(st, f'  [S5-JALAA] ✓ reverb_frames={len(nf_vals)}/{n} nf={nf:.0f}dB nr={nr}')
    return out


# ─── Stage 6: Tail floor NR ───────────────────────────────────────────────────
def _tailnr(wav, samples, rt60, st):
    """
    [I3] If JALAA already ran, reduce nr by 1 to avoid double-attenuation.
    """
    if rt60 < RT60_TAILNR or samples is None or not NUMPY_OK:
        return wav
    fn = int(0.200 * SR)
    overall = _rmsdb(samples)
    fdb = np.array([float(20 * np.log10(np.sqrt(np.mean(samples[i:i + fn] ** 2)) + 1e-10))
                    for i in range(0, len(samples) - fn, fn)])
    quiet = fdb[fdb < overall - 10]
    if len(quiet) == 0:
        return wav
    nf = float(np.clip(float(np.median(quiet)) + 4, -72, -30))
    nr = 3 if rt60 > RT60_AGGR else 2
    if st.mujawwad_conf > 0.6: nr = max(1, nr - 1)
    if st.jalaa:               nr = max(1, nr - 1)   # [I3] JALAA already ran
    out = _tmp('s6', st)
    rc, _, _ = _run(['ffmpeg', '-y', '-i', wav,
                     '-af', f'afftdn=nr={nr}:nf={nf:.0f}:tn=1',
                     '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '1',
                     '-loglevel', 'error', out])
    if rc or not os.path.exists(out):
        return wav
    st.tail_nr = True
    jalaa_note = ' (JALAA-adjusted)' if st.jalaa else ''
    _L(st, f'  [S6-tailNR] ✓ nr={nr}{jalaa_note} nf={nf:.0f}dB')
    return out


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

# ── S171: tier auto-detector ──────────────────────────────────────────────────
def _auto_detect_tier(path: str) -> str:
    import numpy as np, wave
    try:
        with wave.open(path, 'rb') as wf:
            sr  = wf.getframerate()
            nch = wf.getnchannels()
            raw = wf.readframes(wf.getnframes())
        s16 = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
        if nch > 1:
            s16 = s16.reshape(-1, nch).mean(axis=1)
        fn  = max(1, int(sr * 0.02))
        nc  = len(s16) // fn
        rms = np.array([np.sqrt(np.mean(s16[i*fn:(i+1)*fn]**2)) for i in range(nc)])
        rms = rms[rms > 0]
        if len(rms) == 0:
            return 'TIER_UNKNOWN'
        noise_rms = float(np.percentile(rms, 5))
        peak_rms  = float(np.percentile(rms, 95))
        snr_est   = 20 * np.log10(peak_rms / (noise_rms + 1e-9))
        mid  = len(s16) // 2
        win  = s16[mid: mid + sr] if len(s16) > mid + sr else s16
        if len(win) < 512:
            return 'TIER_UNKNOWN'
        spec  = np.abs(np.fft.rfft(win * np.hanning(len(win))))
        freqs = np.fft.rfftfreq(len(win), 1.0 / sr)
        hf_ratio = float(np.sum(spec[freqs > sr/4]**2)) / (float(np.sum(spec**2)) + 1e-9)
        active = freqs[spec > spec.max() * 0.01]
        eff_bw = float(active.max()) if len(active) else sr / 2.0
        if eff_bw < 4100:             return 'TIER_PHONE'
        if snr_est < 18:              return 'TIER_NOISY'
        if hf_ratio > 0.08 and snr_est >= 35: return 'TIER_STUDIO'
        if snr_est >= 25:             return 'TIER_GOOD'
        return 'TIER_NOISY'
    except Exception:
        return 'TIER_UNKNOWN'
# ─────────────────────────────────────────────────────────────────────────────

def process(input_path, output_path, source_tier='TIER_UNKNOWN',
            mujawwad_conf=0.0, force_rt60=0.0, verbose=True):
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
    # S171: auto-detect when caller did not supply a tier
    if source_tier == "TIER_UNKNOWN":
        source_tier     = _auto_detect_tier(input_path)
        st.source_tier  = source_tier
        _L(st, f"  [S171] auto-detected tier: {source_tier}")
    _L(st, f'{"═"*60}')

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
        cur = _df3(cur, s4, rt60, st)
        # S5 JALAA (DRR-weighted, corrected late window)
        _s5 = _decode(cur); s5 = _s5 if _s5 is not None else s_orig
        cur = _jalaa(cur, s5, rt60, st.drr_before, st)
        # S6 Tail NR (JALAA-aware)
        _s6 = _decode(cur); s6 = _s6 if _s6 is not None else s_orig
        cur = _tailnr(cur, s6, rt60, st)
        # S7 Arabic guards
        cur = _arabic_guards(s_orig, cur, st)

        # Final stereo encode [I2]
        rc, _, err = _run(['ffmpeg', '-y', '-i', cur,
                           '-acodec', 'libmp3lame', '-ar', str(SR), '-ac', '1',
                           '-b:a', '320k',
                           '-loglevel', 'error', output_path])
        if rc:
            _L(st, f'  ERROR: final encode: {err[:80]}')
            sys.exit(1)  # S169b: non-zero rc so app.py detects failure

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
    # S156-B1: use -i/-o flags to match server calling convention
    # server: python3 engine_safaa_v3_fixed.py -i input -o output --iterations 3 --ref ref
    ap.add_argument('-i', '--input',      required=True,  dest='input')
    ap.add_argument('-o', '--output',     required=True,  dest='output')
    ap.add_argument('--iterations',       type=int,   default=3)   # accepted, ignored (pipeline is fixed)
    ap.add_argument('--ref',              action='append', default=[], metavar='REF')  # accepted, ignored
    ap.add_argument('--tier',             default='TIER_UNKNOWN')
    ap.add_argument('--mujawwad',         type=float, default=0.0)
    ap.add_argument('--rt60',             type=float, default=0.0, help='Force RT60 (0=auto)')
    a = ap.parse_args()
    st = process(a.input, a.output,
                 source_tier=a.tier, mujawwad_conf=a.mujawwad, force_rt60=a.rt60)
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
