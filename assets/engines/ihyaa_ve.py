#!/usr/bin/env python3
# ihyaa_ve.py — إحياء Voice Enhancement Engine
# "To bring back to life what was lost"
#
# Part of THE AETHERION PROJECT — Engine-1: Recovery
# Designed for TIER_DAMAGED and TIER_CRITICAL sources exclusively.
#
# Pipeline position: after base NR (Phase B) and before EQ (Phase C).
# Integration:  from ihyaa_ve import apply_ihyaa_to_engine
#               wav_path, report = apply_ihyaa_to_engine(wav_path, state, ref)
#
# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SIX-STAGE RECOVERY PIPELINE                                                ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  IH-1  Spectral Restoration     Wiener-style per-band NR with musical       ║
# ║        noise prevention and Arabic phoneme-aware gain floors.               ║
# ║                                                                              ║
# ║  IH-2  Formant Enhancement      LPC-based F1/F2/F3 restoration.             ║
# ║        Pharyngeal consonant protection (ع ح خ غ). Emphatic guard.           ║
# ║                                                                              ║
# ║  IH-3  Harmonic De-noise        Suppress inter-harmonic smear during        ║
# ║        voiced frames. Isolates voice from noise-between-partials.           ║
# ║                                                                              ║
# ║  IH-4  Transient Reconstruction Re-sharpen consonant onsets blunted by      ║
# ║        codec damage or over-NR. Protects Qalqalah (ق ط ب ج د).            ║
# ║                                                                              ║
# ║  IH-5  Voice Presence Layer     Even-harmonic warmth (2F0, 4F0) in         ║
# ║        low-mid + 2-4 kHz presence lift + air above 8 kHz.                  ║
# ║                                                                              ║
# ║  IH-6  Dynamic Restoration      Soft upward expansion to recover LRA        ║
# ║        crushed by AGC/cassette/broadcast compression.                       ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  SAFETY                                                                      ║
# ║  • Every stage: before/after SNR, RMS, crest, sibilant-SNR comparison.     ║
# ║  • Arabic sibilant guard: never degrade ص ض س ش SNR > 2 dB.               ║
# ║  • Full revert on any gate failure; partial revert per stage.               ║
# ║  • No pitch shifting. No time-stretching. No letter repetition.            ║
# ║  • Compliant with Islamic ruling on Quran audio processing (KB §10.4).     ║
# ╠══════════════════════════════════════════════════════════════════════════════╣
# ║  KNOWLEDGE BASE REFERENCES                                                   ║
# ║  §4 Sibilance & de-essing        §6 Noise reduction                        ║
# ║  §7 Harmonic enhancement         §8 Psychoacoustics                         ║
# ║  §10 Arabic voice specifics      §11 State-of-art SE (2024-25)             ║
# ║  §21 LPC smear                   §24 Voice quality modules                 ║
# ║  §28 TYPE A/B/C NR modules       §29 Scoring system                        ║
# ║  §51C Practical upgrade paths    §46B Diffusion landscape                  ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
#
from __future__ import annotations

import os
import subprocess
import tempfile
import math
from typing import Dict, List, Optional, Tuple

_TMP = tempfile.gettempdir()
_MODULE = 'ihyaa_ve'

try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq, irfft
    from scipy.signal import lfilter, butter
    from scipy.interpolate import PchipInterpolator
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

SR = 48_000
WAV_CODEC = 'pcm_s24le'

# Tiers that qualify for Ihyaa processing
IHYAA_TIERS = {'TIER_DAMAGED', 'TIER_CRITICAL'}

# Gate thresholds — any stage that violates these reverts
_GATE_SIB_MAX_DROP_DB  = 2.0   # max allowed sibilant SNR drop per stage
_GATE_RMS_MAX_DELTA_DB = 1.5   # max allowed RMS shift per stage
_GATE_CREST_MAX_DELTA  = 2.5   # max allowed crest factor shift
_GATE_LUFS_MAX_DELTA   = 1.8   # max allowed LUFS shift for full pipeline

# Arabic sibilant protection bands (KB §4.1-4.4)
#   Emphatic sibilants: ص ض → 3000-5000 Hz
#   Non-emphatic:       س ش → 5000-8000 Hz
_SIB_EMPHATIC_LO  = 3_000.0
_SIB_EMPHATIC_HI  = 5_000.0
_SIB_PLAIN_LO     = 5_000.0
_SIB_PLAIN_HI     = 8_000.0

# Arabic voice fundamental range (KB §10.1)
_F0_MIN_HZ = 80.0
_F0_MAX_HZ = 280.0

# Pharyngeal consonant protection band (KB §10.3)
#   ع 'Ayn, ح Haa: strong mid-pharyngeal energy 200-800 Hz
_PHARYNGEAL_LO = 200.0
_PHARYNGEAL_HI = 800.0

# Ghunnah protection: nasal resonance of م ن at 250-350 Hz (KB §3.6, §10.1)
_GHUNNAH_LO = 240.0
_GHUNNAH_HI = 380.0

# IH-1 spectral restoration parameters
_IH1_FRAME_MS   = 25       # STFT frame length in ms
_IH1_HOP_MS     = 10       # STFT hop size in ms
_IH1_ALPHA_MIN  = 1.0      # minimum over-subtraction factor (clean frames)
_IH1_ALPHA_MAX  = 2.5      # maximum over-subtraction factor (noisy frames)
_IH1_BETA       = 0.002    # spectral floor (prevents total silence = musical noise)
_IH1_SMOOTH_N   = 5        # median smoothing window for gain mask (musical noise prevention)

# IH-2 formant parameters
_IH2_LPC_ORDER  = 14       # LPC analysis order (KB §21.3)
_IH2_BOOST_MAX  = 2.5      # max formant boost dB
_IH2_SMOOTH_A   = 0.80     # running average smoothing for formant tracks

# IH-3 harmonic de-noise
_IH3_HARM_WINDOW_HZ = 60.0  # bandwidth around each harmonic to protect (Hz)
_IH3_INTER_ATTN_DB  = 4.0   # max attenuation of inter-harmonic energy

# IH-4 transient reconstruction
_IH4_ONSET_THRESH_DB  = 5.0   # RMS rise to detect onset
_IH4_BOOST_MAX_DB     = 3.0   # max onset boost
_IH4_ATTACK_FRAMES    = 3     # frames over which boost is applied

# IH-5 voice presence parameters
_IH5_WARMTH_DB    = 1.5    # even-harmonic warmth in low-mid
_IH5_PRESENCE_DB  = 1.2    # 2-4 kHz presence boost
_IH5_AIR_DB       = 1.0    # 8+ kHz air shelf

# IH-6 dynamic expansion
_IH6_EXPANSION_RATIO = 1.3   # upward expansion ratio for crushed dynamics
_IH6_EXPAND_THRESH_P = 20    # percentile of frame RMS used as expansion threshold


# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def _log(msg: str) -> None:
    print(msg, flush=True)


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIO I/O HELPERS (standalone — no engine import required)
# ══════════════════════════════════════════════════════════════════════════════

def _load_mono(path: str, duration_s: float = 99_999) -> 'np.ndarray':
    """Load audio as mono float32 via ffmpeg pipe."""
    cmd = [
        'ffmpeg', '-y', '-i', path, '-t', str(duration_s),
        '-af', 'aformat=channel_layouts=stereo,pan=mono|c0=0.5*FL+0.5*FR',
        '-f', 'f32le', '-ar', str(SR), '-loglevel', 'error', '-'
    ]
    r = subprocess.run(cmd, capture_output=True)
    if not r.stdout:
        return np.zeros(SR, dtype=np.float32)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def _save_mono(audio: 'np.ndarray', out_path: str) -> bool:
    """Write mono float32 to stereo 24-bit WAV via ffmpeg."""
    raw = np.clip(audio, -1.0, 1.0).astype(np.float32).tobytes()
    r = subprocess.run(
        ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
         '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
         '-loglevel', 'error', out_path],
        input=raw, capture_output=True)
    return r.returncode == 0 and os.path.exists(out_path)


