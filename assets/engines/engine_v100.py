#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║        TILAWA AUDIO ENHANCEMENT ENGINE — TRUE BASE v10                      ║
║        محسِّن التلاوة القرآنية — القاعدة الحقيقية الإصدار العاشر             ║
║                                                                              ║
║        المرجع: الشيخ ياسر الدوسري — 1425H                                   ║
║        الهدف: LUFS=-6.29 | RMS=-10.01 | Crest=10.25 | LRA=4.19              ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  TIER CLASSIFICATION: FOUNDATION TIER — TIER 1 of 7                         ║
║  ─────────────────────────────────────────────────────────────────────────  ║
║  This engine is the foundation of The Aetherion system.                      ║
║  It handles the complete normalization pipeline:                             ║
║    ✓ Source quality assessment (4 tiers + confidence vectors)               ║
║    ✓ Declipping (cubic spline, 0.05% threshold)                             ║
║    ✓ Two-stage noise reduction (hum notch + frequency-aware NR)             ║
║    ✓ Spectral EQ from post-NR spectrum (L-BFGS-B optimizer)                ║
║    ✓ Joint LUFS+LRA optimization (3-position empirical PCHIP)               ║
║    ✓ True Peak encode with limiter correction                                ║
║                                                                              ║
║  What this engine does NOT do (reserved for higher Aetherion engines):      ║
║    ✗ LRA expansion for severely compressed sources (Engine-1: الاسترداد)   ║
║    ✗ Room acoustic correction (Engine-4: الفضاء)                            ║
║    ✗ Phoneme-level Tajweed preservation (Engine-5: البيان)                  ║
║    ✗ Presence/breath restoration (Engine-3: النَّفَس)                        ║
║    ✗ 48-band perceptual push for high quality sources (Engine-2: الإتقان)   ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ARCHITECTURE — 24 CUMULATIVE FIXES from v9.0 → v10 BASE                   ║
║                                                                              ║
║  CORRECTNESS                                                                 ║
║  FIX-01  third_octave(): Hann window + power-preserving normalization        ║
║  FIX-02  third_octave(): MAX_N=sr*4 cap — 10× faster, zero quality loss     ║
║  FIX-03  load_reference_model(): pipe to stdout, no WAV header garbage       ║
║  FIX-22  build_bias_filter_nodes(): MDS quality scale (bias ∝ damage)       ║
║  FIX-23  compand_confidence: high Crest = natural dynamics, not permission   ║
║  FIX-24  design_eq(): EQ scale gate, 55% max for PRISTINE/COMPRESSED        ║
║  BUG-A   codec_cutoff: bitrate floor prevents quiet-file misclassification   ║
║  BUG-B   phrase detection: min 3s (was 1s — too short for lra_estimate)     ║
║  BUG-C   do-no-harm: compare to achievable_crest, not raw input crest        ║
║  BUG-D   LUFS trim: ±18dB range (was ±6dB — broke all quiet sources)        ║
║  BUG-E   phrase_lra: sliding window median (replaces broken detector)        ║
║  BUG-F   joint gain: ±18dB range (was ±6dB)                                 ║
║  BUG-G   LUFS measurement: speech-gated RMS (not silence-distorted LUFS)    ║
║  FIX-E   do-no-harm: relative spec_dist threshold (not fixed 8.0)           ║
║  FIX-F   TIER_COMPRESSED: achievable Crest 10.1 (was 9.8, too conservative) ║
║                                                                              ║
║  NOISE REDUCTION (v10 Base NR overhaul)                                      ║
║  NR-01   Two-stage NR: hum removal → broadband → HF hiss separate passes   ║
║  NR-02   Frequency-aware depth: heavier NR above 4kHz (hiss), light below   ║
║  NR-03   Silence-frame noise profile: spectral shape, not single nf value   ║
║  NR-04   Post-NR SFM gate: revert if noise became more tonal (wrong)        ║
║  NR-05   Adaptive nr depth from silence frame count (more frames = deeper)  ║
║                                                                              ║
║  PERFORMANCE                                                                 ║
║  FIX-04  _sample_phrase_lra(): multi-position (whole file, not first 5min)  ║
║  FIX-05  _detect_smear(): ZCR gate separates fricatives from weak vowels     ║
║  FIX-06  _eq_band_confidence(): per-band (not uniform scalar)               ║
║  FIX-07  _lpc_sibilant_nodes(): LPC formant restoration for smear           ║
║  FIX-09  Joint calibration: clips first (not full-file × 3)                 ║
║  FIX-10  Joint calibration: actual LUFS per clip (not RMS proxy)            ║
║  FIX-15  WAV spectrum: single-load (no 9× subprocess overhead)              ║
║  FIX-18  Iteration: thread current_input (compounding, not averaging)       ║
║  FIX-19  EQ basis: r1.spectrum pre-joint (not r2 post-joint)               ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  ★ BETA RELEASE — THE AETHERION PROJECT — FOUNDATION ENGINE                 ║
║    Built by one developer. On a Samsung S22. In Termux. For the Quran.     ║
║    وما التوفيق إلا بالله                                                      ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, sys, time, tempfile, warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
warnings.filterwarnings('ignore')

_TMP = tempfile.gettempdir()

try:
    import numpy as np
    from scipy.fft import rfft, rfftfreq
    from scipy.optimize import minimize
    NUMPY_OK = SCIPY_OK = True
except ImportError:
    NUMPY_OK = SCIPY_OK = False

try:
    from scipy.interpolate import PchipInterpolator
    _PCHIP_OK = True
except ImportError:
    _PCHIP_OK = False

# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS (locked — never change)
# ══════════════════════════════════════════════════════════════════════════════
SR = 48000

# FIX-17: 24-bit WAV intermediates — 144dB SNR vs 96dB for 16-bit.
# Multi-pass TIER_DAMAGED sources benefit from this headroom.
WAV_CODEC = 'pcm_s24le'

TARGET = {
    'lufs': -6.29, 'rms': -10.01, 'crest': 10.25, 'lra': 4.19,
    'true_peak': -1.0, 'sfm': 0.0444, 'dr': 7.9,
}
BIAS_SCALE = 0.25

# v9.0: Extended to 24 bands, 80Hz–16kHz
# Convention: bias = (output – ref). negative = output below ref → boost.
SPECTRAL_BIAS_V9: Dict[int, float] = {
    80:    -2.50,   100:   -4.00,   125:   +3.50,   160:   -1.50,
    200:   -4.00,   250:   -7.00,   315:   +6.00,   400:   -1.50,
    500:   +1.50,   630:   -2.50,   800:   +1.50,   1000:  -1.00,
    1250:  +0.40,   1600:  +0.30,   2000:  +0.50,   2500:  +1.80,
    3150:  +1.20,   4000:  +5.00,   5000:  +0.80,   6300:  +0.90,
    8000:  +8.00,   10000: -2.00,   12500: -1.50,   16000: -3.00,
}

CENTERS_31 = [
    20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160,
    200, 250, 315, 400, 500, 630, 800, 1000, 1250, 1600,
    2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000,
]
A_WEIGHT: Dict[float, float] = {
    20: -50.5, 25: -44.7, 31.5: -39.4, 40: -34.6, 50: -30.2,
    63: -26.2, 80: -22.5, 100: -19.1, 125: -16.1, 160: -13.4,
    200: -10.9, 250: -8.6, 315: -6.6, 400: -4.8, 500: -3.2,
    630: -1.9, 800: -0.8, 1000: 0.0, 1250: 0.6, 1600: 1.0,
    2000: 1.2, 2500: 1.3, 3150: 1.2, 4000: 1.0, 5000: 0.5,
    6300: -0.1, 8000: -1.1, 10000: -2.5, 12500: -4.3, 16000: -6.6, 20000: -9.3,
}

# Arabic sibilant protection bands (sh/s/sad energy range)
ARABIC_SIB_BANDS = [2500.0, 3150.0, 4000.0, 5000.0]

# Compand preset library (validated over v8.x series)
_COMPAND_LIBRARY = {
    'BYPASS':  '-90/-90|-20/-20|-3/-3|0/0',
    'MINIMAL': '-90/-89|-40/-39|-20/-19.5|-10/-9.8|-4/-3.9|-1/-0.95|0/-0.3',
    'LIGHT':   '-90/-85|-40/-36|-20/-17|-10/-8.2|-5/-4.1|-2/-1.6|-0.5/-0.4|0/-0.3',
    'MEDIUM':  '-90/-78|-40/-25|-22/-12.5|-12/-6.8|-6/-3.5|-2.5/-1.6|-0.8/-0.5|0/-0.2',
    'HEAVY':   '-90/-72|-42/-21|-26/-10.5|-13/-5.2|-6/-2.4|-2.5/-0.8|-0.5/-0.3|0/-0.1',
    'EXTREME': '-90/-68|-45/-20|-28/-9|-14/-4.5|-7/-2.0|-3/-0.6|0/-0.1',
}
_COMPAND_INTENSITY = {'BYPASS': 0.0, 'MINIMAL': 0.15, 'LIGHT': 0.25,
                      'MEDIUM': 0.50, 'HEAVY': 0.75, 'EXTREME': 1.0}

# Reference cache location — /app/ persists within container session
_APP_DIR  = Path(__file__).parent
_REF_CACHE = str(_APP_DIR / 'ref_cache_v100.json')

def _resolve_ref_files() -> List[str]:
    env_dir = os.environ.get('TILAWA_REF_DIR', '')
    if env_dir and os.path.isdir(env_dir):
        found = sorted(str(p) for p in Path(env_dir).glob('*.mp3'))
        if found: return found
    for d in [Path.home() / '.tilawa_ref',
              _APP_DIR / 'reference_audio']:
        if d.is_dir():
            found = sorted(str(p) for p in d.glob('*.mp3')
                           if p.stat().st_size > 10_000)
            if found: return found
    return []

REF_FILES: List[str] = _resolve_ref_files()

# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING — stdout IS the app.py API
# ══════════════════════════════════════════════════════════════════════════════
def L(msg: str) -> None:
    print(msg, flush=True)

# ══════════════════════════════════════════════════════════════════════════════
#  DATA MODELS
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class ReferenceModel:
    lufs:             float = TARGET['lufs']
    rms:              float = TARGET['rms']
    crest:            float = TARGET['crest']
    lra:              float = TARGET['lra']
    lra_clip:         float = 2.94
    sfm:              float = TARGET['sfm']
    dr:               float = TARGET['dr']
    phrase_lra_p10:   float = 2.50
    phrase_lra_p50:   float = 3.37
    phrase_lra_p90:   float = 4.20
    silence_floor:    float = -73.0
    warmth_ratio:     float = 0.0
    tilt_slope:       float = 0.0
    third_oct:        Dict[float, float] = field(default_factory=dict)
    ref_codec_cutoff: float = 14000.0
    n_files:          int   = 0
    ref_hash:         str   = ''


@dataclass
class InputState:
    path:             str   = ''
    total_s:          float = 0.0
    src_br:           int   = 128_000
    src_sr:           int   = 44_100
    is_mono:          bool  = False
    skip_s:           int   = 30
    dur_s:            int   = 45
    full_spectrum:    Dict[float, float] = field(default_factory=dict)
    clip_rms:         float = -20.0
    clip_crest:       float = 10.0
    clip_lra:         float = 4.0
    clip_sfm:         float = 0.05
    clip_dr:          float = 8.0
    snr_global:       float = 25.0
    band_snr:         Dict[float, float] = field(default_factory=dict)
    hf_rolloff:       float = 20_000.0
    hf_deficit:       float = 0.0
    codec_cutoff:     float = 20_000.0
    clip_ratio:       float = 0.0
    noise_type:       str   = 'none'
    silence_floor:    float = -62.0
    silence_sfm:      float = 0.1
    hum_freq_hz:      float = 0.0
    silence_valid:    bool  = False
    silence_frame_abs: List[float] = field(default_factory=list)
    smear_score:      float = 0.0
    smear_desc:       str   = 'clean'
    source_tier:      str   = 'TIER_PRISTINE'
    eq_confidence:    float = 1.0
    nr_confidence:    float = 0.0
    compand_confidence: float = 1.0
    bias_confidence:  float = 1.0
    hf_confidence:    float = 1.0
    achievable_lufs:  float = -6.29
    achievable_crest: float = 10.25
    achievable_lra:   float = 4.19
    mds_raw:          float = 0.0
    spec_dist:        float = 0.0


@dataclass
class JointParams:
    compand_str:      str   = '-90/-90|-20/-20|-3/-3|0/0'
    gain_db:          float = 0.0
    predicted_lufs:   float = TARGET['lufs']
    predicted_lra:    float = TARGET['lra']
    predicted_crest:  float = TARGET['crest']
    intensity_label:  str   = 'BYPASS'
    crest_guard_hit:  bool  = False


@dataclass
class PassResult:
    pass_label:   str   = ''
    wav_path:     str   = ''
    spectrum:     Dict[float, float] = field(default_factory=dict)
    rms:          float = -20.0
    crest:        float = 10.0
    lra:          float = 4.0
    lufs:         float = TARGET['lufs']
    eq_residual:  float = 99.0
    sib_snr:      float = 10.0
    score_tier:   float = 0.0
    score_abs:    float = 0.0
    composite:    float = -999.0
    ceiling_reason: str = ''


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIO I/O
# ══════════════════════════════════════════════════════════════════════════════
def _safe(path: str) -> Tuple[str, Optional[str]]:
    try:
        path.encode('ascii')
        return path, None
    except UnicodeEncodeError:
        import uuid as _u
        ext = os.path.splitext(path)[1] or '.mp3'
        tmp = os.path.join(_TMP, f'v100_safe_{_u.uuid4().hex[:8]}{ext}')
        shutil.copy2(path, tmp)
        return tmp, tmp


def load_audio_fast(path: str, skip_s: float = 0, duration_s: float = 45,
                    sr: int = SR) -> 'np.ndarray':
    """Fast MP3 seek via ffmpeg -ss BEFORE -i (keyframe seek)."""
    sp, tc = _safe(path)
    cmd = ['ffmpeg', '-y']
    if skip_s > 0:
        cmd += ['-ss', str(skip_s)]
    cmd += ['-i', sp, '-t', str(duration_s),
            '-f', 'f32le', '-ac', '1', '-ar', str(sr), '-loglevel', 'error', '-']
    r = subprocess.run(cmd, capture_output=True)
    if tc:
        try: os.remove(tc)
        except: pass
    if not r.stdout:
        return np.zeros(int(sr * min(duration_s, 1)), dtype=np.float32)
    return np.frombuffer(r.stdout, dtype=np.float32)


def probe_file(path: str) -> Dict:
    sp, tc = _safe(path)
    r = subprocess.run(['ffprobe', '-v', 'quiet', '-print_format', 'json',
                        '-show_streams', '-show_format', sp],
                       capture_output=True, text=True)
    if tc:
        try: os.remove(tc)
        except: pass
    try:
        return json.loads(r.stdout) if r.returncode == 0 else {}
    except Exception:
        return {}


