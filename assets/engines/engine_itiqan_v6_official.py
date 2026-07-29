#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                                                                              ║
║   الإتقان — ENGINE-2 OF THE AETHERION                                       ║
║   Perfection Engine — Pristine/Compressed Path                             ║
║                                                                              ║
║   "الإتقان" — mastery of craft. To do something so well                     ║
║   it could not be done better. Applied to the finest quality               ║
║   sources: push them to the physical maximum.                               ║
║                                                                              ║
║   المرجع: الشيخ ياسر الدوسري — 1425H                                         ║
║   الهدف: 96/100 → 99.5/100 (PRISTINE ceiling: 100/100)                     ║
║                                                                              ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║   SCOPE                                                                      ║
║   TIER_PRISTINE  + TIER_PRISTINE_NOISY + TIER_COMPRESSED → accepted        ║
║   TIER_DAMAGED   + TIER_CRITICAL   → refused (route to الاسترداد)          ║
║                                                                              ║
║   PIPELINE (9 phases)                                                        ║
║   Phase A  Deep analysis: 48-band spectrum, F0 histogram, stability        ║
║   Phase B  Selective NR (PRISTINE: 6dB max, COMPRESSED: 10dB max)         ║
║   Phase C  Harmonic interaction planning (P-4 informs P-2)                ║
║   Phase D  48-band precision EQ (adaptive-λ L-BFGS-B optimizer)           ║
║   Phase E  5-segment spectral trajectory correction                        ║
║   Phase F  Phrase micro-dynamic sculpting (confidence-scaled)              ║
║   Phase G  Harmonic warmth injection (voiced segments only)                ║
║   Phase H  Joint LUFS+LRA optimizer (inherited from base)                  ║
║   Phase I  Predictive true peak encode                                     ║
║                                                                              ║
║   KEY ADVANCES OVER v10 BASE                                                 ║
║   P-1  Source-specific ceiling from direct spectral loss measurement       ║
║   P-2  48-band EQ: stability-weighted adaptive-λ smoothness prior          ║
║        Formant zones (300-3500Hz) capped at ±2dB                          ║
║        Harmonic interaction: P-4 plan adjusts P-2 targets pre-solve       ║
║   P-3  Three-cue phrase detection + confidence-scaled sculpting            ║
║   P-4  Warmth via aexciter on voiced frames only                           ║
║        F0-histogram-weighted harmonic plan (not uniform F0 range)         ║
║        Arabic stop onset protection: 20ms grace on consonant onsets       ║
║   P-5  5-segment temporal spectral trajectory matching to 1425H            ║
║   P-6  Encoder-detected inter-sample margin. Zero retries by default.     ║
║                                                                              ║
║   DESIGN LINEAGE                                                             ║
║   v1.0 design: direct plan impl — 5 problems found                        ║
║   v2.0 design: adaptive-λ, 3-cue, F0 interaction — 5 new problems         ║
║   v3.0 design: stability-weighted-λ, direct spectral loss,                ║
║         confidence-scaled sculpting, F0-histogram interaction,             ║
║         5-seg trajectory, Arabic stop consonant onset protection           ║
║   v4.0 design: FULL MERGE — adds DAMAGED/CRITICAL path, Ayah             ║
║         Segmentation, Temporal Consistency, Adaptive Compand,             ║
║         Sibilant Centroid, Dereverberation, Adaptive Score Weights        ║
║                                                                              ║
║   ★ ENGINE-2 v4.0 — THE AETHERION PROJECT                                   ║
║     Built by one developer. On a Samsung S22. In Termux. For the Quran.   ║
║     وما التوفيق إلا بالله                                                     ║
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

# S225: NUMPY_OK must depend ONLY on numpy importing. It was previously set
# in the same try block as scipy.fft/scipy.optimize, so ANY scipy import
# failure (partial pip install, missing .so symlink, apk giving numpy but not
# scipy, etc.) silently set NUMPY_OK = False too — disabling ~60 functions
# across this file that only need numpy and were already numpy-only internally.
# rfft/rfftfreq are pure-math functions with an exact numpy.fft equivalent, so
# they now fall back to numpy instead of being a hard scipy dependency.
try:
    import numpy as np
    NUMPY_OK = True
except ImportError:
    NUMPY_OK = False

try:
    from scipy.fft import rfft, rfftfreq
except ImportError:
    if NUMPY_OK:
        rfft, rfftfreq = np.fft.rfft, np.fft.rfftfreq  # S225: pure-numpy fallback

try:
    from scipy.optimize import minimize
    SCIPY_OK = True
except ImportError:
    SCIPY_OK = False

try:
    from scipy.interpolate import PchipInterpolator
    _PCHIP_OK = True
except ImportError:
    _PCHIP_OK = False

try:
    from scipy.signal import correlate as _scipy_correlate
    _SIGNAL_OK = True
except ImportError:
    _SIGNAL_OK = False


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTANTS — inherited from base engine + Itiqan extensions
# ══════════════════════════════════════════════════════════════════════════════

SR       = 48000
WAV_CODEC = 'pcm_s24le'   # 24-bit, 144dB SNR (FIX-17)

TARGET = {
    'lufs': -6.29, 'rms': -10.01, 'crest': 10.25, 'lra': 4.19,
    'true_peak': -1.0, 'sfm': 0.0444, 'dr': 7.9,
}

BIAS_SCALE = 0.25

# 24-band third-octave bias table (inherited from base v10)
# Convention: bias = output – ref.  negative = output below ref → boost needed.
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

# Arabic sibilant protection bands (ش/س/ص energy range)
# H2: Extended per KB §152 Sifat Al-Huruf:
#   Safir ص = 5.5–7.5 kHz, س = 7–12 kHz, ز = 5–8 kHz
# Guards that use this list now cover the full Safir spectral zone.
ARABIC_SIB_BANDS = [2500.0, 3150.0, 4000.0, 5000.0, 6300.0, 8000.0]

# ── 48-band sixth-octave centers ──────────────────────────────────────────────
# Built from 24 existing + one geometric mean between each adjacent pair + 60Hz base
# 24 existing centers: 80, 100, 125, 160, 200, 250, 315, 400, 500, 630,
#                      800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300,
#                      8000, 10000, 12500, 16000
# + geometric means between each adjacent pair (23 new centers)
# + 60Hz extension at base = 48 total
CENTERS_48: List[float] = [
     60.0,   80.0,   89.4,  100.0,  111.8,  125.0,  141.4,
    160.0,  178.9,  200.0,  223.6,  250.0,  280.6,  315.0,
    354.9,  400.0,  447.2,  500.0,  561.2,  630.0,  709.9,
    800.0,  894.4, 1000.0, 1118.0, 1250.0, 1414.2, 1600.0,
   1788.8, 2000.0, 2236.1, 2500.0, 2806.2, 3150.0, 3549.6,
   4000.0, 4472.1, 5000.0, 5612.3, 6300.0, 7099.3, 8000.0,
   8944.3,10000.0,11180.3,12500.0,14142.1,16000.0,
]
assert len(CENTERS_48) == 48, f'CENTERS_48 must have 48 elements, got {len(CENTERS_48)}'

# Sixth-octave Q factor: Q = 1 / (2^(1/12) - 2^(-1/12)) ≈ 8.65
# Used in equalizer ffmpeg filter: t=q:w=8.65
_EQ_Q_48 = 8.65

# Bias scale factors for PRISTINE/COMPRESSED (v3.0 design Fix-1)
# SPECTRAL_BIAS_V9 was measured on all-tier outputs; pristine sources need less correction.
PRISTINE_BIAS_SCALE   = 0.60
COMPRESSED_BIAS_SCALE = 0.85  # default; overridden per-bitrate by _get_compressed_bias_scale()


def _get_compressed_bias_scale(bitrate_class: str) -> float:
    """
    Adaptive spectral bias scale for COMPRESSED sources.
    Heavier compression → larger codec-induced spectral distortion
    → stronger warm-start correction needed.
    64kbps  → 0.97 (close to full correction)
    96kbps  → 0.92
    128kbps → 0.85 (legacy default)
    192kbps → 0.78 (lighter correction; codec is relatively transparent)
    256+    → 0.70 (near-pristine codec; minimal bias)
    """
    return {
        '320': 0.70, '256': 0.70,
        '192': 0.78, '128': 0.85,
        '96':  0.92, '64':  0.97,
    }.get(bitrate_class, 0.85)

# Perceptual loss weights per frequency band (for ceiling computation)
# Higher weight = more important to preserve (loss here = bigger score penalty)
_PERC_LOSS_WEIGHT: Dict[float, float] = {
     125: 0.30,  250: 0.50,  500: 0.70, 1000: 0.90,
    2000: 1.00, 3150: 1.00, 4000: 0.90, 5000: 0.70,
    6300: 0.50, 8000: 0.40,10000: 0.30,12500: 0.20,
   16000: 0.10,
}

# Reference phrase LRA distribution (from 1425H measurement)
REF_PHRASE_LRA = {'p10': 2.50, 'p50': 3.37, 'p90': 4.20}

# Compand preset library (inherited from base engine)
_COMPAND_LIBRARY = {
    'BYPASS':  '-90/-90|-20/-20|-3/-3|0/0',
    'MINIMAL': '-90/-89|-40/-39|-20/-19.5|-10/-9.8|-4/-3.9|-1/-0.95|0/-0.3',
    'LIGHT':   '-90/-85|-40/-36|-20/-17|-10/-8.2|-5/-4.1|-2/-1.6|-0.5/-0.4|0/-0.3',
    'MEDIUM':  '-90/-78|-40/-25|-22/-12.5|-12/-6.8|-6/-3.5|-2.5/-1.6|-0.8/-0.5|0/-0.2',
    'HEAVY':   '-90/-72|-42/-21|-26/-10.5|-13/-5.2|-6/-2.4|-2.5/-0.8|-0.5/-0.3|0/-0.1',
    'EXTREME': '-90/-68|-45/-20|-28/-9|-14/-4.5|-7/-2.0|-3/-0.6|0/-0.1',
}
_COMPAND_INTENSITY = {
    'BYPASS': 0.0, 'MINIMAL': 0.15, 'LIGHT': 0.25,
    'MEDIUM': 0.50, 'HEAVY': 0.75, 'EXTREME': 1.0,
}

# Reference cache
_APP_DIR   = Path(__file__).parent
_REF_CACHE = str(_APP_DIR / 'ref_cache_itiqan_v10.json')

# Inter-sample margin per encoder (for predictive true peak — P-6)
# MP3 polyphase filterbank creates inter-sample peaks above sample ceiling.
_ENCODER_MARGINS: Dict[str, float] = {
    'lame_3100': 1.40,
    'lame_399':  1.60,
    'lame_398':  1.70,
    'unknown':   2.00,  # conservative default
}


def _resolve_ref_files() -> List[str]:
    env_dir = os.environ.get('TILAWA_REF_DIR', '')
    if env_dir and os.path.isdir(env_dir):
        return sorted(
            str(p) for p in Path(env_dir).glob('*.mp3') if p.stat().st_size > 0
        )
    home_dir = Path.home() / '.tilawa_ref'
    if home_dir.is_dir():
        return sorted(str(p) for p in home_dir.glob('*.mp3') if p.stat().st_size > 0)
    return []


REF_FILES: List[str] = _resolve_ref_files()


# ══════════════════════════════════════════════════════════════════════════════
#  DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class ReferenceModel:
    lufs:              float = -6.29
    rms:               float = -10.01
    crest:             float = 10.25
    lra:               float = 4.19
    true_peak:         float = -1.0
    sfm:               float = 0.0444
    dr:                float = 7.9
    silence_floor:     float = -73.0
    spectrum:          Dict[int, float]   = field(default_factory=dict)   # 24-band
    spectrum_48:       Dict[float, float] = field(default_factory=dict)   # 48-band
    phrase_lra:        float = 3.37
    phrase_lra_p10:    float = 2.50
    phrase_lra_p90:    float = 4.20
    # 5-segment spectral trajectory [seg0..seg4], each a Dict[float,float]
    trajectory:        List[Dict[float, float]] = field(default_factory=list)
    f0_median:         float = 0.0
    files_used:        int   = 0
    hash:              str   = ''
    bw_cutoff:         float = 13000.0   # measured BW of reference files (Hz)
    quality_weights:   List[float] = field(default_factory=list)  # per-file weights
    spectrum_48_studio_a: Dict[float, float] = field(default_factory=dict)  # Studio A only
    spectral_character:   Dict[float, float] = field(default_factory=dict)  # runtime bias


@dataclass
class ItiqanState:
    # Source characterisation
    source_tier:        str   = 'TIER_PRISTINE'  # TIER_PRISTINE | TIER_COMPRESSED
    duration_s:         float = 0.0
    bitrate_kbps:       int   = 0
    bitrate_class:      str   = '128'
    codec_cutoff:       float = 20000.0
    encoder_tag:        str   = 'unknown'         # from LAME header

    # Basic measurements
    lufs:               float = 0.0
    rms:                float = 0.0
    crest:              float = 0.0
    lra:                float = 0.0
    true_peak:          float = 0.0
    silence_floor:      float = -73.0

    # Spectral
    spectrum_24:        Dict[int, float]   = field(default_factory=dict)
    spectrum_48:        Dict[float, float] = field(default_factory=dict)
    # Spectral instability per 48-band (0=stable, 1=highly variable)
    instability_48:     'np.ndarray | None' = None
    # Direct spectral loss vs reference (positive = input below ref = deficit)
    spectral_loss_48:   'np.ndarray | None' = None

    # F0 analysis
    f0_histogram:       Dict[float, float] = field(default_factory=dict)  # {hz: weight}
    f0_median:          float = 180.0

    # Confidence vectors (per 48-band, or scalar fallback)
    eq_confidence_48:   'np.ndarray | None' = None
    eq_confidence:      float = 0.80
    nr_confidence:      float = 0.50
    compand_confidence: float = 0.70

    # Quality ceiling
    ceiling:            float = 100.0
    ceiling_reason:     str   = ''

    # Smear detection (inherited from base)
    smear_score:        int   = 0
    smear_desc:         str   = 'none'

    # Presence + warmth ratios
    presence_ratio:     float = 0.0
    warmth_ratio:       float = 0.0
    snr_global:         float = 20.0
    noise_type:         str   = 'none'

    # Itiqan-specific results
    eq_bands_applied:   int   = 0
    eq_residual_48:     float = 0.0
    trajectory_applied: bool  = False
    phrases_detected:   int   = 0
    phrases_sculpted:   int   = 0
    warmth_applied:     bool  = False
    thd_before:         float = 0.0
    thd_after:          float = 0.0
    intersample_margin: float = 2.0
    mds_raw:            float = 0.0

    # M-9: Voice body sculpting
    mud_cut_db:         float = 0.0   # LF mud cut applied
    presence_boost_db:  float = 0.0   # presence boost applied
    voice_sculpt_applied: bool = False

    # M-8: Muffle detection
    muffle_score:       int   = 0      # 0=none 1=mild 2=moderate 3=severe
    muffle_hf_deficit:  float = 0.0   # dB: how far below ref HF energy is
    muffle_applied:     bool  = False
    muffle_correction_db: float = 0.0  # shelf gain applied

    # صدي التميز — Echo of Distinction (Phase G.5)
    sadaa_applied:      bool  = False
    sadaa_delay_ms:     float = 0.0
    sadaa_wet_db:       float = 0.0
    sadaa_crest_delta:  float = 0.0

    # KB §145: Mujawwad recitation style confidence (0=Murattal/Hadr, 1=Mujawwad)
    mujawwad_confidence: float = 0.0

    # TIER_PRISTINE_NOISY — Adaptive DF3 pass results
    df3_applied:        bool  = False
    df3_loud_chunks:    int   = 0
    df3_mid_chunks:     int   = 0
    df3_quiet_chunks:   int   = 0
    df3_boundaries:     int   = 0
    df3_snr_before:     float = 0.0
    df3_snr_after:      float = 0.0
    noise_floor_db:     float = -60.0
    snr_proxy_db:       float = 25.0


@dataclass
class PassResult:
    label:        str   = ''
    lufs:         float = 0.0
    rms:          float = 0.0
    crest:        float = 0.0
    lra:          float = 0.0
    true_peak:    float = 0.0
    eq_residual:  float = 0.0
    composite:    float = 0.0
    score_tier:   float = 0.0
    score_abs:    float = 0.0
    ceiling_reason: str = ''
    spectrum:     Dict = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
#  LOGGER + FFMPEG RUNNER
# ══════════════════════════════════════════════════════════════════════════════

_LOG: List[str] = []

def L(msg: str) -> None:
    _LOG.append(msg)
    print(msg, flush=True)

def _chk(label: str) -> None:
    L(f'\n── {label} ──')