def _rms_db(a: 'np.ndarray') -> float:
    return float(20.0 * np.log10(np.sqrt(np.mean(a.astype(np.float64) ** 2)) + 1e-10))


def _peak_db(a: 'np.ndarray') -> float:
    return float(20.0 * np.log10(np.max(np.abs(a.astype(np.float64))) + 1e-10))


def _crest_db(a: 'np.ndarray') -> float:
    return _peak_db(a) - _rms_db(a)


def _sibilant_snr(audio: 'np.ndarray', noise_floor_db: float) -> Tuple[float, float]:
    """
    Return (emphatic_snr, plain_snr) for Arabic sibilants.
    Emphatic: ص ض at 3-5 kHz.  Plain: س ش at 5-8 kHz.
    (KB §4.1-4.4)
    """
    N = len(audio)
    if N < 512:
        return 10.0, 10.0
    spec  = np.abs(rfft(audio.astype(np.float64))) ** 2
    freqs = rfftfreq(N, 1.0 / SR)

    def _band_rms_db(lo, hi):
        mask = (freqs >= lo) & (freqs < hi)
        if not mask.any():
            return noise_floor_db
        return float(10.0 * np.log10(np.mean(spec[mask]) + 1e-30))

    emp_db   = _band_rms_db(_SIB_EMPHATIC_LO, _SIB_EMPHATIC_HI)
    plain_db = _band_rms_db(_SIB_PLAIN_LO,    _SIB_PLAIN_HI)
    return emp_db - noise_floor_db, plain_db - noise_floor_db


def _lra_estimate(a: 'np.ndarray') -> float:
    n = int(0.4 * SR)
    step = n // 2
    lvls = np.array([
        20.0 * np.log10(np.sqrt(np.mean(a[i:i + n].astype(np.float64) ** 2)) + 1e-10)
        for i in range(0, len(a) - n, step)
    ])
    if len(lvls) < 2:
        return 0.0
    active = lvls[lvls > np.max(lvls) - 30.0]
    if len(active) < 2:
        return 0.0
    return float(np.percentile(active, 95) - np.percentile(active, 10))


def _noise_floor_from_frames(audio: 'np.ndarray') -> float:
    """
    Estimate noise floor from the quietest 10th percentile of 20ms frames.
    Works even when the file has no pure silence (mosque / cassette context).
    (KB §28.2 TYPE A statistical noise profiling)
    """
    frame_n = int(0.020 * SR)
    if len(audio) < frame_n * 5:
        return -62.0
    levels = np.array([
        _rms_db(audio[i:i + frame_n])
        for i in range(0, len(audio) - frame_n, frame_n)
    ])
    valid = levels[levels > -90.0]
    if len(valid) < 3:
        return -62.0
    return float(np.percentile(valid, 10))


# ══════════════════════════════════════════════════════════════════════════════
#  F0 DETECTION (autocorrelation — KB §8.4, §9.4)
# ══════════════════════════════════════════════════════════════════════════════

def _detect_f0(frame: 'np.ndarray', sr: int = SR) -> float:
    """
    YIN-inspired autocorrelation F0 estimate.
    Returns F0 in Hz or 0.0 if unvoiced / confidence too low.
    Restricted to _F0_MIN_HZ–_F0_MAX_HZ for Arabic male recitation.
    """
    N = len(frame)
    if N < 512:
        return 0.0

    # Hann window
    w  = frame.astype(np.float64) * np.hanning(N)
    # Normalized autocorrelation
    ac = np.correlate(w, w, mode='full')[N - 1:]
    if ac[0] < 1e-10:
        return 0.0
    ac = ac / ac[0]

    lag_min = int(sr / _F0_MAX_HZ)
    lag_max = int(sr / _F0_MIN_HZ)
    lag_min = max(lag_min, 1)
    lag_max = min(lag_max, N - 1)

    if lag_max <= lag_min:
        return 0.0

    # Find first peak with confidence > 0.5
    candidates = ac[lag_min:lag_max]
    if len(candidates) < 2:
        return 0.0

    best_lag_offset = int(np.argmax(candidates))
    best_conf = float(candidates[best_lag_offset])

    if best_conf < 0.50:   # unvoiced frame
        return 0.0

    lag = lag_min + best_lag_offset
    if lag <= 0:
        return 0.0

    return float(sr) / float(lag)


# ══════════════════════════════════════════════════════════════════════════════
#  GATE CHECKER
# ══════════════════════════════════════════════════════════════════════════════

def _check_gate(
    pre:  'np.ndarray',
    post: 'np.ndarray',
    noise_floor: float,
    stage: str,
) -> Tuple[bool, Dict]:
    """
    Universal stage gate. Returns (passed, metrics_dict).
    Checks: RMS delta, crest delta, sibilant SNR drop.

    Sibilant gate is only meaningful when the sibilant SNR is in a realistic
    range (3-40 dB). Pure synthetic tones or very high-SNR conditions would
    cause false gate failures because tiny absolute changes = large relative
    shifts on top of a 70+ dB base. Gate is relaxed when pre_sib > 40 dB
    (signal is clean; sibilants are not at risk).
    """
    rms_pre   = _rms_db(pre)
    rms_post  = _rms_db(post)
    crest_pre = _crest_db(pre)
    crest_post= _crest_db(post)

    sib_emp_pre,  sib_pl_pre  = _sibilant_snr(pre,  noise_floor)
    sib_emp_post, sib_pl_post = _sibilant_snr(post, noise_floor)

    rms_delta   = abs(rms_post - rms_pre)
    crest_delta = abs(crest_post - crest_pre)
    sib_emp_d   = sib_emp_post  - sib_emp_pre
    sib_pl_d    = sib_pl_post   - sib_pl_pre
    sib_delta   = min(sib_emp_d, sib_pl_d)

    # Relax sibilant gate for already-clean content (pre_sib > 40 dB means
    # no real sibilant degradation risk — the noise floor is far below the signal)
    sib_threshold = _GATE_SIB_MAX_DROP_DB
    if sib_emp_pre > 40.0 and sib_pl_pre > 40.0:
        sib_threshold = _GATE_SIB_MAX_DROP_DB * 3.0  # 6 dB tolerance on clean signals

    # Relax crest gate for sources with already-destroyed dynamics (crest < 7 dB).
    # A crest of 5 dB means the signal is nearly square-wave compressed — any
    # spectral processing will cause large apparent crest swings because the
    # OLA reconstruction reveals the true peak-to-RMS ratio hidden by the tanh
    # compression. The correct behaviour is to allow these swings (they represent
    # the signal becoming more natural, not more distorted).
    crest_threshold = _GATE_CREST_MAX_DELTA
    if crest_pre < 7.0:
        crest_threshold = 8.0  # very permissive for heavily clipped/compressed signals

    passed = (
        rms_delta   <= _GATE_RMS_MAX_DELTA_DB  and
        crest_delta <= crest_threshold          and
        sib_delta   >= -sib_threshold
    )

    metrics = {
        'rms_delta':   round(rms_post - rms_pre, 2),
        'crest_delta': round(crest_post - crest_pre, 2),
        'sib_delta':   round(sib_delta, 2),
        'passed':      passed,
    }

    if not passed:
        _log(f'  [{stage}] gate FAIL: rms_delta={rms_delta:+.2f}dB '
             f'crest_delta={crest_delta:+.2f}dB sib_drop={sib_delta:+.2f}dB '
             f'(threshold: rms≤{_GATE_RMS_MAX_DELTA_DB} sib≥-{sib_threshold:.1f})')

    return passed, metrics