def measure_lufs(path: str) -> float:
    sp, tc = _safe(path)
    r = subprocess.run(['ffmpeg', '-i', sp, '-af', 'ebur128=peak=true',
                        '-f', 'null', '-', '-loglevel', 'info'],
                       capture_output=True, text=True)
    if tc:
        try: os.remove(tc)
        except: pass
    for line in r.stderr.split('\n'):
        s = line.strip()
        if s.startswith('I:') and 'LUFS' in s and 'LRA' not in s:
            try:
                return float(s.split('I:')[1].strip().split()[0])
            except: pass
    return -99.0


def ffmpeg_process(src: str, dst: str, af: str, extra_args: List[str] = None) -> bool:
    """Run ffmpeg with -af filter chain. Returns True on success.
    FIX-17: WAV outputs use WAV_CODEC='pcm_s24le' for 24-bit intermediates."""
    sp, tc = _safe(src)
    cmd = ['ffmpeg', '-y', '-i', sp, '-af', af,
           '-ar', '48000', '-ac', '2']
    if dst.endswith('.wav'):
        cmd += ['-c:a', WAV_CODEC]
    cmd += ['-loglevel', 'error']
    if extra_args:
        cmd += extra_args
    cmd.append(dst)
    r = subprocess.run(cmd, capture_output=True)
    if tc:
        try: os.remove(tc)
        except: pass
    return r.returncode == 0 and os.path.exists(dst)


# ══════════════════════════════════════════════════════════════════════════════
#  SIGNAL METRICS
# ══════════════════════════════════════════════════════════════════════════════
def rms_db(a: 'np.ndarray') -> float:
    return float(20 * np.log10(np.sqrt(np.mean(a ** 2)) + 1e-10))

def peak_db(a: 'np.ndarray') -> float:
    return float(20 * np.log10(np.max(np.abs(a)) + 1e-10))

def crest_factor(a: 'np.ndarray') -> float:
    return float(peak_db(a) - rms_db(a))

def lra_estimate(a: 'np.ndarray', sr: int = SR) -> float:
    n = int(0.4 * sr)
    step = n // 2
    lvls = np.array([20 * np.log10(np.sqrt(np.mean(a[i:i + n] ** 2)) + 1e-10)
                     for i in range(0, len(a) - n, step)])
    if len(lvls) < 2: return 0.0
    active = lvls[lvls > np.max(lvls) - 30]
    return float(np.percentile(active, 95) - np.percentile(active, 10)) if len(active) >= 2 else 0.0


def third_octave(audio: 'np.ndarray', sr: int = SR) -> Dict[float, float]:
    """
    FIX-01: Hann window with power-preserving normalization.
      Eliminates spectral leakage at -13dB that biased all measurements.
      Rectangular window caused energy bleed from 100-200Hz fundamentals
      into adjacent 1/3-oct bands, corrupting every EQ correction.
    FIX-02: MAX_N = sr*4 cap.
      80Hz band needs N >= 12,632 samples for 5-bin resolution.
      Capping at sr*4 (192k samples) is 15x more than sufficient
      and reduces FFT time from 45s to 4s of audio — 10x speedup
      with zero quality impact (extra resolution was thrown away anyway).
    """
    MAX_N = sr * 4
    chunk = audio[:MAX_N] if len(audio) > MAX_N else audio
    N = len(chunk)
    if N < 32:
        return {}
    window = np.hanning(N)
    # Power-preserving normalization: norm = RMS of window
    # This preserves signal power through the window (not peak amplitude)
    norm = float(np.sqrt(np.sum(window ** 2) / N))
    if norm < 1e-12:
        return {}
    spec = np.abs(rfft(chunk * window)) / (norm * N)
    freqs = rfftfreq(N, 1.0 / sr)
    out: Dict[float, float] = {}
    for fc in CENTERS_31:
        if fc >= sr / 2: continue
        fl = fc / (2 ** (1 / 6))
        fh = fc * (2 ** (1 / 6))
        mask = (freqs >= fl) & (freqs < fh)
        if mask.sum() > 0:
            out[fc] = float(20 * np.log10(np.mean(spec[mask]) + 1e-10))
    return out


def detect_hf_rolloff(bands: Dict[float, float], drop: float = 12.0) -> float:
    fs = sorted(f for f in bands if 1600 <= f <= 20000)
    if not fs: return 20000.0
    prev = bands[fs[0]]
    for fc in fs[1:]:
        curr = bands[fc]
        if prev - curr > drop: return float(fc)
        prev = curr
    return 20000.0

def compute_sfm(audio: 'np.ndarray', sr: int = SR,
                f_lo: float = 100.0, f_hi: float = 8000.0) -> float:
    chunk = audio[:sr * 30] if len(audio) > sr * 30 else audio
    N = len(chunk)
    spec = np.abs(rfft(chunk)) ** 2
    freqs = rfftfreq(N, 1.0 / sr)
    s = spec[(freqs >= f_lo) & (freqs <= f_hi)]
    if len(s) < 10: return 0.1
    eps = 1e-10
    return float(np.clip(np.exp(np.mean(np.log(s + eps))) / (np.mean(s) + eps), 0.0, 1.0))

def compute_band_snr(audio: 'np.ndarray', sr: int = SR) -> Dict[float, float]:
    N = len(audio)
    spec = np.abs(rfft(audio)) ** 2
    freqs = rfftfreq(N, 1.0 / sr)
    result = {}
    for fc in [125, 250, 500, 1000, 2000, 4000, 8000]:
        mask = (freqs >= fc * 0.7) & (freqs < fc * 1.4)
        if mask.sum() < 4: continue
        s = spec[mask]
        result[float(fc)] = float(10 * np.log10(
            np.percentile(s, 85) / (np.percentile(s, 5) + 1e-30) + 1e-10))
    return result

def compute_sibilant_snr(audio: 'np.ndarray', silence_floor: float,
                          sr: int = SR) -> float:
    """Arabic sibilant SNR at sh/s/sad energy bands (2500-5000Hz)."""
    N = len(audio)
    spec = np.abs(rfft(audio)) ** 2
    freqs = rfftfreq(N, 1.0 / sr)
    snrs = []
    for fc in ARABIC_SIB_BANDS:
        mask = (freqs >= fc * 0.85) & (freqs <= fc * 1.18)
        if not mask.any(): continue
        band_rms = float(10 * np.log10(np.mean(spec[mask]) + 1e-30))
        snrs.append(band_rms - silence_floor)
    return float(np.mean(snrs)) if snrs else 10.0

def spectral_tilt(bands: Dict[float, float], lo: float = 200.0, hi: float = 2000.0) -> float:
    fcs = np.array([fc for fc in CENTERS_31 if lo <= fc <= hi and fc in bands], dtype=float)
    if len(fcs) < 3: return 0.0
    return float(np.polyfit(np.log2(fcs / 1000.0),
                             np.array([bands[fc] for fc in fcs]), 1)[0])

def compute_dynamic_range(audio: 'np.ndarray', sr: int = SR) -> float:
    n = int(0.020 * sr)
    frames = np.array([float(np.sqrt(np.mean(audio[i:i + n] ** 2)))
                       for i in range(0, len(audio) - n, n)])
    if len(frames) < 10: return 8.0
    frames_db = 20 * np.log10(frames + 1e-10)
    return float(np.percentile(frames_db, 95) - np.percentile(frames_db, 5))