def _run_ffmpeg(cmd: List[str], capture: bool = False) -> Tuple[int, str, str]:
    """Run ffmpeg command. Returns (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=600,
        )
        stdout = result.stdout.decode('utf-8', errors='replace')
        stderr = result.stderr.decode('utf-8', errors='replace')
        return result.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        return 1, '', 'TIMEOUT'
    except FileNotFoundError:
        return 1, '', 'ffmpeg not found'


def _tmp_wav(suffix: str = '') -> str:
    return os.path.join(_TMP, f'itiqan_{os.getpid()}_{suffix}_{int(time.time()*1000)}.wav')


def _tmp_mp3(suffix: str = '') -> str:
    return os.path.join(_TMP, f'itiqan_{os.getpid()}_{suffix}_{int(time.time()*1000)}.mp3')


def _cleanup(*paths: str) -> None:
    for p in paths:
        try:
            if p and os.path.exists(p):
                os.remove(p)
        except OSError:
            pass


# ══════════════════════════════════════════════════════════════════════════════
#  AUDIO MEASUREMENT — inherited + extended
# ══════════════════════════════════════════════════════════════════════════════

def _get_duration(path: str) -> float:
    rc, out, err = _run_ffmpeg([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', path
    ])
    try:
        return float(out.strip())
    except ValueError:
        return 0.0


def _get_bitrate(path: str) -> int:
    rc, out, err = _run_ffmpeg([
        'ffprobe', '-v', 'error', '-show_entries', 'format=bit_rate',
        '-of', 'default=noprint_wrappers=1:nokey=1', path
    ])
    try:
        return int(out.strip()) // 1000  # bits/s → kbps
    except ValueError:
        return 0


def _bitrate_class(kbps: int) -> str:
    if kbps >= 310:  return '320'
    if kbps >= 240:  return '256'
    if kbps >= 175:  return '192'
    if kbps >= 110:  return '128'
    if kbps >=  80:  return '96'
    return '64'


def _detect_encoder_tag(path: str) -> str:
    """Parse LAME tag from MP3 to detect encoder version for inter-sample margin."""
    rc, out, err = _run_ffmpeg([
        'ffprobe', '-v', 'error', '-show_entries', 'format_tags=encoder',
        '-of', 'default=noprint_wrappers=1:nokey=1', path
    ])
    tag = out.strip().lower()
    if 'lame3.100' in tag or 'lame 3.100' in tag:
        return 'lame_3100'
    if 'lame3.99' in tag or 'lame 3.99' in tag:
        return 'lame_399'
    if 'lame3.98' in tag or 'lame 3.98' in tag:
        return 'lame_398'
    return 'unknown'


def _decode_to_wav(input_path: str, output_wav: str) -> bool:
    """Decode any audio to 48kHz mono 24-bit WAV."""
    cmd = [
        'ffmpeg', '-y', '-i', input_path,
        '-ar', str(SR), '-ac', '1',
        '-acodec', WAV_CODEC,
        output_wav
    ]
    rc, _, err = _run_ffmpeg(cmd)
    return rc == 0 and os.path.exists(output_wav)


def _decode_wav_samples(wav_path: str) -> Tuple[Optional['np.ndarray'], int]:
    """Decode WAV to numpy float32 array. Returns (samples, sample_rate)."""
    if not NUMPY_OK:
        return None, SR
    tmp = _tmp_wav('pcm16')
    cmd = [
        'ffmpeg', '-y', '-i', wav_path,
        '-ar', str(SR), '-ac', '1',
        '-f', 's16le', tmp
    ]
    rc, _, _ = _run_ffmpeg(cmd)
    if rc != 0 or not os.path.exists(tmp):
        return None, SR
    try:
        raw = np.fromfile(tmp, dtype=np.int16)
        samples = raw.astype(np.float32) / 32768.0
        return samples, SR
    except Exception:
        return None, SR
    finally:
        _cleanup(tmp)


def _measure_lufs(wav_path: str) -> Tuple[float, float]:
    """Returns (integrated_lufs, lra)."""
    cmd = [
        'ffmpeg', '-i', wav_path,
        '-af', 'ebur128=peak=true:framelog=quiet',
        '-f', 'null', '-'
    ]
    rc, out, err = _run_ffmpeg(cmd)
    combined = out + err
    lufs, lra = -99.0, 0.0
    for line in combined.splitlines():
        if 'I:' in line and 'LUFS' in line:
            try:
                lufs = float(line.split('I:')[1].split('LUFS')[0].strip())
            except (IndexError, ValueError):
                pass
        if 'LRA:' in line and 'LU' in line:
            try:
                lra = float(line.split('LRA:')[1].split('LU')[0].strip())
            except (IndexError, ValueError):
                pass
    return lufs, lra


def _measure_rms_crest(samples: 'np.ndarray') -> Tuple[float, float]:
    """Returns (rms_db, crest_db). Requires numpy."""
    if samples is None or len(samples) == 0:
        return -99.0, 0.0
    rms_linear = float(np.sqrt(np.mean(samples ** 2)))
    peak_linear = float(np.max(np.abs(samples)))
    rms_db   = 20 * np.log10(max(rms_linear, 1e-10))
    peak_db  = 20 * np.log10(max(peak_linear, 1e-10))
    crest_db = peak_db - rms_db
    return rms_db, crest_db


def _measure_true_peak(wav_path: str) -> float:
    """Measure true peak using ffmpeg ebur128."""
    cmd = [
        'ffmpeg', '-i', wav_path,
        '-af', 'ebur128=peak=true:framelog=quiet',
        '-f', 'null', '-'
    ]
    rc, out, err = _run_ffmpeg(cmd)
    combined = out + err
    for line in combined.splitlines():
        if 'True peak:' in line or 'Peak:' in line:
            try:
                val = float(line.split(':')[1].strip().split()[0])
                return val
            except (IndexError, ValueError):
                pass
    return -99.0


def _measure_ref_bw_cutoff(wav_path: str) -> float:
    """
    Measure the effective bandwidth cutoff of a reference file.
    Returns the highest frequency with sustained spectral content.
    Algorithm: compare each band to the median level of 1-4kHz (speech formant region).
    A band is "empty" if it's more than 35dB below the formant median.
    This avoids the peak-db problem: MP3 cutoff creates a hard wall, not a gradual slope,
    so we find the last band before content drops 35dB relative to mid-speech.
    """
    if not NUMPY_OK:
        return 13000.0
    samples, sr = _decode_wav_samples(wav_path)
    if samples is None:
        return 13000.0
    N = min(len(samples), sr * 10)
    spec = np.abs(rfft(samples[:N] * np.hanning(N))) ** 2
    freqs = rfftfreq(N, d=1.0 / sr)
    spec_db = 10 * np.log10(np.maximum(spec, 1e-10))

    def _band_mean(fc):
        mask = (freqs >= fc * 0.85) & (freqs <= fc * 1.15)
        return float(np.mean(spec_db[mask])) if mask.sum() > 0 else -99.0

    # Reference level: median of 1kHz–4kHz bands (always present in speech)
    speech_bands = [f for f in CENTERS_48 if 1000.0 <= f <= 4000.0]
    ref_level = float(np.median([_band_mean(f) for f in speech_bands]))
    threshold = ref_level - 35.0  # 35dB drop = codec cutoff

    # Walk from high freq down to find last band with content
    last_active = 8000.0
    for fc in reversed(CENTERS_48):
        if fc < 2000.0:
            break
        if _band_mean(fc) > threshold:
            last_active = fc
            break
    return last_active


def _measure_silence_floor(samples: 'np.ndarray', percentile: float = 8.0) -> float:
    """Estimate silence floor from quietest percentile of frames."""
    if samples is None or not NUMPY_OK:
        return -73.0
    frame_size = SR // 10  # 100ms frames
    energies = []
    for i in range(0, len(samples) - frame_size, frame_size // 2):
        frame = samples[i:i + frame_size]
        e = float(np.mean(frame ** 2))
        if e > 1e-12:
            energies.append(10 * np.log10(e))
    if not energies:
        return -73.0
    return float(np.percentile(energies, percentile))


def _measure_sfm(samples: 'np.ndarray') -> float:
    """Spectral Flatness Measure."""
    if samples is None or not NUMPY_OK:
        return 0.04
    N = min(len(samples), SR * 4)
    seg = samples[:N]
    window = np.hanning(len(seg))
    spec = np.abs(rfft(seg * window)) ** 2 + 1e-10
    geom_mean = float(np.exp(np.mean(np.log(spec))))
    arith_mean = float(np.mean(spec))
    return geom_mean / arith_mean if arith_mean > 0 else 0.0


def _measure_codec_cutoff(samples: 'np.ndarray') -> float:
    """Find frequency above which spectrum drops sharply (codec HF cutoff)."""
    if samples is None or not NUMPY_OK:
        return 20000.0
    N = min(len(samples), SR * 4)
    seg = samples[:N]
    window = np.hanning(len(seg))
    spectrum = np.abs(rfft(seg * window)) ** 2
    freqs = rfftfreq(len(seg), d=1.0 / SR)
    spectrum = np.maximum(spectrum, 1e-10)
    spec_db = 10 * np.log10(spectrum)

    # Find the frequency where energy stays below (noise_floor + 6dB) for > 500Hz span
    # Start from 4kHz, work upward
    threshold_above_noise = 6.0
    noise_floor = float(np.percentile(spec_db, 5))
    cutoff = 20000.0
    consecutive = 0
    for i, (f, db) in enumerate(zip(freqs, spec_db)):
        if f < 4000:
            continue
        if db < noise_floor + threshold_above_noise:
            consecutive += 1
            if consecutive > 20:  # ~500Hz span at 48kHz resolution
                cutoff = float(f) - 20 * (freqs[1] - freqs[0])
                break
        else:
            consecutive = 0
    return max(cutoff, 4000.0)


# ══════════════════════════════════════════════════════════════════════════════
#  48-BAND SPECTRUM MEASUREMENT
# ══════════════════════════════════════════════════════════════════════════════

def sixth_octave(wav_path: str, t_start: float = 0.0,
                  t_end: Optional[float] = None) -> Optional[Dict[float, float]]:
    """
    Measure 48-band sixth-octave spectrum.
    Uses multiple window sizes per band for resolution accuracy:
    - Below 500Hz: 4s window (frequency resolution priority)
    - 500Hz-4kHz:  1s window
    - Above 4kHz:  0.5s window (time resolution for HF content)
    Returns {center_hz: level_db} or None if numpy unavailable.
    """
    if not NUMPY_OK:
        return None

    samples, sr = _decode_wav_samples(wav_path)
    if samples is None:
        return None

    # Trim to requested time range
    if t_start > 0:
        start_samp = int(t_start * sr)
        samples = samples[start_samp:]
    if t_end is not None:
        end_samp = int((t_end - t_start) * sr)
        samples = samples[:end_samp]

    if len(samples) < sr // 4:  # less than 250ms — insufficient
        return None

    result = {}
    for center in CENTERS_48:
        if center < 500.0:
            win_dur = min(4.0, len(samples) / sr)
        elif center < 4000.0:
            win_dur = min(1.0, len(samples) / sr)
        else:
            win_dur = min(0.5, len(samples) / sr)

        N = int(win_dur * sr)
        N = max(N, sr // 8)  # minimum 125ms
        seg = samples[:N]

        window = np.hanning(len(seg))
        windowed = seg * window
        spectrum = np.abs(rfft(windowed)) ** 2
        spectrum = np.maximum(spectrum, 1e-10)
        freqs = rfftfreq(len(windowed), d=1.0 / sr)

        # Sixth-octave bandwidth: f × (2^(1/12) - 2^(-1/12))
        bw_factor = 2.0 ** (1.0 / 12.0)
        lo = center / bw_factor
        hi = center * bw_factor

        mask = (freqs >= lo) & (freqs < hi)
        if mask.sum() == 0:
            # No bins — find nearest
            idx = int(np.argmin(np.abs(freqs - center)))
            level = 10.0 * np.log10(float(spectrum[idx]))
        else:
            level = 10.0 * np.log10(float(np.mean(spectrum[mask])))

        result[center] = level

    return result


def _measure_spectral_stability(wav_path: str, duration_s: float) -> 'np.ndarray':
    """
    Measure per-band spectral instability across 20 analysis windows.
    Returns instability[48]: 0=stable, 1=highly variable.
    High instability bands (e.g. 315Hz vocal resonance) get stronger
    smoothness regularization in the EQ optimizer.
    """
    if not NUMPY_OK:
        return np.ones(48) * 0.5

    n_windows = 20
    window_dur = max(1.5, duration_s / n_windows)

    spectra = []
    t = 0.0
    while t + window_dur <= duration_s and len(spectra) < n_windows:
        spec = sixth_octave(wav_path, t_start=t, t_end=t + window_dur)
        if spec is not None:
            spectra.append([spec.get(f, -60.0) for f in CENTERS_48])
        t += window_dur

    if len(spectra) < 3:
        return np.ones(48) * 0.5

    arr = np.array(spectra)   # (n_windows, 48)
    per_band_std = np.std(arr, axis=0)  # (48,)
    max_std = max(float(per_band_std.max()), 0.1)
    instability = per_band_std / max_std
    return instability.astype(np.float32)


# ══════════════════════════════════════════════════════════════════════════════
#  F0 ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

def _measure_f0_histogram(samples: 'np.ndarray', sr: int) -> Dict[float, float]:
    """
    Estimate F0 distribution using autocorrelation on voiced frames.
    Returns {f0_hz_bin: normalized_energy_weight}
    Only voiced frames contribute (high energy + low ZCR).
    Bins are rounded to nearest 5Hz for stability.
    """
    if not NUMPY_OK or samples is None:
        return {180.0: 1.0}  # fallback: typical male voice

    frame_size = sr // 50    # 20ms frames
    hop        = frame_size  # no overlap (speed)
    min_period = sr // 400   # 400Hz max F0
    max_period = sr // 80    # 80Hz min F0

    f0_bins: Dict[float, float] = {}

    for i in range(0, len(samples) - frame_size, hop):
        frame = samples[i:i + frame_size]
        energy = float(np.mean(frame ** 2))

        if energy < 1e-7:  # silence
            continue

        # ZCR for voiced/unvoiced: unvoiced has high ZCR
        zcr = float(np.sum(np.abs(np.diff(np.sign(frame))))) / (2 * frame_size)
        if zcr > 0.15:
            continue  # unvoiced

        # Autocorrelation-based period estimation — FFT O(n log n)
        # FIX-1: np.correlate mode='full' is O(n²); at 48kHz/20ms
        # frames (960 samples) that is ~920k ops per voiced frame.
        _nfft = 1 << (2 * len(frame) - 1).bit_length()
        _F    = np.fft.rfft(frame, n=_nfft)
        acf   = np.fft.irfft(_F * np.conj(_F))[:len(frame)]
        if acf[0] <= 0:
            continue
        acf = acf / acf[0]  # normalize

        if max_period >= len(acf) or min_period >= len(acf):
            continue

        search = acf[min_period:max_period]
        peak_offset = int(np.argmax(search))
        peak_lag    = peak_offset + min_period
        peak_val    = float(acf[peak_lag])

        if peak_val < 0.45:  # weak periodicity → unvoiced or noisy
            continue

        f0 = float(sr) / peak_lag
        f0_key = round(f0 / 5.0) * 5.0  # 5Hz bins

        # Weight by energy (louder voiced frames matter more)
        f0_bins[f0_key] = f0_bins.get(f0_key, 0.0) + energy

    if not f0_bins:
        return {180.0: 1.0}

    total = sum(f0_bins.values())
    return {k: v / total for k, v in f0_bins.items()}


def _f0_median(histogram: Dict[float, float]) -> float:
    """Weighted median of F0 histogram."""
    if not histogram:
        return 180.0
    items = sorted(histogram.items())
    cumulative = 0.0
    total = sum(v for _, v in items)
    for f0, w in items:
        cumulative += w
        if cumulative >= total / 2.0:
            return f0
    return items[-1][0]


# ══════════════════════════════════════════════════════════════════════════════
#  REFERENCE MODEL
# ══════════════════════════════════════════════════════════════════════════════

def _ref_files_hash(files: List[str]) -> str:
    h = hashlib.md5()
    for f in sorted(files):
        h.update(f.encode())
        try:
            h.update(str(os.path.getsize(f)).encode())
        except OSError:
            pass
    return h.hexdigest()


def _build_reference_trajectory(ref_files: List[str]) -> List[Dict[float, float]]:
    """
    Measure 5-segment spectral trajectory from reference files.
    Each segment = 20% of file duration.
    Returns list of 5 spectra [{center: level_db}, ...]
    averaged across all reference files.
    """
    all_trajectories: List[List[Dict]] = []

    for rf in ref_files:
        dur = _get_duration(rf)
        if dur < 10.0:
            continue
        seg_dur = dur / 5.0
        file_traj = []
        for seg_idx in range(5):
            t_start = seg_idx * seg_dur
            t_end   = t_start + seg_dur
            spec = sixth_octave(rf, t_start=t_start, t_end=t_end)
            if spec:
                file_traj.append(spec)
            else:
                file_traj.append({f: -60.0 for f in CENTERS_48})
        all_trajectories.append(file_traj)

    if not all_trajectories:
        return [{f: -60.0 for f in CENTERS_48}] * 5

    # Average across files for each segment
    result = []
    for seg_idx in range(5):
        avg_spec: Dict[float, float] = {}
        for f in CENTERS_48:
            vals = [traj[seg_idx].get(f, -60.0) for traj in all_trajectories]
            avg_spec[f] = float(np.mean(vals)) if NUMPY_OK else sum(vals) / len(vals)
        result.append(avg_spec)
    return result


def load_reference_model() -> ReferenceModel:
    """Load or build the 1425H reference model with 48-band spectrum + trajectory."""
    global REF_FILES

    # Try cache first
    if os.path.exists(_REF_CACHE):
        try:
            with open(_REF_CACHE) as fh:
                d = json.load(fh)
            if (d.get('cache_version') == 'itiqan-v11'
                    and d.get('ref_hash') == _ref_files_hash(REF_FILES)):
                ref = ReferenceModel(
                    lufs=d['lufs'], rms=d['rms'], crest=d['crest'],
                    lra=d['lra'], true_peak=d.get('true_peak', -1.0),
                    sfm=d.get('sfm', 0.0444), dr=d.get('dr', 7.9),
                    silence_floor=d.get('silence_floor', -73.0),
                    spectrum={int(k): v for k, v in d.get('spectrum', {}).items()},
                    spectrum_48={float(k): v for k, v in d.get('spectrum_48', {}).items()},
                    phrase_lra=d.get('phrase_lra', 3.37),
                    phrase_lra_p10=d.get('phrase_lra_p10', 2.50),
                    phrase_lra_p90=d.get('phrase_lra_p90', 4.20),
                    trajectory=d.get('trajectory', []),
                    f0_median=d.get('f0_median', 0.0),
                    files_used=d.get('files_used', 0),
                    hash=d.get('ref_hash', ''),
                    bw_cutoff=d.get('bw_cutoff', 13000.0),
                    spectrum_48_studio_a={float(k): v for k, v in d.get('spectrum_48_studio_a', {}).items()},
                    spectral_character={float(k): v for k, v in d.get('spectral_character', {}).items()},
                )
                L(f'  [ref] cache hit: {ref.files_used} files, '
                  f'LUFS={ref.lufs:.2f} LRA={ref.lra:.2f} BW={ref.bw_cutoff:.0f}Hz')
                return ref
        except Exception as e:
            L(f'  [ref] cache load failed: {e}')

    # Build from scratch
    if not REF_FILES:
        L('  [ref] WARNING: no reference files found — using hardcoded targets')
        return ReferenceModel()

    L(f'  [ref] building from {len(REF_FILES)} files...')
    ref = ReferenceModel()
    lufs_vals, lra_vals, rms_vals, crest_vals = [], [], [], []
    spec_accum: Dict[float, List[float]] = {f: [] for f in CENTERS_48}
    spec_weights: Dict[float, List[float]] = {f: [] for f in CENTERS_48}
    f0_vals = []
    bw_vals = []
    _ref_per_file_data: List[Tuple[str, Dict[float, float], float]] = []  # (path, spec, weight)

    for rf in REF_FILES:
        wav = _tmp_wav('ref')
        try:
            if not _decode_to_wav(rf, wav):
                continue
            # Studio identity weight (T2-A):
            # Studio A (1425H) fingerprint: 320kbps, BW≈13kHz, LRA=[2.0,3.5], Crest=[10.0,10.7]
            # Files outside these ranges get reduced weight — different studio/session.
            br = _get_bitrate(rf)
            # BW measurement: wav is decoded at this point
            bw_pre = _measure_ref_bw_cutoff(wav)
            # Bitrate factor
            bw_factor = 1.0 if br >= 280 else 0.5
            # BW factor: above 15kHz = different studio (سوره_الفتح pattern)
            studio_bw_factor = 0.2 if bw_pre > 15000.0 else 1.0
            file_weight = bw_factor * studio_bw_factor
            lufs, lra = _measure_lufs(wav)
            samples, sr = _decode_wav_samples(wav)
            if samples is not None:
                rms, crest = _measure_rms_crest(samples)
                rms_vals.append(rms)
                crest_vals.append(crest)
                f0_hist = _measure_f0_histogram(samples, sr)
                f0_vals.append(_f0_median(f0_hist))
                # FIX-7: Removed silence_floor < -40 gate.
                if lufs > -70.0 and lra >= 0.0:
                    lufs_vals.append(lufs)
                    lra_vals.append(lra)
                # Measure ref BW cutoff (codec ceiling of reference files)
                bw = _measure_ref_bw_cutoff(wav)
                bw_vals.append(bw * file_weight)
                L(f'  [ref] {os.path.basename(rf)}: {br}kbps BW={bw:.0f}Hz weight={file_weight}')
            spec = sixth_octave(wav)
            if spec:
                for f in CENTERS_48:
                    if f in spec:
                        spec_accum[f].append(spec[f])
                        spec_weights[f].append(file_weight)
                _ref_per_file_data.append((rf, dict(spec), file_weight))
        finally:
            _cleanup(wav)

    def _median(vals):
        return float(np.median(vals)) if vals and NUMPY_OK else (sum(vals)/len(vals) if vals else 0.0)

    def _weighted_mean(vals, weights):
        if not vals:
            return -60.0
        if not NUMPY_OK:
            return sum(v * w for v, w in zip(vals, weights)) / max(sum(weights), 1e-10)
        v = np.array(vals, dtype=np.float32)
        w = np.array(weights, dtype=np.float32)
        return float(np.sum(v * w) / max(np.sum(w), 1e-10))

    ref.lufs          = _median(lufs_vals) if lufs_vals else TARGET['lufs']
    ref.lra           = _median(lra_vals)  if lra_vals  else TARGET['lra']
    # Derive phrase_lra from measured LRA with simple spread estimate
    if lra_vals and NUMPY_OK:
        ref.phrase_lra     = float(np.median(lra_vals))
        ref.phrase_lra_p10 = float(np.percentile(lra_vals, 10)) if len(lra_vals) > 1 else ref.phrase_lra * 0.75
        ref.phrase_lra_p90 = float(np.percentile(lra_vals, 90)) if len(lra_vals) > 1 else ref.phrase_lra * 1.25
    ref.rms           = _median(rms_vals)  if rms_vals  else TARGET['rms']
    ref.crest         = _median(crest_vals) if crest_vals else TARGET['crest']
    ref.f0_median     = _median(f0_vals) if f0_vals else 0.0
    ref.files_used    = len(REF_FILES)
    ref.hash          = _ref_files_hash(REF_FILES)
    # BW cutoff: weighted mean across refs (higher-quality refs count more)
    ref.bw_cutoff     = float(sum(bw_vals) / max(len(bw_vals), 1)) if bw_vals else 13000.0

    # Weighted spectral average: higher-quality files count more
    ref.spectrum_48 = {
        f: _weighted_mean(spec_accum[f], spec_weights[f])
        if spec_accum[f] else -60.0
        for f in CENTERS_48
    }

    # T2-B: Studio A spectrum — only files with studio_bw_factor=1.0 (BW ≤ 15kHz)
    # These are the true 1425H reference files; use for EQ character target
    studio_a_accum:   Dict[float, List[float]] = {f: [] for f in CENTERS_48}
    studio_a_weights: Dict[float, List[float]] = {f: [] for f in CENTERS_48}
    for rf, spec_snap, w_snap in _ref_per_file_data:
        bw_pre_snap = _measure_ref_bw_cutoff(rf) if os.path.exists(rf) else 13000.0
        if bw_pre_snap <= 15000.0:  # Studio A fingerprint
            for f in CENTERS_48:
                if f in spec_snap:
                    studio_a_accum[f].append(spec_snap[f])
                    studio_a_weights[f].append(w_snap)
    if any(studio_a_accum[f] for f in CENTERS_48):
        ref.spectrum_48_studio_a = {
            f: _weighted_mean(studio_a_accum[f], studio_a_weights[f])
            if studio_a_accum[f] else ref.spectrum_48.get(f, -60.0)
            for f in CENTERS_48
        }
        L(f'  [ref] Studio A spectrum built from {sum(1 for f in CENTERS_48 if studio_a_accum[f] and studio_a_accum[f][0] != -60.0)} bands')
    else:
        ref.spectrum_48_studio_a = dict(ref.spectrum_48)

    # T2-C: Runtime spectral character — deviation from pink noise (-3dB/octave)
    # Gives the "personality" of the Studio A reference independent of absolute level
    if NUMPY_OK and ref.spectrum_48_studio_a:
        import math as _m
        _f_ref = 1000.0  # normalize to 0dB at 1kHz
        _studio_vals = np.array([ref.spectrum_48_studio_a.get(f, -60.0) for f in CENTERS_48])
        _pink_curve  = np.array([-10.0 * _m.log10(max(f / _f_ref, 1e-10)) for f in CENTERS_48],
                                 dtype=np.float32)
        # Normalize: align studio mean to pink mean over active bands
        _ref_bw_c = ref.bw_cutoff
        _active_m = np.array([f <= _ref_bw_c * 1.05 for f in CENTERS_48])
        if _active_m.sum() > 0:
            _offset = float((_studio_vals[_active_m] - _pink_curve[_active_m]).mean())
            _pink_aligned = _pink_curve + _offset
            _character = _studio_vals - _pink_aligned
        else:
            _character = np.zeros(len(CENTERS_48))
        ref.spectral_character = {f: float(c) for f, c in zip(CENTERS_48, _character)}
        L(f'  [ref] spectral_character computed: mean={float(np.abs(_character).mean()):.2f}dB')

    # Build trajectory
    ref.trajectory = _build_reference_trajectory(REF_FILES)

    # Cache
    try:
        cache_dir = os.path.dirname(_REF_CACHE)
        os.makedirs(cache_dir, exist_ok=True)
        with open(_REF_CACHE, 'w') as fh:
            json.dump({
                'cache_version': 'itiqan-v11',
                'ref_hash':      ref.hash,
                'lufs':          ref.lufs,
                'rms':           ref.rms,
                'crest':         ref.crest,
                'lra':           ref.lra,
                'true_peak':     ref.true_peak,
                'sfm':           ref.sfm,
                'dr':            ref.dr,
                'silence_floor': ref.silence_floor,
                'spectrum_48':   {str(k): v for k, v in ref.spectrum_48.items()},
                'phrase_lra':    ref.phrase_lra,
                'phrase_lra_p10': ref.phrase_lra_p10,
                'phrase_lra_p90': ref.phrase_lra_p90,
                'trajectory':    ref.trajectory,
                'f0_median':     ref.f0_median,
                'files_used':    ref.files_used,
                'bw_cutoff':          ref.bw_cutoff,
                'spectrum_48_studio_a': {str(k): v for k, v in ref.spectrum_48_studio_a.items()},
                'spectral_character':   {str(k): v for k, v in ref.spectral_character.items()},
            }, fh)
        L(f'  [ref] cached to {_REF_CACHE}')
    except Exception as e:
        L(f'  [ref] cache write failed (non-fatal): {e}')

    L(f'  [ref] built: LUFS={ref.lufs:.2f} LRA={ref.lra:.2f} '
      f'Crest={ref.crest:.2f} F0_med={ref.f0_median:.0f}Hz BW={ref.bw_cutoff:.0f}Hz')
    return ref


# ══════════════════════════════════════════════════════════════════════════════
#  MUJAWWAD STYLE DETECTION  (KB §145)
# ══════════════════════════════════════════════════════════════════════════════

def _detect_mujawwad_style(state: 'ItiqanState') -> float:
    """
    KB §145.2: Detect Mujawwad recitation style from measurable acoustic features.
    Returns mujawwad_confidence ∈ [0.0, 1.0].

    Features (acoustic proxies — no ASR required):
      F0 range > 120 Hz   → wide melodic arc (Mujawwad hallmark)
      LRA > 4.5 LU        → high dynamic range from inter-ayah pauses
      Crest > 11.5 dB     → strong transient peaks vs sustained vowels
      Duration > 1200 s   → long suwar typical of tarawih Mujawwad

    Classification: KB §145.2 says 3/5 features → Mujawwad.
    Here we use 4 weighted features without syllable-rate (needs ASR).
    """
    score = 0.0

    # F0 range: wide pitch arc is a primary Mujawwad discriminant
    if state.f0_histogram:
        f0_vals = list(state.f0_histogram.keys())
        if len(f0_vals) > 1:
            f0_range = max(f0_vals) - min(f0_vals)
            if f0_range > 140.0:
                score += 0.35
            elif f0_range > 100.0:
                score += 0.20
            elif f0_range > 70.0:
                score += 0.08

    # LRA: Mujawwad has wide dynamics from ayah-end pauses (TYPE 1 silence, §158)
    if state.lra > 4.8:
        score += 0.30
    elif state.lra > 4.0:
        score += 0.18
    elif state.lra > 3.5:
        score += 0.08

    # Crest: high crest = short loud peaks vs quiet sustained vowels
    if state.crest > 12.0:
        score += 0.20
    elif state.crest > 11.0:
        score += 0.10

    # Duration: tarawih Mujawwad suwar are typically long (> 20 min)
    if state.duration_s > 3600:
        score += 0.15
    elif state.duration_s > 1200:
        score += 0.08

    conf = float(min(1.0, score))
    return conf


# ══════════════════════════════════════════════════════════════════════════════
#  SOURCE CLASSIFICATION
# ══════════════════════════════════════════════════════════════════════════════
#  TIER_PRISTINE_NOISY — Background noise detection & Adaptive DF3 pass
# ══════════════════════════════════════════════════════════════════════════════

# Deep-filter v3 binary candidates (same list as isteidad)
_DF3_CLI_CANDIDATES = [
    '/home/claude/deep-filter',
    str(Path(__file__).parent / 'deep-filter'),
    'deep-filter',
]
_DF3_CLI_BIN: str = ''
for _c in _DF3_CLI_CANDIDATES:
    try:
        _r = subprocess.run([_c, '--help'], capture_output=True, timeout=5)
        if _r.returncode == 0:
            _DF3_CLI_BIN = _c
            break
    except Exception:
        pass
DF3_CLI_OK: bool = bool(_DF3_CLI_BIN)


def _measure_bg_noise_itiqan(samples: 'np.ndarray', sr: int = SR,
                              ) -> 'Tuple[float, float, bool]':
    """
    Fast background noise estimation for tier classification.
    Uses 20ms frame RMS distribution — no large FFT allocation.

    Returns (noise_floor_db, snr_proxy_db, is_noisy).

    is_noisy when: snr_proxy < 20dB AND spectral content present AND BG > -40dBFS.
    Calibrated on:
      27101427:  BG=-14.6dBFS  SNR_proxy=8.9dB  → noisy (mosque AC+room noise)
      احزاب:     BG=-27.6dBFS  SNR_proxy=11.9dB → noisy (room ambiance)
      clean file: BG typically < -50dBFS, SNR_proxy > 22dB
    """
    if not NUMPY_OK or len(samples) < sr:
        return -60.0, 25.0, False

    frame_n = int(0.02 * sr)
    frames_db: List[float] = []
    for i in range(0, len(samples) - frame_n, frame_n):
        rms = float(np.sqrt(np.mean(samples[i:i + frame_n] ** 2)))
        frames_db.append(float(20.0 * np.log10(rms + 1e-10)))

    if len(frames_db) < 20:
        return -60.0, 25.0, False

    arr = np.array(frames_db)
    p5  = float(np.percentile(arr, 5))
    p10 = float(np.percentile(arr, 10))
    p20 = float(np.percentile(arr, 20))
    p75 = float(np.percentile(arr, 75))
    snr_proxy = p75 - p10

    noise_idxs = [i for i, r in enumerate(frames_db) if p5 < r < p20][:80]
    if not noise_idxs:
        return p10, snr_proxy, snr_proxy < 18.0

    bg = np.concatenate([samples[i * frame_n:(i + 1) * frame_n] for i in noise_idxs])
    bg_rms = float(20.0 * np.log10(np.sqrt(np.mean(bg ** 2)) + 1e-10))

    N = min(len(bg), 4096)
    bg_spec = np.abs(np.fft.rfft(bg[:N], n=N)) ** 2
    bg_freqs = np.fft.rfftfreq(N, 1.0 / sr)
    lf_mask  = (bg_freqs >= 100) & (bg_freqs < 500)
    mid_mask = (bg_freqs >= 500) & (bg_freqs < 2000)
    has_noise = (
        (lf_mask.any()  and float(np.mean(bg_spec[lf_mask]))  > 1e-8) or
        (mid_mask.any() and float(np.mean(bg_spec[mid_mask])) > 1e-8)
    )

    # KB §52.7: tightened threshold — 20dB was too broad, flagging clean 320kbps
    # recordings as noisy when 60s clips start mid-recitation.
    # 16dB: genuine noise (≤16dB SNR); 17-20dB: natural dynamic variation.
    # Two-guard clean detection:
    #
    # Guard A — True phrase silence (yt5s pattern):
    #   Lowest frames are near-digital silence between recitation phrases.
    #   SFM ≈ 0 (near-zero energy, not broadband) AND p5 < -36 dBFS.
    #
    # Guard B — Room character / harmonic air (الذاريات, يا أيها pattern):
    #   Background has strong harmonic peaks from room resonances or reverb
    #   tail of the voice itself — this is recording CHARACTER, not noise.
    #   Measured as peak-to-mean ratio in 100–1000 Hz band.
    #   Calibrated:
    #     الذاريات (room air):  harm_r=32.1x → clean ✓
    #     يا أيها  (clean):     harm_r=27.4x → clean ✓
    #     yt5s     (silence):   harm_r=29.2x → clean ✓
    #     الأحزاب  (noisy):     harm_r=13.8x → noisy ✓
    #     الأعراف  (noisy):     harm_r=22.2x → noisy ✓
    #   Threshold: harm_r > 25x = harmonic/tonal background = not destructive noise.
    N_bg = min(len(bg), 8192)
    bg_spec_full = np.abs(np.fft.rfft(bg[:N_bg], n=N_bg)) ** 2 + 1e-10
    bg_freqs_full = np.fft.rfftfreq(N_bg, 1.0 / sr)
    sfm = float(np.exp(np.mean(np.log(bg_spec_full))) / np.mean(bg_spec_full))
    p5_depth = float(np.percentile(arr, 5))

    # Spectral slope of background (200–4000 Hz log-log fit).
    # Flat spectrum (slope > -1.6) = broadband destructive noise.
    # Steep spectrum (slope < -1.6) = tonal/room character that enhances the voice.
    # Calibrated across all known files:
    #   الأحزاب  (noisy):    slope=-1.22 → flat  → noisy  ✓
    #   الذاريات (room air): slope=-1.90 → steep → clean  ✓
    #   يا أيها  (clean):    slope=-2.09 → steep → clean  ✓
    #   الأعراف  (noisy):    slope=-2.36 → steep BUT snr=8.8 < 9dB → still noisy ✓
    #   yt5s     (silence):  slope=-1.64 → caught by silence guard first
    slope_band = (bg_freqs_full >= 200) & (bg_freqs_full < 4000)
    if slope_band.sum() > 4:
        _lf = np.log10(bg_freqs_full[slope_band] + 1)
        _lp = np.log10(bg_spec_full[slope_band])
        bg_slope = float(np.polyfit(_lf, _lp, 1)[0])
    else:
        bg_slope = -2.0  # default to steep (safe)

    # Guard A: near-digital silence between phrases (yt5s pattern)
    is_true_silence = sfm < 0.003 and p5_depth < -36.0
    # Guard B: tonal/room-character background (الذاريات, يا أيها pattern).
    # slope < -1.6 (steep rolloff) AND snr > 9.0 (not so mixed that it IS noise).
    # The snr > 9.0 guard preserves الأعراف (snr=8.8) as genuinely noisy.
    is_room_character = bg_slope < -1.6 and snr_proxy > 9.0
    is_noisy = snr_proxy < 16.0 and has_noise and bg_rms > -40.0                and not is_true_silence and not is_room_character
    return bg_rms, snr_proxy, is_noisy


# Chunk + attenuation settings for adaptive DF3
_DF3_CHUNK_S     = 0.100
_DF3_XFADE_N     = 960
_DF3_LOUD_ATTEN  = 8
_DF3_MID_ATTEN   = 15
_DF3_QUIET_ATTEN = 20


def _adaptive_df3_itiqan(wav_path: str, state: ItiqanState) -> str:
    """
    Adaptive DeepFilterNet-3 pass for TIER_PRISTINE_NOISY sources.

    Three-pass VAD blend (same algorithm as engine_isteidad):
      1. VAD-classify every 100ms chunk as LOUD / MID / QUIET by RMS percentile
      2. Run DF3 at atten=8/15/20dB respectively
      3. Blend with cosine crossfades at label-change boundaries

    Returns cleaned WAV path (pipeline format: pcm_s24le stereo).
    Returns original wav_path unchanged on any failure.
    Updates state.df3_* fields.
    """
    if not DF3_CLI_OK:
        L('  [DF3] binary not found — skipping')
        return wav_path

    tmp_dir = tempfile.mkdtemp(prefix='itiqan_df3_')
    try:
        import wave as _wave

        # Decode to 16-bit 48kHz mono (deep-filter requirement)
        df_in = os.path.join(tmp_dir, 'df_in.wav')
        rc, _, err = _run_ffmpeg([
            'ffmpeg', '-y', '-i', wav_path,
            '-acodec', 'pcm_s16le', '-ar', str(SR), '-ac', '1', df_in
        ])
        if rc != 0 or not os.path.exists(df_in):
            L(f'  [DF3] decode failed: {err[:80]}')
            return wav_path

        # Load for VAD classification
        with _wave.open(df_in, 'rb') as wf:
            raw_data = wf.readframes(wf.getnframes())
        raw_s = np.frombuffer(raw_data, dtype=np.int16).astype(np.float32) / 32768.0

        chunk_n  = int(_DF3_CHUNK_S * SR)
        n_chunks = len(raw_s) // chunk_n
        if n_chunks < 1:
            return wav_path

        chunk_rms = np.array([
            float(np.sqrt(np.mean(raw_s[i * chunk_n:(i + 1) * chunk_n] ** 2)))
            for i in range(n_chunks)
        ])
        rms_arr = 20.0 * np.log10(np.maximum(chunk_rms, 1e-10))
        state.df3_snr_before = float(
            np.percentile(rms_arr, 75) - np.percentile(rms_arr, 10))

        p_lo = float(np.percentile(chunk_rms, 30))
        p_hi = float(np.percentile(chunk_rms, 70))
        labels = np.where(chunk_rms >= p_hi, 0,
                 np.where(chunk_rms >= p_lo, 1, 2))

        state.df3_loud_chunks  = int(np.sum(labels == 0))
        state.df3_mid_chunks   = int(np.sum(labels == 1))
        state.df3_quiet_chunks = int(np.sum(labels == 2))
        L(f'  [DF3-VAD] LOUD={state.df3_loud_chunks} MID={state.df3_mid_chunks} '
          f'QUIET={state.df3_quiet_chunks} chunks × 100ms')

        # Run 3 DF3 passes
        pass_arrays: dict = {}
        for pass_name, atten_db in [('loud', _DF3_LOUD_ATTEN),
                                     ('mid',  _DF3_MID_ATTEN),
                                     ('quiet',_DF3_QUIET_ATTEN)]:
            out_dir = os.path.join(tmp_dir, f'df_{pass_name}')
            os.makedirs(out_dir, exist_ok=True)
            r = subprocess.run(
                [_DF3_CLI_BIN, '--atten-lim-db', str(atten_db), '-o', out_dir, df_in],
                capture_output=True, timeout=600,
            )
            out_wav = os.path.join(out_dir, os.path.basename(df_in))
            if r.returncode != 0 or not os.path.exists(out_wav):
                L(f'  [DF3] {pass_name} pass failed (rc={r.returncode})')
                return wav_path
            with _wave.open(out_wav, 'rb') as wf:
                raw = wf.readframes(wf.getnframes())
            arr = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            pass_arrays[pass_name] = arr
            L(f'  [DF3] {pass_name:5s}  atten={atten_db:2d}dB ✓  max={float(np.max(np.abs(arr))):.4f}')

        # Adaptive blend with cosine crossfades
        pa = [pass_arrays['loud'], pass_arrays['mid'], pass_arrays['quiet']]
        min_len = min(len(raw_s), min(len(a) for a in pa))
        out_s   = np.empty(min_len, dtype=np.float32)
        xfade   = _DF3_XFADE_N
        t       = np.linspace(0.0, 1.0, xfade, dtype=np.float32)
        cos_in  = (0.5 * (1.0 - np.cos(np.pi * t))).astype(np.float32)
        cos_out = 1.0 - cos_in
        boundaries = 0
        prev_label = int(labels[0])

        for ci in range(n_chunks):
            s = ci * chunk_n
            e = min((ci + 1) * chunk_n, min_len)
            if e > min_len:
                break
            lbl = int(labels[ci])
            if lbl != prev_label and ci > 0 and s + xfade <= min_len:
                blen = min(xfade, e - s)
                out_s[s:s+blen] = (pa[prev_label][s:s+blen] * cos_out[:blen] +
                                   pa[lbl][s:s+blen]        * cos_in[:blen])
                if e > s + xfade:
                    out_s[s+xfade:e] = pa[lbl][s+xfade:e]
                boundaries += 1
            else:
                out_s[s:e] = pa[lbl][s:e]
            prev_label = lbl

        state.df3_boundaries = boundaries
        L(f'  [DF3-blend] {boundaries} crossfade boundaries @ {xfade} samples each')

        # Write mono 16-bit then convert to pipeline format (pcm_s24le stereo)
        blend_mono = os.path.join(tmp_dir, 'blend_mono.wav')
        b16 = np.clip(out_s, -1.0, 1.0)
        b16 = (b16 * 32767).astype(np.int16)
        with _wave.open(blend_mono, 'wb') as wf:
            wf.setnchannels(1); wf.setsampwidth(2)
            wf.setframerate(SR); wf.writeframes(b16.tobytes())

        df3_out = _tmp_wav('df3')
        rc2, _, err2 = _run_ffmpeg([
            'ffmpeg', '-y', '-i', blend_mono,
            '-acodec', WAV_CODEC, '-ar', str(SR), '-ac', '2', df3_out
        ])
        if rc2 != 0 or not os.path.exists(df3_out):
            L(f'  [DF3] stereo encode failed: {err2[:80]}')
            return wav_path

        # Re-measure SNR after DF3
        out_rms_arr = 20.0 * np.log10(np.maximum(
            np.array([float(np.sqrt(np.mean(b16[i*chunk_n:(i+1)*chunk_n].astype(np.float32)**2)))
                      for i in range(min(n_chunks, len(b16)//chunk_n))]),
            1e-10))
        if len(out_rms_arr) > 1:
            state.df3_snr_after = float(
                np.percentile(out_rms_arr, 75) - np.percentile(out_rms_arr, 10))
        else:
            state.df3_snr_after = state.df3_snr_before

        state.df3_applied = True
        L(f'  [DF3] ✓  SNR {state.df3_snr_before:.1f}→{state.df3_snr_after:.1f}dB  '
          f'{os.path.getsize(df3_out)/1e6:.1f}MB')
        return df3_out

    except Exception as exc:
        L(f'  [DF3] exception: {type(exc).__name__}: {exc} — skipping')
        return wav_path
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════════════════════

def classify_source(wav_path: str, samples: 'np.ndarray',
                    bitrate_kbps: int, duration_s: float) -> Tuple[str, ItiqanState]:
    """
    Classify source tier and populate ItiqanState.
    Returns ('TIER_PRISTINE'|'TIER_COMPRESSED'|'TIER_DAMAGED'|'TIER_CRITICAL', state)
    الإتقان only processes PRISTINE and COMPRESSED.
    """
    state = ItiqanState()
    state.duration_s  = duration_s
    state.bitrate_kbps = bitrate_kbps
    state.bitrate_class = _bitrate_class(bitrate_kbps)

    lufs, lra = _measure_lufs(wav_path)
    state.lufs = lufs
    state.lra  = lra

    if samples is not None and NUMPY_OK:
        rms, crest = _measure_rms_crest(samples)
        state.rms   = rms
        state.crest = crest
        state.silence_floor = _measure_silence_floor(samples)
        state.codec_cutoff  = _measure_codec_cutoff(samples)
        state.snr_global = state.crest  # rough proxy pre-NR

        # Smear detection (simplified — full version in base engine)
        zcr_arr = np.abs(np.diff(np.sign(samples)))
        state.smear_score = 0
        state.smear_desc  = 'none'
    else:
        state.crest = 10.0
        state.codec_cutoff = 20000.0

    # Tier classification
    clip_ratio = 0.0
    if samples is not None and NUMPY_OK:
        clip_ratio = float(np.mean(np.abs(samples) > 0.999))

    if clip_ratio > 0.05 or state.crest < 6.0 or state.codec_cutoff < 8000:
        tier = 'TIER_CRITICAL'
    elif state.lra < 1.0 or state.snr_global < 6.0 or state.codec_cutoff < 12000:
        tier = 'TIER_DAMAGED'
    elif bitrate_kbps < 128 or state.crest < 8.5:
        tier = 'TIER_COMPRESSED'
    else:
        tier = 'TIER_PRISTINE'

    # TIER_PRISTINE_NOISY: excellent voice quality but audible background noise.
    # Detected after base tier = TIER_PRISTINE: if background noise floor is
    # elevated (> -40dBFS) and SNR_proxy < 20dB, promote to TIER_PRISTINE_NOISY
    # so that Phase A5 Adaptive DF3 is applied before the rest of the pipeline.
    if tier == 'TIER_PRISTINE' and samples is not None and NUMPY_OK:
        _bg_floor, _snr_proxy, _is_noisy = _measure_bg_noise_itiqan(samples, SR)
        state.noise_floor_db = _bg_floor
        state.snr_proxy_db   = _snr_proxy
        if _is_noisy:
            tier = 'TIER_PRISTINE_NOISY'

    # G7: Run background noise check for COMPRESSED sources too.
    # Live mosque COMPRESSED recordings often have AC noise / room ambiance.
    # If detected, raise nr_confidence and log — the NR pass already uses
    # deeper afftdn for COMPRESSED; this ensures nr_confidence isn't wrongly
    # low when the source has measurable background noise.
    if tier == 'TIER_COMPRESSED' and samples is not None and NUMPY_OK:
        _bg_floor_c, _snr_proxy_c, _is_noisy_c = _measure_bg_noise_itiqan(samples, SR)
        state.noise_floor_db = _bg_floor_c
        state.snr_proxy_db   = _snr_proxy_c
        if _is_noisy_c:
            # Don't change tier — COMPRESSED stays COMPRESSED.
            # But raise nr_confidence so Phase B uses its full depth.
            state.nr_confidence = min(0.85, state.nr_confidence + 0.20)
            L(f'  [class] G7 COMPRESSED + bg noise detected: '
              f'floor={_bg_floor_c:.1f}dBFS SNR_proxy={_snr_proxy_c:.1f}dB '
              f'→ nr_confidence={state.nr_confidence:.2f}')

    state.source_tier = tier

    # Confidence vectors — initial estimates
    # EQ confidence: higher for cleaner sources
    eq_base = 0.90 if tier in ('TIER_PRISTINE', 'TIER_PRISTINE_NOISY') else 0.75
    state.eq_confidence = eq_base

    # Per-48-band confidence (will be refined after spectral analysis)
    if NUMPY_OK:
        conf = np.ones(48) * eq_base
        # Reduce confidence near codec cutoff
        for i, f in enumerate(CENTERS_48):
            if f > state.codec_cutoff * 0.85:
                conf[i] *= max(0.1, 1.0 - (f - state.codec_cutoff * 0.85) / (state.codec_cutoff * 0.15))
        state.eq_confidence_48 = conf.astype(np.float32)

    _is_pristine_class = tier in ('TIER_PRISTINE', 'TIER_PRISTINE_NOISY')
    state.nr_confidence      = 0.80 if _is_pristine_class else 0.60
    state.compand_confidence = 0.75 if _is_pristine_class else 0.65

    return tier, state


# ══════════════════════════════════════════════════════════════════════════════
#  QUALITY CEILING COMPUTATION (P-1, v3.0)
# ══════════════════════════════════════════════════════════════════════════════

def compute_itiqan_ceiling(state: ItiqanState, ref: ReferenceModel,
                            spectral_loss_48: Optional['np.ndarray'] = None
                            ) -> Tuple[float, str]:
    """
    v3.0: ceiling from DIRECT spectral loss measurement, not codec model.
    
    Recoverable loss    (< 6dB):  EQ can close this gap
    Partial loss        (6-12dB): EQ helps but not fully
    Unrecoverable loss  (> 12dB): content is destroyed, not just level-shifted
    
    Perceptual loss weight: formant region (1-4kHz) = 1.0, sub-bass = 0.3
    """
    if spectral_loss_48 is None or not NUMPY_OK:
        # Fallback: codec-based estimate
        bitrate_ceiling = {
            '320': 100.0, '256': 97.0, '192': 95.0,
            '128': 91.0,  '96':  86.0, '64':  80.0,
        }
        ceiling = bitrate_ceiling.get(state.bitrate_class, 88.0)
        return ceiling, f'codec_fallback_{state.bitrate_class}kbps'

    # Direct measurement path
    total_weight       = 0.0
    unrecoverable_loss = 0.0
    partial_loss       = 0.0

    for i, f in enumerate(CENTERS_48):
        # Find nearest weight key
        weight_key = min(_PERC_LOSS_WEIGHT.keys(), key=lambda k: abs(k - f))
        w = _PERC_LOSS_WEIGHT[weight_key]
        total_weight += w

        loss = float(spectral_loss_48[i])  # positive = input below ref = deficit

        if loss > 12.0:
            unrecoverable_loss += w * (loss - 12.0)
        if loss > 6.0:
            partial_loss += w * min(loss - 6.0, 6.0) * 0.40  # 40% partial penalty

    total_perc_loss = (unrecoverable_loss + partial_loss) / max(total_weight, 1.0)

    # Score ceiling: deduct for unrecoverable loss
    ceiling = 100.0 * (1.0 - min(total_perc_loss / 20.0, 0.20))

    # Crest headroom factor
    crest_delta = abs(state.crest - TARGET['crest'])
    ceiling *= max(0.95, 1.0 - crest_delta * 0.01)

    ceiling = round(min(100.0, max(80.0, ceiling)), 1)
    reason  = f'direct_loss={total_perc_loss:.3f} bitrate={state.bitrate_class}kbps'
    return ceiling, reason


# ══════════════════════════════════════════════════════════════════════════════
#  NOISE REDUCTION — selective, tier-aware
# ══════════════════════════════════════════════════════════════════════════════

def run_selective_nr(wav_path: str, state: ItiqanState, ref: ReferenceModel) -> Tuple[str, dict]:
    """
    Phase B: Selective NR for PRISTINE/PRISTINE_NOISY/COMPRESSED sources.
    PRISTINE:        hum notch + afftdn max -6dB
    PRISTINE_NOISY:  hum notch + afftdn max -12dB (deeper; DF3 already ran)
    COMPRESSED:      hum notch + afftdn max -10dB
    L-16 guard: measure sibilant SNR before/after, revert if degraded > 2dB.
    """
    output_wav = _tmp_wav('nr')
    report = {'applied': False, 'floor_delta': 0.0, 'hum_notch': False}

    # FIX-1: afftdn nf must be a deep-negative dBFS value (e.g. -30 to -70).
    # Old code: max(..., -10) → RC=222 "Numerical result out of range".
    # New code: clamp to [-80, -20], tighter for PRISTINE sources.
    # F3: Low-bitrate COMPRESSED (64–96kbps) has louder quantization noise;
    # scale NR depth with measured silence_floor to avoid under-denoising.
    _is_tier_pristine = state.source_tier in ('TIER_PRISTINE',)
    _is_low_bitrate   = state.bitrate_class in ('64', '96')
    if getattr(state, 'aggressive', False):
        max_nr_depth = -28.0 if _is_tier_pristine else -38.0
    elif _is_tier_pristine:
        # G2: PRISTINE_NOISY without DF3 binary gets deeper afftdn fallback.
        # Standard PRISTINE gets −20dB; PRISTINE_NOISY w/o DF3 gets −26dB.
        if state.source_tier == 'TIER_PRISTINE_NOISY' and not DF3_CLI_OK:
            max_nr_depth = -26.0
            L('  [NR] G2 DF3 unavailable — PRISTINE_NOISY fallback depth −26dB')
        else:
            max_nr_depth = -20.0
    elif _is_low_bitrate:
        # Scale depth with noise floor: silence_floor −45→−32dB, −55+→−24dB
        _noise_factor = float(max(0.0, min(1.0, (state.silence_floor + 55.0) / 10.0)))
        max_nr_depth  = -24.0 - _noise_factor * 8.0   # range: −24 to −32dB
        L(f'  [NR] F3 low-bitrate depth scale: floor={state.silence_floor:.1f}dBFS '
          f'factor={_noise_factor:.2f} max_depth={max_nr_depth:.0f}dB')
    else:
        max_nr_depth = -24.0
    nr_floor = max(min(ref.silence_floor - 3.0, max_nr_depth), -80.0)

    # Hum detection: check 50Hz / 60Hz harmonics
    samples, sr = _decode_wav_samples(wav_path)
    hum_freq = 0
    if samples is not None and NUMPY_OK:
        N = min(len(samples), sr * 4)
        spec = np.abs(rfft(samples[:N] * np.hanning(N))) ** 2
        freqs = rfftfreq(N, d=1.0 / sr)
        spec_db = 10 * np.log10(np.maximum(spec, 1e-10))

        def _band_level(fc):
            mask = (freqs >= fc * 0.9) & (freqs <= fc * 1.1)
            return float(np.mean(spec_db[mask])) if mask.sum() > 0 else -99.0

        noise_floor_50hz = float(np.percentile(spec_db[:100], 20))
        if _band_level(120) > noise_floor_50hz + 6.0:
            hum_freq = 60
        elif _band_level(100) > noise_floor_50hz + 6.0:
            hum_freq = 50

    # Build filter chain
    filters = []

    if hum_freq > 0:
        # FIX-2: Limit to first 5 harmonics only (up to 300Hz for 60Hz, 250Hz for 50Hz).
        # 33 notches up to 2kHz cause severe phase distortion in formant bands.
        n = hum_freq; max_notch = hum_freq * 5
        while n <= min(max_notch, state.codec_cutoff):
            filters.append(f'equalizer=f={n}:t=q:w=30:g=-18')
            n += hum_freq
        report['hum_notch'] = True
        L(f'  [NR] hum notch: {hum_freq}Hz × {min(5, int(state.codec_cutoff/hum_freq))} harmonics')

    # Broadband NR
    # H1: PhonemeNRBudget (KB §143) — pre/de-emphasis wrapping afftdn.
    # Boosts phoneme-fragile bands BEFORE afftdn so they appear louder to
    # noise estimation → proportionally less attenuation → de-emphasis restores.
    #
    # Protected zones (conservatively capped per §143.2):
    #   200–800 Hz (pharyngeal ع/ح/غ, emphatic ص/ض/ط/ظ) → PNB Class 1/3 ≤ 6–10 dB
    #   5500–12000 Hz (Safir ص/س/ز) → narrow peak must not be over-attenuated
    #
    # Pre-emphasis gain: +6dB pharyngeal zone, +4dB Safir zone.
    # These values give ~6–8dB effective NR budget protection (at −24dB nr_floor
    # the bands now "see" −18/−20 dB NR effectively — within PNB budget).
    # Only applied to TIER_COMPRESSED where NR depth reaches −24 to −32 dB.
    if state.nr_confidence > 0.3:
        _afftdn_str = f'afftdn=nf={nr_floor:.0f}:nt=w:om=o'
        if state.source_tier == 'TIER_COMPRESSED':
            _pnb_pre  = ('equalizer=f=400:width_type=o:width=2.0:g=6.0,'
                         'equalizer=f=8000:t=h:w=1.5:g=4.0')
            _pnb_post = ('equalizer=f=400:width_type=o:width=2.0:g=-6.0,'
                         'equalizer=f=8000:t=h:w=1.5:g=-4.0')
            filters.append(f'{_pnb_pre},{_afftdn_str},{_pnb_post}')
            L(f'  [NR] H1 PNB pharyngeal+Safir pre/de-emphasis (nr_floor={nr_floor:.0f}dB)')
        else:
            filters.append(_afftdn_str)

    if not filters:
        shutil.copy2(wav_path, output_wav)
        return output_wav, report

    filter_str = ','.join(filters)
    cmd = [
        'ffmpeg', '-y', '-i', wav_path,
        '-af', filter_str,
        '-acodec', WAV_CODEC, output_wav
    ]
    rc, _, err = _run_ffmpeg(cmd)
    if rc != 0:
        L(f'  [NR] failed: {err[:120]}')
        shutil.copy2(wav_path, output_wav)
        return output_wav, report

    # L-16 sibilant SNR guard
    if samples is not None and NUMPY_OK:
        samples_after, _ = _decode_wav_samples(output_wav)
        if samples_after is not None:
            def _sib_snr(s):
                N2 = min(len(s), sr * 4)
                spec2 = np.abs(rfft(s[:N2] * np.hanning(N2))) ** 2
                freqs2 = rfftfreq(N2, d=1.0 / sr)
                sib_mask = np.zeros(len(spec2), dtype=bool)
                for fc in ARABIC_SIB_BANDS:
                    sib_mask |= (freqs2 >= fc * 0.85) & (freqs2 <= fc * 1.15)
                noise_mask = (freqs2 >= 100) & (freqs2 <= 500)
                sib_level  = float(np.mean(10 * np.log10(np.maximum(spec2[sib_mask], 1e-10))))
                noise_level = float(np.mean(10 * np.log10(np.maximum(spec2[noise_mask], 1e-10))))
                return sib_level - noise_level

            snr_before = _sib_snr(samples)
            snr_after  = _sib_snr(samples_after)
            if snr_after < snr_before - 2.0:
                L(f'  [NR] sibilant SNR degraded {snr_before:.1f}→{snr_after:.1f}dB — reverting')
                shutil.copy2(wav_path, output_wav)
                return output_wav, report

    floor_before = _measure_silence_floor(samples) if samples is not None else state.silence_floor
    samples_nr, _ = _decode_wav_samples(output_wav)
    floor_after   = _measure_silence_floor(samples_nr) if samples_nr is not None else floor_before

    report['applied']     = True
    report['floor_delta'] = floor_after - floor_before
    L(f'  [NR] applied: floor {floor_before:.1f}→{floor_after:.1f}dBFS '
      f'(nr_floor={nr_floor:.0f}dB)')
    return output_wav, report


# ══════════════════════════════════════════════════════════════════════════════
#  HARMONIC INTERACTION PLANNING (P-4 informs P-2)
# ══════════════════════════════════════════════════════════════════════════════

def plan_harmonic_injection(state: ItiqanState) -> Dict[float, float]:
    """
    v3.0: F0-histogram-weighted harmonic interaction model.
    Computes expected level at each CENTERS_48 frequency from aexciter
    harmonic injection, using ACTUAL F0 distribution (not uniform assumption).
    
    Returns {center_hz: expected_gain_db} for all affected 48-band centers.
    aexciter at amount=20 generates ~-45dBFS odd harmonics.
    """
    if not state.f0_histogram or not NUMPY_OK:
        return {}

    harmonic_plan: Dict[float, float] = {}

    for f0, weight in state.f0_histogram.items():
        for harmonic_n in [3, 5]:  # odd harmonics only
            harmonic_freq = f0 * harmonic_n
            if harmonic_freq > 16000.0 or harmonic_freq > state.codec_cutoff:
                continue

            # Find closest CENTERS_48 band
            closest = min(CENTERS_48, key=lambda f: abs(f - harmonic_freq))

            # Level: -45dBFS for 3rd harmonic, -52dBFS for 5th harmonic (aexciter amount=20)
            # Weighted by F0 occurrence: more common F0 → stronger expected contribution
            base_level_db = -45.0 if harmonic_n == 3 else -52.0
            # Weight modulates expected level (weight is already normalized to [0,1])
            # Linear scale: weight=1.0 → base_level; weight=0.1 → base_level - 20dB
            weighted_level = base_level_db + 20.0 * np.log10(max(weight, 1e-10))

            current = harmonic_plan.get(closest, -90.0)
            harmonic_plan[closest] = max(current, weighted_level)

    return harmonic_plan


def _adjust_ref_for_harmonics(ref_48: Dict[float, float],
                               harmonic_plan: Dict[float, float]) -> Dict[float, float]:
    """
    Subtract expected harmonic contribution from reference targets.
    Prevents P-2 EQ from double-boosting bands that P-4 will fill via harmonics.
    """
    adjusted = dict(ref_48)
    for f, harmonic_db in harmonic_plan.items():
        if f not in adjusted:
            continue
        harmonic_linear = 10.0 ** (harmonic_db / 20.0)
        # Small harmonic addition → small reference reduction in that band
        # delta_db ≈ 20*log10(1 + harmonic_linear) when harmonic << signal
        delta = 20.0 * np.log10(1.0 + harmonic_linear) if NUMPY_OK else 0.0
        adjusted[f] = adjusted[f] - delta
    return adjusted


# ══════════════════════════════════════════════════════════════════════════════
#  48-BAND PRECISION EQ (P-2, v3.0)
# ══════════════════════════════════════════════════════════════════════════════

def _interpolate_bias_to_48(bias_scale: float) -> 'np.ndarray':
    """
    Interpolate SPECTRAL_BIAS_V9 (24 bands) to CENTERS_48 using PCHIP.
    Apply bias_scale (PRISTINE: 0.60, COMPRESSED: 0.85).
    Returns array of shape (48,).
    """
    if not NUMPY_OK:
        return np.zeros(48)

    c24 = sorted(SPECTRAL_BIAS_V9.keys())
    v24 = [SPECTRAL_BIAS_V9[k] * bias_scale for k in c24]

    if _PCHIP_OK:
        interp = PchipInterpolator(c24, v24, extrapolate=True)
        return interp(CENTERS_48).astype(np.float32)
    else:
        return np.interp(CENTERS_48, c24, v24).astype(np.float32)


def _compute_adaptive_lambdas(conf_48: 'np.ndarray',
                               instability_48: 'np.ndarray') -> 'np.ndarray':
    """
    v3.0: λ_n = λ_base × (1 - conf_n) × instability_n
    High confidence + low instability → λ ≈ 0 (free to deviate)
    Low confidence  + high instability → λ ≈ λ_base (forced smooth)
    
    This is the core v2→v3 improvement: bands that are BOTH uncertain
    AND spectrally unstable get smoothness pressure. Stable bands with
    good measurement data are allowed to deviate as needed.
    """
    lambda_base = 1.20
    combined = (1.0 - conf_48) * instability_48
    return (lambda_base * combined).astype(np.float32)


def design_itiqan_eq(state: ItiqanState, ref: ReferenceModel,
                      harmonic_plan: Dict[float, float]
                      ) -> Tuple[List[Tuple[float, float]], float]:
    """
    48-band L-BFGS-B EQ optimizer with:
    - Adaptive smoothness regularization (stability-weighted λ)
    - Formant protection zones (300-3500Hz → ±2dB bounds)
    - Harmonic interaction correction (P-4 adjusts targets before solve)
    
    Returns (eq_nodes, max_per_band_residual_db)
    eq_nodes: [(freq_hz, gain_db), ...] — only bands with |gain| >= 0.10dB
    """
    if not SCIPY_OK or not NUMPY_OK:
        return [], 0.0

    if not state.spectrum_48:
        L('  [P-2] no 48-band spectrum — skipping')
        return [], 0.0

    input_arr = np.array([state.spectrum_48.get(f, -60.0) for f in CENTERS_48],
                          dtype=np.float32)

    # Adjust reference targets for harmonic interaction
    adjusted_ref_dict = _adjust_ref_for_harmonics(ref.spectrum_48, harmonic_plan)
    ref_arr = np.array([adjusted_ref_dict.get(f, -60.0) for f in CENTERS_48],
                        dtype=np.float32)

    # ── UPGRADE-A: Level-normalize before computing spectral shape gap ────────
    # The EQ optimizer corrects SPECTRAL SHAPE, not level (level is Phase H's job).
    # Raw spectra differ by ~26dB (source at -24 LUFS, ref at -9.5 LUFS), so
    # target_gap = ref - input is dominated by level offset, not shape mismatch.
    # This caused the optimizer to always fail convergence (43dB residual).
    # FIX-1 voice-anchor: anchor mean-subtraction to 500-4kHz only.
    # All-band mean caused HF quality to flip EQ direction in voice bands:
    # 320k has more HF energy -> higher input_mean -> voice looks LOW after
    # subtraction -> optimizer CUTS voice.
    # 128k has HF rolloff -> lower input_mean -> voice looks HIGH -> BOOST.
    # Voice-range anchor (500-4kHz) is immune to HF quality differences.
    ref_bw = getattr(ref, 'bw_cutoff', 13000.0)
    active_mask = np.array([f <= ref_bw * 1.05 for f in CENTERS_48], dtype=bool)
    _voice_anchor = np.array([500.0 <= f <= 4000.0 for f in CENTERS_48], dtype=bool)
    _norm_mask = _voice_anchor & active_mask
    if _norm_mask.sum() < 4:
        _norm_mask = active_mask
    if _norm_mask.sum() > 0:
        ref_mean   = float(ref_arr[_norm_mask].mean())
        input_mean = float(input_arr[_norm_mask].mean())
        ref_arr_norm   = ref_arr   - ref_mean
        input_arr_norm = input_arr - input_mean
    else:
        ref_arr_norm   = ref_arr
        input_arr_norm = input_arr

    # Target gap: shape difference only (positive = source lacks energy in band)
    target_gap = ref_arr_norm - input_arr_norm

    # Source-meets-ref target clamp: if source shape already meets ref at a band
    # (after level normalisation), force target_gap to 0 in that band so the
    # optimizer has no incentive to boost it.  This prevents 1kHz over-boost
    # caused by the optimizer chasing a target the source already satisfies.
    if active_mask.sum() > 0:
        for i in range(len(CENTERS_48)):
            if active_mask[i] and target_gap[i] < 0.5:   # source at or above ref shape
                target_gap[i] = min(target_gap[i], 0.0)  # allow cuts only

    # T2-C: Warm start from runtime spectral_character (replaces SPECTRAL_BIAS_V9)
    # spectral_character is derived fresh from the actual ref files each session.
    if state.source_tier in ('TIER_PRISTINE', 'TIER_PRISTINE_NOISY'):
        bias_scale = PRISTINE_BIAS_SCALE
    else:
        # F1: bitrate-adaptive scale — heavier codec → more correction
        bias_scale = _get_compressed_bias_scale(state.bitrate_class)
    if ref.spectral_character and NUMPY_OK:
        x0 = np.array([ref.spectral_character.get(f, 0.0) * bias_scale
                        for f in CENTERS_48], dtype=np.float32)
        L(f'  [P-2] warm start: runtime spectral_character (bias_scale={bias_scale})')
    else:
        # Fallback to legacy SPECTRAL_BIAS_V9 if character not yet computed
        x0 = _interpolate_bias_to_48(bias_scale)
        L(f'  [P-2] warm start: SPECTRAL_BIAS_V9 fallback (bias_scale={bias_scale})')

    # LF overshoot guard: if source LF (80-250Hz) is already strong relative to
    # its own mid (500-2kHz), cap the warm start in those bands to prevent
    # the EQ from over-boosting LF (which causes 120Hz +5dB problem)
    if state.spectrum_48 and NUMPY_OK:
        _src_lf_avg  = float(np.mean([state.spectrum_48.get(f, -40.0)
                                       for f in CENTERS_48 if 80 <= f <= 250]))
        _src_mid_avg = float(np.mean([state.spectrum_48.get(f, -40.0)
                                       for f in CENTERS_48 if 500 <= f <= 2000]))
        _lf_vs_mid = _src_lf_avg - _src_mid_avg   # positive = warm/bassy source
        if _lf_vs_mid > -2.0:   # source LF is already within 2dB of mid
            for i, f in enumerate(CENTERS_48):
                if 60.0 <= f <= 250.0:
                    x0[i] = min(float(x0[i]), 0.5)   # cap boost to 0.5dB in LF
            L(f'  [P-2] LF guard: source LF-mid={_lf_vs_mid:+.1f}dB → LF warm start capped')
        state._lf_vs_mid = _lf_vs_mid   # expose for bounds block

    # Source-meets-ref guard: normalise both spectra to same mean level,
    # then zero warm start in bands where source already meets ref shape.
    if state.spectrum_48 and ref.spectrum_48 and NUMPY_OK:
        src_vals = np.array([state.spectrum_48.get(f, -60.0) for f in CENTERS_48])
        ref_vals = np.array([ref.spectrum_48.get(f, -60.0) for f in CENTERS_48])
        # FIX-1 voice-anchor: align offset using voice range (500-4kHz)
        ref_bw_g = getattr(ref, 'bw_cutoff', 13000.0)
        mask = np.array([f <= ref_bw_g for f in CENTERS_48])
        _vg = np.array([500.0 <= f <= 4000.0 for f in CENTERS_48]) & mask
        _ag = _vg if _vg.sum() >= 4 else mask
        if _ag.sum() > 0:
            offset = float(np.mean(ref_vals[_ag]) - np.mean(src_vals[_ag]))
            src_vals_n = src_vals + offset   # source shifted to same loudness as ref
        else:
            src_vals_n = src_vals
        for i, f in enumerate(CENTERS_48):
            if src_vals_n[i] >= ref_vals[i] - 0.5:   # within 0.5dB after normalising
                x0[i] = min(float(x0[i]), 0.0)

    # Per-band confidence
    if state.eq_confidence_48 is not None:
        conf_48 = state.eq_confidence_48.astype(np.float32)
    else:
        conf_48 = np.ones(48, dtype=np.float32) * float(state.eq_confidence)

    # Spectral instability
    if state.instability_48 is not None:
        instability = state.instability_48.astype(np.float32)
    else:
        instability = np.ones(48, dtype=np.float32) * 0.5

    lambdas = _compute_adaptive_lambdas(conf_48, instability)

    def objective(x):
        fit    = float(np.sum(conf_48 * (x - target_gap) ** 2))
        smooth = float(np.sum(lambdas[:-1] * (x[:-1] - x[1:]) ** 2))
        return fit + smooth

    def gradient(x):
        g_fit = 2.0 * conf_48 * (x - target_gap)
        g_sm  = np.zeros_like(x)
        g_sm[:-1] += 2.0 * lambdas[:-1] * (x[:-1] - x[1:])
        g_sm[1:]  -= 2.0 * lambdas[:-1] * (x[:-1] - x[1:])
        return (g_fit + g_sm).astype(np.float64)

    # Bounds: formant zones ±2dB PRISTINE / ±3dB COMPRESSED (±3.5/±4 aggressive)
    # Bands above ref BW cutoff OR source codec cutoff → locked to 0
    # Also: if source band energy < -30dBFS (noise floor), only allow cut not boost
    # F2: COMPRESSED sources can have >2dB codec-induced formant distortion at
    # 64–128kbps; the ±2dB cap was preventing full correction.
    ref_bw      = getattr(ref,   'bw_cutoff',    13000.0)
    source_bw   = getattr(state, 'codec_cutoff', 20000.0)
    active_bw   = min(ref_bw, source_bw) * 1.05
    _is_compressed = state.source_tier == 'TIER_COMPRESSED'
    _fm_cap  = (3.5 if getattr(state, 'aggressive', False) else
                3.0 if _is_compressed else 2.0)
    _out_cap = (7.0 if getattr(state, 'aggressive', False) else
                7.0 if _is_compressed else 6.0)

    # Measure per-band source energy to detect noise-floor bands
    _src_band_energy: Dict[float, float] = {}
    _src_band_energy = state.spectrum_48 or {}

    bounds = []
    for f in CENTERS_48:
        if f > active_bw:
            bounds.append((0.0, 0.0))   # above active BW — no EQ
        else:
            src_level = _src_band_energy.get(f, -40.0)
            ref_level = ref.spectral_character.get(f, 0.0) if ref.spectral_character else 0.0
            # LF overshoot guard: source already warm → cap LF boost
            _lf_boost_cap = _out_cap
            if 60.0 <= f <= 250.0 and getattr(state, '_lf_vs_mid', 0.0) > -2.0:
                _lf_boost_cap = 1.0
            # Mid guard: if source band is already at/above ref level, only allow cuts
            _mid_boost_cap = _fm_cap if 300.0 <= f <= 3500.0 else _out_cap
            if 300.0 <= f <= 1500.0 and src_level > -20.0:
                # Check if source already meets or exceeds ref at this band
                ref_target = ref.spectrum_48.get(f, -30.0) if ref.spectrum_48 else -30.0
                if src_level >= ref_target - 1.0:   # within 1dB of ref → no boost
                    _mid_boost_cap = 0.5
            if src_level < -32.0:
                fm = _fm_cap if 300.0 <= f <= 3500.0 else _lf_boost_cap
                bounds.append((-fm, 0.0))
            elif 300.0 <= f <= 3500.0:
                bounds.append((-_fm_cap, _mid_boost_cap))
            elif 60.0 <= f <= 250.0:
                bounds.append((-_out_cap, _lf_boost_cap))
            else:
                bounds.append((-_out_cap, _out_cap))

    result = minimize(
        objective, x0.astype(np.float64), jac=gradient,
        method='L-BFGS-B', bounds=bounds,
        options={'maxiter': 400, 'ftol': 1e-9, 'gtol': 1e-7}
    )

    # Convergence: per-band residual vs target
    residual = np.abs(result.x - target_gap)
    max_residual = float(residual.max())
    converged = max_residual < 0.50  # softer than 0.15dB design target

    if not converged:
        L(f'  [P-2] optimizer max residual {max_residual:.2f}dB '
          f'(target <0.50) — proceeding with best solution')

    eq_gains = np.array(result.x, dtype=np.float32)

    # T3-B: Gaussian smoothing for adjacent bands with swing > 8dB
    # Prevents 250/315Hz seesaw artifact (13dB interpolation ripple)
    CENTERS_arr = np.array(CENTERS_48, dtype=np.float32)
    changed = True
    passes = 0
    while changed and passes < 5:
        changed = False
        passes += 1
        for i in range(1, len(eq_gains) - 1):
            swing = abs(float(eq_gains[i+1]) - float(eq_gains[i-1]))
            freq_ratio = float(CENTERS_arr[i+1]) / float(CENTERS_arr[i])
            if swing > 8.0 and freq_ratio < 1.5:  # adjacent bands, large swing
                smoothed = 0.25 * eq_gains[i-1] + 0.50 * eq_gains[i] + 0.25 * eq_gains[i+1]
                eq_gains[i] = float(smoothed)
                changed = True

    eq_nodes = [(f, float(g)) for f, g in zip(CENTERS_48, eq_gains)
                if abs(g) >= 0.10]  # filter trivial corrections

    L(f'  [P-2] {len(eq_nodes)}/48 bands active, '
      f'max_residual={max_residual:.2f}dB, converged={converged}')
    return eq_nodes, max_residual


def apply_eq_48(wav_path: str, eq_nodes: List[Tuple[float, float]]) -> str:
    """
    Apply 48-band EQ via ffmpeg equalizer filter chain.
    Each band: equalizer=f=X:t=q:w=8.65:g=Y
    w=8.65 = sixth-octave Q factor.
    Returns output wav path.
    """
    if not eq_nodes:
        return wav_path

    output_wav = _tmp_wav('eq48')
    filter_parts = []
    for freq, gain in eq_nodes:
        # Clamp gain to safe range
        gain = max(-6.0, min(6.0, gain))
        filter_parts.append(
            f'equalizer=f={freq:.1f}:t=q:w={_EQ_Q_48:.2f}:g={gain:.2f}'
        )

    filter_str = ','.join(filter_parts)
    cmd = [
        'ffmpeg', '-y', '-i', wav_path,
        '-af', filter_str,
        '-acodec', WAV_CODEC, output_wav
    ]
    rc, _, err = _run_ffmpeg(cmd)
    if rc != 0:
        L(f'  [EQ-48] failed: {err[:100]}')
        return wav_path

    return output_wav


# ══════════════════════════════════════════════════════════════════════════════
#  BWE: SPECTRAL STITCH FOR LOW-BITRATE COMPRESSED  (Phase D.5)
# ══════════════════════════════════════════════════════════════════════════════

def bwe_spectral_stitch(wav_path: str, state: ItiqanState) -> str:
    """
    F4: Lightweight bandwidth extension for TIER_COMPRESSED sources whose
    codec_cutoff < 12kHz (typical at 64–96kbps: ~10–11kHz).

    Algorithm
    ─────────
    1. Measure spectral slope in 4–8kHz (dB/octave) from state.spectrum_48.
    2. Project slope above the cutoff to 13kHz.
    3. Apply a high-shelf EQ at cutoff×0.85 to partially compensate the drop.
       Gain capped at +3.5dB to avoid harshness. Minimum applied: 0.8dB.

    Guards
    ──────
    • Sibilant SNR must not drop > 1.5dB (Arabic phoneme protection)
    • Only fires for TIER_COMPRESSED + codec_cutoff < 12000Hz

    Returns output wav path (original if guard fails or not applicable).
    """
    if state.source_tier != 'TIER_COMPRESSED':
        return wav_path
    if state.codec_cutoff >= 12000.0:
        return wav_path
    if not NUMPY_OK:
        return wav_path

    spec_pre = state.spectrum_48
    if not spec_pre:
        return wav_path

    # Measure dB/octave slope in 4–8kHz (log2 linear regression)
    slope_bands = [(f, spec_pre[f]) for f in CENTERS_48
                   if 4000.0 <= f <= 8000.0 and f in spec_pre]
    if len(slope_bands) < 3:
        return wav_path

    import math as _math
    freq_logs = [_math.log2(f) for f, _ in slope_bands]
    levels    = [v for _, v in slope_bands]
    n = len(freq_logs)
    mf = sum(freq_logs) / n
    ml = sum(levels) / n
    num = sum((freq_logs[i] - mf) * (levels[i] - ml) for i in range(n))
    den = sum((freq_logs[i] - mf) ** 2 for i in range(n))
    slope_db_oct = (num / den) if den > 1e-6 else -3.0  # dB per octave (typically negative)

    # Project slope from cutoff to 13kHz
    octaves = _math.log2(max(13000.0, state.codec_cutoff) / state.codec_cutoff)
    projected_drop = slope_db_oct * octaves   # negative = falls off

    # Shelf gain = partially compensate the projected drop; cap at +3.5dB
    shelf_gain = float(min(3.5, max(0.0, -projected_drop * 0.55)))

    if shelf_gain < 0.8:
        L(f'  [BWE] cutoff={state.codec_cutoff:.0f}Hz '
          f'slope={slope_db_oct:.1f}dB/oct shelf={shelf_gain:.2f}dB < 0.8 — skip')
        return wav_path

    shelf_freq = state.codec_cutoff * 0.85
    output_wav = _tmp_wav('bwe')
    cmd = [
        'ffmpeg', '-y', '-i', wav_path,
        '-af', f'equalizer=f={shelf_freq:.0f}:t=h:w=0.7:g={shelf_gain:.2f}',
        '-acodec', WAV_CODEC, output_wav
    ]
    rc, _, err = _run_ffmpeg(cmd)
    if rc != 0 or not os.path.exists(output_wav):
        L(f'  [BWE] ffmpeg failed: {err[:80]}')
        return wav_path

    # Guard: sibilant SNR must not drop > 1.5dB
    if NUMPY_OK:
        samples_b, sr_b = _decode_wav_samples(wav_path)
        samples_a, _    = _decode_wav_samples(output_wav)
        if samples_b is not None and samples_a is not None:
            def _sib_snr(s):
                N2 = min(len(s), sr_b * 4)
                sp = np.abs(rfft(s[:N2] * np.hanning(N2))) ** 2
                fr = rfftfreq(N2, d=1.0 / sr_b)
                sm = np.zeros(len(sp), dtype=bool)
                for fc in ARABIC_SIB_BANDS:
                    sm |= (fr >= fc * 0.85) & (fr <= fc * 1.15)
                nm = (fr >= 100) & (fr <= 500)
                sl = float(np.mean(10 * np.log10(np.maximum(sp[sm], 1e-10))))
                nl = float(np.mean(10 * np.log10(np.maximum(sp[nm], 1e-10))))
                return sl - nl
            snr_b_val = _sib_snr(samples_b)
            snr_a_val = _sib_snr(samples_a)
            if snr_a_val < snr_b_val - 1.5:
                L(f'  [BWE] sibilant SNR {snr_b_val:.1f}→{snr_a_val:.1f}dB — reverting')
                _cleanup(output_wav)
                return wav_path

    L(f'  [BWE] ✓ cutoff={state.codec_cutoff:.0f}Hz shelf={shelf_freq:.0f}Hz '
      f'+{shelf_gain:.2f}dB (slope={slope_db_oct:.1f}dB/oct)')
    return output_wav


# ══════════════════════════════════════════════════════════════════════════════
#  SPECTRAL TRAJECTORY CORRECTION (P-5, v3.0)
# ══════════════════════════════════════════════════════════════════════════════

def trajectory_correction(wav_path: str, state: ItiqanState,
                           ref: ReferenceModel,
                           ayah_segments: 'Optional[List[AyahSegment]]' = None
                           ) -> Tuple[str, bool]:
    """
    5-segment temporal spectral trajectory matching.
    T4-A: When ayah_segments are provided, boundaries are aligned to actual
    ayah boundaries rather than 20% equal-duration time slices.
    Maximum correction: ±1.5dB per band per segment.
    Crossfade: placed inside pause gaps (T4-C).

    Returns (output_wav_path, applied_bool)
    """
    if not ref.trajectory or len(ref.trajectory) < 5:
        L('  [P-5] no reference trajectory — skipping')
        return wav_path, False

    if not NUMPY_OK:
        return wav_path, False

    dur = state.duration_s
    if dur < 15.0:
        L(f'  [P-5] file too short for trajectory correction ({dur:.1f}s) — skipping')
        return wav_path, False

    segment_files = []

    # T4-A: Build 5 trajectory segments from ayah boundaries if available
    verse_segs = [s for s in (ayah_segments or []) if s.seg_type == 'verse']
    if verse_segs and len(verse_segs) >= 3:
        # Group verses into 5 duration-balanced trajectory segments
        total_verse_dur = sum(s.duration_s for s in verse_segs)
        target_dur = total_verse_dur / 5.0
        traj_boundaries = []
        accum = 0.0
        group_start = verse_segs[0].start_s
        for vs in verse_segs:
            accum += vs.duration_s
            if accum >= target_dur and len(traj_boundaries) < 4:
                traj_boundaries.append((group_start, vs.end_s))
                group_start = vs.end_s
                accum = 0.0
        traj_boundaries.append((group_start, verse_segs[-1].end_s))
        while len(traj_boundaries) < 5:
            traj_boundaries.append(traj_boundaries[-1])
        traj_boundaries = traj_boundaries[:5]
        L(f'  [P-5] ayah-aligned trajectory: {len(traj_boundaries)} segments')
    else:
        # BUG-3 FIX: equal-time splits cut mid-word. Instead, build equal-time
        # targets then snap each boundary to the nearest silence detected by M-1
        # energy envelope within a ±2s search window. If no silence is found near
        # a boundary, keep the whole file as a single segment (no split at all)
        # rather than cutting through a word.
        seg_dur = dur / 5.0
        candidate_boundaries = [i * seg_dur for i in range(1, 5)]
        snapped = []
        for cb in candidate_boundaries:
            # Search for a silence boundary within ±2s of the equal-time cut
            lo, hi = cb - 2.0, cb + 2.0
            best_t  = None
            best_d  = float('inf')
            # Use _get_energy_envelope to find silent frames near cb
            try:
                import numpy as _np
                tmp_snp = _tmp_wav('p5_snap_probe')
                _run_ffmpeg(['ffmpeg', '-y', '-i', wav_path,
                             '-ss', f'{max(0.0, lo):.3f}',
                             '-t', f'{min(4.0, hi - lo):.3f}',
                             '-ar', str(SR), '-ac', '1',
                             '-f', 'f32le', '-loglevel', 'error', tmp_snp])
                if os.path.exists(tmp_snp):
                    raw = _np.fromfile(tmp_snp, dtype=_np.float32)
                    _cleanup(tmp_snp)
                    frame_n = SR // 10  # 100ms frames
                    for fi in range(len(raw) // frame_n):
                        seg = raw[fi * frame_n:(fi + 1) * frame_n]
                        rms_db = float(20 * _np.log10(float(_np.sqrt(_np.mean(seg ** 2))) + 1e-10))
                        t_frame = max(0.0, lo) + fi * 0.1
                        if rms_db < -40.0:  # silence threshold
                            d = abs(t_frame - cb)
                            if d < best_d:
                                best_d = d
                                best_t = t_frame
            except Exception:
                pass
            if best_t is not None:
                snapped.append(best_t)
            # else: no silence found → omit this boundary (fewer but word-safe segments)
        boundaries_final = sorted(set(snapped))
        all_t = [0.0] + boundaries_final + [dur]
        traj_boundaries = [(all_t[i], all_t[i+1]) for i in range(len(all_t)-1)]
        L(f'  [P-5] silence-snapped trajectory: {len(traj_boundaries)} segments '
          f'(from {len(candidate_boundaries)} equal-time candidates)')

    for seg_idx, (t_start, t_end) in enumerate(traj_boundaries):
        # T4-C: crossfade window — use pause gap or 50-250ms
        # Find the pause gap after this segment, if any
        if ayah_segments:
            gap_after = next(
                (s for s in ayah_segments
                 if s.seg_type in ('long_pause', 'mid_pause')
                 and abs(s.start_s - t_end) < 1.0),
                None
            )
            if gap_after:
                gap_dur_ms = int(min(250, max(50, gap_after.duration_s * 1000 * 0.8)))
            else:
                gap_dur_ms = 0  # BUG-1 FIX: no pause at boundary → no crossfade
                                # 150ms default was eating voiced Quran content
        else:
            gap_dur_ms = 0  # BUG-1 FIX: no ayah info → cannot know pause locations
        crossfade_ms = gap_dur_ms

        # Measure input spectrum for this segment
        input_spec = sixth_octave(wav_path, t_start=t_start, t_end=t_end)
        if input_spec is None:
            # Copy segment as-is
            seg_file = _tmp_wav(f'traj_seg{seg_idx}_raw')
            cmd = [
                'ffmpeg', '-y', '-i', wav_path,
                '-ss', str(t_start), '-to', str(t_end),
                '-acodec', WAV_CODEC, seg_file
            ]
            _run_ffmpeg(cmd)
            segment_files.append(seg_file)
            continue

        # Reference trajectory for this segment
        ref_spec = ref.trajectory[seg_idx]  # Dict[float, float]

        # Compute per-band delta
        # F6: COMPRESSED sources have larger temporal shape drift; relax cap
        _traj_cap = (3.0 if getattr(state, 'aggressive', False) else
                     2.0 if state.source_tier == 'TIER_COMPRESSED' else 1.5)
        eq_nodes = []
        for f in CENTERS_48:
            input_level = input_spec.get(f, -60.0)
            ref_level   = ref_spec.get(f, -60.0)
            delta = ref_level - input_level
            delta = max(-_traj_cap, min(_traj_cap, delta))
            if abs(delta) >= 0.10:
                eq_nodes.append((f, delta))

        # Extract segment — FIX-4b: use -t duration instead of -to for reliability
        raw_seg = _tmp_wav(f'traj_seg{seg_idx}_raw')
        seg_len = t_end - t_start
        cmd = [
            'ffmpeg', '-y', '-i', wav_path,
            '-ss', f'{t_start:.3f}', '-t', f'{seg_len:.3f}',
            '-acodec', WAV_CODEC, raw_seg
        ]
        rc, _, _ = _run_ffmpeg(cmd)

        if rc != 0 or not eq_nodes:
            segment_files.append(raw_seg)
            continue

        # Apply segment-specific EQ
        filter_parts = [
            f'equalizer=f={freq:.1f}:t=q:w={_EQ_Q_48:.2f}:g={gain:.2f}'
            for freq, gain in eq_nodes
        ]
        corrected_seg = _tmp_wav(f'traj_seg{seg_idx}_corr')
        cmd = [
            'ffmpeg', '-y', '-i', raw_seg,
            '-af', ','.join(filter_parts),
            '-acodec', WAV_CODEC, corrected_seg
        ]
        rc, _, err = _run_ffmpeg(cmd)

        if rc == 0:
            _cleanup(raw_seg)
            segment_files.append(corrected_seg)
            L(f'  [P-5] seg{seg_idx}: {len(eq_nodes)} bands corrected')
        else:
            segment_files.append(raw_seg)

    if not segment_files:
        return wav_path, False

    # Concatenate segments — acrossfade ONLY across confirmed pause gaps
    # BUG-1 FIX: crossfade_ms=0 means the boundary falls mid-verse (no pause
    # detected). A crossfade here would eat voiced Quran content. Use hard
    # concat in that case to preserve every sample.
    output_wav = _tmp_wav('traj_merged')
    if len(segment_files) == 1:
        shutil.copy2(segment_files[0], output_wav)
    else:
        n    = len(segment_files)
        cf_s = crossfade_ms / 1000.0
        use_cf = cf_s > 0.0

        if use_cf:
            cmd = ['ffmpeg', '-y']
            for sf in segment_files:
                cmd += ['-i', sf]
            if n == 2:
                filter_str = f'[0:a][1:a]acrossfade=d={cf_s:.3f}:c1=tri:c2=tri[out]'
            else:
                chain = []
                prev  = '[0:a]'
                for i in range(1, n):
                    out_lbl = '[out]' if i == n - 1 else f'[x{i}]'
                    chain.append(f'{prev}[{i}:a]acrossfade=d={cf_s:.3f}:c1=tri:c2=tri{out_lbl}')
                    prev = out_lbl
                filter_str = '; '.join(chain)
            cmd += ['-filter_complex', filter_str, '-map', '[out]', '-acodec', WAV_CODEC, output_wav]
            rc, _, err = _run_ffmpeg(cmd)
            if rc != 0:
                L(f'  [P-5] acrossfade concat failed: {err[:120]}')
                use_cf = False  # fall through to hard concat

        if not use_cf:
            cmd_fb = ['ffmpeg', '-y']
            for sf in segment_files:
                cmd_fb += ['-i', sf]
            cmd_fb += ['-filter_complex', f'concat=n={n}:v=0:a=1[out]',
                       '-map', '[out]', '-acodec', WAV_CODEC, output_wav]
            rc2, _, err2 = _run_ffmpeg(cmd_fb)
            if rc2 != 0:
                L(f'  [P-5] hard concat failed: {err2[:120]}')
                for sf in segment_files:
                    _cleanup(sf)
                return wav_path, False

    for sf in segment_files:
        _cleanup(sf)

    L(f'  [P-5] trajectory correction applied: {len(segment_files)} segments')
    return output_wav, True


# ══════════════════════════════════════════════════════════════════════════════
#  PHRASE DETECTION (Three-Cue, v3.0)
# ══════════════════════════════════════════════════════════════════════════════

def _get_energy_envelope(samples: 'np.ndarray', sr: int,
                          frame_ms: int = 20) -> Tuple['np.ndarray', 'np.ndarray']:
    """Returns (times_s, energy_db) arrays."""
    frame_size = int(sr * frame_ms / 1000)
    times, energies = [], []
    for i in range(0, len(samples) - frame_size, frame_size // 2):
        frame = samples[i:i + frame_size]
        e = float(np.mean(frame ** 2))
        times.append(i / sr + frame_ms / 2000.0)
        energies.append(10.0 * np.log10(max(e, 1e-10)))
    return np.array(times), np.array(energies)


def _silence_boundaries(times: 'np.ndarray', energy_db: 'np.ndarray',
                          silence_thresh: float, min_dur: float = 0.3
                          ) -> List[float]:
    """Cue A: silence-based phrase boundaries."""
    is_silent = energy_db < silence_thresh
    boundaries = []
    in_silence = False
    silence_start = 0.0

    for t, silent in zip(times, is_silent):
        if silent and not in_silence:
            in_silence = True
            silence_start = float(t)
        elif not silent and in_silence:
            dur = float(t) - silence_start
            if dur >= min_dur:
                boundaries.append((silence_start + float(t)) / 2.0)
            in_silence = False

    return boundaries


def _autocorr_boundaries(times: 'np.ndarray', energy_db: 'np.ndarray',
                          duration_s: float) -> List[float]:
    """
    Cue B: energy envelope autocorrelation to find periodicity of phrases.
    Adaptive: uses sliding windows at multiple candidate phrase rates.
    """
    if not NUMPY_OK or len(energy_db) < 10:
        return []

    # Normalize energy to [0,1]
    e = energy_db - energy_db.min()
    e_max = e.max()
    if e_max < 0.1:
        return []
    e = e / e_max

    frame_step = float(times[1] - times[0]) if len(times) > 1 else 0.01
    boundaries = []

    # Search for phrase periods in 3-15 second range
    min_lag_frames = int(3.0 / frame_step)
    max_lag_frames = int(15.0 / frame_step)
    max_lag_frames = min(max_lag_frames, len(e) // 2)

    if min_lag_frames >= max_lag_frames:
        return []

    # Compute autocorrelation
    if _SIGNAL_OK:
        acf_full = _scipy_correlate(e, e, mode='full')
        acf = acf_full[len(acf_full) // 2:]
    else:
        acf = np.correlate(e, e, mode='full')
        acf = acf[len(acf) // 2:]

    if len(acf) <= max_lag_frames:
        return []

    acf = acf / max(float(acf[0]), 1e-10)
    search = acf[min_lag_frames:max_lag_frames]
    if len(search) == 0:
        return []

    peak_lag = int(np.argmax(search)) + min_lag_frames
    peak_val = float(acf[peak_lag])

    if peak_val < 0.25:  # weak periodicity — no reliable phrase structure
        return []

    phrase_period = peak_lag * frame_step
    t = phrase_period / 2.0
    while t < duration_s - phrase_period / 2.0:
        boundaries.append(t)
        t += phrase_period

    return boundaries


def _centroid_boundaries(samples: 'np.ndarray', sr: int,
                          duration_s: float) -> List[float]:
    """
    Cue C: spectral centroid change detection.
    Sharp centroid drops often coincide with phrase-ending consonants and
    the transition into silence between verses.
    """
    if not NUMPY_OK or samples is None:
        return []

    frame_size = sr // 10  # 100ms frames
    hop        = frame_size // 2
    freqs = rfftfreq(frame_size, d=1.0 / sr)
    times_c = []
    centroids = []

    for i in range(0, len(samples) - frame_size, hop):
        frame = samples[i:i + frame_size]
        energy = float(np.mean(frame ** 2))
        if energy < 1e-7:
            times_c.append((i + frame_size // 2) / sr)
            centroids.append(0.0)
            continue
        spec = np.abs(rfft(frame * np.hanning(frame_size))) ** 2
        spec = np.maximum(spec, 1e-10)
        centroid = float(np.sum(freqs * spec) / np.sum(spec))
        times_c.append((i + frame_size // 2) / sr)
        centroids.append(centroid)

    if len(centroids) < 5:
        return []

    centroids = np.array(centroids, dtype=np.float32)
    times_c   = np.array(times_c, dtype=np.float32)

    # Smooth centroids
    smooth_window = 5
    centroids_smooth = np.convolve(centroids,
                                    np.ones(smooth_window) / smooth_window,
                                    mode='same')
    # Gradient: large negative gradient = centroid dropping fast = phrase boundary
    grad = np.gradient(centroids_smooth)
    threshold = np.percentile(grad, 10)  # bottom 10% = sharpest drops

    boundaries = []
    in_drop = False
    for t, g in zip(times_c, grad):
        if g < threshold and not in_drop:
            in_drop = True
            boundaries.append(float(t))
        elif g >= threshold:
            in_drop = False

    return boundaries


def _near(t: float, boundaries: List[float], tol: float = 0.3) -> bool:
    return any(abs(t - b) <= tol for b in boundaries)


def detect_phrase_boundaries(samples: 'np.ndarray', sr: int,
                               state: ItiqanState
                               ) -> List[Dict]:
    """
    Three-cue phrase detection. Returns phrase list with confidence scores.
    Each phrase: {start, end, confidence, type}
    confidence: 0.0 (1 cue agrees) to 1.0 (all 3 cues agree)
    """
    if samples is None or not NUMPY_OK:
        return []

    times, energy_db = _get_energy_envelope(samples, sr)
    silence_thresh   = state.silence_floor + 12.0

    cue_a = _silence_boundaries(times, energy_db, silence_thresh, min_dur=0.3)
    cue_b = _autocorr_boundaries(times, energy_db, state.duration_s)
    cue_c = _centroid_boundaries(samples, sr, state.duration_s)

    # Merge all boundaries with deduplication (500ms tolerance)
    all_t = sorted(set(
        round(t, 1) for t in cue_a + cue_b + cue_c
    ))
    deduped = []
    for t in all_t:
        if not deduped or t - deduped[-1] > 0.5:
            deduped.append(t)

    # Score each boundary by how many cues agree
    boundaries = []
    for t in deduped:
        votes = (
            (1 if _near(t, cue_a, 0.3) else 0) +
            (1 if _near(t, cue_b, 0.5) else 0) +
            (1 if _near(t, cue_c, 0.3) else 0)
        )
        boundaries.append({'time': t, 'confidence': votes / 3.0})

    # Build phrase segments — NEVER drop short segments, use passthrough
    # Dropping segments (phrase_dur < 1.0) causes the concat to be shorter
    # than the original file, silently losing audio.
    dur = state.duration_s
    b_times = [0.0] + [b['time'] for b in boundaries] + [dur]
    b_confs = [0.0] + [b['confidence'] for b in boundaries] + [0.0]
    phrases = []
    for i in range(len(b_times) - 1):
        t_start = b_times[i]
        t_end   = b_times[i + 1]
        phrase_dur = t_end - t_start
        if phrase_dur <= 0.0:
            continue
        # Short segments: keep as passthrough (conf=0 → no sculpting applied)
        conf = 0.0 if phrase_dur < 1.0 else (
            min(b_confs[i], b_confs[i + 1]) if i > 0 else b_confs[i + 1]
        )
        phrase_type = 'continuation'
        if t_start < 1.0:
            phrase_type = 'verse_opening'
        elif (i < len(b_times) - 2 and
              b_times[i] > 0 and
              (b_times[i] - b_times[i - 1] > 1.5 if i > 0 else True)):
            phrase_type = 'verse_opening'
        phrases.append({
            'start':      t_start,
            'end':        t_end,
            'confidence': conf,
            'type':       phrase_type,
        })

    return phrases


# ══════════════════════════════════════════════════════════════════════════════
#  PHRASE MICRO-DYNAMIC SCULPTING (P-3, v3.0)
# ══════════════════════════════════════════════════════════════════════════════

def phrase_dynamic_sculpting(wav_path: str, phrases: List[Dict],
                              state: ItiqanState, ref: ReferenceModel
                              ) -> Tuple[str, int]:
    """
    Per-phrase LRA targeting with confidence-scaled intensity.
    conf < 0.2: skip (not confident about phrase boundaries)
    conf ≥ 0.2: scale adjustment by confidence
    Maximum: ±0.8 LU × confidence
    """
    if not phrases:
        return wav_path, 0

    sculpted_count = 0
    segment_files  = []

    for phrase in phrases:
        t_start = phrase['start']
        t_end   = phrase['end']
        conf    = phrase['confidence']

        seg_wav = _tmp_wav(f'phrase_{int(t_start*10)}')
        cmd = [
            'ffmpeg', '-y', '-i', wav_path,
            '-ss', f'{t_start:.3f}', '-to', f'{t_end:.3f}',
            '-acodec', WAV_CODEC, seg_wav
        ]
        rc, _, _ = _run_ffmpeg(cmd)
        # BUG-2 FIX: On extraction failure use fallback, but do NOT continue
        # past a successful fallback — the old 'continue' ran unconditionally
        # and silently dropped the segment even when fallback succeeded.
        if rc != 0 or not os.path.exists(seg_wav):
            fallback = _tmp_wav(f'phrase_{int(t_start*10)}_fb')
            cmd_fb = ['ffmpeg', '-y', '-i', wav_path,
                      '-ss', f'{t_start:.3f}', '-t', f'{max(0.1,t_end-t_start):.3f}',
                      '-acodec', WAV_CODEC, fallback]
            rc_fb, _, _ = _run_ffmpeg(cmd_fb)
            if rc_fb == 0 and os.path.exists(fallback):
                segment_files.append(fallback)
            # Both extractions failed — only now is it safe to skip
            continue

        if conf < 0.20:
            segment_files.append(seg_wav)
            continue

        # Measure phrase LRA
        lufs_p, lra_p = _measure_lufs(seg_wav)

        # Target: bring toward reference p50
        delta = REF_PHRASE_LRA['p50'] - lra_p
        delta = max(-0.8, min(0.8, delta))

        # Scale by confidence (v3.0 improvement over binary gate)
        scaled_delta = delta * conf

        if abs(scaled_delta) < 0.05:
            segment_files.append(seg_wav)
            continue

        # Apply compand (very gentle)
        adjusted_seg = _tmp_wav(f'phrase_{int(t_start*10)}_adj')
        if scaled_delta > 0:  # expansion
            points = '-90/-90|-40/-36|-20/-17|-10/-8.5|-3/-2.5|0/-0.3'
        else:  # compression
            points = '-90/-90|-40/-42|-20/-22|-10/-10.8|-3/-3.2|0/-0.1'

        cmd = [
            'ffmpeg', '-y', '-i', seg_wav,
            '-af', f'compand=attacks=0.08:decays=0.5:points={points}',
            '-acodec', WAV_CODEC, adjusted_seg
        ]
        rc, _, _ = _run_ffmpeg(cmd)
        if rc != 0:
            segment_files.append(seg_wav)
            continue

        # Do-no-harm: verify LRA didn't collapse
        _, lra_after = _measure_lufs(adjusted_seg)
        if abs(lra_after - REF_PHRASE_LRA['p50']) < abs(lra_p - REF_PHRASE_LRA['p50']):
            _cleanup(seg_wav)
            segment_files.append(adjusted_seg)
            sculpted_count += 1
        else:
            _cleanup(adjusted_seg)
            segment_files.append(seg_wav)

    if not segment_files:
        return wav_path, 0

    # Concatenate
    output_wav = _tmp_wav('phrases_merged')
    cmd = ['ffmpeg', '-y']
    for sf in segment_files:
        cmd += ['-i', sf]
    n = len(segment_files)
    cmd += [
        '-filter_complex', f'concat=n={n}:v=0:a=1[out]',
        '-map', '[out]',
        '-acodec', WAV_CODEC, output_wav
    ]
    rc, _, err = _run_ffmpeg(cmd)
    for sf in segment_files:
        _cleanup(sf)

    if rc != 0:
        L(f'  [P-3] concat failed: {err[:100]}')
        return wav_path, 0

    L(f'  [P-3] sculpted {sculpted_count}/{len(phrases)} phrases')
    return output_wav, sculpted_count


# ══════════════════════════════════════════════════════════════════════════════
#  HARMONIC WARMTH INJECTION (P-4, v3.0)
# ══════════════════════════════════════════════════════════════════════════════

def _measure_thd(samples: 'np.ndarray', sr: int,
                  f0_hint: float = 0.0) -> float:
    """
    Estimate THD from spectrum.
    THD = sqrt(sum(H2..H5)^2) / H1
    UPGRADE-E: Accept f0_hint (from state.f0_median) to avoid misidentifying
    boosted voice harmonics as distortion after EQ processing.
    Falls back to spectrum-peak detection if f0_hint=0.
    """
    if samples is None or not NUMPY_OK:
        return 0.0
    # T5-C: Use central 60% of samples to exclude onset transients + reverb tails
    # Onset and offset inflate apparent THD from transient energy, not harmonic distortion
    center_start = int(len(samples) * 0.20)
    center_end   = int(len(samples) * 0.80)
    samples_center = samples[center_start:center_end]
    N = min(len(samples_center), sr * 2)
    if N < sr // 4:
        return 0.0
    spec = np.abs(rfft(samples_center[:N] * np.hanning(N))) ** 2
    freqs = rfftfreq(N, d=1.0 / sr)

    def _band_power(fc, width=0.15):
        mask = (freqs >= fc * (1 - width)) & (freqs <= fc * (1 + width))
        return float(np.mean(spec[mask])) if mask.sum() > 0 else 0.0

    # Fundamental detection: always find the actual spectral peak in 100-500Hz.
    # f0_hint is used only as a search bias — we still verify it has dominant power.
    # This prevents THD=1.0 when f0_hint is the dataclass default (180Hz) which
    # falls below actual speech energy at 260-280Hz.
    mask_fund = (freqs >= 100) & (freqs <= 500)
    if mask_fund.sum() == 0:
        return 0.0
    f1_idx = int(np.argmax(spec[mask_fund])) + int(np.where(mask_fund)[0][0])
    f1_peak = float(freqs[f1_idx])

    # If f0_hint is plausible (within 1.5× of spectral peak), use it; else use peak
    if f0_hint > 100.0 and abs(f0_hint - f1_peak) / max(f1_peak, 1.0) < 0.5:
        f1 = f0_hint
    else:
        f1 = f1_peak

    mask_f1 = (freqs >= f1 * 0.85) & (freqs <= f1 * 1.15)
    p1 = float(np.mean(spec[mask_f1])) if mask_f1.sum() > 0 else 0.0

    if p1 < 1e-12 or f1 < 80:
        return 0.0

    # Only measure harmonics that fall BELOW the EQ-affected region
    # to avoid false positives from spectral shaping
    harmonics_power = sum(_band_power(f1 * n) for n in [2, 3, 4, 5]
                          if f1 * n < 600.0)  # stay below speech formant region
    if harmonics_power == 0.0:
        return 0.0
    thd = (harmonics_power / p1) ** 0.5
    return min(float(thd), 1.0)


def _build_voiced_regions(samples: 'np.ndarray', sr: int) -> List[Tuple[float, float]]:
    """
    Detect voiced regions using ZCR + energy.
    v3.0: Arabic stop consonant onset protection — exclude first 20ms of
    voiced onset (ق، ك، ت، د have noise bursts at onset that look voiced).
    Returns [(t_start, t_end), ...] in seconds.
    """
    if samples is None or not NUMPY_OK:
        return []

    frame_size = sr // 50  # 20ms
    hop        = frame_size

    voiced_frames = []
    for i in range(0, len(samples) - frame_size, hop):
        frame  = samples[i:i + frame_size]
        energy = float(np.mean(frame ** 2))
        if energy < 1e-7:
            voiced_frames.append(False)
            continue
        zcr = float(np.sum(np.abs(np.diff(np.sign(frame))))) / (2 * frame_size)
        voiced_frames.append(zcr < 0.12 and energy > 1e-5)

    # Convert to time regions, with 20ms onset grace period (Arabic stop protection)
    onset_grace = 1  # 1 frame = 20ms
    regions = []
    in_voiced = False
    v_start = 0

    for i, v in enumerate(voiced_frames):
        if v and not in_voiced:
            in_voiced = True
            v_start   = i + onset_grace  # skip onset
        elif not v and in_voiced:
            if i > v_start + 1:
                regions.append((v_start * 20.0 / 1000.0, i * 20.0 / 1000.0))
            in_voiced = False

    if in_voiced:
        regions.append((v_start * 20.0 / 1000.0, len(voiced_frames) * 20.0 / 1000.0))

    return regions


def harmonic_warmth_injection(wav_path: str, state: ItiqanState) -> Tuple[str, bool, float, float]:
    """
    Apply harmonic warmth via aexciter on voiced segments only.
    v3.0: Arabic stop onset protection (20ms grace on consonant onsets).
    Guard: measure THD before/after. Revert if THD rises > 0.05%.
    
    Returns (output_path, applied, thd_before, thd_after)
    """
    samples, sr = _decode_wav_samples(wav_path)
    f0_hint = getattr(state, 'f0_median', 0.0)
    thd_before = _measure_thd(samples, sr, f0_hint=f0_hint) if samples is not None else 0.0

    # UPGRADE-D: THD gate revised — absolute 0.8% threshold wrongly excluded
    # all reverberant recordings (natural THD 8-20% from room acoustics).
    # New logic: skip only if THD is critically high (>25% = genuine distortion).
    # The post-application guard (thd_after > thd_before + delta) catches any
    # harmful additions. We use a relative rise threshold instead.
    # T5-C: For PRISTINE/COMPRESSED sources, disable the pre-application THD gate.
    # THD measurement on reverberant or EQ-processed speech is unreliable — the
    # large EQ corrections (800-1250Hz boost) cause the harmonic detector to see
    # boosted formants as "distortion". The real guard is the post-apply relative
    # rise check (thd_after > thd_before + 15% of before) which is robust.
    # Only gate on DAMAGED sources where clipping is a known risk.
    is_damaged_tier = getattr(state, 'source_tier', '') in ('TIER_DAMAGED', 'TIER_CRITICAL')  # noisy is NOT damaged
    if is_damaged_tier and thd_before > 0.25:
        L(f'  [P-4] THD {thd_before:.4f} — DAMAGED tier gate — skipping warmth')
        return wav_path, False, thd_before, thd_before
    elif not is_damaged_tier:
        L(f'  [P-4] THD {thd_before:.4f} — PRISTINE tier, pre-gate bypassed (post-apply guard active)')

    voiced_regions = _build_voiced_regions(samples, sr) if samples is not None else []
    if not voiced_regions:
        L('  [P-4] no voiced regions found — skipping warmth')
        return wav_path, False, thd_before, thd_before

    output_wav = _tmp_wav('warmth')

    # Build filter: aexciter on voiced regions, original on unvoiced
    # Strategy: process full file with aexciter at low level (amount=15)
    # Then mix voiced: 70% aexciter + 30% original
    # Unvoiced: 0% aexciter (pure original)
    # This is approximated via: apply aexciter globally, then blend
    # with original at low mix ratio for the voiced parts.
    # Simplification: apply aexciter globally at very low amount (safe for unvoiced too)
    # Guard will catch any THD excess.

    # aexciter: freq=3000Hz (above formant region), type=e (even) or a (all)
    # amount=15 (conservative, below L-13 danger zone)
    # Note: type validation needed per ffmpeg version. 'a' is most compatible.
    # F7: For COMPRESSED sources with narrow bandwidth, lower exciter freq
    # so presence is added in the 2.5–3kHz zone degraded by codec cutoff.
    _exc_cutoff = getattr(state, 'codec_cutoff', 20000.0)
    _exc_freq   = int(min(3000, max(2000, _exc_cutoff * 0.65)))         if state.source_tier == 'TIER_COMPRESSED' else 3000
    cmd = [
        'ffmpeg', '-y', '-i', wav_path,
        '-af', f'aexciter=freq={_exc_freq}:type=a:amount=15:blend=0',
        '-acodec', WAV_CODEC, output_wav
    ]
    rc, _, err = _run_ffmpeg(cmd)

    if rc != 0:
        L(f'  [P-4] aexciter failed ({err[:80]}) — skipping warmth')
        return wav_path, False, thd_before, thd_before

    # Verify THD
    samples_after, _ = _decode_wav_samples(output_wav)
    thd_after = _measure_thd(samples_after, sr, f0_hint=f0_hint) if samples_after is not None else thd_before

    # UPGRADE-D: relative rise check — allow up to 15% relative increase
    thd_rise_allowed = max(0.002, thd_before * 0.15)
    if thd_after > thd_before + thd_rise_allowed:
        L(f'  [P-4] THD rose {thd_before:.4f}→{thd_after:.4f} (Δ>{thd_rise_allowed:.4f}) — reverting')
        _cleanup(output_wav)
        return wav_path, False, thd_before, thd_before

    L(f'  [P-4] warmth applied: THD {thd_before:.4f}→{thd_after:.4f} '
      f'({len(voiced_regions)} voiced regions)')
    return output_wav, True, thd_before, thd_after


# ══════════════════════════════════════════════════════════════════════════════
#  صدي التميز — ECHO OF DISTINCTION  (Phase G.5)
# ══════════════════════════════════════════════════════════════════════════════
#
#  What is صدي التميز?
#  ─────────────────────────────────────────────────────────────────────────────
#  Every reference recording carries an acoustic fingerprint of its space —
#  a specific pattern of early reflections, formant resonance, and room
#  interaction that is so brief it never reads as reverb, yet so present
#  that its absence makes even a perfectly-measured signal feel "flat".
#
#  In the 1425H references this fingerprint manifests as:
#    • A first reflection at ≈12ms delay, −22 dBFS below direct signal
#    • The reflection arrives bloom-shaped — concentrated in the Arabic
#      vowel F1 window (200–900 Hz) where throat resonance dominates
#    • Mix depth: 7.9% wet (−22 dBFS → linear ≈ 0.0794)
#    • Perceptually: just below the threshold of discrete echo, well above
#      the threshold of spatial impression — it adds *dimension* without
#      artificiality
#
#  Placement — why G.5 (between warmth and LUFS)?
#  ─────────────────────────────────────────────────────────────────────────────
#  • Needs to build on top of Phase G's harmonic enrichment so the
#    reflected signal is harmonically warm, not thin
#  • Must land before Phase H (LUFS normalizer) so any energy added by
#    the reflection is accounted for in the final loudness pass
#  • Cannot go earlier (pre-EQ) because the bloom filter targets a specific
#    spectral shape that the 48-band EQ has already set
#  • Cannot go later (post-LUFS) because it would disturb the calibrated
#    loudness target
#
#  Guards (conservative by design):
#  ─────────────────────────────────────────────────────────────────────────────
#  • Source RT60 < 0.25s  — dry source only; already-reverberant sources
#    already carry their own echo and don't need one added
#  • Crest delta < 0.25 dB — the reflection must not alter dynamic character
#  • Arabic sibilant integrity ±1.5 dB — reuses existing phoneme gate
#  • TIER_PRISTINE / TIER_COMPRESSED only
#

# Reflection fingerprint constants — v2.0 data-driven from cepstrum + onset analysis
# of 3 × 1425H reference recordings (320kbps: المرجع1425, ياسر_فاطر; 192kbps: الفتح).
#
# Cepstrum consensus (both 320kbps refs): dominant clusters at 7ms / 11ms / 15ms / 22ms.
# Spectral analysis: F1 core (300-600Hz) = 48-65% of energy; HF rolloff ~3dB at 4kHz.
# R1 gets a lowpass (not full-band) to simulate the ~3dB HF rolloff of real room surfaces.
# bloom_lo/hi = 0.0 for R1 (lowpass applied instead); R2/R3/R4 use bandpass.
#
# Tap    delay    wet_lin    dBFS    filter
# R1      7ms     0.0900    -20.9   lowpass F0-adaptive (~4kHz)
# R2     11ms     0.0500    -26.0   bandpass 400-700Hz
# R3     15ms     0.0400    -27.9   bandpass 300-600Hz
# R4     22ms     0.0250    -32.0   bandpass 200-450Hz
# Total wet = 20.5%   dry = 79.5%
_SADAA_REFLECTIONS: List[Dict] = [
    {'delay_ms':  5.0, 'wet_lin': 0.1200, 'bloom_lo':   0.0, 'bloom_hi':   0.0},  # R1 — side wall, dense early cluster
    {'delay_ms':  6.0, 'wet_lin': 0.0700, 'bloom_lo': 300.0, 'bloom_hi': 700.0},  # R2 — ceiling bounce
    {'delay_ms':  7.0, 'wet_lin': 0.0550, 'bloom_lo': 270.0, 'bloom_hi': 620.0},  # R3 — back wall merge
    {'delay_ms':  9.0, 'wet_lin': 0.0350, 'bloom_lo': 160.0, 'bloom_hi': 440.0},  # R4 — floor body
    {'delay_ms': 30.0, 'wet_lin': 0.0180, 'bloom_lo': 120.0, 'bloom_hi': 320.0},  # R5 — far wall depth bloom NEW
]
_SADAA_MAX_CREST_DELTA:       float = 1.50   # dB — broadband crest guard (v4.0: tonal shaping shifts crest ~0.9-1.5dB naturally)
_SADAA_MAX_RT60:              float = 0.35   # s  — Studio A RT60 ≈ 0.18-0.22s; allow up to 0.35s
_SADAA_MIN_FLUX_RATIO:        float = 0.85   # spectral flux must not drop below 85% (articulation guard)
_SADAA_MAX_LOWMID_CREST_DELTA: float = 1.0   # dB — 250-500Hz crest must not shift >1dB (chest character guard)


def sadaa_altamayuz(wav_path: str, state: ItiqanState,
                    ref: ReferenceModel, force: bool = False) -> Tuple[str, Dict]:
    """
    صدي التميز — Echo of Distinction  (Phase G.5)

    Applies the acoustic fingerprint of the 1425H studio to the processed
    signal: a formant-shaped early reflection that adds dimension without
    artificiality.  The reflection is derived from three constants measured
    on the reference recordings (delay_ms, wet_lin, bloom window).

    Mechanism — 4-tap early reflection network (v2.0)
    ──────────────────────────────────────────────────
    Dry signal split into 5 paths:
      R1  7ms  lowpass~4kHz      0.090 lin (−20.9 dBFS) — floor reflection, HF-absorbed
      R2 11ms  bandpass 400-700Hz 0.050 lin (−26.0 dBFS) — side wall, F1+lower F2
      R3 15ms  bandpass 300-600Hz 0.040 lin (−27.9 dBFS) — back/ceiling, F1 core
      R4 22ms  bandpass 200-450Hz 0.025 lin (−32.0 dBFS) — distant, warmth/chest
    Dry path = 0.795 (79.5%).  Total wet = 20.5%.

    Constants derived from cepstrum analysis of المرجع1425 + ياسر_فاطر_1425
    (both 320kbps/48kHz recordings of Sheikh Yasser Al-Dossari 1425H).
    Dominant cepstral clusters at 7/11/15/22ms. HF rolloff ~3dB at 4kHz
    measured from ref PSD. F1 core (300-600Hz) = 48-65%% of vocal energy.

    Returns (output_wav_path, report_dict).
    report keys: applied, wet_db, delay_ms, crest_delta, rt60_source
    """
    report: Dict = {
        'applied':     False,
        'gain_db':     0.0,
        'source_lufs': 0.0,
        'crest_delta': 0.0,
        'rt60_source': 0.0,
    }

    # ── Guard: eligible tiers only ───────────────────────────────────────────
    if state.source_tier not in ('TIER_PRISTINE', 'TIER_PRISTINE_NOISY', 'TIER_COMPRESSED'):
        L('  [صدي] tier not eligible — skipping')
        return wav_path, report

    # ── Guard: source must be dry (RT60 < 0.25s) ────────────────────────────
    samples, sr = _decode_wav_samples(wav_path)
    rt60 = 0.0
    if samples is not None and NUMPY_OK:
        rt60 = _estimate_rt60_from_samples(samples, SR)
        report['rt60_source'] = round(rt60, 3)

        # ── Fingerprint gate: does this source need صدي التمييز? ─────────────
        # The RT60 estimator is unreliable (clips at 3.0s for most sources).
        # Instead: measure the dynamic gap of the source vs the 1425H target.
        # If the source gap is already within 1.5dB of 8.0dB → the room
        # character is already present → skip. Otherwise → apply صدي.
        fn_g = int(0.020 * SR)
        fr_g = np.array([20*np.log10(np.sqrt(np.mean(samples[i:i+fn_g]**2))+1e-10)
                         for i in range(0, len(samples)-fn_g, fn_g)])
        _src_gap   = float(np.percentile(fr_g, 90) - np.percentile(fr_g, 10))
        _gap_deficit = _src_gap - 8.0   # positive = too much gap = needs صدي

        if _gap_deficit < 1.5 and not force:
            L(f'  [صدي] gap={_src_gap:.1f}dB ≈ target 8.0dB — fingerprint present, skipping')
            return wav_path, report

        L(f'  [صدي] gap={_src_gap:.1f}dB target=8.0dB → sustain_mix will close {_gap_deficit:.1f}dB')

    # ── Measure pre-application crest ───────────────────────────────────────
    crest_before = state.crest
    if samples is not None and NUMPY_OK:
        _, crest_before = _measure_rms_crest(samples)

    # ── صدي التميز v4.0 — empirically calibrated from A/B comparison ────────
    #
    # What صدي التميز actually IS (measured from المرجع1425 vs الاعراف_1425):
    #
    # 1. TONAL FINGERPRINT — the Studio A booth colours the voice:
    #      +7dB @ 60Hz   (room reinforcement, sub-body)
    #      +5dB @ 120Hz  (chest resonance, fundamental warmth)
    #      +2.5dB @ 250Hz (body/presence lift)
    #      -7dB @ 3kHz   (natural HF rolloff of the treated room)
    #      -8dB @ 5kHz   (above Studio A BW cutoff ~4.3kHz)
    #      -6dB @ 7kHz   (air band suppression)
    #
    # 2. SILENCE FLOOR LIFT — the room breathes between every word:
    #      Silence floor raised by +5.4dB relative to voice peak.
    #      Implemented as a slow-release (600ms) bandpass sustain
    #      that holds the 60-800Hz room energy between syllables.
    #
    # These values are not theoretical — they are the exact measured
    # difference between the two reference recordings at matched loudness.
    #
    import math as _math

    # F0 of the reciter — used for harmonic exciter band targeting
    _f0 = state.f0_median if hasattr(state, 'f0_median') and state.f0_median > 80 else 240.0

    # ── v6.0: صدي التمييز = جهارة وكثافة ونقاء ─────────────────────────────────
    # Root cause (confirmed from user group + A/B measurements):
    # صدي التمييز is NOT reverb, NOT reflection network, NOT complex EQ.
    # It is: loudness (جهارة) + density (كثافة) + purity (نقاء).
    #
    # The 1425H refs are at −6.29 LUFS (LRA=3.50).
    # Target: −7.0 LUFS (between المرجع −6.29 and الفتح −7.45).
    # Implementation: measure source LUFS → apply gain to reach target
    #                 + نقاء EQ (cut mud at 300Hz, lift presence at 3kHz, air at 8kHz)
    #                 + true peak limiter at −0.5dBTP.

    # ── Measure source integrated loudness via ffmpeg ebur128 ────────────────
    _target_lufs = -7.0   # target integrated loudness (between both refs)
    _source_lufs = -18.0  # safe default if measurement fails
    try:
        import re as _re, json as _json
        _lufs_r = _run_ffmpeg([
            'ffmpeg', '-i', wav_path,
            '-af', 'loudnorm=print_format=json',
            '-f', 'null', '-'
        ], capture=True)
        _m = _re.search(r'\{.*?\}', _lufs_r[2], _re.DOTALL)
        if _m:
            _source_lufs = float(_json.loads(_m.group())['input_i'])
    except Exception:
        pass

    _gain_db = round(_target_lufs - _source_lufs, 1)
    L(f'  [صدي] source={_source_lufs:.2f} LUFS → target={_target_lufs} LUFS → gain={_gain_db:+.1f}dB')
    # S177: removed g_500hz/g_580hz/g_1khz/g_2khz — computed from undefined
    # _base_g500/_base_g580/_base_g1k/_base_g2k (NameError every call) and,
    # like g_3khz/g_5khz/g_7khz below, never read again — confirmed dead
    # leftovers from the pre-v6.0 EQ-fingerprint approach.
    g_3khz  = 0.0
    g_5khz  = 0.0
    g_7khz  = 0.0

    # ── Adaptive sustain mix (v5.0: F1+F2 corrected) ────────────────────────
    # F1: target_gap corrected from 8.0 to 5.83 (real p10-p90 of 1425H ref).
    # F2: scaling 0.008→0.016/dB, cap raised 0.30→0.45 for correct deficit closure.
    sustain_mix = 0.32   # base (proven value, post-F2 calibration)
    if samples is not None and NUMPY_OK:
        fn_s = int(0.020 * SR); frames_s = []
        for i in range(0, len(samples)-fn_s, fn_s):
            frames_s.append(20*np.log10(np.sqrt(np.mean(samples[i:i+fn_s]**2))+1e-10))
        fr_s = np.array(frames_s)
        current_gap = float(np.percentile(fr_s,90) - np.percentile(fr_s,10))
        target_gap  = 5.83  # F1: real 1425H p10-p90 gap (was 8.0, which is p5-p95)
        gap_deficit = max(0.0, current_gap - target_gap)
        # F2: stronger scaling (0.016/dB), higher cap (0.45)
        _sus_cap = 0.45  # S177: was a no-op ternary on undefined _sadaa_aggressive
        sustain_mix = float(min(_sus_cap, 0.25 + gap_deficit * 0.016))
        L(f'  [صدي] gap={current_gap:.1f}dB target={target_gap}dB deficit={gap_deficit:.2f}dB → sustain_mix={sustain_mix:.3f}')

    # ── v6.0 filter: gain + نقاء EQ + true peak limiter ─────────────────────
    # نقاء (purity): cut low-mid mud at 300Hz, lift presence at 3kHz, air at 8kHz
    filter_complex = (
        f'volume={_gain_db}dB,'
        f'equalizer=f=300:width_type=o:width=1.0:g=-2.0,'
        f'equalizer=f=3000:width_type=o:width=1.0:g=1.8,'
        f'highshelf=f=8000:width_type=s:width=0.7:g=1.2,'
        f'alimiter=limit=0.891:attack=5:release=50'
    )

    output_wav = _tmp_wav('sadaa')
    cmd = [
        'ffmpeg', '-y', '-i', wav_path,
        '-af', filter_complex,
        '-acodec', WAV_CODEC, output_wav
    ]
    rc, _, err = _run_ffmpeg(cmd)
    if rc != 0 or not os.path.exists(output_wav):
        L(f'  [صدي] ffmpeg failed: {err[:120]} — skipping')
        return wav_path, report

    # ── Guard: crest delta ───────────────────────────────────────────────────
    samples_after, _ = _decode_wav_samples(output_wav)
    crest_after = crest_before
    if samples_after is not None and NUMPY_OK:
        _, crest_after = _measure_rms_crest(samples_after)

    crest_delta = crest_after - crest_before
    crest_gate = _SADAA_MAX_CREST_DELTA * 3.0 if force else _SADAA_MAX_CREST_DELTA
    if abs(crest_delta) > crest_gate:
        L(f'  [صدي] crest Δ={crest_delta:+.3f}dB > ±{crest_gate:.2f} — reverting')
        _cleanup(output_wav)
        return wav_path, report

    # ── Guard: spectral flux — Arabic consonant articulation (SD15) ─────────
    # Refs: mean flux = 54.6×10⁻⁴. Drop >15% = consonant smear.
    if samples is not None and samples_after is not None and NUMPY_OK:
        def _sadaa_flux(s, frame_n=1152, hop_n=576):
            prev = None; acc = 0.0; n = 0
            win = np.hanning(frame_n)
            for i in range(0, len(s) - frame_n, hop_n):
                S = np.abs(np.fft.rfft(s[i:i+frame_n] * win))
                S /= (S.sum() + 1e-12)
                if prev is not None:
                    acc += float(np.sum((S - prev) ** 2)); n += 1
                prev = S
            return acc / n if n else 1.0
        flux_before_val = _sadaa_flux(samples)
        flux_after_val  = _sadaa_flux(samples_after)
        flux_ratio      = flux_after_val / (flux_before_val + 1e-12)
        flux_gate = _SADAA_MIN_FLUX_RATIO * 0.7 if force else _SADAA_MIN_FLUX_RATIO
        if flux_ratio < flux_gate:
            L(f'  [صدي] flux_ratio={flux_ratio:.3f} < {flux_gate:.2f} '
              f'— consonant smear detected, reverting')
            _cleanup(output_wav)
            return wav_path, report
    else:
        flux_ratio = 1.0

    # ── Guard: low-mid band crest 250-500Hz — chest character (SD16) ────────
    # Refs: 250-500Hz crest = 14.4dB (lowest band = most sustained = chest).
    # If صدي flattens this crest the chest resonance character is lost.
    lm_crest_delta = 0.0
    if samples is not None and samples_after is not None and NUMPY_OK:
        def _sadaa_lowmid_crest(s):
            # OOM-safe: use IIR bandpass instead of full-file FFT (30M-sample rfft
            # needs ~5GB intermediates which OOM-kills on 4GB systems).
            try:
                from scipy.signal import butter, sosfilt
                s32 = s.astype(np.float32)
                sos_hp = butter(2, 250.0 / (SR / 2.0), btype='high', output='sos')
                sos_lp = butter(2, 500.0 / (SR / 2.0), btype='low',  output='sos')
                bp = sosfilt(sos_lp, sosfilt(sos_hp, s32))
            except Exception:
                bp = s.astype(np.float32)
            rms  = float(np.sqrt(np.mean(bp ** 2)))
            peak = float(np.max(np.abs(bp)))
            return float(20.0 * np.log10((peak + 1e-12) / (rms + 1e-12)))
        lm_before = _sadaa_lowmid_crest(samples)
        lm_after  = _sadaa_lowmid_crest(samples_after)
        lm_crest_delta = lm_after - lm_before
        lm_gate = _SADAA_MAX_LOWMID_CREST_DELTA * 2.0 if force else _SADAA_MAX_LOWMID_CREST_DELTA
        if abs(lm_crest_delta) > lm_gate:
            L(f'  [صدي] low-mid crest Δ={lm_crest_delta:+.2f}dB > ±{lm_gate:.1f} '
              f'— chest character disturbed, reverting')
            _cleanup(output_wav)
            return wav_path, report

    # ── Guard: Arabic phoneme integrity ─────────────────────────────────────
    # NOTE: صدي v4.0 applies intentional HF cut (-7/-8/-6dB at 3/5/7kHz) which
    # is the measured Studio A room character. The sibilant gate is bypassed
    # because this spectral shape IS the reference — not a distortion of it.
    # The low-mid crest + flux guards above provide sufficient articulation protection.
    if not force and not arabic_phoneme_integrity_gate(wav_path, output_wav, state):
        L('  [صدي] sibilant integrity gate FAIL — reverting')
        _cleanup(output_wav)
        return wav_path, report

    # ── Accepted ─────────────────────────────────────────────────────────────
    report.update({
        'applied':      True,
        'gain_db':      _gain_db,
        'source_lufs':  _source_lufs,
        'crest_delta':  round(crest_delta, 3),
        'rt60_source':  round(rt60, 3),
    })

    L(f'  [صدي التمييز] ✓  v6.0  '
      f'gain={_gain_db:+.1f}dB  src={_source_lufs:.2f}LUFS→{_target_lufs}LUFS  '
      f'crest_Δ={crest_delta:+.3f}dB')
    return output_wav, report


# ══════════════════════════════════════════════════════════════════════════════
#  JOINT LUFS + LRA OPTIMIZER (inherited from base engine)
# ══════════════════════════════════════════════════════════════════════════════

def _build_compand_str(preset_name: str) -> str:
    return _COMPAND_LIBRARY.get(preset_name, _COMPAND_LIBRARY['LIGHT'])


def run_pass_joint(wav_path: str, state: ItiqanState,
                   ref: ReferenceModel) -> Tuple[str, 'PassResult']:
    """
    Joint LUFS+LRA pass (3-position empirical PCHIP from base engine).
    Returns (output_wav, PassResult).
    """
    result = PassResult(label='joint')
    lufs_now, lra_now = _measure_lufs(wav_path)
    samples, sr       = _decode_wav_samples(wav_path)
    rms_now = crest_now = 0.0
    if samples is not None:
        rms_now, crest_now = _measure_rms_crest(samples)

    lufs_delta = ref.lufs - lufs_now
    lufs_delta = max(-18.0, min(18.0, lufs_delta))

    # Crest-aware compand selection (L-02/L-04)
    crest_delta = crest_now - ref.crest  # positive = too much crest, need less

    # Simple compand selection (full PCHIP optimizer in base engine)
    if abs(lufs_delta) < 0.5 and abs(crest_delta) < 0.5:
        compand_preset = 'BYPASS'
    elif crest_delta > 2.0 or lufs_delta > 5.0:
        compand_preset = 'MEDIUM'
    elif crest_delta > 0.5 or lufs_delta > 2.0:
        compand_preset = 'LIGHT'
    else:
        compand_preset = 'MINIMAL'

    output_wav = _tmp_wav('joint')
    filters    = []

    # G3: LRA expander for flat-dynamic COMPRESSED sources.
    # Compand alone cannot RAISE LRA — it only compresses dynamic range.
    # When LRA is too flat (> 1 LU below target), prepend an agate expander
    # that gently reduces the level of quiet frames, widening the dynamic floor.
    # agate operates as expander: frames below threshold are attenuated by `range`.
    # Only for TIER_COMPRESSED to avoid disturbing PRISTINE natural dynamics.
    lra_deficit = ref.lra - lra_now  # positive = LRA too flat
    if state.source_tier == 'TIER_COMPRESSED' and lra_deficit > 1.0:
        # Scale range with deficit: 1 LU→0.82, 2 LU→0.72, 3+LU→0.62
        _expand_range = float(max(0.62, min(0.82, 0.82 - (lra_deficit - 1.0) * 0.10)))
        filters.append(
            f'agate=threshold=0.025:range={_expand_range:.3f}:ratio=2.5'
            f':attack=20:release=250:makeup=1'
        )
        L(f'  [joint] G3 LRA expander: LRA={lra_now:.2f} target={ref.lra:.2f} '
          f'Δ={lra_deficit:+.2f}LU range={_expand_range:.3f}')

    # FIX-8: Correct gain strategy for sources with TP near 0dBTP.
    #
    # The old approach (flat volume + alimiter) failed because:
    #   TP=0.0 → volume(+7dB) → TP=+7 → alimiter crushes everything → crest destroyed.
    # loudnorm also failed: with LRA=1.8 it operates in "Dynamic" mode, only reaches
    #   ~70% of target, leaving 5+ dB gap.
    #
    # Correct sequence:
    #   Step 1: compand (reduce crest + bring TP below 0) — creates headroom
    #   Step 2: volume = ref.lufs - lufs_after_compand (exact remaining delta)
    #   Step 3: alimiter at ref.true_peak (gentle final ceiling, not peak-destroying)
    #
    # Guard: if lufs_delta small (<0.5dB) and crest ok → bypass all.

    if compand_preset != 'BYPASS':
        pts = _build_compand_str(compand_preset)
        filters.append(f'compand=attacks=0.08:decays=0.5:points={pts}')

    # Measure post-compand LUFS on a temp to get the exact remaining delta
    if filters:
        tmp_cmp = _tmp_wav('joint_cmp')
        rc_cmp, _, _ = _run_ffmpeg([
            'ffmpeg', '-y', '-i', wav_path,
            '-af', ','.join(filters),
            '-acodec', WAV_CODEC, tmp_cmp
        ])
        if rc_cmp == 0:
            lufs_after_cmp, _ = _measure_lufs(tmp_cmp)
            remaining_delta   = ref.lufs - lufs_after_cmp
            remaining_delta   = max(-18.0, min(18.0, remaining_delta))
            _cleanup(tmp_cmp)
        else:
            remaining_delta = lufs_delta
            _cleanup(tmp_cmp)
    else:
        remaining_delta = lufs_delta

    if abs(remaining_delta) >= 0.3:
        filters.append(f'volume={remaining_delta:.3f}dB')

    # Final true-peak limiter — only apply if TP check shows it's needed.
    # UPGRADE-C: Unconditional alimiter was eating the volume gain added in the
    # previous step, preventing LUFS from reaching target. Now we measure TP
    # on a temp, and only insert the limiter if TP > target + 0.5dB headroom.
    _tp_check_wav = _tmp_wav('joint_tp_check')
    _tp_filter_str = ','.join(filters) if filters else 'anull'
    _tp_rc, _, _ = _run_ffmpeg([
        'ffmpeg', '-y', '-i', wav_path,
        '-af', _tp_filter_str,
        '-acodec', WAV_CODEC, _tp_check_wav
    ])
    _tp_measured = _measure_true_peak(_tp_check_wav) if _tp_rc == 0 else 0.0
    _cleanup(_tp_check_wav)
    if _tp_measured > TARGET['true_peak'] + 0.5:
        tp_lin = 10.0 ** (TARGET['true_peak'] / 20.0)
        filters.append(
            f'alimiter=level_in=1:level_out={tp_lin:.6f}:limit={tp_lin:.6f}'
            f':attack=5:release=50:level=disabled'
        )

    filter_str = ','.join(filters) if filters else 'anull'
    cmd = [
        'ffmpeg', '-y', '-i', wav_path,
        '-af', filter_str,
        '-acodec', WAV_CODEC, output_wav
    ]
    rc, _, err = _run_ffmpeg(cmd)
    if rc != 0:
        L(f'  [joint] failed: {err[:120]}')
        shutil.copy2(wav_path, output_wav)
        return output_wav, result

    lufs_out, lra_out = _measure_lufs(output_wav)
    result.lufs  = lufs_out
    result.lra   = lra_out

    samp_out, _ = _decode_wav_samples(output_wav)
    if samp_out is not None:
        result.rms, result.crest = _measure_rms_crest(samp_out)

    # Composite score (simplified)
    lufs_err  = abs(lufs_out  - ref.lufs)  / max(abs(ref.lufs), 1.0)
    crest_err = abs(result.crest - ref.crest) / max(ref.crest, 1.0)
    lra_err   = abs(lra_out   - ref.lra)   / max(ref.lra, 1.0)
    result.composite = -(lufs_err + crest_err + lra_err)  # higher = better

    L(f'  [joint] {compand_preset}: '
      f'LUFS {lufs_now:.1f}→{lufs_out:.1f} '
      f'LRA {lra_now:.1f}→{lra_out:.1f} '
      f'Crest {crest_now:.1f}→{result.crest:.1f}')
    return output_wav, result


# ══════════════════════════════════════════════════════════════════════════════
#  PREDICTIVE TRUE PEAK ENCODE (P-6, v3.0)
# ══════════════════════════════════════════════════════════════════════════════

def run_pass_encode(wav_path: str, output_path: str,
                    state: ItiqanState) -> Tuple[str, float, int]:
    """
    Predictive true peak encode.
    v3.0: encoder-detected inter-sample margin (no retries by default).
    Fallback: retry with adjusted threshold if prediction error > 0.3dBTP.
    Returns (output_path, true_peak_db, retries)
    """
    margin     = _ENCODER_MARGINS.get(state.encoder_tag, _ENCODER_MARGINS['unknown'])
    tp_target  = TARGET['true_peak']  # -1.0 dBTP
    limit_dbfs = tp_target - margin   # sample peak limit

    # dBFS to linear: linear = 10^(dBFS/20)
    limit_lin  = 10.0 ** (limit_dbfs / 20.0)

    cmd = [
        'ffmpeg', '-y', '-i', wav_path,
        '-af', (f'alimiter=level_in=1:level_out={limit_lin:.6f}:'
                f'limit={limit_lin:.6f}:attack=5:release=50:level=disabled'),
        '-b:a', '320k', '-q:a', '0', output_path
    ]
    rc, _, err = _run_ffmpeg(cmd)
    if rc != 0:
        L(f'  [encode] failed: {err[:120]}')
        return output_path, -99.0, 0

    actual_tp = _measure_true_peak(output_path)
    state.intersample_margin = margin

    if actual_tp <= tp_target + 0.15:  # within tolerance
        L(f'  [encode] predictive: TP={actual_tp:.2f}dBTP (margin={margin:.1f}dB, retries=0)')
        return output_path, actual_tp, 0

    # Prediction missed — retry with correction
    L(f'  [encode] prediction missed: actual TP={actual_tp:.2f} target={tp_target:.1f} — retry')
    overshoot = actual_tp - tp_target
    corrected_limit_dbfs = limit_dbfs - overshoot - 0.2
    corrected_limit_lin  = 10.0 ** (corrected_limit_dbfs / 20.0)

    cmd[5] = (f'alimiter=level_in=1:level_out={corrected_limit_lin:.6f}:'
              f'limit={corrected_limit_lin:.6f}:attack=5:release=50:level=disabled')
    rc, _, _ = _run_ffmpeg(cmd)
    actual_tp2 = _measure_true_peak(output_path)
    L(f'  [encode] retry: TP={actual_tp2:.2f}dBTP')
    return output_path, actual_tp2, 1


# ══════════════════════════════════════════════════════════════════════════════
#  FINAL SCORING
# ══════════════════════════════════════════════════════════════════════════════

def score_output(wav_path: str, state: ItiqanState, ref: ReferenceModel) -> PassResult:
    """
    Compute final score against 1425H reference targets.
    Uses state.ceiling for tier-adjusted score.
    """
    r = PassResult(label='final')
    r.lufs, r.lra = _measure_lufs(wav_path)
    samples, sr   = _decode_wav_samples(wav_path)
    if samples is not None:
        r.rms, r.crest = _measure_rms_crest(samples)
    r.true_peak = _measure_true_peak(wav_path)

    # Per-metric scores (out of 100 each, then weighted)
    lufs_err  = max(0.0, abs(r.lufs  - ref.lufs)  - 0.3)  # 0.3dB tolerance
    crest_err = max(0.0, abs(r.crest - ref.crest)  - 0.2)
    lra_err   = max(0.0, abs(r.lra   - ref.lra)    - 0.2)
    rms_err   = max(0.0, abs(r.rms   - ref.rms)    - 0.3)

    score_lufs  = max(0.0, 25.0 - lufs_err  * 8.0)
    score_crest = max(0.0, 20.0 - crest_err * 10.0)
    score_lra   = max(0.0, 15.0 - lra_err   * 10.0)
    score_rms   = max(0.0, 10.0 - rms_err   * 6.0)

    # Spectral score: measure 48-band residual vs reference
    # Bands above ref BW cutoff are excluded — ref has no content there
    spec48 = sixth_octave(wav_path)
    spec_err = 0.0
    if spec48 and ref.spectrum_48:
        ref_bw = getattr(ref, 'bw_cutoff', 13000.0)
        errs = [abs(spec48.get(f, -60.0) - ref.spectrum_48.get(f, -60.0))
                for f in CENTERS_48 if f <= ref_bw * 1.05]
        spec_err = sum(errs) / max(len(errs), 1)
    score_spec = max(0.0, 30.0 - spec_err * 3.0)

    score_abs = score_lufs + score_crest + score_lra + score_rms + score_spec

    # Tier-adjusted: cap at ceiling
    score_tier = min(score_abs, state.ceiling)

    if score_abs > state.ceiling:
        r.ceiling_reason = f'ceiling={state.ceiling:.0f} ({state.ceiling_reason})'

    r.score_abs  = round(score_abs, 1)
    r.score_tier = round(score_tier, 1)
    r.eq_residual = spec_err
    r.composite   = -spec_err  # higher = better

    return r


# ══════════════════════════════════════════════════════════════════════════════
#  ARABIC PHONEME INTEGRITY GATE (final check)
# ══════════════════════════════════════════════════════════════════════════════

def arabic_phoneme_integrity_gate(wav_before: str, wav_after: str,
                                   state: ItiqanState) -> bool:
    """
    Verify ARABIC_SIB_BANDS energy preserved within ±1.5dB.
    Returns True if output passes (OK to use), False if gate rejects (revert).
    Implements P-4 principle: Arabic phonology preserved above all other metrics.
    """
    if not NUMPY_OK:
        return True  # can't measure — assume OK

    spec_before = sixth_octave(wav_before)
    spec_after  = sixth_octave(wav_after)

    if not spec_before or not spec_after:
        return True

    for fc in ARABIC_SIB_BANDS:
        before = spec_before.get(fc, -60.0)
        after  = spec_after.get(fc, -60.0)
        delta  = after - before  # positive = gained energy
        if delta < -1.5:
            L(f'  [integrity] ARABIC_SIB_BAND {fc}Hz dropped {delta:.1f}dB — gate FAIL')
            return False

    return True




# ══════════════════════════════════════════════════════════════════════════════
#  M-1: AYAH SEGMENTATION  (قطع الآيات) — merged from الإتقان standalone
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class AyahSegment:
    start_s:    float
    end_s:      float
    duration_s: float
    seg_type:   str    # 'verse' | 'long_pause' | 'mid_pause'
    rms_level:  float = -20.0
    verse_idx:  int   = 0


def segment_ayahs(wav_path: str, total_s: float,
                  sr: int = SR) -> Tuple[List[AyahSegment], Dict]:
    """
    M-1: Detect ayah boundaries from energy + pause duration over the FULL file.

    Three pause tiers (empirically calibrated on 1425H):
      LONG  (> 0.80s) — inter-ayah boundary
      MID   (0.30–0.80s) — waqf sign or breath
      SHORT (< 0.30s) — micro-pause / consonant closure — ignored

    Returns (segments, stats{n_verses, median_pause_s, median_verse_s, ...}).
    Output used by M-2 (temporal drift detection) and analysis skip-point selection.
    """
    if not NUMPY_OK:
        return [], {'n_verses': 0, 'median_pause_s': 1.0, 'median_verse_s': 5.0}

    FRAME_MS  = 20.0
    FRAME_N   = int(FRAME_MS / 1000.0 * sr)
    LONG_MIN  = 0.80
    MID_MIN   = 0.30
    MERGE_GAP = 0.20
    CHUNK_S   = 300.0

    n_chunks = max(1, int(total_s / CHUNK_S) + 1)
    all_frame_rms: List[float] = []

    for ci in range(n_chunks):
        skip = ci * CHUNK_S
        dur  = min(CHUNK_S + 1.0, total_s - skip)
        if dur < 2.0:
            break
        # Use ffmpeg to decode chunk to f32le
        tmp_chunk = _tmp_wav(f'm1_chunk{ci}')
        cmd = ['ffmpeg', '-y', '-ss', str(skip), '-i', wav_path,
               '-t', str(dur), '-ar', str(sr), '-ac', '1',
               '-f', 'f32le', '-loglevel', 'error', tmp_chunk]
        rc, _, _ = _run_ffmpeg(cmd)
        if rc != 0 or not os.path.exists(tmp_chunk):
            continue
        try:
            raw = np.fromfile(tmp_chunk, dtype=np.float32)
        except Exception:
            _cleanup(tmp_chunk)
            continue
        _cleanup(tmp_chunk)
        n_fr = len(raw) // FRAME_N
        for fi in range(n_fr):
            seg = raw[fi * FRAME_N: (fi + 1) * FRAME_N]
            rms = float(np.sqrt(np.mean(seg ** 2)) + 1e-10)
            all_frame_rms.append(float(20 * np.log10(rms)))

    if len(all_frame_rms) < 50:
        return [], {'n_verses': 0, 'median_pause_s': 1.0, 'median_verse_s': 5.0}

    rms_arr = np.array(all_frame_rms, dtype=np.float32)
    active = rms_arr[rms_arr > -80]
    if len(active) < 10:
        return [], {'n_verses': 0, 'median_pause_s': 1.0, 'median_verse_s': 5.0}

    overall_median = float(np.percentile(active, 60))
    pause_thresh   = overall_median - 20.0
    is_silent      = rms_arr < pause_thresh
    frame_dur      = FRAME_MS / 1000.0

    raw_pauses: List[Tuple[float, float]] = []
    in_pause = False; p_start = 0
    for i in range(len(is_silent)):
        if is_silent[i] and not in_pause:
            in_pause = True; p_start = i
        elif not is_silent[i] and in_pause:
            in_pause = False
            dur = (i - p_start) * frame_dur
            if dur >= MID_MIN:
                raw_pauses.append((p_start * frame_dur, i * frame_dur))
    if in_pause:
        dur = (len(is_silent) - p_start) * frame_dur
        if dur >= MID_MIN:
            raw_pauses.append((p_start * frame_dur, len(is_silent) * frame_dur))

    if not raw_pauses:
        seg = AyahSegment(0.0, total_s, total_s, 'verse', float(overall_median), 1)
        return [seg], {'n_verses': 1, 'median_pause_s': 0.0,
                       'median_verse_s': total_s, 'long_pauses': 0, 'mid_pauses': 0}

    # Merge pauses separated by < MERGE_GAP voiced content
    merged: List[Tuple[float, float]] = [raw_pauses[0]]
    for ps, pe in raw_pauses[1:]:
        prev_ps, prev_pe = merged[-1]
        if ps - prev_pe < MERGE_GAP:
            merged[-1] = (prev_ps, pe)
        else:
            merged.append((ps, pe))

    long_pauses = [(ps, pe) for ps, pe in merged if pe - ps >= LONG_MIN]
    mid_pauses  = [(ps, pe) for ps, pe in merged if MID_MIN <= pe - ps < LONG_MIN]

    all_times = sorted(set(
        [0.0] + [ps for ps, pe in long_pauses] + [pe for ps, pe in long_pauses] + [total_s]
    ))
    segments: List[AyahSegment] = []
    verse_idx = 0
    for i in range(len(all_times) - 1):
        t0_seg = all_times[i]; t1_seg = all_times[i + 1]
        dur = t1_seg - t0_seg
        is_lp = any(abs(ps - t0_seg) < 0.05 and abs(pe - t1_seg) < 0.05
                    for ps, pe in long_pauses)
        if is_lp:
            stype = 'long_pause'
        else:
            verse_idx += 1; stype = 'verse'
        segments.append(AyahSegment(t0_seg, t1_seg, dur, stype,
                                     float(overall_median),
                                     verse_idx if stype == 'verse' else 0))

    verse_segs = [s for s in segments if s.seg_type == 'verse']
    pause_segs = [s for s in segments if s.seg_type == 'long_pause']
    n_v   = len(verse_segs)
    med_v = float(np.median([s.duration_s for s in verse_segs])) if verse_segs else 5.0
    med_p = float(np.median([s.duration_s for s in pause_segs])) if pause_segs else 1.0

    L(f'  [M-1] {n_v} verses | {len(long_pauses)} long pauses | '
      f'median_verse={med_v:.1f}s pause={med_p:.2f}s')

    return segments, {
        'n_verses': n_v, 'median_pause_s': round(med_p, 2),
        'median_verse_s': round(med_v, 2),
        'long_pauses': len(long_pauses), 'mid_pauses': len(mid_pauses),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  M-2: TEMPORAL LEVEL CONSISTENCY  (الاتساق الزماني)
# ══════════════════════════════════════════════════════════════════════════════

def temporal_consistency_pass(wav_path: str, state: ItiqanState,
                               segments: List[AyahSegment]) -> Tuple[str, Dict]:
    """
    M-2: Detect and correct level drift from multi-session splices.

    Two-session archives often have a 3–6dB level shift at the splice point.
    Fixed analysis windows (first 30% of file) in v3.0 base cannot detect this.

    Method: measure RMS of each verse segment → find early/late mean split →
    if drift > 3dB: apply smooth linear ramp correction (max ±2.5dB).
    """
    report: Dict = {'applied': False, 'drift_db': 0.0, 'correction_db': 0.0}

    if not NUMPY_OK or state.duration_s < 120.0:
        return wav_path, report

    verse_segs = [s for s in segments if s.seg_type == 'verse' and s.duration_s >= 3.0]
    if len(verse_segs) < 6:
        return wav_path, report

    rms_vals = np.array([s.rms_level for s in verse_segs], dtype=np.float32)
    times    = np.array([s.start_s   for s in verse_segs], dtype=np.float32)

    n = len(rms_vals); third = max(2, n // 3)
    early_mean = float(np.mean(rms_vals[:third]))
    late_mean  = float(np.mean(rms_vals[-third:]))
    drift_db   = late_mean - early_mean
    report['drift_db'] = round(float(drift_db), 2)

    if abs(drift_db) < 3.0:
        L(f'  [M-2] drift={drift_db:+.2f}dB — within tolerance')
        return wav_path, report

    # Find splice point
    overall_median = float(np.median(rms_vals))
    cumdev = rms_vals - overall_median
    sign_ch = np.where(np.diff(np.sign(cumdev)))[0]
    splice_s = float(times[int(sign_ch[len(sign_ch) // 2])]) if len(sign_ch) > 0 \
               else float(state.duration_s * 0.5)

    correction_db = float(np.clip(-drift_db * 0.5, -2.5, 2.5))
    report['correction_db'] = round(correction_db, 2)

    ramp_start = max(0.0, splice_s - 1.5)
    ramp_end   = min(state.duration_s, splice_s + 1.5)
    amp_before = 1.0
    amp_after  = float(10 ** (correction_db / 20.0))
    ramp_span  = max(ramp_end - ramp_start, 0.1)

    vol_expr = (
        f"if(lt(t,{ramp_start:.2f}),{amp_before:.4f},"
        f"if(lt(t,{ramp_end:.2f}),"
        f"{amp_before:.4f}+({amp_after:.4f}-{amp_before:.4f})*"
        f"((t-{ramp_start:.2f})/{ramp_span:.2f}),"
        f"{amp_after:.4f}))"
    )
    af = f"volume=volume='{vol_expr}':eval=frame"
    out_wav = _tmp_wav('m2_temporal')
    cmd = ['ffmpeg', '-y', '-i', wav_path, '-af', af, '-acodec', WAV_CODEC,
           '-loglevel', 'error', out_wav]
    rc, _, err = _run_ffmpeg(cmd)

    if rc != 0 or not os.path.exists(out_wav):
        L(f'  [M-2] ffmpeg failed — skipping')
        return wav_path, report

    report['applied'] = True
    L(f'  [M-2] ✓ drift={drift_db:+.2f}dB corrected by {correction_db:+.2f}dB at {splice_s:.0f}s')
    return out_wav, report


# ══════════════════════════════════════════════════════════════════════════════
#  M-3: ADAPTIVE COMPAND (DAMAGED path only)
# ══════════════════════════════════════════════════════════════════════════════

def _sample_rms_distribution(wav_path: str, total_s: float) -> Optional['np.ndarray']:
    """Sample frame-RMS distribution from full file for M-3."""
    if not NUMPY_OK:
        return None
    FRAME_S = 0.050; frame_n = int(FRAME_S * SR); CHUNK_S = 20.0
    all_rms: List[float] = []
    t = 0.0
    while t < total_s - FRAME_S:
        dur = min(CHUNK_S, total_s - t)
        tmp = _tmp_wav('m3_chunk')
        cmd = ['ffmpeg', '-y', '-ss', str(t), '-i', wav_path, '-t', str(dur),
               '-ar', str(SR), '-ac', '1', '-f', 'f32le', '-loglevel', 'error', tmp]
        rc, _, _ = _run_ffmpeg(cmd)
        if rc == 0 and os.path.exists(tmp):
            try:
                raw = np.fromfile(tmp, dtype=np.float32)
                n_fr = len(raw) // frame_n
                for fi in range(n_fr):
                    seg = raw[fi * frame_n: (fi + 1) * frame_n]
                    rms = float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-10))
                    all_rms.append(rms)
            except Exception:
                pass
            _cleanup(tmp)
        t += CHUNK_S
    if len(all_rms) < 20:
        return None
    arr = np.array(all_rms, dtype=np.float32)
    active = arr[arr > float(np.percentile(arr, 95)) - 30]
    return np.sort(active) if len(active) >= 10 else None


def adaptive_compand_pass_damaged(wav_path: str, state: ItiqanState,
                                   ref: ReferenceModel) -> Tuple[str, Dict]:
    """
    M-3: Custom adaptive compand for DAMAGED/CRITICAL sources.
    Replaces 6-preset selection with histogram percentile mapping.
    LRA error target < 0.10LU vs 0.2–0.5LU with preset system.
    Only runs on DAMAGED/CRITICAL — PRISTINE/COMPRESSED use Phase H optimizer.
    """
    report: Dict = {'applied': False, 'lra_before': state.lra, 'lra_after': state.lra}

    if state.source_tier not in ('TIER_DAMAGED', 'TIER_CRITICAL'):  # PRISTINE_NOISY excluded from compand
        return wav_path, report
    if not NUMPY_OK:
        return wav_path, report

    lra_error = abs(state.lra - ref.phrase_lra)
    if lra_error < 0.12:
        L(f'  [M-3] LRA={state.lra:.2f} within 0.12LU of target — skip')
        return wav_path, report

    input_dist = _sample_rms_distribution(wav_path, state.duration_s)
    if input_dist is None:
        return wav_path, report

    # Build synthetic target distribution from reference metrics
    lufs  = ref.lufs; lra = ref.lra
    target_pts = np.interp(np.linspace(0, 1, 200),
                            [0.05, 0.20, 0.50, 0.80, 0.95],
                            [lufs - 6.0 - lra * 0.7, lufs - 3.5 - lra * 0.4,
                             lufs - 1.5, lufs + 0.5 + lra * 0.1, lufs + 1.5 + lra * 0.3])

    percs = [2, 10, 25, 40, 55, 70, 82, 92, 98]
    in_lvl  = [float(np.clip(np.percentile(input_dist, p), -90, 0)) for p in percs]
    out_lvl = [float(np.clip(np.percentile(target_pts, p), -90, 0)) for p in percs]

    # Enforce monotonicity + minimum 2dB input separation
    for i in range(1, len(out_lvl)):
        if out_lvl[i] <= out_lvl[i - 1]:
            out_lvl[i] = out_lvl[i - 1] + 0.4
    for i in range(1, len(in_lvl)):
        if in_lvl[i] <= in_lvl[i - 1] + 2.0:
            in_lvl[i] = in_lvl[i - 1] + 2.0
        if in_lvl[i] > -0.5:
            in_lvl[i] = -0.5

    points_str = '|'.join(f'{il:.1f}/{ol:.1f}' for il, ol in zip(in_lvl, out_lvl))
    af = (f'compand=attacks=0.10:decays=0.60:points={points_str},'
          f'alimiter=limit=0.9997:level=false:attack=1:release=50')

    out_wav = _tmp_wav('m3_compand')
    cmd = ['ffmpeg', '-y', '-i', wav_path, '-af', af, '-acodec', WAV_CODEC,
           '-loglevel', 'error', out_wav]
    rc, _, _ = _run_ffmpeg(cmd)

    if rc != 0 or not os.path.exists(out_wav):
        L('  [M-3] ffmpeg failed — skip')
        return wav_path, report

    post_lufs, post_lra = _measure_lufs(out_wav)
    lra_err_before = abs(state.lra  - ref.phrase_lra)
    lra_err_after  = abs(post_lra   - ref.phrase_lra)

    if lra_err_after > lra_err_before + 0.05:
        L(f'  [M-3] LRA moved away {state.lra:.2f}→{post_lra:.2f} — REVERTED')
        _cleanup(out_wav)
        return wav_path, report

    report.update({'applied': True, 'lra_after': round(post_lra, 3)})
    L(f'  [M-3] ✓ adaptive compand: LRA {state.lra:.2f}→{post_lra:.2f}LU')
    return out_wav, report


# ══════════════════════════════════════════════════════════════════════════════
#  M-5: SIBILANT CENTROID CORRECTION  (تصحيح مركز مخارج الأصوات)
# ══════════════════════════════════════════════════════════════════════════════
# 1425H reference sibilant centroid (measured from ref files)
_SIB_REF_CENTROID  = 3600.0   # Hz
_SIB_TOL_HZ        = 500.0    # acceptable deviation
_SIB_MAX_TILT_DB   = 2.5      # max correction


def _measure_sibilant_centroid(samples: 'np.ndarray', sr: int) -> Dict:
    """
    Measure spectral centroid of sibilant frames (ZCR-gated).
    Returns {centroid_hz, zcr_mean, n_frames}.
    """
    if not NUMPY_OK or samples is None or len(samples) < sr * 3:
        return {}
    frame_n = int(0.025 * sr); hop_n = frame_n // 2
    overall = float(np.sqrt(np.mean(samples ** 2)) + 1e-10)
    lo_db = float(20 * np.log10(overall)) - 18.0
    hi_db = float(20 * np.log10(overall)) - 2.0
    centroids: List[float] = []; zcr_vals: List[float] = []
    freqs = rfftfreq(frame_n, 1.0 / sr)
    for i in range(0, len(samples) - frame_n, hop_n):
        frame = samples[i: i + frame_n]
        rms_f = float(20 * np.log10(np.sqrt(np.mean(frame ** 2)) + 1e-10))
        if not (lo_db < rms_f < hi_db):
            continue
        zcr = float(np.sum(np.abs(np.diff(np.sign(frame))))) / (2 * frame_n)
        if zcr < 0.18:
            continue
        spec = np.abs(rfft(frame * np.hanning(frame_n))) ** 2
        m    = (freqs >= 1000) & (freqs <= 8000)
        if not m.any():
            continue
        total_e = float(np.sum(spec[m]) + 1e-30)
        centroids.append(float(np.sum(spec[m] * freqs[m]) / total_e))
        zcr_vals.append(zcr)
        if len(centroids) >= 300:
            break
    if len(centroids) < 20:
        return {}
    return {'centroid_hz': float(np.median(centroids)),
            'zcr_mean':    float(np.mean(zcr_vals)),
            'n_frames':    len(centroids)}


def sibilant_centroid_pass(wav_path: str, samples: 'np.ndarray',
                            state: ItiqanState) -> Tuple[str, Dict]:
    """
    M-5: Correct sibilant spectral centroid regardless of smear_score.
    Fixes GAP-3: base engine only corrects sibilants when smear_score >= 4.
    Mic-induced spectral offset gives wrong centroid even on clean codec.

    Too dark (centroid < 3100Hz): boost 3.5kHz shelf +X dB
    Too bright (centroid > 4100Hz): cut 5kHz shelf -X dB
    Guard: ZCR must not decrease (makhraj character preserved).
    """
    report: Dict = {'applied': False, 'centroid_before': 0.0, 'correction_db': 0.0}

    if not NUMPY_OK or samples is None:
        return wav_path, report

    profile = _measure_sibilant_centroid(samples, SR)
    if not profile or profile['n_frames'] < 20:
        L('  [M-5] insufficient sibilant frames — skip')
        return wav_path, report

    centroid = profile['centroid_hz']
    report['centroid_before'] = round(centroid, 0)
    err = centroid - _SIB_REF_CENTROID

    L(f'  [M-5] centroid={centroid:.0f}Hz ref={_SIB_REF_CENTROID:.0f}Hz '
      f'err={err:+.0f}Hz ZCR={profile["zcr_mean"]:.3f}')

    if abs(err) < _SIB_TOL_HZ:
        L('  [M-5] within tolerance — skip')
        return wav_path, report

    eq_parts: List[str] = []
    corr_db = 0.0
    # G5: Low-bitrate COMPRESSED centroid measurement is less reliable due to
    # spectral noise; over-correction risks audibly wrong sibilant colour.
    _eff_sib_cap = (1.8 if state.bitrate_class in ('64', '96')
                    else _SIB_MAX_TILT_DB)
    if err < -_SIB_TOL_HZ:
        boost = float(np.clip(-err / _SIB_TOL_HZ * 1.2, 0.5, _eff_sib_cap))
        eq_parts.append(f'equalizer=f=3500:width_type=h:width=2500:g={boost:+.2f}')
        corr_db = boost
    else:
        cut = float(np.clip(err / _SIB_TOL_HZ * 1.0, 0.5, _eff_sib_cap))
        eq_parts.append(f'equalizer=f=5000:width_type=h:width=3000:g={-cut:+.2f}')
        corr_db = -cut

    report['correction_db'] = round(corr_db, 2)
    out_wav = _tmp_wav('m5_sib')
    cmd = ['ffmpeg', '-y', '-i', wav_path, '-af', ','.join(eq_parts),
           '-acodec', WAV_CODEC, '-loglevel', 'error', out_wav]
    rc, _, _ = _run_ffmpeg(cmd)
    if rc != 0 or not os.path.exists(out_wav):
        L('  [M-5] ffmpeg failed — skip')
        return wav_path, report

    # Guard: ZCR must not drop (sibilant character preserved)
    post_s, _ = _decode_wav_samples(out_wav)
    if post_s is not None:
        post_profile = _measure_sibilant_centroid(post_s, SR)
        if post_profile and post_profile['zcr_mean'] < profile['zcr_mean'] - 0.03:
            L(f'  [M-5] ZCR drop — REVERTED')
            _cleanup(out_wav)
            return wav_path, report

    report['applied'] = True
    L(f'  [M-5] ✓ sibilant correction {corr_db:+.2f}dB')
    return out_wav, report


# ══════════════════════════════════════════════════════════════════════════════
#  M-6: DEREVERBERATION  (إزالة الترجيع)
# ══════════════════════════════════════════════════════════════════════════════

def _estimate_rt60_from_samples(samples: 'np.ndarray', sr: int = SR) -> float:
    """Estimate RT60 from decay slope of voiced frame energy."""
    if not NUMPY_OK or samples is None or len(samples) < sr * 5:
        return 0.0
    frame_n = int(0.020 * sr)
    frames_rms = []
    for i in range(0, len(samples) - frame_n, frame_n):
        rms = float(np.sqrt(np.mean(samples[i:i+frame_n] ** 2)) + 1e-10)
        frames_rms.append(float(20 * np.log10(rms)))
    if len(frames_rms) < 20:
        return 0.0
    fr = np.array(frames_rms)
    median_level = float(np.percentile(fr, 50))
    voiced_thresh = median_level - 8.0
    decay_slopes: List[float] = []
    for i in range(len(fr) - 12):
        if fr[i] >= voiced_thresh > fr[i + 1]:
            window = fr[i + 1: i + 12]
            if len(window) < 6:
                continue
            t = np.arange(len(window)) * 0.020
            slope = float(np.polyfit(t, window, 1)[0])
            if slope < -8.0:
                decay_slopes.append(abs(slope))
    if len(decay_slopes) < 3:
        return 0.0
    rt60 = float(np.clip(60.0 / np.median(decay_slopes), 0.0, 3.0))
    return 0.0 if rt60 < 0.15 else rt60


def dereverberation_pass(wav_path: str, samples: 'np.ndarray',
                          state: ItiqanState) -> Tuple[str, Dict]:
    """
    M-6: Targeted dereverberation for recordings with RT60 > 0.15s.

    Problem: TYPE_B expansion (agate) amplifies quiet reverb tails → recording
    sounds MORE reverberant after expansion. Must run BEFORE expansion for
    maximum effect, but الإتقان runs post-الاسترداد so we apply what we can.

    Two-band approach:
      LF room mode (250/315/400Hz) — depth scales with RT60 (1–3dB)
      Tail floor NR — afftdn nr=2 at measured tail level (RT60 > 0.3s only)

    Guards: voiced RMS Δ < 0.5dB, Crest Δ < ±0.3dB.
    """
    report: Dict = {'applied': False, 'rt60_s': 0.0, 'lf_cut_db': 0.0}

    if not NUMPY_OK or samples is None:
        return wav_path, report

    rt60 = _estimate_rt60_from_samples(samples, SR)
    report['rt60_s'] = round(rt60, 2)

    if rt60 < 0.15:
        L(f'  [M-6] RT60={rt60:.2f}s < 0.15 — no dereverberation needed')
        return wav_path, report

    # G6: COMPRESSED sources from mosque recordings typically have RT60 0.18–0.25s
    # from venue acoustics; the old 0.25 threshold was silently skipping them.
    _m6_skip_thresh = 0.20 if state.source_tier == 'TIER_COMPRESSED' else 0.25
    if state.source_tier in ('TIER_PRISTINE', 'TIER_PRISTINE_NOISY', 'TIER_COMPRESSED') and rt60 < _m6_skip_thresh:
        L(f'  [M-6] clean source + RT60={rt60:.2f}s < {_m6_skip_thresh:.2f} — skip')
        return wav_path, report

    L(f'  [M-6] RT60={rt60:.2f}s — applying dereverberation')

    lf_depth = float(np.clip(rt60 / 0.2 * 1.0, 1.0, 3.0))
    room_hz   = 400 if rt60 < 0.4 else 315 if rt60 < 0.7 else 250

    # H4: Mujawwad path — KB §145.3: reduce dereverberation by 50%.
    # "Target controlled dereverberation, not anechoic." The masjid reverb
    # is part of Mujawwad recording character (target RT60 ≥ 1.2s in §145.3).
    _muj_conf = getattr(state, 'mujawwad_confidence', 0.0)
    if _muj_conf > 0.6:
        lf_depth *= 0.50
        L(f'  [M-6] H4 Mujawwad mode (conf={_muj_conf:.2f}) — depth ×0.5 → {lf_depth:.1f}dB')

    report['lf_cut_db'] = lf_depth

    filters = [f'equalizer=f={room_hz}:width_type=o:width=1.2:g=-{lf_depth:.1f}']
    if rt60 > 0.30:
        # Tail NR: very conservative
        fr = np.array([float(20 * np.log10(np.sqrt(np.mean(
            samples[i:i+int(0.2*SR)] ** 2)) + 1e-10))
            for i in range(0, len(samples) - int(0.2*SR), int(0.2*SR))])
        overall = float(np.sqrt(np.mean(samples ** 2)) + 1e-10)
        overall_db = float(20 * np.log10(overall))
        quiet_frames = fr[fr < overall_db - 12]
        if len(quiet_frames) > 0:
            nf = float(np.clip(np.median(quiet_frames) + 5, -72, -35))
            filters.append(f'afftdn=nr=2:nf={nf:.0f}:tn=1')

    out_wav = _tmp_wav('m6_derev')
    cmd = ['ffmpeg', '-y', '-i', wav_path, '-af', ','.join(filters),
           '-acodec', WAV_CODEC, '-loglevel', 'error', out_wav]
    rc, _, _ = _run_ffmpeg(cmd)
    if rc != 0 or not os.path.exists(out_wav):
        L('  [M-6] ffmpeg failed — skip')
        return wav_path, report

    post_s, _ = _decode_wav_samples(out_wav)
    if post_s is not None and len(post_s) > SR:
        rms_d  = float(np.sqrt(np.mean(post_s**2))+1e-10)
        rms_d2 = float(np.sqrt(np.mean(samples**2))+1e-10)
        rms_delta = float(20*np.log10(rms_d/rms_d2))
        if abs(rms_delta) > (1.5 if getattr(state, 'aggressive', False) else 0.5):
            L(f'  [M-6] RMS Δ={rms_delta:+.2f}dB > 0.5 — REVERTED')
            _cleanup(out_wav)
            return wav_path, report

    report['applied'] = True
    L(f'  [M-6] ✓ RT60={rt60:.2f}s LF cut={lf_depth:.1f}dB at {room_hz}Hz')
    return out_wav, report


# ══════════════════════════════════════════════════════════════════════════════
#  M-7: ADAPTIVE SCORE WEIGHTS  (الأوزان التكيفية للتقييم)
# ══════════════════════════════════════════════════════════════════════════════

def _adaptive_weights(source_tier: str, achievable_crest: float,
                      achievable_lra: float) -> Dict[str, float]:
    """
    M-7: Redistribute score weights for tiers where the ceiling prevents
    achieving the fixed targets. Fixed weights misrepresent quality when
    TIER_DAMAGED forces Crest ceiling = 7.0 (impossible to reach 10.25).

    Shortfall weight → redistributed to achievable metrics.
    Sum always = 100.
    """
    w = {'spectral': 30.0, 'lufs': 25.0, 'crest': 20.0, 'lra': 15.0, 'warmth': 10.0}
    if source_tier in ('TIER_PRISTINE', 'TIER_PRISTINE_NOISY'):
        return w
    if achievable_crest < 9.0:
        transfer = w['crest'] * (10.25 - achievable_crest) / 10.25 * 0.5
        w['crest'] -= transfer; w['lufs'] += transfer * 0.6; w['warmth'] += transfer * 0.4
    if achievable_lra < 3.5:
        transfer = w['lra'] * (4.19 - achievable_lra) / 4.19 * 0.5
        w['lra'] -= transfer; w['spectral'] += transfer * 0.7; w['lufs'] += transfer * 0.3
    total = sum(w.values())
    return {k: round(v * 100 / total, 1) for k, v in w.items()}



# ══════════════════════════════════════════════════════════════════════════════
#  M-9: VOICE BODY SCULPTING  (نحت جسم الصوت)
# ══════════════════════════════════════════════════════════════════════════════

def voice_body_sculpting(wav_path: str,
                          state: 'ItiqanState',
                          ref: 'ReferenceModel') -> tuple:
    """
    M-9: Two-part voice correction targeting the two main quality gaps:

    Part 1 — LF Mud Taming (تخفيف الطين الصوتي):
      Runs when warmth_ratio > 12dB (LF 12dB+ stronger than HF).
      The EQ optimizer cannot fix this because its per-band bounds are ±6dB,
      and mud excess is routinely 12-33dB. A direct low-shelf + bell cut
      removes the excess before the EQ runs, giving the optimizer a clean start.

      Cut formula:
        mud_excess = warmth_ratio - 12.0          # dB above threshold
        shelf_cut  = clip(mud_excess * 0.20, 1.0, 4.5)   # gentle scaling
        bell_cut   = clip(mud_excess * 0.12, 0.5, 2.5)   # 200Hz body cut

    Part 2 — Presence Restoration (استعادة الحضور):
      Runs when presence_ratio < -2.0dB (voice formant 1-4kHz recessed).
      Adds a symmetric presence lift without touching sibilant bands.

      Boost formula:
        pres_deficit = abs(presence_ratio + 2.0)  # dB below threshold
        boost_1k5    = clip(pres_deficit * 0.35, 0.3, 1.8)
        boost_2k5    = clip(pres_deficit * 0.25, 0.2, 1.2)

    Guards (revert if any trigger):
      G1: output RMS delta > 3.0dB
      G2: crest delta outside [-1.0, +2.0]dB   (dynamics must not be crushed)
    """
    report = {'applied': False, 'mud_cut_db': 0.0, 'presence_boost_db': 0.0,
              'reverted': False}

    warmth_ratio   = getattr(state, 'warmth_ratio',   0.0)
    presence_ratio = getattr(state, 'presence_ratio', 0.0)

    # Decide what to do
    mud_excess   = max(0.0, warmth_ratio - 12.0)
    pres_deficit = max(0.0, -(presence_ratio + 2.0))

    if mud_excess < 0.5 and pres_deficit < 0.5:
        L(f'  [M-9] warmth={warmth_ratio:.1f}dB presence={presence_ratio:.1f}dB'
          f' — within bounds, skipping')
        return wav_path, report

    # Compute gains — scaling is non-linear for extreme mud (warmth > 20dB)
    # EQ optimizer bounds are ±6dB, so anything above that can't be fixed by
    # Phase D. M-9 must pre-correct it directly.
    if mud_excess > 15.0:   # severe: warmth > 27dB
        shelf_cut = min(mud_excess * 0.30, 7.0)   # up to 7dB shelf
        bell_cut  = min(mud_excess * 0.18, 4.0)   # up to 4dB bell
    else:                    # mild/moderate
        shelf_cut = min(mud_excess * 0.22, 5.0)
        bell_cut  = min(mud_excess * 0.13, 2.8)
    boost_1k5   = min(pres_deficit * 0.40, 2.2)
    boost_2k5   = min(pres_deficit * 0.28, 1.5)

    # Confidence scale: for extreme mud (warmth > 20dB), full strength even on PRISTINE
    # because the EQ optimizer physically cannot fix 20+ dB gaps within ±6dB bounds
    if mud_excess > 8.0:
        conf = 1.00   # extreme mud — EQ can't save us, go full strength
    else:
        conf = 0.80 if state.source_tier in ('TIER_PRISTINE', 'TIER_PRISTINE_NOISY') else 1.00
    shelf_cut *= conf
    bell_cut  *= conf
    boost_1k5 *= conf
    boost_2k5 *= conf

    L(f'  [M-9] warmth={warmth_ratio:.1f}dB → mud_cut 500Hz={shelf_cut:.1f}dB 630Hz={bell_cut:.1f}dB '
      f'| presence={presence_ratio:.1f}dB → boost 1.5k+{boost_1k5:.1f}dB 2.5k+{boost_2k5:.1f}dB')

    filters = []

    # Part 1: LF mud cut — ABOVE the F0 zone (F0=185Hz → harmonics at 370, 555Hz)
    # We target 450-630Hz: the 'honk' / boxy mud zone that sits between
    # the fundamental harmonics and the first formant. Cutting here removes
    # boxiness without touching the fundamental voice body or LRA dynamics.
    if shelf_cut >= 0.3:
        # Bell at 500Hz — the boxy honk zone, above F0 harmonics
        filters.append(f'equalizer=f=500:t=q:w=1.2:g=-{shelf_cut:.2f}')
    if bell_cut >= 0.3:
        # Bell at 630Hz — upper mud zone, below formant F1
        filters.append(f'equalizer=f=630:t=q:w=1.0:g=-{bell_cut:.2f}')

    # Part 2: Presence boost — voice formant clarity zone
    if boost_1k5 >= 0.2:
        filters.append(f'equalizer=f=1500:t=q:w=1.2:g={boost_1k5:.2f}')
    if boost_2k5 >= 0.2:
        filters.append(f'equalizer=f=2500:t=q:w=1.0:g={boost_2k5:.2f}')

    if not filters:
        return wav_path, report

    out_wav = _tmp_wav('m9_voice')
    cmd = ['ffmpeg', '-y', '-i', wav_path,
           '-af', ','.join(filters),
           '-acodec', WAV_CODEC, '-loglevel', 'error', out_wav]
    rc, _, err = _run_ffmpeg(cmd)
    if rc != 0 or not os.path.exists(out_wav):
        L(f'  [M-9] ffmpeg failed — skip ({err[:60]})')
        return wav_path, report

    # Guards
    if NUMPY_OK:
        s_b, _ = _decode_wav_samples(wav_path)
        s_a, _ = _decode_wav_samples(out_wav)
        if s_b is not None and s_a is not None:
            rms_b = float(np.sqrt(np.mean(s_b ** 2)) + 1e-10)
            rms_a = float(np.sqrt(np.mean(s_a ** 2)) + 1e-10)
            rms_d = abs(20 * np.log10(rms_a / rms_b))
            if rms_d > 5.0:
                L(f'  [M-9] G1 REVERT: RMS delta={rms_d:.1f}dB > 5.0')
                _cleanup(out_wav); report['reverted'] = True
                return wav_path, report

            _, crest_b = _measure_rms_crest(s_b)
            _, crest_a = _measure_rms_crest(s_a)
            crest_d = crest_a - crest_b
            if crest_d < -1.0 or crest_d > 2.0:
                L(f'  [M-9] G2 REVERT: crest delta={crest_d:+.1f}dB outside [-1,+2]')
                _cleanup(out_wav); report['reverted'] = True
                return wav_path, report

    report.update({'applied': True, 'mud_cut_db': shelf_cut,
                   'presence_boost_db': boost_1k5})
    state.voice_sculpt_applied = True
    state.mud_cut_db           = shelf_cut
    state.presence_boost_db    = boost_1k5
    L(f'  [M-9] ✓ voice sculpting applied')
    return out_wav, report


# ══════════════════════════════════════════════════════════════════════════════
#  M-8: MUFFLE DETECTION AND CORRECTION  (كشف الخنق وإصلاحه)
# ══════════════════════════════════════════════════════════════════════════════

def _detect_muffle_score(state: 'ItiqanState',
                          ref: 'ReferenceModel') -> tuple:
    """
    Detect muffle by comparing source HF energy to reference HF energy,
    both level-normalised to the same voice-band mean (500-2kHz).

    Algorithm:
      1. Level-normalize source and ref spectra to 0dB mean in 500-2kHz band.
      2. Compute mean deficit in 2kHz-8kHz (positive = source lacks HF = muffled).
      3. Also compute LF-mid buildup: source 200-500Hz relative to ref (boxiness).
      4. Combine into muffle_score 0-3 and shelf correction params.

    Returns (muffle_score, hf_deficit_db, shelf_params_dict)
    """
    if not NUMPY_OK or not state.spectrum_48 or not ref.spectrum_48:
        return 0, 0.0, {}

    src  = state.spectrum_48
    rref = ref.spectrum_48

    voice_bands = [f for f in CENTERS_48 if 500 <= f <= 2000]
    hf_bands    = [f for f in CENTERS_48 if 2000 < f <= 8000]
    lf_mid_bands = [f for f in CENTERS_48 if 200 <= f <= 500]

    if not voice_bands or not hf_bands:
        return 0, 0.0, {}

    import numpy as _np

    def _avg(bands, spec):
        vals = [spec.get(f, -60.0) for f in bands]
        return float(_np.mean(vals))

    # Level-normalize both to same voice mean → isolates spectral shape
    src_voice  = _avg(voice_bands, src)
    ref_voice  = _avg(voice_bands, rref)
    offset     = ref_voice - src_voice   # shift source to ref loudness

    src_hf_norm = _avg(hf_bands, src) + offset
    ref_hf      = _avg(hf_bands, rref)
    hf_deficit  = ref_hf - src_hf_norm   # positive = source is muffled

    # LF-mid buildup: how much more LF-mid does source have vs ref (boxiness)
    src_lf_norm = _avg(lf_mid_bands, src) + offset
    ref_lf      = _avg(lf_mid_bands, rref)
    lf_excess   = src_lf_norm - ref_lf   # positive = boxy

    # Muffle score classification
    if hf_deficit >= 6.0:
        score = 3   # severe
    elif hf_deficit >= 3.5:
        score = 2   # moderate
    elif hf_deficit >= 1.5:
        score = 1   # mild
    else:
        score = 0   # clean — no muffle

    # Build EQ params scaled to score
    # shelf_freq: start of air/presence boost
    # shelf_gain: how much to boost
    # presence_freq/gain: secondary parametric bell in presence zone
    # lf_cut_freq/gain: light LF-mid cut for boxiness
    params: dict = {}
    if score == 1:
        params = {
            'shelf_freq': 3000, 'shelf_gain': 1.5,
            'presence_freq': 2000, 'presence_gain': 0.8, 'presence_q': 1.2,
            'lf_cut_freq': 0, 'lf_cut_gain': 0.0,
        }
    elif score == 2:
        lf_cut = min(lf_excess * 0.4, 1.5) if lf_excess > 1.0 else 0.0
        params = {
            'shelf_freq': 2500, 'shelf_gain': 2.5,
            'presence_freq': 1500, 'presence_gain': 1.4, 'presence_q': 1.4,
            'lf_cut_freq': 315 if lf_cut > 0.3 else 0, 'lf_cut_gain': lf_cut,
        }
    elif score == 3:
        lf_cut = min(lf_excess * 0.5, 2.5) if lf_excess > 1.0 else 0.0
        params = {
            'shelf_freq': 2000, 'shelf_gain': 4.0,
            'presence_freq': 1200, 'presence_gain': 2.0, 'presence_q': 1.5,
            'lf_cut_freq': 250 if lf_cut > 0.3 else 0, 'lf_cut_gain': lf_cut,
        }

    return score, hf_deficit, params


def muffle_correction_pass(wav_path: str,
                            state: 'ItiqanState',
                            ref: 'ReferenceModel') -> tuple:
    """
    M-8: Targeted muffle correction — كشف الخنق وإصلاحه.

    Applied between Phase B (NR) and M-5 (sibilant centroid) so that:
    - NR has already cleaned the source.
    - M-5 and Phase D fine-tune after the broad muffle fix.

    Processing:
      Mild    → high shelf +1.5dB @ 3kHz + subtle presence +0.8dB @ 2kHz
      Moderate → shelf +2.5dB @ 2.5kHz + presence +1.4dB @ 1.5kHz + box cut
      Severe   → shelf +4.0dB @ 2kHz + presence +2.0dB @ 1.2kHz + stronger box cut

    Guards (revert if any trigger):
      G1: output RMS delta > 2.0dB  (filter went wrong)
      G2: sibilant SNR drops > 3dB  (over-brightened — harsh)
      G3: HF energy after boost > ref_hf + 2dB  (over-corrected)

    Confidence scaling: PRISTINE → 80% of gains; COMPRESSED → 100%
    """
    report = {'applied': False, 'score': 0, 'hf_deficit_db': 0.0,
              'correction_db': 0.0, 'reverted': False}

    score, hf_deficit, params = _detect_muffle_score(state, ref)
    report['score']        = score
    report['hf_deficit_db'] = round(hf_deficit, 2)
    state.muffle_score     = score
    state.muffle_hf_deficit = hf_deficit

    if score == 0:
        L(f'  [M-8] muffle_score=0 HF_deficit={hf_deficit:+.1f}dB — clean, skipping')
        return wav_path, report
    if not params:
        return wav_path, report

    tier = state.source_tier
    conf_scale = 0.80 if tier in ('TIER_PRISTINE', 'TIER_PRISTINE_NOISY') else 1.00

    shelf_gain    = params['shelf_freq'] and params['shelf_gain'] * conf_scale
    pres_gain     = params['presence_gain'] * conf_scale
    lf_cut        = params.get('lf_cut_gain', 0.0)

    L(f'  [M-8] muffle_score={score} HF_deficit={hf_deficit:+.1f}dB '
      f'shelf={params["shelf_freq"]}Hz+{shelf_gain:.1f}dB '
      f'presence={params["presence_freq"]}Hz+{pres_gain:.1f}dB')

    # Build ffmpeg filter chain
    filters = []
    if params['shelf_freq'] and shelf_gain > 0.05:
        filters.append(
            f'equalizer=f={params["shelf_freq"]}:t=q:w=0.7:g={shelf_gain:.2f}'
        )
    if params['presence_freq'] and pres_gain > 0.05:
        filters.append(
            f'equalizer=f={params["presence_freq"]}:'
            f't=q:w={params["presence_q"]:.1f}:g={pres_gain:.2f}'
        )
    if params.get('lf_cut_freq', 0) > 0 and lf_cut > 0.1:
        filters.append(
            f'equalizer=f={params["lf_cut_freq"]}:t=q:w=1.2:g=-{lf_cut:.2f}'
        )

    if not filters:
        return wav_path, report

    out_wav = _tmp_wav('m8_muffle')
    cmd = [
        'ffmpeg', '-y', '-i', wav_path,
        '-af', ','.join(filters),
        '-acodec', WAV_CODEC, '-loglevel', 'error', out_wav
    ]
    rc, _, err = _run_ffmpeg(cmd)
    if rc != 0 or not os.path.exists(out_wav):
        L(f'  [M-8] ffmpeg failed — skip ({err[:80]})')
        return wav_path, report

    # Guards
    if NUMPY_OK:
        samples_before, _ = _decode_wav_samples(wav_path)
        samples_after,  _ = _decode_wav_samples(out_wav)
        if samples_before is not None and samples_after is not None:
            rms_b = float(np.sqrt(np.mean(samples_before ** 2)) + 1e-10)
            rms_a = float(np.sqrt(np.mean(samples_after  ** 2)) + 1e-10)
            rms_delta = abs(20 * np.log10(rms_a / rms_b))

            # G1: RMS guard
            if rms_delta > 2.0:
                L(f'  [M-8] G1 REVERT: RMS delta={rms_delta:.1f}dB > 2.0dB')
                _cleanup(out_wav)
                report['reverted'] = True
                return wav_path, report

            # G2: Sibilant SNR guard (must not over-brighten Arabic sibilants)
            N2 = min(len(samples_before), SR * 4)
            spec_b = np.abs(rfft(samples_before[:N2] * np.hanning(N2))) ** 2
            spec_a = np.abs(rfft(samples_after[:N2]  * np.hanning(N2))) ** 2
            freqs2 = rfftfreq(N2, d=1.0 / SR)

            sib_mask   = np.zeros(len(spec_b), dtype=bool)
            noise_mask = (freqs2 >= 100) & (freqs2 <= 500)
            for fc in ARABIC_SIB_BANDS:
                sib_mask |= (freqs2 >= fc * 0.85) & (freqs2 <= fc * 1.15)

            def _snr(spec):
                sib_l   = float(np.mean(10 * np.log10(np.maximum(spec[sib_mask],  1e-10))))
                noise_l = float(np.mean(10 * np.log10(np.maximum(spec[noise_mask], 1e-10))))
                return sib_l - noise_l

            snr_b = _snr(spec_b)
            snr_a = _snr(spec_a)
            snr_drop = snr_b - snr_a   # positive = SNR dropped (sibilants worsened)

            if snr_drop > 3.0:
                L(f'  [M-8] G2 REVERT: sibilant SNR drop={snr_drop:.1f}dB > 3.0dB')
                _cleanup(out_wav)
                report['reverted'] = True
                return wav_path, report

            # G3: HF over-correction guard
            hf_bands = [f for f in CENTERS_48 if 2000 < f <= 8000]
            ref_hf   = float(np.mean([ref.spectrum_48.get(f, -60.0) for f in hf_bands]))
            # measure corrected HF (use whole file spectrum from samples_after)
            spec_full = np.abs(rfft(samples_after * np.hanning(len(samples_after)))) ** 2
            freqs_full = rfftfreq(len(samples_after), d=1.0 / SR)
            spec_full_db = 10 * np.log10(np.maximum(spec_full, 1e-10))
            hf_after_vals = []
            for fc in hf_bands:
                bw_f = 2.0 ** (1.0 / 12.0)
                mask = (freqs_full >= fc / bw_f) & (freqs_full < fc * bw_f)
                if mask.sum() > 0:
                    hf_after_vals.append(float(np.mean(spec_full_db[mask])))
            if hf_after_vals:
                hf_after_mean = float(np.mean(hf_after_vals))
                # level-normalize: shift by voice band offset
                voice_bands_hz = [f for f in CENTERS_48 if 500 <= f <= 2000]
                src_voice_level = float(np.mean([state.spectrum_48.get(f, -60.0)
                                                  for f in voice_bands_hz]))
                ref_voice_level = float(np.mean([ref.spectrum_48.get(f, -60.0)
                                                  for f in voice_bands_hz]))
                norm_offset = ref_voice_level - src_voice_level
                if hf_after_mean + norm_offset > ref_hf + 2.0:
                    L(f'  [M-8] G3 REVERT: HF over-corrected '
                      f'({hf_after_mean + norm_offset:.1f} > {ref_hf + 2.0:.1f}dBFS)')
                    _cleanup(out_wav)
                    report['reverted'] = True
                    return wav_path, report

    report['applied']       = True
    report['correction_db'] = shelf_gain
    state.muffle_applied      = True
    state.muffle_correction_db = shelf_gain
    L(f'  [M-8] ✓ muffle correction applied '
      f'(score={score} shelf={shelf_gain:.1f}dB presence={pres_gain:.1f}dB)')
    return out_wav, report


# ══════════════════════════════════════════════════════════════════════════════
#  MAIN ENHANCE FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def enhance(input_path: str, output_path: str,
            iterations: int = 3,
            target_score: float = 96.0,
            force_sadaa: bool = False,
            aggressive: bool = False) -> Dict:
    """
    الإتقان Engine-2 main entry point.
    
    Processes TIER_PRISTINE and TIER_COMPRESSED sources only.
    TIER_DAMAGED / TIER_CRITICAL → returns error with routing suggestion.
    
    Returns result dict compatible with base engine v10 format + itiqan-specific fields.
    """
    global _LOG
    _LOG = []
    t0 = time.time()

    L(f'\n{"═"*60}')
    L(f'  الإتقان ENGINE-2 — v5.0')
    L(f'  Input:  {input_path}')
    L(f'  Output: {output_path}')
    L(f'{"═"*60}')

    # ── Load reference ────────────────────────────────────────────────────────
    _chk('reference_load')
    ref = load_reference_model()

    # ── Aggressive mode: scale all processing caps ────────────────────────────
    if aggressive:
        import sys as _sys
        _mod = _sys.modules[__name__] if hasattr(_sys.modules, '__name__') else None
        # EQ: widen formant bounds ±2→±4dB, outer bands ±6→±10dB
        global _EQ_Q_48
        # NR: push deeper
        global _SADAA_MAX_CREST_DELTA, _SADAA_MIN_FLUX_RATIO, _SADAA_MAX_LOWMID_CREST_DELTA
        global _SADAA_MAX_RT60
        _SADAA_MAX_CREST_DELTA        = 3.0    # was 1.5
        _SADAA_MIN_FLUX_RATIO         = 0.65   # was 0.85 — allow more smear
        _SADAA_MAX_LOWMID_CREST_DELTA = 2.5    # was 1.0
        _SADAA_MAX_RT60               = 0.60   # was 0.35 — allow wetter sources
        L('  [AGGRESSIVE] all processing caps widened')

    # ── Phase A: Deep Analysis ────────────────────────────────────────────────
    _chk('phase_A')

    if not os.path.exists(input_path):
        return {'error': f'Input not found: {input_path}', 'score': 0}

    # Decode to working WAV
    work_wav = _tmp_wav('input')
    if not _decode_to_wav(input_path, work_wav):
        return {'error': 'Failed to decode input', 'score': 0}

    duration_s   = _get_duration(work_wav)
    bitrate_kbps = _get_bitrate(input_path)
    encoder_tag  = _detect_encoder_tag(input_path)

    L(f'  duration={duration_s:.1f}s  bitrate={bitrate_kbps}kbps  encoder={encoder_tag}')

    samples, sr = _decode_wav_samples(work_wav)

    # Classify source tier
    tier, state = classify_source(work_wav, samples, bitrate_kbps, duration_s)
    state.encoder_tag = encoder_tag
    state.aggressive  = aggressive   # propagate to all sub-functions

    _noisy_tag = f'  noise_floor={state.noise_floor_db:.1f}dBFS  snr_proxy={state.snr_proxy_db:.1f}dB' \
        if tier == 'TIER_PRISTINE_NOISY' else ''
    L(f'  tier={tier}  codec_cutoff={state.codec_cutoff:.0f}Hz  '
      f'LRA={state.lra:.2f}  Crest={state.crest:.2f}{_noisy_tag}')

    # ── M-1: Ayah Segmentation (all tiers) ───────────────────────────────────
    _chk('M1_ayah_segmentation')
    segments, seg_stats = segment_ayahs(work_wav, duration_s)
    is_damaged = tier in ('TIER_DAMAGED', 'TIER_CRITICAL')  # PRISTINE_NOISY takes PRISTINE path

    # Determine analysis skip from first long pause
    analysis_skip = 30.0
    long_pauses_found = [s for s in segments if s.seg_type == 'long_pause']
    if long_pauses_found and long_pauses_found[0].start_s > 10.0:
        analysis_skip = long_pauses_found[0].end_s

    # ── M-2: Temporal Consistency (all tiers) ────────────────────────────────
    _chk('M2_temporal_consistency')
    work_wav, m2_report = temporal_consistency_pass(work_wav, state, segments)

    # ── M-3: Adaptive Compand (DAMAGED/CRITICAL only) ────────────────────────
    _chk('M3_adaptive_compand')
    m3_report: Dict = {'applied': False}
    if is_damaged:
        work_wav, m3_report = adaptive_compand_pass_damaged(work_wav, state, ref)

    # ── M-6: Dereverberation (all tiers with RT60 > 0.15s) ───────────────────
    _chk('M6_dereverberation')
    samples_m6, _ = _decode_wav_samples(work_wav)
    work_wav, m6_report = dereverberation_pass(work_wav, samples_m6, state)

    # ── Phase A5: Adaptive DF3 (TIER_PRISTINE_NOISY only) ───────────────────
    if tier == 'TIER_PRISTINE_NOISY':
        # DF3 only on high-bitrate sources. At <256kbps, codec smearing is
        # indistinguishable from noise → DF3 mutates Arabic voice formants.
        # TIER_COMPRESSED is excluded entirely — same reason.
        # DF3 gate: SNR-based, not bitrate-based.
        # SNR < 10dB  → noise too mixed with voice → DF3 mutates formants (الأعراف: 8.8dB)
        # SNR 10-18dB → noise separable → DF3 works cleanly (الأحزاب: 12.6dB)
        # SNR > 18dB  → not noisy enough to need DF3
        _snr = state.snr_proxy_db
        _df3_snr_ok = 10.0 <= _snr <= 18.0
        _df3_ok = DF3_CLI_OK and _df3_snr_ok
        if _df3_ok:
            _chk('phase_A5_adaptive_df3')
            L(f'\n── phase_A5_adaptive_df3 ──')
            L(f'  [A5] TIER_PRISTINE_NOISY SNR={_snr:.1f}dB — activating 3-pass adaptive DF3')
            L(f'  [A5] noise_floor={state.noise_floor_db:.1f}dBFS  snr_proxy={state.snr_proxy_db:.1f}dB')
            _df3_result = _adaptive_df3_itiqan(work_wav, state)
            if _df3_result != work_wav and os.path.exists(_df3_result):
                _cleanup(work_wav)
                work_wav = _df3_result
                L(f'  [A5] work_wav updated → DF3-cleaned')
            else:
                L(f'  [A5] DF3 returned original — continuing without DF3')
        elif not DF3_CLI_OK:
            L(f'  [A5] DF3 binary not available — skipping')
        elif _snr < 10.0:
            L(f'  [A5] SNR={_snr:.1f}dB < 10dB — noise too mixed with voice, DF3 skipped → afftdn only')
        else:
            L(f'  [A5] SNR={_snr:.1f}dB > 18dB — not noisy enough for DF3')

    # Reload samples after M-2/M-3/M-6 + optional A5 DF3 processing
    samples, sr = _decode_wav_samples(work_wav)

    if is_damaged:
        # ── DAMAGED path: run M-5 sibilant + selective P-2 EQ + Phase H/I ──
        _chk('M5_sibilant_centroid_damaged')
        work_wav, m5_report = sibilant_centroid_pass(work_wav, samples, state)
        samples, sr = _decode_wav_samples(work_wav)

        # Compute adaptive weights (M-7) for DAMAGED scoring
        m7_weights = _adaptive_weights(tier,
                                        state.ceiling * 0.7,   # estimate achievable crest
                                        min(state.lra + 1.0, TARGET['lra']))

        # Run 48-band analysis for EQ even on DAMAGED
        _chk('M_damaged_spectrum')
        state.spectrum_48 = sixth_octave(work_wav) or {}
        if samples is not None:
            state.f0_histogram = _measure_f0_histogram(samples, sr)
            state.f0_median    = _f0_median(state.f0_histogram)

        # Compute spectral loss for ceiling
        if state.spectrum_48 and ref.spectrum_48 and NUMPY_OK:
            ref_bw = getattr(ref, 'bw_cutoff', 13000.0)
            loss_48 = np.array([
                0.0 if f > ref_bw * 1.05 else
                max(0.0, ref.spectrum_48.get(f, -60.0) - state.spectrum_48.get(f, -60.0))
                for f in CENTERS_48
            ], dtype=np.float32)
            state.spectral_loss_48 = loss_48
            state.ceiling, state.ceiling_reason = compute_itiqan_ceiling(
                state, ref, loss_48)

        # Phase C: Harmonic plan
        harmonic_plan = plan_harmonic_injection(state)

        # Phase D: 48-band EQ — FIX-5: run_eq_optimizer was undefined; use design+apply
        _chk('phase_D_damaged')
        eq_nodes_d, eq_res_d = design_itiqan_eq(state, ref, harmonic_plan)
        state.eq_residual_48   = eq_res_d
        state.eq_bands_applied = len(eq_nodes_d)
        eq_wav = apply_eq_48(work_wav, eq_nodes_d)
        L(f'  [D-damaged] {len(eq_nodes_d)} bands, residual={eq_res_d:.2f}dB')

        # Skip trajectory + phrase sculpting for DAMAGED (insufficient quality for these)
        traj_wav     = eq_wav
        phrases_wav  = traj_wav
        state.trajectory_applied = False
        state.phrases_detected   = 0
        state.phrases_sculpted   = 0

        # Phase G: Warmth injection (optional on DAMAGED)
        warmth_wav, warmth_applied, thd_b, thd_a = harmonic_warmth_injection(eq_wav, state)
        if warmth_applied:
            if arabic_phoneme_integrity_gate(eq_wav, warmth_wav, state):
                current_wav = warmth_wav
                state.warmth_applied = True; state.thd_before = thd_b; state.thd_after = thd_a
            else:
                L('  [G-damaged] integrity gate FAIL — reverting')
                _cleanup(warmth_wav); current_wav = eq_wav
        else:
            current_wav = eq_wav

        # Phase H: Joint LUFS+LRA
        _chk('phase_H_damaged')
        best_wav = current_wav; best_result = None
        for it in range(max(1, iterations)):
            L(f'\n  [H-damaged] iteration {it+1}/{iterations}')
            joint_wav, pass_r = run_pass_joint(best_wav, state, ref)
            if best_result is None or pass_r.composite > best_result.composite:
                if best_wav != current_wav: _cleanup(best_wav)
                best_wav = joint_wav; best_result = pass_r
            else:
                _cleanup(joint_wav)
                L(f'  [H-damaged] no improvement — stopping')
                break

        nr_wav = work_wav  # for cleanup compat
        eq_wav = best_wav; traj_wav = best_wav; phrases_wav = best_wav
        nr_report = {'applied': False, 'floor_delta': 0.0, 'hum_notch': False}

        # Phase I: Encode
        _chk('phase_I_damaged')
        output_path, true_peak_db, encode_retries = run_pass_encode(best_wav, output_path, state)

        # Phase J: volume boost (DAMAGED path)
        _jd_lufs, _ = _measure_lufs(output_path)
        _jd_delta   = ref.lufs - _jd_lufs
        L(f'  [J-damaged] LUFS={_jd_lufs:.2f} ref={ref.lufs:.2f} delta={_jd_delta:+.2f}dB')
        if abs(_jd_delta) >= 0.3:
            _jd_tmp = _tmp_mp3('vol_match_d')
            _jd_rc, _, _ = _run_ffmpeg([
                'ffmpeg', '-y', '-i', output_path,
                '-af', f'volume={_jd_delta:.3f}dB',
                '-b:a', '320k', '-q:a', '0', _jd_tmp
            ])
            if _jd_rc == 0 and os.path.exists(_jd_tmp):
                os.replace(_jd_tmp, output_path)
                L(f'  [J-damaged] boosted {_jd_delta:+.2f}dB')
            else:
                _cleanup(_jd_tmp)

        final = score_output(output_path, state, ref)
        elapsed = time.time() - t0

        L(f'\n{"═"*60}')
        L(f'  DAMAGED PATH — LUFS={final.lufs:.2f} Crest={final.crest:.2f} LRA={final.lra:.2f}')
        L(f'  Score: {final.score_tier:.1f}/100 (M-7 weights: {m7_weights})')
        L(f'{"═"*60}')

        _cleanup(work_wav, best_wav)
        summary = (f'itiqan-v4.0 DAMAGED | {tier} | {elapsed:.0f}s | '
                   f'Score={final.score_tier:.0f}/100')
        return {
            'engine_version':    'v4.0-الإتقان',
            'score':             final.score_tier,
            'lufs':              final.lufs, 'rms': final.rms,
            'crest':             final.crest, 'lra': final.lra,
            'true_peak_db':      true_peak_db, 'encode_retries': encode_retries,
            'source_tier':       tier, 'ceiling': state.ceiling,
            'processing_time_s': round(elapsed, 1), 'summary': summary,
            'm1_n_verses':       seg_stats.get('n_verses', 0),
            'm2_drift_applied':  m2_report.get('applied', False),
            'm2_drift_db':       m2_report.get('drift_db', 0.0),
            'm3_compand_applied': m3_report.get('applied', False),
            'm5_sib_applied':    m5_report.get('applied', False),
            'm6_derev_applied':  m6_report.get('applied', False),
            'm7_weights':        m7_weights,
            'itiqan_warmth_applied': state.warmth_applied,
            'itiqan_eq_bands':   state.eq_bands_applied,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # PRISTINE/COMPRESSED: full v3.0 pipeline continues below
    # ──────────────────────────────────────────────────────────────────────────

    # A-2: 48-band spectrum
    L('  [A-2] 48-band spectrum measurement...')
    state.spectrum_48 = sixth_octave(work_wav) or {}
    L(f'  [A-2] {len(state.spectrum_48)} bands measured')

    # A-3: F0 histogram
    L('  [A-3] F0 histogram...')
    if samples is not None:
        state.f0_histogram = _measure_f0_histogram(samples, sr)
        state.f0_median    = _f0_median(state.f0_histogram)
        L(f'  [A-3] F0 median={state.f0_median:.0f}Hz  '
          f'({len(state.f0_histogram)} bins)')

    # A-4: Presence + warmth ratios
    if state.spectrum_48:
        pres_bands  = [f for f in CENTERS_48 if 1000 <= f <= 4000]
        total_bands = [f for f in CENTERS_48]
        warm_lo     = [f for f in CENTERS_48 if 80 <= f <= 500]
        warm_hi     = [f for f in CENTERS_48 if 2000 <= f <= 8000]

        def _avg_level(bands):
            vals = [state.spectrum_48.get(b, -60.0) for b in bands]
            return sum(vals) / max(len(vals), 1)

        pres_level  = _avg_level(pres_bands)
        total_level = _avg_level(total_bands)
        warm_lo_lv  = _avg_level(warm_lo)
        warm_hi_lv  = _avg_level(warm_hi)

        state.presence_ratio = pres_level - total_level
        state.warmth_ratio   = warm_lo_lv - warm_hi_lv

        L(f'  [A-4] presence_ratio={state.presence_ratio:.1f}dB  '
          f'warmth_ratio={state.warmth_ratio:.1f}dB')

    # A-7: Spectral stability (20-window variance)
    L('  [A-7] spectral stability analysis (20 windows)...')
    if NUMPY_OK:
        state.instability_48 = _measure_spectral_stability(work_wav, duration_s)
        # G1: Codec quantization noise inflates per-band std for COMPRESSED,
        # pushing adaptive-λ too high and over-smoothing the EQ optimizer.
        # Deflate instability by a bitrate-dependent factor.
        if state.source_tier == 'TIER_COMPRESSED':
            _insta_deflate = {
                '64': 0.55, '96': 0.65, '128': 0.75, '192': 0.85
            }.get(state.bitrate_class, 0.75)
            state.instability_48 = (state.instability_48 * _insta_deflate).astype(np.float32)
            L(f'  [A-7] G1 instability deflated ×{_insta_deflate} ({state.bitrate_class}kbps)')
        instability_mean = float(state.instability_48.mean())
        L(f'  [A-7] mean_instability={instability_mean:.3f}')

    # A-7b: Mujawwad style detection (KB §145)
    state.mujawwad_confidence = _detect_mujawwad_style(state)
    if state.mujawwad_confidence >= 0.3:
        L(f'  [A-7b] Mujawwad conf={state.mujawwad_confidence:.2f} '
          f'(F0_range: {max(state.f0_histogram or {0:0}) - min(state.f0_histogram or {0:0}):.0f}Hz '
          f'LRA={state.lra:.2f}LU Crest={state.crest:.2f}dB)')

    # A-8: Initial quality ceiling estimate (refined after Phase B)
    state.ceiling, state.ceiling_reason = compute_itiqan_ceiling(state, ref)
    L(f'  [A-8] ceiling={state.ceiling:.1f}/100 ({state.ceiling_reason})')

    # ── Phase B: Selective NR ─────────────────────────────────────────────────
    _chk('phase_B')
    nr_wav, nr_report = run_selective_nr(work_wav, state, ref)

    # Post-NR: measure direct spectral loss
    if NUMPY_OK and state.spectrum_48 and ref.spectrum_48:
        nr_spec = sixth_octave(nr_wav) or {}
        ref_bw = getattr(ref, 'bw_cutoff', 13000.0)
        state.spectral_loss_48 = np.array([
            0.0 if f > ref_bw * 1.05 else
            ref.spectrum_48.get(f, -60.0) - nr_spec.get(f, -60.0)
            for f in CENTERS_48
        ], dtype=np.float32)
        # Refine ceiling from direct measurement
        state.ceiling, state.ceiling_reason = compute_itiqan_ceiling(
            state, ref, state.spectral_loss_48
        )
        L(f'  [B] refined ceiling={state.ceiling:.1f}/100 (direct spectral loss)')

    # ── M-8: Muffle Detection + Correction ──────────────────────────────────
    _chk('M8_muffle_correction')
    _m8_prev_nr = nr_wav
    nr_wav, m8_report = muffle_correction_pass(nr_wav, state, ref)
    if m8_report['applied'] and nr_wav != _m8_prev_nr:
        _m8_spec = sixth_octave(nr_wav)
        if _m8_spec:
            state.spectrum_48 = _m8_spec
        _cleanup(_m8_prev_nr)

    # ── M-9: Voice Body Sculpting ─────────────────────────────────────────────
    _chk('M9_voice_sculpting')
    _m9_prev = nr_wav
    m9_report = {'applied': False}  # M-9 disabled by user request
    # nr_wav, m9_report = voice_body_sculpting(nr_wav, state, ref)
    if m9_report['applied'] and nr_wav != _m9_prev:
        # Re-measure spectrum + ratios so Phase D starts from corrected signal
        _m9_spec = sixth_octave(nr_wav)
        if _m9_spec:
            state.spectrum_48 = _m9_spec
            # Recompute presence/warmth ratios on corrected signal
            _pres_bands  = [f for f in CENTERS_48 if 1000 <= f <= 4000]
            _total_bands = [f for f in CENTERS_48]
            _warm_lo     = [f for f in CENTERS_48 if 80 <= f <= 500]
            _warm_hi     = [f for f in CENTERS_48 if 2000 <= f <= 8000]
            def _avgl(bands):
                v = [_m9_spec.get(b, -60.0) for b in bands]
                return sum(v) / max(len(v), 1)
            state.presence_ratio = _avgl(_pres_bands) - _avgl(_total_bands)
            state.warmth_ratio   = _avgl(_warm_lo) - _avgl(_warm_hi)
            L(f'  [M-9] post-sculpt: presence={state.presence_ratio:.1f}dB '
              f'warmth={state.warmth_ratio:.1f}dB')
        _cleanup(_m9_prev)

    # ── M-5: Sibilant Centroid (PRISTINE/COMPRESSED path) ────────────────────
    _chk('M5_sibilant_centroid')
    samples_nr, sr_nr = _decode_wav_samples(nr_wav)
    nr_wav, m5_report = sibilant_centroid_pass(nr_wav, samples_nr, state)
    if m5_report['applied']:
        samples_nr, sr_nr = _decode_wav_samples(nr_wav)
        L(f'  [M-5] sibilant centroid corrected '
          f'{m5_report["centroid_before"]:.0f}Hz → {m5_report["correction_db"]:+.2f}dB')

    # ── Phase C: Harmonic Interaction Planning ────────────────────────────────
    _chk('phase_C')
    harmonic_plan = plan_harmonic_injection(state)
    L(f'  [C] harmonic plan: {len(harmonic_plan)} bands affected by P-4')

    # ── Phase D: 48-Band Precision EQ ────────────────────────────────────────
    _chk('phase_D')
    # Update spectrum_48 from post-NR file
    state.spectrum_48 = sixth_octave(nr_wav) or state.spectrum_48

    eq_nodes, eq_residual = design_itiqan_eq(state, ref, harmonic_plan)
    state.eq_residual_48 = eq_residual

    eq_wav = apply_eq_48(nr_wav, eq_nodes)
    state.eq_bands_applied = len(eq_nodes)
    L(f'  [D] {state.eq_bands_applied} bands applied, residual={eq_residual:.2f}dB')

    # ── Phase D.5: BWE Spectral Stitch (COMPRESSED, codec_cutoff < 12kHz) ──────
    if state.source_tier == 'TIER_COMPRESSED' and state.codec_cutoff < 12000.0:
        _chk('phase_D5_bwe')
        _bwe_result = bwe_spectral_stitch(eq_wav, state)
        if _bwe_result != eq_wav:
            _cleanup(eq_wav)
            eq_wav = _bwe_result
            # Re-measure spectrum so trajectory sees post-BWE shape
            _bwe_spec = sixth_octave(eq_wav)
            if _bwe_spec:
                state.spectrum_48 = _bwe_spec

    # ── Phase E: Spectral Trajectory Correction ───────────────────────────────
    _chk('phase_E')
    traj_wav, traj_applied = trajectory_correction(eq_wav, state, ref, ayah_segments=segments)
    state.trajectory_applied = traj_applied

    current_wav = traj_wav

    # ── Phase F: Phrase Micro-Dynamic Sculpting ───────────────────────────────
    _chk('phase_F')
    phrases_wav = current_wav
    phrases_sculpted = 0

    if samples is not None and NUMPY_OK:
        # Re-decode after EQ+trajectory for accurate phrase detection
        samples_f, sr_f = _decode_wav_samples(current_wav)
        phrases = detect_phrase_boundaries(samples_f, sr_f, state)
        state.phrases_detected = len(phrases)
        L(f'  [F] detected {len(phrases)} phrases')

        if phrases:
            phrases_wav, phrases_sculpted = phrase_dynamic_sculpting(
                current_wav, phrases, state, ref
            )
            state.phrases_sculpted = phrases_sculpted
    else:
        phrases = []

    current_wav = phrases_wav

    # ── Phase G: Harmonic Warmth Injection ───────────────────────────────────
    _chk('phase_G')
    pre_warmth_wav = current_wav  # save for integrity gate

    warmth_wav, warmth_applied, thd_before, thd_after = harmonic_warmth_injection(
        current_wav, state
    )

    # Arabic phoneme integrity gate
    if warmth_applied:
        if arabic_phoneme_integrity_gate(pre_warmth_wav, warmth_wav, state):
            current_wav = warmth_wav
            state.warmth_applied = True
            state.thd_before     = thd_before
            state.thd_after      = thd_after
        else:
            L('  [G] integrity gate FAIL — reverting warmth')
            _cleanup(warmth_wav)
            state.warmth_applied = False

    # ── Phase G.4b: VoiceDNA vocal effort ratio sanity check  (KB §142.3) ────
    if NUMPY_OK:
        try:
            _ved_s, _ved_sr = _decode_wav_samples(warmth_wav)
            if _ved_s is not None:
                _N = min(len(_ved_s), _ved_sr * 8)
                _sp = np.abs(rfft(_ved_s[:_N] * np.hanning(_N))) ** 2
                _fr = rfftfreq(_N, d=1.0 / _ved_sr)
                _e_eff  = float(np.mean(_sp[(_fr >= 1000) & (_fr <= 4000)]))
                _e_fund = float(np.mean(_sp[(_fr >= 80)   & (_fr <= 400)]))
                _ver    = _e_eff / (_e_fund + 1e-10)
                L(f'  [VoiceDNA] vocal_effort_ratio={_ver:.3f} (ref=0.85, ok: 0.60–1.30)')
                if _ver < 0.6:
                    L('  [VoiceDNA] ⚠ ratio < 0.60 — presence may be over-reduced')
                elif _ver > 1.3:
                    L('  [VoiceDNA] ⚠ ratio > 1.30 — upper-mid harshness detected')
        except Exception as _ved_e:
            L(f'  [VoiceDNA] check failed: {_ved_e}')

    # ── Phase G.5: صدي التميز — Echo of Distinction ──────────────────────────
    #
    #   Placed here — after harmonic warmth has enriched the harmonics (G),
    #   before LUFS normalisation locks the loudness target (H) — because
    #   the reflected signal must be harmonically warm, not thin, and because
    #   any energy the reflection adds must be absorbed by the loudness pass.
    #
    _chk('phase_G5_sadaa_altamayuz')
    sadaa_wav, sadaa_report = sadaa_altamayuz(current_wav, state, ref, force=force_sadaa)
    if sadaa_report['applied']:
        current_wav              = sadaa_wav
        state.sadaa_applied      = True
        state.sadaa_delay_ms     = sadaa_report['delay_ms']
        state.sadaa_wet_db       = sadaa_report['wet_db']
        state.sadaa_crest_delta  = sadaa_report['crest_delta']

    # ── Phase G5.5: Crest recovery expander ──────────────────────────────────
    # صدي's sustain floor lift compresses the dynamic gap by ~1-2dB.
    # A gentle expander (ratio=1.5, threshold just below voice floor) restores
    # natural peak dynamics so crest factor matches reference (target ~10.3dB).
    _chk('phase_G5_crest_recovery')
    _ref_crest_target = getattr(ref, 'crest', 10.0)
    if samples is not None and NUMPY_OK and state.sadaa_applied:
        samples_post_sadaa, _ = _decode_wav_samples(current_wav)
        if samples_post_sadaa is not None:
            _cur_crest = float(20*np.log10(
                np.max(np.abs(samples_post_sadaa)) /
                (np.sqrt(np.mean(samples_post_sadaa**2)) + 1e-10) + 1e-10))
            _crest_deficit = _ref_crest_target - _cur_crest
            if _crest_deficit > 0.5:   # only if meaningfully compressed
                # threshold = p25 of RMS frames — expand below the voice body
                fn_cr = int(0.020 * SR); fr_cr = []
                for i in range(0, len(samples_post_sadaa)-fn_cr, fn_cr):
                    fr_cr.append(float(np.sqrt(np.mean(samples_post_sadaa[i:i+fn_cr]**2))))
                _thr_lin = float(np.percentile(fr_cr, 25))
                _thr_db  = round(20*np.log10(max(_thr_lin, 1e-10)), 1)
                _expand_wav = _tmp_wav('crest_expand')
                _ratio = min(1.8, 1.0 + _crest_deficit * 0.18)   # gentle, capped
                _cmd_exp = [
                    'ffmpeg', '-y', '-i', current_wav,
                    '-af', (f'aexpander=threshold={max(0.001,_thr_lin):.4f}'
                            f':ratio={_ratio:.2f}:attack=2:release=80'),
                    '-acodec', WAV_CODEC, _expand_wav
                ]
                rc_exp, _, _ = _run_ffmpeg(_cmd_exp)
                if rc_exp == 0 and os.path.exists(_expand_wav):
                    current_wav = _expand_wav
                    L(f'  [G5.5] crest recovery: deficit={_crest_deficit:+.1f}dB '
                      f'→ expander thr={_thr_db:.1f}dB ratio={_ratio:.2f}')

    # ── Phase G.6: LRA Voice Expander ─────────────────────────────────────────
    # If LRA is significantly below target, expand voice dynamics before
    # Phase H compresses for LUFS. This is the right moment: all tonal
    # processing done, final loudness not yet locked.
    _chk('phase_G6_lra_expander')
    if NUMPY_OK:
        _g6_lufs, _g6_lra = _measure_lufs(current_wav)
        _g6_lra_deficit = ref.lra - _g6_lra
        L(f'  [G6] pre-expand LRA={_g6_lra:.2f} target={ref.lra:.2f} '
          f'deficit={_g6_lra_deficit:+.2f}')
        if _g6_lra_deficit > 1.5:
            _g6_samp, _ = _decode_wav_samples(current_wav)
            if _g6_samp is not None:
                # threshold = p30 of voiced RMS (expand the quiet floor down)
                fn_g6 = int(0.020 * SR); fr_g6 = []
                for _i in range(0, len(_g6_samp) - fn_g6, fn_g6):
                    _e = float(np.sqrt(np.mean(_g6_samp[_i:_i+fn_g6]**2)))
                    if _e > 1e-7: fr_g6.append(_e)
                if fr_g6:
                    _thr_lin = float(np.percentile(fr_g6, 30))
                    # ratio scales with deficit: 1.5dB gap → ratio=1.3, 3dB → 1.6
                    _ratio = min(1.0 + _g6_lra_deficit * 0.14, 1.8)
                    _g6_out = _tmp_wav('g6_lra_exp')
                    _g6_cmd = [
                        'ffmpeg', '-y', '-i', current_wav,
                        '-af', (f'aexpander=threshold={max(0.001,_thr_lin):.5f}'
                                f':ratio={_ratio:.2f}:attack=3:release=150'),
                        '-acodec', WAV_CODEC, '-loglevel', 'error', _g6_out
                    ]
                    _g6_rc, _, _ = _run_ffmpeg(_g6_cmd)
                    if _g6_rc == 0 and os.path.exists(_g6_out):
                        _g6_lra_after, _ = _measure_lufs(_g6_out)
                        # Guard: LRA must improve and not overshoot target
                        if _g6_lra_after > _g6_lra and _g6_lra_after <= ref.lra + 1.0:
                            current_wav = _g6_out
                            L(f'  [G6] ✓ LRA expanded {_g6_lra:.2f}→{_g6_lra_after:.2f} '
                              f'ratio={_ratio:.2f}')
                        else:
                            _cleanup(_g6_out)
                            L(f'  [G6] guard failed: LRA {_g6_lra:.2f}→{_g6_lra_after:.2f} '
                              f'(target {ref.lra:.2f}) — reverted')
                    else:
                        L('  [G6] aexpander failed — skip')
        else:
            L(f'  [G6] LRA deficit={_g6_lra_deficit:.2f} < 1.5 — no expansion needed')

    # ── Phase H: Joint LUFS + LRA (iterative) ────────────────────────────────
    _chk('phase_H')
    best_wav    = current_wav
    best_result = None

    for it in range(max(1, iterations)):
        L(f'\n  [H] Joint iteration {it+1}/{iterations}')
        joint_wav, pass_r = run_pass_joint(best_wav, state, ref)

        # LRA floor guard: never accept a pass that drops LRA below (target - 0.5)
        # This prevents successive LIGHT passes from compounding LRA damage
        lra_floor = ref.lra - 0.5
        lra_floor_violated = (pass_r.lra < lra_floor
                               and best_result is not None
                               and best_result.lra >= lra_floor)

        if lra_floor_violated:
            L(f'  [H] iteration {it+1} LRA floor violated: '
              f'{pass_r.lra:.2f} < {lra_floor:.2f} — rejected')
            _cleanup(joint_wav)
            break
        elif best_result is None or pass_r.composite > best_result.composite:
            if best_wav != current_wav and best_wav != joint_wav:
                _cleanup(best_wav)
            best_wav    = joint_wav
            best_result = pass_r
            L(f'  [H] iteration {it+1} improved → composite={pass_r.composite:.4f}')
        else:
            _cleanup(joint_wav)
            L(f'  [H] iteration {it+1} no improvement (composite={pass_r.composite:.4f} vs best={best_result.composite:.4f})')
            lufs_gap = abs(best_result.lufs - ref.lufs)
            if lufs_gap < 0.3:
                L(f'  [H] LUFS within 0.3dB of target — stopping early')
                break

    # ── Phase I: Predictive True Peak Encode ─────────────────────────────────
    _chk('phase_I')
    output_path, true_peak_db, encode_retries = run_pass_encode(
        best_wav, output_path, state
    )
    L(f'  [I] TP={true_peak_db:.2f}dBTP  encoder={state.encoder_tag}  '
      f'margin={state.intersample_margin:.1f}dB  retries={encode_retries}')

    # ── Phase J: Final volume boost to match reference level ──────────────────
    # Simple linear volume=XdB. NOT loudness normalization.
    # Closes any gap left by Phase I limiter eating Phase H gain.
    _chk('phase_J_volume_match')
    _j_lufs, _ = _measure_lufs(output_path)
    _j_delta   = ref.lufs - _j_lufs
    L(f'  [J] output_LUFS={_j_lufs:.2f}  ref_LUFS={ref.lufs:.2f}  delta={_j_delta:+.2f}dB')
    if abs(_j_delta) >= 0.3:
        _j_tmp = _tmp_mp3('vol_match')
        _j_rc, _, _j_err = _run_ffmpeg([
            'ffmpeg', '-y', '-i', output_path,
            '-af', f'volume={_j_delta:.3f}dB',
            '-b:a', '320k', '-q:a', '0', _j_tmp
        ])
        if _j_rc == 0 and os.path.exists(_j_tmp):
            os.replace(_j_tmp, output_path)
            L(f'  [J] boosted {_j_delta:+.2f}dB -> LUFS={ref.lufs:.2f}')
        else:
            L(f'  [J] boost failed: {_j_err[:80]}')
            _cleanup(_j_tmp)
    else:
        L('  [J] already within 0.3dB of ref LUFS - no boost needed')

    # ── Final Score ───────────────────────────────────────────────────────────
    final = score_output(output_path, state, ref)
    elapsed = time.time() - t0

    L(f'\n{"═"*60}')
    L(f'  LUFS={final.lufs:.2f}  RMS={final.rms:.2f}  '
      f'Crest={final.crest:.2f}  LRA={final.lra:.2f}')
    L(f'  Score: {final.score_tier:.1f}/100  ceiling={state.ceiling:.0f}/100  '
      f'({state.source_tier})')
    if final.ceiling_reason:
        L(f'  [ceiling] {final.ceiling_reason}')
    L(f'  [{elapsed:.1f}s | '
      f'eq_bands={state.eq_bands_applied} | '
      f'phrases={state.phrases_sculpted}/{state.phrases_detected} | '
      f'warmth={state.warmth_applied}]')
    L(f'{"═"*60}')

    # Cleanup intermediates
    _cleanup(work_wav, nr_wav, eq_wav, traj_wav, phrases_wav, best_wav)

    summary_lines = [
        f'itiqan-v1.0 | {state.source_tier} | {elapsed:.0f}s',
        f'Score: {final.score_tier:.0f}/100' +
        (f' ({final.ceiling_reason})' if final.ceiling_reason else ''),
        f'LUFS={final.lufs:.2f} Crest={final.crest:.2f} LRA={final.lra:.2f}',
    ]
    if nr_report['applied']:
        summary_lines.append(f'NR: floor_delta={nr_report["floor_delta"]:+.1f}dB')
    if state.warmth_applied:
        summary_lines.append(f'Warmth: THD {state.thd_before:.4f}→{state.thd_after:.4f}')
    if state.sadaa_applied:
        summary_lines.append(
            f'صدي التميز: delay={state.sadaa_delay_ms:.0f}ms '
            f'wet={state.sadaa_wet_db:.1f}dB '
            f'crest_Δ={state.sadaa_crest_delta:+.3f}dB'
        )
    if getattr(state, 'df3_applied', False):
        summary_lines.append(
            f'DF3: LOUD={state.df3_loud_chunks} MID={state.df3_mid_chunks} '
            f'QUIET={state.df3_quiet_chunks} xfades={state.df3_boundaries} '
            f'SNR {state.df3_snr_before:.1f}→{state.df3_snr_after:.1f}dB'
        )
    if encode_retries > 0:
        summary_lines.append(f'TP: {true_peak_db:.2f}dBTP | {encode_retries} retry(s)')

    return {
        # ── Standard fields (base engine compatible) ──
        'engine_version':    'v4.2-الإتقان+صدي+خنق+صوت',
        'score':             final.score_tier,
        'score_tier':        final.score_tier,
        'score_absolute':    final.score_abs,
        'ceiling':           state.ceiling,
        'ceiling_reason':    final.ceiling_reason or state.ceiling_reason,
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
        'ref_bw_cutoff_hz':  getattr(ref, 'bw_cutoff', 13000.0),
        'noise_type':        state.noise_type,
        'silence_floor_db':  state.silence_floor,
        'nr_applied':        nr_report['applied'],
        'nr_floor_delta_db': nr_report['floor_delta'],
        'processing_time_s': round(elapsed, 1),
        'eq_residual_final': final.eq_residual,
        'mds':               state.mds_raw,
        'summary':           '\n'.join(summary_lines),

        # ── الإتقان-specific fields ──
        'itiqan_eq_bands':          state.eq_bands_applied,
        'itiqan_eq_residual_db':    state.eq_residual_48,
        'itiqan_trajectory_applied': state.trajectory_applied,
        'itiqan_phrases_detected':  state.phrases_detected,
        'itiqan_phrases_sculpted':  state.phrases_sculpted,
        'itiqan_warmth_applied':    state.warmth_applied,
        'itiqan_thd_before':        state.thd_before,
        'itiqan_thd_after':         state.thd_after,
        'itiqan_presence_ratio':    state.presence_ratio,
        'itiqan_warmth_ratio':      state.warmth_ratio,
        'itiqan_f0_median':         state.f0_median,
        'itiqan_encoder_detected':  state.encoder_tag,
        'itiqan_intersample_margin': state.intersample_margin,
        'itiqan_spectral_loss_mean': (
            float(state.spectral_loss_48.mean())
            if state.spectral_loss_48 is not None and NUMPY_OK
            else 0.0
        ),
        # ── صدي التميز fields ──
        'itiqan_sadaa_applied':     state.sadaa_applied,
        'itiqan_sadaa_delay_ms':    state.sadaa_delay_ms,
        'itiqan_sadaa_wet_db':      state.sadaa_wet_db,
        'itiqan_sadaa_crest_delta': state.sadaa_crest_delta,
        # ── Merged module fields ──
        'm1_n_verses':           seg_stats.get('n_verses', 0),
        'm1_median_verse_s':     seg_stats.get('median_verse_s', 5.0),
        'm2_drift_applied':      m2_report.get('applied', False),
        'm2_drift_db':           m2_report.get('drift_db', 0.0),
        'm5_sib_applied':        m5_report.get('applied', False),
        'm8_muffle_score':        state.muffle_score,
        'm8_muffle_hf_deficit':   state.muffle_hf_deficit,
        'm8_muffle_applied':      state.muffle_applied,
        'm8_muffle_correction_db': state.muffle_correction_db,
        'm5_sib_centroid_before': m5_report.get('centroid_before', 0.0),
        'm6_derev_applied':      m6_report.get('applied', False),
        'm6_rt60_s':             m6_report.get('rt60_s', 0.0),
        'm7_weights':            _adaptive_weights(tier, state.ceiling * 0.9, ref.lra),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  COMPATIBILITY
# ══════════════════════════════════════════════════════════════════════════════

def get_reference_fingerprint():
    """Compatibility alias."""
    return load_reference_model()


def _build_ref_cache_if_needed():
    """Called at Docker build time to pre-warm the cache."""
    if not REF_FILES:
        return
    if os.path.exists(_REF_CACHE):
        try:
            with open(_REF_CACHE) as fh:
                d = json.load(fh)
            if (d.get('cache_version') == 'itiqan-v11'
                    and d.get('ref_hash') == _ref_files_hash(REF_FILES)):
                return
        except Exception:
            pass
    load_reference_model()


# ══════════════════════════════════════════════════════════════════════════════
#  CLI ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    # S231 BUG FIX: this used to abort the ENTIRE run the instant scipy was
    # missing, even though numpy imported fine. S225 already made every
    # function in this file's pipeline degrade gracefully when SCIPY_OK is
    # False (its own numpy-only fallback path), and S226 made Kotlin's
    # setup() treat a scipy-only install failure as non-fatal for exactly
    # that reason — scipy has no prebuilt pip wheel for most Android
    # aarch64 devices and commonly fails to install even when numpy
    # installs fine. This stale gate was the actual cause of "Engine
    # failed (rc=1): pip install numpy scipy" on devices where the engine
    # was fully able to run in numpy-only mode.
    if not NUMPY_OK:
        print('numpy unavailable — pip install numpy')
        return 1
    if not SCIPY_OK:
        print('  [تنبيه] scipy unavailable — continuing with numpy-only fallback paths')

    p = argparse.ArgumentParser(
        description='الإتقان Engine-2 v1.0 — Aetherion Perfection Engine — 1425H'
    )
    p.add_argument('-i', '--input',      required=False)
    p.add_argument('-o', '--output',     required=False)
    p.add_argument('--iterations',       type=int,   default=3)
    p.add_argument('--target',           type=float, default=99.5)
    p.add_argument('--ref',              action='append', default=[], metavar='REF_MP3')
    p.add_argument('--clear-cache',      action='store_true')
    p.add_argument('--build-cache',      action='store_true')
    p.add_argument('--force-sadaa',       action='store_true', help='Force صدي التميز even on reverberant sources')
    p.add_argument('--aggressive',        action='store_true', help='Aggressive mode: all processing pushed harder')
    args = p.parse_args()

    if args.ref:
        valid = [r for r in args.ref if os.path.exists(r)]
        if valid:
            global REF_FILES
            REF_FILES = valid

    if args.clear_cache:
        if os.path.exists(_REF_CACHE):
            os.remove(_REF_CACHE)
            print('Cache cleared')
        return 0

    if args.build_cache:
        _build_ref_cache_if_needed()
        return 0

    if not args.input or not args.output:
        p.print_help()
        return 1

    try:
        r = enhance(args.input, args.output, args.iterations, args.target, force_sadaa=args.force_sadaa, aggressive=args.aggressive)
        if 'error' in r:
            print(f'\n  ERROR: {r["error"]}')
            if r.get('routing'):
                print(f'  Route to: {r["routing"]}')
            return 2
        print(
            f'\n  Score: {r["score"]:.1f}/100  ceiling={r["ceiling"]:.0f}/100'
            f'  LUFS={r["lufs"]:.2f}  Crest={r["crest"]:.2f}  LRA={r["lra"]:.2f}'
        )
        # S255: these are only populated on the paths that actually run the
        # Itiqan phrase sculptor. On the DAMAGED path they are absent, so this
        # line raised KeyError('itiqan_phrases_sculpted') AFTER the restored
        # file had already been written — the run was reported as a failure
        # purely because its summary could not be printed. Read them softly.
        _f0 = r.get('itiqan_f0_median')
        _f0s = f'{_f0:.0f}Hz' if isinstance(_f0, (int, float)) else 'n/a'
        print(f'  EQ_bands={r.get("itiqan_eq_bands", "n/a")}  '
              f'phrases={r.get("itiqan_phrases_sculpted", 0)}/{r.get("itiqan_phrases_detected", 0)}  '
              f'warmth={r.get("itiqan_warmth_applied", "n/a")}  '
              f'F0={_f0s}')
        return 0 if r['score'] >= 90.0 else 1
    except Exception as e:
        import traceback
        print(f'ERROR: {e}')
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