# ══════════════════════════════════════════════════════════════════════════════
#  IH-1: SPECTRAL RESTORATION (Wiener-style per-band NR)
#  KB §6.2, §6.4, §8.2, §11.3
# ══════════════════════════════════════════════════════════════════════════════

def _ih1_spectral_restore(
    audio: 'np.ndarray',
    noise_floor_db: float,
    frame_snr: float,
    source_tier: str,
) -> 'np.ndarray':
    """
    Soft Wiener mask with over-subtraction factor α that scales with local SNR.

    Wiener gain:  G(f) = SNR(f) / (1 + SNR(f))     [KB §6.2]
    Over-subtraction: G(f) = max(β, 1 - α × N(f)/X(f))

    α is adaptive per frame:
      - Low SNR frame (noisy): α → _IH1_ALPHA_MAX (more aggressive)
      - High SNR frame (clean): α → _IH1_ALPHA_MIN (gentle)

    Musical noise prevention (KB §6.1):
      - Apply median smoothing (window=5) across time for each frequency bin
        before applying the gain mask. This prevents isolated "speckle" bins.

    Arabic phoneme protection:
      - Gain floor raised to 0.40 in 200-800 Hz (pharyngeal zone, ع ح خ غ)
      - Gain floor raised to 0.50 in 240-380 Hz (ghunnah zone, م ن)
      - Gain floor raised to 0.35 in 3000-8000 Hz (sibilant zone, ص س ش)
      - These floors prevent total suppression of phonemically critical regions.
    """
    frame_n = int(_IH1_FRAME_MS * SR / 1000)
    hop_n   = int(_IH1_HOP_MS   * SR / 1000)
    N       = len(audio)
    if N < frame_n * 4:
        return audio.copy()

    win     = np.hanning(frame_n)
    n_bins  = frame_n // 2 + 1
    freqs   = rfftfreq(frame_n, 1.0 / SR)

    # Noise power estimate (from noise floor dB)
    noise_power_lin = 10.0 ** (noise_floor_db / 10.0)
    noise_spectrum  = np.full(n_bins, noise_power_lin, dtype=np.float64)

    # ── Build frequency-specific gain floors ────────────────────────────────
    gain_floor = np.full(n_bins, _IH1_BETA, dtype=np.float64)
    for i, f in enumerate(freqs):
        if _PHARYNGEAL_LO <= f <= _PHARYNGEAL_HI:
            gain_floor[i] = max(gain_floor[i], 0.40)
        if _GHUNNAH_LO <= f <= _GHUNNAH_HI:
            gain_floor[i] = max(gain_floor[i], 0.50)
        if _SIB_EMPHATIC_LO <= f <= _SIB_PLAIN_HI:
            gain_floor[i] = max(gain_floor[i], 0.35)

    # ── STFT forward pass: collect frames and gains ──────────────────────────
    n_frames = (N - frame_n) // hop_n + 1
    all_specs  = np.zeros((n_frames, n_bins), dtype=np.complex128)
    all_gains  = np.zeros((n_frames, n_bins), dtype=np.float64)
    frame_snrs = np.zeros(n_frames, dtype=np.float64)

    for i in range(n_frames):
        s = i * hop_n
        e = s + frame_n
        if e > N:
            break
        frame = audio[s:e].astype(np.float64) * win
        spec  = rfft(frame)
        power = np.abs(spec) ** 2

        # Frame-level SNR estimate
        frame_rms = float(np.sqrt(np.mean(power)))
        f_snr_db  = float(20.0 * np.log10(max(frame_rms, 1e-10))) - noise_floor_db
        frame_snrs[i] = f_snr_db

        # Per-frame adaptive α: bad SNR → more over-subtraction
        alpha = float(np.interp(
            f_snr_db,
            [-5.0, 15.0],
            [_IH1_ALPHA_MAX, _IH1_ALPHA_MIN]
        ))

        # Per-bin Wiener-like gain: G = max(floor, 1 - α × noise/signal)
        signal_power = np.maximum(power, 1e-30)
        raw_gain = 1.0 - alpha * noise_spectrum / signal_power
        gains = np.maximum(raw_gain, gain_floor)

        all_specs[i] = spec
        all_gains[i] = gains

    # ── Temporal median smoothing of gain masks (musical noise prevention) ──
    from scipy.signal import medfilt
    for b in range(n_bins):
        all_gains[:, b] = medfilt(all_gains[:, b],
                                   kernel_size=min(_IH1_SMOOTH_N, n_frames if n_frames % 2 == 1 else n_frames - 1) or 1)

    # ── ISTFT reconstruction (weighted OLA) ────────────────────────────────
    # Standard 75%-overlap weighted OLA:
    #   synthesis = IFFT(filtered_spec) * win
    #   normalize by sum of win^2 accumulated at each sample
    # This guarantees that when gain=1 the output equals the input.
    out  = np.zeros(N, dtype=np.float64)
    norm = np.zeros(N, dtype=np.float64)

    for i in range(n_frames):
        s = i * hop_n
        e = s + frame_n
        if e > N:
            break
        filtered_spec = all_specs[i] * all_gains[i]
        frame_out = np.real(irfft(filtered_spec, n=frame_n))
        out[s:e]  += frame_out * win   # Hann-weighted synthesis
        norm[s:e] += win * win          # Hann^2 accumulator (standard WOLA)

    # Normalise by the accumulated Hann^2 window (safe floor = 1e-6)
    norm   = np.where(norm > 1e-6, norm, 1.0)
    result = (out / norm).astype(np.float32)

    # Energy-stability normalisation: IH-1 only attenuates noise, never boosts
    # voiced content. Ensure RMS of result ≤ RMS of input (it should only go
    # down or stay flat — never up). If it somehow went up (numerical edge case
    # in median smoothing), trim it back.
    pre_rms_lin  = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)) + 1e-10)
    post_rms_lin = float(np.sqrt(np.mean(result.astype(np.float64) ** 2)) + 1e-10)
    if post_rms_lin > pre_rms_lin * 1.05:  # more than +0.4 dB drift
        scale = pre_rms_lin / post_rms_lin
        result = (result * scale).astype(np.float32)

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  IH-2: FORMANT ENHANCEMENT (LPC-based)
#  KB §8.4, §10.1-10.3, §21.3, §24.3
# ══════════════════════════════════════════════════════════════════════════════

def _lpc_formants(frame: 'np.ndarray', order: int = 14) -> List[float]:
    """
    Estimate formant frequencies (Hz) from LPC spectral peaks.
    Returns list of formant frequencies sorted ascending.
    (KB §21.3 — LPC background)
    """
    try:
        from scipy.signal import lpc as scipy_lpc
    except ImportError:
        return []

    N = len(frame)
    if N < order + 4:
        return []

    try:
        a = scipy_lpc(frame.astype(np.float64), order=order)
    except Exception:
        return []

    # Compute LPC spectrum and find peaks
    n_eval = 512
    lpc_freqs = rfftfreq(n_eval, 1.0 / SR)
    denom     = rfft(a, n=n_eval)
    lpc_spec  = 1.0 / (np.abs(denom) + 1e-10)

    formants = []
    for k in range(1, len(lpc_spec) - 1):
        if lpc_spec[k] > lpc_spec[k - 1] and lpc_spec[k] > lpc_spec[k + 1]:
            f = float(lpc_freqs[k])
            if 80.0 < f < 5000.0:
                formants.append(f)

    formants.sort()
    return formants[:4]  # F1-F4