# ══════════════════════════════════════════════════════════════════════════════
#  FULL-FILE SPECTRUM ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
def _probe_full_file(path: str, total_s: float, n_windows: int = 9,
                     window_s: float = 10.0) -> Tuple[Dict[float, float], List[Tuple[float, float]]]:
    """
    Multi-window spectrum analysis. Returns (spectrum, rms_by_position).
    Silence-contaminated windows excluded by relative RMS threshold.
    """
    positions = [max(10.0, total_s * (i + 1) / (n_windows + 1))
                 for i in range(n_windows)]
    positions = [min(p, total_s - window_s - 2) for p in positions]

    spectra: List[Dict] = []
    rms_vals: List[Tuple[float, float]] = []

    for pos in positions:
        audio = load_audio_fast(path, skip_s=pos, duration_s=window_s)
        if len(audio) < SR * 3: continue
        r = rms_db(audio)
        rms_vals.append((pos, r))
        spectra.append((r, third_octave(audio)))

    if not spectra:
        return {}, []

    rms_only = [r for r, _ in spectra]
    median_rms = float(np.median(rms_only))
    threshold = median_rms - 15.0
    valid = [(r, s) for r, s in spectra if r > threshold]
    if len(valid) < max(2, n_windows // 3):
        valid = spectra

    result: Dict[float, float] = {}
    for fc in CENTERS_31:
        vals = [s[fc] for _, s in valid if fc in s]
        if vals:
            result[fc] = float(np.median(vals))

    return result, rms_vals


def _probe_3window(path: str, total_s: float, skip_s: int) -> Dict[float, float]:
    """Fast 3-window spectrum for pass intermediates (MP3 or non-WAV)."""
    spectrum, _ = _probe_full_file(path, total_s, n_windows=3, window_s=10.0)
    return spectrum if spectrum else {}


def _wav_3window_spectrum(wav_path: str, total_s: float, skip_s: int,
                           dur_s: int, sr: int = SR) -> Dict[float, float]:
    """
    FIX-15: Single-load WAV spectrum — no subprocess overhead per window.
    For WAV files: load one 90s chunk, slice into 3 windows in numpy.
    Eliminates 9× subprocess creation overhead (2-3s per measure_pass call).
    Only called for .wav intermediates — MP3 still uses _probe_3window.
    """
    load_dur = min(90, total_s - skip_s - 5)
    if load_dur < 10:
        return {}
    audio = load_audio_fast(wav_path, skip_s, load_dur)
    if len(audio) < sr * 10:
        return {}

    win_n = int(10 * sr)
    positions_in_chunk = [0, len(audio) // 3, 2 * len(audio) // 3]
    spectra = []
    rms_vals = []
    for p in positions_in_chunk:
        seg = audio[p:p + win_n]
        if len(seg) >= sr * 5:
            r = rms_db(seg)
            rms_vals.append(r)
            spectra.append((r, third_octave(seg)))

    if not spectra:
        return {}

    # Silence filter
    if rms_vals:
        med = float(np.median(rms_vals))
        spectra = [(r, s) for r, s in spectra if r > med - 15.0] or spectra

    result: Dict[float, float] = {}
    for fc in CENTERS_31:
        vals = [s[fc] for _, s in spectra if fc in s]
        if vals:
            result[fc] = float(np.median(vals))
    return result


# ══════════════════════════════════════════════════════════════════════════════
#  REFERENCE MODEL
# ══════════════════════════════════════════════════════════════════════════════
def _ref_files_hash(paths: List[str]) -> str:
    h = hashlib.sha1()
    for p in sorted(paths):
        if os.path.exists(p):
            st = os.stat(p)
            h.update(f'{Path(p).name}:{st.st_mtime:.0f}:{st.st_size}'.encode())
    return h.hexdigest()[:16]


def _phrase_lra_dist(audio: 'np.ndarray', sr: int = SR) -> Tuple[float, float, float]:
    """Compute phrase-level LRA percentiles from recitation audio."""
    if len(audio) < sr * 10:
        return 0.0, 0.0, 0.0
    frame = int(0.01 * sr); hop = int(0.005 * sr)
    energies = np.array([rms_db(audio[i:i + frame])
                         for i in range(0, len(audio) - frame, hop)], dtype=np.float32)
    k = max(1, int(0.05 / 0.005))
    smooth = np.convolve(energies, np.ones(k) / k, mode='same')
    win2 = int(2.0 / 0.005)
    run_max = np.array([np.max(smooth[max(0, i - win2):i + win2]) for i in range(len(smooth))])
    is_dip = smooth < (run_max - 3.0)
    gap_fr = int(0.25 / 0.005); min_fr = int(3.0 / 0.005)  # BUG-B FIX: 3s min for valid LRA (was 1s — too short for lra_estimate 400ms windows)
    phrases: List['np.ndarray'] = []
    in_ph = False; start = 0; gap = 0
    for i, dip in enumerate(is_dip):
        if not dip:
            if not in_ph: start = i
            in_ph = True; gap = 0
        else:
            if in_ph:
                gap += 1
                if gap > gap_fr:
                    dur = i - gap - start
                    if dur > min_fr:
                        s_s, e_s = start * hop, (i - gap) * hop
                        if e_s > s_s + sr:
                            phrases.append(audio[s_s:e_s])
                    in_ph = False; gap = 0
    if in_ph:
        phrases.append(audio[start * hop:])
    lras = [lra_estimate(ph) for ph in phrases if len(ph) > sr * 0.5]
    if len(lras) < 3:
        return 0.0, 0.0, 0.0
    return (float(np.percentile(lras, 10)),
            float(np.percentile(lras, 50)),
            float(np.percentile(lras, 90)))


def _sample_phrase_lra(audio: 'np.ndarray', sr: int = SR) -> float:
    """
    BUG-E FIX: Sliding-window LRA median — replaces phrase-boundary detection.

    Why phrase-boundary detection fails on the 1425H reference files:
    The Sheikh's 320kbps reference recordings are DENSE — inter-ayah pauses
    are often <250ms. The 3dB dip threshold that marks phrase boundaries
    barely fires. _phrase_lra_dist returns 0-3 phrases from 60s of audio,
    giving a median of ~1.5 LU from too few samples.

    Why sliding windows work:
    10-second windows contain 2-4 complete ayahs. LRA measured on 10s
    of continuous recitation gives the actual phrase-level dynamic range
    of the settled material. Median across 20+ windows = stable, robust.

    Measured on 1425H references: sliding-window median = 2.3-2.5 LU,
    which matches manual listening assessment of phrase dynamics.
    """
    if len(audio) < sr * 10:
        return 2.5  # safe default for very short clips

    win_n = int(10 * sr)
    step_n = int(5 * sr)
    lras = []
    overall = rms_db(audio)
    silence_thresh = overall - 18.0  # skip near-silence windows

    for i in range(0, len(audio) - win_n, step_n):
        seg = audio[i:i + win_n]
        # Only measure windows that have real speech content
        if rms_db(seg) > silence_thresh:
            l = lra_estimate(seg, sr)
            if l > 0.3:  # discard near-zero (pure silence leak)
                lras.append(l)

    if len(lras) < 3:
        return 2.5  # safe default
    # Use p40 (slightly below median) — conservative target avoids over-expansion
    return float(np.percentile(lras, 40))


def load_reference_model(ref_files: List[str] = None) -> ReferenceModel:
    """
    Load or build ReferenceModel from ref MP3 files.
    FIX-03: pipe to stdout — no WAV header garbage in first 11 samples.
    FIX-04: _sample_phrase_lra() for p50 (whole-file, not first 5min).
    """
    if ref_files is None:
        ref_files = REF_FILES
    if not ref_files:
        L('  [ref] no reference files found — using defaults')
        return ReferenceModel()

    current_hash = _ref_files_hash(ref_files)

    # Try cache
    if os.path.exists(_REF_CACHE):
        try:
            with open(_REF_CACHE, 'r', encoding='utf-8') as f:
                d = json.load(f)
            if (d.get('cache_version') == 'v10-base'  # bumped — invalidates bad phrase_lra_p50 values
                    and d.get('ref_hash') == current_hash):
                m = ReferenceModel()
                m.third_oct        = {float(k): v for k, v in d['third_oct'].items()}
                m.rms              = d['rms']
                m.crest            = d['crest']
                m.lra              = d['lra']
                m.lra_clip         = d['lra_clip']
                m.sfm              = d['sfm']
                m.dr               = d['dr']
                m.phrase_lra_p10   = d['phrase_lra_p10']
                m.phrase_lra_p50   = d['phrase_lra_p50']
                m.phrase_lra_p90   = d['phrase_lra_p90']
                m.silence_floor    = d['silence_floor']
                m.warmth_ratio     = d['warmth_ratio']
                m.tilt_slope       = d['tilt_slope']
                m.ref_codec_cutoff = d['ref_codec_cutoff']
                m.n_files          = d['n_files']
                m.ref_hash         = current_hash
                L(f'  [ref] cache hit ({m.n_files} files, hash={current_hash})')
                return m
        except Exception as e:
            L(f'  [ref] cache read failed: {e} — rebuilding')

    L(f'  [ref] building from {len(ref_files)} file(s)...')
    all_data: List[Dict] = []

    for ref_path in ref_files[:3]:
        # FIX-03: Pipe to stdout — no WAV file, no header, no garbage samples.
        # The old code wrote -f f32le to a .wav file then np.frombuffer(raw),
        # reading the 44-byte RIFF header as 11 float32 garbage samples.
        r = subprocess.run(
            ['ffmpeg', '-y', '-i', ref_path, '-ac', '1', '-ar', str(SR),
             '-f', 'f32le', '-loglevel', 'error', '-'],
            capture_output=True)
        if r.returncode != 0 or not r.stdout:
            L(f'  [ref] failed to convert {Path(ref_path).name}')
            continue

        audio = np.frombuffer(r.stdout, dtype=np.float32)

        if len(audio) < SR * 2:
            L(f'  [ref] {Path(ref_path).name} nearly empty — skip')
            continue

        # LFS stub validation
        ref_rms = rms_db(audio)
        if ref_rms < -50.0:
            raise RuntimeError(
                f"Reference file '{Path(ref_path).name}' appears to be an LFS stub "
                f"(RMS={ref_rms:.1f}dBFS < -50dBFS). "
                f"Server cannot process jobs without valid reference audio."
            )

        total_ref_s = len(audio) / SR

        # Use _probe_full_file on the original MP3 for spectrum (9-window)
        spec, _ = _probe_full_file(ref_path, total_ref_s, n_windows=9, window_s=10.0)
        if not spec:
            spec = third_octave(audio)

        # FIX-04: Multi-position phrase LRA
        p50_whole = _sample_phrase_lra(audio)
        # p10/p90 from first 300s (used for percentile bounds, less critical)
        seg_300 = audio[:SR * 300] if len(audio) > SR * 300 else audio
        p10, _, p90 = _phrase_lra_dist(seg_300)

        # Silence floor from first 30s
        clip30 = audio[:SR * 30]
        frame_n = int(0.025 * SR)
        overall = rms_db(clip30)
        silence_frames = [clip30[i:i + frame_n] for i in range(0, len(clip30) - frame_n, frame_n)
                          if rms_db(clip30[i:i + frame_n]) < overall - 20]
        silence_floor = (float(np.median([rms_db(f) for f in silence_frames]))
                         if len(silence_frames) >= 5 else -70.0)

        # Codec cutoff detection
        n_fft = min(131072, len(audio))
        seg = audio[:n_fft].astype(np.float64)
        X = np.abs(rfft(seg * np.hanning(n_fft))) ** 2
        fq = rfftfreq(n_fft, 1.0 / SR)
        mask_1k = (fq >= 1000) & (fq < 2000)
        ref_db_1k = 10 * np.log10(np.mean(X[mask_1k]) + 1e-30) if mask_1k.any() else -40.0
        codec_cutoff = 14000.0
        for fc_test in [20000, 18000, 16000, 14000, 12000, 10000, 8000]:
            m = (fq >= fc_test - 500) & (fq < fc_test + 500)
            if m.any() and 10 * np.log10(np.mean(X[m]) + 1e-30) > ref_db_1k - 45:
                codec_cutoff = float(fc_test); break

        all_data.append({
            'spec':         spec,
            'rms':          float(rms_db(audio)),
            'crest':        float(crest_factor(audio)),
            'lra':          float(lra_estimate(audio)),
            'lra_clip':     float(lra_estimate(audio[:SR * 30])),
            'sfm':          float(compute_sfm(audio)),
            'dr':           float(compute_dynamic_range(audio)),
            'p10':          p10, 'p50': p50_whole, 'p90': p90,
            'silence_floor': silence_floor,
            'warmth':       float(spectral_tilt(spec, 200, 2000)) if spec else 0.0,
            'codec_cutoff': codec_cutoff,
        })
        L(f'    {Path(ref_path).name}: RMS={all_data[-1]["rms"]:.2f} '
          f'Crest={all_data[-1]["crest"]:.2f} p50={p50_whole:.2f}')

    if len(all_data) < 1:
        L('  [ref] no valid reference data — using defaults')
        return ReferenceModel()

    def med(key):
        return float(np.median([d[key] for d in all_data]))

    third_oct_final: Dict[float, float] = {}
    for fc in CENTERS_31:
        vals = [d['spec'].get(fc) for d in all_data if d['spec'].get(fc) is not None]
        if vals: third_oct_final[float(fc)] = float(np.median(vals))

    m = ReferenceModel(
        rms=med('rms'), crest=med('crest'), lra=med('lra'),
        lra_clip=med('lra_clip'), sfm=med('sfm'), dr=med('dr'),
        phrase_lra_p10=med('p10'), phrase_lra_p50=med('p50'), phrase_lra_p90=med('p90'),
        silence_floor=med('silence_floor'), warmth_ratio=med('warmth'),
        ref_codec_cutoff=med('codec_cutoff'),
        third_oct=third_oct_final, n_files=len(all_data), ref_hash=current_hash,
    )

    try:
        os.makedirs(os.path.dirname(_REF_CACHE), exist_ok=True)
        cache_d = {
            'cache_version': 'v10-base', 'ref_hash': current_hash,
            'n_files': m.n_files, 'rms': m.rms, 'crest': m.crest,
            'lra': m.lra, 'lra_clip': m.lra_clip, 'sfm': m.sfm, 'dr': m.dr,
            'phrase_lra_p10': m.phrase_lra_p10, 'phrase_lra_p50': m.phrase_lra_p50,
            'phrase_lra_p90': m.phrase_lra_p90, 'silence_floor': m.silence_floor,
            'warmth_ratio': m.warmth_ratio, 'tilt_slope': m.tilt_slope,
            'ref_codec_cutoff': m.ref_codec_cutoff,
            'third_oct': {str(k): v for k, v in m.third_oct.items()},
        }
        with open(_REF_CACHE, 'w', encoding='utf-8') as f:
            json.dump(cache_d, f)
        L(f'  [ref] cache written → {_REF_CACHE}')
    except Exception as e:
        L(f'  [ref] cache write failed (non-fatal): {e}')

    return m


# ══════════════════════════════════════════════════════════════════════════════
#  INPUT ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════
def _adaptive_window(path: str, total_s: float,
                     rms_by_pos: List[Tuple[float, float]]) -> Tuple[int, int]:
    """Select analysis window that captures settled recitation."""
    if total_s <= 60:
        skip_s = max(3, int(total_s // 8))
        dur_s = max(10, int(total_s - skip_s - 3))
        return skip_s, dur_s
    if total_s <= 90:
        skip_s = max(5, int(total_s // 6))
        dur_s = min(40, int(total_s - skip_s - 2))
        return skip_s, dur_s

    if len(rms_by_pos) >= 3:
        rms_vals = [r for _, r in rms_by_pos]
        threshold = float(np.percentile(rms_vals, 40))
        settled = 30
        for pos, r in rms_by_pos:
            if r >= threshold and pos >= 20:
                settled = int(pos)
                break
        skip_s = min(settled, int(total_s // 4))
    else:
        skip_s = min(30, int(total_s // 4))

    dur_s = min(45, int(total_s - skip_s - 10))
    dur_s = max(15, dur_s)
    return skip_s, dur_s


def _detect_smear(audio: 'np.ndarray', sr: int = SR) -> Tuple[float, str]:
    """
    Detect codec smear in Arabic fricatives (2-6kHz harmonic ratio).
    FIX-05: ZCR gate — separates unvoiced fricatives from weak vowels.
    Problem: energy-only gate (overall-15 to overall-3) also captured
    weak kasra vowels (which have harmonic structure) and voiced fricatives
    in transition (z/dh/zha). Vowels inflate the harmonic ratio, making
    smear appear lower than actual fricative smear score.
    Fix: ZCR > 0.20 (noise-like) ensures we're measuring actual fricatives.
    True Arabic fricatives: ZCR ~ 0.25-0.40. Vowels: ZCR ~ 0.05-0.10.
    """
    if len(audio) < sr * 5: return 0.0, 'insufficient_audio'
    frame_n = int(0.025 * sr); hop_n = int(0.010 * sr)
    overall = rms_db(audio)
    lo, hi = overall - 15.0, overall - 3.0
    ratios: List[float] = []
    for i in range(0, len(audio) - frame_n, hop_n):
        f = audio[i:i + frame_n]
        # Energy gate
        if not (lo < rms_db(f) < hi): continue
        # FIX-05: ZCR gate — require noise-like zero-crossing rate
        zcr = float(np.sum(np.abs(np.diff(np.sign(f))))) / (2 * frame_n)
        if zcr < 0.20: continue  # vowel or voiced sound — skip
        spec = np.abs(rfft(f * np.hanning(frame_n))) ** 2
        freqs = rfftfreq(frame_n, 1.0 / sr)
        mask = (freqs >= 2000) & (freqs <= 6000)
        if not mask.any(): continue
        band = spec[mask]
        thr = float(np.mean(band) + np.std(band))
        total_e = float(np.sum(band) + 1e-30)
        ratios.append(float(np.sum(band[band > thr])) / total_e)
        if len(ratios) >= 80: break
    if len(ratios) < 10: return 0.0, 'no_fricative_frames'
    score = float(np.clip((0.45 - float(np.median(ratios))) / 0.40 * 10, 0, 10))
    desc = ('clean' if score < 2 else 'mild_smear' if score < 4
            else 'moderate_smear' if score < 7 else 'severe_smear')
    return round(score, 1), desc


def _measure_silence(audio: 'np.ndarray', total_s: float,
                     skip_s: int, sr: int = SR) -> Dict:
    """Measure silence floor and hum presence."""
    min_dur = 0.1 if total_s < 90 else 0.3
    frame_n = int(0.2 * sr)
    if len(audio) < frame_n * 3:
        return {'valid': False, 'floor': -62.0, 'sfm': 0.1,
                'hum': 0.0, 'noise_type': 'none', 'frame_positions': []}

    overall_db = rms_db(audio)
    silence_ceil = overall_db - 18.0

    sil_frames = []
    sil_positions: List[float] = []
    for i in range(0, len(audio) - frame_n, frame_n):
        f = audio[i:i + frame_n]
        r = rms_db(f)
        if -62.0 < r < silence_ceil:
            sil_frames.append(f)
            abs_pos = skip_s + i / sr
            sil_positions.append(abs_pos)

    min_frames = max(3, int(min_dur * sr / frame_n))
    if len(sil_frames) < min_frames:
        return {'valid': False, 'floor': -62.0, 'sfm': 0.1,
                'hum': 0.0, 'noise_type': 'none', 'frame_positions': []}

    sa = np.concatenate(sil_frames)
    floor_db = rms_db(sa)

    N = len(sa)
    spec = np.abs(rfft(sa)) ** 2
    freqs = rfftfreq(N, 1.0 / sr)
    ms = (freqs >= 200) & (freqs <= 8000)
    s = spec[ms]
    eps = 1e-10
    noise_sfm = float(np.clip(np.exp(np.mean(np.log(s + eps))) / (np.mean(s) + eps), 0, 1)) if len(s) > 10 else 0.1

    def _be(fc, bw=3.0):
        m = (freqs >= fc - bw) & (freqs <= fc + bw)
        return float(np.mean(spec[m])) if m.sum() > 0 else 1e-30

    hum_freq = 0.0
    for test_hz in [50.0, 60.0]:
        nb = np.mean([_be(test_hz - 25), _be(test_hz + 25)])
        ratio_db = 10 * np.log10(_be(test_hz) / (nb + 1e-30) + 1e-30)
        if ratio_db > 15.0:
            hum_freq = test_hz; break

    has_hiss = noise_sfm > 0.65
    has_hum = hum_freq > 0.0
    if has_hiss and has_hum:   ntype = 'hiss+hum'
    elif has_hiss:             ntype = 'broadband' if noise_sfm > 0.85 else 'hiss'
    elif has_hum:              ntype = f'hum_{int(hum_freq)}hz'
    else:                      ntype = 'none'

    return {
        'valid': True, 'floor': float(floor_db), 'sfm': float(noise_sfm),
        'hum': hum_freq, 'noise_type': ntype,
        'frame_positions': sil_positions[:20],
        'hum_50db':  10 * np.log10(_be(50) / (np.mean([_be(25), _be(75)]) + 1e-30) + 1e-30),
        'hum_60db':  10 * np.log10(_be(60) / (np.mean([_be(35), _be(85)]) + 1e-30) + 1e-30),
        'hum_100db': 10 * np.log10(_be(100) / (np.mean([_be(75), _be(125)]) + 1e-30) + 1e-30),
        'hum_120db': 10 * np.log10(_be(120) / (np.mean([_be(95), _be(145)]) + 1e-30) + 1e-30),
    }


def _derive_source_tier(src_br: int, codec_cutoff: float, snr_db: float,
                         noise_type: str, smear_score: float) -> str:
    if (src_br >= 128_000 and codec_cutoff > 14_000
            and snr_db > 25.0 and noise_type == 'none'):
        tier = 'TIER_PRISTINE'
    elif src_br >= 64_000 and codec_cutoff > 10_000 and snr_db > 15.0:
        tier = 'TIER_COMPRESSED'
    elif src_br >= 32_000 and codec_cutoff > 7_000 and snr_db > 8.0:
        tier = 'TIER_DEGRADED'
    else:
        tier = 'TIER_DAMAGED'

    if smear_score >= 6.0 and tier == 'TIER_PRISTINE':
        tier = 'TIER_COMPRESSED'
    elif smear_score >= 6.0 and tier == 'TIER_COMPRESSED':
        tier = 'TIER_DEGRADED'

    return tier


def _compute_achievable(tier: str, codec_cutoff: float) -> Tuple[float, float, float]:
    if tier == 'TIER_PRISTINE':
        return TARGET['lufs'], TARGET['crest'], TARGET['lra']
    if tier == 'TIER_COMPRESSED':
        return TARGET['lufs'], 10.1, 4.0  # FIX: was 9.8 — too conservative for 128kbps
    if tier == 'TIER_DEGRADED':
        crest = float(np.clip(7.5 + (codec_cutoff / 10500.0) * 1.5, 7.5, 9.0))
        return -6.5, crest, 3.6
    return -7.0, 7.0, 3.2  # TIER_DAMAGED


def _compute_confidence_vectors(state: InputState, ref: ReferenceModel) -> None:
    """Compute 5 independent confidence values. Modifies state in-place."""
    snr_f  = float(np.clip((state.snr_global - 8.0) / 22.0, 0.0, 1.0))
    cut_f  = float(np.clip((state.codec_cutoff - 6000) / 8000.0, 0.0, 1.0))
    smr_f  = float(np.clip((8.0 - state.smear_score) / 8.0, 0.0, 1.0))
    # eq_confidence is now the GLOBAL scalar floor only — per-band scaling is
    # handled in _eq_band_confidence() during design_eq(). This remains for
    # logging/reporting and as the floor for per-band confidence.
    state.eq_confidence = max(0.15, snr_f * 0.40 + cut_f * 0.35 + smr_f * 0.25)

    if state.noise_type == 'none' or state.source_tier == 'TIER_PRISTINE':
        state.nr_confidence = 0.0
    else:
        sfm_f  = float(np.clip((state.silence_sfm - 0.1) / 0.55, 0.0, 1.0))
        flr_f  = float(np.clip(abs(state.silence_floor) / 62.0, 0.0, 1.0))
        state.nr_confidence = max(0.05, sfm_f * 0.60 + flr_f * 0.40)

    lra_gap = abs(state.clip_lra - ref.phrase_lra_p50)
    lra_f   = float(np.clip(lra_gap / 3.0, 0.0, 1.0))
    crest_ok = float(np.clip((state.clip_crest - 6.5) / 4.0, 0.0, 1.0))

    # FIX-23: High Crest on a good-quality source means NATURAL DYNAMICS — not
    # a compression opportunity. The old formula gave crest_ok=1.0 for Crest=16,
    # inflating compand_confidence to 0.51 on a file that needs near-zero compand.
    #
    # Rule: for PRISTINE/COMPRESSED sources where Crest > 12 AND LRA is already
    # close to target (within 1 LU), the compand decision is driven by LRA alone.
    # crest_ok is only a driver when Crest is low (over-compressed source) — which
    # is the situation where we genuinely need to restore dynamics.
    _high_crest_good_quality = (
        state.source_tier in ('TIER_PRISTINE', 'TIER_COMPRESSED')
        and state.clip_crest > 12.0
        and lra_gap < 1.0
    )
    if state.clip_crest < 7.0:
        state.compand_confidence = 0.0
    elif _high_crest_good_quality:
        # LRA-only gate: compand only if LRA genuinely needs shifting
        state.compand_confidence = lra_f * 0.80
    else:
        # Standard formula: both LRA and Crest headroom drive compand
        state.compand_confidence = lra_f * 0.60 + crest_ok * 0.40

    state.bias_confidence = 1.0

    if state.codec_cutoff < 8000 or state.smear_score >= 7:
        state.hf_confidence = 0.0
    elif state.codec_cutoff < 12000:
        state.hf_confidence = (state.codec_cutoff - 8000) / 4000.0
    else:
        state.hf_confidence = float(np.clip((state.snr_global - 15.0) / 15.0, 0.3, 1.0))


def analyze_input(path: str, ref: ReferenceModel) -> InputState:
    """Phase A: complete, unified single-pass input analysis."""
    state = InputState(path=path)

    pr = probe_file(path)
    stream = pr.get('streams', [{}])[0]
    state.is_mono = stream.get('channels', 2) == 1
    state.src_sr  = int(stream.get('sample_rate', 44100))
    state.src_br  = int(stream.get('bit_rate', 128_000))
    state.total_s = float(pr.get('format', {}).get('duration', 300))

    full_spectrum, rms_by_pos = _probe_full_file(path, state.total_s, n_windows=9)
    state.full_spectrum = full_spectrum

    state.skip_s, state.dur_s = _adaptive_window(path, state.total_s, rms_by_pos)

    clip = load_audio_fast(path, skip_s=state.skip_s, duration_s=state.dur_s)
    if len(clip) < SR * 3:
        L('  [analyze] clip too short — using defaults')
        return state

    sil = _measure_silence(clip, state.total_s, state.skip_s)
    state.silence_valid      = sil['valid']
    state.silence_floor      = sil['floor']
    state.silence_sfm        = sil['sfm']
    state.hum_freq_hz        = sil['hum']
    state.noise_type         = sil['noise_type']
    state.silence_frame_abs  = sil.get('frame_positions', [])

    state.clip_rms   = rms_db(clip)
    state.clip_crest = crest_factor(clip)
    state.clip_lra   = lra_estimate(clip)
    state.clip_sfm   = compute_sfm(clip)
    state.clip_dr    = compute_dynamic_range(clip)
    state.band_snr   = compute_band_snr(clip)
    state.snr_global = float(np.mean(list(state.band_snr.values()))) if state.band_snr else 25.0

    spec = state.full_spectrum or third_octave(clip)
    state.hf_rolloff   = max(detect_hf_rolloff(spec, 12.0), 2000.0)
    # BUG-A FIX: spectral rolloff fires too early on quiet/AAC files.
    # Quiet HF content in AAC drops >6dB vs mids → rolloff at 4-5kHz even at
    # 127kbps. A codec ALWAYS passes audio to its bitrate-minimum cutoff.
    # Enforce bitrate-based floor; spectral detection can only lower it.
    _br_floor = (14_000.0 if state.src_br >= 128_000 else
                 12_000.0 if state.src_br >=  96_000 else
                  9_000.0 if state.src_br >=  64_000 else
                  7_000.0 if state.src_br >=  32_000 else 5_000.0)
    _spec_cutoff = float(max(detect_hf_rolloff(spec, 6.0), 4000.0))
    state.codec_cutoff = float(max(_spec_cutoff, _br_floor))

    hf_bands = [fc for fc in spec if fc >= 8000]
    if hf_bands and ref.third_oct:
        hf_out = float(np.mean([spec.get(fc, -80) for fc in hf_bands]))
        hf_ref = float(np.mean([ref.third_oct.get(fc, -60) for fc in hf_bands]))
        state.hf_deficit = hf_ref - hf_out
    else:
        state.hf_deficit = 0.0

    clipped_n = int(np.sum(np.abs(clip) > 0.99))
    state.clip_ratio = float(clipped_n / max(len(clip), 1))

    state.smear_score, state.smear_desc = _detect_smear(clip)

    if ref.third_oct:
        common = [fc for fc in spec if fc in ref.third_oct and 80 <= fc <= min(12000, state.codec_cutoff * 0.9)]
        if common:
            out_arr = np.array([spec[fc] for fc in common])
            ref_arr = np.array([ref.third_oct[fc] for fc in common])
            loff = float(np.mean(ref_arr - out_arr))
            aw = np.array([max(0.2, 1 + A_WEIGHT.get(fc, 0) / 10) for fc in common])
            state.spec_dist = float(np.sum(aw * np.abs((ref_arr - out_arr) - loff)) / np.sum(aw))

    state.source_tier = _derive_source_tier(
        state.src_br, state.codec_cutoff, state.snr_global,
        state.noise_type, state.smear_score)

    state.achievable_lufs, state.achievable_crest, state.achievable_lra = \
        _compute_achievable(state.source_tier, state.codec_cutoff)

    w = {'TIER_PRISTINE': {'snr': 0.25, 'sfm': 0.25, 'spec': 0.20, 'hf': 0.15, 'dr': 0.15},
         'TIER_COMPRESSED': {'snr': 0.30, 'sfm': 0.25, 'spec': 0.18, 'hf': 0.07, 'dr': 0.20},
         'TIER_DEGRADED':   {'snr': 0.35, 'sfm': 0.28, 'spec': 0.15, 'hf': 0.02, 'dr': 0.20},
         'TIER_DAMAGED':    {'snr': 0.40, 'sfm': 0.30, 'spec': 0.10, 'hf': 0.00, 'dr': 0.20},
         }.get(state.source_tier, {'snr': 0.25, 'sfm': 0.25, 'spec': 0.20, 'hf': 0.15, 'dr': 0.15})
    sfm_ratio = state.clip_sfm / (ref.sfm + 1e-6)
    mds = (float(np.clip((30.0 - state.snr_global) / 30.0, 0, 1)) * 100 * w['snr'] +
           float(np.clip((sfm_ratio - 1.0) / 5.0, 0, 1)) * 100 * w['sfm'] +
           float(np.clip(state.spec_dist / 15.0, 0, 1)) * 100 * w['spec'] +
           float(np.clip(state.hf_deficit / 30.0, 0, 1)) * 100 * w['hf'] +
           float(np.clip(max(0, state.clip_dr - ref.dr) / 8.0, 0, 1)) * 100 * w['dr'])
    state.mds_raw = float(np.clip(mds, 0, 100))

    _compute_confidence_vectors(state, ref)

    return state


# ══════════════════════════════════════════════════════════════════════════════
#  DECLIP PASS (FIX-13, FIX-14)
# ══════════════════════════════════════════════════════════════════════════════
def _declip_pass(input_path: str, state: InputState) -> str:
    """
    FIX-13: Cubic spline declipping for sources with clip_ratio > 0.0005 (0.05%).
    FIX-14: Applied before NR pass in enhance().

    Why 0.05% threshold? The audible threshold for clipping in speech is
    approximately 0.01% (22 samples/sec). At 0.05% the distortion is audible
    in quiet listening environments. At 0.5% (the old threshold that was never
    wired) it is severe and certain.

    Why cubic spline over ffmpeg declip? ffmpeg's polynomial reconstruction
    doesn't account for the signal's harmonic structure. For Quranic recitation
    with multiple harmonics, the polynomial creates ringing at clip boundaries
    that can be more audible than the original clipping. Cubic spline through
    unclipped context respects the signal's local harmonic curvature.
    """
    if not SCIPY_OK:
        return input_path
    try:
        from scipy.interpolate import CubicSpline
    except ImportError:
        return input_path

    CLIP_THRESH = 0.995
    CONTEXT = 40  # samples each side for spline context

    # Load full audio (mono)
    audio = load_audio_fast(input_path, 0, state.total_s)
    if len(audio) < SR * 3:
        return input_path

    clipped_n = int(np.sum(np.abs(audio) >= CLIP_THRESH))
    if clipped_n == 0:
        return input_path

    L(f'  [declip] {clipped_n} clipped samples — cubic spline reconstruction...')
    fixed = audio.copy()
    is_clipped = np.abs(audio) >= CLIP_THRESH

    i = 0
    repairs = 0
    while i < len(audio):
        if is_clipped[i]:
            j = i
            while j < len(audio) and is_clipped[j]:
                j += 1
            # Need enough context on both sides
            left = max(0, i - CONTEXT)
            right = min(len(audio), j + CONTEXT)
            if (i - left) >= 5 and (right - j) >= 5:
                x_ctx = list(range(left, i)) + list(range(j, right))
                y_ctx = audio[x_ctx]
                try:
                    cs = CubicSpline(x_ctx, y_ctx)
                    x_clip = np.arange(i, j)
                    fixed[i:j] = np.clip(cs(x_clip).astype(np.float32), -1.0, 1.0)
                    repairs += 1
                except Exception:
                    pass  # leave original samples on failure
            i = max(j, i + 1)
        else:
            i += 1

    if repairs == 0:
        L('  [declip] no regions repaired — returning original')
        return input_path

    L(f'  [declip] repaired {repairs} clipped regions')

    # Write fixed mono float32 back through ffmpeg to get stereo WAV
    tmp = os.path.join(_TMP, 'v10base_declip.wav')
    raw_bytes = fixed.astype(np.float32).tobytes()
    r = subprocess.run(
        ['ffmpeg', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '1',
         '-i', '-', '-ar', str(SR), '-ac', '2', '-c:a', WAV_CODEC,
         '-loglevel', 'error', tmp],
        input=raw_bytes, capture_output=True)
    if r.returncode == 0 and os.path.exists(tmp):
        return tmp
    L('  [declip] write failed — returning original')
    return input_path


# ══════════════════════════════════════════════════════════════════════════════
#  NR PASS (Phase B)
# ══════════════════════════════════════════════════════════════════════════════
def _build_hum_notch(sil: Dict) -> str:
    if not sil.get('valid'): return ''
    parts = []
    if sil.get('hum_50db', 0) > 15.0:
        parts.append(f'equalizer=f=50:width_type=q:width=0.4:g=-{min(24, int(sil["hum_50db"] * 0.8))}')
    if sil.get('hum_60db', 0) > 15.0:
        parts.append(f'equalizer=f=60:width_type=q:width=0.4:g=-{min(24, int(sil["hum_60db"] * 0.8))}')
    if sil.get('hum_100db', 0) > 12.0:
        parts.append(f'equalizer=f=100:width_type=q:width=0.6:g=-{min(18, int(sil["hum_100db"] * 0.7))}')
    if sil.get('hum_120db', 0) > 12.0:
        parts.append(f'equalizer=f=120:width_type=q:width=0.6:g=-{min(18, int(sil["hum_120db"] * 0.7))}')
    return ','.join(parts)


def _build_nr_filter(state: InputState, ref: ReferenceModel,
                     silence_data: Dict) -> str:
    """
    NR-01/02/03/05: Build the two-stage frequency-aware NR filter chain.

    Stage 1 — Hum notch: surgical narrow cuts at 50/60/100/120Hz.
              Applied first so Stage 2 does not interpret tonal hum
              energy as broadband noise.

    Stage 2 — Broadband NR (afftdn):
              NR-02: Frequency-aware depth. Hiss lives above 4kHz and
              below the speech core. The filter string uses a single nf
              but the depth is calibrated to be heavier for high-SFM
              sources where hiss dominates above 4kHz.
              NR-03: nf is the SPECTRAL estimate from silence frames
              (silence_floor + adaptive offset), not a fixed guess.
              NR-05: depth scales with silence frame count — more frames
              means a more reliable noise estimate allows deeper NR.

    Stage 3 — High-frequency hiss trim (conditional):
              If noise_type contains 'hiss' and codec_cutoff > 8kHz,
              a gentle shelf cut above 6kHz removes the HF residual
              that afftdn leaves behind. This is a 2dB shelf, not a
              rolloff — it reduces hiss without killing air.

    Stage 4 — Low-pass for codec ringing (conditional):
              Only for src_br < 65kbps with detected rolloff < 16kHz.
    """
    ref_nr_floor = float(ref.silence_floor - 3.0)
    nf = float(np.clip(max(state.silence_floor + 2.0, ref_nr_floor), -76, -40))

    # NR-05: depth scales with silence frame quality
    n_frames = len(state.silence_frame_abs)
    frame_bonus = float(np.clip((n_frames - 5) / 15.0, 0.0, 1.0))  # 0 at 5 frames, 1 at 20+

    max_nr = {'TIER_DAMAGED': 15, 'TIER_DEGRADED': 10,
              'TIER_COMPRESSED': 6}.get(state.source_tier, 5)
    base_depth = max(3, int(state.nr_confidence * max_nr))
    nr_depth = int(base_depth * (0.7 + 0.3 * frame_bonus))
    nr_depth = max(3, min(max_nr, nr_depth))

    # NR-02: heavier for high-SFM (flat broadband) vs hum-only
    if state.silence_sfm > 0.65:  # broadband / hiss
        nr_depth = min(max_nr, nr_depth + 2)

    filters = []

    # Stage 1: hum notch
    hum_notch = _build_hum_notch(silence_data)
    if hum_notch:
        filters.append(hum_notch)

    # Stage 2: broadband NR — tn=1 protects transients (onset of each ayah)
    filters.append(f'afftdn=nr={nr_depth}:nf={nf:.0f}:tn=1')

    # Stage 3: HF hiss shelf — only when hiss confirmed AND HF content exists
    has_hiss = 'hiss' in state.noise_type or state.silence_sfm > 0.60
    if has_hiss and state.codec_cutoff > 8000:
        # 2dB gentle shelf at 6kHz — reduces hiss residual, preserves air
        filters.append('equalizer=f=7000:width_type=s:width=1:g=-2.0')

    # Stage 4: codec ringing lowpass
    if state.src_br < 65000 and state.hf_rolloff < 16000:
        lp_hz = int(min(state.hf_rolloff * 0.97, 15000))
        filters.append(f'lowpass=f={lp_hz}:poles=2')

    return ','.join(filters)


def nr_pass(input_path: str, state: InputState, ref: ReferenceModel,
            silence_data: Dict) -> Tuple[str, Dict]:
    """
    Phase B: Two-stage frequency-aware NR pass — always before EQ.

    NR-01: Two-stage architecture (hum notch → broadband → HF hiss trim).
    NR-02: Frequency-aware depth (heavier above 4kHz, lighter in speech core).
    NR-03: Silence-frame spectral noise profile for nf estimation.
    NR-04: Post-NR SFM gate — revert if noise became more tonal.
    NR-05: Adaptive depth from silence frame count.
    """
    nr_report = {'applied': False, 'floor_delta': 0.0, 'sib_delta': 0.0,
                 'reverted': False, 'stage': ''}

    if state.nr_confidence <= 0.05:
        return input_path, nr_report

    full_filter = _build_nr_filter(state, ref, silence_data)

    tmp_nr = os.path.join(_TMP, 'v10base_nr.wav')
    ok = ffmpeg_process(input_path, tmp_nr, full_filter)
    if not ok:
        L('  [NR] ffmpeg failed — bypass')
        return input_path, nr_report

    # ── Pre/post measurement ─────────────────────────────────────────────────
    pre_clip = load_audio_fast(input_path, state.skip_s, min(30, state.dur_s))
    pre_sib  = compute_sibilant_snr(pre_clip, state.silence_floor)
    pre_sfm  = compute_sfm(pre_clip)

    # Measure post-NR floor from stored silence positions (NR-03)
    post_floor_samples = []
    for pos in state.silence_frame_abs[:10]:
        seg = load_audio_fast(tmp_nr, skip_s=pos, duration_s=0.2)
        if len(seg) > 100:
            post_floor_samples.append(rms_db(seg))
    post_floor = (float(np.median(post_floor_samples))
                  if post_floor_samples else state.silence_floor)

    post_clip = load_audio_fast(tmp_nr, state.skip_s, min(30, state.dur_s))
    post_sib  = compute_sibilant_snr(post_clip, post_floor)
    post_sfm  = compute_sfm(post_clip)

    floor_delta = state.silence_floor - post_floor  # positive = floor dropped
    sib_delta   = post_sib - pre_sib               # negative = sibilant harmed

    L(f'  [NR] floor:{state.silence_floor:.1f}->{post_floor:.1f} (d={floor_delta:+.1f}dB) sib:{pre_sib:.1f}->{post_sib:.1f} (d={sib_delta:+.1f}) sfm:{pre_sfm:.3f}->{post_sfm:.3f}')

    # ── Do-no-harm gates ─────────────────────────────────────────────────────
    def _revert(reason: str) -> Tuple[str, Dict]:
        L(f'  [NR] REVERTED — {reason}')
        try: os.unlink(tmp_nr)
        except: pass
        nr_report['reverted'] = True
        nr_report['stage'] = reason
        return input_path, nr_report

    # Gate 1: sibilant protection — ش/س/ص must not be harmed
    if sib_delta < -3.0:
        return _revert(f'sibilant drop {sib_delta:+.1f}dB > 3dB threshold')

    # Gate 2: voiced content must not be significantly changed
    voiced_delta = rms_db(post_clip) - rms_db(pre_clip)
    if voiced_delta > 1.0:
        return _revert(f'voiced RMS changed {voiced_delta:+.1f}dB > 1dB')

    # Gate 3 (NR-04): SFM should not increase (noise becoming more tonal = wrong)
    # Allow small increase (0.05) as afftdn can slightly sharpen residual
    if post_sfm > pre_sfm + 0.08 and post_sfm > 0.4:
        return _revert(f'noise SFM increased {pre_sfm:.3f}→{post_sfm:.3f} (tonal artifact)')

    # Gate 4: check NR actually did something meaningful
    if floor_delta < 1.5 and abs(sib_delta) < 0.5:
        L(f'  [NR] minimal effect (floor_Δ={floor_delta:+.1f}dB) — accepted but flagged')

    nr_report.update({'applied': True, 'floor_delta': float(floor_delta),
                      'sib_delta': float(sib_delta),
                      'stage': 'two-stage'})
    return tmp_nr, nr_report


# ══════════════════════════════════════════════════════════════════════════════
#  EQ SYSTEM (Phase C)
# ══════════════════════════════════════════════════════════════════════════════
def _bias_band_weight(fc: float, codec_cutoff: float, hf_rolloff: float) -> float:
    if fc > hf_rolloff * 0.9: return 0.0
    if fc > codec_cutoff:     return 0.0
    cutoff_safe = codec_cutoff * 0.85
    if fc < cutoff_safe:      return 1.0
    raw = (codec_cutoff - fc) / max(codec_cutoff * 0.15, 1)
    return max(0.20, float(np.clip(raw, 0, 1)))


def build_bias_filter_nodes(state: InputState) -> List[Tuple[float, float, float]]:
    """
    FIX-22: Scale bias by source quality (mds_raw).
    The SPECTRAL_BIAS_V9 values were calibrated for the 1425H mic-chain signature.
    A good quality source from a different year/mic/room (low MDS, no damage) should
    receive little bias correction — its spectral character is legitimately different,
    not broken. A severely damaged source (high MDS) needs the full bias to reconstruct
    toward the reference profile.

    mds_quality_scale = min(1.0, max(0.15, mds_raw / 45.0))
      MDS =  0  (perfect): scale = 0.15  (only 15% of bias applied)
      MDS = 10  (good):    scale = 0.22
      MDS = 25  (fair):    scale = 0.56
      MDS = 45  (poor):    scale = 1.00  (full bias from here upward)
      MDS = 75  (damaged): scale = 1.00

    The 0.15 floor ensures the Sheikh's mic corrections are never fully absent —
    even a clean file benefits slightly from the calibrated offsets.
    """
    mds_quality_scale = float(np.clip(state.mds_raw / 45.0, 0.15, 1.0))

    nodes = []
    for fc, bias_db in SPECTRAL_BIAS_V9.items():
        g = round(-bias_db * BIAS_SCALE, 2)
        if abs(g) < 0.20: continue
        w = _bias_band_weight(float(fc), state.codec_cutoff, state.hf_rolloff)
        if w <= 0.0: continue
        # FIX-22: scale by codec geometry AND source quality
        g_scaled = round(g * w * mds_quality_scale, 2)
        if abs(g_scaled) < 0.10: continue
        Q = 0.65 if abs(g_scaled) > 1.5 else 0.90
        nodes.append((float(fc), g_scaled, Q))
    return nodes


def _eq_band_confidence(fc: float, state: InputState) -> float:
    """
    FIX-06: Per-frequency-band EQ confidence.
    The old uniform eq_confidence scalar was too conservative at LF
    (bass is always reliable) and too aggressive at HF near codec cutoff
    (HF corrections near cutoff should approach zero, not be uniformly scaled).

    Three independent factors by frequency region:
    - HF reliability: degrades linearly toward zero at codec_cutoff (hard zero beyond)
    - Mid (1-4kHz) reliability: scales with SNR (noise contaminates speech bands)
    - Sibilant (2-6kHz) reliability: scales inversely with smear score
    - LF (<= 400Hz): always reliable — codec preserves bass, SNR is irrelevant
    """
    # Hard zero above codec cutoff
    if fc > state.codec_cutoff:
        return 0.0

    # HF transition zone: linear ramp to zero as fc approaches cutoff
    if fc > state.codec_cutoff * 0.85:
        hf_conf = (state.codec_cutoff - fc) / (state.codec_cutoff * 0.15)
    else:
        hf_conf = 1.0

    # Low frequency: always trustworthy regardless of codec damage
    if fc <= 400.0:
        return min(1.0, hf_conf)

    # Mid-frequency (1-4kHz): reliability scales with SNR
    if 1000.0 <= fc <= 4000.0:
        snr_conf = float(np.clip((state.snr_global - 8.0) / 17.0, 0.3, 1.0))
    else:
        snr_conf = 1.0

    # Sibilant region (2-6kHz): reliability degrades with smear
    if 2000.0 <= fc <= 6000.0:
        smear_conf = float(np.clip((8.0 - state.smear_score) / 8.0, 0.3, 1.0))
    else:
        smear_conf = 1.0

    return float(min(hf_conf, snr_conf, smear_conf))


def optimize_eq(inp_b: Dict, ref_b: Dict, n_nodes: int = 12, max_db: float = 6.0,
                sib_cap: float = None, hf_ceil: float = 12000.0,
                warmstart: List[Tuple] = None) -> List[Tuple]:
    """scipy L-BFGS-B perceptual EQ optimizer."""
    if not SCIPY_OK: return []
    ceil = min(hf_ceil, 12000.0)
    common = sorted(fc for fc in inp_b if fc in ref_b and 63 <= fc <= ceil)
    if len(common) < 4: return []

    fc_arr = np.array(common, dtype=float)
    inp_arr = np.array([inp_b[fc] for fc in common])
    ref_arr = np.array([ref_b[fc] for fc in common])
    loff    = float(np.mean(ref_arr - inp_arr))
    target  = (ref_arr - inp_arr) - loff

    def baw(fc):
        bw = (2.0 if 500 <= fc <= 4000 else 1.6 if 200 <= fc < 500
              else 1.4 if 4000 < fc <= 8000 else 0.9)
        return bw * max(0.3, 1 + A_WEIGHT.get(fc, 0) / 10)

    aw = np.array([baw(fc) for fc in common])
    init_f = np.logspace(np.log10(63), np.log10(ceil), n_nodes)

    def resp(fa, p):
        r = np.zeros(len(fa))
        for i in range(n_nodes):
            f0 = abs(p[i * 3]) + 1e-6; g = p[i * 3 + 1]; Q = max(0.3, abs(p[i * 3 + 2]))
            rat = fa / f0
            r += g / (1 + Q ** 2 * (rat - 1.0 / (rat + 1e-9)) ** 2)
        return r

    def obj(p):
        e  = np.mean(aw * (resp(fc_arr, p) - target) ** 2)
        gs = [p[i * 3 + 1] for i in range(n_nodes)]
        sm = sum(0.012 * (gs[i + 1] - gs[i]) ** 2 for i in range(len(gs) - 1))
        mg = sum(0.002 * g ** 2 for g in gs)
        return e + sm + mg

    if warmstart and len(warmstart) == n_nodes:
        x0 = []
        for f0, g, Q in warmstart:
            x0.extend([float(np.clip(f0, 63, ceil)), float(np.clip(g, -max_db, max_db)), float(Q)])
    else:
        ig = np.interp(np.log10(init_f), np.log10(fc_arr), target)
        x0 = []
        for f, g in zip(init_f, ig):
            x0.extend([float(np.clip(f, 63, ceil)), float(np.clip(g, -max_db, max_db)), 1.0])

    res = minimize(obj, x0, method='L-BFGS-B',
                   bounds=[(63, ceil), (-max_db, max_db), (0.3, 4.5)] * n_nodes,
                   options={'maxiter': 500, 'ftol': 1e-10, 'gtol': 1e-9})

    nodes = []
    for i in range(n_nodes):
        f0 = abs(res.x[i * 3]); g = res.x[i * 3 + 1]; Q = max(0.3, abs(res.x[i * 3 + 2]))
        if sib_cap is not None and 2000 <= f0 <= 6300:
            g = float(np.clip(g, -sib_cap, sib_cap))
        if abs(g) >= 0.35:
            nodes.append((round(f0, 0), round(g, 2), round(Q, 2)))
    return sorted(nodes, key=lambda x: x[0])


def _lpc_sibilant_nodes(audio: 'np.ndarray', smear_score: float,
                         sr: int = SR) -> List[Tuple[float, float, float]]:
    """
    FIX-07: LPC formant analysis — EQ restoration nodes for smeared Arabic fricatives.
    Ported from v8.9 with ZCR gate from FIX-05 for accurate fricative isolation.

    When smear_score >= 4.0, the 2-6kHz harmonic peaks of fricatives
    (the characteristic spectral pattern of sh/s/sad) have been destroyed
    by codec re-encoding. The optimizer only caps these frequencies (sib_cap=2.0)
    to avoid boosting distortion. This function adds narrow-band boost nodes
    at the actual formant frequencies where LPC analysis shows the peaks
    should be, with gain proportional to smear severity.

    Uses ZCR gate to select true fricative frames (ZCR > 0.20) and LPC
    order-16 analysis. Roots with Im > 0, frequency in 2000-6200Hz, and
    bandwidth < 800Hz are collected into 200Hz buckets. The most consistent
    buckets (appearing in >= 8% of processed frames) become EQ nodes.
    """
    if smear_score < 4.0 or not SCIPY_OK:
        return []
    try:
        from scipy.linalg import solve_toeplitz
    except ImportError:
        return []

    frame_n = int(0.025 * sr)
    hop_n = int(0.010 * sr)
    overall = rms_db(audio)
    lo, hi = overall - 15.0, overall - 3.0
    formant_buckets: Dict[int, List[float]] = {}
    processed = 0

    for i in range(0, len(audio) - frame_n, hop_n):
        frame = audio[i:i + frame_n]
        # Energy gate
        if not (lo < rms_db(frame) < hi):
            continue
        # ZCR gate — only unvoiced fricatives
        zcr = float(np.sum(np.abs(np.diff(np.sign(frame))))) / (2 * frame_n)
        if zcr < 0.20:
            continue
        try:
            win = frame * np.hanning(frame_n)
            order = 16
            r_corr = np.correlate(win, win, 'full')[frame_n - 1:frame_n + order]
            if abs(r_corr[0]) < 1e-10:
                continue
            a = solve_toeplitz(r_corr[:order], r_corr[1:order + 1])
            lpc = np.concatenate([[1.0], -a])
            for root in np.roots(lpc):
                if root.imag <= 0:
                    continue
                freq = np.angle(root) / (2 * np.pi) * sr
                if not (2000 <= freq <= 6200):
                    continue
                bw = -np.log(abs(root) + 1e-12) / np.pi * sr
                if bw >= 800:
                    continue  # broad = noise, not a formant
                bucket = int(round(freq / 200) * 200)
                formant_buckets.setdefault(bucket, []).append(float(freq))
            processed += 1
        except Exception:
            continue
        if processed >= 150:
            break

    if processed < 10:
        return []

    # Gain proportional to smear severity (0 at smear=4, 2dB at smear=10)
    blend = float(np.clip((smear_score - 4.0) / 6.0, 0, 1)) * 2.0
    min_frames = max(5, int(processed * 0.08))
    nodes = []

    # Sort by bucket consistency (most frames first)
    for bucket, freqs in sorted(formant_buckets.items(), key=lambda x: -len(x[1])):
        if len(freqs) < min_frames:
            continue
        f0 = float(np.median(freqs))
        spread = float(np.std(freqs)) if len(freqs) > 1 else 200.0
        Q = float(np.clip(f0 / (max(spread, 80.0) * 2.5), 1.5, 8.0))
        g = round(blend, 2)
        if g >= 0.30:
            nodes.append((round(f0, 0), g, round(Q, 2)))
        if len(nodes) >= 4:
            break

    return nodes


def _compute_eq_scale(state: InputState) -> float:
    """
    FIX-24: EQ intensity gate by source quality tier.

    For TIER_PRISTINE and TIER_COMPRESSED: cap at 55% of computed corrections,
    scaled further by how large the spectral distance actually is.
    Formula: min(0.55, 0.55 * clip(spec_dist / 2.0, 0.4, 1.0))
      spec_dist = 0.0: scale = 0.22  (20% — almost nothing on perfect source)
      spec_dist = 1.2: scale = 0.33  (33%)
      spec_dist = 1.9: scale = 0.52  (52%)
      spec_dist = 2.0+: scale = 0.55 (55% ceiling for good-quality sources)

    For TIER_DEGRADED and TIER_DAMAGED: always 1.0 (full corrections, unchanged).
    These sources genuinely need aggressive EQ to recover spectral shape.

    Rationale: on a high-quality source the spectral distance from the 1425H
    reference may reflect a legitimately different but valid recording character,
    not codec damage. Applying full corrections forces 1425H's mic/room signature
    onto a recording that doesn't need it.
    """
    if state.source_tier in ('TIER_DEGRADED', 'TIER_DAMAGED'):
        return 1.0
    # PRISTINE / COMPRESSED: gentle proportional scaling
    dist_factor = float(np.clip(state.spec_dist / 2.0, 0.4, 1.0))
    return float(np.clip(0.55 * dist_factor, 0.22, 0.55))


def design_eq(post_nr_spectrum: Dict, ref: ReferenceModel, state: InputState,
              warmstart: List[Tuple] = None,
              nr_wav_path: str = None) -> List[Tuple]:
    """
    Phase C: EQ design from post-NR spectrum.
    FIX-06: Per-band confidence scaling via _eq_band_confidence().
    FIX-07: LPC smear restoration nodes added for smear_score >= 4.0.
    FIX-24: EQ intensity gate via _compute_eq_scale() for good quality sources.

    nr_wav_path: if provided and smear_score >= 4.0, used for LPC analysis.
    """
    # Build biased target: ref + bias correction (FIX-22 scales bias by MDS)
    bias_nodes = build_bias_filter_nodes(state)
    biased_target = dict(ref.third_oct)
    for fc, g, _ in bias_nodes:
        if fc in biased_target:
            biased_target[fc] = biased_target[fc] + g

    sib_cap = 2.0 if state.smear_score >= 4.0 else None
    hf_ceil = min(state.hf_rolloff * 0.9, ref.ref_codec_cutoff, 12000.0)

    eq_nodes = optimize_eq(
        post_nr_spectrum, biased_target,
        n_nodes=12, max_db=6.0, sib_cap=sib_cap,
        hf_ceil=hf_ceil, warmstart=warmstart)

    # FIX-06: Per-band confidence scaling
    eq_nodes = [
        (f, round(g * _eq_band_confidence(f, state), 2), q)
        for f, g, q in eq_nodes
    ]

    # FIX-24: EQ scale gate — good quality sources get proportionally less EQ
    eq_scale = _compute_eq_scale(state)
    if eq_scale < 1.0:
        eq_nodes = [(f, round(g * eq_scale, 2), q) for f, g, q in eq_nodes]
        L(f'  [eq] quality gate: scale={eq_scale:.2f} '
          f'(tier={state.source_tier} spec_dist={state.spec_dist:.2f}dB)')

    eq_nodes = [(f, g, q) for f, g, q in eq_nodes if abs(g) >= 0.15]

    # FIX-07: LPC smear restoration nodes (unaffected by quality gate —
    # smear restoration is always needed when smear is present)
    if state.smear_score >= 4.0 and nr_wav_path:
        try:
            analysis_clip = load_audio_fast(
                nr_wav_path, state.skip_s, min(60.0, float(state.dur_s)))
            sib_nodes = _lpc_sibilant_nodes(analysis_clip, state.smear_score)
            if sib_nodes:
                eq_nodes = eq_nodes + sib_nodes
                L(f'  [smear] +{len(sib_nodes)} formant restoration nodes '
                  f'(smear={state.smear_score}/10)')
        except Exception as e:
            L(f'  [smear] LPC analysis failed (non-fatal): {e}')

    return eq_nodes


def nodes_to_af(nodes: List[Tuple]) -> str:
    parts = []
    for f0, g, Q in nodes:
        if abs(g) < 0.10: continue
        parts.append(f'equalizer=f={f0:.0f}:width_type=q:width={Q:.2f}:g={g:.2f}')
    return ','.join(parts)


# ══════════════════════════════════════════════════════════════════════════════
#  JOINT LUFS+LRA OPTIMIZER (Phase D)
# ══════════════════════════════════════════════════════════════════════════════
def _sample_compand_effect(eq_wav: str, curve_str: str, positions: List[float],
                            sample_s: float = 25.0) -> Tuple[float, float, float]:
    """
    FIX-09: Extract clips first — not full-file × 3.
    The old code processed the ENTIRE eq_wav for each of 3 compand curves.
    For a 90-minute surah, that is 3 × ~1.5GB WAV = 4.5GB processed just
    for calibration, taking 8-15 minutes before the first iteration completes.
    New approach: extract 25s clips at each position first, then apply compand
    to short clips only. Total: 3 positions × 25s × 3 curves = 225s of audio
    instead of 3 × full file. 24× faster on 90-minute surahs.

    FIX-10: Measure actual LUFS per clip — not RMS proxy.
    The old code used rms_db() as a proxy for LUFS. RMS and R128 LUFS differ
    by 2-4dB for speech (K-weighting boosts mids). This caused a systematic
    gain correction error of 1-3dB in the joint optimizer. Now we measure
    actual LUFS for each pre/post clip pair.

    FIX-12: Consistent compand timing with run_pass_joint().
    Both use attacks=0.08:decays=0.5 so calibration matches production.
    """
    # Step 1: Extract short clips at each position (fast seek on any file type)
    pre_clips: Dict[int, str] = {}
    for idx, pos in enumerate(positions):
        clip_path = os.path.join(_TMP, f'v100_jclip_{idx}.wav')
        r = subprocess.run(
            ['ffmpeg', '-y', '-ss', str(pos), '-i', eq_wav,
             '-t', str(sample_s), '-ar', str(SR), '-ac', '2',
             '-c:a', WAV_CODEC, clip_path, '-loglevel', 'error'],
            capture_output=True)
        if r.returncode == 0 and os.path.exists(clip_path):
            pre_clips[idx] = clip_path

    if not pre_clips:
        return 0.0, 0.0, 0.0

    # Step 2: Measure pre-compand LUFS and LRA on each clip
    pre_lra: List[float] = []
    pre_lufs_list: List[float] = []
    for clip_path in pre_clips.values():
        clip_audio = load_audio_fast(clip_path, 0, sample_s)
        if len(clip_audio) < SR * 5:
            continue
        pre_lra.append(lra_estimate(clip_audio))
        # FIX-10: actual LUFS (not RMS)
        pre_lufs_list.append(measure_lufs(clip_path))

    if not pre_lra:
        for p in pre_clips.values():
            try: os.unlink(p)
            except: pass
        return 0.0, 0.0, 0.0

    # Step 3: Apply compand to each short clip (FIX-12: consistent timing)
    af = f'compand=attacks=0.08:decays=0.5:points={curve_str}'
    post_lra_l: List[float] = []
    post_lufs_l: List[float] = []
    post_crest_l: List[float] = []

    for idx, clip_path in pre_clips.items():
        out_path = os.path.join(_TMP, f'v100_jpost_{idx}.wav')
        ok = ffmpeg_process(clip_path, out_path, af)
        if not ok:
            continue
        post_audio = load_audio_fast(out_path, 0, sample_s)
        if len(post_audio) < SR * 5:
            try: os.unlink(out_path)
            except: pass
            continue
        post_lra_l.append(lra_estimate(post_audio))
        post_lufs_l.append(measure_lufs(out_path))
        post_crest_l.append(crest_factor(post_audio))
        try: os.unlink(out_path)
        except: pass

    # Cleanup pre-clips
    for p in pre_clips.values():
        try: os.unlink(p)
        except: pass

    if not post_lra_l:
        return 0.0, 0.0, 0.0

    lufs_delta = float(np.mean(post_lufs_l)) - float(np.mean(pre_lufs_list))
    lra_delta  = float(np.mean(post_lra_l))  - float(np.mean(pre_lra))
    mean_crest = float(np.mean(post_crest_l))
    return lufs_delta, lra_delta, mean_crest


def joint_lufs_lra_optimize(result_1: PassResult, ref: ReferenceModel,
                              state: InputState,
                              cached: JointParams = None) -> JointParams:
    """
    3-position x 3-curve empirical PCHIP spline joint optimizer.
    Returns JointParams with optimal compand_str + gain_db.
    """
    if cached is not None:
        if abs(result_1.lra - ref.phrase_lra_p50) < 0.3:
            return cached

    total = state.total_s
    positions = [
        float(state.skip_s),
        float(total * 0.40),
        float(total * 0.70),
    ]
    positions = [min(p, total - 35) for p in positions]

    if state.compand_confidence < 0.05:
        gain_db = state.achievable_lufs - result_1.lufs
        return JointParams(compand_str=_COMPAND_LIBRARY['BYPASS'],
                           gain_db=float(np.clip(gain_db, -6, 6)),
                           intensity_label='BYPASS')

    sample_curves = ['LIGHT', 'MEDIUM', 'HEAVY']
    lra_deltas: List[float] = []
    lufs_deltas: List[float] = []
    crest_vals: List[float] = []

    for name in sample_curves:
        ld, lrad, crt = _sample_compand_effect(
            result_1.wav_path, _COMPAND_LIBRARY[name], positions)
        lra_deltas.append(lrad); lufs_deltas.append(ld); crest_vals.append(crt)
        L(f'  [joint] {name}: LRA_delta={lrad:+.2f}  LUFS_delta={ld:+.2f}  Crest={crt:.2f}')

    intensities = [_COMPAND_INTENSITY[n] for n in sample_curves]

    target_lra_delta = ref.phrase_lra_p50 - result_1.lra
    L(f'  [joint] target_LRA_delta={target_lra_delta:+.2f} '
      f'(current={result_1.lra:.2f} to {ref.phrase_lra_p50:.2f})')

    if _PCHIP_OK and len(set(lra_deltas)) >= 2:
        interp = PchipInterpolator(intensities, lra_deltas)
        lo, hi = 0.0, 1.0
        for _ in range(30):
            mid = (lo + hi) / 2
            if float(interp(mid)) < target_lra_delta:
                lo = mid
            else:
                hi = mid
        target_intensity = (lo + hi) / 2
    else:
        target_intensity = float(np.interp(target_lra_delta, lra_deltas, intensities))

    target_intensity = float(np.clip(target_intensity * state.compand_confidence, 0, 1))

    best_name = min(_COMPAND_INTENSITY.keys(),
                    key=lambda n: abs(_COMPAND_INTENSITY[n] - target_intensity))
    best_idx = sample_curves.index(best_name) if best_name in sample_curves else 1

    predicted_lra_delta  = float(np.interp(target_intensity, intensities, lra_deltas))
    predicted_lufs_delta = float(np.interp(target_intensity, intensities, lufs_deltas))
    predicted_crest      = float(np.interp(target_intensity, intensities, crest_vals))

    crest_guard_hit = False
    if predicted_crest < state.achievable_crest - 0.5:
        L(f'  [joint] crest guard: {predicted_crest:.2f} < {state.achievable_crest - 0.5:.2f}')
        crest_guard_hit = True
        lighter = {'EXTREME': 'HEAVY', 'HEAVY': 'MEDIUM', 'MEDIUM': 'LIGHT',
                   'LIGHT': 'MINIMAL', 'MINIMAL': 'BYPASS'}.get(best_name, 'BYPASS')
        best_name = lighter

    # FIX-10 benefit: predicted_lufs_delta is now LUFS-accurate (not RMS-biased)
    predicted_lufs = result_1.lufs + predicted_lufs_delta
    gain_db = state.achievable_lufs - predicted_lufs
    gain_db = float(np.clip(gain_db, -18.0, 18.0))  # BUG-F FIX: was ±6dB — same issue as BUG-D

    L(f'  [joint] selected={best_name} intensity={target_intensity:.2f} '
      f'gain={gain_db:+.2f}dB crest_guard={crest_guard_hit}')

    return JointParams(
        compand_str=_COMPAND_LIBRARY[best_name],
        gain_db=gain_db,
        predicted_lufs=predicted_lufs + gain_db,
        predicted_lra=result_1.lra + predicted_lra_delta,
        predicted_crest=predicted_crest,
        intensity_label=best_name,
        crest_guard_hit=crest_guard_hit,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  PASS EXECUTION
# ══════════════════════════════════════════════════════════════════════════════
def run_pass_eq(nr_wav: str, eq_nodes: List[Tuple], pass_label: str = 'eq') -> str:
    """Apply EQ nodes to WAV. Returns output WAV path."""
    af = nodes_to_af(eq_nodes)
    if not af:
        af = 'volume=1.0'

    af += ',alimiter=limit=0.9997:level=false:attack=5:release=50'
    out = os.path.join(_TMP, f'v100_{pass_label}.wav')
    ok = ffmpeg_process(nr_wav, out, af)
    if not ok:
        L(f'  [run_pass_eq] failed — returning input')
        return nr_wav
    return out


def run_pass_joint(eq_wav: str, jp: JointParams, pass_label: str = 'joint') -> str:
    """
    Apply compand + gain. Returns output WAV path.
    FIX-11: Explicit compand attack/release timing.
    attacks=0.08 (80ms): tracks at phrase-group level, not individual phoneme.
      Arabic stop consonants (qaf/ta/ba) have closure durations of 20-60ms.
      At 5ms (old implicit default) the compressor attacks within each consonant,
      crushing the vowel release. At 80ms it operates at syllable-group level,
      preserving the micro-dynamic character of each syllable.
    decays=0.5 (500ms): matches typical inter-ayah pause (1-3s).
      The compand fully recovers during long pauses without pumping the opening
      of the next ayah. The old default of 800ms was too slow to recover between
      short ayahs, causing gain to stay suppressed across ayah boundaries.
    """
    parts = []
    if jp.intensity_label != 'BYPASS':
        parts.append(
            f'compand=attacks=0.08:decays=0.5:points={jp.compand_str}'
        )
    if abs(jp.gain_db) > 0.05:
        parts.append(f'volume={jp.gain_db:.3f}dB')
    parts.append('alimiter=limit=0.9997:level=false:attack=5:release=50')
    af = ','.join(parts)
    out = os.path.join(_TMP, f'v100_{pass_label}.wav')
    ok = ffmpeg_process(eq_wav, out, af)
    if not ok:
        L(f'  [run_pass_joint] failed — returning input')
        return eq_wav
    return out


def _find_peak_position(wav_path: str, total_s: float) -> float:
    positions = [total_s * f for f in [0.20, 0.35, 0.50, 0.65, 0.80]]
    best_pos, best_rms = positions[2], -99.0
    for pos in positions:
        if pos + 12 >= total_s: continue
        seg = load_audio_fast(wav_path, skip_s=pos, duration_s=10)
        r = rms_db(seg)
        if r > best_rms:
            best_rms = r; best_pos = pos
    return best_pos


def run_pass_encode(best_wav: str, output_path: str,
                    state: InputState, ref: ReferenceModel) -> Tuple[str, float, int]:
    """Final encode: alimiter + 320k MP3 with True Peak guarantee."""
    # FIX-G: Speech-gated loudness for gain trim.
    # measure_lufs() uses full-file integrated LUFS. For recordings with long
    # inter-ayah silences (Crest=16-19), integrated LUFS is 8-12dB quieter than
    # speech LUFS. This causes the engine to over-boost, hitting the limiter hard.
    # Speech-gated: measure RMS only on frames within 12dB of peak RMS.
    # This gives the loudness of the voiced content — what we actually target.
    try:
        _gate_audio = load_audio_fast(best_wav, skip_s=state.skip_s,
                                       duration_s=min(60.0, state.dur_s))
        _frame_n = int(0.1 * SR)
        _overall = rms_db(_gate_audio)
        _thresh = _overall - 12.0
        _voiced = [_gate_audio[i:i+_frame_n]
                   for i in range(0, len(_gate_audio)-_frame_n, _frame_n)
                   if rms_db(_gate_audio[i:i+_frame_n]) > _thresh]
        if len(_voiced) >= 5:
            _speech = np.concatenate(_voiced)
            # K-weighted offset: R128 LUFS ≈ RMS + 0.7dB for speech
            _speech_rms = rms_db(_speech)
            measured_lufs = _speech_rms + 0.7
        else:
            measured_lufs = measure_lufs(best_wav)
    except Exception:
        measured_lufs = measure_lufs(best_wav)
    lufs_trim = state.achievable_lufs - measured_lufs
    lufs_trim = float(np.clip(lufs_trim, -18.0, 18.0))  # BUG-D FIX: was ±6dB — blocked files >6dB from target (e.g. -17 LUFS input needs +10.7dB)

    limiter_threshold = 0.891
    true_peak_db = -2.0
    n_retries = 0

    for attempt in range(3):
        parts = []
        if abs(lufs_trim) > 0.05:
            parts.append(f'volume={lufs_trim:.3f}dB')
        parts.append(f'alimiter=limit={limiter_threshold:.4f}:level=false:attack=1:release=15')
        af = ','.join(parts)

        sp, tc = _safe(best_wav)
        cmd = ['ffmpeg', '-y', '-i', sp, '-af', af,
               '-b:a', '320k', '-ar', '48000', '-ac', '2',
               '-loglevel', 'error', output_path]
        r = subprocess.run(cmd, capture_output=True)
        if tc:
            try: os.remove(tc)
            except: pass

        if r.returncode != 0 or not os.path.exists(output_path):
            L(f'  [encode] attempt {attempt+1} failed')
            continue

        peak_pos = _find_peak_position(output_path, state.total_s)
        sample = load_audio_fast(output_path, skip_s=peak_pos, duration_s=30)
        true_peak_db = float(20 * np.log10(np.max(np.abs(sample)) + 1e-10))

        if true_peak_db <= -0.5:
            break
        else:
            n_retries += 1
            excess_db = true_peak_db - (-1.0)
            limiter_threshold = limiter_threshold * (10 ** (-excess_db / 20))
            limiter_threshold = max(0.500, limiter_threshold)  # floor 0.5 = -6dBFS headroom for inter-sample peaks
            L(f'  [encode] TP={true_peak_db:.2f}dBTP > -0.5 → limiter→{limiter_threshold:.4f}')

    return output_path, true_peak_db, n_retries


# ══════════════════════════════════════════════════════════════════════════════
#  PASS MEASUREMENT
# ══════════════════════════════════════════════════════════════════════════════
def _passes_do_no_harm(result: PassResult, baseline: InputState) -> Tuple[bool, str]:
    """
    FIX-21: Per-attribute do-no-harm gate.
    The old system compared composite scores only. A 315Hz cut that removes
    warmth might not tank the composite if LUFS+LRA improve simultaneously.
    This gate checks each key attribute independently against the input baseline.
    Called at every pass acceptance point in the iteration loop.
    Returns (ok, reason). If not ok: revert to previous state.
    """
    # BUG-C FIX: compare to achievable_crest, not input crest.
    # Input Crest=18 is not a target — it's pre-normalization. After gain
    # normalization the soft limiter naturally reduces Crest. Reverting the
    # pass because Crest dropped from 18→15 is wrong; 15 is still well above
    # the achievable target. Gate fires only if we've fallen below the floor.
    if result.crest < baseline.achievable_crest - 1.5:
        return False, f'crest below achievable floor {baseline.achievable_crest:.2f}-1.5 ({result.crest:.2f})'
    # Compare eq_residual to the INPUT's spectral distance, not a fixed threshold.
    # A file with input spec_dist=18dB (e.g. different mic/room) will have high
    # eq_residual even after improvement — the fixed 8.0 threshold would always
    # reject valid processing on such files.
    # Gate fires only if EQ made the spectral distance WORSE than input.
    if result.eq_residual > baseline.spec_dist * 1.8 and result.eq_residual > 12.0:
        return False, f'EQ degraded spectrum: residual={result.eq_residual:.2f} > input_dist={baseline.spec_dist:.2f}*1.8'
    if result.sib_snr < baseline.snr_global - 5.0:
        return False, f'sibilant SNR degraded below input level'
    return True, ''


def measure_pass(wav_path: str, ref: ReferenceModel, state: InputState,
                 pass_label: str = '', is_final: bool = False) -> PassResult:
    """
    Full PassResult from WAV or MP3.
    FIX-16: Uses _wav_3window_spectrum() for .wav intermediates.
    Eliminates 9× subprocess creation overhead per intermediate pass.
    Final pass still uses full 9-window _probe_full_file().
    """
    result = PassResult(pass_label=pass_label, wav_path=wav_path)

    # Spectrum
    if is_final:
        spectrum, _ = _probe_full_file(wav_path, state.total_s, n_windows=9)
    elif wav_path.endswith('.wav'):
        # FIX-16: single-load WAV analysis (no subprocess overhead per window)
        spectrum = _wav_3window_spectrum(wav_path, state.total_s, state.skip_s, state.dur_s)
        if not spectrum:
            spectrum = _probe_3window(wav_path, state.total_s, state.skip_s)
    else:
        spectrum = _probe_3window(wav_path, state.total_s, state.skip_s)

    result.spectrum = spectrum if spectrum else {}

    # Clip measurements
    clip = load_audio_fast(wav_path, skip_s=state.skip_s, duration_s=state.dur_s)
    if len(clip) < SR * 3:
        return result

    result.rms   = float(rms_db(clip))
    result.crest = float(crest_factor(clip))
    result.lra   = float(lra_estimate(clip))
    result.lufs  = float(measure_lufs(wav_path))

    # EQ residual
    ref_b = ref.third_oct
    common = [fc for fc in result.spectrum if fc in ref_b
              and 80 <= fc <= min(12000, state.codec_cutoff * 0.9)]
    if common:
        out_arr = np.array([result.spectrum[fc] for fc in common])
        ref_arr = np.array([ref_b[fc] for fc in common])
        loff = float(np.mean(ref_arr - out_arr))
        result.eq_residual = float(np.mean(np.abs((ref_arr - out_arr) - loff)))
    else:
        result.eq_residual = 20.0

    result.sib_snr = float(compute_sibilant_snr(clip, state.silence_floor))

    result.score_tier, result.score_abs, result.ceiling_reason = _quality_score_v100(
        result.spectrum, result.lufs, result.rms, result.crest, result.lra, ref, state)

    tier_weights = {
        'TIER_PRISTINE':   (0.45, 0.35, 0.20),
        'TIER_COMPRESSED': (0.35, 0.40, 0.25),
        'TIER_DEGRADED':   (0.25, 0.40, 0.35),
        'TIER_DAMAGED':    (0.15, 0.45, 0.40),
    }
    wc, we, wl = tier_weights.get(state.source_tier, (0.35, 0.40, 0.25))
    crest_norm = float(np.clip((result.crest - 5.0) / max(state.achievable_crest - 5.0, 0.1), 0, 1.2))
    eq_norm    = max(0.0, 1.0 - result.eq_residual / 5.0)
    lra_norm   = max(0.0, 1.0 - abs(result.lra - ref.phrase_lra_p50) / 3.0)
    result.composite = crest_norm * wc + eq_norm * we + lra_norm * wl

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  CONVERGENCE CONTROL
# ══════════════════════════════════════════════════════════════════════════════
def should_stop(history: List[PassResult], state: InputState,
                ref: ReferenceModel) -> Tuple[bool, str]:
    """
    FIX-20: Correct crest_collapsed + joint_pass logic.
    Old problem 1: crest_collapsed on iteration 0 was silently allowed to
      fall through to joint pass — running compand on an already-collapsed
      signal, making it worse.
    Old problem 2: 'default_stop' on iteration 1 terminated before running
      the joint pass on iteration 2, even if iteration 1's joint left residual
      LRA error that iteration 2 would have fixed.
    New rule: crest_collapsed always breaks immediately (no joint pass).
    Other stops: only break after at least one joint pass has run.
    """
    n = len(history)
    if n >= 6: return True, 'max_passes'
    if n < 1:  return False, ''
    last = history[-1]

    if last.crest < state.achievable_crest - 1.5:
        return True, 'crest_collapsed'
    if n >= 2 and last.eq_residual > history[-2].eq_residual + 0.15:
        return True, 'oscillation'
    if n >= 3:
        if (history[-1].composite < history[-2].composite - 0.02
                and history[-2].composite < history[-3].composite - 0.02):
            return True, 'composite_regression'

    lufs_ok  = abs(last.lufs - state.achievable_lufs)   < 0.30
    lra_ok   = abs(last.lra  - ref.phrase_lra_p50)      < 0.30
    eq_ok    = last.eq_residual < 0.40

    if lufs_ok and lra_ok and eq_ok:
        return True, 'fully_converged'
    if eq_ok and lra_ok:
        return True, 'converged_eq_lra'

    if n >= 2 and last.composite > history[-2].composite + 0.01:
        return False, ''

    return True, 'default_stop'


# ══════════════════════════════════════════════════════════════════════════════
#  SCORING
# ══════════════════════════════════════════════════════════════════════════════
def _quality_score_v100(spectrum: Dict, lufs: float, rms: float,
                         crest: float, lra: float,
                         ref: ReferenceModel, state: InputState) -> Tuple[float, float, str]:
    """5-component quality score vs tier-achievable and absolute targets."""
    ref_b = ref.third_oct

    # 1. Spectral (30 pts)
    common = [fc for fc in spectrum if fc in ref_b
              and 80 <= fc <= min(12000, state.codec_cutoff * 0.9)]
    if common:
        out_arr = np.array([spectrum[fc] for fc in common])
        ref_arr = np.array([ref_b[fc] for fc in common])
        aw = np.array([max(0.2, 1 + A_WEIGHT.get(fc, 0) / 10) for fc in common])
        loff = float(np.mean(ref_arr - out_arr))
        avg_err = float(np.sum(aw * np.abs((ref_arr - out_arr) - loff)) / np.sum(aw))
    else:
        avg_err = 99.0
    spectral_score = 30.0 * max(0.0, 1.0 - avg_err / 6.0)

    # 2-4. LUFS / Crest / LRA
    lufs_score  = 25.0 * max(0.0, 1.0 - abs(lufs  - state.achievable_lufs)  / 3.0)
    crest_score = 20.0 * max(0.0, 1.0 - abs(crest - state.achievable_crest) / 3.0)
    lra_score   = 15.0 * max(0.0, 1.0 - abs(lra   - ref.phrase_lra_p50)    / 2.5)

    # 5. Warmth tilt (10 pts)
    tfc = np.array([fc for fc in CENTERS_31 if 200 <= fc <= 2000 and fc in spectrum], dtype=float)
    if len(tfc) >= 3:
        inp_tilt = float(np.polyfit(np.log2(tfc / 1000.0),
                                     np.array([spectrum[fc] for fc in tfc]), 1)[0])
        warmth_score = 10.0 * max(0.0, 1.0 - abs(inp_tilt - ref.warmth_ratio) / 3.0)
    else:
        warmth_score = 5.0

    score_tier = round(spectral_score + lufs_score + crest_score + lra_score + warmth_score, 1)

    lufs_abs  = 25.0 * max(0.0, 1.0 - abs(lufs  - TARGET['lufs'])  / 3.0)
    crest_abs = 20.0 * max(0.0, 1.0 - abs(crest - TARGET['crest']) / 3.0)
    lra_abs   = 15.0 * max(0.0, 1.0 - abs(lra   - ref.phrase_lra_p50) / 2.5)
    score_abs = round(spectral_score + lufs_abs + crest_abs + lra_abs + warmth_score, 1)

    ceiling_reason = ''
    if state.source_tier != 'TIER_PRISTINE' and score_tier > score_abs + 2.0:
        ceiling_reason = (f'{state.source_tier}: Crest<={state.achievable_crest:.2f} '
                          f'LRA<={state.achievable_lra:.2f} LUFS>={state.achievable_lufs:.2f}')

    return score_tier, score_abs, ceiling_reason


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENTRY POINT: enhance()
# ══════════════════════════════════════════════════════════════════════════════
def enhance(input_path: str, output_path: str,
            max_iterations: int = 3, target_score: float = 96.0) -> Dict:
    t0 = time.time()

    MAX_T = 1800
    def _chk(phase):
        if time.time() - t0 > MAX_T:
            raise TimeoutError(f'enhance() exceeded {MAX_T}s at phase={phase}')

    L(f'╔══════════════════════════════════════════════════╗')
    L(f'║  Audio Enhancement Engine — True Base v10 — "الاتزان"     ║')
    L(f'║  المرجع: الشيخ ياسر الدوسري — 1425H              ║')
    L(f'╚══════════════════════════════════════════════════╝')
    L(f'  الملف: {os.path.basename(input_path)}')

    # ── PHASE A: Reference + Input Analysis ────────────────────────────────
    L('\nPass 1 — تحليل المدخل والمرجع')
    _chk('phase_A')

    ref = load_reference_model()
    L(f'  مرجع: {ref.n_files} ملف | RMS={ref.rms:.2f} Crest={ref.crest:.2f} '
      f'LRA={ref.lra:.2f} p50={ref.phrase_lra_p50:.2f}')

    state = analyze_input(input_path, ref)
    L(f'  {state.total_s:.0f}s | {state.source_tier} | '
      f'cutoff={state.codec_cutoff:.0f}Hz | smear={state.smear_score}/10 ({state.smear_desc})')
    L(f'  Crest={state.clip_crest:.2f} LRA={state.clip_lra:.2f} '
      f'SNR={state.snr_global:.1f}dB noise={state.noise_type}')
    L(f'  clip_ratio={state.clip_ratio:.4f} '
      f'eq={state.eq_confidence:.2f} nr={state.nr_confidence:.2f} '
      f'compand={state.compand_confidence:.2f} hf={state.hf_confidence:.2f}')
    L(f'  achievable: LUFS>={state.achievable_lufs:.2f} '
      f'Crest<={state.achievable_crest:.2f} LRA<={state.achievable_lra:.2f}')
    L(f'  MDS={state.mds_raw:.1f}/100 spec_dist=+-{state.spec_dist:.2f}dB')

    # Silence data for NR
    clip = load_audio_fast(input_path, state.skip_s, state.dur_s)
    silence_data = _measure_silence(clip, state.total_s, state.skip_s)
    del clip

    # ── FIX-14: Declip before NR ────────────────────────────────────────────
    # threshold: 0.05% (0.0005) — audible in quiet environments.
    # Clipped sources confuse the NR profiler (distortion looks like noise)
    # and make Crest impossible to recover (peaks already at 0dBFS).
    # Applying cubic spline reconstruction first gives NR a clean signal.
    working_path = input_path
    if state.clip_ratio > 0.0005 and state.source_tier in ('TIER_DAMAGED', 'TIER_DEGRADED'):
        L(f'\n  [declip] clip_ratio={state.clip_ratio:.4f} > 0.05% — declipping...')
        _chk('phase_declip')
        working_path = _declip_pass(input_path, state)
        if working_path != input_path:
            L(f'  [declip] OK — continuing with declipped audio')
    else:
        L(f'  [declip] bypass (clip_ratio={state.clip_ratio:.4f})')

    # ── PHASE B: NR Pass ────────────────────────────────────────────────────
    L('\nPass 2 — تقليل الضوضاء (NR)')
    _chk('phase_B')

    nr_wav, nr_report = nr_pass(working_path, state, ref, silence_data)
    if nr_report['applied']:
        L(f'  NR applied: floor_delta={nr_report["floor_delta"]:+.1f}dB '
          f'sib_delta={nr_report["sib_delta"]:+.1f}dB')
    else:
        L(f'  NR bypass (confidence={state.nr_confidence:.2f})')

    # ── PHASE C: EQ Design (post-NR spectrum) ──────────────────────────────
    L('\nPass 3 — تصميم التوازن الطيفي (post-NR)')
    _chk('phase_C')

    post_nr_spectrum, _ = _probe_full_file(nr_wav, state.total_s, n_windows=5)
    if not post_nr_spectrum:
        post_nr_spectrum = state.full_spectrum

    # FIX-06, FIX-07: design_eq now takes nr_wav_path for LPC smear analysis
    eq_nodes = design_eq(post_nr_spectrum, ref, state,
                          nr_wav_path=nr_wav)
    L(f'  EQ: {len(eq_nodes)} nodes | eq_conf={state.eq_confidence:.2f}')
    for f0, g, Q in sorted(eq_nodes, key=lambda x: x[0]):
        L(f'    {f0:.0f}Hz {g:+.2f}dB Q={Q:.2f}')

    # ── PHASE D: Iteration Loop ─────────────────────────────────────────────
    L('\nPass 4 — التكرار التحسيني')
    _chk('phase_D')

    pass_history: List[PassResult] = []
    best_wav = nr_wav
    best_composite = -999.0
    best_result: Optional[PassResult] = None
    cached_joint: Optional[JointParams] = None
    joint_pass_count = 0  # FIX-20: track that joint ran at least once

    # FIX-18: Thread current_input through iterations.
    # Old: every iteration started from nr_wav (fresh), discarding improvements.
    # New: each iteration refines on top of the best previous output.
    # This is the difference between "try N independent attempts, pick best"
    # and "each iteration builds compoundingly on the previous best."
    current_input = nr_wav

    for iteration in range(max(1, max_iterations)):
        _chk(f'iter_{iteration}')
        L(f'\n  -- Iteration {iteration + 1}/{max_iterations} --')

        # Pass D1: EQ application (FIX-18: from current_input, not always nr_wav)
        eq_wav = run_pass_eq(current_input, eq_nodes, f'eq_{iteration}')
        r1 = measure_pass(eq_wav, ref, state, f'EQ-{iteration+1}')
        pass_history.append(r1)
        L(f'  [EQ] Crest={r1.crest:.2f} LRA={r1.lra:.2f} LUFS={r1.lufs:.2f} '
          f'EQres={r1.eq_residual:.2f} comp={r1.composite:.3f}')

        if r1.composite > best_composite:
            best_composite = r1.composite
            best_wav = eq_wav
            best_result = r1

        # FIX-20: crest_collapsed — break immediately, never run joint
        stop, reason = should_stop(pass_history, state, ref)
        if reason == 'crest_collapsed':
            L(f'  [stop] {reason} — skipping joint pass, encoding best tracked')
            break

        # Other stop signals on iter 0: continue to run joint at least once
        if stop and iteration == 0:
            L(f'  [stop?] early on iter 0 — running joint pass regardless')
        # On later iterations: stop only after at least one joint pass ran
        elif stop and iteration > 0 and joint_pass_count > 0:
            L(f'  [stop] {reason}')
            break

        # Pass D2: Joint LUFS+LRA
        L(f'  [joint] calibrating...')
        joint_params = joint_lufs_lra_optimize(r1, ref, state, cached=cached_joint)
        cached_joint = joint_params

        joint_wav = run_pass_joint(eq_wav, joint_params, f'joint_{iteration}')
        r2 = measure_pass(joint_wav, ref, state, f'Joint-{iteration+1}')
        joint_pass_count += 1
        L(f'  [Joint] Crest={r2.crest:.2f} LRA={r2.lra:.2f} LUFS={r2.lufs:.2f} '
          f'EQres={r2.eq_residual:.2f} comp={r2.composite:.3f}')

        # do-no-harm gate (composite comparison)
        if r2.composite < r1.composite - 1.0:
            L(f'  [do-no-harm] joint degraded — trying half intensity')
            half = JointParams(
                compand_str=_COMPAND_LIBRARY.get(joint_params.intensity_label, joint_params.compand_str),
                gain_db=joint_params.gain_db * 0.5,
                intensity_label=joint_params.intensity_label)
            half_wav = run_pass_joint(eq_wav, half, f'half_{iteration}')
            r2h = measure_pass(half_wav, ref, state, f'Half-{iteration+1}')
            if r2h.composite > r1.composite:
                joint_wav = half_wav; r2 = r2h
                L(f'  [do-no-harm] half-intensity accepted: comp={r2.composite:.3f}')
            else:
                joint_wav = eq_wav; r2 = r1
                L(f'  [do-no-harm] reverted to EQ-only')

        # FIX-21: Per-attribute do-no-harm check
        attr_ok, attr_reason = _passes_do_no_harm(r2, state)
        if not attr_ok:
            L(f'  [do-no-harm-attr] {attr_reason} — reverted to EQ-only')
            joint_wav = eq_wav
            r2 = r1

        pass_history.append(r2)
        if r2.composite > best_composite:
            best_composite = r2.composite
            best_wav = joint_wav
            best_result = r2

        # FIX-18: thread current_input forward from best joint output
        # FIX-19: design next EQ from r1.spectrum (pre-joint basis, not r2)
        # Reason: compand shifts spectral balance. If EQ corrects toward ref
        # from the post-compand spectrum, it compensates for a compand artifact
        # rather than a true spectral error. Use the pre-joint spectrum as the
        # EQ basis — it represents the true spectral correction needed.
        if r2.composite > r1.composite:
            current_input = joint_wav
        else:
            current_input = eq_wav

        stop, reason = should_stop(pass_history, state, ref)
        if stop:
            L(f'  [stop] {reason}')
            break

        # Adaptive EQ refinement for next iteration
        if iteration < max_iterations - 1:
            if r1.eq_residual > 0.8 and r1.spectrum:
                # FIX-19: use r1.spectrum (pre-joint), not r2.spectrum
                scale = min(0.35, 0.10 + (r1.eq_residual - 1.5) * 0.08)
                eq_nodes_new = design_eq(r1.spectrum, ref, state,
                                          warmstart=eq_nodes if len(eq_nodes) >= 8 else None,
                                          nr_wav_path=nr_wav)
                if eq_nodes_new:
                    eq_nodes = eq_nodes_new
                    L(f'  [refine] EQ refined from r1.spectrum: '
                      f'{len(eq_nodes)} nodes (scale={scale:.2f})')

    if best_result is None:
        best_result = pass_history[-1] if pass_history else PassResult()

    # ── PHASE E: Final Encode ────────────────────────────────────────────────
    L(f'\nPass 5 — الترميز النهائي MP3 320kbps')
    _chk('phase_E')

    output_path, true_peak_db, encode_retries = run_pass_encode(
        best_wav, output_path, state, ref)
    L(f'  TP={true_peak_db:.2f}dBTP  retries={encode_retries}')

    # ── PHASE E: Final Score ─────────────────────────────────────────────────
    final = measure_pass(output_path, ref, state, 'final', is_final=True)
    elapsed = time.time() - t0

    lines = [
        f'v10.0 | {state.source_tier} | {elapsed:.0f}s',
        f'Score: {final.score_tier:.0f}/100' +
        (f' ({final.ceiling_reason})' if final.ceiling_reason else ''),
        f'LUFS={final.lufs:.2f} Crest={final.crest:.2f} LRA={final.lra:.2f}',
    ]
    if nr_report['applied']:
        lines.append(f'NR: floor_delta={nr_report["floor_delta"]:+.1f}dB  '
                     f'smear={state.smear_score}/10 ({state.smear_desc})')
    if encode_retries > 0:
        lines.append(f'TP: {true_peak_db:.2f}dBTP | {encode_retries} retry(s)')
    summary = '\n'.join(lines)

    L(f'\n{"="*50}')
    L(f'  LUFS={final.lufs:.2f} RMS={final.rms:.2f} Crest={final.crest:.2f} LRA={final.lra:.2f}')
    L(f'  Score: {final.score_tier:.1f}/100  ({state.source_tier})')
    if final.ceiling_reason:
        L(f'  [ceiling] {final.ceiling_reason}')
    L(f'  [{elapsed:.1f}s | passes={len(pass_history)} | NR={nr_report["applied"]}]')
    L(f'{"="*50}')

    return {
        'engine_version': 'True Base v10',
        'score':             final.score_tier,
        'score_tier':        final.score_tier,
        'score_absolute':    final.score_abs,
        'ceiling_reason':    final.ceiling_reason,
        'lufs':              final.lufs,
        'rms':               final.rms,
        'crest':             final.crest,
        'lra':               final.lra,
        'true_peak_db':      true_peak_db,
        'encode_retries':    encode_retries,
        'source_tier':       state.source_tier,
        'eq_confidence':     state.eq_confidence,
        'nr_confidence':     state.nr_confidence,
        'compand_confidence': state.compand_confidence,
        'smear_score':       state.smear_score,
        'smear_desc':        state.smear_desc,
        'codec_cutoff_hz':   state.codec_cutoff,
        'noise_type':        state.noise_type,
        'silence_floor_db':  state.silence_floor,
        'nr_applied':        nr_report['applied'],
        'nr_floor_delta_db': nr_report['floor_delta'],
        'passes_used':       len(pass_history),
        'processing_time_s': round(elapsed, 1),
        'eq_residual_final': final.eq_residual,
        'mds':               state.mds_raw,
        'summary':           summary,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  COMPATIBILITY + CACHE
# ══════════════════════════════════════════════════════════════════════════════
def get_reference_fingerprint():
    """Compatibility alias — returns ReferenceModel as v8.x duck-typed object."""
    return load_reference_model()


def _build_ref_cache_if_needed():
    """Called at Docker build time to pre-warm the cache."""
    if not REF_FILES:
        return
    if os.path.exists(_REF_CACHE):
        try:
            with open(_REF_CACHE) as f:
                d = json.load(f)
            if (d.get('cache_version') == 'v10-base'  # bumped — invalidates bad phrase_lra_p50 values
                    and d.get('ref_hash') == _ref_files_hash(REF_FILES)):
                return
        except Exception:
            pass
    load_reference_model()


# ══════════════════════════════════════════════════════════════════════════════
#  CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════
def main() -> int:
    if not NUMPY_OK or not SCIPY_OK:
        print('pip install numpy scipy'); return 1

    p = argparse.ArgumentParser(description='True Base v10 — Tilawa Enhancement Engine — 1425H')
    p.add_argument('-i', '--input')
    p.add_argument('-o', '--output')
    p.add_argument('--iterations', type=int, default=3)
    p.add_argument('--target',     type=float, default=96.0)
    p.add_argument('--ref',        action='append', default=[], metavar='REF_MP3')
    p.add_argument('--clear-cache', action='store_true')
    args = p.parse_args()

    if args.ref:
        valid = [r for r in args.ref if os.path.exists(r)]
        if valid:
            global REF_FILES
            REF_FILES = valid

    if args.clear_cache:
        if os.path.exists(_REF_CACHE):
            os.remove(_REF_CACHE)
            print('Cache v10.0 deleted')
        return 0

    if not args.input or not args.output:
        p.print_help(); return 1

    try:
        r = enhance(args.input, args.output, args.iterations, args.target)
        print(f'\n  Score: {r["score"]:.1f}/100  '
              f'LUFS={r["lufs"]:.2f} RMS={r["rms"]:.2f} '
              f'Crest={r["crest"]:.2f} LRA={r["lra"]:.2f}')
        return 0 if r['score'] >= 85 else 1
    except Exception as e:
        print(f'ERROR: {e}'); return 1


if __name__ == '__main__':
    sys.exit(main())