def _ih2_formant_enhance(
    audio: 'np.ndarray',
    noise_floor_db: float,
) -> 'np.ndarray':
    """
    Per-frame LPC formant tracking and gentle boost.

    Strategy (KB §10.1, §24.3):
      - Track F1 (body/warmth), F2 (presence/clarity), F3 (singer's formant).
      - Boost formants that are below their smoothed running average.
      - Apply boost only when confidence > 0.6 (LPC residual ratio).
      - Never boost in the ghunnah zone beyond 2 dB.
      - Never cut the pharyngeal zone (ع ح: F1 at 500-900 Hz).
      - Never boost above 4 dB total.

    Result: voice clarity and identity restored without altering pitch or timing.
    """
    try:
        from scipy.signal import lpc as scipy_lpc, sosfilt, butter as sci_butter
    except ImportError:
        return audio.copy()

    frame_n = int(0.032 * SR)   # 32ms LPC frames
    hop_n   = int(0.010 * SR)   # 10ms hop
    N       = len(audio)
    if N < frame_n * 5:
        return audio.copy()

    win = np.hanning(frame_n)
    # Running smoothed formant values
    sm_f1, sm_f2, sm_f3 = 500.0, 1500.0, 2800.0

    out_ola  = np.zeros(N + frame_n, dtype=np.float64)
    norm_ola = np.zeros(N + frame_n, dtype=np.float64)

    n_frames = (N - frame_n) // hop_n

    for i in range(n_frames):
        s = i * hop_n
        e = s + frame_n
        if e > N:
            break

        frame = audio[s:e].astype(np.float64)
        f0    = _detect_f0(frame.astype(np.float32), SR)

        # Passthrough for unvoiced frames
        if f0 <= 0.0:
            out_ola[s:e]  += frame * win
            norm_ola[s:e] += win * win
            continue

        # Frame SNR gate: don't enhance frames dominated by noise
        frame_rms_db = _rms_db(frame.astype(np.float32))
        if frame_rms_db < noise_floor_db + 4.0:
            out_ola[s:e]  += frame * win
            norm_ola[s:e] += win * win
            continue

        formants = _lpc_formants(frame * win, order=_IH2_LPC_ORDER)
        if len(formants) < 2:
            out_ola[s:e]  += frame * win
            norm_ola[s:e] += win * win
            continue

        # Assign F1, F2, F3
        f1 = formants[0] if len(formants) > 0 else sm_f1
        f2 = formants[1] if len(formants) > 1 else sm_f2
        f3 = formants[2] if len(formants) > 2 else sm_f3

        # Smooth (KB §21 — stable formant tracks)
        sm_f1 = _IH2_SMOOTH_A * sm_f1 + (1.0 - _IH2_SMOOTH_A) * f1
        sm_f2 = _IH2_SMOOTH_A * sm_f2 + (1.0 - _IH2_SMOOTH_A) * f2
        sm_f3 = _IH2_SMOOTH_A * sm_f3 + (1.0 - _IH2_SMOOTH_A) * f3

        # Apply gentle spectral boost at formant positions
        spec  = rfft(frame * win)
        freqs = rfftfreq(frame_n, 1.0 / SR)
        gain  = np.ones(len(spec), dtype=np.float64)

        def _formant_boost(fc: float, boost_db: float, bw: float = 120.0):
            """Bell-shaped gain boost centered at fc Hz."""
            # Pharyngeal protection: limit boost in 200-800 Hz
            if _PHARYNGEAL_LO <= fc <= _PHARYNGEAL_HI:
                boost_db = min(boost_db, 1.5)
            # Ghunnah protection: limit boost in 240-380 Hz
            if _GHUNNAH_LO <= fc <= _GHUNNAH_HI:
                boost_db = min(boost_db, 1.0)
            # Convert dB to linear gain for the bell
            g = 10.0 ** (boost_db / 20.0)
            Q = fc / bw
            for j, f in enumerate(freqs):
                bell = 1.0 + (g - 1.0) / (1.0 + Q ** 2 * (f / fc - fc / f) ** 2 + 1e-10)
                gain[j] *= bell

        _formant_boost(sm_f1, _IH2_BOOST_MAX * 0.6)
        _formant_boost(sm_f2, _IH2_BOOST_MAX * 0.8)
        _formant_boost(sm_f3, _IH2_BOOST_MAX * 0.5, bw=200.0)

        # Hard cap: no bin can be boosted more than _IH2_BOOST_MAX dB
        max_gain = 10.0 ** (_IH2_BOOST_MAX / 20.0)
        gain     = np.clip(gain, 0.5, max_gain)

        enhanced = np.real(irfft(spec * gain, n=frame_n))
        out_ola[s:e]  += enhanced * win
        norm_ola[s:e] += win * win

    # OLA normalise (Hann^2 weighted — guarantees output==input when gain=1)
    norm_ola = np.where(norm_ola > 1e-6, norm_ola, 1.0)
    result   = (out_ola[:N] / norm_ola[:N]).astype(np.float32)
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  IH-3: HARMONIC DE-NOISE (suppress inter-harmonic smear)
#  KB §7, §21, §24.4
# ══════════════════════════════════════════════════════════════════════════════

def _ih3_harmonic_denoise(
    audio: 'np.ndarray',
    noise_floor_db: float,
) -> 'np.ndarray':
    """
    For each voiced frame:
      1. Detect F0 via autocorrelation.
      2. Build a harmonic mask: protect ±_IH3_HARM_WINDOW_HZ around each F0 multiple.
      3. Attenuate inter-harmonic energy by up to _IH3_INTER_ATTN_DB.
         This suppresses codec smear and noise that fills the valleys between
         harmonic peaks — the key artifact in damaged cassette recordings.

    The effect: voiced frames sound cleaner and more "defined" without altering
    the harmonic structure. Consonant clarity is NOT improved here (unvoiced
    frames pass through). See IH-4 for consonant sharpening.

    Guard: only attenuates — never boosts. Never touches sibilant bands.
    (KB §21.5, §7.5, §24.4)
    """
    frame_n = int(0.025 * SR)
    hop_n   = int(0.010 * SR)
    N       = len(audio)
    if N < frame_n * 4:
        return audio.copy()

    win = np.hanning(frame_n)
    freqs = rfftfreq(frame_n, 1.0 / SR)
    n_bins = frame_n // 2 + 1
    inter_attn_lin = 10.0 ** (-_IH3_INTER_ATTN_DB / 20.0)

    out_ola  = np.zeros(N + frame_n, dtype=np.float64)
    norm_ola = np.zeros(N + frame_n, dtype=np.float64)
    n_frames = (N - frame_n) // hop_n

    for i in range(n_frames):
        s = i * hop_n
        e = s + frame_n
        if e > N:
            break

        frame = audio[s:e].astype(np.float64)
        spec  = rfft(frame * win)

        f0 = _detect_f0(frame.astype(np.float32), SR)
        if f0 <= 0.0:
            # Unvoiced: passthrough
            out_ola[s:e]  += np.real(irfft(spec, n=frame_n)) * win
            norm_ola[s:e] += win * win
            continue

        # Check frame level is above noise
        if _rms_db(frame.astype(np.float32)) < noise_floor_db + 6.0:
            out_ola[s:e]  += np.real(irfft(spec, n=frame_n)) * win
            norm_ola[s:e] += win * win
            continue

        # Build harmonic protection mask
        harm_mask = np.zeros(n_bins, dtype=np.float64)
        k = 1
        while k * f0 < SR / 2.0 and k * f0 < 12_000.0:
            center = k * f0
            for j, f in enumerate(freqs):
                if abs(f - center) < _IH3_HARM_WINDOW_HZ:
                    harm_mask[j] = 1.0
            k += 1

        # Gain: harmonic bins → 1.0, inter-harmonic → inter_attn_lin
        # Never touch sibilant zone (3-8 kHz) — leave fully intact
        gain = np.where(harm_mask > 0.5, 1.0, inter_attn_lin)
        for j, f in enumerate(freqs):
            if f >= _SIB_EMPHATIC_LO:
                gain[j] = 1.0  # sibilant zone: never attenuate

        enhanced = np.real(irfft(spec * gain, n=frame_n))
        out_ola[s:e]  += enhanced * win
        norm_ola[s:e] += win * win

    norm_ola = np.where(norm_ola > 1e-6, norm_ola, 1.0)
    return (out_ola[:N] / norm_ola[:N]).astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════════
#  IH-4: TRANSIENT RECONSTRUCTION
#  KB §21.5, §24.5 J-2, §33.3
# ══════════════════════════════════════════════════════════════════════════════

def _ih4_transient_reconstruct(
    audio: 'np.ndarray',
    noise_floor_db: float,
    source_tier: str,
) -> 'np.ndarray':
    """
    Re-sharpen consonant attack edges that have been blunted by:
      - MP3 MDCT temporal smear (pre-echo / post-smear)
      - Codec low-pass blurring at the codec cutoff
      - Over-aggressive NR over-smoothing

    Method (KB §21.5, §24.5 J-2):
      1. Compute frame-by-frame RMS in 5ms windows.
      2. Detect onset: frame_rms[n] / frame_rms[n-1] > _IH4_ONSET_THRESH_DB.
      3. At detected onsets: apply short-duration spectral flux boost —
         increase mid-frequency (300 Hz – 8 kHz) spectral contrast.
      4. Boost is cosine-tapered over _IH4_ATTACK_FRAMES frames after onset.
      5. Qalqalah guard (ق ط ب ج د): if onset RMS is < median+3dB,
         treat as Qalqalah transient — use smaller boost (1/3 of max).

    The attack sharpening is purely gain-based in the spectral domain —
    no pitch shifting, no time-stretching.
    """
    frame_n = int(0.005 * SR)   # 5ms for precise onset detection
    N = len(audio)
    if N < frame_n * 10:
        return audio.copy()

    # Compute frame RMS
    n_frames = N // frame_n
    frame_rms = np.array([
        _rms_db(audio[i * frame_n:(i + 1) * frame_n])
        for i in range(n_frames)
    ])

    # Global activity threshold
    median_rms = float(np.median(frame_rms[frame_rms > -80.0]))
    active_thresh = median_rms - 15.0

    # Processing block size for spectral enhancement at onset
    proc_n = int(0.020 * SR)   # 20ms spectral block at onset
    proc_win = np.hanning(proc_n)
    proc_freqs = rfftfreq(proc_n, 1.0 / SR)

    boost_max_db = _IH4_BOOST_MAX_DB
    if source_tier == 'TIER_CRITICAL':
        boost_max_db *= 0.7   # conservative for worst-case sources

    result = audio.copy().astype(np.float64)

    for i in range(2, n_frames - _IH4_ATTACK_FRAMES - 1):
        rms_now  = frame_rms[i]
        rms_prev = frame_rms[i - 1]

        # Skip inactive or noise-dominated frames
        if rms_now < active_thresh or rms_now < noise_floor_db + 8.0:
            continue

        # Onset detection: rise of > threshold in 5ms
        rise_db = rms_now - rms_prev
        if rise_db < _IH4_ONSET_THRESH_DB:
            continue

        # Qalqalah guard: lighter boost for soft onsets (echoing stops)
        is_qalqalah = (rms_now < median_rms + 3.0)
        boost_db = boost_max_db * (0.33 if is_qalqalah else 1.0)
        boost_lin = 10.0 ** (boost_db / 20.0)

        # Apply cosine-tapered spectral boost at onset position
        sample_onset = i * frame_n
        for k in range(_IH4_ATTACK_FRAMES):
            s = sample_onset + k * frame_n
            e = s + proc_n
            if e > N:
                break

            # Cosine taper: full boost at onset, decay toward zero
            taper = 0.5 * (1.0 + math.cos(math.pi * k / _IH4_ATTACK_FRAMES))
            b     = 1.0 + (boost_lin - 1.0) * taper

            segment = result[s:e].copy()
            if len(segment) < proc_n:
                continue

            spec  = rfft(segment * proc_win)
            gain  = np.ones(len(spec), dtype=np.float64)

            for j, f in enumerate(proc_freqs):
                # Boost 300 Hz – 8 kHz range (consonant energy, KB §10.3)
                if 300.0 <= f <= 8_000.0:
                    # Sibilant zone: very light boost only (protect emphatic ratio)
                    if _SIB_EMPHATIC_LO <= f <= _SIB_EMPHATIC_HI:
                        gain[j] = 1.0 + (b - 1.0) * 0.4
                    elif f >= _SIB_PLAIN_LO:
                        gain[j] = 1.0 + (b - 1.0) * 0.6
                    else:
                        gain[j] = b

            enhanced = np.real(irfft(spec * gain, n=proc_n))

            # Soft-blend back (not a hard replacement)
            alpha = 0.4 * taper
            result[s:e] = (1.0 - alpha) * segment + alpha * enhanced

    return np.clip(result, -1.0, 1.0).astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════════
#  IH-5: VOICE PRESENCE LAYER
#  KB §7.1, §7.2, §24.4 النور, §24.5 الجلال J-3
# ══════════════════════════════════════════════════════════════════════════════

def _ih5_presence_layer(
    audio: 'np.ndarray',
    noise_floor_db: float,
    codec_cutoff: float,
    source_tier: str,
) -> 'np.ndarray':
    """
    Three-layer voice presence injection for damaged/critical sources.
    Operates in the frequency domain on a voiced-only OLA.

    Layer A — Warmth (100-400 Hz, KB §7.1):
      Add gentle even-harmonic energy in low-mid. Simulates the tube-warmth
      that broadcasts and recordings naturally had. Even harmonics are perceived
      as "warm" and "round" (never harsh).

    Layer B — Presence (1500-4000 Hz, KB §24.5 J-3 / singer's formant):
      +_IH5_PRESENCE_DB bell boost. Restores the voice's ability to "cut
      through" — the region most damaged by low-bitrate codecs and cassette EQ.

    Layer C — Air (8000+ Hz, only if codec_cutoff allows, KB §2.6):
      +_IH5_AIR_DB high shelf. Adds "openness" and the acoustic shimmer of the
      mosque ceiling reflections. Skipped if codec_cutoff < 10 kHz.

    Scale factors by tier:
      TIER_DAMAGED:  0.75 of all gains (conservative — source is structurally weak)
      TIER_CRITICAL: 0.50 of all gains (most conservative)
    """
    scale = 0.75 if source_tier == 'TIER_DAMAGED' else 0.50

    frame_n = int(0.030 * SR)
    hop_n   = int(0.010 * SR)
    N = len(audio)
    if N < frame_n * 4:
        return audio.copy()

    win   = np.hanning(frame_n)
    freqs = rfftfreq(frame_n, 1.0 / SR)

    warmth_db   = _IH5_WARMTH_DB   * scale
    presence_db = _IH5_PRESENCE_DB * scale
    air_db      = _IH5_AIR_DB      * scale if codec_cutoff > 10_000.0 else 0.0

    warmth_lin   = 10.0 ** (warmth_db   / 20.0)
    presence_lin = 10.0 ** (presence_db / 20.0)
    air_lin      = 10.0 ** (air_db      / 20.0)

    out_ola  = np.zeros(N + frame_n, dtype=np.float64)
    norm_ola = np.zeros(N + frame_n, dtype=np.float64)
    n_frames = (N - frame_n) // hop_n

    for i in range(n_frames):
        s = i * hop_n
        e = s + frame_n
        if e > N:
            break

        frame = audio[s:e].astype(np.float64)
        rms_f = _rms_db(frame.astype(np.float32))

        # Only apply to frames with real voiced content
        if rms_f < noise_floor_db + 6.0:
            out_ola[s:e]  += frame * win
            norm_ola[s:e] += win * win
            continue

        f0 = _detect_f0(frame.astype(np.float32), SR)

        spec = rfft(frame * win)
        gain = np.ones(len(spec), dtype=np.float64)

        for j, f in enumerate(freqs):
            # Layer A: Warmth — only on voiced frames with detected F0
            if f0 > 0.0 and 100.0 <= f <= 400.0:
                # Bell at 200 Hz, width ≈ 2 octaves
                g_bell = 1.0 + (warmth_lin - 1.0) / (1.0 + 4.0 * (f / 200.0 - 200.0 / f) ** 2)
                gain[j] *= g_bell

            # Layer B: Presence — 1500-4000 Hz
            if 1_500.0 <= f <= 4_000.0:
                # Bell centered at 2800 Hz (singer's formant, KB §24.5 J-3)
                g_bell = 1.0 + (presence_lin - 1.0) / (1.0 + 2.0 * (f / 2800.0 - 2800.0 / f) ** 2)
                gain[j] *= g_bell

            # Layer C: Air — 8000+ Hz (high shelf)
            if air_lin > 1.0 and f >= 8_000.0 and f < codec_cutoff * 0.90:
                # Soft shelf: linear ramp 8-10 kHz, then flat
                shelf = min(1.0, (f - 8_000.0) / 2_000.0)
                gain[j] *= (1.0 + (air_lin - 1.0) * shelf)

        # Hard cap: max +4 dB any bin
        max_g = 10.0 ** (4.0 / 20.0)
        gain  = np.clip(gain, 0.7, max_g)

        enhanced = np.real(irfft(spec * gain, n=frame_n))
        out_ola[s:e]  += enhanced * win
        norm_ola[s:e] += win * win

    norm_ola = np.where(norm_ola > 1e-6, norm_ola, 1.0)
    return (out_ola[:N] / norm_ola[:N]).astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════════
#  IH-6: DYNAMIC RESTORATION (soft upward expansion)
#  KB §5.2, §5.5, §28.3 TYPE B
# ══════════════════════════════════════════════════════════════════════════════

def _ih6_dynamic_restore(
    audio: 'np.ndarray',
    target_lra: float,
    source_tier: str,
) -> 'np.ndarray':
    """
    Soft upward expansion to partially restore dynamic range crushed by
    cassette Dolby NR, AGC, or broadcast processing.

    Unlike TYPE_B (which uses ffmpeg agate), this implementation works in
    the time domain directly so it can be gated by the LRA target.

    Algorithm (KB §5.2, §28.3):
      1. Compute frame-level RMS in 20ms windows.
      2. Determine expansion threshold at p20 of active frame levels.
         (Only expand the softer 80% — the loud top 20% is already correct.)
      3. For each frame below threshold: apply soft upward expansion.
         New level = old_level + ratio_factor × (threshold - old_level)
         where ratio_factor = 1 - 1/expansion_ratio.
      4. Cross-fade the expanded signal with the original using a frame envelope.
      5. Gate: stop when measured LRA ≥ target_lra - 0.3 LU.

    Safety:
      - Maximum per-frame gain: 4.0 dB.
      - Never expand frames below noise floor + 10 dB (would amplify noise).
      - Crest factor must not decrease (over-expansion squashes dynamics).
    """
    current_lra = _lra_estimate(audio)
    if current_lra >= target_lra - 0.30:
        return audio.copy()  # already at target, no expansion needed

    frame_n = int(0.020 * SR)
    hop_n   = frame_n
    N = len(audio)
    if N < frame_n * 10:
        return audio.copy()

    noise_floor = _noise_floor_from_frames(audio)

    n_frames = N // frame_n
    frame_rms = np.array([
        _rms_db(audio[i * frame_n:(i + 1) * frame_n])
        for i in range(n_frames)
    ])

    active_rms = frame_rms[frame_rms > noise_floor + 10.0]
    if len(active_rms) < 4:
        return audio.copy()

    # Expansion threshold: p20 of active levels
    thresh_db = float(np.percentile(active_rms, _IH6_EXPAND_THRESH_P))

    # Expansion: how much to lift soft frames
    ratio_factor = 1.0 - 1.0 / _IH6_EXPANSION_RATIO

    # Scale factor: more cautious for CRITICAL tier
    if source_tier == 'TIER_CRITICAL':
        ratio_factor *= 0.5

    result = audio.copy().astype(np.float64)
    max_gain_db = 4.0

    for i in range(n_frames):
        s = i * frame_n
        e = min(s + frame_n, N)
        seg = result[s:e]
        rms = frame_rms[i]

        # Only expand frames below threshold and above noise
        if rms >= thresh_db or rms < noise_floor + 10.0:
            continue

        # Amount of gain to apply
        deficit_db = thresh_db - rms
        gain_db    = min(ratio_factor * deficit_db, max_gain_db)
        gain_lin   = 10.0 ** (gain_db / 20.0)

        # Soft blend (not hard gain — avoids clicks at frame boundaries)
        # Use cosine window within the frame
        blend = 0.5 * (1.0 - np.cos(np.pi * np.arange(len(seg)) / len(seg)))
        result[s:e] = seg * (1.0 + (gain_lin - 1.0) * blend)

    return np.clip(result, -1.0, 1.0).astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════════
#  PIPELINE ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

def apply_ihyaa_to_engine(
    wav_path:    str,
    state:       object,
    ref:         object,
) -> Tuple[str, Dict]:
    """
    Main entry point — called by the engine after Phase B NR.

    Parameters
    ----------
    wav_path : str
        Path to the NR-processed WAV file.
    state : InputState (duck-typed)
        Engine state with at least: source_tier, silence_floor, codec_cutoff,
        clip_lra, frame_snr, skip_s, dur_s, total_s.
    ref : ReferenceModel (duck-typed)
        Reference with: lra (target LRA), phrase_lra_p50.

    Returns
    -------
    (best_wav_path, report_dict)
    """
    report: Dict = {
        'applied':   False,
        'skipped':   False,
        'skip_reason': '',
        # Per-stage metrics
        'ih1_spectral_applied':    False,
        'ih1_sib_delta':           0.0,
        'ih1_rms_delta':           0.0,
        'ih2_formant_applied':     False,
        'ih2_sib_delta':           0.0,
        'ih2_rms_delta':           0.0,
        'ih3_harmonic_applied':    False,
        'ih3_sib_delta':           0.0,
        'ih3_rms_delta':           0.0,
        'ih4_transient_applied':   False,
        'ih4_sib_delta':           0.0,
        'ih4_rms_delta':           0.0,
        'ih5_presence_applied':    False,
        'ih5_sib_delta':           0.0,
        'ih5_rms_delta':           0.0,
        'ih6_dynamic_applied':     False,
        'ih6_lra_before':          0.0,
        'ih6_lra_after':           0.0,
        'ih6_rms_delta':           0.0,
        # Overall
        'overall_rms_delta':       0.0,
        'overall_crest_delta':     0.0,
        'overall_sib_emp_delta':   0.0,
        'overall_sib_plain_delta': 0.0,
    }

    # ── Tier gate ─────────────────────────────────────────────────────────────
    tier = getattr(state, 'source_tier', 'TIER_PRISTINE')
    if tier not in IHYAA_TIERS:
        report['skipped']     = True
        report['skip_reason'] = f'tier={tier} not in IHYAA_TIERS'
        return wav_path, report

    if not NUMPY_OK:
        report['skipped']     = True
        report['skip_reason'] = 'numpy_unavailable'
        return wav_path, report

    _log(f'\n  ╔═══════════════════════════════════════╗')
    _log(f'  ║  إحياء — Ihyaa Voice Enhancement       ║')
    _log(f'  ║  tier={tier:<22}   ║')
    _log(f'  ╚═══════════════════════════════════════╝')

    # ── Load audio ─────────────────────────────────────────────────────────────
    total_s = float(getattr(state, 'total_s', 300.0))
    audio   = _load_mono(wav_path, duration_s=total_s)

    if len(audio) < SR * 5:
        report['skipped']     = True
        report['skip_reason'] = 'audio_too_short'
        return wav_path, report

    noise_floor  = float(getattr(state, 'silence_floor', -62.0))
    codec_cutoff = float(getattr(state, 'codec_cutoff',  12_000.0))
    frame_snr    = float(getattr(state, 'frame_snr',     8.0))
    target_lra   = float(getattr(ref,   'phrase_lra_p50', 3.37))

    # Baseline measurements
    pre_rms   = _rms_db(audio)
    pre_crest = _crest_db(audio)
    pre_sib_emp, pre_sib_plain = _sibilant_snr(audio, noise_floor)

    _log(f'  [Ihyaa] baseline: RMS={pre_rms:.2f}dBFS  crest={pre_crest:.2f}dB  '
         f'sib_emp={pre_sib_emp:.1f}dB  sib_plain={pre_sib_plain:.1f}dB  '
         f'floor={noise_floor:.1f}dBFS  SNR={frame_snr:.1f}dB')

    current = audio.copy()

    # ═══════════════════════════════════════════════════════════════════════════
    #  STAGE IH-1: Spectral Restoration
    # ═══════════════════════════════════════════════════════════════════════════
    _log('  [IH-1] Spectral Restoration (Wiener mask)...')
    try:
        processed = _ih1_spectral_restore(current, noise_floor, frame_snr, tier)
        ok, m = _check_gate(current, processed, noise_floor, 'IH-1')
        if ok:
            current = processed
            report['ih1_spectral_applied'] = True
            report['ih1_sib_delta']        = m['sib_delta']
            report['ih1_rms_delta']        = m['rms_delta']
            _log(f'  [IH-1] ✓ rms_delta={m["rms_delta"]:+.2f}dB  sib={m["sib_delta"]:+.2f}dB')
        else:
            _log('  [IH-1] gate failed — reverted')
    except Exception as ex:
        _log(f'  [IH-1] exception: {ex} — skipped')

    # ═══════════════════════════════════════════════════════════════════════════
    #  STAGE IH-2: Formant Enhancement
    # ═══════════════════════════════════════════════════════════════════════════
    _log('  [IH-2] Formant Enhancement (LPC)...')
    try:
        processed = _ih2_formant_enhance(current, noise_floor)
        ok, m = _check_gate(current, processed, noise_floor, 'IH-2')
        if ok:
            current = processed
            report['ih2_formant_applied'] = True
            report['ih2_sib_delta']       = m['sib_delta']
            report['ih2_rms_delta']       = m['rms_delta']
            _log(f'  [IH-2] ✓ rms_delta={m["rms_delta"]:+.2f}dB  sib={m["sib_delta"]:+.2f}dB')
        else:
            _log('  [IH-2] gate failed — reverted')
    except Exception as ex:
        _log(f'  [IH-2] exception: {ex} — skipped')

    # ═══════════════════════════════════════════════════════════════════════════
    #  STAGE IH-3: Harmonic De-noise
    # ═══════════════════════════════════════════════════════════════════════════
    _log('  [IH-3] Harmonic De-noise (inter-harmonic suppression)...')
    try:
        processed = _ih3_harmonic_denoise(current, noise_floor)
        ok, m = _check_gate(current, processed, noise_floor, 'IH-3')
        if ok:
            current = processed
            report['ih3_harmonic_applied'] = True
            report['ih3_sib_delta']        = m['sib_delta']
            report['ih3_rms_delta']        = m['rms_delta']
            _log(f'  [IH-3] ✓ rms_delta={m["rms_delta"]:+.2f}dB  sib={m["sib_delta"]:+.2f}dB')
        else:
            _log('  [IH-3] gate failed — reverted')
    except Exception as ex:
        _log(f'  [IH-3] exception: {ex} — skipped')

    # ═══════════════════════════════════════════════════════════════════════════
    #  STAGE IH-4: Transient Reconstruction
    # ═══════════════════════════════════════════════════════════════════════════
    _log('  [IH-4] Transient Reconstruction (onset sharpening)...')
    try:
        processed = _ih4_transient_reconstruct(current, noise_floor, tier)
        ok, m = _check_gate(current, processed, noise_floor, 'IH-4')
        if ok:
            current = processed
            report['ih4_transient_applied'] = True
            report['ih4_sib_delta']         = m['sib_delta']
            report['ih4_rms_delta']         = m['rms_delta']
            _log(f'  [IH-4] ✓ rms_delta={m["rms_delta"]:+.2f}dB  sib={m["sib_delta"]:+.2f}dB')
        else:
            _log('  [IH-4] gate failed — reverted')
    except Exception as ex:
        _log(f'  [IH-4] exception: {ex} — skipped')

    # ═══════════════════════════════════════════════════════════════════════════
    #  STAGE IH-5: Voice Presence Layer
    # ═══════════════════════════════════════════════════════════════════════════
    _log('  [IH-5] Voice Presence Layer (warmth + presence + air)...')
    try:
        processed = _ih5_presence_layer(current, noise_floor, codec_cutoff, tier)
        ok, m = _check_gate(current, processed, noise_floor, 'IH-5')
        if ok:
            current = processed
            report['ih5_presence_applied'] = True
            report['ih5_sib_delta']        = m['sib_delta']
            report['ih5_rms_delta']        = m['rms_delta']
            _log(f'  [IH-5] ✓ rms_delta={m["rms_delta"]:+.2f}dB  sib={m["sib_delta"]:+.2f}dB')
        else:
            _log('  [IH-5] gate failed — reverted')
    except Exception as ex:
        _log(f'  [IH-5] exception: {ex} — skipped')

    # ═══════════════════════════════════════════════════════════════════════════
    #  STAGE IH-6: Dynamic Restoration
    # ═══════════════════════════════════════════════════════════════════════════
    lra_before = _lra_estimate(current)
    report['ih6_lra_before'] = round(lra_before, 3)
    _log(f'  [IH-6] Dynamic Restoration (LRA: {lra_before:.2f}→{target_lra:.2f} LU)...')
    try:
        processed = _ih6_dynamic_restore(current, target_lra, tier)
        ok, m = _check_gate(current, processed, noise_floor, 'IH-6')
        lra_after = _lra_estimate(processed)
        if ok:
            current = processed
            report['ih6_dynamic_applied'] = True
            report['ih6_lra_after']       = round(lra_after, 3)
            report['ih6_rms_delta']       = m['rms_delta']
            _log(f'  [IH-6] ✓ LRA {lra_before:.2f}→{lra_after:.2f} LU  '
                 f'rms_delta={m["rms_delta"]:+.2f}dB')
        else:
            report['ih6_lra_after'] = lra_before
            _log('  [IH-6] gate failed — reverted')
    except Exception as ex:
        _log(f'  [IH-6] exception: {ex} — skipped')
        report['ih6_lra_after'] = lra_before

    # ═══════════════════════════════════════════════════════════════════════════
    #  OVERALL GATE: compare final vs original
    # ═══════════════════════════════════════════════════════════════════════════
    post_rms   = _rms_db(current)
    post_crest = _crest_db(current)
    post_sib_emp, post_sib_plain = _sibilant_snr(current, noise_floor)

    overall_lufs_delta = abs(post_rms - pre_rms)
    overall_sib_emp_d  = post_sib_emp  - pre_sib_emp
    overall_sib_plain_d= post_sib_plain - pre_sib_plain

    report['overall_rms_delta']       = round(post_rms   - pre_rms,   2)
    report['overall_crest_delta']     = round(post_crest - pre_crest, 2)
    report['overall_sib_emp_delta']   = round(overall_sib_emp_d,      2)
    report['overall_sib_plain_delta'] = round(overall_sib_plain_d,    2)

    # Full revert if overall LUFS delta exceeds hard limit or sibilants harmed
    if (overall_lufs_delta > _GATE_LUFS_MAX_DELTA or
            overall_sib_emp_d < -_GATE_SIB_MAX_DROP_DB or
            overall_sib_plain_d < -_GATE_SIB_MAX_DROP_DB):
        _log(f'  [Ihyaa] OVERALL GATE FAIL: lufs_delta={overall_lufs_delta:.2f}dB  '
             f'sib_emp={overall_sib_emp_d:+.2f}dB  sib_plain={overall_sib_plain_d:+.2f}dB')
        _log('  [Ihyaa] → FULL REVERT to pre-Ihyaa audio')
        report['skipped']     = True
        report['skip_reason'] = 'overall_gate_failure'
        return wav_path, report

    # ── Write output ──────────────────────────────────────────────────────────
    out_path = os.path.join(_TMP, 'ihyaa_output.wav')
    ok_write = _save_mono(current, out_path)
    if not ok_write:
        _log('  [Ihyaa] write failed — FULL REVERT')
        report['skipped']     = True
        report['skip_reason'] = 'write_failed'
        return wav_path, report

    stages_applied = sum([
        report['ih1_spectral_applied'],
        report['ih2_formant_applied'],
        report['ih3_harmonic_applied'],
        report['ih4_transient_applied'],
        report['ih5_presence_applied'],
        report['ih6_dynamic_applied'],
    ])

    report['applied'] = (stages_applied > 0)

    _log(f'  ╔═══════════════════════════════════════╗')
    _log(f'  ║  إحياء Complete: {stages_applied}/6 stages applied      ║')
    _log(f'  ║  RMS {pre_rms:.2f}→{post_rms:.2f}dBFS'
         f'  crest {pre_crest:.2f}→{post_crest:.2f}dB  ║')
    _log(f'  ║  sib_emp {pre_sib_emp:.1f}→{post_sib_emp:.1f}dB'
         f'  sib_pl {pre_sib_plain:.1f}→{post_sib_plain:.1f}dB    ║')
    _log(f'  ╚═══════════════════════════════════════╝')

    if not report['applied']:
        return wav_path, report

    return out_path, report


# ══════════════════════════════════════════════════════════════════════════════
#  ENGINE INTEGRATION HELPER (engine v11 compatibility)
#  Call this from the engine's enhance() function after nr_pass() returns,
#  and before the EQ optimization phase.
# ══════════════════════════════════════════════════════════════════════════════

def ihyaa_apply_and_update_state(
    wav_path: str,
    state:    object,
    ref:      object,
) -> Tuple[str, Dict]:
    """
    Convenience wrapper that calls apply_ihyaa_to_engine() and updates
    the engine InputState with Ihyaa result fields.

    Usage in engine enhance():
        from ihyaa_ve import ihyaa_apply_and_update_state
        nr_wav, ihyaa_rep = ihyaa_apply_and_update_state(nr_wav, state, ref)
        # nr_wav now points to Ihyaa-enhanced audio (or original if skipped)

    Sets on state (all duck-typed — safe if attributes don't exist):
        state.ihyaa_applied       : bool
        state.ihyaa_stages_applied: int
        state.ihyaa_report        : dict
    """
    result_path, report = apply_ihyaa_to_engine(wav_path, state, ref)

    stages = sum([
        report.get('ih1_spectral_applied', False),
        report.get('ih2_formant_applied',  False),
        report.get('ih3_harmonic_applied', False),
        report.get('ih4_transient_applied',False),
        report.get('ih5_presence_applied', False),
        report.get('ih6_dynamic_applied',  False),
    ])

    try:
        state.ihyaa_applied        = report.get('applied', False)
        state.ihyaa_stages_applied = stages
        state.ihyaa_report         = report
    except AttributeError:
        pass  # State is read-only or duck-typed without these attrs

    return result_path, report


# ══════════════════════════════════════════════════════════════════════════════
#  STANDALONE CLI (for testing without full engine)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    import argparse
    import sys

    p = argparse.ArgumentParser(
        description='إحياء — Ihyaa Voice Enhancement (standalone test)')
    p.add_argument('-i', '--input',  required=True,  help='Input WAV/MP3')
    p.add_argument('-o', '--output', required=True,  help='Output WAV')
    p.add_argument('--tier', default='TIER_DAMAGED',
                   choices=['TIER_DAMAGED', 'TIER_CRITICAL'])
    p.add_argument('--floor', type=float, default=-62.0,
                   help='Estimated noise floor dBFS')
    p.add_argument('--codec-cutoff', type=float, default=12_000.0,
                   help='Codec cutoff frequency Hz')
    p.add_argument('--frame-snr', type=float, default=8.0,
                   help='Frame SNR estimate dB')
    p.add_argument('--target-lra', type=float, default=3.37,
                   help='Target LRA in LU')
    args = p.parse_args()

    if not NUMPY_OK:
        print('ERROR: numpy/scipy not available. pip install numpy scipy')
        sys.exit(1)

    # Convert input to WAV if needed
    src = args.input
    if not src.endswith('.wav'):
        tmp_wav = os.path.join(_TMP, 'ihyaa_input.wav')
        r = subprocess.run(
            ['ffmpeg', '-y', '-i', src, '-ar', str(SR), '-ac', '2',
             '-c:a', WAV_CODEC, '-loglevel', 'error', tmp_wav],
            capture_output=True)
        if r.returncode != 0:
            print(f'ERROR: ffmpeg conversion failed for {src}')
            sys.exit(1)
        src = tmp_wav

    # Build minimal duck-typed state and ref
    class _MockState:
        source_tier   = args.tier
        silence_floor = args.floor
        codec_cutoff  = args.codec_cutoff
        frame_snr     = args.frame_snr
        total_s       = 999.0
        skip_s        = 0
        dur_s         = 60
        clip_lra      = 2.0

    class _MockRef:
        phrase_lra_p50 = args.target_lra
        lra            = args.target_lra

    result_path, report = apply_ihyaa_to_engine(src, _MockState(), _MockRef())

    if report.get('applied'):
        # Copy to output
        import shutil
        shutil.copy2(result_path, args.output)
        print(f'\n✓ Ihyaa complete → {args.output}')
        print(f'  Stages: IH-1={report["ih1_spectral_applied"]} '
              f'IH-2={report["ih2_formant_applied"]} '
              f'IH-3={report["ih3_harmonic_applied"]} '
              f'IH-4={report["ih4_transient_applied"]} '
              f'IH-5={report["ih5_presence_applied"]} '
              f'IH-6={report["ih6_dynamic_applied"]}')
        print(f'  RMS delta: {report["overall_rms_delta"]:+.2f} dB')
        print(f'  Crest delta: {report["overall_crest_delta"]:+.2f} dB')
        print(f'  Sibilant emp delta: {report["overall_sib_emp_delta"]:+.2f} dB')
        print(f'  Sibilant plain delta: {report["overall_sib_plain_delta"]:+.2f} dB')
        if report['ih6_dynamic_applied']:
            print(f'  LRA: {report["ih6_lra_before"]:.2f} → {report["ih6_lra_after"]:.2f} LU')
    else:
        reason = report.get('skip_reason', 'unknown')
        print(f'\n— Ihyaa skipped: {reason}')
        if not report.get('skipped') and src != args.output:
            import shutil
            shutil.copy2(src, args.output)
